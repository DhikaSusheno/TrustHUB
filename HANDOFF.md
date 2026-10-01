# HANDOFF

Work-state notes for the next session. This file is not a brief — the brief is
[`TRUSTHUB.md`](TRUSTHUB.md), the Case Book mapping. See also
[`README.md`](README.md) for how to run it and [`TASK_CONTINUITY.md`](TASK_CONTINUITY.md)
for the full chronological log.

## What this repository is

CALIBER 2026 Case 1, *Manufacturing Knowledge Hub*. A plant knowledge hub for
8 units of a polyolefin plant: it indexes the official document set, answers
questions with a source citation, and attaches a trust verdict to every answer.

Rebranded in place from `DhikaSusheno/Synapse`. The frontend under `frontend/`
is a rewrite — the Synapse UI was deleted (54 files) rather than adapted.

## State: the deliverable is complete and verified

| Area | Status |
|---|---|
| Backend, 20 routes under `/api/plant` | done, verified against the real dataset |
| Trust Engine | done, weights fixed and documented |
| Dataset ingestion | done, 95 documents / 362 chunks / 211 work orders |
| Evaluation set, 63 locked cases | 63/63 = 100.0%, spec version 1.2 |
| Holdout, 102 questions | 98.0%, 2 documented failures |
| Frontend, 9 pages | done, 9/9 verified in headless Chrome |
| Backend test suite | 1329 passed, 31 skipped, 1360 collected (CI/ubuntu) |
| CI | green on both `feat/caliber-case1` and `main` |

Everything measured is in `README.md` and `TRUSTHUB.md`. Do not add a number to
either file that you have not just measured.

## Working rules that were learned the hard way

**Never fabricate a number.** If a figure is not in the measured list below,
measure it before writing it. The dataset is sample data; the interlock
setpoints say so themselves, and the workbook costs are dummy IDR values. Quote
them as what they are.

**Never commit the dataset.** It is under the committee's licence. `.gitignore`
plus `python -m plant.fetch_dataset`. Confirm no `.db` or `.sqlite` file is
tracked before pushing.

**Tests must pass without the dataset.** CI has no dataset, so a
dataset-dependent test is a defect, not a coverage gap. Use the
`stub_dataset_root` / `requires_official_dataset` helpers in
`backend/tests/plant/conftest.py`.

**If a guardrail changes behaviour, re-read the evaluation set.** The
safety-modification cap found three defects in the locked set that no score had
ever shown. A defect in a test set is invisible in the score it produces.

## Measured facts

Ingest: 95 documents (opl 55, datasheet 8, ga 8, interlock 8, pid 8, plot_plan
8), 362 chunks, 8 equipment, 211 work orders, 92 failure links, 105 measured
parameters (79 linear + 26 tables), 79 approved + 16 unknown, 28 instrument
tags, 32 distinct `doc_no`.

Trust: 0 conflicts found, 0 needing SME, **7 verified groups** (never 15), 57
distinct parameter groups, 56 checkable groups. Graph: 134 nodes, 126 links.

Work orders: 211 total, 31 breakdowns, 434.0 h, IDR 537,770,000 total cost,
IDR 413,345,000 breakdown-only cost — different scopes, do not conflate. 19 of
31 breakdowns (61.3%) have a linked OPL.

## Running it

```bash
# backend
pip install -r backend/requirements.txt
export TRUSTHUB_API_TOKEN=<something-long>
export TRUSTHUB_DATASET_ROOT=/path/to/dataset
python -m plant.fetch_dataset
python -m plant.evaluation            # 63/63, exits non-zero if accuracy drops
python -m plant.holdout --fail-under 95   # needs the dataset, not in CI
uvicorn main:app --port 8000

# frontend
cd frontend
npm ci
npm run dev                          # proxies /api to the backend
```

Auth header is `X-TrustHub-Token`. The frontend proxy in
`frontend/app/backend/[...path]/route.ts` holds the token, so it never reaches
the browser. LLM is off by default: `TRUSTHUB_PLANT_LLM_MODE=off|local|external`,
and `external` additionally requires `TRUSTHUB_PLANT_ALLOW_EXTERNAL_LLM=1`.

## Deliberately not built

Component 5 (EDMS / AIMS / Digital Twin) is unbuilt and documented as such. No
mock connector was added to make the diagram look complete. The Case Book was
clear that a well-justified architecture beats more data.

## Environment notes for this machine

- `pytest` lives only in `C:\Users\dhika\Synapse\venv\Scripts\python.exe`.
- Never run `npm run build` while `npm run dev` is live — they share `.next/`.
- Commit messages: write them with Python and use `git commit -F`. `git commit -m`
  mangles escaped quotes in PowerShell.
- Read text with `Get-Content -Encoding UTF8`; without it `▸ ● —` renders as `?`.
- Generated prose in this repo has picked up stray CJK characters. After editing
  any `.md` or docstring, scan for chars above `U+2E80` outside the allowlist
  (`→ — – ↔ § °`).