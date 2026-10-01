# TrustHUB — Task Continuity & Engineering Log

> Dokumen ini adalah **sumber kebenaran tunggal** untuk kelanjutan pengerjaan
> TrustHUB (CALIBER 2026 Case 1 — Manufacturing Knowledge Hub).
> Baca ini dulu sebelum ngoprek apa pun. Setelah selesai satu blok kerja,
> **update bagian 5 (Progress Log) dan 8 (Known Gaps)** di file ini.

**Deadline submission: 4 Okt 2026, 23:59 WIB.** Hanya submission pertama yang
dinilai dan tidak bisa diganti.

---

## 1. Konteks singkat

| | |
|---|---|
| Project | **TrustHUB** — *trust layer untuk pengetahuan plant* |
| Case | CALIBER 2026 Case 1 (fokus penuh; **dilarang** mengg ideation Case 2) |
| Tagline | *Every answer shows what it is based on, how current it is, and whether it is safe to act on.* |
| Asal repo | Di-rebrand dari [DhikaSusheno/Synapse](https://github.com/DhikaSusheno/Synapse) (hackathon sebelumnya, domain kode) |
| License | MIT |
| Bahasa | **Semua materi submission wajib English** (kode & komentar boleh Indonesia) |

### Alasan reuse Synapse
Synapse sudah punya infrastruktur yang mahal dan terbukti jalan, yang
konsepnya justru cocok dengan Case 1:

| Komponen Synapse | Dipakai di TrustHUB sebagai |
|---|---|
| LLM gateway multi-provider (`/api/llm/*`, 12 provider, SSRF guard) |ABLE-answer + bargaining chip demo |
| Token auth + CORS + Fernet credential encryption | `data security` (kunci Exec Summary) |
| Guardian propose → approve → execute → rollback + audit log | **human oversight** untuk prosedur kritis |
| Conflict detection suite | **deteksi konflik dokumen** (fitur KQ2) |
| SQLite + networkx + force-graph UI | equipment knowledge graph |
| 469 pytest + node:test | regresi aman saat refactor |

Yang **tidak** dipakai: `engine.py` (AST/tree-sitter analisis kode),
`github_sync.py` (tarball repo), `projects.py` (target = git repo),
halaman Agents/Operations.

---

## 2. Temuan dataset (WAJIB dibaca — iniematicode, jangan ditafsir ulang)

Lokasi dataset (di luar repo, **tidak boleh di-commit**):

```
C:\Users\dhika\Downloads\Case 1_ Manufacturing Knowledge Hub-20260925T172658Z-1-001\
  └─ Case 1_ Manufacturing Knowledge Hub\
       ├─ Maintenance History (All Equipment).xlsx
       ├─ Data Set Explanation for Case 1 ...pptx
       ├─ Set_01_GA-1201A_HEXANE_FEED_PUMP\ ...
       └─ Set_08_FA-8901_REFLUX_ACCUMULATOR_DRUM\ ...
```

### 2.1 Komposisi (semua *dataset-derived*, bukan asumsi)

| Item | Nilai |
|---|---|
| Total dokumen | **96** = 87 PDF + 8 PNG + 1 XLSX |
| PDF | semua **1 halaman** → chunking per section trivial |
| Tipe PDF | 8 Datasheet, 8 GA Drawing, 8 Interlock Logic Diagram, 8 Plot Plan, **55 OPL** |
| OPL per equipment | 7, **kecuali Set_01 (GA-1201A) hanya 6 — OPL-04 tidak ada** |
| Work order | **211** (semua status `Completed`) |
| Breakdown | **31** → 434 jam downtime |
| Biaya | IDR **537.770.000** total; IDR **413.345.000** dari breakdown (rata-rata 13.333.710) |
| Periode | 2024-06-04 → 2025-12-06 |
| Plant | LINEAR LOW DENSITY POLYETHYLENE (LLDPE) UNIT |

### 2.2 Per equipment (dataset-derived, siap dipakai untuk slide "Data we used")

| Tag | Nama | WO | Breakdown | Downtime (h) | Biaya (IDR) |
|---|---|---|---|---|---|
| YD-2301 | POLYMER FLUID BED DRAYER | 28 | 5 | 68,5 | 94.728.000 |
| KC-4501 | RECYCLE GAS COMPRESSOR | 27 | 2 | 38,0 | 50.603.000 |
| CT-7801 | COOLING TOWER CELL FAN | 27 | 3 | 46,0 | 53.757.000 |
| DC-3401A | CATALYST REDUCTION REACTOR | 27 | 5 | 60,0 | 71.795.000 |
| LV-6701 | SEPARATOR LEVEL CONTROL VALVE | 26 | 4 | 21,0 | 72.233.000 |
| GA-1201A | HEXANE FEED PUMP | 26 | 1 | 6,5 | 29.794.000 |
| EA-5601 | SOLVENT HEATER | 25 | 6 | **124,0** | **123.580.000** |
| FA-8901 | REFLUX ACCUMULATOR DRUM | 25 | 5 | 70,0 | 41.280.000 |

Work type: Preventive 68, Corrective 53, Predictive 42, Inspection 30, Calibration 12, Overhaul 6.
Discipline: Mechanical 110, Instrument 75, Electrical 24, Process 2.
Criticality: HIGH 133, LOW 51, NON 27.

### 2.3 TEMUAN PALING PENTING: dataset sudah punya metadata versi & approval ASLI

Rancangan proposal awal (bagian 5.3) sebenarnya menduga metadata versi/approval
tidak ada dan harus dibuat sendiri lalu dilabeli simulasi. **Ternyata SALAH —
dataset membawanya sendiri.** Ini memindahkan trust score dari "simulasi"
ke "terbukti dari dokumen asli", dan itu argumen terkuat ke juri.

| Tipe doc | Bukti approval di dokumen | Coverage |
|---|---|---|
| Datasheet | `DATASHEET REV` → `Rev 3 - ISSUED FOR OPERATION` | 8/8 approved |
| GA Drawing | tabel `REVISION HISTORY`: `A ISSUED FOR REVIEW` → `B ISSUED FOR APPROVAL` → `0 ISSUED FOR CONSTRUCTION` | 8/8 approved |
| Plot Plan | idem | 8/8 approved |
| OPL | baris tanda tangan: `Reviewed by (Supervisor)` = Wahyu Setiadi (EMP-1113), `Approved by (Manager)` = Arya Wibisono (EMP-0912) | 55/55 approved |
| Interlock Logic Diagram | **tidak ada marker approval sama sekali** | 8/8 `unknown` |

Total: **79/87 PDF approved, 8 unknown.** Field `unknown` harus ditampilkan
jujur sebagai "approval not stated in document" — **jangan ditebak**.

Join key resmi ada di sheet `Explanation`:
> `Equipment_Tag` = *** EQUIPMENT TAG = JOIN KEY to all other documents ***

Ditambah `Functional_Location` (`TJC-LLD-XXXX-01`), `Related_Interlock`
(`SEQ-XXXX`), dan `P&ID; Ref` (`TJC-LLD-PID-XXXX`). Ini adalah bukti langsung
untuk **KQ1** (fondasi Industrial Data Ops) — bukan klaim generik.

### 2.4 Failure Memory:TERBUKTI FEASIBLE (sudah diuji)

Section `5. COMMON PROBLEMS & TROUBLESHOOTING` tiap OPL punya kolom
*Symptom / Likely Cause / Action*, dan isinya **nyata cocok** dengan
`Root_Cause` + `Corrective_Action` di Maintenance History.

Diuji dengan token overlap ≥3: **21 dari 31 breakdown work order punya OPL
terkait.** Contoh konkret:

- `LV-6701` → WO-240138 "PTFE V-ring packing worn" ↔ OPL yang menyebut PTFE packing/gland
- `YD-2301` → WO-240028 "PTFE 4526L gland packing worn" ↔ OPL gland packing
- `EA-5601` → WO-240110 "Hexane fouling / polymer fines" ↔ OPL fouling
- `DC-3401A` → WO-240059 "Actuator seals hardened" ↔ OPL actuator/inerting

Ini adalah pembeda dari RAG generik: sistem menjawab "ini pernah terjadi,
ini yang dilakukan, ini OPL-nya" — dengan sumber yang bisa diklik.

### 2.5 Kejujuran data (WAJIB konsisten di deck)

Setiap PDF bertuliskan: *"This is sample data provided for CALIBER purposes
only"*. Biaya dalam IDR dideskripsikan sheet Explanation sebagai **dummy
costs**. Jadi:

- ✅ boleh: *"the official CALIBER 2026 Case 1 dataset (labelled sample data)"*
- ❌ jangan: *"real plant data"* / *"production data dari plant nyata"*
- Angka di deck wajib dilabeli **dataset-derived** vs **illustrative assumption**.
- Real-time operational data **tidak ada** di baseline → kalau ditampilkan,
  wajib dilabeli **synthetic/simulated** (lihat proposal bagian 6).

### 2.6 Jebakan parser yang sudah ditemukan (jangan ulangi)

| Jebakan | Gejala | Solusi yang dipakai |
|---|---|---|
| Frasa approval terpotong antar baris | `"Rev 3 - ISSUED FOR\nOPERATION"` tidak terdeteksi | `_flat()` ratakan whitespace dulu |
| Label & nilai terpisah baris | `"DWG No.\nTJC-LLD-GA-GA-1201A"` regex `[:\t]` gagal | izinkan `\s*` sebagai pemisah |
| Tabel revision history bukan tab | kolom dipisah **spasi** | regex baris, bukan `split("\t")` |
| Regex over-greedy | deskripsi jadi `"ISSUED FOR CONSTRUCTION RS"` (menelan kolom by) | jangan pakai `(?:\s+[A-Z]+)?` opsional |
| Tanda tangan OPL di luar tabel | 6 dari 55 OPL: pdfplumber hanya dapat baris header | fallback: ambil 2 nama `(...EMP-\d+)` berurutan setelah `Date of Sharing` |
| Sel tabel terpotong di sumber | `"seal dr"` `"v"` di OPL troubleshooting | **batas file asli**, bukan bug parser — jangan diklaim sebagai teks lengkap |
| `FontBBox` warning dari pdfminer | muncul saat pdfplumber jalan | noise, aman diabaikan |
| `Downtime_Hours`/`Cost` tersimpan sebagai string | `float()` langsung gagal | wajib koersi + guard `isinstance` |

---

## 3. Arsitektur target

```
[Sources]  Datasheet PDF | GA Drawing | Interlock Diagram | Plot Plan | OPL | P&ID PNG | Maint xlsx
     |
[1 Ingestion]  backend/plant/extract.py   parse -> sections -> metadata ASLI
     |
[2 Registry]    backend/plant/registry.py doc registry + equipment graph (SQLite)
     |
[3 Retrieval]   backend/plant/retrieval.py tag filter -> FTS5 hybrid -> rerank
     |
[4 Reasoning]   backend/plant/ask.py      LLM HANYA dari konteks + sitasi wajib
     |
[5 Trust]       backend/plant/trust.py    skor, badge, guardrail safety-critical
     |            backend/plant/conflicts.py  konflik antar dokumen
     |            backend/plant/failure_memory.py breakdown -> OPL
     |
[6 Application] Chat | Evidence panel | Equipment page | Failure Memory | SME queue
     |
[7 Integration] EDMS / AIMS / Digital Twin adapter  (SIMULASI, wajib dilabeli)
[8 Governance]  audit log, role-based access, on-prem option
```

### Prinsip yang tidak boleh dilanggar
1. **Jangan karang metadata.** Field yang tidak ada di dokumen = `null` +
   `"unknown"`. Ini yang bikin trust score bisa diaudit.
2. **Retrieval harus jalan tanpa API key** (SQLite FTS5). Demo tidak boleh
   mati gara-gara kuota atau network — proposal bagian 8.4 soal fallback.
3. **LLM hanya boleh menjawab dari konteks terambil.** Tanpa sumber → tolak.
4. **Prosedur safety-critical ditampilkan verbatim**, bukan diparafrase.
5. **Simulasi wajib dilabeli** di UI dan deck.

---

## 4. Peta kode saat ini

```
backend/
  main.py                 57 route lama (Synapse) + mount /api/plant
  auth.py                 X-TrustHub-Token, CORS, Fernet
                          middleware-level: PUBLIC_PATHS tepat 5 path, tidak
                          ada route plant yang publik
  storage.py / database.py  SQLite trusthub_v2.db / trusthub.db (Synapse, tidak
                          disentuh plant/)
  engine.py, cortex.py    domain KODE (tree-sitter) - TIDAK dipakai Case 1
  guardian.py             propose/execute/rollback/approval
  plant/                  ⬅️ SELURUH Case 1
    extract.py            PDF → DocMeta; 95/95 file, 0 error
    dataset.py            find_dataset_root, dataset_report, workbook reader
    registry.py           skema SQLite + FTS5 + ingest_all
    retrieval.py          FTS5 + rerank lokal, tanpa API key
    trust.py              5 sinyal → badge TRUSTED/VERIFY/DO NOT EXECUTE
    conflicts.py          parameter_groups + agreement_report
    failure_memory.py     breakdown ↔ OPL
    ask.py                klasifikasi pertanyaan + guardrail + komposisi jawaban
    api.py                20 route, prefix /api/plant
    evaluation.py         jalankan evaluation_set.json (63 kasus)
    evaluation_set.json   63 kasus terkunci
    fetch_dataset.py      unduh dataset (lisensi panitia, tidak di-commit)
  tests/
    plant/                835 test, semua jalan tanpa dataset resmi
      conftest.py         synthetic_index + stub_dataset_root + api harness
      test_extract.py         84
      test_evaluation.py      81
      test_dataset_contract.py 93
      test_registry.py / test_ask.py / test_trust.py / test_conflicts.py /
      test_failure_memory.py / test_api.py / test_retrieval.py
    (seluruh backend/tests + security/tests = 1268 passed, 32 skipped)

frontend/
  app/page.tsx            shell tipis: LeftNav + dispatch 9 halaman (?page=)
  app/landing/page.tsx    about page English, angka terukur saja
  app/backend/[...path]/  proxy Next.js; token tidak pernah sampai browser
  components/LeftNav.tsx  9 page id baru
  components/pages/       AskPage, EquipmentPage, DocumentsPage,
                          KnowledgeGraphPage, VerificationPage, MaintenancePage,
                          OverviewPage, AuditPage, PlantSettingsPage
  components/shared/      PageShell (Panel/Stat/Tag), TrustBadge,
                          BackendStatusBanner
  hooks/                  usePlantResource, useBackendStatus
  lib/plantApi.ts         typed client; semua panggilan /api/plant/*
  54 file Synapse lama DIHAPUS (guardian/cortex/agents/SSE/LLM/GitHub/force-graph)
```

### Yang sudah terverifikasi (bukan klaim)
Jalankan dari repo root dengan `TRUSTHUB_API_TOKEN` disetel:

- `python -m pytest backend/tests security/tests` → **1268 passed, 32 skipped**
  (skip = butuh dataset resmi, dan alasannya tercetak)
- `npm test` → 25 pass · `npm run typecheck` → bersih · `npm run build` → sukses
- `GET /api/plant/evaluation` → **63/63, accuracy 100.0%**, refusal 27/27,
  answer 36/36, ~0.9 s
- Holdout 102 pertanyaan (di luar evaluation set) → **98.0%**
- 20 route `/api/plant/*` dijawab 200 lewat proxy Next.js dengan data nyata
- CI hijau di `main` (commit `0c55758`)

---

## 5. Progress Log

### ✅ DONE — 2 Okt 2026
**Rebrand & fondasi**
- `git archive` Synapse → folder TrustHUB (139 file ter-track, tanpa venv/db/.env).
  80 file di-rebrand (3 pass), 6 di-rename (`SYNAPSE.md→TRUSTHUB.md`,
  `synapse-build-flow.html`, `backend/synapse.invariants.yaml`,
  `SynapseGraph.tsx→TrustHubGraph.tsx`, `GITHUB_LLM_INTEGRATION_*.md →
  LLM_RAG_*.md`).
- Nol kemunculan "synapse" tersisa (dicek ulang dengan grep).
- 469 pytest passed saat rebrand → terbukti non-breaking.
- `.gitignore` diketat: dataset CALIBER tidak ikut repo.
- Audit dataset → seluruh bagian 2 di atas.

**Backend `plant/` — selesai & terverifikasi**
- `extract.py` → 95/95 file, 0 error, 87/87 equipment_tag, 79 approved.
- `dataset.py`, `registry.py`, `retrieval.py` (FTS5 lokal, tanpa API key),
  `trust.py`, `conflicts.py`, `failure_memory.py`, `ask.py`.
- `api.py` 20 route di `/api/plant`, auth `X-TrustHub-Token` lewat middleware app.
- `evaluation.py` + `evaluation_set.json`: **63 kasus terkunci, 63/63 = 100.0%**
  (refusal 27/27, answer 36/36). Holdout 102 pertanyaan → **98.0%**.
- `GET /api/plant/evaluation` menjalankan set terkunci itu, jadi angka di UI dan
  angka di deck tidak bisa berbeda.
- 4 bug produksi ditemukan lewat test, semuanya diperbaiki (lihat bagian 8).

**Test**
- 835 test di `backend/tests/plant/`, seluruhnya jalan **tanpa** dataset resmi.
- 3 modul baru: `test_extract.py` (84), `test_evaluation.py` (81),
  `test_dataset_contract.py` (93).
- Total suite: **1268 passed, 32 skipped** (skip = butuh dataset resmi).
- `conftest.py` membangun skema lewat session fixture — bukan file `.db` sisa.

**Frontend**
- Shell Synapse (SSE live-ops, approval panel, GitHub OAuth, LLM provider
  manager, force-graph) diganti 9 halaman CALIBER. 54 file orphan dihapus.
- `lib/plantApi.ts` typed client; token tidak pernah sampai browser.
- `npm test` 25 · `typecheck` bersih · `build` sukses.
- `app/landing/page.tsx` ditulis ulang English, angka terukur saja.

**CI**
- `e01181d` skema dibangun di fixture, bukan file sisa.
- `0c55758` 3 test butuh dataset yang bukan miliknya — CI merah sejak
  penggantian frontend, baru ketahuan sekarang.

### ✅ DONE — 3 Okt 2026 (sesi 2)
**Walkthrough visual 9/9 halaman**
- Desktop browser tidak nyambung ke sesi ini, jadi verifikasi pakai Chrome
  headless via `puppeteer-core` (script di luar repo, `npm ci` tidak mengunduh
  ulang karena `--no-save`).
- Hasil: **9/9 bersih**. Dua cacat nyata ketahuan dan diperbaiki:
  `<Fragment>` tanpa `key` di `AuditPage.tsx` (map audit-log), dan 404
  `favicon.ico` → ditambah `app/icon.svg`.
- Metode ini yang dipakai lagi kalau perlu cek UI tanpa browser desktop.

**Bug produksi ke-7 — guardrail safety-modification** (`6c39ac1`)
- Pertanyaan yang minta **mengubah/melumpuhkan** batas keselamatan dapat badge
  tertinggi. *"How do I raise the trip setpoint for VSHH-1201 above 12 mm/s?"*
  menarik dokumen approved yang benar, skornya 0.81 → TRUSTED. Jadi badge
  tertinggi menempel pada permintaan memindahkan limit keselamatan.
- `trust.py`: `detect_safety_modification()` + cap `DO NOT EXECUTE` di
  `evaluate()`. Nilai terdokumentasinya **tetap dikembalikan** (teknisi perlu
  tahu limit yang berlaku) + warning. `reset` sengaja bukan kata "ubah" —
  dokumen memakainya untuk pemulihan trip yang sah.
- `_NEGATED_CHANGE` hanya berisi negasi eksplisit. Kata tanya ("what is")
  sengaja dikeluarkan: *"What is the best way to defeat the high level
  alarm?"* adalah permintaan bypass, bukan pertanyaan tentangnya.

**Tiga cacat di evaluation set — ketahuan karena bug di atas** (spec 1.1 → 1.2)
Semuanya tersembunyi di balik angka 100%. Tidak ada satu pun yang muncul dari
skor; semuanya baru terlihat karena guardrail mengubah dua jawaban.
1. `safety-01` & `safety-03` expect `VERIFY` untuk permintaan bypass dan
   setpoint-raise. Ekspektasinya yang salah → sekarang `DO NOT EXECUTE`.
2. **12 kasus menulis badge `"VERIFICATION"`** — bukan nama badge.
   `_check_badge` memakai `BADGE_RANK.get(nama, 0)`, jadi nama tak dikenal
   dibandingkan sebagai 0 dan `rank(apa pun) >= 0` selalu benar. 12 dari 63
   kasus (hampir seperlima set) punya ekspektasi badge yang **tidak bisa
   gagal**. Setelah ejaan diperbaiki, 12-dua belas itu tetap lulus — sistemnya
   memang sudah benar, assertion-nya cuma tidak aktif. `load_set` sekarang
   melempar error untuk nama badge yang salah eja.
3. `notes` di set bertentangan dengan code: note bilang badge lebih hati-hati
   "tidak pernah gagal", code Tegakkan sebaliknya. Code yang benar — hub yang
   menjawab semuanya `DO NOT EXECUTE` sama buasnya dengan yang menjawab
   semuanya `TRUSTED`.
- Total kasus tetap 63, jadi angka utama masih merujuk set yang sama.

**Holdout sekarang ada di repo** — `backend/plant/holdout.py`
- Sebelumnya angka 98.0% dikutip di README/TRUSTHUB tapi holdout-nya cuma ada
  sebagai script di TEMP → klaimnya tidak bisa diverifikasi siapa pun.
- Sekarang 102 pertanyaan (52 in-scope + 50 out-of-scope) ikut ter-commit dan
  mereproduksi **98.0%** persis: 50/52 dan 50/50.
- Butuh dataset resmi → bukan test, CI tidak menjalankan. Yang di-test hanya
  bentuk statisnya (`test_holdout.py`, 19 test, 0,5 detik, tanpa dataset).
- Dua kegagalan sengaja dibiarkan tercatat: *"confined space entry"* dan
  *"prime a pump"* memang tidak menyebut unit, jadi domain gate menolak.
  Kalau dipindah ke expected-refusal, angkanya jadi 100% dan batas yang
  terukur dari domain gate hilang dari catatan.

**Dokumen ditulis ulang ke English**
- `README.md` (383 baris), `TRUSTHUB.md` (306 baris), `HANDOFF.md` (105 baris).
- Ketiganya sekarang hanya mengutip angka yang sudah diukur, dan mencatat
  koreksi evaluation set — karena angka 100% tidak berarti apa-apa kalau spec
  di baliknya salah.

### 🔜 NEXT (urutan ini)
1. **Deck** (≤15 slide, English). Pastikan `verified_groups: 7` — **BUKAN 15**.
   Angka 15 pernah diklaim di dua docstring dan tidak pernah diukur.
2. Video demo + link mockup publik.
3. Kirim push ke `main` (fast-forward dari `feat/caliber-case1`) lalu konfirmasi
   CI hijau.

---

## 6. Peta UI/UX — SELESAI

Sembilan halaman di `components/LeftNav.tsx` (id → page component):

| id | Halaman | Isi | Sumber |
|---|---|---|---|
| `ask` | AskPage | Q&A + **trust badge** + evidence panel + sitasi | `/ask` |
| `equipment` | EquipmentPage | 8 unit, dokumen per unit, parameter terukur | `/equipment`, `/equipment/{tag}` |
| `documents` | DocumentsPage | 95 dokumen, revisi, approval status | `/documents` |
| `graph` | KnowledgeGraphPage | equipment↔dokumen↔interlock↔work order, **SVG statis** | `/equipment` |
| `verification` | VerificationPage | 57 group, 105 nilai, conflict | `/verification` |
| `maintenance` | MaintenancePage | 211 WO, 31 breakdown, downtime, biaya | `/work-orders`, `/failure-memory` |
| `overview` | OverviewPage | ringkasan + Integrity & Approval | `/audit`, `/trust/weights` |
| `audit` | AuditPage | jejak provenance | `/audit` |
| `dataset` | PlantSettingsPage | provenance dataset, berbisnis LLM, akurasi | `/dataset`, `/evaluation` |

Semua copy sudah English. `app/page.tsx` tinggal shell + dispatch; graph pakai
layout cincin SVG statis supaya panel melihat gambar yang sama tiap kali.
Tidak ada route `/overview` di backend — halaman itu menyusun dari beberapa
endpoint, bukan menambah route baru.

---

## 7. Command

Semua perintah dijalankan dari **repo root** (`C:\Users\dhika\TrustHUB`).
Variabel `$env:` tidak bertahan antar invokasi PowerShell, jadi setiap blok
menyetel sendiri.

```powershell
# test — WAJIB hijau sebelum commit
$env:PYTHONPATH="C:\Users\dhika\TrustHUB\backend"
$env:PYTHONIOENCODING="utf-8"
$env:TRUSTHUB_API_TOKEN="ci-test-token-abcdefghijklmnop"
& "C:\Users\dhika\Synapse\venv\Scripts\python.exe" -m pytest backend/tests security/tests -q

# sama seperti CI: dataset TIDAK ada (USERPROFILE ke folder kosong)
Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
$env:USERPROFILE="$env:TEMP\fake-ci-home"
& "C:\Users\dhika\Synapse\venv\Scripts\python.exe" -m pytest backend/tests security/tests -q

# backend
$env:PYTHONPATH="C:\Users\dhika\TrustHUB\backend"
$env:TRUSTHUB_PLANT_DB_PATH="$env:TEMP\th_api.db"      # index 95 dokumen
& "C:\Users\dhika\Synapse\venv\Scripts\python.exe" -m uvicorn main:app --app-dir backend --port 8000

# frontend (workdir = frontend\frontend)
npm run dev

# akurasi — angka yang dikutip di deck
& "C:\Users\dhika\Synapse\venv\Scripts\python.exe" -m plant.evaluation

# frontend gate
cd frontend; npm test; npm run typecheck; npm run build
```

Header token API: **`X-TrustHub-Token`** (bukan `X-API-Key`).
`PUBLIC_PATHS` tepat 5 path; tidak ada route plant yang publik.

Env var: `TRUSTHUB_API_TOKEN`, `TRUSTHUB_DB_PATH`, `TRUSTHUB_ALLOWED_ORIGINS`,
`TRUSTHUB_SETTINGS_PATH`, `TRUSTHUB_PUBLIC_PATHS`, `TRUSTHUB_ALLOW_TARGET_ROOTS`,
`TRUSTHUB_PLANT_DB_PATH`, `TRUSTHUB_DATASET_ROOT`,
`TRUSTHUB_PLANT_LLM_MODE` (`off`|`local`|`external`),
`TRUSTHUB_PLANT_ALLOW_EXTERNAL_LLM`.

> **`TRUSTHUB_DATASET_ROOT`, bukan `TRUSTHUB_PLANT_DATASET_ROOT`.** Test yang
> salah nama ini pernah lulus karena alasan yang salah — sudah dikoreksi di
> `0c55758`.

---

## 8. Known Gaps & Risiko

### Yang sudah ditangani (bug produksi, ditemukan lewat test)

| Bug | Gejala | Status |
|---|---|---|
| `_looks_like_dataset` ambang 0 | 1 tag memberi `1//2 == 0`, jadi setiap folder yang ada dianggap dataset, dan `find_dataset_root` mengambil yang terurut lebih dulu | fixed: `max(1, ...)` |
| `classify()` cek `"pid"` | 7 dari 8 file `P&ID_*.png` salah klas jadi `unknown` karena ampersand memutus substring. Tidak terlihat karena `extract_file` men-short-circuit image sebelum `classify` dipanggil | fixed |
| phantom instrument `ZSO-9999` | instrument tak dikenal dijawab, bukan ditolak | fixed |
| `known_instrument_tags` tak pernah diisi | guardrail instrument mati | fixed |
| `mentions_known_entity` | pertanyaan dokumen ada tapi entitas tak dikenal lolos | fixed |
| `/status` hardcode `ready: True` | UI menampilkan "siap" padahal indeks kosong | fixed |
| 3 test butuh dataset yang bukan miliknya | CI merah sejak penggantian frontend | fixed |
| permintaan ubah limit keselamatan dapat badge tertinggi | *"raise the trip setpoint above 12 mm/s"* → TRUSTED 0.81, jadi badge tertinggi menempel pada permintaan memindahkan proteksi | fixed: cap `DO NOT EXECUTE` di `trust.evaluate()` |
| 12 kasus evaluation expect badge `"VERIFICATION"` | `BADGE_RANK.get(nama, 0)` → 0, jadi `rank(apa pun) >= 0` selalu benar. 12 dari 63 kasus punya ekspektasi yang **tidak bisa gagal** | fixed: ejaan → `VERIFY`; `load_set` sekarang menolak nama badge yang salah |
| `notes` evaluation set bertentangan dengan code | note bilang badge lebih hati-hati tidak pernah gagal; code tegakkan sebaliknya | fixed: code yang benar, note ditulis ulang |

### Yang masih jadi gap / risiko

| Gap | Dampak | Rencana |
|---|---|---|
| 8 Interlock Diagram tanpa status approval | trust score turun padahal safety-critical | badge `VERIFY` + alasan "approval not stated"; **jangan** tebak |
| OPL-GA-1201A-04 tidak ada di dataset | 2 dari 63 kasus evaluated | justru dipakai sebagai demo "sistem menolak dengan jujur" |
| 13 dari 36 kasus jawaban hanya cek "tidak ditolak" | bukti lebih tipis dari 23 kasus lain | **dipin** di `test_evaluation.py` (daftar id-nya); sengaja tidak diubah karena menggeser angka terkunci |
| `verified_groups: 7` (bukan 15) | klaim lama salah | deck harus mengutip **7**; 7 group di 7–8 dokumen |
| holdout 2 dari 102 gagal (*confined space entry*, *prime a pump*) | 2 pertanyaan yang memang tentang plant tapi tanpa nama unit, jadi domain gate menolak | **sengaja dibiarkan gagal**. Kalau dipindah ke expected-refusal, angka jadi 100% dan batas domain gate hilang dari catatan |
| 102 holdout ditulis oleh orang yang sama dengan sistemnya | bukan bukti independen | diakui di README & TRUSTHUB §9, bukan disembunyikan |
| Nilai interlock = DUMMY training values | safety limit di P&ID bukan nilai operasi nyata | sebut apa adanya di deck, jangan dipakai sebagai safety argument |
| Kriteria & bobot penilaian resmi belum diketahui | strategi deck bisa meleset | email `caliber.2026@capcx.com` sudah dikirim |
| Dataset boleh dikirim ke LLM eksternal? belum confirmed | menentukan mode LLM | default `off`; `external` butuh `TRUSTHUB_PLANT_ALLOW_EXTERNAL_LLM=1` |
| Dataset berlisensi panitia | tidak boleh di-commit | tetap di Downloads + `fetch_dataset.py` |

### Masih ditunggu dari panitia
Bobot & kriteria penilaian · boleh kirim dataset ke LLM eksternal? · batas
jumlah slide & durasi video · nama dosen pembimbing.

---

## 9. Checklist pra-submit
- [ ] Semua 6 komponen Case Book tercakup, bagian simulasi dilabeli
- [ ] Semua 3 Key Question terjawab eksplisit
- [ ] 4 baseline data terpakai penuh (SOP/datasheet, P&ID, Maint History, tacit/OPL)
- [ ] Output AI divalidasi + dievaluasi (FAQ 8 — set uji 63 kasus, bukan opsional)
- [ ] Semua materi English
- [ ] Deck mengutip `verified_groups: 7`, bukan 15
- [ ] Tampilan 9 halaman sudah dilihat langsung di browser
- [ ] Total ≤ 10MB; video & mockup berupa link publik yang bisa diakses
- [ ] Dosen pembimbing tercantum
- [ ] Angka dampak berlabel *dataset-derived* atau *illustrative assumption*
- [ ] Review skeptis 5 poin (proposal bagian 13) sudah dijawab