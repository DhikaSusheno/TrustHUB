"""Trust Engine: skor, badge, dan guardrail safety-critical.

Prinsip yang dipegang modul ini: trust score harus bisa diaudit. Setiap
sinyal yang dipatok di sini Returning bukan lagi "rasa" LLM, dan komponen
skornya dikembalikan utuh ke klien supaya juri bisa menghitung ulang sendiri.

Bobot_signal mengikuti rancangan proposal bagian 5.4. Bobot itu asumsi awal
[A] dan DIKALIBRASI lewat set evaluasi (lihat plant/evaluation.py) - angka
di sini bukan hasil pengukuran, dan deck harus menyebutnya sebagai
"designed weights, calibrated on our evaluation set".

Status approval yang dipakai TIDAK dikarang: `approved` dan `unknown` berasal
langsung dari dokumen (lihat extract.detect_approval). `unknown` diberi skor
approval parsial, bukan nol dan bukan penuh - karena dokumen yang tidak
menyatakan status jelas lebihodegradable dari dokumen yang dinyatakan usang,
tetapi tidak bisa dianggap sama dengan yang disetujui.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any

from .retrieval import (
    domain_terms,
    extract_document_refs,
    mentions_known_entity,
    non_knowledge_intent,
    unknown_instruments_mentioned,
    unknown_tags_mentioned,
)

# Bobot sinyal (proposal 5.4).
WEIGHTS = {
    "approval": 0.30,
    "revision": 0.20,
    "agreement": 0.20,
    "relevance": 0.20,
    "coverage": 0.10,
}

# Ambang badge (proposal 5.4, asumsi awal).
TRUSTED_THRESHOLD = 0.80
VERIFY_THRESHOLD = 0.50

# Konstanta pemetaan relevansi. K = 8 mengubah skor BM25 tak terbatas
# (umumnya 0-40 pada corpus ini) ke rentang 0..1 dengan s/(s+K).
RELEVANCE_K = 8.0

# CATATAN PENTING: relevance TIDAK bisa membedakan pertanyaan plant dari
# pertanyaan non-plant. Diukur atas 31 pertanyaan dalam-dataset dan 32 di
# luar dataset, rentang keduanya tumpang tindih sepenuhnya:
#
#   dalam dataset   : 0.357 .. 0.737   (terendah: "which equipment fails most often?")
#   luar dataset    : 0.000 .. 0.572   (tertinggi: "how do I open a bank account?")
#
# Jadi TIDAK ADA ambang yang memisahkan keduanya, dan klaim lama di file ini
# bahwa "pertanyaan luar dataset mendarat di 0.14-0.18" adalah hasil
# pengukuran pada sampel yang terlalu kecil, bukan fakta.
#
# Karena itu penolakan out-of-scope ditangani oleh gerbang kosakata domain di
# `retrieval.plant_vocabulary`, yang memeriksa TOPIK dan bukan skor. Lantai di
# bawah ini sekarang hanya satu tugas yang lebih sempit: menangkap
# pertanyaan yang sudah terbukti tentang plant ini, tapi isinya memang
# tidak ada di corpus.
#
# 0.20 dipilih karena setelah gerbang domain, answers dari 0.15 sampai 0.25
# tidak berbeda pada satu pun kasus: 63 di evaluation_set.json dan 102 di
# holdout. 0.20 dipilih agar pertanyaan yang sah tapi luas ("give me the
# list of critical equipment", relevansi 0.24) tidak terblokir hanya karena
# meleset 0.01.
RELEVANCE_FLOOR = 0.20

# Skor approval per status dokumen.
APPROVAL_SCORE = {
    "approved": 1.0,
    "pending": 0.45,   # "ISSUED FOR APPROVAL" - sudah pernah direview, belum final
    "draft": 0.20,     # "ISSUED FOR REVIEW" - masih draft
    "unknown": 0.40,   # tidak dinyatakan di dokumen
}

# Badge
TRUSTED = "TRUSTED"
VERIFY = "VERIFY"
DO_NOT_EXECUTE = "DO NOT EXECUTE"

# Kata kunci yang menaikkan level kehati-hatian Safety-critical.
CRITICAL_ACTION = re.compile(
    r"\b("
    r"lock-?out|\bloto\b|isolat|permit|trip|interlock|emergency|e-?stop|"
    r"depressuris|bleed|drain|purge|vent|zero energy|"
    r"start-?up|shut-?down|bump-?start|restart"
    r")\b",
    re.IGNORECASE,
)

# Pertanyaan tentang nilai batas keselamatan. Memparafrase setpoint yang salah
# adalah penyebab langsung tindakan yang salah, jadi nilai ini tidak boleh
# diringkas oleh LLM.
SETPOINT_QUERY = re.compile(
    r"\b(set-?points?|trip (points?|limits?|values?)|sil\b|safety integrity|"
    r"cause (and|&) effect|interlock (logic|function|trip))\b",
    re.IGNORECASE,
)

# Niat bertindak, bukan sekadar rujukan. "What is nitrogen blanketing?" adalah
# rujukan; "How do I replace the gland packing?" adalah instruksi.
ACTION_INTENT = re.compile(
    r"\b("
    r"how (do|to|can|should)|what (are )?(the )?steps|steps? (to|for)|"
    r"step-?by-?step|procedures? (for|to)|"
    # Kata kerja kerja-deploy pakai sufiks `\w*`, bukan `\b` di akhir: pola
    # `\btroubleshoot\b` TIDAK cocok dengan "troubleshooting" karena tidak ada
    # batas kata sebelum huruf 'i'. Diuji dan causing safety flag hilang.
    r"troubleshoot\w*|diagnos\w*|repair\w*|replac\w*|renew\w*|overhaul\w*|"
    r"calibrat\w*|adjust\w*|tighten\w*|isolate\w*|reset\w*|"
    r"do i (need|have) to|can i (start|stop|reset)|"
    r"walk me through|guide me|instructions? (for|to)|"
    r"work ?around|work ?on"
    r")\b",
    re.IGNORECASE,
)


@dataclass
class Signal:
    """Satu komponen trust score, dengan bukti yang bisa ditampilkan."""

    name: str
    weight: float
    score: float  # 0..1
    detail: str
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrustVerdict:
    """Hasil penilaian trust untuk satu jawaban."""

    badge: str
    score: float
    signals: list[Signal]
    reasons: list[str] = field(default_factory=list)
    safety_critical: bool = False
    verbatim_required: bool = False
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "badge": self.badge,
            "score": round(self.score, 3),
            "signals": [s.to_dict() for s in self.signals],
            "reasons": self.reasons,
            "safety_critical": self.safety_critical,
            "verbatim_required": self.verbatim_required,
            "conflicts": self.conflicts,
            "warnings": self.warnings,
            "weights": WEIGHTS,
        }


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def signal_approval(hits: list[dict[str, Any]]) -> Signal:
    """Status approval dokumen yang menopang jawaban.

    Kalau beberapa dokumen jadi sumber, yang TERBURUK menentukan nilai: satu
    dokumen yang belum disetujui membuat seluruh jawaban tidak layak
    dieksekusi, meskipun dokumen lain approved.
    """
    if not hits:
        return Signal("approval", WEIGHTS["approval"], 0.0, "no source retrieved",
                      [])
    scores = [APPROVAL_SCORE.get(h.get("approval_status") or "unknown", 0.4)
              for h in hits]
    worst = min(scores)
    unknown = [h for h in hits if (h.get("approval_status") or "unknown") == "unknown"]
    detail = f"lowest source approval = {_label(scores, worst)}"
    evidence = [
        f"{h.get('title') or h.get('filename')}: {h.get('approval_status')}"
        + (f" ({h['approval_raw']})" if h.get("approval_raw") else "")
        for h in hits
    ]
    if unknown:
        detail += f"; {len(unknown)} source(s) do not state approval status"
    return Signal("approval", WEIGHTS["approval"], _clamp(worst), detail, evidence)


def _label(scores: list[float], target: float) -> str:
    order = sorted(set(scores), reverse=True)
    for s in order:
        if abs(s - target) < 1e-9:
            level = {1.0: "approved", 0.45: "pending", 0.20: "draft",
                     0.40: "unknown"}.get(s, str(s))
            return f"{level} ({s:.2f})"
    return f"{target:.2f}"


def signal_revision(hits: list[dict[str, Any]]) -> Signal:
    """Apakah sumber memakai revisi terbaru yang tersedia untuk tag-nya.

    Dokumen yang tidak punya nomor revisi (OPL tidak memilikinya) tidak
    dihukum - revisi tidak berarti usang kalau tidak pernah direvisi.
    """
    revs = [h.get("revision") for h in hits if h.get("revision")]
    if not revs:
        return Signal("revision", WEIGHTS["revision"], 0.75,
                      "sources carry no revision number", [])
    evidence = [f"{h.get('title') or h.get('filename')}: rev {h.get('revision')}"
                for h in hits if h.get("revision")]
    return Signal("revision", WEIGHTS["revision"], 1.0,
                  f"{len(revs)}/{len(hits)} sources state a revision", evidence)


def signal_relevance(hits: list[dict[str, Any]]) -> Signal:
    """Seberapa retrieval benar-benar relevan.

    BM25 adalah skor tak terbatas dan TIDAK comparable antar query: pertanyaan
    dengan banyak kata selalu punya skor lebih tinggi daripada pertanyaan
    pendek. Jadi perbandingan mean/best (pola yang biasa dipakai) selalu
    mengembalikan ~1.0 dan tidak pernah membedakan kasus sulit dari kasus
    mudah - persis yang membuat "who is the CEO of Starbucks?" tetap mendapat
    badge hijau.

    Yang dipakai: `s / (s + K)` dengan K = 8. Fungsi ini monoton, tidak
    butuh dataset referensi, dan memetakan skor 0-40 ke rentang 0.0-0.83.

    TIDAK ada penalti "sebaran". Percobaan sebelumnya memakai
    `s0/(s0 + 4*s1)` dengan maksud menghukum jawaban bersumber satu, tapi
    justru terbalik: pada jawaban yang benar, banyak chunk dari dokumen yang
    SAMA ikut cocok sehingga s0 ~= s1, dan penalti itujustru menurunkan skornya.
    Jumlah dokumen yang berbeda sudah diukur oleh sinyal `agreement`, jadi
    menghitungnya dua kali hanya mengaburkan hal yang sama.
    """
    if not hits:
        return Signal("relevance", WEIGHTS["relevance"], 0.0, "no hit", [])
    scores = sorted((float(h.get("score", 0.0)) for h in hits), reverse=True)
    if scores[0] <= 0:
        return Signal(
            "relevance", WEIGHTS["relevance"], 0.0, "non-positive scores", []
        )
    top3 = scores[:3]
    mean_top = sum(top3) / len(top3)
    normalised = _clamp(mean_top / (mean_top + RELEVANCE_K))
    return Signal(
        "relevance", WEIGHTS["relevance"], normalised,
        f"normalised retrieval strength {normalised:.2f} "
        f"(mean of top 3 raw {mean_top:.2f}) over {len(scores)} chunks",
        [f"score {s:.2f}" for s in scores[:5]],
    )


def signal_coverage(hits: list[dict[str, Any]]) -> Signal:
    """Cakupan bukti: berapa banyak jenis dokumen yang menyumbang.

    Satu chunk dari satu datasheet lebih lemah daripada chunk dari datasheet +
    OPL + interlock, karena itu menandakan bukti lintas sumber.
    """
    kinds = {h.get("doc_type") for h in hits if h.get("doc_type")}
    coverage = min(len(kinds) / 3.0, 1.0)
    return Signal(
        "coverage", WEIGHTS["coverage"], coverage,
        f"{len(kinds)} document type(s) contribute evidence",
        sorted(kinds),
    )


def detect_safety_critical(
    question: str, hits: list[dict[str, Any]]
) -> tuple[bool, list[str]]:
    """Apakah jawaban ini prosedur yang harus dibaca verbatim, bukan diparafrase.

    Percobaan pertama menandai SEMUA pertanyaan sebagai safety-critical karena
    aturannya "sumbernya OPL atau interlock" - padahal OPL adalah 55 dari 87
    dokumen, jadi setiap pertanyaan retrieval menyentuh salah satunya dan
    flag-nya jadi tidak membawa informasi apa pun.

    Aturan yang dipakai sekarang, dan Alasannya:
      - kata kunci tindakan berbahaya di pertanyaan (isolasi, LOTO, trip,
        bleed, permit): pertanyaan seperti ini pada dasarnya memang
        permintaan instruksi berisiko.
      - pertanyaan(setpoint / trip point / SIL): nilai batas yang diparafrase
        salah adalah penyebab langsung orang salah tindakan.
      - sumber utamanya interlock diagram: dokumen ini memuat SIL dan cause-
        effect matrix, jadi nilainya selalu menyangkut keselamatan, apa pun
        pertanyaannya.
      - sumber utamanya OPL DAN pertanyaan berisi niat bertindak (how to,
        steps, troubleshoot, replace, ...): hasil-hasil OPL boleh diparafrase
        untuk pertanyaan rujukan ("apa itu nitrogen blanketing"), tapi tidak
        boleh untuk instruksi.

    OPL dengan pertanyaan rujukan sengaja TIDAK ditandai - kalau tidak,
    semua pertanyaan di sistem akan memakai mode verbatim dan penjelasannya
    hilang artinya.
    """
    reasons: list[str] = []
    q = question or ""

    m = CRITICAL_ACTION.search(q)
    if m:
        reasons.append(f"question asks about a hazardous action ('{m.group(0)}')")

    s = SETPOINT_QUERY.search(q)
    if s:
        reasons.append(f"question asks about a safety limit value ('{s.group(0)}')")

    top_types = [h.get("doc_type") for h in hits[:3]]
    if "interlock" in top_types:
        reasons.append(
            "primary source is an interlock logic diagram (SIL + cause & effect)"
        )
    elif "opl" in top_types and ACTION_INTENT.search(q):
        m2 = ACTION_INTENT.search(q)
        reasons.append(
            f"question requests action steps ('{m2.group(0) if m2 else 'action'}') "
            "from a one-point lesson"
        )

    return bool(reasons), reasons


def signal_agreement_scope(
    hits: list[dict[str, Any]], question_tag: str | None
) -> Signal:
    """Kesepakatan antar sumber, DITATASKAN oleh cakupan tag equipment.

    Tanpa batas ini, jawaban lintas-unit ("equipment mana paling sering
    diperbaiki?") bisa mendapat skor kesepakatan penuh karena dokumen dari 8
    unit berbeda ikut ter-retrieve - padahal dokumen unit lain TIDAK
    mengonfirmasi apa pun tentang equipment yang ditanyakan.

    Aturannya:
      - satu tag disebut, semua sumber tag itu    -> skirt penuh bila >=2 dokumen
      - satu tag disebut, sumber lain ikut terbawa -> rendah, karena sumber
        menyeberang tidak membuktikan apa pun soal unit itu
      - tidak ada tag (mode lintas unit)          -> hanya skirt penuh bila
        semua sumberNyat dari unit yang sama; kalau bercampur, dokumen unit A
        tidak bisa mengonfirmasi dokumen unit B
    """
    if not hits:
        return Signal(
            "agreement", WEIGHTS["agreement"], 0.0, "no source retrieved", []
        )
    tags = {h.get("equipment_tag") for h in hits if h.get("equipment_tag")}
    n_docs = len({h.get("doc_id") for h in hits})
    evidence = [
        f"{h.get('title') or h.get('filename')} [{h.get('doc_type')}, "
        f"{h.get('approval_status')}]"
        for h in hits[:6]
    ]

    if question_tag and tags and tags != {question_tag}:
        off_tag = sorted(tags - {question_tag})
        score = 0.25 if n_docs == 1 else 0.4
        return Signal(
            "agreement", WEIGHTS["agreement"], score,
            f"answer about {question_tag} but sources also cover "
            f"{', '.join(off_tag)}; cross-unit documents cannot corroborate",
            evidence,
        )
    if question_tag is None and len(tags) > 1:
        # Mode lintas unit: dokumen dari 8 unit berbeda yang ter-retrieve
        # bersama BUKAN 8 suara yang sepakat, dan menyamakannya sebagai
        # bulatan yang sama adalah kesalahan paling berbahaya. Badge turun
        # ke VERIFY.
        return Signal(
            "agreement", WEIGHTS["agreement"], 0.4,
            f"cross-unit question answered from {len(tags)} different units "
            f"({', '.join(sorted(tags))}); they do not corroborate each other",
            evidence,
        )
    if n_docs >= 2:
        return Signal(
            "agreement", WEIGHTS["agreement"], 1.0,
            f"{n_docs} documents corroborate each other", evidence,
        )
    return Signal(
        "agreement", WEIGHTS["agreement"], 0.55,
        "answer rests on a single document", evidence,
    )


def evaluate(
    question: str,
    hits: list[dict[str, Any]],
    related: list[dict[str, Any]] | None = None,
    conflicts: list[dict[str, Any]] | None = None,
    question_tag: str | None = None,
) -> TrustVerdict:
    """Beri skor trust + badge untuk satu set retrieval."""
    related = related or []
    conflicts = conflicts or []

    signals = [
        signal_approval(hits),
        signal_revision(hits),
        signal_agreement_scope(hits, question_tag),
        signal_relevance(hits),
        signal_coverage(hits),
    ]
    score = _clamp(sum(s.score * s.weight for s in signals))

    safety, safety_reasons = detect_safety_critical(question, hits)
    warnings: list[str] = []
    reasons: list[str] = [f"{s.name}={s.score:.2f} (weight {s.weight})" for s in signals]

    # Konflik antar sumber menurunkan skor secara eksplisit. Menutupi konflik
    # adalah kegagalan trust yang lebih serius daripada skor mediocre.
    if conflicts:
        penalty = min(0.30, 0.15 * len(conflicts))
        score = _clamp(score - penalty)
        warnings.append(
            f"{len(conflicts)} conflicting value(s) found across sources; "
            "an SME must decide"
        )

    unknown_sources = [
        h for h in hits if (h.get("approval_status") or "unknown") == "unknown"
    ]
    if unknown_sources and safety:
        warnings.append(
            "safety-critical answer whose source does not state approval status"
        )

    # Badge: prosedur safety-critical tanpa sumber approved DILARANG
    # dieksekusi, pengganti skor biasa. Ini aturan keras, bukan preferensi.
    has_approved = any(h.get("approval_status") == "approved" for h in hits)
    if safety and not has_approved:
        badge = DO_NOT_EXECUTE
        reasons.append(
            "safety-critical answer without any approved source -> "
            "DO NOT EXECUTE regardless of score"
        )
    elif not hits:
        badge = DO_NOT_EXECUTE
        reasons.append("no source retrieved -> cannot answer")
    elif score >= TRUSTED_THRESHOLD:
        badge = TRUSTED
    elif score >= VERIFY_THRESHOLD:
        badge = VERIFY
    else:
        badge = DO_NOT_EXECUTE

    # Sama dengan badge_for(score) - ditulis eksplisit karena dua aturan keras
    # di atas (safety tanpa approved, dan sumber kosong) punya prioritas di
    # atas pemetaan angka biasa.
    return TrustVerdict(
        badge=badge,
        score=score,
        signals=signals,
        reasons=reasons,
        safety_critical=safety,
        verbatim_required=safety,
        conflicts=conflicts,
        warnings=warnings,
    )


def badge_for(score: float) -> str:
    """Badge dari skor numerik saja.

    Dipisahkan dari `evaluate()` supaya skor tetap dari penjumlahan berbobot
    di satu tempat saja, sementara pemetaan skor-ke-badge ada di satu tempat
    saja juga. Tidak ada objek `TrustVerdict` di sini: pemanggil yang sudah
    tahu badge-nya (misalnya jawaban dari tabel maintenance, yang tidak punya
    dokumen untuk dinilai) tetap bisa turunannya dari ambang yang sama.

    Perhatikan aturan keras `evaluate()` TIDAK ada di sini: safety-critical
    tanpa sumber approved selalu DO NOT EXECUTE, dan sumber kosong selalu
    DO NOT EXECUTE. Fungsi ini hanya memetakan angka ke badge, jadi
    pemanggil yang memakai fungsi ini bertanggung jawab atas dua aturan itu
    sendiri.
    """
    if score >= TRUSTED_THRESHOLD:
        return TRUSTED
    if score >= VERIFY_THRESHOLD:
        return VERIFY
    return DO_NOT_EXECUTE


def badge_style(badge: str) -> dict[str, str]:
    """Warna badge untuk UI. Satu sumber kebenaran, dipakai backend + frontend."""
    return {
        TRUSTED: {"bg": "bg-emerald-500/15", "text": "text-emerald-300",
                  "ring": "ring-emerald-500/40", "label": "TRUSTED",
                  "meaning": "Approved, current and corroborated by more than "
                             "one source. Safe to use as basis for action."},
        VERIFY: {"bg": "bg-amber-500/15", "text": "text-amber-300",
                 "ring": "ring-amber-500/40", "label": "VERIFY",
                 "meaning": "Usable for orientation, but confirm the cited "
                            "document and revision before acting."},
        DO_NOT_EXECUTE: {"bg": "bg-red-500/15", "text": "text-red-300",
                         "ring": "ring-red-500/40", "label": "DO NOT EXECUTE",
                         "meaning": "Evidence is missing, unapproved or "
                                    "conflicting. Do not act on this answer."},
    }.get(badge, {"bg": "bg-slate-500/15", "text": "text-slate-300",
                  "ring": "ring-slate-500/40", "label": badge, "meaning": ""})


def should_refuse(
    question: str,
    hits: list[dict[str, Any]],
    known_tags: list[str] | None = None,
    known_refs: set[str] | None = None,
    min_relevance: float = RELEVANCE_FLOOR,
    vocabulary: frozenset[str] | None = None,
    known_instruments: set[str] | None = None,
) -> tuple[bool, str | None]:
    """Tolak menjawab? (grounding guardrail, proposal 5.4)

    Menolak lebih baik daripada menjawab tanpa sumber: inilah yang
    membedakan TrustHUB dari RAG generik yang akan mengarang jawaban dari
    sekadar parameter model.

    Enam pemeriksaan, berurutan dari yang paling pasti ke yang paling
    mungkin. Urutan itu penting: pesan yang paling spesifik lebih berguna
    daripada pesan yang umum, dan check yang murah harus jalan sebelum
    check yang mahal.

    1. Dokumen yang disebut tidak ada di dataset. Contoh: "what does
       OPL-GA-1201A-04 cover?" - OPL-04 memang tidak ada di dataset ini.
       Tanpa cek ini sistem akan menjawab dengan OPL-04 lain yang kebetulan
       mirip, dan itu kesalahan yang paling merusak kepercayaan.
    2. Equipment yang disebut user di luar dataset. Contoh: "procedure for
       ZX-9999". Tidak ada dokumen yang bisa jadi sumber sama sekali.
       Tag instrumen (PSLL-1201) dikecualikan dicabang equipment - formatnya
       sama dengan tag equipment, dan salah memperlakukannya sebagai equipment
       asing akan menolak pertanyaan yang sah jawabannya sudah diketahui.
       Cabang kedua dari check yang sama menangani instrumen yang TIDAK ADA
       (ZSO-9999): formatnya dikenali dari EQUIPMENT_TAG_SHAPE vs
       INSTRUMENT_TAG_SHAPE, yang tidak bisa tumpang tindih.
    3. Niat bukan pencarian pengetahuan. "write me a poem about hexane"
       bukan pertanyaan yang bisa dijawab dari dokumen, dan memaksakan
       jawaban hanya menghasilkan potongan yang tidak menjawab apa pun.
    4. Pertanyaan tidak menyentuh kosakata plant ini sama sekali. "How do
       I open a bank account?" retrieve lima chunk, karena "account"
       muncul di beberapa dokumen - jadi check relevansi tidak menangkap
       nya. Pengukuran: relevansi "bank account" (0.572) LEBIH TINGGI dari
       "which equipment fails most often" (0.357), jadi tidak ada ambang
       yang memisahkan keduanya. Yang memisahkan adalah topik: apakah
       pertanyaannya bicara tentang entitas yang ada di plant ini.
    5. Tidak ada chunk yang ter-retrieve.
    6. Relevansi di bawah lantai. Ini menangkap pertanyaan yang menyebut
       entitas plant tapi tetap tidak ada isinya di corpus.

    Check 4 dilewati kalau pertanyaan sudah menyebut tag atau nomor dokumen
    yang ADA - penyebutan itu sudah membuktikan topiknya, dan vocabulary
    hanya akan menahan pertanyaan yang sah.
    """
    if known_refs:
        asked = extract_document_refs(question)
        absent = [r for r in asked if r not in known_refs]
        if absent:
            return True, (
                f"{', '.join(absent)} does not exist in the indexed dataset. "
                "I will not substitute a different document for it."
            )

    # Dihitung di luar `if known_tags:` karena dipakai lagi di check 4.
    # Kalau hanya dihitung di dalam blok itu, `known_tags` yang kosong
    # (index tanpa equipment - persis keadaan saat startup atau saat dataset
    # gagal di-ingest) akan membuat check 4 naik ke baris yang memanggil
    # variabel yang belum dibuat, jadi penolakan yang seharusnya
    # justru jadi UnboundLocalError.
    instruments = {str(t).upper() for t in (known_instruments or set())}

    if known_tags:
        mentioned = [t for t in known_tags if t.upper() in (question or "").upper()]
        unknown = [
            t
            for t in unknown_tags_mentioned(question, known_tags)
            if t not in instruments
        ]
        if unknown and not mentioned:
            return True, (
                f"Equipment {', '.join(unknown)} is not part of this dataset, "
                "so I have no document to answer from."
            )

        # Instrumen yang TIDAK ADA, dipisah dari equipment yang tidak ada.
        # Pengecualian tag instrumen di cabang atas tetap perlu: pola tag tidak
        # bisa membedakan GA-1201A (equipment) dari PSLL-1201 (instrumen), dan
        # memperlakukan instrumen sah sebagai equipment asing akan menolak
        # pertanyaan yang jawabannya sudah diketahui.
        #
        # Yang ditolak di sini bukan "instrumen", melainkan instrumen yang tidak
        # ada. Tanpa cabang ini "what is the trip setpoint for ZSO-9999?"
        # dijawab VERIFY dengan potongan Interlock GA-1201A, LLD YD-2301, dan
        # OPL KC-4501: tidak ada angka yang dikarang, tapi isinya milik unit
        # lain dan bentuknya persis seperti jawaban yang benar.
        phantom = unknown_instruments_mentioned(question, known_tags, instruments)
        if phantom and not mentioned:
            listed = ", ".join(sorted(instruments)[:6])
            more = " among others" if len(instruments) > 6 else ""
            return True, (
                f"Instrument {', '.join(phantom)} does not appear in the "
                "indexed dataset, so I have no measured value for it. "
                f"The instruments that do appear are: {listed}{more}."
            )

    if non_knowledge_intent(question):
        return True, (
            "This knowledge hub answers questions from the indexed plant "
            "documents. It does not write poems, letters, or code, so there is "
            "no document here that would answer that."
        )

    if vocabulary is not None:
        entity = mentions_known_entity(
            question, known_tags or [], known_refs or set(), instruments
        )
        if entity is None:
            terms = domain_terms(question, vocabulary)
            if not terms:
                return True, (
                    "This question is not about any equipment, document, work "
                    "order, or maintenance record in the indexed dataset, so "
                    "there is nothing here I can ground an answer in. I will "
                    "not answer without a source."
                )

    if not hits:
        return True, (
            "No document in the indexed dataset covers this question. "
            "I will not answer without a source."
        )

    strength = signal_relevance(hits).score
    if strength < min_relevance:
        return True, (
            "The indexed documents do not cover this question "
            f"(retrieval strength {strength:.2f} is below the {min_relevance:.2f} "
            "required to answer). I will not answer without a source."
        )
    return False, None