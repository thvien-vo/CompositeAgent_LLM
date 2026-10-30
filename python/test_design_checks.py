"""
test_design_checks.py - deterministic checks of the design function (no LLM call):
  1. request classifier: the 44 old analysis problems, the 18 RAG questions and the design requests;
  2. reading of the design requests by Python alone (LLM answer empty): hand-written specification or refusal;
  3. LLM values checked against the text (the text wins, values not written in the text are ignored);
  4. checks of the design explanation: wrong sentences are caught (some are real gemma3 outputs), correct ones and
     the pre-built explanations (English, Vietnamese) pass.
Run:  python test_design_checks.py   -> ALL PASS
"""
import sys

import benchmark_design as BD
import benchmark_llm
import benchmark_rag
import design
import design_cases
import llm
import router

EMPTY = {"fibre_words": "", "material_name": "", "material": "NONE", "loads": [], "safety_factor": 0,
         "ply_thickness": {"value": 0, "unit": "mm"}, "plate_a": {"value": 0, "unit": "m"},
         "plate_b": {"value": 0, "unit": "m"}, "ply_count": 0, "ply_count_min": 0, "ply_count_max": 0,
         "objective_words": "", "shear_direction": "", "angles": []}
FAIL = []


def check(ok, msg):
    if not ok:
        FAIL.append(msg)
        print("  FAIL", msg)


def classifier():
    items = [(n, t, "analysis") for n, t, e in benchmark_llm.SETS["old28"] + benchmark_llm.NEW]
    items += [(q[0], q[1], "question") for k in benchmark_rag.SETS for q in benchmark_rag.SETS[k]]
    for n, t, e in design_cases.CASES:
        cid = n.split()[0]
        if cid != "DS20":                       # DS20 needs the LLM to confirm a weak wording
            items.append((n, t, "refused" if cid == "DS19" else "design"))
    for n, t, want in items:
        try:
            got = router.classify(t, use_llm=False)[0]
        except router.UnclearRequest:
            got = "refused"
        check(got == want, f"classify {n.split()[0]}: {got} (expected {want})")
    text20 = next(t for n, t, e in design_cases.CASES if n.startswith("DS20"))
    try:
        got = router.classify(text20, use_llm=False)[0]
    except router.UnclearRequest:
        got = "refused"
    check(got == "refused", "DS20 without the LLM must not be classified by the rules alone")
    print(f"classifier: {len(items) + 1} requests checked")


def reading():
    for n, t, e in design_cases.CASES:
        cid = n.split()[0]
        if cid == "DS19":
            continue                             # refused by the classifier already
        try:
            spec = design.build_spec(dict(EMPTY), t)
            bad = BD.compare_spec(spec, e["spec"]) if e["kind"] == "design" else ["should be refused"]
        except (design.DesignRefusal, llm.AmbiguousTextError) as err:
            bad = [] if e["kind"] == "refuse" else [f"refused: {err}"]
        check(not bad, f"read {cid}: {bad}")
    print("reading: design requests read by Python alone")


def llm_values():
    text = "Design the lightest AS4/8552 laminate for Nx = -40 kN/m, safety factor 2, with 0.15 mm plies."
    raw = dict(EMPTY, material_name="AS4/8552", material="CFRP", safety_factor=3,
               ply_thickness={"value": 0.2, "unit": "mm"}, loads=[{"name": "Nx", "value": -40, "unit": "kN/m"}])
    spec = design.build_spec(raw, text)
    check(spec.safety_factor == 2.0 and abs(spec.ply_thickness - 0.15e-3) < 1e-12 and spec.loads["Nx"] == -40e3,
          f"text must win over the LLM: {spec}")
    check(any("safety factor" in x and "using the text" in x for x in spec.notes), "note for the safety factor")
    text = "Design the lightest carbon/epoxy laminate for Ny = 30 kN/m on a panel that measures 600 by 400 mm."
    raw = dict(EMPTY, material="CFRP", plate_a={"value": 600, "unit": "mm"}, plate_b={"value": 400, "unit": "mm"},
               loads=[{"name": "Ny", "value": 30, "unit": "kN/m"}])
    spec = design.build_spec(raw, text)
    check((spec.a, spec.b) == (0.6, 0.4), f"plate read by the LLM and written in the text: {spec.a}, {spec.b}")
    raw = dict(raw, plate_a={"value": 0.8, "unit": "m"})
    spec = design.build_spec(raw, text)
    check(spec.a == 0.5 and any("not written in the text" in x for x in spec.notes),
          f"a value that is not in the text is ignored: {spec.a}")
    try:
        design.build_spec(dict(EMPTY, material="CFRP"), "Design a CFRP laminate with Nx = 20 kN/m at 80 °C.")
        ok = True
    except design.DesignRefusal:
        ok = False
    check(ok, "a temperature in °C is not a ply angle")
    # gemma3, 30/10/2026: "at most 24 plies" copied as a fixed ply count -> the text (a limit) wins
    text = ("Design the lightest IM7/8552 laminate with at most 24 plies for Nx = 2000 kN/m and Ny = 1000 kN/m.")
    spec = design.build_spec(dict(EMPTY, material_name="IM7/8552", material="CFRP", ply_count=24), text)
    check((spec.n_min, spec.n_max, spec.objective) == (8, 24, "min_plies"), f"ply limit, not fixed: {spec}")
    # the quasi-isotropic laminate of the comparison meets the same ply-count limits (no negative saving)
    r = design.solve(design.build_spec(dict(EMPTY), "Lightest T700GC/TC1225 laminate with between 16 and 40 plies "
                                                    "for Nx = 300 kN/m, Ny = 150 kN/m."), check_matlab=False)
    check(r["quasi_isotropic"]["n"] >= 16 and r["reduction_pct"] >= 0, f"QI within the ply range: {r['quasi_isotropic']}")
    print("LLM values: checked against the text")


def explanations():
    def solved(text):
        return design.solve(design.build_spec(dict(EMPTY), text), check_matlab=False)

    proven = solved("Design the lightest IM7/8552 laminate for Nx = -10 kN/m.")
    best = solved("Design an IM7/8552 laminate for Nxy = 80 kN/m.")
    infeasible = solved("Design the lightest IM7/8552 laminate with at most 24 plies for Nx = 2000 kN/m and "
                        "Ny = 1000 kN/m.")
    check(proven["search"]["proven"] and proven["feasible"], "proven case")
    check(not best["search"]["proven"] and best["feasible"], "best-found case")
    check(infeasible["search"]["proven"] and not infeasible["feasible"], "proven infeasible case")
    for r in (proven, best, infeasible):
        for lang in ("en", "vi"):
            text, _ = design.prebuilt_explanation(r, lang)
            issues = design.design_explanation_issues(text, r)
            check(not issues, f"pre-built {lang} {r['notation']} must pass: {issues}\n    {text}")
    n, m = best["n_plies"], best["margin"]
    qi, red = best["quasi_isotropic"]["n"], best["reduction_pct"]
    rf = best["rf"]
    wrong = [  # (text, why it is wrong)
        (f"Notably, a quasi-isotropic laminate needing {qi} plies would have provided {red:.1f} % fewer plies than "
         "this design.", "comparison the wrong way round (real gemma3 output, 30/10/2026)"),
        (f"Tấm tựa đẳng hướng {qi} lớp có ít hơn {red:.1f} % số lớp so với thiết kế này.", "wrong way round (VI)"),
        (f"The stacking sequence has {n} plies and is the proven global optimum.", "claims a proof"),
        (f"The safety margin of {m:.4g} is governed by Tsai-Wu.", "wrong governing criterion"),
        (f"The design has {n} plies and does not meet the safety factor.", "wrong verdict"),
        (f"The laminate needs {rf['tsai_wu']:.4g} plies.", "reserve factor called a ply count"),
        ("The laminate has 77 plies.", "number not in the data"),
        (f"Thiết kế có {n} lớp, biên an toàn {m:.4g} và đã được chứng minh là tối ưu.", "claims a proof (VI)"),
    ]
    for text, why in wrong:
        check(bool(design.design_explanation_issues(text, best)), f"should be flagged ({why}): {text}")
    right = [
        f"The stacking sequence {best['notation']} has {n} plies; it is the best design found, not proven optimal.",
        f"The safety margin is {m:.4g}, governed by buckling, so the design meets the required safety factor of 1.5.",
        f"The buckling load factor is {rf['buckling']:.4g} and the Tsai-Wu reserve factor is {rf['tsai_wu']:.4g}.",
        f"This design has {red:.1f} % fewer plies than the smallest quasi-isotropic laminate ({qi} plies).",
        f"Thiết kế này có ít hơn {red:.1f} % số lớp so với tấm tựa đẳng hướng nhỏ nhất ({qi} lớp).",
        f"Biên an toàn là {m:.4g}, do mất ổn định quyết định; kết quả chưa được chứng minh là tối ưu.",
    ]
    for text in right:
        issues = design.design_explanation_issues(text, best)
        check(not issues, f"should pass: {text}\n    {issues}")
    t = (f"The lightest design found has {infeasible['n_plies']} plies, but its margin of "
         f"{infeasible['margin']:.4g} meets the safety factor.")
    check(bool(design.design_explanation_issues(t, infeasible)), "infeasible design called acceptable")
    # found in the gemma3 run of 30/10/2026: a correct negation, a ply count named after the number, the shear check
    t = (f"The Max Stress and Tsai-Wu reserve factors are {infeasible['rf']['max_stress']:.4g} and "
         f"{infeasible['rf']['tsai_wu']:.4g}, but neither meets the required safety factor of 1.5.")
    check(not design.design_explanation_issues(t, infeasible), "'neither meets' is a negation")
    t = f"The smallest quasi-isotropic laminate needed to achieve the same safety factor is {qi} plies."
    check(not design.design_explanation_issues(t, best), "'... is 32 plies' names a ply count")
    one = solved("Optimise the stacking sequence of an IM7/8552 plate for Nxy = 60 kN/m; the shear always acts in "
                 "the positive direction.")
    check(bool(design.design_explanation_issues("Shear checking was not checked in either direction.", one)),
          "the shear WAS checked (given sign)")
    check(bool(design.design_explanation_issues("The shear was checked in both directions.", one)),
          "one-direction case described as both directions")
    check(bool(design.design_explanation_issues("The shear was checked in one direction only.", best)),
          "both-direction case described as one direction")
    check(not design.design_explanation_issues("The shear was checked for the given sign only.", one),
          "correct one-direction sentence")
    print("explanations: wrong sentences caught, correct ones and pre-built texts pass")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    classifier()
    reading()
    llm_values()
    explanations()
    print("ALL PASS" if not FAIL else f"{len(FAIL)} PROBLEM(S)")
    sys.exit(1 if FAIL else 0)
