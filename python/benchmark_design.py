"""
benchmark_design.py - the design function on the test requests of design_cases.py (written before the code).

For each request:
  * classification (router.classify): design requests -> "design"; the refused cases are refused either by the
    classifier (DS19) or by the reading of the request (unsupported / unclear);
  * reading: the specification read by the agent (design.parse_design) vs the specification written by hand;
  * result: the agent's design vs a DIRECT call of optimization.optimize(...) built from the hand-written
    specification (not from what the agent read): optimize(method="exhaustive") when the agent reports a proven
    result, else optimize(method="ga", seed 0, GA + local search) - same ply count, same margin (1e-9), same layup;
  * explanation (optional, --explain): source llm / llm-retry / prebuilt.
Run:  python benchmark_design.py --backend ollama [--explain] [--ids DS1,DS3]
Results: ../deliverables/benchmark/design_benchmark_<backend>_<time>.json and .md
"""
import argparse
import contextlib
import datetime
import io
import json
import os
import time
import traceback

import design
import design_cases
import llm
import router

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deliverables", "benchmark")
FIELDS = ("safety_factor", "ply_thickness", "a", "b", "n_min", "n_max", "objective", "shear_both", "max_contiguous",
          "min_fraction")


def compare_spec(spec, e):
    """Differences between a DesignSpec and the expected specification (empty = read correctly)."""
    bad = []
    if spec.group != e["material"]:
        bad.append(f"group {spec.group} (expected {e['material']})")
    if spec.row != e["row"]:
        bad.append(f"material row '{spec.row}' (expected '{e['row']}')")
    for k in ("Nx", "Ny", "Nxy"):
        if abs(spec.loads[k] - e["loads"][k]) > 1e-6 * max(1.0, abs(e["loads"][k])):
            bad.append(f"{k} = {spec.loads[k]:g} (expected {e['loads'][k]:g})")
    for k in FIELDS:
        v, w = getattr(spec, k), e[k]
        if (v != w) if not isinstance(w, float) else (v is None or abs(v - w) > 1e-9 * abs(w)):
            bad.append(f"{k} = {v} (expected {w})")
    return bad


def direct_optimize(e, proven):
    """optimization.optimize(...) called directly with the hand-written specification."""
    from ml import predict_material
    from optimization import optimize
    from optimization.api import make_problem
    from optimization.evaluate import Plate
    from optimization.ga import GAConfig
    from optimization.material import KEYS, Material, get_material
    from optimization.rules import Rules
    if e["row"]:
        mat = get_material(e["row"], e["material"], verbose=False)
    else:
        props = predict_material(e["material"])
        mat = Material(**{k: float(props[k]) for k in KEYS}, name=f"{e['material']} (ML)")
    p = make_problem(e["loads"], material=mat, safety_factor=e["safety_factor"], plate=Plate(e["a"], e["b"]),
                     ply_thickness=e["ply_thickness"], ritz_terms=design.RITZ_TERMS, shear_both_signs=e["shear_both"],
                     rules=Rules(n_min=e["n_min"], n_max=e["n_max"], max_contiguous=e["max_contiguous"],
                                 min_fraction=e["min_fraction"]))
    if proven:
        return optimize(None, problem=p, method="exhaustive", time_limit=design.EXACT_TIME_LIMIT)
    return optimize(None, problem=p, method="ga", seed=0,
                    ga_config=GAConfig(budget=10000, local_search=True, objective=e["objective"]))


def run_case(name, text, exp, backend, explain, lang):
    row = {"id": name.split()[0], "name": name, "expected": exp["kind"]}
    t0 = time.time()
    try:
        kind, why = router.classify(text, backend=backend)
    except router.UnclearRequest as err:
        kind, why = "refused", str(err)
    row["class"], row["class_reason"] = kind, why
    if kind != "design":
        row.update(outcome="refused" if kind == "refused" else f"classified as {kind}",
                   correct=(exp["kind"] == "refuse" and kind == "refused"), seconds=round(time.time() - t0, 1))
        return row
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            spec = design.parse_design(text, backend=backend)
    except design.DesignRefusal as err:
        row.update(outcome="refused", refusal=str(err), correct=exp["kind"] == "refuse",
                   seconds=round(time.time() - t0, 1), raw=design.LAST_DESIGN.get("raw"))
        return row
    row["raw"] = design.LAST_DESIGN.get("raw")
    row["spec"] = {k: v for k, v in design.asdict(spec).items()}
    if exp["kind"] == "refuse":
        row.update(outcome="NOT refused", correct=False, seconds=round(time.time() - t0, 1))
        return row
    row["read_errors"] = compare_spec(spec, exp["spec"])
    with contextlib.redirect_stdout(buf):
        r = design.solve(spec, check_matlab=True)
    row["result"] = {"notation": r["notation"], "n": r["n_plies"], "margin": r["margin"], "feasible": r["feasible"],
                     "status": r["search"]["status"], "proven": r["search"]["proven"],
                     "n_proven": r["search"].get("n_proven"), "governing": r["governing"], "rf": r["rf"],
                     "matlab_pass": (r["matlab"] or {}).get("pass"), "buckling_check": r["buckling_check"],
                     "qi_n": r["quasi_isotropic"]["n"], "reduction_pct": r["reduction_pct"],
                     "search_time_s": r["search_time_s"]}
    d = direct_optimize(exp["spec"], r["search"]["proven"])
    same = (d.n_plies == r["n_plies"] and abs(d.margin - r["margin"]) <= 1e-9 * abs(d.margin)
            and d.notation == r["notation"])
    row["direct"] = {"method": d.method, "notation": d.notation, "n": d.n_plies, "margin": d.margin,
                     "status": d.status, "same_as_agent": same}
    if explain:
        try:
            with contextlib.redirect_stdout(buf):
                answer, info = design.explain_design(r, backend=backend, lang=lang)
            row["explanation"] = {"source": info["source"], "first_issues": info["first_issues"],
                                  "issues": info["issues"], "rejected": info["rejected"], "text": answer}
        except Exception as err:
            row["explanation"] = {"source": "error", "error": f"{type(err).__name__}: {err}"}
    row["outcome"] = "designed"
    row["correct"] = not row["read_errors"] and same and (r["matlab"] or {}).get("pass") is True
    if exp.get("note", "").startswith("expected: no feasible"):
        row["note"] = f"expected infeasible -> feasible = {r['feasible']}"
    row["seconds"] = round(time.time() - t0, 1)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="ollama", choices=["hf", "ollama", "auto"])
    ap.add_argument("--explain", action="store_true")
    ap.add_argument("--lang", default="en", choices=["en", "vi"])
    ap.add_argument("--ids", default="")
    args = ap.parse_args()
    only = set(args.ids.split(",")) if args.ids else None
    rows = []
    for name, text, exp in design_cases.CASES:
        if only and name.split()[0] not in only:
            continue
        try:
            row = run_case(name, text, exp, args.backend, args.explain, args.lang)
        except Exception as err:
            row = {"id": name.split()[0], "name": name, "outcome": "ERROR", "correct": False,
                   "error": f"{type(err).__name__}: {err}", "trace": traceback.format_exc()[-1500:]}
        rows.append(row)
        print(f"{row['id']:5} {row.get('class', ''):9} {row['outcome']:12} correct={row['correct']}  "
              f"{row.get('seconds', '')} s  " + (f"read errors: {row['read_errors']}" if row.get("read_errors") else "")
              + (f" direct={row['direct']['same_as_agent']}" if "direct" in row else "")
              + (f" expl={row['explanation']['source']}" if "explanation" in row else "")
              + (f" {row.get('refusal', row.get('class_reason', ''))[:90]}" if row["outcome"] == "refused" else "")
              + (f" {row.get('error', '')}" if row["outcome"] == "ERROR" else ""), flush=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    os.makedirs(OUT, exist_ok=True)
    base = os.path.join(OUT, f"design_benchmark_{args.backend}_{stamp}")
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1, default=str)
    with open(base + ".md", "w", encoding="utf-8") as f:
        f.write(report(rows, args))
    print(report(rows, args))
    print(f"Saved {base}.json / .md")
    try:
        from matlab_clt import close_engine
        close_engine()
    except Exception:
        pass


def report(rows, args):
    designs = [r for r in rows if r.get("expected") == "design"]
    refuse = [r for r in rows if r.get("expected") == "refuse"]
    cls_ok = sum(1 for r in designs if r.get("class") == "design")
    read_ok = sum(1 for r in designs if r.get("outcome") == "designed" and not r.get("read_errors"))
    same = sum(1 for r in designs if (r.get("direct") or {}).get("same_as_agent"))
    mat = sum(1 for r in designs if (r.get("result") or {}).get("matlab_pass") is True)
    ref_ok = sum(1 for r in refuse if r.get("correct"))
    expl = [r["explanation"]["source"] for r in rows if "explanation" in r]
    lines = [f"# Design benchmark - backend {args.backend} - {datetime.datetime.now():%Y-%m-%d %H:%M}", "",
             f"LLM: {llm.LAST_BACKEND}. Requests: {len(rows)} ({len(designs)} to design, {len(refuse)} to refuse).", "",
             "| measure | result |", "|---|---|",
             f"| classified as design (design requests) | {cls_ok}/{len(designs)} |",
             f"| specification read correctly | {read_ok}/{len(designs)} |",
             f"| agent result = direct optimize(...) call | {same}/{len(designs)} |",
             f"| MATLAB re-check passed | {mat}/{len(designs)} |",
             f"| refused as they should be | {ref_ok}/{len(refuse)} |",
             f"| fully correct | {sum(1 for r in rows if r.get('correct'))}/{len(rows)} |"]
    if expl:
        lines.append(f"| explanation: LLM / after one retry / pre-built | {expl.count('llm')} / "
                     f"{expl.count('llm-retry')} / {expl.count('prebuilt')} |")
    lines += ["", "| id | outcome | design | plies | margin | status | MATLAB | direct call | time (s) | note |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        res = r.get("result") or {}
        note = "; ".join(r.get("read_errors") or []) or r.get("refusal", "") or (
            r.get("class_reason", "") if r.get("outcome") == "refused" else "") or r.get("note", "") or r.get("error", "")
        lines.append(f"| {r['id']} | {r['outcome']} | {res.get('notation', '')} | {res.get('n', '')} | "
                     f"{'' if not res else f'{res['margin']:.4g}'} | {res.get('status', '')} | "
                     f"{'' if not res else res.get('matlab_pass')} | "
                     f"{'' if 'direct' not in r else r['direct']['same_as_agent']} | {r.get('seconds', '')} | "
                     f"{note[:120]} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
