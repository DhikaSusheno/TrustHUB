# Security & QC PRD — Rule Engine + Demo Reliability

Scope untuk: [@pidpid35](https://github.com/pidpid35) (QC-1 · Rule engine), [@zuyss](https://github.com/zuyss) (QC-2 · Demo/Integrasi).
Konteks penuh: [`../TRUSTHUB.md`](../TRUSTHUB.md) section 2.

> **Catatan penomoran.** PRD ini ditulis saat `TRUSTHUB.md` masih punya
> sub-section bernomor (2.2, 2.5, 2.7, 3.1, 3.2, 4.4, 4.5). Case Book sekarang
> hanya bernomor 1–9 tanpa sub-section, jadi semua rujukan "section X.Y" di
> bawah sudah diarahkan ke section yang benar-benar ada. Tabel di kolom
> "Target" menuliskan nama section, bukan lagi hanya nomornya.

## Goal (dari TRUSTHUB.md §6 Security, reliability, oversight, dan §4 AI output is validated and evaluated)

- 100% operasi tak dikenal (tidak match rule apa pun) **wajib** minta approval manusia — nol pengecualian (fail-closed), dibuktikan lewat skenario tes eksplisit.
- Waktu dari "operasi berisiko diminta" sampai "rollback selesai" saat skenario gagal disuntikkan: **< 10 detik**.
- Graph terbentuk dari repo sample dalam **< 30 detik** saat live ingest.

## Deliverable wajib

| # | Deliverable | Owner | Target rule/kode di TRUSTHUB.md |
|---|---|---|---|
| 1 | Daftar skenario uji (termasuk operasi tak dikenal) | QC-1 | §4 AI output is validated and evaluated |
| 2 | Test case untuk rule table & blast radius (unknown tool → `require_approval: true`) | QC-1 | §4 AI output is validated and evaluated |
| 3 | Adversarial test: coba bobol jalur approval | QC-1 | §4 AI output is validated and evaluated |
| 4 | Pastikan default fail-closed konsisten di semua jalur | QC-1 | §6 Security, reliability, oversight (human oversight) |
| 5 | Repo demo + seed data + skenario migrasi yang sengaja rusak | QC-2 | §9 Where each claim can be checked |
| 6 | Tes integrasi end-to-end backend↔frontend↔Bob | QC-2 | — |
| 7 | Uji ulang skenario rusak→rollback sampai reliable, rekam video fallback | QC-2 | §9 Where each claim can be checked |
| 8 | Sahkan rollback benar-benar memulihkan state (bukan cuma "sukses teknis") | QC-1 | §7 What is missing |

## Non-Goals

- Bukan tim yang menulis fitur baru — tugas kalian adalah menemukan yang rusak dan memverifikasi yang benar.
- Tidak menyimpan credential/secret asli di repo demo — pakai `.gitignore` di root.

## Definition of done per fase

- **Jam 2**: daftar skenario uji + repo demo/seed data disusun.
- **Jam 16**: mulai tulis test case rule engine begitu API pertama dari backend ada.
- **Jam 30**: semua temuan bug sudah dilaporkan balik ke backend/frontend (lihat panah feedback loop di `../trusthub-build-flow.html`) — jangan menumpuk temuan.
- **Jam 40**: fase pengerasan selesai — mulai rehearsal penuh & rekam video fallback (asuransi kalau live demo gagal di depan juri).
- **Jam 46**: submission checklist bagian teknis & aset terisi.
