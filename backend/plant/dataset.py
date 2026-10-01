"""Lokasi, validasi, dan statistik dataset CALIBER 2026 Case 1.

Dataset resmi milik panitia TIDAK boleh di-commit ke repo (lisensi + ukuran).
Modul ini mencarinya di beberapa lokasi yang masuk akal, memvalidasi
kelengkapan, dan menghitung statistik *dataset-derived* untuk deck.

Lokasi pencarian (berurutan):
  1. env `TRUSTHUB_DATASET_ROOT`
  2. argumen yang diberikan pemanggil
  3. `backend/dataset/` (lokasi hasil fetch_dataset.py)
  4. folder unduhan user, termasuk nama folder hasil unduh Case Book

Semua statistik di sini dihitung dari file aslinya, bukan angka yang diketik
manual, supaya tidak bisa menyimpang dari dataset.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .extract import EQUIPMENT_TAGS, iter_dataset_files

# Nama folder setelah unzip Case Book. Dipakai untuk mengenali root yang benar
# di dalam folder unduhan, karena ada satu level folderrapper dari ZIP.
_DATASET_FOLDER = "Case 1_ Manufacturing Knowledge Hub"
_MAINT_XLSX = "Maintenance History (All Equipment).xlsx"


class DatasetNotFound(RuntimeError):
    """Dataset CALIBER tidak ditemukan di lokasi yang diharapkan."""


# ---------------------------------------------------------------------------
# Penemuan
# ---------------------------------------------------------------------------


def _looks_like_dataset(path: Path) -> bool:
    """Suatu direktori dianggap dataset kalau punya dokumen per equipment.

    Ambangnya setengah dari jumlah tag yang dikenal, dengan lantai 1. Tanpa
    lantai itu, satu tag saja memberi ambang `0 // 2 == 0`, dan setiap
    direktori yang ada - termasuk folder lain di Downloads - dianggap dataset.
    Ini bukan masalah teoritis: `find_dataset_root` memindai isi folder
    Downloads, jadi ambang nol berarti ia mengambil folder bernama apa pun yang
    kebetulan terurut lebih dulu.
    """
    if not path.is_dir():
        return False
    if not EQUIPMENT_TAGS:
        return False
    hits = 0
    for tag in EQUIPMENT_TAGS:
        if list(path.rglob(f"*{tag}*")):
            hits += 1
    return hits >= max(1, len(EQUIPMENT_TAGS) // 2)


def find_dataset_root(explicit: str | os.PathLike[str] | None = None) -> Path:
    """Temukan root dataset, atau lempar DatasetNotFound.

    `explicit` menang atas segalanya supaya test bisa menunjuk fixture.
    """
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.environ.get("TRUSTHUB_DATASET_ROOT", "").strip()
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve().parent
    candidates.append(here.parent / "dataset")  # backend/dataset/
    candidates.append(here.parent.parent / "dataset")  # repo root/dataset/

    home = Path.home()
    downloads = home / "Downloads"
    if downloads.is_dir():
        # Folder hasil unzip: <nama>-<timestamp>-1-001/Case 1_ .../
        for child in sorted(downloads.iterdir(), reverse=True):
            if child.is_dir():
                candidates.append(child)
                candidates.append(child / _DATASET_FOLDER)
    candidates.append(downloads / _DATASET_FOLDER)

    for cand in candidates:
        if _looks_like_dataset(cand):
            return cand.resolve()
    raise DatasetNotFound(
        "Dataset CALIBER Case 1 tidak ditemukan. Cari dengan:\n"
        f"  1. set env TRUSTHUB_DATASET_ROOT='<path ke \"{_DATASET_FOLDER}\">'\n"
        f"  2. atau taruh di {here.parent / 'dataset'}\n"
        f"  3. atau jalankan backend/plant/fetch_dataset.py dari repo ini\n"
        f"  Lokasi yang sudah dicek: {[str(c) for c in candidates[:8]]}"
    )


def resolve_xlsx(root: Path) -> Path | None:
    """Cari file Maintenance History di bawah `root`."""
    for cand in sorted(root.rglob(_MAINT_XLSX)):
        return cand
    matches = [p for p in root.rglob("*.xlsx") if "aintenance" in p.name]
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# Statistik dataset-derived
# ---------------------------------------------------------------------------


def _num(value: Any) -> float | None:
    """Angka di xlsx disimpan campur string dan float - coerce dengan aman."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class DatasetReport:
    root: str
    pdf_count: int
    png_count: int
    xlsx_path: str | None
    by_doc_type: dict[str, int]
    opl_counts: dict[str, int]
    missing_opl: dict[str, list[int]]
    wo_total: int | None
    breakdown_total: int | None
    downtime_hours: float | None
    total_cost_idr: float | None
    breakdown_cost_idr: float | None
    per_equipment: list[dict[str, Any]]
    date_range: tuple[str, str] | None
    problems: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "pdf_count": self.pdf_count,
            "png_count": self.png_count,
            "xlsx_path": self.xlsx_path,
            "by_doc_type": self.by_doc_type,
            "opl_counts": self.opl_counts,
            "missing_opl": self.missing_opl,
            "wo_total": self.wo_total,
            "breakdown_total": self.breakdown_total,
            "downtime_hours": self.downtime_hours,
            "total_cost_idr": self.total_cost_idr,
            "breakdown_cost_idr": self.breakdown_cost_idr,
            "per_equipment": self.per_equipment,
            "date_range": self.date_range,
            "problems": self.problems,
        }


def read_maintenance_history(root: Path) -> list[dict[str, Any]]:
    """Baca sheet maintenance jadi list of dict dengan nama kolom asli.

    Kolom `Downtime_Hours` dan kolom biaya disimpan sebagai TEKS di workbook,
    jadi semua numerik harus dikoersi. Nilai yang tidak terbaca jadi None dan
    diabaikan saat agregasi - bukan dianggap nol, karena keduanya berbeda
    arti untuk perhitungan downtime.
    """
    xlsx = resolve_xlsx(root)
    if xlsx is None:
        raise DatasetNotFound(f"Maintenance history tidak ditemukan di {root}")

    from openpyxl import load_workbook

    wb = load_workbook(xlsx, data_only=True, read_only=True)
    sheet = None
    for ws in wb.worksheets:
        header = [c for c in next(ws.iter_rows(values_only=True), []) or []]
        if any(h == "WO_Number" for h in header if isinstance(h, str)):
            sheet = ws
            break
    if sheet is None:
        raise DatasetNotFound(f"Sheets maintenance history tidak ada di {xlsx}")

    rows = list(sheet.iter_rows(values_only=True))
    wb.close()
    header = list(rows[0])
    out: list[dict[str, Any]] = []
    for raw in rows[1:]:
        if raw is None or not any(raw):
            continue
        record = {header[i]: raw[i] for i in range(min(len(header), len(raw)))}
        for key in ("Downtime_Hours", "Labor_Hours", "Total_Cost_IDR",
                    "Labor_Cost_IDR", "Material_Cost_IDR"):
            if key in record:
                record[key] = _num(record[key])
        record["Breakdown"] = str(record.get("Breakdown") or "").strip()
        out.append(record)
    return out


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def dataset_report(root: str | os.PathLike[str] | None = None) -> DatasetReport:
    """Hitung statistik dataset-derived + daftar masalah yang ditemukan."""
    root_path = find_dataset_root(root)
    files = iter_dataset_files(root_path)
    pdfs = [f for f in files if f.lower().endswith(".pdf")]
    pngs = [f for f in files if f.lower().endswith((".png", ".jpg", ".jpeg"))]

    problems: list[str] = []
    by_doc_type: dict[str, int] = {}
    opl_counts: dict[str, int] = {t: 0 for t in EQUIPMENT_TAGS}
    missing_opl: dict[str, list[int]] = {}

    for f in pdfs:
        base = os.path.basename(f)
        if base.startswith("OPL"):
            for tag in EQUIPMENT_TAGS:
                if tag in base:
                    opl_counts[tag] += 1
                    break
            else:
                problems.append(f"Nama OPL tanpa tag equipment dikenal: {base}")
            continue
        low = base.lower()
        kind = (
            "datasheet" if "datasheet" in low
            else "interlock" if "interlock" in low
            else "plot_plan" if "plot plan" in low
            else "ga" if "drawing" in low
            else "unknown"
        )
        by_doc_type[kind] = by_doc_type.get(kind, 0) + 1

    # OPL yang hilang sengaja dicatat sebagai temuan, bukan dibiarkan diam.
    # Penomoran OPL di dataset ini maksimal 7 per equipment.
    for tag, count in opl_counts.items():
        present = {
            int(m.group(1))
            for f in pdfs
            if os.path.basename(f).startswith("OPL") and tag in os.path.basename(f)
            for m in [re.search(rf"{re.escape(tag)}-(\d\d)", f)]
            if m
        }
        gaps = sorted(set(range(1, 8)) - present)
        if gaps:
            missing_opl[tag] = gaps
            problems.append(f"{tag}: OPL nomor {gaps} tidak ada di dataset")

    for tag in EQUIPMENT_TAGS:
        if not any(tag in f for f in files):
            problems.append(f"Equipment {tag}: tidak ada dokumen sama sekali")

    wo_total = breakdown_total = None
    downtime = cost = breakdown_cost = None
    per_equipment: list[dict[str, Any]] = []
    date_range: tuple[str, str] | None = None

    try:
        history = read_maintenance_history(root_path)
    except DatasetNotFound as exc:
        problems.append(str(exc))
        history = []

    if history:
        wo_total = len(history)
        breakdowns = [r for r in history if r.get("Breakdown") == "Yes"]
        breakdown_total = len(breakdowns)
        dt = [r["Downtime_Hours"] for r in history if r.get("Downtime_Hours") is not None]
        downtime = sum(dt) if dt else 0.0
        cs = [r["Total_Cost_IDR"] for r in history if r.get("Total_Cost_IDR") is not None]
        cost = sum(cs) if cs else 0.0
        bcs = [
            r["Total_Cost_IDR"]
            for r in breakdowns
            if r.get("Total_Cost_IDR") is not None
        ]
        breakdown_cost = sum(bcs) if bcs else 0.0

        dates = [r.get("Report_Date") for r in history if r.get("Report_Date")]
        if dates:
            date_range = (_iso(min(dates)), _iso(max(dates)))

        for tag in EQUIPMENT_TAGS:
            sub = [r for r in history if r.get("Equipment_Tag") == tag]
            if not sub:
                continue
            bsub = [r for r in sub if r.get("Breakdown") == "Yes"]
            per_equipment.append(
                {
                    "equipment_tag": tag,
                    "equipment_name": next(
                        (r.get("Equipment_Name") for r in sub if r.get("Equipment_Name")),
                        None,
                    ),
                    "area_name": next((r.get("Area_Name") for r in sub), None),
                    "criticality": next((r.get("Criticality") for r in sub), None),
                    "functional_location": next(
                        (r.get("Functional_Location") for r in sub), None
                    ),
                    "interlock_ref": next(
                        (r.get("Related_Interlock") for r in sub), None
                    ),
                    "wo_count": len(sub),
                    "breakdown_count": len(bsub),
                    "downtime_hours": sum(
                        r["Downtime_Hours"] or 0.0 for r in sub
                    ),
                    "total_cost_idr": sum(
                        r["Total_Cost_IDR"] or 0.0 for r in sub
                    ),
                }
            )
        # equipment yang ada dokumen tapi tidak ada di history = masalah data
        for tag in EQUIPMENT_TAGS:
            if opl_counts.get(tag) and not any(
                p["equipment_tag"] == tag for p in per_equipment
            ):
                problems.append(
                    f"{tag}: ada dokumen tapi tidak ada di maintenance history"
                )
    else:
        problems.append("Maintenance history kosong atau tidak terbaca")

    return DatasetReport(
        root=str(root_path),
        pdf_count=len(pdfs),
        png_count=len(pngs),
        xlsx_path=str(resolve_xlsx(root_path)) if resolve_xlsx(root_path) else None,
        by_doc_type=by_doc_type,
        opl_counts=opl_counts,
        missing_opl=missing_opl,
        wo_total=wo_total,
        breakdown_total=breakdown_total,
        downtime_hours=downtime,
        total_cost_idr=cost,
        breakdown_cost_idr=breakdown_cost,
        per_equipment=per_equipment,
        date_range=date_range,
        problems=problems,
    )