# TrustHub â€” Design System & Page Spec

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

> **Canvas graph wajib `#080d14`.** Dulu `#0f172a` (slate-900) â€”creates a seam
> karena `#0d1117` panel di atasnya. Sama dengan `bg-app`.

### Tema gelap dan terang

Ada dua tema. Yangé€‰ gelap di declare di `:root`, jadi itu default-nya dan
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

| Peran | Gelap | Terang |
|---|---|---|
| `--surface` | `#080d14` | `#eef1f4` |
| `--panel` | `#0d1117` | `#f9fafb` |
| `--panel-2` | `#0f141b` | `#f2f5f7` |
| `--inset` | `#0a0e14` | `#e3e8ed` |
| `--surface-hover` | `#131a24` | `#e9edf1` |
| `--line` | `#1e293b` | `#d7dde4` |
| `--ink-1` s/d `--ink-5` | `#f1f5f9` â†’ `#475569` | `#0f1722` â†’ `#8a9bad` |

Diukur terhadap warna panel tiap tema, semua warna accent dan semua langkah teks
lolos WCAG AA di tema terang: biru 6.41, hijau 4.80, merah 6.19, amber 4.81,
teks utama 17.2, sekunder 7.0. Dua langkah muted ada di 4.31 dan 2.73, yaitu
tempat yang sudah ditempati tema gelap sekarang (3.98 dan 2.50); keduanya dipakai
untuk placeholder dan meta, bukan body copy, dan angka itu tidak diperburuk demi
menyamakan dua tema.

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
| Vignette | `radial-gradient(130% 90% at 50% 0%)`, hitam `0 â†’ 0.38` | Menahan mata di tengah halaman, meng-ground bagian bawah |

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
lagi sebagai `bg-[#080d14]` di `layout.tsx` atau container halaman â€” itulah
alasan deklarasi ganda tersebut sudah dihapus.

### Logo

`components/shared/LogoMark.tsx` â€” satu-satunya sumber. Dipakai oleh `LeftNav`
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
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  BackendStatusBanner (dalam flow, bukan fixed)      â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚  TopNavbar (h-12, bg-panel, border-b)               â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ LeftNav  â”‚  <Page Content>          â”‚ GuardianPanel â”‚
â”‚ w-52     â”‚  flex-1 overflow-y-auto  â”‚ w-72          â”‚
â”‚          â”‚                          â”‚ (only on      â”‚
â”‚          â”‚                          â”‚ overview +    â”‚
â”‚          â”‚                          â”‚ guardian)     â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

`<body>` punya `h-screen overflow-hidden`, `layout.tsx` membungkus children dalam
flex column `min-h-0 flex-1`, dan root setiap halaman memakai **`h-full`** â€”
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
  `<html>`. **Jangan** deklarasikan ulang di `:root` â€” itu menimpa nama family
  hasil hash dan diam-diam jatuh ke system-ui (bug B-04).
- Ikon navigasi: SVG garis 24Ã—24, `stroke="currentColor"`, `strokeWidth={1.7}`.
  Tidak ada emoji sebagai ikon â€” warna emoji ikut sistem operasi sehingga tidak
  konsisten dengan UI yang monochrome.
- Entitas HTML (`&#183;`) hanya bisa dipakai di **teks JSX**. Di dalam string
  literal JS akan tampil apa adanya (bug B-16). Gunakan karakter aslinya.

---

## Route 0 â€” Landing / Explainer (`/landing`)

Server component. Tanpa state, tanpa fetch, tanpa `"use client"`.
Tujuan: juri memahami masalah dan solusi tanpa perlu penjelasan pemateri.

| Section | Isi | Syarat |
|---|---|---|
| Nav | Logo, anchor `#problem` `#how` `#agents` `#demo`, CTA `Open Live Demo` | Sticky, CTA ke `/` |
| Hero | Nama hackathon, 1 headline, 1 paragraf value, 2 CTA, 4 stat faktual | Headline menyebut masalah, bukan fitur |
| Problem | 3 kartu (review kalah cepat, tidak ada pemahaman bersama, sulit rollback) | Framing masalah |
| How it works | 4 langkah `01â€“04`: Understand â†’ Propose â†’ Guard â†’ Verify | Sebut blast radius, conflict, rollback |
| Properties | 4 kartu: Reversible, Conflict-aware, Fail-closed, Human in the loop | Semua harus benar-benar ada di backend |
| Agents | 3 kartu: Guardian, Cortex, Review | Tidak tumpang tindih |
| Demo path | 3 langkah bernomor, tiap langkah menyebut halaman tujuan | Jalur yang bisa didemokan manual |
| Stack | 8 chip teknologi | Hanya yang ada di `package.json` |
| Footer | Satu kalimat produk + link ke demo | â€” |

**Token visual:** `bg-app #080d14`, `bg-panel #0d1117`, `border slate-800/60`,
aksen tunggal `#3b82f6`, `rounded-xl` untuk kartu, `rounded-lg` untuk kontrol,
`max-w-6xl` + `px-6`.

**Aturan konten:** faktual saja, tidak boleh ada angka traction/performa yang
dikarang, tidak boleh ada slug generik, dan setiap langkah demo harus menyebut
halaman tujuan.

**Landing page memakai shell sendiri** â€” tanpa `TopNavbar`/`LeftNav`, tanpa
graph. Itu disengaja: halaman ini harus bisa dibaca tanpa login dan tanpa
backend hidup.

**Scroll:** `<body>` memakai `h-screen overflow-hidden` supaya dashboard tidak
bergeser saat banner muncul. Landing page karena itu **wajib** jadi scroll
container-nya sendiri â€” root-nya `h-full overflow-y-auto`. Tanpa itu, konten
5+ layar terpotong dan tidak ada scrollbar. Halaman dashboard tidak boleh
meniru pola ini; mereka sudah punya `overflow-y-auto` sendiri di dalam.

**Anchor:** header landing `sticky top-0` setinggi `h-14` (56px). Semua
section yang punya `id` wajib pakai `scroll-mt-14`, kalau tidak header akan
menutupi judul section begitu anchor diklik.

---

## Navigation Pages (9 halaman)

| ID | Label | Komponen | Owner | Status |
|---|---|---|---|---|
| `overview` | Overview | `OverviewMain` | FE-1 | âœ… Done |
| `code-graph` | Code Graph | `CodeGraphPage` | FE-1 | âœ… Done |
| `guardian` | Guardian | `GuardianPage` | FE-1 | âœ… Done |
| `cortex` | Cortex | `CortexPage` | FE-1 | âœ… Done |
| `agents` | Agents | `AgentsPage` | FE-1 | âœ… Done |
| `approvals` | Approvals | `ApprovalsPage` | FE-2 | âœ… Done (Shann) |
| `operations` | Operations | `OperationsPage` | FE-2 | âœ… Done (Shann) |
| `security` | Security | `SecurityPage` | FE-1 | âœ… Done |
| `settings` | Settings | `SettingsPage` | FE-1 | âœ… Done |

---

## Page 1 â€” Code Graph

**Layout:** 2-kolom (graph fullwidth kiri + selected node panel kanan)

### Left Area â€” Code Graph Canvas
- `TrustHubGraph` fullscreen dengan header panel:
  - Title: "Code Graph" + subtitle "Hybrid AST + semantic understanding"
  - Search bar: `Search files, symbols, docs...` â€” **benar-benar menyaring**
    (`lib/graphFilter.ts`), cocok ke `name` dan `id`, case-insensitive
  - Filter pills: `All | File | Symbol | Dependency | Doc` â€” menyaring node
    berdasarkan tipe. Node bertipe `operation` **selalu ikut**, apa pun filter,
    supaya status Approved/executing tidak hilang saat user mengetik
  - Zoom controls (+/âˆ’/reset)
  - Edge Relationships legend (calls, uses, defines, documents, depends on)
- Graph canvas mengisi sisa ruang
- Saat filter aktif, canvas kanan atas menampilkan `n/total nodes`
- Edge yang salah satu ujungnya tersaring ikut hilang â€” tidak ada edge menuju
  node yang tidak ada

### Right Area â€” Selected Node Panel (`w-64`)
- **Selected Node card:**
  - Icon file type + nama node (e.g. `app.py`)
  - Fields: Type, Path, Imports, Referenced by
  - Button: "View Details â†’"
- **Live SSE Activity panel:**
  - Badge: `â— Live`
  - List real-time events: timestamp + pesan singkat (last 5)

### Backend endpoints:
- `GET /graph/nodes` â€” load semua nodes
- `GET /graph/edges` â€” load semua edges
- `GET /stream` â€” SSE live updates
- `POST /explain_topic` â€” saat node diklik

---

## Page 2 â€” Guardian

**Layout:** single column scroll

### Header section:
- Badge: `â— ACTIVE`
- Title: "Guardian"
- Subtitle: "Protecting risky changes â€¢ Reversible â€¢ Conflict-aware"

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
- Horizontal step bar: Propose â†’ Snapshot â†’ Approve â†’ Execute â†’ Verify â†’ Complete
- Progress indicator current step
- Button: "View Logs â†’"

### Backend endpoints:
- `GET /list_pending_approvals`
- `POST /approve_operation`
- `POST /execute_operation`
- `GET /operations`

---

## Page 3 â€” Cortex

**Layout:** 3-kolom (repo tree kiri | explain panel tengah | graph context kanan)

### Left â€” Repository Tree (`w-56`):
- Search bar
- File tree dengan expand/collapse
- Highlight node yang dipilih

### Center â€” Explain Topic:
- Badge: `REVIEW MODE`
- Input field: "How does the guardian module work?"
- Button: **Explain**
- Result sections:
  - **Definition** â€” teks penjelasan
  - **Mental Model** â€” cara pikir
  - **Example** â€” code snippet

### Right â€” Review Artifact + Graph Context:
- **Review Artifact card:**
  - Input path/diff
  - Button: "Run Review"
  - Scores: Completeness / Clarity / Correctness vs Spec / Risk (0â€“10)
- **Graph Context** mini-graph (subset dari force graph)

### Backend endpoints:
- `POST /explain_topic`
- `POST /review_artifact`
- `GET /graph/nodes` (untuk tree)
- `GET /repo_health`
- `GET /complexity_report`
- `POST /find_path`
- `POST /suggest_refactor`

### Centre â€” kartu tambahan (live, urutan ke bawah):
- **Repo Health** â€” skor 0â€“100 + label, summary, 4 stat (Files / Documented / Dead code / Complex), hub nodes
- **Complexity Ranking** â€” tabel top 10 simbol: nama + `file:line`, complexity, lines, badge risk
- **Find Path** â€” dua input (from â†’ to), hasil jalur sebagai chain node + label relasi
- **Refactor Suggestions** â€” satu input nama entitas, metrics (cx / lines / degree / docs) + daftar saran berprioritas

Semuanya respek `NEXT_PUBLIC_USE_LIVE_SSE`: kalau `false`, tiap kartu menampilkan
"Live data OFF" dan tombol nonaktif â€” bukan mock data.

---

## Page 4 â€” Agents

**Layout:** header agents cards + 2-kolom bawah

### Top â€” 3 Agent Cards (horizontal):
Setiap card:
- Icon + Name (Guardian / Cortex / Review)
- Subtitle (Protection & Safety / Understanding & Review / Code Review & Analysis)
- Stats: Tasks (number) + Status (â— Healthy / â— Running)

### Bottom Left â€” Current Tasks:
- List 3â€“5 tasks:
  - Agent name + task description + timestamp
  - Real-time dari SSE `operation_*` events

### Bottom Right â€” SSE Event Stream:
- Badge: `â— Live`
- Scrollable list: timestamp | agent | event message
- Color-coded per agent

### Bottom â€” Agent Activity Chart:
- Line chart (Guardian=biru, Cortex=ungu, Review=abu)
- X-axis: waktu (10 tick)
- Y-axis: activity level

### Conflict sidebar:
- Badge count merah
- Op name + conflict details + "View â†’" button

### Recent Actions list:
- Agent | action | timestamp (relative)

### Backend endpoints:
- `GET /stream` â€” SSE untuk live tasks + event stream
- `GET /operations?limit=5` â€” recent actions
- `GET /repo_health` â€” agent health status

---

## Page 5 â€” Approvals âœ… (Shann)

Sudah diimplementasi oleh @ShannWasHere di commit `8c085c3`.

Spec: table dengan kolom TIME | OPERATION | RISK | AGENT | CONFLICTS + tombol Approve/Deny per row + Operation Details panel di bawah.

---

## Page 6 â€” Operations âœ… (Shann)

Sudah diimplementasi oleh @ShannWasHere di commit `8c085c3`.

Spec: Live Execution step tracker + Operation History table dengan filter.

---

## Page 7 â€” Security

**Layout:** 2x2 grid cards + event feed

### Security Overview card:
- Stats: Total Checks | Violations | Blocked Ops | Rules Active
- Badge: `â— Healthy`

### Rule Engine card:
- Title + "Static rules & heuristics (not ML)"
- Policy: "Fail-closed (default)"
- Rule list:
  - Dangerous operation detection
  - Conflict detection (overlapping resources)
  - Reversibility requirement
  - Unknown operation fail-closed
  - Blast radius classification
- Button: "View Rules â†’"

### Adversarial Test Results card:
- N/M tests passed badge
- Checklist items (green=pass, red=fail)
- Button: "View Details â†’"

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
- `GET /repo_health` â€” overall health
- `GET /operations?status=failed` â€” failed ops
- `GET /operations?status=rolled_back` â€” rollbacks
- `GET /stream` â€” live security events

---

## Page 8 â€” Settings

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
- `GET /health` â€” server status
- `GET /graph/summary` â€” storage stats
- (Settings disimpan di localStorage frontend â€” tidak butuh backend endpoint baru)

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

## Backend Endpoints â€” Mapping ke Halaman

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

- `lib/mockData.ts` â€” MOCK_NODES, MOCK_LINKS, MOCK_TIMELINE (graph + timeline)
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
â”œâ”€â”€ DESIGN_SYSTEM.md         â† dokumen ini
â”œâ”€â”€ PRD.md                   â† scope + bug ledger + checklist demo
â”œâ”€â”€ MASTER_PROMPT.md         â† prompt lanjutan ke AI agent
â”œâ”€â”€ README.md                â† cara run + endpoint map
â”œâ”€â”€ app/
â”‚   â”œâ”€â”€ page.tsx             â† shell 3 kolom + routing 9 halaman
â”‚                              + ApprovalsPage & OperationsPage (fungsi lokal)
â”‚   â”œâ”€â”€ landing/page.tsx     â† explainer hackathon (server component)
â”‚   â”œâ”€â”€ globals.css
â”‚   â”œâ”€â”€ layout.tsx           â† flex column: banner di flow, children h-full
â”‚   â””â”€â”€ api/graph/route.ts
â”œâ”€â”€ components/
â”‚   â”œâ”€â”€ LeftNav.tsx          â† FE-1: navigasi kiri
â”‚   â”œâ”€â”€ TopNavbar.tsx        â† FE-1: top bar
â”‚   â”œâ”€â”€ GuardianPanel.tsx    â† FE-1: right panel
â”‚   â”œâ”€â”€ OverviewMain.tsx     â† FE-1: halaman overview
â”‚   â”œâ”€â”€ TrustHubGraph.tsx     â† FE-1+2: force graph canvas
â”‚   â”œâ”€â”€ pages/
â”‚   â”‚   â”œâ”€â”€ CodeGraphPage.tsx  â† FE-1 âœ…
â”‚   â”‚   â”œâ”€â”€ GuardianPage.tsx   â† FE-1 âœ…
â”‚   â”‚   â”œâ”€â”€ CortexPage.tsx     â† FE-1 âœ…
â”‚   â”‚   â”œâ”€â”€ AgentsPage.tsx     â† FE-1 âœ…
â”‚   â”‚   â”œâ”€â”€ SecurityPage.tsx   â† FE-1 âœ…
â”‚   â”‚   â””â”€â”€ SettingsPage.tsx   â† FE-1 âœ…
â”‚   â””â”€â”€ shared/
â”‚       â”œâ”€â”€ RiskBadge.tsx            â† FE-1 âœ…
â”‚       â”œâ”€â”€ StatusBadge.tsx          â† FE-1 âœ…
â”‚       â”œâ”€â”€ AgentBadge.tsx           â† FE-1 âœ…
â”‚       â””â”€â”€ BackendStatusBanner.tsx  â† DEMO DATA / LIVE / OFFLINE
â”œâ”€â”€ hooks/
â”‚   â”œâ”€â”€ useSSE.ts
â”‚   â”œâ”€â”€ useSSEStream.ts
â”‚   â”œâ”€â”€ useBackendStatus.ts  â† SATU poller /health, banyak subscriber
â”‚   â”œâ”€â”€ useLiveOps.ts        â† FE-1 âœ… poll /operations
â”‚   â””â”€â”€ useMockSimulation.ts
â””â”€â”€ lib/
    â”œâ”€â”€ types.ts
    â”œâ”€â”€ mockData.ts
    â”œâ”€â”€ graphFilter.ts       â† filter + search graph (pure, ada test)
    â”œâ”€â”€ derive.ts            â† FE-1 âœ… derivasi data live -> UI
    â”œâ”€â”€ derive.test.ts       â† FE-1 âœ…
    â””â”€â”€ nodeVisuals.ts
```

---

## Checklist Implementasi

### FE-1 @nabilfauzandafa
- [x] OverviewMain (Code Graph panel + Timeline + Risk & Activity + Feature Cards)
- [x] LeftNav (9 item + badge)
- [x] TopNavbar
- [x] GuardianPanel (semua pending ops, scrollable)
- [x] CodeGraphPage â€” graph fullscreen + node panel + SSE activity
- [x] GuardianPage â€” pending op detail + reversibility + timeline
- [x] CortexPage â€” repo tree dari `/graph/nodes` + explain + review + graph context
- [x] CortexPage â€” 4 endpoint BE yang sebelumnya tidak pernah dipanggil: `/repo_health`, `/complexity_report`, `/find_path`, `/suggest_refactor`
- [x] AgentsPage â€” 3 agent cards + tasks + SSE stream + activity chart (data live)
- [x] SecurityPage â€” stats + rule engine + conflict candidates + event feed (data live)
- [x] SettingsPage â€” tabs: General + MCP / Server + Storage + Repository + Approval
- [x] SettingsPage â€” persistensi `localStorage` + Save/Reset + error handling
- [x] Shared badges (RiskBadge, StatusBadge, AgentBadge) + BackendStatusBanner
- [x] hooks/useLiveOps.ts â€” poll `/operations`
- [x] hooks/useBackendStatus.ts â€” satu poller `/health`, banyak subscriber
- [x] lib/derive.ts + lib/derive.test.ts â€” derivasi murni + 20 test
- [x] lib/graphFilter.ts + lib/graphFilter.test.ts â€” filter/search graph + 9 test
- [x] Nav "Agents" masuk LeftNav (sebelumnya halaman tidak terjangkau)
- [x] Landing `/landing` â€” explainer hackathon, server component, statis
- [x] Shell: banner masuk flow, `h-screen` pindah ke `<body>`, halaman `h-full`
- [x] `color-scheme: dark` + `:focus-visible` global

### FE-2 @ShannWasHere
- [x] GuardianPanel â€” semua pending ops (commit 8c085c3)
- [x] ApprovalsPage â€” table + approve/deny + detail
- [x] OperationsPage â€” live execution + filter status + history table

> `ApprovalsPage` dan `OperationsPage` **bukan file terpisah**. Keduanya fungsi
> lokal di `app/page.tsx` (baris 165 dan 195), bukan di `components/pages/`.
> Itu sebabnya `components/pages/` hanya berisi 6 file. `OperationsSidebar`
> tidak pernah ada sebagai komponen â€” log ikut di `OperationsPage`.

### Backend @DhikaSusheno / @Masrendra
- [x] Semua endpoint yang dipakai FE-1 sudah ada (`/operations`, `/graph/summary`, `/graph/nodes`, `/health`)
- [ ] (opsional) `GET /security/rules` â€” kalau ditambah, `RULES` di SecurityPage diisi dari backend
- [ ] (opsional) `GET /settings` + `POST /settings` â€” **tidak dipakai**. Tab Settings
      pakai `localStorage` supaya berfungsi tanpa endpoint baru. Kalau endpoint
      ini suatu hari ada, `lib/settings.ts` bisa jadi satu tempat untuk pindah.
