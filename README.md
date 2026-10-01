# TrustHub

Reversible, conflict-aware understanding layer for AI coding agents.
Built for the **IBM Bob 2.0 Hackathon** (lablab.ai), 25–27 Sept 2026.

TrustHub gives an AI coding agent two things: a live map of how code connects
(for onboarding & review), and an automatic reflex that reverses risky
operations before they become disasters — even when multiple agents are
working at once.

Full PRD, master prompt, and architecture: [`TRUSTHUB.md`](./TRUSTHUB.md).
48-hour build flow diagram: [`trusthub-build-flow.html`](./trusthub-build-flow.html).

## Team (6 orang, 3 tim, kerja mandiri masing-masing dengan Bob 2.0 + AI tools lain)

| Tim | Orang | Fokus | PRD | Master Prompt |
|---|---|---|---|---|
| Backend (`/backend`) | [@DhikaSusheno](https://github.com/DhikaSusheno) · [@Masrendra](https://github.com/Masrendra) | Guardian (propose/execute/rollback) + Cortex (ingest/mentor/review), MCP server | [PRD](./backend/PRD.md) | [Master Prompt](./backend/MASTER_PROMPT.md) |
| Frontend / UI-UX (`/frontend`) | [@nabilfauzandafa](https://github.com/nabilfauzandafa) · [@ShannWasHere](https://github.com/ShannWasHere) | Live graph (force-graph) + dashboard (sidebar, approve/deny), SSE consumer | [PRD](./frontend/PRD.md) | [Master Prompt](./frontend/MASTER_PROMPT.md) |
| Security & QC (`/security`) | [@pidpid35](https://github.com/pidpid35) · [@zuyss](https://github.com/zuyss) | Rule engine tests, adversarial/fail-closed testing, demo reliability, rollback verification | [PRD](./security/PRD.md) | [Master Prompt](./security/MASTER_PROMPT.md) |

Ownership per folder is enforced via [`CODEOWNERS`](./.github/CODEOWNERS). Setiap tim kerja mandiri dari PRD + Master Prompt masing-masing (diturunkan dari [`TRUSTHUB.md`](./TRUSTHUB.md) — kontrak SQLite schema, rule table, dan SSE event shape tetap satu sumber kebenaran bersama, dikunci di jam 2).

## Workflow (48 jam)

Lihat detail lengkap tiap fase & tugas per orang di `trusthub-build-flow.html`.
Ringkasan fase:

| Fase | Jam | Checkpoint |
|---|---|---|
| Setup | 0–2 | Skema SQLite & kontrak MCP dikunci |
| Build paralel | 2–16 | Demo internal pertama di jam 16 |
| Integrasi | 16–30 | Semua temuan QC masuk daftar perbaikan di jam 30 |
| Pengerasan | 30–40 | Rehearsal penuh mulai jam 40 — stop nambah fitur baru |
| Rehearsal | 40–46 | Video fallback demo direkam |
| Submit | 46–48 | Kirim lebih awal dari deadline |

## Stack (tanpa dependency server eksternal)

- Backend: Python + FastAPI, SQLite (`nodes`/`edges`/`operations`/`approvals`) + `networkx`, tree-sitter, SSE bawaan FastAPI.
- Frontend: Next.js + `react-force-graph-2d`.
- Tidak ada Redis/Neo4j/Qdrant/Ollama.

## Menjalankan secara lokal

Semua command dijalankan dari root repo. Dua service yang harus hidup:

```bash
# Terminal 1 - backend (WAJIB 127.0.0.1, bukan localhost: di Windows
# localhost lebih dulu di-resolve ke ::1, sedangkan uvicorn bind IPv4)
cd backend
../venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000

# Terminal 2 - frontend
cd frontend
npm run dev          # http://127.0.0.1:3000
```

Konfigurasi minimum: `TRUSTHUB_API_TOKEN` yang **sama persis** di `backend/.env`
dan `frontend/.env.local` (lihat `backend/.env.example` dan
`frontend/.env.local.example`). Tanpa itu, proxy membalas 502.

Path proxy frontend adalah `/backend`, bukan `/api/backend` — contoh lengkap:

```
POST http://127.0.0.1:3000/backend/api/llm/chat
X-TrustHub-Token: <TRUSTHUB_API_TOKEN>
```

## Test

```bash
# Semua test - WAJIB dari root repo (pytest.ini yang menentukan testpaths)
venv/Scripts/python.exe -m pytest -q

# Test saja
cd security && python -m pytest -q

# Frontend
cd frontend && npm test && npm run typecheck && npm run lint
```

Tool bantu lokal: `backend/tools/mock_llm.py` (server OpenAI-compatible tiruan,
untuk verifikasi rantai LLM tanpa menarik model) dan
`backend/tools/find_undefined.py` (pemeriksaan statis nama yang belum
didefinisikan — dijaga oleh `backend/tests/test_no_undefined_names.py`).

## License

MIT — lihat [`LICENSE`](./LICENSE).
