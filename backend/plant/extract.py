"""Ekstraksi dokumen CALIBER -> sections + metadata asli.

Penting: modul ini hanya MENGAMBIL metadata yang benar-benar tertulis di
dokumen (doc no, rev, status approval, approver, tanggal, tag equipment).
Tidak ada metadata yang dikarang di sini. Kalau sebuah field tidak ada di
dokumen, hasilnya `None` dan registry mencatatnya sebagai tidak diketahui -
bukan ditebak.

Tiap dokumen dataset CALIBER Case 1 adalah satu halaman PDF dengan struktur
tetap, jadi parsing berbasis label lebih akurat daripada heuristik umum.

Tipe dokumen yang dikenali:
  datasheet  Equipment Datasheet - <TAG>.pdf
  ga         Equipment GA Drawing / Equipment Drawing - <TAG>.pdf
  interlock  Interlock Logic Diagram - <TAG>.pdf
  plot_plan  Plot Plan - <TAG>.pdf
  opl        OPL-<TAG>-NN - <Judul>.pdf
  pid        P&ID_Set_NN.png  (gambar, tidak ada teks)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, asdict
from typing import Any

# ---------------------------------------------------------------------------
# Konstanta domain
# ---------------------------------------------------------------------------

EQUIPMENT_TAGS = [
    "GA-1201A",  # Hexane Feed Pump
    "YD-2301",  # Polymer Fluid Bed Dryer
    "DC-3401A",  # Catalyst Reduction Reactor
    "KC-4501",  # Recycle Gas Compressor
    "EA-5601",  # Solvent Heater
    "LV-6701",  # Separator Level Control Valve
    "CT-7801",  # Cooling Tower Cell Fan
    "FA-8901",  # Reflux Accumulator Drum
]

_TAG_ALT = "|".join(re.escape(t) for t in EQUIPMENT_TAGS)

# Status approval yang muncul di dataset. Dipetakan ke level kehormatan
# (lihat trust.py). "ISSUED FOR OPERATION" dan "ISSUED FOR CONSTRUCTION"
# adalah status akhir; sisanya masih tahap Ferguson.
APPROVAL_STATES = [
    ("ISSUED FOR OPERATION", "approved"),
    ("ISSUED FOR CONSTRUCTION", "approved"),
    ("ISSUED FOR APPROVAL", "pending"),
    ("ISSUED FOR REVIEW", "draft"),
    ("ISSUED FOR INFORMATION", "draft"),
]


# ---------------------------------------------------------------------------
# Struktur hasil
# ---------------------------------------------------------------------------


@dataclass
class DocMeta:
    """Metadata satu dokumen. Semua field diturunkan dari isi dokumen."""

    doc_type: str  # datasheet | ga | interlock | plot_plan | opl | pid
    equipment_tag: str | None = None
    equipment_name: str | None = None
    doc_no: str | None = None  # TJC-LLD-DS-GA-1201A
    drawing_no: str | None = None  # alias doc_no untuk gambar
    title: str | None = None
    revision: str | None = None  # "3"
    approval_status: str | None = None  # approved | pending | draft | unknown
    approval_raw: str | None = None  # teks apa adanya dari dokumen
    revision_history: list[dict[str, str]] = field(default_factory=list)
    effective_date: str | None = None
    functional_location: str | None = None  # TJC-LLD-1200-01
    area_name: str | None = None
    plant: str | None = None
    criticality: str | None = None
    interlock_ref: str | None = None  # SEQ-1201
    interlock_sil: str | None = None  # SIL 1
    pid_ref: str | None = None  # TJC-LLD-PID-1201
    discipline: str | None = None
    opl_no: str | None = None  # OPL-GA-1201A-06
    opl_classification: list[str] = field(default_factory=list)
    prepared_by: str | None = None
    reviewed_by: str | None = None
    approved_by: str | None = None
    related_docs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractedDoc:
    """Dokumen + isiraq yang sudah dipisah per bagian."""

    path: str
    filename: str
    meta: DocMeta
    text: str = ""  # teks penuh, untuk FTS
    sections: list[dict[str, str]] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "filename": self.filename,
            "meta": self.meta.to_dict(),
            "text": self.text,
            "sections": self.sections,
            "tables": self.tables,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Deteksi tipe dokumen
# ---------------------------------------------------------------------------


def classify(filename: str, text: str = "") -> str:
    """Tentukan tipe dokumen dari nama file, dengan teks sebagai cadangan."""
    base = os.path.basename(filename)
    if base.startswith("OPL"):
        return "opl"
    low = base.lower()
    if "pid" in low and base.lower().endswith(".png"):
        return "pid"
    if "interlock" in low:
        return "interlock"
    if "plot plan" in low:
        return "plot_plan"
    if "datasheet" in low or "data sheet" in low:
        return "datasheet"
    if "ga drawing" in low or "drawing" in low:
        return "ga"
    # cadangan: berbasis isi
    if "ONE POINT LESSON" in text:
        return "opl"
    if "INTERLOCK LOGIC DIAGRAM" in text:
        return "interlock"
    if "DATA SHEET" in text:
        return "datasheet"
    if "PLOT PLAN" in text:
        return "plot_plan"
    if "GENERAL ARRANGEMENT" in text:
        return "ga"
    return "unknown"


# ---------------------------------------------------------------------------
# Helper parsing
# ---------------------------------------------------------------------------


def _first(pattern: str, text: str, group: int = 1) -> str | None:
    """Cocokkan pattern dan ambil hasil. Pattern tanpa capture group aman:
    yang dikembalikan adalah seluruh match."""
    m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if not m:
        return None
    return (m.group(group) if group <= m.re.groups else m.group(0)).strip() or None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip(" \t:*|")
    return value or None


def _flat(text: str) -> str:
    """Ratakan whitespace.

    PDF single-page memecah frasa di beberapa baris, mis. di datasheet
    "Rev 3 - ISSUED FOR\\nOPERATION". Tanpa perataan, pencarian frasa approval
    selalu gagal dan dokumen terlihat belum disetujui padahal jelas sudah.
    """
    return re.sub(r"\s+", " ", text)


def detect_approval(raw_text: str) -> tuple[str | None, str | None]:
    """Temukan status approval dari teks dokumen.

    Mengembalikan (level, teks_asli). Level: approved | pending | draft |
    unknown. Mengembalikan `unknown` kalau tidak ada status - pemanggil wajib
    memperlakukan itu sebagai "tidak diketahui", bukan sebagai draft.
    """
    text = _flat(raw_text)
    for needle, level in APPROVAL_STATES:
        if needle.lower() in text.lower():
            m = re.search(
                rf"([A-Za-z0-9\-/. ]{{0,40}}{re.escape(needle)}[A-Za-z0-9\-/. ]{{0,20}})",
                text,
                re.IGNORECASE,
            )
            return level, _clean(m.group(1)) if m else needle
    return "unknown", None


def _kv_from_tables(
    tables: list[list[list[str]]], header_keyword: str
) -> dict[str, str]:
    """Baca tabel label->nilai yang header-nya memuat `header_keyword`.

    Dipakai untuk baris tanda tangan OPL (Prepared/Reviewed/Approved by,
    Date of Sharing) yang pypdf tulis sebagai blok label lalu blok nilai,
    bukan sebagai pasangan "label: nilai" - sehingga harus dibaca dari tabel.
    """
    for rows in tables:
        for idx, row in enumerate(rows):
            lowered = [c.lower() for c in row]
            if not any(header_keyword.lower() in c for c in lowered):
                continue
            values = rows[idx + 1] if idx + 1 < len(rows) else []
            return {
                row[i]: values[i]
                for i in range(min(len(row), len(values)))
                if row[i] and values[i]
            }
    return {}


def parse_revision_history(text: str) -> list[dict[str, str]]:
    """Baca tabel REVISION HISTORY (REV | DESCRIPTION | BY | DATE).

    Bentuk baris di PDF: `0 ISSUED FOR CONSTRUCTION RS 05-06-2026` - kolom
    dipisah SPASI, bukan tab, jadi regex dipakai dan bukan split. Baris
    pertama yang cocok dalam urutan teks adalah revisi terbaru.

    Datasheet tidak punya tabel ini - statusnya ditulis inline
    ("Rev 3 - ISSUED FOR OPERATION") dan ditangani oleh detect_approval().
    """
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(
        r"^\s*([A-Z0-9]{1,2})\s+"
        r"(ISSUED FOR (?:REVIEW|APPROVAL|CONSTRUCTION|OPERATION|INFORMATION|AS BUILT))"
        r"(?:\s+([A-Z]{2,4}))?"
        r"(?:\s+(\d{2}-\d{2}-\d{4}))?\s*$",
        re.IGNORECASE,
    )
    for line in text.splitlines():
        m = pattern.match(line)
        if not m:
            continue
        rev = m.group(1).upper()
        if rev in seen:
            continue
        seen.add(rev)
        row = {"rev": rev, "description": m.group(2).strip().upper()}
        if m.group(3):
            row["by"] = m.group(3).upper()
        if m.group(4):
            row["date"] = m.group(4)
        rows.append(row)
    return rows


def _extract_person(text: str, label: str) -> str | None:
    """Ambil nama orang di sebelah label, mis. 'Approved by (Manager)'."""
    m = re.search(
        rf"{re.escape(label)}\s*[:\t]?\s*([A-Z][A-Za-z.'\- ]{{2,60}}\(EMP-\d+\))",
        text,
    )
    if m:
        return _clean(m.group(1))
    # sebagian OPL menaruh nama di baris berikutnya
    return None


# ---------------------------------------------------------------------------
# Metadata per tipe dokumen
# ---------------------------------------------------------------------------


def _meta_common(text: str, meta: DocMeta) -> None:
    """Isi field yang berlaku lintas semua tipe dokumen."""
    meta.equipment_tag = meta.equipment_tag or _first(rf"\b({_TAG_ALT})\b", text)
    meta.functional_location = meta.functional_location or _first(
        r"TJC-LLD-\d{4}-\d{2}", text
    )
    meta.interlock_ref = meta.interlock_ref or _first(r"\b(SEQ-\d{4})\b", text)
    m = re.search(r"\bSIL\s*([0-4])\b", text, re.IGNORECASE)
    if m:
        meta.interlock_sil = f"SIL {m.group(1)}"
    meta.pid_ref = meta.pid_ref or _first(r"TJC-LLD-PID-\d{4}", text)
    if meta.plant is None:
        meta.plant = _clean(
            _first(r"LINEAR LOW DENSITY POLYETHYLENE(?:\s*\(LLDPE\))?\s*UNIT", text)
        )
    if meta.criticality is None:
        meta.criticality = _first(r"\b(HIGH CRITICAL|LOW CRITICAL|NON CRITICAL)\b", text)

    # Cross-reference antar dokumen (disebut eksplisit di tiap PDF).
    if not meta.related_docs:
        refs = set()
        for pat in (r"TJC-LLD-(?:PID|IL|DS|GA|PP)-[A-Z]{1,3}-?\d{3,4}[A-Z]?",
                    r"WPN-[A-Z]{3}-\d{3}",
                    r"\bSEQ-\d{4}\b"):
            refs.update(re.findall(pat, text))
        meta.related_docs = sorted(refs)


def _meta_datasheet(text: str, meta: DocMeta) -> None:
    flat = _flat(text)
    meta.doc_no = _first(r"DOC NO:\s*([A-Z0-9\-/]+)", flat)
    meta.revision = _first(r"\bREV:\s*([A-Z0-9]+)", flat)
    meta.equipment_name = _clean(
        _first(r"EQUIPMENT\s*NAME\s+([A-Z0-9 ()\-]+)", flat)
        or _first(
            r"\b([A-Z][A-Z ]{4,40}(?:PUMP|DRYER|REACTOR|COMPRESSOR|HEATER|VALVE|FAN|DRUM))\b",
            flat,
        )
    )
    # Datasheet menulis revisi + status dalam satu baris, dipisah baris baru
    # di PDF: "DATASHEET REV\nRev 3 - ISSUED FOR\nOPERATION".
    m = re.search(
        r"(Rev\s+[A-Z0-9]+)\s*-\s*(ISSUED FOR\s+[A-Z]+)", flat, re.IGNORECASE
    )
    if m:
        meta.revision = _clean(m.group(1)).replace("Rev ", "")
        meta.approval_raw = _clean(m.group(0))
        meta.approval_status, _ = detect_approval(m.group(0))
    else:
        meta.approval_status, meta.approval_raw = detect_approval(flat)
    if not meta.title:
        meta.title = _clean(_first(r"([A-Z][A-Z ]+DATA SHEET)", flat))


def _meta_drawing(text: str, meta: DocMeta) -> None:
    flat = _flat(text)
    # Label dan nilai dipisah baris baru di PDF ("DWG No.\nTJC-LLD-GA-GA-1201A"),
    # jadi pemisah label:value harus boleh berupa whitespace apa pun.
    meta.drawing_no = _first(r"DWG(?:\s*No\.?)?\s*:?\s*([A-Z0-9\-/]{6,})", flat)
    meta.doc_no = meta.doc_no or meta.drawing_no
    meta.revision = _first(r"\bREV:\s*([A-Z0-9]+)", flat)
    # History revision dibaca dari teks mentah: barisnya dipisah spasi dan
    # perataan whitespace tidak akan menghapusnya, tapi pemisahan baris tetap
    # dibutuhkan untuk anchoring pola.
    hist = parse_revision_history(text)
    meta.revision_history = hist
    # Status approval = entri revisi TERAKHIR di tabel history.
    if hist:
        last = hist[-1]
        level, _ = detect_approval(last["description"])
        meta.approval_status = level
        meta.approval_raw = last["description"]
        meta.effective_date = last.get("date")
        if not meta.revision:
            meta.revision = last.get("rev")
    else:
        level, raw = detect_approval(flat)
        meta.approval_status, meta.approval_raw = level, raw
    if not meta.title:
        meta.title = _clean(
            _first(r"(GENERAL ARRANGEMENT DRAWING)", flat)
            or _first(r"(PLOT PLAN / EQUIPMENT LOCATION)", flat)
        )


def _meta_interlock(text: str, meta: DocMeta) -> None:
    meta.doc_no = _first(r"DOC NO:\s*([A-Z0-9\-/]+)", text)
    meta.revision = _first(r"\bREV:\s*([A-Z0-9]+)", text)
    meta.approval_status, meta.approval_raw = detect_approval(text)
    m = re.search(r"WORK NO:\s*([A-Z]{2}-\d+)", text)
    if m:
        meta.title = f"Interlock Logic Diagram {meta.equipment_tag or ''}".strip()
    if not meta.title:
        meta.title = "Interlock Logic Diagram & Cause / Effect Matrix"


def _meta_opl(text: str, meta: DocMeta, tables: list[list[list[str]]]) -> None:
    flat = _flat(text)
    meta.opl_no = _first(r"OPL No:\s*(OPL-[A-Z0-9\-]+)", flat)
    meta.title = _clean(_first(r"OPL Title\s+([^\n]{4,90})", text))
    meta.discipline = _clean(_first(r"Discipline\s+([^\n]{3,40})", text))
    meta.area_name = meta.area_name or _clean(
        _first(r"Area / Unit\s+([^\n]{3,60})", text)
    )
    meta.prepared_by = _clean(_first(r"Prepared by\s+([^\n]{3,60})", text))

    # Baris tanda tangan: pdfplumber membacanya sebagai tabel 2 baris (header
    # label, lalu nilai). Ini satu-satunya tempat nama approver dan tanggal
    # pembagian OPL muncul, jadi harus dibaca dari tabel - teks linear
    # menumpuk semua label sebelum semua nilai sehingga tidak bisa dipasangkan.
    signoff = _kv_from_tables(tables, "Prepared by")
    for label, value in signoff.items():
        key = label.strip().lower()
        if key.startswith("prepared"):
            meta.prepared_by = meta.prepared_by or _clean(value)
        elif key.startswith("reviewed"):
            meta.reviewed_by = _clean(value)
        elif key.startswith("approved"):
            meta.approved_by = _clean(value)
        elif key.startswith("date"):
            meta.effective_date = _clean(value)

    # 6 dari 55 OPL menaruh nilai tanda tangan di luar area tabel, sehingga
    # pdfplumber hanya mengembalikan baris header. Untuk itu, ambil nama dari
    # teks: setelah blok label, dua nama ber-EMP muncul berurutan
    # (reviewer lalu approver), dan sisa teks setelahnya adalah tanggal.
    if not meta.reviewed_by or not meta.approved_by:
        flat_text = _flat(text)
        anchor = flat_text.find("Date of Sharing")
        if anchor > 0:
            people = re.findall(
                r"([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+)*\s*\(EMP-\d+\))",
                flat_text[anchor:],
            )
            if people:
                meta.reviewed_by = meta.reviewed_by or _clean(people[0])
            if len(people) > 1:
                meta.approved_by = meta.approved_by or _clean(people[1])
            if not meta.effective_date and people:
                tail = flat_text[anchor:]
                last = tail.rfind(people[-1]) + len(people[-1])
                date = _clean(tail[last : last + 40].strip(" ,."))
                if date and re.match(r"[A-Za-z]{3},", date):
                    meta.effective_date = date

    # Klasifikasi OPL: menandai jenis pengetahuan (basic/improvement/trouble).
    for cls in ("Basic Knowledge", "Improvement", "Trouble Case"):
        if re.search(rf"\[X\]\s*{re.escape(cls)}", flat, re.IGNORECASE):
            meta.opl_classification.append(cls)
    meta.approval_status, meta.approval_raw = detect_approval(flat)
    # OPL tidak menulis "ISSUED FOR ..." di badan dokumen. Presence of a named
    # approver IS the approval evidence we actually have - jadi dicatat sebagai
    # approved dengan bukti yang bisa ditampilkan ke user.
    if meta.approval_status == "unknown" and meta.approved_by:
        meta.approval_status = "approved"
        meta.approval_raw = f"Approved by {meta.approved_by}"


# ---------------------------------------------------------------------------
# Pemecah section
# ---------------------------------------------------------------------------

_SECTION_PATTERNS = [
    ("purpose", r"1\.\s*PURPOSE\s*/?\s*OBJECTIVE"),
    ("safety", r"2\.\s*SAFETY\s+PRECAUTIONS?"),
    ("tools", r"3\.\s*TOOLS\s*(?:&|AND)\s*MATERIALS?"),
    ("procedure", r"4\.\s*DETAILED\s+PROCEDURE"),
    ("troubleshooting", r"5\.\s*COMMON\s+PROBLEMS"),
    ("learning", r"6\.\s*KEY\s+LEARNING\s+POINTS"),
]


def split_sections(text: str) -> list[dict[str, str]]:
    """Pecah OPL jadi bagian bernomor agar sitasi bisa menunjuk bagian."""
    if "1.\tPURPOSE" not in text and "1. PURPOSE" not in text:
        return []
    marks: list[tuple[int, str]] = []
    for name, pat in _SECTION_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            marks.append((m.start(), name))
    marks.sort()
    out: list[dict[str, str]] = []
    for i, (pos, name) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        out.append({"section": name, "content": text[pos:end].strip()})
    return out


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _read_pdf(path: str) -> tuple[str, list[list[list[str]]]]:
    """Baca teks + tabel satu PDF. pdfplumber untuk tabel, pypydd untuk teks."""
    text = ""
    tables: list[list[list[str]]] = []
    try:
        from pypdf import PdfReader

        reader = PdfReader(path)
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        text = ""
    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                for tbl in page.extract_tables():
                    rows = [
                        [(c or "").strip() for c in row]
                        for row in tbl
                        if any((c or "").strip() for c in row)
                    ]
                    if rows:
                        tables.append(rows)
    except Exception:
        pass
    return text, tables


def extract_file(path: str) -> ExtractedDoc:
    """Ekstrak satu file dataset menjadi ExtractedDoc."""
    filename = os.path.basename(path)
    ext = os.path.splitext(filename)[1].lower()

    if ext in {".png", ".jpg", ".jpeg"}:
        meta = DocMeta(doc_type="pid", equipment_tag=_first(rf"\b({_TAG_ALT})\b", filename))
        meta.title = f"P&ID {meta.equipment_tag or ''}".strip()
        meta.approval_status = "unknown"
        return ExtractedDoc(path=path, filename=filename, meta=meta, text="")

    text, tables = _read_pdf(path)
    doc_type = classify(filename, text)
    meta = DocMeta(doc_type=doc_type)

    if doc_type == "datasheet":
        _meta_datasheet(text, meta)
    elif doc_type in {"ga", "plot_plan"}:
        _meta_drawing(text, meta)
    elif doc_type == "interlock":
        _meta_interlock(text, meta)
    elif doc_type == "opl":
        _meta_opl(text, meta, tables)

    _meta_common(text, meta)

    return ExtractedDoc(
        path=path,
        filename=filename,
        meta=meta,
        text=text,
        sections=split_sections(text),
        tables=tables,
    )


def iter_dataset_files(root: str) -> list[str]:
    """Kumpulkan semua file dataset (PDF/PNG/XLSX) di bawah `root`."""
    found: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in {".pdf", ".png", ".jpg", ".jpeg"}:
                found.append(os.path.join(dirpath, fn))
    return sorted(found)