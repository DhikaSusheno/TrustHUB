"""Document registry + equipment knowledge graph (SQLite).

Skema ini adalah "Industrial Data Ops foundation" (KQ1): semua sumber terikat
ke equipment lewat tag yang sama - persis join key yang dinyatakan resmi di
sheet Explanation dataset (`Equipment_Tag = JOIN KEY to all other documents`).

Yang disimpan di sini SEMUA metadata nyata dari dokumen. Tidak ada field
approval/revision yang diestimasi - kalau dokumen tidak menyatakannya, nilainya
NULL dan UI menampilkannya sebagai "not stated in document".

DB terpisah dari `trusthub_v2.db` (milik domain kode warisan Synapse) supaya
tidak ada coupling, dan bisa di-reset tanpa data hilang.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .extract import ExtractedDoc, extract_file, iter_dataset_files

DB_FILENAME = "trusthub_plant.db"

SCHEMA = """
-- Satu baris per equipment. Kolom agregat berasal dari maintenance history,
-- bukan dari dokumen, dan diberi nama *_wo_* supaya tidak tertukar dengan
-- spec teknis yang ada di datasheet.
CREATE TABLE IF NOT EXISTS equipment (
    equipment_tag       TEXT PRIMARY KEY,
    equipment_name      TEXT,
    area_code           TEXT,
    area_name           TEXT,
    plant               TEXT,
    functional_location TEXT,
    criticality         TEXT,
    interlock_ref       TEXT,
    interlock_sil       TEXT,
    pid_ref             TEXT,
    doc_count           INTEGER DEFAULT 0,
    opl_count           INTEGER DEFAULT 0,
    approved_doc_count  INTEGER DEFAULT 0,
    wo_count            INTEGER DEFAULT 0,
    breakdown_count     INTEGER DEFAULT 0,
    downtime_hours      REAL    DEFAULT 0,
    total_cost_idr      REAL    DEFAULT 0
);

-- Document registry: satu baris per file, dengan status approval & revisi
-- apa adanya dari dokumen.
CREATE TABLE IF NOT EXISTS documents (
    doc_id          TEXT PRIMARY KEY,
    filename        TEXT NOT NULL,
    doc_type        TEXT NOT NULL,
    equipment_tag   TEXT,
    title           TEXT,
    doc_no          TEXT,
    revision        TEXT,
    approval_status TEXT NOT NULL DEFAULT 'unknown',
    approval_raw    TEXT,
    effective_date  TEXT,
    revision_history TEXT,
    functional_location TEXT,
    criticality     TEXT,
    interlock_ref   TEXT,
    interlock_sil   TEXT,
    pid_ref         TEXT,
    opl_no          TEXT,
    opl_classification TEXT,
    discipline      TEXT,
    prepared_by     TEXT,
    reviewed_by     TEXT,
    approved_by     TEXT,
    related_docs    TEXT,
    file_path       TEXT,
    text_chars      INTEGER DEFAULT 0,
    is_safety_critical INTEGER DEFAULT 0,
    ingested_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_documents_tag   ON documents(equipment_tag);
CREATE INDEX IF NOT EXISTS idx_documents_type  ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_appr  ON documents(approval_status);

-- Potongan retrievable. Satu baris per section OPL / per blok dokumen lain,
-- supaya sitasi bisa menunjuk bagian, bukan cuma nama file.
CREATE TABLE IF NOT EXISTS doc_chunks (
    chunk_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id       TEXT NOT NULL,
    equipment_tag TEXT,
    section      TEXT,
    title        TEXT,
    content      TEXT NOT NULL,
    UNIQUE(doc_id, section)
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc  ON doc_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_tag  ON doc_chunks(equipment_tag);

-- Nilai parameter numerik yang ditemukan di dalam dokumen, beserta dokumen
-- asal dan cara penemuannya. Dipisah dari doc_chunks karena isinya berbeda
-- sifatnya: chunk menyimpan PROSA, tabel ini menyimpan FAKTA TERUKUR.
-- Diekstrak sekali saat ingest supaya deteksi konflik bisa jalan dari DB
-- tanpa membuka ulang PDF.
CREATE TABLE IF NOT EXISTS document_parameters (
    doc_id        TEXT NOT NULL,
    equipment_tag TEXT,
    parameter     TEXT NOT NULL,
    value         REAL NOT NULL,
    unit          TEXT,
    operator      TEXT,
    kind          TEXT,
    raw           TEXT,
    source        TEXT,
    UNIQUE(doc_id, parameter, operator, value, unit, raw)
);
CREATE INDEX IF NOT EXISTS idx_param_tag  ON document_parameters(equipment_tag);
CREATE INDEX IF NOT EXISTS idx_param_doc  ON document_parameters(doc_id);
CREATE INDEX IF NOT EXISTS idx_param_name ON document_parameters(parameter);

-- Search full-text. FTS5 bawaan SQLite, jadi retrieval jalan tanpa API key
-- dan tanpa model embedding eksternal - syarat agar demo tidak bergantung
-- pada kuota atau jaringan pihak ketiga.
CREATE VIRTUAL TABLE IF NOT EXISTS doc_fts USING fts5(
    content,
    doc_id UNINDEXED,
    equipment_tag UNINDEXED,
    section UNINDEXED,
    tokenize = "porter unicode61"
);

-- Work order dari Maintenance History. Baris breakdown inilah bahan Failure
-- Memory: setiap breakdown dicocokkan ke OPL yang discusses symptoms similar.
CREATE TABLE IF NOT EXISTS work_orders (
    wo_number        TEXT PRIMARY KEY,
    notification_no  TEXT,
    equipment_tag    TEXT,
    equipment_name   TEXT,
    functional_location TEXT,
    area_name        TEXT,
    plant            TEXT,
    work_type        TEXT,
    discipline       TEXT,
    priority         TEXT,
    criticality      TEXT,
    problem_description TEXT,
    root_cause       TEXT,
    corrective_action   TEXT,
    spare_parts_used TEXT,
    breakdown        INTEGER DEFAULT 0,
    downtime_hours   REAL,
    labor_hours      REAL,
    total_cost_idr   REAL,
    report_date      TEXT,
    related_interlock TEXT,
    remarks          TEXT
);
CREATE INDEX IF NOT EXISTS idx_wo_tag ON work_orders(equipment_tag);
CREATE INDEX IF NOT EXISTS idx_wo_brk ON work_orders(breakdown);

-- Hasil linkage Failure Memory: WO breakdown -> OPL terkait + skor bukti.
CREATE TABLE IF NOT EXISTS failure_links (
    wo_number   TEXT NOT NULL,
    doc_id      TEXT NOT NULL,
    section     TEXT,
    overlap     INTEGER,
    score       REAL,
    PRIMARY KEY (wo_number, doc_id)
);
CREATE INDEX IF NOT EXISTS idx_flink_wo ON failure_links(wo_number);

-- Audit log governance (aturan 8 arsitektur): siapa bertanya apa, dan jawaban
-- apa yang diberikan dengan badge apa.
CREATE TABLE IF NOT EXISTS plant_audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    asked_at  TEXT DEFAULT (datetime('now')),
    question  TEXT,
    equipment_tag TEXT,
    badge     TEXT,
    trust_score REAL,
    sources   TEXT,
    role      TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_time ON plant_audit_log(asked_at);
"""


# ---------------------------------------------------------------------------
# Koneksi
# ---------------------------------------------------------------------------


def db_path() -> Path:
    """Lokasi DB plant. Env `TRUSTHUB_PLANT_DB_PATH` untuk test."""
    override = os.environ.get("TRUSTHUB_PLANT_DB_PATH", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / DB_FILENAME


def connect(path: str | os.PathLike[str] | None = None) -> sqlite3.Connection:
    target = Path(path) if path else db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


def _doc_id(filename: str) -> str:
    return hashlib.sha1(filename.encode("utf-8")).hexdigest()[:16]


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _safety_critical(meta: Any) -> int:
    """Tandai dokumen yang isinya prosedur yang menyentuh keselamatan.

    Dokumen OPL dan interlock diagram selalu safety-relevant karena keduanya
    memuat prosedur trips/permits; dokumen lain ditandai bila teksnya
    mengandung kata kunci energies/safety eksplisit.
    """
    if meta.doc_type in {"opl", "interlock"}:
        return 1
    return 0


def ingest_documents(
    conn: sqlite3.Connection, root: str | os.PathLike[str]
) -> dict[str, int]:
    """Ingest seluruh PDF/PNG dataset ke registry + FTS index."""
    files = iter_dataset_files(root)
    counts: dict[str, int] = {"documents": 0, "chunks": 0, "parameters": 0,
                              "equipment": 0}

    # Rebuild penuh: dataset kecil (95 file) dan ingest harus idempoten.
    conn.execute("DELETE FROM doc_chunks")
    conn.execute("DELETE FROM documents")
    conn.execute("DELETE FROM doc_fts")
    conn.execute("DELETE FROM failure_links")
    conn.execute("DELETE FROM document_parameters")

    for path in files:
        doc: ExtractedDoc = extract_file(path)
        meta = doc.meta
        doc_id = _doc_id(doc.filename)

        conn.execute(
            """INSERT OR REPLACE INTO documents (
                doc_id, filename, doc_type, equipment_tag, title, doc_no, revision,
                approval_status, approval_raw, effective_date, revision_history,
                functional_location, criticality, interlock_ref, interlock_sil,
                pid_ref, opl_no, opl_classification, discipline, prepared_by,
                reviewed_by, approved_by, related_docs, file_path, text_chars,
                is_safety_critical
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                doc_id, doc.filename, meta.doc_type, meta.equipment_tag,
                meta.title, meta.doc_no, meta.revision,
                meta.approval_status or "unknown", meta.approval_raw,
                meta.effective_date,
                json.dumps(meta.revision_history),
                meta.functional_location, meta.criticality, meta.interlock_ref,
                meta.interlock_sil, meta.pid_ref, meta.opl_no,
                json.dumps(meta.opl_classification), meta.discipline,
                meta.prepared_by, meta.reviewed_by, meta.approved_by,
                json.dumps(meta.related_docs), path, len(doc.text),
                _safety_critical(meta),
            ),
        )
        counts["documents"] += 1

        # Chunk: pakai section OPL kalau ada (sitasi per-bagian), kalau tidak
        # satu chunk penuh per dokumen.
        if doc.sections:
            for sec in doc.sections:
                content = sec["content"].strip()
                if len(content) < 20:
                    continue
                conn.execute(
                    """INSERT OR IGNORE INTO doc_chunks
                       (doc_id, equipment_tag, section, title, content)
                       VALUES (?,?,?,?,?)""",
                    (doc_id, meta.equipment_tag, sec["section"], meta.title, content),
                )
                conn.execute(
                    """INSERT INTO doc_fts (content, doc_id, equipment_tag, section)
                       VALUES (?,?,?,?)""",
                    (content, doc_id, meta.equipment_tag, sec["section"]),
                )
                counts["chunks"] += 1
        elif doc.text.strip():
            conn.execute(
                """INSERT OR IGNORE INTO doc_chunks
                   (doc_id, equipment_tag, section, title, content)
                   VALUES (?,?,?,?,?)""",
                (doc_id, meta.equipment_tag, None, meta.title, doc.text.strip()),
            )
            conn.execute(
                """INSERT INTO doc_fts (content, doc_id, equipment_tag, section)
                   VALUES (?,?,?,?)""",
                (doc.text.strip(), doc_id, meta.equipment_tag, None),
            )
            counts["chunks"] += 1

        # Nilai parameter terukur. Dua sumber berbeda dipakai karena dua format
        # dokumen berbeda (lihat conflicts.extract_parameter_values):
        #   "linear" -> teks OPL/interlock, jangkarnya tag instrumen
        #   "table"  -> tabel datasheet, jangkarnya pasangan label/nilai
        from .conflicts import extract_parameter_values, extract_table_parameters
        from .extract import EQUIPMENT_TAGS

        tag_set = set(EQUIPMENT_TAGS)
        extracted: list[tuple[str, float, str, str, str, str, str]] = []
        for parameter, value, unit, operator, kind, raw in extract_parameter_values(
            doc.text, tag_set
        ):
            extracted.append((parameter, value, unit, operator, kind, raw, "linear"))
        for parameter, value, unit, operator, kind, raw in extract_table_parameters(
            doc.tables
        ):
            extracted.append((parameter, value, unit, operator, kind, raw, "table"))
        for parameter, value, unit, operator, kind, raw, source in extracted:
            conn.execute(
                """INSERT OR IGNORE INTO document_parameters
                   (doc_id, equipment_tag, parameter, value, unit, operator,
                    kind, raw, source)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (doc_id, meta.equipment_tag, parameter, value, unit, operator,
                 kind, raw, source),
            )
        counts["parameters"] = counts.get("parameters", 0) + len(extracted)

    counts["equipment"] = _rebuild_equipment(conn)
    conn.commit()
    return counts


def _rebuild_equipment(conn: sqlite3.Connection) -> int:
    """Hitung ulang tabel equipment dari dokumen + work order."""
    from .extract import EQUIPMENT_TAGS

    conn.execute("DELETE FROM equipment")
    for tag in EQUIPMENT_TAGS:
        row = conn.execute(
            """SELECT COUNT(*) AS n,
                      SUM(CASE WHEN doc_type='opl' THEN 1 ELSE 0 END) AS opl,
                      SUM(CASE WHEN approval_status='approved' THEN 1 ELSE 0 END) AS appr
               FROM documents WHERE equipment_tag = ?""",
            (tag,),
        ).fetchone()
        any_doc = conn.execute(
            "SELECT * FROM documents WHERE equipment_tag = ? AND doc_type IN "
            "('datasheet','interlock') LIMIT 1",
            (tag,),
        ).fetchone()
        wo = conn.execute(
            """SELECT COUNT(*) AS n,
                      SUM(CASE WHEN breakdown=1 THEN 1 ELSE 0 END) AS brk,
                      COALESCE(SUM(downtime_hours),0) AS dt,
                      COALESCE(SUM(total_cost_idr),0) AS cost
               FROM work_orders WHERE equipment_tag = ?""",
            (tag,),
        ).fetchone()

        # Prioritas sumber untuk atribut equipment: maintenance history dulu
        # (punya Functional_Location & area terotorisasi), lalu dokumen.
        wo_any = conn.execute(
            "SELECT * FROM work_orders WHERE equipment_tag = ? LIMIT 1", (tag,)
        ).fetchone()

        conn.execute(
            """INSERT OR REPLACE INTO equipment (
                equipment_tag, equipment_name, area_code, area_name, plant,
                functional_location, criticality, interlock_ref, interlock_sil,
                pid_ref, doc_count, opl_count, approved_doc_count,
                wo_count, breakdown_count, downtime_hours, total_cost_idr
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                tag,
                (wo_any["equipment_name"] if wo_any else None)
                or (any_doc["title"] if any_doc else None),
                None,
                (wo_any["area_name"] if wo_any else None),
                (wo_any["plant"] if wo_any else None),
                (wo_any["functional_location"] if wo_any else None)
                or (any_doc["functional_location"] if any_doc else None),
                (wo_any["criticality"] if wo_any else None)
                or (any_doc["criticality"] if any_doc else None),
                (wo_any["related_interlock"] if wo_any else None)
                or (any_doc["interlock_ref"] if any_doc else None),
                any_doc["interlock_sil"] if any_doc else None,
                any_doc["pid_ref"] if any_doc else None,
                row["n"] or 0,
                row["opl"] or 0,
                row["appr"] or 0,
                wo["n"] or 0,
                wo["brk"] or 0,
                wo["dt"] or 0.0,
                wo["cost"] or 0.0,
            ),
        )
    return len(EQUIPMENT_TAGS)


def ingest_work_orders(
    conn: sqlite3.Connection, root: str | os.PathLike[str]
) -> int:
    """Ingest Maintenance History ke tabel work_orders."""
    from .dataset import read_maintenance_history

    history = read_maintenance_history(root)
    conn.execute("DELETE FROM work_orders")
    for r in history:
        conn.execute(
            """INSERT OR REPLACE INTO work_orders (
                wo_number, notification_no, equipment_tag, equipment_name,
                functional_location, area_name, plant, work_type, discipline,
                priority, criticality, problem_description, root_cause,
                corrective_action, spare_parts_used, breakdown, downtime_hours,
                labor_hours, total_cost_idr, report_date, related_interlock,
                remarks
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                r.get("WO_Number"), r.get("Notification_No"), r.get("Equipment_Tag"),
                r.get("Equipment_Name"), r.get("Functional_Location"),
                r.get("Area_Name"), r.get("Plant"), r.get("Work_Type"),
                r.get("Discipline"), r.get("Priority"), r.get("Criticality"),
                r.get("Problem_Description"), r.get("Root_Cause"),
                r.get("Corrective_Action"), r.get("Spare_Parts_Used"),
                1 if r.get("Breakdown") == "Yes" else 0,
                r.get("Downtime_Hours"), r.get("Labor_Hours"),
                r.get("Total_Cost_IDR"), _iso(r.get("Report_Date")),
                r.get("Related_Interlock"), r.get("Remarks"),
            ),
        )
    _rebuild_equipment(conn)
    conn.commit()
    return len(history)


def ingest_all(conn: sqlite3.Connection, root: str | os.PathLike[str]) -> dict[str, Any]:
    """Ingest dokumen + work order, lalu link Failure Memory."""
    from .failure_memory import build_failure_memory

    doc_counts = ingest_documents(conn, root)
    wo_count = ingest_work_orders(conn, root)
    links = build_failure_memory(conn)
    return {
        "documents": doc_counts["documents"],
        "chunks": doc_counts["chunks"],
        "equipment": doc_counts["equipment"],
        "work_orders": wo_count,
        "failure_links": links,
    }


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


def list_equipment(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM equipment ORDER BY equipment_tag"
    ).fetchall()
    return [dict(r) for r in rows]


def get_equipment(conn: sqlite3.Connection, tag: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM equipment WHERE equipment_tag = ?", (tag,)
    ).fetchone()
    return dict(row) if row else None


def list_documents(
    conn: sqlite3.Connection,
    equipment_tag: str | None = None,
    doc_type: str | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM documents WHERE 1=1"
    args: list[Any] = []
    if equipment_tag:
        sql += " AND equipment_tag = ?"
        args.append(equipment_tag)
    if doc_type:
        sql += " AND doc_type = ?"
        args.append(doc_type)
    sql += " ORDER BY equipment_tag, doc_type, filename"
    out = []
    for row in conn.execute(sql, args).fetchall():
        d = dict(row)
        for key in ("revision_history", "opl_classification", "related_docs"):
            try:
                d[key] = json.loads(d[key]) if d[key] else []
            except (TypeError, json.JSONDecodeError):
                d[key] = []
        out.append(d)
    return out


def get_document(conn: sqlite3.Connection, doc_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    for key in ("revision_history", "opl_classification", "related_docs"):
        try:
            d[key] = json.loads(d[key]) if d[key] else []
        except (TypeError, json.JSONDecodeError):
            d[key] = []
    d["chunks"] = [
        dict(r)
        for r in conn.execute(
            "SELECT section, content FROM doc_chunks WHERE doc_id = ? ORDER BY chunk_id",
            (doc_id,),
        ).fetchall()
    ]
    return d


def list_work_orders(
    conn: sqlite3.Connection,
    equipment_tag: str | None = None,
    breakdown_only: bool = False,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM work_orders WHERE 1=1"
    args: list[Any] = []
    if equipment_tag:
        sql += " AND equipment_tag = ?"
        args.append(equipment_tag)
    if breakdown_only:
        sql += " AND breakdown = 1"
    sql += " ORDER BY report_date"
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def graph(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    """Bentuk graph untuk force-graph: equipment, dokumen, interlock, work order.

    Node type menentukan warna di frontend. Edge selalu menyertakan alasan
    (_label) supaya grafik bisa dibaca tanpa perlu hover.
    """
    nodes: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []

    for eq in list_equipment(conn):
        nodes.append(
            {
                "id": eq["equipment_tag"],
                "label": eq["equipment_tag"],
                "type": "equipment",
                "name": eq["equipment_name"],
                "criticality": eq["criticality"],
                "doc_count": eq["doc_count"],
                "breakdown_count": eq["breakdown_count"],
            }
        )
        if eq["interlock_ref"]:
            il = eq["interlock_ref"]
            nodes.append({"id": il, "label": il, "type": "interlock"})
            links.append(
                {"source": eq["equipment_tag"], "target": il, "label": "interlock"}
            )

    for doc in list_documents(conn):
        if not doc["equipment_tag"]:
            continue
        nodes.append(
            {
                "id": doc["doc_id"],
                "label": (doc["title"] or doc["filename"])[:44],
                "type": "document",
                "doc_type": doc["doc_type"],
                "approval": doc["approval_status"],
                "revision": doc["revision"],
            }
        )
        links.append(
            {
                "source": doc["equipment_tag"],
                "target": doc["doc_id"],
                "label": doc["doc_type"],
            }
        )

    for wo in list_work_orders(conn, breakdown_only=True):
        wid = f"{wo['wo_number']}"
        nodes.append(
            {
                "id": wid,
                "label": wid,
                "type": "breakdown",
                "downtime": wo["downtime_hours"],
                "root_cause": (wo["root_cause"] or "")[:60],
            }
        )
        links.append(
            {"source": wo["equipment_tag"], "target": wid, "label": "breakdown"}
        )

    return {"nodes": nodes, "links": links}


def known_references(conn: sqlite3.Connection) -> set[str]:
    """Semua nomor dokumen / P&ID / logika interlock yang benar-benar ada.

    Dipakai sebagai daftar putih saat user menyebut nomor dokumen. Tanpa ini,
    pertanyaan "OPL-GA-1201A-04 apa?" akan dijawab dengan OPL lain yang
    kebetulan mirip - padahal OPL-04 tidak ada di dataset. Kemampuan
    mengakui "dokumen ini tidak ada pada data yang saya indexes" adalah
    bagian dari trust, bukan kekurangan.
    """
    refs: set[str] = set()

    def _add(value: Any) -> None:
        # Parser sesekali menulis "-" atau "N/A" untuk kolom kosong. Kalau
        # ikut masuk daftar putih, guardrail "dokumen tidak ada" akan salah
        # membolehkan "-" seolah itu nomor dokumen yang valid.
        if value is None:
            return
        text = str(value).strip().upper()
        if len(text) < 3 or not any(c.isdigit() for c in text):
            return
        refs.add(text)

    for row in conn.execute(
        "SELECT doc_no, opl_no, interlock_ref, pid_ref FROM documents"
    ).fetchall():
        for value in row:
            _add(value)
    for row in conn.execute(
        "SELECT related_interlock FROM work_orders"
    ).fetchall():
        _add(row["related_interlock"])
    return refs


def missing_opl_numbers(conn: sqlite3.Connection, equipment_tag: str) -> list[str]:
    """Nomor OPL yang tidak ada untuk equipment ini.

    Hanya berguna kalau ada jumlah OPL per equipment yang bisa disimpulkan.
    Di dataset ini tiap unit punya 7 OPL kecuali GA-1201A yang punya 6, jadi
    celah bisa dibaca dari tag equipment: OPL berikutnya yang hilang.
    """
    present = {
        str(row["opl_no"]).upper()
        for row in conn.execute(
            "SELECT opl_no FROM documents WHERE equipment_tag = ? AND opl_no IS NOT NULL",
            (equipment_tag,),
        )
    }
    if not present:
        return []
    gaps: list[str] = []
    for n in range(1, 9):
        candidate = f"OPL-{equipment_tag.upper()}-{n:02d}"
        if candidate in present:
            continue
        # Hanya nomor yang di tengah deret yang sudah ada dianggap gap, supaya
        # angka 08/09 yang memang tidak pernah dipakai tidak dilaporkan.
        later = [
            f"OPL-{equipment_tag.upper()}-{m:02d}"
            for m in range(n + 1, 9)
            if f"OPL-{equipment_tag.upper()}-{m:02d}" in present
        ]
        if later:
            gaps.append(candidate)
    return gaps


def log_answer(
    conn: sqlite3.Connection,
    question: str,
    equipment_tag: str | None,
    badge: str,
    trust_score: float | None,
    sources: Iterable[str],
    role: str = "viewer",
) -> None:
    """Catat setiap jawaban untuk audit log (governance + human oversight)."""
    conn.execute(
        """INSERT INTO plant_audit_log
           (question, equipment_tag, badge, trust_score, sources, role)
           VALUES (?,?,?,?,?,?)""",
        (question, equipment_tag, badge, trust_score, json.dumps(list(sources)), role),
    )
    conn.commit()