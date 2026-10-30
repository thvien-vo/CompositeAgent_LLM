"""
Independent check of figures_v2, for every figure and both versions. Shares no code with the plotting scripts: the
sources are read again here, and the final PDF and PNG files are read back.

  1 text collisions (from the reports of the two plotting scripts)
  2 colours: every stroke, fill and text colour read from the PDF; no opacity below 1
  3 fonts read from the PDF: Computer Modern only, embedded, no Type 3
  4 font sizes read from the PDF
  5 numbers: every number printed in each PDF against the sources; every table cell; Python against MATLAB, curve by curve
  6 pip freeze of the venv used by the presentation, before and after (SKIPPED without its baseline file)
  7 git status against the state at the start (SKIPPED without its baseline file)
  and: files, dimensions, no titles

Run in a VS Code terminal at D:\\CompositeAgent:
    venv_fig\\Scripts\\activate
    python deliverables\\figures_v2\\verify_numbers.py
"""
from __future__ import annotations

import collections
import csv
import json
import math
import os
import re
import statistics
import subprocess
import sys

import pymupdf
from PIL import Image

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RES = os.path.join(ROOT, "deliverables", "optimization", "results")
MINUS = "\u2212"
PALETTE = {"#000000", "#0047ab", "#d55e00", "#009e73", "#6a1b9a", "#c2185b", "#ffffff"}
PAPER = ["Fig1_workflow", "Fig2_leriche_haftka", "Fig3_pareto", "Fig4_qi_comparison", "Fig5_algorithms",
         "FigS1_pareto_all_C1_C4", "FigS1_pareto_all_C5_C8", "FigS2_convergence_t0125_p1", "FigS2_convergence_t0125_p2",
         "FigS3_convergence_t0183_p1", "FigS3_convergence_t0183_p2", "FigS4_best_so_far_C4", "FigS5_ritz_before_after"]
SLIDES = ["Fig1_workflow", "Fig2_leriche_haftka", "Fig3_pareto", "Fig4_qi_comparison_t0125", "Fig4_qi_comparison_t0183",
          "Fig5_algorithms_t0125", "Fig5_algorithms_t0183"]
WIDTHS = {"Fig2_leriche_haftka": 140.0}
TK = ("t0125", "t0183")
ALGOS = ("ga", "nsga2", "ga_ls")

RESULT = collections.defaultdict(lambda: collections.defaultdict(list))   # check -> (figure, version) -> problems
COUNT = collections.Counter()
SKIPPED = set()                # checks without a baseline file, for example in a fresh clone


def note(check, fig, version, passed, message=""):
    COUNT[check] += 1
    RESULT[check][(fig, version)]
    if not passed:
        RESULT[check][(fig, version)].append(message)


def rows_of(name):
    with open(os.path.join(RES, *name.split("/")), encoding="utf-8") as f:
        return list(csv.DictReader(f))


CASES = [r for r in rows_of("cases_summary.csv") if r["model"] == "ritz_full"]
OLD = [r for r in rows_of("before_ritz/cases_summary.csv") if r["model"] == "closed_form"]
RUNS = [r for r in rows_of("runs.csv") if r["model"] == "ritz_full"]
LH = rows_of("leriche_haftka_summary.csv")
SHEAR = rows_of("shear_both_signs.csv")
with open(os.path.join(RES, "fronts.json"), encoding="utf-8") as f:
    FRONTS = json.load(f)
with open(os.path.join(RES, "run_cases_meta.json"), encoding="utf-8") as f:
    META = json.load(f)
NMAX = max(q["n"] for v in FRONTS.values() for q in v["bounds"])
IDS = list(dict.fromkeys(r["case"] for r in CASES))


def case(c, tk, table=None):
    return next(r for r in (table or CASES) if r["case"] == c and r["thickness"] == tk)


def half_up(v):
    return int(math.floor(float(v) + 0.5))


def done(r):
    return r["exact_status"] in ("optimal", "infeasible")


def feas(r):
    return r["feasible"] == "True"


def count_of(r, m):
    return int(float(r[f"{m}_success"] if done(r) else r[f"{m}_reach_reference"]))


# ------------------------------------------------------------------------------------- numbers expected
def expected(name):
    """Numbers that must appear in the PDF of one figure, with their multiplicity, other than axis ticks."""
    c = collections.Counter()
    t = re.search(r"t0(125|183)", name)
    if name.startswith("Fig4"):
        for tk in TK:
            for i in IDS:
                r = case(i, tk)
                c[r["qi_n"]] += 1
                c[r["n_opt"] if feas(r) else str(NMAX)] += 1
                if r["mass_reduction_pct"]:
                    c[f"{half_up(r['mass_reduction_pct'])}"] += 1
            c[str(NMAX)] += 1          # the ply limit
    elif name.startswith("Fig5"):
        for tk in TK:
            for i in IDS:
                for m in ALGOS:
                    c[str(count_of(case(i, tk), m))] += 1
        c[str(len(META["seeds"]))] += 2        # the axis titles
    elif name.startswith("FigS5"):
        for tk in TK:
            for i in IDS:
                r, o = case(i, tk), case(i, tk, OLD)
                if feas(r):
                    c[r["n_opt"]] += 1
                else:
                    c[str(NMAX)] += 1
                if feas(o):
                    c[o["n_opt"]] += 1
    return c


TICKS = {"Fig2_leriche_haftka": ["100", "300", "1000", "3000", "6000", "0", "25", "50", "75", "100"]}
for nm in PAPER:
    if "pareto" in nm:
        TICKS[nm] = ["10", "20", "30", "40", "50", "60"] * 2 + ["0", "2", "4", "6", "8"] * 2
    if "convergence" in nm:
        TICKS[nm] = ["30", "100", "300", "1000", "3000", "10000"] * 2 + ["0", "25", "50", "75", "100"] * 2
TICKS["Fig4_qi_comparison"] = ["0", "25", "50", "75", "100"]
TICKS["Fig5_algorithms"] = ["0", "5", "10", "15", "20"] * 2
TICKS["FigS4_best_so_far_C4"] = ["30", "100", "300", "1000", "3000", "10000"] * 3 + ["22", "23", "24", "25", "26"]
TICKS["FigS5_ritz_before_after"] = ["0", "20", "40", "60"]
EXTRA = {"FigS4_best_so_far_C4": ["25", "75"], "Fig4_qi_comparison": ["1.5"]}
for nm in PAPER:
    if "pareto" in nm:
        EXTRA[nm] = ["1.5"] * 4


def pdf_numbers(page):
    """Whole numbers and decimals printed on a page, without case names and the thickness labels."""
    text = page.get_text("text")
    text = re.sub(r"\bC[1-8]\b", " ", text)
    # the decimal point of a formula comes back as a colon from the MATLAB fonts
    text = re.sub(r"(\d)\s*[.:]\s*(\d)", r"\1.\2", text)
    text = re.sub(r"(?<![\d.])0\.1(?:25|83)\s*(?:mm)?", " ", text)
    return re.findall(r"(?<![A-Za-z\d.])\d+(?:\.\d+)?", text)


def check_numbers(name, version, page):
    got = collections.Counter(pdf_numbers(page))
    want = expected(name) + collections.Counter(TICKS.get(name, [])) + collections.Counter(EXTRA.get(name, []))
    if version == "MATLAB" and name == "Fig4_qi_comparison":
        want["6"] += 1       # the glyph of the sign "greater or equal" in the MATLAB math font comes back as a 6
    diff_extra = got - want
    diff_miss = want - got
    note(5, name, version, not diff_extra and not diff_miss, f"extra {dict(diff_extra)} missing {dict(diff_miss)}")


# --------------------------------------------------------------------------------------- PDF reading
def rgb_hex(c):
    return "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in c)


def check_pdf(name, version, path):
    doc = pymupdf.open(path)
    page = doc[0]
    w_mm = page.rect.width / 72 * 25.4
    note("files", name, version, abs(w_mm - WIDTHS.get(name, 190.0)) < 0.3, f"page width {w_mm:.2f} mm")
    note("files", name, version, page.rect.height / 72 * 25.4 <= 240, "page taller than 240 mm")
    fonts = page.get_fonts(full=True)
    note(3, name, version, bool(fonts), "no fonts")
    for f in fonts:
        base = f[3].split("+")[-1]
        note(3, name, version, f[2] != "Type3" and "Type 3" not in f[2], f"Type 3: {base}")
        note(3, name, version, f[1] not in ("n/a", ""), f"not embedded: {base}")
        note(3, name, version, re.fullmatch(r"(CM[A-Z]+\d+|SFRM\d+|mw[ab]_cm[a-z]+\d+)", base) is not None, f"font {base}")
    colours = set()
    for d in page.get_drawings():
        for key, op in (("color", "stroke_opacity"), ("fill", "fill_opacity")):
            c = d.get(key)
            if c is not None:
                colours.add(rgb_hex(c))
                o = d.get(op)
                note(2, name, version, o is None or o >= 0.999, f"opacity {o}")
    for c in colours:
        note(2, name, version, c in PALETTE, f"colour {c}")
    sizes = collections.Counter()
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                if not s["text"].strip():
                    continue
                hexc = "#%06x" % s["color"]
                white_ok = name.startswith("Fig1")
                note(2, name, version, hexc == "#000000" or (white_ok and hexc == "#ffffff"), f"text colour {hexc}: {s['text']}")
                size = s["size"]
                sizes[round(size, 1)] += 1
                if size < 6.9:
                    note(4, name, version, size >= 5.9 and s["text"].strip() in ("min", "cr", "ns", "\u2217", "*"),
                         f"{size:.2f} pt: {s['text']}")
                else:
                    note(4, name, version, True)
    check_numbers(name, version, page)
    doc.close()
    return sizes


def check_png(path, name, version, dpi, width_mm):
    with Image.open(path) as im:
        w, h = im.size
        note("files", name, version, abs(w - width_mm / 25.4 * dpi) < 13, f"PNG width {w} px")
        note("files", name, version, abs(im.info.get("dpi", (0, 0))[0] - dpi) < 1, f"PNG dpi {im.info.get('dpi')}")
        return w, h


# ----------------------------------------------------------------------------------- reports and series
def load_report(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {(r["name"], r["mode"]): r for r in data}


def aslist(v):
    return v if isinstance(v, list) else [v]


def check_series(py, mt):
    for key, r in py.items():
        name, mode = key
        if key not in mt:
            note(5, name, "MATLAB", False, "no MATLAB report")
            continue
        m = mt[key]
        a = collections.defaultdict(list)
        b = collections.defaultdict(list)
        for s in r["series"]:
            a[s["label"]].append((aslist(s["x"]), aslist(s["y"])))
        for s in aslist(m["series"]):
            lab = {"bar GALS": "bar GA + LS", "bar NSGA": "bar NSGA-II"}.get(s["label"], s["label"])
            b[lab].append((aslist(s["x"]), aslist(s["y"])))
        note(5, name, "both", set(a) == set(b), f"series differ: {sorted(set(a) ^ set(b))[:6]}")
        for lab in a:
            if lab not in b or len(a[lab]) != len(b[lab]):
                note(5, name, "both", False, f"series {lab}: {len(a[lab])} against {len(b.get(lab, []))}")
                continue
            for (x1, y1), (x2, y2) in zip(sorted(a[lab]), sorted(b[lab])):
                same = len(x1) == len(x2) and all(abs(p - q) <= 1e-9 * max(1, abs(p)) for p, q in zip(x1 + y1, x2 + y2))
                note(5, name, "both", same, f"values of series {lab} differ")
        t1 = sorted(re.sub(r"\s+", " ", t.replace("{}", "")) for t in r["text"])
        t2 = sorted(re.sub(r"\s+", " ", t.replace("{}", "")) for t in aslist(m["text"]))
        note(5, name, "both", t1 == t2, f"text differs: {sorted(set(t1) ^ set(t2))[:4]}")


# ------------------------------------------------------------------------------------- sources, tables
def check_sources():
    fig = "sources"
    for r in CASES:
        for m in ALGOS:
            rr = [x for x in RUNS if x["case"] == r["case"] and x["tkey"] == r["thickness"] and x["method"] == m]
            good = [x for x in rr if int(x["n_plies"]) == int(r["n_opt"]) and float(x["margin"]) >= float(r["margin_opt"]) * (1 - 1e-9)]
            note(5, fig, "data", len(good) == int(r[f"{m}_reach_reference"]), f"{r['case']} {r['thickness']} {m}: reach")
            hits = [float(x["hit_evals"]) for x in good if x["hit_evals"] not in ("", "None")]
            med = r[f"{m}_evals_to_hit_median"]
            note(5, fig, "data", (not hits and not med) or (hits and abs(statistics.median(hits) - float(med)) < 1e-9),
                 f"{r['case']} {r['thickness']} {m}: median")
    with open(os.path.join(RES, "tables.md"), encoding="utf-8") as f:
        md = f.read()
    for tk in TK:
        t2 = md.split(f"## T2-{tk}.")[1].split("##")[0]
        for r in [x for x in CASES if x["thickness"] == tk]:
            c = [x.strip() for x in next(v for v in t2.splitlines() if v.startswith(f"| {r['case']} ")).strip("| ").split(" | ")]
            note(5, fig, "data", c[3] == r["n_opt"] and c[-2] == r["qi_n"], f"tables.md {r['case']} {tk}")
    t6 = md.split("## T6.")[1].split("##")[0]
    for r in LH:
        c = [x.strip() for x in next(v for v in t6.splitlines() if v.startswith(f"| {r['case']} ")).strip("| ").split(" | ")]
        note(5, fig, "data", c[4] == "%.2f" % float(r["lambda_exhaustive"]) and c[6] == r["lambda_paper"], f"tables.md {r['case']}")
    for q in SHEAR:
        r = case(q["case"], q["thickness"])
        note(5, fig, "data", q["one_n"] == r["n_opt"] and q["one_qi_n"] == r["qi_n"], f"shear {q['case']}")


def read_table(name):
    with open(os.path.join(HERE, "tables", f"{name}.csv"), encoding="utf-8-sig", newline="") as f:
        data = list(csv.reader(f))
    with open(os.path.join(HERE, "tables", f"{name}.tex"), encoding="utf-8") as f:
        return data[1:], f.read()


def sci(v):
    v = float(v)
    if v == 0:
        return "0"
    e = int(math.floor(math.log10(abs(v))))
    return ("%s%.1f \u00d7 10^%d" % (MINUS if v < 0 else "", abs(v) / 10 ** e, e))


def check_tables():
    rows, _ = read_table("Table_load_cases")
    for row in rows:
        r = case(row[0], "t0125")
        note(5, "Table_load_cases", "table", row[2:5] == [sci(r["Nx"]), sci(r["Ny"]), sci(r["Nxy"])], str(row))
    rows, _ = read_table("Table_leriche_haftka")
    for row in rows:
        r = next(x for x in LH if x["case"] == row[0])
        note(5, "Table_leriche_haftka", "table", row[3] == "%.2f" % float(r["lambda_paper"])
             and row[4] == "%.2f" % float(r["lambda_exhaustive"]) and row[5] == "%+.5f%%" % (float(r["rel_diff_vs_paper"]) * 100), str(row))
    rows, tex = read_table("Table_convergence")
    for row in rows:
        i = 2
        for tk in TK:
            r = case(row[0], tk)
            mark = ("" if done(r) else "\u2021") + ("" if feas(r) else "\u00a7")
            for m in ALGOS:
                med = r[f"{m}_evals_to_hit_median"]
                want = str(half_up(med)) if med else ("n/a" if not done(r) else "\u2013")
                note(5, "Table_convergence", "table", row[i] == f"{count_of(r, m)}/{r[m + '_runs']}{mark}" and row[i + 1] == want,
                     f"{row[0]} {tk} {m}")
                i += 2
    rows, _ = read_table("Table_shear_directions")
    for row in rows:
        tk = "t0125" if row[1] == "0.125" else "t0183"
        q = next(x for x in SHEAR if x["case"] == row[0] and x["thickness"] == tk)
        note(5, "Table_shear_directions", "table", row[3] == "%.4f" % float(q["one_margin"]) and row[4] == "%.4f" % float(q["one_margin_reversed"])
             and row[7] == "%.4f" % float(q["both_margin"]), str(row))


def check_captions():
    with open(os.path.join(HERE, "_captions.json"), encoding="utf-8") as f:
        caps = json.load(f)
    last = {max(q["n"] for q in FRONTS[f"{c}|{tk}|ritz_full"]["exact_per_n"] if q["max_margin"] is not None)
            for c in ("C4", "C5", "C7") for tk in TK}
    c5, c8 = case("C5", "t0125"), case("C8", "t0125")
    allowed = {"0.125", "0.183", "1.5", "8", str(NMAX), str(len(META["seeds"])), str(META["budget"]), LH[0]["ga_runs"],
               "%.2f" % float(c8["margin_opt"])}
    allowed |= {str(x) for x in last} | {c5[f"{m}_reach_reference"] for m in ALGOS}
    for fig, text in caps.items():
        text = re.sub(r"\bC[1-8]\b|Fig\. 3|D_(?:16|26)|\bTable_\w+|\[0/\u00b145/90\]|25th and 75th", " ", text)
        for tok in re.findall(r"(?<![\w.])\d+(?:\.\d+)?", text):
            note("captions", fig, "text", tok in allowed, f"'{tok}' is not a source value")


def matrix():
    out = ["", f"{'figure':46s}{'version':9s}collisions colours fonts sizes numbers"]
    for name, mode in [(n, "paper") for n in PAPER] + [(n, "slide") for n in SLIDES]:
        tag = f"{name} [{mode}]"
        for version in ("Python", "MATLAB"):
            cells = []
            for k in (1, 2, 3, 4, 5):
                keys = [(tag, version)]
                if mode == "paper":
                    keys += [(name, version), (name, "both")]
                elif k == 5:
                    keys = [(name, "both")]
                elif k == 3:           # slides are PNG files only
                    cells.append("-")
                    continue
                seen = [q for q in keys if q in RESULT[k]]
                bad = sum(len(RESULT[k][q]) for q in seen)
                cells.append("-" if not seen else ("ok" if not bad else "FAIL"))
            out.append(f"{tag:46s}{version:9s}" + "".join(f"{c:<{w}s}" for c, w in zip(cells, (11, 8, 6, 6, 7))))
    return out


# ------------------------------------------------------------------------------------- pip, git, words
def baseline(name):
    path = os.path.join(HERE, name)
    return path if os.path.exists(path) else None


def check_environment():
    path = baseline("_pip_freeze_venv_before.txt")
    if path is None:
        SKIPPED.add(6)
    else:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        now = subprocess.run([os.path.join(ROOT, "venv", "Scripts", "python.exe"), "-m", "pip", "freeze"], capture_output=True,
                             text=True, env=env)
        with open(path, encoding="utf-8-sig") as f:
            before = f.read().split()
        note(6, "venv", "presentation", before == now.stdout.split(), "pip freeze changed")
        with open(os.path.join(HERE, "_pip_freeze_venv_after.txt"), "w", encoding="utf-8") as f:
            f.write(now.stdout)
    path = baseline("_git_status_before.txt")
    if path is None:
        SKIPPED.add(7)
        return
    status = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
    status = {s.strip() for s in status if s.strip()}
    with open(path, encoding="utf-8-sig") as f:
        base = {s.strip() for s in f if s.strip()}
    new = {s for s in status - base if "__pycache__" not in s}
    note(7, "git", "repository", new <= {"?? deliverables/figures_v2/"}, f"unexpected: {sorted(new)}")
    diff = subprocess.run(["git", "diff", "--stat"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    note(7, "git", "repository", diff == "", f"tracked files changed: {diff}")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    reports = {"Python": load_report(os.path.join(HERE, "python", "_report_python.json")),
               "MATLAB": load_report(os.path.join(HERE, "matlab", "_report_matlab.json"))}
    for version, folder in (("Python", "python"), ("MATLAB", "matlab")):
        rep = reports[version]
        for (name, mode), r in sorted(rep.items()):
            cols = aslist(r["collisions"]) if r["collisions"] else []
            note(1, f"{name} [{mode}]", version, not cols, "; ".join(cols[:4]))
            scan = aslist(r["colours"]) if r["colours"] else []
            note(2, f"{name} [{mode}]", version, not scan, "; ".join(scan[:4]))
            note("titles", name, version, not r["titles"], "title in the figure")
            note(4, f"{name} [{mode}]", version, r["fonts"]["min_size"] >= 7, f"size {r['fonts']['min_size']}")
        for name in PAPER:
            pdf = os.path.join(HERE, folder, "pdf", f"{name}.pdf")
            png = os.path.join(HERE, folder, "png", f"{name}.png")
            note("files", name, version, os.path.exists(pdf) and os.path.exists(png), "missing")
            check_pdf(name, version, pdf)
            check_png(png, name, version, 1000, WIDTHS.get(name, 190.0))
        for name in SLIDES:
            png = os.path.join(HERE, folder, "slides", f"{name}_slide.png")
            note("files", name, version, os.path.exists(png), "missing slide")
            w, h = check_png(png, f"{name} [slide]", version, 300, 338.67)
            note("files", name, version, abs(w / h - 16 / 9) < 0.01, f"ratio {w}x{h}")
    check_series(reports["Python"], reports["MATLAB"])
    check_sources()
    check_tables()
    check_captions()
    check_environment()
    lines = []
    titles = {1: "Text collisions", 2: "Colours", 3: "Fonts", 4: "Font sizes", 5: "Numbers", 6: "pip freeze of the venv",
              7: "git status", "files": "Files and dimensions", "titles": "No titles",
              "captions": "Numbers in captions"}
    bad = 0
    for k in (1, 2, 3, 4, 5, 6, 7, "files", "titles", "captions"):
        n = sum(len(v) for v in RESULT[k].values())
        bad += n
        lines.append(f"{titles[k]:26s} SKIPPED (no baseline)" if k in SKIPPED else f"{titles[k]:26s} {COUNT[k]:6d} checks  {n} problems")
    lines.append("")
    for k in (1, 2, 3, 4, 5, 6, 7, "files", "titles", "captions"):
        for (fig, version), msgs in sorted(RESULT[k].items(), key=str):
            for m in msgs[:5]:
                lines.append(f"[{titles[k]}] {fig} {version}: {m}")
    if not bad:
        lines.append("No problems.")
    lines += matrix()
    text = "\n".join(lines)
    print(text)
    with open(os.path.join(HERE, "_verification.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
