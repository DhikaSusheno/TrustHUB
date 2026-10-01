"""Hybrid retrieval terfilter per equipment, tanpa API eksternal.

Kenapa tidak memakai embedding API sebagai default:
  - demo tidak boleh mati karena kuota atau jaringan (proposal 8.4)
  - belum diketahui apakah dataset boleh dikirim ke LLM API eksternal
    (unknown #4 di proposal, sudah ditanyakan ke panitia)
  - kunci soal "dataset to external API" masih terbuka, jadi lokal dulu

SQLite FTS5 memberi keyword retrieval + stemming (porter) + unicode61
case folding, yang untuk corpus dokumen teknik berbahasa Inggris ini sudah
cukup. Dipasangkan dengan filter tag equipment supaya retrieval tidak pernah
mencampur unit yang berbeda - inilah bedanya dari satu vector store global.

Kalau nanti embedding lokal ditambahkan, `search()` tetap jadi antarmuka yang
sama sehingga tidak ada yang perlu ditulis ulang di pemanggilnya.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

# Kata kunci yang menandai pertanyaan safety-critical. Kalau muncul di
# pertanyaan, guardrail verbatim di trust.py diaktifkan.
SAFETY_PATTERNS = re.compile(
    r"\b("
    r"interlock|trip|lockout|lock-out|loto|isolation|isolate|permit|"
    r"start-?up|startup|shut-?down|shutdown|emergency stop|e-?stop|"
    r"pressure|vent|bleed|drain|purge|energy|hazard|nitrogen|inert"
    r")\b",
    re.IGNORECASE,
)

# Istilah yang sering diketik engineer tapi tidak persis muncul di dokumen.
# Padanan ini membantu recall tanpa mengubah dokumen.
SYNONYMS = {
    "seal": ["mechanical seal", "gland", "flush"],
    "pump": ["pump", "casing", "impeller"],
    "vibration": ["vibration", "vshh", "vibration switch"],
    "temperature": ["temperature", "tshh", "thermocouple"],
    "bearing": ["bearing", "7310", "6310"],
    "compressor": ["compressor", "piston", "surge"],
    "valve": ["valve", "positioner", "actuator"],
    "gasket": ["gasket", "spiral wound", "seal face"],
    "fouling": ["fouling", "fouled", "deposit", "polymer fines"],
    "flow": ["flow", "flow rate", "min flow"],
    "pressure": ["pressure", "set point", "barg"],
    "packing": ["packing", "ptfe", "v-ring"],
    "alignment": ["alignment", "misalignment", "laser"],
}


def is_safety_critical(question: str) -> bool:
    """True kalau pertanyaan menyentuh prosedur yang berbahaya."""
    return bool(SAFETY_PATTERNS.search(question or ""))


def _expand(query: str) -> list[str]:
    """Tambah sinonim engineering ke query (dipakai untuk query FTS)."""
    terms = set()
    low = (query or "").lower()
    for key, words in SYNONYMS.items():
        if key in low:
            terms.update(words)
    return sorted(terms)


def _fts_query(query: str) -> str:
    """Ubah pertanyaan bebas menjadi query FTS5.

    Dua keputusan penting:

    1. Karakter khusus FTS (`AND`, `OR`, `-`, `"`, `*`, `NEAR`) dibuang, hanya
       token alfanumerik yang dipakai - kalau lolos, query bisa invalid atau
       berubah maksud.
    2. Operatornya OR, bukan AND. Pertanyaan engineer hampir selalu panjang
       ("what is the start-up and priming procedure for GA-1201A?") dan dalam
       bahasa alami tidak semua kata harus ada di dokumen yang sama. Dengan AND
       pertanyaan seperti ini mengembalikan nol hasil, lalu sistem akan
       menolak pertanyaan yang sebenarnya jelas ada jawabannya.
    """
    tokens = [t for t in re.findall(r"[A-Za-z0-9]+", query or "") if len(t) >= 2]
    if not tokens:
        return ""
    return " OR ".join(f'"{t}"' for t in tokens)


# Pola tag equipment: dua huruf, tanda hubung, 3-4 digit, opsional huruf
# (GA-1201A, DC-3401A, YD-2301). Dipakai untuk MENDETEKSI tag yang disebut
# user tapi tidak ada di dataset - kasus yang harus ditolak, bukan dijawab
# dengan dokumen unit lain.
TAG_PATTERN = re.compile(r"\b[A-Z]{2}-\d{3,4}[A-Z]?\b")

# Pertanyaan yang memang lintas equipment. Untuk pertanyaan seperti ini, tidak
# adanya tag BUKAN kekurangan - justru pengelompokan per unit adalah substansi
# pertanyaannya, jadi memaksakan satu tag akan menjawab dengan benar tetapi
# menyesatkan.
CROSS_UNIT_CUES = re.compile(
    r"\b("
    r"which (equipment|unit|pump|valve|compressor)|"
    r"what (equipment|unit)|"
    r"most (often|frequent|common|prone)|"
    r"compare|comparison|ranking|ranked|worst|best|"
    r"across (all|the|every)|all equipment|every equipment|"
    r"whole plant|plant-?wide|overall|"
    r"list (all|the) (equipment|unit)|summar(?:y|ise|ize)"
    r")\b",
    re.IGNORECASE,
)


def is_cross_unit_question(question: str) -> bool:
    """True kalau pertanyaannya memang bersifat lintas equipment."""
    return bool(CROSS_UNIT_CUES.search(question or ""))


def unknown_tags_mentioned(question: str, known_tags: list[str]) -> list[str]:
    """Tag berformat equipment yang disebut user tapi di luar dataset."""
    known = {t.upper() for t in known_tags}
    found = {m.group(0).upper() for m in TAG_PATTERN.finditer((question or "").upper())}
    return sorted(found - known)


# Identitas dokumen yang bisa disebut user. Ini penting karena dataset punya
# celah yang disengaja (OPL-GA-1201A-04 tidak ada) - sistem harus bisa tahu
# bahwa dokumen yang ditanyakan TIDAK ADA, bukan diam-diam menjawab dengan
# OPL lain yang kebetulan mirip.
#   OPL-GA-1201A-04        nomor one-point lesson
#   TJC-LLD-DS-GA-1201A    nomor dokumen (datasheet, GA, interlock)
#   TJC-LLD-PID-1201       referensi P&ID
#   SEQ-1201               nomor logika interlock
DOC_REF_PATTERNS = (
    re.compile(r"\bOPL-[A-Z]{2}-\d{4}[A-Z]?-\d{2}\b"),
    re.compile(r"\bTJC-[A-Z]{2,4}-[A-Z]{2,3}-[A-Z0-9]{3,4}[A-Z]?\b"),
    re.compile(r"\bSEQ-\d{4}\b"),
)


def extract_document_refs(question: str) -> list[str]:
    """Semua nomor dokumen/interlock yang disebut di pertanyaan."""
    refs: set[str] = set()
    q = question or ""
    for pattern in DOC_REF_PATTERNS:
        for m in pattern.finditer(q):
            refs.add(m.group(0).upper())
    return sorted(refs)


def detect_equipment_tag(
    question: str, known_tags: list[str], doc_hits: list[dict[str, Any]] | None = None
) -> str | None:
    """Resolusi tag equipment dari pertanyaan.

    HANYA dari penyebutan eksplisit di teks pertanyaan. Hasil retrieval
    sengaja TIDAK dipakai untuk menebak tag: FTS5 selalu mengembalikan hit
    untuk pertanyaan apa pun yang punya satu kata yang kebetulan muncul,
    sehingga menebak tag dari sana membuat "who is the CEO of Starbucks?"
    ter-answer sebagai pertanyaan tentang FA-8901. Kalau user tidak menyebut
    equipment, jawabannya adalah None = mode lintas unit, dan `evaluate()`
    yang menilai apakah bukti lintas unit itu cukup.

    Parameter `doc_hits` diterima demi kompatibilitas pemanggil lama, diabaikan.
    """
    upper = (question or "").upper()
    mentioned = [t for t in known_tags if t.upper() in upper]
    if len(mentioned) == 1:
        return mentioned[0]
    # Lebih dari satu tag disebut ("compare GA-1201A and EA-5601") = pertanyaan
    # lintas unit. Memilih salah satunya akan menjawab separuh pertanyaan dengan
    # keyakinan penuh, jadi dikembalikan None supaya mode lintas unit yang
    # dipakai - dan sinyal `agreement` akan menurunkan badge-nya karena sumber
    # dari unit berbeda tidak saling mengonfirmasi.
    return None


def search(
    conn: sqlite3.Connection,
    query: str,
    equipment_tag: str | None = None,
    doc_type: str | None = None,
    top_k: int = 8,
) -> list[dict[str, Any]]:
    """Cari chunk terbaik.

    Filter `equipment_tag` diterapkan sebagai filter TIGHT di SQL, bukan
    sesudahnya:equipment yang salah tidak boleh masuk kandidat even kalau
    skornya tinggi, karena memberi jawaban prosedur unit lain lebih berbahaya
    daripada tidak menjawab.
    """
    match = _fts_query(query)
    if not match:
        return []

    args: list[Any] = [match]
    sql = (
        "SELECT f.doc_id, f.equipment_tag, f.section, f.content, "
        "       bm25(doc_fts) AS rank "
        "FROM doc_fts f WHERE doc_fts MATCH ?"
    )
    if equipment_tag:
        sql += " AND f.equipment_tag = ?"
        args.append(equipment_tag)
    sql += " ORDER BY rank LIMIT ?"
    args.append(max(top_k * 4, 20))  # ambil lebih banyak untuk rerank di Python

    try:
        rows = conn.execute(sql, args).fetchall()
    except sqlite3.OperationalError:
        return []

    hits = [dict(r) for r in rows]
    if not hits and equipment_tag:
        # Equipment tertentu mungkin tidak punya dokumen yang cocok. Jangan
        # diam-diam pakai dokumen unit lain - kembalikan kosong supaya
        # pemanggil bisa menolak dengan jujur.
        return []

    # Rerank: BM25 + bonus kecocokan equipment + bonus keceocokan tag.
    expanded = set(_expand(query))
    low_query = (query or "").lower()
    for hit in hits:
        bonus = 0.0
        if equipment_tag and hit["equipment_tag"] == equipment_tag:
            bonus += 1.5
        content_low = hit["content"].lower()
        if expanded and any(w in content_low for w in expanded):
            bonus += 0.5
        if equipment_tag and equipment_tag in content_low:
            bonus += 0.5
        # bm25() mengembalikan nilai negatif (lebih kecil = lebih baik).
        hit["score"] = -float(hit["rank"]) + bonus
        hit.pop("rank", None)

    hits.sort(key=lambda h: h["score"], reverse=True)
    hits = hits[:top_k]

    # Lampirkan metadata dokumen supaya trust engine tidak perlu query lagi.
    if hits:
        doc_ids = list({h["doc_id"] for h in hits})
        placeholders = ",".join("?" * len(doc_ids))
        docs = {
            d["doc_id"]: d
            for d in conn.execute(
                f"SELECT doc_id, filename, doc_type, title, revision, "
                f"approval_status, approval_raw, effective_date, approved_by, "
                f"is_safety_critical FROM documents WHERE doc_id IN ({placeholders})",
                doc_ids,
            ).fetchall()
        }
        for hit in hits:
            hit.update(docs.get(hit["doc_id"], {}))
    return hits


def context_for_answer(hits: list[dict[str, Any]], max_chars: int = 6000) -> str:
    """Rakit konteks terformat untuk LLM.

    Setiap bagian diberi label sumber eksplisit supaya model bisa mengutip,
    dan penomoran langkah tetap utuh (satu baris = satu langkah).
    """
    parts: list[str] = []
    used = 0
    for i, hit in enumerate(hits, 1):
        header = (
            f"[SOURCE {i}] {hit.get('title') or hit.get('filename')} "
            f"({hit.get('doc_type')}, rev {hit.get('revision') or 'n/a'}, "
            f"approval: {hit.get('approval_status')})"
            + (f", section: {hit['section']}" if hit.get("section") else "")
        )
        block = f"{header}\n{hit['content']}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts)


def related_documents(conn: sqlite3.Connection, doc_id: str) -> list[dict[str, Any]]:
    """Dokumen lain yang mereferensikan hal sama (cross-reference eksplisit).

    Ini sumber sinyal "kesepakatan antar sumber" dan juga cara menemukan
    dokumen yang potentiellement bertentangan.
    """
    doc = conn.execute(
        "SELECT equipment_tag, pid_ref, interlock_ref FROM documents WHERE doc_id = ?",
        (doc_id,),
    ).fetchone()
    if not doc:
        return []

    sql = (
        "SELECT doc_id, filename, doc_type, title, revision, approval_status "
        "FROM documents WHERE equipment_tag = ? AND doc_id != ?"
    )
    args: list[Any] = [doc["equipment_tag"], doc_id]
    if doc["interlock_ref"]:
        sql += " AND interlock_ref = ?"
        args.append(doc["interlock_ref"])
    sql += " ORDER BY doc_type, filename LIMIT 20"
    return [dict(r) for r in conn.execute(sql, args).fetchall()]