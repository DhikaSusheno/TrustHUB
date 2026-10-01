# TrustHUB — Case Mapping

**CALIBER 2026 · Case 1: Manufacturing Knowledge Hub**

This document maps every requirement in the Case Book to something that exists in
this repository and runs. Where a requirement is only partially met, or met by
simulation, it says so.

Numbers here are measured against the official dataset. `README.md` has the full
tables; this file is the requirement-by-requirement argument.

---

## 1. The six required components

| # | Case Book component | What exists | Where | Real? |
|---|---|---|---|---|
| 1 | Industrial Data Ops | Equipment-centric knowledge graph + document registry carrying type, tag, revision, approval status, approver identity | `plant/registry.py`, `plant/extract.py`, `GET /api/plant/graph` | **Real** |
| 2 | AI Document Ingestion | Per-file-type pipeline: linear PDF text, PDF tables, workbook columns, image label/tag extraction | `plant/extract.py` (541 lines), `plant/dataset.py` | **Real** |
| 3 | Q&A Assistant + Semantic Search | Tag-filtered retrieval with rerank, then a grounded answer with mandatory citation | `plant/retrieval.py`, `plant/ask.py` | **Real** |
| 4 | Traceable Answer with Source | Source, document revision, approval status, trust score, and a three-value badge on every answer | `plant/trust.py`, `GET /api/plant/ask` | **Real** |
| 5 | EDMS / AIMS / Digital Twin Integration | — | — | **Not built** |
| 6 | Failure Memory System (and Recommendation) | Failure modes and past actions joined to one-point lessons, per unit, over 211 work orders | `plant/failure_memory.py`, `GET /api/plant/failure-memory` | **Real** |

### On component 5, honestly

The Case Book names EDMS/AIMS/Digital Twin integration. **We did not build it,
and this document does not claim we did.**

The earlier draft of this project proposed a "simulated connector" with a
realistic revision/status schema. We dropped it. A mock EDMS adapter demonstrates
nothing that the document registry does not already demonstrate for real, and
presenting a fabricated integration as a delivered component is exactly the kind
of claim that fails under a sceptical reading. The registry's revision, approval
and effective-date fields are populated from the real documents, which is the
same data an EDMS would hold, sourced honestly instead of faked.

The integration path is documented in §6 as a roadmap, not as a feature.

---

## 2. The three key questions

The Case Book requires each to be answered explicitly.

### KQ1 — What is the foundation for Industrial Data Ops?

> We link every source to the equipment it describes. An equipment-centric
> knowledge graph connects datasheets, P&IDs, GA drawings, interlock diagrams,
> one-point lessons and maintenance records through a shared tag. A document
> registry tracks revision, approval status and effective date for each file. New
> sources join by mapping to a tag and a metadata schema, so the foundation scales
> from 8 units to a full plant without redesign.

**Evidence.** The join key is not our invention — the dataset's own `Explanation`
sheet defines `Equipment_Tag` as the *"JOIN KEY to all other documents"*, which
`Functional_Location` and `P&ID Ref` reinforce. The graph returns 134 nodes and
126 links: 8 equipment, 87 documents, 8 interlock diagrams, 31 breakdowns.
Adding a document type means adding a `classify()` branch and a chunker, not
changing the schema.

### KQ2 — How does AI help engineers find trustworthy information and reduce wrong execution?

> Speed, plus a trust verdict on every answer. Retrieval is restricted to the
> relevant equipment. Answers cite document and revision. A Trust Engine scores
> approval status, revision currency, cross-source agreement, relevance and
> evidence coverage. Conflicting sources are surfaced rather than silently
> resolved. When evidence is missing, the system declines to answer.

**Evidence.** Five weighted signals, printed in the UI at `/api/plant/trust/weights`
rather than buried. 27 of 63 locked evaluation cases expect a refusal and 27 are
refused — refusal is a measured behaviour, not a disclaimer. The phantom-instrument
case (`ZSO-9999`) matches the shape of a real tag but is not one of the 28 in the
dataset, and is refused rather than answered.

**The badge is not purely a score.** Two situations override the arithmetic, and
both are the ones where a score would point a person the wrong way. A
safety-critical answer with no approved source is `DO NOT EXECUTE` regardless of
score. And a question asking to *change* or *defeat* a safety limit is capped at
`DO NOT EXECUTE`: *"How do I raise the trip setpoint for VSHH-1201 above
12 mm/s?"* retrieves the correct approved document and scores 0.81, which would
award it the highest badge on a request to move a safety limit. The documented
value is still returned — a technician does need to know the limit in force —
but the badge no longer endorses the change. Asking what the setpoint *is* is
unaffected. This is the difference between a trust score and a trust decision,
and it is where the Case Book's "reduce wrong execution" is actually won or lost.

### KQ3 — How does it integrate with operational systems for reliability, troubleshooting and continuous improvement?

> Failure Memory turns maintenance history into troubleshooting guidance. For each
> unit, recurring failure modes and past actions are linked to the relevant
> one-point lessons. 31 breakdowns, 434.0 hours of downtime and IDR 413,345,000
> of recorded breakdown cost are aggregated from the workbook, and 19 of the 31
> breakdowns (61.3%) already have a linked lesson. The 12 that do not are shown
> as a coverage gap, not hidden.

**Evidence, and its limit.** The read-only side is real. The *write-back* leg —
an SME approving a new lesson, which then improves the base — is **not
implemented.** The audit log records every question asked, which is the
instrument a write-back loop would need, but there is no approval queue and no
persistence of new knowledge. This is the largest gap in the submission and §7
lists it as such.

---

## 3. The four baseline data types

| Baseline type | How it is used | Extracted |
|---|---|---|
| SOP and datasheet | Revision and approval parsing; measured setpoints; `DATASHEET REV` marker | 8 datasheets, 26 values |
| P&ID | Equipment tag and label extraction, linked to the unit | 8 P&ID images |
| Maintenance History | Work orders, breakdowns, downtime, cost, failure-mode aggregation | 211 work orders, 31 breakdowns |
| Tacit knowledge (SME / OPL) | One-point lessons, read for troubleshooting, linked to breakdowns | 55 OPL documents, 48 values |

Plus 8 GA drawings and 8 interlock diagrams from the same dataset.

**Claim limit on P&IDs.** We extract equipment tags and text labels. We do **not**
claim to read topology, connectivity, or instrument relationships from the
diagrams. The eight P&ID files are images; nothing in this system interprets what
the drawn lines mean.

---

## 4. AI output is validated and evaluated

The Case Book is explicit that an accuracy test set is not optional. Ours runs
three ways, and all three execute the same 63-case locked set.

| Path | Command / route |
|---|---|
| CLI | `python -m plant.evaluation` |
| API | `GET /api/plant/evaluation` |
| UI | the Dataset page |

**Result: 63 / 63 = 100.0%.** Refusals 27/27, answers 36/36, ~1.3 s. A separate
102-question holdout, never used for tuning, scores 98.0%. It is committed as
`backend/plant/holdout.py` and reproduces with `python -m plant.holdout`. Its two
failures are documented rather than reclassified.

By category: in-scope document 15/15, in-scope parameter 5/5, in-scope maintenance
11/11, safety-critical 5/5, missing document 2/2, unknown equipment 3/3, out of
scope 22/22.

The evaluation is a **fixture, not a promise**. `backend/tests/plant/test_evaluation.py`
fails the build if accuracy drops below 100% or if any case is deleted or
renamed. The set is versioned (`version: 1.2`) so a future change is visible as
a change rather than a silent improvement.

### The set itself was wrong three times, and the score never showed it

This is the most important thing to say about the evaluation, because it is the
part a sceptical reviewer will not otherwise see. Version 1.2 corrects three
defects in version 1.1. **All three sat behind a reported 100%.**

1. **Two expectations had the wrong answer.** `safety-01` and `safety-03`
   expected `VERIFY` for a bypass request and a setpoint-raise request. The
   highest trust badge was being awarded to a question asking the system to
   defeat or move a safety limit. Both now expect `DO NOT EXECUTE`, and the
   trust engine caps those questions accordingly.
2. **Twelve assertions were vacuous.** Twelve cases spelled the badge
   `VERIFICATION`, which is not a badge name. The comparison is a dict lookup
   defaulting to 0, so `rank(anything) >= 0` is always true — those twelve cases
   could not fail, whatever the system answered. Nearly one case in five had a
   badge expectation with no content in it. `load_set` now raises on a
   misspelled badge name, and a test checks the spelling of every expectation.
3. **The notes contradicted the code.** The set claimed a more cautious badge was
   "never a failure"; the code enforced the opposite. The code is right — a hub
   that answers everything `DO NOT EXECUTE` is as useless as one that answers
   everything `TRUSTED`, so over-caution is a regression too. The notes now
   describe the floor the code enforces.

They surfaced only because the new guardrail changed two answers and forced the
set to be read again. **A defect in a test set is invisible in the score it
produces**, and that is the argument for reading the set rather than quoting it.

### What the evaluation set does not prove

Stated plainly, because a 100% figure invites the question:

- **13 of the 36 answer cases only assert that the system did not refuse.** They
  are genuine guards against answering what it should not answer, but they are
  weaker evidence than the 23 cases that check the content. Their exact ids are
  pinned in `test_evaluation.py` so the count cannot quietly change.
- **The set was written by the people who wrote the system.** A 102-question
  holdout is reported to give a fairer reading, but it shares an author.
- **100% reflects a well-behaved dataset.** The documents largely agree with each
  other. The conflict-detection path is therefore exercised mostly by unit tests,
  not by the evaluation set, because there is no real conflict in this data to
  detect. That is a property of the input, not a strength of the detector.

---

## 5. Data architecture

The Case Book prefers "well-justified, high-quality data architecture" over
integrating more data. We added no data source beyond the baseline four plus the
drawings already in the dataset.

```
87 PDF + 8 P&ID PNG + workbook
        |
  extract.py        metadata, revision, approver identity, measured values
        |
  dataset.py        locate + validate; dataset-derived statistics
        |
  registry.py       SQLite: equipment, documents, doc_chunks,
        |           equipment_documents, failure_events, work_orders,
        |           failure_links, parameter_values + FTS5 index
  retrieval.py      FTS5 -> tag filter -> rerank
        |
  trust.py          5 signals -> 0.0-1.0 -> TRUSTED | VERIFY | DO NOT EXECUTE
        |
  ask.py  conflicts.py  failure_memory.py  evaluation.py
        |
  api.py            20 routes, prefix /api/plant, own router
        |
  Next.js proxy     injects the token server-side; browser never sees it
        |
  9 pages
```

**Why SQLite FTS5 and not a vector store.** It needs no API key, no model download
and no network. The prototype runs air-gapped, which is also how a plant data
room actually behaves. The cost is that lexical matching has to be rescued by the
tag filter and the rerank; that trade is documented rather than hidden.

**`plant/` never imports `main.py`.** It is mounted as an independent router so the
Case 1 code has no dependency on the inherited Synapse application and can be
lifted out without surgery.

---

## 6. Security, reliability, oversight

The Executive Summary asks for these to be visible, so they are concrete here.

| Concern | Measure |
|---|---|
| Data security | Retrieval is local. LLM mode defaults to `off`; no document text leaves the machine. `external` mode additionally requires `TRUSTHUB_PLANT_ALLOW_EXTERNAL_LLM=1` and refuses to run without it. |
| Access control | `X-TrustHub-Token` on every plant route, enforced by app-level middleware. Five public paths exactly; **no plant route is public.** |
| Browser credential exposure | The Next.js handler injects the token server-side. The token is never in the bundle. Cross-site requests are rejected via `Sec-Fetch-Site`, so the proxy is not an open door. |
| Auditability | Every question, its badge, its score and its sources are logged and shown at `/api/plant/audit`. |
| Explainability | The five weights and three thresholds are printed in the UI, not hard-coded in prose. |
| Safe degradation | With no LLM, the answer is composed from the indexed data. If retrieval yields nothing, the system refuses instead of generating. |
| Human oversight | `DO NOT EXECUTE` and `VERIFY` push the decision to a person. Safety-critical procedure steps are quoted verbatim from the document, never paraphrased. |

**Overclaim avoided:** there is no role-based access control and no SSO. There is
one shared token. Role separation is roadmap, not a feature.

---

## 7. What is missing

Listed because a submission that hides its gaps is worse than one that names
them.

| Gap | Effect | Status |
|---|---|---|
| No EDMS/AIMS/Digital Twin integration | Component 5 unbuilt | Deliberate. See §1. |
| No SME write-back loop | KQ3's continuous-improvement leg incomplete | **Largest gap.** |
| No role-based access | One shared token, not viewer / SME approver | Roadmap |
| P&IDs are images | Only tags and labels extracted, not topology | Claim is scoped to match |
| Interlock diagrams unapproved | 16 of 95 documents score `unknown`, and the 8 interlock diagrams are among them | Scored `unknown`, never guessed |
| `OPL-GA-1201A-04` missing from the dataset | 2 evaluation cases | Used as the honest-refusal demo |
| 6 OPL documents have no readable share date | Revision signal unavailable for them | Reported as `null`, not defaulted |
| Some OPL table cells truncated in source | Quoted troubleshooting text is partial | Shown as-is, marked |

---

## 8. Data provenance and honesty statement

Every document in the dataset carries the notice **"This is sample data provided
for CALIBER purposes only."** The workbook's `Explanation` sheet describes the
costs as dummy IDR values, and the interlock diagrams state in their own text
that the trip setpoints are **dummy training values**.

Therefore:

- We describe the data as **the official CALIBER-provided dataset, labelled sample
  data**. We do not call it production plant data.
- Interlock setpoints are reported as what they are and are **not** used as a
  safety argument anywhere in this project.
- Costs are described as the dummy IDR values the workbook declares them to be.
- The dataset is **not committed** to this repository. It is committee-licensed;
  `backend/plant/fetch_dataset.py` records where it belongs, and the application
  reports an empty index honestly when it is absent.
- **Real-time operational data and incident reports are named in the Case Book
  problem statement but are not in the baseline dataset.** We did not fabricate
  them. The system has no real-time feed, and nothing in the UI implies one.

---

## 9. Where each claim can be checked

| Claim | Check |
|---|---|
| 95 documents, 362 chunks, 8 units, 211 work orders | `GET /api/plant/status` |
| 105 measured values, 57 parameter groups, 0 conflicts | `GET /api/plant/verification`, `/conflicts` |
| 7 verified groups across 7–8 documents | `GET /api/plant/verification` |
| 63/63 = 100.0% | `python -m plant.evaluation` or `GET /api/plant/evaluation` |
| 98.0% on a 102-question holdout | `python -m plant.holdout`, needs the dataset |
| The five weights and thresholds | `GET /api/plant/trust/weights` |
| 31 breakdowns, 434.0 h, IDR 413,345,000, 61.3% linked | `GET /api/plant/failure-memory` |
| 55 documents carry a named approver | `GET /api/plant/documents?approval_status=approved` |
| Tests pass without the dataset | `pytest backend/tests security/tests` on a clean checkout |
| The dataset shape is what we claim | `backend/tests/plant/test_dataset_contract.py` |
