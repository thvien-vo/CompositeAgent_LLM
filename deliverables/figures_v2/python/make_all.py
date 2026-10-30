"""
Regenerates all Python figures and all tables from the stored result files. Nothing is recomputed; every number comes
from deliverables\\optimization\\results\\.

VS Code terminal at D:\\CompositeAgent:
    venv_fig\\Scripts\\activate
    python deliverables\\figures_v2\\python\\make_all.py              all figures
    python deliverables\\figures_v2\\python\\make_all.py Fig3 FigS1   only these
"""
from __future__ import annotations

import ast
import csv
import json
import math
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
import style as st  # noqa: E402
from style import PAPER, SLIDE, SLIDE_H, SLIDE_W, Page  # noqa: E402

BASE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(BASE))
RESULTS = os.path.join(ROOT, "deliverables", "optimization", "results")
CASES_PY = os.path.join(ROOT, "python", "optimization", "experiments", "cases.py")
MODEL = "ritz_full"
T_KEYS = ("t0125", "t0183")
ALGOS = (("GA", "ga"), ("NSGA-II", "nsga2"), ("GA + LS", "ga_ls"))
MINUS = "\u2212"
PARETO_TOP = 8      # upper end of the RF_min axis of the Pareto figures
REPORT = []


# ------------------------------------------------------------------------------------------------ data
def read_csv(name):
    with open(os.path.join(RESULTS, *name.split("/")), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_json(name):
    with open(os.path.join(RESULTS, name), encoding="utf-8") as f:
        return json.load(f)


class Data:
    def __init__(self):
        self.summary = [r for r in read_csv("cases_summary.csv") if r["model"] == MODEL]
        self.ids = list(dict.fromkeys(r["case"] for r in self.summary))
        self.cases = {(r["case"], r["thickness"]): r for r in self.summary}
        self.names = {r["case"]: r["name_en"] for r in self.summary}
        self.fronts = read_json("fronts.json")
        self.history = read_json("runs_history.json")
        self.meta = read_json("run_cases_meta.json")
        self.lh = read_csv("leriche_haftka_summary.csv")
        self.lh_hist = read_json("leriche_haftka_histories.json")
        self.shear = {(r["case"], r["thickness"]): r for r in read_csv("shear_both_signs.csv")}
        self.old = {(r["case"], r["thickness"]): r for r in read_csv("before_ritz/cases_summary.csv")
                    if r["model"] == "closed_form"}
        with open(CASES_PY, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        const = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
                 if isinstance(n, ast.Assign) and n.targets[0].id in ("SAFETY_FACTOR", "PLATE")}
        self.sf, self.plate = const["SAFETY_FACTOR"], const["PLATE"]
        self.nmax = max(q["n"] for f in self.fronts.values() for q in f["bounds"])
        self.budget = self.meta["budget"]
        self.seeds = len(self.meta["seeds"])


def feasible(r):
    return r["feasible"] == "True"


def proven(r):
    return r["exact_status"] in ("optimal", "infeasible")


def saving_tex(v):
    return rf"$-{half_up(v)}\%$"


def half_up(v):
    return int(math.floor(float(v) + 0.5))


def grid(W, H, left, right, bottom, top, gapx, gapy, rows, cols):
    w = (W - left - right - (cols - 1) * gapx) / cols
    h = (H - bottom - top - (rows - 1) * gapy) / rows
    return [[(left + c * (w + gapx), H - top - (r + 1) * h - r * gapy, w, h) for c in range(cols)] for r in range(rows)]


def axis_start(first_hit):
    x = first_hit * 0.8
    e = 10 ** math.floor(math.log10(x))
    return math.floor(x / e) * e


def ecdf(hits, n_runs, x0, x1):
    hits = sorted(hits)
    xs = np.concatenate([[x0], np.repeat(hits, 2), [x1]])
    ys = np.concatenate([[0, 0], np.repeat(np.arange(1, len(hits) + 1) * 100.0 / n_runs, 2)])[: len(xs)]
    return xs, ys


def finish(p):
    REPORT.append(p.save(HERE))
    print(p.name, p.s.mode, "collisions", len(REPORT[-1]["collisions"]), "colours", len(REPORT[-1]["colours"]), flush=True)


# ---------------------------------------------------------------------------------------------- Fig1
TEXT_PAPER = {
    "request": ["Request in words", "(English or Vietnamese)"],
    "router": ["Router: Python rules first,", "LLM confirms weak design wording"],
    "refused": ["Refused with a hint", "(unclear or contradictory text)"],
    "a_read": ["LLM copies numbers and units", "into a fixed JSON schema"],
    "a_chk": ["Python checks every value against", "the text; one retry, else refused"],
    "d_read": ["LLM copies the request", "into a fixed JSON schema"],
    "d_chk": ["Python re-reads the text: the text", "wins; defaults are printed"],
    "q_vec": ["Question turned into a vector", "(nomic-embed-text)"],
    "q_ret": ["Retrieval from the material data:", "cosine similarity + exact name match"],
    "ply": ["Ply properties: measured values when one known material system is named,",
            "else ML (random forest) prediction for the fibre group"],
    "q_prompt": ["Prompt built from the best rows", "and a ranking computed by Python"],
    "clt": ["CLT in MATLAB: ABD matrix, ply", "stresses, Max Stress failure index"],
    "opt": ["Optimiser: exact search; if it", "cannot finish, GA + local search"],
    "final": ["Final design checked: MATLAB strength,", "polynomial Ritz, quasi-isotropic laminate"],
    "a_llm": ["LLM explains the numbers"],
    "d_llm": ["LLM explains the design"],
    "q_llm": ["LLM answers and cites report and page"],
    "a_guard": ["Every number must be in the data and", "named correctly; else pre-built text"],
    "d_guard": ["Every number must be in the data and", "named correctly; else pre-built text"],
    "q_guard": ["Numbers and report ids must be in", "the rows; else pre-built text"],
    "out": ["Result, with an explanation or answer that passed the guard"],
}
TEXT_SLIDE = {
    "request": ["Request in words"], "router": ["Router: Python rules, LLM confirms"],
    "refused": ["Refused with a hint"], "a_read": ["LLM copies numbers, units"], "a_chk": ["Python checks against text"],
    "d_read": ["LLM copies the request"], "d_chk": ["Python re-reads the text"], "q_vec": ["Question to vector"],
    "q_ret": ["Retrieval from material data"], "ply": ["Ply properties: measured values, else ML prediction"],
    "q_prompt": ["Prompt from best rows"], "clt": ["CLT in MATLAB"], "opt": ["Exact search, else GA + LS"],
    "final": ["MATLAB, Ritz, quasi-isotropic"], "a_llm": ["LLM explains the numbers"], "d_llm": ["LLM explains the design"],
    "q_llm": ["LLM answers, cites source"], "a_guard": ["Numbers checked against data"],
    "d_guard": ["Numbers checked against data"], "q_guard": ["Numbers checked against rows"],
    "out": ["Result, with a verified explanation or answer"],
}


def fig1(d, s):
    paper = s.mode == "paper"
    W, H = (190.0, 131.0) if paper else (SLIDE_W, SLIDE_H)
    p = Page("Fig1_workflow", W, H, s)
    T = TEXT_PAPER if paper else TEXT_SLIDE
    gap_c = 4.0 if paper else 6.0
    mx = 0.6 if paper else 1.2
    cw = (W - 2 * gap_c - 2 * mx) / 3
    cx = [mx + i * (cw + gap_c) for i in range(3)]
    mid = [x + cw / 2 for x in cx]
    key_y = H - 2.8 if paper else H - 5.5
    h1, h2 = (10.5, 7.0) if paper else (14.6, 14.6)
    g = 3.6 if paper else 4.9
    rows = {}
    y = H - (7.0 if paper else 11.0)
    for key, hh, gap in (("top", h1, 8.5 if paper else 12.5), ("read", h1, g), ("chk", h1, g), ("data", h1, g), ("comp", h1, g),
                         ("final", h1, g), ("llm", h2 if paper else h1, g), ("guard", h1, g), ("out", h2, 0.0)):
        rows[key] = (y - hh, hh)
        y -= hh + gap
    x = mx
    for kind, dx in (("llm", 24), ("data", 36), ("comp", 37), ("check", 28)) if paper else (("llm", 46), ("data", 82), ("comp", 88), ("check", 60)):
        wk, hk = (s.sample, s.mm(s.legend)) if paper else (s.sample, s.mm(s.legend))
        p.block(x, key_y - hk / 2, wk, hk, [], kind)
        p.text(x + wk + 1.5, key_y, st.BLOCK_NAME[kind], s.legend, ha="left")
        x += dx

    def block(col, row, key, kind, span=1):
        yy, hh = rows[row]
        p.block(cx[col], yy, cw * span + gap_c * (span - 1), hh, T[key], kind)

    def down(col, r0, r1):
        p.arrow((mid[col], rows[r0][0]), (mid[col], rows[r1][0] + rows[r1][1]))

    block(0, "top", "request", None)
    block(1, "top", "router", "check")
    block(2, "top", "refused", None)
    yt, ht = rows["top"]
    p.arrow((cx[0] + cw, yt + ht / 2), (cx[1], yt + ht / 2))
    p.arrow((cx[1] + cw, yt + ht / 2), (cx[2], yt + ht / 2))
    bus = yt - (2.6 if paper else 3.4)
    p.wire((mid[1], yt), (mid[1], bus))
    p.wire((mid[0], bus), (mid[2], bus))
    for i, lab in enumerate(("Analysis", "Design", "Question")):
        p.arrow((mid[i], bus), (mid[i], rows["read"][0] + rows["read"][1]))
        p.text(mid[i] + (1.2 if paper else 2.4), bus - (1.4 if paper else 2.8), lab, s.block, ha="left", va="top")
    block(0, "read", "a_read", "llm")
    block(1, "read", "d_read", "llm")
    block(2, "read", "q_vec", "data")
    block(0, "chk", "a_chk", "check")
    block(1, "chk", "d_chk", "check")
    block(2, "chk", "q_ret", "data")
    block(0, "data", "ply", "data", 2)
    block(2, "data", "q_prompt", "data")
    block(0, "comp", "clt", "comp")
    block(1, "comp", "opt", "comp")
    block(1, "final", "final", "check")
    block(0, "llm", "a_llm", "llm")
    block(1, "llm", "d_llm", "llm")
    block(2, "llm", "q_llm", "llm")
    block(0, "guard", "a_guard", "check")
    block(1, "guard", "d_guard", "check")
    block(2, "guard", "q_guard", "check")
    block(0, "out", "out", None, 3)
    for c in (0, 1, 2):
        down(c, "read", "chk")
        down(c, "chk", "data")
        down(c, "llm", "guard")
        down(c, "guard", "out")
    down(0, "data", "comp")
    down(1, "data", "comp")
    down(0, "comp", "llm")
    down(1, "comp", "final")
    down(1, "final", "llm")
    down(2, "data", "llm")
    finish(p)


# ---------------------------------------------------------------------------------------------- Fig2
def lh_curves(d):
    out = []
    for r in d.lh:
        runs = d.lh_hist[r["case"]]["runs"]
        for flag, algo, pre in ((False, "GA", "ga"), (True, "GA + LS", "ga_ls")):
            rr = [x for x in runs if bool(x.get("local_search", False)) == flag]
            hits = [x["hit_evals"] for x in rr if x["hit_evals"] is not None]
            if len(hits) != int(r[f"{pre}_exact_hits"]):
                raise ValueError("history and summary disagree")
            out.append((r["case"], algo, hits, len(rr)))
    return out


def fig2(d, s):
    paper = s.mode == "paper"
    W, H = (140.0, 84.0) if paper else (SLIDE_W, SLIDE_H)
    box = (13.0, 11.0, W - 17.0, H - 20.0) if paper else (28.0, 22.0, W - 36.0, H - 41.0)
    p = Page("Fig2_leriche_haftka", W, H, s)
    curves = lh_curves(d)
    x1 = float(d.lh[0]["ga_budget"])
    x0 = axis_start(min(min(c[2]) for c in curves))
    ticks = [100, 300, 1000, 3000, x1]
    ax = p.axes(box, (x0, x1), (0, 104), xlog=True, xticks=ticks, yticks=(0, 25, 50, 75, 100),
                xlabels=[f"{t:g}" for t in ticks], ylabels=["0", "25", "50", "75", "100"])
    for case, algo, hits, n in curves:
        xs, ys = ecdf(hits, n, x0, x1)
        xs = np.minimum(xs, x1)
        p.line(ax, xs, ys, case, ls=st.ALGO_LS[algo], marker=st.CASE_MARK[case], every=(2, 8),
               mfc=st.ROLE[case] if algo == "GA + LS" else st.WHITE, mew=s.mew * 1.6, label=f"{case} {algo}")
    p.xlabel(ax, "Distinct designs evaluated", 1.2 if paper else 3.0)
    p.ylabel(ax, r"Runs at the exact optimum (\%)", 3.4 if paper else 10.0)
    y = H - 4.0 if paper else H - 8.0
    xs = (13, 29, 45, 61, 80, 101) if paper else (28, 66, 104, 142, 184, 234)
    for i, r in enumerate(d.lh):
        c = r["case"]
        p.key_line(xs[i], y, c, c, ls="", marker=st.CASE_MARK[c])
    p.key_line(xs[4], y, "exact", "GA", ls="--")
    p.key_line(xs[5], y, "exact", "GA + LS", ls="-")
    finish(p)


# ---------------------------------------------------------------------------------------- Fig3 and FigS1
def pareto_panel(d, p, ax, case):
    s = p.s
    for tk in T_KEYS:
        f = d.fronts[f"{case}|{tk}|{MODEL}"]
        tf = [(q["n"], q["margin"]) for q in f["true_front"]]
        p.line(ax, *zip(*tf), tk, marker=st.THICK_MARK[tk], ms=s.ms * 0.9, zorder=4, label=f"{case} {tk} exact")
    for tk in T_KEYS:
        f = d.fronts[f"{case}|{tk}|{MODEL}"]
        pts = sorted({(int(n), float(m)) for fr in f["nsga2_fronts"] for n, m in fr if float(m) < 0.985 * ax.yl[1]})
        p.line(ax, [a for a, _ in pts], [b for _, b in pts], "seed", ls="", marker="o", ms=s.ms_small, mfc="none",
               mew=s.mew, zorder=5, label=f"{case} {tk} NSGA-II")
    for tk in T_KEYS:
        r = d.cases[(case, tk)]
        if feasible(r):
            p.line(ax, [int(r["n_opt"])], [float(r["margin_opt"])], "exact", ls="", marker="D", ms=s.ms * 1.1, zorder=6,
                   label=f"{case} {tk} optimum")
    p.hline(ax, d.sf)
    x, y, w, h = ax.mm_box
    p.text(x + w, float(p.Y(ax, d.sf)) + 1.9 * s.pad, rf"$RF_{{\min}} = {d.sf:g}$", s.ref, ha="right", va="bottom")


def pareto_key(p, xs, y):
    s = p.s
    p.key_line(xs[0], y, "t0125", st.THICK_TEXT["t0125"], marker=st.THICK_MARK["t0125"], ms=s.ms * 0.9)
    p.key_line(xs[1], y, "t0183", st.THICK_TEXT["t0183"], marker=st.THICK_MARK["t0183"], ms=s.ms * 0.9)
    p.key_line(xs[2], y, "seed", "NSGA-II, each seed", ls="", marker="o", ms=s.ms_small, mfc="none")
    p.key_line(xs[3], y, "exact", "Optimum", ls="", marker="D", ms=s.ms * 1.1)


def pareto_page(d, s, name, cases):
    paper = s.mode == "paper"
    W, H = (190.0, 128.0) if paper else (SLIDE_W, SLIDE_H)
    p = Page(name, W, H, s)
    g = grid(W, H, 13, 2, 11, 12.5, 7, 9, 2, 2) if paper else grid(W, H, 28, 5, 22, 24, 12, 14, 2, 2)
    xt, yt = (10, 20, 30, 40, 50, 60), (0, 2, 4, 6, 8)
    lim_x, lim_y = (6, 66), (0, PARETO_TOP)
    axes = []
    for i, c in enumerate(cases):
        r, q = i // 2, i % 2
        ax = p.axes(g[r][q], lim_x, lim_y, xticks=xt, yticks=yt, xlabels=[str(v) for v in xt] if r == 1 else None,
                    ylabels=[str(v) for v in yt] if q == 0 else None)
        pareto_panel(d, p, ax, c)
        p.panel(ax, "abcd"[i], f"{c} {d.names[c]}")
        axes.append(ax)
    for ax in axes[2:]:
        p.xlabel(ax, "Number of plies, $n$", 1.2 if paper else 3.0)
    for ax in (axes[0], axes[2]):
        p.ylabel(ax, r"$RF_{\min}$", 3.4 if paper else 10.0)
    pareto_key(p, (13, 49, 85, 125) if paper else (28, 100, 172, 257), H - 3.5 if paper else H - 8.0)
    finish(p)


def fig3(d, s):
    pareto_page(d, s, "Fig3_pareto", ("C1", "C4", "C5", "C7"))


def figS1(d, s):
    pareto_page(d, s, "FigS1_pareto_all_C1_C4", tuple(d.ids[:4]))
    pareto_page(d, s, "FigS1_pareto_all_C5_C8", tuple(d.ids[4:]))


def table_load_cases(d):
    a, b = d.plate
    plate = f"{a:g} \u00d7 {b:g}"
    header = ["Case", "Load case", "N_x (N/m)", "N_y (N/m)", "N_xy (N/m)", "Plate a \u00d7 b (m)"]
    tex = ["Case", "Load case", r"$N_x$ (N/m)", r"$N_y$ (N/m)", r"$N_{xy}$ (N/m)", r"Plate $a \times b$ (m)"]
    rows = []
    for c in d.ids:
        r = d.cases[(c, T_KEYS[0])]
        rows.append([c, d.names[c], sci(r["Nx"]), sci(r["Ny"]), sci(r["Nxy"]), plate])
    write_table("Table_load_cases", header, rows, tex, rows, "llrrrl",
                f"Load cases of the laminate study (IM7/8552, simply supported plate, safety factor {d.sf:g}).",
                "tab:load_cases")


# ---------------------------------------------------------------------------------------------- Fig4
def qi_panel(d, p, ax, tk):
    s = p.s
    w, gap = 0.38, 0.015
    for i, c in enumerate(d.ids):
        r = d.cases[(c, tk)]
        qi = int(r["qi_n"])
        xa, xb = i + 1 - w - gap, i + 1 - gap
        p.bar(ax, xa, xb, qi, "qi", mark="s")
        p.text(float(p.X(ax, (xa + xb) / 2)), float(p.Y(ax, qi)) + s.pad * 0.9, str(qi), s.barnum, va="bottom")
        xa, xb = i + 1 + gap, i + 1 + gap + w
        if feasible(r):
            n = int(r["n_opt"])
            p.bar(ax, xa, xb, n, "opt", mark="o")
            p.text(float(p.X(ax, (xa + xb) / 2)), float(p.Y(ax, n)) + s.pad * 0.9, str(n), s.barnum, va="bottom")
        else:
            p.hatch_bar(ax, xa, xb, d.nmax)
            p.text(float(p.X(ax, xa)), float(p.Y(ax, d.nmax)) + s.pad * 0.9, f"${{>}}{d.nmax}$", s.barnum, ha="left", va="bottom")


def qi_axes(d, p, box, tk, left=True):
    s = p.s
    yt = (0, 25, 50, 75, 100)
    top = max(int(r["qi_n"]) for r in d.summary) * 1.1
    ax = p.axes(box, (0.4, len(d.ids) + 0.6), (0, top), xticks=range(1, len(d.ids) + 1), yticks=yt,
                ylabels=[str(v) for v in yt] if left else None)
    x, y, w, h = box
    y1 = y - s.ticklen - s.pad
    y2 = y1 - s.mm(s.tick) * 1.28
    for i, c in enumerate(d.ids):
        r = d.cases[(c, tk)]
        xm = float(p.X(ax, i + 1))
        p.text(xm, y1, c, s.tick, va="top")
        p.text(xm, y2, saving_tex(r["mass_reduction_pct"]) if r["mass_reduction_pct"] else "n/a", s.tick, va="top")
    ax.tick_params(axis="x", length=0)
    qi_panel(d, p, ax, tk)
    p.hline(ax, d.nmax)
    p.text(x + 0.8, float(p.Y(ax, d.nmax)) + s.pad * 1.9, f"Ply limit ({d.nmax})", s.legend, ha="left", va="bottom")
    return ax


def fig4_key(p, xs, y):
    p.key_bar(xs[0], y, "qi", "Quasi-isotropic", mark="s")
    p.key_bar(xs[1], y, "opt", "Optimised laminate", mark="o")
    p.key_bar(xs[2], y, "opt", "No feasible design", hatch=True)


def fig4(d, s):
    if s.mode == "paper":
        W, H = 190.0, 88.0
        p = Page("Fig4_qi_comparison", W, H, s)
        g = grid(W, H, 13, 2, 15, 12.5, 6, 0, 1, 2)
        for i, tk in enumerate(T_KEYS):
            ax = qi_axes(d, p, g[0][i], tk, left=i == 0)
            p.panel(ax, "ab"[i], st.THICK_TEXT[tk])
            p.xlabel(ax, r"Load case and mass saving", 1.2)
        p.ylabel(p.fig.axes[1], rf"Plies needed for $RF_{{\min}} \geq {d.sf:g}$", 3.4)
        fig4_key(p, (13, 50, 94), H - 3.5)
        finish(p)
        return
    for tk in T_KEYS:
        W, H = SLIDE_W, SLIDE_H
        p = Page(f"Fig4_qi_comparison_{tk}", W, H, s)
        ax = qi_axes(d, p, (28, 33, W - 33, H - 57), tk)
        p.xlabel(ax, "Load case and mass saving", 3.0)
        p.ylabel(ax, rf"Plies needed for $RF_{{\min}} \geq {d.sf:g}$", 10.0)
        fig4_key(p, (28, 105, 195), H - 8.0)
        p.text(W - 5, H - 8.0, st.THICK_TEXT[tk], s.legend, ha="right")
        finish(p)


# ---------------------------------------------------------------------------------------------- Fig5
def conv_cell(d, case, tk, pre):
    r = d.cases[(case, tk)]
    col = f"{pre}_success" if proven(r) else f"{pre}_reach_reference"
    return int(float(r[col])), int(r[f"{pre}_runs"]), r[f"{pre}_evals_to_hit_median"]


def algo_axes(d, p, box, tk, ticks=True):
    s = p.s
    yt = (0, 5, 10, 15, 20)
    ax = p.axes(box, (0.45, len(d.ids) + 0.55), (0, d.seeds * 1.18), xticks=range(1, len(d.ids) + 1), yticks=yt,
                xlabels=d.ids if ticks else None, ylabels=[str(v) for v in yt])
    w, gap = 0.27, 0.012
    for i, c in enumerate(d.ids):
        for j, (algo, pre) in enumerate(ALGOS):
            hits, _, _ = conv_cell(d, c, tk, pre)
            xa = i + 1 + (j - 1.5) * w + (j - 1) * gap
            xb = xa + w
            xm = float(p.X(ax, (xa + xb) / 2))
            if hits:
                p.bar(ax, xa, xb, hits, algo, mark=st.ALGO_MARK[algo])
            p.series.append({"label": f"{c} {tk} {algo}", "x": [i + 1.0], "y": [float(hits)]})
            p.text(xm, float(p.Y(ax, hits)) + s.pad * 0.9, str(hits), s.barnum, va="bottom")
    return ax


def fig5_key(p, xs, y):
    for x, (algo, _) in zip(xs, ALGOS):
        p.key_bar(x, y, algo, st.ALGO_NAME[algo], mark=st.ALGO_MARK[algo])


def fig5(d, s):
    if s.mode == "paper":
        W, H = 190.0, 112.0
        p = Page("Fig5_algorithms", W, H, s)
        g = grid(W, H, 13, 2, 11, 12.5, 0, 9, 2, 1)
        for i, tk in enumerate(T_KEYS):
            ax = algo_axes(d, p, g[i][0], tk, ticks=i == 1)
            p.panel(ax, "ab"[i], st.THICK_TEXT[tk])
            p.ylabel(ax, f"Runs at the optimum (of {d.seeds})", 3.4)
            if i == 1:
                p.xlabel(ax, "Load case", 1.2)
        fig5_key(p, (13, 38, 72), H - 3.5)
        finish(p)
        return
    for tk in T_KEYS:
        W, H = SLIDE_W, SLIDE_H
        p = Page(f"Fig5_algorithms_{tk}", W, H, s)
        ax = algo_axes(d, p, (28, 22, W - 33, H - 46), tk)
        p.xlabel(ax, "Load case", 3.0)
        p.ylabel(ax, f"Runs at the optimum (of {d.seeds})", 10.0)
        fig5_key(p, (28, 85, 185), H - 8.0)
        p.text(W - 5, H - 8.0, st.THICK_TEXT[tk], s.legend, ha="right")
        finish(p)


def table_convergence(d):
    labels = {"t0125": "t = 0.125 mm", "t0183": "t = 0.183 mm"}
    header = ["Case", "Load case"]
    for tk in T_KEYS:
        for a, _ in ALGOS:
            header += [f"{labels[tk]}, {a}: runs at optimum", f"{labels[tk]}, {a}: median designs evaluated"]
    rows, tex = [], []
    for c in d.ids:
        row, trow = [c, d.names[c]], [c, d.names[c]]
        for tk in T_KEYS:
            r = d.cases[(c, tk)]
            mark = ("" if proven(r) else "\u2021") + ("" if feasible(r) else "\u00a7")
            for _, pre in ALGOS:
                hits, runs, med = conv_cell(d, c, tk, pre)
                m = str(half_up(med)) if med else ("n/a" if not proven(r) else "\u2013")
                row += [f"{hits}/{runs}{mark}", m]
                trow.append(f"{hits}/{runs}{mark} ({m})")
        rows.append(row)
        tex.append(trow)
    top = (r"& & \multicolumn{3}{c}{$t = 0.125$ mm} & \multicolumn{3}{c}{$t = 0.183$ mm} \\ \cmidrule(lr){3-5}"
           r"\cmidrule(lr){6-8}" + "\n")
    note = (f"Entries: runs ending at the optimum out of {d.seeds} (median distinct designs evaluated to reach it). "
            r"$^{\ddagger}$ No proven optimum: runs ending at the best known design; evaluations not recorded. "
            rf"$^{{\S}}$ No feasible design: runs ending at the largest-margin {d.nmax}-ply design.")
    write_table("Table_convergence", header, rows, [top + "Case", "Load case"] + [a for _ in T_KEYS for a, _ in ALGOS], tex,
                "llrrrrrr", "Performance of the algorithms against the exact optimum.", "tab:convergence", note)


# ---------------------------------------------------------------------------------------- FigS2, FigS3
def conv_page(d, s, tk, name, cases, first):
    W, H = 190.0, 128.0
    p = Page(name, W, H, s)
    g = grid(W, H, 13, 4.5, 11, 12.5, 7, 9, 2, 2)
    hits_all = [x["hit_evals"] for x in d.history if x["hit_evals"] is not None]
    x0 = axis_start(min(hits_all))
    xt, yt = (30, 100, 300, 1000, 3000, d.budget), (0, 25, 50, 75, 100)
    axes = []
    for i, c in enumerate(cases):
        rr_, q = i // 2, i % 2
        ax = p.axes(g[rr_][q], (x0, d.budget), (0, 104), xlog=True, xticks=xt, yticks=yt,
                    xlabels=[f"{v:g}" for v in xt] if rr_ == 1 else None, ylabels=[str(v) for v in yt] if q == 0 else None)
        r = d.cases[(c, tk)]
        n_o, m_o = int(r["n_opt"]), float(r["margin_opt"])
        drawn = 0
        for algo, pre in ALGOS:
            rows = [x for x in d.history if (x["case"], x["tkey"], x["model"], x["method"]) == (c, tk, MODEL, pre)]
            ok = [x for x in rows if x["history"][-1][1] == n_o and x["history"][-1][2] >= m_o * (1 - 1e-9)]
            hits = [x["hit_evals"] for x in ok if x["hit_evals"] is not None]
            if proven(r):
                xs, ys = ecdf(hits, len(rows), x0, d.budget)
                p.line(ax, xs, ys, algo, ls=st.ALGO_LS[algo], label=f"{c} {tk} {algo}")
                drawn += len(hits)
        if not drawn:
            bx, by, bw, bh = ax.mm_box
            p.text(bx + bw / 2, by + bh / 2, "no proven optimum" if not proven(r) else "no run reached the optimum", s.legend)
        p.panel(ax, "abcdefgh"[first + i], f"{c} {d.names[c]}")
        axes.append(ax)
    for ax in axes[2:]:
        p.xlabel(ax, "Distinct designs evaluated", 1.2)
    for ax in (axes[0], axes[2]):
        p.ylabel(ax, r"Runs at the optimum (\%)", 3.4)
    for x, (algo, _) in zip((13, 38, 72), ALGOS):
        p.key_line(x, H - 3.5, algo, st.ALGO_NAME[algo], ls=st.ALGO_LS[algo])
    finish(p)


def figS2(d, s):
    conv_page(d, s, "t0125", "FigS2_convergence_t0125_p1", tuple(d.ids[:4]), 0)
    conv_page(d, s, "t0125", "FigS2_convergence_t0125_p2", tuple(d.ids[4:]), 4)


def figS3(d, s):
    conv_page(d, s, "t0183", "FigS3_convergence_t0183_p1", tuple(d.ids[:4]), 0)
    conv_page(d, s, "t0183", "FigS3_convergence_t0183_p2", tuple(d.ids[4:]), 4)


# ---------------------------------------------------------------------------------------------- FigS4
def figS4(d, s, case="C4", tk="t0125"):
    W, H = 190.0, 68.0
    p = Page("FigS4_best_so_far_C4", W, H, s)
    g = grid(W, H, 13, 4.5, 11, 12.5, 7, 0, 1, 3)
    grid_x = np.logspace(math.log10(20), math.log10(d.budget), 501)
    n_o = int(d.cases[(case, tk)]["n_opt"])
    tops, curves = [], []
    for algo, pre in ALGOS:
        rr = [x for x in d.history if (x["case"], x["tkey"], x["model"], x["method"]) == (case, tk, MODEL, pre)]
        vals = np.full((len(rr), len(grid_x)), np.nan)
        for i, run in enumerate(rr):
            h = np.array(run["history"], dtype=float)
            k = np.searchsorted(h[:, 0], grid_x, side="right") - 1
            vals[i, k >= 0] = h[k[k >= 0], 1]
        keep = np.isfinite(vals).all(axis=0)
        v = vals[:, keep]
        curves.append((algo, grid_x[keep], np.percentile(v, 25, axis=0), np.median(v, axis=0), np.percentile(v, 75, axis=0)))
        tops.append(float(np.percentile(v, 75, axis=0).max()))
    yt = list(np.arange(n_o, max(tops) + 0.5, 1))
    xt = (30, 100, 300, 1000, 3000, d.budget)
    for i, (algo, x, lo, med, hi) in enumerate(curves):
        ax = p.axes(g[0][i], (20, d.budget), (n_o - 0.8, max(tops) + 0.5), xlog=True, xticks=xt, yticks=yt,
                    xlabels=[f"{v:g}" for v in xt], ylabels=[f"{int(v)}" for v in yt] if i == 0 else None)
        p.line(ax, x, lo, algo, ls="-", lw=s.thin, label=f"{algo} q25", zorder=3)
        p.line(ax, x, hi, algo, ls="-", lw=s.thin, label=f"{algo} q75", zorder=3)
        p.line(ax, x, med, algo, ls=st.ALGO_LS[algo], label=f"{algo} median", zorder=4)
        p.hline(ax, n_o, ls=":")
        p.panel(ax, "abc"[i], st.ALGO_NAME[algo])
        p.xlabel(ax, "Distinct designs evaluated", 1.2)
    p.ylabel(p.fig.axes[1], "Plies of the best design so far", 3.4)
    y = H - 3.5
    p.key_line(13, y, "exact", "Median", ls="-")
    p.key_line(40, y, "exact", "25th and 75th percentiles", ls="-", lw=s.thin)
    p.key_line(96, y, "exact", "Exact optimum", ls=":", lw=s.ref_lw)
    finish(p)


# ---------------------------------------------------------------------------------------------- FigS5
def figS5(d, s):
    W, H = 190.0, 82.0
    p = Page("FigS5_ritz_before_after", W, H, s)
    g = grid(W, H, 13, 2, 11, 12.5, 6, 0, 1, 2)
    yt = (0, 20, 40, 60)
    top = d.nmax * 1.14
    for i, tk in enumerate(T_KEYS):
        ax = p.axes(g[0][i], (0.4, len(d.ids) + 0.6), (0, top), xticks=range(1, len(d.ids) + 1), yticks=yt,
                    xlabels=d.ids, ylabels=[str(v) for v in yt] if i == 0 else None)
        w, gap = 0.38, 0.015
        for j, c in enumerate(d.ids):
            for role, row, xa in (("qi", d.old[(c, tk)], j + 1 - w - gap), ("opt", d.cases[(c, tk)], j + 1 + gap)):
                xb = xa + w
                ym = float(p.X(ax, (xa + xb) / 2))
                if feasible(row):
                    n = int(row["n_opt"])
                    p.bar(ax, xa, xb, n, role, mark="s" if role == "qi" else "o")
                    p.text(ym, float(p.Y(ax, n)) + s.pad * 0.9, str(n), s.barnum, va="bottom")
                else:
                    p.hatch_bar(ax, xa, xb, d.nmax, role)
                    if role == "opt":       # one label for the pair: both models have no feasible design here
                        p.text(float(p.X(ax, j + 1)), float(p.Y(ax, d.nmax)) + s.pad * 0.9, f"${{>}}{d.nmax}$", s.barnum, va="bottom")
        p.panel(ax, "ab"[i], st.THICK_TEXT[tk])
        p.xlabel(ax, "Load case", 1.2)
    p.ylabel(p.fig.axes[1], "Optimised plies", 3.4)
    p.key_bar(13, H - 3.5, "qi", "Before: closed form, shear buckling not checked", mark="s")
    p.key_bar(104, H - 3.5, "opt", "After: Rayleigh-Ritz", mark="o")
    finish(p)


# ---------------------------------------------------------------------------------------------- tables
def sci(v):
    v = float(v)
    if v == 0:
        return "0"
    e = int(math.floor(math.log10(abs(v))))
    return f"{MINUS if v < 0 else ''}{abs(v) / 10 ** e:.1f} \u00d7 10^{e}"


def tex_cell(x):
    x = str(x)
    if " \u00d7 10^" in x:
        m, e = x.split(" \u00d7 10^")
        return f"${m.replace(MINUS, '-')} \\times 10^{{{e}}}$"
    if x.startswith("$"):
        return x
    for a, b in (("%", r"\%"), (">", "$>$"), (MINUS, "$-$"), ("\u2021", r"$^{\ddagger}$"), ("\u00a7", r"$^{\S}$"), ("\u00d7", r"$\times$")):
        x = x.replace(a, b)
    return x


def write_table(name, header, rows, tex_header, tex_rows, align, caption, label, note=""):
    folder = os.path.join(BASE, "tables")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, f"{name}.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    out = [r"% requires \usepackage{booktabs}", r"\begin{table}[htbp]", r"\centering", f"\\caption{{{caption}}}",
           f"\\label{{{label}}}", f"\\begin{{tabular}}{{{align}}}", r"\toprule", " & ".join(tex_header) + r" \\", r"\midrule"]
    out += [" & ".join(tex_cell(c) for c in r) + r" \\" for r in tex_rows]
    out += [r"\bottomrule", r"\end{tabular}"]
    if note:
        out += [r"\par\smallskip", r"{\footnotesize " + note + "}"]
    out += [r"\end{table}", ""]
    with open(os.path.join(folder, f"{name}.tex"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def table_lh(d):
    header = ["Case", "Plies", "N_y/N_x", "\u03bb_cr source (lb/in)", "\u03bb_cr this study (lb/in)", "Difference (%)",
              "Reference value from"]
    tex = ["Case", "Plies", r"$N_y/N_x$", r"$\lambda_{\mathrm{cr}}$ source (lb/in)",
           r"$\lambda_{\mathrm{cr}}$ this study (lb/in)", r"Difference (\%)", "Reference value from"]
    rows = []
    for r in d.lh:
        rows.append([r["case"], r["plies"], f"{float(r['Ny_over_Nx']):g}", f"{float(r['lambda_paper']):.2f}",
                     f"{float(r['lambda_exhaustive']):.2f}", f"{float(r['rel_diff_vs_paper']) * 100:+.5f}%",
                     r["paper_ref"].replace("[T] ", "Le Riche (1994), ")])
    note = (r"$\lambda_{\mathrm{cr}}$ multiplies the reference load $N_x = 1$ lb/in, $N_y = (N_y/N_x)$ lb/in, so its value "
            r"equals the critical $N_x$ in lb/in. This study: exhaustive enumeration of the design space.")
    write_table("Table_leriche_haftka", header, rows, tex, rows, "lrrrrrl",
                "Le Riche and Haftka benchmark: reference values and exhaustive search of this study.",
                "tab:leriche_haftka", note)


# ------------------------------------------------------------------------------------------- README
def table_shear(d):
    header = ["Case", "t (mm)", "One direction: n*", "One direction: RF_min", "RF_min if N_xy reverses", "One direction: saving (%)",
              "Both directions: n", "Both directions: RF_min", "Both directions: status", "Both directions: saving (%)"]
    tex = ["Case", r"$t$ (mm)", r"$n^{*}$", r"$RF_{\min}$", r"$RF_{\min}$ reversed", r"Saving (\%)", r"$\pm N_{xy}$: $n$",
           r"$\pm N_{xy}$: $RF_{\min}$", "Status", r"Saving (\%)"]
    rows = []
    for (c, tk), q in d.shear.items():
        r = d.cases[(c, tk)]
        limit = f"> {d.nmax}"
        rows.append([c, f"{float(r['ply_thickness_mm']):.3f}", q["one_n"] if feasible(r) else limit, f"{float(q['one_margin']):.4f}",
                     f"{float(q['one_margin_reversed']):.4f}", f"{float(q['one_saving_pct']):.1f}" if q["one_saving_pct"] else "n/a",
                     q["both_n"] if q["both_feasible"] == "True" else limit, f"{float(q['both_margin']):.4f}", q["both_status"],
                     f"{float(q['both_saving_pct']):.1f}" if q["both_saving_pct"] else "n/a"])
    write_table("Table_shear_directions", header, rows, tex, rows, "lrrrrrrrlr",
                "Optimum for shear of one sign and for shear of both signs.", "tab:shear_directions")


def captions(d):
    t1, t2 = "t = 0.125 mm", "t = 0.183 mm"
    best = {a: d.cases[("C5", "t0125")][f"{p}_reach_reference"] for a, p in ALGOS}
    c8 = float(d.cases[("C8", "t0125")]["margin_opt"])
    runs = d.seeds
    one = "Results are for shear of one sign."
    last = {max(q["n"] for q in d.fronts[f"{c}|{tk}|{MODEL}"]["exact_per_n"] if q["max_margin"] is not None)
            for c in ("C4", "C5", "C7") for tk in T_KEYS}
    assert len(last) == 1
    last = last.pop()
    # the sentences below state these facts in words: stop if the data no longer support them
    assert not feasible(d.cases[("C8", "t0125")]) and feasible(d.cases[("C8", "t0183")]) and not feasible(d.old[("C8", "t0125")])
    assert not proven(d.cases[("C5", "t0125")]) and d.cases[("C5", "t0125")]["n_proven_by_bound"] == "True"
    assert {c for (c, tk), r in d.cases.items() if feasible(r) and int(d.old[(c, tk)]["n_opt"]) != int(r["n_opt"])} == {"C5"}
    return {
        "Fig1": "Workflow of the agent. Python rules classify a request written in English or Vietnamese; the LLM only "
                "confirms weak design wording, and unclear or contradictory text is refused with a hint. Analysis requests "
                "use classical laminate theory in MATLAB, design requests use the optimiser and a final check of the design, "
                "and questions on material data follow a separate retrieval branch. Python checks every LLM output.",
        "Fig2": f"Convergence on the Le Riche and Haftka benchmark: share of {d.lh[0]['ga_runs']} runs at the exact optimum "
                f"against the number of distinct designs evaluated, for the GA (dashed line, hollow markers) and GA + local "
                f"search (solid line, filled markers). The exact optimum comes from exhaustive enumeration.",
        "Fig3": f"Pareto fronts between the number of plies n and the smallest reserve factor RF_min for four load cases, "
                f"{t1} and {t2}. Lines: exact non-dominated front, ending at n = {last} for C4, C5 and C7. Hollow markers: "
                f"final NSGA-II fronts of all seeds. Filled diamonds: optimum, the fewest plies with RF_min \u2265 {d.sf:g}. "
                f"The vertical axis stops at RF_min = {PARETO_TOP} so that the region around the constraint stays readable; "
                f"the fronts continue above it. In C5 with {t1} the optimum has a proven ply count and the best known "
                f"RF_min. {one}",
        "Fig4": f"Plies needed for RF_min \u2265 {d.sf:g}: smallest quasi-isotropic [0/\u00b145/90]ns laminate against the optimised "
                f"stacking sequence, for (a) {t1} and (b) {t2}. Percentages under the case names are the mass saving, "
                f"(n_QI \u2212 n*)/n_QI, rounded to whole numbers; both laminates use the same ply, so plies and mass are "
                f"proportional. The hatched column marks C8 with {t1}, which has no feasible design within {d.nmax} plies "
                f"(largest RF_min = {c8:.2f}). The ply limit applies to the optimiser only. {one}",
        "Fig5": f"Runs out of {runs} that end at the optimum, for each algorithm and load case, (a) {t1} and (b) {t2}, with a "
                f"budget of {d.budget} distinct designs. C5 with {t1} has no proven optimum, so its columns count the runs at "
                f"the best known design ({best['GA']}, {best['NSGA-II']} and {best['GA + LS']} runs for GA, NSGA-II and GA + "
                f"local search). C8 with {t1} has no feasible design, so its columns count the runs at the largest-margin "
                f"{d.nmax}-ply design. Median evaluations are in Table_convergence. {one}",
        "FigS1": f"Pareto fronts of all eight load cases, {t1} and {t2}, in two parts. Symbols as in Fig. 3. C8 with {t1} has "
                 f"no feasible design within {d.nmax} plies, so no optimum is marked for it.",
        "FigS2": f"Share of runs ending at the optimum against distinct designs evaluated, {t1}, {runs} seeds, in two parts. "
                 f"C5 has no proven optimum, so no curves can be drawn: evaluations to the best known design were not recorded.",
        "FigS3": f"Share of runs ending at the optimum against distinct designs evaluated, {t2}, {runs} seeds, in two parts.",
        "FigS4": f"Plies of the best design so far, C4 Biaxial compression, {t1}: median of {runs} runs with the 25th and 75th "
                 f"percentiles. Curves start once every run has a best design. Odd median values are midpoints between runs "
                 f"at two even ply counts.",
        "FigS5": f"Optimised plies with the previous buckling model (closed form, D_16 = D_26 = 0, shear buckling not checked) "
                 f"and with Rayleigh-Ritz including D_16, D_26 and N_xy, for (a) {t1} and (b) {t2}. Only pure shear changes the "
                 f"ply count. Hatched columns: C8 with {t1}, with no feasible design within {d.nmax} plies in either model.",
    }


FIG_FILES = (("Fig1", ["Fig1_workflow"], "python\\main.py, router.py, llm.py, rag.py, design.py, ml.py, materials.py, matlab_clt.py"),
             ("Fig2", ["Fig2_leriche_haftka"], "leriche_haftka_summary.csv, leriche_haftka_histories.json"),
             ("Fig3", ["Fig3_pareto"], "fronts.json, cases_summary.csv"),
             ("Fig4", ["Fig4_qi_comparison"], "cases_summary.csv, fronts.json (ply limit)"),
             ("Fig5", ["Fig5_algorithms"], "cases_summary.csv, run_cases_meta.json"),
             ("FigS1", ["FigS1_pareto_all_C1_C4", "FigS1_pareto_all_C5_C8"], "fronts.json, cases_summary.csv"),
             ("FigS2", ["FigS2_convergence_t0125_p1", "FigS2_convergence_t0125_p2"], "runs_history.json, cases_summary.csv"),
             ("FigS3", ["FigS3_convergence_t0183_p1", "FigS3_convergence_t0183_p2"], "runs_history.json, cases_summary.csv"),
             ("FigS4", ["FigS4_best_so_far_C4"], "runs_history.json, cases_summary.csv"),
             ("FigS5", ["FigS5_ritz_before_after"], "before_ritz\\cases_summary.csv, cases_summary.csv"))


def write_readme(d):
    cap = captions(d)
    with open(os.path.join(BASE, "_captions.json"), "w", encoding="utf-8") as f:
        json.dump(cap, f, ensure_ascii=False, indent=1)
    py = r"python deliverables\figures_v2\python\make_all.py"
    md = ["# Figures, Python and MATLAB versions", "",
          "All figures and tables are generated from the stored files in deliverables\\optimization\\results\\. Nothing is "
          "recomputed. Python and MATLAB versions share the same layout in millimetres.", "", "## Regenerate", "",
          "Python, in a VS Code terminal at D:\\CompositeAgent:", "", "```", r"venv_fig\Scripts\activate", py,
          r"python deliverables\figures_v2\compare.py", r"python deliverables\figures_v2\verify_numbers.py", "```", "",
          "MATLAB: cd to deliverables\\figures_v2\\matlab, then run make_all. It writes the PDF files in _raw and calls "
          "postprocess.py with venv_fig, which scales them to the journal size and makes the PNG files.", "",
          "One figure only: `" + py + " Fig3`, or make_all(\"Fig3\") in MATLAB.", ""]
    for key, stems, source in FIG_FILES:
        md += [f"## {key}", ""]
        for stem in stems:
            md.append(f"- python\\pdf\\{stem}.pdf, python\\png\\{stem}.png; matlab\\pdf\\{stem}.pdf, matlab\\png\\{stem}.png; "
                      f"compare\\{stem}_compare.png")
        if key in SLIDE_FIGS:
            names = [f"{stems[0]}_{tk}_slide.png" for tk in T_KEYS] if key in ("Fig4", "Fig5") else [f"{stems[0]}_slide.png"]
            md.append("- Slides: " + ", ".join(names) + " (in python\\slides and matlab\\slides)")
        md += [f"- Data: {source}", f"- Regenerate: `{py} {key}`", "", f"**Caption.** {cap[key]}", ""]
    md += ["## Tables", "", "tables\\ holds Table_load_cases, Table_leriche_haftka, Table_convergence and "
           "Table_shear_directions, each as .csv (UTF-8 with BOM) and .tex (needs booktabs).", "", "## Unit of \u03bb_cr", "",
           "In LH-A to LH-D, \u03bb_cr multiplies a reference load N_x = 1 lb/in (python\\optimization\\leriche_haftka.py, "
           "`problem`: \"Nx = 1 lb/in, so lambda is in lb/in as in the source\"). Its value equals the critical N_x in lb/in.", ""]
    with open(os.path.join(BASE, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))


# ---------------------------------------------------------------------------------------------- driver
PAPER_FIGS = {"Fig1": fig1, "Fig2": fig2, "Fig3": fig3, "Fig4": fig4, "Fig5": fig5, "FigS1": figS1, "FigS2": figS2,
              "FigS3": figS3, "FigS4": figS4, "FigS5": figS5}
SLIDE_FIGS = ("Fig1", "Fig2", "Fig3", "Fig4", "Fig5")


def main(names):
    st.use_style()
    d = Data()
    for nm in names or PAPER_FIGS:
        PAPER_FIGS[nm](d, PAPER)
        if nm in SLIDE_FIGS:
            PAPER_FIGS[nm](d, SLIDE)
    table_lh(d)
    table_load_cases(d)
    table_convergence(d)
    table_shear(d)
    write_readme(d)
    path = os.path.join(HERE, "_report_python.json")
    old = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            old = json.load(f)
    done = {(r["name"], r["mode"]) for r in REPORT}
    with open(path, "w", encoding="utf-8") as f:
        json.dump([r for r in old if (r["name"], r["mode"]) not in done] + REPORT, f, ensure_ascii=False, indent=0)
    bad = sum(len(r["collisions"]) + len(r["colours"]) for r in REPORT)
    print("problems:", bad)
    for r in REPORT:
        for b in r["collisions"][:6] + r["colours"][:6]:
            print(" ", r["name"], r["mode"], b)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main(sys.argv[1:])
