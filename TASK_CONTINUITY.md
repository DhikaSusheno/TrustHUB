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

Kedua angka biaya di bawah **bukan scope yang sama**, jadi dipisah agar tidak
tercampur: kolom "Biaya breakdown" hanya menjumlahkan 31 baris `Breakdown=yes`
(total IDR 413.345.000, sama dengan `/failure-memory`), sedangkan "Biaya total
WO" menjumlahkan seluruh 211 WO (IDR 537.770.000). Kolom WO dan Downtime juga
beda scope: WO = semua pekerjaan, Downtime = breakdown saja.

| Tag | Nama | WO | Breakdown | Downtime breakdown (h) | Biaya breakdown (IDR) | Biaya total WO (IDR) |
|---|---|---|---|---|---|---|
| YD-2301 | POLYMER FLUID BED DRAYER | 28 | 5 | 68,5 | 81.049.000 | 94.728.000 |
| KC-4501 | RECYCLE GAS COMPRESSOR | 27 | 2 | 38,0 | 37.673.000 | 50.603.000 |
| CT-7801 | COOLING TOWER CELL FAN | 27 | 3 | 46,0 | 41.874.000 | 53.757.000 |
| DC-3401A | CATALYST REDUCTION REACTOR | 27 | 5 | 60,0 | 46.118.000 | 71.795.000 |
| LV-6701 | SEPARATOR LEVEL CONTROL VALVE | 26 | 4 | 21,0 | 59.257.000 | 72.233.000 |
| GA-1201A | HEXANE FEED PUMP | 26 | 1 | 6,5 | 12.630.000 | 29.794.000 |
| EA-5601 | SOLVENT HEATER | 25 | 6 | **124,0** | **104.167.000** | 123.580.000 |
| FA-8901 | REFLUX ACCUMULATOR DRUM | 25 | 5 | 70,0 | 30.577.000 | 41.280.000 |

Semua kolom dihitung ulang dari `Maintenance History (All Equipment).xlsx`, bukan
disalin dari `/failure-memory` yang hanya memuat breakdown-scope.

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

> **Angka 21 di bawah adalah probe riset, bukan angka yang dipublikasikan.**
> Matcher produksi di `failure_memory.py` memberi **19 dari 31 (61.3%)** — itu
> angka yang ada di deck, README, TRUSTHUB.md, video, dan UI. Selisihnya punya
> sebab: probe token-overlap terlalu longgar, jadi ia ikut menghitung OPL yang
> hanya berbagi kata umum dengan root cause. **21 adalah overstatement pada
> probe, bukan kelemahan pada matcher.** Kalau "21 dari 31" muncul di mana pun
> selain paragraf ini, itu catatan riset yang belum dikoreksi, bukan klaim
> produk.

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
  main.py                 29 route /api warisan Synapse + mount /api/plant
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
    holdout.py            102 pertanyaan holdout (butuh dataset, bukan CI)
    fetch_dataset.py      unduh dataset (lisensi panitia, tidak di-commit)
  tests/
    plant/                896 test, semua jalan tanpa dataset resmi
      conftest.py         synthetic_index + stub_dataset_root + api harness
      test_api.py             117
      test_retrieval.py       141
      test_trust.py           106
      test_ask.py              99
      test_dataset_contract.py  93
      test_evaluation.py        91
      test_extract.py           84
      test_registry.py          75
      test_conflicts.py         71
      test_holdout.py           19
    (seluruh backend/tests 1232 + security/tests 128 = 1360 collected;
     1329 passed / 31 skipped di CI ubuntu, 1328 passed / 32 skipped di Windows)

frontend/
  app/page.tsx            shell tipis: LeftNav + dispatch 9 halaman (?page=)
  app/landing/page.tsx    about page English, angka terukur saja
  app/backend/[...path]/  proxy Next.js; token tidak pernah sampai browser
  app/icon.svg            favicon, digambar ulang pada 32px
  components/LeftNav.tsx  9 page id baru + ThemeSwitcher + LanguageSwitcher
  components/pages/       AskPage, EquipmentPage, DocumentsPage,
                          KnowledgeGraphPage, VerificationPage, MaintenancePage,
                          OverviewPage, AuditPage, PlantSettingsPage
  components/shared/      PageShell (Panel/Stat/Tag), TrustBadge,
                          BackendStatusBanner, LogoMark (satu-satunya sumber),
                          ThemeSwitcher, LanguageSwitcher
  components/landing/     PetroProcessMotif (schematic, aria-hidden, dekoratif)
  hooks/                  usePlantResource, useBackendStatus
  lib/plantApi.ts         typed client; semua panggilan /api/plant/*
  lib/theme/ThemeProvider.tsx  data-theme di <html>, persist + no-flash
  lib/i18n/                LocaleProvider.tsx (locale dibaca setelah mount)
                          dictionary.ts (9 nama halaman + status loading/error)
  app/globals.css         SATU-SATUNYA pemilik surface + token warna RGB
  54 file Synapse lama DIHAPUS (guardian/cortex/agents/SSE/LLM/GitHub/force-graph)
```

### Yang sudah terverifikasi (bukan klaim)
Jalankan dari repo root dengan `TRUSTHUB_API_TOKEN` disetel:

- `python -m pytest backend/tests security/tests` → **1329 passed, 31 skipped**
  (CI ubuntu). Di Windows: **1328 passed, 32 skipped**. Keduanya 1360 collected;
  beda 1 test adalah yang butuh POSIX permission. Skip = butuh dataset resmi.
- `npm test` → 25 pass · `npm run typecheck` → bersih · `npm run build` → sukses
- `GET /api/plant/evaluation` → **63/63, accuracy 100.0%**, refusal 27/27,
  answer 36/36, ~0.9 s
- Holdout 102 pertanyaan (di luar evaluation set) → **98.0%**
- 20 route `/api/plant/*` dijawab 200 lewat proxy Next.js dengan data nyata
- Deck: **13 halaman = 7 main + 6 appendix**, 16.186 karakter bisa diekstrak,
  28/28 klaim gerbang hadir, 0 overflow
- CI hijau di `main`, HEAD `695b7d4`

> Angka di blok ini diukur ulang pada 2 Okt 2026 di clone bersih `695b7d4`,
> tanpa dataset resmi, memakai perintah yang sama seperti CI.

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
- 896 test di `backend/tests/plant/`, seluruhnya jalan **tanpa** dataset resmi.
- 3 modul baru: `test_extract.py` (84), `test_evaluation.py` (91),
  `test_dataset_contract.py` (93).
- Total suite: **1329 passed, 31 skipped** di CI ubuntu (1360 collected);
  1328/32 di Windows. Skip = butuh dataset resmi, +1 butuh POSIX permission.
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

### ✅ DONE — deck
> **Struktur deck berubah di `e922bfe`.** Paragraf ini ditulis ulang pada
> 2 Okt 2026. Angka "15 slide" yang ada di versi lama file ini sudah tidak
> benar dan jangan dipakai lagi.

- `docs/deck/deck.html` → **PDF 13 halaman = 7 main + 6 appendix**, English,
  316 KB (batas 10 MB). Render via headless Chrome
  (`docs/deck/build/render.mjs`), jadi teksnya vektor dan **bisa dicari** —
  panel bisa copy-paste, tidak akan puzzled. 16.186 karakter terekstrak.
- 960x540 pt, rasio persis 16:9. `@page` mengunci ukuran halaman.
- **Booklet CALIBER membatasi 7 slide termasuk cover, mengecualikan appendix.**
  Deck 15 slide melanggar itu, dan setiap main slide setelah yang ketujuh
  adalah alasan juri berhenti membaca. Semuanya sekarang 7 main slide dalam
  urutan yang diminta, dan bukti yang tadinya dipakai menggembalakan slide 8–15
  dipindah ke 6 appendix slide, tempat limit itu tidak menjangkau.
- **7 main slide:** title → problem → objective/workflow/technology →
  exposure (terukur vs asumsi) → phases → trust thesis → team profile.
- **6 appendix slide:** A1 trust engine · A2 "score is not a decision" + dua
  override rule + angka retrieval 10.68/7.56/5.44 · A3 tiga pertanyaan, tiga
  perilaku benar · A4 failure memory · A5 validasi 63 kasus · A6 ingestion &
  graph 134 node.
- Komponen 5 dinyatakan **NOT BUILT** di main slide 4 dan 6.
- `7 verified groups` sekarang muncul di **A1**, bukan main deck. Angka 15
  tidak muncul di mana pun.
- Audit layout otomatis (`audit.mjs`): 13/13 halaman, **0 overflow**.
- **Angka deck diverifikasi mesin terhadap API yang sedang jalan**
  (`docs/build/deckverify.py`): 28 klaim gerbang, plus 5 frasa terlarang yang
  harus **absen**: `15 verified groups`, `production data`, `real plant data`,
  `0.572`, `spec v1.1`. Semuanya lulus.
- PDF **tidak** di-commit. `.gitignore` punya aturan `*.pdf` sebagai pagar
  agar 87 PDF dataset berlisensi panitia tidak ikut terpush. Aturan itu tidak
  dilonggarkan demi deck: `deck.html` yang di-version-control, PDF-nya build
  output, dan harga yang dibayar adalah satu file binary tidak ikut repo.

> **Yang belum dijalankan:** `deckverify.py` membandingkan angka deck dengan
> API yang hidup, jadi ia butuh dataset resmi dan **tidak** bisa dijalankan di
> CI. Untuk deck 7-slide ia belum pernah dijalankan. Yang sudah diverifikasi
> tanpa dataset: 13 halaman, 0 overflow, 28/28 klaim gerbang hadir, dan
> 5 frasa terlarang absen.

### 🐞 DUA KLAIM DEK YANG SALAH — SUDAH DIPERBAIKI
Temuan dari build video, bukan dari review mata. Pelajaran: klaim yang tidak
bisa direproduksi harus dianggap salah sampai dibuktikan.

> Nomor slide di bawah mengikuti deck **15-slide yang lama**. Di deck 13 halaman
> sekarang, kedua klaim ini pindah: yang pertama ke **appendix A2**, yang kedua
> ke **appendix A6**. Isi dan angkanya tidak berubah, hanya tempatnya.

1. **Dulu slide 9, angka `0.572` vs `0.357` — tidak bisa direproduksi sama
   sekali.** Klaim itu bilang "How do I open a bank account?" Menguen memencet
   retrieval lebih tinggi dari pertanyaan in-scope. Tapi respons
   `/api/plant/ask` **tidak punya sinyal `relevance` sama sekali** untuk
   pertanyaan yang ditolak, karena guardrail jalan sebelum scoring.
   `trust_score` = 0.00 (ditolak) dan 0.60 (jawab). Angka 0.572/0.357 berasal
   dari keadaan kode lama.
   **Yang benar dan lebih kuat:** di lapisan retrieval, "How do I open a bank
   account?" retrieve di **10.68** — skor tertinggi dari semua yang diuji,
   di atas pertanyaan asli "What is the trip setpoint for VSHH-1201?" (7.56)
   dan hampir dua kali "Which equipment fails most often?" (5.44). Jadi
   threshold retrieval akan melepaskannya. Ia ditolak karena **topik**, di tahap
   lebih awal. Ini argumen yang lebih kuat, dan bisa direproduksi.
2. **Dulu slide 6, "134 nodes" vs layar yang menulis `47 nodes, 39 relations
   shown`.** API memang benar (134 = 8 equipment + 87 document + 8 interlock
   + 31 breakdown, 126 links). Cincin di halaman Graph sengaja hanya menggambar
   47 node non-dokumen, karena 87 node dokumen dalam satu lingkaran tidak
   terbaca. Sekarang deck menyebut keduanya dan menjelaskan bedanya, supaya
   panel yang memakai video tidak mengira ada dua graf yang berbeda.
   `deckverify.py` sudah punya assertion untuk angka 10.68 / 7.56 / 5.44, dan
   **memeriksa `0.572` tidak pernah muncul lagi**. Dicek ulang 2 Okt 2026:
   `0.572` memang **absen** dari `deck.html`.

### ✅ DONE — video demo
- `docs/demo/TrustHUB-demo.mp4`: **2 menit 26 detik**, 1280x720, H.264 yuv420p,
  4,1 MB. Requirement 2-3 menit. Tidak ada narasi; **caption yang jadi
  narasi** (panel menonton tanpa suara).
- **Dibangun, bukan direkam.** `capture.mjs` menjalankan UI asli di :3000
  terhadap dataset asli, satu frame per beat (14 beat). Jadi tidak ada spinner
  yang terpotong, dan semua frame bisa diperiksa sebelum ada yang menonton.
- Setiap beat menyimpan **teks yang benar-benar ter-render** di `beats.json`.
  `verify.py` lalu membandingkan tiap caption dengan teks frame-nya. Dua caption
  terbongkar dan ditulis ulang karena tidak cocok dengan layarnya.
- `verify.py` juga gagal kalau frame memuat `production data`, `real plant
  data`, `15 verified`, atau `spec v1.1`.
- Capture bersih: **0 console error, 0 page error, 0 failed request** di 5
  putaran penuh.
- `checkvideo.py`: `blackdetect` 0 stretch hitam, luminance 12 sampel stabil
  (29,5-38,5). Aliasing di tengah video bukan frame hitam.
- Tooling di `docs/demo/build/`, bukan di `frontend/`, dengan
  `package.json` sendiri. Alasan sama seperti deck: `npm ci` di mesin panel
  tidak perlu mengunduh browser untuk skrip yang tidak akan pernah mereka
  jalankan. Path diturunkan dari `import.meta.url`, jadi tidak ada `C:\Users\...`
  yang di-hardcode.

### ✅ DONE — 2 Okt 2026 (sesi 3): deck 7-slide, dua tema, dua bahasa
> Blok ini tidak pernah ditulis ke file ini sampai 2 Okt 2026, padahal 16
> commit sudah landed setelah `005c78b`. Itu sebabnya bagian 4, 5, dan 8 punya
> angka basi sampai sekarang. Rekap di sini, semua sudah terverifikasi.

**Deck: 15 slide → 7 main + 6 appendix** (`e922bfe`)
- Booklet CALIBER membatasi **7 slide termasuk cover, appendix dikecualikan**.
  Deck lama 15 slide, jadi setiap main slide setelah ketujuh adalah alasan juri
  berhenti membaca.
- Tidak ada yang dibuang: bobot & ambang trust, teks guardrail, pembacaan
  interlock hidup, angka failure memory, hitungan validasi, dan hitungan graph
  semuanya masih ada di PDF, hanya di appendix.
- `audit_deliverables.py` menegakkan angka yang salah **dua arah**: ia
  membatasi halaman di 15 (deck 7-slide yang patuh lolos gratis), dan ia
  menyematkan cek placeholder ke slide 1 dan 15 — jadi ia melaporkan "terisi"
  di slide yang sudah tidak ada, bukan melaporkan apa pun. Sekarang ia memisah
  appendix lewat marker footer, mengecek 7 main slide terhadap limit, dan
  melaporkan **setiap** placeholder yang tersisa per slide.
- `render.mjs` juga tidak pernah menghapus screenshot, jadi deck 13-slide
  duduk di samping `slide-14.png` dan `slide-15.png` dari versi 15-slide.

**Build deck jadi portabel** (`34edc77`)
- `render.mjs` dan `audit.mjs` mencari root repo lewat path absolut di home
  user lain, jadi build gagal di mana saja selain mesin itu. Sekarang dari
  `import.meta.url`, dan Chrome dicari lewat `CHROME_PATH` + lokasi install
  biasa.
- `deckverify.py` dulu hanya mengecek API hidup dan PDF ada, **tidak pernah
  membandingkan satu angka pun** dengan API. Dengan count di-stub 94 terhadap
  95 yang tercatat, ia tetap lulus. Sekarang ia menurunkan angka yang
  diceknya dari respons, dan melaporkan STALE dengan exit non-zero. Index yang
  belum dibangun dulu memunculkan traceback 503; sekarang ia menjelaskan apa
  yang harus dijalankan.

**Provenance: bug produksi ke-8** (`ee2f142`)
- `/status` meng-hardcode "All documents come from the official CALIBER-provided
  dataset". String itu dirender di halaman overview dan dataset, jadi indeks
  yang dibangun dari apa pun_else mempresentasikan diri sebagai dataset resmi.
- Provenance sekarang dibaca dari tabel `data_provenance`, yang ditulis saat
  indeks dibangun di luar pipeline resmi. Tabel tidak ada = `fetch_dataset`
  yang membangunnya, dan itu satu-satunya jalur yang memakai dataset berlisensi.

**Cakupan test hilang diam-diam: bug ke-9** (`ef0574f`)
- `backend/tests/test_model_discovery.py` menandai 3 test `@pytest.mark.asyncio`,
  tapi `pytest-asyncio` hanya pernah dideklarasikan di
  `security/requirements-test.txt`. Install `backend/requirements.txt` saja —
  yang dibaca developer backend lebih dulu — memberi 3 kegagalan
  *"async def functions are not natively supported"*.
- Bentuknya sama dengan regresi path-traversal yang dulu tertangkap CI: run
  hijau yang diam-diam mengumpulkan lebih sedikit dari seharusnya. Diperbaiki
  dengan mencerminkan pemisahan `security/requirements-test.txt`, di-pin ke
  versi yang sama supaya dua suite tidak bisa melenceng.
- Terverifikasi di Windows, dataset tidak ada, invocation sama seperti CI:
  **3 failed / 1325 passed** sebelum → **1328 passed / 32 skipped** sesudah.
  1360 collected dua-duanya.

**Dua tema + sistem token** (`54bf41b`, `48e7790`, `94ab556`, `575308c`)
- App tadinya dark-only dan bilang begitu di ~400 tempat: 31 hex surface
  hardcoded, 55 `border-slate-800/60`, dan `tailwind.config.cjs` dengan
  `extend` kosong. Menambah toggle di atas itu akan menumpuk palet kedua di atas
  palet pertama, jadi **paletnya yang di-tokenisasi lebih dulu**.
- Satu atribut: `data-theme` di `<html>`, setiap warna lewat CSS variable.
  Tidak ada varian `dark:` dan tidak ada komponen yang perlu tahu tema mana
  yang aktif. Skala slate di-remap, bukan diperpanjang, karena `text-slate-400`
  muncul 62 kali dan artinya "teks sekunder"; mengganti 62 call site adalah
  kerja yang sama dengan diff yang lebih buruk. Semua nilainya triplet RGB
  karena `tailwind.config.cjs` mengonsumsinya sebagai
  `rgb(var(--x) / <alpha-value>)` — satu-satunya bentuk yang menjaga modifier
  alpha di call site.
- Dark dideklarasikan di `:root` jadi default, byte per byte seperti yang
  pernah dikirim, jadi tidak ada yang bergeser bagi yang tidak pernah membuka
  switcher.
- Kontras **diukur, bukan ditebak**. Terakhir di `575308c`, enam langkah ink di
  light terhadap panel: **16.59, 14.11, 10.44, 7.83, 5.96, 4.83** — semua lolos
  AA. Palet dark tidak disentuh.
- `48e7790`: script bootstrap menulis `data-theme` sebelum React hydrate, tapi
  server tidak pernah merender atribut itu, jadi React melaporkan mismatch di
  setiap halaman. `suppressHydrationWarning` di `<html>` — di elemen itu saja,
  karena hanya suppressing atribut & teks elemen tempatnya duduk.
- `94ab556`: light theme semula `#f9fafb` — putih dalam nama saja. Semua
  surface light sekarang grey step. Panel digreykan memakan kontras, jadi
  aksen diturunkan juga: green `#15803d` (4.35) dan amber `#b45309` (4.36)
  Against near-white, keduanya di bawah AA.
- **Bug tambahan di `54bf41b`:** menamai sebuah warna `"hover"` bentrok dengan
  variant `hover:`, jadi `hover:bg-hover` **tidak pernah ter-emit**. Hover state
  di suggestion chip Ask mati diam-diem. Diganti `surface-hover`, dan audit 23
  variant di source terhadap CSS yang.disajikan sekarang tidak menemukan yang
  hilang.

**Dua bahasa, English beku** (`66b5dc7`)
- Sembilan nama halaman, status index di sidebar, judul halaman, dan state
  loading/error jadi dictionary key. Select di sidebar ganti locale, pilihan
  bertahan setelah reload.
- **English adalah default dan dibekukan**: `verify.py` dan `deckverify.py`
  assert string English tertentu terhadap frame video dan PDF submission, dan
  **videonya tidak bisa direkam ulang tanpa dataset berlisensi**. Hanya chrome
  yang diterjemahkan. Badge, alasan penolakan, jawaban, judul dokumen, dan
  catatan lisensi dataset adalah nilai yang dikembalikan backend dalam
  English, dan jawaban setengah terjemahan lebih buruk daripada English
  karena pembaca tidak bisa tahu bagian mana yang otoritatif.
- Locale dibaca setelah mount, bukan saat render, supaya server dan client
  setuju di frame pertama.

**Surface + satu logo** (`1c1df4b`, `fb259ad`)
- Latar `#080d14` polos FIELD membanding di monitor 27 inci dan terbaca
  seperti lubang. Sekarang ada grain halus dan vignette tepi. Batasannya:
  tidak boleh menaikkan luminance rata-rata — jarak background ke panel cuma 5
  level merah, 4 hijau, 3 biru, jadi highlight yang cukup terlihat harus
  mendorong background melewati panel dan setiap panel berhenti terbaca
  sebagai terangkat. Grain tidak punya mean; vignette hanya gelapkan. Itu
  sebabnya background dapat tekstur, bukan glow.
- Logo punya tiga gambar berbeda: `LogoMark` di-copy-paste ke `LeftNav` lalu
  lagi ke header landing, dan `app/icon.svg` melenceng jadi perisai hijau —
  jadi tab menampilkan mark berbeda dari nav, dan yang ketiga itu berwarna
  seperti verdict TRUSTED. **Sebuah icon tidak boleh memutus apa pun.** Ketiganya
  sekarang dari `components/shared/LogoMark.tsx`, favicon digambar ulang di 32
  supaya bisa membawa stroke lebih tebal dan tetap terbaca di 16px.
- Landing punya schematic process train (feed pump, heat exchanger, reactor,
  stream keluar) bertag P-001/T-101/R-201/E-301. Dekoratif, `aria-hidden`.
  **Tanpa nama perusahaan dan tanpa logo**, karena ringkasan distribusi yang
  menyertai dataset resmi memperlakukan nama dan logo itu sebagai merek
  dagang.
- Empat angka landing kini dilabeli sebagai dataset resmi, dan halaman
  menyatakan selisihnya secara terbuka: pengunjung yang menjalankan ini lokal
  terhadap test fixture melihat 10 dokumen dan 3 unit. Selisih antara dua set
  angka itu sebelumnya tidak terlihat di mana pun, dan membiarkan juri
  mencarinya sendiri adalah kesalahan yang avoidable.

**Mojibake + BOM** (`94ab556`)
- 64 rangkaian di 9 file adalah byte UTF-8 yang dibaca sebagai Windows-1252 lalu
  ditulis balik — seperti em dash jadi tiga karakter. Dipulihkan dengan
  **mendekode byte run**, bukan pattern-match daftar yang sudah dikenal, itu
  sebabnya panah dan box drawing ikut kembali bersama dash.
- Dua di antaranya terlihat di layar: chevron DocumentsPage sebagai sampah 3
  karakter, bullet dan middle dot di EquipmentPage/MaintenancePage, serta dash
  rusak di aria-label logo LeftNav.
- Scan yang menemukannya juga sebabnya ia bertahan: pass sebelumnya hanya
  melihat `css`, `ts`, `tsx`, jadi BOM di `tailwind.config.cjs` dan di file
  invariants backend tidak pernah masuk scope. **Sembilan file** punya BOM dan
  kesembilannya sekarang bersih; scan cakup `cjs`, `yaml`, `md` juga.
- Satu string CJK sengaja tersisa: token Jepang di
  `test_auth_and_input_bounds.py` adalah fixture untuk header non-ASCII yang
  sampai ke uvicorn utuh. Itu assertion-nya, bukan kerusakan.

**Tiga MASTER_PROMPT.md di-resync** (`4a82345`, `01ef940`, PR #4)
- Ketiga brief (`backend/`, `frontend/`, `security/`) ditulis ulang dan
  di-ground ke `TRUSTHUB.md` yang sebenarnya, bukan ke deskripsi yang
  di Warisan Synapse.

### 🔜 NEXT (urutan ini)
> Diperbarui 2 Okt 2026. Item 1 dan 2 tidak bisa dikerjakan tanpa akun, dan
> item 3 tidak bisa tanpa jawaban panitia.

1. **Upload video ke YouTube** dan dapat link publiknya. MP4-nya sudah jadi di
   `docs/demo/TrustHUB-demo.mp4` (2:26, 4,1 MB, sudah di-commit).
2. **Link mockup publik.** Masih satu-satunya deliverable yang belum ada sama
   sekali. **Sudah diputuskan 2 Okt: dataset boleh ditaruh di host** (volume /
   upload, **tidak pernah** di-commit ke git). Yang belum ada di repo: **nol**
   konfigurasi deploy — tidak ada Dockerfile, fly.toml, railway.json,
   render.yaml, atau Procfile. Sisi repo yang perlu dikerjakan: image
   (Next standalone + uvicorn), `.dockerignore`, healthcheck, ingest dataset
   saat start kalau `TRUSTHUB_DATASET_ROOT` terisi, lalu isi link-nya ke slide 7.
3. **Placeholder yang masih terbuka di main deck** — `audit_deliverables.py`
   akan melaporkan semuanya sebagai `PLACEHOLDER PRESENT`:
   - supervisor ("to be confirmed by the committee") — **slide 1 dan slide 7**
   - nama tim ("team name to be confirmed") — **slide 1**
   - anggota 2 dan 3: nama, jurusan, semester, keahlian, kontribusi — **slide 7**
   - semester Dhika Susheno — **slide 7**
   - "Link to be added on submission" (video + mockup) — **slide 7**

   Yang bisa ditutup tanpa committee: nama tim, anggota 2 & 3, semester. Yang
   benar-benar **menunggu jawaban panitia**: nama dosen pembimbing. Jangan kirim
   dengan placeholder kalau sudah tahu.
4. Setelah link masuk, edit **slide 7** (bukan slide 15 lagi), render ulang PDF,
   lalu jalankan `docs/build/audit_deliverables.py`.
5. **`deckverify.py` belum pernah dijalankan untuk deck 7-slide.** Ia
   membandingkan angka deck dengan API hidup, jadi butuh dataset resmi dan tidak
   bisa jalan di CI. Jalankan sekali secara lokal sebelum submit, kalau sempat.

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

Semua **nilai** (badge, alasan penolakan, jawaban, judul dokumen, catatan lisensi
dataset) dikembalikan backend dalam English dan **harus tetap English** — jawaban
setengah terjemahan lebih buruk karena pembaca tidak tahu bagian mana yang
otoritatif, dan `verify.py` / `deckverify.py` meng-assert string English
tersebut terhadap frame video dan PDF submission yang tidak bisa direkam ulang.
Yang diterjemahkan hanya **chrome**: 9 nama halaman, status index, judul
halaman, state loading/error — lewat `lib/i18n/dictionary.ts`. Default English.

`app/page.tsx` tinggal shell + dispatch; graph pakai layout cincin SVG statis
supaya panel melihat gambar yang sama tiap kali. Tidak ada route `/overview` di
backend — halaman itu menyusun dari beberapa endpoint, bukan menambah route baru.

**Dua switcher di footer nav, keduanya `<select>` native** dengan alasan yang
sama: browser memegang perilaku keyboard dan screen reader.
- `ThemeSwitcher` → dark / light, di `data-theme` `<html>`, persist + no-flash
  lewat script bootstrap di root layout.
- `LanguageSwitcher` → English / Indonesian, persist, locale dibaca setelah mount
  supaya server dan client agree di frame pertama.

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
| `/status` hardcode provenance CALIBER | string "All documents come from the official CALIBER-provided dataset" dirender di halaman overview + dataset, jadi indeks yang dibangun dari apa pun_else mempresentasikan diri sebagai dataset resmi | fixed: tabel `data_provenance`; tabel tidak ada = hanya `fetch_dataset` yang membangunnya (`ee2f142`) |
| `pytest-asyncio` tidak dideklarasikan di `backend/requirements-test.txt` | 3 test `@pytest.mark.asyncio` **gagal** kalau hanya `requirements.txt` yang diinstall; di CI tersembunyi di balik `security/requirements-test.txt`. Run hijau yang diam-diam mengumpulkan lebih sedikit dari seharusnya | fixed: dicerminkan, di-pin versi sama dengan suite security (`ef0574f`) |
| `hover:bg-hover` tidak pernah ter-emit | menamai warna `"hover"` bentrok dengan variant `hover:`; hover state di suggestion chip Ask **mati diam-diem** | fixed: `surface-hover`; audit 23 variant terhadap CSS.disajikan bersih (`54bf41b`) |
| hydration error di setiap halaman | script bootstrap tulis `data-theme` sebelum React hydrate, tapi server tidak pernah merender atribut itu | fixed: `suppressHydrationWarning` di `<html>` saja (`48e7790`) |
| 64 rangkaian mojibake + 9 BOM | byte UTF-8 dibaca sebagai Windows-1252 lalu ditulis balik; chevron DocumentsPage, bullet EquipmentPage/MaintenancePage, dan aria-label LeftNav tampil sebagai sampah di layar | fixed: dipulihkan dengan mendekode byte run; scan sekarang cakup `cjs`, `yaml`, `md` (`94ab556`) |
| `audit_deliverables.py` menegakkan limit yang salah | membatasi halaman di 15 (deck 7-slide lolos gratis) dan menyematkan cek placeholder ke slide yang sudah tidak ada, jadi melaporkan "terisi" | fixed: appendix dipisah via marker footer, 7 main slide dicek, placeholder dilaporkan per slide (`e922bfe`) |
| `deckverify.py` tidak pernah membandingkan angka | hanya mengecek API hidup + PDF ada; dengan count di-stub 94 terhadap 95 ia tetap lulus | fixed: angka diturunkan dari respons; lapis STALE dengan exit non-zero (`34edc77`) |
| `render.mjs`/`audit.mjs` hardcode home user lain | build gagal di setiap mesin selain mesin aslinya; screenshot lama tidak pernah dihapus | fixed: root dari `import.meta.url`, Chrome via `CHROME_PATH` (`34edc77`, `e922bfe`) |

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
| **Nol konfigurasi deploy di repo** | satu-satunya deliverable yang belum ada sama sekali: link mockup publik | sudah diputuskan 2 Okt bahwa dataset boleh ditaruh di host (volume/upload, bukan git). Sisi repo: Dockerfile (Next standalone + uvicorn), `.dockerignore`, healthcheck, ingest saat start, lalu isi link ke slide 7 |
| **Light theme belum pernah dilihat mata** | kontras **terukur** (6 langkah ink: 16.59 / 14.11 / 10.44 / 7.83 / 5.96 / 4.83, semua lolos AA) dan sudah diperiksa di CSS yang disajikan, tapi **tidak ada yang pernah membuka halaman light theme** | author menyebutnya sendiri sebagai "the one check left" di `54bf41b` dan `575308c`. Buka app, klik switcher Light, lalu lihat. 10 menit |
| **`frontend/DESIGN_SYSTEM.md` masih dokumentasi Synapse** | ~28 KB yang membaca `GuardianPanel`, `CortexPage`, halaman Agents, dan endpoint `/graph/nodes`, `/repo_health`, `/cortex/*` — **tidak ada satu pun yang ada di TrustHUB**. Reviewer yang membukanya melihat produk yang berbeda | bagian token/surface sudah benar dan sengaja ditambahkan `1c1df4b`; sisanya stale. Tulis ulang ke 9 halaman CALIBER + 2 tema, atau hapus dan taruh isinya di `MASTER_PROMPT.md` |
| `deckverify.py` belum pernah jalan untuk deck 7-slide | ia membandingkan angka deck dengan API hidup → butuh dataset resmi, tidak bisa jalan di CI | sudah terverifikasi tanpa dataset: 13 halaman, 0 overflow, 28/28 klaim gerbang, 5 frasa terlarang absen. Jalankan sekali lokal sebelum submit kalau sempat |
| Placeholder masih terbuka di main deck | supervisor, nama tim, anggota 2 & 3, semester, link video + mockup — semuanya di slide 1 dan 7 | lihat daftar persis di §5 NEXT. `audit_deliverables.py` akan melaporkan semuanya sebagai `PLACEHOLDER PRESENT` |

### Masih ditunggu dari panitia
Bobot & kriteria penilaian · boleh kirim dataset ke LLM eksternal? · batas
jumlah slide & durasi video · nama dosen pembimbing.

---

## 9. Checklist pra-submit
- [x] Semua 6 komponen Case Book tercakup, komponen 5 dinyatakan NOT BUILT
- [x] Semua 3 Key Question terjawab eksplisit
- [x] 4 baseline data terpakai penuh (SOP/datasheet, P&ID, Maint History, tacit/OPL)
- [x] Output AI divalidasi + dievaluasi (FAQ 8 — set uji 63 kasus, bukan opsional)
- [x] Semua materi submission English (chrome UI punya mode Indonesian, opsional)
- [x] Deck mengutip `verified_groups: 7`, bukan 15
- [x] Deck 7 main slide + appendix, sesuai limit booklet
- [x] 9 halaman sudah dilihat langsung di browser (headless Chrome, 9/9 bersih)
- [ ] **Light theme dilihat langsung** — satu-satunya halaman UI yang belum pernah
      dibuka mata; kontrasnya terukur tapi penampilannya belum
- [ ] **Tidak ada `PLACEHOLDER PRESENT` di 7 main slide** — jalankan
      `python docs/build/audit_deliverables.py` dan pastikan baris itu kosong
- [ ] Total ≤ 10MB; video & mockup berupa link publik yang bisa diakses
- [ ] Video ter-upload (link di slide 7)
- [ ] Mockup ter-deploy (link di slide 7)
- [ ] Dosen pembimbing tercantum
- [ ] Anggota tim 2 & 3 + semester tercantum
- [x] Angka dampak berlabel *dataset-derived* atau *illustrative assumption*
- [x] Review skeptis 5 poin (proposal bagian 13) sudah dijawab
