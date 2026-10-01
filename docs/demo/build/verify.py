"""Check the demo video's narration against what the frames actually say.

A video whose captions describe a system that is not on screen is worse than no
video. Each beat carries the text the frame really rendered, so the claims in
`note` are checked against that text rather than against a PNG nobody can grep.
"""

import json
import pathlib
import re
import sys

OUT = pathlib.Path(__file__).resolve().parent.parent
beats = json.loads((OUT / "beats.json").read_text(encoding="utf-8"))["beats"]


def frame(slug):
    for b in beats:
        if slug in b["frame"]:
            return b
    raise SystemExit(f"no frame matching {slug}")


def has(slug, *needles):
    b = frame(slug)
    low = b["text"].lower()
    missing = [n for n in needles if n.lower() not in low]
    return missing, b


print("=== each beat must actually show what its caption claims ===")

CLAIMS = [
    ("ask-answered", ["7.1", "VSHH-1201", "verify"], "the setpoint answer and its badge"),
    ("ask-missing-doc", ["refus", "OPL-GA-1201A-04"], "the missing-document refusal"),
    ("ask-out-of-scope", ["refus", "deliberate refusal", "do not execute"], "the out-of-scope refusal, with its stated reason"),
    ("ask-safety", ["do not execute", "PSLL-1201"], "the bypass being refused"),
    ("equipment", ["GA-1201A", "1201A"], "equipment tags on screen"),
    ("graph", ["1201", "47 nodes", "39 relations", "87"],
     "the ring totals as shown, plus the relation counts for the documents"),
    ("overview", ["0.30", "0.20", "0.10", "0.80", "0.50", "95", "211"],
     "the published weights and thresholds, plus the system counts"),
    ("verification", ["63 of 63", "spec v1.2", "27/27", "36/36", "100.0", "7"],
     "the locked set executed live, and the cross-confirmed groups"),
    ("maintenance", ["breakdown", "434", "61.3", "19 of 31", "dummy"],
     "failure memory numbers, and the dummy-rupiah framing"),
    ("audit", [], "audit page renders"),
    ("documents", ["approval", "revision"], "document metadata columns"),
    ("dataset", ["sample data", "one-point lessons"], "licence framing and dataset shape"),
    ("landing", ["trusthub"], "landing page"),
    ("ask-idle", ["try one of these"], "the example chips"),
]

bad = []
for slug, needles, what in CLAIMS:
    missing, b = has(slug, *needles)
    tag = "ok  " if not missing else "MISS"
    if missing:
        bad.append((slug, missing))
    print(f"  {tag} {slug:<20} {what}")
    for m in missing:
        print(f"        not on the frame: {m!r}")

print()
print("=== numbers quoted in captions must appear on their own frame ===")
# The captions themselves state figures. Check the load-bearing ones.
CAPTION_NUMBERS = [
    ("ask-answered", ["7.1", "verify"]),
    ("verification", ["63 of 63", "1.2", "27/27", "36/36"]),
    ("overview", ["0.30", "0.10", "0.80"]),
    ("graph", ["47", "39", "87"]),
    ("maintenance", ["31", "434"]),
]
for slug, nums in CAPTION_NUMBERS:
    b = frame(slug)
    low = b["text"].replace(",", "").lower()
    missing = [x for x in nums if x.lower() not in low]
    tag = "ok  " if not missing else "MISS"
    if missing:
        bad.append((slug, f"caption numbers not visible: {missing}"))
    print(f"  {tag} {slug:<20} {nums}")

print()
print("=== forbidden phrasings anywhere in the frames ===")
FORBIDDEN = {
    "production data": "the dataset is labelled sample data by its authors",
    "real plant data": "same reason",
    "15 verified": "a claim that was never measured and is wrong",
    "spec v1.1": "the corrected set is v1.2",
}
for phrase, why in FORBIDDEN.items():
    hits = [b["frame"] for b in beats if phrase.lower() in b["text"].lower()]
    tag = "ok  " if not hits else "FAIL"
    if hits:
        bad.append((phrase, hits))
    print(f"  {tag} absent: {phrase!r} ({why})")
    for h in hits:
        print(f"        found on {h}")

print()
print("=== sample-data framing must be present, not just absent-of-wrong-claims ===")
present = [b["frame"] for b in beats if "sample data" in b["text"].lower()]
print(f"  {'ok  ' if present else 'MISS'} 'sample data' appears on {len(present)} frame(s)")
if not present:
    bad.append(("sample data framing", "absent"))

print()
print("=== duration ===")
total = sum(b["seconds"] for b in beats)
print(f"  {len(beats)} beats, {total}s = {total/60:.2f} min")
if total > 180:
    bad.append(("duration", f"{total}s exceeds the 180s cap"))

print()
if bad:
    print(f"{len(bad)} PROBLEM(S):")
    for x in bad:
        print("  ", x)
    sys.exit(1)
print("every caption matches the frame it describes")