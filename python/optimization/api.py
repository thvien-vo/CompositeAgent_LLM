"""
api.py - entry point of Layer 1 (reused by Layer 2 / Layer 3).

    from optimization import optimize
    res = optimize({"Nx": -1e4, "Ny": -5e3, "Nxy": 0}, material="IM7/8552", method="ga", seed=1)
    print(res.summary())

method: "exhaustive" (exact; count-level enumeration when there is no buckling, else full enumeration within
time_limit), "ga" (single objective: fewest plies, then largest margin), "nsga2" (pymoo, plies vs margin).
Never returns a rule-violating or infeasible design silently: status is "optimal" (proven by exhaustive search),
"feasible" (found by a heuristic), "infeasible" (no design with margin >= safety factor in the ply range; the
best design found is returned and flagged) or "unknown (time limit)".
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np

from .evaluate import Plate, Problem, analyze_design
from .exhaustive import exhaustive, strength_only_exact
from .ga import GAConfig, GeneticAlgorithm
from .material import DEFAULT_PLY_THICKNESS, Material, get_material
from .rules import ANGLES, Rules, check_rules, full_laminate, notation


@dataclass
class OptimizationResult:
    """Structured result of one optimization run (SI units; angles in degrees, ply 1 = bottom)."""
    method: str
    seed: Optional[int]
    status: str
    feasible: bool
    stacking_deg: List[float]
    notation: str
    n_plies: int
    thickness_mm: float
    margin: float
    safety_factor: float
    rf: Dict[str, float]
    governing_criterion: str
    critical_ply: Optional[int]
    critical_angle: Optional[float]
    buckling_mode: Optional[Tuple[int, int]]
    buckling_ritz_with_shear: float
    D16_over_D11: float
    D26_over_D22: float
    rules_check: Dict[str, bool]
    n_evaluations: int
    n_calls: int
    runtime_s: float
    history: List[Dict] = field(default_factory=list)
    pareto: List[Dict] = field(default_factory=list)
    per_n: List[Dict] = field(default_factory=list)
    hit_evals: Optional[int] = None
    matlab: Optional[Dict] = None
    warnings: List[str] = field(default_factory=list)
    problem: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)

    def summary(self) -> str:
        lines = [f"[{self.method}{'' if self.seed is None else f' seed {self.seed}'}] status: {self.status}",
                 f"  stacking : {self.notation}   ({self.n_plies} plies, {self.thickness_mm:.4g} mm)",
                 f"  margin   : {self.margin:.4f}  (required >= {self.safety_factor})  governed by "
                 f"{self.governing_criterion}" + (f", ply {self.critical_ply} ({self.critical_angle:g} deg)"
                                                  if self.critical_ply else "")
                 + (f", mode (m,n)={self.buckling_mode}" if self.governing_criterion == "buckling" else ""),
                 "  RF       : " + ", ".join(f"{k}={v:.4g}" for k, v in self.rf.items()),
                 f"  |D16|/D11={self.D16_over_D11:.3f}  |D26|/D22={self.D26_over_D22:.3f}  "
                 f"(closed-form buckling ignores D16, D26)",
                 f"  evaluations: {self.n_evaluations}  time: {self.runtime_s:.2f} s"]
        if self.matlab is not None:
            lines.append(f"  MATLAB check: {'PASS' if self.matlab['pass'] else 'FAIL'}  margin MATLAB = "
                         f"{self.matlab['margin_matlab']:.6g}")
        for w in self.warnings:
            lines.append(f"  [warning] {w}")
        return "\n".join(lines)


def _loads_tuple(loads) -> Tuple[float, float, float]:
    if isinstance(loads, Mapping):
        for k in ("Mx", "My", "Mxy"):
            if float(loads.get(k, 0.0)) != 0.0:
                raise ValueError("Layer 1 handles in-plane loads only (Mx = My = Mxy = 0)")
        return float(loads.get("Nx", 0.0)), float(loads.get("Ny", 0.0)), float(loads.get("Nxy", 0.0))
    t = tuple(float(x) for x in loads)
    if len(t) != 3:
        raise ValueError("loads = (Nx, Ny, Nxy) in N/m")
    return t


def make_problem(loads, material: Union[str, Material, None] = "IM7/8552", rules: Optional[Rules] = None,
                 safety_factor: float = 1.5, plate: Optional[Plate] = None,
                 ply_thickness: float = DEFAULT_PLY_THICKNESS, encoding: str = "ply",
                 criteria: Sequence[str] = ("max_stress", "tsai_wu", "buckling"), f12_star: float = -0.5,
                 buckling_model: str = "closed_form", **kw) -> Problem:
    mat = get_material(material or "IM7/8552") if not isinstance(material, Material) else material
    return Problem(loads=_loads_tuple(loads), material=mat, rules=rules or Rules(), safety_factor=safety_factor,
                   plate=plate or Plate(), ply_thickness=ply_thickness, encoding=encoding,
                   criteria=tuple(criteria), f12_star=f12_star, buckling_model=buckling_model, **kw)


def warnings_for(problem: Problem) -> List[str]:
    Nx, Ny, Nxy = problem.loads
    w = list(problem.material.warnings)
    if "buckling" in problem.criteria and problem.buckling_model == "closed_form":
        if Nx >= 0 and Ny >= 0:
            w.append("no compressive load -> buckling not checked (closed form needs Nx < 0 or Ny < 0)")
        if Nxy != 0:
            w.append("Nxy is not part of the closed-form buckling check (shear buckling ignored); "
                     "see buckling_ritz_with_shear for a Ritz estimate that includes Nxy")
    if not problem.rules.symmetric and "buckling" in problem.criteria:
        w.append("non-symmetric laminates: closed-form buckling uses D only (B coupling ignored)")
    return w


def result_from_design(problem: Problem, full: Sequence[int], method: str, seed: Optional[int], status: str,
                       n_eval: int, n_calls: int, runtime: float, verify_matlab: bool = False, **extra
                       ) -> OptimizationResult:
    det = analyze_design(problem, full)
    chk = check_rules(full, problem.rules)
    feasible = det["margin"] >= problem.safety_factor
    warns = warnings_for(problem)
    if not all(chk.values()):
        warns.append(f"DESIGN RULES VIOLATED: {chk}")
    if not feasible:
        warns.append(f"INFEASIBLE: no design with margin >= {problem.safety_factor} found in "
                     f"{problem.rules.n_min}-{problem.rules.n_max} plies; best design found is reported "
                     f"(margin {det['margin']:.4f})")
    res = OptimizationResult(
        method=method, seed=seed, status=status if feasible or status.startswith("infeasible") else "infeasible",
        feasible=bool(feasible), stacking_deg=det["angles"], notation=notation(full, problem.rules.symmetric),
        n_plies=det["n_plies"], thickness_mm=det["thickness_mm"], margin=det["margin"],
        safety_factor=problem.safety_factor, rf=det["rf"], governing_criterion=det["governing"],
        critical_ply=det["critical_ply"], critical_angle=det["critical_angle"],
        buckling_mode=det["buckling_mode_mn"], buckling_ritz_with_shear=det["buckling_ritz_with_shear"],
        D16_over_D11=det["D16_over_D11"], D26_over_D22=det["D26_over_D22"], rules_check=chk,
        n_evaluations=int(n_eval), n_calls=int(n_calls), runtime_s=float(runtime), warnings=warns,
        problem=problem.describe(), **extra)
    if verify_matlab:
        from .matlab_check import verify_design
        res.matlab = verify_design(problem, full, det)
    return res


def optimize(loads, material: Union[str, Material, None] = "IM7/8552", rules: Optional[Rules] = None,
             safety_factor: float = 1.5, plate: Optional[Plate] = None, method: str = "ga", seed: int = 0,
             ply_thickness: float = DEFAULT_PLY_THICKNESS, encoding: str = "ply",
             criteria: Sequence[str] = ("max_stress", "tsai_wu", "buckling"), f12_star: float = -0.5,
             buckling_model: str = "closed_form", budget: int = 10000, pop_size: Optional[int] = None,
             ga_config: Optional[GAConfig] = None, time_limit: float = 600.0, verify_matlab: bool = False,
             target: Optional[Tuple[int, float]] = None, problem: Optional[Problem] = None,
             verbose: bool = False) -> OptimizationResult:
    """Optimise the stacking sequence (fewest plies with safety margin >= safety_factor).

    loads: {"Nx", "Ny", "Nxy"} (N/m, tension +) or a tuple. material: name (measured CSV row / ML group) or
    Material. rules: Rules(...) (symmetric, balanced, 10 % rule, max 4 contiguous, 8-64 plies by default).
    plate: Plate(a, b) simply supported (default 0.5 x 0.5 m). seed: random seed (ga / nsga2).
    budget: distinct designs analysed (ga / nsga2). target: known optimum (n, margin) to record hit_evals.
    """
    t0 = time.perf_counter()
    p = problem or make_problem(loads, material, rules, safety_factor, plate, ply_thickness, encoding, criteria,
                                f12_star, buckling_model)
    if method == "exhaustive":
        no_buckling = not ("buckling" in p.criteria and p.has_compression)
        r = strength_only_exact(p) if (no_buckling and p.rules.symmetric) else exhaustive(p, time_limit=time_limit,
                                                                                          verbose=verbose)
        best = r["best"]
        if best is None:
            raise RuntimeError("exhaustive search could not complete any ply count within the time limit")
        status = r["status"]
        return result_from_design(p, best["full"], method, None, status, r.get("n_evaluated", 0),
                                  r.get("n_evaluated", 0), time.perf_counter() - t0, verify_matlab,
                                  per_n=[{k: v for k, v in x.items() if k != "full"} for x in r["per_n"]])
    if method == "ga":
        cfg = ga_config or GAConfig(budget=budget, pop_size=pop_size or GAConfig.pop_size)
        r = GeneticAlgorithm(p, cfg, seed).run(target=target, verbose=verbose)
        pareto = []
    elif method == "nsga2":
        from .nsga2 import run_nsga2
        r = run_nsga2(p, seed=seed, pop_size=pop_size or 40, budget=budget, ga_config=ga_config, target=target,
                      verbose=verbose)
        pareto = [{"n": q["n"], "margin": q["margin"],
                   "notation": notation(full_laminate(p.enc.decode(q["genes"][None]), p.rules.symmetric)[0],
                                        p.rules.symmetric)} for q in r["pareto"]]
    else:
        raise ValueError("method must be 'exhaustive', 'ga' or 'nsga2'")
    full = full_laminate(p.enc.decode(r["best_genes"][None]), p.rules.symmetric)[0]
    status = "feasible" if r["feasible"] else "infeasible"
    return result_from_design(p, full, method, seed, status, r["n_evaluations"], r["n_calls"],
                              time.perf_counter() - t0, verify_matlab, history=r["history"], pareto=pareto,
                              hit_evals=r["hit_evals"])


def quasi_isotropic(problem: Problem, n_max: int = 128) -> Dict:
    """Smallest [0/45/-45/90]_ns laminate (n = 8, 16, ...) with margin >= safety factor (same criteria).
    Searched up to n_max plies (beyond the optimizer's 64-ply range, to quantify the comparison)."""
    from .evaluate import Evaluator
    from dataclasses import replace
    p = replace(problem, rules=replace(problem.rules, n_max=max(problem.rules.n_max, n_max)), encoding="ply")
    ev = Evaluator(p)
    rows = []
    for k in range(1, n_max // 8 + 1):
        half = np.array([[0, 1, 2, 3] * k], dtype=np.int8)
        r = ev.compute_plies(half)
        rows.append({"n": 8 * k, "margin": float(r["margin"][0])})
        if r["margin"][0] >= problem.safety_factor:
            full = full_laminate(half, True)[0]
            return {"n": 8 * k, "margin": float(r["margin"][0]), "full": full.tolist(),
                    "notation": f"[0/45/-45/90]_{k}s", "found": True, "scan": rows}
    return {"n": None, "margin": rows[-1]["margin"], "found": False, "scan": rows}
