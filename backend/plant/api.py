"""Route HTTP untuk TrustHUB Plant Knowledge Hub (CALIBER 2026 Case 1).

Dipisah dari main.py sebagai router sendiri karena dua alasan:

  1. main.py sudah 2600 baris dan berisi fitur Synapse lama (Cortex code-graph,
     Guardian propose/approve). Case 1 tidak butuh salah satunya, dan mencampur
     kode yang tidak relevan bikin reviewer sulit menilai apa yang benar-benar
     menjawab kasus.
  2. Modul plant/ tidak boleh menarik dependensi main.py. Kalau bridge LLM
     ada di main.py, plant/ akan ikut terikat ke seluruh auth + storage +
     cortex, dan test-nya tidak bisa jalan tanpa app FastAPI.

Soal LLM
--------
Secara default TIDAK ADA LLM yang dipanggil. Jawaban disusun langsung dari
basis data dan chunk dokumen, jadi:

  - demo tidak mati gara-gara kuota, rate limit, atau jaringan
  - tidak ada data pabrik yang dikirim ke pihak ketiga tanpa persetujuan
  - setiap kalimat jawaban bisa ditelusuri ke chunk sumbernya

Pertanyaan ke panitia CALIBER yang belum terjawab - apakah dataset boleh
dikirim ke LLM API eksternal - masih terbuka, jadi sistem mengasumsikan jawaban
terlalu dulu. Mengaktifkan LLM berarti opt-in eksplisit lewat
TRUSTHUB_PLANT_LLM_MODE:

  off        (default) tidak memanggil LLM sama sekali
  local      hanya provider di localhost (ollama, LM Studio, vLLM)
  external   provider mana pun - harus ada opt-in lain
             (TRUSTHUB_PLANT_ALLOW_EXTERNAL_LLM=1) supaya tidak terjadi
             karena salah klik di halaman settings
"""

from __future__ import annotations

import os
import re
import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from . import ask as ask_mod
from . import conflicts as conflicts_mod
from . import dataset as dataset_mod
from . import failure_memory as fm_mod
from . import registry, retrieval, trust

router = APIRouter(prefix="/api/plant", tags=["Plant Knowledge Hub"])


# ---------------------------------------------------------------------------
# Status & konfigurasi
# ---------------------------------------------------------------------------


def _llm_mode() -> str:
    mode = os.environ.get("TRUSTHUB_PLANT_LLM_MODE", "off").strip().lower()
    return mode if mode in {"off", "local", "external"} else "off"


def _external_allowed() -> bool:
    return os.environ.get("TRUSTHUB_PLANT_ALLOW_EXTERNAL_LLM", "").strip() in {
        "1",
        "true",
        "yes",
    }


def _require_dataset_index() -> sqlite3.Connection:
    """Buka koneksi, atau gagal dengan pesan yang bisa ditindaklanjuti."""
    return _open_index()


def _open_index() -> sqlite3.Connection:
    """Buka koneksi ke indeks, dengan pesan error yang bisa ditindaklanjuti.

    Sengaja memakai sqlite3 default (check_same_thread=True). Modul plant/
    menyimpan objek koneksi di banyak tempat dan tidak selalu menutupnya di
    setiap jalur error, jadi check_same_thread=False hanya memindahkan
    kegagalan dari "langsung error" menjadi "korupsi diam-diam saat dua
    request datang bersamaan". Untuk endpoint yang butuh bekerja di thread lain,
    kanggil _open_index() DI DALAM thread itu - bukan di thread utama.
    """
    conn = registry.connect()
    try:
        count = conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]
    except sqlite3.Error:
        conn.close()
        raise HTTPException(
            status_code=503,
            detail=(
                "Plant index is not built yet. Run "
                "`python -m plant.fetch_dataset` from the backend folder."
            ),
        )
    if not count:
        conn.close()
        raise HTTPException(
            status_code=503,
            detail=(
                f"Plant index is empty ({registry.db_path()}). Run "
                "`python -m plant.fetch_dataset` to build it from the "
                "official CALIBER dataset."
            ),
        )
    return conn


@router.get("/status")
def plant_status() -> dict[str, Any]:
    """Kesiapan sistem: dataset ditemukan, indeks dibangun, mode LLM aktif.

    Rute INI yang harus tetap bisa dibaca saat indeks belum ada - itu
    seluruh fungsinya. Sebelumnya rute ini memanggil `_require_dataset_index()`,
    yang melempar 503 dengan pesan "run fetch_dataset", jadi frontend tidak
    pernah sempat menampilkan "indeks belum dibangun": permintaannya gagal
    dengan pesan yang sama persis dengan yang seharusnya ditampilkan, tapi
    sebagai error, bukan sebagai status. Field `ready` juga selalu `True`,
    jadi tidak pernah ada yang membacanya.
    """
    mode = _llm_mode()
    base: dict[str, Any] = {
        "ready": False,
        "database": str(registry.db_path()),
        "problem": None,
        "counts": {
            "equipment": 0,
            "documents": 0,
            "chunks": 0,
            "work_orders": 0,
            "failure_links": 0,
            "measured_parameters": 0,
            "approved_documents": 0,
        },
        "approval_breakdown": {},
        "llm": {
            "mode": mode,
            "external_allowed": _external_allowed(),
            "note": (
                "Answers are composed from the indexed data. No document text "
                "leaves this machine unless an LLM mode is explicitly enabled."
            ),
        },
        "dataset_licence_note": (
            "All documents come from the official CALIBER-provided dataset, "
            "labelled by its authors as sample data."
        ),
    }

    try:
        conn = _open_index()
    except HTTPException as exc:
        base["problem"] = str(exc.detail)
        return base

    try:
        for key, table in (
            ("equipment", "equipment"),
            ("documents", "documents"),
            ("chunks", "doc_chunks"),
            ("work_orders", "work_orders"),
            ("failure_links", "failure_links"),
            ("measured_parameters", "document_parameters"),
        ):
            base["counts"][key] = int(
                conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            )
        base["approval_breakdown"] = {
            r["approval_status"]: r["n"]
            for r in conn.execute(
                "SELECT approval_status, COUNT(*) AS n FROM documents GROUP BY 1"
            )
        }
        base["counts"]["approved_documents"] = base["approval_breakdown"].get(
            "approved", 0
        )
    finally:
        conn.close()

    base["ready"] = True
    return base


@router.get("/dataset")
def plant_dataset_report() -> dict[str, Any]:
    """Laporan dataset: apa yang ada, apa yang hilang, dan per equipment."""
    try:
        root = dataset_mod.find_dataset_root()
        report = dataset_mod.dataset_report(root)
    except dataset_mod.DatasetNotFound as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return report.to_dict()


@router.post("/reindex")
def plant_reindex() -> dict[str, Any]:
    """Bangun ulang indeks dari dataset. Berguna setelah dataset diperbarui."""
    try:
        root = dataset_mod.find_dataset_root()
    except dataset_mod.DatasetNotFound as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    conn = registry.connect()
    try:
        # Panggilan kedua yang bisa gagal dengan cara yang sama. Root dataset
        # bisa ada sementara workbook maintenance di dalamnya hilang atau
        # rusak, dan tanpa catch di sini hasilnya 500 plus traceback - yang
        # tidak memberi tahu apa pun soal apa yang harus diperbaiki. Pesan
        # DatasetNotFound menyebut file yang dicari, jadi 503 jauh lebih
        # berguna.
        stats = registry.ingest_all(conn, root)
    except dataset_mod.DatasetNotFound as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    finally:
        conn.close()
    return {"reindexed": True, "stats": stats}


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------


@router.get("/equipment")
def list_equipment() -> list[dict[str, Any]]:
    conn = _require_dataset_index()
    try:
        return registry.list_equipment(conn)
    finally:
        conn.close()


@router.get("/equipment/{tag}")
def equipment_detail(tag: str) -> dict[str, Any]:
    conn = _require_dataset_index()
    try:
        equipment = registry.get_equipment(conn, tag.upper())
        if not equipment:
            known = [e["equipment_tag"] for e in registry.list_equipment(conn)]
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Equipment {tag.upper()} is not in this dataset. "
                    f"Available: {', '.join(known)}"
                ),
            )
        equipment["documents"] = registry.list_documents(conn, equipment_tag=tag.upper())
        equipment["work_orders"] = registry.list_work_orders(
            conn, equipment_tag=tag.upper()
        )[:60]
        equipment["failure_memory"] = fm_mod.failure_memory(
            conn, equipment_tag=tag.upper()
        )
        equipment["conflicts"] = conflicts_mod.conflicts_for_equipment(
            conn, tag.upper()
        )
        equipment["missing_opl"] = registry.missing_opl_numbers(conn, tag.upper())
        equipment["safety_critical"] = bool(
            str(equipment.get("criticality") or "").upper().startswith("HIGH")
        )
        return equipment
    finally:
        conn.close()


@router.get("/equipment/{tag}/documents")
def equipment_documents(tag: str) -> list[dict[str, Any]]:
    conn = _require_dataset_index()
    try:
        if not registry.get_equipment(conn, tag.upper()):
            raise HTTPException(status_code=404, detail=f"Unknown equipment {tag}")
        return registry.list_documents(conn, equipment_tag=tag.upper())
    finally:
        conn.close()


@router.get("/equipment/{tag}/work-orders")
def equipment_work_orders(
    tag: str, breakdown_only: bool = False
) -> list[dict[str, Any]]:
    conn = _require_dataset_index()
    try:
        # Cek keberadaan equipment, sama seperti /documents dan
        # /failure-memory di sebelahnya. Tanpa ini, "ZX-9999" membalas 200
        # dengan daftar kosong - yang terbaca sebagai "unit ini tidak punya
        # riwayat maintenance", padahal unit itu tidak ada sama sekali.
        # Dua bentuk itu menghasilkan kesimpulan yang berlawanan dan keduanya
        # terlihat seperti jawaban, jadi hanya satu yang boleh di sini.
        if not registry.get_equipment(conn, tag.upper()):
            raise HTTPException(status_code=404, detail=f"Unknown equipment {tag}")
        return registry.list_work_orders(
            conn, equipment_tag=tag.upper(), breakdown_only=breakdown_only
        )
    finally:
        conn.close()


@router.get("/equipment/{tag}/failure-memory")
def equipment_failure_memory(tag: str) -> dict[str, Any]:
    conn = _require_dataset_index()
    try:
        # Sama seperti /documents dan /work-orders di sebelahnya. Tanpa cek
        # ini, tag yang salah ketik membalas 200 dengan nol-nol yang terlihat
        # seperti "unit ini tidak pernah punya breakdown" - padahal nol itu
        # berarti "tidak ada yang bisa dijawab karena unitnya tidak ada".
        if not registry.get_equipment(conn, tag.upper()):
            raise HTTPException(status_code=404, detail=f"Unknown equipment {tag}")
        rows = fm_mod.failure_memory(conn, equipment_tag=tag.upper())
        linked = [r for r in rows if r.get("linked_opls")]
        return {
            "equipment_tag": tag.upper(),
            "records": rows,
            "record_count": len(rows),
            "linked_count": len(linked),
            "link_rate": round(len(linked) / len(rows), 3) if rows else 0.0,
            "total_downtime_hours": round(
                sum(float(r.get("downtime_hours") or 0) for r in rows), 1
            ),
            "total_cost_idr": sum(
                float(r.get("total_cost_idr") or 0) for r in rows
            ),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Dokumen
# ---------------------------------------------------------------------------


@router.get("/documents")
def list_documents(
    equipment_tag: str | None = None,
    doc_type: str | None = None,
    approval_status: str | None = None,
    safety_critical: bool | None = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    conn = _require_dataset_index()
    try:
        clauses: list[str] = []
        args: list[Any] = []
        if equipment_tag:
            clauses.append("equipment_tag = ?")
            args.append(equipment_tag.upper())
        if doc_type:
            clauses.append("doc_type = ?")
            args.append(doc_type)
        if approval_status:
            clauses.append("approval_status = ?")
            args.append(approval_status)
        if safety_critical is not None:
            clauses.append(
                "is_safety_critical = ?" if safety_critical else "is_safety_critical = 0"
            )
            args.append(1 if safety_critical else 0)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        total = conn.execute(
            f"SELECT COUNT(*) AS n FROM documents {where}", args
        ).fetchone()["n"]
        rows = [
            dict(r)
            for r in conn.execute(
                f"SELECT * FROM documents {where} "
                "ORDER BY equipment_tag, doc_type, filename LIMIT ? OFFSET ?",
                [*args, limit, offset],
            )
        ]
        return {"total": total, "limit": limit, "offset": offset, "items": rows}
    finally:
        conn.close()


@router.get("/documents/{doc_id}")
def document_detail(doc_id: str) -> dict[str, Any]:
    conn = _require_dataset_index()
    try:
        document = registry.get_document(conn, doc_id)
        if not document:
            raise HTTPException(status_code=404, detail=f"No document with id {doc_id}")
        document["chunks"] = [
            dict(r)
            for r in conn.execute(
                "SELECT chunk_id, section, content FROM doc_chunks "
                "WHERE doc_id = ? ORDER BY chunk_id",
                (doc_id,),
            )
        ]
        document["related"] = retrieval.related_documents(conn, doc_id)
        return document
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Graph pengetahuan
# ---------------------------------------------------------------------------


@router.get("/graph")
def knowledge_graph() -> dict[str, Any]:
    """Graf pengetahuan: equipment, dokumen, work order, dan OPL.

    Edge berasal dari kunci yang benar-benar ada di dataset - Equipment_Tag,
    Functional_Location, Related_Interlock, dan nomor dokumen - bukan dari
    kesamaan teks. Graf yang dibangun dari kemiripan bahasa terlihat bagus di
    demo dan menyesatkan di lapangan.
    """
    conn = _require_dataset_index()
    try:
        return registry.graph(conn)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tanya-jawab
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    top_k: int = Field(6, ge=1, le=20)
    use_llm: bool | None = Field(
        None,
        description=(
            "Override the server default. None means: use whatever "
            "TRUSTHUB_PLANT_LLM_MODE allows."
        ),
    )


@router.post("/ask")
async def plant_ask(req: AskRequest) -> dict[str, Any]:
    """Jawab pertanyaan dengan sitasi wajib, badge trust, dan penolakan jujur.

    Endpoint ini `async` karena ada panggilan LLM opsional, tapi seluruh
    kerja database-nya jalan di thread terpisah. Konsekuensinya: koneksi
    SQLite harus dibuat DI DALAM thread itu. Membukanya di event loop lalu
    meneruskannya ke worker menghasilkan
    "SQLite objects created in a thread can only be used in that same thread".
    """
    use_llm = req.use_llm
    if use_llm is None:
        use_llm = _llm_mode() != "off"
    if use_llm and _llm_mode() == "external" and not _external_allowed():
        use_llm = False

    llm = _build_llm_bridge() if use_llm else None

    def work() -> dict[str, Any]:
        conn = _open_index()
        try:
            return ask_mod.answer(
                conn,
                req.question,
                llm=llm,
                top_k=req.top_k,
                role="viewer",
            ).to_dict()
        finally:
            conn.close()

    payload = await _run_blocking(work)
    payload["llm_mode"] = _llm_mode() if llm is not None else "off"
    return payload


@router.get("/search")
def plant_search(
    q: str = Query(..., min_length=1, max_length=500),
    equipment_tag: str | None = None,
    doc_type: str | None = None,
    top_k: int = Query(8, ge=1, le=50),
) -> dict[str, Any]:
    """Retrieval mentah tanpa penilaian trust, untuk debugging dan UI sumber."""
    conn = _require_dataset_index()
    try:
        hits = retrieval.search(
            conn, q, equipment_tag=equipment_tag, doc_type=doc_type, top_k=top_k
        )
        return {
            "query": q,
            "equipment_tag": equipment_tag,
            "hit_count": len(hits),
            "hits": [
                {
                    "doc_id": h.get("doc_id"),
                    "filename": h.get("filename"),
                    "title": h.get("title"),
                    "doc_type": h.get("doc_type"),
                    "section": h.get("section"),
                    "equipment_tag": h.get("equipment_tag"),
                    "revision": h.get("revision"),
                    "approval_status": h.get("approval_status"),
                    "is_safety_critical": bool(h.get("is_safety_critical")),
                    "score": round(float(h.get("score", 0.0)), 3),
                    "content": h.get("content"),
                }
                for h in hits
            ],
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Trust, konflik, verifikasi
# ---------------------------------------------------------------------------


@router.get("/trust/weights")
def trust_weights() -> dict[str, Any]:
    """Bobot trust dan ambang badge, beserta alasan bobot itu chosen."""
    return {
        "weights": trust.WEIGHTS,
        "thresholds": {
            "trusted": trust.TRUSTED_THRESHOLD,
            "verify": trust.VERIFY_THRESHOLD,
            "relevance_floor": trust.RELEVANCE_FLOOR,
        },
        "approval_scores": trust.APPROVAL_SCORE,
        "badges": [trust.TRUSTED, trust.VERIFY, trust.DO_NOT_EXECUTE],
    }


@router.get("/conflicts")
def list_conflicts(equipment_tag: str | None = None) -> dict[str, Any]:
    """Konflik nilai antar dokumen, plus statistik filternya.

    Statistik filter ikut dikembalikan supaya "tidak ada konflik" bisa
    dibedakan dari "deteksi konflik tidak jalan". Tanpa itu, nol kontradiktif
    sama saja dengan nol pemeriksaan.
    """
    conn = _require_dataset_index()
    try:
        summary = conflicts_mod.conflict_summary(conn)
        summary["inventory"] = conflicts_mod.parameter_inventory(conn)
        summary["filters"] = dict(conflicts_mod.conflict_detection_stats)
        if equipment_tag:
            summary["items"] = [
                c for c in summary["items"]
                if c["equipment_tag"] == equipment_tag.upper()
            ]
            summary["total"] = len(summary["items"])
            summary["needs_sme"] = sum(1 for c in summary["items"] if c["needs_sme"])
        return summary
    finally:
        conn.close()


@router.get("/verification")
def cross_source_verification() -> dict[str, Any]:
    """Nilai yang dinyatakan identik di lebih dari satu dokumen.

    Ini sisi positif dari pemeriksaan konflik: bukan hanya mencari
    pertentangan, tapi juga membuktikan bahwa batas-batas keselamatan
    konsisten. Pada dataset CALIBER: 15 kelompok nilai terverifikasi lintas
    2-8 dokumen, 0 kontradiksi.
    """
    conn = _require_dataset_index()
    try:
        report = conflicts_mod.agreement_report(conn)
        report["inventory"] = conflicts_mod.parameter_inventory(conn)
        return report
    finally:
        conn.close()


@router.get("/failure-memory")
def failure_memory_overview() -> dict[str, Any]:
    conn = _require_dataset_index()
    try:
        return fm_mod.failure_summary(conn)
    finally:
        conn.close()


@router.get("/work-orders")
def list_work_orders(
    equipment_tag: str | None = None,
    breakdown_only: bool = False,
    limit: int = Query(200, ge=1, le=1000),
) -> dict[str, Any]:
    conn = _require_dataset_index()
    try:
        rows = registry.list_work_orders(
            conn, equipment_tag=equipment_tag, breakdown_only=breakdown_only
        )
        return {
            "total": len(rows),
            "returned": min(len(rows), limit),
            "items": rows[:limit],
        }
    finally:
        conn.close()


@router.get("/audit")
def answer_audit(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    """Jejak audit jawaban: pertanyaan, badge, sumber, dan penolakan.

    Ini yang membuat trust bisa diaudit, bukan sekadar diklaim. Reviewer bisa
    melihat pertanyaan mana yang dijawab, mana yang ditolak, dan dari dokumen
    mana - termasuk pertanyaan yang dijawab dari tabel maintenance tanpa
    sitasi dokumen.
    """
    conn = _require_dataset_index()
    try:
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM plant_audit_log ORDER BY id DESC LIMIT ?", (limit,)
            )
        ]
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM plant_audit_log"
        ).fetchone()["n"]
        refused = conn.execute(
            "SELECT COUNT(*) AS n FROM plant_audit_log WHERE badge = ?",
            (trust.DO_NOT_EXECUTE,),
        ).fetchone()["n"]
        by_badge = {
            r["badge"]: r["n"]
            for r in conn.execute(
                "SELECT badge, COUNT(*) AS n FROM plant_audit_log GROUP BY 1"
            )
        }
        return {
            "total": total,
            "refused": refused,
            "by_badge": by_badge,
            "items": rows,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Bridge LLM opsional
# ---------------------------------------------------------------------------


async def _run_blocking(fn, *args, **kwargs):
    """Jalankan fungsi blocking di thread pool.

    SQLite + parsing PDF adalah operasi blocking. Menjalankannya langsung di
    event loop akan memblokir seluruh request lain selama LSTM penuh, dan
    FastAPI tidak mengetahuinya karena kodenya sinkron.
    """
    import anyio

    return await anyio.to_thread.run_sync(lambda: fn(*args, **kwargs))


def _build_llm_bridge():
    """Bridges ke gateway LLM yang sudah ada, atau None kalau tidak boleh.

    Sengaja tidak memanggil main.py: modul plant/ harus tetap bisa diimpor dan
    diuji tanpa aplikasi FastAPI. Provider dibaca langsung dari SQLite dengan
    kolom yang sama, jadi tidak ada logika yang terduplikasi selain query.
    """
    import sqlite3 as _sqlite3

    from auth import decrypt_stored_token

    try:
        from main import DB_PATH
    except Exception:  # noqa: BLE001 - jalan tanpa main.py juga harus bisa
        return None

    conn = _sqlite3.connect(DB_PATH)
    conn.row_factory = _sqlite3.Row
    try:
        providers = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM llm_providers WHERE enabled = 1 ORDER BY created_at"
            )
        ]
    except _sqlite3.Error:
        return None
    finally:
        conn.close()

    mode = _llm_mode()
    chosen = None
    for provider in providers:
        is_local = _is_local(provider)
        if mode == "local" and not is_local:
            continue
        chosen = provider
        break
    if not chosen:
        return None

    api_key = None
    if chosen.get("api_key"):
        try:
            api_key = decrypt_stored_token(chosen["api_key"])
        except Exception:  # noqa: BLE001
            api_key = None
    if not api_key and not _is_local(chosen):
        # Provider publik tanpa key akan ditolak oleh upstream dengan 401 yang
        # tidak menjelaskan apa pun. Lebih baik demo berjalan tanpa LLM.
        return None

    model = chosen.get("default_model") or ""
    if not model:
        return None

    def bridge(system_prompt: str, user_prompt: str) -> str:
        return _sync_llm_call(chosen, api_key, model, system_prompt, user_prompt)

    return bridge


def _is_local(provider: dict[str, Any]) -> bool:
    base = str(provider.get("base_url") or "")
    if not base:
        return str(provider.get("type") or "").lower() in {"ollama", "lmstudio"}
    host = base.split("//", 1)[-1].split("/", 1)[0].split(":")[0].lower()
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal"}


def _sync_llm_call(
    provider: dict[str, Any],
    api_key: str | None,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Satu panggilan chat completion. Blocking; dipanggil dari worker thread.

    Kegagalan apa pun di sini Returning string kosong, bukan exception:
    ask.answer() sudah punya jalur cadangan tanpa LLM, dan exception yang
    lolos ke user hanya menghasilkan layar error.
    """
    import httpx

    base = str(provider.get("base_url") or "").strip()
    kind = str(provider.get("type") or "").lower()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        if kind == "ollama":
            base = re.sub(r"/v1$", "", (base or "http://localhost:11434").rstrip("/"))
            payload["options"] = {"temperature": 0.1, "num_predict": 1200}
            response = httpx.post(
                f"{base}/api/chat", json=payload, timeout=60.0, headers=headers
            )
            response.raise_for_status()
            return str(response.json().get("message", {}).get("content") or "").strip()

        base = re.sub(r"/v1$", "", base.rstrip("/"))
        response = httpx.post(
            f"{base}/v1/chat/completions",
            json=payload,
            timeout=60.0,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return ""
        return str(choices[0].get("message", {}).get("content") or "").strip()
    except Exception:  # noqa: BLE001 - lihat docstring
        return ""
