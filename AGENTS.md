# TrustHUB Agent Guidelines (`AGENTS.md`)

> Guidance for AI coding agents (Claude, Codex, Antigravity, OpenCode, Kimi) working on TrustHUB.

## 1. Domain & Architecture Source of Truth
- Primary Master Document: [`TRUSTHUB.md`](./TRUSTHUB.md) (Case Mapping for CALIBER 2026 Case 1: Manufacturing Knowledge Hub).
- Backend Brief: [`backend/MASTER_PROMPT.md`](./backend/MASTER_PROMPT.md) (FastAPI + SQLite, `/api/plant/*`).
- Frontend Brief: [`frontend/MASTER_PROMPT.md`](./frontend/MASTER_PROMPT.md) (Next.js 15 + React 19 + Tailwind).
- Security & QC Brief: [`security/MASTER_PROMPT.md`](./security/MASTER_PROMPT.md) (Evaluation integrity, fail-closed security).

## 2. UI / UX Design & Anti-AI-Slop Filter
For any UI, layout, copywriting, or styling work on TrustHUB, read [`DESIGN.md`](./DESIGN.md) and [`frontend/DESIGN_SYSTEM.md`](./frontend/DESIGN_SYSTEM.md) first:
- **Style Direction:** Industrial data room, high-density plant telemetry, `#080d14` slate background.
- **Anti-Slop Filter:**
  - FORBIDDEN: Generic blue/purple gradients, neon orbs, blueprint background grids.
  - FORBIDDEN: Invented stats, fake testimonials, fake numbers.
  - FORBIDDEN: Em dashes (`—`) in agent-written copy.
  - FORBIDDEN: Emojis used as navigation icons.
  - REQUIRED: High-contrast WCAG AA accessible light/dark themes, mandatory trust badges (`TRUSTED`, `VERIFY`, `DO NOT EXECUTE`), 24×24 SVG line icons, monospace tags (`GA-1201A`, `VSHH-1201`).
