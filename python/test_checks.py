"""
test_checks.py - tests of the deterministic checks in llm.build_problem (no LLM call).
For every benchmark problem (28 old + 16 new) three fake LLM answers are built from the known answer:
  perfect   : what a perfect LLM would write                -> must give the right input (or refuse if expected)
  no_loads  : the LLM forgot every load                     -> must recover the loads from the text, or refuse
  misplaced : the LLM put each load in the wrong slot       -> must recover, or refuse
A wrong result without an error ("silent") is never allowed.
Run:  python test_checks.py
"""
import sys

import llm
from benchmark_llm import NEW, SETS, compare

ROT = {"Nx": "Ny", "Ny": "Nxy", "Nxy": "Nx", "Mx": "My", "My": "Mxy", "Mxy": "Mx"}


def fake_raw(exp, loads_mode, text):
    t = exp["thickness"]
    same = all(abs(x - t[0]) < 1e-15 for x in t)
    total = same and any(w in text.lower() for w in llm.TOTAL_WORDS)  # the text gives only the total
    loads = [{"name": k, "value": v, "unit": "N/m" if k.startswith("N") else "N*m/m"}
             for k, v in exp["loads"].items() if v != 0]
    if loads_mode == "no_loads":
        loads = []
    elif loads_mode == "misplaced":
        loads = [dict(q, name=ROT[q["name"]]) for q in loads]
    return {"fibre_words": "", "material_name": "", "material": exp["material"],
            "layup": "/".join(f"{a:g}" for a in exp["angles"]),
            "ply_thickness": {"value": t[0] if same and not total else 0, "unit": "m"},
            "total_thickness": {"value": sum(t) if total else 0, "unit": "m"},
            "ply_thickness_list": [] if same else [{"value": x, "unit": "m"} for x in t], "loads": loads}


def main():
    cases = SETS["old28"] + NEW
    bad = 0
    tally = {}
    for mode in ("perfect", "no_loads", "misplaced"):
        for name, text, exp in cases:
            if mode != "perfect" and not any(exp["loads"].values()) and not exp.get("refuse"):
                continue
            try:
                problem, warns = llm.build_problem(fake_raw(exp, mode, text), text)
                err = None
            except ValueError as e:
                problem, err = None, str(e)
            if exp.get("refuse"):
                outcome = "refused (correct)" if problem is None else "NOT refused"
                ok = problem is None
            elif problem is None:
                outcome = "refused"
                ok = mode != "perfect"  # refusing is acceptable only when the LLM answer was bad
            else:
                good = compare(exp, problem)[0]
                outcome = "correct" if good else "SILENT WRONG"
                ok = good
            tally[(mode, outcome)] = tally.get((mode, outcome), 0) + 1
            if not ok:
                bad += 1
                print(f"[{mode:9}] {name}: {outcome}" + (f" - {err}" if err else
                      f" - got {problem.loads.model_dump()} row={problem.material_name!r}"))
    for (mode, outcome), k in sorted(tally.items()):
        print(f"{mode:10} {outcome:20} {k}")
    print("ALL PASS" if bad == 0 else f"{bad} PROBLEMS")
    return bad


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(1 if main() else 0)
