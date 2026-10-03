# TrustHUB: Master Prompt for Demo, Deck and Pitch Delivery

> **Purpose.** A single brief for an AI agent (or a person) who has to finish the
> demonstrator, restructure the PowerPoint, and rehearse the three-person pitch.
> Everything in this file is either verified against the running system or
> explicitly marked as an open decision. Nothing here is aspirational.
>
> **Read this first, then** `TRUSTHUB.md` (requirement mapping),
> `DESIGN.md` + `AGENTS.md` (visual and anti-slop rules),
> `TASK_CONTINUITY.md` (history and open work), `README.md` (number tables).

---

## 0. The one-paragraph brief

TrustHUB is an industrial knowledge hub for an LLDPE plant unit (Set 01). It reads
the official CALIBER dataset (95 documents, 8 equipment units, 211 work orders),
answers an engineer's question with a mandatory citation, and then says how far
that answer can be trusted. The contribution is not a chatbot. It is that the
system **refuses on purpose, in writing, with a reason**, and that every refusal
is a measured behaviour rather than a disclaimer. The pitch must make the judges
care about the refusals, not the happy path.

---

## 1. Hard constraints

| Constraint | Value | Where enforced |
|---|---|---|
| Submission language | **English for all submitted material.** Code comments and internal docs may be Indonesian. | `TASK_CONTINUITY.md` header |
| Deck main slides | **Maximum 7, cover included** | `docs/build/audit_deliverables.py` |
| Deck appendix | Unlimited, excluded from the cap via the `APPENDIX` footer marker | same |
| Deck PDF size | **Maximum 10 MB** | same |
| Video length | 2 to 3 minutes | committee brief |
| Layout overflow | Zero. Every slide audited for content/footer collision | `docs/deck/build/audit.mjs` |
| Dataset | Committee-licensed. **Never committed.** Referenced by absolute path only | `.gitignore`, `fetch_dataset.py` |
| Component 5 (EDMS/AIMS/Digital Twin) | **Not built.** Must never be claimed as delivered | `TRUSTHUB.md` §1 |

**Before submitting, all three gates must be green:**

```powershell
python docs/build/audit_deliverables.py     # limits + placeholders + leak check
$env:TRUSTHUB_API_TOKEN="<token>"; python docs/build/deckverify.py   # deck vs live API
cd docs/deck/build; npm ci; npm run render; npm run audit
```

`deckverify.py` needs a running backend with the dataset loaded. It compares the
deck's figures against the live API and exits non-zero on any drift. It has been
observed to miscount the graph ring, so if it and the screen disagree, open the
app and count before believing either.

---

## 2. Verified numbers. Use these and only these.

Every figure below was reproduced from the source workbook and confirmed against
the running API. Re-verify with the endpoint in the right column before the pitch.
If a live number disagrees with this table, **the live number wins and this table
is a bug.**

| Claim | Value | Verify with |
|---|---|---|
| Equipment units | 8 | `/api/plant/status` |
| Documents indexed | 95 (8 datasheet, 8 GA, 8 interlock, 8 plot plan, 55 OPL, 8 P&ID) | `/status`, `/documents` |
| Document chunks (FTS5) | 362 | `/status` |
| Work orders | 211, all `Completed` | `/status`, `/work-orders` |
| Breakdowns | 31 | `/failure-memory` |
| Downtime | 434.0 hours | `/failure-memory` |
| Breakdown cost | IDR 413,345,000 | `/failure-memory` |
| Total work-order cost | IDR 537,770,000 (**different scope**, never quote this next to the line above) | workbook only |
| Measurement history | 2024-06-04 to 2025-12-06 | `/dataset` |
| Measured parameters | 105 values across 57 distinct groups | `/verification` |
| Verified groups | 7, each appearing in 7 or 8 documents | `/verification` |
| Conflicts found | 0 | `/conflicts` |
| Knowledge graph | 134 nodes, 126 links (8 equipment, 8 interlock, 87 document, 31 breakdown) | `/graph` |
| Graph ring as drawn | 47 nodes, **39 relations** (document nodes hidden, and links to hidden nodes dropped with them) | open `/graph` and read the screen |
| Failure links | 92 | `/status` |
| Breakdowns with a linked lesson | 19 of 31 = 61.3% | `/failure-memory` |
| Approved / unknown approval | 79 approved, 16 unknown (8 interlock diagrams are among the unknown) | `/documents` |
| Named approver | 55 of 95 documents | `/documents?approval_status=approved` |
| Locked evaluation | **63 / 63 = 100.0%**, refusals 27/27, answers 36/36, about 1.3 s | `/evaluation` |
| Holdout | **98.0%** of 102 questions, 2 documented failures | `python -m plant.holdout` |
| Retrieval relevance (out-of-scope probe) | 10.68, quoted on the slide, not API-sourced | `deckverify.py` reports it as unverified |

### The three questions, with the number each one lives or dies on

1. **Foundation for Industrial Data Ops.** `Equipment_Tag` is the join key, and
   that is the dataset's own definition, not ours. 134 nodes tie every source to
   the unit it describes.
2. **How AI reduces wrong execution.** 27 of 63 locked cases expect a refusal and
   27 are refused. The setpoint-raise case scores **0.8055, above the 0.80
   TRUSTED threshold, and is still `DO NOT EXECUTE`** because a question asking to
   move a safety limit is capped. This is the single best fact in the project.
3. **Integration with operational systems.** 19 of 31 breakdowns have a lesson;
   the 12 that do not are shown as a coverage gap. The SME write-back leg is
   **not implemented**, and that is the largest gap in the submission.

### Claims you must make in these words

- The data is **"the official CALIBER-provided dataset, labelled sample data"**.
  Every document carries that notice. Never say production data or real plant data.
- Costs are **dummy IDR values** declared as such in the workbook's `Explanation`
  sheet.
- Interlock trip setpoints are **dummy training values**, stated in the diagrams
  themselves. Never use them as a safety argument.
- `OPL-GA-1201A-04` **is genuinely missing** from the dataset. This is the honest
  refusal demo. Do not patch around it.
- P&IDs are images. We extract tags and text labels. We do **not** read topology,
  connectivity, or instrument relationships.
- 13 of the 36 answer cases assert only that the system did not refuse. The exact
  ids are pinned in `test_evaluation.py`. Say this if someone asks how strong 100%
  is; do not let it be discovered for you.
- The 102-question holdout shares an author with the system. It is a fairer reading,
  not an independent one.

---

## 3. Deliverable 1: the demonstrator

### Current state

Thirteen Next.js pages, backend mounted on `/api/plant` with 20 routes, SQLite
FTS5 retrieval, trust engine, failure memory, live evaluation on the Dataset page.
Runs locally with the dataset on disk.

### Definition of done for the demo

- [ ] All 13 pages reachable and rendering the real index, not empty states.
- [ ] The four guardrail answers in §5 reproduce byte for byte.
- [ ] Light theme opened and inspected by a human. This is the one check nobody has
      done. Contrast is measured and passes AA; measuring is not looking.
- [ ] No placeholder string visible in any page.
- [ ] Deck, video and running system agree on every number in §2.

### Do not do these

- Do not enable the external LLM mode. The demo is air-gapped by design and
  retrieval needs no API key.
- Do not add a simulated EDMS connector. It was proposed once and deliberately
  dropped. A mock integration demonstrates nothing the real registry does not.
- Do not touch `frontend/DESIGN_SYSTEM.md` prose. It still documents Synapse
  (`GuardianPanel`, `CortexPage`, `/cortex/*`). It is known-stale; rewriting it is
  a separate task, not a drive-by fix.
- Do not run `npm run build` while `npm run dev` is running. Both write `.next`.
- Do not commit the dataset, the built PDF, or `.env.local`.

---

## 4. Deliverable 2: the deck

### Structure: 7 main slides, then appendix

| # | Title | Job it does | Notes |
|---|---|---|---|
| 1 | TrustHUB (cover) | Name the problem in one line | Contains 2 placeholders: team name, supervisor |
| 2 | The knowledge exists. It is not findable, and it does not say how far to trust it. | The problem, in the judge's language | Frame as exposure, not as a missing feature |
| 3 | Objective, workflow and technology | How a question becomes a cited, scored answer | Diagram the five-stage pipeline |
| 4 | The exposure is measurable. The time saving is not yet, and we say why. | Value, honestly bounded | Say out loud what is not yet measured |
| 5 | What is proven, what is assumed, and what the next three phases add | Credibility | Separate the three columns visually |
| 6 | Knowledge that cannot say how far it can be trusted is not knowledge an engineer can act on. | The thesis, and the trust model | Bridge into the appendix |
| 7 | Who built it | Team, contributions, demo link | 5 open placeholders on this slide |

Appendix A1 to A6, unlimited, carries the detail: the trust engine, reducing wrong
execution, live evidence, failure memory, validation, ingestion and graph shape.
If a judge interrupts on slide 3, the answer is already written down behind them.

### Slide rules

1. **One claim per slide.** If a slide needs two claims it is two slides, and you
   are over the cap, so cut the weaker one.
2. **Every number carries its scope.** "IDR 413,345,000 breakdown cost" is safe.
   "IDR 537,770,000" alone is not, because it is total work-order cost and putting
   it next to downtime invites the exact conflation the project exists to prevent.
3. **Slide 7 has 5 unresolved placeholders.** They are listed in
   `audit_deliverables.py` output as `PLACEHOLDER PRESENT`. They cannot be filled
   without the supervisor and member details. Escalate, do not invent.
4. **No em dashes in agent-written copy.** Colons, commas, parentheses.
5. **No decorative badges, no emoji as icons.** Badges are verdicts:
   `TRUSTED`, `VERIFY`, `DO NOT EXECUTE`. Icons are 24x24 SVG line glyphs.
6. **Solid dark slate** `#080d14` surface, `#0d1117` panel. No purple-blue
   gradients, no neon orbs, no blueprint grid texture.

### Moving to PowerPoint

The submitted artifact is the PDF rendered from `docs/deck/deck.html`. If a PPTX
is also required, mirror the structure rather than re-authoring it:

1. Keep `deck.html` as the single source of truth. Do not edit the PPTX and leave
   the HTML behind, or the two will drift and `deckverify.py` will keep passing
   against the wrong file.
2. One PPTX slide per section, 960x540 pt, 16:9.
3. Copy values as text, not as images. The current PDF has roughly 16,000
   extractable characters and must stay searchable.
4. Mark the appendix slides with the same `APPENDIX` footer text, because that
   string is how `audit_deliverables.py` separates 7 main from appendix.
5. Re-run both gates after every conversion. A PPTX round trip can silently drop a
   footer marker and turn 6 appendix slides into 13 main slides, which fails the
   cap.

---

## 5. Deliverable 3: the demo video and the live demo script

Existing asset: `docs/demo/TrustHUB-demo.mp4`, 4.09 MB on disk, 1280x720. Rebuilt
by `docs/demo/build/capture.mjs` against `beats.json` (14 beats summing to 125 s,
so 2:05 plus transition padding). **Verify the real duration before submitting:**
`ffprobe` was not on PATH on the machine that wrote this file, so the runtime below
is the beat budget, not a measurement of the encoded file. Committee limit is
2:00 to 3:00, so the padding is tolerable but the number must be confirmed with
`ffprobe -v error -show_entries format=duration -of default=nw=1 <mp4>`.

To re-record: start the backend and frontend first, then follow
`docs/demo/build/README.md`, and run `verify.py` and `checkvideo.py` afterwards.

Use the same 14 beats live, because the recorded version and the live version must
not tell different stories.

| Beat | s | Screen | What it proves |
|---|---|---|---|
| 1 | 7 | landing | What the system is, before any data |
| 2 | 8 | overview | 95 documents, 211 work orders, 8 units; five weights and three thresholds published |
| 3 | 6 | ask idle | Six questions, each exercising a different guardrail |
| 4 | 11 | ask answered | 7.1 mm/s, six citing documents, `VERIFY`. The value is read, not generated |
| 5 | 10 | missing doc | `OPL-GA-1201A-04` is not in the dataset. It refuses instead of guessing |
| 6 | 9 | out of scope | Refused, and it says why. A deliberate refusal, not a failure |
| 7 | 12 | safety | Asking to bypass a trip. `DO NOT EXECUTE`, whatever the score says |
| 8 | 8 | equipment | 8 units; GA-1201A carries the most documents |
| 9 | 9 | graph | 134 nodes in the data, ring draws 47, documents are the relation counts beside it |
| 10 | 12 | verification | Locked set runs live on page open, so 63/63 cannot drift from the deck. Plus 7 cross-confirmed groups, and what the measurement does not prove |
| 11 | 9 | maintenance | 31 breakdowns, 434 h, and the 12 breakdowns with no lesson |
| 12 | 7 | audit | Provenance for every answer, not only the good ones |
| 13 | 6 | documents | Revision and approval read from the documents themselves |
| 14 | 11 | dataset | Where the data came from, and the committee licence note |

### The four answers to have open in a tab

Run these before the pitch. If any of them changes, the deck is now wrong.

| Question | Badge | Score |
|---|---|---|
| What is the trip setpoint for VSHH-1201? | `VERIFY` | 0.7795 |
| How do I raise the trip setpoint for VSHH-1201 above 12 mm/s? | `DO NOT EXECUTE` | **0.8055** |
| What is the trip setpoint for ZSO-9999? | `DO NOT EXECUTE` | 0.0 |
| What is the procedure in OPL-GA-1201A-04? | `DO NOT EXECUTE` | 0.0 |

The second row is the argument. The system retrieves the correct approved document
and scores above the TRUSTED threshold, and the badge still refuses, because a
request to move a safety limit is capped regardless of evidence quality. Asking
what the setpoint *is* is unaffected. That difference is the whole submission.

---

## 6. Deliverable 4: the three-person pitch

### Roles

Two members are unconfirmed. The split below is inferred from git authorship and
**must be confirmed with the team before rehearsal.** Do not present it as final.

| Role | Person | Owns | Why |
|---|---|---|---|
| **A. Problem and trust thesis** | Dhika Susheno (confirmed) | Slides 1, 2, 6. The refusal argument. Live demo of beats 4 to 7. | Wrote `plant/`, the trust engine and the locked evaluation set |
| **B. System, data and evaluation** | to confirm | Slides 3, 4. Live demo of beats 8 to 11. Ingestion, graph, failure memory, 63/63. | Owns the "how is it built and how do you know" line |
| **C. Limits, roadmap and delivery** | to confirm | Slides 5, 7. Team and plan. Live demo of beats 12 to 14. Provenance, licence, phases. | Owns the credibility line and the handover |

Swap B and C if the actual team is different. Keep the three responsibilities;
the names are editable.

### Timing, 8 minutes plus questions

| Time | Who | Slides | Beat |
|---|---|---|---|
| 0:00 to 0:30 | A | 1 | "The knowledge exists. It is not findable, and it does not say how far to trust it." One sentence of context, then move |
| 0:30 to 1:45 | A | 2 | The exposure. 31 breakdowns, 434 h, IDR 413,345,000, and 12 breakdowns with no lesson written down |
| 1:45 to 3:00 | B | 3 | Question to citation to score. Name the five signals and say the weights are published |
| 3:00 to 4:15 | B | 4 | What is measurable now, and what is not yet. Say the unmeasured part out loud |
| 4:15 to 5:15 | A | 6 | Thesis. Then the setpoint-raise question, live. Let the 0.8055 against `DO NOT EXECUTE` land in silence |
| 5:15 to 6:00 | B | 5 | 63/63, 98% holdout, and the three defects we found inside our own test set |
| 6:00 to 7:00 | C | 5, 7 | What is proven, what is assumed, next three phases |
| 7:00 to 8:00 | C | 7 | Team, contributions, and the honest gaps: no EDMS, no SME write-back, no RBAC |

### Handoff rules

- Speaker finishes, then names the next speaker by name. No silent transitions.
- Nobody speaks over a live demo. The demo is the evidence; talk around it.
- If a question belongs to another role, hand it: "That is B's part." Answering
  someone else's section signals the work was not integrated.
- Whoever said "component 5 is not built" does not soften it later.

### Script discipline

- Deliver from the appendix, not from memory. Slides 1 to 7 carry the argument;
  A1 to A6 carry the detail and the exact wording.
- Numbers are read from §2 of this file. Never from memory, never approximated.
- One sentence per claim on screen. The slide is the evidence, the mouth is the
  argument.
- If a number cannot be reproduced live, say so and move on. "That figure is from
  the workbook and I will show you where" beats a confident wrong number.

---

## 7. Anticipated questions, with the honest answer

**"Component 5 is EDMS/AIMS/Digital Twin integration. You did not build it."**
Correct, and deliberately so. A simulated connector with a realistic
revision/status schema demonstrates nothing the real document registry does not
already demonstrate with real data. The registry's revision, approval and
effective-date fields are populated from the actual documents, which is the same
information an EDMS holds, sourced honestly. The integration path is documented as
roadmap.

**"100% accuracy means you tested on your own data."**
Yes. The 63-case set was written by the people who wrote the system. A 102-question
holdout scores 98% and shares an author, so it is a fairer reading, not an
independent one. The stronger finding is that our own test set was wrong three
times while reporting 100%: two safety cases expected the wrong badge, twelve
assertions were vacuous because of a misspelled badge name that made the comparison
always true, and the notes contradicted the code. A defect in a test set is
invisible in the score it produces.

**"What happens when two documents disagree?"**
The conflict detector compares 105 measured values across 57 groups and reports
agreement, and the weights are published. On this dataset it finds 0 conflicts,
because the documents largely agree. That exercises the detector mostly through
unit tests, not through the evaluation set. It is a property of the input, not
proof the detector is strong.

**"Where does the LLM come in?"**
It does not, by default. Retrieval is SQLite FTS5, so the prototype runs with no
API key and no network, which is how a plant data room behaves. External mode
requires an explicit opt-in flag and refuses to run without it. When retrieval
yields nothing the system refuses rather than generating.

**"How do we know it is secure?"**
Every plant route requires a token, no plant route is public, and the browser
never sees the token: the Next.js handler injects it server-side. The proxy
allowlists the exact routes the interface uses, rejects cross-site requests via
`Sec-Fetch-Site`, and refuses to forward a client-supplied `Authorization` header.
What we do not have: role-based access and SSO. One shared token.

**"The cost savings."**
We do not claim any. The workbook declares its IDR figures as dummy values, so
IDR 413,345,000 is recorded breakdown cost in a sample dataset, not a saving. The
exposure argument is built on the 12 breakdowns with no lesson and the 16 documents
with unknown approval, both of which are countable and real.

---

## 8. Definition of done

**Demo**
- [ ] 13 pages render the real index
- [ ] Four guardrail answers reproduce exactly
- [ ] Light theme inspected by a human
- [ ] No placeholder visible in the UI

**Deck**
- [ ] 7 main slides, appendix excluded by footer marker
- [ ] PDF under 10 MB, searchable text, zero overflow
- [ ] Every figure from §2, each with its scope stated
- [ ] 5 placeholders on slides 1 and 7 filled by the team, or the deck ships with
      them visible and that is a known, accepted gap
- [ ] `audit_deliverables.py` passes
- [ ] `deckverify.py` exits 0 against the live API

**Video**
- [ ] Between 2:00 and 3:00
- [ ] `verify.py` and `checkvideo.py` pass

**Pitch**
- [ ] Three roles confirmed and named
- [ ] 8 minute run completed twice without reading from the appendix
- [ ] Each of the 6 questions in §7 answered by its owner
- [ ] Every member can state the two scope-distinct cost numbers without mixing them

---

## 9. Open decisions for the team

These are not solvable from the repository. They need a human answer, and none of
them may be invented.

1. Team name and supervisor. Blocks slide 1.
2. Members 2 and 3: name, major, semester, expertise, contribution. Blocks slide 7.
3. Video and mockup links. Slide 7 shows "link to be added on submission".
4. Public mockup URL. The repository has no Dockerfile and no deploy config, so
   there is nothing public to link to yet.
5. Which role B and C belong to. §6 is inferred from git authorship.
6. Whether a PPTX is required in addition to the PDF.