"""
Final step of the MATLAB figures, called by make_all.m: scales the PDF files in _raw to the journal size (MATLAB draws
them 1.5 times larger, see style_setup.m), writes pdf\\, png\\ (1000 dpi) and slides\\ (300 dpi), and removes _raw.
"""
import os
import shutil
import sys

import pymupdf
from pypdf import PdfReader, PdfWriter, Transformation

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "_raw")
K = 1.0 / 1.5


def scale(src, dst):
    reader = PdfReader(src)
    page = reader.pages[0]
    W, H = float(page.mediabox.width), float(page.mediabox.height)
    page.add_transformation(Transformation().scale(K))
    for box in (page.mediabox, page.cropbox, page.trimbox, page.bleedbox, page.artbox):
        box.lower_left = (0, 0)
        box.upper_right = (W * K, H * K)
    writer = PdfWriter()
    writer.add_page(page)
    writer.write(dst)


def main():
    for sub in ("pdf", "png", "slides"):
        os.makedirs(os.path.join(HERE, sub), exist_ok=True)
    for name in sorted(os.listdir(RAW)):
        stem = name[:-4]
        src = os.path.join(RAW, name)
        slide = stem.endswith("_slide")
        dst = os.path.join(RAW, f"{stem}.scaled") if slide else os.path.join(HERE, "pdf", name)
        scale(src, dst)
        doc = pymupdf.open(dst, filetype="pdf")
        dpi = 300 if slide else 1000
        pix = doc[0].get_pixmap(dpi=dpi, alpha=False)
        pix.set_dpi(dpi, dpi)
        pix.save(os.path.join(HERE, "slides" if slide else "png", f"{stem}.png"))
        doc.close()
    shutil.rmtree(RAW)
    print("postprocess done")


if __name__ == "__main__":
    main()
