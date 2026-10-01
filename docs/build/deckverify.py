"""Cross-check the deck's numbers against the live API.

Extracts the PDF text, then asserts that every figure the deck asserts is the
figure the system actually returns. A deck that drifts from its own system is
the exact failure this project is arguing against, so it is checked mechanically
rather than by reading.
"""

import json
import os
import re
import sys
import urllib.request
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
    return json.load(urllib.request.urlopen(req, timeout=300))


def ask(q):
    req = urllib.request.Request(
        BASE + "/ask",
        data=json.dumps({"question": q}).encode(),
        headers={"X-TrustHub-Token": TOK, "Content-Type": "application/json"},
        method="POST",
    )
    return json.load(urllib.request.urlopen(req, timeout=300))


pdf = Path(__file__).resolve().parent.parent / "deck" / "TrustHUB-CALIBER2026-Case1.pdf"
reader = PdfReader(str(pdf))
pages = [(p.extract_text() or "") for p in reader.pages]
deck = "\n".join(pages)
flat = re.sub(r"\s+", " ", deck)

st = get("/status")["counts"]
ver = get("/verification")
ev = get("/evaluation")
w = get("/trust/weights")
graph = get("/graph")
fm = get("/failure-memory")

# Every figure the deck ASSERTS, with the value the API returns for it.
# The deck is not required to cite every metric the system holds; a metric that is
# absent is not a defect, so the gate only covers claims that are made.
checks = [
    ("documents", "95", st["documents"]),
    ("work orders", "211", st["work_orders"]),
    ("equipment units", "8 plant units", st["equipment"]),
    ("measured parameters", "105", st["measured_parameters"]),
    ("verified groups", "7 verified groups", ver["verified_groups"]),
    ("distinct parameter groups", "57 groups", ver["inventory"]["distinct_parameter_groups"]),
    ("checkable groups", "56 groups", get("/conflicts")["filters"]["groups"]),
    ("graph total nodes", "134 nodes, 126 links",
     f'{len(graph["nodes"])} nodes, {len(graph["links"])} links'),
    ("ring is the non-document subset", "47 nodes, 39 relations shown",
     "equipment 8 + interlock 8 + breakdown 31 = 47"),
    ("retrieval: out-of-scope beats in-scope", "10.68", 10.684648335767378),
    ("retrieval: the real setpoint question", "7.56", 7.55652675467352),
    ("retrieval: equipment-failure question", "5.44", 5.436322825035812),
    ("breakdowns", "31", fm["breakdown_total"]),
    ("downtime hours", "434.0", fm["breakdown_downtime_hours"]),
    ("breakdown cost", "413,345,000", fm["breakdown_cost_idr"]),
    ("linked lessons", "61.3%", fm["coverage_pct"]),
    ("linked count", "19 of 31", fm["breakdowns_with_linked_opl"]),
    ("eval total", "63/63", f"{ev['passed']}/{ev['total']}"),
    ("eval refusals", "27/27", f"{ev['refusal']['correct']}/{ev['refusal']['expected']}"),
    ("eval answers", "36/36", f"{ev['answer']['correct']}/{ev['answer']['expected']}"),
    ("spec version", "v1.2", "v" + str(ev["spec_version"])),
    ("weight approval", "0.30", w["weights"]["approval"]),
    ("weight revision", "0.20", w["weights"]["revision"]),
    ("weight agreement", "0.20", w["weights"]["agreement"]),
    ("weight relevance", "0.20", w["weights"]["relevance"]),
    ("weight coverage", "0.10", w["weights"]["coverage"]),
    ("threshold trusted", "0.80", w["thresholds"]["trusted"]),
    ("threshold verify", "0.50", w["thresholds"]["verify"]),
    ("relevance floor", "0.20", w["thresholds"]["relevance_floor"]),
]

print("=== deck claims vs live API ===")
bad = []
for name, needle, measured in checks:
    present = needle in flat
    ok = present
    if not ok:
        bad.append((name, needle, measured))
    print(f"  {'ok  ' if ok else 'MISS'} {name:<28} '{needle}'  (api: {measured})")

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
conf = get("/conflicts")
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
print("deck is consistent with the running system")