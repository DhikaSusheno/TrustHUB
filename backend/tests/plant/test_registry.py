"""Test registry: skema, ingest, dan query.

Skema adalah kontrak antara `extract.py` (yang menulis) dan `retrieval.py` /
`conflicts.py` / `ask.py` (yang membaca). Kalau satu kolom hilang, yang paling
banyak gagal adalah pertanyaan pengguna, dan gejalanya terlihat seperti
"dokumennya tidak ada", bukan seperti bugs.

Test di sini sengaja memakai `synthetic_index_reopened` di beberapa tempat:
data harus benar-benar ada di file, bukan cuma di koneksi yang sama. Registry
yang menyimpan cache di memori akan lolos test yang hanya memakai satu
koneksi, lalu gagal begitu server berjalan dua worker.
"""

from __future__ import annotations

import pytest

from plant import registry

# `conftest` diimpor sebagai modul biasa, bukan sebagai `from .conftest`:
# folder test tidak punya __init__.py, jadi impor relatifnya gagal. pytest
# menyisipkan folder test ke sys.path, jadi impor datar ini yang benar.
from conftest import (
    FIXTURE_DOCUMENTS,
    FIXTURE_EQUIPMENT,
    FIXTURE_WORK_ORDERS,
)


# ---------------------------------------------------------------------------
# Skema
# ---------------------------------------------------------------------------


EXPECTED_TABLES = {
    "equipment",
    "documents",
    "doc_chunks",
    "document_parameters",
    "doc_fts",
    "work_orders",
    "failure_links",
    "plant_audit_log",
}


class TestSchema:
    def test_schema_is_idempotent(self, synthetic_db) -> None:
        # Dipanggil dua kali saat start-up. Kalau tidak idempoten, proses
        # kedua gagal start.
        import sqlite3

        conn = registry.connect(synthetic_db)
        try:
            conn.executescript(registry.SCHEMA)
            conn.executescript(registry.SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def test_all_tables_exist(self, synthetic_index) -> None:
        rows = synthetic_index.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
        ).fetchall()
        present = {r["name"] for r in rows}
        missing = EXPECTED_TABLES - present
        assert not missing, f"missing tables: {missing}"

    def test_fts_index_exists(self, synthetic_index) -> None:
        # Tanpa FTS5 retrieval tidak mungkin jalan, dan gejalanya "semua
        # pencarian mengembalikan kosong" - bukan "sistemnya rusak".
        assert "doc_fts" in {
            r["name"] for r in synthetic_index.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    @pytest.mark.parametrize(
        "table,columns",
        [
            ("documents", {"doc_id", "filename", "doc_type", "equipment_tag",
                           "approval_status", "revision", "doc_no",
                           "is_safety_critical"}),
            ("document_parameters", {"doc_id", "equipment_tag", "parameter",
                                     "value", "unit", "operator", "kind",
                                     "source"}),
            ("work_orders", {"wo_number", "equipment_tag", "work_type",
                             "discipline", "breakdown", "downtime_hours",
                             "total_cost_idr"}),
            ("equipment", {"equipment_tag", "equipment_name", "criticality",
                           "wo_count", "breakdown_count", "downtime_hours",
                           "total_cost_idr"}),
            ("plant_audit_log", {"question", "asked_at", "badge", "trust_score"}),
        ],
    )
    def test_required_columns_present(
        self, synthetic_index, table: str, columns: set[str]
    ) -> None:
        have = {r["name"] for r in synthetic_index.execute(f"PRAGMA table_info({table})")}
        assert columns <= have, f"{table} missing {columns - have}"

    def test_approval_status_is_never_guessed(self, synthetic_index) -> None:
        # Kolomnya punya DEFAULT 'unknown'. Kalau default-nya 'approved', setiap
        # dokumen tanpa marker ditandatangani secara tidak sengaja.
        row = synthetic_index.execute(
            "SELECT dflt_value FROM pragma_table_info('documents') "
            "WHERE name = 'approval_status'"
        ).fetchone()
        assert row is not None
        assert "approved" not in (row["dflt_value"] or "").lower()


# ---------------------------------------------------------------------------
# Koneksi
# ---------------------------------------------------------------------------


class TestConnect:
    def test_row_factory_is_dict(self, synthetic_db) -> None:
        # Hampir semua modul memakai `row["nama"]`. Kalau row_factory default,
        # setiap query gagal dengan TypeError.
        conn = registry.connect(synthetic_db)
        try:
            row = conn.execute("SELECT 1 AS n").fetchone()
            assert row["n"] == 1
        finally:
            conn.close()

    def test_foreign_keys_are_on(self, synthetic_db) -> None:
        conn = registry.connect(synthetic_db)
        try:
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        finally:
            conn.close()

    def test_path_is_honoured(self, tmp_path) -> None:
        target = tmp_path / "explicit.db"
        conn = registry.connect(target)
        try:
            conn.executescript(registry.SCHEMA)
            conn.commit()
        finally:
            conn.close()
        assert target.exists()

    def test_environment_variable_wins(self, tmp_path, monkeypatch) -> None:
        # Test dan CIDATABASE yang salah diam-diam membuat database kosong di
        # repo, dan semua test Retrieval lolos karena tidak ada yang mencari.
        target = tmp_path / "from_env.db"
        monkeypatch.setenv("TRUSTHUB_PLANT_DB_PATH", str(target))
        conn = registry.connect()
        try:
            conn.executescript(registry.SCHEMA)
            conn.commit()
        finally:
            conn.close()
        assert target.exists()


class TestDocId:
    def test_is_deterministic(self) -> None:
        # Doc id harus stabil antar proses; kalau tidak, citation lama tidak
        # bisa dibuka ke dokumen yang sama setelah reindex.
        a = registry._doc_id("OPL-EQ-0001-01 - Seal_Flush.pdf")
        b = registry._doc_id("OPL-EQ-0001-01 - Seal_Flush.pdf")
        assert a == b

    def test_differs_per_filename(self) -> None:
        assert registry._doc_id("a.pdf") != registry._doc_id("b.pdf")

    def test_is_usable_as_a_url_segment(self) -> None:
        doc_id = registry._doc_id("OPL-EQ-0001-01 - Seal_Flush.pdf")
        assert "/" not in doc_id and " " not in doc_id


class TestIso:
    """`_iso` meneruskan nilai apa adanya. Ia tidak mengurai apa pun.

    Itu pilihan, bukan kelalaian. `effective_date` di dataset CALIBER campur
    tiga format: "05-06-2026" (dd-mm-yyyy), "Sunday, 22 March 2026", dan
    "Thursday, 26 March 2026". Semuanya ambigu tanpa tahu format aslinya -
    "05-06-2026" bisa 5 Juni atau 6 Mei, dan tidak ada kolom yang
    menyuruhkannya.

    Normalisasi di sini berarti menebak, dan tanggal hasil tebakan terlihat
    seperti data. Untuk `report_date` tidak masalah: workbook maintenance
    menyimpannya sebagai ISO ("2025-12-06T15:46:00"), terukur pada 211 dari
    211 baris, jadi `ORDER BY report_date` benar secara leksikografis tanpa
    perlu diurai.
    """

    @pytest.mark.parametrize(
        "raw",
        ["2025-01-15", "15-01-2025", "15/01/2025", "Sunday, 22 March 2026",
         None, "", "  2025-01-15  ", 12345],
    )
    def test_never_raises(self, raw) -> None:
        registry._iso(raw)

    def test_date_objects_are_formatted(self) -> None:
        import datetime as dt

        out = registry._iso(dt.datetime(2025, 1, 15, 8, 30))
        assert out == "2025-01-15T08:30:00"

    def test_none_stays_none(self) -> None:
        # None berarti "tidak ada tanggal", dan itu berbeda dari tanggal yang
        # tidak bisa dibaca.
        assert registry._iso(None) is None

    def test_unparsable_text_is_not_a_fabricated_date(self) -> None:
        # "sometime last year" tetap "sometime last year". Kalau ia diubah jadi
        # None, hilang informasi bahwa dokumen memang menulis sesuatu; kalau
        # diubah jadi tanggal karangan, ia terlihat seperti data.
        assert registry._iso("sometime last year") == "sometime last year"

    def test_dd_mm_yyyy_is_not_silently_reordered(self) -> None:
        # Mengubahnya jadi "2026-06-05" berarti menebak bahwa kolomnya
        # dd-mm-yyyy. Untuk tanggal seperti 05-06-2026 tebakannya bisa salah
        # dan hasilnya tidak pernah ketahuan.
        assert registry._iso("05-06-2026") == "05-06-2026"


class TestSafetyCriticalClassification:
    """OPL dan interlock selalu safety-relevant; sisanya tidak.

    Alasannya isi dokumennya, bukan jenis filenya: OPL memuat prosedur trip dan
    permit, interlock memuat cause & effect. Datasheet, GA, dan Plot Plan
    memuat spesifikasi dan tata letak - tidak ada instruksi yang dijalankan
    sambil membacanya.
    """

    @pytest.mark.parametrize(
        "doc_type,expected",
        [("opl", True), ("interlock", True), ("datasheet", False),
         ("ga", False), ("plot_plan", False)],
    )
    def test_by_doc_type(self, doc_type: str, expected: bool) -> None:
        from plant.extract import DocMeta

        # Dikembalikan sebagai INTEGER 0/1 karena langsung masuk ke kolom
        # SQLite `INTEGER`, jadi yang diuji adalah nilai boolean-nya.
        assert bool(registry._safety_critical(DocMeta(doc_type=doc_type))) is expected

    def test_unknown_doc_type_is_not_safety_critical(self) -> None:
        # Tipe yang belum dikenal tidak boleh diasumsikan aman ATAU berbahaya.
        # Default-nya tidak safety-critical karena itu tidak memberi alasan
        # verbatim pada jawaban yang tidak perlu verbatim.
        from plant.extract import DocMeta

        assert bool(registry._safety_critical(DocMeta(doc_type="mystery"))) is False

    def test_returns_a_sqlite_integer(self) -> None:
        from plant.extract import DocMeta

        value = registry._safety_critical(DocMeta(doc_type="opl"))
        assert value in (0, 1)


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


class TestListEquipment:
    def test_returns_every_fixture_unit(self, synthetic_index) -> None:
        rows = registry.list_equipment(synthetic_index)
        assert len(rows) == FIXTURE_EQUIPMENT

    def test_sorted_by_tag(self, synthetic_index) -> None:
        tags = [r["equipment_tag"] for r in registry.list_equipment(synthetic_index)]
        assert tags == sorted(tags)

    def test_get_known_tag(self, synthetic_index) -> None:
        row = registry.get_equipment(synthetic_index, "EQ-0001")
        assert row and row["equipment_tag"] == "EQ-0001"

    def test_get_requires_the_canonical_upper_case_tag(self, synthetic_index) -> None:
        # Sengaja exact-match di level registry: tag disimpan uppercase dan
        # pemanggil wajib menormalkan. `api.py` melakukan `tag.upper()` di
        # setiap rute, dan itu diuji di test_api.py. Kalau normalisasi
        # dipindahkan ke sini, satu rute yang lupa memanggilnya akan mengembalikan
        # 404 untuk tag yang jelas ada.
        assert registry.get_equipment(synthetic_index, "eq-0001") is None

    def test_get_unknown_tag_is_none_not_an_exception(self, synthetic_index) -> None:
        # Panggilannya wajib mengembalikan None supaya pemanggil bisa menahan
        # HTTP 404 dengan daftar tag yang tersedia.
        assert registry.get_equipment(synthetic_index, "ZZ-9999") is None

    def test_empty_index(self, empty_index) -> None:
        assert registry.list_equipment(empty_index) == []


class TestListDocuments:
    def test_counts_match_the_fixture(self, synthetic_index) -> None:
        assert len(registry.list_documents(synthetic_index)) == FIXTURE_DOCUMENTS

    def test_filter_by_equipment(self, synthetic_index) -> None:
        rows = registry.list_documents(synthetic_index, equipment_tag="EQ-0001")
        assert rows
        assert all(r["equipment_tag"] == "EQ-0001" for r in rows)

    def test_filter_by_doc_type(self, synthetic_index) -> None:
        rows = registry.list_documents(synthetic_index, doc_type="interlock")
        assert rows
        assert all(r["doc_type"] == "interlock" for r in rows)

    def test_filters_combine(self, synthetic_index) -> None:
        rows = registry.list_documents(
            synthetic_index, equipment_tag="EQ-0001", doc_type="opl"
        )
        assert all(
            r["equipment_tag"] == "EQ-0001" and r["doc_type"] == "opl" for r in rows
        )

    def test_unknown_filter_returns_empty(self, synthetic_index) -> None:
        assert registry.list_documents(synthetic_index, equipment_tag="ZZ-9999") == []

    def test_get_document(self, synthetic_index) -> None:
        row = registry.get_document(synthetic_index, "d1a")
        assert row and row["doc_id"] == "d1a"

    def test_get_unknown_document_is_none(self, synthetic_index) -> None:
        assert registry.get_document(synthetic_index, "nope") is None


class TestListWorkOrders:
    def test_counts_match_the_fixture(self, synthetic_index) -> None:
        assert len(registry.list_work_orders(synthetic_index)) == FIXTURE_WORK_ORDERS

    def test_filter_by_equipment(self, synthetic_index) -> None:
        rows = registry.list_work_orders(synthetic_index, equipment_tag="EQ-0001")
        assert rows and all(r["equipment_tag"] == "EQ-0001" for r in rows)

    def test_breakdown_only(self, synthetic_index) -> None:
        rows = registry.list_work_orders(synthetic_index, breakdown_only=True)
        assert rows and all(r["breakdown"] for r in rows)
        # Fixture: WO-0001, WO-0003, WO-0004, WO-0006 adalah breakdown.
        assert len(rows) == 4

    def test_breakdown_only_is_stricter_than_all(self, synthetic_index) -> None:
        all_rows = registry.list_work_orders(synthetic_index)
        breakdowns = registry.list_work_orders(synthetic_index, breakdown_only=True)
        assert len(breakdowns) < len(all_rows)

    def test_sorted_oldest_first(self, synthetic_index) -> None:
        # Urut naik, bukan turun. "Riwayat maintenance" dibaca sebagai kronologi:
        # operator ingin melihat urutan kejadian, dan breakdown berikutnya
        #gebnisnya terlihat paling dekat di akhir. UI yang mau terbaru dulu
        # membalikkan sendiri.
        dates = [r["report_date"] for r in registry.list_work_orders(synthetic_index)]
        assert dates == sorted(dates)

    def test_breakdown_filter_keeps_the_same_order(self, synthetic_index) -> None:
        breakdowns = registry.list_work_orders(synthetic_index, breakdown_only=True)
        dates = [r["report_date"] for r in breakdowns]
        assert dates == sorted(dates)


class TestGraph:
    def test_has_nodes_and_links(self, synthetic_index) -> None:
        g = registry.graph(synthetic_index)
        assert g["nodes"] and g["links"]

    def test_every_node_has_an_id_and_label(self, synthetic_index) -> None:
        for node in registry.graph(synthetic_index)["nodes"]:
            assert node.get("id")
            assert node.get("label")

    def test_links_reference_existing_nodes(self, synthetic_index) -> None:
        # Link yang menunjuk node yang tidak ada membuat graf menampilkan
        # garis ke Nowhere, dan tidak ada error.
        g = registry.graph(synthetic_index)
        ids = {n["id"] for n in g["nodes"]}
        for link in g["links"]:
            assert link["source"] in ids, f"dangling source {link['source']}"
            assert link["target"] in ids, f"dangling target {link['target']}"

    def test_empty_index_gives_an_empty_graph(self, empty_index) -> None:
        g = registry.graph(empty_index)
        assert g["nodes"] == [] and g["links"] == []


# ---------------------------------------------------------------------------
# Known entities
# ---------------------------------------------------------------------------


class TestKnownReferences:
    def test_includes_document_numbers(self, synthetic_index) -> None:
        refs = registry.known_references(synthetic_index)
        assert "OPL-EQ-0001-01" in {r.upper() for r in refs}

    def test_is_uppercase(self, synthetic_index) -> None:
        refs = registry.known_references(synthetic_index)
        assert all(r == r.upper() for r in refs)

    def test_empty_index(self, empty_index) -> None:
        assert registry.known_references(empty_index) == set()

    def test_usable_as_a_frozenset(self, synthetic_index) -> None:
        assert isinstance(frozenset(registry.known_references(synthetic_index)), frozenset)


class TestKnownInstrumentTags:
    def test_includes_parameter_tags(self, synthetic_index) -> None:
        tags = registry.known_instrument_tags(synthetic_index)
        assert "PSLL-0001" in {t.upper() for t in tags}
        assert "TSHH-0002" in {t.upper() for t in tags}

    def test_excludes_equipment_tags(self, synthetic_index) -> None:
        # Kalau tag equipment ikut di sini, pertanyaan tentang unit yang tidak
        # dikenal bisa lolos sebagai "tag instrumen yang dikenal".
        tags = {t.upper() for t in registry.known_instrument_tags(synthetic_index)}
        assert "EQ-0001" not in tags

    def test_empty_index(self, empty_index) -> None:
        assert registry.known_instrument_tags(empty_index) == set()


class TestMissingOplNumbers:
    def test_returns_a_list(self, synthetic_index) -> None:
        assert isinstance(
            registry.missing_opl_numbers(synthetic_index, "EQ-0001"), list
        )

    def test_unknown_equipment_does_not_raise(self, synthetic_index) -> None:
        assert isinstance(
            registry.missing_opl_numbers(synthetic_index, "ZZ-9999"), list
        )


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class TestLogAnswer:
    def test_records_the_question_and_badge(self, synthetic_index) -> None:
        registry.log_answer(
            synthetic_index, "what is the seal flush plan", "EQ-0001",
            "VERIFY", 0.72, ["d1a"], "engineer",
        )
        row = synthetic_index.execute(
            "SELECT * FROM plant_audit_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row["question"] == "what is the seal flush plan"
        assert row["badge"] == "VERIFY"

    def test_records_an_empty_source_list(self, synthetic_index) -> None:
        # Penolakan juga perlu dicatat: "sistem tidak menjawab apa pun" adalah
        # informasi yang sama pentingnya dengan jawaban.
        registry.log_answer(
            synthetic_index, "who is the CEO of Starbucks", None,
            "DO NOT EXECUTE", 0.0, [], "engineer",
        )
        row = synthetic_index.execute(
            "SELECT * FROM plant_audit_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row["badge"] == "DO NOT EXECUTE"

    def test_never_raises_on_long_input(self, synthetic_index) -> None:
        registry.log_answer(
            synthetic_index, "x" * 5000, None, "DO NOT EXECUTE", 0.0, [], "engineer"
        )

    def test_survives_reopen(self, synthetic_db) -> None:
        conn = registry.connect(synthetic_db)
        conn.executescript(registry.SCHEMA)
        registry.log_answer(conn, "q", None, "VERIFY", 0.6, [], "engineer")
        conn.commit()
        conn.close()

        again = registry.connect(synthetic_db)
        try:
            assert again.execute(
                "SELECT COUNT(*) AS n FROM plant_audit_log"
            ).fetchone()["n"] == 1
        finally:
            again.close()


class TestDataIsOnDisk:
    def test_reopening_sees_the_same_rows(self, synthetic_index_reopened) -> None:
        # Kalau registry menyimpan cache di memori, test yang hanya memakai satu
        # koneksi lolos, lalu server gagal begitu dua worker berjalan.
        conn = synthetic_index_reopened
        assert len(registry.list_equipment(conn)) == FIXTURE_EQUIPMENT
        assert len(registry.list_documents(conn)) == FIXTURE_DOCUMENTS
        assert len(registry.list_work_orders(conn)) == FIXTURE_WORK_ORDERS


# ---------------------------------------------------------------------------
# ingest_all reports what it stored
# ---------------------------------------------------------------------------


class TestIngestAllCounts:
    """`ingest_all` butuh dataset nyata, jadi diuji lewat dataset aslinya."""

    def test_reports_parameters_and_deduplication(
        self, official_dataset, official_dataset_root
    ) -> None:
        # `parameters` dihitung ulang dari database, bukan diteruskan dari
        # doc_counts, supaya angkanya sama dengan yang benar-benar ditulis.
        counts = registry.ingest_all(official_dataset, official_dataset_root)
        assert "parameters" in counts
        assert "parameter_values_extracted" in counts
        assert counts["documents"] > 0
        assert counts["work_orders"] > 0

    def test_stored_parameters_never_exceed_extracted(
        self, official_dataset, official_dataset_root
    ) -> None:
        # Baris disimpan dengan INSERT OR IGNORE, jadi nilai yang ditulis di
        # beberapa dokumen dihitung sekali. Kalau ini terbalik, berarti dedup
        # mati dan setiap dokumen yang mengulang setpoint menambah baris.
        counts = registry.ingest_all(official_dataset, official_dataset_root)
        assert counts["parameters"] <= counts["parameter_values_extracted"]

    def test_missing_root_raises_dataset_not_found(self, synthetic_index, tmp_path) -> None:
        # Bukan mengembalikan nol. Nol dibaca sebagai "dataset ada tapi tidak
        # berisi apa pun", dan itu kesimpulan yang salah untuk demo.
        from plant import dataset

        with pytest.raises(dataset.DatasetNotFound):
            registry.ingest_all(synthetic_index, tmp_path / "does-not-exist")