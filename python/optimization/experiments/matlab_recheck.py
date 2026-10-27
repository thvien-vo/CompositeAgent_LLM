"""
Experiment 2b - re-check every final design of run_cases.py (results/final_designs.json) with the agent's MATLAB
engine (matlab/clt_engine.m): CLT errors and RFs recomputed from MATLAB output, tolerance 1e-9.
Writes results/matlab_final_designs.csv and fills the matlab_pass / margin_matlab columns of cases_summary.csv.
If the MATLAB engine cannot start (probe in a child process with a time-out), it says so and exits; nothing
is marked as passed.
Run: python -m optimization.experiments.matlab_recheck
"""
from __future__ import annotations

import csv
import os

from optimization import matlab_check
from optimization.api import make_problem
from optimization.evaluate import Plate
from optimization.material import get_material
from optimization.rules import notation
from optimization.experiments.cases import CASES, MATERIAL, PLATE, SAFETY_FACTOR, THICKNESSES
from optimization.experiments.common import RESULTS, Timer, read_json, setup, write_csv, write_json


def main(probe_timeout: float = 180.0) -> bool:
    setup()
    T = Timer()
    designs = read_json("final_designs.json")
    if not matlab_check.available(probe_timeout):
        msg = (f"MATLAB engine could not start within {probe_timeout:.0f} s -> {len(designs)} final designs NOT "
               "re-checked in MATLAB (run this script again when MATLAB works)")
        print(msg)
        write_json("matlab_final_designs_status.json", {"done": False, "message": msg})
        return False
    mat = get_material(MATERIAL, verbose=False)
    cases = {c["id"]: c for c in CASES}
    rows = []
    for d in designs:
        c = cases[d["case"]]
        p = make_problem(c["loads"], material=mat, safety_factor=SAFETY_FACTOR, plate=Plate(*PLATE),
                         ply_thickness=THICKNESSES[d["thickness"]], buckling_model=d["model"], ritz_terms=10)
        r = matlab_check.verify_design(p, d["full"])
        rows.append({"case": d["case"], "thickness": d["thickness"], "model": d["model"], "source": d["source"],
                     "design": notation(d["full"], True), "n_plies": len(d["full"]),
                     "margin_python": r["margin_python"], "margin_matlab": r["margin_matlab"],
                     **{f"e_rf_{k}": v for k, v in r["e_rf"].items()}, "e_ABD": r["clt"]["e_ABD"],
                     "e_stress": r["clt"]["e_stress"], "e_FI": r["clt"]["e_FI"], "pass": r["pass"]})
    matlab_check.close()
    write_csv("matlab_final_designs.csv", rows)
    # fill the summary table
    path = os.path.join(RESULTS, "cases_summary.csv")
    with open(path, encoding="utf-8") as f:
        summ = list(csv.DictReader(f))
    for s in summ:
        ref = next(r for r in rows if (r["case"], r["thickness"], r["model"]) == (s["case"], s["thickness"], s["model"]))
        s["matlab_pass"] = ref["pass"]
        s["margin_matlab"] = ref["margin_matlab"]
    write_csv("cases_summary.csv", summ)
    ok = all(r["pass"] for r in rows)
    write_json("matlab_final_designs_status.json", {"done": True, "n_designs": len(rows),
                                                    "n_pass": sum(r["pass"] for r in rows), "all_pass": ok,
                                                    "max_e_ABD": max(r["e_ABD"] for r in rows),
                                                    "max_e_stress": max(r["e_stress"] for r in rows),
                                                    "time_s": T()})
    print(f"MATLAB re-check: {sum(r['pass'] for r in rows)}/{len(rows)} final designs pass (tol {matlab_check.TOL:g})")
    return ok


if __name__ == "__main__":
    main()
