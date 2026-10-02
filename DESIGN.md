# TrustHUB — Design Direction & Anti-Slop Guidelines (`DESIGN.md`)

> **Industrial Knowledge Hub & Guardrail System (CALIBER 2026)**
> Single Source of Truth for visual identity, UI/UX anti-slop rules, color tokens, and craftsmanship standards for TrustHUB.

---

## 1. Brand Identity & Character

TrustHUB is an industrial data ops platform for manufacturing plant engineers (LLDPE Unit). It is a **high-density, technical data room** where accuracy, traceability, and trust badges determine real-world execution safety.

- **Visual Tone:** Industrial, precise, authoritative, quiet.
- **Core Value:** Trust over ornamentation. Every visual element must serve visual hierarchy, readability, or safety decision-making.
- **Identity Test:** If the TrustHUB logo is removed, the design must still feel like a professional plant data room—not a generic SaaS landing page.

---

## 2. Anti-AI-Slop Rules (Hard Gates & Purpose-Gates)

### 🚫 Forbidden Patterns (Banned AI Slop)
1. **No Purple-to-Blue Gradients or Neon Radial Orbs:** Backgrounds are solid, dark slate (`#080d14` surface, `#0d1117` panel). Accent colors are 100% functional.
2. **No Background Blueprint Grids or Graph Paper:** Texture is restricted to subtle SVG noise grain (`feTurbulence`, 0.05 opacity) + vignette. Blueprint lines clutter document text reading.
3. **No Fake Metrics or Invented Stats:** All numbers (e.g. 134 nodes, 87 documents, 211 work orders, 31 breakdowns, IDR 413,345,000 cost) are derived from real dataset APIs (`/api/plant/status`, `/api/plant/failure-memory`). Zero fabricated statistics.
4. **No Decorative Capsule Badges or Emojis as Icons:** Badges represent real trust verdicts (`TRUSTED`, `VERIFY`, `DO NOT EXECUTE`). Icons are SVG line glyphs (24×24, 1.7px stroke). Emojis are forbidden as navigation icons.
5. **No Dead Interactive Controls:** Buttons, tabs, search bars, and dropdowns must have real state handlers or clear fallback notices. No non-functional UI controls.
6. **No Em Dashes (`—`) in Agent-Generated Copy:** Use colons, commas, or parentheses instead.

### 🎨 Color & Theme Standards
- **Dark Mode (Default):** Deep slate background (`#080d14`), panels (`#0d1117`), borders (`slate-800/60`).
- **Light Mode (Opt-in via `data-theme="light"`):** Stepped grey surfaces (`#dde2e6` surface, `#edeff1` panel) passing WCAG AA contrast for all 6 text steps. No harsh pure white `#ffffff` backgrounds.
- **Functional Accents Only:**
  - `accent-blue` (`#3b82f6`): Active navigation, primary action, system status.
  - `accent-green` (`#22c55e` / `TRUSTED`): Approved sources, verified setpoints, healthy connection.
  - `accent-amber` (`#fbbf24` / `VERIFY`): Needs human verification, unapproved interlocks, demo data mode.
  - `accent-red` (`#ef4444` / `DO NOT EXECUTE`): Safety-critical override, missing source, execution blocked.

---

## 3. Typography & Data Density

- **Primary Sans:** Inter (loaded via `next/font/local` CSS variables). Clean, high-legibility sans-serif for UI labels, tables, and document summaries.
- **Monospace:** JetBrains / Geist Mono for equipment tags (`GA-1201A`, `VSHH-1201`), setpoints (`12 mm/s`), document revision numbers (`Rev 2.1`), and SQLite node IDs.
- **Hierarchy:**
  - `h1`: Page title (20px / 1.25rem, bold, `text-ink-1`)
  - `h2`: Section header (16px / 1rem, semibold)
  - Table data: 13px / 0.8125rem, mono for tags/values, sans for text.

---

## 4. Craftsmanship & UI Resilience Checklist

- [x] **Functional Completeness:** Every button, tab, and filter has an active handler.
- [x] **Content-Driven Composition:** 9 dedicated pages matching engineer workflow (`ask`, `equipment`, `documents`, `graph`, `verification`, `maintenance`, `overview`, `audit`, `dataset`).
- [x] **Resilience Across Themes:** Dark and light modes fully functional without hydration mismatches (`data-theme` set pre-paint).
- [x] **Evidence & Traceability:** Every Q&A answer explicitly displays document revision, approval status, trust score, and mandatory citation.
- [x] **Keyboard Accessibility:** All interactive elements reachable via `Tab`, modals closable via `Escape`, visible ring outline on `:focus-visible`.
