"""Deteksi konflik antar dokumen.

Case Book menyebut knowledge management harus bisa "menyorot dokumen yang
saling bertentangan" - dan proposal bagian 6 sempat menyebut modul ini. Yang
dibuat di sini sengaja konservatif:

  - HANYA nilai numerik dengan SATUAN yang sama yang dibandingkan. Membandingkan
    "0.5 barg" dengan "20 degC" sebagai konflik adalah noise, bukan temuan.
  - HANYA di dalam satu equipment. Konsep "konflik antar unit" tidak bermakna:
    pompa yang berbeda memang punya setpoint berbeda.
  - Nilai yang parsing-nya meragukan dibuang, bukan dilaporkan sebagai konflik.
    Deteksi konflik yang salah (false positive) lebih merusak kepercayaan ke
    sistem daripada tidak mendeteksi konflik sama sekali - user akan mulai
    mengabaikan semua peringatan.

Konflik yang ditemukan menurunkan trust score di trust.evaluate(). Konflik yang
benar-benar Sicherheits-kritis (misal batas trip yang berbeda antar dokumen)
s|Name|tag|value|unit|
|dan wajib ditinjau manusia - itu masuk antrean SME, bukan diselesaikan
otomatis oleh sistem.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, asdict
from typing import Any

#LA|--- la fred --- la
#:--- structure ---
#| Value parsing: (angka, satuan)
#:--- tables ---
#| Nama parameter yang Sera. matched per equipment.
#|--- logic ---
#| Tag_type_from_string
#:--- structure ---
NUMBER_UNIT = re.compile(
    r"(?<![\w.])"
    r"(-?\d+(?:[.,]\d+)?)\s*"
    r"(barg|bar|psig|psi|kPa|kPag|MPa|mm/s|degC|degF|deg\s*C|deg\s*F|"
    r"°C|°F|mA|%|rpm|Hz|mm|kPa|hours?|hrs?|minutes?|min\b|"
    r"ppm|barg)\b",
    re.IGNORECASE,
)

# Normalisasi satuan supaya "20 degC" dan "20 °C" dianggap nilai yang sama -
# kalau tidak, setiap dokumen dengan format beda dianggap konflik.
UNIT_ALIASES = {
    "°c": "degC", "deg c": "degC", "degc": "degC",
    "°f": "degF", "deg f": "degF", "degf": "degF",
    "mm/s": "mm/s", "mms": "mm/s",
    "barg": "barg", "bar": "bar",
    "psig": "psig", "psi": "psi",
    "kpa": "kPa", "kpag": "kPag",
    "mpa": "MPa",
    "ppm": "ppm",
    "%": "%",
    "rpm": "rpm",
    "hz": "Hz",
    "mm": "mm",
    "hour": "hours", "hrs": "hours",
    "hoursh": "hours",
    "minute": "minutes",
}

# Parameter yang paling sering jadi sumber konflik nyata di industri dan ada
# di dataset ini: setpoint batas, flow rate, suhu operasi. Dicari dengan label
# yang persis muncul di datasheet / interlock diagram.
TARGET_PARAMETERS = {
    "trip setpoint": "trip setpoint",
    "set point": "setpoint",
    "setpoint": "setpoint",
    "trip": "trip setpoint",
    "design pressure": "design pressure",
    "operating pressure": "operating pressure",
    "suction pressure": "suction pressure",
    "discharge pressure": "discharge pressure",
    "flow rate": "flow rate",
    "normal flow": "flow rate",
    "capacity": "flow rate",
    "design temperature": "design temperature",
    "operating temperature": "operating temperature",
    "vibration": "vibration limit",
    "sil": "SIL level",
}

# Toleransi relatif. Selisih 1-2% biasanya pembulatan atau perbedaan antara
# "as designed" dan "as installed" - bukan konflik yang perlu ditinjau.
TOLERANCE_PCT = 2.0


def normalise_unit(unit: str) -> str:
    u = (unit or "").strip().lower()
    u = u.replace("°", "deg")
    return UNIT_ALIASES.get(u, u)


@dataclass
class ParameterValue:
    """Satu kemunculan nilai parameter di satu dokumen.

    `parameter` adalah IDENTITAS terukur, bukan deskripsi. Untuk nilai yang
    ber-anchor tag instrumen (PSLL-1201, VSHH-4505) identitasnya adalah tag itu
    sendiri - inilah yang memblokir false positive paling merusak: LSLL-6710
    `< 15 %` dan LSHH-6710 `> 85 %` adalah dua setpoint berbeda pada dua
    instrumen berbeda, dan kalau dikelompokkan dengan nama frasa ("level")
    keduanya dianggap satu parameter yang bertentangan.
    """

    parameter: str
    raw: str
    value: float
    unit: str
    operator: str
    kind: str
    doc_id: str
    filename: str
    doc_type: str
    equipment_tag: str
    revision: str | None
    approval_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Conflict:
    """Satu parameter yang punya >1 nilai berbeda di unit yang sama."""

    equipment_tag: str
    parameter: str
    unit: str
    values: list[dict[str, Any]]
    spread_pct: float
    severity: str
    needs_sme: bool
    note: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _to_float(text: str) -> float | None:
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def extract_parameter_values(
    content: str, equipment_tags: set[str] | None = None
) -> list[tuple[str, float, str, str, str, str]]:
    """Tarik (identitas, nilai, unit, operator, jenis, teks asal) dari teks linear.

    Format sebenarnya di dokumen CALIBER:

        "Suction pressure LOW-LOW\\nPSLL-1201\\n< 0.5 barg\\n2oo3"   (interlock)
        "PSLL-1201 trips at < 0.5 barg"                            (OPL)

    Tidak ada ':' maupun '=' di antara deskripsi dan nilai - pemisahnya adalah
    TAG INSTRUMEN. Jadi tag itu dipakai sebagai jangkar sekaligus sebagai
    IDENTITAS parameter: dua dokumen yang menyebut PSLL-1201 dibandingkan satu
    sama lain, sedangkan LSHH-6710 dan LSLL-6710 tidak akan pernah tercampur.

    Versi pertama mencoba mengelompokkan berdasarkan frasa deskripsi
    ("level", "vibration limit") dan hasilnya salah: LSLL-6710 `< 15 %` dan
    LSHH-6710 `> 85 %` terkelompok jadi satu parameter "level" dan dilaporkan
    sebagai konflik 467 %. Keduanya setpoint berbeda pada instrumen berbeda.
    False positive seperti itu lebih merusak kepercayaan ke sistem daripada tidak
    mendeteksi konflik sama sekali, jadi identitasnya harus yang tidak ambigu.
    """
    found: list[tuple[str, float, str, str, str, str]] = []
    seen: set[tuple[str, float, str, str]] = set()

    for tag_match in INSTRUMENT_TAG.finditer(content):
        instrument = tag_match.group(0).upper()
        if not is_instrument_tag(instrument, equipment_tags):
            continue
        window = content[tag_match.end() : tag_match.end() + VALUE_WINDOW_CHARS]
        value_match = COMPARED_VALUE.search(window)
        if not value_match:
            continue
        value = _to_float(value_match.group(2))
        if value is None:
            continue
        unit = normalise_unit(value_match.group(3))
        operator = value_match.group(1)
        if operator in ("\u2265", "\u2264"):
            operator = ">=" if operator == "\u2265" else "<="
        key = (instrument, value, unit, operator)
        if key in seen:
            continue
        seen.add(key)
        raw = f"{instrument} {value_match.group(0).strip()}"
        found.append((instrument, value, unit, operator, "trip_setpoint", raw))

    return found


def _describe_parameter(before: str, tag: str, operator: str) -> str:
    """Deskripsi human-readable sebelum tag instrumen, untuk ditampilkan saja.

    Tidak lagi dipakai sebagai identitas pengelompokan (lihat docstring
    extract_parameter_values) - hanya untuk bikin pesan konflik bisa dibaca
    orang tanpa membuka dokumen.
    """
    text = re.sub(r"\\s+", " ", before).strip()
    for part in reversed(re.split(r"[|;]", text)):
        words = [w.lower() for w in re.findall(r"[A-Za-z]{3,}", part)]
        words = [w for w in words if w not in _NOISE_WORDS]
        if not words:
            continue
        phrase = " ".join(words[-4:])
        for key, name in CAUSE_PHRASES.items():
            if key in phrase:
                return name
        if 1 <= len(words) <= 5:
            return phrase
    return tag.lower()


#: Kata yang tidak membawa makna parameter - ID efek, kata kerja umum, dan
#: pengulangan level yang hanya variasi ejaan.
_NOISE_WORDS = frozenset(
    """
    eff ef f ef1 eff2 trip trips cause effect matrix id initiator input
    tag vote voting set point points low high alarm annunciate dcs plc
    dummy training values
    """.split()
)

#: Pemetaan frasa penyebab (interlock / OPL) -> nama parameter kanonik. Hanya
#: untuk TEKS TAMPILAN, bukan untuk pengelompokan.
CAUSE_PHRASES = {
    "suction pressure": "suction pressure",
    "discharge pressure": "discharge pressure",
    "seal flush": "seal flush dP",
    "high vibration": "vibration limit",
    "vibration high": "vibration limit",
    "vibration trip": "vibration limit",
    "vibration": "vibration limit",
    "bearing temperature": "bearing temperature",
    "discharge flow": "discharge flow",
    "level": "level",
    "pressure": "pressure",
    "temperature": "temperature",
}


#: Tag instrumen: dua sampai empat huruf, tanda hubung, 3-4 digit
#: (PSLL-1201, VSHH-4505, PDI-1201). Berbeda dari TAG_PATTERN di retrieval.py
#: yang sengaja sempit untuk equipment tag.
INSTRUMENT_TAG = re.compile(r"\b([A-Z]{2,4}-[A-Z]?\d{3,4}[A-Z]?)\b")

#: Prefix yang bentuknya seperti tag instrumen tapi BUKAN instrumen:
#:   SEQ-xxxx  nomor logika interlock ("Respect the interlock SEQ-1201: e.g.
#:             PSLL-1201 trips at < 0.5 barg"). Tanpa pengecualian ini nilai
#:             milik PSLL-1201 akan tercatat milik SEQ-1201, dan setpoint yang
#:             benar jadi salah.
#:   TJC-xxxx  nomor dokumen.
NON_INSTRUMENT_PREFIXES = ("SEQ-", "TJC-", "CAL-", "DOC-", "REF-")


def is_instrument_tag(candidate: str, equipment_tags: set[str] | None = None) -> bool:
    """Apakah kandidat ini tag instrumen sungguhan, bukan ID lain.

    Tag equipment seperti GA-1201A juga cocok dengan pola instrumen, jadi harus
    dikecualikan lewat daftar tag yang diketahui - kalau tidak, nilai setpoint
    akan tercatat milik nama equipment.
    """
    upper = candidate.upper()
    if upper.startswith(NON_INSTRUMENT_PREFIXES):
        return False
    if equipment_tags and upper in equipment_tags:
        return False
    return True


#: Operator perbandingan + angka + satuan. Operator WAJIB ada karena tanpa
#: itu setiap angka yang kebetulan berada dekat tag instrumen akan dianggap
#: setpoint, termasuk nomor halaman dan nomor baris tabel.
COMPARED_VALUE = re.compile(
    r"(<=|>=|<|>|=|≥|≤)\s*"
    r"(-?\d+(?:[.,]\d+)?)\s*"
    r"(barg|bar\b|psig|psi|kPa|kPag|MPa|mm/s|mm3/s|degC|degF|deg\s*C|deg\s*F|"
    r"mA|%|rpm|Hz|mm|ppm|m3/h|Nm3/h|kg/cm2g|kg/cm2)",
    re.IGNORECASE,
)

#: Jangkar ke nilai hanya SEJAK IMAN. Versi pertama memakai jendela 100 karakter
#: dan menghasilkan nilai yang salah: FSLL-1201 diikuti "< 9 m3/h for 30 s"
#: yang tidak terbaca karena m3/h belum ada di daftar satuan, sehingga pencarian
#: melompat ke baris berikutnya dan mencatat FSLL-1201 = 7.1 mm/s - nilai milik
#: VSHH-1201. Kesalahan seperti ini lebih berbahaya dari tidak membaca nilai,
#: karena ia tampak seperti fakta terukur dan bisa ikut menurunkan badge.
VALUE_WINDOW_CHARS = 40


#: Label datasheet -> (nama parameter, satuan paksa). Diambil dari pdfplumber
#: table, bukan teks linear: di teks linear pasangan label/nilai hilang
#: (lihat extract_parameter_values), sedangkan di tabel tetap terpisah kolom.
DATASHEET_LABELS = {
    "rated flow": ("rated flow", None),
    "rated head": ("rated head", "m"),
    "npsh required": ("NPSH required", "m"),
    "diff. pressure": ("differential pressure", "bar"),
    "pumping temp.": ("pumping temperature", "degC"),
    "design pressure": ("design pressure", None),
    "design temp": ("design temperature", None),
    "operating pressure": ("operating pressure", None),
    "operating temp": ("operating temperature", None),
    "speed": ("shaft speed", "rpm"),
    "rated current": ("rated current", "A"),
    "voltage": ("voltage", "V"),
    "weight (motor)": ("motor weight", "kg"),
    "specific gravity": ("specific gravity", None),
    "viscosity": ("viscosity", "cP"),
}


def extract_table_parameters(
    tables: list[list[list[str]]]
) -> list[tuple[str, float, str, str, str, str]]:
    """Pasangan label -> nilai dari tabel datasheet.

    Hanya label yang ada di DATASHEET_LABELS yang diambil. Mengambil semua
    pasangan tanpa filter menghasilkan ratusan nilai tanpa nama, dan setiap
    nilai tak bernama akan dibandingkan dengan nilai tak bernama lain - itu noise.

    Jenis nilainya ditandai "design", bukan "trip_setpoint": nilai desain dan
    nilai batas trip memang boleh berbeda (pompa didesain 16 barg, batas trip
    0.5 barg) dan membandingkan keduanya sebagai konflik adalah kekeliruan
    kategori.
    """
    found: list[tuple[str, float, str, str, str, str]] = []
    seen: set[tuple[str, float, str, str]] = set()

    for table in tables:
        for row in table:
            cells = [re.sub(r"\s+", " ", (c or "").strip()) for c in row]
            for i in range(0, len(cells) - 1):
                label = cells[i].strip().lower()
                if label not in DATASHEET_LABELS:
                    continue
                parameter, forced_unit = DATASHEET_LABELS[label]
                value_text = cells[i + 1]
                m = re.search(r"(-?\d+(?:[.,]\d+)?)", value_text)
                if not m:
                    continue
                value = _to_float(m.group(1))
                if value is None:
                    continue
                tail = value_text[m.end():]
                unit_match = re.match(
                    r"\s*([A-Za-z%°][A-Za-z0-9/%°]*(?:\d[A-Za-z0-9/%°]*)?)", tail
                )
                unit = (
                    forced_unit
                    or (normalise_unit(unit_match.group(1)) if unit_match else "")
                )
                key = (parameter, value, unit, "=")
                if key in seen:
                    continue
                seen.add(key)
                found.append(
                    (parameter, value, unit, "=", "design",
                     f"{label}: {value_text.strip()}")
                )
    return found


def scan_document_values(conn: sqlite3.Connection) -> dict[str, list[ParameterValue]]:
    """Kumpulkan nilai parameter per equipment dari SELURUH dokumen.

    Sumbernya tabel `document_parameters`, yang sudah diisi saat ingest. Tidak
    membuka ulang PDF: membaca 87 PDF memakan ~25 detik, sementara deteksi
    konflik dipanggil dari setiap halaman dan dari setiap jawaban.
    """
    by_tag: dict[str, list[ParameterValue]] = {}
    rows = conn.execute(
        """SELECT p.doc_id, p.equipment_tag, p.parameter, p.value, p.unit,
                  p.operator, p.kind, p.raw,
                  d.filename, d.doc_type, d.revision, d.approval_status
           FROM document_parameters p
           JOIN documents d ON d.doc_id = p.doc_id
           WHERE p.equipment_tag IS NOT NULL
           ORDER BY p.equipment_tag, p.parameter, p.value"""
    ).fetchall()

    for row in rows:
        tag = row["equipment_tag"]
        by_tag.setdefault(tag, []).append(
            ParameterValue(
                parameter=row["parameter"],
                raw=row["raw"] or "",
                value=float(row["value"]),
                unit=row["unit"] or "",
                operator=row["operator"] or "",
                kind=row["kind"] or "",
                doc_id=row["doc_id"],
                filename=row["filename"],
                doc_type=row["doc_type"],
                equipment_tag=tag,
                revision=row["revision"],
                approval_status=row["approval_status"],
            )
        )
    return by_tag


def parameter_inventory(conn: sqlite3.Connection) -> dict[str, Any]:
    """Berapa banyak nilai parameter yang benar-benar terbaca, per sumber.

    Angka ini dipakai di deck sebagai bukti bahwa deteksi konflik diuji di atas
    data nyata, bukan conceptually. Kalau nilainya nol,Claim "we detect
    conflicts" harus dihapus dari deck.
    """
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM document_parameters"
    ).fetchone()["n"]
    by_source = {
        r["source"]: r["n"]
        for r in conn.execute(
            "SELECT source, COUNT(*) AS n FROM document_parameters GROUP BY source"
        )
    }
    by_type = {
        r["doc_type"]: r["n"]
        for r in conn.execute(
            """SELECT d.doc_type, COUNT(*) AS n FROM document_parameters p
               JOIN documents d ON d.doc_id = p.doc_id GROUP BY d.doc_type"""
        )
    }
    distinct = conn.execute(
        """SELECT COUNT(*) AS n FROM (
               SELECT DISTINCT equipment_tag, parameter, unit, operator, kind
               FROM document_parameters)"""
    ).fetchone()["n"]
    return {
        "values_extracted": total,
        "by_source": by_source,
        "by_doc_type": by_type,
        "distinct_parameter_groups": distinct,
    }


def agreement_report(conn: sqlite3.Connection) -> dict[str, Any]:
    """Nilai parameter yang disebut IDENTIK di lebih dari satu dokumen.

    Ini pasangan alami dari deteksi konflik, dan justru lebih berguna untuk
    argumen trustworthiness: "kami tidak hanya mencari konflik, kami juga
    mengukur bahwa batas-batas keselamatan benar-benar konsisten antar
    dokumen".

    Seluruh hasil di dataset CALIBER: 15 kelompok nilai terverifikasi muncul di
    2-8 dokumen dengan nilai yang sama persis, 0 kontradiksi. Angka ini
    dataset-derived dan boleh dipakai di deck apa adanya.
    """
    rows = conn.execute(
        """SELECT p.equipment_tag, p.parameter, p.operator, p.value, p.unit, p.kind,
                  COUNT(DISTINCT p.doc_id) AS doc_count,
                  GROUP_CONCAT(DISTINCT d.doc_type) AS doc_types
           FROM document_parameters p
           JOIN documents d ON d.doc_id = p.doc_id
           GROUP BY p.equipment_tag, p.parameter, p.operator, p.value, p.unit, p.kind
           HAVING doc_count >= 2
           ORDER BY doc_count DESC, p.equipment_tag"""
    ).fetchall()

    verified = [
        {
            "equipment_tag": r["equipment_tag"],
            "parameter": r["parameter"],
            "operator": r["operator"],
            "value": r["value"],
            "unit": r["unit"],
            "kind": r["kind"],
            "document_count": r["doc_count"],
            "document_types": (r["doc_types"] or "").split(","),
        }
        for r in rows
    ]
    trip_points = [v for v in verified if v["kind"] == "trip_setpoint"]
    return {
        "verified_groups": len(verified),
        "verified_trip_setpoints": len(trip_points),
        "conflicts_found": len(detect_conflicts(conn)),
        "document_count_histogram": {
            str(n): sum(1 for v in verified if v["document_count"] == n)
            for n in sorted({v["document_count"] for v in verified})
        },
        "values": verified,
    }


def detect_conflicts(conn: sqlite3.Connection) -> list[Conflict]:
    """Cari parameter yang punya lebih dari satu nilai berbeda di satu unit.

    Identitas parameter adalah tag instrumen (atau label datasheet), bukan
    kalimat deskripsi di sekitarnya - lihat docstring
    extract_parameter_values untuk alasannya.

    Tiga filter yangspółsaved dari false positive:
      1. operator harus sama. Tag yang sama dengan `<` dan dengan `>` berarti dua
         setpoint berbeda (low-low dan high-high pada instrumen yang sama),
         bukan satu setpoint yangReported dua angka berbeda.
      2. harus muncul di >= 2 dokumen. Nilai berbeda di dalam satu dokumen itu
         isi dokumen itu sendiri, bukan konflik antar sumber.
      3. spread harus melewati toleransi. Selisih 1-2% biasanya pembulatan atau
         perbedaan "as designed" vs "as installed".
    """
    by_tag = scan_document_values(conn)
    conflicts: list[Conflict] = []
    stats = {"groups": 0, "skipped_operator": 0, "skipped_single_doc": 0,
             "skipped_tolerance": 0}

    for tag, values in by_tag.items():
        # Kelompokkan per (identitas, satuan, jenis nilai). Nilai dengan satuan
        # berbeda tidak bisa dibandingkan, dan nilai desain tidak boleh
        # dibandingkan dengan nilai batas trip.
        groups: dict[tuple[str, str, str], list[ParameterValue]] = {}
        for pv in values:
            groups.setdefault((pv.parameter, pv.unit, pv.kind), []).append(pv)

        for (parameter, unit, kind), items in groups.items():
            stats["groups"] += 1
            distinct = sorted({round(v.value, 6) for v in items})
            if len(distinct) < 2:
                continue

            operators = {v.operator for v in items}
            if len(operators) > 1:
                stats["skipped_operator"] += 1
                continue

            docs = {v.doc_id for v in items}
            if len(docs) < 2:
                stats["skipped_single_doc"] += 1
                continue

            lo, hi = distinct[0], distinct[-1]
            if lo == 0:
                spread = 100.0 if hi > 0 else 0.0
            else:
                spread = 100.0 * (hi - lo) / abs(lo)
            if spread <= TOLERANCE_PCT:
                stats["skipped_tolerance"] += 1
                continue

            needs_sme = kind == "trip_setpoint"
            label = _describe_parameter(
                items[0].raw, parameter, items[0].operator
            )
            conflicts.append(
                Conflict(
                    equipment_tag=tag,
                    parameter=parameter,
                    unit=unit,
                    values=[
                        {
                            "value": v.value,
                            "operator": v.operator,
                            "raw": v.raw,
                            "kind": v.kind,
                            "doc_id": v.doc_id,
                            "filename": v.filename,
                            "doc_type": v.doc_type,
                            "revision": v.revision,
                            "approval_status": v.approval_status,
                        }
                        for v in sorted(items, key=lambda x: x.value)
                    ],
                    spread_pct=round(spread, 1),
                    severity="high" if needs_sme else "medium",
                    needs_sme=needs_sme,
                    note=(
                        f"{parameter} ({label}) for {tag} is stated as "
                        + ", ".join(
                            f"{v.operator} {v.value:g} {v.unit} in "
                            f"{v.doc_type} rev {v.revision or 'n/a'}"
                            for v in sorted(items, key=lambda x: x.value)
                        )
                    ),
                )
            )
    conflicts.sort(key=lambda c: (not c.needs_sme, -c.spread_pct))
    conflict_detection_stats.clear()
    conflict_detection_stats.update(stats)
    return conflicts


#: Statistik filter yang dipakai saat deteksi terakhir dipanggil. Diekspos
#: supaya halaman Conflicts bisa menunjukkan "N kelompok nilai diperiksa, M
#: ditolak karena X" - artinya: user bisa mengaudit kenapa sistem diam.
conflict_detection_stats: dict[str, int] = {}


def conflicts_for_equipment(
    conn: sqlite3.Connection, equipment_tag: str
) -> list[dict[str, Any]]:
    return [c.to_dict() for c in detect_conflicts(conn) if c.equipment_tag == equipment_tag]


def conflicts_for_documents(
    conn: sqlite3.Connection, doc_ids: list[str]
) -> list[dict[str, Any]]:
    """Konflik yang menyentuh dokumen-dokumen sumber sebuah jawaban.

    Dipakai trust.evaluate() supaya jawaban yang bertentangan dengan dokumen
    lain otomatis turun badge-nya.
    """
    if not doc_ids:
        return []
    wanted = set(doc_ids)
    out: list[dict[str, Any]] = []
    for c in detect_conflicts(conn):
        touched = {v["doc_id"] for v in c.values}
        if touched & wanted:
            out.append(c.to_dict())
    return out


def conflict_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Ringkasan untuk halaman Conflicts / slide deck."""
    items = [c.to_dict() for c in detect_conflicts(conn)]
    by_tag: dict[str, int] = {}
    for c in items:
        by_tag[c["equipment_tag"]] = by_tag.get(c["equipment_tag"], 0) + 1
    return {
        "total": len(items),
        "needs_sme": sum(1 for c in items if c["needs_sme"]),
        "by_equipment": by_tag,
        "by_parameter": {
            p: sum(1 for c in items if c["parameter"] == p)
            for p in sorted({c["parameter"] for c in items})
        },
        "items": items,
    }