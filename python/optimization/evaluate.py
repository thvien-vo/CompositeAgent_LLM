"""
evaluate.py - problem definition and batch evaluation of laminates.

Safety margin of a design = min over plies and over the active criteria of the reserve factor (RF):
    RF_max_stress (linear), RF_tsai_wu (quadratic, F12* given), RF_buckling (load factor), [RF_max_strain].
A design is feasible when margin >= safety_factor (default 1.5). An optional per-criterion divisor
(criterion_factors) reproduces formulations where a factor is built into one criterion only
(Le Riche & Haftka: lambda_cs = strain RF / 1.5, lambda_cb without factor).

Symmetric laminates use a fast exact path: with B = 0 and in-plane loads only, the laminate strain is uniform,
eps0 = A^-1 N, and A depends only on the ply counts, so ply stresses depend only on the ply angle;
D = sum of Qbar(angle) * position weight. Non-symmetric laminates use the general CLT path (A, B, D, curvature,
stresses at ply mid-height as in clt_engine.m).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import buckling, clt, failure
from .material import DEFAULT_PLY_THICKNESS, Material
from .rules import ANGLES, EMPTY, ENCODINGS, Encoding, Rules, full_laminate

CRITERION_NAMES = ("max_stress", "tsai_wu", "max_strain", "buckling")


@dataclass(frozen=True)
class Plate:
    """Simply supported rectangular plate, a along x, b along y (m)."""
    a: float = 0.5
    b: float = 0.5


@dataclass
class Problem:
    """Everything that defines one optimization problem (all SI)."""
    loads: Tuple[float, float, float]                       # (Nx, Ny, Nxy) N/m, tension +
    material: Material
    rules: Rules = field(default_factory=Rules)
    safety_factor: float = 1.5
    plate: Plate = field(default_factory=Plate)
    ply_thickness: float = DEFAULT_PLY_THICKNESS
    encoding: str = "ply"                                   # "ply" or "stack" (0_2, +-45, 90_2)
    criteria: Tuple[str, ...] = ("max_stress", "tsai_wu", "buckling")
    f12_star: float = -0.5
    buckling_model: str = "closed_form"                     # "closed_form" (spec) or "ritz" (adds Nxy)
    ritz_terms: int = 12
    buckling_modes: Optional[Tuple[int, int]] = None        # None = proven-complete mode scan
    strain_allowables: Optional[Tuple[float, float, float]] = None
    criterion_factors: Dict[str, float] = field(default_factory=dict)
    name: str = ""

    def __post_init__(self):
        self.loads = tuple(float(x) for x in self.loads)
        bad = [c for c in self.criteria if c not in CRITERION_NAMES]
        if bad:
            raise ValueError(f"unknown criteria {bad}")
        if "max_strain" in self.criteria and self.strain_allowables is None:
            raise ValueError("max_strain needs strain_allowables")
        if self.buckling_model not in ("closed_form", "ritz"):
            raise ValueError("buckling_model must be 'closed_form' or 'ritz'")

    @property
    def enc(self) -> Encoding:
        return ENCODINGS[self.encoding]

    @property
    def has_compression(self) -> bool:
        Nx, Ny, Nxy = self.loads
        return Nx < 0 or Ny < 0 or (self.buckling_model == "ritz" and Nxy != 0)

    def describe(self) -> Dict:
        return {"Nx": self.loads[0], "Ny": self.loads[1], "Nxy": self.loads[2], "material": self.material.name,
                "safety_factor": self.safety_factor, "a": self.plate.a, "b": self.plate.b,
                "ply_thickness": self.ply_thickness, "encoding": self.encoding, "criteria": list(self.criteria),
                "f12_star": self.f12_star, "buckling_model": self.buckling_model,
                "rules": {"symmetric": self.rules.symmetric, "balanced": self.rules.balanced,
                          "min_fraction": self.rules.min_fraction, "max_contiguous": self.rules.max_contiguous,
                          "n_min": self.rules.n_min, "n_max": self.rules.n_max}}


class Evaluator:
    """Batch evaluation with a cache. Counters: n_calls (designs requested), n_unique (designs analysed)."""

    def __init__(self, problem: Problem, n_genes: Optional[int] = None):
        self.p = problem
        self.enc = problem.enc
        self.Q = clt.q_matrix(problem.material.E1, problem.material.E2, problem.material.G12, problem.material.nu12)
        self.Qb = clt.qbar(self.Q, ANGLES)                                   # (4, 3, 3)
        self.Qb_ext = np.concatenate([self.Qb, np.zeros((1, 3, 3))])         # index 4 = EMPTY -> 0
        self.N = np.array(problem.loads)
        unit = self.enc.plies_per_symbol * problem.rules.multiplier()
        self.n_genes = n_genes or problem.rules.n_max // unit
        self.cache: Dict[bytes, Tuple] = {}
        self.n_calls = 0
        self.n_unique = 0
        self.factors = np.array([problem.criterion_factors.get(c, 1.0) for c in problem.criteria])

    # ------------------------------------------------------------------ public
    def evaluate(self, genes: np.ndarray) -> Dict[str, np.ndarray]:
        """Evaluate canonical design strings (P, n_genes). Returns arrays: n_plies, margin, rf (P, n_crit),
        crit (index of the governing criterion), feasible."""
        g = np.atleast_2d(np.asarray(genes, dtype=np.int8))
        self.n_calls += len(g)
        keys = [r.tobytes() for r in g]
        todo, seen = [], set()
        for i, k in enumerate(keys):
            if k not in self.cache and k not in seen:
                todo.append(i)
                seen.add(k)
        if todo:
            res = self.compute_plies(self.enc.decode(g[todo]))
            for j, i in enumerate(todo):
                self.cache[keys[i]] = (res["n_plies"][j], res["margin"][j], res["rf"][j], res["crit"][j])
            self.n_unique += len(todo)
        n = np.array([self.cache[k][0] for k in keys])
        margin = np.array([self.cache[k][1] for k in keys])
        rf = np.array([self.cache[k][2] for k in keys])
        crit = np.array([self.cache[k][3] for k in keys])
        return {"n_plies": n, "margin": margin, "rf": rf, "crit": crit,
                "feasible": margin >= self.p.safety_factor}

    def compute_plies(self, plies: np.ndarray) -> Dict[str, np.ndarray]:
        """No cache, no counters. plies: (P, W) ply codes, EMPTY padding at the start (right-aligned)."""
        plies = np.atleast_2d(plies)
        if self.p.rules.symmetric:
            return self._symmetric(plies)
        full = full_laminate(plies, False)
        if full.dtype != object:
            return self._general(full)
        out = {k: [None] * len(plies) for k in ("n_plies", "margin", "rf", "crit")}
        lens = np.array([len(r) for r in full])
        for L in np.unique(lens):
            idx = np.where(lens == L)[0]
            r = self._general(np.array([full[i] for i in idx], dtype=int))
            for k in out:
                for j, i in enumerate(idx):
                    out[k][i] = r[k][j]
        return {k: np.array(v) for k, v in out.items()}

    # ------------------------------------------------------------------ paths
    def _finish(self, n_plies, rf_strength: Dict[str, np.ndarray], D: np.ndarray):
        cols = []
        for c in self.p.criteria:
            if c == "buckling":
                cols.append(self.buckling_rf(D))
            else:
                cols.append(rf_strength[c])
        rf = np.stack(cols, axis=1) / self.factors[None, :]
        crit = np.argmin(rf, axis=1)
        return {"n_plies": n_plies, "margin": rf[np.arange(len(rf)), crit], "rf": rf, "crit": crit}

    def _strength_rf(self, stress12: np.ndarray, strain12: np.ndarray) -> Dict[str, np.ndarray]:
        out = {}
        m = self.p.material
        if "max_stress" in self.p.criteria:
            out["max_stress"] = failure.rf_max_stress(stress12, m)
        if "tsai_wu" in self.p.criteria:
            out["tsai_wu"] = failure.rf_tsai_wu(stress12, m, self.p.f12_star)
        if "max_strain" in self.p.criteria:
            out["max_strain"] = failure.rf_max_strain(strain12, self.p.strain_allowables)
        return out

    def _symmetric(self, half: np.ndarray):
        P, W = half.shape
        t = self.p.ply_thickness
        counts = np.stack([(half == k).sum(axis=1) for k in range(4)], axis=1)          # (P, 4)
        n_plies = 2 * counts.sum(axis=1)
        A = 2.0 * t * np.einsum("pk,kij->pij", counts.astype(float), self.Qb)
        eps0 = clt.midplane_strain_symmetric(A, self.N)
        strain12, stress12 = clt.ply_stress_from_strain(eps0, ANGLES, self.Q)           # (P, 4, 3)
        present = counts > 0
        rf_s = {k: np.where(present, v, np.inf).min(axis=1)
                for k, v in self._strength_rf(stress12, strain12).items()}
        j = np.arange(W)[::-1]                                     # distance index from the mid-plane
        w = 2.0 * t ** 3 * ((j + 1.0) ** 3 - j ** 3) / 3.0         # both mirrored plies
        Qp = self.Qb_ext[np.where(half >= 0, half, 4)]             # (P, W, 3, 3)
        D = np.einsum("w,pwij->pij", w, Qp)
        return self._finish(n_plies, rf_s, D)

    def _general(self, full: np.ndarray):
        P, n = full.shape
        t = np.full(full.shape, self.p.ply_thickness)
        ang = ANGLES[full]
        A, B, D = clt.abd_matrices(ang, t, self.Q)
        ABD = np.concatenate([np.concatenate([A, B], axis=2), np.concatenate([B, D], axis=2)], axis=1)
        rhs = np.broadcast_to(np.concatenate([self.N, np.zeros(3)]), (P, 6))[..., None]
        sol = np.linalg.solve(ABD, rhs)[..., 0]
        eps0, kappa = sol[:, :3], sol[:, 3:]
        z = clt.z_coordinates(t)
        zmid = (z[:, :-1] + z[:, 1:]) / 2.0
        eps_xy = eps0[:, None, :] + zmid[..., None] * kappa[:, None, :]
        strain12 = clt.strain_to_material(eps_xy, ang)
        stress12 = strain12 @ self.Q.T
        rf_s = {k: v.min(axis=1) for k, v in self._strength_rf(stress12, strain12).items()}
        return self._finish(np.full(P, n), rf_s, D)

    def buckling_rf(self, D: np.ndarray) -> np.ndarray:
        Nx, Ny, Nxy = self.p.loads
        a, b = self.p.plate.a, self.p.plate.b
        if self.p.buckling_model == "ritz":
            return buckling.ritz(D[:, 0, 0], D[:, 0, 1], D[:, 1, 1], D[:, 2, 2], Nx, Ny, Nxy, a, b,
                                 self.p.ritz_terms, self.p.ritz_terms)
        lam, _, _, _ = buckling.closed_form(D[:, 0, 0], D[:, 0, 1], D[:, 1, 1], D[:, 2, 2], Nx, Ny, a, b,
                                            self.p.buckling_modes)
        return lam


# ---------------------------------------------------------------------------------------------- details
def analyze_design(problem: Problem, full: Sequence[int]) -> Dict:
    """Detailed analysis of one design (full laminate ply codes, ply 1 first) with the general CLT path:
    per-ply RFs, critical ply / criterion, buckling mode, D16/D11, D26/D22, Ritz check (with Nxy)."""
    f = np.asarray(full, dtype=int)
    ang = ANGLES[f]
    m = problem.material
    Nx, Ny, Nxy = problem.loads
    res = clt.analyze(ang, problem.ply_thickness, m, Nx, Ny, Nxy)
    stress, strain = res["ply_stress"], res["ply_strain"]
    per_ply: Dict[str, np.ndarray] = {}
    if "max_stress" in problem.criteria:
        per_ply["max_stress"] = failure.rf_max_stress(stress, m)
    if "tsai_wu" in problem.criteria:
        per_ply["tsai_wu"] = failure.rf_tsai_wu(stress, m, problem.f12_star)
    if "max_strain" in problem.criteria:
        per_ply["max_strain"] = failure.rf_max_strain(strain, problem.strain_allowables)
    for c in per_ply:
        per_ply[c] = per_ply[c] / problem.criterion_factors.get(c, 1.0)
    D = res["D"]
    a, b = problem.plate.a, problem.plate.b
    lam_cf, mm, nn, capped = buckling.closed_form([D[0, 0]], [D[0, 1]], [D[1, 1]], [D[2, 2]], Nx, Ny, a, b,
                                                  problem.buckling_modes)
    lam_ritz = float(buckling.ritz([D[0, 0]], [D[0, 1]], [D[1, 1]], [D[2, 2]], Nx, Ny, Nxy, a, b, 20, 20)[0])
    rf = {c: float(np.min(v)) for c, v in per_ply.items()}
    crit_ply = {c: int(np.argmin(v)) + 1 for c, v in per_ply.items()}
    if "buckling" in problem.criteria:
        rf["buckling"] = float(lam_ritz if problem.buckling_model == "ritz" else lam_cf[0]) / \
            problem.criterion_factors.get("buckling", 1.0)
    governing = min(rf, key=lambda c: rf[c])
    margin = rf[governing]
    ms_ratios = failure.max_stress_ratios(stress, m)
    k = crit_ply.get(governing)
    mode = None
    if governing == "max_stress" or (governing == "tsai_wu" and k):
        mode = failure.MAX_STRESS_MODES[int(np.argmax(ms_ratios[k - 1]))]
    return {
        "n_plies": len(f), "angles": [float(x) for x in ang], "rf": rf, "margin": float(margin),
        "governing": governing, "critical_ply": k, "critical_angle": float(ang[k - 1]) if k else None,
        "max_stress_mode_in_critical_ply": mode, "critical_ply_per_criterion": crit_ply,
        "buckling_mode_mn": (int(mm[0]), int(nn[0])) if np.isfinite(lam_cf[0]) else None,
        "buckling_closed_form": float(lam_cf[0]), "buckling_ritz_with_shear": lam_ritz,
        "mode_scan_capped": bool(capped),
        "D16_over_D11": float(abs(D[0, 2]) / D[0, 0]), "D26_over_D22": float(abs(D[1, 2]) / D[1, 1]),
        "ABD": res["ABD"], "max_failure_index": res["max_failure_index"], "critical_ply_matlab_style": res["critical_ply"],
        "thickness_mm": float(len(f) * problem.ply_thickness * 1e3),
    }


def lexi_rank(n_plies: np.ndarray, margin: np.ndarray, sf: float) -> np.ndarray:
    """Order (best first) for the 'fewest plies' problem: feasible before infeasible; feasible by fewer plies,
    then larger margin; infeasible by smaller violation (sf - margin) / sf, then fewer plies."""
    feas = margin >= sf
    viol = np.where(feas, 0.0, (sf - margin) / sf)
    return np.lexsort((-margin, np.where(feas, n_plies, 0), viol, ~feas))


def better(a: Tuple[int, float], b: Tuple[int, float], sf: float) -> bool:
    """True if design a = (n, margin) is strictly better than b for the fewest-plies problem."""
    fa, fb = a[1] >= sf, b[1] >= sf
    if fa != fb:
        return fa
    if fa:
        return a[0] < b[0] or (a[0] == b[0] and a[1] > b[1])
    return a[1] > b[1] or (a[1] == b[1] and a[0] < b[0])
