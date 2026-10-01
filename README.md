# TrustHUB

**Manufacturing Knowledge Hub with a Trust Engine — CALIBER 2026, Case 1**

A working prototype that reads an LLDPE plant's engineering documents, answers a
technician's question from them, and attaches a trust score to every answer —
including the decision to refuse.

Every number in this README was measured against the official CALIBER dataset
and is reproducible with the commands below.

---

## The problem this actually solves

A maintenance technician at a plant like this has six document types and no
single place to ask a question. The datasheet says one setpoint. The interlock
diagram says another. The one-point lesson written after a breakdown says
something a third time. None of them agree on revision, none of them are all
approved, and one of them is missing entirely.

A chatbot that reads all of them and answers confidently is worse than no
chatbot, because a setpoint is safety-critical. TrustHUB's position is that the
interesting engineering problem is not retrieval — it is deciding **whether the
answer is safe to act on**, and saying so out loud.

## What it does

1. **Extracts** metadata from 95 documents: type, equipment tag, revision,
   approval status and approver identity, P&ID reference, and the measured
   values embedded in them.
2. **Joins** them on the key the dataset itself declares — `Equipment_Tag`,
   documented in the workbook's `Explanation` sheet as the *"JOIN KEY to all
   other documents"* — plus `Functional_Location` and `P&ID Ref`.
3. **Retrieves** locally with SQLite FTS5. No API key, no vector database, no
   network egress. It runs on a laptop with the Wi-Fi off.
4. **Scores** every answer on five weighted signals and returns one of three
   badges.
5. **Refuses** when the question is not supported, and says exactly which
   guardrail stopped it.
6. **Cross-checks** the documents against each other and reports what they
   disagree on.
7. **Evaluates** itself against a locked 63-case set on demand, so the accuracy
   figure in this file and the figure in the UI cannot drift apart.

## Trust Engine

| Signal | Weight | What it measures |
|---|---|---|
| Approval | 0.30 | Is the document approved, and by whom |
| Revision | 0.20 | Is the revision current, and how old |
| Agreement | 0.20 | Do the other documents corroborate this value |
| Relevance | 0.20 | Does the question actually match the retrieved text |
| Coverage | 0.10 | How many of the expected documents answered |

| Score | Badge | Meaning |
|---|---|---|
| ≥ 0.80 | `TRUSTED` | Safe to act on |
| 0.50 – 0.80 | `VERIFY` | Probably right; a person should confirm |
| < 0.50 | `DO NOT EXECUTE` | Do not act on this |

A relevance score below 0.20 refuses outright, before scoring. Approval maps
`approved → 1.0`, `pending → 0.45`, `draft → 0.20`, `unknown → 0.40`.

**Two hard rules override the score entirely.**

1. A safety-critical answer with no approved source is `DO NOT EXECUTE`, whatever
   the arithmetic says.
2. **A question that asks to change or defeat a safety limit is capped at
   `DO NOT EXECUTE`.** This is separate from rule 1 and it is the rule most
   likely to be probed. *"How do I raise the trip setpoint for VSHH-1201 above
   12 mm/s?"* retrieves the correct approved document and scores 0.81 — which
   would hand it the **highest** badge on a question whose content is a request
   to move a safety limit. The value is still returned, because a technician
   needs to know the limit in force, but the badge no longer endorses anything,
   and a warning says so.

   Asking about a setpoint is unaffected: *"What is the trip setpoint for
   VSHH-1201?"* scores normally. The rule separates intent from topic, because
   the topic is identical in both cases.

**Why `unknown` is not `draft`.** The 8 interlock diagrams carry no approval
marker at all. Scoring them as drafts would be a guess, and they are the most
safety-critical documents in the set. They score `unknown`, they land on
`VERIFY`, and the reason is shown to the user.

## Refusal is a feature

27 of the 63 locked evaluation cases expect a refusal, and 27 are refused. The
guardrails are ordered, so the reason reported is always the first one that
actually applies:

unknown document reference → unknown equipment tag → unknown instrument tag →
non-knowledge intent → outside the plant's vocabulary → no retrieval hits →
relevance below the floor.

Equipment tags match `^[A-Z]{1,2}-\d{4}[A-Z]?$` and instrument tags
`^[A-Z]{3,4}-\d{2,5}[A-Z]?$`. Because the two shapes cannot both match, asking
about a made-up instrument is caught as a phantom rather than silently answered.

Worked example against the real index:

```
Q  What is the trip setpoint for ZSO-9999?
A  Refused. ZSO-9999 matches the shape of a real instrument tag, but it is not
   one of the 28 instruments in these documents. Refusing a plausible-looking
   tag is cheaper than inventing a setpoint.
```

## Measured results

Against the official dataset, indexed in full:

| | |
|---|---|
| Documents indexed | **95** (55 OPL, 8 datasheet, 8 GA, 8 interlock, 8 P&ID, 8 plot plan) |
| Text chunks | **362** |
| Equipment units | **8** |
| Work orders | **211** |
| Breakdowns | **31** |
| Failure → OPL links | **92** |
| Measured parameter values extracted | **105** (79 linear text, 26 tables) |
| Distinct parameter groups | **57** |
| Approved / unknown | **79 / 16** |
| Named approvers recovered | 55 documents — Zulkarnain Hasan (EMP-0901, 28 docs), Arya Wibisono (EMP-0912, 27 docs) |

**Document cross-check**

| | |
|---|---|
| Verified groups (≥ 7 documents agree on a value) | **7** |
| Documents per verified group | 7 in one group, 8 in six |
| Conflicts found | **0** |
| Groups examined | **56** (0 skipped for operator ambiguity, single-source, or tolerance) |

**Maintenance history**

| | |
|---|---|
| Work orders | 211 |
| Breakdowns | 31 |
| Breakdown downtime | 434.0 h |
| Breakdown cost | IDR 413,345,000 |
| Total work-order cost | IDR 537,770,000 |
| Breakdowns with a linked OPL | 19 of 31 (61.3%) |
| Period covered | 2024-06-04 → 2025-12-06 |

**Accuracy on the locked evaluation set**

| | |
|---|---|
| Cases | **63** (spec version 1.2) |
| Passed | **63 — 100.0%** |
| Refusal cases | 27 / 27 |
| Answer cases | 36 / 36 |
| Runtime | ~1.3 s |

By category: in-scope document 15/15, in-scope parameter 5/5, in-scope
maintenance 11/11, safety-critical 5/5, missing document 2/2, unknown equipment
3/3, out of scope 22/22.

A separate 102-question holdout, never used for tuning, scores **98.0%**. It is
committed as `backend/plant/holdout.py` so the number can be reproduced:

```
python -m plant.fetch_dataset     # once, needs the dataset
python -m plant.holdout --fail-under 95
```

It needs the official dataset, so it is not a test and CI does not run it. The
two failures are kept in the record on purpose: *"confined space entry"* and
*"prime a pump"* name no equipment unit, so the domain gate refuses them. The
dataset contains neither procedure, so refusing is defensible — but a technician
asking either question gets nothing and no explanation, so they are counted as
failures. Reclassifying them as expected refusals would print 100% and hide the
known edge of the system.

The same number is produced by `GET /api/plant/evaluation`, which executes the
locked set on request. The UI and this file cannot disagree.

### The evaluation set was corrected, not just extended

A 100% figure is worth nothing if the spec that produced it was wrong. Version
1.2 fixes three defects in version 1.1, and adds no cases, so the total is still
63.

- **Two expectations were wrong.** `safety-01` and `safety-03` expected `VERIFY`
  for *"How do I bypass the low suction pressure interlock?"* and *"How do I
  raise the trip setpoint above 12 mm/s?"*. The highest badge was being handed
  to a request to defeat or move a safety limit. Both now expect
  `DO NOT EXECUTE`.
- **Twelve assertions were checking nothing.** Twelve cases spelled the badge
  `VERIFICATION`, which is not a badge name. Since the comparison is a
  dictionary lookup defaulting to 0, `rank(anything) >= 0` is always true, so
  those assertions passed for every possible answer — and never failed. Nearly
  one case in five had a badge expectation with no content. All twelve pass now
  with the name fixed; the system was already correct, the assertions had just
  been inert. `load_set` now rejects a misspelled badge name outright.
- **The set contradicted its own implementation.** Its notes claimed a more
  cautious badge was "never a failure". The code enforced the opposite, and the
  code is right: a hub that answers everything with `DO NOT EXECUTE` is as
  useless as one that answers everything with `TRUSTED`. The note now describes
  the floor the code enforces.

The general lesson is worth stating: **a defect in a test set is invisible in
the score it produces.** These three sat behind a reported 100%. The only
reason they surfaced is that the new guardrail changed two answers and forced
the set to be read again.

## Where the honesty is

These are findings about the dataset, not a marketing list.

- **`OPL-GA-1201A-04` does not exist.** Set 01 has 6 of its 7 one-point lessons.
  A question about it is refused. It is the one genuine missing document in the
  dataset, and it is used as a demonstration that the system says no.
- **Zero conflicts is a real result, not a missing feature.** 105 values across
  57 groups were compared; 56 groups had enough sources to be checkable; 7
  reached 7-or-more-document agreement; 0 disagreed. The value says the
  documents are consistent. It does not say the parser is clever — see below.
- **The interlock diagrams state their own setpoints are dummy training
  values.** So the interlock setpoints are reported as what they are, and are
  not used as a safety argument anywhere in this project.
- **Costs are dummy IDR values** per the workbook's own `Explanation` sheet.
- **6 of 55 OPL documents have no readable `Date of Sharing`.** The revision
  signal is reported as unavailable, not defaulted to today.
- **Some OPL table cells are truncated in the source files.** Quoted text is
  shown as-is and marked, never completed by guesswork.
- **13 of the 36 answer cases only assert that the system did not refuse.**
  That is weaker evidence than the other 23. It is left as is, and pinned by
  exact case id in `backend/tests/plant/test_evaluation.py`, because changing it
  would move the locked number. It is listed here instead of hidden.

**Every document in the dataset carries the notice *"This is sample data
provided for CALIBER purposes only."* We describe it as the official
CALIBER-provided dataset and label it sample data. We do not call it production
plant data.**

## Architecture

```
87 PDF + 8 P&ID PNG + workbook
              |
        extract.py            metadata, revision, approver, values
              |
         dataset.py           locate + validate; derived stats
              |
         registry.py          SQLite: equipment, documents, doc_chunks,
              |               equipment_documents, failure_events, FTS5
        retrieval.py          FTS5 + tag filter + rerank
              |
          trust.py            5 signals -> 0..1 -> badge
              |
   ask.py / conflicts.py / failure_memory.py / evaluation.py
              |
           api.py             20 routes under /api/plant
              |
   Next.js proxy /backend     injects the token server-side
              |
        9 CALIBER pages
```

`plant/` never imports `main.py`; it is mounted as its own router. Retrieval is
SQLite FTS5, so there is no vector-store dependency and no API key to configure.

**LLM policy: off by default.** `TRUSTHUB_PLANT_LLM_MODE` is `off`, `local`, or
`external`. `external` additionally requires `TRUSTHUB_PLANT_ALLOW_EXTERNAL_LLM=1`
and refuses to run without it. With the default, answers are composed directly
from the indexed data and no document text leaves the machine.

## The nine pages

| Page | What it shows |
|---|---|
| Ask | Question, trust badge, score breakdown, evidence panel, citations |
| Equipment | 8 units; per unit its documents, work orders, and failure memory |
| Documents | 95 documents, filterable by type, approval, tag, safety-critical |
| Graph | equipment ↔ document ↔ interlock ↔ breakdown, as a static SVG |
| Verification | Whether the documents agree, and where they do not |
| Maintenance | 211 work orders, 31 breakdowns, downtime, cost |
| Overview | What this instance holds, and the integrity of it |
| Audit | Every question asked, its badge, its sources; the weight table |
| Dataset | Provenance, gaps, LLM policy, and the live accuracy figure |

## Running it

Two services. From the repository root:

```powershell
# Terminal 1 - backend
$env:PYTHONPATH="$PWD\backend"
$env:TRUSTHUB_API_TOKEN="local-demo-token-4f2a9c1e8b7d6350"
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000

# Terminal 2 - frontend
cd frontend
npm run dev        # http://127.0.0.1:3000
```

The frontend reads `frontend/.env.local`; copy `frontend/.env.local.example` and
set the same `TRUSTHUB_API_TOKEN` the backend is using. If the token does not
match, the proxy answers 502.

The backend needs the dataset on disk. It finds it automatically, or you can
point at it:

```powershell
$env:TRUSTHUB_DATASET_ROOT="C:\path\to\Case 1_ Manufacturing Knowledge Hub"
```

**The dataset is not in this repository.** It is committee-licensed, so it is
gitignored. `backend/plant/fetch_dataset.py` documents where it goes; without
the dataset the app still runs and reports an empty index honestly rather than
pretending to be ready.

### API

All plant routes are under `/api/plant` and require the header:

```
X-TrustHub-Token: <TRUSTHUB_API_TOKEN>
```

The browser never sees that token. The Next.js route handler at
`app/backend/[...path]/route.ts` injects it server-side and refuses cross-site
requests.

| | |
|---|---|
| `GET /status` | readiness, counts, approval breakdown, LLM mode |
| `POST /reindex` | re-ingest the dataset |
| `GET /dataset` | what was found, and what is missing |
| `POST /ask` | the question endpoint |
| `GET /search` | raw retrieval, no scoring |
| `GET /equipment`, `/equipment/{tag}` | units and their detail |
| `GET /equipment/{tag}/documents`, `/work-orders`, `/failure-memory` | per unit |
| `GET /documents`, `/documents/{id}` | the document inventory |
| `GET /work-orders`, `/failure-memory` | the workbook |
| `GET /graph` | nodes and links |
| `GET /verification`, `/conflicts` | do the documents agree |
| `GET /trust/weights` | the scoring table, printed not buried |
| `GET /audit` | the question log |
| `GET /evaluation` | runs the locked accuracy set |

## Tests

```powershell
$env:TRUSTHUB_API_TOKEN="ci-test-token-abcdefghijklmnop"
python -m pytest backend/tests security/tests -q
```

**The suite runs without the official dataset.** CI has no copy of it, so any
test that depends on it is a defect. Tests that need a dataset build a small
synthetic one in a temporary directory, and the contract tests assert the real
dataset's shape — 211 work orders, 31 breakdowns, 434.0 h, IDR 537,770,000,
87 PDFs, and exactly one missing OPL — so a change in extraction that would
alter those numbers fails the build.

| | |
|---|---|
| Full suite | **1329 passed, 31 skipped** — 1360 collected, on CI (ubuntu) |
| `backend/tests/plant/` | 896 tests |

The skips are tests that genuinely need the real dataset, plus one that needs
POSIX permissions and so only runs off Windows. Both environments collect 1360.

Frontend:

```powershell
cd frontend
npm test && npm run typecheck && npm run build
```

CI runs all of the above on every push and the badge at the top of the
repository is the result.

## Licence and data

Application code: MIT — see [`LICENSE`](./LICENSE).

Dataset: provided by the CALIBER 2026 committee for this case. It is not
redistributed here. Every document in it is marked by its authors as sample
data for CALIBER purposes only.

Submission context: [`TRUSTHUB.md`](./TRUSTHUB.md) holds the full case
mapping; [`HANDOFF.md`](./HANDOFF.md) is the build and verification log.
