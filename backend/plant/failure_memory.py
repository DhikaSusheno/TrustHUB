"""Failure Memory: hubungkan breakdown nyata ke prosedur yang relevan.

Case Book menyebut komponen ke-6 "Failure Memory System **and Recommendation**".
Modul ini menjawab bagian "system"-nya: setiap breakdown di maintenance history
dicocokkan ke OPL yang membahas gejala serupa, sehingga teknisi mendapat
"ini pernah terjadi, ini yang dilakukan, ini procedurnya".

Yang dibedakan dari sekadar pencarian teks: pencocokan dihitung antara
`Root_Cause` + `Corrective_Action` dari work order dan section
"5. COMMON PROBLEMS & TROUBLESHOOTING" milik OPL equipment yang sama. Field itu
memang berisi Symptom / Likely Cause / Action dalam bahasa yang sama dengan
kolom work order - jadi ini bukan tebakan, tapi dua tabel yang memang dibuat
saling melengkapi oleh penulis dataset.

Rekomendasi tindakan diambil dari OPL terkait (bukan dari LLM), supaya bisa
disorot sebagai "documented action" dan tetap dapat sumber yang bisa diklik.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

# Stopword bahasa Inggris + kata kerja umum yang muncul di SEMUA baris
# maintenance history, sehingga tidak bisa membedakan satu penyebab dari
# yang lain. Tanpa filter ini, hampir setiap work order akan "cocok" dengan OPL
# mana pun dan linkage-nya jadi tidak berguna.
STOPWORDS = frozenset("""
a an the and or of to in on at for with by from as is are was were be been being
it its this that these those there here not no non has have had do does did
will would shall should can could may might must
after before during within without into onto from up down out off over under
one two three four five six seven eight nine ten
new old good bad normal abnormal issue issues problem problems
found finding was were due caused cause caused by
de component unit system equipment area job work
and per each all any some more most other another such same
main about between both during few further only own too very
""".split())

# Istilah domain yang terlalu umum untuk dipakai sebagai bukti kecocokan
# sendiri - muncul hampir di semua OPL, jadi tidak membedakan.
GENERIC_DOMAIN = frozenset("""
check verify confirm ensure ensure remove clean replace renew adjust inspect
examine record monitor trend normal abnormal alarm trip set valve sensor
pressure temperature level flow vibration current voltage
operator technician supervisor manager engineer
problem action cause symptom
""".split())

MIN_OVERLAP = 3  # token bukti minimum untuk dianggap(match)


def _tokens(text: str) -> set[str]:
    """Token bermakna: panjang >= 4, alphabetic-ish, bukan stopword."""
    raw = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {
        t for t in raw
        if len(t) >= 4 and t not in STOPWORDS and not t.isdigit()
    }


def _evidence_tokens(text: str) -> set[str]:
    """Token yang punya daya pembeda: buang juga istilah domain generik."""
    return _tokens(text) - GENERIC_DOMAIN


def _score(query: set[str], candidate: set[str]) -> tuple[int, list[str]]:
    shared = query & candidate
    return len(shared), sorted(shared)


def build_failure_memory(conn: sqlite3.Connection) -> int:
    """Bangun tabel failure_links untuk seluruh breakdown.

    Hanya work order dengan `Breakdown = Yes` yang dilink - event planned dan
    predictive bukan failure memory. Link hanya dicari di OPL equipment yang
    sama, karena prosedur unit lain tidak bisa dieksekusi pada unit ini.
    """
    conn.execute("DELETE FROM failure_links")

    opls = conn.execute(
        """SELECT c.doc_id, c.section, c.content, d.equipment_tag, d.title,
                  d.opl_no, d.filename
           FROM doc_chunks c
           JOIN documents d ON d.doc_id = c.doc_id
           WHERE d.doc_type = 'opl' AND c.section = 'troubleshooting'"""
    ).fetchall()
    if not opls:
        return 0

    # Cache token per OPL supaya tidak dihitung ulang untuk 31 work order.
    opl_tokens: dict[str, set[str]] = {
        row["doc_id"]: _evidence_tokens(row["content"]) for row in opls
    }
    opl_by_tag: dict[str, list[sqlite3.Row]] = {}
    for row in opls:
        opl_by_tag.setdefault(row["equipment_tag"], []).append(row)

    breakdowns = conn.execute(
        """SELECT * FROM work_orders WHERE breakdown = 1
           ORDER BY equipment_tag, report_date"""
    ).fetchall()

    linked = 0
    for wo in breakdowns:
        tag = wo["equipment_tag"]
        candidates = opl_by_tag.get(tag, [])
        if not candidates:
            continue
        # Gabungkan root cause + corrective action + problem: ketiganya
        # penting karena gejala sering ditulis di problem, penyebab di root
        # cause, dan solusinya hanya ada di corrective action.
        wo_tokens = _evidence_tokens(
            " ".join(
                str(wo[k] or "")
                for k in ("problem_description", "root_cause", "corrective_action")
            )
        )
        if not wo_tokens:
            continue
        for opl in candidates:
            overlap, shared = _score(wo_tokens, opl_tokens[opl["doc_id"]])
            if overlap < MIN_OVERLAP:
                continue
            # Overlap dinormalisasi dengan min() agar OPL panjang tidak otomatis
            # menang hanya karena panjangnya.
            denom = min(len(wo_tokens), len(opl_tokens[opl["doc_id"]])) or 1
            score = overlap / denom
            conn.execute(
                """INSERT OR REPLACE INTO failure_links
                   (wo_number, doc_id, section, overlap, score)
                   VALUES (?,?,?,?,?)""",
                (wo["wo_number"], opl["doc_id"], opl["section"], overlap, score),
            )
            linked += 1
    conn.commit()
    return linked


def failure_memory(
    conn: sqlite3.Connection,
    equipment_tag: str | None = None,
    include_planned: bool = False,
) -> list[dict[str, Any]]:
    """Failure Memory per equipment, lengkap dengan OPL dan tindakan terdokumentasi."""
    sql = """SELECT w.* FROM work_orders w"""
    args: list[Any] = []
    where = []
    if not include_planned:
        where.append("w.breakdown = 1")
    if equipment_tag:
        where.append("w.equipment_tag = ?")
        args.append(equipment_tag)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY w.equipment_tag, w.report_date"

    out: list[dict[str, Any]] = []
    for wo in conn.execute(sql, args).fetchall():
        links = conn.execute(
            """SELECT f.wo_number, f.doc_id, f.overlap, f.score,
                      d.title, d.opl_no, d.filename, d.approval_status,
                      d.revision, d.approved_by
               FROM failure_links f JOIN documents d ON d.doc_id = f.doc_id
               WHERE f.wo_number = ? ORDER BY f.score DESC""",
            (wo["wo_number"],),
        ).fetchall()
        record = dict(wo)
        record["linked_opls"] = [dict(l) for l in links]
        record["failure_mode"] = _failure_mode(wo["root_cause"], wo["problem_description"])
        out.append(record)
    return out


def _failure_mode(root_cause: str | None, problem: str | None) -> str:
    """Klasifikasi mode kegagalan sederhana dari teks root cause.

    Ini kategorisasi leksikal untuk navigasi dan agregasi, bukan diagnosis.
    Tags berasal dari kata kunci yang benar-benar muncul di dataset; kalau
    tidak ada yang cocok, mode-nya `unclassified` dan UI harus honestly
    menampilkannya sebagai belum terklasifikasi.
    """
    text = f"{root_cause or ''} {problem or ''}".lower()
    buckets = [
        ("packing_seal", ("packing", "gasket", "seal", "o-ring", "v-ring")),
        ("fouling_deposit", ("fouling", "fouled", "deposit", "fines", "sludge")),
        ("wear", ("worn", "wear", "spalling", "eroded", "beyond limit")),
        ("instrument_drift", ("drift", "calibrat", "sensor", "cell drift")),
        ("misalignment_coupling", ("misalign", "align", "coupling")),
        ("valve_actuator", ("positioner", "actuator", "stem seized", "seat")),
        ("electrical", ("overload", "wiring", "insulation", "thermography")),
        ("corrosion", ("corrosion", "wall thickness", "corroded")),
        ("obstruction", ("plugged", "blocked", "restricted", "bridle legs")),
    ]
    for mode, keys in buckets:
        if any(k in text for k in keys):
            return mode
    return "unclassified"


def recommendation_for(
    conn: sqlite3.Connection, wo_number: str
) -> dict[str, Any]:
    """Rekomendasi tindakan terdokumentasi untuk satu breakdown.

    Sumbernya OPL yang ter-link, BUKAN LLM - supaya tindakan yang ditampilkan
    bisa ditelusuri ke dokumen aslinya beserta approver-nya.
    """
    wo = conn.execute(
        "SELECT * FROM work_orders WHERE wo_number = ?", (wo_number,)
    ).fetchone()
    if not wo:
        return {"ok": False, "reason": f"work order {wo_number} not found"}

    rows = conn.execute(
        """SELECT f.score, d.doc_id, d.opl_no, d.title, d.filename,
                  d.approval_status, d.revision, d.approved_by, c.content
           FROM failure_links f
           JOIN documents d ON d.doc_id = f.doc_id
           JOIN doc_chunks c ON c.doc_id = f.doc_id AND c.section = f.section
           WHERE f.wo_number = ? ORDER BY f.score DESC""",
        (wo_number,),
    ).fetchall()

    if not rows:
        return {
            "ok": True,
            "wo_number": wo_number,
            "equipment_tag": wo["equipment_tag"],
            "root_cause": wo["root_cause"],
            "corrective_action_taken": wo["corrective_action"],
            "recommended_action": None,
            "note": (
                "No OPL in this dataset covers this failure mode. The action "
                "below is what was actually done in this work order, not a "
                "recommendation from a procedure."
            ),
        }

    top = rows[0]
    return {
        "ok": True,
        "wo_number": wo_number,
        "equipment_tag": wo["equipment_tag"],
        "root_cause": wo["root_cause"],
        "corrective_action_taken": wo["corrective_action"],
        "recommended_action": top["content"],
        "source": {
            "doc_id": top["doc_id"],
            "opl_no": top["opl_no"],
            "title": top["title"],
            "filename": top["filename"],
            "approval_status": top["approval_status"],
            "revision": top["revision"],
            "approved_by": top["approved_by"],
        },
        "match_score": top["score"],
        "also_see": [
            {
                "doc_id": r["doc_id"],
                "opl_no": r["opl_no"],
                "title": r["title"],
                "score": r["score"],
            }
            for r in rows[1:4]
        ],
    }


def failure_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Agregasi Failure Memory untuk slide 'data we used'."""
    per_tag: dict[str, dict[str, Any]] = {}
    for wo in conn.execute("SELECT * FROM work_orders WHERE breakdown = 1"):
        tag = wo["equipment_tag"]
        bucket = per_tag.setdefault(
            tag,
            {
                "equipment_tag": tag,
                "breakdown_count": 0,
                "downtime_hours": 0.0,
                "total_cost_idr": 0.0,
                "linked_count": 0,
                "modes": {},
            },
        )
        bucket["breakdown_count"] += 1
        bucket["downtime_hours"] += float(wo["downtime_hours"] or 0.0)
        bucket["total_cost_idr"] += float(wo["total_cost_idr"] or 0.0)
        mode = _failure_mode(wo["root_cause"], wo["problem_description"])
        bucket["modes"][mode] = bucket["modes"].get(mode, 0) + 1

    for row in conn.execute(
        "SELECT w.equipment_tag AS tag, COUNT(*) AS n FROM failure_links f "
        "JOIN work_orders w ON w.wo_number = f.wo_number GROUP BY w.equipment_tag"
    ):
        if row["tag"] in per_tag:
            per_tag[row["tag"]]["linked_count"] = row["n"]

    total = conn.execute(
        """SELECT COUNT(*) AS n,
                  COALESCE(SUM(downtime_hours),0) AS dt,
                  COALESCE(SUM(total_cost_idr),0) AS cost
           FROM work_orders WHERE breakdown = 1"""
    ).fetchone()
    linked_wo = conn.execute(
        "SELECT COUNT(DISTINCT wo_number) AS n FROM failure_links"
    ).fetchone()

    return {
        "breakdown_total": total["n"],
        "breakdown_downtime_hours": total["dt"],
        "breakdown_cost_idr": total["cost"],
        "breakdowns_with_linked_opl": linked_wo["n"],
        "coverage_pct": (
            round(100.0 * linked_wo["n"] / total["n"], 1) if total["n"] else 0.0
        ),
        "per_equipment": sorted(
            per_tag.values(), key=lambda b: -b["downtime_hours"]
        ),
    }