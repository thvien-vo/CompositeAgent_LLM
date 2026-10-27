"""
Markdown tables for the report, generated from the CSV / JSON results (numbers are never typed by hand).
Run: python -m optimization.experiments.make_tables   -> results/tables.md
"""
from __future__ import annotations

import csv
import json
import os

from optimization.experiments.common import RESULTS, setup


def _csv(name):
    p = os.path.join(RESULTS, name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _json(name):
    p = os.path.join(RESULTS, name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def f(x, fmt="{:.4g}", none="-"):
    if x in (None, "", "None"):
        return none
    try:
        return fmt.format(float(x))
    except ValueError:
        return str(x)


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main():
    setup()
    md = []
    v = _json("matlab_verification.json")
    if v:
        md.append("## T1. Python vs MATLAB (random laminates)\n")
        md.append(table(["laminates", "pass", "max e_ABD", "max e_stress", "max e_FI", "non-symmetric", "with moments"],
                        [[v["n_cases"], v["n_pass"], f(v["max_e_ABD"], "{:.1e}"), f(v["max_e_stress"], "{:.1e}"),
                          f(v["max_e_FI"], "{:.1e}"), v["n_nonsymmetric"], v["n_with_moments"]]]))
    s = _csv("cases_summary.csv")
    if s:
        for tk, lab in (("t0125", "0.125 mm"), ("t0183", "0.18288 mm (NCAMP)")):
            rows = [r for r in s if r["thickness"] == tk and r["model"] == "closed_form"]
            md.append(f"\n## T2-{tk}. Optimum per load case, ply {lab}, closed-form buckling (spec model)\n")
            md.append(table(
                ["case", "Nx, Ny, Nxy (N/m)", "status", "n*", "proven lower bound", "design (half, outer->mid)",
                 "margin", "governing", "RF MS / TW / buck", "|D16|/D11, |D26|/D22", "QI n", "mass saving"],
                [[f"{r['case']} {r['name_vi']}", f"{f(r['Nx'], '{:g}')}, {f(r['Ny'], '{:g}')}, {f(r['Nxy'], '{:g}')}",
                  r["exact_status"], r["n_opt"], r["n_lower_bound"] or "none <= 64", r["design"],
                  f(r["margin_opt"], "{:.4f}"), r["governing"] + (f" (ply {r['critical_ply']}, {f(r['critical_angle'], '{:g}')} deg)" if r["critical_ply"] else ""),
                  f"{f(r['rf_max_stress'])} / {f(r['rf_tsai_wu'])} / {f(r['rf_buckling'])}",
                  f"{f(r['D16_over_D11'], '{:.3f}')}, {f(r['D26_over_D22'], '{:.3f}')}",
                  r["qi_n"] or "> 128", (f(r["mass_reduction_pct"], "{:.1f}") + " %") if r["mass_reduction_pct"] else "-"]
                 for r in rows]))
            md.append(f"\n## T3-{tk}. GA, GA + local search and NSGA-II against the exact optimum, ply {lab}\n")
            md.append(table(
                ["case", "exact search time", "GA success", "GA evals to hit (mean / max)",
                 "GA+LS success", "GA+LS evals to hit (mean / max)",
                 "NSGA-II success", "NSGA-II evals to hit (mean / max)", "time per run GA / GA+LS / NSGA-II",
                 "NSGA-II exact front points"],
                [[r["case"], f"{f(r['exact_time_s'], '{:.1f}')} s",
                  f"{r['ga_success']}/{r['ga_runs']}",
                  f"{f(r['ga_evals_to_hit_mean'], '{:.0f}')} / {r['ga_evals_to_hit_max'] or '-'}",
                  f"{r['ga_ls_success']}/{r['ga_ls_runs']}",
                  f"{f(r['ga_ls_evals_to_hit_mean'], '{:.0f}')} / {r['ga_ls_evals_to_hit_max'] or '-'}",
                  f"{r['nsga2_success']}/{r['nsga2_runs']}",
                  f"{f(r['nsga2_evals_to_hit_mean'], '{:.0f}')} / {r['nsga2_evals_to_hit_max'] or '-'}",
                  f"{f(r['ga_time_mean_s'], '{:.1f}')} / {f(r['ga_ls_time_mean_s'], '{:.1f}')} / {f(r['nsga2_time_mean_s'], '{:.1f}')} s",
                  (f(float(r["nsga2_front_points_exact_mean"]) * 100, "{:.0f}") + f" % of {r['true_front_points']}")
                  if r.get("nsga2_front_points_exact_mean") else "-"]
                 for r in rows]))
        rows = [r for r in s if r["model"] == "ritz"]
        if rows:
            md.append("\n## T4. Supplement: buckling by Ritz including Nxy (shear cases)\n")
            md.append(table(
                ["case", "ply", "status", "n (closed form)", "n (Ritz)", "proven lower bound", "design", "margin",
                 "governing", "GA / GA+LS / NSGA-II reaching it", "QI n"],
                [[r["case"], r["thickness"], r["exact_status"],
                  next((q["n_opt"] for q in s if q["case"] == r["case"] and q["thickness"] == r["thickness"]
                        and q["model"] == "closed_form"), "-"),
                  r["n_opt"], r["n_lower_bound_effective"], r["design"], f(r["margin_opt"], "{:.4f}"), r["governing"],
                  f"{r['ga_reach_reference']}/{r['ga_runs']} / {r['ga_ls_reach_reference']}/{r['ga_ls_runs']} / "
                  f"{r['nsga2_reach_reference']}/{r['nsga2_runs']}",
                  r["qi_n"] or "> 128"] for r in rows]))
            md.append("\nClosed-form designs checked with Ritz (with Nxy):\n")
            md.append(table(["case", "ply", "closed-form design", "Ritz buckling factor incl. Nxy", "margin incl. shear buckling"],
                            [[r["case"], r["thickness"], r["design"], f(r["buckling_ritz_with_shear"]),
                              f(min(float(r["buckling_ritz_with_shear"]), float(r["rf_max_stress"] or 1e99),
                                    float(r["rf_tsai_wu"] or 1e99)), "{:.4f}")]
                             for r in s if r["model"] == "closed_form" and float(r["Nxy"]) != 0]))
    m = _csv("matlab_final_designs.csv")
    st = _json("matlab_final_designs_status.json")
    md.append("\n## T5. MATLAB re-check of the final designs\n")
    if m:
        md.append(table(["designs", "pass", "max e_ABD", "max e_stress", "max |RF diff|"],
                        [[len(m), sum(r["pass"] == "True" for r in m),
                          f(max(float(r["e_ABD"]) for r in m), "{:.1e}"), f(max(float(r["e_stress"]) for r in m), "{:.1e}"),
                          f(max(max(float(r[k]) for k in r if k.startswith("e_rf_") and r[k] not in ("", None)) for r in m), "{:.1e}")]]))
    elif st:
        md.append(st.get("message", ""))
    lh = _csv("leriche_haftka_summary.csv")
    if lh:
        md.append("\n## T6. Le Riche & Haftka benchmark (fixed thickness, max lambda_cr)\n")
        md.append(table(["case", "problem", "design space", "valid designs", "exhaustive lambda*", "# optima",
                         "source value", "difference", "same with full mode scan", "GA exact (practical 0.1 %)",
                         "GA+LS exact (practical)", "evals to exact GA / GA+LS (mean)"],
                        [[r["case"], r["title"], f"{int(r['design_space']):,}", f"{int(r['valid_designs']):,}",
                          f(r["lambda_exhaustive"], "{:.2f}"), r["n_optima_exhaustive"], r["lambda_paper"],
                          f(float(r["rel_diff_vs_paper"]) * 100, "{:+.5f}") + " %", f(r["lambda_full_mode_scan"], "{:.2f}"),
                          f"{r['ga_exact_hits']}/{r['ga_runs']} ({r['ga_practical_hits']})",
                          f"{r['ga_ls_exact_hits']}/{r['ga_ls_runs']} ({r['ga_ls_practical_hits']})",
                          f"{f(r['ga_evals_to_exact_mean'], '{:.0f}')} / {f(r['ga_ls_evals_to_exact_mean'], '{:.0f}')}"]
                         for r in lh]))
        md.append("\nOptimal designs found by exhaustive search:\n")
        md.append(table(["case", "design (stacks, half)", "governing", "mode (m,n)"],
                        [[r["case"], r["design_exhaustive"], r["governing"], r["mode_mn"]] for r in lh]))
    pd_ = _csv("leriche_haftka_paper_designs.csv")
    if pd_:
        md.append("\n## T7. Designs printed in the source, recomputed\n")
        md.append(table(["case", "design (stacks outer->mid)", "lambda_b ours", "lambda_b source", "rel. diff",
                         "lambda_cs ours", "lambda_cs source", "rel. diff"],
                        [[r["case"], r["design_stacks"], f(r["lambda_b_ours"], "{:.2f}"), f(r["lambda_b_paper"], "{:.2f}"),
                          f(r["rel_diff_b"], "{:+.1e}"), f(r["lambda_cs_ours"], "{:.2f}"), f(r["lambda_cs_paper"], "{:.2f}"),
                          f(r["rel_diff_cs"], "{:+.1e}")] for r in pd_]))
    mt = _csv("leriche_haftka_1995_min_thickness.csv")
    if mt:
        md.append("\n## T8. Le Riche & Haftka (1995) minimum-thickness cases\n")
        md.append(table(["case", "Nx, Ny (lb/in)", "n* (exhaustive)", "lambda_cr", "design", "best lambda at 44 / 48 / 52",
                         "source", "GA exact", "GA+LS exact"],
                        [[r["case"], f"{f(r['Nx_lbin'], '{:g}')}, {f(r['Ny_lbin'], '{:g}')}", r["n_opt_exhaustive"],
                          f(r["lambda_cr_opt"], "{:.4f}"), r["design"],
                          f"{f(r['lambda_best_44'], '{:.3f}')} / {f(r['lambda_best_48'], '{:.3f}')} / {f(r['lambda_best_52'], '{:.3f}')}",
                          f"n* = {r['paper_n_opt']}" + (f"; {r['paper_lambda_44_48_52']}" if r["paper_lambda_44_48_52"] else ""),
                          f"{r['ga_exact_hits']}/{r['ga_runs']}", f"{r['ga_ls_exact_hits']}/{r['ga_ls_runs']}"] for r in mt]))
    path = os.path.join(RESULTS, "tables.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print("tables:", path)


if __name__ == "__main__":
    main()
