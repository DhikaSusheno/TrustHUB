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
| Frasaapproval terpotong baris | `"Rev 3 - ISSUED FOR\nOPERATION"` tidak terdeteksi | `_flat()` ratakan whitespace dulu |
| Label & nilai terpisah baris | `"DWG No.\nTJC-LLD-GA-GA-1201A"` regex `[:\t]` gagal | izinkan `\s*` sebagai pemisah |
| Tabel revision history bukan tab | kolom dipisah **spasi** | regex baris, bukan `split("\t")` |
| Regex over-greedy | deskripsi jadi `"ISSUED FOR CONSTRUCTION RS"` (menelan kolom by) | jangan pakai `(?:\s+[A-Z]+)?` opsional |
| Tanda tangan OPL di luar tabel | 6 dari 55 OPL: pdfplumber hanya dapat baris header | fallback: ambil 2 nama `(...EMP-\d+)` berurutan setelah `Date of Sharing` |
| Sel tabel terpotong di sumber | `"seal dr"` `"v"` di OPL troubleshooting | **batas file asli**, bukan bug parser — jangan diklaim sebagai teks lengkap |
| `FontBBox` warning dari pdfminer | muncul saat pdfplumber jalan | noise, aman diabaikan |
| `Downtime_Hours`/`Cost` tersimpan sebagai string | `float()` langsung gagal | wajibkoersi + guard `isinstance` |

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
  main.py                 2983 baris, 57 route. RAG lama (butuh API key) di 2812-2973
  auth.py                 X-TrustHub-Token, CORS, Fernet
  storage.py / database.py  SQLite trusthub_v2.db / trusthub.db
  engine.py, cortex.py    ⚠️ domain KODE (tree-sitter) - belum diganti
  guardian.py             propose/execute/rollback/approval (BAHKAN untuk human oversight)
  settings.py, projects.py, github_sync.py, demo_*.py
  trusthub.invariants.yaml
  plant/                  ⬅️ BARU, sedang dikerjakan
    __init__.py
    extract.py            ✅ SELESAI & teruji ke 95/95 file, 0 error
    dataset.py            ⬜(next)
    registry.py           ⬜
    retrieval.py          ⬜
    trust.py              ⬜
    conflicts.py          ⬜
    failure_memory.py     ⬜
    ask.py                ⬜
  tests/                  469 pytest suite (yang masih hijau)

frontend/
  app/page.tsx            shell 3 kolom + router client-side (?page=)
  components/LeftNav.tsx  ⚠️ 9 halaman domain KODE - belum diganti
  components/pages/       CodeGraphPage, GuardianPage, CortexPage, AgentsPage,
                          SecurityPage, SettingsPage  ⚠️
  components/TrustHubGraph.tsx  force-graph (bisa dipakai untuk equipment graph)
```

### `extract.py` — yang sudah jadi & terverifikasi
`DocMeta` (22 field) + `ExtractedDoc` (text, sections, tables).
`split_sections()` memecah OPL jadi `purpose / safety / tools / procedure /
troubleshooting / learning` — dipakai untuk sitasi menunjuk bagian.
`_kv_from_tables()` membaca baris tanda tangan OPL.
Terverifikasi: **95 file, 0 error, 87/87 equipment_tag, 79/87 approved.**

---

## 5. Progress Log

### ✅ DONE — 2 Okt 2026
- **Clone & rebrand penuh.** `git archive` Synapse → folder TrustHUB (139 file
  ter-track, tanpa venv/db/.env). 80 file di-rebrand (3 pass:
  `SYNAPSE→TRUSTHUB`, `Synapse→TrustHub`, `synapse→trusthub`).
  6 file di-rename: `SYNAPSE.md→TRUSTHUB.md`, `synapse-build-flow.html`,
  `backend/synapse.invariants.yaml`, `SynapseGraph.tsx→TrustHubGraph.tsx`,
  `GITHUB_LLM_INTEGRATION_*.md → LLM_RAG_*.md`.
- **Nol kemunculan "synapse" tersisa** (dicek ulang dengan grep).
- **469 pytest passed, 2 skipped** → rebrand terbukti non-breaking.
- **Push ke `main`** (commit `1e3fa11`), branch `feat/caliber-case1` dibuat.
- **`.gitignore`** diketat: dataset CALIBER tidak ikut repo.
- **Audit dataset** → seluruh bagian 2 di atas.
- **`backend/plant/extract.py`** selesai & teruji ke 95/95 file.

### 🔜 NEXT (urutan ini)
1. `plant/dataset.py` — lokasi + validasi dataset, stats dataset-derived
2. `plant/registry.py` — SQLite schema: `equipment`, `documents`, `doc_chunks`,
   `equipment_documents`, `failure_events`, FTS5 virtual table
3. `plant/retrieval.py` — FTS5 + filter tag + rerank (tanpa API)
4. `plant/trust.py` — 5 sinyal, badge TRUSTED/VERIFY/DO NOT EXECUTE,
   guardrail safety-critical verbatim
5. `plant/failure_memory.py` — 31 breakdown ↔ 55 OPL
6. `plant/conflicts.py` — nilai berbeda untuk parameter sama
7. Route FastAPI `/api/plant/*` di `main.py`
8. Test suite baru untuk `plant/` (wajib, CI sudah menolak susut)
9. **Frontend: ganti 5 halaman + tambah 3 baru** (lihat bagian 6)
10. **Evaluation set 20-30 pertanyaan** + angka akurasi (wajib, FAQ 8)
11. Tulis ulang `README.md`, `TRUSTHUB.md`, `HANDOFF.md`

---

## 6. Peta UI/UX target (belum dikerjakan)

| Halaman sekarang | Jadi | Isi |
|---|---|---|
| `code-graph` | `knowledge-graph` | graph equipment↔dokumen↔interlock↔work order |
| `cortex` | `ask` | Q&A + **trust badge** + evidence panel + sitasi |
| `agents`, `operations` | **hapus** | tidak relevan Case 1 |
| `guardian` | `oversight` | approve/reject + audit log (human oversight) |
| `security` | `sources` | 96 dokumen, status approval, provenance |
| `settings` | `settings` | tetap (LLM provider) |
| — | `equipment` | 8 unit + halaman per tag |
| — | `failure-memory` | breakdown ↔ OPL + tindakan sebelumnya |
| — | `evaluation` | angka akurasi dari test set |

Semua copy masih Bahasa Indonesia dan menyebut "codebase"/"repository" —
**wajib ditulis ulang ke English** (syarat submission).

---

## 7. Command

```powershell
# test (WAJIB hijau sebelum commit)
$env:TRUSTHUB_API_TOKEN="ci-test-token-abcdefghijklmnop"
& "C:\Users\dhika\Synapse\venv\Scripts\python.exe" -m pytest -q

# backend
cd C:\Users\dhika\TrustHUB\backend
uvicorn main:app --reload --port 8000

# cek extractor cepat (tidak perlu server)
python -c "import sys;sys.path.insert(0,'.');from plant import extract;print(len(extract.iter_dataset_files(r'<DATASET_ROOT>')))"
```

Env var (semua sudah di-rebrand): `TRUSTHUB_API_TOKEN`, `TRUSTHUB_DB_PATH`,
`TRUSTHUB_ALLOWED_ORIGINS`, `TRUSTHUB_SETTINGS_PATH`, `TRUSTHUB_PUBLIC_PATHS`,
`TRUSTHUB_ALLOW_TARGET_ROOTS`. Header token: `X-TrustHub-Token`.

---

## 8. Known Gaps & Risiko

| Gap | Dampak | Rencana |
|---|---|---|
| 8 Interlock Diagram tanpa status approval | trust score-nya turun, padahal itu safety-critical | tampilkan badge `VERIFY` + alasan "approval not stated"; **jangan** tebak |
| OPL-GA-1201A-04 tidak ada di dataset | pertanyaan tentang itu tidak bisa dijawab | jadikan demo skenario "sistem menolak dengan jujur" |
| Sel tabel OPL terpotong di file sumber | jawaban troubleshooting terpotong | tampilkan apa adanya + tandai `truncated in source` |
| 6 OPL tanpa `Date of Sharing` terbaca | sinyal "revision currency" tidak tersedia | `null`, bukan default ke tanggal hari ini |
| Kriteria & bobot penilaian resmi belum diketahui | strategi deck bisa meleset | cek ke panitia: caliber.2026@capcx.com |
| **Boleh kirim dataset ke LLM API eksternal?** belum confirmed | menentukan apakah butuh model lokal | **tanya panitia**; retrieval sudah lokal (FTS5) jadi aman |
| Dataset berlisensi panitia | tidak boleh di-commit | tetap di Downloads + `fetch_dataset.py` |

### Pertanyaan yang harus ditanyakan ke panitia
1. Bobot & kriteria penilaian resmi?
2. Dataset boleh dikirim ke LLM API eksternal? (kalau tidak → model lokal/on-prem)
3. Batas jumlah slide & durasi video?
4. Nama dosen pembimbing yang harus tercantum?

---

## 9. Checklist pra-submit
- [ ] Semua 6 komponen Case Book tercakup, bagian simulasi dilabeli
- [ ] Semua 3 Key Question terjawab eksplisit
- [ ] 4 baseline data terpakai penuh (SOP/datasheet, P&ID, Maint History, tacit/OPL)
- [ ] Output AI divalidasi + dievaluasi (FAQ 8 — set uji bukan opsional)
- [ ] Semua materi English
- [ ] Total ≤ 10MB; video & mockup berupa link publik yang bisa diakses
- [ ] Dosen pembimbing tercantum
- [ ] Angka dampak berlabel *dataset-derived* atau *illustrative assumption*
- [ ] Review skeptis 5 poin (proposal bagian 13) sudah dijawab