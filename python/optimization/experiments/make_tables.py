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
    bv = _json("buckling_verification.json")
    if bv:
        md.append("\n## T1b. Checks of the buckling model (Rayleigh-Ritz with D16, D26, Nxy), made before using it\n")
        rows_ = [["compression, D16 = D26 = 0, vs closed form of the previous version",
                  f"{bv['compression_vs_closed_form']['n_cases']} cases", "-", "-",
                  f"max {100 * bv['compression_vs_closed_form']['max_rel_error']:.1e} %", "< 0.5 %",
                  "pass" if bv["compression_vs_closed_form"]["pass"] else "FAIL"]]
        sq = bv["square_shear"]
        rows_.append(["square isotropic plate, pure shear: k_s", "x".join(map(str, sq["terms"])),
                      f"{sq['k_s']:.4f}", "9.34", f"{100 * sq['rel_error']:.2f} %", "<= 1 %",
                      "pass" if sq["pass"] else "FAIL"])
        for r in bv["long_shear"]:
            rows_.append([f"isotropic plate a/b = {r['a_over_b']:g}, pure shear: k_s", "x".join(map(str, r["terms"])),
                          f"{r['k_s']:.4f}", f"{r['reference']:.4f} ({r['reference_name']})",
                          f"{100 * r['rel_error']:.2f} %", "<= 2 %" if r["very_long_check"] else "information",
                          ("pass" if r["pass"] else "FAIL") if r["very_long_check"] else "-"])
        for r in bv["composite"]:
            rows_.append([f"IM7/8552 {r['laminate']}, loads {tuple(r['loads'])}: sine series vs Legendre polynomials",
                          "x".join(map(str, r["terms"])) + " vs p = 16", f"{r['lambda_sine']:.5g}",
                          f"{r['lambda_polynomial_p16']:.5g}", f"{100 * r['sine_vs_polynomial']:+.2f} %", "check", "-"])
        for r in bv.get("nemeth_1992", []):
            rows_.append([f"Nemeth 1992 long SS {r['laminate']} graphite-epoxy, shear: (aniso - ortho) / ortho",
                          "x".join(map(str, r["terms"])) + ", a/b = 10",
                          f"{100 * r['diff_positive_shear']:+.1f} % (+Nxy) / {100 * r['diff_negative_shear']:+.1f} % (-Nxy)",
                          f"about {100 * r['quoted_difference']:g} %", "-", "comparison", "-"])
        md.append(table(["check", "terms", "value", "reference", "difference", "required", "result"], rows_))
        md.append("\nConvergence of the square plate (M x N: k_s): "
                  + ", ".join(f"{M}x{N}: {k:.4f}" for M, N, k in sq["sequence"])
                  + f"; Legendre polynomials p = 16: {sq['k_s_polynomial_p16']:.4f}.")
    s = _csv("cases_summary.csv")
    old = _csv(os.path.join("before_ritz", "cases_summary.csv"))
    if s:
        for tk, lab in (("t0125", "0.125 mm"), ("t0183", "0.18288 mm (NCAMP)")):
            rows = [r for r in s if r["thickness"] == tk and r["model"] == "ritz_full"]
            md.append(f"\n## T2-{tk}. Optimum per load case, ply {lab}, buckling by Rayleigh-Ritz with D16, D26, Nxy\n")
            md.append(table(
                ["case", "Nx, Ny, Nxy (N/m)", "status", "n*", "proven lower bound", "design (half, outer->mid)",
                 "margin", "governing", "RF MS / TW / buck", "|D16|/D11, |D26|/D22", "QI n", "mass saving"],
                [[f"{r['case']} {r['name_vi']}", f"{f(r['Nx'], '{:g}')}, {f(r['Ny'], '{:g}')}, {f(r['Nxy'], '{:g}')}",
                  r["exact_status"] if not (r["exact_status"].startswith("unknown") and r.get("n_proven_by_bound") == "True")
                  else "n* proven by the bound; margin = best known", r["n_opt"],
                  r["n_lower_bound_effective"] or "none <= 64", r["design"],
                  f(r["margin_opt"], "{:.4f}"), r["governing"] + (f" (ply {r['critical_ply']}, {f(r['critical_angle'], '{:g}')} deg)" if r["critical_ply"] else ""),
                  f"{f(r['rf_max_stress'])} / {f(r['rf_tsai_wu'])} / {f(r['rf_buckling'])}",
                  f"{f(r['D16_over_D11'], '{:.3f}')}, {f(r['D26_over_D22'], '{:.3f}')}",
                  r["qi_n"] or "> 128", (f(r["mass_reduction_pct"], "{:.1f}") + " %") if r["mass_reduction_pct"] else
                  ("infeasible" if r["feasible"] != "True" else "-")]
                 for r in rows]))
            md.append(f"\n## T3-{tk}. GA, GA + local search and NSGA-II against the exact optimum, ply {lab}\n")
            md.append("*success* = final answer is the PROVEN global optimum; when the exact search could not prove it, "
                      "*reach best known* counts the runs that end at the best design found by any run.\n")

            def succ(r, m):
                if r[f"{m}_success"] not in ("", None, "None"):
                    return f"{r[f'{m}_success']}/{r[f'{m}_runs']}"
                return f"- (reach best known {r[f'{m}_reach_reference']}/{r[f'{m}_runs']})"

            md.append(table(
                ["case", "exact search time", "GA success", "GA evals to hit (mean / max)",
                 "GA+LS success", "GA+LS evals to hit (mean / max)",
                 "NSGA-II success", "NSGA-II evals to hit (mean / max)", "time per run GA / GA+LS / NSGA-II",
                 "NSGA-II exact front points"],
                [[r["case"], f"{f(r['exact_time_s'], '{:.1f}')} s", succ(r, "ga"),
                  f"{f(r['ga_evals_to_hit_mean'], '{:.0f}')} / {r['ga_evals_to_hit_max'] or '-'}",
                  succ(r, "ga_ls"),
                  f"{f(r['ga_ls_evals_to_hit_mean'], '{:.0f}')} / {r['ga_ls_evals_to_hit_max'] or '-'}",
                  succ(r, "nsga2"),
                  f"{f(r['nsga2_evals_to_hit_mean'], '{:.0f}')} / {r['nsga2_evals_to_hit_max'] or '-'}",
                  f"{f(r['ga_time_mean_s'], '{:.1f}')} / {f(r['ga_ls_time_mean_s'], '{:.1f}')} / {f(r['nsga2_time_mean_s'], '{:.1f}')} s",
                  (f(float(r["nsga2_front_points_exact_mean"]) * 100, "{:.0f}") + f" % of {r['true_front_points']}")
                  if r.get("nsga2_front_points_exact_mean") else "-"]
                 for r in rows]))
        md.append("\n## T4. Number of Ritz terms per case and convergence of the final designs\n")
        md.append("*terms study*: smallest k >= 8 with change < 0.5 % from k to k + 2 on 9 reference laminates "
                  "(quasi-isotropic and +-45 outside); *final design*: series grown from 6 x 6 in steps of 2 until the "
                  "change is < 0.5 % (M x N: lambda); the margin uses the lower of the two values.\n")
        md.append(table(["case", "ply", "terms in optimisation (M x N)", "terms study: largest change k -> k+2",
                         "final design: sequence", "last change", "buckling RF used",
                         "closed form (Nx, Ny only, D16 = D26 = 0)"],
                        [[r["case"], r["thickness"], r["ritz_terms_MN"] or "- (no compression / shear)",
                          (f(float(r["ritz_terms_study_max_change"]) * 100, "{:.3f}") + " %")
                          if r["ritz_terms_study_max_change"] else "-",
                          r.get("buckling_full_sequence") or "-",
                          (f(float(r["buckling_full_last_change"]) * 100, "{:.3f}") + " %")
                          if r.get("buckling_full_last_change") not in (None, "", "None") else "-",
                          f(r["rf_buckling"]), f(r["buckling_closed_form"])]
                         for r in s if r["model"] == "ritz_full"]))
        if old:
            md.append("\n## T5b. Before / after: previous model (closed form, no shear buckling, D16 = D26 = 0) vs "
                      "Rayleigh-Ritz with D16, D26, Nxy\n")
            rws = []

            def ms(q):
                if q["mass_reduction_pct"] not in ("", None, "None"):
                    return f(q["mass_reduction_pct"], "{:.1f}") + " %"
                return "infeasible" if q["feasible"] != "True" else "-"

            for r in s:
                o = next((q for q in old if q["case"] == r["case"] and q["thickness"] == r["thickness"]
                          and q["model"] == "closed_form"), None)
                if r["model"] != "ritz_full" or o is None:
                    continue
                rws.append([f"{r['case']} {r['name_vi']}", r["thickness"], f"{o['n_opt']} ({f(o['margin_opt'], '{:.4f}')})",
                            f"{r['n_opt']} ({f(r['margin_opt'], '{:.4f}')})", o["qi_n"] or "> 128", r["qi_n"] or "> 128",
                            ms(o) + (" (shear buckling not checked)" if float(o["Nxy"]) != 0 and ms(o) != "infeasible" else ""),
                            ms(r), r["exact_status"]])
            md.append(table(["case", "ply", "before: n* (margin)", "after: n* (margin)", "QI n before", "QI n after",
                             "mass saving before", "mass saving after", "status after"], rws))
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
