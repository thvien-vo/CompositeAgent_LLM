"""
test_explain_checks.py - tests of the deterministic checks on LLM texts (no LLM call, no MATLAB):
  1. llm.explanation_issues: each number of a CLT explanation must be named as what it is (English and
     Vietnamese) and the safe / not safe verdict must agree with the failure index.
     Wrong texts written by gemma3:4b in the demo (ABD(1,1) = 5.94e7 N/m called a "load" / "load capacity") and
     hand-written wrong sentences must be caught; correct texts (Hugging Face answers from the demo logs,
     hand-written ones and the pre-built Python explanation) must pass.
  2. rag.check_citations: each NCAMP report id in a RAG answer must be the source of the material it is
     attached to (same sentence), and a [F] / ranking answer must cite the report of its material.
The CLT results are computed with the Python CLT of the optimization module (same numbers as clt_engine.m).
Run:  python test_explain_checks.py
"""
import sys

import numpy as np

import llm
import rag
from ml import predict_material
from optimization.clt import analyze
from schemas import CLTInput

CASES = {  # name -> (material, angles, ply thickness, loads); same laminates as the demo problems
    "P1": ("CFRP", [0, 45, -45, 90, 90, -45, 45, 0], 0.000125, {"Nx": 1000, "Ny": 500, "Nxy": 100}),
    "P2": ("GFRP", [0, 45, -45, -45, 45, 0], 0.00015, {"Nxy": 40000, "Nx": 150000, "My": 10}),
}

# (case, text, must be flagged?)
TEXTS = [
    # gemma3:4b in the offline demo of 28/10/2026 (logs/demo_20261028_121538.log) - the two wrong sentences
    ("P1", "The program computed a load of 59400000.0 N/m, suggesting a significant load capacity.", True),
    ("P2", "The program calculated a nominal ABD11 N/m load of 28660000.0 N/m, which is significantly higher than "
           "the laminate’s capacity.", True),
    # ... and its correct sentences
    ("P1", "The Classical Laminate Theory calculation indicates a maximum failure index of 0.002381 across ply 4, "
           "which is oriented at 90.0 degrees. This ply is critical due to the highest calculated transverse stress "
           "of 0.1518 MPa, which is compared to the transverse tensile strength of 63.76 MPa. The governing mode is "
           "transverse (sigma2, tension). The laminate is classified as safe with a safety factor of 420.0, "
           "calculated as the inverse of the failure index.", False),
    ("P2", "The Classical Laminate Theory calculation indicates that the laminate is not safe, with a maximum failure "
           "index of 1.096. Ply number 4, at an angle of -45.0 degrees, is the critical ply due to its failure index "
           "exceeding 1.0. The governing mode of failure is transverse (sigma2, tension) with a governing stress of "
           "49.49 MPa, compared to the transverse tensile strength of 45.17 MPa. The resulting safety factor is "
           "0.9127, signifying a low margin of safety.", False),
    # Hugging Face in the online demo (logs/demo_20261028_121100.log)
    ("P1", "The maximum failure index is 0.002381 and it occurs in plies 4 and 5, both oriented at 90°. Because the "
           "index is well below 1, the laminate is considered safe. The safety factor, defined as 1 / FI, is about "
           "420.0. The critical condition is governed by the transverse (σ₂) tensile mode, where the transverse "
           "stress in the 90° plies reaches 0.1518 MPa. This stress is compared with the transverse tensile "
           "strength Yt of 63.76 MPa, resulting in the very low failure index.", False),
    ("P2", "The CLT analysis of the 6‑ply GFRP laminate under the given in‑plane and bending loads yields a maximum "
           "failure index of 1.096. This value occurs in ply 4, which is oriented at –45° relative to the global "
           "axes. The safety factor, defined as 1 divided by the failure index, is 0.9127. The ply is critical "
           "because the governing failure mode is transverse tension (σ2), with a computed σ2 of 49.49 MPa. This "
           "stress is compared with the transverse tensile strength Yt of 45.17 MPa, giving a ratio (49.49/45.17) "
           "of 1.096, which drives the failure index above the allowable limit.", False),
    # ABD in the same sentence as "loads" (HF, same log): against the rule "ABD never with load / capacity"
    ("P1", "The CLT analysis of the 8‑ply CFRP laminate (total thickness 1 mm) under the specified in‑plane loads "
           "yields an ABD11 of 5.94 × 10⁷ N/m.", True),
    # hand-written, English
    ("P1", "ABD(1,1) = 5.94e7 N/m is the in-plane extensional stiffness of the laminate.", False),
    ("P1", "The A11 stiffness, 5.94 x 10^7 N/m, is not a load.", False),
    ("P1", "The laminate can carry a load of 5.94e7 N/m.", True),
    ("P1", "The in-plane stiffness ABD(1,1) of 5.94e7 N/m gives the laminate a high load capacity.", True),
    ("P1", "The failure index is 420.", True),
    ("P1", "The safety factor is 0.002381.", True),
    ("P1", "Ply 4 has a stress of 63.76 MPa.", True),
    ("P1", "The transverse stress is 0.1518 MPa, far below the transverse tensile strength Yt = 63.76 MPa.", False),
    ("P1", "All loads could be multiplied by 420 before the first ply fails.", False),
    ("P1", "The failure index of 0.002381 MPa is small.", True),
    ("P1", "Under Nx = 1000 N/m, Ny = 500 N/m and Nxy = 100 N/m the 8-ply laminate is safe.", False),
    ("P1", "The applied load Nx = 1000 N/m gives a stiffness of 1000 N/m.", True),
    ("P2", "Ply 4 fails: its failure index is 1.096 and the safety factor is 0.9127 < 1.", False),
    ("P2", "The Max Stress failure index of the critical ply is 1.096.", False),
    # hand-written, Vietnamese
    ("P1", "ABD(1,1) = 5,94·10⁷ N/m là độ cứng kéo trong mặt phẳng của tấm.", False),
    ("P1", "ABD(1,1) = 5,94·10⁷ N/m cho thấy khả năng chịu tải rất lớn.", True),
    ("P1", "Tải trọng tính được là 5,94e7 N/m.", True),
    ("P1", "Độ cứng 5,94e7 N/m cho thấy tấm có sức chịu tải lớn.", True),
    ("P1", "Chỉ số phá hủy lớn nhất là 0,002381 tại lớp 4 (lớp 90°).", False),
    ("P1", "Chỉ số phá hủy là 420.", True),
    ("P1", "Hệ số an toàn là 420, tấm an toàn.", False),
    ("P1", "Hệ số an toàn là 0,002381.", True),
    ("P1", "Ứng suất ngang σ2 = 0,1518 MPa so với độ bền kéo ngang Yt = 63,76 MPa.", False),
    ("P1", "Ứng suất của lớp 4 là 63,76 MPa.", True),
    ("P2", "Chỉ số Max Stress lớn nhất là 1,096 nên tấm không an toàn; hệ số an toàn 1/FI = 0,9127.", False),
    # gemma3:4b in the 44-problem run of 28/10/2026 (first version of the checks): correct sentences that were
    # rejected, and wrong verdicts that were not caught
    ("P1", "The in-plane stiffness (ABD11) is 5.94e+07 N/m, representing a measure of the laminate's extensional "
           "stiffness, not a load or force.", False),
    ("P1", "The in-plane stiffness, ABD11, is 5.94e+07 N/m, representing a stiffness value and not a load, force, "
           "or load capacity.", False),
    ("P2", "The maximum stress failure index of the critical ply is |49.49 MPa| / 45.17 MPa = 1.096.", False),
    ("P1", "The safety factor is 420, derived from 1 / 0.002381, so the loads could be increased by 420.", False),
    ("P1", "The maximum failure index is 0.002381, signifying that the laminate is currently unsafe.", True),
    ("P1", "The maximum failure index is 0.002381, indicating that the laminate is not currently safe.", True),
    ("P2", "The maximum failure index is 1.096, so the laminate is safe.", True),
    ("P2", "Chỉ số phá hủy lớn nhất là 1,096 nên tấm an toàn.", True),
    ("P2", "Chỉ số phá hủy lớn nhất là 1,096 nên tấm không an toàn.", False),
    ("P1", "Consequently, the safety factor is 420, demonstrating that the laminate could withstand a load of 420 "
           "times the maximum failure index before the first ply fails.", True),
    ("P1", "The safety factor is 420, signifying that a load of 420 could be applied before the first ply fails.", True),
    ("P2", "Per-ply stresses show that the largest failure index is in ply 4, where the |sigma2| / Yt ratio is 1.096.",
     False),
    ("P1", "The laminate is SAFE because the max_failure_index (0.002381) is less than 1.", False),
    # Hugging Face, online demo of 28/10/2026 15:49 (first answer to problem 2, rejected by an earlier version)
    ("P2", "To be safe, the loads would have to be reduced to about 91 % of their value (safety factor 0.9127).",
     False),
    # gemma3:4b, Vietnamese explanations of 28/10/2026 16:1x: a wrong comparison with 1, and a correct sentence
    ("P1", "Điều này cho thấy, với tải trọng hiện tại, tấm laminate vẫn an toàn, vì chỉ số lỗi hỏng lớn hơn 1.", True),
    ("P1", "Hệ số an toàn của laminate là 420, cho thấy laminate vẫn an toàn nếu nhân các tải trọng lên 420 lần "
           "trước khi lớp 4 bị phá hủy.", False),
    ("P1", "The maximum failure index is 0.002381, which is far below the failure limit of 1, so the laminate is "
           "safe.", False),
    ("P1", "The safety factor is 420, which is less than 1.", True),
    ("P2", "The safety factor is 0.9127, which is less than 1, so the critical ply fails.", False),
    ("P2", "The maximum failure index of 1.096 is below 1.", True),
    ("P1", "Per-ply stresses show that ply 4 has the highest failure index due to its 0.1518 MPa stress.", False),
    ("P1", "Ply 4 has the highest failure index due to its 63.76 MPa stress.", True),
    # comparisons with 1 when the failure index is only named inside the definition of the safety factor
    ("P2", "The safety factor of 0.9127, the reciprocal of the failure index, is below 1.", False),
    ("P2", "The safety factor, i.e. 1 divided by the maximum failure index, is 0.9127, which is less than 1.", False),
    ("P2", "The reciprocal of the failure index, 0.9127, is below 1, so the laminate is not safe.", False),
    ("P2", "Hệ số an toàn, tức là nghịch đảo của chỉ số phá hủy, bằng 0.9127, nhỏ hơn 1.", False),
    ("P2", "The failure index of 1.096 is below 1.", True),
    ("P1", "The safety factor of 420, the reciprocal of the failure index, is below 1.", True),
    ("P1", "Hệ số an toàn, tức là nghịch đảo của chỉ số phá hủy, bằng 420, nhỏ hơn 1.", True),
]

# (answer, context materials named in it, must be flagged?)
RAG_TEXTS = [
    # gemma3:4b in the offline demo of 28/10/2026: all three materials attributed to one report
    ("The NCAMP material with the highest longitudinal tensile strength (Xt) is T1100G/3960 with a value of 3645 MPa "
     "(source [1]: p.34). The material T1100GC/TC380 has 3277 MPa (source [2]: p.38), and IM7G/EP2202 has 2967 MPa "
     "(source [3]: p.35). This information was obtained from the NCAMP NCP-RP-2023-002 Rev B database.", True),
    ("The NCAMP material with the highest Xt is T1100G/3960 with 3645 MPa (source [1]: NCAMP NCP-RP-2023-002 Rev B, "
     "lamina summary table p.34). T1100GC/TC380 has 3277 MPa (source [2]: NCAMP NCP-RP-2025-010 Rev -, p.38).", False),
    ("T1100G/3960 has the highest Xt, 3645 MPa (NCAMP NCP-RP-2023-002 Rev B, p.34), followed by T1100GC/TC380 with "
     "3277 MPa (NCAMP NCP-RP-2023-002, p.38).", True),
    ("According to NCAMP NCP-RP-2009-028 Rev B, Table 3-3 p.37, the Xt of IM7/8552 is 2212 MPa.", False),
    ("The longitudinal tensile strength Xt of IM7/8552 is 2212 MPa (source: NCAMP NCP-RP-2010-008 Rev D, p.37).", True),
    ("Độ bền cắt S của AS4/8552 là 91.6 MPa (nguồn: NCAMP NCP-RP-2010-008 Rev D, lamina summary table p.37).", False),
    ("Độ bền cắt S của AS4/8552 là 91.6 MPa (nguồn: NCAMP NCP-RP-2008-004 Rev B, p.35).", True),
    ("The database does not contain it.", False),
]


def fake_result(name):
    mat_name, angles, t, loads = CASES[name]
    mat = predict_material(mat_name)
    full = {k: float(loads.get(k, 0.0)) for k in llm.LOAD_KEYS}
    problem = CLTInput.model_validate({"material": mat_name, "plies": [{"angle": a, "thickness": t} for a in angles],
                                       "loads": full})
    m = type("M", (), mat)
    r = analyze(angles, t, m, **full)
    result = {"ABD": r["ABD"].tolist(), "ply_stress": r["ply_stress"].tolist(),
              "failure_index": [[float(x)] for x in r["failure_index"]],
              "max_failure_index": r["max_failure_index"], "critical_ply": float(r["critical_ply"])}
    return problem, result, mat


def main():
    bad = 0
    data = {n: fake_result(n) for n in CASES}
    s1 = llm.summarize(*data["P1"])
    assert abs(s1["max_failure_index"] - 0.002381) < 1e-6 and s1["critical_ply"] == 4, s1
    assert abs(s1["ABD11_N_per_m"] - 5.94e7) / 5.94e7 < 1e-3, s1
    for case, text, flag in TEXTS:
        issues = llm.explanation_issues(text, *data[case])
        if bool(issues) != flag:
            bad += 1
            print(f"[meaning] WRONG ({'should be flagged' if flag else 'false alarm'}): {text[:90]}...\n   {issues}")
    for case in CASES:
        for lang in ("en", "vi"):
            text, note = llm.prebuilt_explanation(*data[case], lang=lang)
            issues = llm.explanation_issues(text, *data[case])
            if issues:
                bad += 1
                print(f"[prebuilt {case} {lang}] does not pass its own checks: {issues}\n   {text}")
    for text, flag in RAG_TEXTS:
        issues = rag.check_citations(text)
        if bool(issues) != flag:
            bad += 1
            print(f"[citation] WRONG ({'should be flagged' if flag else 'false alarm'}): {text[:90]}...\n   {issues}")
    n = len(TEXTS) + 2 * len(CASES) + len(RAG_TEXTS)
    print(f"{n - bad}/{n} checks as expected")
    print("ALL PASS" if bad == 0 else f"{bad} PROBLEMS")
    return bad


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(1 if main() else 0)
