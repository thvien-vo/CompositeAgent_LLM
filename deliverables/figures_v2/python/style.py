"""
Shared style and page layer of the Python figures. To change journal, edit this file only.
A Page has data axes at fixed positions in mm and one transparent overlay in mm that holds all text, so every figure is
laid out in the same coordinates as the MATLAB version (matlab\\style_setup.m, matlab\\make_all.m).
Target: Elsevier, Composite Structures.
"""
from __future__ import annotations

import io
import os

import matplotlib

matplotlib.use("Agg")
import pymupdf as fitz  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import scienceplots  # noqa: E402,F401
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle  # noqa: E402
from matplotlib.text import Text  # noqa: E402

MM = 1.0 / 25.4
PT_MM = 25.4 / 72.0
CAP = 0.68                     # height of a capital letter or digit, in font sizes
PAPER_W = {"single": 90.0, "onehalf": 140.0, "double": 190.0}
SLIDE_W, SLIDE_H = 338.67, 190.5
DPI_PAPER, DPI_SLIDE = 1000, 300

BLACK, COBALT, ORANGE = "#000000", "#0047AB", "#D55E00"
GREEN, PURPLE, MAGENTA, WHITE = "#009E73", "#6A1B9A", "#C2185B", "#FFFFFF"
PALETTE = {BLACK, COBALT, ORANGE, GREEN, PURPLE, MAGENTA}
ROLE = {"qi": BLACK, "opt": COBALT, "GA": COBALT, "NSGA-II": ORANGE, "GA + LS": GREEN, "t0125": ORANGE, "t0183": PURPLE,
        "seed": MAGENTA, "exact": BLACK, "LH-A": COBALT, "LH-B": ORANGE, "LH-C": GREEN, "LH-D": MAGENTA}
ALGO_LS = {"GA": "--", "NSGA-II": "-.", "GA + LS": "-"}
ALGO_MARK = {"GA": "s", "NSGA-II": "D", "GA + LS": "o"}
ALGO_NAME = {"GA": "GA", "NSGA-II": "NSGA-II", "GA + LS": "GA + local search"}
THICK_MARK = {"t0125": "o", "t0183": "s"}
THICK_TEXT = {"t0125": r"$t = 0.125\,\mathrm{mm}$", "t0183": r"$t = 0.183\,\mathrm{mm}$"}
CASE_MARK = {"LH-A": "o", "LH-B": "s", "LH-C": "^", "LH-D": "D"}
BLOCK = {"llm": COBALT, "data": GREEN, "comp": ORANGE, "check": PURPLE}
BLOCK_NAME = {"llm": "LLM", "data": "Data and ML", "comp": "Computation", "check": "Check"}


class Style:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def mm(self, pt):
        return pt * PT_MM


PAPER = Style(mode="paper", label=9, tick=8, legend=8, barnum=7, panel=10, name=9, block=8, lw=1.5, thin=0.8, axes=0.7,
              ticklen=1.2, pad=0.9, ms=4.0, ms_small=2.6, mew=0.5, sample=7.0, dpi=DPI_PAPER, ref=9, ref_lw=1.3, corner=1.2)
SLIDE = Style(mode="slide", label=20, tick=18, legend=18, barnum=18, panel=20, name=18, block=18, lw=3.0, thin=1.6,
              axes=1.4, ticklen=2.4, pad=1.8, ms=9.0, ms_small=6.0, mew=1.0, sample=14.0, dpi=DPI_SLIDE, ref=18, ref_lw=2.6,
              corner=2.4)


def use_style():
    plt.style.use(["science"])
    plt.rcParams.update({
        "text.usetex": True,
        "font.family": "serif",
        "font.serif": ["Computer Modern Roman"],
        "text.latex.preamble": r"\usepackage{amsmath,amssymb,siunitx}",
        "axes.grid": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.top": False,
        "ytick.right": False,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.minor.visible": False,
        "ytick.minor.visible": False,
        "lines.solid_capstyle": "butt",
        "lines.dash_capstyle": "butt",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.bbox": "standard",
        "pdf.fonttype": 42,
    })


def overlaps(a, b, tol=0.05):
    return a[0] < b[2] - tol and b[0] < a[2] - tol and a[1] < b[3] - tol and b[1] < a[3] - tol


def seg_hits_box(p, q, box):
    """Liang-Barsky: does the segment p-q enter the box (x0, y0, x1, y1)?"""
    t0, t1 = 0.0, 1.0
    dx, dy = q[0] - p[0], q[1] - p[1]
    for d, a, lo, hi in ((dx, p[0], box[0], box[2]), (dy, p[1], box[1], box[3])):
        if abs(d) < 1e-12:
            if a <= lo or a >= hi:
                return False
            continue
        u, v = (lo - a) / d, (hi - a) / d
        if u > v:
            u, v = v, u
        t0, t1 = max(t0, u), min(t1, v)
        if t0 >= t1:
            return False
    return True


def clip_to_box(xy, box):
    """Keeps the parts of a polyline inside box, as a list of segments."""
    out = []
    for p, q in zip(xy[:-1], xy[1:]):
        if not (np.isfinite(p).all() and np.isfinite(q).all()):
            continue
        t0, t1 = 0.0, 1.0
        dx, dy = q[0] - p[0], q[1] - p[1]
        keep = True
        for d, a, lo, hi in ((dx, p[0], box[0], box[2]), (dy, p[1], box[1], box[3])):
            if abs(d) < 1e-12:
                keep = keep and lo <= a <= hi
                continue
            u, v = (lo - a) / d, (hi - a) / d
            if u > v:
                u, v = v, u
            t0, t1 = max(t0, u), min(t1, v)
        if keep and t0 <= t1:
            out.append(((p[0] + t0 * dx, p[1] + t0 * dy), (p[0] + t1 * dx, p[1] + t1 * dy)))
    return out


class Page:
    def __init__(self, name, W, H, s):
        self.name, self.W, self.H, self.s = name, W, H, s
        self.fig = plt.figure(figsize=(W * MM, H * MM))
        self.ov = self.fig.add_axes([0, 0, 1, 1], zorder=20)
        self.ov.set_xlim(0, W)
        self.ov.set_ylim(0, H)
        self.ov.set_axis_off()
        self.ov.patch.set_visible(False)
        self.texts, self.segs, self.rects, self.marks, self.blocks, self.series = [], [], [], [], [], []

    # ------------------------------------------------------------------------------ axes and coordinates
    def axes(self, box, xlim, ylim, xlog=False, ylog=False, xticks=(), yticks=(), xlabels=None, ylabels=None):
        x, y, w, h = box
        s = self.s
        ax = self.fig.add_axes([x / self.W, y / self.H, w / self.W, h / self.H], zorder=5)
        ax.mm_box, ax.xl, ax.yl, ax.xlog, ax.ylog = box, xlim, ylim, xlog, ylog
        ax.set_xscale("log" if xlog else "linear")
        ax.set_yscale("log" if ylog else "linear")
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        ax.set_xticks(list(xticks))
        ax.set_yticks(list(yticks))
        ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        ax.tick_params(labelbottom=False, labelleft=False, length=s.ticklen / PT_MM, width=s.axes, color=BLACK)
        for side in ("left", "bottom"):
            ax.spines[side].set_linewidth(s.axes)
            ax.spines[side].set_color(BLACK)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        self.segs.append(((x, y), (x + w, y)))
        self.segs.append(((x, y), (x, y + h)))
        for v, lab in zip(xticks, xlabels if xlabels is not None else [None] * len(xticks)):
            if lab is not None:
                self.text(self.X(ax, v), y - s.ticklen - s.pad, lab, s.tick, va="top")
        for v, lab in zip(yticks, ylabels if ylabels is not None else [None] * len(yticks)):
            if lab is not None:
                self.text(x - s.ticklen - s.pad, self.Y(ax, v), lab, s.tick, ha="right")
        return ax

    def X(self, ax, v):
        x, _, w, _ = ax.mm_box
        lo, hi = ax.xl
        f = (np.log10(v) - np.log10(lo)) / (np.log10(hi) - np.log10(lo)) if ax.xlog else (np.asarray(v) - lo) / (hi - lo)
        return x + f * w

    def Y(self, ax, v):
        _, y, _, h = ax.mm_box
        lo, hi = ax.yl
        f = (np.log10(v) - np.log10(lo)) / (np.log10(hi) - np.log10(lo)) if ax.ylog else (np.asarray(v) - lo) / (hi - lo)
        return y + f * h

    def box_of(self, ax):
        x, y, w, h = ax.mm_box
        return (x, y, x + w, y + h)

    # ------------------------------------------------------------------------------------------- text
    def text(self, x, y, txt, size, ha="center", va="center", rot=0, color=BLACK, inside=None):
        """Every label is anchored on its baseline, which both versions place in the same way."""
        if va != "baseline":
            y -= {"center": 0.5, "top": 1.0, "bottom": 0.0}[va] * CAP * size * PT_MM
        t = self.ov.text(x, y, txt, fontsize=size, ha=ha, va="baseline", rotation=rot, rotation_mode="anchor", color=color,
                         zorder=30)
        t.inside = inside
        self.texts.append(t)
        return t

    def xlabel(self, ax, txt, y):
        x0, _, w, _ = ax.mm_box
        self.text(x0 + w / 2, y, txt, self.s.label, va="bottom")

    def ylabel(self, ax, txt, x):
        _, y0, _, h = ax.mm_box
        self.text(x + 0.5 * CAP * self.s.label * PT_MM, y0 + h / 2, txt, self.s.label, va="baseline", rot=90)

    def panel(self, ax, letter, name=""):
        s = self.s
        x, y, _, h = ax.mm_box
        yt = y + h + s.pad * 1.3
        self.text(x, yt, rf"\textbf{{({letter})}}", s.panel, ha="left", va="baseline")
        if name:
            self.text(x + s.mm(s.panel) * 2.1, yt, name, s.name, ha="left", va="baseline")

    # --------------------------------------------------------------------------------------- data marks
    def line(self, ax, x, y, role, ls="-", lw=None, marker=None, ms=None, mfc=None, mec=None, mew=None, every=None,
             label="", zorder=4):
        s = self.s
        color = ROLE[role]
        x, y = np.asarray(x, float), np.asarray(y, float)
        ln, = ax.plot(x, y, ls=ls, lw=lw or s.lw, color=color, marker=marker, ms=ms or s.ms, mfc=mfc or color,
                      mec=mec or color, mew=mew if mew is not None else s.mew, markevery=every, zorder=zorder,
                      solid_joinstyle="miter", clip_on=True)
        xy = np.column_stack([self.X(ax, x), self.Y(ax, y)])
        box = self.box_of(ax)
        if ls not in ("", "None"):
            self.segs += clip_to_box(xy, box)
        if marker:
            idx = range(len(x)) if every is None else range(every[0], len(x), every[1])
            r = (ms or s.ms) * PT_MM / 2
            for i in idx:
                if box[0] <= xy[i, 0] <= box[2] and box[1] <= xy[i, 1] <= box[3]:
                    self.marks.append((xy[i, 0], xy[i, 1], r))
        self.series.append({"label": label or role, "x": [float(v) for v in x], "y": [float(v) for v in y]})
        return ln

    def hline(self, ax, y, role="exact", ls="--", lw=None):
        lw = lw or self.s.ref_lw
        ln, = ax.plot(ax.xl, [y, y], ls=ls, lw=lw, color=ROLE[role], zorder=3)
        ym = float(self.Y(ax, y))
        self.segs.append(((ax.mm_box[0], ym), (ax.mm_box[0] + ax.mm_box[2], ym)))
        return ln

    def bar(self, ax, x0, x1, h, role, mark=None):
        """Filled column; mark is a white marker inside the column, for reading in black and white."""
        ax.add_patch(Rectangle((x0, 0), x1 - x0, h, fc=ROLE[role], ec="none", lw=0, zorder=2))
        self.rects.append((float(self.X(ax, x0)), float(self.Y(ax, 0)), float(self.X(ax, x1)), float(self.Y(ax, h))))
        self.series.append({"label": f"bar {role}", "x": [float(x0), float(x1)], "y": [0.0, float(h)]})
        y_mm = float(self.Y(ax, 0)) + 1.5 * self.s.mm(self.s.ms)
        if mark and float(self.Y(ax, h)) - float(self.Y(ax, 0)) > 3.0 * self.s.mm(self.s.ms):
            self.ov.plot([self.X(ax, (x0 + x1) / 2)], [y_mm], ls="", marker=mark, ms=self.s.ms, color=WHITE, mfc=WHITE,
                         mec=WHITE, mew=0, zorder=15)

    def hatch_bar(self, ax, x0, x1, h, role="opt"):
        """Open column with 45 degree lines, drawn in mm so that it is the same in both versions."""
        s = self.s
        ax.add_patch(Rectangle((x0, 0), x1 - x0, h, fc="none", ec=ROLE[role], lw=0.8 if s.mode == "paper" else 1.6,
                               zorder=2))
        xa, ya, xb, yb = (float(self.X(ax, x0)), float(self.Y(ax, 0)), float(self.X(ax, x1)), float(self.Y(ax, h)))
        step = 1.5 if s.mode == "paper" else 3.0
        c = xa - (yb - ya)
        while c < xb:
            seg = clip_to_box(np.array([[c, ya], [c + (yb - ya), yb]]), (xa, ya, xb, yb))
            for p, q in seg:
                self.ov.plot([p[0], q[0]], [p[1], q[1]], color=ROLE[role], lw=s.thin * 0.75, solid_capstyle="butt", zorder=15)
            c += step
        self.rects.append((xa, ya, xb, yb))
        self.series.append({"label": f"open bar {role}", "x": [float(x0), float(x1)], "y": [0.0, float(h)]})

    # -------------------------------------------------------------------------- legend strip, blocks, arrows
    def key_line(self, x, y, role, label, ls="-", marker=None, mfc=None, mec=None, ms=None, mew=None, lw=None):
        s = self.s
        c = ROLE[role]
        drawn = ls not in ("", "None")
        wide = s.sample if drawn else s.sample * 0.45
        if drawn:
            self.ov.plot([x, x + wide], [y, y], ls=ls, lw=lw or s.lw, color=c, zorder=15)
        if marker:
            self.ov.plot([x + wide / 2], [y], ls="", marker=marker, ms=ms or s.ms, color=c, mfc=mfc or c, mec=mec or c,
                         mew=mew if mew is not None else s.mew, zorder=16)
        self.text(x + wide + 1.2 * s.pad, y, label, s.legend, ha="left", va="center")

    def key_bar(self, x, y, role, label, mark=None, hatch=False):
        s = self.s
        w, h = s.sample * 0.8, s.mm(s.legend) * 0.95
        if hatch:
            self.ov.add_patch(Rectangle((x, y - h / 2), w, h, fc="none", ec=ROLE[role], lw=0.8 if s.mode == "paper" else 1.6,
                                        zorder=15))
            step = 1.5 if s.mode == "paper" else 3.0
            c = x - h
            while c < x + w:
                for p, q in clip_to_box(np.array([[c, y - h / 2], [c + h, y + h / 2]]), (x, y - h / 2, x + w, y + h / 2)):
                    self.ov.plot([p[0], q[0]], [p[1], q[1]], color=ROLE[role], lw=s.thin * 0.75, zorder=15)
                c += step
        else:
            self.ov.add_patch(Rectangle((x, y - h / 2), w, h, fc=ROLE[role], ec="none", lw=0, zorder=15))
            if mark:
                self.ov.plot([x + w / 2], [y], ls="", marker=mark, ms=s.ms * 0.9, color=WHITE, mfc=WHITE, mec=WHITE, mew=0,
                             zorder=16)
        self.text(x + w + 1.2 * s.pad, y, label, s.legend, ha="left", va="center")

    def block(self, x, y, w, h, lines, kind):
        s = self.s
        fc = BLOCK.get(kind, WHITE)
        self.ov.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={s.corner}",
                                         fc=fc, ec=BLACK, lw=0.8 if s.mode == "paper" else 1.6, zorder=10))
        box = (x, y, x + w, y + h)
        self.blocks.append(box)
        color = WHITE if kind in ("llm", "check") else BLACK
        lead = s.mm(s.block) * 1.22
        y0 = y + h / 2 + (len(lines) - 1) * lead / 2
        for i, txt in enumerate(lines):
            self.text(x + w / 2, y0 - i * lead, txt, s.block, color=color, inside=box)

    def arrow(self, p, q):
        s = self.s
        L, W = (1.7, 0.7) if s.mode == "paper" else (3.4, 1.4)
        d = np.array(q, float) - np.array(p, float)
        d /= np.hypot(*d)
        n = np.array([-d[1], d[0]])
        base = np.array(q, float) - L * d
        self.ov.plot([p[0], base[0]], [p[1], base[1]], color=BLACK, lw=0.8 if s.mode == "paper" else 1.6, zorder=8,
                     solid_capstyle="butt")
        self.ov.add_patch(Polygon([q, base + W * n, base - W * n], closed=True, fc=BLACK, ec="none", lw=0, zorder=8))
        self.segs.append((tuple(p), tuple(q)))

    def wire(self, p, q):
        self.ov.plot([p[0], q[0]], [p[1], q[1]], color=BLACK, lw=0.8 if self.s.mode == "paper" else 1.6, zorder=8,
                     solid_capstyle="projecting")
        self.segs.append((tuple(p), tuple(q)))

    # ----------------------------------------------------------------------------------------- checks
    def text_boxes(self):
        r = self.fig.canvas.get_renderer()
        out = []
        for t in self.texts:
            e = t.get_window_extent(r)
            k = 25.4 / self.fig.dpi
            out.append((e.x0 * k, e.y0 * k, e.x1 * k, e.y1 * k))
        return out

    def collisions(self):
        boxes = self.text_boxes()
        bad = []
        for i, a in enumerate(boxes):
            ti = self.texts[i]
            if a[0] < 0 or a[1] < 0 or a[2] > self.W or a[3] > self.H:
                bad.append(f"outside the page: {ti.get_text()}")
            for j in range(i + 1, len(boxes)):
                if overlaps(a, boxes[j]):
                    bad.append(f"text/text: {ti.get_text()} | {self.texts[j].get_text()}")
            if ti.inside is not None:
                b = ti.inside
                if not (a[0] >= b[0] and a[1] >= b[1] and a[2] <= b[2] and a[3] <= b[3]):
                    bad.append(f"text leaves its block: {ti.get_text()}")
            for r in self.rects:
                if overlaps(a, r):
                    bad.append(f"text/column: {ti.get_text()}")
            if ti.inside is None:
                for b in self.blocks:
                    if overlaps(a, b):
                        bad.append(f"text/block: {ti.get_text()}")
            for p, q in self.segs:
                if seg_hits_box(p, q, a):
                    bad.append(f"text/line: {ti.get_text()}")
                    break
            for x, y, m in self.marks:
                if a[0] - m < x < a[2] + m and a[1] - m < y < a[3] + m:
                    bad.append(f"text/marker: {ti.get_text()}")
                    break
        return sorted(set(bad))

    def colour_scan(self):
        bad = []
        ok = {c.lower() for c in PALETTE} | {WHITE.lower()}

        def check(c, what):
            if c is None or (isinstance(c, str) and c == "none"):
                return
            rgba = matplotlib.colors.to_rgba(c)
            if 0 < rgba[3] < 1:
                bad.append(f"alpha {rgba[3]} on {what}")
            if rgba[3] > 0 and matplotlib.colors.to_hex(rgba).lower() not in ok:
                bad.append(f"colour {matplotlib.colors.to_hex(rgba)} on {what}")

        for a in self.fig.findobj():
            if not a.get_visible():
                continue
            if a.get_alpha() is not None and a.get_alpha() < 1:
                bad.append(f"alpha on {type(a).__name__}")
            if isinstance(a, Line2D):
                check(a.get_color(), "line")
                if a.get_marker() not in (None, "None", "", " "):
                    check(a.get_markerfacecolor(), "marker face")
                    check(a.get_markeredgecolor(), "marker edge")
            elif isinstance(a, Text):
                if a.get_text().strip():
                    hexc = matplotlib.colors.to_hex(a.get_color()).lower()
                    if hexc != BLACK and not (hexc == WHITE.lower() and getattr(a, "inside", None) is not None):
                        bad.append(f"text colour {hexc}: {a.get_text()}")
            elif isinstance(a, (Rectangle, Polygon, FancyBboxPatch)):
                if a.get_visible():
                    check(a.get_facecolor(), "patch face")
                    check(a.get_edgecolor(), "patch edge")
        return sorted(set(bad))

    def font_scan(self):
        low = min(float(t.get_fontsize()) for t in self.texts)
        return {"min_size": low, "bad": [t.get_text() for t in self.texts if t.get_fontsize() < 7]}

    # ------------------------------------------------------------------------------------------- output
    def save(self, base):
        s = self.s
        self.fig.canvas.draw()
        report = {"name": self.name, "mode": s.mode, "collisions": self.collisions(), "colours": self.colour_scan(),
                  "fonts": self.font_scan(), "n_text": len(self.texts), "titles": bool(self.fig.get_suptitle()),
                  "series": self.series, "text": [t.get_text() for t in self.texts]}
        buf = io.BytesIO()
        self.fig.savefig(buf, format="pdf")
        plt.close(self.fig)
        doc = fitz.open(stream=buf.getvalue(), filetype="pdf")
        pix = doc[0].get_pixmap(dpi=s.dpi, alpha=False)
        pix.set_dpi(s.dpi, s.dpi)
        if s.mode == "paper":
            os.makedirs(os.path.join(base, "pdf"), exist_ok=True)
            os.makedirs(os.path.join(base, "png"), exist_ok=True)
            with open(os.path.join(base, "pdf", f"{self.name}.pdf"), "wb") as f:
                f.write(buf.getvalue())
            pix.save(os.path.join(base, "png", f"{self.name}.png"))
        else:
            os.makedirs(os.path.join(base, "slides"), exist_ok=True)
            pix.save(os.path.join(base, "slides", f"{self.name}_slide.png"))
        return report
