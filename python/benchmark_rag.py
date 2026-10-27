"""
benchmark_rag.py - test the RAG answers against known values from composite_lamina_dataset_v4.csv.

For each question: is the right material retrieved? does the answer contain the right number,
the right report id and page? does the guardrail find invented numbers?
Run:  python benchmark_rag.py [--backends hf,ollama]
Results: ../deliverables/benchmark/rag_benchmark_<time>.md / .json
"""
import argparse
import datetime
import json
import os
import re
import time

import rag

# (id, question, material that must be retrieved, strings the answer must contain (any-of groups))
QUESTIONS = [
    ("R1", "What is the longitudinal tensile strength Xt of IM7/8552?", "IM7/8552",
     [["2212"], ["NCP-RP-2009-028"], ["37"]]),
    ("R2", "Độ bền cắt S của AS4/8552 là bao nhiêu?", "AS4/8552",
     [["91.6", "91,6"], ["NCP-RP-2010-008"], ["37"]]),
    ("R3", "What is E1 of T1100G/3960 and which report is it from?", "T1100G/3960",
     [["170.5"], ["NCP-RP-2023-002"], ["34"]]),
    ("R4", "Give the transverse compressive strength Yc of T650/5320-1.", "T650/5320-1",
     [["274"], ["NCP-RP-2013-001"], ["35"]]),
    ("R5", "What is the Poisson's ratio nu12 of T40-800/5215? Is the value reliable?", "T40-800/5215",
     [["0.164"], ["anomal", "low", "unreliable", "not reliable", "caution", "question"]]),
    ("R6", "Which NCAMP material has the highest Xt?", "T1100G/3960",
     [["T1100G/3960"], ["3645"], ["NCP-RP-2023-002"]]),
    ("R7", "Vật liệu sợi thủy tinh nào có mô đun dọc E1 lớn nhất?", "E-glass/LY556",
     [["E-glass/LY556", "LY556"], ["53.48", "53,48"]]),
    ("R8", "What is the tensile strength of titanium Ti-6Al-4V?", None,
     [["not contain", "does not", "no data", "not in", "không có", "not available", "not include"]]),
    ("R9", "What is the in-plane shear strength S of T650/5250-5?", "T650/5250-5",
     [["not reported", "not available", "does not", "not given", "not provide"]]),
    ("R10", "What is the fibre volume fraction of AS4/MTM45-1?", "AS4/MTM45-1",
     [["0.58"], ["NCP-RP-2008-004"]]),
    ("R11", "What is Yc of Kevlar 49/epoxy?", "Kevlar 49/epoxy",
     [["53"], ["conflict", "not yet verified", "not verified", "unverified"]]),
    ("R12", "Mô đun cắt G12 của IM7/BT250E-6 là bao nhiêu?", "IM7/BT250E-6",
     [["4.34", "4,34"], ["NCP-RP-2015-019"], ["31"]]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backends", default="hf,ollama")
    args = ap.parse_args()
    rows = []
    for b in args.backends.split(","):
        for qid, q, mat, groups in QUESTIONS:
            t0 = time.time()
            try:
                res = rag.answer(q, backend=b, show_context=False)
                err = None
            except Exception as e:
                res, err = None, f"{type(e).__name__}: {str(e)[:200]}"
            sec = time.time() - t0
            if res:
                retrieved = [h["material"] for h in res["hits"]]
                hit = mat is None or mat in retrieved
                text = res["answer"]
                missing = [g for g in groups if not any(s.lower() in text.lower() for s in g)]
                ok = hit and not missing and not res["suspicious_numbers"]
            else:
                retrieved, hit, text, missing, ok = [], False, err, groups, False
            rows.append({"backend": b, "id": qid, "question": q, "ok": ok, "retrieval_hit": hit,
                         "retrieved": retrieved, "missing": missing, "seconds": round(sec, 1),
                         "suspicious": res["suspicious_numbers"] if res else None, "answer": text})
            print(f"[{b:6}] {'OK  ' if ok else 'FAIL'} {sec:5.1f}s {qid} retrieved={retrieved}"
                  + ("" if ok else f"\n      missing={missing} suspicious={res and res['suspicious_numbers']}")
                  + f"\n      {re.sub(r'\s+', ' ', text or '')[:300]}", flush=True)

    lines = [f"# RAG benchmark ({len(QUESTIONS)} questions)",
             f"Run: {datetime.datetime.now():%Y-%m-%d %H:%M}. Embedding: {rag.EMBED_MODEL} (Ollama).", "",
             "| backend | answer correct | right material retrieved | guardrail clean | mean s/question |",
             "|---|---|---|---|---|"]
    for b in args.backends.split(","):
        rs = [r for r in rows if r["backend"] == b]
        n = len(rs)
        lines.append(f"| {b} | **{sum(r['ok'] for r in rs)}/{n}** | {sum(r['retrieval_hit'] for r in rs)}/{n} | "
                     f"{sum(1 for r in rs if r['suspicious'] == [])}/{n} | {sum(r['seconds'] for r in rs) / n:.1f} |")
    lines += ["", "## Answers", ""]
    for r in rows:
        lines.append(f"- **{r['backend']} {r['id']}** {'OK' if r['ok'] else 'FAIL'} - {r['question']}  \n"
                     f"  {re.sub(r'\s+', ' ', r['answer'] or '')}"
                     + ("" if r["ok"] else f"  \n  missing: {r['missing']}; suspicious numbers: {r['suspicious']}"))
    md = "\n".join(lines)
    print("\n" + md)
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deliverables", "benchmark")
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, f"rag_benchmark_{datetime.datetime.now():%Y%m%d_%H%M}")
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1, ensure_ascii=False)
    with open(base + ".md", "w", encoding="utf-8") as f:
        f.write(md + "\n")
    print(f"\nSaved {base}.md / .json")


if __name__ == "__main__":
    main()
