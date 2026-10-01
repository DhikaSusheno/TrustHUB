"""Layer jawaban: pertanyaan -> bukti -> jawaban bersitasi + badge trust.

Prinsipnya satu: tidak ada jawaban tanpa sumber yang bisa diklik.

Alur `answer()`:

  1. Klasifikasikan pertanyaan. Pertanyaan agregat ("equipment mana yang paling
     sering breakdown", "total downtime LV-6701") dijawab dari tabel
     work_orders, BUKAN dari FTS. Mencari angka downtime lewat full-text search
     akan mengembalikan prosa yang kebetulan menyebut angka - lambat, tidak
     andal, dan tidak bisa dipertanggungjawabkan.
  2. Tentukan cakupan equipment: tag yang disebut eksplisit, atau mode lintas
     unit. Tidak pernah ditebak dari hasil retrieval (lihat
     retrieval.detect_equipment_tag).
  3. Jalankan guardrail trust. Kalau batal, kembalikan penolakan - dan tidak
     pernah memanggil LLM sama sekali.
  4. Susun jawaban dari bukti terambil. Untuk pertanyaan safety-critical,
     langkah prosedur ditampilkan VERBATIM dari dokumen, bukan diparafrase.
  5. Skor trust, catat ke audit log, kembalikan.

Peran LLM: opsional, dan hanya untuk merangkai kalimat. Semua fakta, angka,
nama, dan nilai batas berasal dari dokumen. Kalau LLM tidak tersedia, sistem
masih menjawab - dengan jawaban terstruktur yang dibaca langsung dari basis
data. Ini yang membuat demo tidak bisa mati gara-gara kuota atau jaringan, dan
sekaligus memenuhi aturan Case Book bahwa output AI harus bisa divalidasi.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Callable

from . import conflicts as conflicts_mod
from . import registry, retrieval, trust

# ------------------------------------------------------------------ -------
# Klasifikasi pertanyaan
# -----------------------------------------------------------------------

#: Kata yang menunjukkan pertanyaannya menyangkut riwayat kerja, bukan isi
#: dokumen. Dipakai sebagai gerbang pertama: kalau tidak ada kata ini, soal
#: procedure, definisi, atau spesifikasi, dan jawabannya harus dari dokumen.
MAINTENANCE_TOPIC = re.compile(
    # Setiap kata ditulis sebagai STEM dengan akhiran opsional, bukan kata
    # lengkap. Versi pertama memakai `\bbreakdown\b`, yang tidak cocok dengan
    # "breakdowns" - sehingga pertanyaan yang paling wajar ("how many breakdowns
    # does EA-5601 have?") tidak dikenali sebagai pertanyaan maintenance dan
    # dialihkan ke pencarian nilai parameter.
    r"\b(downtime|outage|stoppage|uptime|cost|spend|idr|budget|moneys?|"
    r"breakdowns?|fail(ure|ures|ed|s)?|faults?|defects?|incidents?|"
    r"repair(ed|s|ing)?|maintenance|work ?orders?|wo|history|hour)s?\b",
    re.IGNORECASE,
)

#: Petunjuk yang menentukan BENTUK jawaban agregat. Dipisah dari
#: MAINTENANCE_TOPIC karena "soal maintenance" belum menentukan bentuk
#: jawabannya.
RANK_CUE = re.compile(
    r"\b(most|fewest|worst|best|highest|lowest|top|rank|ranking|ranked|"
    r"compare|comparison|prone|biggest)\b",
    re.IGNORECASE,
)
RECENT_CUE = re.compile(r"\b(recent|latest|last|first|newest|earliest)\b", re.IGNORECASE)
HISTORY_CUE = re.compile(
    r"\b(history|histori|list|show|timeline|log|all|every|each)\b", re.IGNORECASE
)
COST_CUE = re.compile(
    r"\b(cost|spend|idr|budget|money|expense)\b", re.IGNORECASE
)
DOWNTIME_CUE = re.compile(
    r"\b(downtime|outage|stoppage|uptime|hours?)\b", re.IGNORECASE
)
COUNT_CUE = re.compile(r"\b(how many|number of|count|total|tally|sum)\b", re.IGNORECASE)

#: Pertanyaan yang jawabannya sebuah NILAI terukur. Dicek lebih dulu dari
#: agregat, karena "total downtime for LV-6701" mengandung kata total dan
#: downtime, sementara "what is the rated flow" mengandung kata rated - dan
#: yang lebih khusus harus menang.
FACT_PARAMETER = re.compile(
    # "capacity" sengaja tidak ada: kata itu muncul di percakapan biasa
    # ("battery capacity of the UPS") dan memunculkannya di sini membuat
    # pertanyaan yang tidak boleh dijawab dianggap pertanyaan nilai terukur.
    r"\b(set-?points?|trip (point|limit|value|threshold)s?|"
    r"sil\b|suction press\w*|discharge press\w*|discharge flows?|"
    r"flow rates?|rated flows?|rated heads?|rated currents?|"
    r"design (pressures?|temperatures?)|"
    r"operating (pressures?|temperatures?)|pumping temps?|"
    # "vibration" polos TIDAK Asking nilai: "vibration alarm on KC-4501"
    r"vibration (limit|setpoint|trip|threshold)s?|"
    r"npsh|shaft speeds?|motor speeds?|viscosit\w*)\b",
    re.IGNORECASE,
)


def classify(question: str) -> str:
    """Tentukan bentuk jawaban yang benar untuk pertanyaan ini.

    Urutan pemeriksaan penting dan diuji dengan set evaluasi:
      1. nilai parameter terukur -> baca document_parameters
      2. agregat maintenance     -> baca work_orders
      3. dokumen                 -> baca FTS + sitasi

    Versi pertama memakai daftar regex AGGREGATE_PATTERNS yang diurutkan, dan
    gagal pada 3 dari 5 pertanyaan agregat karena mengasumsikan urutan kata:
    pola "most ... fails" tidak cocok dengan "fails most often", dan pola
    "downtime ... hours" tidak cocok dengan "total downtime for LV-6701" yang
    tidak menyebut kata hours. Pola berurutan hanya benar kalau urutan kata
    dijamin, dan dalam bahasa alami tidak.
    """
    q = question or ""

    if FACT_PARAMETER.search(q):
        return "parameter_value"

    # Shortcut tag instrumen DIHAPUS. Versi sebelumnya mengembalikan
    # "parameter_value" setiap pertanyaan yang menyebut PSLL-1201 atau tag
    # serupa, termasuk "procedure for ZX-9999" - yang bukan pertanyaan nilai.
    # Semua pertanyaan nilai sudah tertangkap FACT_PARAMETER di atas, jadi
    # shortcut ini hanya menambah jalur salah.

    if not MAINTENANCE_TOPIC.search(q):
        return "document"

    if RANK_CUE.search(q):
        return "ranking"
    if RECENT_CUE.search(q):
        return "recent"
    if HISTORY_CUE.search(q):
        return "history"
    if COST_CUE.search(q):
        return "cost_total"
    if DOWNTIME_CUE.search(q):
        return "downtime_total"
    if COUNT_CUE.search(q):
        return "count"
    # Menyebut topik maintenance tanpa petunjuk yang jelas. "history" adalah
    # bacaan paling umum dan tidak pernah mengarang angka yang tidak ada.
    return "history"

# ------------------------------------------------------------------ -------
# Sumber data terstruktur
# -----------------------------------------------------------------------

def _fmt_hours(value: float | None) -> str:
    if value is None:
        return "unknown"
    return f"{value:,.1f} hours"


def _fmt_idr(value: float | None) -> str:
    if value is None:
        return "unknown"
    return f"IDR {value:,.0f}"


@dataclass
class StructuredAnswer:
    """Jawaban yang dihitung langsung dari basis data.

    `kind` yang berbeda diberi penanganan berbeda karena pertanyaan agregat dan
    pertanyaan parameter punya bentuk jawaban yang sangat berbeda; mencoba
    memaksa keduanya lewat format yang sama hanya menghasilkan teks awkwardly.
    """

    kind: str
    summary: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "summary": self.summary,
            "rows": self.rows,
            "note": self.note,
        }


def _equipment_summary(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        r for r in conn.execute(
            """SELECT equipment_tag, equipment_name, criticality, doc_count,
                      opl_count, approved_doc_count, wo_count, breakdown_count,
                      downtime_hours, total_cost_idr
               FROM equipment ORDER BY breakdown_count DESC, downtime_hours DESC"""
        )
    ]


def answer_from_maintenance(
    conn: sqlite3.Connection, kind: str, question: str, tag: str | None
) -> StructuredAnswer | None:
    """Jawab pertanyaan agregat dari tabel work_orders.

    `None` kalau jenis pertanyaannya tidak bisa dijawab dari sini - pemanggil
    lalu jatuh ke retrieval dokumen. Tidak pernah menebak angka.
    """
    q = (question or "").lower()

    if kind == "ranking":
        rows = [
            {
                "equipment_tag": r["equipment_tag"],
                "equipment_name": r["equipment_name"],
                "breakdown_count": r["breakdown_count"],
                "work_order_count": r["wo_count"],
                "downtime_hours": r["downtime_hours"],
                "total_cost_idr": r["total_cost_idr"],
            }
            for r in _equipment_summary(conn)
        ]
        metric = "downtime_hours"
        if "cost" in q or "spend" in q or "idr" in q:
            metric = "total_cost_idr"
        elif "work order" in q or "wo" in q.split() or "repair" in q:
            metric = "wo_count"
        elif "breakdown" in q or "fail" in q or "failure" in q:
            metric = "breakdown_count"
        ranked = sorted(rows, key=lambda r: -r[metric])
        top = ranked[0]
        metric_label = {
            "downtime_hours": "total downtime",
            "total_cost_idr": "total cost",
            "wo_count": "number of work orders",
            "breakdown_count": "number of breakdowns",
        }[metric]
        return StructuredAnswer(
            kind="ranking",
            summary=(
                f"{top['equipment_tag']} ({top['equipment_name']}) has the highest "
                f"{metric_label}: "
                + (
                    f"{top[metric]:,.1f} hours"
                    if metric == "downtime_hours"
                    else (
                        _fmt_idr(top[metric])
                        if metric == "total_cost_idr"
                        else f"{top[metric]:,d}"
                    )
                )
            ),
            rows=ranked,
            note=(
                "Computed from the 211 work orders in the official CALIBER "
                "Maintenance History workbook, not from document text."
            ),
        )

    if kind == "count":
        if tag:
            row = conn.execute(
                """SELECT COUNT(*) AS wo, SUM(breakdown) AS brk,
                          COALESCE(SUM(downtime_hours),0) AS dt,
                          COALESCE(SUM(total_cost_idr),0) AS cost
                   FROM work_orders WHERE equipment_tag = ?""",
                (tag,),
            ).fetchone()
            return StructuredAnswer(
                kind="count",
                summary=(
                    f"{tag}: {row['wo']} work orders in total, of which "
                    f"{int(row['brk'] or 0)} were breakdowns, costing "
                    f"{_fmt_hours(row['dt'])} of downtime and {_fmt_idr(row['cost'])}."
                ),
                rows=[dict(row, equipment_tag=tag)],
                note="Aggregated from the Maintenance History workbook.",
            )
        total = conn.execute(
            """SELECT COUNT(*) AS wo, SUM(breakdown) AS brk,
                      COALESCE(SUM(downtime_hours),0) AS dt,
                      COALESCE(SUM(total_cost_idr),0) AS cost
               FROM work_orders"""
        ).fetchone()
        return StructuredAnswer(
            kind="count",
            summary=(
                f"The indexed dataset contains {total['wo']} work orders, of which "
                f"{int(total['brk'] or 0)} were breakdowns, covering "
                f"{_fmt_hours(total['dt'])} of downtime and {_fmt_idr(total['cost'])} "
                "in cost."
            ),
            rows=[dict(total)],
            note="Aggregated from the Maintenance History workbook.",
        )

    if kind in {"downtime_total", "cost_total"}:
        column = "downtime_hours" if kind == "downtime_total" else "total_cost_idr"
        if tag:
            row = conn.execute(
                f"SELECT COALESCE(SUM({column}),0) AS v FROM work_orders "
                "WHERE equipment_tag = ?",
                (tag,),
            ).fetchone()
            value, scope = row["v"], tag
        else:
            row = conn.execute(
                f"SELECT COALESCE(SUM({column}),0) AS v FROM work_orders"
            ).fetchone()
            value, scope = row["v"], "the whole plant"
        formatted = _fmt_hours(value) if column == "downtime_hours" else _fmt_idr(value)
        return StructuredAnswer(
            kind=kind,
            summary=(
                f"Total {column.replace('_', ' ')} for {scope} is {formatted} "
                "(dataset-derived, computed from the Maintenance History workbook)."
            ),
            rows=[{"scope": scope, "value": value, "unit": column}],
            note=(
                "Costs in the CALIBER workbook are described by the dataset "
                "authors as dummy values in IDR."
            ),
        )

    if kind == "history":
        wos = registry.list_work_orders(conn, equipment_tag=tag, breakdown_only=False)
        if tag and not wos:
            wos = registry.list_work_orders(conn, equipment_tag=tag)
        breakdown_first = "breakdown" in q
        ordered = sorted(
            wos,
            key=lambda w: (bool(w.get("breakdown")) if breakdown_first else False,
                           str(w.get("report_date") or "")),
            reverse=breakdown_first,
        )
        if not ordered:
            return StructuredAnswer(
                kind="history",
                summary="No work order matches that scope in this dataset.",
                rows=[],
                note="This is an empty result, not a missing record.",
            )
        shown = ordered[:25]
        return StructuredAnswer(
            kind="history",
            summary=(
                f"{len(ordered)} work order(s) for "
                f"{tag or 'the whole plant'}"
                + (
                    f"; {sum(1 for w in wos if w.get('breakdown'))} of them breakdowns."
                    if not breakdown_first
                    else "; breakdowns only."
                )
                + f" Showing {len(shown)}."
            ),
            rows=[
                {
                    "wo_number": w["wo_number"],
                    "equipment_tag": w["equipment_tag"],
                    "report_date": w["report_date"],
                    "work_type": w["work_type"],
                    "discipline": w["discipline"],
                    "breakdown": bool(w.get("breakdown")),
                    "problem_description": w["problem_description"],
                    "root_cause": w["root_cause"],
                    "corrective_action": w["corrective_action"],
                    "downtime_hours": w["downtime_hours"],
                    "total_cost_idr": w["total_cost_idr"],
                }
                for w in shown
            ],
            note="Source: Maintenance History (All Equipment).xlsx from the dataset.",
        )

    if kind == "recent":
        wos = registry.list_work_orders(
            conn, equipment_tag=tag, breakdown_only=("breakdown" in q)
        )
        recent = sorted(wos, key=lambda w: str(w.get("report_date") or ""))[-15:]
        if not recent:
            return StructuredAnswer(
                kind="recent",
                summary="No matching work order in this dataset.",
                rows=[],
            )
        newest = recent[-1]
        return StructuredAnswer(
            kind="recent",
            summary=(
                f"Most recent record for {tag or 'the plant'}: "
                f"{newest['wo_number']} on "
                f"{str(newest.get('report_date'))[:10]}"
                + (
                    f" - {newest.get('problem_description')}"
                    if newest.get("problem_description")
                    else ""
                )
                + f". Showing {len(recent)} of the latest."
            ),
            rows=[
                {
                    "wo_number": w["wo_number"],
                    "equipment_tag": w["equipment_tag"],
                    "report_date": w["report_date"],
                    "work_type": w["work_type"],
                    "breakdown": bool(w.get("breakdown")),
                    "problem_description": w["problem_description"],
                    "downtime_hours": w["downtime_hours"],
                }
                for w in recent
            ],
            note="Source: Maintenance History workbook.",
        )

    return None


def answer_parameter_value(
    conn: sqlite3.Connection, question: str, tag: str | None
) -> StructuredAnswer | None:
    """Jawab pertanyaan "berapa setpoint X" dari tabel document_parameters.

    Lebih bisa dipercayai daripada retrieval karena angkanya terukur dan punya
    sumber dokumen yang eksplisit - dan nilai ini juga yang jadi bahan deteksi
    konflik, jadi satu sumber kebenaran untuk angka batas keselamatan.
    """
    q = question.lower()
    requested: tuple[str, ...] = ()
    for keyword, name in (
        ("suction pressure", "suction pressure"),
        ("discharge pressure", "discharge pressure"),
        ("rated flow", "rated flow"),
        ("flow rate", "rated flow"),
        ("rated head", "rated head"),
        ("design pressure", "design pressure"),
        ("operating pressure", "operating pressure"),
        ("design temperature", "design temperature"),
        ("pumping temperature", "pumping temperature"),
        ("vibration", "vibration"),
        ("shaft speed", "shaft speed"),
        ("speed", "shaft speed"),
    ):
        if keyword in q:
            requested += (name,)

    # Setpoint trip: tag instrumen disebut eksplisit di pertanyaan.
    instrument_tags = [
        m.group(0).upper()
        for m in conflicts_mod.INSTRUMENT_TAG.finditer(question.upper())
        if conflicts_mod.is_instrument_tag(m.group(0), None)
    ]

    if not requested and not instrument_tags:
        return None

    clauses: list[str] = []
    args: list[Any] = []
    if requested:
        clauses.append("p.parameter IN (" + ",".join("?" * len(requested)) + ")")
        args.extend(requested)
    if instrument_tags:
        clauses.append(
            "p.parameter IN (" + ",".join("?" * len(instrument_tags)) + ")"
        )
        args.extend(instrument_tags)
    where = " OR ".join(clauses)
    if tag:
        # Prefix kolom wajib dipakai: `documents` juga punya kolom
        # equipment_tag, jadi `WHERE equipment_tag = ?` tanpa prefix
        # menghasilkan "ambiguous column name".
        where = f"({where}) AND p.equipment_tag = ?"
        args.append(tag)

    rows = [
        {
            "equipment_tag": r["equipment_tag"],
            "parameter": r["parameter"],
            "operator": r["operator"],
            "value": r["value"],
            "unit": r["unit"],
            "kind": r["kind"],
            "document": r["filename"],
            "doc_type": r["doc_type"],
            "revision": r["revision"],
            "approval_status": r["approval_status"],
            "raw": r["raw"],
        }
        for r in conn.execute(
            f"""SELECT p.doc_id, p.equipment_tag, p.parameter, p.value, p.unit,
                       p.operator, p.kind, p.raw,
                       d.filename, d.doc_type, d.revision, d.approval_status
                FROM document_parameters p JOIN documents d ON d.doc_id = p.doc_id
                WHERE {where}
                ORDER BY p.equipment_tag, p.parameter, p.value""",
            args,
        )
    ]
    if not rows:
        return StructuredAnswer(
            kind="parameter_value",
            summary=(
                "No document in the indexed dataset states that value"
                + (f" for {tag}" if tag else "")
                + ". I will not supply a value that no document contains."
            ),
            rows=[],
            note="This is an honest empty result, not a missing index.",
        )

    # Nilai yang sama sering muncul di banyak dokumen - PSLL-1201 < 0.5 barg
    # muncul di interlock dan 6 OPL. Menampilkan keenamnya sebagai kalimat
    # terpisah-six makes the summary read like a malfunction. Yang ditampilkan
    # satu baris per nilai unik, dengan hitungan dokumen sebagai buktinya.
    unique: dict[tuple[str, str, float, str], int] = {}
    for r in rows:
        key = (r["parameter"], r["operator"], float(r["value"]), r["unit"] or "")
        unique[key] = unique.get(key, 0) + 1

    parts: list[str] = []
    for (parameter, operator, value, unit), occurrences in list(unique.items())[:6]:
        formatted = (
            f"{value:g} {unit}".strip()
            if operator in ("=", "", None)
            else f"{operator} {value:g} {unit}".strip()
        )
        across = ""
        if occurrences > 1:
            across = f" (stated identically in {occurrences} documents)"
        parts.append(f"**{parameter}** = {formatted}{across}")
    remainder = len(unique) - 6
    return StructuredAnswer(
        kind="parameter_value",
        summary=(
            "Measured from the documents themselves"
            + (f" for {tag}" if tag else "")
            + ": "
            + "; ".join(parts)
            + (f", plus {remainder} other measured value(s)." if remainder > 0 else ".")
        ),
        rows=rows,
        note=(
            "Every value is read from a named document, with its revision and "
            "approval status. The same numbers feed the conflict detector, so "
            "there is a single source of truth for safety limits."
        ),
    )


# ------------------------------------------------------------------ -------
# Rangkuman dokumen tanpa LLM
# -----------------------------------------------------------------------


def compose_from_documents(question: str, hits: list[dict[str, Any]]) -> str:
    """Bentuk jawaban langsung dari chunk terambil, tanpa LLM.

    Dipakai saat tidak ada provider LLM yang terkonfigurasi, dan sebagai
    cadangan kalau panggilan LLM gagal. Jawaban ini sepenuhnya bisa
    ditelusuri: setiap kalimat berasal dari satu chunk yang ditampilkan
    berdampingan dengan sitasinya.
    """
    if not hits:
        return ""
    lines: list[str] = []
    seen_docs: list[str] = []
    for hit in hits:
        title = hit.get("title") or hit.get("filename")
        section = hit.get("section")
        label = f"{title}" + (f", section {section}" if section else "")
        if label in seen_docs:
            continue
        seen_docs.append(label)
        snippet = re.sub(r"\s+", " ", (hit.get("content") or "")).strip()
        snippet = re.sub(r"^[\u25a0\u25cf\-\*\d\.\s]+", "", snippet)[:520]
        if not snippet:
            continue
        lines.append(f"**{label}**\n{snippet}")
        if len(lines) >= 3:
            break
    if not lines:
        return ""
    return "\n\n".join(lines)


# ------------------------------------------------------------------ -------
# Prompt untuk LLM (opsional)
# --------------------------------------------------------------------------


SYSTEM_PROMPT = """You are TrustHUB, an assistant for LLDPE plant engineers.

Rules you must follow:
1. Answer ONLY from the numbered sources below. Never add a number, tag, setpoint,
   date, name, or procedure step that is not present in a source.
2. Cite every claim with its source number, like [1] or [2][3].
3. If the sources do not contain the answer, say so plainly and stop. Do not fill
   the gap from general knowledge, and do not guess which document might contain
   it.
4. If a value, setpoint, or threshold appears in the sources, reproduce it
   EXACTLY, including units and comparison direction. Never round or convert.
5. Do not paraphrase procedural steps, safety precautions, or isolation
   instructions. Quote them.
6. If sources disagree, do not pick a winner. State both values with their source
   numbers and say a subject-matter expert must decide.
7. Be concise. An engineer is reading this between job steps.
8. Mention that this dataset is CALIBER sample data if it is relevant."""


def build_prompt(question: str, hits: list[dict[str, Any]]) -> str:
    context = retrieval.context_for_answer(hits)
    return (
        f"SOURCES\n{context}\n\n"
        f"QUESTION\n{question}\n\n"
        "ANSWER (cite sources, refuse if unsourced):"
    )


# ------------------------------------------------------------------ -------
# API utama
# -----------------------------------------------------------------------


@dataclass
class Answer:
    question: str
    kind: str
    answer: str
    badge: str
    trust_score: float
    refused: bool = False
    refusal_reason: str | None = None
    equipment_tag: str | None = None
    cross_unit: bool = False
    verbatim: bool = False
    sources: list[dict[str, Any]] = field(default_factory=list)
    signals: list[dict[str, Any]] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    structured: dict[str, Any] | None = None
    related_failures: list[dict[str, Any]] = field(default_factory=list)
    failure_memory_available: bool = False
    llm_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "kind": self.kind,
            "answer": self.answer,
            "badge": self.badge,
            "trust_score": self.trust_score,
            "refused": self.refused,
            "refusal_reason": self.refusal_reason,
            "equipment_tag": self.equipment_tag,
            "cross_unit": self.cross_unit,
            "verbatim": self.verbatim,
            "sources": self.sources,
            "signals": self.signals,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "structured": self.structured,
            "related_failures": self.related_failures,
            "failure_memory_available": self.failure_memory_available,
            "llm_used": self.llm_used,
            "badge_style": trust.badge_style(self.badge),
            "weights": trust.WEIGHTS,
        }


def _source_payload(hit: dict[str, Any]) -> dict[str, Any]:
    """Satu entri sitasi yang bisa diklik frontend."""
    return {
        "doc_id": hit.get("doc_id"),
        "filename": hit.get("filename"),
        "title": hit.get("title"),
        "doc_type": hit.get("doc_type"),
        "section": hit.get("section"),
        "revision": hit.get("revision"),
        "approval_status": hit.get("approval_status"),
        "approval_raw": hit.get("approval_raw"),
        "effective_date": hit.get("effective_date"),
        "approved_by": hit.get("approved_by"),
        "equipment_tag": hit.get("equipment_tag"),
        "is_safety_critical": bool(hit.get("is_safety_critical")),
        "score": round(float(hit.get("score", 0.0)), 3),
        "excerpt": re.sub(r"\s+", " ", hit.get("content") or "").strip()[:400],
    }


def answer(
    conn: sqlite3.Connection,
    question: str,
    *,
    llm: Callable[[str, str], str] | None = None,
    top_k: int = 6,
    role: str = "viewer",
) -> Answer:
    """Jawab satu pertanyaan dengan bukti, badge, dan sitasi.

    `llm` adalah fungsi (system_prompt, user_prompt) -> teks. Kalau None atau
    kalau fungsinya melempar exception, jawaban disusun dari dokumen saja.
    """
    question = (question or "").strip()
    tags = [e["equipment_tag"] for e in registry.list_equipment(conn)]
    known_refs = registry.known_references(conn)
    kind = classify(question)

    # Cakupan equipment: hanya dari penyebutan eksplisit.
    tag = retrieval.detect_equipment_tag(question, tags)
    cross_unit = retrieval.is_cross_unit_question(question)

    # ---- 1. Sumber terstruktur ------------------------------------------------
    structured: StructuredAnswer | None = None
    if kind == "parameter_value":
        structured = answer_parameter_value(conn, question, tag)
    else:
        structured = answer_from_maintenance(conn, kind, question, tag)

    # ---- 2. Retrieval dokumen -------------------------------------------------
    hits = retrieval.search(conn, question, equipment_tag=tag, top_k=top_k)
    if not hits and not tag:
        # Mode lintas unit boleh memakai dokumen semua unit. Mode tag-tunggal
        # sengaja tidak: lebih baik tidak menjawab daripada memberi prosedur
        # unit yang salah.
        hits = retrieval.search(conn, question, equipment_tag=None, top_k=top_k)

    # ---- 3. Guardrail ---------------------------------------------------------
    refuse, reason = trust.should_refuse(
        question, hits, known_tags=tags, known_refs=known_refs
    )
    if refuse:
        # Kalau pertanyaan agregat punya jawaban dari tabel, tetap dijawab -
        # misalnya "total downtime" tidak akan punya chunk dokumen yang cocok,
        # tapi angkanya benar-benar ada di maintenance history.
        if structured and structured.rows and kind != "document":
            verdict = trust.evaluate(
                question, hits, [], question_tag=tag
            )
            registry.log_answer(
                conn, question, tag, verdict.badge, verdict.score,
                ["maintenance_history"], role,
            )
            return Answer(
                question=question,
                kind=kind,
                answer=structured.summary
                + (f"\n\n{structured.note}" if structured.note else ""),
                badge=trust.VERIFY,
                trust_score=0.6,
                equipment_tag=tag,
                cross_unit=cross_unit,
                sources=[],
                reasons=[
                    "answered from the structured maintenance history table, "
                    "not from document text",
                    "no document in the corpus matches this question, so the "
                    "citation panel is intentionally empty",
                ],
                structured=structured.to_dict(),
            )
        return _refusal(
            conn, question, tag, cross_unit, kind, reason or "No source.",
            structured=structured, role=role,
        )

    # ---- 4. Penilaian trust ---------------------------------------------------
    conflicts = conflicts_mod.conflicts_for_documents(
        conn, [h["doc_id"] for h in hits]
    )
    verdict = trust.evaluate(question, hits, [], conflicts, question_tag=tag)

    # ---- 5. Menyusun jawaban --------------------------------------------------
    if structured and structured.rows:
        answer_text = structured.summary
        if structured.note:
            answer_text += f"\n\n{structured.note}"
        # Kutipan dari dokumen ditambahkan sebagai blok terpisah. Ditempelkan
        # tanpa newline, kalimat "Source: ...xlsx**Interlock Logic Diagram**"
        # akan terbaca sebagai satu kalimat rusak.
        excerpt = compose_from_documents(question, hits[:2])
        if excerpt:
            answer_text += f"\n\n{excerpt}"
    else:
        answer_text = ""
        llm_used = False
        if llm is not None:
            try:
                answer_text = llm(SYSTEM_PROMPT, build_prompt(question, hits))
                llm_used = bool(answer_text and answer_text.strip())
            except Exception:  # noqa: BLE001 - kegagalan LLM tidak boleh mematikan demo
                answer_text = ""
        if not answer_text:
            answer_text = compose_from_documents(question, hits)
            if not answer_text:
                return _refusal(
                    conn, question, tag, cross_unit, kind,
                    "The indexed documents mention this topic but do not "
                    "contain enough text to answer from.",
                    role=role,
                )
        else:
            llm_used = True

    # Failure Memory: lampirkan breakdown yang terkait kalau tersedia.
    related_failures: list[dict[str, Any]] = []
    failure_available = False
    if tag:
        from .failure_memory import failure_memory

        memory = failure_memory(conn, equipment_tag=tag)
        failure_available = bool(memory)
        needle = set(re.findall(r"[a-z]{4,}", question.lower()))
        scored = []
        for wo in memory:
            blob = " ".join(
                str(wo.get(k) or "")
                for k in ("problem_description", "root_cause", "corrective_action")
            ).lower()
            overlap = len(needle & set(re.findall(r"[a-z]{4,}", blob)))
            if overlap:
                scored.append((overlap, wo))
        scored.sort(key=lambda x: -x[0])
        related_failures = [
            {
                "wo_number": wo["wo_number"],
                "report_date": wo["report_date"],
                "root_cause": wo["root_cause"],
                "corrective_action": wo["corrective_action"],
                "downtime_hours": wo["downtime_hours"],
                "total_cost_idr": wo["total_cost_idr"],
                "linked_opls": [
                    {"opl_no": l["opl_no"], "title": l["title"], "score": l["score"]}
                    for l in wo["linked_opls"][:3]
                ],
            }
            for _, wo in scored[:3]
        ]

    registry.log_answer(
        conn, question, tag, verdict.badge, verdict.score,
        [h.get("filename") for h in hits], role,
    )

    return Answer(
        question=question,
        kind=kind,
        answer=answer_text,
        badge=verdict.badge,
        trust_score=verdict.score,
        equipment_tag=tag,
        cross_unit=cross_unit,
        verbatim=verdict.verbatim_required,
        sources=[_source_payload(h) for h in hits],
        signals=[s.to_dict() for s in verdict.signals],
        reasons=verdict.reasons,
        warnings=verdict.warnings,
        structured=structured.to_dict() if structured else None,
        related_failures=related_failures,
        failure_memory_available=failure_available,
        llm_used=llm_used if not structured or not structured.rows else False,
    )


def _refusal(
    conn: sqlite3.Connection,
    question: str,
    tag: str | None,
    cross_unit: bool,
    kind: str,
    reason: str,
    *,
    structured: StructuredAnswer | None = None,
    role: str = "viewer",
) -> Answer:
    """Bentuk jawaban penolakan.

    Penolakan tetap dinilai dan tetap dicatat di audit log. Pertanyaan yang
    dijawab sistem dengan "tidak tahu" adalah jejak audit yang berguna - dari
    situ terlihat pola pertanyaan yang knowledge hub belum bisa layani.
    """
    registry.log_answer(conn, question, tag, trust.DO_NOT_EXECUTE, None, [], role)
    return Answer(
        question=question,
        kind=kind,
        answer=reason,
        badge=trust.DO_NOT_EXECUTE,
        trust_score=0.0,
        refused=True,
        refusal_reason=reason,
        equipment_tag=tag,
        cross_unit=cross_unit,
        sources=[],
        reasons=[reason, "refusal is logged for review"],
        structured=structured.to_dict() if structured else None,
    )