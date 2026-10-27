"""
rag.py - RAG (Retrieval-Augmented Generation) over the composite material database.

Flow (the one GS. Nishikawa / MathWorks proposed; vector store is a JSON file for now):
  question -> nomic-embed-text (Ollama, text -> 768-number vector)
           -> similarity search over the 25 materials (cosine similarity + exact material-name match)
           -> best rows (+ a ranking computed by Python for "highest / lowest" questions) put in the prompt
           -> LLM (gpt-oss-120b on Hugging Face, or gemma3:4b on Ollama) answers and cites report + page
           -> guardrail: every number in the answer must appear in the retrieved context

Database = composite_lamina_dataset_v4.csv (25 lamina systems: 15 NCAMP reports checked against the PDF,
10 textbook rows). Vectors are cached in rag_index.json (rebuilt automatically when the CSV changes).
Later this store can be replaced by PostgreSQL + pgvector without changing the idea.

Run:
  python rag.py                                   interactive (type 'exit' to stop)
  python rag.py "What is Xt of IM7/8552?"
  python rag.py --backend ollama "Độ bền cắt S của AS4/8552 là bao nhiêu?"
Needs:  ollama pull nomic-embed-text   (and gemma3:4b for offline answers)
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys

import pandas as pd

import llm
from llm import _post, ask_llm

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_CSV = os.path.join(HERE, "composite_lamina_dataset_v4.csv")
INDEX_PATH = os.path.join(HERE, "rag_index.json")
EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
DOC_VERSION = "2"  # change when row_to_text changes -> index is rebuilt
TOP_K = 3

PROPS = [  # (csv column, label, unit)
    ("E1_GPa", "E1 (longitudinal modulus)", "GPa"),
    ("E2_GPa", "E2 (transverse modulus)", "GPa"),
    ("G12_GPa", "G12 (in-plane shear modulus)", "GPa"),
    ("nu12", "nu12 (Poisson's ratio)", ""),
    ("Xt_MPa", "Xt (longitudinal tensile strength)", "MPa"),
    ("Xc_MPa", "Xc (longitudinal compressive strength)", "MPa"),
    ("Yt_MPa", "Yt (transverse tensile strength)", "MPa"),
    ("Yc_MPa", "Yc (transverse compressive strength)", "MPa"),
    ("S_MPa", "S (in-plane shear strength)", "MPa"),
]

# phrases that point to one property (checked in this order: specific phrases first),
# then the bare symbols (Xt, E1, S...) as separate words
PROP_PHRASES = [
    ("Yt_MPa", ["transverse tensile", "kéo ngang"]),
    ("Yc_MPa", ["transverse compressive", "transverse compression", "nén ngang"]),
    ("E2_GPa", ["transverse modulus", "mô đun ngang", "mô-đun ngang", "modun ngang"]),
    ("G12_GPa", ["shear modulus", "mô đun cắt", "mô-đun cắt", "modun cắt"]),
    ("nu12", ["poisson", "ν12"]),
    ("S_MPa", ["shear strength", "độ bền cắt", "bền cắt"]),
    ("Xc_MPa", ["compressive strength", "compression strength", "độ bền nén", "bền nén"]),
    ("Xt_MPa", ["tensile strength", "độ bền kéo", "bền kéo"]),
    ("E1_GPa", ["longitudinal modulus", "young", "stiffest", "mô đun dọc", "mô-đun dọc", "modun dọc",
                "mô đun đàn hồi", "cứng nhất", "modulus"]),
]
PROP_SYMBOLS = {"E1_GPa": "e1", "E2_GPa": "e2", "G12_GPa": "g12", "nu12": "nu12", "Xt_MPa": "xt",
                "Xc_MPa": "xc", "Yt_MPa": "yt", "Yc_MPa": "yc", "S_MPa": "s"}
MAX_WORDS = ["highest", "largest", "maximum", "greatest", "strongest", "stiffest", r"\bbest\b", r"\bmax\b",
             "cao nhất", "lớn nhất", "mạnh nhất", "cứng nhất", "tốt nhất"]
MIN_WORDS = ["lowest", "smallest", "minimum", "weakest", r"\bmin\b", "thấp nhất", "nhỏ nhất", "yếu nhất",
             "kém nhất"]
GENERIC_PARTS = {"epoxy"}


def row_to_text(r):
    """One CSV row -> one readable 'document' that is embedded and shown to the LLM."""
    parts = [
        f"Material {r['material']}: {r['fiber']} fibre ({r['fiber_class']}) in {r['matrix']} "
        f"matrix ({r['matrix_family']}), fibre volume fraction Vf = {r['Vf']}."
    ]
    for col, label, unit in PROPS:
        v = r[col]
        if pd.isna(v):
            parts.append(f"{label}: not reported.")
        else:
            parts.append(f"{label} = {v:g} {unit}".rstrip() + ".")
    if isinstance(r.get("S_definition"), str) and r["S_definition"] != "as reported":
        parts.append(f"S definition: {r['S_definition']}.")
    parts.append(f"Source: {r['source']}. Verification status: {r['verify_status']}.")
    if isinstance(r.get("note"), str) and r["note"].strip():
        parts.append(f"Note: {r['note']}")
    return " ".join(parts)


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_table():
    return pd.read_csv(DATA_CSV)


# ------------------------------------------------------------------ embeddings + index
def embed(texts, kind):
    """kind = 'search_document' or 'search_query' (prefixes required by nomic-embed-text)."""
    reply = _post("/api/embed", {"model": EMBED_MODEL, "input": [f"{kind}: {t}" for t in texts]}, timeout=120)
    return reply["embeddings"]


def _fingerprint():
    with open(DATA_CSV, "rb") as f:
        return hashlib.sha256(f.read() + EMBED_MODEL.encode() + DOC_VERSION.encode()).hexdigest()


def load_index():
    """Load vectors from rag_index.json, or (re)build them from the CSV."""
    fp = _fingerprint()
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, encoding="utf-8") as f:
            idx = json.load(f)
        if idx.get("fingerprint") == fp:
            return idx
    print(f"rag.py: building vector index of the material database with {EMBED_MODEL} ...")
    df = load_table()
    docs = [row_to_text(r) for _, r in df.iterrows()]
    vecs = embed(docs, "search_document")
    idx = {"fingerprint": fp, "model": EMBED_MODEL, "materials": df["material"].tolist(),
           "docs": docs, "vectors": vecs}
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(idx, f)
    print(f"rag.py: indexed {len(docs)} materials -> {os.path.basename(INDEX_PATH)}")
    return idx


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def name_boost(question, material):
    """1.0 if the full material name is in the question (ignoring spaces, '/', '-'),
    else 0.25 per distinctive part (fibre or matrix name) found, max 0.5."""
    q = _norm(question)
    if _norm(material) in q:
        return 1.0
    parts = [_norm(p) for p in re.split(r"[/ ]", material)]
    hits = sum(1 for p in parts if len(p) >= 3 and p not in GENERIC_PARTS and p in q)
    return min(0.25 * hits, 0.5)


def search(question, k=TOP_K):
    """Return the k best documents as dicts {score, cosine, boost, material, text}.
    If the embedding model is not available, falls back to name matching + word overlap."""
    try:
        idx = load_index()
        q = embed([question], "search_query")[0]
        cos = [_cosine(q, v) for v in idx["vectors"]]
        materials, docs = idx["materials"], idx["docs"]
        mode = "embedding"
    except Exception as e:
        print(f"[rag.py] embedding search not available ({str(e)[:100]}) -> keyword search only")
        df = load_table()
        materials, docs = df["material"].tolist(), [row_to_text(r) for _, r in df.iterrows()]
        qw = set(re.findall(r"\w+", question.lower()))
        cos = [len(qw & set(re.findall(r"\w+", d.lower()))) / (len(qw) or 1) * 0.5 for d in docs]
        mode = "keyword"
    hits = []
    for c, m, d in zip(cos, materials, docs):
        b = name_boost(question, m)
        hits.append({"score": c + b, "cosine": c, "boost": b, "material": m, "text": d, "mode": mode})
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:k]


# ------------------------------------------------------------------ ranking questions ("highest Xt?")
def detect_property(question):
    """'Xt_MPa' for 'What is the tensile strength of ...?', 'Vf' for fibre volume fraction, else None."""
    ql = question.lower()
    if "volume fraction" in ql or "tỷ lệ thể tích" in ql or "tỉ lệ thể tích" in ql or re.search(r"\bvf\b", ql):
        return "Vf"
    for col, words in PROP_PHRASES:
        if any(w in ql for w in words):
            return col
    for col, sym in PROP_SYMBOLS.items():
        if re.search(rf"(?<![\w'’]){sym}(?![\w'’])", ql):
            return col
    return None


def detect_ranking(question):
    """('Xt_MPa', 'max') for 'Which material has the highest tensile strength?', else None."""
    ql = question.lower()
    has = lambda words: any(re.search(w, ql) for w in words)
    direction = "max" if has(MAX_WORDS) else "min" if has(MIN_WORDS) else None
    col = detect_property(question) if direction else None
    return (col, direction) if col and col != "Vf" else None


def fact_line(question, hits):
    """If the question names one material exactly and one property, look the value up directly in the table
    (no LLM) -> (text for the prompt, value or None if not reported, unit). Else None."""
    col = detect_property(question)
    exact = [h for h in hits if h["boost"] >= 1.0]
    if col is None or len(exact) != 1:
        return None
    m = exact[0]["material"]
    r = load_table().set_index("material").loc[m]
    label, unit = ("Vf (fibre volume fraction)", "") if col == "Vf" else next(
        (lab, u) for c, lab, u in PROPS if c == col)
    v = None if pd.isna(r[col]) else float(r[col])
    shown = "not reported in the database" if v is None else f"{v:g} {unit}".rstrip()
    return (f"Database value looked up by Python: {label} of {m} = {shown} "
            f"(source: {r['source']}; status: {r['verify_status']})", v, unit)


def ranking_block(question, n=5):
    """Text block with the top-n materials for a 'highest/lowest' question, and their names; or (None, [])."""
    det = detect_ranking(question)
    if det is None:
        return None, []
    col, direction = det
    df = load_table()
    ql = question.lower()
    scope = "all materials"
    if "ncamp" in ql:
        df, scope = df[df["data_type"] == "ncamp_mean"], "NCAMP materials only"
    for fc, words in {"carbon": ["carbon", "cfrp"], "glass": ["glass", "gfrp", "thủy tinh", "thuỷ tinh"],
                      "aramid": ["aramid", "kevlar"]}.items():
        if any(w in ql for w in words):
            df, scope = df[df["fiber_class"] == fc], f"{scope}, {fc} fibre"
    df = df[df[col].notna()].sort_values(col, ascending=(direction == "min"))
    label, unit = next((lab, u) for c, lab, u in PROPS if c == col)
    lines = [f"{i}. {r['material']}: {r[col]:g} {unit} (source: {r['source']}; status: {r['verify_status']})".replace(" )", ")")
             for i, (_, r) in enumerate(df.head(n).iterrows(), 1)]
    head = (f"Ranking computed by Python from the whole database ({scope}, {len(df)} materials with data), "
            f"property {label}, {'highest' if direction == 'max' else 'lowest'} first:")
    return head + "\n" + "\n".join(lines), df["material"].head(n).tolist()


# ------------------------------------------------------------------ answer
PROMPT = """
You are an assistant for composite material data. Answer the question using ONLY the context below.
- Give each number with its unit, and cite the source of THAT row exactly as written in the context, in the
  form "(source [<row number>]: <the Source text of that row>)". If that source has no page, say so.
- If a line [F] is given, it is the exact database value for the question: use it.
- If a ranking [R] is given, cite the source written after the material in the ranking.
- If a Note says a value is anomalous, conflicting or should be excluded, say that the value is doubtful.
- If the verification status is "needs_check" or "conflict", say that this value is not yet verified.
- If the answer is not in the context, say that the database does not contain it. Do not invent numbers.
- Answer in the same language as the question, in 1-4 sentences of plain text (no markdown, no LaTeX).

Context:
{context}

Question: {question}
"""


def _ascii(s):
    return re.sub("[‐‑‒–−]", "-", s or "")


def check_numbers(answer_text, context):
    """Numbers and NCAMP report ids in the answer that are not in the context (rounding allowed).
    Empty list = OK."""
    answer_text, context = _ascii(answer_text), _ascii(context)
    bad = [rid for rid in re.findall(r"NCP-RP-\d{4}-\d{3}", answer_text) if rid not in context]
    allowed = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", context)]
    for tok in re.findall(r"(?<![\w.])\d+(?:[.,]\d+)?", answer_text):
        v = float(tok.replace(",", "."))
        digits = len(re.sub(r"[^0-9]", "", tok).lstrip("0")) or 1
        rel = max(0.5 * 10 ** (1 - digits), 0.005)
        if not any(abs(v - a) <= rel * max(a, 1e-12) for a in allowed):
            bad.append(tok)
    return bad


def answer(question, k=TOP_K, backend=None, show_context=True):
    """Returns dict: answer, hits, ranking, context, suspicious_numbers, backend."""
    ranking, top = ranking_block(question)
    if ranking:  # "highest / lowest" question: the rows to show are the top of the ranking
        df = load_table().set_index("material")
        hits = [{"score": 0.0, "cosine": 0.0, "boost": 0.0, "material": m, "text": row_to_text(df.loc[m].to_dict()
                 | {"material": m}), "mode": "ranking"} for m in top[:k]]
    else:
        hits = search(question, k)
    blocks = [f"[{i}] {h['text']}" for i, h in enumerate(hits, 1)]
    if ranking:
        blocks.append(f"[R] {ranking}")
    fact = None if ranking else fact_line(question, hits)
    if fact:
        blocks.append(f"[F] {fact[0]}")
    context = "\n\n".join(blocks)
    if show_context:
        print(f"\n--- Retrieved from database ({hits[0]['mode']} search, top {k}) ---")
        for i, h in enumerate(hits, 1):
            print(f"[{i}] {h['material']:18} " + ("(top of the ranking below)" if h["mode"] == "ranking" else
                  f"score {h['score']:.3f} (similarity {h['cosine']:.3f} + name match {h['boost']:.2f})"))
        if ranking:
            print("[R] " + ranking.replace("\n", "\n    "))
        if fact:
            print("[F] " + fact[0])
    text = ask_llm(PROMPT.format(context=context, question=question), backend=backend)
    consistent = None
    if fact:  # does the answer state the value the table has?
        t = _ascii(text).lower()
        if fact[1] is None:
            consistent = any(w in t for w in ["not reported", "not available", "does not", "not given", "not provide",
                                              "no value", "không có", "chưa có", "không được báo cáo"])
        else:
            consistent = any(abs(float(x.replace(",", ".")) - fact[1]) <= 1e-9 + 0.005 * abs(fact[1])
                             for x in re.findall(r"\d+(?:[.,]\d+)?", t))
    return {"answer": text.strip(), "hits": hits, "ranking": ranking, "fact": fact, "fact_consistent": consistent,
            "context": context, "suspicious_numbers": check_numbers(text, context), "backend": llm.LAST_BACKEND}


def print_answer(res):
    print(f"\n=== ANSWER ({res['backend']}) ===\n{res['answer']}")
    print("\nSources of the retrieved rows:")
    df = load_table().set_index("material")
    for i, h in enumerate(res["hits"], 1):
        r = df.loc[h["material"]]
        print(f"  [{i}] {h['material']}: {r['source']} (status: {r['verify_status']})")
    if res["suspicious_numbers"]:
        print(f"[guardrail] numbers / report ids not found in the retrieved rows: {res['suspicious_numbers']}"
              " - check them")
    else:
        print("[guardrail] every number and report id in the answer appears in the retrieved database rows")
    if res.get("fact_consistent") is not None:
        print(f"[fact-check] the answer {'AGREES' if res['fact_consistent'] else 'does NOT agree'} with the "
              f"database value looked up by Python")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="RAG over the composite material database")
    ap.add_argument("question", nargs="*")
    ap.add_argument("--backend", default=None, choices=["auto", "hf", "ollama"])
    ap.add_argument("-k", type=int, default=TOP_K)
    args = ap.parse_args()
    if args.question:
        print_answer(answer(" ".join(args.question), k=args.k, backend=args.backend))
    else:
        print("RAG demo - ask about the 25 materials in the database (type 'exit' to stop).")
        while True:
            q = input("\nQuestion: ").strip()
            if q.lower() in ("exit", "quit", ""):
                break
            print_answer(answer(q, k=args.k, backend=args.backend))
