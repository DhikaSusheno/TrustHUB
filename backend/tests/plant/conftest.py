"""Fixture untuk test `plant/`.

Kenapa tidak memakai dataset CALIBER
-----------------------------------
Dataset resmi tidak boleh masuk repository (lisensi committee), jadi CI tidak
memilikinya. Kalau test bergantung padanya, seluruh suite akan skip di CI dan
hijau tanpa menjalankan apa pun - pola yang persis membuat CI tidak berarti.

Jadi test di sini dibangun di atas `synthetic_index`: indeks SQLite dengan
isi yang dikontrol penuh dan dibuat langsung oleh test, tanpa PDF dan tanpa
dataset. Itu cukup untuk menguji bagian yang justru rawan rusak:

  - klasifikasi pertanyaan
  - guardrail penolakan
  - resolusi tag equipment dan nama
  - ekstraksi/penggabungan nilai parameter
  - deteksi konflik dan kesesuaian
  - pembentukan badge trust
  - rute HTTP

Test yang benar-benar butuh dokumen asli (mis. "OPL-GA-1201A-04 tidak ada
di dataset resmi") ditandai `requires_official_dataset` dan akan skip
dengan alasan yang tercetak, bukan diam-diam.

Angka di fixture ini DIBUAT untuk test, bukan disalin dari dataset resmi.
Kalau suatu saat diambil dari data asli, test yang meng-assert nilainya harus
ikut berubah secara sadar.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from plant import dataset as dataset_mod
from plant import extract as extract_mod
from plant import registry

#: Jumlah equipment, dokumen, dan work order di fixture.
FIXTURE_EQUIPMENT = 3
FIXTURE_DOCUMENTS = 10
FIXTURE_WORK_ORDERS = 6
FIXTURE_APPROVED = 5
FIXTURE_UNKNOWN_APPROVAL = 3
FIXTURE_PENDING = 1


def _clear_caches() -> None:
    """Buang cache kosakata yang di-key dengan id(koneksi).

    pytest memakai Address Reuse, jadi id() koneksi baru bisa sama dengan
    id() koneksi sebelumnya yang sudah ditutup. Kalau cache tidak dibuang,
    test kedua menerima kosakata milik test pertama - dan supaya lolos dengan
    jawaban yang salah.
    """
    from plant import retrieval

    retrieval._VOCABULARY_CACHE.clear()


# ---------------------------------------------------------------------------
# Builders. Dipisah dari fixture supaya `api_client` bisa membangun indeks
# yang identik di database terpisah tanpa menduplikasi isi.
# ---------------------------------------------------------------------------


def add_document(
    conn: sqlite3.Connection,
    doc_id: str,
    filename: str,
    doc_type: str,
    equipment_tag: str | None,
    *,
    title: str = "",
    doc_no: str | None = None,
    revision: str | None = None,
    approval_status: str = "approved",
    approved_by: str | None = None,
    safety: bool = False,
    chunks: list[tuple[str, str]] | None = None,
) -> str:
    """Sisipkan satu dokumen beserta chunk dan indeks FTS-nya."""
    conn.execute(
        """INSERT OR REPLACE INTO documents
           (doc_id, filename, doc_type, equipment_tag, title, doc_no, revision,
            approval_status, approved_by, is_safety_critical)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (doc_id, filename, doc_type, equipment_tag, title, doc_no, revision,
         approval_status, approved_by, 1 if safety else 0),
    )
    for section, content in chunks or []:
        conn.execute(
            """INSERT OR REPLACE INTO doc_chunks
               (doc_id, equipment_tag, section, title, content)
               VALUES (?,?,?,?,?)""",
            (doc_id, equipment_tag, section, title, content),
        )
        conn.execute(
            "INSERT INTO doc_fts (content, doc_id, equipment_tag, section) "
            "VALUES (?,?,?,?)",
            (content, doc_id, equipment_tag, section),
        )
    return doc_id


def add_parameter(
    conn: sqlite3.Connection,
    doc_id: str,
    equipment_tag: str,
    parameter: str,
    value: float,
    unit: str,
    operator: str,
    *,
    kind: str = "trip_setpoint",
    source: str = "linear",
) -> None:
    """`source` diisi karena parameter_inventory mengelompokkan menurut asal."""
    conn.execute(
        """INSERT OR IGNORE INTO document_parameters
           (doc_id, equipment_tag, parameter, value, unit, operator, kind, raw,
            source)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (doc_id, equipment_tag, parameter, value, unit, operator, kind,
         f"{parameter} {operator} {value} {unit}", source),
    )


def add_work_order(
    conn: sqlite3.Connection,
    wo_number: str,
    equipment_tag: str,
    *,
    work_type: str = "Corrective",
    discipline: str = "Mechanical",
    breakdown: int = 0,
    downtime_hours: float = 0.0,
    total_cost_idr: float = 0.0,
    problem: str = "",
    root_cause: str = "",
    corrective_action: str = "",
    report_date: str = "2025-01-15",
) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO work_orders
           (wo_number, equipment_tag, work_type, discipline, breakdown,
            downtime_hours, total_cost_idr, problem_description, root_cause,
            corrective_action, report_date)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (wo_number, equipment_tag, work_type, discipline, breakdown,
         downtime_hours, total_cost_idr, problem, root_cause,
         corrective_action, report_date),
    )


def build_synthetic_index(conn: sqlite3.Connection) -> None:
    """Isi database dengan 3 equipment, 9 dokumen, parameter, dan work order.

    Isi dirancang supaya tiap jalur kode punya minimal satu kasus yang
   umbered. Secara khusus:

      * EQ-0001 punya 3 dokumen dengan setpoint PSLL-0001 yang sama ->
        harus muncul di "verified", bukan "conflict".
      * EQ-0002 punya 2 dokumen dengan setpoint yang berbeda jauh ->
        harus muncul di "conflict", dan hanya itu.
      * EQ-0002 datasheet berstatus 'pending', dan interlock-nya 'unknown' ->
        status approval tidak boleh ditebak jadi 'approved'. Menebaknya di
        sini akan membuat badge TRUSTED untuk dokumen yang tidak pernah
        ditandatangani.
      * EQ-0001 punya breakdown dengan root cause yang cocok dengan isi OPL
        -> harus punya failure link.
    """
    conn.executescript(registry.SCHEMA)

    for tag, name, area, crit in (
        ("EQ-0001", "SAMPLE FEED PUMP", "AREA ONE", "HIGH CRITICAL"),
        ("EQ-0002", "SAMPLE REACTOR VESSEL", "AREA TWO", "LOW CRITICAL"),
        ("EQ-0003", "SAMPLE AIR COMPRESSOR", "AREA THREE", "NON CRITICAL"),
    ):
        conn.execute(
            """INSERT INTO equipment
               (equipment_tag, equipment_name, area_name, criticality,
                functional_location, interlock_ref, pid_ref)
               VALUES (?,?,?,?,?,?,?)""",
            (tag, name, area, crit, f"FL-{tag}", f"TJC-LLD-IL-{tag}",
             f"P&ID {tag}"),
        )

    # ---- EQ-0001: setpoint konsisten di 3 dokumen ----------------------------
    add_document(
        conn, "d1a", "OPL-EQ-0001-01 - Seal_Flush.pdf", "opl", "EQ-0001",
        title="Mechanical seal flush plan", doc_no="OPL-EQ-0001-01",
        revision="A", approval_status="approved", approved_by="EMP-0001",
        safety=True,
        chunks=[
            ("purpose", "This One Point Lesson explains the mechanical seal "
                        "flush plan for EQ-0001. Reviewed by EMP-0001."),
            ("procedure", "Establish the seal flush flow, then verify the low "
                          "suction pressure trip PSLL-0001 trips at 0.5 barg."),
            ("troubleshooting", "If the mechanical seal leaks, check the flush "
                                "pressure and the gland packing first."),
        ],
    )
    add_parameter(conn, "d1a", "EQ-0001", "PSLL-0001", 0.5, "barg", "<")

    add_document(
        conn, "d1b", "Interlock Logic Diagram - EQ-0001.pdf", "interlock",
        "EQ-0001", title="Interlock logic diagram", doc_no="TJC-LLD-IL-EQ-0001",
        approval_status="unknown", safety=True,
        chunks=[
            ("whole", "INTERLOCK LOGIC DIAGRAM AND CAUSE EFFECT MATRIX for "
                      "EQ-0001. PSLL-0001 trip when pressure is below 0.5 barg."),
        ],
    )
    add_parameter(conn, "d1b", "EQ-0001", "PSLL-0001", 0.5, "barg", "<")

    add_document(
        conn, "d1c", "Equipment Datasheet - EQ-0001.pdf", "datasheet", "EQ-0001",
        title="Equipment datasheet", doc_no="DATASHEET EQ-0001",
        revision="Rev 3 - ISSUED FOR OPERATION", approval_status="approved",
        chunks=[
            ("design", "Design pressures and operating temperature. "
                       "PSLL-0001 low suction pressure trip is set below 0.5 barg."),
        ],
    )
    add_parameter(conn, "d1c", "EQ-0001", "PSLL-0001", 0.5, "barg", "<")

    add_document(
        conn, "d1d", "GA Drawing - EQ-0001.pdf", "ga", "EQ-0001",
        title="General arrangement drawing", doc_no="GA-EQ-0001",
        revision="0", approval_status="approved",
        chunks=[("drawing", "General arrangement and dimensional drawing for "
                            "EQ-0001 in AREA ONE.")],
    )
    add_document(
        conn, "d1e", "Plot Plan - AREA ONE.pdf", "plot_plan", "EQ-0001",
        title="Plot plan", doc_no="PP-AREA-ONE", approval_status="approved",
        chunks=[("layout", "Plot plan and equipment layout for AREA ONE.")],
    )

    # ---- EQ-0002: setpoint BERTOLAKAN di 2 dokumen ---------------------------
    add_document(
        conn, "d2a", "Interlock Logic Diagram - EQ-0002.pdf", "interlock",
        "EQ-0002", title="Interlock logic diagram", doc_no="TJC-LLD-IL-EQ-0002",
        approval_status="unknown", safety=True,
        chunks=[("whole", "INTERLOCK LOGIC DIAGRAM for EQ-0002. "
                          "TSHH-0002 trip when temperature is above 230 degC.")],
    )
    add_parameter(conn, "d2a", "EQ-0002", "TSHH-0002", 230.0, "degC", ">")

    add_document(
        conn, "d2b", "OPL-EQ-0002-01 - Reactor_Startup.pdf", "opl", "EQ-0002",
        title="Reactor start-up", doc_no="OPL-EQ-0002-01", revision="B",
        approval_status="approved", approved_by="EMP-0002", safety=True,
        chunks=[("procedure", "Start-up procedure for EQ-0002. "
                              "TSHH-0002 high temperature trip set above 125 degC.")],
    )
    add_parameter(conn, "d2b", "EQ-0002", "TSHH-0002", 125.0, "degC", ">")

    add_document(
        conn, "d2c", "Equipment Datasheet - EQ-0002.pdf", "datasheet", "EQ-0002",
        title="Equipment datasheet", doc_no="DATASHEET EQ-0002",
        revision="Rev 1 - ISSUED FOR REVIEW", approval_status="pending",
        chunks=[("design", "Design pressure and operating temperature for "
                           "EQ-0002 sample reactor vessel.")],
    )

    # ---- EQ-0003: interlock tanpa approval marker ---------------------------
    add_document(
        conn, "d3a", "OPL-EQ-0003-01 - Compressor_Vibration.pdf", "opl", "EQ-0003",
        title="Compressor vibration trending", doc_no="OPL-EQ-0003-01",
        approval_status="unknown",
        chunks=[("purpose", "Vibration trending and alarm response lesson for "
                            "EQ-0003 sample air compressor.")],
    )
    add_document(
        conn, "d3b", "Equipment Datasheet - EQ-0003.pdf", "datasheet", "EQ-0003",
        title="Equipment datasheet", doc_no="DATASHEET EQ-0003",
        revision="Rev 2 - ISSUED FOR OPERATION", approval_status="approved",
        chunks=[("design", "Nameplate and design data for EQ-0003.")],
    )

    # ---- Work orders ---------------------------------------------------------
    add_work_order(conn, "WO-0001", "EQ-0001", breakdown=1,
                   downtime_hours=12.0, total_cost_idr=50_000_000.0,
                   work_type="Corrective", discipline="Mechanical",
                   problem="Mechanical seal leak and loss of barrier fluid",
                   root_cause="Gland packing worn out and flush pressure low",
                   corrective_action="Replace gland packing and reset flush plan")
    add_work_order(conn, "WO-0002", "EQ-0001", breakdown=0,
                   work_type="Preventive", discipline="Mechanical",
                   problem="Scheduled seal flush verification")
    add_work_order(conn, "WO-0003", "EQ-0001", breakdown=1,
                   downtime_hours=4.5, total_cost_idr=20_000_000.0,
                   work_type="Corrective", discipline="Instrument",
                   problem="Pump vibration above limit", report_date="2025-03-02")
    add_work_order(conn, "WO-0004", "EQ-0002", breakdown=1,
                   downtime_hours=30.0, total_cost_idr=90_000_000.0,
                   work_type="Corrective", discipline="Process",
                   problem="Reactor temperature excursion", report_date="2025-04-11")
    add_work_order(conn, "WO-0005", "EQ-0002", breakdown=0,
                   work_type="Calibration", discipline="Instrument",
                   problem="Annual calibration")
    add_work_order(conn, "WO-0006", "EQ-0003", breakdown=1,
                   downtime_hours=6.0, total_cost_idr=10_000_000.0,
                   work_type="Predictive", discipline="Electrical",
                   problem="Compressor bearing degradation", report_date="2025-05-20")

    conn.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_db(tmp_path: Path) -> Path:
    """Buat indeks kosong dengan skema penuh, lalu kembalikan path-nya."""
    path = tmp_path / "plant_test.db"
    conn = registry.connect(path)
    try:
        conn.executescript(registry.SCHEMA)
        conn.commit()
    finally:
        conn.close()
    return path


@pytest.fixture
def empty_index(synthetic_db: Path) -> sqlite3.Connection:
    """Koneksi ke indeks dengan skema tapi tanpa data."""
    conn = registry.connect(synthetic_db)
    try:
        yield conn
    finally:
        conn.close()
        _clear_caches()


@pytest.fixture
def synthetic_index(synthetic_db: Path) -> sqlite3.Connection:
    """Koneksi ke indeks sintetis yang sudah terisi."""
    conn = registry.connect(synthetic_db)
    build_synthetic_index(conn)
    _clear_caches()
    try:
        yield conn
    finally:
        conn.close()
        _clear_caches()


@pytest.fixture
def synthetic_index_reopened(synthetic_db: Path) -> sqlite3.Connection:
    """Indeks sintetis yang dibuka sebagai koneksi kedua.

    Dipakai untuk membuktikan data benar-benar ada di file, bukan hanya di
    memori objek yang sama - kalau registry menyimpan cache di memori, test
    ini akan menangkapnya.
    """
    conn = registry.connect(synthetic_db)
    build_synthetic_index(conn)
    conn.close()
    _clear_caches()
    reopened = registry.connect(synthetic_db)
    try:
        yield reopened
    finally:
        reopened.close()
        _clear_caches()


# ---------------------------------------------------------------------------
# Dataset resmi (opsional)
# ---------------------------------------------------------------------------


def official_dataset_available() -> bool:
    """True kalau dataset CALIBER ada di mesin ini."""
    try:
        dataset_mod.find_dataset_root()
    except Exception:  # noqa: BLE001 - ketiadaan dataset itu normal, bukan error
        return False
    return True


#: Penanda untuk test yang benar-benar butuh dataset resmi. Test ini skip
#: dengan ALASAN yang terbaca, supaya "hijau" tidak disalahartikan sebagai
#: "tercover".
requires_official_dataset = pytest.mark.skipif(
    not official_dataset_available(),
    reason=(
        "Dataset CALIBER tidak ada di mesin ini (lisensi committee, sengaja "
        "tidak masuk repo). Jalankan `python -m plant.fetch_dataset` setelah "
        "menyalin dataset secara manual untuk menjalankan test ini."
    ),
)


@pytest.fixture(scope="session")
def official_dataset_root() -> Path:
    """Root dataset CALIBER, atau skip dengan alasan yang terbaca."""
    if not official_dataset_available():
        pytest.skip(
            "Dataset CALIBER tidak ada di mesin ini; lihat "
            "requires_official_dataset untuk cara mengaktifkannya."
        )
    return dataset_mod.find_dataset_root()


@pytest.fixture(scope="session")
def official_dataset(official_dataset_root: Path, tmp_path_factory):
    """Index yang dibangun dari dataset CALIBER sungguhan.

    Session-scoped karena membangunnya memakan sekitar 45 detik: 87 PDF
    satu halaman dibaca satu per satu, karena label dan nilai pada tabel
    datasheet berpasangan secara posisional. Linearisasi seluruh dokumen sekali
    jalan membuat metadata satu dokumen hilang kalau ada satu yang gagal.

    Database-nya di direktori sementara milik pytest, bukan di database
    pengembangan, jadi test ini tidak pernah mengubah indeks yang sedang
    dipakai demo dan tidak pernah menulis ke dalam repo.
    """
    tmp_dir = tmp_path_factory.mktemp("official_dataset")
    conn = registry.connect(tmp_dir / "official_test.db")
    try:
        registry.ingest_all(conn, official_dataset_root)
        yield conn
    finally:
        conn.close()
        _clear_caches()


# ---------------------------------------------------------------------------
# Stub dataset untuk route `/dataset`
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_dataset_root(tmp_path: Path) -> Path:
    """Dataset CALIBER palsu yang cukup untuk route `/dataset`.

    Rute `/dataset` membaca filesystem, bukan index, jadi tidak bisa diuji di
    atas indeks sintetis. Tanpa stub ini, test-nya hanya bisa lulus di mesin
    yang punya dataset resmi - persis pola "hijau lokal, merah di CI" yang
    sudah pernah menimpa repo ini.

    Yang dipin stub ini: 8 unit, masing-masing satu datasheet, dan satu baris
    work order. Cukup untuk `/dataset` mengembalikan 200 dengan angka yang
    bisa diperiksa, dan cukup kecil untuk tidak mengaburkan test.
    """
    from openpyxl import Workbook

    # Dibaca lewat modul, bukan alias: daftar tag harus sama persis dengan
    # yang dipakai ekstraktor, bukan salinan yang bisa basi.
    tags = extract_mod.EQUIPMENT_TAGS

    root = tmp_path / "stub-dataset"
    docs = root / "Set_01"
    docs.mkdir(parents=True)

    for tag in tags:
        (docs / f"Equipment Datasheet - {tag}.pdf").write_bytes(b"%PDF-1.4")
        for n in (1, 2, 3, 4, 5, 6, 7):
            (docs / f"OPL-{tag}-{n:02d} - Lesson_{n}.pdf").write_bytes(b"%PDF-1.4")

    wb = Workbook()
    ws = wb.active
    ws.title = "Maintenance History"
    ws.append(
        [
            "WO_Number", "Report_Date", "Equipment_Tag", "Equipment_Name",
            "Area_Name", "Criticality", "Functional_Location",
            "Related_Interlock", "Work_Type", "Discipline", "Breakdown",
            "Downtime_Hours", "Labor_Hours", "Total_Cost_IDR",
            "Labor_Cost_IDR", "Material_Cost_IDR", "Problem_Description",
            "Root_Cause", "Corrective_Action",
        ]
    )
    ws.append(
        [
            "WO-STUB-1", "2025-01-15", "GA-1201A", "STUB PUMP", "AREA ONE",
            "HIGH CRITICAL", "FL-GA-1201A", "TJC-LLD-IL-GA-1201A", "Corrective",
            "Mechanical", "Yes", 3.5, 1.0, 7_500_000.0, 1_000_000.0,
            6_500_000.0, "Stub problem", "Stub cause", "Stub action",
        ]
    )
    wb.save(root / "Maintenance History (All Equipment).xlsx")
    wb.close()
    return root


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


class ApiHarness:
    """Wrapper kecil di atas TestClient supaya test tidak mengulang header."""

    def __init__(self, client: Any, db_path: Path) -> None:
        self.client = client
        self.db_path = db_path
        self.headers = {"X-TrustHub-Token": "ci-test-token-abcdefghijklmnop"}

    def get(self, url: str, **kwargs: Any):
        return self.client.get(url, headers=self.headers, **kwargs)

    def post(self, url: str, **kwargs: Any):
        return self.client.post(url, headers=self.headers, **kwargs)

    def ask(self, question: str, **kwargs: Any):
        return self.post("/api/plant/ask", json={"question": question, **kwargs})


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stub_dataset_root: Path):
    """TestClient untuk /api/plant/* di atas indeks sintetis.

    Token dan path database disetel lewat environment karena `plant.api`
    membacanya saat modul di-import. Import dicache di level interpreter,
    jadi patch dilakukan sebelum import pertama.

    `TRUSTHUB_DATASET_ROOT` juga disetel, ke dataset palsu milik test. Rute
    `/dataset` membaca filesystem dan tidak punya index sebagai pengganti, jadi
    tanpa ini tiga test-nya hanya lulus di mesin yang punya dataset resmi dan
    gagal di CI. Namanya `TRUSTHUB_DATASET_ROOT` - itu yang dibaca
    `dataset.find_dataset_root`; `TRUSTHUB_PLANT_DATASET_ROOT` tidak pernah
    dibaca sama sekali.
    """
    db = tmp_path / "plant_api_test.db"
    build_synthetic_index(registry.connect(db))
    _clear_caches()

    monkeypatch.setenv("TRUSTHUB_API_TOKEN", "ci-test-token-abcdefghijklmnop")
    monkeypatch.setenv("TRUSTHUB_PLANT_DB_PATH", str(db))
    monkeypatch.setenv("TRUSTHUB_PLANT_LLM_MODE", "off")
    monkeypatch.setenv("TRUSTHUB_PLANT_ALLOW_EXTERNAL_LLM", "0")
    monkeypatch.setenv("TRUSTHUB_DATASET_ROOT", str(stub_dataset_root))

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import plant.api as plant_api

    # Router dibungkus app minimal, bukan diuji langsung dengan
    # TestClient(router). FastAPI memasang exception handler-nya sebagai
    # middleware pada level app, jadi TestClient(router) melempar HTTPException
    # ke pemanggil alih-alih mengubahnya jadi respons 404/503. Test yang
    # sengaja memeriksa penolakan itu akan gagal dengan cara yang menyesatkan.
    # App minimal ini juga mencerminkan cara main.py memasang router.
    app = FastAPI()
    app.include_router(plant_api.router)

    _clear_caches()
    with TestClient(app) as client:
        yield ApiHarness(client, db)
    _clear_caches()