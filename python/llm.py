"""
llm.py - LLM part of the CLT agent (same function names as before, main.py calls them):
  - parse_input(user_text)                 -> CLTInput  (LLM step 1: text -> structured data)
  - explain_result(problem, r, material)   -> str       (LLM step 4: numbers -> explanation)

Backends (choose with $env:LLM_BACKEND = "auto" | "hf" | "ollama", default "auto"):
  hf     : openai/gpt-oss-120b via Hugging Face Inference Providers (needs $env:HF_TOKEN, PRO credits)
  ollama : gemma3:4b running locally with Ollama (free, offline)  https://ollama.com/download
  auto   : try the backends in AUTO_ORDER; if one fails (no internet, no token...) use the next.

Step 1 design ("LLM reads, Python calculates", version v2):
  The LLM only COPIES numbers and units from the text into a fixed JSON shape (the shape is enforced:
  Ollama "format", Hugging Face "response_format"). Python then expands the stacking sequence
  (layup.py, e.g. [0/90]2s -> 8 plies) and converts units (mm -> m, kN/m -> N/m, ...).
  The old version (v1, LLM did everything) is kept in llm_v1_baseline.py; benchmark_llm.py compares them.
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

from schemas import CLTInput
from ml import MATERIAL_DB
from layup import LayupError, expand_layup

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")          # local model (Ollama)
HF_MODEL = os.environ.get("HF_MODEL", "openai/gpt-oss-120b")  # cloud model (Hugging Face)
# Cerebras answered in ~1 s in our tests (27/10/2026); if it fails the retry lets Hugging Face choose.
HF_PROVIDERS = [os.environ.get("HF_PROVIDER", "cerebras"), "auto"]
BACKEND = os.environ.get("LLM_BACKEND", "auto").lower()
AUTO_ORDER = ["hf", "ollama"]  # chosen from benchmark_llm.py results (see PROGRESS.md)
LAST_BACKEND = None  # which backend answered the last call (printed by main.py / demos)
LAST_PARSE = {}      # details of the last parse_input() call: raw LLM JSON, warnings, time
TIMEOUT = 600        # Ollama: the first call loads the model into GPU memory
HF_TIMEOUT = 45      # Hugging Face: fail fast so "auto" can switch to Ollama when offline

LOAD_KEYS = ["Nx", "Ny", "Nxy", "Mx", "My", "Mxy"]

# ---- units the LLM may write, and their factor to SI (m, N/m, N*m/m = N) ----
LENGTH_UNITS = {"m": 1.0, "mm": 1e-3, "um": 1e-6, "in": 0.0254}
FORCE_UNITS = {"N/m": 1.0, "kN/m": 1e3, "N/mm": 1e3, "lbf/in": 4.4482216152605 / 0.0254}
MOMENT_UNITS = {"N*m/m": 1.0, "N": 1.0, "N*mm/mm": 1.0, "N*mm/m": 1e-3, "kN*m/m": 1e3,
                "lbf*in/in": 4.4482216152605}


def _qty(units):
    return {"type": "object",
            "properties": {"value": {"type": "number"}, "unit": {"type": "string", "enum": list(units)}},
            "required": ["value", "unit"]}


EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "material": {"type": "string", "enum": list(MATERIAL_DB)},
        "layup": {"type": "string"},
        "ply_thickness": _qty(LENGTH_UNITS),
        "total_thickness": _qty(LENGTH_UNITS),
        "ply_thickness_list": {"type": "array", "items": _qty(LENGTH_UNITS)},
        "loads": {
            "type": "object",
            "properties": {k: _qty(FORCE_UNITS if k.startswith("N") else MOMENT_UNITS) for k in LOAD_KEYS},
            "required": LOAD_KEYS,
        },
    },
    "required": ["material", "layup", "ply_thickness", "total_thickness", "ply_thickness_list", "loads"],
}


# ------------------------------------------------------------------ backends
def _post(path, payload, timeout=TIMEOUT):
    """Send one request to the local Ollama server and return the JSON reply."""
    req = urllib.request.Request(
        OLLAMA_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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
        "options": {"temperature": 0, "num_ctx": 8192},  # 0 = same input gives the same answer
    }
    if json_schema is not None:
        payload["format"] = json_schema
    return _post("/api/chat", payload)["message"]["content"]


def _ask_hf(prompt, json_schema=None):
    from huggingface_hub import InferenceClient  # imported here so Ollama-only use needs no HF
    if not os.environ.get("HF_TOKEN"):
        raise RuntimeError("HF_TOKEN is not set")
    kw = {}
    if json_schema is not None:
        kw["response_format"] = {"type": "json_schema", "json_schema": {"name": "answer", "schema": json_schema}}
    last_err = None
    for attempt, provider in enumerate(HF_PROVIDERS):  # retry once, with another provider
        client = InferenceClient(provider=provider, timeout=HF_TIMEOUT)  # reads HF_TOKEN from the environment
        try:
            resp = client.chat.completions.create(
                model=HF_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000,  # gpt-oss "thinks" first; too small a limit returns no content
                temperature=0,
                **kw,
            )
            text = resp.choices[0].message.content
            if not text or not text.strip():
                raise RuntimeError(f"empty reply (finish_reason={resp.choices[0].finish_reason})")
            return text
        except Exception as e:
            last_err = e
            if attempt + 1 < len(HF_PROVIDERS):
                print(f"[llm.py] HF provider '{provider}' failed ({type(e).__name__}: {str(e)[:100]}) -> retrying")
                time.sleep(1)
    raise last_err


_ASK = {"hf": _ask_hf, "ollama": _ask_ollama}
_NAME = {"hf": lambda: f"Hugging Face ({HF_MODEL})", "ollama": lambda: f"Ollama ({MODEL})"}


def backend_order(backend=None):
    b = (backend or BACKEND).lower()
    if b in _ASK:
        return [b]
    if b != "auto":
        raise ValueError(f"LLM_BACKEND must be auto, hf or ollama (got '{b}')")
    return [x for x in AUTO_ORDER if x != "hf" or os.environ.get("HF_TOKEN")] or ["ollama"]


def ask_llm(prompt, json_schema=None, backend=None):
    """Send a prompt to the chosen LLM backend (with automatic fallback in 'auto') and return its text."""
    global LAST_BACKEND
    order = backend_order(backend)
    errors = []
    for i, b in enumerate(order):
        try:
            text = _ASK[b](prompt, json_schema)
            LAST_BACKEND = _NAME[b]()
            return text
        except Exception as e:
            errors.append(f"{_NAME[b]()}: {type(e).__name__}: {str(e)[:200]}")
            if i + 1 < len(order):
                print(f"[llm.py] {_NAME[b]()} failed ({type(e).__name__}: {str(e)[:120]}) "
                      f"-> using {_NAME[order[i + 1]]()}")
    raise RuntimeError("All LLM backends failed:\n  " + "\n  ".join(errors))


def _extract_json(text):
    """Models sometimes wrap JSON in ```json ... ```; keep only the {...} part."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"LLM did not return JSON:\n{text}")
    return json.loads(text[start:end + 1])


# ------------------------------------------------------------------ step 1: text -> CLTInput
PARSE_PROMPT = """
You copy the data of a composite laminate problem into JSON for a Classical Laminate Theory (CLT) program.
Copy numbers and units EXACTLY as written. Do NOT convert units and do NOT expand the stacking
sequence: the program does that itself.

TEXT:
{text}

Fields:
- "material": one of {materials}. Carbon or graphite fibre (T300, AS4, IM7, "sợi carbon"...) -> CFRP;
  glass fibre (E-glass, S-glass, fiberglass, "sợi thủy tinh") -> GFRP; aramid or Kevlar -> KEVLAR.
- "layup": the stacking sequence copied exactly as written, e.g. "[0/±45]s", "[0/90]2s", "[45/-45]".
  If the plies are listed one by one, write all their angles in order separated by "/", e.g. "0/90/90/0".
- "ply_thickness": thickness of ONE ply when all plies have the same thickness, otherwise value 0.
- "total_thickness": the total laminate thickness, only if the text gives it instead of the ply thickness,
  otherwise value 0.
- "ply_thickness_list": only if the plies have DIFFERENT thicknesses: one entry per ply, same order as
  the layup. Otherwise [].
- "loads": Nx, Ny, Nxy (force per unit length) and Mx, My, Mxy (moment per unit length) with their units.
  Use value 0 for anything not mentioned. Keep the sign (-1.5 stays -1.5).
  Write a decimal comma as a point (0,15 -> 0.15).
Unit names: length "m", "mm", "um" (= µm), "in"; force per length "N/m", "kN/m", "N/mm", "lbf/in";
moment per length "N*m/m", "N*mm/mm", "N*mm/m", "kN*m/m", "lbf*in/in" (N.m/m and N·m/m are "N*m/m").

Answer only with JSON.
"""


def _si(q, table, what):
    unit = str(q.get("unit", "")).strip()
    if unit not in table:
        raise ValueError(f"unknown unit '{unit}' for {what}")
    return float(q.get("value", 0) or 0) * table[unit]


def build_problem(raw):
    """Deterministic part of step 1: raw LLM JSON (values as written) -> CLTInput in SI units.
    Returns (CLTInput, warnings)."""
    warnings = []
    try:
        angles = expand_layup(raw.get("layup", ""))
    except LayupError as e:
        raise ValueError(f"cannot read the stacking sequence '{raw.get('layup')}': {e}") from None
    n = len(angles)

    lst = [q for q in raw.get("ply_thickness_list") or [] if float(q.get("value", 0) or 0) > 0]
    ply_t = raw.get("ply_thickness") or {}
    tot_t = raw.get("total_thickness") or {}
    if lst and len(lst) == n:
        thick = [_si(q, LENGTH_UNITS, "ply thickness") for q in lst]
    elif float(ply_t.get("value", 0) or 0) > 0:
        thick = [_si(ply_t, LENGTH_UNITS, "ply thickness")] * n
        if lst:
            warnings.append(f"ignored a list of {len(lst)} ply thicknesses (layup has {n} plies)")
    elif float(tot_t.get("value", 0) or 0) > 0:
        thick = [_si(tot_t, LENGTH_UNITS, "total thickness") / n] * n
        warnings.append(f"ply thickness = total thickness / {n} plies")
    elif lst:
        raise ValueError(f"{len(lst)} ply thicknesses given but the layup has {n} plies")
    else:
        raise ValueError("no ply thickness or total thickness found in the text")

    # safety net: a single ply is never thicker than 5 mm -> the value was probably in mm
    if any(t > 0.005 for t in thick):
        thick = [t / 1000.0 if t > 0.005 else t for t in thick]
        warnings.append("ply thickness > 5 mm looked like millimetres -> divided by 1000")

    loads = {}
    for k in LOAD_KEYS:
        q = (raw.get("loads") or {}).get(k) or {"value": 0, "unit": "N/m" if k.startswith("N") else "N*m/m"}
        loads[k] = _si(q, FORCE_UNITS if k.startswith("N") else MOMENT_UNITS, k)
    if all(v == 0 for v in loads.values()):
        warnings.append("all loads are 0")

    problem = CLTInput.model_validate({
        "material": raw.get("material"),
        "plies": [{"angle": a, "thickness": t} for a, t in zip(angles, thick)],
        "loads": loads,
    })
    return problem, warnings


def parse_input(user_text, backend=None):
    global LAST_PARSE
    prompt = PARSE_PROMPT.format(text=user_text.strip(), materials=", ".join(MATERIAL_DB))
    t0 = time.time()
    text = ask_llm(prompt, json_schema=EXTRACT_SCHEMA, backend=backend)
    raw = _extract_json(text)
    LAST_PARSE = {"raw": raw, "backend": LAST_BACKEND, "seconds": round(time.time() - t0, 2), "warnings": []}
    problem, warnings = build_problem(raw)
    LAST_PARSE["warnings"] = warnings
    for w in warnings:
        print(f"[llm.py] note: {w}")
    return problem


# ------------------------------------------------------------------ step 4: numbers -> explanation
def _plain(x, digits=4):
    """Turn MATLAB results (matlab.double) into plain short Python numbers/lists."""
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


def summarize(problem, result, material):
    """Deterministic summary of the CLT result (no LLM): critical ply, failure mode, safety factor."""
    fi = [float(r[0]) for r in result["failure_index"]]
    stress = [list(map(float, r)) for r in result["ply_stress"]]
    angles = [p.angle for p in problem.plies]
    max_fi = float(result["max_failure_index"])
    crit = int(result["critical_ply"])
    tied = [i + 1 for i, v in enumerate(fi) if abs(v - max_fi) <= 1e-9 * max(max_fi, 1e-30)]
    s1, s2, t12 = stress[crit - 1]
    # (mode, stress component, its value, strength used, strength value) - same rules as clt_engine.m
    modes = [
        ("fibre direction", "sigma1", s1, "Xt (longitudinal tensile strength)" if s1 >= 0
         else "Xc (longitudinal compressive strength)", material["Xt"] if s1 >= 0 else material["Xc"]),
        ("transverse", "sigma2", s2, "Yt (transverse tensile strength)" if s2 >= 0
         else "Yc (transverse compressive strength)", material["Yt"] if s2 >= 0 else material["Yc"]),
        ("in-plane shear", "tau12", t12, "S (in-plane shear strength)", material["S"]),
    ]
    mode = max(modes, key=lambda m: abs(m[2]) / m[4])
    return {
        "n_plies": len(angles),
        "total_thickness_mm": round(sum(p.thickness for p in problem.plies) * 1e3, 6),
        "max_failure_index": float(f"{max_fi:.4g}"),
        "critical_ply": crit,
        "critical_ply_angle_deg": angles[crit - 1],
        "plies_with_same_max_index": tied,
        "governing_mode": f"{mode[0]} ({mode[1]}, {'tension' if mode[2] >= 0 else 'compression'})"
                          if mode[1] != "tau12" else "in-plane shear (tau12)",
        "governing_stress_MPa": float(f"{mode[2] / 1e6:.4g}"),
        "compared_with": mode[3],
        "strength_MPa": float(f"{mode[4] / 1e6:.4g}"),
        "safety_factor_1_over_FI": float(f"{1 / max_fi:.4g}") if max_fi > 0 else None,
        "safe": max_fi < 1,
        "ABD11_N_per_m": float(f"{float(result['ABD'][0][0]):.4g}"),
    }


def explain_result(problem, result, material=None, backend=None, lang="en"):
    material = material or {}
    plies = []
    for i, (p, s, f) in enumerate(zip(problem.plies, result["ply_stress"], result["failure_index"]), 1):
        s = list(map(float, s))
        plies.append({"ply": i, "angle_deg": p.angle, "sigma1_MPa": float(f"{s[0] / 1e6:.4g}"),
                      "sigma2_MPa": float(f"{s[1] / 1e6:.4g}"), "tau12_MPa": float(f"{s[2] / 1e6:.4g}"),
                      "failure_index": float(f"{float(f[0]):.4g}")})
    strengths = {k: float(f"{material[k] / 1e6:.4g}") for k in ("Xt", "Xc", "Yt", "Yc", "S") if k in material}
    summary = summarize(problem, result, material) if strengths else {}
    language = "Vietnamese" if lang == "vi" else "English"
    prompt = f"""
Briefly explain the result of a Classical Laminate Theory (CLT) calculation for an engineer
(5-8 sentences, plain text, no tables, no markdown, in {language}).

Laminate: {problem.material}, {len(problem.plies)} plies, loads (N/m and N*m/m): {problem.loads.model_dump_json()}
Ply strengths used, from the ML model (MPa): {json.dumps(strengths)}
Per-ply stresses in fibre axes and Max Stress failure index (>= 1 means the ply fails):
{json.dumps(plies)}
Summary computed by the program: {json.dumps(summary)}

Say: the maximum failure index and which ply (number and angle) is critical, whether the laminate is safe
(index < 1) and its safety factor, and why that ply is critical: use "governing_mode", "governing_stress_MPa",
"compared_with" and "strength_MPa" from the summary (failure index = |stress| / strength).
Use only numbers given above; do not invent any number.
"""
    return ask_llm(prompt, backend=backend)


def check_explanation(text, problem, result, material):
    """Simple guardrail: list the numbers in the LLM explanation that do not appear in the data we gave it
    (allowing rounding). Returns a list of suspicious numbers (empty list = nothing suspicious)."""
    allowed = set()

    def add(v):
        v = float(v)
        allowed.add(v)
        for scale in (1e-6, 1e-3, 1e3, 1e6, 100):
            allowed.add(v * scale)

    s = summarize(problem, result, material)
    for v in s.values():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            add(v)
        elif isinstance(v, list):
            for x in v:
                add(x)
    for r in result["ply_stress"]:
        for v in r:
            add(v)
    for r in result["failure_index"]:
        add(r[0])
    for k, v in material.items():
        add(v)
    for p in problem.plies:
        add(p.angle)
        add(p.thickness)
    for v in problem.loads.model_dump().values():
        add(v)
    for i in range(0, len(problem.plies) + 2):
        add(i)
    add(100)
    sup = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
    # "5.94 × 10⁷", "5.94 x 10^7", "5.94·10^7", "5.94e7" -> "5.94e7"
    norm = re.sub(r"\s*[x×·*]\s*10\s*\^?\s*\(?([-+⁻⁺−]?[0-9⁰¹²³⁴⁵⁶⁷⁸⁹]+)\)?",
                  lambda m: "e" + m.group(1).translate(sup).replace("−", "-"), text)
    norm = norm.replace("−", "-").replace("‑", "-")
    suspicious = []
    for m in re.finditer(r"(?<![\w.])[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?", norm):
        tok = m.group()
        if re.fullmatch(r"[-+]?\d{1,3}(,\d{3})+", tok):  # 1,000 = thousands separator
            tok = tok.replace(",", "")
        tok = tok.replace(",", ".")
        try:
            v = float(tok)
        except ValueError:
            continue
        digits = len(re.sub(r"[^0-9]", "", re.split("[eE]", tok)[0]).lstrip("0")) or 1
        rel = max(0.5 * 10 ** (1 - digits), 0.005)  # tolerance follows the digits the LLM wrote
        if not any(abs(v - a) <= rel * max(abs(a), 1e-30) or abs(abs(v) - abs(a)) <= rel * max(abs(a), 1e-30)
                   for a in allowed):
            suspicious.append(m.group())
    return suspicious
