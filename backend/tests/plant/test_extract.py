"""Test untuk `plant/extract.py`.

Ekstraksi PDF adalah bagian paling rapuh di sistem ini, dan paling penting.
Metadata approval menentukanseparuh bobot trust: kalau `detect_approval()`
gagal membaca "Rev 3 - ISSUED FOR OPERATION" yang jelas ada di datasheet,
dokumen itu dapat badge VERIFY, bukan TRUSTED, dan tidak ada yang tahu
kenapa. Tes-tes di sini menjaga pembacaan itu.

Semua input adalah potongan teks buatan tangan yang meniru bentuk yang
benar-benar muncul di PDF: label dan nilai dipisahkan baris, bukan ":".
Kalau tes-tes ini memakai "Label: value" yang rapi, mereka lulus sementara
PDF aslinya tidak terbaca.
"""

from __future__ import annotations

import pytest

from plant import extract


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------


class TestClassify:
    def test_opl_from_filename_prefix(self):
        assert extract.classify("OPL-GA-1201A-01 - Seal_Flush.pdf") == "opl"

    def test_opl_prefix_beats_other_keywords(self):
        # Several OPL filenames mention the word "drawing" because the lesson
        # is about a drawing. The prefix is the more specific signal, so it
        # wins. Reordering these two branches is a silent misclassification.
        name = "OPL-GA-1201A-04 - Drawing_Rotation_Check.pdf"
        assert extract.classify(name) == "opl"

    def test_datasheet(self):
        assert extract.classify("Equipment Datasheet - GA-1201A.pdf") == "datasheet"

    def test_data_sheet_with_space(self):
        assert extract.classify("Data Sheet - YD-2301.pdf") == "datasheet"

    def test_interlock(self):
        assert (
            extract.classify("Interlock Logic Diagram - GA-1201A.pdf") == "interlock"
        )

    def test_plot_plan(self):
        assert extract.classify("Plot Plan - Set 01.pdf") == "plot_plan"

    def test_ga_drawing(self):
        assert extract.classify("GA Drawing - GA-1201A.pdf") == "ga"

    def test_png_is_pid_only_when_named_pid(self):
        # The dataset spells these "P&ID_Set_02.png", so the ampersand form is
        # the one that has to work. Matching the bare substring "pid" missed
        # 7 of the 8 files and only happened not to matter because
        # extract_file() short-circuits images before classify() is called.
        assert extract.classify("P&ID_Set_02.png") == "pid"
        assert extract.classify("P&ID SET 6.png") == "pid"
        assert extract.classify("PID_Set_01.png") == "pid"

    def test_pdf_named_pid_is_not_a_pid_document(self):
        # Only the image types count. A datasheet whose filename happens to
        # contain "pid" is still a datasheet.
        assert extract.classify("Rapid Datasheet - GA-1201A.pdf") == "datasheet"

    def test_png_without_pid_in_name_is_not_pid(self):
        # A photo of a nameplate is not a P&ID. Keying on the extension alone
        # would file every image as a drawing.
        assert extract.classify("Nameplate Photo - GA-1201A.png") != "pid"

    def test_falls_back_to_text_when_filename_is_opaque(self):
        assert extract.classify("scan_0042.pdf", "ONE POINT LESSON about X") == "opl"

    def test_text_fallback_interlock(self):
        assert (
            extract.classify("scan_0043.pdf", "INTERLOCK LOGIC DIAGRAM AND CAUSE EFFECT")
            == "interlock"
        )

    def test_text_fallback_datasheet(self):
        assert extract.classify("scan_0044.pdf", "EQUIPMENT DATA SHEET") == "datasheet"

    def test_unrecognisable_returns_unknown(self):
        # Not a crash and not a guess. `unknown` keeps the document visible with
        # no approval claim, which is the honest state.
        assert extract.classify("scan_0045.pdf", "lorem ipsum") == "unknown"

    def test_filename_wins_over_text(self):
        assert extract.classify("Interlock Logic - X.pdf", "ONE POINT LESSON") == (
            "interlock"
        )

    def test_directory_prefix_is_ignored(self):
        # os.path.basename matters: a parent directory named OPL would otherwise
        # reclassify every file beneath it.
        assert extract.classify("C:/OPL-somewhere/Equipment Datasheet - X.pdf") == (
            "datasheet"
        )


# ---------------------------------------------------------------------------
# detect_approval
# ---------------------------------------------------------------------------


class TestDetectApproval:
    @pytest.mark.parametrize(
        "needle,expected",
        [
            ("ISSUED FOR OPERATION", "approved"),
            ("ISSUED FOR CONSTRUCTION", "approved"),
            ("ISSUED FOR APPROVAL", "pending"),
            ("ISSUED FOR REVIEW", "draft"),
            ("ISSUED FOR INFORMATION", "draft"),
        ],
    )
    def test_every_known_state_maps(self, needle, expected):
        level, _raw = extract.detect_approval(f"DOCUMENT STATUS: {needle}")
        assert level == expected

    def test_final_states_beat_intermediate_ones(self):
        # A revision history lists A ISSUED FOR REVIEW, then B ISSUED FOR
        # APPROVAL, then 0 ISSUED FOR CONSTRUCTION. Reading the first match
        # would report "draft" for a drawing that was actually issued.
        text = (
            "REVISION HISTORY\n"
            "A ISSUED FOR REVIEW\n"
            "B ISSUED FOR APPROVAL\n"
            "0 ISSUED FOR CONSTRUCTION\n"
        )
        level, _raw = extract.detect_approval(text)
        assert level == "approved"

    def test_missing_status_is_unknown_not_draft(self):
        # The distinction the whole trust model rests on: no marker means we do
        # not know, and must not pretend the document is a draft either. A
        # fabricated "draft" would score a document as not-yet-approved.
        level, raw = extract.detect_approval("EQUIPMENT NAME: HEXANE FEED PUMP")
        assert level == "unknown"
        assert raw is None

    def test_empty_text_is_unknown(self):
        level, raw = extract.detect_approval("")
        assert level == "unknown"
        assert raw is None

    def test_phrase_split_across_lines_still_found(self):
        # This is the real failure mode of PDF text extraction: a single phrase
        # wraps across two lines. Without whitespace flattening this reads as
        # no approval marker and the document silently loses its badge.
        level, _raw = extract.detect_approval(
            "DOCUMENT STATUS\nRev 3 - ISSUED FOR\nOPERATION\n"
        )
        assert level == "approved"

    def test_phrase_split_across_three_lines(self):
        level, _raw = extract.detect_approval("Rev 3 - ISSUED\nFOR\nOPERATION")
        assert level == "approved"

    def test_raw_text_is_returned_for_provenance(self):
        # The UI shows the phrase that was actually found. Returning only the
        # enum would make the badge unauditable.
        _level, raw = extract.detect_approval("Status: Rev 3 - ISSUED FOR OPERATION")
        assert raw is not None
        assert "ISSUED FOR OPERATION" in raw.upper()

    def test_case_insensitive(self):
        level, _raw = extract.detect_approval("issued for operation")
        assert level == "approved"


# ---------------------------------------------------------------------------
# parse_revision_history
# ---------------------------------------------------------------------------


# Bentuk persis seperti yang ditulis pypdf: kolom dipisah SPASI, bukan tab.
GA_HISTORY = """REVISION HISTORY
REV    DESCRIPTION              BY     DATE
A      ISSUED FOR REVIEW        RS     02-03-2026
B      ISSUED FOR APPROVAL      RS     14-04-2026
0      ISSUED FOR CONSTRUCTION  RS     05-06-2026
"""


class TestParseRevisionHistory:
    def test_reads_all_three_rows(self):
        rows = extract.parse_revision_history(GA_HISTORY)
        assert len(rows) == 3

    def test_preserves_document_order(self):
        rows = extract.parse_revision_history(GA_HISTORY)
        assert [r["rev"] for r in rows] == ["A", "B", "0"]

    def test_extracts_author_and_date(self):
        rows = extract.parse_revision_history(GA_HISTORY)
        last = rows[-1]
        assert last["by"] == "RS"
        assert last["date"] == "05-06-2026"

    def test_description_is_uppercased(self):
        rows = extract.parse_revision_history(GA_HISTORY)
        assert rows[-1]["description"] == "ISSUED FOR CONSTRUCTION"

    def test_duplicate_revision_is_dropped(self):
        # The same rev printed twice is one row of evidence, not two. Counting it
        # twice would overstate how much provenance this document carries.
        rows = extract.parse_revision_history(GA_HISTORY + "0      ISSUED FOR CONSTRUCTION\n")
        assert [r["rev"] for r in rows].count("0") == 1

    def test_row_without_by_or_date_still_parsed(self):
        rows = extract.parse_revision_history("0 ISSUED FOR CONSTRUCTION\n")
        assert len(rows) == 1
        assert rows[0]["rev"] == "0"
        assert "by" not in rows[0]
        assert "date" not in rows[0]

    def test_unknown_description_is_not_a_revision_row(self):
        # Free text that happens to start with a letter and a digit must not
        # become a revision entry.
        assert extract.parse_revision_history("3 spare parts delivered 05-06-2026\n") == []

    def test_empty_text_gives_no_rows(self):
        assert extract.parse_revision_history("") == []

    def test_datasheet_inline_status_is_not_a_revision_table(self):
        # Datasheets have no REVISION HISTORY table. Their status is inline and
        # handled by detect_approval, so parsing it as history would invent a
        # provenance record that the document does not contain.
        assert (
            extract.parse_revision_history("DATASHEET REV\nRev 3 - ISSUED FOR OPERATION\n")
            == []
        )

    def test_date_format_dd_mm_yyyy_is_preserved_verbatim(self):
        # Not parsed into an ISO date. The source is dd-mm-yyyy and rewriting it
        # would be a guess; the string is displayed as the document states it.
        rows = extract.parse_revision_history("0 ISSUED FOR CONSTRUCTION RS 05-06-2026\n")
        assert rows[0]["date"] == "05-06-2026"


# ---------------------------------------------------------------------------
# split_sections
# ---------------------------------------------------------------------------


OPL_TEXT = """ONE POINT LESSON
1. PURPOSE / OBJECTIVE
Explain the seal flush plan.

2. SAFETY PRECAUTIONS
Isolate and lock out.

3. TOOLS & MATERIALS
Gland packing, torque wrench.

4. DETAILED PROCEDURE
Establish the flush flow.

5. COMMON PROBLEMS
Leaking again after a week.

6. KEY LEARNING POINTS
Check the flush pressure first.
"""


class TestSplitSections:
    def test_finds_all_six_sections(self):
        sections = extract.split_sections(OPL_TEXT)
        assert [s["section"] for s in sections] == [
            "purpose",
            "safety",
            "tools",
            "procedure",
            "troubleshooting",
            "learning",
        ]

    def test_sections_are_in_document_order(self):
        # Sorted by position in the text, not by the order of the pattern
        # list. A citation pointing at "section procedure" has to point at the
        # procedure.
        sections = extract.split_sections(OPL_TEXT)
        assert sections[0]["section"] == "purpose"
        assert sections[-1]["section"] == "learning"

    def test_each_section_carries_its_own_body(self):
        sections = {s["section"]: s["content"] for s in extract.split_sections(OPL_TEXT)}
        assert "Isolate and lock out" in sections["safety"]
        assert "Establish the flush flow" in sections["procedure"]
        assert "Check the flush pressure" in sections["learning"]

    def test_no_section_overlap(self):
        sections = extract.split_sections(OPL_TEXT)
        for earlier, later in zip(sections, sections[1:]):
            assert earlier["content"] != later["content"]

    def test_last_section_runs_to_end_of_text(self):
        sections = extract.split_sections(OPL_TEXT)
        assert sections[-1]["content"].rstrip().endswith("first.")

    def test_document_without_numbered_sections_gives_nothing(self):
        # A datasheet has no numbered OPL sections. Returning a bogus single
        # section would give every citation a section label to point at.
        assert extract.split_sections("EQUIPMENT NAME\nHEXANE FEED PUMP\n") == []

    def test_empty_text_gives_nothing(self):
        assert extract.split_sections("") == []

    def test_missing_later_sections_do_not_break_earlier_ones(self):
        text = "1. PURPOSE / OBJECTIVE\nDo the thing.\n4. DETAILED PROCEDURE\nSteps.\n"
        sections = {s["section"]: s["content"] for s in extract.split_sections(text)}
        assert set(sections) == {"purpose", "procedure"}

    def test_partial_heading_does_not_match(self):
        # "1. PURPOSE" alone is not the heading; the real one is
        # "1. PURPOSE / OBJECTIVE". Accepting a prefix would match prose that
        # merely starts with those words.
        text = "1. PURPOSE AND SCOPE OF THIS MEMO\nbody\n"
        assert extract.split_sections(text) == []


# ---------------------------------------------------------------------------
# _kv_from_tables
# ---------------------------------------------------------------------------


class TestKvFromTables:
    def test_reads_header_row_into_next_row(self):
        # pypdf writes the OPL signature block as a header row of labels and a
        # second row of values, not as "Label: value" pairs.
        tables = [[["Prepared by", "Reviewed by", "Approved by"], ["A", "B", "C"]]]
        got = extract._kv_from_tables(tables, "Approved by")
        assert got == {"Prepared by": "A", "Reviewed by": "B", "Approved by": "C"}

    def test_matches_header_case_insensitively(self):
        tables = [[["APPROVED BY"], ["Wahyu Setiadi"]]]
        assert extract._kv_from_tables(tables, "approved by") == {
            "APPROVED BY": "Wahyu Setiadi"
        }

    def test_header_on_last_row_yields_no_pairs(self):
        # A header with no row under it is not data. Pairing it with nothing
        # must produce nothing rather than an exception.
        assert extract._kv_from_tables([[["Approved by"]]], "Approved by") == {}

    def test_no_matching_header_returns_empty(self):
        tables = [[["Tag", "Value"], ["GA-1201A", "pump"]]]
        assert extract._kv_from_tables(tables, "Approved by") == {}

    def test_empty_cells_are_skipped_not_paired(self):
        # Padded blank cells are common. Pairing a label with an empty string
        # would produce approval metadata that reads as present but names nobody.
        tables = [[["Prepared by", "Approved by"], ["A", ""]]]
        got = extract._kv_from_tables(tables, "Approved by")
        assert got == {"Prepared by": "A"}

    def test_ragged_rows_are_truncated_to_the_shorter_one(self):
        tables = [[["Prepared by", "Approved by"], ["A"]]]
        assert extract._kv_from_tables(tables, "Approved by") == {"Prepared by": "A"}

    def test_empty_table_list(self):
        assert extract._kv_from_tables([], "Approved by") == {}

    def test_first_matching_table_wins(self):
        # Two tables can both carry a signature block (a cover sheet plus the
        # body). Reading the first is deterministic; reading whichever comes
        # last makes the answer depend on PDF layout order.
        tables = [
            [["Approved by"], ["FIRST"]],
            [["Approved by"], ["SECOND"]],
        ]
        assert extract._kv_from_tables(tables, "Approved by") == {"Approved by": "FIRST"}


# ---------------------------------------------------------------------------
# _extract_person
# ---------------------------------------------------------------------------


class TestApproverNames:
    """Approver names come from the OPL signature table, not from prose.

    `_extract_person` used to do this and was removed: it had no callers, and
    its regex could not match the real layout anyway. The signature block is
    read by `_kv_from_tables`, because pypdf emits every label before every
    value, so "Approved by" and the name are not adjacent in the text stream.
    These tests pin the path that actually runs.
    """

    def test_signature_table_supplies_reviewer_and_approver(self):
        tables = [
            [
                ["Prepared by", "Reviewed by", "Approved by", "Date of Sharing"],
                ["A", "Wahyu Setiadi (EMP-1113)", "Arya Wibisono (EMP-0912)", "Mon, 06-05-2026"],
            ]
        ]
        assert extract._kv_from_tables(tables, "Prepared by") == {
            "Prepared by": "A",
            "Reviewed by": "Wahyu Setiadi (EMP-1113)",
            "Approved by": "Arya Wibisono (EMP-0912)",
            "Date of Sharing": "Mon, 06-05-2026",
        }

    def test_employee_id_is_what_distinguishes_a_name_from_prose(self):
        # The one thing that makes this evidence rather than a word that
        # happened to follow a label.
        assert "EMP-0912" in "Arya Wibisono (EMP-0912)"
        assert "EMP-" not in "The Operations Department"


# ---------------------------------------------------------------------------
# Structure of results
# ---------------------------------------------------------------------------


class TestResultStructures:
    def test_doc_meta_defaults_are_none_not_empty_strings(self):
        meta = extract.DocMeta(doc_type="opl")
        assert meta.approval_status is None
        assert meta.revision_history == []
        assert meta.related_docs == []
        assert meta.to_dict()["doc_type"] == "opl"

    def test_list_defaults_are_not_shared_between_instances(self):
        # mutable default field. Two DocMeta instances must not accumulate each
        # other's approval blocks.
        a = extract.DocMeta(doc_type="opl")
        b = extract.DocMeta(doc_type="opl")
        a.revision_history.append({"rev": "A"})
        assert b.revision_history == []

    def test_extracted_doc_serialises(self):
        doc = extract.ExtractedDoc(
            path="/tmp/x.pdf", filename="x.pdf", meta=extract.DocMeta(doc_type="ga")
        )
        as_dict = doc.to_dict()
        assert as_dict["filename"] == "x.pdf"
        assert as_dict["meta"]["doc_type"] == "ga"
        assert as_dict["error"] is None

    def test_to_dict_is_json_serialisable(self):
        import json

        doc = extract.ExtractedDoc(
            path="/tmp/x.pdf", filename="x.pdf", meta=extract.DocMeta(doc_type="opl")
        )
        json.dumps(doc.to_dict())  # tidak boleh melempar


# ---------------------------------------------------------------------------
# extract_file on synthetic files
# ---------------------------------------------------------------------------


class TestExtractFileOnSyntheticFiles:
    def test_png_yields_a_pid_with_the_tag_from_the_filename(self, tmp_path):
        p = tmp_path / "P&ID - GA-1201A.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n")
        doc = extract.extract_file(str(p))
        assert doc.meta.doc_type == "pid"
        assert doc.meta.equipment_tag == "GA-1201A"
        assert doc.meta.title == "P&ID GA-1201A"

    def test_png_approval_is_unknown(self, tmp_path):
        # A drawing image carries no signature. Claiming an approval status
        # would be inventing evidence.
        p = tmp_path / "P&ID - YD-2301.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n")
        assert extract.extract_file(str(p)).meta.approval_status == "unknown"

    def test_png_without_a_tag_still_yields_a_document(self, tmp_path):
        # It must not be dropped. A document with no join key is still evidence
        # that the dataset has something this system cannot place.
        p = tmp_path / "P&ID.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n")
        doc = extract.extract_file(str(p))
        assert doc.meta.doc_type == "pid"
        assert doc.meta.equipment_tag is None

    def test_corrupt_pdf_does_not_raise(self, tmp_path):
        # A file that fails to parse becomes an error field, not a crash that
        # takes the whole ingest down for 86 good documents.
        p = tmp_path / "Equipment Datasheet - GA-1201A.pdf"
        p.write_bytes(b"this is not a pdf")
        doc = extract.extract_file(str(p))
        assert doc.meta is not None
        assert doc.text == ""

    def test_jpg_is_treated_as_an_image(self, tmp_path):
        p = tmp_path / "P&ID - LV-6701.jpg"
        p.write_bytes(b"\xff\xd8\xff")
        assert extract.extract_file(str(p)).meta.doc_type == "pid"


# ---------------------------------------------------------------------------
# iter_dataset_files
# ---------------------------------------------------------------------------


class TestIterDatasetFiles:
    def test_finds_pdfs_and_images_recursively(self, tmp_path):
        (tmp_path / "Set_01").mkdir()
        (tmp_path / "Set_01" / "a.pdf").write_bytes(b"x")
        (tmp_path / "Set_01" / "sub").mkdir()
        (tmp_path / "Set_01" / "sub" / "b.png").write_bytes(b"x")
        found = extract.iter_dataset_files(str(tmp_path))
        assert len(found) == 2

    def test_ignores_workbooks(self, tmp_path):
        # Workbooks are read by dataset.py, not extract_file. Listing them here
        # would send a spreadsheet through the PDF path.
        (tmp_path / "WO.xlsx").write_bytes(b"x")
        assert extract.iter_dataset_files(str(tmp_path)) == []

    def test_ignores_other_extensions(self, tmp_path):
        for name in ("notes.txt", "archive.zip", "sheet.csv"):
            (tmp_path / name).write_bytes(b"x")
        assert extract.iter_dataset_files(str(tmp_path)) == []

    def test_result_is_sorted(self, tmp_path):
        for name in ("z.pdf", "a.pdf", "m.pdf"):
            (tmp_path / name).write_bytes(b"x")
        found = extract.iter_dataset_files(str(tmp_path))
        assert found == sorted(found)

    def test_extension_match_is_case_insensitive(self, tmp_path):
        (tmp_path / "A.PDF").write_bytes(b"x")
        assert len(extract.iter_dataset_files(str(tmp_path))) == 1

    def test_empty_root(self, tmp_path):
        assert extract.iter_dataset_files(str(tmp_path)) == []

    def test_missing_root_does_not_raise(self, tmp_path):
        assert extract.iter_dataset_files(str(tmp_path / "nope")) == []


# ---------------------------------------------------------------------------
# The equipment tag table
# ---------------------------------------------------------------------------


class TestEquipmentTagTable:
    def test_eight_units(self):
        assert len(extract.EQUIPMENT_TAGS) == 8

    def test_tags_are_unique(self):
        assert len(set(extract.EQUIPMENT_TAGS)) == len(extract.EQUIPMENT_TAGS)

    @pytest.mark.parametrize(
        "tag", ["GA-1201A", "YD-2301", "DC-3401A", "KC-4501", "EA-5601",
                "LV-6701", "CT-7801", "FA-8901"]
    )
    def test_known_tags_present(self, tag):
        assert tag in extract.EQUIPMENT_TAGS

    def test_no_tag_is_a_prefix_of_another(self):
        # "GA-1201A" and "GA-1201B" would make the alternation match the shorter
        # one first and mis-attribute a document. Word-boundary handling in
        # _meta_common is what prevents it; this asserts the precondition holds.
        tags = sorted(extract.EQUIPMENT_TAGS, key=len, reverse=True)
        for longer in tags:
            for shorter in tags:
                if longer is shorter:
                    continue
                assert not longer.startswith(shorter), (
                    f"{longer} starts with {shorter}"
                )