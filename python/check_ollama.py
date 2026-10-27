"""
check_ollama.py - check that Ollama is ready before running main.py / rag.py.
Run:  python check_ollama.py
"""
import sys

from llm import MODEL, OLLAMA_URL, _ask_ollama as ask_llm
from rag import EMBED_MODEL, embed

import json
import urllib.request

ok = True
try:
    with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=10) as r:
        names = [m["name"] for m in json.loads(r.read().decode("utf-8")).get("models", [])]
    print(f"[OK] Ollama is running at {OLLAMA_URL}")
    print("     installed models:", ", ".join(names) or "(none)")
except Exception:
    print(f"[FAIL] Ollama is not running at {OLLAMA_URL}. Open the Ollama app, then run this again.")
    sys.exit(1)

for need in (MODEL, EMBED_MODEL):
    have = any(n == need or n.split(":")[0] == need for n in names)
    print(f"[{'OK' if have else 'FAIL'}] model {need}" + ("" if have else f"  -> run: ollama pull {need}"))
    ok = ok and have
if not ok:
    sys.exit(1)

print("Testing chat model (first call loads the model, can take ~30 s) ...")
print("     reply:", ask_llm("Reply with exactly: OK").strip()[:60])
v = embed(["test"], "search_query")[0]
print(f"[OK] embedding model returns vectors of length {len(v)}")
print("\nAll good. Next:  python main.py   and   python rag.py")
