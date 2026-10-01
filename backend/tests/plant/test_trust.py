"""Test Trust Engine: skor, badge, dan guardrail penolakan.

Modul ini yang memutuskan boleh-tidaknya sebuah jawaban dipakai di lapangan.
Test di sini sengaja memusatkan attention pada dua hal:

  1. angka ambang dan bobotnya konsisten satu sama lain, dan
  2. penolakan terjadi pada urutan yang benar.

Urutannya penting karena beberapa pemeriksaan overlap. "P-8802 bukan equipment
di sini" dan "tidak ada sumber" sama-sama berarti jangan dijawab, tapi pesannya
berbeda dan orang yang membaca perlu tahu alasan yang sebenarnya. Test yang
salah urutan akan tetap hijau kalau tidak memeriksa pesannya.
"""

from __future__ import annotations

import pytest

from plant import registry
from plant import trust


# ---------------------------------------------------------------------------
# Konstanta
# ---------------------------------------------------------------------------


class TestConstants:
    def test_weights_sum_to_one(self) -> None:
        # Kalau tidak berjumlah satu, skor bukan probabilitas dan angka 0.80
        # sebagai ambang TRUSTED kehilangan makna.
        assert sum(trust.WEIGHTS.values()) == pytest.approx(1.0), trust.WEIGHTS

    def test_weights_are_non_negative(self) -> None:
        assert all(w >= 0 for w in trust.WEIGHTS.values())

    @pytest.mark.parametrize(
        "name",
        ["approval", "revision", "agreement", "relevance", "coverage"],
    )
    def test_every_signal_has_a_weight(self, name: str) -> None:
        assert name in trust.WEIGHTS

    def test_no_signal_without_a_weight(self) -> None:
        # Sinyal yang punya bobot nol diam-diam diabaikan. Kalau nama sinyal
        # berubah tapi bobotnya tidak, kesalahan itu tidak terlihat.
        assert set(trust.WEIGHTS) >= {
            "approval", "revision", "agreement", "relevance", "coverage",
        }

    def test_thresholds_are_ordered(self) -> None:
        assert trust.TRUSTED_THRESHOLD > trust.VERIFY_THRESHOLD

    def test_badges_are_distinct_strings(self) -> None:
        assert len({trust.TRUSTED, trust.VERIFY, trust.DO_NOT_EXECUTE}) == 3


# ---------------------------------------------------------------------------
# badge_for
# ---------------------------------------------------------------------------


class TestBadgeFor:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (1.00, trust.TRUSTED),
            (0.80, trust.TRUSTED),
            (0.799, trust.VERIFY),
            (0.50, trust.VERIFY),
            (0.499, trust.DO_NOT_EXECUTE),
            (0.00, trust.DO_NOT_EXECUTE),
        ],
    )
    def test_boundaries(self, score: float, expected: str) -> None:
        assert trust.badge_for(score) == expected

    def test_agrees_with_evaluate_on_a_clean_answer(self, synthetic_index) -> None:
        # badge_for adalah pemetaan skor-ke-badge. evaluate() punya dua aturan
        # keras yang TIDAK ada di badge_for, jadi yang dibandingkan di sini
        # hanya kasus yang kedua aturan itu tidak berlaku.
        hits = registry_approved_hits()
        verdict = trust.evaluate("what is the maintenance history", hits)
        assert verdict.badge == trust.badge_for(verdict.score)

    def test_does_not_apply_the_safety_rule(self) -> None:
        # Aturan keras ada di evaluate(), bukan di sini. Kalau badge_for
        # ikut menerapkannya, pemanggil yang sudah tahu badge-nya tidak
        # bisa memakai fungsi ini sama sekali.
        assert trust.badge_for(1.0) == trust.TRUSTED


def registry_approved_hits() -> list[dict[str, object]]:
    """Dua hit dari dokumen approved, tanpa pertanyaan safety."""
    return [
        {
            "doc_id": "d1a",
            "equipment_tag": "EQ-0001",
            "doc_type": "opl",
            "filename": "OPL-EQ-0001-01 - Seal_Flush.pdf",
            "revision": "A",
            "approval_status": "approved",
            "approved_by": "EMP-0001",
            "is_safety_critical": 0,
            "score": 12.0,
            "content": "Establish the seal flush flow for EQ-0001.",
        },
        {
            "doc_id": "d1b",
            "equipment_tag": "EQ-0001",
            "doc_type": "interlock",
            "filename": "Interlock Logic Diagram - EQ-0001.pdf",
            "revision": "",
            "approval_status": "unknown",
            "approved_by": None,
            "is_safety_critical": 0,
            "score": 9.0,
            "content": "Interlock logic diagram for EQ-0001.",
        },
    ]


# ---------------------------------------------------------------------------
# Sinyal individual
# ---------------------------------------------------------------------------


class TestSignalApproval:
    """Skor approval memakai status TERBURUK, bukan yang terbaik."""

    @staticmethod
    def _hits(*statuses: str) -> list[dict[str, object]]:
        return [
            {
                "doc_id": f"d{i}", "equipment_tag": "EQ-0001",
                "doc_type": "opl", "filename": f"OPL-{i}.pdf",
                "title": f"OPL {i}", "revision": "A",
                "approval_status": s, "approved_by": "EMP-0001" if s == "approved" else None,
                "is_safety_critical": 0, "score": 10.0, "content": "seal flush plan",
            }
            for i, s in enumerate(statuses)
        ]

    def test_no_hits_scores_zero(self) -> None:
        assert trust.signal_approval([]).score == 0.0

    def test_all_approved_scores_highest(self) -> None:
        sig = trust.signal_approval(self._hits("approved", "approved"))
        assert sig.score > 0.9

    def test_one_unknown_source_drags_the_whole_answer_down(self) -> None:
        # Ini disengaja: satu dokumen yang belum disetujui membuat seluruh
        # jawaban tidak layak dieksekusi, meskipun yang lain approved.
        both = trust.signal_approval(self._hits("approved", "approved"))
        mixed = trust.signal_approval(self._hits("approved", "unknown"))
        assert mixed.score < both.score

    def test_unknown_alone_is_not_zero(self) -> None:
        assert 0 < trust.signal_approval(self._hits("unknown")).score < 1

    def test_missing_status_is_treated_as_unknown(self) -> None:
        # Dokumen tanpa kolom status harus dinilai sebagai unknown. Menganggapnya
        # approved akan memberi badge tinggi ke dokumen yang tidak pernah
        # ditandatangani siapa pun.
        without = [{k: v for k, v in h.items() if k != "approval_status"}
                   for h in self._hits("approved")]
        assert trust.signal_approval(without).score == pytest.approx(
            trust.signal_approval(self._hits("unknown")).score
        )

    def test_detail_names_the_weakest_source(self) -> None:
        sig = trust.signal_approval(self._hits("approved", "unknown"))
        assert "unknown" in sig.detail

    def test_evidence_lists_every_source(self) -> None:
        sig = trust.signal_approval(self._hits("approved", "unknown"))
        assert len(sig.evidence) == 2


class TestSignalRevision:
    def test_no_revision_is_not_penalised_to_zero(self) -> None:
        # OPL tidak punya nomor revisi. Revisi tidak berarti usang kalau
        # dokumennya tidak pernah direvisi, jadi skornya tinggi, bukan nol.
        sig = trust.signal_revision([{"revision": "", "filename": "a.pdf"}])
        assert sig.score > 0.5

    def test_absent_and_empty_agree(self) -> None:
        absent = trust.signal_revision([{"filename": "a.pdf"}]).score
        empty = trust.signal_revision([{"revision": "", "filename": "a.pdf"}]).score
        assert absent == empty

    def test_stating_a_revision_scores_full(self) -> None:
        assert trust.signal_revision(
            [{"revision": "A", "filename": "a.pdf"}]
        ).score == 1.0

    def test_detail_reports_the_ratio(self) -> None:
        sig = trust.signal_revision([
            {"revision": "A", "filename": "a.pdf"},
            {"revision": "", "filename": "b.pdf"},
        ])
        assert "1/2" in sig.detail


class TestSignalRelevance:
    @staticmethod
    def _hits(*scores: float) -> list[dict[str, object]]:
        return [{"score": s, "doc_id": f"d{i}"} for i, s in enumerate(scores)]

    def test_zero_hits(self) -> None:
        assert trust.signal_relevance([]).score == 0.0

    def test_is_bounded(self) -> None:
        for hits in (self._hits(1.0), self._hits(40.0), self._hits(400.0)):
            assert 0.0 <= trust.signal_relevance(hits).score <= 1.0

    def test_is_monotonic(self) -> None:
        low = trust.signal_relevance(self._hits(5.0)).score
        high = trust.signal_relevance(self._hits(20.0)).score
        assert high > low

    def test_saturates_rather_than_exceeding_one(self) -> None:
        # s/(s+K) tanpa clamp akan lewat 1.0 pada BM25 yang sangat tinggi,
        # dan badge yang dihitung dari angka > 1 terlihat kuat secara palsu.
        assert trust.signal_relevance(self._hits(1e6)).score <= 1.0

    def test_zero_scores_give_zero(self) -> None:
        assert trust.signal_relevance(self._hits(0.0, 0.0)).score == 0.0

    def test_negative_scores_do_not_produce_a_positive_signal(self) -> None:
        assert trust.signal_relevance(self._hits(-5.0, -1.0)).score == 0.0


class TestSignalCoverage:
    def test_no_hits(self) -> None:
        assert trust.signal_coverage([]).score == 0.0

    def test_more_document_types_raise_coverage(self) -> None:
        one = trust.signal_coverage([
            {"doc_id": "a", "doc_type": "opl"},
        ])
        two = trust.signal_coverage([
            {"doc_id": "a", "doc_type": "opl"},
            {"doc_id": "b", "doc_type": "interlock"},
        ])
        assert two.score > one.score

    def test_more_chunks_of_one_document_do_not_raise_coverage(self) -> None:
        # Dua chunk dari dokumen yang sama bukan dua sumber.
        one = trust.signal_coverage([{"doc_id": "a", "doc_type": "opl"}])
        two = trust.signal_coverage([
            {"doc_id": "a", "doc_type": "opl"},
            {"doc_id": "a", "doc_type": "opl"},
        ])
        assert two.score == one.score


class TestSignalAgreement:
    """Kesepakatan Astronomical diBATAS oleh cakupan tag equipment."""

    @staticmethod
    def _hits(*specs: tuple[str, str]) -> list[dict[str, object]]:
        return [
            {"doc_id": doc_id, "equipment_tag": tag, "doc_type": "opl",
             "filename": f"{doc_id}.pdf", "title": doc_id, "revision": "A",
             "approval_status": "approved", "score": 10.0}
            for doc_id, tag in specs
        ]

    def test_no_hits(self) -> None:
        assert trust.signal_agreement_scope([], "EQ-0001").score == 0.0

    def test_two_documents_same_tag_agree_fully(self) -> None:
        sig = trust.signal_agreement_scope(
            self._hits(("d1", "EQ-0001"), ("d2", "EQ-0001")), "EQ-0001"
        )
        assert sig.score == 1.0

    def test_single_document_scores_partially_not_zero(self) -> None:
        # 0.55, bukan 0. Satu dokumen tidak dikuatkan siapa pun, tapi dokumen
        # approved satu-satunya yang menjawab memang bukti. Menolaknya seluruhnya
        # akan membuat pertanyaan sepesifik "apa revisi datasheet EA-5601?"
        # selalu dijawab DO NOT EXECUTE.
        sig = trust.signal_agreement_scope(self._hits(("d1", "EQ-0001")), "EQ-0001")
        assert sig.score == 0.55
        assert "single document" in sig.detail

    def test_off_tag_documents_cannot_corroborate(self) -> None:
        # Sumber unit lain tidak membuktikan apa pun soal unit yang ditanya.
        sig = trust.signal_agreement_scope(
            self._hits(("d1", "EQ-0001"), ("d2", "EQ-0002")), "EQ-0001"
        )
        assert sig.score < 1.0
        assert "EQ-0002" in sig.detail

    def test_cross_unit_question_needs_one_unit_to_corrobate(self) -> None:
        mixed = trust.signal_agreement_scope(
            self._hits(("d1", "EQ-0001"), ("d2", "EQ-0002")), None
        )
        single_unit = trust.signal_agreement_scope(
            self._hits(("d1", "EQ-0001"), ("d2", "EQ-0001")), None
        )
        assert mixed.score < single_unit.score
        assert mixed.score <= 0.4

    def test_never_claims_agreement_from_other_units(self) -> None:
        # Badge tidak boleh naik hanya karena dokumen unit lain ikut terbawa.
        sig = trust.signal_agreement_scope(
            self._hits(("d1", "EQ-0001"), ("d2", "EQ-0002"), ("d3", "EQ-0003")),
            "EQ-0001",
        )
        assert sig.score <= 0.4


# ---------------------------------------------------------------------------
# detect_safety_critical
# ---------------------------------------------------------------------------


class TestDetectSafetyCritical:
    @pytest.mark.parametrize(
        "question",
        [
            "how do I bypass the interlock on EQ-0001",
            "how do I raise the trip setpoint above 12 mm/s",
            "can I disable the shutdown protection",
            "how do I jump the shutdown on EQ-0002",
        ],
    )
    def test_flags_changing_a_protection(self, question: str) -> None:
        safety, reasons = trust.detect_safety_critical(question, [])
        assert safety is True
        assert reasons

    def test_reading_a_setpoint_is_still_verbatim_only(self) -> None:
        # Bukan tidak sengaja. Membaca batas keselamatan memang aman, tapi
        # memparafrase angka batas yang salah adalah penyebab langsung orang
        # salah tindakan - jadi responsnya harus menampilkan angka apa adanya,
        # bukan ringkasan.
        safety, reasons = trust.detect_safety_critical(
            "what is the trip setpoint for PSLL-0001", registry_approved_hits()
        )
        assert safety is True
        assert any("safety limit value" in r for r in reasons)

    def test_reference_question_about_an_opl_is_not_verbatim(self) -> None:
        # Kalau OPL apa pun membuat respons verbatim, maka setiap pertanyaan
        # retrieval memakai mode verbatim dan penjelasannya hilang artinya.
        opl = [dict(registry_approved_hits()[0], doc_type="opl")]
        safety, _ = trust.detect_safety_critical(
            "what is nitrogen blanketing", opl
        )
        assert safety is False

    def test_opl_with_action_intent_is_verbatim(self) -> None:
        opl = [dict(registry_approved_hits()[0], doc_type="opl")]
        safety, reasons = trust.detect_safety_critical(
            "how do I replace the gland packing on EQ-0001", opl
        )
        assert safety is True
        assert any("action steps" in r for r in reasons)

    def test_interlock_source_is_always_verbatim(self) -> None:
        # Diagram interlock memuat SIL dan cause & effect, jadi nilainya
        # menyangkut keselamatan apa pun pertanyaannya.
        hits = [dict(registry_approved_hits()[0], doc_type="interlock")]
        safety, reasons = trust.detect_safety_critical("what is nitrogen blanketing",
                                                       hits)
        assert safety is True
        assert any("interlock" in r for r in reasons)


# ---------------------------------------------------------------------------
# evaluate: aturan keras
# ---------------------------------------------------------------------------


class TestEvaluateHardRules:
    def test_no_hits_is_never_answerable(self) -> None:
        verdict = trust.evaluate("what is the seal flush plan", [])
        assert verdict.badge == trust.DO_NOT_EXECUTE
        assert any("no source" in r for r in verdict.reasons)

    def test_safety_without_approved_source_is_never_answerable(self) -> None:
        hits = [{
            "doc_id": "d9", "equipment_tag": "EQ-0009", "doc_type": "opl",
            "filename": "OPL-EQ-0009-01.pdf", "revision": "A",
            "approval_status": "unknown", "approved_by": None,
            "is_safety_critical": 1, "score": 30.0,
            "content": "Bypass the interlock by lifting the trip wire.",
        }]
        verdict = trust.evaluate(
            "how do I bypass the interlock on EQ-0009", hits
        )
        assert verdict.badge == trust.DO_NOT_EXECUTE
        assert verdict.verbatim_required is True

    def test_safety_rule_beats_a_high_score_without_approved_sources(self) -> None:
        # Empat dokumen dengan skor relevansi tinggi, tapi tidak satu pun
        # menyatakan status approval. Aturan keras harus menang atas skor.
        hits = []
        for i in range(4):
            hits.append({
                "doc_id": f"d{i}", "equipment_tag": "EQ-0009", "doc_type": "opl",
                "filename": f"OPL-{i}.pdf", "title": f"OPL {i}", "revision": "A",
                "approval_status": "unknown", "approved_by": None,
                "is_safety_critical": 1, "score": 40.0 - i,
                "content": "bypass interlock disable shutdown override",
            })
        verdict = trust.evaluate(
            "how do I bypass the interlock on EQ-0009", hits
        )
        assert verdict.badge == trust.DO_NOT_EXECUTE
        assert verdict.score >= trust.VERIFY_THRESHOLD, (
            "test ini tidak menguji aturan keras kalau skornya sendiri sudah "
            f"rendah; got {verdict.score:.2f}"
        )
        assert any("approved source" in r for r in verdict.reasons)

    def test_safety_with_an_approved_source_is_allowed(self) -> None:
        # Aturan kerasnya adalah "tanpa sumber approved", bukan "kalau
        # safety". Dokumentasi interlock yang sudah disetujui memang boleh
        # dipakai untuk menjawab pertanyaan ini - jawabannya adalah
        # penjelasan mengapa interlock itu ada, bukan cara mematikannya.
        hits = [{
            "doc_id": "d0", "equipment_tag": "EQ-0009", "doc_type": "opl",
            "filename": "OPL-0.pdf", "title": "OPL 0", "revision": "A",
            "approval_status": "approved", "approved_by": "EMP-0001",
            "is_safety_critical": 1, "score": 40.0,
            "content": "the interlock exists to prevent this; do not bypass it",
        }]
        verdict = trust.evaluate(
            "can I bypass the interlock on EQ-0009", hits
        )
        assert verdict.safety_critical is True
        assert verdict.verbatim_required is True

    def test_verdict_is_serialisable(self) -> None:
        payload = trust.evaluate("maintenance history", registry_approved_hits()).to_dict()
        assert payload["badge"] in {trust.TRUSTED, trust.VERIFY, trust.DO_NOT_EXECUTE}
        assert 0.0 <= payload["score"] <= 1.0

    def test_conflicts_are_carried_into_the_verdict(self) -> None:
        marker = [{"doc_id": "d1b", "parameter": "TSHH-0002"}]
        verdict = trust.evaluate(
            "maintenance history", registry_approved_hits(), [], marker
        )
        assert verdict.conflicts == marker

    def test_reasons_are_never_empty(self) -> None:
        verdict = trust.evaluate("maintenance history", registry_approved_hits())
        assert verdict.reasons, "every verdict must explain itself"


# ---------------------------------------------------------------------------
# should_refuse: enam pemeriksaan berurutan
# ---------------------------------------------------------------------------


def refuse(
    question: str,
    *,
    hits: list | None = None,
    tags: list | None = None,
    refs: frozenset | None = None,
    vocabulary=None,
    instruments: frozenset | None = None,
):
    return trust.should_refuse(
        question,
        hits if hits is not None else registry_approved_hits(),
        tags if tags is not None else ["EQ-0001", "EQ-0002", "EQ-0003"],
        refs if refs is not None else frozenset({"OPL-EQ-0001-01"}),
        trust.RELEVANCE_FLOOR,
        vocabulary,
        instruments if instruments is not None else frozenset({"PSLL-0001"}),
    )


class TestShouldRefuse:
    def test_unknown_document_reference(self) -> None:
        refused, reason = refuse("what does OPL-GA-1201A-04 say")
        assert refused is True
        assert "OPL-GA-1201A-04" in reason or "not" in reason.lower()

    def test_known_document_reference_is_not_refused_for_that_reason(self) -> None:
        refused, reason = refuse("what does OPL-EQ-0001-01 say")
        assert refused is False, reason

    def test_unknown_equipment_tag(self) -> None:
        refused, reason = refuse("procedure for P-8802")
        assert refused is True
        assert "P-8802" in reason

    def test_unknown_instrument_tag_is_not_an_equipment_refusal(self) -> None:
        # VSHH-1201 bukan equipment. Menolak sebagai equipment yang tidak
        # dikenal akan salah dan memalukan.
        refused, reason = refuse(
            "what is the trip setpoint for VSHH-9999?",
            instruments=frozenset({"PSLL-0001"}),
        )
        assert "VSHH-9999" not in (reason or ""), reason

    def test_non_knowledge_intent(self) -> None:
        refused, _ = refuse("write me a poem about hexane")
        assert refused is True

    def test_no_hits(self) -> None:
        refused, reason = refuse("maintenance history", hits=[])
        assert refused is True
        assert reason

    def test_low_relevance(self) -> None:
        weak = [dict(registry_approved_hits()[0], score=0.05)]
        refused, reason = refuse("how do I change the gland packing", hits=weak)
        assert refused is True
        assert reason

    def test_good_question_is_not_refused(self) -> None:
        refused, reason = refuse("what is the seal flush plan for EQ-0001")
        assert refused is False, reason

    def test_returns_reason_when_refused(self) -> None:
        for question in ("write me a poem", "procedure for P-8802",
                         "what does OPL-GA-1201A-04 say"):
            refused, reason = refuse(question)
            assert refused is True
            assert reason, f"{question!r} refused without a reason"


class TestRefusalOrder:
    def test_unknown_document_wins_over_unknown_equipment(self) -> None:
        # Dua-duanya salah. Pesan harus menyebut dokumen, karena itu yang
        # benar-benar ingin ditanyakan user, dan karena memakai dokumen unit
        # lain sama sekali tidak akan menjawabnya.
        refused, reason = refuse(
            "what does OPL-P-8802-01 say", tags=["EQ-0001"]
        )
        assert refused is True
        assert "OPL-P-8802-01" in reason

    def test_unknown_equipment_wins_over_no_hits(self) -> None:
        refused, reason = refuse("procedure for P-8802", hits=[])
        assert refused is True
        assert "P-8802" in reason
        assert "source" not in reason.lower() or "not in" in reason.lower()

    def test_unknown_equipment_is_reported_before_non_knowledge_intent(self) -> None:
        # "write me a poem about P-8802" bisa ditolak dengan dua alasan yang
        # sama-sama benar. Urutan yang dipakai: tag yang tidak dikenal
        # dilaporkan lebih dulu.
        #
        # Alasannya disengaja. Kalau user sebenarnya memang bermaksud P-8802,
        # itu informasi yang bisa ditindaklanjuti - datanya yang salah. Kalau
        # dia memang cuma mau puisi, dia akan bertanya sekali lagi dan
        # baru waktu itu jawabannya "saya menjawab dari dokumen". Sebaliknya,
        # kalau urutannya dibalik, user yang salah ketik tag mendapat jawaban
        # yang sama sekali tidak menyangkut inti masalahnya.
        refused, reason = refuse("write me a poem about P-8802", tags=["EQ-0001"])
        assert refused is True
        assert "P-8802" in reason

    def test_non_knowledge_intent_is_reported_when_the_tag_is_known(self) -> None:
        refused, reason = refuse("write me a poem about the seal flush")
        assert refused is True
        assert "P-8802" not in (reason or "")