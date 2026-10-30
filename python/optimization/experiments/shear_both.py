"""
Shear that may reverse: the Layer 1 load cases with a shear load (C5, C6, C7, C8, both ply thicknesses) optimised
again with shear_both_signs = True (every design is checked for +Nxy AND -Nxy, strength and buckling), compared with
the published one-direction results (results/cases_summary.csv, read as they are; the main study is not rerun and
keeps the option off).

Two-direction answer: exact search (branch and bound with proven bounds, same model and number of Ritz terms as the
main study) with a time limit; when it cannot finish, GA + local search (5 seeds, budget 10 000) gives the best
design found, and the proven bounds give a lower bound of the ply count. Quasi-isotropic comparison with the same
option.
Run:  python -m optimization.experiments.shear_both     -> results/shear_both_signs.csv, .json, .md
"""
from __future__ import annotations

import argparse
import csv
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

import numpy as np

from optimization.api import optimize, quasi_isotropic
from optimization.evaluate import analyze_design
from optimization.ga import GAConfig
from optimization.material import get_material
from optimization.rules import notation
from optimization.experiments.cases import CASES, MATERIAL, THICKNESS_LABEL
from optimization.experiments.common import RESULTS, Timer, read_json, setup, write_csv, write_json
from optimization.experiments.run_cases import build_problem, effective_lower_bound, exact_answer

SHEAR = ["C5", "C6", "C7", "C8"]
SEEDS = range(5)
EXACT_LIMIT = 300.0
WORKERS = 3
CODE = {0.0: 0, 45.0: 1, -45.0: 2, 90.0: 3}


def _problem(case_id, tkey, terms):
    case = next(c for c in CASES if c["id"] == case_id)
    p = build_problem(get_material(MATERIAL, verbose=False), case, tkey, terms=terms)
    return replace(p, shear_both_signs=True)


def _exact(args):
    case_id, tkey, terms = args
    p = _problem(case_id, tkey, terms)
    r = exact_answer(p, EXACT_LIMIT, None)
    r["n_lower_bound_effective"] = effective_lower_bound(p, r) if r.get("bounds") else None
    best = r.get("best")
    return {"case": case_id, "tkey": tkey, "status": r["status"], "time_s": r["time_s"],
            "n_lower_bound": r["n_lower_bound_effective"],
            "best": None if best is None else {"n": best["n"], "full": best["full"],
                                               "margin": best.get("max_margin", best.get("max_margin_lower"))}}


def _ga(args):
    case_id, tkey, terms, seed = args
    p = _problem(case_id, tkey, terms)
    res = optimize(None, problem=p, method="ga", seed=seed, ga_config=GAConfig(budget=10000, local_search=True))
    return {"case": case_id, "tkey": tkey, "seed": seed, "n": res.n_plies, "margin": res.margin,
            "feasible": res.feasible, "stacking": res.stacking_deg, "time_s": res.runtime_s}


def _one_way_rows():
    with open(os.path.join(RESULTS, "cases_summary.csv"), encoding="utf-8") as f:
        return {(r["case"], r["thickness"]): r for r in csv.DictReader(f) if r["model"] == "ritz_full"}


def main(workers: int = WORKERS):
    setup()
    t = Timer()
    terms = read_json("ritz_terms.json")
    jobs = [(c, tk, terms[f"{c}|{tk}"]["k"] or 8) for c in SHEAR for tk in ("t0125", "t0183")]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        exact = {(r["case"], r["tkey"]): r for r in pool.map(_exact, jobs)}
        ga = list(pool.map(_ga, [(c, tk, k, s) for c, tk, k in jobs for s in SEEDS]))
    one = _one_way_rows()
    rows, details = [], []
    for c, tk, k in jobs:
        p = _problem(c, tk, k)
        ex = exact[(c, tk)]
        runs = [g for g in ga if g["case"] == c and g["tkey"] == tk]
        best_ga = min(runs, key=lambda g: (not g["feasible"], g["n"] if g["feasible"] else 0, -g["margin"]))
        if ex["status"] in ("optimal", "infeasible") and ex["best"] is not None:
            full, status = ex["best"]["full"], ex["status"]
        else:
            full = [CODE[a] for a in best_ga["stacking"]]
            status = "best found (GA + local search)" if best_ga["feasible"] else "no feasible design found"
        det = analyze_design(p, full)
        n, margin = len(full), det["margin"]
        hit = sum(1 for g in runs if g["n"] == n and abs(g["margin"] - margin) <= 1e-9 * margin)
        qi = quasi_isotropic(p)
        o = one[(c, tk)]
        p1 = replace(p, shear_both_signs=False)
        o_full = [CODE[float(x)] for x in _angles(o["design"])]
        rev = analyze_design(replace(p1, loads=(p.loads[0], p.loads[1], -p.loads[2])), o_full)["margin"]
        feas = margin >= p.safety_factor
        saving = 100.0 * (qi["n"] - n) / qi["n"] if (feas and qi["found"]) else None
        rows.append({
            "case": c, "name_en": next(x["en"] for x in CASES if x["id"] == c), "thickness": tk,
            "Nx": p.loads[0], "Ny": p.loads[1], "Nxy": p.loads[2],
            "one_n": int(o["n_opt"]), "one_margin": float(o["margin_opt"]), "one_status": o["exact_status"],
            "one_margin_reversed": rev, "one_qi_n": o["qi_n"], "one_saving_pct": o["mass_reduction_pct"],
            "both_n": n, "both_margin": margin, "both_status": status, "both_feasible": feas,
            "both_n_lower_bound": ex["n_lower_bound"], "both_design": notation(full, True),
            "both_governing": det["governing"], "both_governing_shear_sign": det.get("governing_shear_sign", ""),
            "both_D16_over_D11": det["D16_over_D11"], "both_qi_n": qi["n"] if qi["found"] else "",
            "both_saving_pct": "" if saving is None else saving,
            "gals_seeds_at_answer": f"{hit}/{len(runs)}", "exact_time_s": ex["time_s"],
            "ritz_terms_k": k})
        details.append({"case": c, "tkey": tk, "exact": ex, "ga": runs, "analysis": {
            k2: v for k2, v in det.items() if k2 not in ("ABD",)}})
    write_csv("shear_both_signs.csv", rows)
    write_json("shear_both_signs.json", {"rows": rows, "details": details, "time_s": t()})
    with open(os.path.join(RESULTS, "shear_both_signs.md"), "w", encoding="utf-8") as f:
        f.write(markdown(rows))
    print(markdown(rows))
    print(f"total {t():.0f} s")


def _angles(design: str):
    """'[90/-45_2/0]s' -> full list of angles (symmetric)."""
    half = []
    for tok in design.strip("[]s").split("/"):
        a, _, k = tok.partition("_")
        half += [float(a)] * (int(k) if k else 1)
    return half + half[::-1]


def _fmt(x, nd=4):
    return "" if x in ("", None) else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def markdown(rows) -> str:
    out = ["*One direction* = published results (shear of the given sign only; results/cases_summary.csv). *Both "
           "directions* = shear_both_signs: strength and buckling for +Nxy and -Nxy, the smaller RF counts. "
           "*margin if reversed* = margin of the one-direction optimum when Nxy changes sign. *n lower bound* = "
           "proven lower bound of the ply count (both directions). Mass saving vs the smallest quasi-isotropic "
           "[0/45/-45/90]ns laminate checked with the same option.", ""]
    for tk in ("t0125", "t0183"):
        out += [f"**Ply {THICKNESS_LABEL[tk]}**", "",
                "| case | Nx, Ny, Nxy (N/m) | one direction: n* (margin) | margin if reversed | saving one dir. | "
                "both directions: n (margin) | status | n lower bound | design (half, outer->mid) | governing (sign) "
                "| |D16|/D11 | QI n | saving both dir. | GA+LS seeds at this answer |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            if r["thickness"] != tk:
                continue
            sv1 = f"{float(r['one_saving_pct']):.1f} %" if r["one_saving_pct"] not in ("", None) else "infeasible"
            sv2 = f"{r['both_saving_pct']:.1f} %" if r["both_saving_pct"] not in ("", None) else (
                "infeasible" if not r["both_feasible"] else "-")
            out.append(f"| {r['case']} {r['name_en']} | {r['Nx']:g}, {r['Ny']:g}, {r['Nxy']:g} | {r['one_n']} "
                       f"({r['one_margin']:.4f}) | {r['one_margin_reversed']:.4f} | {sv1} | {r['both_n']} "
                       f"({r['both_margin']:.4f}) | {r['both_status']} | {_fmt(r['both_n_lower_bound'])} | "
                       f"{r['both_design']} | {r['both_governing']} ({r['both_governing_shear_sign'] or '='}) | "
                       f"{r['both_D16_over_D11']:.3f} | {_fmt(r['both_qi_n'])} | {sv2} | {r['gals_seeds_at_answer']} |")
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=WORKERS)
    main(ap.parse_args().workers)
