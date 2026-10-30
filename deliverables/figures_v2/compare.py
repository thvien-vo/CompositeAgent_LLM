"""Side-by-side images of the Python and MATLAB versions: compare\\<figure>_compare.png."""
import os
import sys

import matplotlib
from PIL import Image, ImageDraw, ImageFont

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "compare")
Image.MAX_IMAGE_PIXELS = None
FONT = ImageFont.truetype(os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf", "cmr10.ttf"), 44)
WIDTH, GAP, HEAD = 2000, 60, 80


def load(path):
    with Image.open(path) as im:
        im = im.convert("RGB")
    k = WIDTH / im.size[0]
    return im.resize((WIDTH, int(im.size[1] * k)), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    done = 0
    for sub in ("png", "slides"):
        for name in sorted(os.listdir(os.path.join(HERE, "python", sub))):
            mat = os.path.join(HERE, "matlab", sub, name)
            if not os.path.exists(mat):
                print("no MATLAB version:", name)
                continue
            left, right = load(os.path.join(HERE, "python", sub, name)), load(mat)
            H = max(left.size[1], right.size[1])
            sheet = Image.new("RGB", (2 * WIDTH + 3 * GAP, H + HEAD + GAP), "white")
            draw = ImageDraw.Draw(sheet)
            draw.text((GAP, 14), "Python", fill="black", font=FONT)
            draw.text((2 * GAP + WIDTH, 14), "MATLAB", fill="black", font=FONT)
            sheet.paste(left, (GAP, HEAD))
            sheet.paste(right, (2 * GAP + WIDTH, HEAD))
            sheet.save(os.path.join(OUT, f"{name[:-4]}_compare.png"))
            done += 1
    print("compare images:", done)


if __name__ == "__main__":
    main()
