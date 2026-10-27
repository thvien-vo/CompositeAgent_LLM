"""
layup.py - turn a stacking-sequence string into the full list of ply angles (deterministic,
no LLM). Used by llm.py so the LLM only has to COPY the notation from the text; expanding
"[0/90]2s" correctly is done here (LLMs often get repeats/symmetry wrong).

Supported notation (case-insensitive, degree signs ignored):
  0, 45, -45, 90          plain list (separators: / , ; space)
  [0/45/-45/90]s          s / S / _s / sym  = symmetric: sequence + mirror image
  [0/90]2s                repeat 2 times, then symmetric
  [±45]3, [+-45], [+/-45] ± a  = +a, -a      ;  ∓ a = -a, +a
  [0_2/90]s, [0₂/90]s     0_2 = two 0° plies
  [(0/90)2/45]s           groups in ( ) or [ ] can carry their own repeat / s
  [0/90]T                 T (total) = no change
Not supported: overbar for an odd middle ply ([0/90̄]s). Raises LayupError for anything unclear.
"""
import re

_SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")


class LayupError(ValueError):
    pass


def _normalize(text):
    s = re.sub("[₀-₉]+", lambda m: "_" + m.group().translate(_SUB), str(text).strip())  # 0₂ -> 0_2
    s = s.replace("+/-", "±").replace("+-", "±").replace("-/+", "∓").replace("-+", "∓")
    s = s.replace("−", "-").replace("–", "-")           # unicode minus / en dash
    s = re.sub(r"(?i)°|º|deg(rees?)?", "", s)
    s = re.sub(r"(?i)\bsym(metric)?\b", "s", s)
    s = re.sub(r"\s*([\[\]()/,;±∓_])\s*", r"\1", s)    # spaces around symbols mean nothing
    s = re.sub(r"\s+", ",", s)                           # remaining spaces separate angles
    return s


class _Parser:
    def __init__(self, s):
        self.s, self.i = s, 0

    def peek(self):
        return self.s[self.i] if self.i < len(self.s) else ""

    def seq(self, closing=""):
        out = []
        while True:
            out += self.item()
            c = self.peek()
            if c in ("/", ",", ";"):
                self.i += 1
                continue
            if c == closing or c == "":
                return out
            raise LayupError(f"unexpected '{c}' at position {self.i} in '{self.s}'")

    def item(self):
        c = self.peek()
        if c in ("[", "("):
            self.i += 1
            inner = self.seq("]" if c == "[" else ")")
            if self.peek() != ("]" if c == "[" else ")"):
                raise LayupError(f"missing closing bracket in '{self.s}'")
            self.i += 1
        else:
            inner = self.angle()
        return self.suffix(inner)

    def angle(self):
        m = re.compile(r"([±∓]?)([+-]?\d+(?:\.\d+)?)").match(self.s, self.i)
        if not m:
            raise LayupError(f"expected an angle at position {self.i} in '{self.s}'")
        self.i = m.end()
        sign, a = m.group(1), float(m.group(2))
        if sign == "±":
            return [a, -a]
        if sign == "∓":
            return [-a, a]
        return [a]

    def suffix(self, plies):
        while True:
            m = re.compile(r"_?(\d+)?([sSTt]?)").match(self.s, self.i)
            if not m or m.end() == self.i:
                return plies
            self.i = m.end()
            if m.group(1):
                n = int(m.group(1))
                if not 1 <= n <= 50:
                    raise LayupError(f"repeat count {n} looks wrong in '{self.s}'")
                plies = plies * n
            if m.group(2) in ("s", "S"):
                plies = plies + plies[::-1]


def expand_layup(text):
    """'[0/±45]s' -> [0.0, 45.0, -45.0, -45.0, 45.0, 0.0]"""
    s = _normalize(text)
    if not s:
        raise LayupError("empty layup")
    p = _Parser(s)
    plies = p.seq()
    if p.i != len(s):
        raise LayupError(f"could not read the end of '{text}'")
    if not plies or len(plies) > 500:
        raise LayupError(f"layup '{text}' gives {len(plies)} plies")
    for a in plies:
        if not -90 <= a <= 90:
            raise LayupError(f"ply angle {a} outside -90..90 in '{text}'")
    return plies


if __name__ == "__main__":
    tests = {
        "0, 45, -45, 90": [0, 45, -45, 90],
        "[0/45/-45/90]s": [0, 45, -45, 90, 90, -45, 45, 0],
        "[0/90]2s": [0, 90, 0, 90, 90, 0, 90, 0],
        "[0/±45]s": [0, 45, -45, -45, 45, 0],
        "[±30]2s": [30, -30, 30, -30, -30, 30, -30, 30],
        "[+-45]": [45, -45],
        "[0_2/90]s": [0, 0, 90, 90, 0, 0],
        "[0₂/90]s": [0, 0, 90, 90, 0, 0],
        "[(0/90)2/45]s": [0, 90, 0, 90, 45, 45, 90, 0, 90, 0],
        "[0°/90°]T": [0, 90],
        "0° / 30° / 60° / 90° / 0°": [0, 30, 60, 90, 0],
        "[0/90/45/-45]_s": [0, 90, 45, -45, -45, 45, 90, 0],
        "[45/-45]": [45, -45],
        "[0/90] sym": [0, 90, 90, 0],
        "0 90 90 0": [0, 90, 90, 0],
    }
    bad = 0
    for t, want in tests.items():
        got = expand_layup(t)
        ok = got == [float(a) for a in want]
        bad += not ok
        print(f"[{'OK' if ok else 'FAIL'}] {t!r:32} -> {got}")
    for t in ["[0/90", "abc", "[0/120]", ""]:
        try:
            expand_layup(t)
            print(f"[FAIL] {t!r} should raise")
            bad += 1
        except LayupError as e:
            print(f"[OK] {t!r:32} -> LayupError: {e}")
    print("ALL PASS" if bad == 0 else f"{bad} FAILED")
