# TrustHub — Design System & Page Spec

> Dokumen ini adalah **source of truth** untuk semua tim frontend (FE-1, FE-2) dan backend.
> Berdasarkan `Dashboard TrustHubnya.png` yang ditetapkan sebagai desain final.
> Diupdate oleh: @nabilfauzandafa (FE-1)
> Scope & bug ledger: [`PRD.md`](./PRD.md)

---

## Color Palette

| Token | Hex | Dipakai untuk |
|---|---|---|
| `bg-app` | `#080d14` | Background utama |
| `bg-panel` | `#0d1117` | Card / panel |
| `bg-sidebar` | `#0d1117` | LeftNav + GuardianPanel |
| `border` | `slate-800/60` | Semua border |
| `text-primary` | `white` | Heading |
| `text-secondary` | `slate-400` | Subtitle / label |
| `text-muted` | `slate-500/600` | Placeholder, meta |
| `accent-blue` | `#3b82f6` | Guardian agent, active nav, CTA |
| `accent-purple` | `#a855f7` | Cortex agent |
| `accent-green` | `#22c55e` | Success, verified, healthy |
| `accent-yellow` | `#fbbf24` | Pending, warning, demo data |
| `accent-red` | `#ef4444` | High risk, failed, conflict |
| `accent-orange` | `#fb923c` | Executing |

> **Canvas graph wajib `#080d14`.** Dulu `#0f172a` (slate-900) —creates a seam
> karena `#0d1117` panel di atasnya. Sama dengan `bg-app`.

### Tema gelap dan terang

Ada dua tema. Yang gelap di declare di `:root`, jadi itu default-nya dan
tema yang sudah dipakai sebelum fitur ini ada. Terang menimpanya lewat
`[data-theme="light"]`. Menaruh default di `:root` (bukan di
`[data-theme="dark"]`) berarti pengunjung yang skripnya belum jalan tetap melihat
tema gelap, bukan kilatan terang.

Cara kerjanya **satu atribut**, `data-theme` di `<html>`. Semua warna di app ini
menyelesaikan diri lewat CSS variable, jadi berganti tema **tidak** mengganti
class apa pun dan **tidak** memicu re-render. Karena itu tidak ada satupun
komponen yang perlu tahu tema mana yang aktif, dan tidak ada varian `dark:`.

Semua token adalah RGB triplet, bukan hex, karena `tailwind.config.cjs`
menggunakannya sebagai `rgb(var(--x) / <alpha-value>)`. Hanya bentuk itu yang
tetap menyediakan modifier alpha di call site, dan call site memang memakainya
(`border-slate-800/60`).

Skala `slate` **dipetakan ulang**, bukan ditambah. `text-slate-400` muncul 62 kali
dan artinya "teks sekunder"; kalau dibiarkan menunjuk ke hex aslinya, teks itu
tidak terbaca di panel terang. Menulis ulang 62 call site ke nama baru
butuh kerja yang sama dengan diff yang lebih buruk.

| Peran | Gelap | Terang (abu-abu) |
|---|---|---|
| `--surface` | `#080d14` | `#dde2e6` |
| `--panel` | `#0d1117` | `#edeff1` |
| `--panel-2` | `#0f141b` | `#e4e7ea` |
| `--inset` | `#0a0e14` | `#d4d9dd` |
| `--surface-hover` | `#131a24` | `#dde1e4` |
| `--deep` | `#0f172a` | `#d8dcdf` |
| `--line` | `#1e293b` | `#c6ccd2` |
| `--ink-1` s/d `--ink-5` | `#f1f5f9` → `#475569` | `#0a0f1c` → `#586a7d` |

**Tidak ada putih murni di tema terang.** Panel lama `#f9fafb` putih dalam nama saja,
dan bidang besar yang mendekati putih melelahkan untuk shift panjang. Semua
permukaan terang sekarang abu-abu bertingkat, sehingga panel tetap terbaca
terangkat dari surface (1.13:1) dan border tetap terlihat (1.41:1).

Abu-abu mengurangi kontras, jadi accent harus turun bersamanya. Terhadap panel
abu-abu `#edeff1` yang baru: teks utama 15.62, sekunder 8.98, `--ink-3` 6.35,
biru 5.81, hijau 6.19, merah 5.61, amber 6.15 — semua lolos AA. Hijau `#15803d`
(4.35) dan amber `#b45309` (4.36) sebenarnya sudah gagal pada panel putih lama
dan hanya lolos pada langkah yang lebih gelap yang dipakai sekarang.

**Seluruh ramp terang kini lolos AA.** Ramp pertamanya memang gagal: `--ink-4`
ada di 3.91 (hanya large-text) dan `--ink-5` di 2.47 (gagal). Keduanya dipakai
untuk kalimat sungguhan — `text-slate-500` melintasi 64 file dan `text-slate-600`
melintasi 45 — jadi alasan "kan cuma abu-abu placeholder" tidak benar.

`--ink-4` harus bergerak lebih jauh daripada `--ink-5`, justru karena `--ink-5`
yang lebih pudar dan tetap harus tembus 4.5. Menggelapkan hanya dasar ramp
itulah yang menyisakan 2.47 di sana pada percobaan pertama.

Terhadap panel abu-abu `#edeff1`, keenam langkah sekarang: 16.59, 14.11, 10.44,
7.83, 5.96, 4.83. Ramp masih terbaca sebagai ramp; jarak terkecil ada di
`--ink-4` ke `--ink-5` dengan rasio luminansi 0.74.

Nama label **tidak** ikut berubah. Opsi itu tetap terbaca `Light` / `Terang`
meskipun warnanya abu-abu, karena yang dijanjikan switcher adalah mode terang
terhadap mode gelap, bukan pilihan putih terhadap hitam.

> **`text-white` tidak boleh dipetakan ke tinta.** Dipakai untuk body copy di
> panel (harus membalik di terang) **dan** untuk 4 label di atas `bg-blue-600`
> (harus tetap putih di kedua tema). Keempatnya sengaja dibiarkan `text-white`.
> Yang lain sudah diganti `text-ink`.

> **Jangan menamai token warna `hover`.** bertabrakan dengan variant `hover:`.
> `hover:bg-hover` tidak pernah ter-generate dan state hover mati diam-diam.
> Namanya `--surface-hover`.

### Permukaan background

`#080d14` adalah warna dasar, bukan warnanya yang dilihat user. Di atasnya
`globals.css` menambah dua hal, dan tidak ada yang lain:

| Lapisan | Nilai | Fungsi |
|---|---|---|
| Grain | `feTurbulence`, `opacity 0.05`, tile 160px | Menghentikan bidang near-black yang luas agar tidak banding di monitor |
| Vignette | `radial-gradient(130% 90% at 50% 0%)`, hitam `0 → 0.38` | Menahan mata di tengah halaman, meng-ground bagian bawah |

Keduanya sengaja **tidak menaikkan luminance rata-rata**. Kalau background
dibuat lebih terang dari `#0d1117`, panel berhenti terbaca sebagai lapisan yang
melayang di atas. Grain dipilih justru karena tidak punya mean, jadi hubungan
kedalaman itu tetap utuh.

`background-attachment: fixed` dipakai karena app scroll di dalam container
yang tingginya tetap, sehingga grain tidak ikut bergerak di bawah teks.

> **Jangan** menambahkan grid blueprint, glow, atau orb di belakang konten.
> Ketiganya cocok untuk tema industri dan ketiganya akan bersaing dengan
> pembaca dokumen yang tugasnya justru dibaca.

Satu-satunya pemilik background adalah `globals.css`. Jangan menuliskannya
lagi sebagai `bg-[#080d14]` di `layout.tsx` atau container halaman — itulah
alasan deklarasi ganda tersebut sudah dihapus.

### Logo

`components/shared/LogoMark.tsx` — satu-satunya sumber. Dipakai oleh `LeftNav`
dan header landing; `app/icon.svg` adalah gambarnya yang sama pada 32px dengan
stroke lebih tebal agar tetap terbaca di tab browser 16px.

Bentuknya heksagon dengan lubang tengah: heksagon adalah hardware di plant dan
sekaligus "hub" pada nama TrustHUB; lubangnya adalah satu sumber yang disepakati
dokumen lain. Dua bentuk, satu warna, tanpa gradien.

> Logo ini pernah di-copy-paste ke dua file dan `icon.svg` melenceng ke perisai
> hijau yang sekaligus mengklaim status TRUSTED. Ketiganya kini satu file.

---

## Layout Shell

```
┌─────────────────────────────────────────────────────┐
│  BackendStatusBanner (dalam flow, bukan fixed)      │
├─────────────────────────────────────────────────────┤
│  TopNavbar (h-12, bg-panel, border-b)               │
├──────────┬──────────────────────────┬───────────────┤
│ LeftNav  │  <Page Content>          │ GuardianPanel │
│ w-52     │  flex-1 overflow-y-auto  │ w-72          │
│          │                          │ (only on      │
│          │                          │ overview +    │
│          │                          │ guardian)     │
└──────────┴──────────────────────────┴───────────────┘
```

`<body>` punya `h-screen overflow-hidden`, `layout.tsx` membungkus children dalam
flex column `min-h-0 flex-1`, dan root setiap halaman memakai **`h-full`** —
bukan `h-screen`. Kalau halaman memakai `h-screen`, total tinggi melebihi viewport
setelah banner ditambahkan.

> **Jangan pakai `position: fixed` untuk bar di `top-0`.** Itu menutupi
> `TopNavbar` dan logo `LeftNav` (bug B-01). Banner harus anak flex column.

**TopNavbar props:** `nodeCount`, `edgeCount`, `onOpenSettings`
**LeftNav props:** `activePage`, `onNavigate`, `pendingApprovals`
**GuardianPanel props:** `pendingOps`, `onOpDecided`

### Aturan global

- `color-scheme: dark` wajib ada di `globals.css`. Tanpa itu `<select>`,
  scrollbar, dan input popup browser membuka dengan latar terang.
- `:focus-visible` sudah didefinisikan global (ring biru 2px). Jangan dihapus.
- `--font-inter` berasal dari `next/font/local` lewat `inter.variable` pada
  `<html>`. **Jangan** deklarasikan ulang di `:root` — itu menimpa nama family
  hasil hash dan diam-diam jatuh ke system-ui (bug B-04).
- Ikon navigasi: SVG garis 24×24, `stroke="currentColor"`, `strokeWidth={1.7}`.
  Tidak ada emoji sebagai ikon — warna emoji ikut sistem operasi sehingga tidak
  konsisten dengan UI yang monochrome.
- Entitas HTML (`&#183;`) hanya bisa dipakai di **teks JSX**. Di dalam string
  literal JS akan tampil apa adanya (bug B-16). Gunakan karakter aslinya.

---

## Route 0 — Landing / Explainer (`/landing`)

Server component. Tanpa state, tanpa fetch, tanpa `"use client"`.
Tujuan: juri memahami masalah dan solusi tanpa perlu penjelasan pemateri.

| Section | Isi | Syarat |
|---|---|---|
| Nav | Logo, anchor `#problem` `#how` `#agents` `#demo`, CTA `Open Live Demo` | Sticky, CTA ke `/` |
| Hero | Nama hackathon, 1 headline, 1 paragraf value, 2 CTA, 4 stat faktual | Headline menyebut masalah, bukan fitur |
| Problem | 3 kartu (review kalah cepat, tidak ada pemahaman bersama, sulit rollback) | Framing masalah |
| How it works | 4 langkah `01–04`: Understand → Propose → Guard → Verify | Sebut blast radius, conflict, rollback |
| Properties | 4 kartu: Reversible, Conflict-aware, Fail-closed, Human in the loop | Semua harus benar-benar ada di backend |
| Agents | 3 kartu: Guardian, Cortex, Review | Tidak tumpang tindih |
| Demo path | 3 langkah bernomor, tiap langkah menyebut halaman tujuan | Jalur yang bisa didemokan manual |
| Stack | 8 chip teknologi | Hanya yang ada di `package.json` |
| Footer | Satu kalimat produk + link ke demo | — |

**Token visual:** `bg-app #080d14`, `bg-panel #0d1117`, `border slate-800/60`,
aksen tunggal `#3b82f6`, `rounded-xl` untuk kartu, `rounded-lg` untuk kontrol,
`max-w-6xl` + `px-6`.

**Aturan konten:** faktual saja, tidak boleh ada angka traction/performa yang
dikarang, tidak boleh ada slug generik, dan setiap langkah demo harus menyebut
halaman tujuan.

**Landing page memakai shell sendiri** — tanpa `TopNavbar`/`LeftNav`, tanpa
graph. Itu disengaja: halaman ini harus bisa dibaca tanpa login dan tanpa
backend hidup.

**Scroll:** `<body>` memakai `h-screen overflow-hidden` supaya dashboard tidak
bergeser saat banner muncul. Landing page karena itu **wajib** jadi scroll
container-nya sendiri — root-nya `h-full overflow-y-auto`. Tanpa itu, konten
5+ layar terpotong dan tidak ada scrollbar. Halaman dashboard tidak boleh
meniru pola ini; mereka sudah punya `overflow-y-auto` sendiri di dalam.

**Anchor:** header landing `sticky top-0` setinggi `h-14` (56px). Semua
section yang punya `id` wajib pakai `scroll-mt-14`, kalau tidak header akan
menutupi judul section begitu anchor diklik.

---

## Navigation Pages (9 halaman)

| ID | Label | Komponen | Fungsi | Status |
|---|---|---|---|---|
| `ask` | Ask | `AskPage` | AI Q&A Assistant + Semantic Search + Trust Badge & Mandatory Citation | ✅ Active |
| `equipment` | Equipment | `EquipmentPage` | Equipment-centric Knowledge Graph & Unit view | ✅ Active |
| `documents` | Documents | `DocumentsPage` | Document Registry (revision, approval status, approver identity) | ✅ Active |
| `graph` | Graph | `KnowledgeGraphPage` | Interactive Knowledge Graph (134 nodes, 126 links) | ✅ Active |
| `verification` | Verification | `VerificationPage` | Multi-document cross-source setpoint verification | ✅ Active |
| `maintenance` | Maintenance | `MaintenancePage` | Failure Memory System (211 work orders, 31 breakdowns) | ✅ Active |
| `overview` | Overview | `OverviewPage` | Instance status summary & system metrics | ✅ Active |
| `audit` | Audit | `AuditPage` | Complete question audit trail + trust engine weights | ✅ Active |
| `dataset` | Dataset | `PlantSettingsPage` | Dataset provenance, dataset contract & LLM posture | ✅ Active |

---

## Page 1 — Code Graph

**Layout:** 2-kolom (graph fullwidth kiri + selected node panel kanan)

### Left Area — Code Graph Canvas
- `TrustHubGraph` fullscreen dengan header panel:
  - Title: "Code Graph" + subtitle "Hybrid AST + semantic understanding"
  - Search bar: `Search files, symbols, docs...` — **benar-benar menyaring**
    (`lib/graphFilter.ts`), cocok ke `name` dan `id`, case-insensitive
  - Filter pills: `All | File | Symbol | Dependency | Doc` — menyaring node
    berdasarkan tipe. Node bertipe `operation` **selalu ikut**, apa pun filter,
    supaya status Approved/executing tidak hilang saat user mengetik
  - Zoom controls (+/−/reset)
  - Edge Relationships legend (calls, uses, defines, documents, depends on)
- Graph canvas mengisi sisa ruang
- Saat filter aktif, canvas kanan atas menampilkan `n/total nodes`
- Edge yang salah satu ujungnya tersaring ikut hilang — tidak ada edge menuju
  node yang tidak ada

### Right Area — Selected Node Panel (`w-64`)
- **Selected Node card:**
  - Icon file type + nama node (e.g. `app.py`)
  - Fields: Type, Path, Imports, Referenced by
  - Button: "View Details →"
- **Live SSE Activity panel:**
  - Badge: `● Live`
  - List real-time events: timestamp + pesan singkat (last 5)

### Backend endpoints:
- `GET /graph/nodes` — load semua nodes
- `GET /graph/edges` — load semua edges
- `GET /stream` — SSE live updates
- `POST /explain_topic` — saat node diklik

---

## Page 2 — Guardian

**Layout:** single column scroll

### Header section:
- Badge: `● ACTIVE`
- Title: "Guardian"
- Subtitle: "Protecting risky changes • Reversible • Conflict-aware"

### Pending Operation Card (merah):
- Title: "Pending Operation" + badge `High Risk`
- Op name + description
- Meta table: Agent | Target | Blast Radius | Time
- **Reversibility Plan** (3 checklist steps)
- **Conflict Detection** panel (overlap resource alert)
- **Automation** checklist: SQLite snapshot / Verification checks / Rollback plan
- **Approval Gate** (requires human approval text)
- Tombol **Approve** (hijau) + **Deny** (merah)

### Operation Timeline:
- Horizontal step bar: Propose → Snapshot → Approve → Execute → Verify → Complete
- Progress indicator current step
- Button: "View Logs →"

### Backend endpoints:
- `GET /list_pending_approvals`
- `POST /approve_operation`
- `POST /execute_operation`
- `GET /operations`

---

## Page 3 — Cortex

**Layout:** 3-kolom (repo tree kiri | explain panel tengah | graph context kanan)

### Left — Repository Tree (`w-56`):
- Search bar
- File tree dengan expand/collapse
- Highlight node yang dipilih

### Center — Explain Topic:
- Badge: `REVIEW MODE`
- Input field: "How does the guardian module work?"
- Button: **Explain**
- Result sections:
  - **Definition** — teks penjelasan
  - **Mental Model** — cara pikir
  - **Example** — code snippet

### Right — Review Artifact + Graph Context:
- **Review Artifact card:**
  - Input path/diff
  - Button: "Run Review"
  - Scores: Completeness / Clarity / Correctness vs Spec / Risk (0–10)
- **Graph Context** mini-graph (subset dari force graph)

### Backend endpoints:
- `POST /explain_topic`
- `POST /review_artifact`
- `GET /graph/nodes` (untuk tree)
- `GET /repo_health`
- `GET /complexity_report`
- `POST /find_path`
- `POST /suggest_refactor`

### Centre — kartu tambahan (live, urutan ke bawah):
- **Repo Health** — skor 0–100 + label, summary, 4 stat (Files / Documented / Dead code / Complex), hub nodes
- **Complexity Ranking** — tabel top 10 simbol: nama + `file:line`, complexity, lines, badge risk
- **Find Path** — dua input (from → to), hasil jalur sebagai chain node + label relasi
- **Refactor Suggestions** — satu input nama entitas, metrics (cx / lines / degree / docs) + daftar saran berprioritas

Semuanya respek `NEXT_PUBLIC_USE_LIVE_SSE`: kalau `false`, tiap kartu menampilkan
"Live data OFF" dan tombol nonaktif — bukan mock data.

---

## Page 4 — Agents

**Layout:** header agents cards + 2-kolom bawah

### Top — 3 Agent Cards (horizontal):
Setiap card:
- Icon + Name (Guardian / Cortex / Review)
- Subtitle (Protection & Safety / Understanding & Review / Code Review & Analysis)
- Stats: Tasks (number) + Status (● Healthy / ● Running)

### Bottom Left — Current Tasks:
- List 3–5 tasks:
  - Agent name + task description + timestamp
  - Real-time dari SSE `operation_*` events

### Bottom Right — SSE Event Stream:
- Badge: `● Live`
- Scrollable list: timestamp | agent | event message
- Color-coded per agent

### Bottom — Agent Activity Chart:
- Line chart (Guardian=biru, Cortex=ungu, Review=abu)
- X-axis: waktu (10 tick)
- Y-axis: activity level

### Conflict sidebar:
- Badge count merah
- Op name + conflict details + "View →" button

### Recent Actions list:
- Agent | action | timestamp (relative)

### Backend endpoints:
- `GET /stream` — SSE untuk live tasks + event stream
- `GET /operations?limit=5` — recent actions
- `GET /repo_health` — agent health status

---

## Page 5 — Approvals ✅ (Shann)

Sudah diimplementasi oleh @ShannWasHere di commit `8c085c3`.

Spec: table dengan kolom TIME | OPERATION | RISK | AGENT | CONFLICTS + tombol Approve/Deny per row + Operation Details panel di bawah.

---

## Page 6 — Operations ✅ (Shann)

Sudah diimplementasi oleh @ShannWasHere di commit `8c085c3`.

Spec: Live Execution step tracker + Operation History table dengan filter.

---

## Page 7 — Security

**Layout:** 2x2 grid cards + event feed

### Security Overview card:
- Stats: Total Checks | Violations | Blocked Ops | Rules Active
- Badge: `● Healthy`

### Rule Engine card:
- Title + "Static rules & heuristics (not ML)"
- Policy: "Fail-closed (default)"
- Rule list:
  - Dangerous operation detection
  - Conflict detection (overlapping resources)
  - Reversibility requirement
  - Unknown operation fail-closed
  - Blast radius classification
- Button: "View Rules →"

### Adversarial Test Results card:
- N/M tests passed badge
- Checklist items (green=pass, red=fail)
- Button: "View Details →"

### Conflict Checks card:
- Count badge
- "N conflicts today" + list

### Rollback Verification card:
- N/M successful badge
- Recent rollbacks list dengan timestamp

### Security Event Feed:
- Chronological list: timestamp | event | status
- Color-coded: merah=blocked, kuning=warning, hijau=ok

### Backend endpoints:
- `GET /repo_health` — overall health
- `GET /operations?status=failed` — failed ops
- `GET /operations?status=rolled_back` — rollbacks
- `GET /stream` — live security events

---

## Page 8 — Settings

**Layout:** tabs kiri + content kanan

### Tabs:
`General | MCP / Server | Storage | Repository | Approval`

### Tab: General
- Platform Name (input: "TrustHub")
- Environment (dropdown: Production)
- Log Level (dropdown)
- Developer mode toggle

### Tab: MCP / Server
- FastAPI Server status (Running / Port)
- SSE Stream status (Connected / Stream)
- MCP Task status

### Tab: Storage
- Database File path
- Tables: nodes, edges, operations

### Tab: Repository
- Default Branch (input)
- Workspace Path (input)
- Auto DB Migration toggle
- Enable Conflict Detection toggle
- Enable SSM Events toggle

> Tidak ada tombol **Browse** dan tidak ada tombol **View Schema** di tab
> Storage. Keduanya tidak bisa dikerjakan: browser tidak bisa memilih folder di
> server, dan tidak ada endpoint schema. Kontrol yang tidak bisa dikerjakan
> dihapus, bukan dipalsukan.

### Tab: Approval
- Default approval mode
- Conflict auto-deny toggle

### Persistence
Semua preferensi di atas disimpan di `localStorage` (`trusthub.settings`).
Backend tidak punya endpoint `/settings`. `Save Changes` menulis, `Reset to
Default` menghapus key dan mengembalikan form ke default, keduanya menampilkan
umpan balik "Saved to this browser".

Nilai yang **tidak** bisa diubah dari UI (status server, SSE, storage) selalu
berasal dari backend nyata. `MCP / Server` menampilkan kondisi sebenarnya dari
`useBackendStatus()`, bukan teks hardcoded.

### Buttons: Reset to Default | Save Changes

### Backend endpoints:
- `GET /health` — server status
- `GET /graph/summary` — storage stats
- (Settings disimpan di localStorage frontend — tidak butuh backend endpoint baru)

---

## Component Library Bersama

### Badge variants
```tsx
// Risk
<RiskBadge level="high|medium|low|unknown" />

// Status
<StatusBadge status="pending|approved|executing|verified|failed|rolled_back" />

// Agent
<AgentBadge agent="guardian|cortex|review" />
```

### Shared tokens (Tailwind classes)
```
panel:     bg-[#0d1117] rounded-xl border border-slate-800/60
card:      bg-slate-800/40 rounded-xl border border-slate-700/60
btn-green: bg-green-600 hover:bg-green-500 text-white text-xs font-bold rounded-lg py-2
btn-red:   bg-red-700/80 hover:bg-red-600 text-white text-xs font-bold rounded-lg py-2
btn-ghost: border border-slate-700/60 text-slate-400 hover:text-slate-200 hover:border-slate-600
```

---

## Backend Endpoints — Mapping ke Halaman

| Endpoint | Method | Dipakai di halaman |
|---|---|---|
| `/stream` | GET SSE | Code Graph, Agents, Operations, Security |
| `/graph/nodes` | GET | Code Graph, Cortex |
| `/graph/edges` | GET | Code Graph |
| `/graph/summary` | GET | Settings (Storage tab) |
| `/understand_repo` | POST | Code Graph (trigger ingest) |
| `/explain_topic` | POST | Code Graph (node click), Cortex |
| `/review_artifact` | POST | Cortex |
| `/repo_health` | GET | Cortex (Repo Health card) |
| `/complexity_report` | GET | Cortex (Complexity Ranking card) |
| `/find_path` | POST | Cortex (Find Path card) |
| `/suggest_refactor` | POST | Cortex (Refactor Suggestions card) |
| `/list_pending_approvals` | GET | Guardian, Approvals |
| `/propose_operation` | POST | Guardian (demo) |
| `/approve_operation` | POST | Guardian, Approvals, GuardianPanel |
| `/execute_operation` | POST | Guardian, Approvals, GuardianPanel |
| `/operations` | GET | Operations, Approvals, Agents |
| `/health` | GET | Settings |

---

## Data untuk Mode `NEXT_PUBLIC_USE_LIVE_SSE=false`

- `lib/mockData.ts` — MOCK_NODES, MOCK_LINKS, MOCK_TIMELINE (graph + timeline)
- Halaman Agents & Security **tidak punya mock**. Statistik diturunkan dari
  `GET /operations` + `GET /graph/summary` lewat `lib/derive.ts`, jadi mode env-off
  menampilkan badge "Env off" + empty state, bukan angka palsu.

---

## Kontrak API (Backend perlu expose)

Semua endpoint sudah ada di backend. Yang dipakai FE-1:

| Endpoint | Method | Dipakai untuk |
|---|---|---|
| `/operations?limit=100` | GET | Agents, Security (poll 5s) |
| `/graph/summary` | GET | Agents (jumlah symbol/file), Settings |
| `/graph/nodes?type=file\|doc` | GET | Cortex (repo tree) |
| `/health` | GET | Settings |

Tidak ada endpoint baru yang dibutuhkan. Kalau nanti backend menambah
`/security/rules`, ganti konstanta `RULES` di `SecurityPage.tsx` dengan fetch.

---

## File Structure (Post-Redesign)

```
frontend/
├── DESIGN_SYSTEM.md         ← dokumen ini
├── PRD.md                   ← scope + bug ledger + checklist demo
├── MASTER_PROMPT.md         ← prompt lanjutan ke AI agent
├── README.md                ← cara run + endpoint map
├── app/
│   ├── page.tsx             ← shell 3 kolom + routing 9 halaman
│                              + ApprovalsPage & OperationsPage (fungsi lokal)
│   ├── landing/page.tsx     ← explainer hackathon (server component)
│   ├── globals.css
│   ├── layout.tsx           ← flex column: banner di flow, children h-full
│   └── api/graph/route.ts
├── components/
│   ├── LeftNav.tsx          ← FE-1: navigasi kiri
│   ├── TopNavbar.tsx        ← FE-1: top bar
│   ├── GuardianPanel.tsx    ← FE-1: right panel
│   ├── OverviewMain.tsx     ← FE-1: halaman overview
│   ├── TrustHubGraph.tsx     ← FE-1+2: force graph canvas
│   ├── pages/
│   │   ├── CodeGraphPage.tsx  ← FE-1 ✅
│   │   ├── GuardianPage.tsx   ← FE-1 ✅
│   │   ├── CortexPage.tsx     ← FE-1 ✅
│   │   ├── AgentsPage.tsx     ← FE-1 ✅
│   │   ├── SecurityPage.tsx   ← FE-1 ✅
│   │   └── SettingsPage.tsx   ← FE-1 ✅
│   └── shared/
│       ├── RiskBadge.tsx            ← FE-1 ✅
│       ├── StatusBadge.tsx          ← FE-1 ✅
│       ├── AgentBadge.tsx           ← FE-1 ✅
│       └── BackendStatusBanner.tsx  ← DEMO DATA / LIVE / OFFLINE
├── hooks/
│   ├── useSSE.ts
│   ├── useSSEStream.ts
│   ├── useBackendStatus.ts  ← SATU poller /health, banyak subscriber
│   ├── useLiveOps.ts        ← FE-1 ✅ poll /operations
│   └── useMockSimulation.ts
└── lib/
    ├── types.ts
    ├── mockData.ts
    ├── graphFilter.ts       ← filter + search graph (pure, ada test)
    ├── derive.ts            ← FE-1 ✅ derivasi data live -> UI
    ├── derive.test.ts       ← FE-1 ✅
    └── nodeVisuals.ts
```

---

## Checklist Implementasi

### FE-1 @nabilfauzandafa
- [x] OverviewMain (Code Graph panel + Timeline + Risk & Activity + Feature Cards)
- [x] LeftNav (9 item + badge)
- [x] TopNavbar
- [x] GuardianPanel (semua pending ops, scrollable)
- [x] CodeGraphPage — graph fullscreen + node panel + SSE activity
- [x] GuardianPage — pending op detail + reversibility + timeline
- [x] CortexPage — repo tree dari `/graph/nodes` + explain + review + graph context
- [x] CortexPage — 4 endpoint BE yang sebelumnya tidak pernah dipanggil: `/repo_health`, `/complexity_report`, `/find_path`, `/suggest_refactor`
- [x] AgentsPage — 3 agent cards + tasks + SSE stream + activity chart (data live)
- [x] SecurityPage — stats + rule engine + conflict candidates + event feed (data live)
- [x] SettingsPage — tabs: General + MCP / Server + Storage + Repository + Approval
- [x] SettingsPage — persistensi `localStorage` + Save/Reset + error handling
- [x] Shared badges (RiskBadge, StatusBadge, AgentBadge) + BackendStatusBanner
- [x] hooks/useLiveOps.ts — poll `/operations`
- [x] hooks/useBackendStatus.ts — satu poller `/health`, banyak subscriber
- [x] lib/derive.ts + lib/derive.test.ts — derivasi murni + 20 test
- [x] lib/graphFilter.ts + lib/graphFilter.test.ts — filter/search graph + 9 test
- [x] Nav "Agents" masuk LeftNav (sebelumnya halaman tidak terjangkau)
- [x] Landing `/landing` — explainer hackathon, server component, statis
- [x] Shell: banner masuk flow, `h-screen` pindah ke `<body>`, halaman `h-full`
- [x] `color-scheme: dark` + `:focus-visible` global

### FE-2 @ShannWasHere
- [x] GuardianPanel — semua pending ops (commit 8c085c3)
- [x] ApprovalsPage — table + approve/deny + detail
- [x] OperationsPage — live execution + filter status + history table

> `ApprovalsPage` dan `OperationsPage` **bukan file terpisah**. Keduanya fungsi
> lokal di `app/page.tsx` (baris 165 dan 195), bukan di `components/pages/`.
> Itu sebabnya `components/pages/` hanya berisi 6 file. `OperationsSidebar`
> tidak pernah ada sebagai komponen — log ikut di `OperationsPage`.

### Backend @DhikaSusheno / @Masrendra
- [x] Semua endpoint yang dipakai FE-1 sudah ada (`/operations`, `/graph/summary`, `/graph/nodes`, `/health`)
- [ ] (opsional) `GET /security/rules` — kalau ditambah, `RULES` di SecurityPage diisi dari backend
- [ ] (opsional) `GET /settings` + `POST /settings` — **tidak dipakai**. Tab Settings
      pakai `localStorage` supaya berfungsi tanpa endpoint baru. Kalau endpoint
      ini suatu hari ada, `lib/settings.ts` bisa jadi satu tempat untuk pindah.
