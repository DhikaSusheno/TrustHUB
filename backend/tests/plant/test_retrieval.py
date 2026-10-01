"""Test parsing dan routing di `plant.retrieval`.

Modul ini memegang keputusan yang paling diam-diam keliru: tag mana yang
disebut user, equipment mana yang dimaksud, dan dokumen mana yang sebenarnya
diminta. Semua test di sini memakai string dan regex murni - tidak butuh
dataset.
"""

from __future__ import annotations

import pytest

from plant import retrieval

KNOWN = ["EQ-0001", "EQ-0002", "EQ-0003"]


# ---------------------------------------------------------------------------
# TAG_PATTERN
# ---------------------------------------------------------------------------


class TestTagPattern:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("What about EQ-0001?", ["EQ-0001"]),
            ("eq-0001 needs a seal flush", ["EQ-0001"]),
            ("compare EQ-0001 and EQ-0002", ["EQ-0001", "EQ-0002"]),
            # Tag equipment di dataset CALIBER: dua huruf, 4 digit, huruf akhir
            ("check GA-1201A today", ["GA-1201A"]),
            ("check DC-3401A today", ["DC-3401A"]),
            # Tag instrumen punya bentuk sama dan HARUS ikut tertangkap,
            # kalau tidak guardrail akan menganggapnya equipment biasa.
            ("trip setpoint for PSLL-1201", ["PSLL-1201"]),
            # Satu huruf sebelum tanda hubung: pengguna akan mengetik seperti
            # ini, dan pola lama dua huruf melewatkannya.
            ("procedure for P-8802", ["P-8802"]),
            ("procedure for P-9901", ["P-9901"]),
        ],
    )
    def test_matches_expected(self, text: str, expected: list[str]) -> None:
        found = sorted(m.group(0).upper() for m in retrieval.TAG_PATTERN.finditer(text.upper()))
        assert found == sorted(expected)

    @pytest.mark.parametrize(
        "text",
        [
            "what is the answer",
            # Angka polos bukan tag
            "there were 31 breakdowns in 2025",
            # Standar tanpa nomor: memang bukan bentuk tag sama sekali
            "is this ASME rated",
        ],
    )
    def test_rejects_non_tags(self, text: str) -> None:
        found = [m.group(0) for m in retrieval.TAG_PATTERN.finditer(text.upper())]
        assert found == [], f"{text!r} should not match a tag, got {found}"

    @pytest.mark.parametrize(
        "text",
        [
            "we follow ISO-9001 in this plant",
            "the PRE-0001 stage",
            "compare P-8802 and ZSO-1201",
        ],
    )
    def test_prefix_length_is_not_decided_by_tag_pattern(self, text: str) -> None:
        # TAG_PATTERN SENGAJA tidak bisa membedakan equipment dari instrumen
        # atau dari kode standar: "ISO" juga tiga huruf, sama seperti prefix
        # instrumen "ZSO". Bentuk equipment dipisahkan di EQUIPMENT_TAG_SHAPE.
        #
        # Test ini ada supaya tidak ada yang "memperbaiki" pola ini tanpa
        # memperbaiki EQUIPMENT_TAG_SHAPE juga - itulah bug yang sebenarnya.
        found = [m.group(0) for m in retrieval.TAG_PATTERN.finditer(text.upper())]
        assert found, (
            f"{text!r} no longer matches TAG_PATTERN; if the pattern was "
            "narrowed, EQUIPMENT_TAG_SHAPE must be re-checked at the same time"
        )


class TestEquipmentTagShape:
    @pytest.mark.parametrize(
        "tag",
        [
            "GA-1201A", "DC-3401A", "YD-2301", "CT-7801", "KC-4501",
            "LV-6701", "EA-5601", "FA-8901",   # dataset CALIBER
            "EQ-0001",                           # fixture test
            "P-8802", "P-9901",                  # satu huruf sebelum tanda hubung
        ],
    )
    def test_equipment_tags_match(self, tag: str) -> None:
        assert retrieval.EQUIPMENT_TAG_SHAPE.match(tag), f"{tag} should be equipment"

    @pytest.mark.parametrize(
        "tag",
        [
            # Tag instrumen dataset: prefix 3-4 huruf
            "PSLL-1201", "TSHH-1201", "VSHH-1201", "LSHH-8901", "ZSO-1201",
            "FSLL-1201", "LSLL-5601",
            # Standar, bukan unit
            "ISO-9001",
        ],
    )
    def test_non_equipment_tags_do_not_match(self, tag: str) -> None:
        assert not retrieval.EQUIPMENT_TAG_SHAPE.match(tag), (
            f"{tag} should not be treated as an equipment tag"
        )


class TestUnknownTagsMentioned:
    def test_finds_unknown(self) -> None:
        assert retrieval.unknown_tags_mentioned(
            "procedure for P-8802", KNOWN
        ) == ["P-8802"]

    def test_known_tag_is_not_unknown(self) -> None:
        assert retrieval.unknown_tags_mentioned("procedure for EQ-0001", KNOWN) == []

    def test_deduplicates(self) -> None:
        found = retrieval.unknown_tags_mentioned(
            "compare P-8802 with P-8802 and ZZ-0001", KNOWN
        )
        assert found == ["P-8802", "ZZ-0001"]

    def test_empty_question(self) -> None:
        assert retrieval.unknown_tags_mentioned("", KNOWN) == []

    def test_mixed_known_and_unknown(self) -> None:
        found = retrieval.unknown_tags_mentioned(
            "compare EQ-0001 with P-8802", KNOWN
        )
        assert found == ["P-8802"]

    @pytest.mark.parametrize(
        "question",
        [
            # Tag instrumen yang tidak dikenal BUKAN alasan penolakan: itu
            # nilai terukur, bukan equipment. Kalau ikut ditolak, "what is the
            # trip setpoint for VSHH-9999?" dijawab "equipment not in
            # dataset" padahal tidak ada equipment dengan nama itu. Jalur
            # structured masih punya baris untuk tag itu, jadi sistem akan
            # diam-diam menjawab dengan angka yang benar dan nol sitasi.
            "what is the trip setpoint for VSHH-9999?",
            "trip setpoint for TSHH-8888",
            "what is the LSHH-7777 setting",
            # Standar mutu, bukan unit
            "do we comply with ISO-9001?",
            "is this ASME rated",
        ],
    )
    def test_instrument_and_standard_tags_are_not_unknown_equipment(
        self, question: str
    ) -> None:
        assert retrieval.unknown_tags_mentioned(question, KNOWN) == []


# ---------------------------------------------------------------------------
# Document references
# ---------------------------------------------------------------------------


class TestExtractDocumentRefs:
    @pytest.mark.parametrize(
        "question,expected_present",
        [
            ("what does OPL-EQ-0001-01 say", "OPL-EQ-0001-01"),
            ("summarise TJC-LLD-IL-EQ-0001", "TJC-LLD-IL-EQ-0001"),
            ("show me SEQ-TJC-LLD-1200", "SEQ-TJC-LLD-1200"),
            ("read CAL-EQ-0001-01", "CAL-EQ-0001-01"),
        ],
    )
    def test_extracts_reference(
        self, question: str, expected_present: str
    ) -> None:
        found = retrieval.extract_document_refs(question)
        assert any(expected_present.upper() in ref.upper() for ref in found), (
            f"{expected_present!r} not found in {found!r}"
        )

    def test_plain_question_has_no_refs(self) -> None:
        assert retrieval.extract_document_refs("how do I change a gland packing") == []

    @pytest.mark.parametrize(
        "ref",
        [
            # Bentuk yang diukur dari dataset CALIBER. Pola TJC versi lama
            # tidak mencocokkan SATU PUN dari 32 doc_no, karena pola itu menuntut
            # segmen terakhir tanpa tanda hubung sementara doc_no berakhir dengan
            # TAG EQUIPMENT ("TJC-LLD-DS-GA-1201A").
            "TJC-LLD-DS-GA-1201A",
            "TJC-LLD-GA-DC-3401A",
            "TJC-LLD-IL-CT-7801",
            "TJC-LLD-PID-1201",       # P&ID reference
            "TJC-LLD-1200-01",        # functional_location
            "SEQ-1201",               # interlock logic sequence
            "WPN-MAT-001",            # related workbook
            "OPL-GA-1201A-04",        # one point lesson, termasuk yang HILANG
        ],
    )
    def test_real_dataset_reference_shapes(self, ref: str) -> None:
        assert ref in retrieval.extract_document_refs(f"what does {ref} say"), (
            f"{ref} must be recognised as a document reference"
        )

    @pytest.mark.parametrize(
        "text",
        [
            # Equipment tag polos BUKAN nomor dokumen. Kalau tidak, "what
            # about GA-1201A" akan dianggap penyebutan dokumen dan memicu
            # pemeriksaan "dokumen ini tidak ada".
            "what about GA-1201A",
            "procedure for EQ-0001",
        ],
    )
    def test_equipment_tag_is_not_a_document_reference(self, text: str) -> None:
        assert retrieval.extract_document_refs(text) == []


# ---------------------------------------------------------------------------
# Equipment name resolution
# ---------------------------------------------------------------------------


class TestNameAliases:
    """Alias diturunkan dari tabel equipment, bukan hardcode."""

    def test_requires_distinctive_words(self, synthetic_index) -> None:
        aliases = retrieval.name_aliases(synthetic_index)
        assert set(aliases) == {"EQ-0001", "EQ-0002", "EQ-0003"}

    def test_shared_words_are_dropped(self, synthetic_index) -> None:
        # Semua nama fixture mengandung "SAMPLE", jadi kata itu tidak
        # boleh jadi padanan: menyebut "sample" tidak menentukan unit mana.
        for tag, options in retrieval.name_aliases(synthetic_index).items():
            for alias in options:
                assert "sample" not in alias, f"{tag}: shared word leaked into {alias}"

    def test_empty_database_gives_no_aliases(self, empty_index) -> None:
        assert retrieval.name_aliases(empty_index) == {}

    def test_single_distinctive_word_is_not_enough(self, empty_index) -> None:
        # Kalau nama hanya punya satu kata pembeda, menyebut kata itu belum
        # tentu menentukan unit, jadi tidak boleh jadi padanan.
        import sqlite3

        empty_index.execute(
            "INSERT INTO equipment (equipment_tag, equipment_name) VALUES (?, ?)",
            ("EQ-0009", "UNIQUENAME"),
        )
        empty_index.commit()
        assert "EQ-0009" not in retrieval.name_aliases(empty_index)


class TestResolveByEquipmentName:
    ALIASES = {
        "EQ-0001": ("feed pump",),
        "EQ-0002": ("reactor vessel",),
        "EQ-0003": ("air compressor",),
    }

    @pytest.mark.parametrize(
        "question,expected",
        [
            ("procedure for the feed pump", "EQ-0001"),
            ("the feed pump leaks", "EQ-0001"),
            ("describe the reactor vessel", "EQ-0002"),
            ("tell me about the air compressor", "EQ-0003"),
        ],
    )
    def test_resolves_full_name(self, question: str, expected: str) -> None:
        assert retrieval.resolve_by_equipment_name(
            question, KNOWN, self.ALIASES
        ) == expected

    def test_without_aliases_nothing_resolves(self) -> None:
        # Bukan kegagalan: mode lintas unit lebih jujur daripada menebak unit
        # yang salah.
        assert retrieval.resolve_by_equipment_name("the feed pump", KNOWN) is None

    def test_partial_name_is_not_enough(self) -> None:
        # "vessel" sendirian tidak menentukan unit mana.
        assert retrieval.resolve_by_equipment_name("what about the vessel", KNOWN,
                                                   self.ALIASES) is None

    def test_unknown_tag_name_not_resolved(self) -> None:
        assert retrieval.resolve_by_equipment_name(
            "the feed pump", ["EQ-0002", "EQ-0003"], self.ALIASES
        ) is None

    def test_empty_question(self) -> None:
        assert retrieval.resolve_by_equipment_name("", KNOWN, self.ALIASES) is None

    def test_no_alias_match(self) -> None:
        assert retrieval.resolve_by_equipment_name(
            "what is the weather", KNOWN, self.ALIASES
        ) is None

    def test_longest_match_wins(self) -> None:
        # Dua unit punya padanan yang tumpang tindih sebagian; yang lebih
        # spesifik harus menang, bukan yang pertama di dict.
        overlapping = {
            "EQ-0001": ("pump",),
            "EQ-0002": ("reactor vessel pump",),
        }
        assert retrieval.resolve_by_equipment_name(
            "the reactor vessel pump", KNOWN, overlapping
        ) == "EQ-0002"


class TestDetectEquipmentTag:
    def test_literal_tag_wins(self) -> None:
        assert retrieval.detect_equipment_tag(
            "procedure for EQ-0002", KNOWN
        ) == "EQ-0002"

    def test_two_tags_is_cross_unit(self) -> None:
        # Memilih salah satu akan menjawab separuh pertanyaan dengan
        # keyakinan penuh, jadi hasilnya harus None.
        assert retrieval.detect_equipment_tag(
            "compare EQ-0001 and EQ-0002 downtime", KNOWN
        ) is None

    def test_name_resolves_to_tag(self) -> None:
        assert retrieval.detect_equipment_tag(
            "procedure for the feed pump", KNOWN, None, {"EQ-0001": ("feed pump",)}
        ) == "EQ-0001"

    def test_name_needs_aliases(self) -> None:
        # Tanpa alias, nama unit tidak dikenali dan hasilnya mode lintas unit.
        assert retrieval.detect_equipment_tag(
            "procedure for the feed pump", KNOWN
        ) is None

    def test_no_mention_is_none(self) -> None:
        assert retrieval.detect_equipment_tag(
            "which equipment fails most often", KNOWN
        ) is None

    def test_tag_resolution_is_case_insensitive(self) -> None:
        assert retrieval.detect_equipment_tag("procedure for eq-0001", KNOWN) == "EQ-0001"

    def test_doc_hits_are_ignored(self) -> None:
        # Parameter doc_hits sengaja diabaikan. FTS5 selalu mengembalikan
        # hit untuk pertanyaan apa pun yang punya satu kata yang kebetulan
        # muncul, jadi menebak tag dari sana membuat "who is the CEO of
        # Starbucks?" ter-answer sebagai pertanyaan tentang sebuah unit.
        fake_hits = [{"equipment_tag": "EQ-0003", "score": 99.0}]
        assert retrieval.detect_equipment_tag(
            "who is the CEO of Starbucks", KNOWN, fake_hits
        ) is None


# ---------------------------------------------------------------------------
# Cross-unit cues
# ---------------------------------------------------------------------------


class TestCrossUnitCues:
    @pytest.mark.parametrize(
        "question",
        [
            "which equipment fails most often",
            "what equipment has the most breakdowns",
            "compare EQ-0001 and EQ-0002",
            "which unit has the highest downtime",
            "total repair cost for the whole plant",
            "list all equipment",
            "summarise the maintenance situation",
            "which pump is worst",
        ],
    )
    def test_detects_cross_unit(self, question: str) -> None:
        assert retrieval.is_cross_unit_question(question) is True

    @pytest.mark.parametrize(
        "question",
        [
            "what is the trip setpoint for PSLL-0001",
            "how do I change the gland packing on EQ-0001",
            "what does OPL-EQ-0001-01 say",
            "",
        ],
    )
    def test_single_unit_is_not_cross_unit(self, question: str) -> None:
        assert retrieval.is_cross_unit_question(question) is False


# ---------------------------------------------------------------------------
# Non-knowledge intent
# ---------------------------------------------------------------------------


class TestNonKnowledgeIntent:
    @pytest.mark.parametrize(
        "question",
        [
            "write me a poem about hexane",
            "Write me a haiku about pumps",
            "draft an email to the vendor",
            "compose a limereme about valves",
            "write a cover letter for a data analyst job",
            "tell me a joke about engineers",
            "translate this to French please",
            "summarise the plot of Hamlet",
        ],
    )
    def test_detects_creative_request(self, question: str) -> None:
        assert retrieval.non_knowledge_intent(question) is True

    @pytest.mark.parametrize(
        "question",
        [
            "what is the trip setpoint for PSLL-0001",
            "summarise the OPL lesson for EQ-0001",
            # "write" sebagai bagian dari "written" tidak boleh memicu
            "what is written in the datasheet for EQ-0001",
            "how do I change the gland packing",
            "total downtime for the whole plant",
            "",
        ],
    )
    def test_knowledge_request_is_not_flagged(self, question: str) -> None:
        assert retrieval.non_knowledge_intent(question) is False


# ---------------------------------------------------------------------------
# Document type intent
# ---------------------------------------------------------------------------


class TestRequestedDocTypes:
    @pytest.mark.parametrize(
        "question,doc_type",
        [
            ("what is the interlock logic for EQ-0001", "interlock"),
            ("show me the cause and effect matrix", "interlock"),
            ("give me the datasheet for EQ-0001", "datasheet"),
            ("show me the plot plan", "plot_plan"),
            ("which revision is the GA drawing", "ga"),
            ("summarise the one point lesson for EQ-0001", "opl"),
        ],
    )
    def test_routes_to_doc_type(self, question: str, doc_type: str) -> None:
        assert doc_type in [t for _, t in retrieval.requested_doc_types(question)]

    def test_generic_question_has_no_intent(self) -> None:
        assert retrieval.requested_doc_types("which equipment fails most often") == []

    def test_multiple_intents_are_all_returned(self) -> None:
        wanted = [t for _, t in
                  retrieval.requested_doc_types("show the datasheet and the plot plan")]
        assert "datasheet" in wanted and "plot_plan" in wanted

    def test_intent_carries_a_bonus(self) -> None:
        pairs = retrieval.requested_doc_types("interlock logic")
        assert pairs and pairs[0][0] > 0


# ---------------------------------------------------------------------------
# Per-document cap
# ---------------------------------------------------------------------------


class TestCapPerDocument:
    @staticmethod
    def _hits(layout: list[tuple[str, int]]) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for doc_id, count in layout:
            for i in range(count):
                out.append({"doc_id": doc_id, "score": 100.0 - i, "i": i})
        return out

    def test_caps_chunks_per_document(self) -> None:
        hits = self._hits([("a", 5), ("b", 2)])
        kept = retrieval._cap_per_document(hits, top_k=10, per_document=3)
        assert sum(1 for h in kept if h["doc_id"] == "a") == 3
        assert sum(1 for h in kept if h["doc_id"] == "b") == 2

    def test_respects_top_k(self) -> None:
        hits = self._hits([("a", 4), ("b", 4), ("c", 4)])
        assert len(retrieval._cap_per_document(hits, top_k=5, per_document=3)) == 5

    def test_preserves_order(self) -> None:
        hits = self._hits([("a", 3), ("b", 3)])
        kept = retrieval._cap_per_document(hits, top_k=6, per_document=2)
        assert [h["doc_id"] for h in kept] == ["a", "a", "b", "b"]

    def test_empty_hits(self) -> None:
        assert retrieval._cap_per_document([], top_k=5) == []

    def test_single_document_under_cap(self) -> None:
        hits = self._hits([("a", 2)])
        assert len(retrieval._cap_per_document(hits, top_k=5, per_document=3)) == 2

    def test_cap_does_not_reorder_by_score(self) -> None:
        # Setara tinggi, tapi hanya tiga pertama dari "a" yang boleh lewat.
        hits = self._hits([("a", 10)])
        kept = retrieval._cap_per_document(hits, top_k=10, per_document=3)
        assert [h["i"] for h in kept] == [0, 1, 2]


# ---------------------------------------------------------------------------
# FTS query building
# ---------------------------------------------------------------------------


class TestFtsQuery:
    @pytest.mark.parametrize(
        "query",
        [
            "what is the trip setpoint for PSLL-0001",
            "how do I change the gland packing",
            "",
            "   ",
        ],
    )
    def test_never_raises(self, query: str) -> None:
        # Query kosong adalah penyebab klasik OperationalError dari FTS5.
        # Fungsi ini harus selalu mengembalikan string yang bisa diparse.
        result = retrieval._fts_query(query)
        assert isinstance(result, str)

    def test_quotes_every_term(self) -> None:
        q = retrieval._fts_query("gland packing")
        assert '"' in q


# ---------------------------------------------------------------------------
# Retrieval against the synthetic index
# ---------------------------------------------------------------------------


class TestSearch:
    def test_finds_matching_chunk(self, synthetic_index) -> None:
        hits = retrieval.search(synthetic_index, "gland packing", top_k=5)
        assert hits, "should find the gland packing chunk"
        assert any("gland packing" in h["content"].lower() for h in hits)

    def test_hits_carry_document_metadata(self, synthetic_index) -> None:
        # Metadata harus menempel SEBELUM scoring, karena bonus niat jenis
        # dokumen membandingkan doc_type. Kalau menempel setelah, doc_type
        # selalu None saat rerank dan seluruh bonus itu diam-diam mati.
        hits = retrieval.search(synthetic_index, "interlock logic", top_k=3)
        assert hits
        for h in hits:
            assert h.get("doc_type")
            assert h.get("filename")
            assert "approval_status" in h

    def test_equipment_filter_narrows(self, synthetic_index) -> None:
        hits = retrieval.search(synthetic_index, "start-up", equipment_tag="EQ-0002",
                                top_k=5)
        assert hits
        assert all(h["equipment_tag"] == "EQ-0002" for h in hits)

    def test_unknown_equipment_filter_returns_empty(self, synthetic_index) -> None:
        # Equipment yang tidak punya dokumen harus menghasilkan kosong supaya
        # pemanggil bisa menolak dengan jujur - bukan diam-diam memakai
        # dokumen unit lain.
        hits = retrieval.search(synthetic_index, "anything",
                                equipment_tag="EQ-9999", top_k=5)
        assert hits == []

    def test_doc_type_filter(self, synthetic_index) -> None:
        hits = retrieval.search(synthetic_index, "EQ-0001", doc_type="interlock",
                                top_k=5)
        assert hits
        assert all(h["doc_type"] == "interlock" for h in hits)

    def test_interlock_intent_beats_repetition(self, synthetic_index) -> None:
        # OPL EQ-0001 mengulang kata kunci lebih banyak, tapi pertanyaan
        # expressly meminta logika interlock, jadi diagramnya harus naik.
        hits = retrieval.search(synthetic_index, "interlock logic for EQ-0001",
                                equipment_tag="EQ-0001", top_k=5)
        assert hits
        assert any(h["doc_type"] == "interlock" for h in hits)

    def test_per_document_cap_applies_to_results(self, synthetic_index) -> None:
        hits = retrieval.search(synthetic_index, "EQ-0001 seal", top_k=6)
        per_doc: dict[str, int] = {}
        for h in hits:
            per_doc[h["doc_id"]] = per_doc.get(h["doc_id"], 0) + 1
        assert all(n <= retrieval.PER_DOCUMENT_CAP for n in per_doc.values()), per_doc

    def test_scores_are_sorted_descending(self, synthetic_index) -> None:
        hits = retrieval.search(synthetic_index, "EQ-0001", top_k=8)
        scores = [h["score"] for h in hits]
        assert scores == sorted(scores, reverse=True)

    def test_nonsense_query_returns_no_documentation_error(
        self, synthetic_index
    ) -> None:
        # Tidak harus error.Fq5 mungkin mengembalikan 0 baris.
        assert isinstance(retrieval.search(synthetic_index, "zzzqqqxyz",
                                          top_k=3), list)

    def test_empty_index_returns_empty(self, empty_index) -> None:
        assert retrieval.search(empty_index, "anything", top_k=5) == []

    def test_top_k_is_respected(self, synthetic_index) -> None:
        assert len(retrieval.search(synthetic_index, "EQ-0001", top_k=2)) <= 2


class TestContextForAnswer:
    def test_returns_string(self, synthetic_index) -> None:
        hits = retrieval.search(synthetic_index, "gland packing", top_k=3)
        assert isinstance(retrieval.context_for_answer(hits), str)

    def test_empty_hits(self) -> None:
        assert retrieval.context_for_answer([]) == ""

    def test_respects_max_chars(self, synthetic_index) -> None:
        hits = retrieval.search(synthetic_index, "EQ-0001", top_k=10)
        out = retrieval.context_for_answer(hits, max_chars=200)
        assert len(out) <= 400  # allow for the per-hit header line


class TestRelatedDocuments:
    def test_finds_sibling_docs(self, synthetic_index) -> None:
        related = retrieval.related_documents(synthetic_index, "d1a")
        assert isinstance(related, list)
        assert all(r.get("doc_id") != "d1a" for r in related)

    def test_unknown_doc_id(self, synthetic_index) -> None:
        assert isinstance(retrieval.related_documents(synthetic_index, "nope"), list)
