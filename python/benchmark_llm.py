"""
benchmark_llm.py - compare how well each LLM backend extracts CLT input data from text.

For every test problem we know the correct answer (written by hand). Each backend/prompt version
reads the text; we compare material, number of plies, angles, thicknesses and the 6 loads.
A case counts as CORRECT only if everything matches (tolerance 1e-6 relative).

Run:
  python benchmark_llm.py                       -> dev set, versions v1 (original) + v3 (current), hf+ollama
  python benchmark_llm.py --set holdout         -> held-out set (never used to tune the prompt)
  python benchmark_llm.py --versions v3 --backends ollama --repeat 3
Results: ../deliverables/benchmark/llm_benchmark_<set>_<time>.json and .md
"""
import argparse
import datetime
import json
import os
import time

import llm
import llm_v1_baseline

LBF_IN = 4.4482216152605 / 0.0254  # 1 lbf/in in N/m


def P(material, angles, t, **loads):
    """Expected answer. t = one thickness (m) for all plies, or a list per ply."""
    ts = t if isinstance(t, list) else [t] * len(angles)
    return {"material": material, "angles": [float(a) for a in angles], "thickness": ts,
            "loads": {k: float(loads.get(k, 0.0)) for k in llm.LOAD_KEYS}}


DEV = [
    ("D1 en, 4 plies list, mm",
     "CFRP laminate. Ply angles: 0, 45, -45, 90. Ply thickness: 0.125 mm. Nx=1000 N/m. Ny=500 N/m. Nxy=100 N/m.",
     P("CFRP", [0, 45, -45, 90], 0.000125, Nx=1000, Ny=500, Nxy=100)),
    ("D2 en, [..]s 8 plies (= demo.py case)",
     "Carbon/epoxy laminate [0/45/-45/90]s, each ply 0.125 mm thick. In-plane loads: Nx = 1000 N/m, "
     "Ny = 500 N/m, Nxy = 100 N/m. No moments.",
     P("CFRP", [0, 45, -45, 90, 90, -45, 45, 0], 0.000125, Nx=1000, Ny=500, Nxy=100)),
    ("D3 en, [..]2s, kN/m, negative load",
     "Glass fibre / epoxy plate with stacking sequence [0/90]2s. Ply thickness 0.2 mm. "
     "Applied loads: Nx = 2 kN/m, Ny = -1.5 kN/m.",
     P("GFRP", [0, 90, 0, 90, 90, 0, 90, 0], 0.0002, Nx=2000, Ny=-1500)),
    ("D4 en, Kevlar, thickness in m, moment",
     "Kevlar 49/epoxy laminate, 3 plies at 0°, 90°, 0°. Each ply is 0.00015 m thick. "
     "Loading: Nx = 500 N/m and bending moment Mx = 2 N·m/m.",
     P("KEVLAR", [0, 90, 0], 0.00015, Nx=500, Mx=2)),
    ("D5 vi, [0/±45]s, decimal comma, moment",
     "Tấm composite sợi thủy tinh/epoxy, xếp lớp [0/±45]s, mỗi lớp dày 0,15 mm. "
     "Tải trọng: Nx = 1200 N/m, Nxy = 300 N/m, mô-men uốn My = 5 N.m/m.",
     P("GFRP", [0, 45, -45, -45, 45, 0], 0.00015, Nx=1200, Nxy=300, My=5)),
    ("D6 en, total thickness, N/mm",
     "An 8-ply carbon fibre laminate [0/90/45/-45]s has a total thickness of 1.2 mm (all plies equal). "
     "Loads: Nx = 1.5 N/mm, Ny = 0.5 N/mm, Nxy = 0.",
     P("CFRP", [0, 90, 45, -45, -45, 45, 90, 0], 0.00015, Nx=1500, Ny=500)),
    ("D7 en, different ply thickness, µm, pure bending",
     "CFRP cross-ply: 0° ply 200 µm, 90° ply 100 µm, 90° ply 100 µm, 0° ply 200 µm. "
     "Pure bending: Mx = 10 N·m/m, My = -4 N·m/m, Mxy = 1 N·m/m. No in-plane forces.",
     P("CFRP", [0, 90, 90, 0], [0.0002, 0.0001, 0.0001, 0.0002], Mx=10, My=-4, Mxy=1)),
    ("D8 en, T300/5208, [±30]2s, negative shear",
     "T300/5208 carbon-epoxy, layup [±30]2s, t_ply = 0.127 mm. Nxy = -250 N/m only.",
     P("CFRP", [30, -30, 30, -30, -30, 30, -30, 30], 0.000127, Nxy=-250)),
    ("D9 vi, 5 plies list, kN/m, N·mm/m",
     "Vật liệu: sợi carbon. 5 lớp với góc lần lượt 0, 30, 60, 90, 0 độ; mỗi lớp 0.25 mm. "
     "Chịu lực kéo Nx = 3 kN/m và mô-men xoắn Mxy = 1500 N·mm/m.",
     P("CFRP", [0, 30, 60, 90, 0], 0.00025, Nx=3000, Mxy=1.5)),
    ("D10 en, aramid 2 plies, all 6 loads",
     "Aramid fibre composite, two plies [45/-45] (antisymmetric), each 0.3 mm. Nx = 800 N/m, Ny = 200 N/m, "
     "Nxy = 50 N/m, Mx = 0.5 N·m/m, My = 0.2 N·m/m, Mxy = 0.1 N·m/m.",
     P("KEVLAR", [45, -45], 0.0003, Nx=800, Ny=200, Nxy=50, Mx=0.5, My=0.2, Mxy=0.1)),
]

# Written on 27/10/2026 together with DEV, but NOT used while tuning the v2 prompt.
HOLDOUT = [
    ("H1 en, IM7/8552 [45/0/-45/90]2s 16 plies, kN/m, Mxy",
     "Analyse a quasi-isotropic IM7/8552 laminate [45/0/-45/90]2s with 0.183 mm plies under "
     "Nx = 25 kN/m and Mxy = -0.8 N·m/m.",
     P("CFRP", [45, 0, -45, 90, 45, 0, -45, 90, 90, -45, 0, 45, 90, -45, 0, 45], 0.000183,
       Nx=25000, Mxy=-0.8)),
    ("H2 vi, Kevlar, total thickness 0,8 mm",
     "Cho tấm Kevlar/epoxy gồm 4 lớp: 0°, 90°, 90°, 0°. Tổng chiều dày tấm là 0,8 mm. "
     "Tấm chịu Ny = 750 N/m và Nxy = -120 N/m.",
     P("KEVLAR", [0, 90, 90, 0], 0.0002, Ny=750, Nxy=-120)),
    ("H3 en, imperial units (in, lbf/in)",
     "E-glass/epoxy [0/90/0], ply thickness 0.005 in, Nx = 100 lbf/in.",
     P("GFRP", [0, 90, 0], 0.000127, Nx=100 * LBF_IN)),
    ("H4 en, compact style, compression + moment",
     "AS4/3501-6, 6 plies: 0/60/-60/-60/60/0, t = 0.15mm each, Nx=-800N/m (compression), Ny=0, "
     "Nxy=200N/m, Mx=0.3 N.m/m",
     P("CFRP", [0, 60, -60, -60, 60, 0], 0.00015, Nx=-800, Nxy=200, Mx=0.3)),
    ("H5 vi, [0/90]s, only moment in N·mm/mm",
     "Tấm CFRP [0/90]s, mỗi lớp 0,125 mm, chỉ chịu mô-men uốn Mx = 2,5 N·mm/mm.",
     P("CFRP", [0, 90, 90, 0], 0.000125, Mx=2.5)),
    ("H6 en, fiberglass 5 plies different thickness",
     "Fiberglass laminate, from bottom to top: 45° (0.3 mm), -45° (0.3 mm), 0° (0.5 mm), -45° (0.3 mm), "
     "45° (0.3 mm). Loads Nx = 4000 N/m, Ny = 1000 N/m.",
     P("GFRP", [45, -45, 0, -45, 45], [0.0003, 0.0003, 0.0005, 0.0003, 0.0003], Nx=4000, Ny=1000)),
]

# Written on 27/10/2026 18:35, AFTER holdout was run once (v3 ollama 4/6) and BEFORE the
# thickness / ply-count checks were added; run only once after those changes.
HOLDOUT2 = [
    ("N1 en, [..]T notation, kN/m",
     "Compute the CLT response of a [0/90/0/90]T E-glass/epoxy laminate. Each ply: 0.25 mm. "
     "Loads: Nx = 5 kN/m, Ny = 5 kN/m.",
     P("GFRP", [0, 90, 0, 90], 0.00025, Nx=5000, Ny=5000)),
    ("N2 vi, 6 plies listed, total thickness, moment",
     "Tấm 6 lớp sợi carbon/epoxy, các lớp lần lượt 0°, 60°, -60°, -60°, 60°, 0°, tổng chiều dày 0,9 mm. "
     "Chịu Nx = 600 N/m, Mx = 1,2 N·m/m.",
     P("CFRP", [0, 60, -60, -60, 60, 0], 0.00015, Nx=600, Mx=1.2)),
    ("N3 en, Kevlar [0/90]s, shear + twisting moment",
     "Kevlar/epoxy symmetric cross-ply [0/90]s with ply thickness 0.1 mm, subjected to shear "
     "Nxy = 150 N/m and twisting moment Mxy = 0.05 N·m/m.",
     P("KEVLAR", [0, 90, 90, 0], 0.0001, Nxy=150, Mxy=0.05)),
    ("N4 en, graphite, load in words (no symbol)",
     "A graphite/epoxy 4-ply laminate [45/-45/-45/45] with 0.15 mm plies carries an in-plane force of "
     "2 N/mm in the x direction.",
     P("CFRP", [45, -45, -45, 45], 0.00015, Nx=2000)),
    ("N5 vi, 3 plies, thickness per ply",
     "Tấm GFRP 3 lớp: lớp 1 góc 0° dày 0,4 mm; lớp 2 góc 90° dày 0,2 mm; lớp 3 góc 0° dày 0,4 mm. "
     "Tải Nx = 2500 N/m, Ny = 400 N/m.",
     P("GFRP", [0, 90, 0], [0.0004, 0.0002, 0.0004], Nx=2500, Ny=400)),
    ("N6 en, [0/±45/90]s, total thickness, 4 loads",
     "CFRP [0/±45/90]s, total laminate thickness 1.6 mm, Nx = -2 kN/m, Ny = 1 kN/m, Nxy = 0.5 kN/m, "
     "Mx = 0.4 N·m/m.",
     P("CFRP", [0, 45, -45, 90, 90, -45, 45, 0], 0.0002, Nx=-2000, Ny=1000, Nxy=500, Mx=0.4)),
]

# Written on 27/10/2026 18:45, BEFORE the SI-grounding + explicit-load reading were run on anything;
# run only once with that final code.
HOLDOUT3 = [
    ("T1 en, S2-glass [90/0/90], kN/m mixed, Mxy",
     "Laminate: S2-glass/epoxy, stacking [90/0/90], plies of 0.3 mm. Apply Nx = 900 N/m, Ny = 2.4 kN/m "
     "and Mxy = 0.15 N·m/m.",
     P("GFRP", [90, 0, 90], 0.0003, Nx=900, Ny=2400, Mxy=0.15)),
    ("T2 vi, [0/90/±45]s, kN/m + moment",
     "Cho tấm CFRP gồm 8 lớp xếp theo [0/90/±45]s, chiều dày mỗi lớp 0,2 mm. Tấm chịu kéo Nx = 4 kN/m "
     "và mô-men uốn Mx = 3 N·m/m.",
     P("CFRP", [0, 90, 45, -45, -45, 45, 90, 0], 0.0002, Nx=4000, Mx=3)),
    ("T3 en, aramid [±60]s, negative shear",
     "Aramid/epoxy [±60]s laminate; t = 0.125 mm per ply; loads Nx = 300 N/m, Nxy = -75 N/m.",
     P("KEVLAR", [60, -60, -60, 60], 0.000125, Nx=300, Nxy=-75)),
    ("T4 en, imperial thickness + lbf·in/in moment",
     "IM7/8552 tape, [0/45/90/-45]s, 0.0072 in per ply. Mx = 5 lbf·in/in.",
     P("CFRP", [0, 45, 90, -45, -45, 90, 45, 0], 0.0072 * 0.0254, Mx=5 * 4.4482216152605)),
    ("T5 vi, angles listed, µm",
     "Vật liệu sợi thủy tinh, 4 lớp với các góc 30°, -30°, -30°, 30°, mỗi lớp dày 150 µm. "
     "Chỉ có lực cắt Nxy = 500 N/m.",
     P("GFRP", [30, -30, -30, 30], 0.00015, Nxy=500)),
    ("T6 en, 'Nx = Ny = 1.2 kN/m'",
     "Carbon fibre laminate with plies 0°/90°/90°/0°, each 0.2 mm, under biaxial tension Nx = Ny = 1.2 kN/m.",
     P("CFRP", [0, 90, 90, 0], 0.0002, Nx=1200, Ny=1200)),
]

SETS = {"dev": DEV, "holdout": HOLDOUT, "holdout2": HOLDOUT2, "holdout3": HOLDOUT3}


def _close(a, b, rel=1e-6):
    return abs(a - b) <= rel * max(abs(a), abs(b)) + 1e-12


def compare(exp, problem):
    got_angles = [p.angle for p in problem.plies]
    got_t = [p.thickness for p in problem.plies]
    loads = problem.loads.model_dump()
    checks = {
        "material": problem.material == exp["material"],
        "n_plies": len(got_angles) == len(exp["angles"]),
        "angles": len(got_angles) == len(exp["angles"]) and all(_close(a, b) for a, b in zip(got_angles, exp["angles"])),
        "thickness": len(got_t) == len(exp["thickness"]) and all(_close(a, b) for a, b in zip(got_t, exp["thickness"])),
    }
    bad_loads = [k for k in llm.LOAD_KEYS if not _close(loads[k], exp["loads"][k])]
    checks["loads"] = not bad_loads
    errors = []
    if not checks["material"]:
        errors.append(f"material {problem.material} (want {exp['material']})")
    if not checks["angles"]:
        errors.append(f"angles {got_angles} (want {exp['angles']})")
    if not checks["thickness"]:
        errors.append(f"thickness {got_t} (want {exp['thickness']})")
    for k in bad_loads:
        errors.append(f"{k}={loads[k]:g} (want {exp['loads'][k]:g})")
    return all(checks.values()), checks, bad_loads, errors


def run_one(version, backend, text):
    """Returns (problem or None, seconds, error text or None, raw LLM output)."""
    t0 = time.time()
    try:
        if version == "v1":
            llm_v1_baseline.BACKEND = backend
            problem = llm_v1_baseline.parse_input(text)
            raw = None
        else:
            llm.LAST_PARSE = {}
            problem = llm.parse_input(text, backend=backend)
            raw = llm.LAST_PARSE.get("raw")
        return problem, time.time() - t0, None, raw
    except Exception as e:
        return None, time.time() - t0, f"{type(e).__name__}: {str(e)[:300]}", None


def llm_only_correct(version, exp):
    """Would the FIRST LLM answer be correct without the Python checks against the text?
    (unit conversion and layup expansion are still done by Python). v1 has no checks."""
    if version == "v1":
        return None
    attempts = llm.LAST_PARSE.get("attempts") or []
    if not attempts:
        return False
    try:
        problem, _ = llm.build_problem(attempts[0], text=None)
        return compare(exp, problem)[0]
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="dev", choices=list(SETS))
    ap.add_argument("--versions", default="v1,v3", help="v1 = original llm.py; anything else = current llm.py")
    ap.add_argument("--backends", default="hf,ollama")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--cases", default="", help="comma list of case ids, e.g. D3,D7")
    args = ap.parse_args()

    cases = SETS[args.set]
    if args.cases:
        want = set(args.cases.split(","))
        cases = [c for c in cases if c[0].split()[0] in want]
    combos = [(v, b) for v in args.versions.split(",") for b in args.backends.split(",")]
    rows = []
    for v, b in combos:
        for rep in range(args.repeat):
            for name, text, exp in cases:
                problem, sec, err, raw = run_one(v, b, text)
                if problem is not None:
                    ok, checks, bad_loads, errors = compare(exp, problem)
                else:
                    ok, checks, bad_loads, errors = False, {}, list(llm.LOAD_KEYS), [err]
                alone = llm_only_correct(v, exp)
                rows.append({"version": v, "backend": b, "repeat": rep, "case": name, "correct": ok,
                             "llm_only_correct": alone, "checks": checks, "errors": errors,
                             "seconds": round(sec, 2), "raw": raw,
                             "attempts": None if v == "v1" else llm.LAST_PARSE.get("attempts"),
                             "parsed": problem.model_dump() if problem is not None else None})
                print(f"[{v}/{b:6}] {'OK  ' if ok else 'FAIL'} {sec:6.1f}s  {name}"
                      + ("" if alone is None else f"   (LLM alone: {'OK' if alone else 'wrong'})")
                      + ("" if ok else "\n      -> " + "; ".join(errors)), flush=True)

    # ---- summary table
    lines = [f"# LLM extraction benchmark ({args.set} set, {len(cases)} cases, repeat {args.repeat})",
             f"Run: {datetime.datetime.now():%Y-%m-%d %H:%M}. HF model: {llm.HF_MODEL}; Ollama model: {llm.MODEL}.", "",
             "'fully correct' = final CLT input of the agent. 'LLM alone' = first LLM answer without the Python "
             "checks against the text (v1 has no checks).", "",
             "| version | backend | fully correct | LLM alone | material | plies+angles | thickness | loads (6 each) | parse errors | mean s/case |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for v, b in combos:
        rs = [r for r in rows if r["version"] == v and r["backend"] == b]
        n = len(rs)
        c = lambda key: sum(1 for r in rs if r["checks"].get(key))
        load_ok = sum(6 - sum(1 for e in r["errors"] if e.split("=")[0] in llm.LOAD_KEYS) if r["checks"] else 0
                      for r in rs)
        crashed = sum(1 for r in rs if not r["checks"])
        alone = "-" if v == "v1" else f"{sum(1 for r in rs if r['llm_only_correct'])}/{n}"
        lines.append(f"| {v} | {b} | **{sum(r['correct'] for r in rs)}/{n}** | {alone} | {c('material')}/{n} | "
                     f"{c('angles')}/{n} | {c('thickness')}/{n} | {load_ok}/{6 * n} | {crashed} | "
                     f"{sum(r['seconds'] for r in rs) / max(n, 1):.1f} |")
    lines += ["", "## Failures", ""]
    for r in rows:
        if not r["correct"]:
            lines.append(f"- {r['version']}/{r['backend']} rep{r['repeat']} **{r['case']}**: " + "; ".join(r["errors"]))
    md = "\n".join(lines)
    print("\n" + md)

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deliverables", "benchmark")
    os.makedirs(out_dir, exist_ok=True)
    stamp = f"{datetime.datetime.now():%Y%m%d_%H%M}"
    base = os.path.join(out_dir, f"llm_benchmark_{args.set}_{stamp}")
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump({"args": vars(args), "rows": rows}, f, indent=1, ensure_ascii=False)
    with open(base + ".md", "w", encoding="utf-8") as f:
        f.write(md + "\n")
    print(f"\nSaved {base}.md / .json")


if __name__ == "__main__":
    main()
