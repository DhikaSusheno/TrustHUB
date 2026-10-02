// lib/i18n/dictionary.ts
// Chrome copy for the interface language, in the two locales shipped.
//
// SCOPE, and the reason it is drawn here: only chrome is translated. Trust
// badges, refusal reasons, answers, document titles, and dataset licence text
// are values the backend returns, in English, and they stay English in every
// locale. A half-translated answer is worse than an English one, because the
// reader cannot tell which half is authoritative.
//
// The English column is FROZEN. docs/demo/build/verify.py and
// docs/build/deckverify.py assert specific English strings against the recorded
// video frames and the submission PDF. Changing an English value here breaks
// both gates, and the video cannot be re-recorded without the licensed dataset.
// Translate; do not edit the English.
//
// This file is data only. It is imported by the provider and holds no logic, so
// a missing key fails the type check rather than rendering an empty label.

export const LOCALES = ["en", "id"] as const;
export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";

/** Endonyms: a reader looking for their own language scans for its own name. */
export const LOCALE_NAME: Record<Locale, string> = {
  en: "English",
  id: "Bahasa Indonesia",
};

/** BCP 47 tags, for Intl. Indonesian differs from English in number grouping. */
export const LOCALE_TAG: Record<Locale, string> = {
  en: "en-US",
  id: "id-ID",
};

type Entry = { en: string; id: string };

export const STRINGS = {
  // LeftNav: the nine pages.
  "nav.ask": { en: "Ask", id: "Tanya" },
  "nav.equipment": { en: "Equipment", id: "Peralatan" },
  "nav.documents": { en: "Documents", id: "Dokumen" },
  "nav.graph": { en: "Graph", id: "Graf" },
  "nav.verification": { en: "Verification", id: "Pemeriksaan" },
  "nav.maintenance": { en: "Maintenance", id: "Pemeliharaan" },
  "nav.overview": { en: "Overview", id: "Ringkasan" },
  "nav.audit": { en: "Audit", id: "Audit" },
  "nav.dataset": { en: "Dataset", id: "Data" },

  // LeftNav footer: index state, read by anyone deciding whether to trust the page.
"status.index_ready": { en: "Index ready", id: "Indeks siap" },
"status.index_absent": { en: "Index not built", id: "Indeks belum dibuat" },
"status.index_checking": { en: "Checking index…", id: "Memeriksa indeks…" },
  "status.backend_offline": { en: "Backend offline", id: "Server tidak tersambung" },

  // Page headers. English frozen, see the note above.
  "page.ask.title": { en: "Ask the Knowledge Hub", id: "Ajukan pertanyaan" },
  "page.ask.subtitle": {
    en: "Every answer carries a trust badge, the documents behind it, and the reason for its score. Questions with no support are refused.",
    id: "Setiap jawaban membawa tanda kepercayaan, dokumen di balik jawabannya, dan alasan skornya. Pertanyaan tanpa dukungan akan ditolak.",
  },
  "page.equipment.title": { en: "Equipment", id: "Peralatan" },
  "page.equipment.subtitle": {
    en: "Eight units in Set 01, each with interlock logic, a P&ID reference, and maintenance history.",
    id: "Delapan unit pada Set 01, masing-masing dengan logika pengaman (interlock), referensi gambar proses (P&ID), dan riwayat pemeliharaan.",
  },
  "page.documents.title": { en: "Documents", id: "Dokumen" },
  "page.documents.subtitle": {
    en: "Every indexed file with its document number, revision, and the approval marker that was actually found in it.",
    id: "Setiap berkas yang terindeks, lengkap dengan nomor dokumen, revisi, dan tanda persetujuan yang benar-benar ditemukan di dalamnya.",
  },
  "page.graph.title": { en: "Knowledge Graph", id: "Graf pengetahuan" },
  "page.graph.subtitle": {
    en: "How the documents, interlock logic, and failure history connect. Every unit is linked to the documents that govern it.",
    id: "Bagaimana dokumen, logika pengaman, dan riwayat kegagalan saling terhubung. Setiap unit ditautkan ke dokumen yang mengaturnya.",
  },
  "page.verification.title": { en: "Verification", id: "Pemeriksaan" },
  "page.verification.subtitle": {
    en: "Do the documents agree with each other? Extraction inventory, cross-confirmed values, and every contradiction found.",
    id: "Apakah dokumen-dokumen ini saling cocok? Daftar hasil pembacaan, nilai yang dikonfirmasi silang, dan setiap kontradiksi yang ditemukan.",
  },
  "page.maintenance.title": { en: "Maintenance History", id: "Riwayat pemeliharaan" },
  "page.maintenance.subtitle": {
    en: "211 work orders and 31 breakdowns, 2024-06-04 to 2025-12-06. Costs are the workbook's own dummy rupiah values.",
    id: "211 perintah kerja dan 31 kerusakan, 4 Juni 2024 sampai 6 Desember 2025. Biaya memakai nilai rupiah contoh dari buku kerja.",
  },
  "page.overview.title": { en: "Manufacturing Knowledge Hub", id: "Pusat pengetahuan manufaktur" },
  "page.overview.subtitle": {
    en: "LLDPE unit, Set 01. Documents, interlock logic, and maintenance history in one index.",
    id: "Unit LLDPE, Set 01. Dokumen, logika pengaman, dan riwayat pemeliharaan dalam satu indeks.",
  },
  "page.audit.title": { en: "Audit & Trust", id: "Audit & kepercayaan" },
  "page.audit.subtitle": {
    en: "How the score is computed, and every question this instance has been asked.",
    id: "Cara skor dihitung, dan setiap pertanyaan yang pernah diajukan ke sistem ini.",
  },
  "page.dataset.title": { en: "Dataset & Policy", id: "Data & Kebijakan" },
  "page.dataset.subtitle": {
    en: "Provenance, index contents, and what this system will and will not do with the data.",
    id: "Asal-usul data, isi indeks, dan apa yang akan serta tidak akan dilakukan sistem ini terhadap data.",
  },

  // Shared states. Every data-backed page renders these three.
  "state.loading": { en: "Loading", id: "Memuat" },
  "state.no_index": { en: "Plant index not built", id: "Indeks plant belum dibuat" },
  "state.load_failed": { en: "Could not load this view", id: "Halaman ini tidak dapat dimuat" },
  "state.try_again": { en: "Try again", id: "Coba lagi" },

  // Language control.
  "lang.label": { en: "Language", id: "Bahasa" },
  "lang.switch_to": { en: "Switch interface language", id: "Ganti bahasa antarmuka" },

  // LeftNav footer: colour theme.
  "theme.label": { en: "Colour theme", id: "Tema warna" },
  "theme.dark": { en: "Dark", id: "Gelap" },
  "theme.light": { en: "Light", id: "Terang" },
} satisfies Record<string, Entry>;

export type StringKey = keyof typeof STRINGS;

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}