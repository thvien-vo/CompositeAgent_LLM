"""
main.py - CLT agent, 4 steps:
  (1) LLM reads the problem text  -> structured input (llm.parse_input)
  (2) ML predicts 9 ply properties -> E1, E2, G12, nu12, Xt, Xc, Yt, Yc, S (ml.predict_material)
  (3) MATLAB runs CLT              -> ABD, ply stresses, Max Stress failure index (clt_engine.m)
  (4) LLM explains the numbers     -> short text (llm.explain_result), numbers checked by a guardrail

Run:
  python main.py                                   built-in example
  python main.py "CFRP [0/90]s, 0.125 mm plies, Nx = 1 kN/m"
  python main.py --file problem.txt --backend ollama --lang vi
  --backend auto|hf|ollama  (default: $env:LLM_BACKEND or auto = Hugging Face, else Ollama)
"""
import argparse
import sys
import time

import llm
from llm import check_explanation, explain_result, parse_input, summarize
from ml import predict_material
from matlab_clt import run_clt

EXAMPLE = """
CFRP laminate.
Ply angles: 0, 45, -45, 90.
Ply thickness: 0.125 mm.
Nx=1000 N/m.
Ny=500 N/m.
Nxy=100 N/m.
"""


def print_problem(problem):
    print(f"  material : {problem.material}")
    print(f"  plies    : {len(problem.plies)}  angles = {[round(p.angle, 3) for p in problem.plies]}")
    ts = sorted({round(p.thickness * 1e3, 6) for p in problem.plies})
    print(f"  thickness: {ts} mm per ply, total {sum(p.thickness for p in problem.plies) * 1e3:.4g} mm")
    L = problem.loads
    print(f"  loads    : Nx={L.Nx:g}  Ny={L.Ny:g}  Nxy={L.Nxy:g} N/m   Mx={L.Mx:g}  My={L.My:g}  Mxy={L.Mxy:g} N*m/m")


def main(user_text, backend=None, lang="en", explain=True):
    t_all = time.time()

    # 1 LLM: text -> data
    print("\n[1/4] LLM reads the problem ...")
    t = time.time()
    problem = parse_input(user_text, backend=backend)
    print(f"  ({llm.LAST_BACKEND}, {time.time() - t:.1f} s)")
    print_problem(problem)

    # 2 ML: material properties
    print("\n[2/4] ML predicts ply properties (Random Forest, 25-material dataset) ...")
    material = predict_material(problem.material)
    print(f"  E1={material['E1'] / 1e9:.4g} GPa  E2={material['E2'] / 1e9:.4g} GPa  G12={material['G12'] / 1e9:.4g} GPa  "
          f"nu12={material['nu12']:.3g}")
    print(f"  Xt={material['Xt'] / 1e6:.4g}  Xc={material['Xc'] / 1e6:.4g}  Yt={material['Yt'] / 1e6:.4g}  "
          f"Yc={material['Yc'] / 1e6:.4g}  S={material['S'] / 1e6:.4g} MPa")

    # 3 MATLAB: CLT
    print("\n[3/4] MATLAB computes CLT ...")
    t = time.time()
    result = run_clt(problem, material)
    s = summarize(problem, result, material)
    print(f"  ({time.time() - t:.1f} s)")
    print(f"  ABD(1,1)          = {s['ABD11_N_per_m']:.4g} N/m")
    print(f"  max failure index = {s['max_failure_index']:.4g}   (Max Stress; >= 1 means failure)")
    print(f"  critical ply      = {s['critical_ply']} (angle {s['critical_ply_angle_deg']:g} deg)"
          + (f", same index in plies {s['plies_with_same_max_index']}" if len(s["plies_with_same_max_index"]) > 1 else ""))
    print(f"  governing mode    = {s['governing_mode']}: {s['governing_stress_MPa']:g} MPa vs "
          f"{s['compared_with'].split()[0]} = {s['strength_MPa']:g} MPa")
    print(f"  safety factor     = {s['safety_factor_1_over_FI']}   -> {'SAFE' if s['safe'] else 'FAILS'}")

    # 4 LLM: explanation (never blocks the numbers above)
    answer, suspicious = None, []
    if explain:
        print("\n[4/4] LLM explains the result ...")
        t = time.time()
        try:
            answer = explain_result(problem, result, material, backend=backend, lang=lang)
            print(f"  ({llm.LAST_BACKEND}, {time.time() - t:.1f} s)")
            suspicious = check_explanation(answer, problem, result, material)
        except Exception as e:
            print(f"  explanation not available: {type(e).__name__}: {str(e)[:200]}")
    print(f"\nTotal time: {time.time() - t_all:.1f} s")
    return {"problem": problem, "material": material, "result": result, "summary": s,
            "answer": answer, "suspicious_numbers": suspicious}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="CLT agent: text -> LLM -> ML -> MATLAB -> LLM")
    ap.add_argument("text", nargs="*", help="problem text (default: built-in example)")
    ap.add_argument("--file", help="read the problem text from a file")
    ap.add_argument("--backend", default=None, choices=["auto", "hf", "ollama"])
    ap.add_argument("--lang", default="en", choices=["en", "vi"], help="language of the explanation")
    ap.add_argument("--no-explain", action="store_true")
    args = ap.parse_args()
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            user_text = f.read()
    else:
        user_text = " ".join(args.text) or EXAMPLE
    print("===== PROBLEM =====")
    print(user_text.strip())

    out = main(user_text, backend=args.backend, lang=args.lang, explain=not args.no_explain)

    if out["answer"]:
        print("\n===== EXPLANATION (LLM) =====")
        print(out["answer"].strip())
        if out["suspicious_numbers"]:
            print(f"\n[guardrail] numbers not found in the CLT data: {out['suspicious_numbers']} - check them")
        else:
            print("\n[guardrail] every number in the explanation matches the CLT data")
