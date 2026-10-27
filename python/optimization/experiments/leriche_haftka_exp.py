"""
Experiment 3 - Le Riche & Haftka benchmark (fixed thickness, maximise the failure load), see
optimization/leriche_haftka.py for sources and problem data.

1. our lambda_b / lambda_cs for every design printed in the source (model reproduction check);
2. exhaustive enumeration of the whole design space (3^12 = 531 441 strings for 48 plies, 3^16 = 43 046 721 for
   64 plies) -> exact global optimum, compared with the value reported in the source;
3. GA (objective "max_margin", stack encoding) over many seeds: exact hits and "practical optima" (within 0.1 %,
   the definition of the source) within the evaluation budget;
4. extra: the minimum-thickness load cases of Le Riche & Haftka (1995), exhaustive + GA (fewest plies).
Run: python -m optimization.experiments.leriche_haftka_exp [--quick]
"""
from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

import numpy as np

from optimization import leriche_haftka as LH

from optimization.evaluate import analyze_design
from optimization.exhaustive import exhaustive
from optimization.ga import GAConfig, GeneticAlgorithm
from optimization.rules import notation
from optimization.experiments.common import Timer, setup, write_csv, write_json


def stack_notation(full):
    """Half laminate in stacks, e.g. [90_2/(±45)_2/0_2]s."""
    half = list(full[: len(full) // 2])
    names = []
    for i in range(0, len(half), 2):
        a, b = half[i], half[i + 1]
        names.append("0" if a == 0 else ("90" if a == 3 else "±45"))
    out, i = [], 0
    while i < len(names):
        j = i
        while j + 1 < len(names) and names[j + 1] == names[i]:
            j += 1
        k = j - i + 1
        nm = names[i]
        out.append(f"{nm}_{2 * k}" if nm in ("0", "90") else (f"(±45)_{k}" if k > 1 else "±45"))
        i = j + 1
    return "[" + "/".join(out) + "]s"


def ga_task(args):
    p, seed, budget, target, objective, ls = args
    cfg = GAConfig(budget=budget, objective=objective, local_search=ls)
    r = GeneticAlgorithm(p, cfg, seed).run(target=target)
    # practical optimum (within 0.1 %) hit: first evaluation count where best >= 0.999 * target
    prac = None
    if target is not None:
        for h in r["history"]:
            ok = (h["margin"] >= 0.999 * target[1]) if objective == "max_margin" else \
                (h["n_plies"] == target[0] and h["margin"] >= 0.999 * target[1])
            if ok:
                prac = h["evals"]
                break
    hist = [[h["evals"], h["n_plies"], h["margin"]] for h in r["history"]]
    return {"seed": seed, "local_search": ls, "margin": r["margin"], "n_plies": r["n_plies"], "hit_evals": r["hit_evals"],
            "practical_evals": prac, "n_evaluations": r["n_evaluations"], "time_s": r["time_s"],
            "history": hist[:: max(1, len(hist) // 200)] + [hist[-1]]}


def _ga_stats(row, allruns):
    for ls, pre in ((False, "ga"), (True, "ga_ls")):
        runs = [r for r in allruns if r["local_search"] == ls]
        hits = [r["hit_evals"] for r in runs if r["hit_evals"] is not None]
        prac = [r["practical_evals"] for r in runs if r["practical_evals"] is not None]
        row.update({f"{pre}_runs": len(runs), f"{pre}_exact_hits": len(hits), f"{pre}_practical_hits": len(prac),
                    f"{pre}_evals_to_exact_mean": float(np.mean(hits)) if hits else None,
                    f"{pre}_evals_to_practical_mean": float(np.mean(prac)) if prac else None,
                    f"{pre}_time_mean_s": float(np.mean([r["time_s"] for r in runs]))})


def main(quick: bool = False):
    setup()
    T = Timer()
    seeds = list(range(5 if quick else 20))
    budget = 6000  # = the 6000-analysis cap per search used by Le Riche & Haftka (1995)
    designs, summary, histories = [], [], {}
    for v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[v] = "1"
    pool = ProcessPoolExecutor(max_workers=max(1, min(12, (os.cpu_count() or 2) - 4)))
    for case in LH.CASES:
        designs += LH.evaluate_paper_designs(case)
        p = LH.problem(case)
        if quick and case.plies == 64:
            print(f"[{case.id}] skipped in quick mode (43 M designs)")
            continue
        t = Timer()
        ex = exhaustive(p, objective="max_margin", time_limit=3600)
        best = ex["best"]
        lam_star = best["max_margin"]
        full = best["full"]
        # same optimum with the proven-complete mode scan instead of m, n <= 5 ?
        det_full = analyze_design(replace(p, buckling_modes=None), full)
        det5 = analyze_design(p, full)
        tgt = (case.plies, lam_star)
        allruns = list(pool.map(ga_task, [(p, s, budget, tgt, "max_margin", ls) for ls in (False, True) for s in seeds]))
        row = {"case": case.id, "title": case.title, "plies": case.plies, "a_in": case.a_in, "b_in": case.b_in,
               "Ny_over_Nx": case.ny_over_nx, "design_space": 3 ** (case.plies // 4),
               "valid_designs": best["n_valid"], "exhaustive_time_s": t(),
               "lambda_exhaustive": lam_star, "n_optima_exhaustive": best["n_optima"],
               "design_exhaustive": stack_notation(full), "governing": det5["governing"],
               "lambda_paper": case.paper_lambda, "paper_ref": case.paper_ref,
               "rel_diff_vs_paper": (lam_star - case.paper_lambda) / case.paper_lambda,
               "lambda_full_mode_scan": det_full["margin"], "mode_mn": det5["buckling_mode_mn"], "ga_budget": budget}
        _ga_stats(row, allruns)
        summary.append(row)
        histories[case.id] = {"target": lam_star, "runs": allruns}
        print(f"[{case.id}] exhaustive lambda*={lam_star:.6g} ({best['n_optima']} optima, {t():.1f} s) "
              f"paper {case.paper_lambda} ({row['rel_diff_vs_paper']:+.2e});  full mode scan {det_full['margin']:.6g};  "
              f"GA exact {row['ga_exact_hits']}/{row['ga_runs']} (practical {row['ga_practical_hits']}), "
              f"GA+LS exact {row['ga_ls_exact_hits']}/{row['ga_ls_runs']} (practical {row['ga_ls_practical_hits']})",
              flush=True)

    # minimum-thickness cases of Le Riche & Haftka (1995)
    mt_rows = []
    for name, nx, ny in LH.MIN_THICKNESS_CASES:
        p = LH.min_thickness_problem(nx, ny)
        t = Timer()
        ex = exhaustive(p, objective="min_plies", front_to_n=52, time_limit=600)
        per = {r["n"]: r["max_margin"] for r in ex["per_n"]}
        b = ex["best"]
        tgt = (b["n"], b["max_margin"])
        allruns = list(pool.map(ga_task, [(p, s, 6000, tgt, "min_plies", ls) for ls in (False, True) for s in seeds]))
        row = {"case": name, "Nx_lbin": nx, "Ny_lbin": ny, "n_opt_exhaustive": b["n"],
               "lambda_cr_opt": b["max_margin"], "design": stack_notation(b["full"]),
               "lambda_best_44": per.get(44), "lambda_best_48": per.get(48), "lambda_best_52": per.get(52),
               "paper_n_opt": 48, "paper_lambda_44_48_52": "0.879 / 1.040 / 1.201" if name == "LC1" else "",
               "exhaustive_time_s": t(), "ga_budget": 6000}
        _ga_stats(row, allruns)
        mt_rows.append(row)
        histories[f"1995-{name}"] = {"target": b["max_margin"], "runs": allruns}
        print(f"[1995 {name}] n*={b['n']} lambda={b['max_margin']:.4f} best@44/48/52 = "
              f"{per.get(44)}, {per.get(48)}, {per.get(52)};  GA exact {row['ga_exact_hits']}/{row['ga_runs']}, "
              f"GA+LS exact {row['ga_ls_exact_hits']}/{row['ga_ls_runs']}", flush=True)
    pool.shutdown()
    write_csv("leriche_haftka_paper_designs.csv", designs)
    write_csv("leriche_haftka_summary.csv", summary)
    write_csv("leriche_haftka_1995_min_thickness.csv", mt_rows)
    write_json("leriche_haftka_histories.json", histories)
    print(f"done in {T():.0f} s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    main(ap.parse_args().quick)
