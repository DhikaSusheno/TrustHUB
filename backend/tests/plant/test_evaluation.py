"""Test untuk `plant/evaluation.py` dan `evaluation_set.json`.

Dua hal diverifikasi di sini, dan keduanya penting secara berbeda.

Yang pertama adalah kontrak file test itu sendiri. Angka akurasi yang
dikutip di deck dibaca dari file ini, jadi file ini adalah klaim. Kalau
seseorang menambah kasus yang isinya dijawab oleh indexesintetis, atau
menghapus kasus yang menyulitkan, angkanya naik tanpa sistemnya membaik.
Test di sini menahan spec tetap jujur: id unik, cukup banyak kasus di
setiap kategori, dan setiap kasus punya ekspektasi yang jelas.

Yang kedua adalah bahwa machinery evaluasinya benar. Sebagian besar test
memakai `run_case` dengan kasus buatan untuk menguji logika pencocokan
secara terisolasi, karena hasil atas 100% terhadap dataset resmi adalah
fakta yang tidak bisa direproduksi di CI (dataset itu tidak ada di sini).
Test yang butuh dataset resmi ditandai dan skip dengan alasan terbaca.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from plant import evaluation, trust

# `conftest` diimpor sebagai modul biasa, bukan `from .conftest`: folder test
# tidak punya __init__.py, jadi impor relatifnya gagal dengan "attempted
# relative import with no known parent package". pytest menyisipkan folder test
# ke sys.path, jadi impor datar inilah yang benar.
from conftest import requires_official_dataset

#: Folder `backend/`. Diperlukan untuk subprocess: pytest menaruh `backend/`
#: di sys.path prosesnya sendiri, tapi subprocess mewarisi environment, bukan
#: sys.path. Tanpa ini `python -m plant.evaluation` hanya jalan kalau
#: PYTHONPATH kebetulan sudah diisi di shell - lulus di satu mesin, gagal di CI.
_BACKEND_DIR = str(Path(__file__).resolve().parents[2])


@pytest.fixture(scope="module")
def spec() -> dict:
    return evaluation.load_set()


@pytest.fixture(scope="module")
def cases(spec: dict) -> list[dict]:
    return spec["cases"]


# ---------------------------------------------------------------------------
# Kontrak file test
# ---------------------------------------------------------------------------


class TestSetFileContract:
    def test_spec_declares_a_version(self, spec):
        # The report quotes this. A missing version would make it impossible to
        # tell which number was measured when.
        assert spec.get("version")

    def test_set_is_not_empty(self, cases):
        assert len(cases) >= 50, (
            f"hanya {len(cases)} kasus. Set yang kecil bisa lulus dengan "
            f"akurasi tinggi karena hanya menguji kasus yang mudah."
        )

    def test_ids_are_unique(self, cases):
        ids = [c["id"] for c in cases]
        duplicates = {i for i in ids if ids.count(i) > 1}
        assert not duplicates, f"id duplikat: {sorted(duplicates)}"

    def test_every_expects_badge_is_a_real_badge_name(self, cases):
        """Ejaan `expects_badge` harus persis salah satu dari tiga badge.

        Ini test yang menjaga koreksi versi 1.2 tetap benar. Versi 1.1
        menulis "VERIFICATION" pada 12 kasus. `_check_badge` memakai
        `BADGE_RANK.get(nama, 0)`, jadi nama yang tidak dikenal dibandingkan
        sebagai 0: `rank(apa pun) >= 0` selalu benar. Dua belas dari 63 kasus
        punya ekspektasi badge yang tidak memeriksa apa pun, dan tidak ada satu
        pun yang gagal - accurasinya tetap 100% sepanjang waktu.

        Test ini tidak bisa menangkap itu dari angka, jadi ia memeriksa
        ejaannya secara langsung.
        """
        for case in cases:
            expected = case.get("expects_badge")
            if expected is None:
                continue
            assert expected in evaluation.BADGE_RANK, (
                f"kasus {case['id']}: expects_badge={expected!r} bukan nama "
                f"badge. Pilihan: {sorted(evaluation.BADGE_RANK)}"
            )

    def test_the_modification_cases_expect_do_not_execute(self, cases):
        """Dua kasus yang meminta mengubah batas keselamatan harus expect DNE.

        Versi 1.1 menetapkan kedua kasus ini ke VERIFY, jadi badge tertinggi
        diberikan ke pertanyaan yang isinya justru meminta menaikkan proteksi.
        Ekspektasinya yang salah, bukan jawabannya.
        """
        by_id = {c["id"]: c for c in cases}
        for cid, question_fragment in (
            ("safety-01", "bypass"),
            ("safety-03", "raise the trip setpoint"),
        ):
            case = by_id[cid]
            assert question_fragment in case["question"], case["question"]
            assert case["expects_badge"] == "DO NOT EXECUTE", (
                f"{cid} meminta perubahan batas keselamatan, jadi badge "
                f"tertingginya dibatasi: {case['expects_badge']!r}"
            )
            # Badge dibatasi, tapi nilai terdokumentasinya tetap harus
            # dikembalikan - teknisi tetap perlu tahu batas yang berlaku.
            assert case.get("answer_contains"), (
                f"{cid} harus tetap assert nilai yang dikembalikan"
            )
            assert case["expects_refused"] is False, (
                f"{cid} tidak boleh menolak: nilai terdokumentasinya ada"
            )

    def test_every_case_has_an_id_and_question(self, cases):
        for case in cases:
            assert case.get("id"), f"kasus tanpa id: {case}"
            assert case.get("question"), f"kasus {case.get('id')} tanpa question"

    def test_every_case_declares_refused_or_not(self, cases):
        # An absent expects_refused is falsy, so a typo would silently turn an
        # answerable case into a refusal case and lower the score for no reason.
        for case in cases:
            assert "expects_refused" in case, (
                f"kasus {case['id']} tidak menulis expects_refused"
            )
            assert isinstance(case["expects_refused"], bool)

    def test_refusal_cases_name_a_reason(self, cases):
        for case in cases:
            if case["expects_refused"]:
                assert case.get("refusal_reason"), (
                    f"kasus {case['id']} menolak tanpa menyebut alasannya"
                )

    def test_refusal_reasons_are_ones_the_checker_knows(self, cases):
        # An unknown reason makes `_check_refusal_reason` pass vacuously, which
        # would let a refusal pass for the wrong reason and score as correct.
        for case in cases:
            reason = case.get("refusal_reason")
            if reason:
                assert reason in evaluation.REFUSAL_MARKERS, (
                    f"kasus {case['id']} memakai alasan '{reason}' yang tidak "
                    f"ada di REFUSAL_MARKERS, jadi ceknya jadi tidak bermakna"
                )

    def test_most_answer_cases_state_what_they_expect(self, cases):
        """Hampir semua kasus jawaban harus menyebut apa yang diharapkan.

        13 dari 36 kasus jawaban hanya memeriksa "tidak ditolak": pertanyaannya
        dijawab dari dokumen apa pun yang cocok, dan badge-nya tidak lebih buruk
        dari EXPECTED_NONE. Itu tetap bukti nyata - sebuah sistem yang menjawab
        pertanyaan yang salah sudah gagal - tapi tidak sedalam kasus yang
        memeriksa isi jawabannya.

        Kasus-kasus itu sengaja dibiarkan apa adanya. Menambah `answer_contains`
        ke sini berarti mengubah angka yang sudah dikunci dan dikutip di deck,
        dan angka itu harus hasil pengukuran, bukan hasil penyesuaian. Yang dijaga
        test ini adalah jumlahnya tidak boleh naik diam-diam: menghapus ekspektasi
        dari kasus yang punya ekspektasi harus menggagalkan test.
        """
        answerable = [c for c in cases if not c["expects_refused"]]
        pinned = [
            c
            for c in answerable
            if any(
                c.get(key)
                for key in (
                    "answer_contains",
                    "expects_equipment_tag",
                    "expects_kind",
                    "expects_source_doc_type",
                )
            )
        ]
        assert len(pinned) >= len(answerable) - 13, (
            f"hanya {len(pinned)}/{len(answerable)} kasus jawaban yang "
            f"menyatakan ekspektasi; angka 13 adalah batas bawah yang disepakati"
        )

    def test_the_weak_cases_are_the_documented_ones(self, cases):
        """Daftar kasus yang hanya memeriksa "tidak ditolak" harus tetap sama.

        Kalau daftar ini berubah, angka 13 di docstring test sebelumnya juga
        berubah dan catatan di modul ini harus ikut diperbarui.
        """
        weak = sorted(
            c["id"]
            for c in cases
            if not c["expects_refused"]
            and not any(
                c.get(key)
                for key in (
                    "answer_contains",
                    "expects_equipment_tag",
                    "expects_kind",
                    "expects_source_doc_type",
                )
            )
        )
        assert weak == [
            "doc-09", "doc-10", "doc-11", "doc-12", "doc-13", "doc-14",
            "doc-15", "maint-08", "maint-09", "maint-10", "maint-11",
            "safety-04", "safety-05",
        ], (
            f"kasus jawaban tanpa ekspektasi berubah menjadi: {weak}. "
            f"Perbarui juga catatan di test_most_answer_cases_state_what_they_expect."
        )

    def test_answer_contains_is_a_list_of_strings(self, cases):
        for case in cases:
            needles = case.get("answer_contains")
            if needles is not None:
                assert isinstance(needles, list), case["id"]
                assert all(isinstance(n, str) for n in needles), case["id"]

    def test_both_refusals_and_answers_are_represented(self, cases):
        # Refusal-only set would score 100% while the hub answers everything.
        # Answer-only set would score 100% while the hub refuses everything.
        refused = sum(1 for c in cases if c["expects_refused"])
        assert 0 < refused < len(cases), (
            f"{refused}/{len(cases)} kasus penolakan. Yang diukur harus dua arah."
        )

    def test_phantom_references_are_present(self, cases):
        # Set harus memuat pertanyaan yang WAJIB ditolak: unit yang tidak ada,
        # dokumen yang tidak ada. Kalau set ini hanya berisi pertanyaan yang
        # wajar, guardrail tidak pernah diuji. Tiga bentuk yang diuji:
        # dokumen OPL yang hilang, tag dua huruf, dan tag satu huruf - bentuk
        # terakhir hanya tertangkap kalau EQUIPMENT_TAG_SHAPE mengizinkan satu
        # huruf sebelum tanda hubung.
        questions = " ".join(c["question"].lower() for c in cases)
        for marker in ("opl-ga-1201a-04", "zx-4455", "p-8802"):
            assert marker in questions, (
                f"tidak ada kasus yang memakai referensi hantu {marker!r}"
            )

    def test_every_refusal_case_is_a_phantom_or_out_of_scope(self, cases):
        # Menolak pertanyaan yang sebenarnya bisa dijawab akan menaikkan angka
        # penolakan tanpa membuat guardrail jadi lebih baik. Setiap kasus
        # penolakan harus menyebut sesuatu yang benar-benar tidak ada di
        # dataset.
        refusals = [c for c in cases if c["expects_refused"]]
        missing_doc = [
            c for c in refusals if c.get("refusal_reason") == "unknown document reference"
        ]
        unknown_tag = [
            c for c in refusals if c.get("refusal_reason") == "unknown equipment tag"
        ]
        assert len(missing_doc) >= 2, (
            "harus ada kasus dokumen yang hilang - itu satu-satunya cara "
            "membuktikan guardrail membaca nomor dokumen, bukan sekadar "
            "menolak pertanyaan yang tak jelas"
        )
        assert len(unknown_tag) >= 3
        # Sisanya adalah pertanyaan di luar lingkup, yang memang tidak punya
        # jawaban di dokumen apa pun.
        for case in unknown_tag:
            assert any(
                tag in case["question"].upper()
                for tag in ("P-8802", "P-9901", "ZX-4455")
            ), f"{case['id']} menolak tag yang bukan phantom"

    def test_categories_cover_more_than_one_kind(self, spec, cases):
        # One category means one kind of question, which means the score says
        # nothing about the system.
        assert len({c.get("category", "uncategorised") for c in cases}) >= 5

    def test_every_category_has_enough_cases_to_mean_something(self, spec, cases):
        """Tidak ada kategori yang hanya satu kasusnya.

        `missing_document` memang cuma 2 - dan itu memang jujur: hanya ada satu
        dokumen yang hilang di dataset (OPL-GA-1201A-04), jadi menambah kasus
        di kategori itu berarti mengarang dokumen yang tidak hilang. Dua kasus
        sudah menguji jalur itu dari dua arah: menanyakan dokumen itu langsung,
        lalu menanyakan isinya.
        """
        counts: dict[str, int] = {}
        for case in cases:
            key = case.get("category", "uncategorised")
            counts[key] = counts.get(key, 0) + 1
        thin = {k: v for k, v in counts.items() if v < 2}
        assert not thin, f"kategori dengan satu kasus tidak membuktikan apa pun: {thin}"

    def test_missing_document_cases_all_name_the_one_actually_missing_doc(self, cases):
        """Semua kasus `missing_document` harus menunjuk dokumen yang sama.

        Hanya OPL-GA-1201A-04 yang hilang dari dataset. Kalau sebuah kasus
        mention dokumen yang sebenarnya ADA, itu bukan kasus penolakan - itu
        kasus yang akan gagal, atau lebih buruk, lulus karena alasan lain.
        """
        missing = [c for c in cases if c.get("category") == "missing_document"]
        for case in missing:
            assert "OPL-GA-1201A-04" in case["question"].upper(), (
                f"{case['id']} categorized as missing_document but does not "
                f"name the one document that is actually missing"
            )

    def test_the_two_missing_document_cases_ask_different_questions(self, cases):
        """Dua kasus harus menguji dua jalur, bukan mengulang pertanyaan sama.

        Satu menanyakan dokumennya ("tell me about OPL-GA-1201A-04"), satu
        menanyakan isinya. Yang kedua lebih penting: kalau guardrail hanya
        mengenali pola "tell me about X" dan gagal pada pertanyaan isi, kasus
        kedua menangkapnya.
        """
        missing = [c for c in cases if c.get("category") == "missing_document"]
        assert len(missing) == 2
        assert len({c["question"].lower() for c in missing}) == 2
        questions = " ".join(c["question"].lower() for c in missing)
        assert "lesson say" in questions or "what does" in questions, (
            "satu dari dua kasus harus menanyakan isi dokumen, bukan hanya "
            "nama dokumennya"
        )

    def test_file_is_valid_utf8_json(self):
        # read_text with an explicit encoding. If the encoding is left to the
        # platform this passes on Windows and fails on the CI runner.
        raw = evaluation.SET_PATH.read_text(encoding="utf-8")
        json.loads(raw)


# ---------------------------------------------------------------------------
# Badge ordering
# ---------------------------------------------------------------------------


class TestBadgeRank:
    def test_rank_is_strictly_ordered(self):
        assert (
            evaluation.BADGE_RANK[trust.TRUSTED]
            > evaluation.BADGE_RANK[trust.VERIFY]
            > evaluation.BADGE_RANK[trust.DO_NOT_EXECUTE]
        )

    def test_all_three_badges_are_ranked(self):
        assert len(evaluation.BADGE_RANK) == 3

    def test_no_expected_badge_passes(self):
        # A case that does not constrain the badge must not constrain it.
        assert evaluation._check_badge(trust.DO_NOT_EXECUTE, None) is True

    def test_exact_match_passes(self):
        assert evaluation._check_badge(trust.TRUSTED, trust.TRUSTED) is True

    def test_stronger_badge_than_expected_passes(self):
        # Caution is never wrong: TRUSTED when VERIFY was expected is a better
        # outcome, and the test must not punish it.
        assert evaluation._check_badge(trust.TRUSTED, trust.VERIFY) is True
        assert evaluation._check_badge(trust.VERIFY, trust.DO_NOT_EXECUTE) is True

    def test_weaker_badge_fails(self):
        # This is the direction that matters. A hub that marks an approved,
        # corroborated, multi-source answer DO NOT EXECUTE is broken, and the
        # test set has to be able to catch that.
        assert evaluation._check_badge(trust.DO_NOT_EXECUTE, trust.TRUSTED) is False
        assert evaluation._check_badge(trust.VERIFY, trust.TRUSTED) is False

    def test_unknown_badge_scores_zero(self):
        # An unrecognised badge must not pass as TRUSTED, which would happen if
        # the lookup defaulted to the maximum.
        assert evaluation.BADGE_RANK.get("SOMETHING_ELSE", 0) == 0
        assert evaluation._check_badge("SOMETHING_ELSE", trust.TRUSTED) is False


class TestLoadSetRejectsMisspelledBadges:
    """`load_set` harus menolak `expects_badge` yang bukan nama badge.

    `_check_badge` sendiri tidak bisa melaporkan hal ini: nama yang tidak
    dikenal dibandingkan sebagai 0, jadi `rank(apa pun) >= 0` selalu benar.
    Itulah persis yang terjadi pada 12 kasus "VERIFICATION" di v1.1 -
    assertion-nya hampa dan run tetap melaporkan 100%. Menolak file saat load
    time adalah satu-satunya tempat kesalahan itu terlihat.
    """

    @staticmethod
    def _spec_with_badge(tmp_path, badge, case_id="x-01"):
        spec = {
            "version": "test",
            "cases": [
                {
                    "id": case_id,
                    "question": "What is the trip setpoint for VSHH-1201?",
                    "expects_refused": False,
                    "expects_badge": badge,
                }
            ],
        }
        path = tmp_path / "set.json"
        path.write_text(json.dumps(spec), encoding="utf-8")
        return path

    @pytest.mark.parametrize("badge", sorted(evaluation.BADGE_RANK))
    def test_a_real_badge_name_is_accepted(self, tmp_path, badge):
        path = self._spec_with_badge(tmp_path, badge)
        assert evaluation.load_set(path)["cases"]

    def test_the_v11_typo_is_rejected(self, tmp_path):
        # The exact string that shipped in v1.1 on twelve cases.
        path = self._spec_with_badge(tmp_path, "VERIFICATION")
        with pytest.raises(ValueError, match="VERIFICATION"):
            evaluation.load_set(path)

    def test_the_error_names_the_case(self, tmp_path):
        # An error that does not say which case is one nobody can act on.
        path = self._spec_with_badge(tmp_path, "veriy", case_id="scope-42")
        with pytest.raises(ValueError, match="scope-42"):
            evaluation.load_set(path)

    def test_no_badge_expectation_is_still_accepted(self, tmp_path):
        spec = {
            "version": "test",
            "cases": [
                {
                    "id": "x-02",
                    "question": "write me a poem about hexane",
                    "expects_refused": True,
                }
            ],
        }
        path = tmp_path / "set.json"
        path.write_text(json.dumps(spec), encoding="utf-8")
        assert evaluation.load_set(path)["cases"]

    def test_the_shipped_set_passes_validation(self):
        # Guards against the validator rejecting the file it ships with.
        assert evaluation.load_set()["cases"]


# ---------------------------------------------------------------------------
# Refusal-reason and substring matching
# ---------------------------------------------------------------------------


class TestRefusalReasonCheck:
    def test_absent_expectation_passes(self):
        assert evaluation._check_refusal_reason("anything at all", None) is True

    def test_unknown_reason_passes(self):
        # Unreachable through load_set(), which is checked separately. Kept
        # permissive so that adding a reason to the JSON before adding it to
        # REFUSAL_MARKERS fails loudly in TestSetFileContract instead of
        # silently scoring the wrong refusals as correct.
        assert evaluation._check_refusal_reason("whatever", "some new reason") is True

    def test_matching_marker_passes(self):
        answer = "Document OPL-GA-1201A-04 does not exist in this dataset."
        assert evaluation._check_refusal_reason(answer, "unknown document reference")

    def test_any_one_marker_is_enough(self):
        answer = "There is no document that covers this question."
        assert evaluation._check_refusal_reason(answer, "unknown document reference")

    def test_wrong_reason_fails(self):
        # Refused, but for the wrong reason. Counting this as correct would let
        # the guardrail regress from "checks the tag" to "refuses everything"
        # without the score moving.
        answer = "That equipment tag is not part of this dataset."
        assert not evaluation._check_refusal_reason(answer, "unknown document reference")

    def test_matching_is_case_insensitive(self):
        assert evaluation._check_refusal_reason(
            "THERE IS NO DOCUMENT HERE", "unknown document reference"
        )


class TestContainsCheck:
    def test_absent_needles_pass(self):
        assert evaluation._check_contains("anything", None) == []

    def test_all_present_returns_empty(self):
        assert evaluation._check_contains("value is 95 degC", ["95 degc"]) == []

    def test_missing_needle_is_reported(self):
        assert evaluation._check_contains("value is 95 degC", ["7.1 mm/s"]) == ["7.1 mm/s"]

    def test_every_missing_needle_is_reported(self):
        missing = evaluation._check_contains("value is 95 degC", ["zzz", "qqq"])
        assert missing == ["zzz", "qqq"]

    def test_single_letter_needle_matches_inside_a_word(self):
        # Not a bug, but a real property of substring matching that a future
        # author will trip over: "a" is a substring of "value", so it counts as
        # present. Asserted so the behaviour is chosen rather than discovered.
        assert evaluation._check_contains("value is 95 degC", ["a"]) == []

    def test_matching_is_case_insensitive(self):
        assert evaluation._check_contains("TSHH-1201 > 95 degC", ["tshh-1201"]) == []

    def test_empty_needle_always_matches(self):
        # Would otherwise report every answer as missing a blank string.
        assert evaluation._check_contains("anything", [""]) == []

    def test_none_answer_does_not_raise(self):
        # run_case coerces answer to "" before calling, so this documents that
        # the coercion is load-bearing.
        assert evaluation._check_contains("", ["95"]) == ["95"]


# ---------------------------------------------------------------------------
# run_case, against the synthetic index
# ---------------------------------------------------------------------------


@pytest.fixture
def small_index(synthetic_index: sqlite3.Connection) -> sqlite3.Connection:
    """Indeks sintetis, dipin_alias agar nama fixture tidak menyesatkan.

    Dipakai oleh test `run_case`, yang butuh indeks yang benar-benar bisa
    menjawab, bukan indeks kosong. `EQ-0001` punya set point PSLL-0001 = 0.5
    barg di tiga dokumen, jadi jawaban parameternya harus terverifikasi dan
    ditandai `verbatim`.
    """
    return synthetic_index


class TestRunCasePassesAndFails:
    def test_passing_answer_case(self, small_index):
        result = evaluation.run_case(
            small_index,
            {
                "id": "t1", "question": "What is the PSLL-0001 trip setpoint?",
                "expects_refused": False, "answer_contains": ["0.5"],
            },
        )
        assert result["passed"], result["failures"]

    def test_tag_is_not_guessed_when_the_question_omits_it(self, small_index):
        """Unit yang tidak disebut di pertanyaan tidak boleh ditebak.

        Pertanyaan "apa set point PSLL-0001?" tidak menyebut unit, jadi
        `equipment_tag` harus None meski indeks hanya punya satu unit dengan
        tag itu. Menebak di sini berarti badge dan tabel equipment menampilkan
        unit yang tidak disebut dalam pertanyaan - dan kalau nanti indeks
        punya dua unit dengan tag serupa, tebakannya jadi salah tanpa terlihat.

        Perhatikan konsekuensinya: badge jadi lebih rendah. Itu memang pilihan
        yang benar. Menjawab dengan sumber yang benar tetapi mengaitkannya ke
        unit yang tidak disebut lebih berbahaya daripada menjawab dengan
        kehati-hatian.
        """
        result = evaluation.run_case(
            small_index,
            {
                "id": "t1b", "question": "What is the PSLL-0001 trip setpoint?",
                "expects_refused": False,
            },
        )
        assert result["equipment_tag"] is None
        assert not result["actual_refused"]

    def test_tag_is_resolved_when_the_question_names_the_unit(self, small_index):
        for question in (
            "What is the PSLL-0001 trip setpoint for EQ-0001?",
            "What is the PSLL-0001 trip setpoint on the sample feed pump?",
        ):
            result = evaluation.run_case(
                small_index, {"id": "t1c", "question": question,
                              "expects_refused": False},
            )
            assert result["equipment_tag"] == "EQ-0001", question
            assert result["passed"], result["failures"]

    def test_result_reports_the_id_and_category(self, small_index):
        result = evaluation.run_case(
            small_index,
            {"id": "t2", "question": "PSLL-0001 setpoint?", "expects_refused": False,
             "category": "trip setpoint"},
        )
        assert result["id"] == "t2"
        assert result["category"] == "trip setpoint"

    def test_uncategorised_case_gets_a_default(self, small_index):
        result = evaluation.run_case(
            small_index, {"id": "t3", "question": "PSLL-0001?", "expects_refused": False}
        )
        assert result["category"] == "uncategorised"

    def test_failing_answer_case_lists_what_was_missing(self, small_index):
        result = evaluation.run_case(
            small_index,
            {"id": "t4", "question": "PSLL-0001 setpoint?",
             "expects_refused": False, "answer_contains": ["9999 degC"]},
        )
        assert not result["passed"]
        assert any("9999 degC" in f for f in result["failures"])

    def test_wrong_tag_is_a_failure(self, small_index):
        result = evaluation.run_case(
            small_index,
            {"id": "t5", "question": "PSLL-0001 setpoint?",
             "expects_refused": False, "expects_equipment_tag": "EQ-9999"},
        )
        assert not result["passed"]
        assert any("EQ-9999" in f for f in result["failures"])

    def test_wrong_kind_is_a_failure(self, small_index):
        result = evaluation.run_case(
            small_index,
            {"id": "t6", "question": "PSLL-0001 setpoint?",
             "expects_refused": False, "expects_kind": "procedure"},
        )
        assert not result["passed"]
        assert any("kind" in f for f in result["failures"])

    def test_missing_expected_doc_type_is_a_failure(self, small_index):
        result = evaluation.run_case(
            small_index,
            {"id": "t7", "question": "PSLL-0001 setpoint?",
             "expects_refused": False, "expects_source_doc_type": "datasheet"},
        )
        assert not result["passed"]
        assert any("datasheet" in f for f in result["failures"])

    def test_wrong_verbatim_flag_is_a_failure(self, small_index):
        result = evaluation.run_case(
            small_index,
            {"id": "t8", "question": "PSLL-0001 setpoint?",
             "expects_refused": False, "expects_verbatim": True},
        )
        assert not result["passed"]

    def test_correct_verbatim_flag_passes(self, small_index):
        result = evaluation.run_case(
            small_index,
            {"id": "t9", "question": "PSLL-0001 setpoint?",
             "expects_refused": False, "expects_verbatim": False},
        )
        assert result["passed"], result["failures"]

    def test_a_refused_answer_case_fails(self, small_index):
        # The question is answerable here, so refusing it is a failure and not
        # an acceptable cautious outcome.
        result = evaluation.run_case(
            small_index,
            {"id": "t10", "question": "What is the PSLL-0001 trip setpoint for EQ-0001?",
             "expects_refused": False},
        )
        if result["actual_refused"]:
            assert not result["passed"]
            assert any("refused an in-scope question" in f for f in result["failures"])


class TestRunCaseOnRefusals:
    def test_correct_refusal_passes(self, small_index):
        result = evaluation.run_case(
            small_index,
            {"id": "r1", "question": "What is the setpoint for PSLL-9999 on ZX-9999?",
             "expects_refused": True, "refusal_reason": "unknown equipment tag"},
        )
        assert result["actual_refused"]
        assert result["passed"], result["failures"]

    def test_answered_when_it_should_have_refused_fails(self, small_index):
        result = evaluation.run_case(
            small_index,
            {"id": "r2", "question": "What is the PSLL-0001 setpoint?",
             "expects_refused": True, "refusal_reason": "unknown equipment tag"},
        )
        assert not result["passed"]
        assert any("had to be refused" in f for f in result["failures"])

    def test_refusal_for_the_wrong_reason_fails(self, small_index):
        result = evaluation.run_case(
            small_index,
            {"id": "r3", "question": "Tell me about the history of the banana trade",
             "expects_refused": True, "refusal_reason": "unknown equipment tag"},
        )
        if result["actual_refused"]:
            assert not result["passed"]
            assert any("not for the expected reason" in f for f in result["failures"])

    def test_refusal_must_carry_the_do_not_execute_badge(self, small_index):
        # A refusal with a TRUSTED badge is contradictory on its face: the badge
        # says the source is approved and corroborated.
        result = evaluation.run_case(
            small_index,
            {"id": "r4", "question": "Setpoint for PSLL-9999 on ZX-9999?",
             "expects_refused": True, "refusal_reason": "unknown equipment tag"},
        )
        if result["actual_refused"]:
            assert result["actual_badge"] == trust.DO_NOT_EXECUTE

    def test_refusal_reason_is_not_checked_against_answer_contains(self, small_index):
        # A refusal case with answer_contains would be contradictory. The
        # contains branch must not run for refusals, or the case could never
        # pass.
        result = evaluation.run_case(
            small_index,
            {"id": "r5", "question": "Setpoint for PSLL-9999 on ZX-9999?",
             "expects_refused": True, "refusal_reason": "unknown equipment tag",
             "answer_contains": ["this should never be checked"]},
        )
        assert result["passed"], result["failures"]


class TestRunCaseResultShape:
    def test_every_field_is_present_and_serialisable(self, small_index):
        result = evaluation.run_case(
            small_index,
            {"id": "s1", "question": "PSLL-0001 setpoint?", "expects_refused": False},
        )
        for key in (
            "id", "category", "question", "expected_refused", "actual_refused",
            "expected_badge", "actual_badge", "trust_score", "kind",
            "equipment_tag", "source_count", "source_doc_types", "verbatim",
            "passed", "failures", "answer",
        ):
            assert key in result, f"kunci {key} hilang dari hasil"

    def test_trust_score_is_rounded_to_three_places(self, small_index):
        # The report is read by humans and pasted into a deck. A 17-digit float
        # is unreadable and invites transcription error.
        result = evaluation.run_case(
            small_index,
            {"id": "s2", "question": "PSLL-0001 setpoint?", "expects_refused": False},
        )
        score = result["trust_score"]
        assert isinstance(score, float)
        assert round(score, 3) == score

    def test_source_doc_types_are_deduplicated_and_sorted(self, small_index):
        result = evaluation.run_case(
            small_index,
            {"id": "s3", "question": "PSLL-0001 setpoint?", "expects_refused": False},
        )
        types = result["source_doc_types"]
        assert types == sorted(set(types))

    def test_passing_case_has_no_failures(self, small_index):
        result = evaluation.run_case(
            small_index,
            {"id": "s4", "question": "PSLL-0001 trip setpoint for EQ-0001?",
             "expects_refused": False, "answer_contains": ["0.5"]},
        )
        assert result["passed"]
        assert result["failures"] == []


# ---------------------------------------------------------------------------
# evaluate()
# ---------------------------------------------------------------------------


class TestEvaluateOnSyntheticIndex:
    """`evaluate()` against an index that does NOT satisfy the locked set.

    The synthetic index has none of the real tags, so nearly every case refuses
    and the score is low. That is the point: it proves the score is computed
    from the index rather than hard-coded. A test asserting 100% here would be
    asserting the exact thing this module must not do.
    """

    def test_report_has_the_documented_keys(self, synthetic_index):
        report = evaluation.evaluate(synthetic_index)
        for key in (
            "spec_version", "total", "passed", "accuracy_pct", "refusal",
            "answer", "by_category", "elapsed_seconds", "results",
        ):
            assert key in report, f"kunci {key} hilang dari report"

    def test_total_matches_the_set_size(self, synthetic_index, cases):
        assert evaluation.evaluate(synthetic_index)["total"] == len(cases)

    def test_passed_never_exceeds_total(self, synthetic_index):
        report = evaluation.evaluate(synthetic_index)
        assert 0 <= report["passed"] <= report["total"]

    def test_accuracy_is_derived_not_stated(self, synthetic_index):
        report = evaluation.evaluate(synthetic_index)
        expected = round(100.0 * report["passed"] / report["total"], 1)
        assert report["accuracy_pct"] == expected

    def test_refusal_and_answer_buckets_partition_the_set(self, synthetic_index, cases):
        # Every case is in exactly one bucket. If they did not sum to the total,
        # the two numbers the deck quotes would not add up to the accuracy.
        report = evaluation.evaluate(synthetic_index)
        assert report["refusal"]["expected"] + report["answer"]["expected"] == (
            report["total"]
        )
        assert report["refusal"]["expected"] == sum(
            1 for c in cases if c["expects_refused"]
        )

    def test_by_category_sums_to_total(self, synthetic_index):
        report = evaluation.evaluate(synthetic_index)
        assert sum(b["total"] for b in report["by_category"].values()) == report["total"]

    def test_by_category_passed_never_exceeds_total(self, synthetic_index):
        for bucket in evaluation.evaluate(synthetic_index)["by_category"].values():
            assert bucket["passed"] <= bucket["total"]

    def test_results_length_matches_total(self, synthetic_index):
        report = evaluation.evaluate(synthetic_index)
        assert len(report["results"]) == report["total"]

    def test_refusal_accuracy_is_reported_separately(self, synthetic_index):
        # Reported apart from overall accuracy because a hub that answers
        # everything scores 100% overall and is useless in a plant. Collapsing
        # them into one number would hide the property that matters most.
        report = evaluation.evaluate(synthetic_index)
        assert set(report["refusal"]) == {"expected", "correct", "pct"}

    def test_empty_index_scores_zero_on_the_phantom_cases(
        self, empty_index: sqlite3.Connection
    ):
        report = evaluation.evaluate(empty_index)
        assert report["refusal"]["pct"] > 0.0, (
            "dengan indeks kosong, pertanyaan tentang unit yang tidak dikenal "
            "seharusnya ditolak"
        )

    def test_elapsed_is_measured_and_positive(self, synthetic_index):
        report = evaluation.evaluate(synthetic_index)
        assert report["elapsed_seconds"] > 0


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


class TestMain:
    """CLI-nya sendiri.

    `python -m plant.evaluation` adalah perintah yang disebut di deck, jadi
    harus benar-benar jalan. Yang diuji di sini perilakunya, bukan hanya
    return code.
    """

    def _run_cli(self, args, **kwargs):
        import os
        import subprocess
        import sys

        # PYTHONPATH di sini, bukan diwarisi dari pytest. pytest membuat
        # `plant` bisa diimpor di dalam proses test lewat sys.path, tapi itu
        # tidak diwarisi ke subprocess. Tanpa baris ini test ini lulus di
        # mesin yang PYTHONPATH-nya sudah diisi dan gagal di CI.
        env = dict(os.environ)
        env["PYTHONPATH"] = _BACKEND_DIR
        return subprocess.run(
            [sys.executable, "-m", "plant.evaluation", *args],
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            **kwargs,
        )

    def test_help_exits_zero(self):
        result = self._run_cli(["--help"])
        assert result.returncode == 0, result.stderr

    def test_help_documents_every_flag(self):
        # Kalau ada flag yang tidak muncul di help, orang yang membacanya akan
        # menyimpulkan flag itu tidak ada.
        result = self._run_cli(["--help"])
        for flag in ("--json", "--verbose", "--fail-under", "--out"):
            assert flag in result.stdout, f"{flag} tidak muncul di --help"

    def test_help_works_with_a_minimal_environment(self):
        # --help adalah cara orang memastikan perintahnya ada sebelum menyiapkan
        # apa pun. Kalau butuh environment penuh, `python -m plant.evaluation
        # --help` saja sudah gagal untuk pembaca yang baru datang.
        #
        # PYTHONPATH harus tetap menunjuk folder backend, karena `plant` hanya
        # bisa diimpor dari sana. Yang diuji: tidak ada variabel lain yang
        # dibutuhkan, terutama token API dan path database.
        import os
        import subprocess
        import sys

        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": _BACKEND_DIR,
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
            # pathlib.Path.home() needs these on Windows; several imports in
            # the dependency chain resolve a home directory at import time.
            "USERPROFILE": os.environ.get("USERPROFILE", ""),
            "HOMEDRIVE": os.environ.get("HOMEDRIVE", ""),
            "HOMEPATH": os.environ.get("HOMEPATH", ""),
        }
        result = subprocess.run(
            [sys.executable, "-m", "plant.evaluation", "--help"],
            capture_output=True, text=True, timeout=300, env=env,
        )
        assert result.returncode == 0, result.stderr

    def _cli_env(self, tmp_path, **extra):
        """Environment minimum yang cukup untuk menjalankan CLI.

        `TRUSTHUB_DATASET_ROOT` adalah nama yang dibaca
        `dataset.find_dataset_root`, bukan `TRUSTHUB_PLANT_DATASET_ROOT` -
        nama kedua hanya dipakai untuk path database. Salah nama di sini
        berarti dataset sungguhan di mesin ini tetap ditemukan, dan test
        yang dimaksudnya menguji jalur yang salah.

        `USERPROFILE`/`HOMEDRIVE`/`HOMEPATH` ikut dipasang karena
        `pathlib.Path.home()` membacanya di Windows, dan beberapa import
        mencari direktori rumah saat import - tanpa itu interpreter gagal
        sebelum `main()` dijalankan sama sekali.
        """
        import os

        env = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
            "PYTHONPATH": _BACKEND_DIR,
            "USERPROFILE": os.environ.get("USERPROFILE", ""),
            "HOMEDRIVE": os.environ.get("HOMEDRIVE", ""),
            "HOMEPATH": os.environ.get("HOMEPATH", ""),
        }
        env.update(extra)
        return env

    def test_missing_dataset_exits_two_not_zero(self, tmp_path):
        """Exit 2 saat dataset tidak ditemukan.

        Bukan 0. `main()` mengembalikan 2 di sini, dan tidak boleh berubah
        jadi 0 karena "tidak ada yang gagal" - dataset yang hilang berarti
        test set tidak dijalankan sama sekali, yang berbeda jauh dari lulus.
        """
        import subprocess
        import sys

        env = self._cli_env(
            tmp_path,
            # Path yang memang tidak ada, jadi find_dataset_root() gagal
            # walaupun ada dataset sungguhan di Downloads mesin ini.
            TRUSTHUB_DATASET_ROOT=str(tmp_path / "no-such-dataset"),
            TRUSTHUB_PLANT_DB_PATH=str(tmp_path / "unused.db"),
        )
        result = subprocess.run(
            [sys.executable, "-m", "plant.evaluation", "--json"],
            capture_output=True, text=True, timeout=300, env=env,
        )
        assert result.returncode == 2, (
            f"harus keluar dengan 2, bukan {result.returncode}. "
            f"stderr={result.stderr[:300]}"
        )
        # Pesan harus menyebut dataset secara spesifik. Exit 2 yang sama juga
        # dipakai untuk "index kosong", jadi kalau test ini tidak memeriksa
        # pesannya, ia bisa lulus karena alasan yang salah - seperti yang
        # terjadi pada versi pertama test ini.
        assert "dataset" in result.stderr.lower(), result.stderr[:300]

    def test_empty_index_exits_two(self, tmp_path):
        """Exit 2 juga untuk index yang ada tapi kosong.

        Kasus berbeda dari dataset hilang: datasetnya ada, tapi database belum
        pernah di-build. Tanpa test ini, `return 2` di cabang kedua bisa
        dihapus dan tidak ada yang sadar, karena test di atas sudah hijau dari
        cabang pertama.
        """
        import subprocess
        import sys

        from plant import extract as extract_mod

        dataset = tmp_path / "dataset"
        dataset.mkdir()
        for tag in extract_mod.EQUIPMENT_TAGS:
            (dataset / f"Equipment Datasheet - {tag}.pdf").write_bytes(b"%PDF-1.4")

        env = self._cli_env(
            tmp_path,
            TRUSTHUB_DATASET_ROOT=str(dataset),
            TRUSTHUB_PLANT_DB_PATH=str(tmp_path / "empty-index.db"),
        )
        result = subprocess.run(
            [sys.executable, "-m", "plant.evaluation", "--json"],
            capture_output=True, text=True, timeout=300, env=env,
        )
        assert result.returncode == 2, result.stderr[:300]
        # Pesan harus menyebut index, bukan dataset - kalau tidak, kedua
        # cabang hanya bisa dibedakan oleh isi pesan, dan tes ini kembali
        # bercampur.
        assert "index" in result.stderr.lower(), result.stderr[:300]
        assert "fetch_dataset" in result.stderr, result.stderr[:300]


# ---------------------------------------------------------------------------
# Against the official dataset
# ---------------------------------------------------------------------------


@requires_official_dataset
class TestAgainstOfficialDataset:
    """The headline number, reproducible only where the dataset exists."""

    def test_every_case_passes(self, official_dataset):
        report = evaluation.evaluate(official_dataset)
        failed = [r for r in report["results"] if not r["passed"]]
        assert not failed, (
            f"{len(failed)}/{report['total']} kasus gagal:\n"
            + "\n".join(f"  {r['id']}: {r['failures']}" for r in failed[:10])
        )

    def test_accuracy_is_100(self, official_dataset):
        assert evaluation.evaluate(official_dataset)["accuracy_pct"] == 100.0

    def test_every_refusal_is_refused(self, official_dataset):
        report = evaluation.evaluate(official_dataset)
        assert report["refusal"]["correct"] == report["refusal"]["expected"]

    def test_every_answer_is_answered(self, official_dataset):
        report = evaluation.evaluate(official_dataset)
        assert report["answer"]["correct"] == report["answer"]["expected"]

    def test_set_size_is_the_documented_number(self, official_dataset, cases):
        # The deck says 63 cases. If this fails, the deck and the set have
        # diverged and one of them is wrong.
        assert len(cases) == 63

    def test_refusal_and_answer_counts_are_the_documented_numbers(
        self, official_dataset
    ):
        report = evaluation.evaluate(official_dataset)
        assert report["refusal"]["expected"] == 27
        assert report["answer"]["expected"] == 36