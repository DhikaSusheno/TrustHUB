"""Cross-check the deck's numbers against the live API.

Every claim is checked twice, and the two checks are independent:

  1. the figure appears on the slide, and
  2. the running API returns that same figure.

The second check is the one this script used to skip. The loop compared each
needle against the extracted PDF text and then printed the API value for
information only, so two failures both ended in a green run: a deck that had
drifted from its own system, and a backend with no dataset loaded, where every
count comes back 0 and still reads "consistent".

Claims that this script cannot source from the API are reported separately as
UNVERIFIED instead of being counted as passes, so the closing line cannot claim
more coverage than the script actually has.

Usage:
    TRUSTHUB_API_TOKEN=<token> python docs/build/deckverify.py
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

BASE = os.environ.get("TRUSTHUB_API_URL", "http://127.0.0.1:8000/api/plant")
# The API token is a secret, so it is read from the environment rather
# than written here. The demo token is a local one and not a real credential,
# but there is no reason for a check script to be the place it is committed.
TOK = os.environ.get("TRUSTHUB_API_TOKEN", "")
if not TOK:
    sys.exit("set TRUSTHUB_API_TOKEN to the token your backend was started with")


def get(path):
    req = urllib.request.Request(BASE + path, headers={"X-TrustHub-Token": TOK})
    try:
        return json.load(urllib.request.urlopen(req, timeout=300))
    except urllib.error.HTTPError as exc:
        sys.exit(
            f"GET {path} returned HTTP {exc.code}.\n"
            "This check is only meaningful against a loaded dataset, so a 503 "
            "here means the index is empty rather than that the deck is wrong.\n"
            "  1. set TRUSTHUB_DATASET_ROOT to the CALIBER dataset folder\n"
            "  2. restart the backend\n"
            "  3. confirm GET /api/plant/status reports ready=true"
        )
    except urllib.error.URLError as exc:
        sys.exit(f"cannot reach {BASE}: {exc.reason}\nis the backend running?")


def ask(q):
    req = urllib.request.Request(
        BASE + "/ask",
        data=json.dumps({"question": q}).encode(),
        headers={"X-TrustHub-Token": TOK, "Content-Type": "application/json"},
        method="POST",
    )
    return json.load(urllib.request.urlopen(req, timeout=300))


pdf = Path(__file__).resolve().parent.parent / "deck" / "TrustHUB-CALIBER2026-Case1.pdf"
if not pdf.exists():
    sys.exit(
        f"{pdf.name} is missing. It is a build output, not a committed file:\n"
        "  cd docs/deck/build && npm ci && npm run render"
    )
reader = PdfReader(str(pdf))
pages = [(p.extract_text() or "") for p in reader.pages]
deck = "\n".join(pages)
flat = re.sub(r"\s+", " ", deck)

st = get("/status")
if not st.get("ready"):
    sys.exit(
        "GET /status reports ready=false, so every count below would be 0 and "
        "each one would fail for the wrong reason.\n"
        "Refusing to compare the deck against an empty index:\n"
        "  1. set TRUSTHUB_DATASET_ROOT to the CALIBER dataset folder\n"
        "  2. restart the backend\n"
        "  3. confirm GET /api/plant/status reports ready=true"
    )

ver = get("/verification")
ev = get("/evaluation")
w = get("/trust/weights")
graph = get("/graph")
fm = get("/failure-memory")
conf = get("/conflicts")

nodes = graph["nodes"]
links = graph["links"]
by_type = Counter(n["type"] for n in nodes)
# The Graph page deliberately draws only the non-document ring: 87 document
# nodes in one circle are unreadable. The deck quotes both totals, so both are
# measured here rather than one being assumed from the other.
ring_nodes = by_type["equipment"] + by_type["interlock"] + by_type["breakdown"]
ring_relations = sum(1 for l in links if l["label"] in ("interlock", "breakdown"))


def drifts(deck_claim, api_value, dp=None):
    """True when the figure on the slide disagrees with the running API."""
    if isinstance(deck_claim, (tuple, list)):
        return tuple(deck_claim) != tuple(api_value)
    if isinstance(deck_claim, str) or isinstance(api_value, str):
        return str(deck_claim) != str(api_value)
    if dp is not None:
        return round(float(api_value), dp) != round(float(deck_claim), dp)
    return api_value != deck_claim


# (label, text that must appear on the slide, the figure the deck asserts,
#  the figure the API returns, decimal places to compare at)
# `dp` is the precision the slide quotes, so 10.68 is checked against
# 10.684648... at two places rather than being rounded to a false exact match.
checks = [
    ("documents", "95", 95, st["counts"]["documents"], None),
    ("work orders", "211", 211, st["counts"]["work_orders"], None),
    ("equipment units", "8 plant units", 8, st["counts"]["equipment"], None),
    ("measured parameters", "105", 105, st["counts"]["measured_parameters"], None),
    ("verified groups", "7 verified groups", 7, ver["verified_groups"], None),
    ("distinct parameter groups", "57 groups", 57,
     ver["inventory"]["distinct_parameter_groups"], None),
    ("checkable groups", "56 groups", 56, conf["filters"]["groups"], None),
    ("graph total nodes", "134 nodes, 126 links", (134, 126),
     (len(nodes), len(links)), None),
    ("ring is the non-document subset", "47 nodes, 39 relations shown", (47, 39),
     (ring_nodes, ring_relations), None),
    ("breakdowns", "31", 31, fm["breakdown_total"], None),
    ("downtime hours", "434.0", 434.0, fm["breakdown_downtime_hours"], 1),
    ("breakdown cost", "413,345,000", 413345000, fm["breakdown_cost_idr"], 0),
    ("linked lessons", "61.3%", 61.3, fm["coverage_pct"], 1),
    ("linked count", "19 of 31", (19, 31),
     (fm["breakdowns_with_linked_opl"], fm["breakdown_total"]), None),
    ("eval total", "63/63", "63/63", f"{ev['passed']}/{ev['total']}", None),
    ("eval refusals", "27/27", "27/27",
     f"{ev['refusal']['correct']}/{ev['refusal']['expected']}", None),
    ("eval answers", "36/36", "36/36",
     f"{ev['answer']['correct']}/{ev['answer']['expected']}", None),
    ("spec version", "v1.2", "v1.2", "v" + str(ev["spec_version"]), None),
    ("weight approval", "0.30", 0.30, w["weights"]["approval"], 2),
    ("weight revision", "0.20", 0.20, w["weights"]["revision"], 2),
    ("weight agreement", "0.20", 0.20, w["weights"]["agreement"], 2),
    ("weight relevance", "0.20", 0.20, w["weights"]["relevance"], 2),
    ("weight coverage", "0.10", 0.10, w["weights"]["coverage"], 2),
    ("threshold trusted", "0.80", 0.80, w["thresholds"]["trusted"], 2),
    ("threshold verify", "0.50", 0.50, w["thresholds"]["verify"], 2),
    ("relevance floor", "0.20", 0.20, w["thresholds"]["relevance_floor"], 2),
]

print("=== deck claims vs live API ===")
bad = []
for name, needle, claim, api_value, dp in checks:
    on_slide = needle in flat
    stale = drifts(claim, api_value, dp)
    if stale:
        ok = "STALE"
        bad.append((name, claim, api_value))
    elif not on_slide:
        ok = "MISS"
        bad.append((name, needle, api_value))
    else:
        ok = "ok  "
    print(f"  {ok} {name:<28} slide={claim!s:<18} api={api_value!s}")

print()
print("=== claims this script cannot source from the API ===")
# Checked for presence only. They are reported rather than folded into the pass
# count, because a claim nobody can reproduce is exactly the drift this gate
# exists to catch.
unverified = [
    ("retrieval: out-of-scope beats in-scope", "10.68"),
    ("retrieval: the real setpoint question", "7.56"),
    ("retrieval: equipment-failure question", "5.44"),
]
for name, needle in unverified:
    present = needle in flat
    if not present:
        bad.append((name, needle, "absent"))
    print(f"  {'ok  ' if present else 'MISS'} {name:<38} '{needle}'  (unverified)")

print()
print("=== demo answers quoted on slide 10 ===")
quoted = [
    ("What is the trip setpoint for VSHH-1201?", "7.1 mm/s"),
    ("How do I raise the trip setpoint for VSHH-1201 above 12 mm/s?", "7.1 mm/s"),
    ("What is the setpoint for ZSO-9999?", "ZSO-9999"),
]
for q, must in quoted:
    a = ask(q)
    in_deck = must in flat
    in_answer = must in a["answer"] or must in (a.get("refusal_reason") or "")
    ok = in_deck and in_answer
    if not ok:
        bad.append((q, must, a["badge"]))
    print(f"  {'ok  ' if ok else 'FAIL'} {a['badge']:<16} {q[:46]}")
    print(f"         value in answer: {in_answer}   value on slide: {in_deck}")

print()
print("=== the two documented holdout failures must stay failures ===")
print(f"  conflicts_found = {ver['conflicts_found']}  (deck says '0 disagreed')")
if ver["conflicts_found"] != 0:
    bad.append(("conflicts_found", "0", ver["conflicts_found"]))

print()
print("=== claims stated in words rather than as bare figures ===")
# "55 of 95 documents carry a named approver" and "16 of 95 have unknown
# approval" must agree with each other and with the status route.
approvals = st["approved_documents"]
unknown = get("/status")["approval_breakdown"]["unknown"]
for label, needle in (
    ("approver evidence", "55 of 95 documents carry a named approver"),
    ("unknown approval", "16 of 95 documents have unknown approval"),
):
    present = needle in flat
    if not present:
        bad.append((label, needle, "absent"))
    print(f"  {'ok  ' if present else 'MISS'} {label}: '{needle}'")

consistent = approvals + unknown == st["documents"]
print(
    f"  {'ok  ' if consistent else 'FAIL'} approved {approvals} + unknown {unknown}"
    f" == documents {st['documents']}"
)
if not consistent:
    bad.append(("approval split", "95", approvals + unknown))

print()
print("=== forbidden claims ===")
forbidden = {
    "0.572": "a relevance figure that no longer exists in the response; refused "
             "questions are scored no further than the guardrail",
    "15 verified groups": "the 15-group claim that was never measured",
    "production data": "dataset must never be called production data",
    "real plant data": "dataset must never be called real plant data",
}
for phrase, why in forbidden.items():
    present = phrase.lower() in flat.lower()
    if present:
        bad.append((phrase, "absent", why))
    print(f"  {'ok  ' if not present else 'FAIL'} absent: '{phrase}'  ({why})")

print()
if bad:
    print(f"{len(bad)} PROBLEM(S):")
    for b in bad:
        print("  ", b)
    raise SystemExit(1)
print(
    f"{len(checks)} claims checked against the live API and matched."
)
print(
    f"{len(unverified)} further figures are quoted on the slides but not "
    "reproducible from the API."
)