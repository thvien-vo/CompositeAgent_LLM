"""
llm_v1_baseline.py - FROZEN copy of the original llm.py (before 27/10/2026), kept only so
benchmark_llm.py can compare the old prompt (v1) with the new one (v2). Do not use in the agent.
"""
"""
llm.py - LLM part of the CLT agent. Two backends, same function names as before
(main.py does not change):
  - parse_input(user_text)      -> CLTInput   (LLM step 1: text -> structured data)
  - explain_result(problem, r)  -> str        (LLM step 4: numbers -> explanation)

Backends (choose with $env:LLM_BACKEND = "auto" | "hf" | "ollama", default "auto"):
  hf     : openai/gpt-oss-120b via Hugging Face Inference Providers (needs $env:HF_TOKEN, PRO credits)
  ollama : gemma3:4b running locally with Ollama (free, offline)  https://ollama.com/download
  auto   : use hf if HF_TOKEN is set; if that call fails, fall back to ollama automatically.
"""
import json
import os
import urllib.error
import urllib.request

from schemas import CLTInput
from ml import MATERIAL_DB

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")          # local model (Ollama)
HF_MODEL = os.environ.get("HF_MODEL", "openai/gpt-oss-120b")  # cloud model (Hugging Face)
BACKEND = os.environ.get("LLM_BACKEND", "auto").lower()
LAST_BACKEND = None  # which backend answered the last call (printed by main.py / demos)
TIMEOUT = 600  # seconds; the first call loads the model into memory

LOAD_KEYS = ["Nx", "Ny", "Nxy", "Mx", "My", "Mxy"]

# JSON schema given to Ollama: the model is FORCED to answer in exactly this shape,
# and "material" can only be one of the names ml.py supports.
CLT_SCHEMA = {
    "type": "object",
    "properties": {
        "material": {"type": "string", "enum": list(MATERIAL_DB)},
        "plies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"angle": {"type": "number"}, "thickness": {"type": "number"}},
                "required": ["angle", "thickness"],
            },
        },
        "loads": {
            "type": "object",
            "properties": {k: {"type": "number"} for k in LOAD_KEYS},
            "required": LOAD_KEYS,
        },
    },
    "required": ["material", "plies", "loads"],
}


def _post(path, payload):
    """Send one request to the local Ollama server and return the JSON reply."""
    req = urllib.request.Request(
        OLLAMA_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        if e.code == 404:
            raise RuntimeError(
                f"Ollama does not have model '{payload.get('model')}'. "
                f"Run in the terminal:  ollama pull {payload.get('model')}\n(details: {detail})"
            ) from None
        raise RuntimeError(f"Ollama error {e.code}: {detail}") from None
    except urllib.error.URLError:
        raise RuntimeError(
            f"Cannot reach Ollama at {OLLAMA_URL}. Is Ollama running? "
            "Open the Ollama app (llama icon in the taskbar), or run 'ollama serve' in another terminal."
        ) from None


def _ask_ollama(prompt, json_schema=None):
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0},  # 0 = same input gives the same answer
    }
    if json_schema is not None:
        payload["format"] = json_schema
    return _post("/api/chat", payload)["message"]["content"]


def _ask_hf(prompt):
    from huggingface_hub import InferenceClient  # imported here so Ollama-only use needs no HF
    client = InferenceClient(timeout=TIMEOUT)    # reads HF_TOKEN from the environment
    resp = client.chat.completions.create(
        model=HF_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0,
    )
    return resp.choices[0].message.content


def ask_llm(prompt, json_schema=None):
    """Send a prompt to the chosen LLM backend and return its text answer."""
    global LAST_BACKEND
    use_hf = BACKEND == "hf" or (BACKEND == "auto" and os.environ.get("HF_TOKEN"))
    if use_hf:
        try:
            text = _ask_hf(prompt)
            LAST_BACKEND = f"Hugging Face ({HF_MODEL})"
            return text
        except Exception as e:
            if BACKEND == "hf":
                raise
            print(f"[llm.py] Hugging Face failed ({type(e).__name__}: {str(e)[:120]}) -> using Ollama")
    text = _ask_ollama(prompt, json_schema)
    LAST_BACKEND = f"Ollama ({MODEL})"
    return text


def _extract_json(text):
    """Small models sometimes wrap JSON in ```json ... ```; keep only the {...} part."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"LLM did not return JSON:\n{text}")
    return json.loads(text[start:end + 1])


def _fix_units(data):
    """Safety net: a single ply is never thicker than 5 mm. If the LLM kept millimetres
    (e.g. 0.125 instead of 0.000125 m), convert to metres and say so."""
    fixed = []
    for ply in data.get("plies", []):
        t = float(ply["thickness"])
        if t > 0.005:
            ply["thickness"] = t / 1000.0
            fixed.append(t)
    if fixed:
        print(f"[llm.py] {len(fixed)} ply thickness value(s) looked like mm -> converted to metres")
    for k in LOAD_KEYS:
        data.setdefault("loads", {}).setdefault(k, 0.0)
    return data


def parse_input(user_text):
    supported = ", ".join(MATERIAL_DB)  # "CFRP, GFRP, KEVLAR"

    prompt = f"""
You are an assistant for composite material analysis.

Extract the information needed for a Classical Laminate Theory (CLT) calculation from the text below.

TEXT:
{user_text}

Rules:
- "material" must be exactly one of: {supported}. Carbon fiber -> CFRP, glass fiber -> GFRP, aramid/Kevlar -> KEVLAR.
- "plies": one entry per ply, in the order given. If a stacking like [0/45/-45/90]s is symmetric (s), write all plies.
- "angle" in degrees.
- "thickness" in METERS (e.g. "0.125 mm" -> 0.000125, NOT 0.125).
- "Nx","Ny","Nxy" in N/m. "Mx","My","Mxy" in N (N.m/m). Use 0 for anything not mentioned.

Answer only with JSON.
"""
    text = ask_llm(prompt, json_schema=CLT_SCHEMA)
    data = _fix_units(_extract_json(text))
    return CLTInput.model_validate(data)


def _plain(x, digits=4):
    """Turn MATLAB results (matlab.double) into plain short Python numbers/lists for the prompt."""
    if type(x).__module__.startswith("matlab"):  # matlab.double and similar
        rows = [list(r) for r in x]
        rows = [[float(f"{v:.{digits}g}") for v in r] for r in rows]
        return rows[0] if len(rows) == 1 else rows
    if isinstance(x, dict):
        return {k: _plain(v, digits) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v, digits) for v in x]
    if isinstance(x, float):
        return float(f"{x:.{digits}g}")
    return x


def explain_result(problem, result):
    compact = _plain(result)
    prompt = f"""
Briefly explain the CLT calculation result below for an engineer (5-8 sentences, plain text).

Input (SI units: thickness in m, loads in N/m):
{problem.model_dump_json()}

CLT result (stress in Pa, ply_stress rows = [sigma1, sigma2, tau12] in fibre axes;
failure_index uses the Max Stress criterion, >= 1 means the ply fails):
{json.dumps(compact)}

Mention: the maximum failure index and which ply (number and angle) is critical, whether the laminate
is safe (index < 1), and why that ply is critical (compare its sigma2 with the transverse strength if relevant).
Do not invent any number that is not given above.
"""
    return ask_llm(prompt)
