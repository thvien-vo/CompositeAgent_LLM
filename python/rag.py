"""
rag.py - first RAG (Retrieval-Augmented Generation) prototype for the composite agent.

Idea (same flow GS. Nishikawa / Mr. Saito proposed, in Python for now):
  question -> nomic-embed-text (text -> vector) -> similarity search in the material database
           -> best matching rows put into the prompt -> gemma3 answers, citing the source report/page

Database = composite_lamina_dataset_v4.csv (25 real lamina systems, 15 from NCAMP reports).
Vectors are stored in rag_index.json (rebuilt automatically when the CSV or model changes).
Later this store can be replaced by PostgreSQL + pgvector without changing the idea.

Run:
  python rag.py                      -> interactive questions (type 'exit' to stop)
  python rag.py "What is Xt of IM7/8552?"
Needs:  ollama pull gemma3:4b   and   ollama pull nomic-embed-text
"""
import hashlib
import json
import math
import os
import sys

import pandas as pd

from llm import _post, ask_llm

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_CSV = os.path.join(HERE, "composite_lamina_dataset_v4.csv")
INDEX_PATH = os.path.join(HERE, "rag_index.json")
EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
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
    parts.append(f"Source: {r['source']}. Verification status: {r['verify_status']}.")
    if isinstance(r.get("note"), str) and r["note"].strip():
        parts.append(f"Note: {r['note']}")
    return " ".join(parts)


def embed(texts, kind):
    """kind = 'search_document' or 'search_query' (prefixes required by nomic-embed-text)."""
    reply = _post("/api/embed", {"model": EMBED_MODEL, "input": [f"{kind}: {t}" for t in texts]})
    return reply["embeddings"]


def _fingerprint():
    with open(DATA_CSV, "rb") as f:
        return hashlib.sha256(f.read() + EMBED_MODEL.encode()).hexdigest()


def load_index():
    """Load vectors from rag_index.json, or (re)build them from the CSV."""
    fp = _fingerprint()
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, encoding="utf-8") as f:
            idx = json.load(f)
        if idx.get("fingerprint") == fp:
            return idx
    print(f"rag.py: building vector index of the material database with {EMBED_MODEL} ...")
    df = pd.read_csv(DATA_CSV)
    docs = [row_to_text(r) for _, r in df.iterrows()]
    vecs = embed(docs, "search_document")
    idx = {"fingerprint": fp, "model": EMBED_MODEL, "docs": docs, "vectors": vecs}
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(idx, f)
    print(f"rag.py: indexed {len(docs)} materials -> {os.path.basename(INDEX_PATH)}")
    return idx


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def search(question, k=TOP_K):
    """Return the k most similar documents as (score, text)."""
    idx = load_index()
    q = embed([question], "search_query")[0]
    scored = sorted(((_cosine(q, v), d) for v, d in zip(idx["vectors"], idx["docs"])), reverse=True)
    return scored[:k]


def answer(question, k=TOP_K, show_context=True):
    hits = search(question, k)
    if show_context:
        print("\n--- Retrieved from database ---")
        for i, (s, d) in enumerate(hits, 1):
            print(f"[{i}] (similarity {s:.3f}) {d[:110]}...")
    context = "\n\n".join(f"[{i}] {d}" for i, (_, d) in enumerate(hits, 1))
    prompt = f"""
You are an assistant for composite material data. Answer the question using ONLY the context below.
Give the number with its unit, and cite the source report and page shown in the context, e.g. "(source [1]: NCAMP NCP-RP-2009-028, p.37)".
If the answer is not in the context, say that the database does not contain it. Do not invent numbers.

Context:
{context}

Question: {question}
"""
    return ask_llm(prompt)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        print("\n=== ANSWER ===\n" + answer(q))
    else:
        print("RAG demo - ask about the 25 materials in the database (type 'exit' to stop).")
        while True:
            q = input("\nQuestion: ").strip()
            if q.lower() in ("exit", "quit", ""):
                break
            print("\n=== ANSWER ===\n" + answer(q))
