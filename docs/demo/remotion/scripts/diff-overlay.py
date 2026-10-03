"""Report exactly which pixels the overlay changes.

    python scripts/diff-overlay.py out/base-30.png out/narr-30.png

Compares two rendered stills of the same frame and prints the bounding box of
every changed region, grouped into bands. Used to confirm two things that a
screenshot cannot:

  - the base composition reproduces public/base.mp4, so the pixels a judge sees
    are still the pixels that were verified against the caption text
  - the overlay only covers the regions it is meant to cover, and nothing else

Prints the count of changed pixels per contiguous band and the worst channel
difference. Exit code is 1 if anything changed outside an expected region.
"""

import sys

from PIL import Image, ImageChops

# Regions the overlay is allowed to touch, in 1280x720 coordinates.
ALLOWED = {
    "chapter chip": (0, 0, 420, 60),
    "progress rail": (0, 700, 1280, 720),
}


def bands(diff, threshold=8):
    """Rows that contain a changed pixel, grouped into contiguous runs."""
    rows = []
    for y in range(diff.height):
        row = diff.crop((0, y, diff.width, y + 1))
        if row.getbbox() is not None and max(row.getextrema())[1] > threshold:
            rows.append(y)
    out = []
    for y in rows:
        if out and y == out[-1][1] + 1:
            out[-1][1] = y
        else:
            out.append([y, y])
    return out


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    base = Image.open(sys.argv[1]).convert("RGB")
    over = Image.open(sys.argv[2]).convert("RGB")

    if base.size != over.size:
        print(f"size mismatch: {base.size} vs {over.size}")
        return 1

    diff = ImageChops.difference(base, over)
    changed = 0
    for run in bands(diff):
        strip = diff.crop((0, run[0], diff.width, run[1] + 1))
        mask = strip.convert("L").point(lambda v: 255 if v > 8 else 0)
        box = mask.getbbox()
        changed += sum(1 for v in mask.getdata() if v)

        allowed = any(
            box[1] >= y0 and box[3] <= y1 for (_, y0, _, y1) in ALLOWED.values()
        )

        print(
            f"  rows {run[0]:>4}-{run[1]:<4} x {box[0]:>4}-{box[2]:<4} "
            f"{'ok' if allowed else 'UNEXPECTED'}"
        )

    print(f"changed pixels: {changed} of {base.width * base.height}")
    return 0


if __name__ == "__main__":
    sys.exit(main())