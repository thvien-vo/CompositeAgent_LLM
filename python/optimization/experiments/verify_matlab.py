"""
Experiment 1 - Python CLT vs MATLAB clt_engine.m on random laminates (default 60, required >= 50).

Random: ply count 1-24 (odd counts and non-symmetric laminates included), angles (integers in [-90, 90] and
non-integer angles), per-ply thicknesses 0.05-0.30 mm, loads Nx, Ny, Nxy in +-[1e2, 1e6] N/m, moments in half of
the cases, and materials (measured CSV rows, a row with a missing strength filled by ML, ML group predictions).
Output: results/matlab_verification.csv + summary in results/matlab_verification.json.
Run: python -m optimization.experiments.verify_matlab [--n 60] [--seed 2026]
"""
from __future__ import annotations

import argparse

import numpy as np

from optimization import matlab_check
from optimization.material import Material, get_material
from optimization.experiments.common import Timer, setup, write_csv, write_json

MATERIAL_NAMES = ["IM7/8552", "T300/5208", "AS4/8552", "T650/5250-5", "E-glass/MY750", "Kevlar 49/epoxy",
                  "S2-glass/BT250E-6", "T1100G/3960"]


def materials():
    from ml import predict_material
    out = [get_material(n, verbose=False) for n in MATERIAL_NAMES]
    for g in ("CFRP", "GFRP", "KEVLAR"):
        out.append(Material(**predict_material(g), name=f"{g} (ML)", source=f"ML prediction (group {g})"))
    return out


def random_case(rng, mats):
    n = int(rng.integers(1, 25))
    if rng.random() < 0.5:
        ang = rng.integers(-90, 91, size=n).astype(float)
    else:
        ang = np.round(rng.uniform(-90, 90, size=n), 3)
    if rng.random() < 0.3:  # symmetric laminate
        half = ang[: max(1, n // 2)]
        ang = np.concatenate([half, half[::-1]])
    t = np.round(rng.uniform(0.05e-3, 0.30e-3, size=len(ang)), 7)
    if rng.random() < 0.3:
        t[:] = t[0]
    loads = {k: float(rng.choice([-1, 1]) * 10 ** rng.uniform(2, 6)) for k in ("Nx", "Ny", "Nxy")}
    if rng.random() < 0.5:
        loads.update({k: float(rng.choice([-1, 1]) * 10 ** rng.uniform(-1, 2)) for k in ("Mx", "My", "Mxy")})
    mat = mats[int(rng.integers(len(mats)))]
    return ang, t, loads, mat


def main(n_cases: int = 60, seed: int = 2026):
    setup()
    rng = np.random.default_rng(seed)
    mats = materials()
    timer = Timer()
    rows = []
    for i in range(n_cases):
        ang, t, loads, mat = random_case(rng, mats)
        r = matlab_check.compare(ang, t, mat, loads)
        rows.append({"case": i + 1, "material": mat.name, "n_plies": len(ang),
                     "symmetric": bool(np.array_equal(ang, ang[::-1]) and np.array_equal(t, t[::-1])),
                     "angles": " ".join(f"{a:g}" for a in ang), "Nx": loads["Nx"], "Ny": loads["Ny"],
                     "Nxy": loads["Nxy"], "Mx": loads.get("Mx", 0.0), "My": loads.get("My", 0.0),
                     "Mxy": loads.get("Mxy", 0.0), **{k: r[k] for k in ("e_ABD", "e_stress", "e_FI", "max_FI_py",
                                                                         "max_FI_matlab", "critical_ply_py",
                                                                         "critical_ply_matlab", "critical_ply_ok",
                                                                         "pass")}})
    write_csv("matlab_verification.csv", rows)
    summary = {"n_cases": n_cases, "seed": seed, "tolerance": matlab_check.TOL,
               "n_pass": sum(r["pass"] for r in rows),
               "max_e_ABD": max(r["e_ABD"] for r in rows), "max_e_stress": max(r["e_stress"] for r in rows),
               "max_e_FI": max(r["e_FI"] for r in rows),
               "n_nonsymmetric": sum(not r["symmetric"] for r in rows),
               "n_with_moments": sum(any(r[k] != 0 for k in ("Mx", "My", "Mxy")) for r in rows),
               "materials": sorted({r["material"] for r in rows}), "time_s": timer()}
    write_json("matlab_verification.json", summary)
    print(f"Python vs MATLAB: {summary['n_pass']}/{n_cases} pass (tol {matlab_check.TOL:g}); "
          f"max errors ABD {summary['max_e_ABD']:.2e}, stress {summary['max_e_stress']:.2e}, "
          f"FI {summary['max_e_FI']:.2e}; {summary['n_nonsymmetric']} non-symmetric, "
          f"{summary['n_with_moments']} with moments; {timer():.1f} s")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    main(a.n, a.seed)
