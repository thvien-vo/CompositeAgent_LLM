"""
Figures (PNG) from the result files of run_cases.py and leriche_haftka_exp.py.
Colours: validated categorical palette (blue, orange, aqua; dataviz reference palette, light mode);
every figure has a CSV table next to it in results/ (relief for the low-contrast aqua).
Run: python -m optimization.experiments.make_figures
"""
from __future__ import annotations

import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from optimization.experiments.cases import CASES, SAFETY_FACTOR, THICKNESS_LABEL  # noqa: E402
from optimization.experiments.common import FIGS, RESULTS, read_json, setup  # noqa: E402

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 9, "axes.titlesize": 10,
    "lines.linewidth": 2.0, "legend.frameon": False,
})


def _read_csv(name):
    with open(os.path.join(RESULTS, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def pareto(tkey="t0125", model="closed_form"):
    fronts = read_json("fronts.json")
    fig, axes = plt.subplots(2, 4, figsize=(13, 6.2), constrained_layout=True)
    for ax, c in zip(axes.flat, CASES):
        key = f"{c['id']}|{tkey}|{model}"
        if key not in fronts:
            ax.set_visible(False)
            continue
        f = fronts[key]
        ex = [(q["n"], q["max_margin"]) for q in f["exact_per_n"] if q["max_margin"] is not None]
        ub = [(q["n"], q["margin_upper_bound"]) for q in f["bounds"]]
        nmax = max([n for n, _ in ex] + [0])
        for fr in f["nsga2_fronts"]:
            pts = [(n, m) for n, m in fr if n <= max(nmax, 20)]
            if pts:
                ax.plot(*zip(*pts), "o", ms=6, color=ORANGE, alpha=0.35, mec=SURF, mew=1.0,
                        label="NSGA-II front (each seed)" if fr is f["nsga2_fronts"][0] else None)
        if ex:
            ax.plot(*zip(*ex), "-", color=BLUE, label="exact best margin per ply count")
            ax.plot(*zip(*ex), "o", ms=4, color=BLUE)
        ubx = [(n, m) for n, m in ub if n <= max(nmax, 20)]
        if ubx:
            ax.plot(*zip(*ubx), ":", color=INK2, lw=1.2, label="proven upper bound")
        ax.axhline(SAFETY_FACTOR, color=INK2, lw=1.0, ls="--")
        ax.text(ax.get_xlim()[0] if False else 8.2, SAFETY_FACTOR, " SF = 1.5", va="bottom", color=INK2, fontsize=8)
        ax.set_title(f"{c['id']} {c['en']}\nNx, Ny, Nxy = {', '.join(f'{v:g}' for v in c['loads'])} N/m")
        ax.set_xlabel("number of plies n (-)")
        ax.set_ylabel("safety margin = min RF (-)")
        ys = [m for _, m in ex] + [SAFETY_FACTOR]
        ax.set_ylim(0, min(max(ys) * 1.15, 12))
        ax.set_xlim(7, max(nmax, 20) + 1)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.05))
    fig.suptitle(f"Pareto front: plies vs safety margin (IM7/8552, ply {THICKNESS_LABEL[tkey]}, plate 0.5 x 0.5 m)",
                 fontsize=11)
    out = os.path.join(FIGS, f"pareto_{tkey}.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def convergence(tkey="t0125", model="closed_form"):
    """Share of runs that have found the exact optimum vs number of evaluations (ECDF of evals-to-hit)."""
    runs = read_json("runs_history.json")
    meta = read_json("run_cases_meta.json")
    budget = meta["budget"]
    fig, axes = plt.subplots(2, 4, figsize=(13, 6.0), constrained_layout=True, sharey=True)
    for ax, c in zip(axes.flat, CASES):
        for m, col, lab in (("ga", BLUE, "GA"), ("nsga2", ORANGE, "NSGA-II")):
            rr = [r for r in runs if (r["case"], r["tkey"], r["model"], r["method"]) == (c["id"], tkey, model, m)]
            if not rr:
                continue
            hits = sorted(r["hit_evals"] for r in rr if r["hit_evals"] is not None)
            xs = np.concatenate([[0], np.repeat(hits, 2), [budget]])
            ys = np.concatenate([[0, 0], np.repeat(np.arange(1, len(hits) + 1) / len(rr), 2)])[: len(xs)]
            ax.plot(xs, ys, "-", color=col, label=f"{lab} ({len(hits)}/{len(rr)} runs)")
        ax.set_title(f"{c['id']} {c['en']}")
        ax.set_xlabel("distinct designs evaluated (-)")
        ax.set_ylabel("share of runs at the exact optimum (-)")
        ax.set_xlim(0, budget)
        ax.set_ylim(0, 1.05)
        ax.legend(loc="lower right", fontsize=8)
    fig.suptitle(f"Convergence: runs that reached the exhaustive-search optimum (ply {THICKNESS_LABEL[tkey]}, "
                 f"{len(meta['seeds'])} seeds each)", fontsize=11)
    out = os.path.join(FIGS, f"convergence_{tkey}.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def best_so_far(tkey="t0125", model="closed_form", case="C4"):
    """Median best ply count / margin of the best design so far, GA vs NSGA-II, one case."""
    runs = read_json("runs_history.json")
    meta = read_json("run_cases_meta.json")
    grid = np.linspace(0, meta["budget"], 201)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8), constrained_layout=True)
    for m, col, lab in (("ga", BLUE, "GA"), ("nsga2", ORANGE, "NSGA-II")):
        rr = [r for r in runs if (r["case"], r["tkey"], r["model"], r["method"]) == (case, tkey, model, m)]
        N = np.full((len(rr), len(grid)), np.nan)
        M = np.full((len(rr), len(grid)), np.nan)
        for i, r in enumerate(rr):
            h = np.array(r["history"], dtype=float)
            for j, g in enumerate(grid):
                k = np.searchsorted(h[:, 0], g, side="right") - 1
                if k >= 0:
                    N[i, j], M[i, j] = h[k, 1], h[k, 2]
        for ax, A in ((axes[0], N), (axes[1], M)):
            med = np.nanmedian(A, axis=0)
            lo, hi = np.nanpercentile(A, 25, axis=0), np.nanpercentile(A, 75, axis=0)
            ax.fill_between(grid, lo, hi, color=col, alpha=0.15, lw=0)
            ax.plot(grid, med, color=col, label=f"{lab} median (band: 25-75 %)")
    axes[0].set_ylabel("plies of best design so far (-)")
    axes[1].set_ylabel("margin of best design so far (-)")
    axes[1].axhline(SAFETY_FACTOR, color=INK2, lw=1.0, ls="--")
    for ax in axes:
        ax.set_xlabel("distinct designs evaluated (-)")
        ax.legend(fontsize=8)
    name = next(c["en"] for c in CASES if c["id"] == case)
    fig.suptitle(f"Best-so-far design, {case} {name} (ply {THICKNESS_LABEL[tkey]})", fontsize=11)
    out = os.path.join(FIGS, f"best_so_far_{case}_{tkey}.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def quasi_iso():
    rows = [r for r in _read_csv("cases_summary.csv") if r["model"] == "closed_form"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2), constrained_layout=True, sharey=True)
    for ax, tk in zip(axes, ("t0125", "t0183")):
        rr = [r for r in rows if r["thickness"] == tk]
        x = np.arange(len(rr))
        qi = [_num(r["qi_n"]) for r in rr]
        opt = [_num(r["n_opt"]) for r in rr]
        w = 0.38
        ax.bar(x - w / 2 - 0.01, [q or 0 for q in qi], w, color=INK2, alpha=0.55, label="quasi-isotropic [0/±45/90]ns")
        ax.bar(x + w / 2 + 0.01, opt, w, color=BLUE, label="optimised stacking sequence")
        for i, r in enumerate(rr):
            red = _num(r["mass_reduction_pct"])
            feas = r["feasible"] == "True"
            lab = f"-{red:.0f} %" if red is not None else ("infeasible\n<= 64 plies" if not feas else "")
            ax.text(x[i] + w / 2, (opt[i] or 0) + 1.5, lab, ha="center", va="bottom", fontsize=8, color=INK)
            if qi[i]:
                ax.text(x[i] - w / 2, qi[i] + 0.5, f"{int(qi[i])}", ha="center", va="bottom", fontsize=7, color=INK2)
        ax.axhline(64, color=INK2, lw=1.0, ls="--")
        ax.text(len(rr) - 0.5, 64, "optimizer limit 64 plies", ha="right", va="bottom", fontsize=8, color=INK2)
        ax.set_xticks(x, [f"{r['case']}\n{r['name_en']}" for r in rr], fontsize=7.5)
        ax.set_ylabel("plies needed for margin >= 1.5 (-)")
        ax.set_title(f"ply {THICKNESS_LABEL[tk]}  (label: mass saving vs quasi-isotropic)")
        ax.legend(loc="upper left", fontsize=8)
    fig.suptitle("Optimised laminate vs smallest quasi-isotropic laminate meeting the same margin", fontsize=11)
    out = os.path.join(FIGS, "quasi_isotropic_comparison.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def leriche():
    s = _read_csv("leriche_haftka_summary.csv")
    hist = read_json("leriche_haftka_histories.json")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), constrained_layout=True)
    ax = axes[0]
    x = np.arange(len(s))
    paper = [_num(r["lambda_paper"]) for r in s]
    ours = [_num(r["lambda_exhaustive"]) for r in s]
    w = 0.38
    ax.bar(x - w / 2 - 0.01, paper, w, color=INK2, alpha=0.55, label="value reported by Le Riche (1994 / 1993)")
    ax.bar(x + w / 2 + 0.01, ours, w, color=BLUE, label="exhaustive search, this work")
    for i, r in enumerate(s):
        ax.text(x[i] + w / 2, ours[i] * 1.01, f"{ours[i]:.2f}\n({_num(r['rel_diff_vs_paper']) * 100:+.4f} %)",
                ha="center", va="bottom", fontsize=7.5)
    ax.set_xticks(x, [f"{r['case']}\n{r['plies']} plies, Ny/Nx={_num(r['Ny_over_Nx']):g}" for r in s], fontsize=8)
    ax.set_ylabel("critical load factor lambda_cr (lb/in)")
    ax.set_ylim(0, max(ours + paper) * 1.25)
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title("Global optimum: source vs exhaustive search")
    ax = axes[1]
    cols = [BLUE, ORANGE, AQUA, INK2]
    for (cid, h), col in zip(hist.items(), cols):
        runs = h["runs"]
        hits = sorted(r["hit_evals"] for r in runs if r["hit_evals"] is not None)
        budget = max(r["n_evaluations"] for r in runs)
        xs = np.concatenate([[0], np.repeat(hits, 2), [budget]])
        ys = np.concatenate([[0, 0], np.repeat(np.arange(1, len(hits) + 1) / len(runs), 2)])[: len(xs)]
        ax.plot(xs, ys, color=col, label=f"{cid} ({len(hits)}/{len(runs)})")
    ax.set_xlabel("distinct designs evaluated (-)")
    ax.set_ylabel("share of GA runs at the exact optimum (-)")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=8, loc="lower right")
    ax.set_title("GA convergence on the benchmark")
    out = os.path.join(FIGS, "leriche_haftka.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def main():
    setup()
    made = []
    for fn, args in ((pareto, ("t0125",)), (pareto, ("t0183",)), (convergence, ("t0125",)),
                     (convergence, ("t0183",)), (best_so_far, ("t0125", "closed_form", "C4")),
                     (quasi_iso, ()), (leriche, ())):
        try:
            made.append(fn(*args))
        except FileNotFoundError as e:
            print(f"skip {fn.__name__}: {e}")
    for m in made:
        print("figure:", m)


if __name__ == "__main__":
    main()
