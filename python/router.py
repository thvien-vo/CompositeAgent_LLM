"""
router.py - what does the user want? Three kinds of request, decided by Python rules first:
  "analysis" : a GIVEN laminate (stacking sequence in the text) under loads -> CLT agent (main.py, unchanged)
  "design"   : choose the stacking sequence (lightest / strongest for a ply count) -> design.py (optimiser)
  "question" : a question about the material data -> RAG (rag.py)
The LLM is asked only when the rules see weak wording for a design ("I need a laminate that can carry ...") and
no other cue; its answer is accepted only if it confirms the design. Contradictory or unclear text is refused with
a hint, never guessed.
"""
import re

from layup import LayupError, expand_layup
from numwords import convert as numbers_from_words

GUIDE = ("Write it as one of: (1) an ANALYSIS of a given laminate, e.g. 'CFRP [0/90]s, 0.125 mm plies, "
         "Nx = 1 kN/m'; (2) a DESIGN request, e.g. 'Design the lightest IM7/8552 laminate for Nx = -50 kN/m'; "
         "(3) a QUESTION about material data, e.g. 'What is Xt of IM7/8552?'")

# strong cues: the text asks the program to choose the stacking sequence
DESIGN_CUES = (
    r"\bdesign(?:ing)?\b|\boptimi[sz]|\boptimum\b|\boptimal\b|\blightest\b|\bfewest\b|\bthinnest\b|"
    r"\bminimum (?:number of )?plies\b|\bminimi[sz]e (?:the )?(?:weight|mass|thickness|number of plies)|"
    r"\bstrongest\b|\b(?:largest|highest|maximum|max) (?:safety )?margin|\bmaximi[sz]e (?:the )?(?:safety )?margin|"
    r"\bbest (?:stacking|layup|lay-up|laminate)|\b(?:which|what) (?:stacking|layup|lay-up)|\bhow many plies|"
    r"\bfind (?:the |a )?(?:best |optimum |lightest )?(?:stacking|layup|lay-up|laminate)|"
    r"thiết kế|tối ưu|nhẹ nhất|ít lớp nhất|mỏng nhất|bền nhất|bao nhiêu lớp|"
    r"tìm (?:thứ tự|cách) xếp|chọn (?:thứ tự|cách) xếp|biên an toàn lớn nhất")
# weak cues: a need for a laminate, without asking for a design in so many words (LLM must confirm)
WEAK_DESIGN_CUES = (
    r"\b(?:i|we) (?:need|want|require|am looking for|are looking for)\b|\bsuggest|\brecommend|\bsuitable\b|"
    r"\bwhich laminate\b|\bwhat laminate\b|\bthat can (?:carry|withstand|take|resist)|"
    r"tôi cần|chúng tôi cần|cần một tấm|đề xuất|gợi ý|nên dùng|phù hợp")
QUESTION_CUES = (
    r"\?\s*$|^\s*(?:what|which|give|list|tell me|show me|is there|cho biết|cho tôi biết|liệt kê)\b|"
    r"là bao nhiêu|là gì\b|\bnào\b")
_LAYUP = r"\[[^\[\]]+\](?:_?\d+)?(?:_?(?:sym(?:metric)?|[sSTt])(?![A-Za-z]))?"
_LOAD_SYMBOL_VALUE = r"(?<![A-Za-z])[NM]\s*_?\{?\s*(?:xy|yx|x|y)\}?\s*(?:=|:|\bof\b|\bis\b|là|bằng)\s*[-+]?\d"


def _bracket_layups(text):
    out = []
    for cand in re.findall(_LAYUP, text):
        try:
            if len(expand_layup(cand)) >= 2:      # "[1]" is a citation, not a stacking sequence
                out.append(cand)
        except LayupError:
            pass
    return out


def signals(text):
    """The cues the rules look at (also printed when a request is refused)."""
    import llm
    t = numbers_from_words(text.strip())[0]
    low = t.lower()
    return {
        "layup": _bracket_layups(t),
        "angle_list": llm._angles_from_text(t),
        "loads": bool(llm._load_quantities(t)) or bool(re.search(_LOAD_SYMBOL_VALUE, t)),
        "design": [m.group(0) for m in re.finditer(DESIGN_CUES, low)],
        "weak_design": [m.group(0) for m in re.finditer(WEAK_DESIGN_CUES, low)],
        "question": bool(re.search(QUESTION_CUES, low)),
    }


CONFIRM_PROMPT = """Does this request ask a program to CHOOSE (design) the stacking sequence of a composite laminate
for the given loads? Answer "design" if it does, "analysis" if it gives a laminate to be checked, "question" if it
asks about material data, "unclear" otherwise.

REQUEST:
{text}

Answer only with JSON."""
CONFIRM_SCHEMA = {"type": "object", "properties": {"kind": {"type": "string",
                                                            "enum": ["design", "analysis", "question", "unclear"]}},
                  "required": ["kind"]}


class UnclearRequest(ValueError):
    """The request cannot be classified safely: the message says why and how to write it."""


def classify(text, backend=None, use_llm=True):
    """-> (kind, reason). kind in {"analysis", "design", "question"}; raises UnclearRequest otherwise."""
    s = signals(text)
    if s["design"] and s["layup"]:
        raise UnclearRequest(
            f"the text gives a stacking sequence ({s['layup'][0]}) AND asks for a design ('{s['design'][0]}'): "
            "to check that laminate, remove the design words; to design a new one, remove the stacking sequence. "
            + GUIDE)
    if s["layup"] or (s["angle_list"] and not s["design"]):
        return "analysis", ("stacking sequence in the text: " + (s["layup"][0] if s["layup"] else
                                                                 f"plies {s['angle_list']}"))
    if s["design"]:
        return "design", f"design words: {', '.join(dict.fromkeys(s['design']))}"
    if s["question"] and not s["loads"]:
        return "question", "a question without loads or stacking sequence"
    if s["weak_design"] and s["loads"] and use_llm:
        import llm
        ans = llm._extract_json(llm.ask_llm(CONFIRM_PROMPT.format(text=text.strip()), json_schema=CONFIRM_SCHEMA,
                                            backend=backend)).get("kind")
        if ans == "design":
            return "design", (f"wording '{s['weak_design'][0]}' + loads, design confirmed by the LLM "
                              f"({llm.LAST_BACKEND})")
        raise UnclearRequest(f"'{s['weak_design'][0]}' could mean a design request, but the LLM read it as "
                             f"'{ans}'. " + GUIDE)
    if s["loads"]:
        raise UnclearRequest("the text gives loads but no stacking sequence and does not ask for a design. " + GUIDE)
    raise UnclearRequest("no stacking sequence, no design request and no question found. " + GUIDE)
