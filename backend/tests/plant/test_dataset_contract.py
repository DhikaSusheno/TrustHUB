"""Test untuk `plant/dataset.py`, dan kontrak dataset resmi.

Dua bagian dengan sifat berbeda.

Yang pertama adalah `dataset_report()` di atas dataset buatan. Hitungan
downtime, biaya, dan jumlah OPL adalah angka yang dikutip di deck, dan salah
satu saja bisa salah hitung tanpa kelihatan. Dataset buatan di sini ditulis
dengan angka yang bisa dihitung dengan tangan, jadi test membandingkan
agregasi dengan hasil yang sudah diketahui benar, bukan dengan output
sebelumnya.

Bagian kedua adalah kontrak dataset resmi: jumlah dokumen per jenis, unit
yang hanya kehilangan satu OPL, dan angka work order. Semua itu ditandai
`requires_official_dataset` dan skip dengan alasan yang tercetak, karena
lisensi committee melarang dataset ini masuk repo - jadi CI tidak memilikinya
dan tidak boleh ikut mengarang angkanya.

Angka di bagian kedua disalin dari pengukuran, bukan dari harapan. Kalau
suatu saat dataset resmi diganti versinya, test-test ini akan gagal, dan itu
memang yang mau terjadi: deck ikut gagal, bukan diam-diam jadi tidak benar.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from plant import dataset as dataset_mod
from plant import extract

from conftest import requires_official_dataset


# ---------------------------------------------------------------------------
# _num
# ---------------------------------------------------------------------------


class TestNum:
    """Coercion angka dari workbook.

    Kolom numerik di workbook disimpan campur float dan teks. Yang penting
    di sini adalah nilai yang tidak terbaca jadi `None` dan bukan `0.0`:
    downtime yang gagal dibaca tidak sama dengan downtime nol, dan
    menjadikannya nol diam-diam akan menurunkan total downtime yang dikutip.
    """

    @pytest.mark.parametrize(
        "value,expected",
        [
            (12, 12.0),
            (12.5, 12.5),
            ("12.5", 12.5),
            (" 12.5 ", 12.5),
            (-3, -3.0),
            (None, None),
            ("", None),
            ("  ", None),
            ("n/a", None),
            ("abc", None),
            (True, None),
            (False, None),
        ],
    )
    def test_coercion(self, value, expected):
        assert dataset_mod._num(value) == expected

    def test_booleans_are_rejected(self):
        # `bool` adalah subclass dari `int`, jadi tanpa guard eksplisit
        # `True` akan jadi 1.0 - sebuah work order yang ditandai benar akan
        # menyumbang downtime satu jam.
        assert dataset_mod._num(True) is None
        assert dataset_mod._num(False) is None

    def test_indonesian_thousands_separator_is_not_a_number(self):
        # "1.234.567" tidak bisa jadi float dengan titik sebagai pemisah ribuan.
        # Nilainya jadi None dan tidak ikut dijumlahkan. Ini keterbatasan yang
        # diketahui, bukan sesuatu yang dipoles diam-diam: kalau workbook suatu
        # saat menyimpan biaya sebagai teks bergaya Indonesia, totalnya akan
        # terlalu kecil dan angka di deck ikut salah.
        assert dataset_mod._num("1.234.567") is None
        assert dataset_mod._num("1,5") is None


# ---------------------------------------------------------------------------
# _iso
# ---------------------------------------------------------------------------


class TestIso:
    """`_iso` meneruskan nilai apa adanya, tanpa menebak format.

    Alasan disengaja: tanggal di workbook bisa berupa `datetime`, bisa berupa
    string yang sudah terformat, dan bisa berupa string yang formatnya salah.
    Mengubahnya ke ISO berarti menebak, dan tebakan pada tanggal adalah
    kesalahan diam-diam. Nilai asli lebih berguna untuk ditelusuri.
    """

    def test_datetime_is_converted(self):
        import datetime

        assert (
            dataset_mod._iso(datetime.datetime(2025, 3, 2, 0, 0))
            == "2025-03-02T00:00:00"
        )

    def test_date_is_converted(self):
        import datetime

        assert (
            dataset_mod._iso(datetime.date(2025, 3, 2)) == "2025-03-02"
        )

    def test_string_is_passed_through_verbatim(self):
        # Bukan "02-03-2025" dan bukan "2025-03-02". Kalau teksnya sudah
        # format lain, dia tetap seperti aslinya.
        assert dataset_mod._iso("02-03-2025") == "02-03-2025"
        assert dataset_mod._iso("05 June 2026") == "05 June 2026"

    def test_none_stays_none(self):
        assert dataset_mod._iso(None) is None

    def test_unparseable_string_is_not_an_exception(self):
        # Workbook bisa menyimpan "TBD" atau "-". Itu harus bertahan supaya
        # bisa dilihat, bukan meledak saat menghitung date_range.
        assert dataset_mod._iso("TBD") == "TBD"


# ---------------------------------------------------------------------------
# Penemuan dataset
# ---------------------------------------------------------------------------


class TestLooksLikeDataset:
    """Deteksi rootdataset dari isinya, bukan dari namanya."""

    def _make(self, root: Path, tags: list[str]) -> None:
        for tag in tags:
            (root / f"Equipment Datasheet - {tag}.pdf").write_bytes(b"x")

    def test_directory_with_most_tags_is_a_dataset(self, tmp_path):
        self._make(tmp_path, extract.EQUIPMENT_TAGS)
        assert dataset_mod._looks_like_dataset(tmp_path)

    def test_directory_with_half_the_tags_is_a_dataset(self, tmp_path):
        # Ambangnya setengah, bukan semua. Meminta semua tag akan menolak
        # dataset yang sah kalau satu unitnya memang tidak ada dokumen.
        self._make(tmp_path, extract.EQUIPMENT_TAGS[:4])
        assert dataset_mod._looks_like_dataset(tmp_path)

    def test_directory_with_too_few_tags_is_rejected(self, tmp_path):
        # Folder unduhan lain di Downloads tidak boleh dianggap dataset. Ini
        # yang menjaga pencarian tidak memilih folder yang salah.
        self._make(tmp_path, extract.EQUIPMENT_TAGS[:2])
        assert not dataset_mod._looks_like_dataset(tmp_path)

    def test_file_is_not_a_dataset(self, tmp_path):
        f = tmp_path / "dataset.pdf"
        f.write_bytes(b"x")
        assert not dataset_mod._looks_like_dataset(f)

    def test_missing_directory_is_rejected(self, tmp_path):
        assert not dataset_mod._looks_like_dataset(tmp_path / "nope")

    def test_empty_directory_is_rejected(self, tmp_path):
        assert not dataset_mod._looks_like_dataset(tmp_path)

    def test_tags_are_matched_in_subdirectories(self, tmp_path):
        # Folder hasil unzip punya satu level wrapper, jadi dokumennya satu
        # folder lebih dalam dari root yang benar.
        deep = tmp_path / "Case 1_ Manufacturing Knowledge Hub" / "Set_01"
        deep.mkdir(parents=True)
        self._make(deep, extract.EQUIPMENT_TAGS)
        assert dataset_mod._looks_like_dataset(tmp_path)


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Direktori rumah palsu tanpa folder Downloads.

    Tanpa ini, test yang seharusnya gagal bisa saja "berhasil" justru karena
    dataset asli ada di Downloads mesin ini - dan hasilnya berbeda di CI, yang
    tidak punya dataset. `Path.home` dipatch, bukan environment variable,
    karena `dataset.find_dataset_root` memanggilnya secara langsung.
    """
    fake = tmp_path / "fake-home"
    fake.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake))
    return fake


class TestFindDatasetRoot:
    def test_explicit_path_wins(self, tmp_path):
        root = tmp_path / "ds"
        root.mkdir()
        for tag in extract.EQUIPMENT_TAGS:
            (root / f"Datasheet - {tag}.pdf").write_bytes(b"x")
        assert dataset_mod.find_dataset_root(str(root)) == root.resolve()

    def test_explicit_wrapper_folder_is_accepted(self, tmp_path):
        """Folder pembungkus hasil unzip juga boleh dipakai sebagai root.

        `rglob` bersifat rekursif, jadi wrapper dikenali begitu saja. Yang
        penting bukan path mana yang dikembalikan, tapi bahwa semua dokumennya
        terlihat dari path itu - kalau tidak, `ingest_all` akan membangun
        indeks nol dokumen dan terlihat seperti sistem yang bekerja.
        """
        wrapper = tmp_path / "Case 1_ Manufacturing Knowledge Hub-20260925T172658Z-1-001"
        inner = wrapper / "Case 1_ Manufacturing Knowledge Hub" / "Set_01"
        inner.mkdir(parents=True)
        for tag in extract.EQUIPMENT_TAGS:
            (inner / f"Datasheet - {tag}.pdf").write_bytes(b"x")
        found = dataset_mod.find_dataset_root(str(wrapper))
        assert found == wrapper.resolve()
        assert len(extract.iter_dataset_files(str(found))) == len(
            extract.EQUIPMENT_TAGS
        )

    def test_env_var_is_consulted(self, tmp_path, monkeypatch):
        root = tmp_path / "from-env"
        root.mkdir()
        for tag in extract.EQUIPMENT_TAGS:
            (root / f"Datasheet - {tag}.pdf").write_bytes(b"x")
        monkeypatch.setenv("TRUSTHUB_DATASET_ROOT", str(root))
        assert dataset_mod.find_dataset_root() == root.resolve()

    def test_explicit_beats_env(self, tmp_path, monkeypatch):
        explicit = tmp_path / "explicit"
        from_env = tmp_path / "env"
        for d in (explicit, from_env):
            d.mkdir()
            for tag in extract.EQUIPMENT_TAGS:
                (d / f"Datasheet - {tag}.pdf").write_bytes(b"x")
        monkeypatch.setenv("TRUSTHUB_DATASET_ROOT", str(from_env))
        assert dataset_mod.find_dataset_root(str(explicit)) == explicit.resolve()

    def test_blank_env_var_is_ignored(self, tmp_path, monkeypatch):
        # String kosong dari CI wajib diperlakukan sebagai "tidak diisi", bukan
        # sebagai path "" yang menunjuk direktori kerja.
        monkeypatch.setenv("TRUSTHUB_DATASET_ROOT", "   ")
        root = tmp_path / "ds"
        root.mkdir()
        for tag in extract.EQUIPMENT_TAGS:
            (root / f"Datasheet - {tag}.pdf").write_bytes(b"x")
        monkeypatch.setenv("TRUSTHUB_DATASET_ROOT", "")
        assert dataset_mod.find_dataset_root(str(root)) == root.resolve()

    def test_missing_raises_with_actionable_advice(
        self, tmp_path, monkeypatch, isolated_home
    ):
        monkeypatch.setenv("TRUSTHUB_DATASET_ROOT", str(tmp_path / "nope"))
        monkeypatch.setattr(dataset_mod, "EQUIPMENT_TAGS", ["ZZ-9999"])
        with pytest.raises(dataset_mod.DatasetNotFound) as exc:
            dataset_mod.find_dataset_root()
        message = str(exc.value)
        # Pesan error harus menyebut cara memperbaikinya. Tanpa itu, user
        # hanya melihat "not found" dan tidak tahu harus melakukan apa.
        assert "TRUSTHUB_DATASET_ROOT" in message
        assert "fetch_dataset" in message

    def test_raises_rather_than_returning_a_wrong_path(
        self, tmp_path, monkeypatch, isolated_home
    ):
        """Tidak boleh ada fallback diam-diam ke direktori yang salah.

        `ingest_all` melempar DatasetNotFound kalau root hilang, dan itu
        sengaja: membangun indeks dari folder yang bukan dataset akan
        menghasilkan 0 dokumen dan terlihat seperti sistem yang bekerja.
        """
        monkeypatch.setenv("TRUSTHUB_DATASET_ROOT", str(tmp_path / "nope"))
        monkeypatch.setattr(dataset_mod, "EQUIPMENT_TAGS", ["ZZ-9999"])
        with pytest.raises(dataset_mod.DatasetNotFound):
            dataset_mod.find_dataset_root()

    def test_an_unrelated_directory_is_not_mistaken_for_the_dataset(
        self, tmp_path, monkeypatch, isolated_home
    ):
        """Folder biasa harus ditolak, bukan dianggap dataset.

        Ini kasus nyata di mesin ini: folder Downloads berisi 119 direktori,
        dan tanpa ambang yang benar `find_dataset_root` akan mengambil yang
        mana saja yang kebetulan terurut lebih dulu.
        """
        monkeypatch.setenv("TRUSTHUB_DATASET_ROOT", str(tmp_path / "nope"))
        unrelated = isolated_home / "Downloads" / "Some Other Project"
        unrelated.mkdir(parents=True)
        (unrelated / "notes.pdf").write_bytes(b"x")
        with pytest.raises(dataset_mod.DatasetNotFound):
            dataset_mod.find_dataset_root()

    def test_the_tag_threshold_is_never_zero(self, tmp_path, monkeypatch):
        """Ambang deteksi tidak boleh turun ke nol.

        `hits >= len(EQUIPMENT_TAGS) // 2` dengan satu tag memberi ambang 0,
        dan setiap direktori yang ada akan lolos - termasuk `Downloads/Test`,
        `Downloads/C#`, dan 100+ folder lain yang ada di mesin ini.
        """
        monkeypatch.setattr(dataset_mod, "EQUIPMENT_TAGS", ["GA-1201A"])
        empty = tmp_path / "empty"
        empty.mkdir()
        assert not dataset_mod._looks_like_dataset(empty)

        tagged = tmp_path / "tagged"
        tagged.mkdir()
        (tagged / "Datasheet - GA-1201A.pdf").write_bytes(b"x")
        assert dataset_mod._looks_like_dataset(tagged)


# ---------------------------------------------------------------------------
# resolve_xlsx
# ---------------------------------------------------------------------------


class TestResolveXlsx:
    def test_finds_the_exact_name(self, tmp_path):
        target = tmp_path / "Maintenance History (All Equipment).xlsx"
        target.write_bytes(b"x")
        assert dataset_mod.resolve_xlsx(tmp_path) == target

    def test_falls_back_to_a_name_containing_maintenance(self, tmp_path):
        # Nama file bisa berbeda. Pencocokan longgar ini yang membuatnya tetap
        # bekerja, dan hanya dipakai kalau nama persis tidak ada.
        target = tmp_path / "maintenance_history_final.xlsx"
        target.write_bytes(b"x")
        assert dataset_mod.resolve_xlsx(tmp_path) == target

    def test_exact_name_beats_fuzzy_name(self, tmp_path):
        exact = tmp_path / "Maintenance History (All Equipment).xlsx"
        fuzzy = tmp_path / "zz_maintenance_old.xlsx"
        fuzzy.write_bytes(b"x")
        exact.write_bytes(b"x")
        assert dataset_mod.resolve_xlsx(tmp_path) == exact

    def test_is_deterministic_among_several_fuzzy_matches(self, tmp_path):
        # Kalau ada dua yang cocok samar, hasilnya harus tetap sama setiap
        # kali dijalankan. Urutan rglob tidak dijamin, jadi yang diurutkan
        # dulu sebelum diambil.
        for name in ("bbb_maintenance.xlsx", "aaa_maintenance.xlsx"):
            (tmp_path / name).write_bytes(b"x")
        picks = {dataset_mod.resolve_xlsx(tmp_path) for _ in range(5)}
        assert len(picks) == 1, picks

    def test_missing_workbook_returns_none(self, tmp_path):
        assert dataset_mod.resolve_xlsx(tmp_path) is None

    def test_unrelated_workbook_returns_none(self, tmp_path):
        (tmp_path / "Equipment List.xlsx").write_bytes(b"x")
        assert dataset_mod.resolve_xlsx(tmp_path) is None

    def test_searches_subdirectories(self, tmp_path):
        nested = tmp_path / "workbooks"
        nested.mkdir()
        target = nested / "Maintenance History (All Equipment).xlsx"
        target.write_bytes(b"x")
        assert dataset_mod.resolve_xlsx(tmp_path) == target


# ---------------------------------------------------------------------------
# Dataset buatan untuk menguji agregasi
# ---------------------------------------------------------------------------

#: Header sheet maintenance. Nama kolom dipakai apa adanya sebagai kunci
#: dict, jadi daftar ini adalah kontrak antara workbook dan kode.
MAINT_HEADER = [
    "WO_Number",
    "Report_Date",
    "Equipment_Tag",
    "Equipment_Name",
    "Area_Name",
    "Criticality",
    "Functional_Location",
    "Related_Interlock",
    "Work_Type",
    "Discipline",
    "Breakdown",
    "Downtime_Hours",
    "Labor_Hours",
    "Total_Cost_IDR",
    "Labor_Cost_IDR",
    "Material_Cost_IDR",
    "Problem_Description",
    "Root_Cause",
    "Corrective_Action",
]


def _write_maintenance_workbook(path: Path, rows: list[list[Any]]) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    # Sheet pertama bukan sheet maintenance - ini persis seperti workbook
    # resmi, yang punya sheet `Explanation` lebih dulu. Selector harus
    # membaca header, bukan mengambil sheet pertama.
    explanation = wb.active
    explanation.title = "Explanation"
    explanation.append(["Field", "Meaning"])
    explanation.append(
        ["Equipment_Tag", "JOIN KEY to all other documents"]
    )
    sheet = wb.create_sheet("Maintenance History")
    sheet.append(MAINT_HEADER)
    for row in rows:
        sheet.append(row)
    wb.save(path)
    wb.close()


def _wo(
    number: str,
    tag: str,
    *,
    report_date: Any = "2025-01-15",
    work_type: str = "Corrective",
    discipline: str = "Mechanical",
    breakdown: str = "No",
    downtime: Any = 0.0,
    cost: Any = 0.0,
) -> list[Any]:
    """Satu baris work order, dengan kolom lain diisi default."""
    row: list[Any] = [""] * len(MAINT_HEADER)
    values = {
        "WO_Number": number,
        "Report_Date": report_date,
        "Equipment_Tag": tag,
        "Equipment_Name": f"NAME OF {tag}",
        "Area_Name": "AREA ONE",
        "Criticality": "HIGH CRITICAL",
        "Functional_Location": f"FL-{tag}",
        "Related_Interlock": f"TJC-LLD-IL-{tag}",
        "Work_Type": work_type,
        "Discipline": discipline,
        "Breakdown": breakdown,
        "Downtime_Hours": downtime,
        "Labor_Hours": 2.0,
        "Total_Cost_IDR": cost,
        "Labor_Cost_IDR": 1_000_000.0,
        "Material_Cost_IDR": 2_000_000.0,
        "Problem_Description": "Synthetic problem for test",
        "Root_Cause": "Synthetic cause",
        "Corrective_Action": "Synthetic action",
    }
    for i, key in enumerate(MAINT_HEADER):
        row[i] = values[key]
    return row


@pytest.fixture
def synthetic_dataset_root(tmp_path: Path) -> Path:
    """DatasetCALIBER-buatan dengan hitungan yang bisa dihitung manual.

    Isinya:
      - 8 unit, masing-masing 1 datasheet + 1 interlock + 1 plot plan + 1 GA
      - 7 OPL per unit, KECUALI GA-1201A yang kehilangan nomor 4
      - 8 P&ID PNG
      - 4 work order: 2 breakdown (12 jam + 4.5 jam, 50 juta + 20 juta),
        1 preventive tanpa downtime, 1 breakdown tanpa downtime

    Jadi yang harus keluar: downtime 16.5 jam, total biaya 70 juta, biaya
    breakdown 70 juta, 3 breakdown.
    """
    root = tmp_path / "synthetic-dataset"
    docs = root / "Set_01"
    docs.mkdir(parents=True)

    for tag in extract.EQUIPMENT_TAGS:
        (docs / f"Equipment Datasheet - {tag}.pdf").write_bytes(b"%PDF-1.4")
        (docs / f"Interlock Logic Diagram - {tag}.pdf").write_bytes(b"%PDF-1.4")
        (docs / f"Plot Plan - Set 01 - {tag}.pdf").write_bytes(b"%PDF-1.4")
        (docs / f"GA Drawing - {tag}.pdf").write_bytes(b"%PDF-1.4")
        numbers = [1, 2, 3, 5, 6, 7] if tag == "GA-1201A" else [1, 2, 3, 4, 5, 6, 7]
        for n in numbers:
            (docs / f"OPL-{tag}-{n:02d} - Lesson_{n}.pdf").write_bytes(b"%PDF-1.4")
        (docs / f"P&ID Set {tag}.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    _write_maintenance_workbook(
        root / "Maintenance History (All Equipment).xlsx",
        [
            _wo("WO-1", "GA-1201A", breakdown="Yes", downtime=12.0, cost=50_000_000.0),
            _wo("WO-2", "GA-1201A", breakdown="No", work_type="Preventive",
                downtime=0.0, cost=0.0, report_date="2025-03-02"),
            _wo("WO-3", "GA-1201A", breakdown="Yes", downtime=4.5, cost=20_000_000.0,
                discipline="Instrument", report_date="2025-05-20"),
            _wo("WO-4", "YD-2301", breakdown="Yes", downtime=0.0, cost=0.0,
                discipline="Process", report_date="2024-06-04"),
        ],
    )
    return root


class TestReadMaintenanceHistory:
    def test_reads_every_row(self, synthetic_dataset_root):
        rows = dataset_mod.read_maintenance_history(synthetic_dataset_root)
        assert len(rows) == 4

    def test_column_names_are_preserved(self, synthetic_dataset_root):
        row = dataset_mod.read_maintenance_history(synthetic_dataset_root)[0]
        assert row["WO_Number"] == "WO-1"
        assert row["Equipment_Tag"] == "GA-1201A"

    def test_numeric_columns_become_floats(self, synthetic_dataset_root):
        row = dataset_mod.read_maintenance_history(synthetic_dataset_root)[0]
        assert row["Downtime_Hours"] == 12.0
        assert row["Total_Cost_IDR"] == 50_000_000.0

    def test_breakdown_flag_is_normalised_to_a_string(self, synthetic_dataset_root):
        # `str(... or "").strip()`: angka 1/0 dan boolean di kolom ini
        # menjadi "Yes"/"No" supaya perbandingan di agregasi tidak lupus.
        row = dataset_mod.read_maintenance_history(synthetic_dataset_root)[0]
        assert row["Breakdown"] == "Yes"

    def test_sheet_is_found_by_header_not_by_position(self, synthetic_dataset_root):
        # Workbook punya sheet `Explanation` lebih dulu. Kalau selector ambil
        # sheet pertama, history akan terbaca kosong dan semua total nol.
        rows = dataset_mod.read_maintenance_history(synthetic_dataset_root)
        assert rows, "sheet maintenance tidak ditemukan"

    def test_missing_workbook_raises_dataset_not_found(self, tmp_path):
        with pytest.raises(dataset_mod.DatasetNotFound):
            dataset_mod.read_maintenance_history(tmp_path)

    def test_workbook_without_wo_number_column_raises(self, tmp_path):
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["Something", "Else"])
        ws.append([1, 2])
        wb.save(tmp_path / "Maintenance History (All Equipment).xlsx")
        wb.close()
        with pytest.raises(dataset_mod.DatasetNotFound):
            dataset_mod.read_maintenance_history(tmp_path)

    def test_blank_rows_are_skipped(self, tmp_path):
        _write_maintenance_workbook(
            tmp_path / "Maintenance History (All Equipment).xlsx",
            [_wo("WO-1", "GA-1201A"), [None] * len(MAINT_HEADER)],
        )
        assert len(dataset_mod.read_maintenance_history(tmp_path)) == 1


class TestDatasetReportOnSyntheticDataset:
    """Agregasi diuji terhadap angka yang bisa dihitung dengan tangan."""

    @pytest.fixture
    def report(self, synthetic_dataset_root) -> dataset_mod.DatasetReport:
        return dataset_mod.dataset_report(str(synthetic_dataset_root))

    def test_pdf_count(self, report):
        # 8 unit x (4 dokumen + 7 OPL) - 1 OPL yang hilang = 32 + 55 = 87.
        assert report.pdf_count == 87

    def test_png_count(self, report):
        assert report.png_count == 8

    def test_doc_type_counts(self, report):
        assert report.by_doc_type == {
            "datasheet": 8, "interlock": 8, "plot_plan": 8, "ga": 8,
        }

    def test_opl_counts_per_equipment(self, report):
        assert report.opl_counts["GA-1201A"] == 6
        assert report.opl_counts["YD-2301"] == 7

    def test_the_one_missing_opl_is_reported(self, report):
        # Ini demo "dokumen yang benar-benar hilang", jadi harus disebut,
        # bukan dibiarkan. OPL-04 GA-1201A memang absen dari dataset resmi.
        assert report.missing_opl == {"GA-1201A": [4]}

    def test_missing_opl_becomes_a_problem_with_a_reason(self, report):
        assert any("GA-1201A" in p and "4" in p for p in report.problems)

    def test_work_order_total(self, report):
        assert report.wo_total == 4

    def test_breakdown_total(self, report):
        assert report.breakdown_total == 3

    def test_downtime_is_summed_only_over_readable_values(self, report):
        # 12 + 0 + 4.5 + 0. Baris dengan downtime kosong tidak dihitung, bukan
        # dianggap nol - tapi di sini hasilnya sama, jadi yang dibuktikan
        # adalah penjumlahannya benar.
        assert report.downtime_hours == pytest.approx(16.5)

    def test_total_cost(self, report):
        assert report.total_cost_idr == pytest.approx(70_000_000.0)

    def test_breakdown_cost_excludes_preventive_work(self, report):
        assert report.breakdown_cost_idr == pytest.approx(70_000_000.0)

    def test_per_equipment_breakdown(self, report):
        by_tag = {p["equipment_tag"]: p for p in report.per_equipment}
        # Hanya dua unit yang punya work order; unit lain tidak boleh muncul
        # dengan angka nol, karena itu akan terlihat seperti data yang lengkap.
        assert set(by_tag) == {"GA-1201A", "YD-2301"}
        assert by_tag["GA-1201A"]["wo_count"] == 3
        assert by_tag["GA-1201A"]["breakdown_count"] == 2
        assert by_tag["GA-1201A"]["downtime_hours"] == pytest.approx(16.5)
        assert by_tag["GA-1201A"]["total_cost_idr"] == pytest.approx(70_000_000.0)
        assert by_tag["YD-2301"]["wo_count"] == 1
        assert by_tag["YD-2301"]["breakdown_count"] == 1

    def test_equipment_metadata_comes_from_the_workbook(self, report):
        by_tag = {p["equipment_tag"]: p for p in report.per_equipment}
        assert by_tag["GA-1201A"]["area_name"] == "AREA ONE"
        assert by_tag["GA-1201A"]["functional_location"] == "FL-GA-1201A"
        assert by_tag["GA-1201A"]["interlock_ref"] == "TJC-LLD-IL-GA-1201A"

    def test_date_range_spans_the_whole_history(self, report):
        assert report.date_range == ("2024-06-04", "2025-05-20")

    def test_equipment_without_work_orders_is_a_problem(self, report):
        # Enam unit punya dokumen tapi tidak ada history. Itujurang data
        # yang harus terlihat, bukan dihilangkan diam-diam.
        assert any(
            "tidak ada di maintenance history" in p for p in report.problems
        )

    def test_no_problem_is_invented_for_a_clean_dataset(self, report):
        unexpected = [
            p for p in report.problems
            if "tidak ada di maintenance history" not in p
            and not p.startswith("GA-1201A: OPL nomor")
        ]
        assert unexpected == [], unexpected

    def test_report_is_json_serialisable(self, report):
        import json

        json.dumps(report.to_dict())

    def test_to_dict_exposes_every_field(self, report):
        as_dict = report.to_dict()
        for key in (
            "root", "pdf_count", "png_count", "xlsx_path", "by_doc_type",
            "opl_counts", "missing_opl", "wo_total", "breakdown_total",
            "downtime_hours", "total_cost_idr", "breakdown_cost_idr",
            "per_equipment", "date_range", "problems",
        ):
            assert key in as_dict, key


class TestDatasetReportWithoutHistory:
    """Tanpa workbook, laporan harus tetapTerbit dengan masalah yang menyebut."""

    def test_totals_are_none_not_zero(self, tmp_path, monkeypatch):
        root = tmp_path / "docs-only"
        (root / "Set_01").mkdir(parents=True)
        for tag in extract.EQUIPMENT_TAGS:
            (root / "Set_01" / f"Equipment Datasheet - {tag}.pdf").write_bytes(b"x")
        report = dataset_mod.dataset_report(str(root))
        # `None`, bukan 0. "Tidak ada data" dan "nol work order" berbeda, dan
        # UI harus bisa menampilkan keduanya secara berbeda.
        assert report.wo_total is None
        assert report.breakdown_total is None
        assert report.downtime_hours is None
        assert report.total_cost_idr is None

    def test_the_missing_workbook_is_named_in_problems(self, tmp_path):
        root = tmp_path / "docs-only"
        (root / "Set_01").mkdir(parents=True)
        for tag in extract.EQUIPMENT_TAGS:
            (root / "Set_01" / f"Equipment Datasheet - {tag}.pdf").write_bytes(b"x")
        report = dataset_mod.dataset_report(str(root))
        assert any(
            "Maintenance history" in p for p in report.problems
        ), report.problems

    def test_opl_without_a_recognised_tag_is_flagged(self, tmp_path):
        root = tmp_path / "odd"
        root.mkdir()
        for tag in extract.EQUIPMENT_TAGS:
            (root / f"Equipment Datasheet - {tag}.pdf").write_bytes(b"x")
        (root / "OPL-ZZ-0001-01 - Mystery.pdf").write_bytes(b"x")
        report = dataset_mod.dataset_report(str(root))
        assert any(
            "tanpa tag equipment dikenal" in p for p in report.problems
        ), report.problems


# ---------------------------------------------------------------------------
# Kontrak dataset resmi
# ---------------------------------------------------------------------------


@requires_official_dataset
class TestOfficialDatasetShape:
    """Bentuk dataset resmi, diukur dari isinya.

    Angka-angka ini dikutip di deck. Kalau dataset resmi diganti, test ini
    gagal - dan itu memang gunanya: deck harus ikut gagal, bukan diam-diam
    jadi tidak benar.
    """

    @pytest.fixture(scope="class")
    def report(self, official_dataset_root) -> dataset_mod.DatasetReport:
        return dataset_mod.dataset_report(str(official_dataset_root))

    def test_eight_equipment_units(self):
        assert len(extract.EQUIPMENT_TAGS) == 8

    def test_pdf_count(self, report):
        assert report.pdf_count == 87

    def test_every_unit_has_one_of_each_reference_document(self, report):
        assert report.by_doc_type["datasheet"] == 8
        assert report.by_doc_type["ga"] == 8
        assert report.by_doc_type["interlock"] == 8
        assert report.by_doc_type["plot_plan"] == 8

    def test_eight_pid_images(self, report):
        assert report.png_count == 8

    def test_opl_total(self, report):
        assert sum(report.opl_counts.values()) == 55

    def test_exactly_one_opl_is_missing(self, report):
        # GA-1201A kehilangan OPL-04. Ini satu-satunya dokumen yang hilang,
        # dan dipakai sebagai kasus penolakan yang jujur di evaluation set.
        assert report.missing_opl == {"GA-1201A": [4]}

    def test_work_order_total(self, report):
        assert report.wo_total == 211

    def test_breakdown_total(self, report):
        assert report.breakdown_total == 31

    def test_downtime_hours(self, report):
        assert report.downtime_hours == pytest.approx(434.0)

    def test_total_cost(self, report):
        assert report.total_cost_idr == pytest.approx(537_770_000.0)

    def test_breakdown_cost_is_a_subset_of_total_cost(self, report):
        assert report.breakdown_cost_idr == pytest.approx(413_345_000.0)
        assert report.breakdown_cost_idr < report.total_cost_idr

    def test_every_unit_appears_in_the_maintenance_history(self, report):
        assert {p["equipment_tag"] for p in report.per_equipment} == set(
            extract.EQUIPMENT_TAGS
        )

    def test_per_equipment_counts_sum_to_the_totals(self, report):
        assert sum(p["wo_count"] for p in report.per_equipment) == report.wo_total
        assert (
            sum(p["breakdown_count"] for p in report.per_equipment)
            == report.breakdown_total
        )
        assert sum(p["downtime_hours"] for p in report.per_equipment) == (
            pytest.approx(report.downtime_hours)
        )

    def test_date_range(self, report):
        # Bukan ("2024-06-04", "2025-12-06"). Kolom Report_Date di workbook
        # adalah datetime, jadi `_iso` mengembalikan waktu juga. Itu pilihan
        # yang disengaja: memangkas ke tanggal akan menyembunyikan jam yang
        # benar-benar tercatat, dan tanggal tidak selalu yang dicari orang
        # saat membandingkan dua work order pada hari yang sama.
        first, last = report.date_range
        assert first.startswith("2024-06-04")
        assert last.startswith("2025-12-06")
        assert first < last

    def test_date_range_strings_are_not_reformatted(self, report):
        # `_iso` meneruskan string apa adanya. Kalau suatu saat workbook
        # menyimpan tanggal sebagai teks, tanggal itu akan tampil persis
        # seperti di workbook - dan perbandingan string menjadi tidak valid,
        # yang lebih baik daripada diam-diam salah urut.
        assert isinstance(report.date_range[0], str)

    def test_no_unexpected_problems(self, report):
        # Satu masalah yang diharapkan: OPL-04 GA-1201A yang hilang. Selain itu
        # dataset harus bersih, karena kalau tidak, temuan di UI jadi tidak
        # trustworthy.
        unexpected = [
            p for p in report.problems
            if not p.startswith("GA-1201A: OPL nomor")
        ]
        assert unexpected == [], unexpected

    def test_workbook_is_the_one_from_the_dataset(self, report):
        assert report.xlsx_path is not None
        assert report.xlsx_path.endswith(".xlsx")


@requires_official_dataset
class TestOfficialDatasetIsIndexedConsistently:
    """Laporan dataset harus cocok dengan apa yang benar-benar terindeks.

    Dua sumber angka yang dihitung berbeda - satu dari nama file, satu dari
    isi database - harus sepakat. Kalau tidak, salah satunya salah dan tidak
    ada yang tahu mana.
    """

    def test_document_count_matches_the_index(self, official_dataset):
        report = dataset_mod.dataset_report()
        conn: sqlite3.Connection = official_dataset
        indexed = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        assert indexed == report.pdf_count + report.png_count

    def test_equipment_count_matches_the_index(self, official_dataset):
        conn: sqlite3.Connection = official_dataset
        indexed = conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0]
        assert indexed == len(extract.EQUIPMENT_TAGS)

    def test_work_order_count_matches_the_index(self, official_dataset):
        conn: sqlite3.Connection = official_dataset
        report = dataset_mod.dataset_report()
        indexed = conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
        assert indexed == report.wo_total

    def test_no_document_is_lost_during_extraction(self, official_dataset):
        """Setiap file yang dilaporkan harus punya baris di tabel documents.

        Ini yang menangkap PDF yang gagal dibaca: `extract_file` mengembalikan
        objek dengan `error`, bukan melempar exception, jadi jumlah file dan
        jumlah baris bisa berbeda tanpa ada yang melihat.
        """
        conn: sqlite3.Connection = official_dataset
        report = dataset_mod.dataset_report()
        indexed_filenames = {
            row[0] for row in conn.execute("SELECT filename FROM documents")
        }
        found = set(extract.iter_dataset_files(report.root))
        missing = {
            f for f in found if f.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            not in indexed_filenames
        }
        assert not missing, f"file ada tapi tidak terindeks: {sorted(missing)}"

    def test_opl_gap_is_absent_from_the_index(self, official_dataset):
        """Nomor OPL yang hilang tidak boleh muncul sebagai dokumen.

        Kalau OPL-GA-1201A-04 somehow terindeks, laporan dataset salah dan
        kasus penolakan di evaluation set jadi tidak konsisten dengan data.
        """
        conn: sqlite3.Connection = official_dataset
        hits = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE filename LIKE '%GA-1201A-04%'"
        ).fetchone()[0]
        assert hits == 0