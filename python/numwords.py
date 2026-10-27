"""
numwords.py - numbers written in words -> digits, so the checks in llm.py can find every number of a problem.
  "one thousand five hundred newtons per metre" -> "1500 newtons per metre"
  "chịu lực kéo hai kN/m"                       -> "chịu lực kéo 2 kN/m"
To avoid false hits ("năm 2026" = year 2026, "one of the plies"), a group of number words is converted only
if it contains a multiplier (hundred, thousand, trăm, nghìn, mươi...) or is followed by a unit / "plies" / "lớp".
"""
import re
import unicodedata

EN_VALUE = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen".split())}
EN_VALUE.update({w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())})
EN_MULT = {"hundred": 100, "thousand": 1000, "million": 1_000_000}
EN_JOIN = {"and", "a", "point"}
VI_DIGIT = {"không": 0, "một": 1, "mốt": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4, "năm": 5, "lăm": 5, "sáu": 6,
            "bảy": 7, "tám": 8, "chín": 9}
VI_MULT = {"mười", "mươi", "trăm", "nghìn", "ngàn", "triệu"}
VI_JOIN = {"linh", "lẻ", "phẩy"}
UNIT_AFTER = re.compile(r"\s*(?:k?N\b|k?N\s*/|N\s*[·.*⋅]|mm\b|µm|μm|um\b|m\b|in\b|inch|lbf|newtons?|kilonewtons?|"
                        r"plies|ply|lớp|layers?|độ|°|degrees?)", re.I)


def _parse_en(words):
    if "point" in words:
        i = words.index("point")
        whole = _parse_en(words[:i]) if i else 0
        digits = "".join(str(EN_VALUE[w]) for w in words[i + 1:] if w in EN_VALUE and EN_VALUE[w] < 10)
        return float(f"{whole}.{digits}") if digits else whole
    total = group = 0
    for w in words:
        if w in EN_VALUE:
            group += EN_VALUE[w]
        elif w == "hundred":
            group = (group or 1) * 100
        elif w in ("thousand", "million"):
            total += (group or 1) * EN_MULT[w]
            group = 0
    return total + group


def _parse_vi(words):
    if "phẩy" in words:
        i = words.index("phẩy")
        whole = _parse_vi(words[:i]) if i else 0
        digits = "".join(str(VI_DIGIT[w]) for w in words[i + 1:] if w in VI_DIGIT)
        return float(f"{whole}.{digits}") if digits else whole
    total = group = 0
    digit = None
    for w in words:
        if w in VI_DIGIT:
            digit = VI_DIGIT[w]
        elif w == "mười":
            group += 10
            digit = None
        elif w == "mươi":
            group += (digit or 1) * 10
            digit = None
        elif w == "trăm":
            group += (digit or 1) * 100
            digit = None
        elif w in ("nghìn", "ngàn", "triệu"):
            group += digit or 0
            total += (group or 1) * (1000 if w != "triệu" else 1_000_000)
            group, digit = 0, None
    return total + group + (digit or 0)


def _fmt(v):
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def convert(text):
    """-> (text with number words replaced by digits, list of (words, value)). Text is NFC-normalised."""
    text = unicodedata.normalize("NFC", text)
    words = list(re.finditer(r"[^\W\d_]+", text))
    runs, cur = [], []
    for m in words:
        w = m.group().lower()
        known = w in EN_VALUE or w in EN_MULT or w in EN_JOIN or w in VI_DIGIT or w in VI_MULT or w in VI_JOIN
        joined = cur and re.fullmatch(r"[\s-]*", text[cur[-1].end():m.start()])
        if known and (not cur or joined):
            cur.append(m)
        else:
            if cur:
                runs.append(cur)
            cur = [m] if known else []
    if cur:
        runs.append(cur)

    found = []
    for run in runs:
        while run and run[0].group().lower() in (EN_JOIN | VI_JOIN) - {"a"}:
            run = run[1:]
        while run and run[-1].group().lower() in EN_JOIN | VI_JOIN:
            run = run[:-1]
        if run and run[0].group().lower() == "a" and (len(run) < 2 or run[1].group().lower() not in EN_MULT):
            run = run[1:]
        ws = [m.group().lower() for m in run]
        if not ws or not any(w in EN_VALUE or w in EN_MULT or w in VI_DIGIT or w in VI_MULT for w in ws):
            continue
        en = all(w in EN_VALUE or w in EN_MULT or w in EN_JOIN for w in ws)
        vi = all(w in VI_DIGIT or w in VI_MULT or w in VI_JOIN for w in ws)
        if not (en or vi):
            continue
        has_mult = any(w in EN_MULT or w in VI_MULT for w in ws)
        unit_next = UNIT_AFTER.match(text, run[-1].end())
        if not (has_mult or unit_next):
            continue
        value = _parse_en(ws) if en else _parse_vi(ws)
        found.append((run[0].start(), run[-1].end(), text[run[0].start():run[-1].end()], value))
    out = text
    for start, end, words_txt, value in sorted(found, reverse=True):
        out = out[:start] + _fmt(value) + out[end:]
    return out, [(w, v) for _, _, w, v in sorted(found)]


if __name__ == "__main__":
    tests = [
        ("loaded by one thousand five hundred newtons per metre in the x direction", "1500 newtons"),
        ("chịu lực kéo hai kN/m theo phương x", "kéo 2 kN/m"),
        ("a tensile load of twenty-five kN/m", "of 25 kN/m"),
        ("a thousand N/m", "1000 N/m"),
        ("two plies [45/-45]", "2 plies"),
        ("one point five kN/m", "1.5 kN/m"),
        ("hai nghìn năm trăm N/m", "2500 N/m"),
        ("một trăm hai mươi N/m", "120 N/m"),
        ("mười lăm N/m", "15 N/m"),
        ("không phẩy năm mm", "0.5 mm"),
        ("trong năm 2026, tấm có ba lớp", "trong năm 2026, tấm có 3 lớp"),
        ("one of the plies is thicker", "one of the plies"),
        ("a tensile load of 1000 N/m", "a tensile load of 1000 N/m"),
        ("hai mặt của tấm", "hai mặt"),
    ]
    bad = 0
    for t, want in tests:
        got, f = convert(t)
        ok = want in got
        bad += not ok
        print(f"[{'OK' if ok else 'FAIL'}] {t!r} -> {got!r} {f}")
    print("ALL PASS" if not bad else f"{bad} FAILED")
