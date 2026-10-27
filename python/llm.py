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

import materials
from schemas import CLTInput
from ml import MATERIAL_DB
from layup import LayupError, expand_layup
from numwords import convert as numbers_from_words

# 127.0.0.1, not "localhost": on Windows "localhost" first tries IPv6 and costs ~2 s per call
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
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
        "fibre_words": {"type": "string"},
        "material_name": {"type": "string"},
        "material": {"type": "string", "enum": list(MATERIAL_DB)},
        "layup": {"type": "string"},
        "ply_thickness": _qty(LENGTH_UNITS),
        "total_thickness": _qty(LENGTH_UNITS),
        "ply_thickness_list": {"type": "array", "items": _qty(LENGTH_UNITS)},
        "loads": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string", "enum": LOAD_KEYS},
                               "value": {"type": "number"},
                               "unit": {"type": "string", "enum": list(FORCE_UNITS) + list(MOMENT_UNITS)}},
                "required": ["name", "value", "unit"],
            },
        },
    },
    "required": ["fibre_words", "material_name", "material", "layup", "ply_thickness", "total_thickness",
                 "ply_thickness_list", "loads"],
}

# fibre words -> material class (checked on the ORIGINAL text, so a small LLM cannot pick the wrong class)
MATERIAL_KEYWORDS = {
    "GFRP": ["glass", "gfrp", "thủy tinh", "thuỷ tinh", "fiberglass", "fibreglass", "scotchply"],
    "KEVLAR": ["kevlar", "aramid"],
    "CFRP": ["carbon", "cfrp", "graphite", "cacbon", "các bon", "t300", "t700", "t800", "t1100", "t650",
             "as4", "im7", "hts40", "cfrp"],
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


HF_CALL_LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "hf_calls.log")


def _count_hf_call(provider):
    """One line per request sent to Hugging Face (credits are limited) -> logs/hf_calls.log."""
    try:
        os.makedirs(os.path.dirname(HF_CALL_LOG), exist_ok=True)
        with open(HF_CALL_LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{provider}\n")
    except OSError:
        pass


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
        _count_hf_call(provider)
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


_SKIP_UNTIL = {}  # backend -> time; after a failure in "auto" mode the backend is skipped for 5 minutes


def ask_llm(prompt, json_schema=None, backend=None):
    """Send a prompt to the chosen LLM backend (with automatic fallback in 'auto') and return its text."""
    global LAST_BACKEND
    order = backend_order(backend)
    errors = []
    for i, b in enumerate(order):
        if len(order) > 1 and i + 1 < len(order) and time.time() < _SKIP_UNTIL.get(b, 0):
            continue  # failed a moment ago: go straight to the next backend
        try:
            text = _ASK[b](prompt, json_schema)
            LAST_BACKEND = _NAME[b]()
            _SKIP_UNTIL.pop(b, None)
            return text
        except Exception as e:
            if len(order) > 1:
                _SKIP_UNTIL[b] = time.time() + 300
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
- "fibre_words": the words of the text that name the fibre or material, e.g. "Glass fibre / epoxy".
- "material_name": the specific material system (fibre grade / resin grade) copied exactly as written,
  e.g. "IM7/8552", "T300/5208", "Hexcel 8552 / IM7". Use "" if the text only gives a generic name such as
  "carbon/epoxy", "CFRP" or "glass fibre".
- "material": one of {materials}. Carbon or graphite fibre (T300, AS4, IM7, "sợi carbon"...) -> CFRP;
  glass fibre (E-glass, S-glass, fiberglass, "sợi thủy tinh") -> GFRP; aramid or Kevlar -> KEVLAR.
- "layup": the stacking sequence copied exactly as written, e.g. "[0/±45]s", "[0/90]2s", "[45/-45]".
  If the plies are listed one by one, write all their angles in order separated by "/", e.g. "0/90/90/0".
- "ply_thickness": thickness of ONE ply when the text gives it, otherwise value 0.
- "total_thickness": the total laminate thickness when the text gives it, otherwise value 0.
- "ply_thickness_list": only if the plies have DIFFERENT thicknesses: one entry per ply, same order as
  the layup. Otherwise [].
- "loads": one entry for EACH load written in the text, with the symbol used in the text:
  Nx, Ny, Nxy (force per unit length) or Mx, My, Mxy (moment per unit length).
  Example: "Nxy = 300 N/m" -> {{"name": "Nxy", "value": 300, "unit": "N/m"}};
           "My = 5 N.m/m" -> {{"name": "My", "value": 5, "unit": "N*m/m"}}.
  Do not add loads that are not written. Keep the sign (-1.5 stays -1.5).
  Loads may be described in words: "a tensile load of 1000 N/m along x" -> Nx = 1000;
  "a compressive force of 2 kN/m in the y direction" -> Ny = -2 kN/m; "shear force" -> Nxy;
  "twisting moment" -> Mxy. If the text does not say the direction of a load, do NOT guess: leave it out.
Write a decimal comma as a point (0,15 -> 0.15).
Unit names: length "m", "mm", "um" (= µm), "in"; force per length "N/m", "kN/m", "N/mm", "lbf/in";
moment per length "N*m/m", "N*mm/mm", "N*mm/m", "kN*m/m", "lbf*in/in" (N.m/m and N·m/m are "N*m/m").

Answer only with JSON.
"""

_NUM = r"[-+]?\d+(?:[.,]\d+)?"
_LAYUP_IN_TEXT = r"\[[^\[\]]+\](?:_?\d+)?(?:_?(?:sym(?:metric)?|[sSTt])(?![A-Za-z]))?"
_LOAD_SYMBOL = r"(?<![A-Za-z])([NM])\s*_?\{?\s*(xy|yx|x|y)\}?(?![A-Za-z])"


def _text_numbers(text):
    """All numbers written in the text (decimal comma understood), as positive floats."""
    nums = set()
    for tok in re.findall(_NUM, text):
        nums.add(abs(float(tok.replace(",", "."))))
        for part in re.split(",", tok):  # "0,45" could also be the list 0, 45
            nums.add(abs(float(part)))
    return nums


# how each unit is written in a text (the SI unit of each kind is always allowed)
_D = r"[·.*⋅]?\s*"
_PER_M = r"\s+per\s+met(?:er|re)s?\b"
UNIT_PATTERNS = {
    "mm": r"mm(?![a-z])", "um": r"µm|μm|\bum\b|micron|micromet", "in": r"\d\s*(?:in\b|inch)",
    "kN/m": rf"kN\s*/\s*m(?!m)|kilonewtons?{_PER_M}|kN{_PER_M}",
    "N/mm": r"(?<![kK])N\s*/\s*mm|(?<!kilo)newtons?\s+per\s+millimet(?:er|re)s?\b",
    "lbf/in": r"lbf?\s*/\s*in",
    "N/m": rf"(?<![kK])N\s*/\s*m(?!m)|(?<!kilo)newtons?{_PER_M}|(?<![kK])N{_PER_M}",
    "kN*m/m": rf"kN\s*{_D}m\s*/\s*m(?!m)", "N*mm/mm": rf"(?<![kK])N\s*{_D}mm\s*/\s*mm",
    "N*mm/m": rf"(?<![kK])N\s*{_D}mm\s*/\s*m(?!m)",
    "N*m/m": rf"(?<![kK])N\s*{_D}m\s*/\s*m(?!m)|newton[- ]?met(?:er|re)s?{_PER_M}",
    "lbf*in/in": rf"lbf?\s*{_D}-?\s*in\s*/\s*in",
}
_ALWAYS = {"m", "N/m", "N*m/m", "N"}


def _text_units(text):
    return _ALWAYS | {u for u, p in UNIT_PATTERNS.items() if re.search(p, text)}


def _grounded_si(si_value, nums, units, table):
    """True if the SI value can be made from a number AND a unit that are both written in the text
    (e.g. 5000 N/m <- '5' and 'kN/m'). Catches an LLM that converts the number but keeps the old unit."""
    v = abs(float(si_value))
    if v == 0:
        return True
    return any(abs(v - n * table[u]) <= 1e-6 * max(v, 1e-12) for n in nums for u in units if u in table)


def _loads_from_text(text):
    """Loads written explicitly as 'Nx = 5 kN/m', 'Mx=0,3 N.m/m' -> {name: SI value}. Only when the unit
    is clear; everything else is left to the LLM."""
    out = {}
    for m in re.finditer(_LOAD_SYMBOL + r"\s*(?:[=:]|\bof\b|\bis\b|là|bằng)\s*(" + _NUM + r")\s*([^\s,;)]*)", text):
        name = m.group(1) + m.group(2).replace("yx", "xy")
        value = float(m.group(3).replace(",", "."))
        unit_txt = m.group(4).rstrip(".")
        table = FORCE_UNITS if name.startswith("N") else MOMENT_UNITS
        unit = next((u for u in sorted(UNIT_PATTERNS, key=len, reverse=True)
                     if u in table and re.fullmatch(r"(?:\d\s*)?(?:" + UNIT_PATTERNS[u] + r")", unit_txt)), None)
        if unit is None and unit_txt in ("N/m", "N·m/m", "N.m/m", "N*m/m", "Nm/m"):
            unit = "N/m" if name.startswith("N") else "N*m/m"
        if value == 0:
            out.setdefault(name, 0.0)
        elif unit is not None:
            out.setdefault(name, value * table[unit])
    return out


_WORD_NUM = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
             "twelve": 12, "sixteen": 16, "hai": 2, "ba": 3, "bốn": 4, "năm": 5, "sáu": 6, "bảy": 7, "tám": 8}
_PLY_COUNT = r"(?<![\d.,])(\d+|" + "|".join(_WORD_NUM) + r")\s*[-‑ ]?\s*(?:plies|ply|lớp|layers?)(?!\w)"
TOTAL_WORDS = ["total", "tổng", "overall", "laminate thickness", "chiều dày tấm", "độ dày tấm", "bề dày tấm"]
PLY_WORDS = ["each", "per ply", "ply thickness", "ply:", "t_ply", "every ply", "mm plies", "µm plies", "um plies",
             "mỗi lớp", "dày mỗi", "chiều dày lớp", "độ dày lớp", "chiều dày mỗi"]


def _ply_count_in_text(text):
    """'8-ply', '3 plies', 'two plies', '4 lớp' -> that number (None if absent or contradictory)."""
    found = {int(m) if m.isdigit() else _WORD_NUM[m.lower()] for m in re.findall(_PLY_COUNT, text, flags=re.I)}
    return found.pop() if len(found) == 1 else None


def _material_from_text(text):
    tl = text.lower()
    found = [m for m, words in MATERIAL_KEYWORDS.items() if any(w in tl for w in words)]
    return found[0] if len(found) == 1 else None


class AmbiguousTextError(ValueError):
    """The problem text itself is ambiguous (e.g. a load without direction): asking the LLM again cannot help."""


_ASSIGN = r"\s*(?:[=:]|\bof\b|\bis\b|là|bằng)\s*"
_CLAUSE_SPLIT = re.compile(r"(?<!\d)[.;,](?!\d)|\band\b|\bvà\b|\bwith\b|\bplus\b")
LOAD_WORDS = (r"\bload|\bforce|\bmoment|\btension|\btensile|compress|\bshear|bending|twist|torsion|tải|lực|"
              r"mô[- ]?men|momen|kéo|nén|uốn|xoắn")
NO_LOAD = r"no load|unloaded|not loaded|zero load|không (?:chịu )?tải"
_LETTER = r"a-zà-ỹ"


def _clause(text, start, end):
    """The part of the sentence around text[start:end], cut at , ; . 'and' 'with' 'và'."""
    left = 0
    for m in _CLAUSE_SPLIT.finditer(text[:start]):
        left = m.end()
    m = _CLAUSE_SPLIT.search(text, end)
    return text[left:m.start() if m else len(text)]


def _load_quantities(text):
    """Every 'number + force or moment per length unit' in the text (also in words: '1500 newtons per metre')."""
    found = {}
    for u, pattern in UNIT_PATTERNS.items():
        if u not in FORCE_UNITS and u not in MOMENT_UNITS:
            continue
        kind, table = ("N", FORCE_UNITS) if u in FORCE_UNITS else ("M", MOMENT_UNITS)
        for m in re.finditer(r"(?<![\w.])(" + _NUM + r")\s*(?:" + pattern + r")", text):
            s = m.start(1)
            if s not in found or m.end() > found[s]["end"]:
                value = float(m.group(1).replace(",", "."))
                found[s] = {"start": s, "end": m.end(), "text": m.group(0).strip(), "value": value, "unit": u,
                            "kind": kind, "si": value * table[u]}
    return sorted(found.values(), key=lambda q: q["start"])


def _expected_keys(text, q):
    """Which load(s) a quantity of the text belongs to, from its own words. -> (set of keys or None, sign, clause).
    'Nx = Ny = 1.2 kN/m' -> {Nx, Ny}; 'a compressive force of 2 kN/m in the y direction' -> {Ny}, -1;
    'shear force of 500 N/m' -> {Nxy}; 'twisting moment' -> {Mxy}; 'load 1000 N/m' -> None (direction unknown)."""
    cl = _clause(text, q["start"], q["end"])
    chain = re.search(r"((?:" + _LOAD_SYMBOL + _ASSIGN + r")+)$", text[:q["start"]])
    syms = [a + b.replace("yx", "xy") for a, b in re.findall(_LOAD_SYMBOL, chain.group(1))] if chain else []
    if not syms:
        in_clause = {a + b.replace("yx", "xy") for a, b in re.findall(_LOAD_SYMBOL, cl)}
        syms = list(in_clause) if len(in_clause) == 1 else []
    syms = [s for s in syms if s[0] == q["kind"]]
    if syms:
        return set(syms), 1, cl
    low = cl.lower()
    sign = -1 if q["value"] > 0 and re.search(r"compress|nén", low) else 1
    x = re.search(rf"(?<![{_LETTER}])x(?![{_LETTER}])|\baxial|uniaxial|longitudinal|\b0\s*°\s*direction", low)
    y = re.search(rf"(?<![{_LETTER}])y(?![{_LETTER}])|\b90\s*°\s*direction", low)
    if q["kind"] == "N":
        key = "Nxy" if re.search(r"shear|cắt", low) else "Nx" if x and not y else "Ny" if y and not x else None
    elif re.search(r"twist|torsion|xoắn", low):
        key = "Mxy"
    else:
        key = None if "about" in low else "Mx" if x and not y else "My" if y and not x else None
    return ({key} if key else None), sign, cl


def _check_quantities(text, loads, warnings):
    """Every non-zero load written in the text must end up in exactly the load it belongs to.
    Loads with a clear direction are set from the text; a load without direction stops the agent."""
    qs = [q for q in _load_quantities(text) if q["si"] != 0]
    claimed, owner = {}, {}
    for q in qs:
        keys, sign, cl = _expected_keys(text, q)
        if keys is None:
            raise AmbiguousTextError(
                f"the text gives the load '{q['text']}' (in '{cl.strip()}') but not its direction (x, y, shear or "
                f"twisting) - please write it e.g. as 'Nx = {q['text']}'")
        want = sign * q["si"]
        for k in keys:
            if k in claimed and abs(claimed[k] - want) > 1e-9 * max(abs(want), 1e-12):
                raise AmbiguousTextError(f"the text gives two different values for {k}: {owner[k]} and '{q['text']}'")
            claimed[k], owner[k] = want, f"'{q['text']}'"
    for k, want in claimed.items():
        if abs(loads[k] - want) > 1e-9 * max(abs(want), 1e-12):
            warnings.append(f"LLM read {k} = {loads[k]:g}, the text gives {owner[k]} for {k} -> {k} = {want:g} (SI)")
            loads[k] = want
    for k in LOAD_KEYS:  # a value the LLM put in the wrong load
        if loads[k] != 0 and k not in claimed and any(abs(abs(loads[k]) - abs(q["si"])) <= 1e-9 * abs(q["si"])
                                                       for q in qs):
            warnings.append(f"LLM put {loads[k]:g} in {k}, but the text gives that value to another load -> {k} = 0")
            loads[k] = 0.0
    return qs


_LENGTH_WORDS = {"mm": 1e-3, "µm": 1e-6, "μm": 1e-6, "um": 1e-6, "micron": 1e-6, "microns": 1e-6, "m": 1.0,
                 "in": 0.0254, "inch": 0.0254, "inches": 0.0254}


def _unused_numbers(text, angles, thick, n, qs, name_text):
    """Numbers written in the text that the agent did not use (Vf, a forgotten load...). Warning only."""
    spans = [(m.start(), m.end()) for m in re.finditer(_LAYUP_IN_TEXT, text)]
    spans += [(q["start"], q["end"]) for q in qs]
    spans += [(m.start(), m.end()) for m in re.finditer(r"[\w-]+\s*/\s*[\w-]+", text)
              if re.search(r"[A-Za-z]", m.group())]  # material names such as IM7/8552, 5250-5 / T650
    spans += [(m.start(), m.end()) for m in re.finditer(_LOAD_SYMBOL + _ASSIGN + r"0+(?:[.,]0+)?(?!\d)", text)]
    abs_angles = {abs(a) for a in angles}
    sizes = {round(t, 12) for t in thick} | {round(sum(thick), 12)}
    unused = []
    for m in re.finditer(r"(?<![A-Za-z0-9_.,])[-+]?\d+(?:[.,]\d+)?(?!\d)", text):
        if any(a <= m.start() < b for a, b in spans):
            continue
        tok = m.group()
        v = abs(float(tok.replace(",", ".")))
        after, before = text[m.end():m.end() + 14], text[max(0, m.start() - 10):m.start()]
        if v == 0 or tok.lstrip("+-") in name_text:
            continue
        if re.match(r"\s*°", after) or (v in abs_angles and not re.match(r"\s*[a-zµμ]", after, re.I)):
            continue
        if re.match(r"\s*[-‑ ]?\s*(?:plies|ply|lớp|layers?)\b", after, re.I) and v == n:
            continue
        if re.search(r"(?:ply|lớp|layer)\s*$", before, re.I):
            continue
        lm = re.match(r"\s*(mm|µm|μm|um|microns?|m|inch(?:es)?|in)\b", after)
        if lm and any(abs(v * _LENGTH_WORDS[lm.group(1)] - s) <= 1e-9 for s in sizes):
            continue
        unused.append(tok)
    return unused


def _si(q, table, what):
    unit = str(q.get("unit", "")).strip()
    if unit not in table:
        raise ValueError(f"unknown unit '{unit}' for {what}")
    return float(q.get("value", 0) or 0) * table[unit]


def build_problem(raw, text=None):
    """Deterministic part of step 1: raw LLM JSON (values as written) -> CLTInput in SI units.
    If the original text is given, every LLM value is checked against it (grounding):
    numbers that are not written in the text are dropped, a [..] layup written in the text wins,
    the fibre class named in the text wins. Returns (CLTInput, warnings)."""
    warnings = []
    if text:
        text = numbers_from_words(text)[0]  # "two kN/m" -> "2 kN/m" so every number can be checked
    nums = _text_numbers(text) if text else None
    units = _text_units(text) if text else None

    # material group (CFRP / GFRP / KEVLAR) and, if named, the specific material system of the CSV
    material = raw.get("material")
    if text:
        m_text = _material_from_text(text)
        if m_text and m_text != material:
            warnings.append(f"LLM said material {material}, text names {m_text} -> using {m_text}")
            material = m_text
    material_name, material_note = "", ""
    if text:
        material_name, material_note = materials.resolve(raw.get("material_name", ""), text)
        group = materials.group_of(material_name) if material_name else None
        if group and group != material:
            warnings.append(f"{material_name} is {group}, not {material} -> using {group}")
            material = group

    # stacking sequence
    layup = raw.get("layup", "")
    try:
        angles = expand_layup(layup)
    except LayupError as e:
        angles, err = None, e
    if text:
        in_text = []
        for cand in re.findall(_LAYUP_IN_TEXT, text):
            try:
                plies = expand_layup(cand)
                if len(plies) >= 2:  # "[1]" is a citation, not a layup
                    in_text.append(plies)
            except LayupError:
                pass
        if in_text and all(a == in_text[0] for a in in_text) and angles != in_text[0]:
            warnings.append(f"LLM wrote layup '{layup}', the text has {re.findall(_LAYUP_IN_TEXT, text)[0]}"
                            " -> using the text")
            angles = in_text[0]
        elif not in_text and angles is not None and nums is not None:
            missing = sorted({a for a in angles if a != 0 and abs(a) not in nums})
            if missing:
                raise ValueError(f"the layup '{layup}' has angle(s) {missing} that are not written in the text")
    if angles is None:
        raise ValueError(f"cannot read the stacking sequence '{layup}': {err}")
    n = len(angles)
    from_text = bool(text) and bool(in_text)  # the [..] notation in the text decided the plies
    stated = _ply_count_in_text(text) if text else None
    if stated and stated != n:
        if from_text:
            warnings.append(f"the text says {stated} plies but its layup notation gives {n} -> using {n}")
        else:
            raise ValueError(f"the text says {stated} plies but the layup '{layup}' has {n} plies")

    # thickness: drop values that cannot be made from a number + unit written in the text
    def keep(q, what):
        if q and nums is not None and float(q.get("value", 0) or 0) > 0 and (
                q.get("unit") not in LENGTH_UNITS or
                not _grounded_si(_si(q, LENGTH_UNITS, what), nums, units, LENGTH_UNITS)):
            warnings.append(f"{what} {q.get('value')} {q.get('unit')} is not written in the text -> ignored")
            return {"value": 0, "unit": "mm"}
        return q or {}

    lst = [keep(q, "ply thickness") for q in raw.get("ply_thickness_list") or []]
    lst = [q for q in lst if float(q.get("value", 0) or 0) > 0]
    ply_t = keep(raw.get("ply_thickness"), "ply thickness")
    tot_t = keep(raw.get("total_thickness"), "total thickness")
    if lst and len(lst) != n and (len({(q["value"], q["unit"]) for q in lst}) > 1 or
                                  (not from_text and len(lst) >= 2)):
        raise ValueError(f"{len(lst)} ply thicknesses were given but the layup '{layup}' has {n} plies")
    # ply thickness and total thickness both given but they disagree: the words of the text decide
    if float(ply_t.get("value", 0) or 0) > 0 and float(tot_t.get("value", 0) or 0) > 0:
        ply_si, tot_si = _si(ply_t, LENGTH_UNITS, "ply thickness"), _si(tot_t, LENGTH_UNITS, "total thickness")
        if abs(ply_si * n - tot_si) > 0.01 * tot_si:
            tl = (text or "").lower()
            says_total, says_ply = any(w in tl for w in TOTAL_WORDS), any(w in tl for w in PLY_WORDS)
            if says_total and not says_ply:
                warnings.append(f"ply thickness x {n} != total thickness; the text speaks of a total -> using total")
                ply_t = {"value": 0, "unit": "mm"}
            elif says_ply and not says_total:
                warnings.append(f"ply thickness x {n} != total thickness; the text speaks of each ply -> using ply")
                tot_t = {"value": 0, "unit": "mm"}
            else:
                raise ValueError(f"ply thickness {ply_t.get('value')} {ply_t.get('unit')} x {n} plies does not "
                                 f"match total thickness {tot_t.get('value')} {tot_t.get('unit')}")
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

    # loads: list of {name, value, unit}; check symbol, unit kind and value against the text
    loads = {k: 0.0 for k in LOAD_KEYS}
    symbols_in_text = None
    if text:
        symbols_in_text = {(a + b.replace("yx", "xy")) for a, b in re.findall(_LOAD_SYMBOL, text)}
    for q in raw.get("loads") or []:
        k, v, unit = q.get("name"), float(q.get("value", 0) or 0), q.get("unit")
        if k not in loads or v == 0:
            continue
        table = FORCE_UNITS if k.startswith("N") else MOMENT_UNITS
        if unit not in table:
            warnings.append(f"{k} = {v:g} has unit '{unit}', which is not a "
                            f"{'force' if k.startswith('N') else 'moment'} per length -> ignored")
            continue
        if symbols_in_text and k not in symbols_in_text:
            warnings.append(f"{k} = {v:g} {unit}: the text has no {k} -> ignored")
            continue
        if nums is not None and not _grounded_si(v * table[unit], nums, units, table):
            warnings.append(f"{k} = {v:g} {unit} is not written in the text -> ignored")
            continue
        if loads[k] != 0 and loads[k] != v * table[unit]:
            warnings.append(f"{k} given twice by the LLM -> keeping the first value")
            continue
        loads[k] = v * table[unit]
    # loads written explicitly as "Nx = 5 kN/m" are read by Python too; the text wins over the LLM
    qs, explicit = [], {}
    if text:
        explicit = _loads_from_text(text)
        for k, si in explicit.items():
            if abs(loads[k] - si) > 1e-9 * max(abs(si), 1e-12):
                warnings.append(f"LLM read {k} = {loads[k]:g}, the text says {k} = {si:g} (SI) -> using the text")
                loads[k] = si
        # every load quantity of the text ("1000 N/m along x", "2 kN/m") must be in the right load
        qs = _check_quantities(text, loads, warnings)
    if all(v == 0 for v in loads.values()):
        low = (text or "").lower()
        if text and (re.search(LOAD_WORDS, low) or re.search(_LOAD_SYMBOL, text)):
            if re.search(NO_LOAD, low) or (explicit and all(v == 0 for v in explicit.values())):
                warnings.append("all loads are 0 (the text says so)")
            else:
                raise ValueError("the text speaks of a load, but every load read is 0")
        else:
            warnings.append("the text gives no load: all loads are 0")

    if text:
        unused = _unused_numbers(text, angles, thick, n, qs,
                                 f"{raw.get('material_name', '')} {material_name}")
        if unused:
            warnings.append(f"numbers in the text that the agent did not use: {unused} - check that none of "
                            "them is a load or a thickness")

    problem = CLTInput.model_validate({
        "material": material,
        "plies": [{"angle": a, "thickness": t} for a, t in zip(angles, thick)],
        "loads": loads,
        "material_name": material_name,
        "material_note": material_note,
    })
    return problem, warnings


def parse_input(user_text, backend=None):
    """LLM reads the text -> Python checks the answer against the text. If a check fails, the LLM gets
    one more try with the list of problems (self-correction); if it fails again, a clear error is raised."""
    global LAST_PARSE
    text, words = numbers_from_words(user_text.strip())
    for w, v in words:
        print(f"[llm.py] note: number written in words '{w}' read as {v:g}")
    base = PARSE_PROMPT.format(text=text, materials=", ".join(MATERIAL_DB))
    prompt = base
    t0 = time.time()
    attempts = []
    for attempt in (1, 2):
        raw = _extract_json(ask_llm(prompt, json_schema=EXTRACT_SCHEMA, backend=backend))
        attempts.append(raw)
        try:
            problem, warnings = build_problem(raw, text)
            break
        except AmbiguousTextError as e:  # the text itself is unclear: asking again cannot help
            LAST_PARSE = {"raw": raw, "attempts": attempts, "backend": LAST_BACKEND, "error": str(e)}
            raise ValueError(f"the problem text is ambiguous: {e}") from None
        except ValueError as e:
            if attempt == 2:
                LAST_PARSE = {"raw": raw, "attempts": attempts, "backend": LAST_BACKEND, "error": str(e)}
                raise ValueError(f"the LLM could not read the problem reliably: {e}") from None
            print(f"[llm.py] check failed ({e}) -> asking the LLM to correct its answer")
            prompt = (base + f"\nYour previous answer was:\n{json.dumps(raw, ensure_ascii=False)}\n"
                      f"It has this problem: {e}.\nRead the TEXT again and answer with the corrected JSON.")
    LAST_PARSE = {"raw": raw, "attempts": attempts, "backend": LAST_BACKEND,
                  "seconds": round(time.time() - t0, 2), "warnings": warnings}
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
