"""
materials.py - ply properties for the CLT step.

If the problem names ONE material system that matches exactly one row of composite_lamina_dataset_v4.csv
(fibre AND matrix both recognised; case, "/", "-", spaces and maker names such as "Hexcel" ignored), the
MEASURED values of that row are used (GPa x 1e9, MPa x 1e6 -> Pa). Otherwise - no name, only a fibre name
("IM7" is in 4 rows), or a name that is not in the data - the ML prediction for the group (CFRP / GFRP /
KEVLAR) is used, as before, and the reason is printed.
Missing values (S of T650/5250-5) and values excluded as anomalous in ml.EXCLUDE (nu12 = 0.164 of
T40-800/5215) are replaced by the ML prediction for the group, with a warning naming the column.
Reads the CSV only; ml.py, the trained models and the CSV are not changed.
"""
import re

import pandas as pd

from ml import DATA_CSV, EXCLUDE, TARGETS, predict_material

GROUP_OF_CLASS = {"carbon": "CFRP", "glass": "GFRP", "aramid": "KEVLAR"}
# maker / product words that do not identify the fibre or the resin
MAKERS = {"hexcel", "cytec", "cycom", "toray", "tencate", "newport", "narmco", "hercules", "avco", "3m", "ciba",
          "tenax", "tenaxe", "thornel", "pyrofil", "cetex", "gevetex", "silenka", "solvay", "unitape", "tape",
          "prepreg", "uni", "unidirectional", "laminate", "composite", "resin", "fibre", "fiber", "matrix"}
GENERIC = {"epoxy", "carbon", "glass", "aramid", "kevlar", "graphite", "cfrp", "gfrp"}

_df = None
_keys = None


def table():
    global _df
    if _df is None:
        _df = pd.read_csv(DATA_CSV)
    return _df


def _tokens(s):
    """'Hexcel 8552 / IM7' -> ['8552', 'im7'];  'T650/5320-1' -> ['t650', '53201'] (maker words dropped)."""
    s = re.sub(r"\([^)]*\)", " ", str(s))  # "(LM PAEK)"
    out = []
    for w in re.findall(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", s):
        w = w.lower().replace("-", "")
        if w not in MAKERS:
            out.append(w)
    return out


def _ngrams(tokens, nmax=3):
    return {"".join(tokens[i:i + n]) for n in range(1, nmax + 1) for i in range(len(tokens) - n + 1)}


def _norm(s):
    return "".join(_tokens(s))


def _row_keys():
    """For every row: fibre keys, matrix keys (from the 'material' name and the fibre / matrix columns)."""
    global _keys
    if _keys is None:
        _keys = []
        for _, r in table().iterrows():
            name = r["material"]
            if "/" in name:
                f_part, m_part = name.split("/", 1)
                fk, mk = {_norm(f_part)}, {_norm(m_part)}
            else:  # "Scotchply 1002"
                fk, mk = set(), set()
            fk.add(_norm(r["fiber"]))
            mk.add(_norm(str(r["matrix"]).split("/")[0]))
            _keys.append({"material": name, "fibre": {k for k in fk if k}, "matrix": {k for k in mk if k},
                          "full": _norm(name)})
    return _keys


def _match(tokens, contiguous):
    """Rows whose fibre AND matrix are both in the tokens. contiguous=True: the two must be next to each
    other (used to scan a whole problem text); False: anywhere (used for the short name the LLM copied)."""
    grams = _ngrams(tokens)
    full, fibre_only, matrix_only = [], [], []
    for k in _row_keys():
        f_hit = any(f in grams for f in k["fibre"])
        m_hit = any(m in grams and m not in GENERIC for m in k["matrix"]) or (
            any(m in grams for m in k["matrix"] & GENERIC) and f_hit)
        if contiguous:
            pair = k["full"] in grams or any(f + m in grams or m + f in grams for f in k["fibre"] for m in k["matrix"])
        else:
            pair = k["full"] in grams or (f_hit and m_hit)
        if pair:
            full.append(k["material"])
        elif f_hit:
            fibre_only.append(k["material"])
        elif m_hit:
            matrix_only.append(k["material"])
    return full, fibre_only, matrix_only


def resolve(llm_name, text):
    """-> (row material name or "", note). llm_name = material name copied by the LLM (may be empty)."""
    name = (llm_name or "").strip()
    text_tokens = set(_tokens(text))
    if name and not set(_tokens(name)) <= text_tokens:
        note = f"material name '{name}' from the LLM is not written in the text -> ignored"
        name = ""
    else:
        note = ""
    from_text, _, _ = _match(_tokens(text), contiguous=True)
    if name:
        full, fibre_only, matrix_only = _match(_tokens(name), contiguous=False)
        if len(full) == 1:
            return full[0], note
        if len(set(from_text)) == 1:
            return from_text[0], f"'{name}' did not identify one row; the text names {from_text[0]}"
        if len(full) > 1:
            return "", f"'{name}' matches {len(full)} rows ({', '.join(full)}) -> not unique"
        if fibre_only:
            return "", (f"'{name}' identifies only the fibre: {len(fibre_only)} row(s) ({', '.join(fibre_only)}) "
                        "-> not unique")
        if matrix_only:
            return "", (f"'{name}' identifies only the matrix: {len(matrix_only)} row(s) "
                        f"({', '.join(matrix_only)}) -> not unique")
        return "", f"'{name}' is not in the database ({len(table())} materials)"
    if len(set(from_text)) == 1:
        return from_text[0], (note + "; " if note else "") + f"the text names {from_text[0]}"
    if len(set(from_text)) > 1:
        return "", f"the text names several materials ({', '.join(sorted(set(from_text)))}) -> not unique"
    _, fibre_only, matrix_only = _match(_tokens(text), contiguous=False)
    prefix = note + "; " if note else ""
    if fibre_only:
        return "", (prefix + f"the text identifies only the fibre: {len(fibre_only)} row(s) "
                    f"({', '.join(fibre_only)}) -> not unique")
    if matrix_only:
        return "", (prefix + f"the text identifies only the matrix: {len(matrix_only)} row(s) "
                    f"({', '.join(matrix_only)}) -> not unique")
    return "", note or "no specific material system named"


def group_of(material_name):
    r = table().set_index("material").loc[material_name]
    return GROUP_OF_CLASS.get(r["fiber_class"])


def source_text(r):
    """'measured: NCAMP NCP-RP-2009-028 Rev B, p.37' or 'measured: Tsai & Hahn (1980) ..., no page'."""
    src = str(r["source"])
    page = re.search(r"p\.\s*(\d+)", src)
    if r["data_type"] == "ncamp_mean":
        rep = re.search(r"(NCP-RP[^,]*)", src)
        return f"measured: NCAMP {rep.group(1).strip() if rep else src}, p.{page.group(1) if page else '?'}"
    return f"measured: {src}, no page" + ("" if page is None else f" p.{page.group(1)}")


def ply_properties(problem):
    """-> (dict E1..S in SI units for clt_engine.m, source text, list of warnings)."""
    name = getattr(problem, "material_name", "") or ""
    if not name:
        return predict_material(problem.material), f"ML prediction (group {problem.material})", []
    r = table().set_index("material").loc[name]
    group = GROUP_OF_CLASS.get(r["fiber_class"], problem.material)
    props, warnings, ml = {}, [], None
    for col, (key, scale) in TARGETS.items():
        value = r[col]
        excluded = int(r["id"]) in EXCLUDE.get(col, [])
        if pd.isna(value) or excluded:
            ml = ml or predict_material(group)
            props[key] = ml[key]
            why = "not reported" if pd.isna(value) else f"excluded as anomalous ({float(value):g})"
            shown = f"{ml[key]:.4g}" if key == "nu12" else f"{ml[key] / scale:.4g} {col.split('_')[1]}"
            warnings.append(f"{key} of {name} {why} -> ML prediction for group {group} used: {shown}")
        else:
            props[key] = float(f"{float(value) * scale:.6g}")
    if r["verify_status"] != "verified_pdf":
        warnings.append(f"{name} comes from a textbook; verification status '{r['verify_status']}'"
                        + (f" ({r['note']})" if isinstance(r["note"], str) and r["note"].strip() else ""))
    if not 0 < props["nu12"] < 0.5 or any(v <= 0 for v in props.values()):
        raise ValueError(f"implausible properties for {name}: {props}")
    return props, source_text(r), warnings


if __name__ == "__main__":
    tests = [("IM7/8552", "IM7/8552 laminate"), ("Hexcel 8552 / IM7", "Hexcel 8552 / IM7 prepreg"),
             ("IM7", "IM7 carbon/epoxy"), ("T800S/3900-2", "T800S/3900-2 carbon/epoxy"),
             ("", "Cytec Cycom 5250-5 / T650 unitape"), ("T40-800/5215", "T40-800/5215 laminate"),
             ("AS4/3501-6", "AS4/3501-6, 6 plies"), ("Kevlar 49/epoxy", "Kevlar 49/epoxy laminate"),
             ("Kevlar/epoxy", "Kevlar/epoxy [0/90]s"), ("E-glass/epoxy", "E-glass/epoxy [0/90/0]"),
             ("S2-glass/epoxy", "S2-glass/epoxy"), ("S2-glass/BT250E-6", "S2-glass/BT250E-6, [0/90/0]"),
             ("IM7/8552", "IM8/8552 typo"), ("", "Carbon/epoxy laminate [0/45/-45/90]s")]
    for nm, tx in tests:
        print(f"{nm!r:22} | {tx!r:40} -> {resolve(nm, tx)}")
