# Master Prompt - TrustHub Frontend

Prompt siap salin untuk AI agent yang melanjutkan pekerjaan frontend TrustHub.
Wraps [`PRD.md`](./PRD.md) dan [`DESIGN_SYSTEM.md`](./DESIGN_SYSTEM.md).

Konteks produk penuh: [`../TRUSTHUB.md`](../TRUSTHUB.md).

> **Revisi 2026-10-02.** Prompt ini sebelumnya menyebut Next 14 + React 18,
> route `/api/graph`, komponen `RiskBadge`/`StatusBadge`/`AgentBadge`/
> `TopNavbar`/`TrustHubGraph`/`GuardianPanel`, dan kelas `bg-[#0d1117]`.
> Semua itu sudah tidak ada. Bagian di bawah diverifikasi ulang terhadap
> `package.json` dan filesystem. Jangan restore angka lama dari versi prompt
> sebelumnya.

---

## Cara pakai

Salin blok di bawah ke agent yang bekerja di `frontend/`. Bagian **WORKING
AGREEMENT** bukan opsional - dia yang membuat output agent bisa di-review.

---

## Prompt

````text
You are working in `frontend/` of "TrustHub" - a knowledge hub dashboard for a
manufacturing plant, built on a reversible guardrail system for AI coding agents
(IBM Bob 2.0 Hackathon). The demo surface today is the plant domain: documents,
equipment, maintenance, verification, audit, and a code graph over the plant repo.

Stack is fixed and already installed: Next.js 15.5.24 (app router) + React 19 +
TypeScript + Tailwind. Backend is FastAPI + SQLite.
Read `package.json` before assuming any library is available. **Zero new
dependencies** - if a feature seems to need one, it does not.

## ROLE

You render state. Rollback logic, conflict detection, and blast radius live in
the backend. If you catch yourself deciding whether an operation should be
rolled back, you are in the wrong file.

## READ FIRST, IN THIS ORDER

1. `DESIGN_SYSTEM.md` - color tokens, layout shell, the 9 pages that exist now
2. `../TRUSTHUB.md` - product context and data contracts
3. `README.md` - how to run, endpoint map, env vars
4. `PRD.md` - **historical.** See the drift note below before you read it.

### Drift note: PRD.md is not authoritative for structure

`PRD.md` describes an earlier Guardian/Cortex-era dashboard. Its bug ledger
(B-01..B-27) is still a useful record of *why* certain rules exist, but its
deliverables table and its maintenance rules are stale. Concretely:

- It lists `TopNavbar.tsx`, `TrustHubGraph.tsx`, `SettingsPage.tsx`,
  `graphFilter.ts`, and `graphFilter.test.ts`. None of those files exist.
- It claims 36 tests. The suite is 25.
- Its section 11 says "Tidak ada CSS variable untuk warna" (no CSS variables for
  color). **That is obsolete and directly dangerous.** `app/globals.css` now
  defines 26 color tokens as CSS variables on `:root` and `[data-theme=light]`.
  Do not delete them and do not hardcode hex values in components. See "COLOR"
  below.
- Its demo checklist routes to Guardian and Approvals pages that no longer exist.

When `PRD.md` and the code disagree, **the code is right here**, and `PRD.md`
needs a fix. Record the fix rather than working around it.

`DESIGN_SYSTEM.md` is current for tokens but still has a stale Guardian/Cortex
section describing pages that were removed. Read the token tables; ignore that
section.

## ROUTES

| Route | What | Rendering |
|---|---|---|
| `/` | 9-page dashboard, sidebar shell | Client. Pages are `dynamic(..., { ssr: false })` |
| `/landing` | Explainer page for hackathon judges | **Server component.** No state, no fetch, no `"use client"` |
| `/backend/[...path]` | Token-injecting proxy to FastAPI | Server route handler, 6 methods |

Notes:

- There is no `/api/graph` route and no `app/api/` directory. `app/` contains
  only `layout.tsx`, `page.tsx`, `globals.css`, `icon.svg`, `landing/`, and
  `backend/`.
- `?page=<navId>` is honoured on first paint so a URL can be shared. An unknown
  or stale bookmark falls back to the default page rather than rendering blank.
- The proxy route lives at `app/backend/[...path]/route.ts`. It injects
  `X-TrustHub-Token` server-side so the token never reaches the browser.

Never put a `position: fixed` banner or bar at `top-0` here. The root layout is
a full-height flex column; anything `fixed` will cover the top bar and the
`LeftNav` logo. That was bug B-01.

## THE 9 PAGES

`app/page.tsx` holds one `activePage` state and swaps components. There is no
router, and that is deliberate. Each page owns its own data, so switching is a
component swap with no shared fetch and no shared store.

The single source of truth for the nav is `NAV_ITEMS` in `components/LeftNav.tsx`.
`NAV_PAGES` is derived from it so the `?page=` guard cannot drift from the nav.

| Nav id | Component | Label key |
|---|---|---|
| `ask` | `AskPage` | `nav.ask` |
| `overview` | `OverviewPage` | `nav.overview` |
| `equipment` | `EquipmentPage` | `nav.equipment` |
| `documents` | `DocumentsPage` | `nav.documents` |
| `graph` | `KnowledgeGraphPage` | `nav.graph` |
| `verification` | `VerificationPage` | `nav.verification` |
| `maintenance` | `MaintenancePage` | `nav.maintenance` |
| `audit` | `AuditPage` | `nav.audit` |
| `dataset` | `PlantSettingsPage` | `nav.dataset` |

`ask` is `DEFAULT_PAGE` on a cold load. Note the id `dataset` currently renders
`PlantSettingsPage`; the mismatch is known and unfixed. If you touch either
name, fix both in the same commit.

## COLOR

Colors are CSS variables in `app/globals.css`, remapped to Tailwind in
`tailwind.config.ts`. Use the token classes. Never write a hex value in a
component.

- Surfaces: `bg-app`/`bg-surface`, `bg-panel`, `bg-panel-2`, `bg-inset`,
  `bg-surface-hover`, `bg-deep`
- Text: `text-ink` (which maps to the ramp `--ink-1` .. `--ink-5`, plus
  `--ink-1b`), used via `text-ink-1`, `text-ink-2`, ... `text-ink-5`
- Borders: `border-line`, `border-line-2`
- Accents: `accent-blue` and `accent-blue-soft`/`-softest`, `accent-green`,
  `accent-red`, `accent-amber`, each with `-soft`/`-softest` steps
- Page texture: `--page-edge` and `--page-grain` drive the vignette and grain
  layers. They are not Tailwind colors.

Two themes ship:

- Dark is the default. `:root` holds the dark values.
- Light is opt-in via `data-theme="light"` on `<html>`.

Theme ownership rules, all load-bearing:

- `<html>` carries `lang="en"` and `suppressHydrationWarning`. The theme
  bootstrap script in `app/layout.tsx` writes `data-theme` **before paint**.
- Do **not** pass `data-theme` as a JSX prop. Server-rendered HTML would then
  disagree with the client and React 19 reports a hydration mismatch. The
  attribute belongs to `ThemeProvider` and the bootstrap script only.
- Persistence key is `localStorage["trusthub.theme"]`.
- Toggle labels are fixed strings: `Light` / `Terang`. Do not rename them.

Light mode surfaces are grey, not white. All six text steps pass WCAG AA against
the panel surface; keep it that way when you add a text color.

## WORKING AGREEMENT

**Do not ship a control that does not do anything.** A button, chevron, or
`Cmd+K` hint with no handler is a bug, not a placeholder. Three legal
resolutions:

1. Wire it up.
2. Remove the affordance.
3. Write a one-line `ponytail:` comment naming the ceiling and the upgrade path
   - only if it genuinely cannot be built right now.

**One source of truth for connection status.** Import `useBackendStatus()` from
`hooks/useBackendStatus.ts`. It is a single module-level poller with many
subscribers. Never call `/health` from a component. Two independent polls can
disagree, which is how the UI ended up showing "Live Connection" and "OFFLINE"
at the same time (B-02).

**Mock data must announce itself.** When `NEXT_PUBLIC_USE_LIVE_SSE=false`, the
UI is showing samples, not real runs. `BackendStatusBanner` says `DEMO DATA`.
Never claim mock data as real, in UI copy or in a commit message.

**Never swallow an error.** `catch { return; }` makes "the request failed" and
"there is no data" indistinguishable. Render the backend's own error text when
it gives one, and abort in-flight requests on unmount with `AbortController`.

**Accessibility is not polish.** A `<span>` next to an `<input>` is not a label.
Icon-only buttons need `aria-label`. Switches need `role="switch"` +
`aria-checked`. The project defines `:focus-visible` in `app/globals.css` -
do not remove it and do not suppress the outline without a replacement.

**Content on `/landing` must be verifiable.** Every claim must be checkable
against the code in this repo. No invented traction, user, or performance
numbers. No "revolutionary", "next-generation", "seamless".

## BEFORE YOU WRITE

1. `npm run typecheck` - must be green before you start.
2. Find the sibling file that already does the same thing. Match its shape:
   fetch pattern, error copy, card markup, class naming, state naming.
3. Reuse the shared primitives in `components/shared/`: `PageShell`,
   `TrustBadge`, `BackendStatusBanner`, `LogoMark`, `ThemeSwitcher`,
   `LanguageSwitcher`.

## PATTERNS THAT ARE ALREADY RIGHT - DO NOT "FIX" THEM

- **`lib/ThemeProvider.tsx` and `lib/LocaleProvider.tsx` are the only owners of
  their `data-theme` / `lang` attributes.** Components read them; they never set
  them. This split with the pre-paint bootstrap script is what keeps React 19
  hydration quiet.
- **`lib/proxyGuard.ts` is shared by every proxy route handler**, and
  `lib/proxyGuard.test.ts` asserts that by scanning route files. If you add a
  second proxy, that test will fail until you wire the guard in.
- **`lib/backendUrl.ts` normalization** is regression-locked by
  `lib/backendUrl.test.ts` (BUG-11, the proxy-token contract).
- **`app/page.tsx` renders 9 pages from one `activePage` state.** There is no
  router. Keep it that way unless asked.
- **Every page is `dynamic(..., { ssr: false })`.** They call a protected API,
  so they cannot render on the server.
- **`lib/platformSettings.ts` is the typed shape; `lib/usePlatformSettings.ts`
  is the React binding.** Do not inline a second settings shape.
- **`lib/plantApi.ts` is the typed client for `/api/plant/*`.** Add new backend
  calls there, not scattered in components.
- **`lib/i18n/dictionary.ts` holds every UI string**, English and Indonesian in
  one typed map. `nav.overview` is `Ringkasan` in Indonesian. A hardcoded
  string in a component is a bug.
- **`lib/*.ts` files with branches ship with a `lib/*.test.ts`.** `npm test`
  runs `node --test "lib/*.test.ts"`. No test framework, no fixtures, no
  snapshots. There are 3 test files: `backendUrl`, `platformSettings`,
  `proxyGuard`.
- **A hardcoded UI string needs no test.** A branch, loop, parser, or money path
  does.

## KNOWN GAPS - do not silently "fix" these, ask first

- **`app/backend/[...path]/route.ts` has no path allowlist and no method
  allowlist.** It exports GET, POST, PUT, PATCH, DELETE, OPTIONS and forwards
  to `${BACKEND}/${segments}`. Any backend route is reachable through the
  proxy, including `/settings`, `/settings/reset`, `/browse`, and the Guardian
  and GitHub routes.
- **Its per-segment `encodeURIComponent` does not stop `..`.**
  `encodeURIComponent("..")` returns `".."`, so a traversal segment survives
  re-encoding and normalizes in the backend. There is no regression test for
  this on the frontend side.
- **A missing `Sec-Fetch-Site` header is deliberately allowed** for non-browser
  clients, and `lib/proxyGuard.test.ts` asserts that as correct behavior. So
  anything that can reach the Next.js port can drive the proxy with the server's
  credentials. Mitigations belong at deploy time: bind Next.js to localhost, or
  set `TRUSTHUB_PROXY_ALLOWED_ORIGINS`.

These belong to `../security/`. Report them there; do not patch them inside a UI
task.

## FINISHING

Run all four. Three green does not imply the fourth.

```
npm run lint
npm run typecheck
npm test
npm run build
```

Stop any `next dev` before `npm run build`; a concurrent dev server corrupts
`.next` and produces a bogus `Cannot find module './873.js'`.

Then report in this shape, one line each, nothing else:

```
[x] what you did
skipped: [what], add when [the condition that justifies it]
```

Update `PRD.md` if you fixed or deferred a bug in the ledger. If you added a
route, add it to this table and to `README.md`.

## DO NOT TOUCH

`backend/` and `security/`. If a UI change needs a new backend endpoint, write
it down as a request at the bottom of `PRD.md` and keep going with the frontend
degraded-but-honest path.
````

---

## Yang sengaja tidak ada di prompt ini

| Tidak ada | Kenapa |
|---|---|
| Daftar aesthetic (warna, font, spacing) | Sudah ada di `DESIGN_SYSTEM.md`; mengulangnya di sini hanya membuat drift |
| Spec 9 halaman | Sudah ada di `DESIGN_SYSTEM.md` dan tabel route di atas |
| Daftar endpoint | Sudah ada di `README.md` |
| Nilai hex token warna | Token hidup di `app/globals.css`; menyalin nilainya ke sini pasti basi |
| Timeline hackathon | Fase ada di `PRD.md` sebagai checklist demo, bukan jadwal kerja |