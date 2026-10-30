"""
design.py - design a composite laminate from a request in words (English or Vietnamese):
  (1) the LLM copies the numbers and units of the request (fixed JSON schema); Python reads the same values from the
      text, checks every LLM value against it (the text wins) and fills the defaults, printed as such;
  (2) ply properties: measured CSV values when one known material system is named, else the ML prediction for the
      group (with a warning: predicted properties have errors, the result is for reference only);
  (3) the optimiser (python/optimization): exact search (branch and bound with proven bounds) when it can finish,
      else GA + local search with a fixed seed -> "proven optimum" or "best design found";
  (4) the final design is checked again: strength in MATLAB clt_engine.m (must match Python), buckling against an
      independent polynomial Ritz solution, reserve factor of each criterion, and the smallest quasi-isotropic
      laminate that meets the same constraints (% fewer plies; no mass in kg: the data have no density);
  (5) the LLM explains the result; every number and the words next to it are checked (English and Vietnamese);
      one retry, else a pre-built explanation.
Supported: in-plane loads Nx, Ny, Nxy (moments are refused); objectives "fewest plies" (default) and "largest
safety margin for a given ply count"; plies 0, +45, -45, 90; symmetric and balanced laminates (the 10 % rule and the
limit of identical plies in a row can be changed); simply supported a x b plate. A shear load is checked in both
directions unless the text says that it acts in one direction only.

Run:  python design.py "Design the lightest IM7/8552 laminate for Nx = -50 kN/m" [--backend ollama] [--lang vi]
"""
import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

import llm
import materials
from numwords import convert as numbers_from_words

DEFAULTS = {"safety_factor": 1.5, "ply_thickness": 0.125e-3, "a": 0.5, "b": 0.5, "n_min": 8, "n_max": 64,
            "max_contiguous": 4, "min_fraction": 0.10}
RITZ_TERMS = 8           # size of the sine series (8 x 8 on a square plate), as in the Layer 1 study
EXACT_TIME_LIMIT = 30.0  # s for the exact search; the whole optimisation stays within about 60 s
BUCKLING_CHECK_TOL_PCT = 2.0   # sine series vs polynomial Ritz: <= 0.62 % on the verification plates (Layer 1, 4.0)
ML_WARNING = ("ply properties are ML predictions with an error: the result is for reference only / tính chất vật "
              "liệu là dự đoán, có sai số; kết quả chỉ mang tính tham khảo")
LAST_DESIGN = {}


class DesignRefusal(ValueError):
    """The request asks for something the design function does not support, or is unclear: say what and why."""


SUPPORTED = ("supported: in-plane loads Nx, Ny, Nxy; objective 'lightest' (fewest plies, default) or 'largest "
             "safety margin' for a given number of plies; plies 0, +45, -45, 90; symmetric, balanced laminates")


@dataclass
class DesignSpec:
    group: str                       # CFRP / GFRP / KEVLAR
    row: str                         # CSV material whose measured values are used ("" = ML prediction)
    loads: Dict[str, float]          # Nx, Ny, Nxy in N/m (tension +)
    safety_factor: float = 1.5
    ply_thickness: float = 0.125e-3  # m
    a: float = 0.5                   # m, along x
    b: float = 0.5                   # m, along y
    n_min: int = 8
    n_max: int = 64
    objective: str = "min_plies"     # or "max_margin" (n_min == n_max)
    shear_both: bool = False         # check +Nxy and -Nxy
    max_contiguous: Optional[int] = 4
    min_fraction: Optional[float] = 0.10
    material_note: str = ""
    defaults: List[str] = field(default_factory=list)   # values not given in the text (defaults used)
    notes: List[str] = field(default_factory=list)      # how the values were read, warnings


# ---------------------------------------------------------------------------------------------- step 1: reading
DESIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "fibre_words": {"type": "string"},
        "material_name": {"type": "string"},
        "material": {"type": "string", "enum": list(llm.MATERIAL_DB) + ["NONE"]},
        "loads": llm.EXTRACT_SCHEMA["properties"]["loads"],
        "safety_factor": {"type": "number"},
        "ply_thickness": llm._qty(llm.LENGTH_UNITS),
        "plate_a": llm._qty(llm.LENGTH_UNITS),
        "plate_b": llm._qty(llm.LENGTH_UNITS),
        "ply_count": {"type": "integer"},
        "ply_count_min": {"type": "integer"},
        "ply_count_max": {"type": "integer"},
        "objective_words": {"type": "string"},
        "shear_direction": {"type": "string", "enum": ["one", "both", ""]},
        "angles": {"type": "array", "items": {"type": "number"}},
    },
    "required": ["fibre_words", "material_name", "material", "loads", "safety_factor", "ply_thickness", "plate_a",
                 "plate_b", "ply_count", "ply_count_min", "ply_count_max", "objective_words", "shear_direction",
                 "angles"],
}

DESIGN_PROMPT = """
You copy the data of a composite laminate DESIGN request into JSON. The program chooses the stacking sequence
itself; you only copy what the text says. Copy numbers and units EXACTLY as written; do not convert units.

TEXT:
{text}

Fields:
- "fibre_words": the words of the text that name the fibre or material ("" if none).
- "material_name": the specific material system copied exactly as written, e.g. "IM7/8552", "AS4/8552"; "" if the
  text only gives a generic name such as "carbon/epoxy" or "glass fibre".
- "material": CFRP (carbon or graphite fibre), GFRP (glass fibre), KEVLAR (aramid, Kevlar), or NONE if the text
  names no fibre or material.
- "loads": one entry for EACH load written in the text: Nx, Ny, Nxy (force per unit length) or Mx, My, Mxy (moment
  per unit length), with the value and unit as written. A compressive load ("compression", "compressive", "nén") is
  negative: "a compressive load of 20 kN/m in the x direction" -> {{"name": "Nx", "value": -20, "unit": "kN/m"}}.
  "shear force" or "lực cắt" -> Nxy. Do not add loads that are not written; if the direction of a load is not
  written, leave it out.
- "safety_factor": the safety factor if the text gives one, else 0.
- "ply_thickness": the thickness of one ply if written, else value 0.
- "plate_a", "plate_b": plate length along x and width along y if written (e.g. "0.6 m x 0.4 m"), else value 0.
- "ply_count": the exact number of plies if the text fixes it ("a 24-ply laminate"), else 0.
- "ply_count_min", "ply_count_max": limits of the number of plies if written ("between 16 and 40 plies",
  "at most 24 plies"), else 0.
- "objective_words": the words of the text that say what is to be optimised, e.g. "lightest", "largest safety
  margin", "nhẹ nhất", "bền nhất"; "" if none.
- "shear_direction": "one" if the text says the shear acts in one direction only, "both" if it says the shear may
  reverse, "" otherwise.
- "angles": the ply angles the text allows, as numbers (e.g. [0, 45, -45, 90]); [] if the text does not list them.
Write a decimal comma as a point (0,15 -> 0.15). Unit names: length "m", "mm", "um", "in"; force per length "N/m",
"kN/m", "N/mm", "lbf/in"; moment per length "N*m/m", "N*mm/mm", "N*mm/m", "kN*m/m", "lbf*in/in".

Answer only with JSON.
"""

_N = r"(\d+(?:[.,]\d+)?)"
_LEN = {"mm": 1e-3, "cm": 1e-2, "m": 1.0, "µm": 1e-6, "μm": 1e-6, "um": 1e-6, "in": 0.0254}
PLY = r"(?:plies|ply|lớp|layers?)"
IN_A_ROW = (r"\s*(?:(?:of\s+the\s+)?same\s+(?:angle|orientation|direction)\s*)?(?:cùng\s+góc\s*)?"
            r"(?:in\s+a\s+row|contiguous|consecutive|liền\s+nhau|liên\s+tiếp)")
SF_RE = r"(?:safety\s+factor|factor\s+of\s+safety|\bFoS\b|\bSF\b|hệ\s+số\s+an\s+toàn)\s*(?:of|=|:|is|là|bằng)?\s*" + _N
PLY_T_RES = [
    _N + r"\s*(mm|µm|μm|um|in)\s*(?:thick\s+)?(?:plies|ply)\b",
    r"(?:ply\s+thickness|thickness\s+of\s+(?:each|one|a)\s+ply|t_?ply|each\s+ply|per\s+ply|mỗi\s+lớp(?:\s+dày)?|"
    r"(?:độ|chiều)\s+dày\s+(?:mỗi\s+)?lớp|dày\s+mỗi\s+lớp)\s*(?:is|of|=|:|là|bằng)?\s*" + _N + r"\s*(mm|µm|μm|um|in)\b",
    _N + r"\s*(mm|µm|μm|um|in)\s*(?:per\s+ply|each|mỗi\s+lớp)",
]
PLATE_RES = [
    _N + r"\s*(mm|cm|m)?\s*[x×*]\s*" + _N + r"\s*(mm|cm|m)\b",
    r"\ba\s*=\s*" + _N + r"\s*(mm|cm|m)\b[^.;]*?\bb\s*=\s*" + _N + r"\s*(mm|cm|m)\b",
]
RANGE_RE = r"(?:between|from|từ)\s*(\d+)\s*(?:and|to|đến|tới|-|–)\s*(\d+)\s*" + PLY
MAX_RE = (r"(?:at\s+most|up\s+to|no\s+more\s+than|not\s+more\s+than|maximum\s+of|maximum|max\.?|tối\s+đa|"
          r"không\s+quá|nhiều\s+nhất)\s*(\d+)\s*" + PLY + r"(?!" + IN_A_ROW + r")")
MIN_RE = (r"(?:at\s+least|no\s+fewer\s+than|not\s+fewer\s+than|minimum\s+of|minimum|tối\s+thiểu|ít\s+nhất)\s*(\d+)"
          r"\s*" + PLY + r"(?!" + IN_A_ROW + r")")
CONTIG_RE = (r"(?:no\s+more\s+than|not\s+more\s+than|at\s+most|maximum\s+of|max\.?|tối\s+đa|không\s+quá)\s*(\d+)\s*"
             r"(?:identical\s+)?" + PLY + IN_A_ROW)
EXACT_RE = r"(?<![\d.,])(\d+)\s*[-‑ ]?\s*" + PLY + r"(?!\w)"
MINFRAC_RE = (r"(?:at\s+least|ít\s+nhất|tối\s+thiểu)\s*" + _N + r"\s*%\s*(?:of\s+the\s+plies\s*)?(?:in|per|for|ở|cho)?"
              r"\s*(?:each|every|mỗi)")
NO_CONTIG = r"no\s+(?:limit|restriction)\s+on\s+(?:identical|contiguous|consecutive)\s+plies|without\s+the\s+contiguity"
NO_10PCT = r"without\s+the\s+10\s*%\s*rule|no\s+10\s*%\s*rule|không\s+cần\s+(?:luật\s+)?10\s*%"
UNSUPPORTED_RULES = (r"\b(?:non-?symmetric|unsymmetric(?:al)?|asymmetric|unbalanced)\b|không\s+đối\s+xứng|"
                     r"không\s+cân\s+bằng|without\s+(?:the\s+)?(?:symmetry|balance)")
MIN_PLIES_WORDS = (r"lightest|fewest\s+plies|minimum\s+(?:number\s+of\s+)?plies|minimum\s+(?:weight|mass|thickness)|"
                   r"minimi[sz]e\s+(?:the\s+)?(?:weight|mass|thickness|number\s+of\s+plies)|thinnest|nhẹ\s+nhất|"
                   r"ít\s+lớp\s+nhất|mỏng\s+nhất|khối\s+lượng\s+nhỏ\s+nhất")
MAX_MARGIN_WORDS = (r"strongest|(?:largest|highest|maximum|max)\s+(?:safety\s+)?margin|"
                    r"maximi[sz]e\s+(?:the\s+)?(?:safety\s+)?margin|(?:largest|highest|maximum)\s+(?:reserve|safety)"
                    r"\s+factor|bền\s+nhất|biên\s+an\s+toàn\s+lớn\s+nhất|hệ\s+số\s+an\s+toàn\s+lớn\s+nhất")
OTHER_OBJECTIVE = (r"stiffest|(?:maximum|highest|max)\s+stiffness|maximi[sz]e\s+(?:the\s+)?(?:stiffness|buckling\s+load|"
                   r"(?:natural\s+)?frequency)|cheapest|(?:minimum|lowest)\s+(?:cost|deflection|strain)|"
                   r"minimi[sz]e\s+(?:the\s+)?(?:cost|deflection|strain)|cứng\s+nhất|rẻ\s+nhất|độ\s+cứng\s+lớn\s+nhất|"
                   r"tần\s+số")
ONE_DIRECTION = (r"one\s+direction\s+only|only\s+(?:in\s+)?one\s+direction|in\s+one\s+direction|always\s+(?:acts?\s+)?"
                 r"(?:in\s+)?(?:the\s+)?(?:same|positive|negative)\s+(?:direction|sign)|(?:does|will)\s+not\s+reverse|"
                 r"never\s+reverses|always\s+positive|chỉ\s+(?:theo\s+)?một\s+chiều|không\s+đổi\s+chiều|"
                 r"luôn\s+(?:cùng|một)\s+chiều|luôn\s+dương")
BOTH_DIRECTIONS = (r"(?:may|can|could|might)\s+reverse|both\s+directions|either\s+direction|reversible|reversing|"
                   r"đổi\s+chiều|cả\s+hai\s+chiều")
ANGLE_MENTION = (r"(?:±|\+/-|\+-)\s*(\d+(?:[.,]\d+)?)|(?<![\w.])(-?\d+(?:[.,]\d+)?)\s*(?:(?:°|º)(?!\s*[CF]\b)|"
                 r"deg\b|degrees?\b(?!\s*(?:celsius|fahrenheit))|độ\b(?!\s*c\b))")


def _f(s):
    return float(s.replace(",", "."))


def _first(patterns, text):
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if m:
            return m
    return None


def read_text_values(text):
    """Values that Python reads directly from the text (None = not written); out["spans"] = the parts of the text
    that were read (to report the numbers that nothing used)."""
    out, spans = {}, []

    def take(m):
        if m:
            spans.append(m.span())
        return m

    m = take(re.search(SF_RE, text, flags=re.IGNORECASE))
    out["safety_factor"] = _f(m.group(1)) if m else None
    m = take(_first(PLY_T_RES, text))
    out["ply_thickness"] = _f(m.group(1)) * _LEN[m.group(2)] if m else None
    out["plate"] = None
    for p in PLATE_RES:
        m = re.search(p, text, flags=re.IGNORECASE)
        if m:
            u1 = m.group(2) or m.group(4)
            a, b = _f(m.group(1)) * _LEN[u1], _f(m.group(3)) * _LEN[m.group(4)]
            if a >= 0.05 and b >= 0.05:   # plate sizes, not "8 x 0.125 mm"
                out["plate"] = (a, b)
                take(m)
                break
    used = []
    m = take(re.search(CONTIG_RE, text, flags=re.IGNORECASE))
    out["max_contiguous"] = int(m.group(1)) if m else None
    if m:
        used.append(m.span())
    out["no_contiguity"] = bool(take(re.search(NO_CONTIG, text, flags=re.IGNORECASE)))
    m = take(re.search(MINFRAC_RE, text, flags=re.IGNORECASE))
    out["min_fraction"] = _f(m.group(1)) / 100.0 if m else None
    out["no_10pct"] = bool(take(re.search(NO_10PCT, text, flags=re.IGNORECASE)))
    out["n_range"] = None
    m = take(re.search(RANGE_RE, text, flags=re.IGNORECASE))
    if m:
        out["n_range"] = (int(m.group(1)), int(m.group(2)))
        used.append(m.span())
    m = take(re.search(MAX_RE, text, flags=re.IGNORECASE))
    out["n_max"] = int(m.group(1)) if m else None
    if m:
        used.append(m.span())
    m = take(re.search(MIN_RE, text, flags=re.IGNORECASE))
    out["n_min"] = int(m.group(1)) if m else None
    if m:
        used.append(m.span())
    exact = set()
    for x in re.finditer(EXACT_RE, text, flags=re.IGNORECASE):
        if not any(a <= x.start() < b for a, b in used) and not re.match(IN_A_ROW, text[x.end():], flags=re.I):
            exact.add(int(x.group(1)))
            spans.append(x.span())
    out["n_exact"] = exact
    low = text.lower()
    out["objective_other"] = [x.group(0) for x in re.finditer(OTHER_OBJECTIVE, low)]
    out["objective_min"] = [x.group(0) for x in re.finditer(MIN_PLIES_WORDS, low)]
    out["objective_max"] = [x.group(0) for x in re.finditer(MAX_MARGIN_WORDS, low)]
    out["one_direction"] = bool(re.search(ONE_DIRECTION, low))
    out["both_directions"] = bool(re.search(BOTH_DIRECTIONS, low)) and not out["one_direction"]
    out["unsupported_rules"] = [x.group(0) for x in re.finditer(UNSUPPORTED_RULES, low)]
    angles = set()
    for x in re.finditer(ANGLE_MENTION, text):
        spans.append(x.span())
        if re.match(r"\s*(?:direction|axis|phương|hướng)", text[x.end():], flags=re.IGNORECASE):
            continue   # "the 0° direction" is a load direction, not a ply angle
        angles.add(abs(_f(x.group(1) or x.group(2))))
    out["angles"] = angles
    out["spans"] = spans
    return out


def _unused_numbers(text, spans):
    """Numbers of the text that no reader used (a forgotten load, Vf...): reported as a note."""
    spans = list(spans)
    spans += [(q["start"], q["end"]) for q in llm._load_quantities(text)]
    spans += [m.span() for m in re.finditer(llm._LOAD_SYMBOL + llm._ASSIGN + r"[-+]?\d+(?:[.,]\d+)?", text)]
    spans += [m.span() for m in re.finditer(r"[\w-]+(?:\s+\d+)?\s*/\s*[\w-]+", text) if re.search(r"[A-Za-z]",
                                                                                               m.group())]
    out = []
    for m in re.finditer(r"(?<![A-Za-z0-9_.,])[-+]?\d+(?:[.,]\d+)?(?!\d)", text):
        if not any(a <= m.start() < b for a, b in spans) and float(m.group().replace(",", ".")) != 0:
            out.append(m.group())
    return out


def _grounded_number(v, nums, tol=1e-9):
    return any(abs(abs(float(v)) - n) <= tol * max(1.0, n) for n in nums)


def build_spec(raw, text):
    """Raw LLM answer + the text -> DesignSpec (SI). Python values from the text win; LLM values are used only if
    they are written in the text. Unsupported or unclear requests raise DesignRefusal (or AmbiguousTextError)."""
    text = numbers_from_words(text)[0]
    nums, units = llm._text_numbers(text), llm._text_units(text)
    notes, defaults = [], []
    tv = read_text_values(text)

    # --- material: a named CSV material (measured values) or the fibre group (ML prediction)
    row, note = materials.resolve(raw.get("material_name", ""), text)
    group_text = llm._material_from_text(text)
    if row:
        group = materials.group_of(row)
        if group is None:
            raise DesignRefusal(f"{row} is not a CFRP, GFRP or Kevlar material; the ML fallback cannot be used")
    elif group_text:
        group = group_text
        if raw.get("material") not in (group_text, None):
            notes.append(f"LLM said material {raw.get('material')}, the text names {group_text} -> {group_text}")
    else:
        raise DesignRefusal("the text names no material or fibre type (e.g. 'IM7/8552', 'carbon/epoxy', "
                            "'glass/epoxy', 'Kevlar/epoxy'); the program does not guess it")

    # --- loads: the same checks as the analysis agent; in-plane loads only
    warn = []
    loads, _ = llm.read_loads(raw.get("loads"), text, nums, units, warn)
    notes += warn
    moments = {k: v for k, v in loads.items() if k.startswith("M") and v != 0}
    if moments:
        raise DesignRefusal(f"the request has moment(s) {', '.join(moments)}; the optimisation handles in-plane "
                            "loads Nx, Ny, Nxy only (" + SUPPORTED + ")")
    in_plane = {k: loads[k] for k in ("Nx", "Ny", "Nxy")}
    if all(v == 0 for v in in_plane.values()):
        raise DesignRefusal("no in-plane load (Nx, Ny, Nxy) is given; a design needs the loads")

    # --- what is not supported
    if tv["unsupported_rules"]:
        raise DesignRefusal(f"'{tv['unsupported_rules'][0]}': only symmetric, balanced laminates are designed "
                            "(the exact search and the buckling model assume them)")
    bad_angles = sorted(a for a in tv["angles"] if a not in (0.0, 45.0, 90.0))
    llm_angles = {abs(float(a)) for a in raw.get("angles") or []}
    if bad_angles:
        raise DesignRefusal(f"ply angle(s) {bad_angles} deg: only 0, +45, -45 and 90 degree plies are supported")
    if tv["angles"] and tv["angles"] != {0.0, 45.0, 90.0}:
        raise DesignRefusal(f"the text allows only the angles {sorted(tv['angles'])}; the design uses 0, +45, -45 "
                            "and 90 together (each direction >= 10 % of the plies)")
    if llm_angles - {0.0, 45.0, 90.0} and not tv["angles"]:
        notes.append(f"LLM listed angles {sorted(llm_angles)} that are not written as angles in the text -> ignored")
    if not tv["angles"]:
        defaults.append("ply angles 0, +45, -45, 90")

    # --- objective and ply count
    if tv["objective_other"]:
        raise DesignRefusal(f"objective '{tv['objective_other'][0]}' is not supported; " + SUPPORTED)
    n_min, n_max = DEFAULTS["n_min"], DEFAULTS["n_max"]
    exact = set(tv["n_exact"])
    python_counts = bool(exact or tv["n_range"] or tv["n_min"] or tv["n_max"])
    llm_n = int(raw.get("ply_count") or 0)
    if python_counts and llm_n and llm_n not in exact:
        notes.append(f"LLM read a fixed ply count {llm_n}, but the text gives a limit of the ply count, not a fixed "
                     "number -> using the text")
    if not python_counts and int(raw.get("ply_count") or 0) > 0:
        n = int(raw["ply_count"])
        if _grounded_number(n, nums) and re.search(PLY, text, flags=re.IGNORECASE):
            exact = {n}
            notes.append(f"ply count {n} read by the LLM (written in the text)")
    if len(exact) > 1:
        raise DesignRefusal(f"the text gives several ply counts {sorted(exact)}; give one, or a range "
                            "('between 16 and 40 plies')")
    if exact:
        n_min = n_max = exact.pop()
        if tv["objective_min"]:
            raise DesignRefusal(f"'{tv['objective_min'][0]}' and a fixed number of plies ({n_min}) contradict each "
                                "other: with a fixed ply count the objective is the largest safety margin")
        objective = "max_margin"
    else:
        if tv["objective_max"]:
            raise DesignRefusal(f"'{tv['objective_max'][0]}' needs a fixed number of plies (e.g. 'a 24-ply "
                                "laminate'); without it the objective is the lightest laminate")
        objective = "min_plies"
        if not tv["objective_min"]:
            defaults.append("objective: lightest laminate (fewest plies)")
        if tv["n_range"]:
            n_min, n_max = tv["n_range"]
        else:
            if tv["n_min"]:
                n_min = tv["n_min"]
            if tv["n_max"]:
                n_max = tv["n_max"]
            for key, val in (("ply_count_min", tv["n_min"]), ("ply_count_max", tv["n_max"])):
                v = int(raw.get(key) or 0)
                if v and not python_counts and _grounded_number(v, nums):
                    if key == "ply_count_min":
                        n_min = v
                    else:
                        n_max = v
                    notes.append(f"{key.replace('_', ' ')} {v} read by the LLM (written in the text)")
        if (n_min, n_max) == (DEFAULTS["n_min"], DEFAULTS["n_max"]):
            defaults.append("ply count 8-64")
    if n_min > n_max:
        raise DesignRefusal(f"ply count range {n_min}-{n_max} is empty")
    if n_max > 64:
        raise DesignRefusal(f"at most 64 plies are supported (the text asks for up to {n_max})")
    if objective == "max_margin" and n_min % 2:
        raise DesignRefusal(f"{n_min} plies: a symmetric laminate has an even number of plies")

    # --- safety factor, ply thickness, plate: text first, else a grounded LLM value, else the default
    def pick(name, text_val, llm_val, default, show, grounded, plausible):
        if text_val is not None:
            if llm_val and abs(llm_val - text_val) > 1e-9 * abs(text_val):
                notes.append(f"LLM read {name} = {show(llm_val)}, the text says {show(text_val)} -> using the text")
            return text_val
        if llm_val and grounded and plausible(llm_val):
            notes.append(f"{name} {show(llm_val)} read by the LLM (written in the text)")
            return llm_val
        if llm_val and not grounded:
            notes.append(f"LLM gave {name} {show(llm_val)}, which is not written in the text -> ignored")
        elif llm_val:     # e.g. the plate size "0,5 m" copied as the ply thickness
            notes.append(f"LLM gave {name} {show(llm_val)}, which is not a plausible {name} -> ignored")
        defaults.append(f"{name} {show(default)}")
        return default

    sf_llm = float(raw.get("safety_factor") or 0)
    sf = pick("safety factor", tv["safety_factor"], sf_llm, DEFAULTS["safety_factor"], lambda v: f"{v:g}",
              _grounded_number(sf_llm, nums), lambda v: 1.0 <= v <= 5.0)

    def length(q):
        try:
            return llm._si(q, llm.LENGTH_UNITS, "length") if q and float(q.get("value", 0) or 0) > 0 else 0.0
        except ValueError:
            return 0.0

    t_llm = length(raw.get("ply_thickness"))
    t = pick("ply thickness", tv["ply_thickness"], t_llm, DEFAULTS["ply_thickness"], lambda v: f"{v * 1e3:g} mm",
             bool(t_llm) and llm._grounded_si(t_llm, nums, units, llm.LENGTH_UNITS), lambda v: 0.02e-3 <= v <= 1e-3)
    a_llm, b_llm = length(raw.get("plate_a")), length(raw.get("plate_b"))
    pa, pb = tv["plate"] if tv["plate"] else (None, None)
    ground = lambda v: bool(v) and llm._grounded_si(v, nums, units, {"m": 1.0, "mm": 1e-3})
    plate_ok = lambda v: 0.05 <= v <= 5.0
    a = pick("plate length a", pa, a_llm, DEFAULTS["a"], lambda v: f"{v:g} m", ground(a_llm), plate_ok)
    b = pick("plate width b", pb, b_llm, DEFAULTS["b"], lambda v: f"{v:g} m", ground(b_llm), plate_ok)
    if not (1.0 <= sf <= 5.0):
        raise DesignRefusal(f"safety factor {sf:g}: expected a value between 1 and 5")
    if not (0.02e-3 <= t <= 1.0e-3):
        raise DesignRefusal(f"ply thickness {t * 1e3:g} mm is outside 0.02-1 mm")
    if not (0.05 <= a <= 5.0 and 0.05 <= b <= 5.0):
        raise DesignRefusal(f"plate {a:g} m x {b:g} m is outside 0.05-5 m")

    # --- design rules (symmetric and balanced always)
    max_contig, min_frac = DEFAULTS["max_contiguous"], DEFAULTS["min_fraction"]
    if tv["no_contiguity"]:
        max_contig = None
    elif tv["max_contiguous"]:
        max_contig = tv["max_contiguous"]
        if max_contig < 2:
            raise DesignRefusal("a symmetric laminate needs at least 2 identical plies in a row at the mid-plane")
    if tv["no_10pct"]:
        min_frac = None
    elif tv["min_fraction"] is not None:
        min_frac = tv["min_fraction"]
    if max_contig == 4 and min_frac == 0.10:
        defaults.append("design rules: symmetric, balanced, >= 10 % of the plies in each direction, <= 4 identical "
                        "plies in a row")

    # --- shear direction
    both = False
    if in_plane["Nxy"] != 0:
        if tv["one_direction"]:
            notes.append("the text says the shear acts in one direction only -> only the given sign of Nxy is checked")
        else:
            both = True
            if not tv["both_directions"]:
                defaults.append("shear checked in both directions (+Nxy and -Nxy): the text does not say that the "
                                "shear acts in one direction only")
            if raw.get("shear_direction") == "one":
                notes.append("the LLM said 'one direction', but the text does not say so -> both directions")
    unused = _unused_numbers(text, tv["spans"])
    if unused:
        notes.append(f"numbers in the text that the program did not use: {unused} - check that none of them is a "
                     "load or a requirement")
    return DesignSpec(group=group, row=row, loads=in_plane, safety_factor=sf, ply_thickness=t, a=a, b=b,
                      n_min=n_min, n_max=n_max, objective=objective, shear_both=both, max_contiguous=max_contig,
                      min_fraction=min_frac, material_note=note, defaults=defaults, notes=notes)


def parse_design(user_text, backend=None):
    """LLM copies the request -> Python checks it against the text (one retry when a check fails; requests that
    are not supported or unclear are refused at once, asking again cannot help)."""
    global LAST_DESIGN
    text, words = numbers_from_words(user_text.strip())
    base = DESIGN_PROMPT.format(text=text)
    prompt, attempts = base, []
    for attempt in (1, 2):
        raw = llm._extract_json(llm.ask_llm(prompt, json_schema=DESIGN_SCHEMA, backend=backend))
        attempts.append(raw)
        try:
            spec = build_spec(raw, text)
            break
        except (DesignRefusal, llm.AmbiguousTextError) as e:
            LAST_DESIGN = {"raw": raw, "attempts": attempts, "backend": llm.LAST_BACKEND, "refused": str(e)}
            if isinstance(e, llm.AmbiguousTextError):
                raise DesignRefusal(f"the request is ambiguous: {e}") from None
            raise
        except ValueError as e:
            if attempt == 2:
                LAST_DESIGN = {"raw": raw, "attempts": attempts, "backend": llm.LAST_BACKEND, "error": str(e)}
                raise DesignRefusal(f"the LLM could not read the request reliably: {e}") from None
            print(f"[design.py] check failed ({e}) -> asking the LLM to correct its answer")
            prompt = (base + f"\nYour previous answer was:\n{json.dumps(raw, ensure_ascii=False)}\n"
                      f"It has this problem: {e}.\nRead the TEXT again and answer with the corrected JSON.")
    for w, v in words:
        spec.notes.insert(0, f"number written in words '{w}' read as {v:g}")
    LAST_DESIGN = {"raw": raw, "attempts": attempts, "backend": llm.LAST_BACKEND, "spec": asdict(spec)}
    return spec


# ------------------------------------------------------------------------------- step 2-4: optimise and check
def material_of(spec):
    from ml import predict_material
    from optimization.material import KEYS, Material, get_material
    if spec.row:
        return get_material(spec.row, spec.group, verbose=False)
    props = predict_material(spec.group)
    return Material(**{k: float(props[k]) for k in KEYS}, name=f"{spec.group} (ML)",
                    source=f"ML prediction (group {spec.group})", warnings=(ML_WARNING,))


def problem_of(spec, material=None):
    """The optimisation problem of a specification (same parameters as a direct optimize(...) call)."""
    from optimization.api import make_problem
    from optimization.evaluate import Plate
    from optimization.rules import Rules
    rules = Rules(n_min=spec.n_min, n_max=spec.n_max, max_contiguous=spec.max_contiguous,
                  min_fraction=spec.min_fraction)
    return make_problem(spec.loads, material=material or material_of(spec), rules=rules,
                        safety_factor=spec.safety_factor, plate=Plate(spec.a, spec.b),
                        ply_thickness=spec.ply_thickness, ritz_terms=RITZ_TERMS, shear_both_signs=spec.shear_both)


def _share_matlab_engine():
    """The optimiser's MATLAB check uses the agent's MATLAB session (one engine per process)."""
    import matlab_clt
    from optimization import matlab_check
    matlab_check._eng = matlab_clt._get_engine()


def counts_per_angle(full):
    return {a: int(sum(1 for x in full if x == c)) for c, a in ((0, "0"), (1, "+45"), (2, "-45"), (3, "90"))}


def solve(spec, check_matlab=True):
    """Optimise and check one specification -> dict with the design, its reserve factors and the checks."""
    import numpy as np
    from optimization import buckling
    from optimization.api import design_search, quasi_isotropic
    from optimization.evaluate import analyze_design
    from optimization.rules import ANGLES, check_rules, notation
    t0 = time.time()
    mat = material_of(spec)
    p = problem_of(spec, mat)
    search = design_search(p, objective=spec.objective, time_limit=EXACT_TIME_LIMIT)
    full = search["full"]
    det = analyze_design(p, full)
    feasible = det["margin"] >= p.safety_factor
    out = {"spec": asdict(spec), "material": mat.to_dict(), "search": search, "full": full,
           "notation": notation(full, True), "n_plies": len(full), "counts": counts_per_angle(full),
           "thickness_mm": len(full) * spec.ply_thickness * 1e3, "rf": det["rf"], "margin": det["margin"],
           "feasible": feasible, "governing": det["governing"], "critical_ply": det["critical_ply"],
           "critical_angle": det["critical_angle"], "governing_shear_sign": det.get("governing_shear_sign"),
           "D16_over_D11": det["D16_over_D11"], "rules_ok": all(check_rules(full, p.rules).values()),
           "search_time_s": search["time_s"]}
    if not feasible:
        out["failing"] = [c for c, v in det["rf"].items() if v < p.safety_factor]
    # buckling: Ritz (sine series) vs the independent polynomial Ritz solution, each shear direction
    D = det["ABD"][3:, 3:]
    bk = []
    if "buckling" in det["rf"] and np.isfinite(det["rf"]["buckling"]):
        for Nx, Ny, Nxy in p.load_cases():
            lam_s = float(buckling.ritz_full(D, Nx, Ny, Nxy, spec.a, spec.b, *buckling.terms_for(RITZ_TERMS, spec.a,
                                                                                                 spec.b))[0])
            conv = buckling.converge(D, Nx, Ny, Nxy, spec.a, spec.b, start=6, step=2, tol=0.005)
            lam_p = buckling.ritz_polynomial(D, Nx, Ny, Nxy, spec.a, spec.b, p=12)
            lam = min(lam_s, conv["lambda"])
            bk.append({"Nxy": Nxy, "lambda_sine": lam, "lambda_polynomial": lam_p,
                       "difference_pct": 100.0 * (lam - lam_p) / lam_p if np.isfinite(lam_p) else None,
                       "converged_terms": (conv["M"], conv["N"])})
    out["buckling_check"] = bk
    # strength (and buckling from the MATLAB D matrix) recomputed in MATLAB
    out["matlab"] = None
    if check_matlab:
        try:
            _share_matlab_engine()
            from optimization.matlab_check import verify_design
            v = verify_design(p, full, det)
            out["matlab"] = {"pass": v["pass"], "e_rf": v["e_rf"], "rf_matlab": v["rf_matlab"],
                             "e_clt": max(v["clt"]["e_ABD"], v["clt"]["e_stress"], v["clt"]["e_FI"])}
        except Exception as e:
            out["matlab"] = {"pass": None, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    qi = quasi_isotropic(p, n_min=spec.n_min)       # same constraints, including the smallest ply count
    out["quasi_isotropic"] = {"n": qi["n"], "margin": qi["margin"], "found": qi["found"],
                              "notation": qi.get("notation")}
    out["reduction_pct"] = (100.0 * (qi["n"] - len(full)) / qi["n"]) if (qi["found"] and feasible) else None
    out["time_s"] = time.time() - t0
    return out


# ---------------------------------------------------------------------------------------- step 5: explanation
CRIT_NAME = {"max_stress": "Max Stress", "tsai_wu": "Tsai-Wu", "buckling": "buckling"}
CRIT_VI = {"max_stress": "Max Stress", "tsai_wu": "Tsai-Wu", "buckling": "mất ổn định"}


def status_text(r, lang="en"):
    s = r["search"]
    if s["proven"] and r["spec"]["objective"] == "max_margin":
        n = r["n_plies"]
        return (f"proven largest safety margin for {n} plies (exact search)" if lang == "en" else
                f"biên an toàn lớn nhất đã chứng minh với {n} lớp (tìm kiếm chính xác)")
    if s["proven"]:
        if s["status"] == "optimal":
            return "proven optimum (exact search)" if lang == "en" else "tối ưu đã chứng minh (tìm kiếm chính xác)"
        return ("proven infeasible within the ply range (exact search); shown: the design with the largest margin"
                if lang == "en" else "đã chứng minh là không khả thi trong khoảng số lớp đã cho (tìm kiếm chính "
                "xác); in ra: phương án có biên lớn nhất")
    if s["status"] == "best found":
        if s.get("n_proven"):
            return ("best design found; its ply count is proven minimal" if lang == "en" else
                    "phương án tốt nhất tìm được; số lớp đã chứng minh là nhỏ nhất")
        return ("best design found (GA + local search), not proven optimal" if lang == "en" else
                "phương án tốt nhất tìm được (GA + tìm kiếm cục bộ), chưa chứng minh là tối ưu")
    return ("no feasible design found (GA + local search), not proven infeasible" if lang == "en" else
            "không tìm được phương án đạt (GA + tìm kiếm cục bộ), chưa chứng minh là không khả thi")


def design_data(r):
    """Named quantities (value, unit, meaning) passed to the LLM; also the value table of the checks."""
    sp = r["spec"]
    rows = [("stacking sequence", r["notation"], "", "half laminate from the outer surface to the mid-plane, s = "
             "symmetric"),
            ("number of plies", r["n_plies"], "plies", "total ply count of the laminate"),
            ("0 deg plies", r["counts"]["0"], "plies", "number of plies at 0 deg"),
            ("+45 deg plies", r["counts"]["+45"], "plies", "number of plies at +45 deg"),
            ("-45 deg plies", r["counts"]["-45"], "plies", "number of plies at -45 deg"),
            ("90 deg plies", r["counts"]["90"], "plies", "number of plies at 90 deg"),
            ("laminate thickness", round(r["thickness_mm"], 4), "mm", "total thickness"),
            ("result status", status_text(r), "", "proven optimum or best design found"),
            ("safety margin", round(r["margin"], 4), "", "smallest reserve factor over all plies and criteria"),
            ("required safety factor", sp["safety_factor"], "", "the margin must be at least this"),
            ("verdict", "the design meets the safety factor" if r["feasible"] else
             "the design does NOT meet the safety factor", "", "")]
    for c in ("max_stress", "tsai_wu", "buckling"):
        v = r["rf"].get(c)
        if v is None:
            continue
        rows.append((f"{CRIT_NAME[c]} reserve factor", "no buckling (infinite)" if v == float("inf") else round(v, 4),
                     "", "load multiplier at which this criterion is reached" if c != "buckling" else
                     "buckling load factor: load multiplier at which the plate buckles (Rayleigh-Ritz, D16, D26)"))
    rows.append(("governing criterion", CRIT_NAME[r["governing"]], "", "the criterion that gives the margin"))
    if r["governing"] != "buckling" and r["critical_ply"]:
        rows.append(("critical ply", r["critical_ply"], "", f"ply number (angle {r['critical_angle']:g} deg)"))
    if sp["loads"]["Nxy"]:
        rows.append(("shear direction", "both directions checked (+Nxy and -Nxy, the smaller reserve factor counts)"
                     if sp["shear_both"] else "only the sign given in the request was checked (the request says the "
                     "shear acts in one direction)", "", ""))
    qi = r["quasi_isotropic"]
    if qi["found"]:
        rows.append(("quasi-isotropic laminate needed", qi["n"], "plies",
                     "smallest [0/45/-45/90]ns laminate that meets the same safety factor"))
    if r["reduction_pct"] == 0:
        rows.append(("ply count compared with quasi-isotropic", "the same number of plies", "", ""))
    elif r["reduction_pct"] is not None:
        rows.append(("fewer plies than quasi-isotropic", round(r["reduction_pct"], 1), "%",
                     "(quasi-isotropic plies - design plies) / quasi-isotropic plies; say it with this sentence: "
                     f"'This design has {r['reduction_pct']:.1f} % fewer plies than the smallest quasi-isotropic "
                     f"laminate ({qi['n']} plies).' / 'Thiết kế này có ít hơn {r['reduction_pct']:.1f} % số lớp so với "
                     f"tấm tựa đẳng hướng nhỏ nhất ({qi['n']} lớp).'"))
    rows.append(("material properties", "measured (" + r["material"]["source"] + ")" if sp["row"] else
                 f"ML prediction for {sp['group']} (has an error, result for reference only)", "", ""))
    return rows


EXPLAIN_PROMPT = """You explain the result of a composite laminate design to an engineer, in {language}.
Use ONLY the data below. Give every number exactly as written, together with its name. Do not compute new numbers,
do not convert units, do not add advice about other laminates.

DATA (name = value unit - meaning):
{data}

Write 4 to 7 sentences: the stacking sequence and its number of plies (with the plies of each angle), whether the
result is a proven optimum or the best design found, the safety margin and the criterion that governs it, the
reserve factors of the criteria, and the comparison with the quasi-isotropic laminate. If the design does not meet
the safety factor, say so clearly. Write natural sentences (do not copy the data lines as "name = value") and answer
only with the explanation, without an introduction.
"""


def _explain_prompt(r, lang):
    lines = []
    for name, v, unit, meaning in design_data(r):
        lines.append(f"- {name} = {v}{(' ' + unit) if unit else ''}" + (f" - {meaning}" if meaning else ""))
    return EXPLAIN_PROMPT.format(language="Vietnamese" if lang == "vi" else "English", data="\n".join(lines))


DESIGN_KIND_WORDS = {
    "ply": ["ply", "plies", "layer", "layers", "lamina", "laminae", "lớp"],
    "safety_factor": ["reserve factor", "reserve factors", "safety factor", "factor of safety", "safety margin",
                      "margin", "rf", "times", "multiplied by", "load multiplier", "multiplier", "hệ số dự trữ",
                      "biên an toàn", "hệ số an toàn", "hệ số nhân tải", "lần", "biên"],
    "buckling": ["buckling", "buckling load factor", "load factor", "critical load", "eigenvalue",
                 "mất ổn định", "hệ số tải tới hạn", "tải tới hạn", "hệ số tải"],
    "percent": ["fewer", "reduction", "saving", "lighter", "less", "ít hơn", "giảm", "nhẹ hơn"],
    "thickness": ["thickness", "thick", "độ dày", "dày", "chiều dày"],
    "angle": ["degree", "degrees", "deg", "angle", "góc"],
    "load": ["load", "loads", "force", "tải", "lực"],
    "criterion": ["max stress", "tsai-wu", "tsai wu"],
}
DESIGN_KIND_SYMBOLS = {"angle": ["°"], "load": ["Nx", "Ny", "Nxy"]}
DESIGN_KIND_NAMES = {"ply": "a ply count / ply number", "safety_factor": "a reserve factor / safety factor",
                     "buckling": "a buckling load factor", "percent": "a percentage", "thickness": "a thickness",
                     "angle": "an angle", "load": "a load", "criterion": "a criterion name"}
DESIGN_COMPATIBLE = {"buckling": {"safety_factor"}, "safety_factor": {"buckling"}}
_VOCAB = None


def _vocab():
    global _VOCAB
    if _VOCAB is None:
        _VOCAB = llm.keyword_vocabulary(DESIGN_KIND_WORDS, DESIGN_KIND_SYMBOLS, DESIGN_COMPATIBLE, DESIGN_KIND_NAMES)
    return _VOCAB


def _value_table(r):
    sp = r["spec"]
    rows = [(r["n_plies"], "ply", "the number of plies")]
    rows += [(v, "ply", f"the number of {a} deg plies") for a, v in r["counts"].items() if v]
    rows += [(r["thickness_mm"] * 1e-3, "thickness", "the laminate thickness"),
             (sp["ply_thickness"], "thickness", "the ply thickness"),
             (r["margin"], "safety_factor", "the safety margin"),
             (sp["safety_factor"], "safety_factor", "the required safety factor")]
    for c, v in r["rf"].items():
        if v != float("inf"):
            rows.append((v, "buckling" if c == "buckling" else "safety_factor", f"the {CRIT_NAME[c]} reserve factor"))
    if r["critical_ply"]:
        rows.append((r["critical_ply"], "ply", "the critical ply"))
    if r["critical_angle"] is not None:
        rows.append((r["critical_angle"], "angle", "the angle of the critical ply"))
    rows += [(a, "angle", "a ply angle") for a in (45.0, 90.0)]
    qi = r["quasi_isotropic"]
    if qi["found"]:
        rows.append((qi["n"], "ply", "the plies of the quasi-isotropic laminate"))
    if r["reduction_pct"]:
        rows.append((r["reduction_pct"], "percent", "the reduction of the ply count"))
    for k, v in sp["loads"].items():
        if v:
            rows.append((v, "load", k))
    return [(float(v), k, lab) for v, k, lab in rows if v is not None and float(v) != 0]


_NOT_FEASIBLE_RE = (r"\b(?:infeasible|not\s+feasible|no\s+feasible|does\s+not\s+meet|doesn['’]t\s+meet|fails?\s+to\s+"
                    r"meet|not\s+safe|unsafe)\b|không\s+khả\s+thi|không\s+đạt|chưa\s+đạt|không\s+an\s+toàn")
_FEASIBLE_RE = (r"(?<!not\s)(?<!n['’]t\s)\b(?:meets|satisfies|fulfils|fulfills)\s+(?:the\s+)?(?:required\s+)?"
                r"(?:safety|constraint)|(?<!không\s)(?<!chưa\s)\bđạt\s+(?:yêu\s+cầu|hệ\s+số\s+an\s+toàn)")
_PROVEN_RE = r"\bproven\b|\bguarantee|\bglobally\s+optimal|\bglobal\s+optimum|chứng\s+minh|tối\s+ưu\s+toàn\s+cục"
_SHEAR_NOT_CHECKED_RE = (r"(?:shear|cắt)[^.;]{0,50}?(?:(?:was|were|is|has|have)\s+not\s+(?:been\s+)?checked|"
                         r"not\s+checked|neither\s+direction|không\s+(?:được\s+)?kiểm\s+tra)")
_SHEAR_ONE_RE = r"one\s+direction\s+only|only\s+(?:in\s+)?one\s+direction|given\s+sign\s+only|chỉ\s+(?:theo\s+)?một\s+chiều"
_SHEAR_BOTH_RE = r"both\s+directions|both\s+signs|\+nxy\s+and\s+-nxy|cả\s+hai\s+chiều"
# "the quasi-isotropic laminate ... has 10 % fewer plies than this design" (the reduction belongs to the design)
_WRONG_WAY_RE = (r"(?:fewer|less|lighter|thinner|ít\s+hơn|nhẹ\s+hơn|mỏng\s+hơn|giảm)(?:[^.;]|\.(?=\d)){0,60}?"
                 r"(?:\bthan|so\s+với)\s+"
                 r"(?:this\s+|the\s+|our\s+)?(?:proposed\s+|optimi[sz]ed\s+|optimal\s+|optimum\s+)?(?:design|stacking|"
                 r"thiết\s+kế|phương\s+án)")
_GOVERNED_RE = (r"(?:governed|controlled|limited|determined|decided|driven)\s+by\s+(?:the\s+)?(?P<en>buckling|tsai[- ]wu|"
                r"max(?:imum)?\s+stress)|(?:tiêu\s+chuẩn\s+quyết\s+định\s+(?:là\s+)?|do\s+)(?P<vi>mất\s+ổn\s+định|"
                r"tsai[- ]wu|max\s+stress)")


def design_explanation_issues(text, r):
    """Every number must be one of the data and be named as what it is (English or Vietnamese); the verdicts
    (feasible or not, proven or not, governing criterion) must agree with the result."""
    # report numbers, pages and years of the material source are names, not quantities
    text = re.sub(r"NCP[-‑–]RP[-‑–][\w‑–-]+(?:\s+Rev\s+[\w-]+)?", "report", text)
    text = re.sub(r"\bp\.\s*\d+|\(\d{4}\)", "", text)
    issues = llm.check_meaning(text, None, None, None, table=_value_table(r), vocab=_vocab(), report_unknown=True,
                               noun_after=True)
    t = llm._normalize(text).lower()
    if r["feasible"] and re.search(_NOT_FEASIBLE_RE, t):
        issues.append(f"the design meets the safety factor, but the text says '{re.search(_NOT_FEASIBLE_RE, t).group()}'")
    if not r["feasible"]:
        for m in re.finditer(_FEASIBLE_RE, t):
            after = t[m.end():m.end() + 20]
            if not re.search(r"\b(?:not|neither|nor|none|no|never|fails?|không|chưa)\b", t[max(0, m.start() - 40):
                                                                                             m.start()]) \
                    and not re.match(r"[\w\s]*?(?:=|:)\s*(?:no|không)\b", after):    # "... meets the safety factor = NO"
                issues.append(f"the design does NOT meet the safety factor, but the text says '{m.group()}'")
                break
    if r["spec"]["loads"]["Nxy"]:
        m = re.search(_SHEAR_NOT_CHECKED_RE, t)
        if m:
            issues.append(f"the shear was checked ({'both directions' if r['spec']['shear_both'] else 'the given sign'}"
                          f"), but the text says '{m.group()}'")
        wrong = _SHEAR_ONE_RE if r["spec"]["shear_both"] else _SHEAR_BOTH_RE
        done = "in both directions" if r["spec"]["shear_both"] else "for the given sign only"
        m = re.search(wrong, t)
        if m and not llm._negated(t, m.start()):
            issues.append(f"the shear was checked {done}, but the text says '{m.group()}'")
    for m in re.finditer(_PROVEN_RE, t):
        if r["search"]["proven"]:
            break
        before = t[max(0, m.start() - 14):m.start()]
        if llm._negated(t, m.start()) or re.search(r"\b(?:not|chưa)\s+(?:been\s+|được\s+)?$", before):
            continue
        if r["search"].get("n_proven") and re.search(r"ply\s+count|number\s+of\s+plies|số\s+lớp",
                                                     t[max(0, m.start() - 50):m.end() + 50]):
            continue      # the ply count IS proven minimal (only the margin is not)
        issues.append(f"the result is the best design found, not a proven optimum, but the text says '{m.group()}'")
        break
    # a margin / reserve factor of the DESIGN written after "quasi-isotropic" in the same sentence is given to the
    # quasi-isotropic laminate (its margin is not in the data): "a quasi-isotropic laminate ... would reach 0.296"
    design_rf = [r["margin"]] + [v for v in r["rf"].values() if v != float("inf")]
    for sm in re.finditer(r"(?:[^.!?;\n]|\.(?=\d))+", re.sub(r"\[[^\]]*\]\s*[a-z0-9]*", "layup", t)):
        sent = sm.group()
        q = re.search(r"quasi[- ]?isotropic|tựa\s+đẳng\s+hướng", sent)
        if not q:
            continue
        for x in re.finditer(r"(?<![\w.])\d+(?:[.,]\d+)?", sent[q.end():]):
            v = float(x.group().replace(",", "."))
            if v not in (r["spec"]["safety_factor"],) and any(abs(v - f) <= 5e-4 * f for f in design_rf):
                issues.append(f"'{x.group()}' is a reserve factor of the DESIGN, but the sentence gives it to the "
                              "quasi-isotropic laminate")
                break
    m = re.search(_WRONG_WAY_RE, t)
    if m:
        issues.append(f"the DESIGN has fewer plies than the quasi-isotropic laminate, but the text says "
                      f"'{m.group().strip()}' (the comparison is the wrong way round)")
    for m in re.finditer(_GOVERNED_RE, t):
        w = (m.group("en") or m.group("vi")).replace("-", " ")
        said = "buckling" if ("buckling" in w or "ổn định" in w) else "tsai_wu" if "tsai" in w else "max_stress"
        if said != r["governing"]:
            issues.append(f"the margin is governed by {CRIT_NAME[r['governing']]}, but the text says "
                          f"'{m.group().strip()}'")
    return issues


def prebuilt_explanation(r, lang="en"):
    """Explanation written by Python from the result (always passes its own checks)."""
    c = r["counts"]
    sf = r["spec"]["safety_factor"]
    rf = r["rf"]
    qi = r["quasi_isotropic"]
    if lang == "vi":
        out = [f"Thứ tự xếp lớp {r['notation']} có {r['n_plies']} lớp: {c['0']} lớp 0°, {c['+45']} lớp +45°, "
               f"{c['-45']} lớp -45° và {c['90']} lớp 90°; kết quả: {status_text(r, 'vi')}.",
               f"Biên an toàn là {r['margin']:.4g} (yêu cầu hệ số an toàn {sf:g}), "
               + ("đạt yêu cầu" if r["feasible"] else "KHÔNG đạt yêu cầu")
               + f"; tiêu chuẩn quyết định là {CRIT_VI[r['governing']]}."]
        parts = [f"{CRIT_VI[k]} {v:.4g}" for k, v in rf.items() if v != float("inf")]
        if parts:
            out.append("Hệ số dự trữ của từng tiêu chuẩn: " + ", ".join(parts) + ".")
        if "buckling" in rf and rf["buckling"] == float("inf"):
            out.append("Tải này không làm tấm mất ổn định (không có nén, lực kéo lấn át).")
        if r["reduction_pct"]:
            out.append(f"Tấm tựa đẳng hướng nhỏ nhất cần {qi['n']} lớp để có cùng hệ số an toàn, nên thiết kế này "
                       f"ít hơn {r['reduction_pct']:.1f} % số lớp.")
        elif r["reduction_pct"] == 0:
            out.append(f"Tấm tựa đẳng hướng nhỏ nhất cũng cần {qi['n']} lớp.")
        note = "(bản dựng sẵn bằng Python từ kết quả tính, vì lời giải thích của LLM không qua được bước kiểm tra)"
    else:
        out = [f"The stacking sequence {r['notation']} has {r['n_plies']} plies: {c['0']} plies at 0°, "
               f"{c['+45']} plies at +45°, {c['-45']} plies at -45° and {c['90']} plies at 90°; result: "
               f"{status_text(r)}.",
               f"The safety margin is {r['margin']:.4g} for a required safety factor of {sf:g}, so the design "
               + ("meets the safety factor" if r["feasible"] else "does NOT meet the safety factor")
               + f"; the governing criterion is {CRIT_NAME[r['governing']]}."]
        parts = [f"{CRIT_NAME[k]} {v:.4g}" for k, v in rf.items() if v != float("inf")]
        if parts:
            out.append("Reserve factors of the criteria: " + ", ".join(parts) + ".")
        if "buckling" in rf and rf["buckling"] == float("inf"):
            out.append("These loads cannot make the plate buckle (no compression, or the tension dominates).")
        if r["reduction_pct"]:
            out.append(f"The smallest quasi-isotropic laminate needs {qi['n']} plies to reach the same safety "
                       f"factor, so this design has {r['reduction_pct']:.1f} % fewer plies.")
        elif r["reduction_pct"] == 0:
            out.append(f"The smallest quasi-isotropic laminate also needs {qi['n']} plies.")
        note = "(pre-built explanation written by Python from the results, because the LLM text did not pass the checks)"
    return " ".join(out), note


def explain_design(r, backend=None, lang="en"):
    """LLM explanation + checks; one retry with the list of problems; else the pre-built explanation."""
    prompt = _explain_prompt(r, lang)
    text = llm.ask_llm(prompt, backend=backend)
    issues = design_explanation_issues(text, r)
    if not issues:
        return text, {"source": "llm", "issues": [], "first_issues": [], "rejected": []}
    print(f"  [check] the explanation has {len(issues)} problem(s) -> asking the LLM again (once):")
    for x in issues:
        print(f"          - {x}")
    retry = (prompt + "\nYour previous answer was:\n" + text.strip() + "\n\nThe program found these problems in it:\n"
             + "\n".join(f"- {x}" for x in issues) + "\nWrite the explanation again without these problems.\n")
    text2 = llm.ask_llm(retry, backend=backend)
    issues2 = design_explanation_issues(text2, r)
    if not issues2:
        return text2, {"source": "llm-retry", "issues": [], "first_issues": issues, "rejected": [text]}
    pre, note = prebuilt_explanation(r, lang)
    return pre, {"source": "prebuilt", "issues": issues2, "first_issues": issues, "note": note,
                 "rejected": [text, text2]}


# ---------------------------------------------------------------------------------------------- printing / CLI
def print_spec(spec, material_source):
    L = spec.loads
    print(f"  material : {spec.row or spec.group} -> {material_source}")
    print(f"  loads    : Nx={L['Nx']:g}  Ny={L['Ny']:g}  Nxy={L['Nxy']:g} N/m"
          + ("   (shear checked for +Nxy and -Nxy)" if spec.shear_both else ""))
    obj = "lightest (fewest plies)" if spec.objective == "min_plies" else f"largest safety margin with {spec.n_min} plies"
    print(f"  objective: {obj}; plies {spec.n_min}-{spec.n_max}; safety factor {spec.safety_factor:g}")
    print(f"  plate    : {spec.a:g} m x {spec.b:g} m, simply supported; ply thickness {spec.ply_thickness * 1e3:g} mm")
    rules = ["symmetric", "balanced"]
    rules.append(f">= {spec.min_fraction * 100:g} % per direction" if spec.min_fraction else "no 10 % rule")
    rules.append(f"<= {spec.max_contiguous} identical plies in a row" if spec.max_contiguous else "no contiguity limit")
    print(f"  rules    : {', '.join(rules)}; angles 0, +45, -45, 90")
    if spec.defaults:
        print("  defaults used (not given in the text): " + "; ".join(spec.defaults))
    for n in spec.notes:
        print(f"  [note] {n}")


def print_result(r):
    s = r["search"]
    sp = r["spec"]
    ex = s["exact"]
    print(f"  search   : exact search {ex['status']}"
          + (f" ({ex.get('time_s', 0):.1f} s)" if ex.get("time_s") is not None else "")
          + (f"; GA + local search (seed {s['ga']['seed']}, {s['ga']['budget']} designs, {s['ga']['time_s']:.1f} s)"
             if s["ga"] else "")
          + (f"; proven lower bound of the ply count: {ex['n_lower_bound']}" if ex.get("n_lower_bound") and
             not s["proven"] else ""))
    print(f"  RESULT   : {r['notation']}   {r['n_plies']} plies ({r['thickness_mm']:.4g} mm)  ->  {status_text(r)}")
    c = r["counts"]
    print(f"  plies per angle: 0: {c['0']}   +45: {c['+45']}   -45: {c['-45']}   90: {c['90']}")
    rf = "   ".join(f"{CRIT_NAME[k]} {('inf (no buckling)' if v == float('inf') else f'{v:.4g}')}"
                    for k, v in r["rf"].items())
    print(f"  reserve factors: {rf}")
    where = (f", ply {r['critical_ply']} ({r['critical_angle']:g} deg)" if r["governing"] != "buckling" and
             r["critical_ply"] else "")
    sign = (f", shear {r['governing_shear_sign']}Nxy" if sp["shear_both"] and r.get("governing_shear_sign") else "")
    print(f"  margin   : {r['margin']:.4g} (required {sp['safety_factor']:g}) governed by "
          f"{CRIT_NAME[r['governing']]}{where}{sign}  -> {'MEETS the safety factor' if r['feasible'] else 'DOES NOT MEET the safety factor'}")
    if not r["feasible"]:
        print(f"  [not feasible] criteria below {sp['safety_factor']:g}: "
              + ", ".join(f"{CRIT_NAME[k]} {r['rf'][k]:.4g}" for k in r["failing"]))
    m = r["matlab"]
    if m is None:
        print("  check MATLAB: not run")
    elif m.get("pass") is None:
        print(f"  check MATLAB: not available ({m['error']})")
    else:
        print(f"  check MATLAB clt_engine.m (strength): {'PASS' if m['pass'] else 'FAIL'}  (largest relative "
              f"difference Python/MATLAB {max([m['e_clt']] + list(m['e_rf'].values())):.1e})")
    for b in r["buckling_check"]:
        print(f"  check buckling (Nxy={b['Nxy']:g}): sine-series Ritz {b['lambda_sine']:.4g} vs independent "
              f"polynomial Ritz {b['lambda_polynomial']:.4g} -> difference {b['difference_pct']:+.2f} %")
        if b["difference_pct"] is not None and abs(b["difference_pct"]) > BUCKLING_CHECK_TOL_PCT:
            print(f"  [warning] the two buckling solutions differ by more than {BUCKLING_CHECK_TOL_PCT:g} % "
                  "(both are upper bounds): treat the buckling reserve factor with care")
    qi = r["quasi_isotropic"]
    if qi["found"]:
        red = (f" -> this design has {r['reduction_pct']:.1f} % fewer plies" if r["reduction_pct"] else
               " -> the same number of plies" if r["reduction_pct"] == 0 else "")
        print(f"  quasi-isotropic: smallest [0/45/-45/90]ns meeting the same constraints = {qi['n']} plies{red}")
    else:
        print("  quasi-isotropic: no [0/45/-45/90]ns laminate up to 128 plies meets the constraints")
    if not sp["row"]:
        print(f"  [warning] {ML_WARNING}")
    for w in r["material"]["warnings"]:
        if w != ML_WARNING:
            print(f"  [warning] material: {w}")


def main(user_text, backend=None, lang="en", explain=True, check_matlab=True):
    t_all = time.time()
    print("\n[1/4] LLM reads the design request ...")
    t = time.time()
    spec = parse_design(user_text, backend=backend)
    print(f"  ({llm.LAST_BACKEND}, {time.time() - t:.1f} s)")
    mat = material_of(spec)
    print_spec(spec, mat.source)
    print("\n[2/4] Optimiser (exact search, else GA + local search) ...")
    print("\n[3/4] Checks: MATLAB strength, polynomial Ritz buckling, quasi-isotropic comparison ...")
    r = solve(spec, check_matlab=check_matlab)
    print(f"  ({r['time_s']:.1f} s, of which search {r['search_time_s']:.1f} s)")
    print_result(r)
    answer, info = None, {}
    if explain:
        print("\n[4/4] LLM explains the design ...")
        t = time.time()
        try:
            answer, info = explain_design(r, backend=backend, lang=lang)
            print(f"  ({llm.LAST_BACKEND}, {time.time() - t:.1f} s)")
        except Exception as e:
            print(f"  explanation not available: {type(e).__name__}: {str(e)[:200]}")
    print(f"\nTotal time: {time.time() - t_all:.1f} s")
    return {"spec": spec, "result": r, "answer": answer, "explanation": info}


def print_explanation(out):
    if not out.get("answer"):
        return
    info = out.get("explanation") or {}
    if info.get("source") == "prebuilt":
        print("\n===== EXPLANATION (pre-built by Python) =====")
        print(out["answer"].strip())
        print(f"  {info['note']}")
        return
    print("\n===== EXPLANATION (LLM) =====")
    print(out["answer"].strip())
    print("\n[guardrail] every number in the explanation is one of the design data and is named as what it is"
          + (" (after one retry)" if info.get("source") == "llm-retry" else ""))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Design a composite laminate from a request in words")
    ap.add_argument("text", nargs="+", help="design request")
    ap.add_argument("--backend", default=None, choices=["auto", "hf", "ollama"])
    ap.add_argument("--lang", default="en", choices=["en", "vi"])
    ap.add_argument("--no-explain", action="store_true")
    args = ap.parse_args()
    text = " ".join(args.text)
    print("===== DESIGN REQUEST =====")
    print(text.strip())
    try:
        out = main(text, backend=args.backend, lang=args.lang, explain=not args.no_explain)
        print_explanation(out)
    except DesignRefusal as e:
        print(f"\n[REFUSED] {e}")
    finally:
        try:
            from matlab_clt import close_engine
            close_engine()
        except Exception:
            pass
