# Master Prompt - Backend (Guardian + Cortex)

Turunan scoped dari master prompt penuh di [`../TRUSTHUB.md`](../TRUSTHUB.md) section 1. Pakai ini sebagai brief awal ke Bob 2.0 / AI agent kamu untuk kerja mandiri di folder `backend/`.

> **Revisi 2026-10-02.** Tool Guardian/Cortex masih hidup dan masih jadi
> bagian kontrak, tapi demo yang ditampilkan hari ini adalah domain plant
> (`/api/plant/*`). Prompt ini sebelumnya tidak menyebut router plant sama
> sekali, dan urutan prioritasnya masih menunjuk Guardian/Cortex sebagai
> prioritas 1. Bagian di bawah diverifikasi ulang terhadap `main.py`,
> `plant/api.py`, dan filesystem.

---

```
You are building the BACKEND half of "TrustHub" - a reversible, conflict-aware
understanding layer for AI coding agents (IBM Bob 2.0 Hackathon).

ROLE: You own the MCP server (FastAPI). Frontend and Security/QC consume your
API and SSE stream as black boxes - do not change the agreed contract (SQLite
schema in TRUSTHUB.md 4.2, SSE event shape) without syncing with them first.

## ROUTE MAP - read this before you touch routing

`main.py` declares ~40 routes directly and mounts one extra router. Full
inventory:

| Group | Mount | Routes |
|---|---|---|
| Plant Knowledge Hub | `plant/api.py` via `include_router` at `main.py:163`, prefix `/api/plant` | 20: status, dataset, reindex, equipment (+4 nested), documents (+1), graph, ask, search, trust/weights, conflicts, verification, evaluation, failure-memory, work-orders, audit |
| Guardian | `main.py` | propose_operation, execute_operation, list_pending_approvals, approve_operation, operations |
| Cortex | `main.py` | understand_repo, explain_topic, review_artifact, repo_health, complexity_report, find_path, suggest_refactor |
| Engine | `main.py`, `include_in_schema=False` | ingest_repository, ask_about, review_change, health_report, rank_complexity, trace_connection, propose_refactor, propose_operation |
| Targets | `main.py` | browse, list, create, patch, activate, delete |
| Settings | `main.py` | GET/POST settings, POST settings/reset, GET browse |
| Graph | `main.py` | nodes, edges, summary |
| GitHub | `main.py` | auth url/callback, delete connection, PAT, user, repos, tree, contents, sync |
| LLM | `main.py` | providers CRUD, models, discover, chat, explain, review, refactor, project llm-config |
| RAG | `main.py` | ingest, search |
| SSE | `main.py` | GET /stream |

Two consequences that are easy to get wrong:

- `/api/plant/*` is **not** written in `main.py`. Editing `main.py` will never
  show you a plant route; edit `plant/api.py`.
- Several routes are `include_in_schema=False`, so they are invisible in
  `/docs` while still being live. Absence from the schema does not mean the
  endpoint is gone.

## WHICH HALF IS CASE 1 - the master already answers this

Do not decide this yourself. `../TRUSTHUB.md` is the case-mapping document for
CALIBER 2026 Case 1, and it settles the question twice:

- **Section 1** lists the six required Case Book components. Five are real and
  every one of them is plant-domain, mapped to `plant/`. Component 5, EDMS/AIMS
  integration, is declared **not built**, and the master explains at length why
  a simulated connector was deliberately dropped.
- **Section 5** states that `plant/` never imports `main.py`, is mounted as an
  independent router, and calls the surrounding application "the inherited
  Synapse application" - mounted specifically so the Case 1 code "can be lifted
  out without surgery".

So `/api/plant/*` is the Case 1 surface, by the master's own account. Guardian,
Cortex, Graph, GitHub, LLM, RAG, Targets, and Settings are the inherited
application around it. Keep them working; do not present them as Case 1
deliverables, and do not add a Case 1 feature that depends on them. If a
proposed change would make `plant/` import `main.py`, stop - that breaks the
master's stated architecture.

## GOAL: Implement two capability groups

1. GUARDIAN (BE-1) - before executing any risky, hard-to-reverse operation
   (schema migration first, others are stubs), generate a reversibility
   plan, gate it by risk, execute, verify post-conditions, auto-rollback on
   failure. Before acting, check whether any other in-flight/recent
   operation touches an overlapping resource (conflict-aware gating).
2. CORTEX (BE-2) - ingest a target repo (tree-sitter AST pass for
   files/functions/classes/imports, then read README/docs and propose
   DOCUMENTS/EXPLAINS/REFERENCES edges), answer "explain this module"
   questions from the graph, and (nice-to-have) score artifacts/diffs.

Plant data access is a third, newer group that the original brief does not
mention: `plant/` holds ingestion, retrieval, trust weighting, and conflict
scoring over the CALIBER dataset. Treat it as first-class, not a demo hack.

## TOOLS YOU EXPOSE

Guardian + Cortex, exact signatures in `../TRUSTHUB.md` section 1:
`understand_repo`, `explain_topic`, `review_artifact`, `propose_operation`,
`execute_operation`, `list_pending_approvals`, `approve_operation`.

## SECURITY POSTURE - you own all of this

These are load-bearing and easy to break by accident:

- **Every route requires `X-TrustHub-Token`** via `enforce_api_token` in
  `main.py`, unless it is in `PUBLIC_PATHS` in `auth.py`. The public set is
  exactly `/health`, `/docs`, `/redoc`, `/openapi.json`,
  `/docs/oauth2-redirect`.
- **`TRUSTHUB_PUBLIC_PATHS` widens that set from the environment.** It is
  intentionally separated from the default set in code so the safe baseline
  stays readable. Never move a default path out, and never add a path to it
  without flagging it to Security/QC.
- **`FERNET_KEY` from the environment wins.** If it is absent, `auth.py`
  generates a key and persists it to `backend/.fernet_key`. That file is
  gitignored, but it sits next to the SQLite DB, so a backup of the repo
  directory carries both. Treat "where does the Fernet key live" as a
  security question, not a convenience one.
- **`settings.py` validates paths against allowed roots and a sensitive-file
  denylist** (`.env`, keys, credentials). Regression tests live in
  `../security/tests/test_issue_63_66_path_security.py`. Do not weaken the
  denylist without reading that file first.
- **No endpoint may log or echo a token.** The frontend proxy already strips
  client `Authorization` and `X-TrustHub-Token` headers and rewrites the token
  last, so the backend sees exactly one token header.

`trusthub.invariants.yaml` at the repo root of `backend/` is the declared
invariant list. It has one top-level key, `invariants`. If you change a
behavior that an invariant covers, update that file in the same commit.

## CONSTRAINTS

- No Redis, no Neo4j, no Qdrant, no Ollama. Storage = SQLite + in-memory
  networkx. Must run with `pip install -r requirements.txt && uvicorn
  main:app` and nothing else.
- Ship DB migration end-to-end BEFORE any other operation type.
- Every risky action MUST have a rollback plan or MUST require human
  approval - fail-closed default for unknown operation types.
- Build a scripted, reproducible failure scenario (a migration that breaks
  something on purpose). `demo_migration_script.py` and `demo_reset.py` exist
  for this - this is the single most important scene.

## KNOWN DEBT - do not fix opportunistically

- **Guardian uses a polymorphic foreign key** for operations, referenced from
  `guardian.py` around line 1027 and declared in `database.py` around lines
  66-75. It has no enforcement and no clean migration path. It is documented as
  postponed because a partial fix risks data loss. Leave it alone unless the
  task is explicitly about it.
- **Dependencies are pinned old.** `python-multipart==0.0.9` in particular.
  Bumping is fine, but do it in its own commit with tests, never mixed into a
  feature.
- **`backend/.fernet_key` is generated per-machine.** Deleting the DB without
  deleting the key, or vice versa, produces an unreadable database. Document
  the pairing.

## PRIORITY ORDER (stop anywhere, still demoable)

1. Keep `/api/plant/*` answering for the demo dataset - a broken demo surface
   outranks everything below it.
2. `propose_operation` + `execute_operation` for migration, with conflict-check.
3. `understand_repo` + `explain_topic`.
4. `review_artifact` (cut first if time is short).
5. SSE stream polish - frontend needs this to render live, don't gold-plate.

## OUTPUT OF EVERY STEP

Keep the SQLite graph and the SSE event log as the single source of truth -
frontend renders straight from these, no duplicate state. Do not touch
`frontend/` or `security/` folders.
```

## Checkpoint sync wajib

Jam 0-2: sepakati bentuk event SSE dengan FE-1/FE-2 (lihat `../frontend/MASTER_PROMPT.md`). Jam 16: demo internal pertama harus jalan meski kasar.