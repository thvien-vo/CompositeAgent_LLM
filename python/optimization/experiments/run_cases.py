"""
Experiment 2 - the 8 load cases: exact answer (exhaustive / count-level / certified bound), GA and NSGA-II over
many seeds (success rate = exact global optimum found within the evaluation budget), Pareto fronts,
quasi-isotropic comparison, MATLAB re-check of the final designs (matlab_recheck.py), two ply thicknesses, and a supplementary run
with Ritz buckling (includes Nxy) for the shear cases.

Run:  python -m optimization.experiments.run_cases            (full: 20 seeds, budget 10 000, ~30-60 min)
      python -m optimization.experiments.run_cases --quick    (3 seeds, budget 3 000, short exhaustive)
"""
from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Optional

import numpy as np

from optimization.api import make_problem, optimize, quasi_isotropic
from optimization.evaluate import Plate, Problem, analyze_design
from optimization.exhaustive import count_upper_bounds, exhaustive, strength_only_exact
from optimization.material import get_material
from optimization.rules import notation
from optimization.experiments.cases import (CASES, MATERIAL, PLATE, SAFETY_FACTOR, SHEAR_CASES, THICKNESSES)
from optimization.experiments.common import Timer, setup, write_csv, write_json

RTOL = 1e-9


def build_problem(mat, case: Dict, tkey: str, model: str) -> Problem:
    return make_problem(case["loads"], material=mat, safety_factor=SAFETY_FACTOR, plate=Plate(*PLATE),
                        ply_thickness=THICKNESSES[tkey], buckling_model=model, ritz_terms=10)


def exact_answer(p: Problem, time_limit: float, front_to_n: Optional[int], start_at_bound: bool = False) -> Dict:
    """Exact answer. start_at_bound: skip the ply counts PROVEN infeasible by count_upper_bounds (used for the
    expensive Ritz model; the per-n maxima below the bound are then not enumerated)."""
    t = Timer()
    bounds = count_upper_bounds(p)
    if not p.has_compression or "buckling" not in p.criteria:
        r = strength_only_exact(p)
        r["method"] = "count-level enumeration (exact, all n <= 64)"
    else:
        start = bounds["n_lower_bound"] if start_at_bound else None
        if start_at_bound and start is None:
            r = {"status": "infeasible", "best": None, "per_n": [], "complete": True, "feasible": False}
        else:
            r = exhaustive(p, time_limit=time_limit, front_to_n=front_to_n, n_start=start)
        r["method"] = "enumeration of all family strings" + (f" from the proven bound n >= {start}" if start else "")             + ("" if r["complete"] else " (stopped by time limit)")
    r["bounds"] = bounds
    r["time_s"] = t()
    return r


def true_front(per_n: List[Dict]) -> List[Dict]:
    """Non-dominated (n, max margin) points of the exact per-n maxima."""
    out, best = [], -np.inf
    for r in sorted(per_n, key=lambda r: r["n"]):
        if r.get("max_margin") is not None and r["max_margin"] > best:
            out.append({"n": r["n"], "margin": r["max_margin"]})
            best = r["max_margin"]
    return out


def run_one(task: Dict) -> Dict:
    p: Problem = task["problem"]
    res = optimize(None, problem=p, method=task["method"], seed=task["seed"], budget=task["budget"],
                   target=task["target"])
    hist = [[h["evals"], h["n_plies"], h["margin"]] for h in res.history]
    keep = sorted({0, len(hist) - 1} | {i for i in range(1, len(hist)) if hist[i][1:] != hist[i - 1][1:]})
    return {"case": task["case"], "tkey": task["tkey"], "model": task["model"], "method": task["method"],
            "seed": task["seed"], "n_plies": res.n_plies, "margin": res.margin, "feasible": res.feasible,
            "status": res.status, "notation": res.notation, "hit_evals": res.hit_evals,
            "n_evaluations": res.n_evaluations, "runtime_s": res.runtime_s, "history": [hist[i] for i in keep],
            "pareto": [[q["n"], q["margin"]] for q in res.pareto], "stacking": res.stacking_deg}


def main(quick: bool = False, workers: int = 0, only: Optional[List[str]] = None, ritz: bool = True):
    setup()
    T = Timer()
    seeds = list(range(3 if quick else 20))
    budget = 3000 if quick else 10000
    ex_time = 60.0 if quick else 600.0
    front_to = None if quick else 32
    mat = get_material(MATERIAL)
    cases = [c for c in CASES if not only or c["id"] in only]
    configs = [(c, tk, "closed_form") for tk in THICKNESSES for c in cases]
    if ritz:
        configs += [(c, tk, "ritz") for tk in THICKNESSES for c in cases if c["id"] in SHEAR_CASES]

    # 1) exact answers ---------------------------------------------------------------------------------
    exact = {}
    for c, tk, model in configs:
        p = build_problem(mat, c, tk, model)
        lim = ex_time if model == "closed_form" else (60.0 if quick else 600.0)
        r = exact_answer(p, lim, front_to if model == "closed_form" else None, start_at_bound=(model == "ritz"))
        exact[(c["id"], tk, model)] = r
        b = r["best"]
        print(f"[exact] {c['id']} {tk} {model:11s} status={r['status']:<22s} "
              f"n={b['n'] if b else None} margin={b['max_margin'] if b else float('nan'):.6g} "
              f"lower bound n>={r['bounds']['n_lower_bound']}  ({r['time_s']:.1f} s)", flush=True)

    # 2) GA / NSGA-II runs ------------------------------------------------------------------------------
    tasks = []
    for c, tk, model in configs:
        p = build_problem(mat, c, tk, model)
        r = exact[(c["id"], tk, model)]
        proven = r["status"] in ("optimal", "infeasible") and r["best"] is not None
        target = (r["best"]["n"], r["best"]["max_margin"]) if proven else None
        for method in ("ga", "nsga2"):
            for s in (seeds if model == "closed_form" else seeds[:10]):
                tasks.append({"problem": p, "case": c["id"], "tkey": tk, "model": model, "method": method,
                              "seed": s, "budget": budget, "target": target})
    n_workers = workers or max(1, min(12, (os.cpu_count() or 2) - 4))
    for v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):  # one BLAS thread per process
        os.environ[v] = "1"
    print(f"running {len(tasks)} GA / NSGA-II runs on {n_workers} processes ...", flush=True)
    with ProcessPoolExecutor(max_workers=n_workers) as pool:
        runs = list(pool.map(run_one, tasks, chunksize=2))

    # 3) summaries, quasi-isotropic; designs for the MATLAB re-check (matlab_recheck.py) -----------------
    code = {0.0: 0, 45.0: 1, -45.0: 2, 90.0: 3}
    summary, to_check, fronts = [], [], {}
    for c, tk, model in configs:
        key = (c["id"], tk, model)
        p = build_problem(mat, c, tk, model)
        r = exact[key]
        b = r["best"]
        proven = r["status"] in ("optimal", "infeasible") and b is not None
        rows = {m: [x for x in runs if (x["case"], x["tkey"], x["model"], x["method"]) == key + (m,)]
                for m in ("ga", "nsga2")}
        # reference design: exact if proven, else best over all GA / NSGA-II runs
        if proven:
            ref_full, ref_src = list(b["full"]), "exact"
        else:
            allr = rows["ga"] + rows["nsga2"]
            feas = [x for x in allr if x["feasible"]]
            pick = min(feas, key=lambda x: (x["n_plies"], -x["margin"])) if feas else max(allr, key=lambda x: x["margin"])
            ref_full = [code[a] for a in pick["stacking"]]
            ref_src = f"best of GA/NSGA-II runs ({pick['method']} seed {pick['seed']})"
        det = analyze_design(p, ref_full)
        qi = quasi_isotropic(p)
        to_check.append({"case": c["id"], "thickness": tk, "model": model, "source": ref_src, "full": ref_full})
        for m in ("ga", "nsga2"):  # the best GA / NSGA-II designs too, when they differ from the reference
            best = min(rows[m], key=lambda x: (not x["feasible"], x["n_plies"] if x["feasible"] else 0, -x["margin"]))
            full = [code[a] for a in best["stacking"]]
            if full != ref_full:
                to_check.append({"case": c["id"], "thickness": tk, "model": model,
                                 "source": f"best {m} run (seed {best['seed']})", "full": full})
        tf = true_front(r["per_n"])
        fronts["|".join(key)] = {"exact_per_n": [{"n": x["n"], "max_margin": x.get("max_margin")} for x in r["per_n"]],
                                 "true_front": tf, "bounds": r["bounds"]["per_n"],
                                 "nsga2_fronts": [x["pareto"] for x in rows["nsga2"]]}
        row = {"case": c["id"], "name_vi": c["vi"], "name_en": c["en"], "thickness": tk,
               "ply_thickness_mm": THICKNESSES[tk] * 1e3, "model": model,
               "Nx": c["loads"][0], "Ny": c["loads"][1], "Nxy": c["loads"][2],
               "exact_status": r["status"], "exact_method": r["method"], "exact_time_s": r["time_s"],
               "n_lower_bound": r["bounds"]["n_lower_bound"], "reference": ref_src,
               "n_opt": det["n_plies"], "thickness_opt_mm": det["thickness_mm"], "margin_opt": det["margin"],
               "feasible": det["margin"] >= SAFETY_FACTOR, "design": notation(ref_full, True),
               "governing": det["governing"], "critical_ply": det["critical_ply"],
               "critical_angle": det["critical_angle"], "buckling_mode": det["buckling_mode_mn"],
               "rf_max_stress": det["rf"].get("max_stress"), "rf_tsai_wu": det["rf"].get("tsai_wu"),
               "rf_buckling": det["rf"].get("buckling"), "buckling_ritz_with_shear": det["buckling_ritz_with_shear"],
               "D16_over_D11": det["D16_over_D11"], "D26_over_D22": det["D26_over_D22"],
               "qi_n": qi["n"], "qi_margin": qi["margin"] if qi["found"] else None,
               "mass_reduction_pct": (100.0 * (qi["n"] - det["n_plies"]) / qi["n"]) if (qi["found"] and det["margin"] >= SAFETY_FACTOR) else None,
               "matlab_pass": None, "margin_matlab": None}
        for m in ("ga", "nsga2"):
            rr = rows[m]
            hits = [x["hit_evals"] for x in rr if x["hit_evals"] is not None]
            row[f"{m}_runs"] = len(rr)
            row[f"{m}_success"] = len(hits) if proven else None
            row[f"{m}_success_rate"] = (len(hits) / len(rr)) if proven else None
            row[f"{m}_evals_to_hit_mean"] = float(np.mean(hits)) if hits else None
            row[f"{m}_evals_to_hit_median"] = float(np.median(hits)) if hits else None
            row[f"{m}_evals_to_hit_max"] = int(max(hits)) if hits else None
            row[f"{m}_evaluations_mean"] = float(np.mean([x["n_evaluations"] for x in rr]))
            row[f"{m}_time_mean_s"] = float(np.mean([x["runtime_s"] for x in rr]))
            row[f"{m}_best_n"] = min(x["n_plies"] for x in rr if x["feasible"]) if any(x["feasible"] for x in rr) else None
            row[f"{m}_results"] = "; ".join(sorted({f"{x['n_plies']}:{x['margin']:.6g}" for x in rr}))
            # agreement with the reference design (exact optimum, or best known when no proof exists)
            row[f"{m}_reach_reference"] = sum(1 for x in rr if x["n_plies"] == det["n_plies"]
                                              and x["margin"] >= det["margin"] * (1 - RTOL))
            row["n_proven_by_bound"] = (r["bounds"]["n_lower_bound"] == det["n_plies"]) and det["margin"] >= SAFETY_FACTOR
            if m == "nsga2" and tf:
                fr = []
                for x in rr:
                    got = {int(n): mm for n, mm in x["pareto"]}
                    fr.append(np.mean([1.0 if (q["n"] in got and got[q["n"]] >= q["margin"] * (1 - RTOL)) else 0.0
                                       for q in tf]))
                row["nsga2_front_points_exact_mean"] = float(np.mean(fr))
                row["true_front_points"] = len(tf)
        summary.append(row)
        print(f"[{c['id']} {tk} {model}] n*={row['n_opt']} margin={row['margin_opt']:.5g} {row['design']}  "
              f"GA {row['ga_success']}/{row['ga_runs']}  NSGA-II {row['nsga2_success']}/{row['nsga2_runs']}  "
              f"QI n={row['qi_n']}", flush=True)

    write_csv("cases_summary.csv", summary)
    write_csv("runs.csv", [{k: v for k, v in x.items() if k not in ("history", "pareto", "stacking")} for x in runs])
    write_json("final_designs.json", to_check)
    write_json("runs_history.json", [{k: x[k] for k in ("case", "tkey", "model", "method", "seed", "history",
                                                        "hit_evals", "n_evaluations")} for x in runs])
    write_json("fronts.json", fronts)
    write_json("run_cases_meta.json", {"quick": quick, "seeds": seeds, "budget": budget,
                                       "exhaustive_time_limit_s": ex_time, "front_to_n": front_to,
                                       "material": mat.to_dict(), "total_time_s": T()})
    print(f"done in {T():.0f} s ({len(to_check)} final designs written for the MATLAB re-check)")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--no-ritz", action="store_true")
    a = ap.parse_args()
    main(a.quick, a.workers, a.only, not a.no_ritz)
