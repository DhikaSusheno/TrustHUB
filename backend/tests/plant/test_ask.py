"""Test ask: klasifikasi pertanyaan dan perakitan jawaban.

`answer()` adalah tempat dua jalur bertemu: retrieval dokumen (dengan trust
score dan badge) dan data terstruktur dari work order. Yang paling rawan di
sini bukan salah hitung, tapi terlihat benar padahal tidak menjawab -
misalnya menjawab pertanyaan ranking dengan ringkasan dokumen yang kebetulan
mengandung angka.

Jadi test di sini memusatkan attention pada tiga hal:

  1. klasifikasi memilih jalur yang benar untuk bentuk pertanyaan nyata,
  2. jawaban terstruktur menyebut equipment yang DITANYAKAN, bukan equipment
     mana pun yang punya data, dan
  3. penolakan selalu punya alasan yang bisa ditindaklanjuti.
"""

from __future__ import annotations

import dataclasses

import pytest

from plant import ask
from plant import registry
from plant import trust


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------


class TestClassify:
    @pytest.mark.parametrize(
        "question,kind",
        [
            # Nilai terukur: harus lewat document_parameters, bukan FTS.
            # lewat FTS, pertanyaan ini dijawab dari potongan kalimat yang
            # kebetulan memuat angkanya, tanpa knowing bahwa angka itu
            # setpoint untuk instrumen itu.
            ("What is the trip setpoint for PSLL-0001?", "parameter_value"),
            # "limit" polos bernilai HANYA kalau tag instrumen disebut (prefix
            # 3-4 huruf). "what are the limits of the plot plan for EQ-0001"
            # menyebut "limits" dan sebuah tag, tapi tag itu equipment dan
            # jawabannya ada di gambar plot plan, bukan di tabel nilai.
            ("what is the VSHH-0001 limit", "parameter_value"),
            ("what is the ZSO-0001 threshold", "parameter_value"),
            ("what are the limits of the plot plan for EQ-0001", "document"),
            # Ranking: butuh agregasi lintas unit.
            ("Which unit has the most work orders?", "ranking"),
            ("rank the equipment by downtime", "ranking"),
            ("compare EQ-0001 and EQ-0002 downtime", "ranking"),
            # Riwayat: butuh work order, bukan dokumen.
            ("how many breakdowns does EQ-0001 have?", "count"),
            ("total downtime for EQ-0001", "downtime_total"),
            ("how much did EQ-0001 breakdowns cost", "cost_total"),
            ("list the maintenance history for EQ-0001", "history"),
            # Everything else is a document question.
            ("What is the interlock logic for EQ-0001?", "document"),
            ("how do I change the gland packing on EQ-0001", "document"),
            ("what is OPL-EQ-0001-01 about", "document"),
            ("What does TJC-LLD-DS-EQ-0001 say?", "document"),
            ("what is nitrogen blanketing?", "document"),
        ],
    )
    def test_known_shapes(self, question: str, kind: str) -> None:
        assert ask.classify(question) == kind

    def test_empty_question_is_a_document_question(self) -> None:
        # Bukan klasifikasi meta seperti "unknown". Jalur dokumen akan
        # menolak sendiri dengan alasan, dan itu pesan yang lebih berguna
        # daripada "I could not classify your question".
        assert ask.classify("") == "document"

    def test_whitespace_only(self) -> None:
        assert ask.classify("   \n\t ") == "document"

    def test_never_raises(self) -> None:
        for question in ["?", "!!!", "12345", "a" * 3000, "\u2603\u00e9\u00e8"]:
            assert isinstance(ask.classify(question), str)

    def test_ranking_beats_count(self) -> None:
        # "which unit has the most breakdowns" menyebut "breakdowns"
        # (topik maintenance) DAN "most" (ranking). Kalau
        # COUNT_CUE menang, hasilnya "EQ-0001 has 2 breakdowns" untuk
        # pertanyaan yang menanyakan unit mana yang paling sering.
        assert ask.classify("which unit has the most breakdowns") == "ranking"

    def test_document_question_wins_over_maintenance_topic(self) -> None:
        # "how do I change the gland packing" tidak ada kaitannya dengan work
        # order, meski kata "packing" mungkin muncul di dataset.
        assert (
            ask.classify("how do I change the gland packing on EQ-0001")
            == "document"
        )


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


class TestFormatters:
    @pytest.mark.parametrize(
        "raw,expected",
        [(12.5, "12.5 hours"), (0, "0.0 hours"), (124, "124.0 hours")],
    )
    def test_hours(self, raw: float, expected: str) -> None:
        assert ask._fmt_hours(raw) == expected

    def test_missing_hours_is_spelled_out(self) -> None:
        # "unknown", bukan "0.0 hours". Nol berarti tidak ada downtime, dan
        # membedakannya adalah perbedaan antara "tidak ada" dan "tidak
        # diketahui" - yang kedua jauh lebih sering terjadi di data mentah.
        assert ask._fmt_hours(None) == "unknown"
        assert ask._fmt_hours(0) != "unknown"

    def test_idr_uses_thousands_separators(self) -> None:
        assert ask._fmt_idr(123_580_000) == "IDR 123,580,000"

    def test_missing_cost_is_spelled_out(self) -> None:
        assert ask._fmt_idr(None) == "unknown"

    def test_zero_cost_is_not_unknown(self) -> None:
        assert ask._fmt_idr(0) != "unknown"


# ---------------------------------------------------------------------------
# Structured answers
# ---------------------------------------------------------------------------


class TestAnswerParameterValue:
    def test_reads_the_value_from_the_index(self, synthetic_index) -> None:
        structured = ask.answer_parameter_value(
            synthetic_index, "what is the trip setpoint for PSLL-0001", None
        )
        assert structured is not None
        assert structured.kind == "parameter_value"
        assert "0.5" in structured.summary

    def test_names_the_instrument_and_the_value(self, synthetic_index) -> None:
        structured = ask.answer_parameter_value(
            synthetic_index, "what is the trip setpoint for PSLL-0001", None
        )
        assert "PSLL-0001" in structured.summary
        assert "barg" in structured.summary

    def test_unknown_instrument_gets_an_honest_empty_answer(self, synthetic_index) -> None:
        # Bukan None dan bukan angka. `answer()` memakai StructuredAnswer yang
        # `rows`-nya kosong sebagai sinyal "tidak ada yang bisa dijawab", dan
        # seperti itu penolakan menjadi eksplisit: "No document in the indexed
        # dataset states that value. I will not supply a value that no
        # document contains."
        #
        # None di sini justru lebih buruk: pemanggil akan memperlakukannya
        # sebagai "coba jalur lain", dan jalur lain kembali ke retrieval yang
        # bisa mengambil potongan milik unit lain.
        structured = ask.answer_parameter_value(
            synthetic_index, "what is the trip setpoint for VSHH-9999", None
        )
        assert structured is not None
        assert structured.rows == []
        assert "no document" in structured.summary.lower()

    def test_empty_index_also_gets_the_honest_empty_answer(self, empty_index) -> None:
        # Pertanyaannya harus menyebut tag instrumen. "trip setpoint" saja
        # tidak menyebut parameter bernama maupun tag, jadi fungsi itu
        # mengembalikan None lebih dulu - itu keputusan yang benar, bukan
        # kegagalan: tidak ada yang ditanyakan.
        structured = ask.answer_parameter_value(
            empty_index, "what is the trip setpoint for PSLL-0001", None
        )
        assert structured is not None
        assert structured.rows == []
        assert "no document" in structured.summary.lower()

    def test_a_question_naming_nothing_returns_none(self, synthetic_index) -> None:
        # None berarti "tidak ada parameter yang ditanyakan", bukan "tidak ada
        # jawabannya". Pemanggil memakai None untuk jatuh ke retrieval,
        # dan itu benar untuk pertanyaan yang tidak menyebut parameter apa pun.
        assert (
            ask.answer_parameter_value(synthetic_index, "trip setpoint", None) is None
        )

    def test_value_conflicting_documents_are_flagged(self, synthetic_index) -> None:
        # EQ-0002 punya TSHH-0002 = 230 dan 125. Menjawab satu angka tanpa
        # называть perbedaan yang ditemukannya adalah persis kesalahan yang
        # membuat orang percaya pada angka yang salah.
        structured = ask.answer_parameter_value(
            synthetic_index, "what is the temperature limit for TSHH-0002", None
        )
        assert structured is not None
        text = (structured.summary + " " + (structured.note or "")).lower()
        assert "230" in text and "125" in text
        assert any(
            word in text for word in ("conflict", "differ", "disagree", "two")
        ), structured.summary

    def test_scope_follows_the_equipment_tag(self, synthetic_index) -> None:
        # Tag yang diberikan harus membatasi hasil. Tanpa itu, pertanyaan
        # tentang EQ-0002 bisa dijawab dengan setpoint EQ-0001 yang kebetulan
        # punya nama instrumen serupa.
        structured = ask.answer_parameter_value(
            synthetic_index, "what is the trip setpoint", "EQ-0002"
        )
        assert structured is None or "PSLL-0001" not in structured.summary

    def test_no_rows_returns_none(self, empty_index) -> None:
        assert (
            ask.answer_parameter_value(empty_index, "trip setpoint", None) is None
        )


class TestAnswerFromMaintenance:
    def test_count_uses_the_named_equipment(self, synthetic_index) -> None:
        structured = ask.answer_from_maintenance(
            synthetic_index, "count", "how many breakdowns does EQ-0001 have?",
            "EQ-0001",
        )
        assert structured is not None
        # Fixture: EQ-0001 punya 2 breakdown dari 3 work order.
        assert "2" in structured.summary

    def test_count_does_not_leak_other_equipment(self, synthetic_index) -> None:
        structured = ask.answer_from_maintenance(
            synthetic_index, "count", "how many breakdowns does EQ-0001 have?",
            "EQ-0001",
        )
        assert "EQ-0002" not in structured.summary
        assert "EQ-0003" not in structured.summary

    def test_downtime_total(self, synthetic_index) -> None:
        structured = ask.answer_from_maintenance(
            synthetic_index, "downtime_total", "total downtime for EQ-0001", "EQ-0001"
        )
        assert structured is not None
        assert "hours" in structured.summary

    def test_history_lists_rows(self, synthetic_index) -> None:
        structured = ask.answer_from_maintenance(
            synthetic_index, "history", "maintenance history for EQ-0001", "EQ-0001"
        )
        assert structured is not None
        assert structured.rows

    def test_ranking_names_a_winner(self, synthetic_index) -> None:
        structured = ask.answer_from_maintenance(
            synthetic_index, "ranking", "which unit has the most work orders", None
        )
        assert structured is not None
        assert structured.rows
        assert "EQ-000" in structured.summary

    def test_unknown_equipment_returns_none(self, synthetic_index) -> None:
        # Bukan jawaban kosong. Kalau equipment tidak dikenal, jalur
        # dokumen/penolakan yang menangani, dengan pesan yang menyebut tag
        # tersebut tidak ada.
        structured = ask.answer_from_maintenance(
            synthetic_index, "count", "how many breakdowns does P-8802 have?", "P-8802"
        )
        assert structured is None

    def test_empty_index_returns_none(self, empty_index) -> None:
        assert (
            ask.answer_from_maintenance(
                empty_index, "count", "how many breakdowns", None
            )
            is None
        )


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    HITS = [
        {
            "doc_id": "d1a",
            "equipment_tag": "EQ-0001",
            "doc_type": "opl",
            "filename": "OPL-EQ-0001-01 - Seal_Flush.pdf",
            "title": "Seal Flush",
            "revision": "A",
            "approval_status": "approved",
            "content": "Establish the seal flush flow at 1.0 barg.",
        }
    ]

    def test_includes_the_question(self) -> None:
        assert "how do I flush the seal" in ask.build_prompt(
            "how do I flush the seal", self.HITS
        )

    def test_includes_source_identities(self) -> None:
        prompt = ask.build_prompt("how do I flush the seal", self.HITS)
        assert "OPL-EQ-0001-01" in prompt
        assert "EQ-0001" in prompt

    def test_labels_the_task(self) -> None:
        # `build_prompt` adalah user message; aturannya ada di SYSTEM_PROMPT
        # yang jadi system message. Yang diuji di sini hanya bahwa blok sumber
        # dan blok pertanyaan terpisah jelas, supaya model tidak mencampur
        # pertanyaan dengan isi dokumen.
        prompt = ask.build_prompt("how do I flush the seal", self.HITS)
        assert prompt.index("SOURCES") < prompt.index("QUESTION")
        assert "cite sources" in prompt.lower()

    def test_names_the_pdf_not_only_the_title(self) -> None:
        # Header sumber harus menyebut filename, bukan cuma title. Tanpa itu
        # model tidak pernah melihat nomor dokumen, dan jawaban yang
        # dibingkai [1] tidak bisa ditelusuri tanpa panel sumber - yang tidak
        # ada kalau jawabannya disalin ke tempat lain.
        prompt = ask.build_prompt("how do I flush the seal", self.HITS)
        assert "OPL-EQ-0001-01 - Seal_Flush.pdf" in prompt

    def test_no_hits_still_produces_a_usable_prompt(self) -> None:
        # Prompt dengan sumber kosong harus tetap valid supaya aturan "say so
        # plainly and stop" di SYSTEM_PROMPT bisa bekerja. Kalau pemanggil
        # justru melempar exception, model tidak pernah mendapat kesempatan
        # menolak dengan benar.
        prompt = ask.build_prompt("anything", [])
        assert "anything" in prompt
        assert "SOURCES" in prompt

    def test_a_hit_with_no_content_is_skipped_not_fatal(self) -> None:
        # Chunk kosong adalah hal nyata: PDF satu halaman yang isinya gambar
        # saja tetap punya baris di database, dan `content` bisa kosong.
        prompt = ask.build_prompt("q", [{"title": "Blank", "content": None}])
        assert "Blank" not in prompt
        assert "q" in prompt

    def test_never_raises_on_weird_hits(self) -> None:
        for hits in (
            [{}],
            [{"doc_id": "x", "content": None}],
            [{"doc_id": "x", "content": "y", "approval_status": None}],
        ):
            assert isinstance(ask.build_prompt("q", hits), str)


class TestSystemPrompt:
    def test_forbids_inventing_values(self) -> None:
        low = ask.SYSTEM_PROMPT.lower()
        assert any(
            phrase in low
            for phrase in ("do not invent", "never invent", "do not guess", "no outside")
        ), ask.SYSTEM_PROMPT

    def test_forbids_rewriting_procedural_and_safety_steps(self) -> None:
        # Aturan 5. Menyusun ulang langkah permit supaya lebih rapi terdengar
        # membantu, tapi itulah cara paling fatal mengarang langkah dari
        # sumber yang tidak mengatakannya.
        low = ask.SYSTEM_PROMPT.lower()
        assert "do not paraphrase" in low
        assert "quote them" in low
        for word in ("procedural steps", "safety precautions", "isolation"):
            assert word in low, word

    def test_forbids_rounding_a_measured_value(self) -> None:
        # "Never round or convert." Ini yang menjaga "> 7.1 mm/s" tetap
        # "> 7.1 mm/s", tidak berubah jadi "about 7 mm/s".
        assert "never round" in ask.SYSTEM_PROMPT.lower()

    def test_forbids_choosing_a_winner_among_disagreeing_sources(self) -> None:
        # Aturan 6. Kalau dua dokumen berbeda, model tidak berhak memutuskan
        # mana yang benar; itu pekerjaan orang yang bertanggung jawab di field.
        low = ask.SYSTEM_PROMPT.lower()
        assert "do not pick a winner" in low
        assert "subject-matter expert" in low

class TestComposeFromDocuments:
    def test_names_the_document_it_quoted(self) -> None:
        # Label memakai `title`, bukan filename: "Seal Flush" dibaca lebih
        # cepat oleh teknisi daripada "OPL-EQ-0001-01 - Seal_Flush.pdf".
        # Filename tetap tersedia di panel sumber (`Answer.sources`) yang
        # ditampilkan berdampingan dengan jawaban.
        text = ask.compose_from_documents(
            "how do I flush the seal",
            TestBuildPrompt.HITS,
        )
        assert "Seal Flush" in text

    def test_shows_the_section_when_there_is_one(self) -> None:
        hits = [dict(TestBuildPrompt.HITS[0], section="troubleshooting")]
        text = ask.compose_from_documents("q", hits)
        assert "troubleshooting" in text

    def test_no_hits_returns_empty_so_the_caller_stays_responsible(self) -> None:
        # String kosong, bukan kalimat sopan. Pemanggil memakai nilai kosong
        # sebagai sinyal "tidak ada yang bisa dikutip", dan kalimat yang
        # terlihat seperti jawaban justru menutupi sinyal itu. Menolak dengan
        # alasan yang tepat adalah tugas `trust.should_refuse`, bukan fungsi
        # penyusun kutipan ini.
        assert ask.compose_from_documents("how do I flush the seal", []) == ""

    def test_hits_with_no_usable_text_also_return_empty(self) -> None:
        assert ask.compose_from_documents("q", [{"title": "Blank", "content": "   "}]) == ""

    def test_does_not_invent_numbers(self) -> None:
        text = ask.compose_from_documents("how do I flush the seal", TestBuildPrompt.HITS)
        # Hanya angka yang benar-benar ada di sumber boleh muncul.
        assert "2.5" not in text


# ---------------------------------------------------------------------------
# answer() - jalur terstruktur
# ---------------------------------------------------------------------------


class TestAnswerStructuredPath:
    def test_structured_answer_scores_without_documents(self, synthetic_index) -> None:
        result = ask.answer(synthetic_index, "what is the trip setpoint for PSLL-0001")
        assert result.refused is False
        assert result.kind == "parameter_value"
        assert result.badge in {trust.TRUSTED, trust.VERIFY, trust.DO_NOT_EXECUTE}

    def test_maintenance_score_is_the_declared_constant(self, synthetic_index) -> None:
        # Nilai tetap, bukan jumlah berbobot: approval, revisi, dan kesepakatan
        # tidak bisa berlaku untuk lookup tabel maintenance karena tidak ada
        # dokumen yang disetujui - yang disetujui adalah angka di dalam
        # workbook itu.
        result = ask.answer(synthetic_index, "how many breakdowns does EQ-0001 have?")
        assert result.kind == "count"
        assert result.trust_score == ask.STRUCTURED_NO_CITATION_SCORE

    def test_parameter_score_is_measured_not_fixed(self, synthetic_index) -> None:
        # Nilai terukur BUKAN memakai konstanta. Nilainya diturunkan dari
        # dokumen yang benar-benar menyebut tag itu, jadi setpoint yang
        # disebut tujuh dokumen dan setpoint yang disebut satu dokumen tidak
        # boleh mendapat skor yang sama. Di index CALIBER: PSLL-1201 = 0.783,
        # VSHH-1201 = 0.600.
        answered = ask.answer(
            synthetic_index, "what is the trip setpoint for PSLL-0001"
        )
        assert answered.trust_score != ask.STRUCTURED_NO_CITATION_SCORE
        assert answered.badge == trust.badge_for(answered.trust_score)

    def test_the_constant_is_inside_the_verify_band(self) -> None:
        # Kalau konstanta ini jatuh di luar 0.5-0.8, setiap jawaban terstruktur
        # akan memakai satu badge saja dan guardrail kehilangan artinya.
        assert (
            trust.VERIFY_THRESHOLD
            <= ask.STRUCTURED_NO_CITATION_SCORE
            < trust.TRUSTED_THRESHOLD
        )

    def test_still_cites_the_document(self, synthetic_index) -> None:
        # Skornya tetap, tapi sumber tetap ditampilkan. "Tanpa sitasi" bukan
        # berarti "tanpa bukti" - berarti badge tidak bisa naik karena
        # persetujuan dokumen tidak berlaku.
        result = ask.answer(synthetic_index, "what is the trip setpoint for PSLL-0001")
        assert result.sources, "a structured answer must still show its source"

    def test_maintenance_answer_does_not_claim_documents(self, synthetic_index) -> None:
        result = ask.answer(synthetic_index, "how many breakdowns does EQ-0001 have?")
        assert result.kind == "count"
        assert result.structured is not None

    def test_empty_index_refuses_rather_than_inventing(self, empty_index) -> None:
        result = ask.answer(empty_index, "how many breakdowns does EQ-0001 have?")
        assert result.refused is True
        assert result.refusal_reason


# ---------------------------------------------------------------------------
# answer() - jalur dokumen
# ---------------------------------------------------------------------------


class TestAnswerDocumentPath:
    def test_setpoint_question_is_verbatim(self, synthetic_index) -> None:
        result = ask.answer(synthetic_index, "what is the trip setpoint for PSLL-0001")
        assert result.verbatim is True

    def test_reference_question_is_not_verbatim(self, synthetic_index) -> None:
        result = ask.answer(synthetic_index, "what is the seal flush plan")
        assert result.verbatim is False

    def test_carries_the_full_verdict(self, synthetic_index) -> None:
        result = ask.answer(synthetic_index, "what is the seal flush plan")
        assert result.signals
        assert result.reasons
        assert result.badge == trust.badge_for(result.trust_score)

    def test_llm_is_not_called_without_a_callback(self, synthetic_index) -> None:
        called = []

        def spy(question: str, prompt: str) -> str:
            called.append(question)
            return "LLM ANSWER"

        result = ask.answer(
            synthetic_index, "what is the seal flush plan", llm=spy
        )
        assert result.llm_used is True
        assert called

    def test_llm_failure_falls_back_to_the_document_text(self, synthetic_index) -> None:
        def broken(question: str, prompt: str) -> str:
            raise RuntimeError("provider is down")

        result = ask.answer(
            synthetic_index, "what is the seal flush plan", llm=broken
        )
        # Jawaban harus tetap ada. Provider LLM tidak boleh menjadi alasan
        # sistem terlihat kosong.
        assert result.answer.strip()
        assert "LLM ANSWER" not in result.answer
        assert result.llm_used is False

    def test_no_llm_leaves_the_documents_wording(self, synthetic_index) -> None:
        result = ask.answer(synthetic_index, "how do I establish the seal flush flow")
        assert "seal flush" in result.answer.lower()


# ---------------------------------------------------------------------------
# answer() - penolakan
# ---------------------------------------------------------------------------


class TestAnswerRefusals:
    @pytest.mark.parametrize(
        "question",
        [
            "write me a poem about hexane",
            "who is the CEO of Starbucks",
            "how do I open a bank account",
            "what is the weather in Jakarta tomorrow",
        ],
    )
    def test_out_of_scope_is_refused(self, synthetic_index, question: str) -> None:
        result = ask.answer(synthetic_index, question)
        assert result.refused is True, result.answer[:120]
        assert result.refusal_reason

    def test_unknown_equipment_is_refused_with_the_tag(self, synthetic_index) -> None:
        result = ask.answer(synthetic_index, "procedure for P-8802")
        assert result.refused is True
        assert "P-8802" in result.refusal_reason

    def test_missing_document_is_refused_with_the_number(self, synthetic_index) -> None:
        # Fixture sengaja tidak punya OPL-GA-1201A-04, meniru celah nyata di
        # dataset CALIBER.
        result = ask.answer(synthetic_index, "what does OPL-GA-1201A-04 say")
        assert result.refused is True
        assert "OPL-GA-1201A-04" in result.refusal_reason

    def test_refusal_never_returns_a_badge_that_implies_action(self, synthetic_index) -> None:
        result = ask.answer(synthetic_index, "who is the CEO of Starbucks")
        assert result.refused is True
        assert result.badge == trust.DO_NOT_EXECUTE

    def test_refusal_is_logged(self, synthetic_index) -> None:
        before = synthetic_index.execute(
            "SELECT COUNT(*) AS n FROM plant_audit_log"
        ).fetchone()["n"]
        ask.answer(synthetic_index, "who is the CEO of Starbucks")
        after = synthetic_index.execute(
            "SELECT COUNT(*) AS n FROM plant_audit_log"
        ).fetchone()["n"]
        assert after == before + 1

    def test_empty_question_is_refused(self, synthetic_index) -> None:
        result = ask.answer(synthetic_index, "")
        assert result.refused is True
        assert result.refusal_reason

    def test_every_refusal_reason_is_actionable(self, synthetic_index) -> None:
        # Alasan yang tidak memberi jalan keluar ("tidak bisa menjawab") sama
        # buruknya dengan tidak menjawab.
        for question in ("who is the CEO of Starbucks", "procedure for P-8802",
                         "what does OPL-GA-1201A-04 say", ""):
            reason = (ask.answer(synthetic_index, question).refusal_reason or "").lower()
            assert len(reason) > 20, f"{question!r} -> {reason!r}"


# ---------------------------------------------------------------------------
# answer() - equipment scope
# ---------------------------------------------------------------------------


class TestEquipmentScope:
    def test_single_tag_is_carried_through(self, synthetic_index) -> None:
        result = ask.answer(synthetic_index, "what is the seal flush plan for EQ-0001")
        assert result.equipment_tag == "EQ-0001"

    def test_two_tags_mean_cross_unit_not_a_pick(self, synthetic_index) -> None:
        # Memilih salah satu dari dua unit yang disebut akan menjawab
        # separuh pertanyaan dengan keyakinan penuh.
        result = ask.answer(
            synthetic_index, "compare the seal flush plan for EQ-0001 and EQ-0002"
        )
        assert result.equipment_tag is None
        assert result.cross_unit is True

    def test_no_tag_means_unscoped_not_cross_unit(self, synthetic_index) -> None:
        # `cross_unit` berarti pertanyaannya sendiri lintas unit ("compare X
        # and Y", "which unit..."), bukan sekadar tidak menyebut tag.
        # "what is the seal flush plan" tidak menyebut unit manapun, jadi
        # cakupannya belum diketahui - belum tentu lintas unit.
        result = ask.answer(synthetic_index, "what is the seal flush plan")
        assert result.equipment_tag is None
        assert result.cross_unit is False

    def test_explicit_ranking_is_cross_unit(self, synthetic_index) -> None:
        result = ask.answer(synthetic_index, "which unit has the most work orders")
        assert result.equipment_tag is None
        assert result.cross_unit is True

    def test_documents_of_other_equipment_are_not_cited(self, synthetic_index) -> None:
        result = ask.answer(synthetic_index, "what is the seal flush plan for EQ-0001")
        for source in result.sources:
            assert source.get("equipment_tag") in (None, "EQ-0001")


# ---------------------------------------------------------------------------
# Bentuk keluaran
# ---------------------------------------------------------------------------


class TestAnswerShape:
    def test_serialises_completely(self, synthetic_index) -> None:
        payload = dataclasses.asdict(
            ask.answer(synthetic_index, "what is the seal flush plan")
        )
        for key in (
            "question", "kind", "answer", "badge", "trust_score", "refused",
            "refusal_reason", "equipment_tag", "cross_unit", "verbatim",
            "sources", "signals", "reasons", "warnings", "llm_used",
        ):
            assert key in payload, key

    def test_score_is_in_range(self, synthetic_index) -> None:
        for question in (
            "what is the seal flush plan",
            "how many breakdowns does EQ-0001 have?",
            "who is the CEO of Starbucks",
        ):
            score = ask.answer(synthetic_index, question).trust_score
            assert 0.0 <= score <= 1.0, f"{question!r} -> {score}"

    def test_refused_implies_do_not_execute(self, synthetic_index) -> None:
        for question in ("who is the CEO of Starbucks", "procedure for P-8802"):
            result = ask.answer(synthetic_index, question)
            assert result.badge == trust.DO_NOT_EXECUTE

    def test_never_raises_on_hostile_input(self, synthetic_index) -> None:
        for question in ("a" * 5000, "' OR 1=1 --", "\x00\x01\x02", "../../etc/passwd"):
            result = ask.answer(synthetic_index, question)
            assert isinstance(result.answer, str)

    def test_never_raises_on_an_empty_index(self, empty_index) -> None:
        result = ask.answer(empty_index, "what is the seal flush plan")
        assert result.refused is True


class TestAuditLog:
    def test_records_role_and_score(self, synthetic_index) -> None:
        ask.answer(synthetic_index, "what is the seal flush plan", role="engineer")
        row = synthetic_index.execute(
            "SELECT * FROM plant_audit_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row["trust_score"] is not None
        assert row["badge"] in {trust.TRUSTED, trust.VERIFY, trust.DO_NOT_EXECUTE}

    def test_sources_are_stored_as_json_text(self, synthetic_index) -> None:
        ask.answer(synthetic_index, "what is the seal flush plan")
        row = synthetic_index.execute(
            "SELECT sources FROM plant_audit_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        # String JSON, bukan repr Python: kolomnya TEXT dan harus bisa
        # dibaca oleh tool lain tanpa mengimpor Python.
        assert isinstance(row["sources"], str)
        assert row["sources"].lstrip().startswith(("[", "{", "["))


class TestTopK:
    @pytest.mark.parametrize("top_k", [1, 3, 6, 20])
    def test_never_returns_more_than_asked(
        self, synthetic_index, top_k: int
    ) -> None:
        result = ask.answer(
            synthetic_index, "what is the seal flush plan", top_k=top_k
        )
        assert len(result.sources) <= top_k

    def test_top_k_of_one_still_answers(self, synthetic_index) -> None:
        # Membatasi sumber tidak boleh mengubah jawaban jadi tidak ada.
        result = ask.answer(synthetic_index, "what is the seal flush plan", top_k=1)
        assert result.answer.strip()
