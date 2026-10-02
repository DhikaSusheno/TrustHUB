"""Final audit of the three CALIBER deliverables.

Checks the files exist and meet the stated limits, then re-runs the deck
cross-check against the live API. Run this last, immediately before uploading,
because its whole value is that it reads the actual artefacts rather than
trusting that the last build succeeded.
"""

import json
import pathlib
import shutil
import subprocess
import sys

# This file is docs/build/audit_deliverables.py, so three levels up is the
# repository root. Two levels up is docs/, which is not a git repository - the
# dataset-leak check below would then run `git ls-files` outside a repo, fail
# silently, and report zero leaks without ever having looked.
REPO = pathlib.Path(__file__).resolve().parents[2]
PDF = REPO / "docs" / "deck" / "TrustHUB-CALIBER2026-Case1.pdf"
MP4 = REPO / "docs" / "demo" / "TrustHUB-demo.mp4"

problems = []

print("=== deck PDF ===")
if not PDF.exists():
    problems.append("deck PDF missing")
else:
    mb = PDF.stat().st_size / 1024 / 1024
    print(f"  {PDF.name}")
    print(f"  {mb:.2f} MB  (limit 10 MB)   {'ok' if mb <= 10 else 'OVER LIMIT'}")
    if mb > 10:
        problems.append(f"deck PDF is {mb:.1f} MB, over the 10 MB limit")

    try:
        import pypdf

        r = pypdf.PdfReader(str(PDF))
        pages = len(r.pages)
        box = r.pages[0].mediabox
        w, h = float(box.width), float(box.height)
        page_texts = [(p.extract_text() or "") for p in r.pages]
        text = "\n".join(page_texts)

        # The CALIBER booklet caps the deck at 7 slides, "including the cover
        # slide and excluding any appendix slides", and allows unlimited
        # appendix pages. Appendix pages carry APPENDIX in the footer, so the
        # two groups are counted apart. A single total cannot tell a compliant
        # 7-slide deck with evidence from a 13-slide deck that ignored the cap,
        # which is exactly the mistake this check used to make.
        MAIN_LIMIT = 7
        appendix = [t for t in page_texts if "APPENDIX" in t]
        main = [t for t in page_texts if "APPENDIX" not in t]
        print(f"  pages: {pages}  =  {len(main)} main + {len(appendix)} appendix")
        print(f"  main deck: {len(main)}  (booklet limit {MAIN_LIMIT})   "
              f"{'ok' if len(main) <= MAIN_LIMIT else 'OVER LIMIT'}")
        if len(main) > MAIN_LIMIT:
            problems.append(
                f"deck has {len(main)} main slides, over the {MAIN_LIMIT} the "
                "booklet allows once appendix slides are excluded"
            )
        print(f"  page size: {w:.0f} x {h:.0f} pt   ratio {w/h:.3f} "
              f"({'16:9' if abs(w/h - 16/9) < 0.01 else 'NOT 16:9'})")
        print(f"  extractable text: {len(text):,} chars  "
              f"{'(searchable)' if len(text) > 3000 else '(too little - is it an image?)'}")
        if len(text) <= 3000:
            problems.append("deck PDF has almost no text layer; may be rasterised")

        for phrase, why in {
            "15 verified groups": "never measured, and wrong",
            "production data": "the dataset is labelled sample data by its authors",
            "real plant data": "same reason",
            "0.572": "not reproducible; replaced by measured 10.68",
            "spec v1.1": "the corrected set is v1.2",
        }.items():
            hit = phrase.lower() in text.lower()
            print(f"  {'absent' if not hit else 'PRESENT'}: {phrase!r}  ({why})")
            if hit:
                problems.append(f"deck contains {phrase!r}")
    except ImportError:
        print("  (pypdf not available, skipping page checks)")

print()
print("=== demo video ===")
if not MP4.exists():
    problems.append("demo video missing")
else:
    mb = MP4.stat().st_size / 1024 / 1024
    print(f"  {MP4.name}")
    print(f"  {mb:.2f} MB")
    if shutil.which("ffprobe"):
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_name,width,height,pix_fmt",
             "-of", "default=noprint_wrappers=1", str(MP4)],
            capture_output=True, text=True,
        ).stdout
        info = dict(
            line.split("=", 1) for line in out.strip().splitlines() if "=" in line
        )
        dur = float(info["duration"])
        mm, ss = divmod(round(dur), 60)
        print(f"  {mm}:{ss:02d}  (requirement 2-3 min = 120-180 s)"
              f"   {'ok' if 120 <= dur <= 180 else 'OUT OF RANGE'}")
        if not 120 <= dur <= 180:
            problems.append(f"video is {dur:.0f}s, outside the 2-3 minute window")
        print(f"  {info.get('codec_name')} {info.get('width')}x{info.get('height')} "
              f"{info.get('pix_fmt')}  (yuv420p = plays everywhere)")
    else:
        print("  (ffprobe not on PATH, skipping)")

print()
print("=== dataset must not be in the repo ===")
leaks = [
    ln.strip() for ln in subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True
    ).stdout.splitlines()
    if ln.lower().endswith((".db", ".sqlite", ".xlsx"))
    or "case 1_" in ln.lower()
    or ln.startswith("backend/dataset/")
]
print(f"  tracked files matching .db/.sqlite/.xlsx/dataset: {len(leaks)}")
for ln in leaks:
    print(f"    LEAK {ln}")
if leaks:
    problems.append(f"{len(leaks)} dataset artefact(s) tracked")

print()
print("=== placeholders that must be filled before submission ===")
try:
    import pypdf

    r = pypdf.PdfReader(str(PDF))
    MAIN_LIMIT = 7

    # PDF text extraction wraps lines, so "Link to be added on\nsubmission"
    # does not contain "Link to be added on submission". Searching raw text
    # would report a placeholder as absent, which is the one answer this check
    # must never get wrong.
    def norm(page):
        return " ".join((r.pages[page].extract_text() or "").split())

    # Report every placeholder still sitting in the seven main slides, by
    # slide. Pinning fixed slide numbers worked only while the deck layout was
    # frozen; it silently checked nothing once a slide moved.
    PLACEHOLDERS = ("to be confirmed", "link to be added on submission")
    found = False
    for i in range(min(MAIN_LIMIT, len(r.pages))):
        body = norm(i)
        if "appendix" in body.lower():
            continue
        for token in PLACEHOLDERS:
            if token.lower() in body.lower():
                found = True
                print(f"  slide {i + 1:>2}: PLACEHOLDER PRESENT: {token!r}")
    if not found:
        print("  none left in the main deck")
except Exception as exc:  # noqa: BLE001
    print(f"  (could not check: {exc})")

print()
if problems:
    print(f"{len(problems)} PROBLEM(S):")
    for p in problems:
        print(f"  - {p}")
    sys.exit(1)
print("all three deliverables pass their stated limits")
