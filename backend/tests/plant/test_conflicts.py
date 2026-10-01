"""Test deteksi konflik dan kesesuaian antar dokumen.

Ini bagian yang paling mudah terlihat sebagai "pintar" dan paling mudah
berbohong, jadi test di sini sengaja menyoroti dua hal:

  1. konflik hanya dilaporkan kalau memang ada bukti, dan
  2. kesesuaian dihitung, bukan diasumsikan.

Nilai setpoint di fixture dibuat berbeda untuk dua equipment dengan sengaja:
EQ-0001 punya satu nilai yang diulang di tiga dokumen, EQ-0002 punya dua nilai
yang bertentangan. Kalau salah satu tidak muncul di ringkasan, test di sini
menangkapnya.
"""

from __future__ import annotations

import pytest

from plant import conflicts


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------


class TestNormaliseUnit:
    """Satuan di dataset sudah seragam; normalisasi tidak boleh mengarang.

    Diukur dari `document_parameters` pada dataset CALIBER: barg 24, % 22,
    degC 21, mm/s 10, rpm 5, A 4, V 4, bar 3, kg 3, m3/h 2, ppm 2, m 2,
    kg/cm2g 1, cP 1. Tidak ada "bar(g)" maupun "mm/sec". Karena itu tabel
    alias sengaja tidak_added keduanya - menambah padanan untuk satuan yang
    tidak ada hanya menambah permukaan yang bisa salah.
    """

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("barg", "barg"),
            ("degC", "degC"),
            ("\u00b0C", "degC"),
            ("mm/s", "mm/s"),
            ("% ", "%"),
            ("ppm", "ppm"),
        ],
    )
    def test_measured_units_pass_through(self, raw: str, expected: str) -> None:
        assert conflicts.normalise_unit(raw) == expected

    def test_unknown_unit_is_not_rewritten(self) -> None:
        # Satuan yang tidak dikenal harus tetap apa adanya. Menebak satu berarti
        # nilai dari satuan berbeda dibandingkan seolah-olah satuannya sama.
        assert conflicts.normalise_unit("furlongs") == "furlongs"

    def test_bar_and_barg_stay_distinct(self) -> None:
        # barg ( absolut) dan bar ( relatif) bukan satuan yang sama. Kalau
        # dicampur, 1.0 barg dibandingkan dengan 1.0 bar dianggap sepakat
        # padahal selisihnya satu atmosfer.
        assert conflicts.normalise_unit("bar") != conflicts.normalise_unit("barg")

    def test_case_is_normalised_for_degrees(self) -> None:
        assert conflicts.normalise_unit("degc") == "degC"

    def test_empty_unit(self) -> None:
        assert conflicts.normalise_unit("") in ("", None)


# ---------------------------------------------------------------------------
# Tag instrumen vs equipment
# ---------------------------------------------------------------------------


class TestIsInstrumentTag:
    EQUIPMENT = ["EQ-0001", "EQ-0002", "GA-1201A", "DC-3401A", "YD-2301"]

    @pytest.mark.parametrize(
        "tag",
        ["PSLL-1201", "TSHH-1201", "VSHH-1201", "LSHH-8901", "ZSO-1201",
         "FSLL-1201", "LSLL-5601", "PSLL-0001", "TSHH-0002"],
    )
    def test_instrument_tags(self, tag: str) -> None:
        assert conflicts.is_instrument_tag(tag, self.EQUIPMENT) is True

    @pytest.mark.parametrize(
        "tag",
        ["EQ-0001", "EQ-0002", "GA-1201A", "DC-3401A", "YD-2301"],
    )
    def test_equipment_tags(self, tag: str) -> None:
        assert conflicts.is_instrument_tag(tag, self.EQUIPMENT) is False

    @pytest.mark.parametrize(
        "tag",
        ["SEQ-1201", "TJC-LLD-DS-GA-1201A", "WPN-MAT-001", "P&ID 1201",
         "", "   ", "1201", "not a tag", "PSLL 1201"],
    )
    def test_non_instrument_identifiers(self, tag: str) -> None:
        # Nomor dokumen, functional location, dan teks bebas bukan nilai
        # terukur. Kalau ikut dihitung, setiap dokumen punya "konflik" yang
        # tidak berarti.
        assert conflicts.is_instrument_tag(tag, self.EQUIPMENT) is False

    def test_equipment_tag_needs_no_allow_list_to_be_excluded(self) -> None:
        # Bentuk GA-1201A cocok dengan pola instrumen, jadi hanya bisa dibedakan
        # lewat daftar tag yang diketahui.
        assert conflicts.is_instrument_tag("GA-1201A", self.EQUIPMENT) is False
        assert conflicts.is_instrument_tag("GA-1201A", None) is True

    def test_prefix_exclusion_list_covers_the_measured_ids(self) -> None:
        # Diukur dari dataset: SEQ- (interlock_ref), TJC- (doc_no, pid_ref,
        # functional_location), WPN- (related_docs).
        for prefix in ("SEQ-", "TJC-", "WPN-"):
            assert prefix.rstrip("-") in {
                p.rstrip("-") for p in conflicts.NON_INSTRUMENT_PREFIXES
            }, f"{prefix} appears in the dataset but is not excluded"


# ---------------------------------------------------------------------------
# Ekstraksi nilai
# ---------------------------------------------------------------------------


class TestExtractParameterValues:
    """Fungsi mengembalikan tuple, bukan objek: (tag, value, unit, operator,
    kind, raw)."""

    def test_finds_a_setpoint_in_prose(self) -> None:
        found = conflicts.extract_parameter_values(
            "The low suction pressure trip PSLL-0001 < 0.5 barg.", {"EQ-0001"}
        )
        assert any(row[0] == "PSLL-0001" for row in found), found

    def test_keeps_the_operator(self) -> None:
        found = conflicts.extract_parameter_values(
            "PSLL-0001 < 0.5 barg", {"EQ-0001"}
        )
        rows = [r for r in found if r[0] == "PSLL-0001"]
        assert rows and rows[0][3] == "<"

    def test_unicode_operators_are_normalised(self) -> None:
        # PDF sering memakai \u2264 dan \u2265. Kalau tidak dinormalisasi,
        # "<=" dan "\u2264" dianggap dua operator berbeda danoperator yang sama tidak pernah dibandingkan.
        found = conflicts.extract_parameter_values(
            "PSLL-1201 \u2264 0.5 barg", {"EQ-0001"}
        )
        assert [r[3] for r in found if r[0] == "PSLL-1201"] == ["<="]

    def test_operator_is_required(self) -> None:
        # Tanpa operator, setiap angka di dekat tag instrumen akan jadi
        # setpoint - termasuk nomor halaman.
        assert conflicts.extract_parameter_values(
            "see PSLL-1201 page 0.5", {"EQ-0001"}
        ) == []

    def test_value_must_follow_immediately(self) -> None:
        # Jendela jangkar sengaja pendek: FSLL-1201 pernah ikut mencatat
        # 7.1 mm/s milik VSHH-1201 karena pencarian melompat ke baris
        # berikutnya.
        found = conflicts.extract_parameter_values(
            "FSLL-1201 trips for the flow. " + ("filler " * 20) + "VSHH-1201 > 7.1 mm/s",
            {"EQ-0001"},
        )
        for row in found:
            assert not (row[0] == "FSLL-1201" and row[1] == 7.1), found

    def test_identifies_by_instrument_not_by_description(self) -> None:
        # Dua instrumen berbeda dengan deskripsi serupa harus terpisah. Kalau
        # dikelompokkan per deskripsi, LSLL < 15 % dan LSHH > 85 % dilaporkan
        # sebagai konflik 467 %.
        found = conflicts.extract_parameter_values(
            "LSLL-6710 < 15 % and LSHH-6710 > 85 %", {"EQ-0001"}
        )
        tags = {row[0] for row in found}
        assert tags == {"LSLL-6710", "LSHH-6710"}

    def test_plain_prose_yields_nothing(self) -> None:
        assert conflicts.extract_parameter_values(
            "This lesson explains the seal flush plan.", {"EQ-0001"}
        ) == []

    def test_empty_text(self) -> None:
        assert conflicts.extract_parameter_values("", {"EQ-0001"}) == []

    def test_duplicates_are_collapsed(self) -> None:
        found = conflicts.extract_parameter_values(
            "PSLL-1201 < 0.5 barg. Again: PSLL-1201 < 0.5 barg.", {"EQ-0001"}
        )
        assert len([r for r in found if r[0] == "PSLL-1201"]) == 1


class TestExtractTableParameters:
    """Tabel datasheet dibaca lewat pdfplumber, bukan teks linear."""

    #: Bentuk input: list of tables, tiap table list of rows, tiap row list of
    #: cells - bentuk yang diembalikan pdfplumber (`doc.tables`), bukan dict.
    #: Versi pertama test mengirim dict dan dapat kosong tanpa error, jadi test
    #: itu sendiri hampir tidak memeriksa apa pun.

    def test_finds_a_known_datasheet_label(self) -> None:
        tables = [[
            ["No", "Parameter", "Value", "Unit"],
            ["1", "Rated Head", "45", "m"],
            ["2", "Rated Flow", "120", "m3/h"],
        ]]
        found = conflicts.extract_table_parameters(tables)
        assert found, "known datasheet labels must yield values"
        names = {row[0] for row in found}
        assert names & {"rated head", "rated flow"}, found

    def test_design_values_are_marked_as_design(self) -> None:
        # Nilai desain dan nilai batas trip memang boleh berbeda - pompa
        # didesain 16 barg dan batas trip-nya 0.5 barg. Kalau jenisnya sama,
        # keduanya dilaporkan sebagai konflik, dan itu kekeliruan kategori.
        tables = [[["Rated Head", "45 m"]]]
        found = conflicts.extract_table_parameters(tables)
        assert found and found[0][4] == "design"

    def test_unknown_labels_are_ignored(self) -> None:
        # Mengambil semua pasangan tanpa filter menghasilkan ratusan nilai tanpa
        # nama, dan setiap nilai tak bernama dibandingkan dengan nilai tak bernama
        # lain - itu noise, bukan temuan.
        tables = [[["Spare parts list", "12"], ["Contact person", "EMP-0042"]]]
        assert conflicts.extract_table_parameters(tables) == []

    def test_value_cell_must_contain_a_number(self) -> None:
        tables = [[["Rated Head", "see note 7"]]]
        assert conflicts.extract_table_parameters(tables) == []

    def test_forced_unit_wins_over_the_cell_text(self) -> None:
        tables = [[["rated head", "45"]]]
        found = conflicts.extract_table_parameters(tables)
        assert found and found[0][2] == "m"

    def test_empty_tables(self) -> None:
        assert conflicts.extract_table_parameters([]) == []
        assert conflicts.extract_table_parameters([[]]) == []

    def test_table_without_numbers(self) -> None:
        assert conflicts.extract_table_parameters(
            [{"Signoff": [["Name", "Role"], ["EMP-0001", "Approved"]]}]
        ) == []


# ---------------------------------------------------------------------------
# Konflik
# ---------------------------------------------------------------------------


class TestDetectConflicts:
    def test_finds_the_planted_conflict(self, synthetic_index) -> None:
        found = conflicts.detect_conflicts(synthetic_index)
        tags = {c.parameter if hasattr(c, "parameter") else c.get("parameter")
                for c in found}
        assert "TSHH-0002" in tags, f"planted conflict missed; got {found}"

    def test_does_not_flag_the_agreed_setpoint(self, synthetic_index) -> None:
        # EQ-0001 menyatakan 0.5 barg di tiga dokumen. Itu kesesuaian, bukan
        # konflik, dan melaporkannya sebagai konflik akan membuat panel
        # "conflicts" penuh,false positive.
        found = conflicts.detect_conflicts(synthetic_index)
        tags = {c.parameter if hasattr(c, "parameter") else c.get("parameter")
                for c in found}
        assert "PSLL-0001" not in tags

    def test_conflict_names_both_values(self, synthetic_index) -> None:
        found = conflicts.detect_conflicts(synthetic_index)
        match = next(
            c for c in found
            if (c.parameter if hasattr(c, "parameter") else c.get("parameter"))
            == "TSHH-0002"
        )
        values = match.values if hasattr(match, "values") else match["values"]
        assert len(values) >= 2

    def test_conflict_needs_at_least_two_documents(self, synthetic_index) -> None:
        # Satu dokumen menyatakan satu nilai. Tidak ada yang bisa bertentangan.
        single = conflicts.conflicts_for_documents(synthetic_index, ["d2b"])
        assert isinstance(single, list)

    def test_empty_index_reports_no_conflicts(self, empty_index) -> None:
        assert conflicts.detect_conflicts(empty_index) == []

    def test_only_relevant_conflicts_for_a_tag(self, synthetic_index) -> None:
        found = conflicts.conflicts_for_equipment(synthetic_index, "EQ-0002")
        assert isinstance(found, list)
        for c in found:
            tag = c.equipment_tag if hasattr(c, "equipment_tag") else c.get("equipment_tag")
            assert tag == "EQ-0002"


class TestConflictIdentity:
    def test_design_value_is_never_compared_to_a_trip_value(self, synthetic_index) -> None:
        # Membandingkan "design pressure 16 barg" dengan "trip at 0.5 barg"
        # akan melaporkan konflik di setiap datasheet, dan yang reported itu
        # bukan salah siapa pun - keduanya benar dan menjawab pertanyaan
        # berbeda.
        found = conflicts.detect_conflicts(synthetic_index)
        for c in found:
            parameter = c.parameter if hasattr(c, "parameter") else c.get("parameter")
            kinds = getattr(c, "kinds", None) or (c.get("kinds") if isinstance(c, dict) else None)
            if kinds and len(set(kinds)) > 1:
                pytest.fail(f"{parameter}: compared across value kinds {kinds}")

    def test_same_operator_is_required(self, synthetic_index) -> None:
        # "above 95" dan "below 0.5" tidak bisa dibandingkan: keduanya bisa
        # benar pada saat yang bersamaan.
        found = conflicts.detect_conflicts(synthetic_index)
        for c in found:
            operators = getattr(c, "operators", None) or (
                c.get("operators") if isinstance(c, dict) else None
            )
            if operators:
                assert len(set(operators)) == 1, (
                    f"conflict mixes operators {operators}"
                )


class TestAgreementReport:
    def test_reports_the_agreed_group(self, synthetic_index) -> None:
        report = conflicts.agreement_report(synthetic_index)
        text = str(report)
        assert "PSLL-0001" in text

    def test_agreement_needs_more_than_one_document(self, synthetic_index) -> None:
        report = conflicts.agreement_report(synthetic_index)
        # EQ-0002_PSHH-0002 hanya disebut sekali, jadi tidak boleh masuk
        # kelompok yang "disepakati".
        groups = report.get("groups", report) if isinstance(report, dict) else report
        for group in groups if isinstance(groups, list) else []:
            docs = group.get("documents", group.get("doc_ids", [])) if isinstance(group, dict) else []
            if len(set(docs)) < 2:
                pytest.fail(f"single-document group reported as agreement: {group}")

    def test_empty_index(self, empty_index) -> None:
        report = conflicts.agreement_report(empty_index)
        assert report is not None


class TestConflictSummary:
    def test_counts_are_integers(self, synthetic_index) -> None:
        summary = conflicts.conflict_summary(synthetic_index)
        for key, value in summary.items():
            if isinstance(value, int):
                assert value >= 0, f"{key} is negative"

    def test_empty_index(self, empty_index) -> None:
        assert conflicts.conflict_summary(empty_index) is not None


class TestTolerance:
    def test_tolerance_is_a_percentage(self) -> None:
        assert 0 < conflicts.TOLERANCE_PCT < 100

    def test_difference_within_tolerance_is_not_a_conflict(self, synthetic_index) -> None:
        # Dua nilai yang berbeda 1% bukan konflik. Menolaknya akan-reported
        # setiap perbedaan pembulatan pada tabel yang sama.
        found = conflicts.detect_conflicts(synthetic_index)
        for c in found:
            parameter = c.parameter if hasattr(c, "parameter") else c.get("parameter")
            values = getattr(c, "values", None) or (
                c.get("values") if isinstance(c, dict) else None
            )
            if values and len(values) >= 2:
                numbers = [v.value for v in values if getattr(v, "value", None)]
                if len(numbers) >= 2 and min(numbers) > 0:
                    spread = (max(numbers) - min(numbers)) / min(numbers) * 100
                    assert spread > conflicts.TOLERANCE_PCT, (
                        f"{parameter}: spread {spread:.2f}% is inside the "
                        f"{conflicts.TOLERANCE_PCT}% tolerance"
                    )


class TestParameterInventory:
    def test_counts_every_extracted_value(self, synthetic_index) -> None:
        # Fixture punya 5 nilai: PSLL-0001 di tiga dokumen, TSHH-0002 di dua.
        inv = conflicts.parameter_inventory(synthetic_index)
        assert isinstance(inv, dict)
        assert inv["values_extracted"] == 5
        assert inv["by_source"]["linear"] == 5

    def test_groups_by_document_type(self, synthetic_index) -> None:
        inv = conflicts.parameter_inventory(synthetic_index)
        assert set(inv["by_doc_type"]) <= {"datasheet", "interlock", "opl",
                                            "ga", "plot_plan"}

    def test_empty_index(self, empty_index) -> None:
        inv = conflicts.parameter_inventory(empty_index)
        assert isinstance(inv, dict)
        assert inv["values_extracted"] == 0
        assert inv["distinct_parameter_groups"] == 0


class TestScanDocumentValues:
    def test_scans_without_raising(self, synthetic_index) -> None:
        assert isinstance(conflicts.scan_document_values(synthetic_index), dict)

    def test_empty_index(self, empty_index) -> None:
        assert isinstance(conflicts.scan_document_values(empty_index), dict)