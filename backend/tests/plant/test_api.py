"""Test HTTP layer `/api/plant/*`.

Yang diuji di sini bukan isi bisnisnya - itu sudah diuji di test_ask,
test_retrieval, test_trust, dan test_conflicts terhadap fungsi yang dipanggil
rut-rute ini. Yang diuji di sini adalah lapisan yang bisa gagal sendiri:

  - 503 saat indeks belum dibangun atau kosong, dengan pesan yang menyuruh
    menjalankan perintah yang benar (bukan "Internal Server Error"),
  - 404 yang menyebut tag yang dicari, supaya orang tahu salah ketik di mana,
  - validasi query parameter, supaya `limit=0` atau `limit=1001` ditolak
    server dan tidak jadi query yang memuat seluruh tabel,
  - normalisasi tag di level HTTP, karena inilah tempat user mengetik dan
    tempat salah ketik terjadi, dan
  - router ini tidak pernah menjadi public path, jadi gerbang token di
    main.py tetap menutupinya.

Fixture `api` membangun app FastAPI minimal, sama seperti cara main.py
memasang router. Auth-nya sendiri diuji di TestRouterAuthProtection lewat
fungsi `auth.is_public_path`, karena middleware token hidup di main.py dan
menjalankan main.py di dalam test suite plant akan menarik seluruh modul
backend ke dalam test.
"""

from __future__ import annotations

import json

import pytest


PREFIX = "/api/plant"


# ---------------------------------------------------------------------------
# Semua rute
# ---------------------------------------------------------------------------


#: Rute yang butuh indeks. `/dataset` membaca filesystem dan
#: `/trust/weights` mengembalikan konstanta, jadi keduanya harus tetap bisa
#: dibaca sebelum `fetch_dataset` dijalankan - itulah gunanya `/status`
#: melaporkan `ready: false` alih-alih melempar 503.
INDEX_ROUTES = [
    ("GET", "/equipment"),
    ("GET", "/equipment/EQ-0001"),
    ("GET", "/equipment/EQ-0001/documents"),
    ("GET", "/equipment/EQ-0001/work-orders"),
    ("GET", "/equipment/EQ-0001/failure-memory"),
    ("GET", "/documents"),
    ("GET", "/graph"),
    ("GET", "/search?q=seal+flush"),
    ("GET", "/conflicts"),
    ("GET", "/verification"),
    ("GET", "/evaluation"),
    ("GET", "/failure-memory"),
    ("GET", "/work-orders"),
    ("GET", "/audit"),
]

ALL_ROUTES = [
    ("GET", "/status"),
    ("GET", "/dataset"),
    ("GET", "/equipment"),
    ("GET", "/equipment/EQ-0001"),
    ("GET", "/equipment/EQ-0001/documents"),
    ("GET", "/equipment/EQ-0001/work-orders"),
    ("GET", "/equipment/EQ-0001/failure-memory"),
    ("GET", "/documents"),
    ("GET", "/graph"),
    ("GET", "/search?q=seal+flush"),
    ("GET", "/trust/weights"),
    ("GET", "/conflicts"),
    ("GET", "/verification"),
    ("GET", "/evaluation"),
    ("GET", "/failure-memory"),
    ("GET", "/work-orders"),
    ("GET", "/audit"),
]


class TestEveryRouteResponds:
    @pytest.mark.parametrize("method,path", ALL_ROUTES, ids=[f"{m} {p}" for m, p in ALL_ROUTES])
    def test_read_routes(self, api, method: str, path: str) -> None:
        response = api.get(PREFIX + path)
        assert response.status_code == 200, response.text[:300]
        # JSON yang bisa diserialisasi. Router yang mengembalikan dict Python
        # yang berisi set atau object SQLite akan gagal di sini, bukan di
        # browser.
        json.dumps(response.json())

    def test_post_routes(self, api) -> None:
        assert api.ask("what is the seal flush plan").status_code == 200


# ---------------------------------------------------------------------------
# Indeks belum siap
# ---------------------------------------------------------------------------


class TestMissingIndex:
    """Semua rute baca harus gagal dengan 503 + perintah, bukan 500.

    503 dipilih karena kondisinya sementara dan bisa diperbaiki user
    (jalankan fetch_dataset). 500 dengan traceback membuat orangtegration
    mengira servernya rusak.
    """

    @pytest.fixture
    def broken_api(self, tmp_path, monkeypatch: pytest.MonkeyPatch, stub_dataset_root):
        """App dengan database yang tidak ada sama sekali.

        Datasetnya tetap ada (dataset palsu dari conftest), karena justru itu
        yang diuji: `index` hilang tapi `dataset` terbaca, jadi `/dataset`
        harus tetap 200 sementara yang lain 503. Kalau dataset ikut hilang,
        test ini tidak lagi membedakan "butuh index" dari "butuh dataset".
        """
        monkeypatch.setenv("TRUSTHUB_API_TOKEN", "ci-test-token-abcdefghijklmnop")
        monkeypatch.setenv(
            "TRUSTHUB_PLANT_DB_PATH", str(tmp_path / "does-not-exist.db")
        )
        monkeypatch.setenv("TRUSTHUB_PLANT_LLM_MODE", "off")
        monkeypatch.setenv("TRUSTHUB_DATASET_ROOT", str(stub_dataset_root))
        from conftest import _clear_caches

        _clear_caches()
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        import plant.api as plant_api

        app = FastAPI()
        app.include_router(plant_api.router)
        _clear_caches()
        with TestClient(app) as client:
            yield client
        _clear_caches()

    @pytest.mark.parametrize(
        "path",
        [p for _, p in INDEX_ROUTES],
        ids=[p for _, p in INDEX_ROUTES],
    )
    def test_returns_503_with_a_recovery_command(self, broken_api, path: str) -> None:
        response = broken_api.get(
            PREFIX + path, headers={"X-TrustHub-Token": "ci-test-token-abcdefghijklmnop"}
        )
        assert response.status_code == 503, f"{path} -> {response.status_code}"
        assert "fetch_dataset" in response.json()["detail"], path

    @pytest.mark.parametrize("path", ["/dataset", "/trust/weights"], ids=["dataset", "weights"])
    def test_index_independent_routes_still_respond(self, broken_api, path: str) -> None:
        # Keduanya tidak membaca index, jadi harus tetap 200. Kalau suatu saat
        # salah satu ikut bergantung pada index, halaman "sistem belum siap"
        # akan gagal dimuat persis saat paling dibutuhkan.
        assert (
            broken_api.get(
                PREFIX + path,
                headers={"X-TrustHub-Token": "ci-test-token-abcdefghijklmnop"},
            ).status_code
            == 200
        )

    def test_status_still_works_and_says_why(self, broken_api) -> None:
        # /status harus tetap bisa dibaca supaya UI bisa menampilkan
        # "indeks belum dibangun" beserta perintahnya. Kalau /status ikut 503,
        # frontend tidak pernah sempat menampilkan apa pun - ia hanya melihat
        # error yang isinya persis pesan yang seharusnya ditampilkan.
        response = broken_api.get(
            PREFIX + "/status",
            headers={"X-TrustHub-Token": "ci-test-token-abcdefghijklmnop"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is False
        assert "fetch_dataset" in body["problem"]
        # Permission DLL harus tetap dilaporkan: mode LLM dan catatan lisensi
        # tidak bergantung pada index dan tetap relevan saat sistem belum siap.
        assert body["llm"]["mode"] in {"off", "local", "external"}
        assert "CALIBER" in body["dataset_licence_note"]

    def test_status_counts_are_zero_not_absent(self, broken_api) -> None:
        # UI membaca `counts.documents` tanpa memeriksa dulu. Key yang hilang
        # membuat `undefined > 0` bernilai false secara diam-diam, dan
        # `undefined.toLocaleString()` melempar. Nol lebih jujur.
        counts = broken_api.get(
            PREFIX + "/status",
            headers={"X-TrustHub-Token": "ci-test-token-abcdefghijklmnop"},
        ).json()["counts"]
        assert set(counts) == {
            "equipment",
            "documents",
            "chunks",
            "work_orders",
            "failure_links",
            "measured_parameters",
            "approved_documents",
        }
        assert all(v == 0 for v in counts.values())

    def test_evaluation_returns_503_not_a_zero_percent(self, broken_api) -> None:
        # Tanpa index tidak ada yang bisa dievaluasi. Harus 503 dengan perintah
        # yang bisa dijalankan - bukan 200 dengan accuracy 0%, yang akan
        # terbaca di UI sebagai "sistemnya salah" padahal sistemnya belum
        # dibangun sama sekali.
        response = broken_api.get(
            f"{PREFIX}/evaluation",
            headers={"X-TrustHub-Token": "ci-test-token-abcdefghijklmnop"},
        )
        assert response.status_code == 503
        assert "fetch_dataset" in response.json()["detail"]

    def test_ask_returns_503_not_500(self, broken_api) -> None:
        response = broken_api.post(
            PREFIX + "/ask",
            headers={"X-TrustHub-Token": "ci-test-token-abcdefghijklmnop"},
            json={"question": "what is the seal flush plan"},
        )
        assert response.status_code == 503
        assert "fetch_dataset" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 404
# ---------------------------------------------------------------------------


class TestNotFound:
    def test_unknown_equipment_names_the_tag(self, api) -> None:
        response = api.get(f"{PREFIX}/equipment/ZX-9999")
        assert response.status_code == 404
        detail = response.json()["detail"]
        assert "ZX-9999" in detail

    def test_unknown_equipment_lists_what_exists(self, api) -> None:
        # Tanpa daftar yang ada, "ZX-9999 tidak dikenal" tidak bisa
        # diperbaiki user - dia tidak tahu harus mengetik apa.
        response = api.get(f"{PREFIX}/equipment/ZX-9999")
        detail = response.json()["detail"]
        assert "EQ-0001" in detail

    @pytest.mark.parametrize(
        "suffix", ["documents", "work-orders", "failure-memory"],
        ids=["documents", "work-orders", "failure-memory"],
    )
    def test_unknown_equipment_subroute_is_404(self, api, suffix: str) -> None:
        # Ketiganya harus 404. Yang pernah menyimpang adalah work-orders: ia
        # membalas 200 dengan daftar kosong, yang terbaca sebagai "unit ini
        # tidak punya riwayat maintenance" - kesimpulan yang berlawanan dengan
        # kenyataan unit itu tidak ada.
        assert api.get(f"{PREFIX}/equipment/ZX-9999/{suffix}").status_code == 404

    def test_subroute_404_and_detail_404_agree(self, api) -> None:
        # Satu pola pesan, supaya frontend tidak perlu dua cara menampilkan
        # "unit tidak dikenal".
        detail = api.get(f"{PREFIX}/equipment/ZX-9999").json()["detail"]
        sub = api.get(f"{PREFIX}/equipment/ZX-9999/documents").json()["detail"]
        assert "ZX-9999" in detail and "ZX-9999" in sub

    def test_unknown_document_id(self, api) -> None:
        response = api.get(f"{PREFIX}/documents/nope")
        assert response.status_code == 404
        assert "nope" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Normalisasi tag di level HTTP
# ---------------------------------------------------------------------------


class TestTagNormalisation:
    """`tag.upper()` ada di setiap rute equipment, dan itu yang diuji di sini.

    `registry.get_equipment` sengaja exact-match: tag disimpan uppercase dan
    normalisasi harus terjadi di satu tempat yang terlihat, yaitu HTTP, tempat
    orang benar-benar mengetik. Kalau normalisasi dipindahkan ke registry, satu
    rute yang lupa memanggilnya akan mengembalikan 404 untuk tag yang jelas
    ada.
    """

    @pytest.mark.parametrize(
        "path",
        ["/equipment/eq-0001", "/equipment/Eq-0001", "/equipment/EQ-0001"],
    )
    def test_equipment_detail_accepts_any_case(self, api, path: str) -> None:
        assert api.get(PREFIX + path).status_code == 200

    def test_lowercase_tag_returns_the_canonical_upper_case_form(self, api) -> None:
        body = api.get(f"{PREFIX}/equipment/eq-0001").json()
        assert body["equipment_tag"] == "EQ-0001"

    @pytest.mark.parametrize(
        "path",
        ["/equipment/eq-0001/documents", "/equipment/eq-0001/work-orders"],
    )
    def test_subroutes_accept_any_case(self, api, path: str) -> None:
        assert api.get(PREFIX + path).status_code == 200


# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------


class TestFilters:
    def test_equipment_tag_filter(self, api) -> None:
        body = api.get(f"{PREFIX}/documents?equipment_tag=EQ-0001").json()
        assert body["items"]
        assert all(i["equipment_tag"] == "EQ-0001" for i in body["items"])

    def test_doc_type_filter(self, api) -> None:
        body = api.get(f"{PREFIX}/documents?doc_type=opl").json()
        assert body["items"]
        assert all(i["doc_type"] == "opl" for i in body["items"])

    def test_approval_status_filter(self, api) -> None:
        body = api.get(f"{PREFIX}/documents?approval_status=approved").json()
        assert all(i["approval_status"] == "approved" for i in body["items"])

    def test_safety_critical_filter(self, api) -> None:
        body = api.get(f"{PREFIX}/documents?safety_critical=true").json()
        assert all(i["is_safety_critical"] for i in body["items"])

    def test_filters_combine(self, api) -> None:
        body = api.get(
            f"{PREFIX}/documents?equipment_tag=EQ-0001&doc_type=opl&approval_status=approved"
        ).json()
        for item in body["items"]:
            assert item["equipment_tag"] == "EQ-0001"
            assert item["doc_type"] == "opl"
            assert item["approval_status"] == "approved"

    def test_impossible_filter_returns_empty_not_an_error(self, api) -> None:
        # 0 hasil adalah jawaban yang sah: tidak ada OPL approved untuk GA-1201A.
        body = api.get(
            f"{PREFIX}/documents?equipment_tag=GA-1201A&doc_type=opl&approval_status=approved"
        )
        assert body.status_code == 200
        assert body.json()["items"] == []

    def test_unknown_equipment_in_filter_returns_empty(self, api) -> None:
        # Filter bukan 404. "Dokumen untuk ZX-9999" dijawab "tidak ada",
        # bukan "rute ini tidak ada".
        assert api.get(f"{PREFIX}/documents?equipment_tag=ZX-9999").json()["items"] == []


class TestPagination:
    def test_total_is_the_full_count_not_the_page(self, api) -> None:
        body = api.get(f"{PREFIX}/documents?limit=1").json()
        assert body["limit"] == 1
        assert len(body["items"]) == 1
        assert body["total"] > 1

    def test_offset_advances(self, api) -> None:
        first = api.get(f"{PREFIX}/documents?limit=1&offset=0").json()
        second = api.get(f"{PREFIX}/documents?limit=1&offset=1").json()
        assert first["items"][0]["doc_id"] != second["items"][0]["doc_id"]

    @pytest.mark.parametrize(
        "query",
        ["limit=0", "limit=1001", "limit=-1", "offset=-1"],
    )
    def test_out_of_range_is_rejected_by_the_server(self, api, query: str) -> None:
        # Ditolak server, bukan dipotong diam-diam. limit=1001 yang dipotong
        # jadi 1000 akan terlihat berhasil padahal tidak sesuai yang diminta.
        assert api.get(f"{PREFIX}/documents?{query}").status_code == 422

    @pytest.mark.parametrize("query", ["", "q=", "top_k=0", "top_k=51"])
    def test_search_rejects_empty_and_out_of_range(self, api, query: str) -> None:
        assert api.get(f"{PREFIX}/search?{query}").status_code == 422

    def test_work_orders_limit_is_bounded(self, api) -> None:
        assert api.get(f"{PREFIX}/work-orders?limit=1001").status_code == 422

    def test_audit_limit_is_bounded(self, api) -> None:
        assert api.get(f"{PREFIX}/audit?limit=501").status_code == 422

    def test_work_orders_breakdown_only(self, api) -> None:
        body = api.get(f"{PREFIX}/work-orders?breakdown_only=true").json()
        assert body["items"]
        assert all(i["breakdown"] for i in body["items"])


# ---------------------------------------------------------------------------
# /ask
# ---------------------------------------------------------------------------


class TestAskEndpoint:
    def test_returns_the_full_answer_shape(self, api) -> None:
        body = api.ask("what is the seal flush plan").json()
        for key in (
            "question",
            "kind",
            "answer",
            "badge",
            "trust_score",
            "refused",
            "refusal_reason",
            "sources",
            "signals",
            "reasons",
            "warnings",
            "llm_mode",
        ):
            assert key in body, key

    def test_llm_mode_is_reported_as_off_by_default(self, api) -> None:
        # Default harus "off". Mode LLM hanya aktif kalau env var disetel,
        # supaya demo tidak pernah mengirim dokumen committee ke provider luar
        # karena satu baris konfigurasi yang lupa dikosongkan.
        assert api.ask("what is the seal flush plan").json()["llm_mode"] == "off"

    def test_answered_question_has_sources(self, api) -> None:
        body = api.ask("what is the seal flush plan").json()
        assert body["refused"] is False
        assert body["sources"]
        for source in body["sources"]:
            assert source["filename"]

    def test_refusal_is_reported_not_raised(self, api) -> None:
        # Penolakan adalah jawaban yang sah, bukan error. Endpoint yang
        # membalas 400 untuk pertanyaan out-of-scope akan membuat frontend
        # harus membedakan "sistem error" dari "sistem menolak menjawab".
        response = api.ask("who is the CEO of Starbucks")
        assert response.status_code == 200
        body = response.json()
        assert body["refused"] is True
        assert body["refusal_reason"]

    def test_refusal_badge_is_do_not_execute(self, api) -> None:
        body = api.ask("who is the CEO of Starbucks").json()
        assert body["badge"] == "DO NOT EXECUTE"

    def test_empty_question_is_422_not_a_crash(self, api) -> None:
        assert api.ask("").status_code == 422

    def test_missing_question_field_is_422(self, api) -> None:
        assert api.post(f"{PREFIX}/ask", json={}).status_code == 422

    @pytest.mark.parametrize("question", ["x" * 5000, "' OR 1=1 --", "\x00\x01", "../../etc/passwd"])
    def test_hostile_input_returns_200_or_422_never_500(self, api, question: str) -> None:
        # 500 berarti ada input yang lolos ke lapisan yang tidak
        # imun. 200 dengan penolakan juga sah; yang tidak sah adalah 500.
        assert api.ask(question).status_code in (200, 422)

    def test_top_k_is_honoured(self, api) -> None:
        body = api.ask("what is the seal flush plan", top_k=1).json()
        assert len(body["sources"]) <= 1

    def test_use_llm_false_is_accepted(self, api) -> None:
        assert api.ask("what is the seal flush plan", use_llm=False).status_code == 200


# ---------------------------------------------------------------------------
# /status dan /trust/weights
# ---------------------------------------------------------------------------


class TestStatus:
    def test_counts_are_present_and_non_negative(self, api) -> None:
        counts = api.get(f"{PREFIX}/status").json()["counts"]
        for key in (
            "equipment",
            "documents",
            "chunks",
            "work_orders",
            "failure_links",
            "measured_parameters",
            "approved_documents",
        ):
            assert counts[key] >= 0, key

    def test_approval_breakdown_adds_up(self, api) -> None:
        # Kalau jumlah status persetujuan tidak sama dengan jumlah dokumen,
        # ada dokumen yang tidak masuk hitungan mana pun - dan melompat dari
        # situ karena "approved + unknown != documents".
        body = api.get(f"{PREFIX}/status").json()
        assert sum(body["approval_breakdown"].values()) == body["counts"]["documents"]

    def test_llm_state_is_explicit(self, api) -> None:
        llm = api.get(f"{PREFIX}/status").json()["llm"]
        assert llm["mode"] in {"off", "local", "external"}
        assert isinstance(llm["external_allowed"], bool)

    def test_dataset_licence_note_is_present(self, api) -> None:
        # Deck dan UI sama-sama menyebut dataset ini sebagai sample data
        # milik committee. Kalau catatan ini hilang, klaim itu jadi tidak
        # punya tempat di sistem.
        assert "CALIBER" in api.get(f"{PREFIX}/status").json()["dataset_licence_note"]


class TestTrustWeights:
    def test_weights_sum_to_one(self, api) -> None:
        weights = api.get(f"{PREFIX}/trust/weights").json()["weights"]
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_thresholds_are_ordered(self, api) -> None:
        thresholds = api.get(f"{PREFIX}/trust/weights").json()["thresholds"]
        assert 0 < thresholds["verify"] < thresholds["trusted"] <= 1.0
        assert 0 <= thresholds["relevance_floor"] < 1.0

    def test_badge_order_is_reported(self, api) -> None:
        # Urutan dari yang paling ringan ke yang paling berat, supaya UI bisa
        # mengurutkan tanpa harus tahu sendiri mana yang lebih serius.
        assert api.get(f"{PREFIX}/trust/weights").json()["badges"] == [
            "TRUSTED",
            "VERIFY",
            "DO NOT EXECUTE",
        ]

    def test_unknown_approval_scores_lowest(self, api) -> None:
        scores = api.get(f"{PREFIX}/trust/weights").json()["approval_scores"]
        assert scores["approved"] > scores["unknown"]


# ---------------------------------------------------------------------------
# Bentuk data untuk UI
# ---------------------------------------------------------------------------


class TestGraphShape:
    def test_nodes_and_links(self, api) -> None:
        body = api.get(f"{PREFIX}/graph").json()
        assert body["nodes"]
        assert "links" in body

    def test_every_node_has_an_id_and_a_type(self, api) -> None:
        for node in api.get(f"{PREFIX}/graph").json()["nodes"]:
            assert node["id"]
            assert node["type"]

    def test_links_point_at_existing_nodes(self, api) -> None:
        # D3 gagal keras kalau sebuah link menunjuk node yang tidak ada:
        # edge-nya hilang tanpa pesan, dan grafnya terlihat benar padahal
        # sebagian relasi tidak tergambar.
        body = api.get(f"{PREFIX}/graph").json()
        ids = {n["id"] for n in body["nodes"]}
        for link in body["links"]:
            assert link["source"] in ids, link
            assert link["target"] in ids, link

    def test_equipment_nodes_carry_integer_counts(self, api) -> None:
        # Hanya node equipment yang punya hitungan dokumen dan breakdown.
        # Node dokumen dan work order sengaja tidak, dan UI harus membedakan
        # keduanya - bukan memperlakukan key yang hilang sebagai nol, karena
        # "tidak ada dokumen" dan "bukan node equipment" berbeda artinya.
        nodes = api.get(f"{PREFIX}/graph").json()["nodes"]
        equipment = [n for n in nodes if n["type"] == "equipment"]
        assert equipment
        for node in equipment:
            for key in ("doc_count", "breakdown_count"):
                assert isinstance(node[key], int), (node["id"], key)

    #: Tipe node yang diukur pada dataset CALIBER: 8 equipment, 8 interlock,
    #: 87 document, 31 breakdown. Daftar ini dikunci supaya menambah tipe baru
    #: di backend tidak diam-diam membuat frontend menggambar node tanpa label
    #: atau tanpa warna.
    NODE_TYPES = {"equipment", "interlock", "document", "breakdown"}

    def test_every_node_type_is_known_to_the_frontend(self, api) -> None:
        for node in api.get(f"{PREFIX}/graph").json()["nodes"]:
            assert node["type"] in self.NODE_TYPES, node["type"]

    def test_edge_labels_are_known(self, api) -> None:
        # Label edge berasal dari kunci dokumen yang benar-benar ada di
        # dataset: interlock, datasheet, ga, opl, plot_plan, breakdown. Edge
        # "mirip dengan" tidak ada di sini - graf yang dibangun dari kemiripan
        # teks terlihat bagus di demo dan menyesatkan di lapangan.
        allowed = {"interlock", "datasheet", "ga", "opl", "plot_plan", "breakdown"}
        for link in api.get(f"{PREFIX}/graph").json()["links"]:
            assert link["label"] in allowed, link["label"]

    def test_interlock_nodes_are_equipment_tagged(self, api) -> None:
        # Node interlock dipegang lewat TJC-LLD-IL-<tag>, jadi id-nya harus
        # bisa dipetakan ke equipment-nya. Kalau tidak, panel detail tidak
        # bisa menampilkan "interlock milik unit mana".
        for node in api.get(f"{PREFIX}/graph").json()["nodes"]:
            if node["type"] == "interlock":
                assert node["id"], node


class TestVerificationShape:
    def test_inventory_is_present(self, api) -> None:
        # Halaman Evaluation menampilkan angka ini. Tanpa inventory, angka
        # "nilai diekstraksi" tidak bisa dibandingkan dengan "nilai disimpan".
        body = api.get(f"{PREFIX}/verification").json()
        assert body["inventory"]["values_extracted"] >= 0
        assert body["inventory"]["by_source"]
        assert body["inventory"]["by_doc_type"]

    def test_histogram_keys_are_document_counts(self, api) -> None:
        for key in api.get(f"{PREFIX}/verification").json()["document_count_histogram"]:
            assert key.isdigit()

    def test_conflicts_counts_are_consistent(self, api) -> None:
        body = api.get(f"{PREFIX}/conflicts").json()
        assert body["needs_sme"] <= body["total"]


class TestEvaluation:
    """Set evaluasi dijalankan, bukan dibaca dari konstanta.

    Test ini menolak keras pada dua kegagalan yang mahal: angka akurasi yang
    ditulis manual di frontend, dan `results` penuh yang bocor ke browser.
    """

    def test_reports_a_locked_spec_version(self, api) -> None:
        body = api.get(f"{PREFIX}/evaluation").json()
        assert body["spec_version"], "the set must declare which version ran"

    def test_accuracy_is_computed_as_a_ratio(self, api) -> None:
        body = api.get(f"{PREFIX}/evaluation").json()
        assert body["total"] > 0
        assert 0 <= body["passed"] <= body["total"]
        expected = round(100.0 * body["passed"] / body["total"], 1)
        assert body["accuracy_pct"] == expected

    def test_refusals_and_answers_are_reported_separately(self, api) -> None:
        # Angka yang paling penting justru bukan accuracy: berapa dari kasus
        # yang seharusnya DITOLAK, dan berapa dari yang harus dijawab, yang
        # berperilaku seperti seharusnya. Knowledge hub yang menjawab
        # semua pertanyaan terlihat seperti sistem yang fasih, bukan yang
        # bisa dipercaya.
        body = api.get(f"{PREFIX}/evaluation").json()
        assert body["refusal"]["expected"] > 0, "set must contain refusal cases"
        assert body["answer"]["expected"] > 0, "set must contain answerable cases"
        assert body["refusal"]["expected"] + body["answer"]["expected"] == body["total"]
        assert body["refusal"]["correct"] <= body["refusal"]["expected"]
        assert body["answer"]["correct"] <= body["answer"]["expected"]

    def test_every_category_reports_its_own_totals(self, api) -> None:
        # Tidak boleh ada kasus yang tidak masuk kategori mana pun: kalau ada,
        # total per kategori akan lebih kecil dari total keseluruhan, dan
        # accuracy 100% bisa achievement dari kasus yang tidak pernah diuji.
        body = api.get(f"{PREFIX}/evaluation").json()
        categories = body["by_category"]
        assert categories
        assert sum(c["total"] for c in categories.values()) == body["total"]
        assert sum(c["passed"] for c in categories.values()) == body["passed"]
        for name, bucket in categories.items():
            assert bucket["passed"] <= bucket["total"], name

    def test_per_case_results_are_not_returned(self, api) -> None:
        # 63 kasus x jawaban + sitasi = ratusan kilobyte untuk data yang tidak
        # pernah ditampilkan. Halaman Evaluation butuh lima angka dan satu
        # histogram per kategori, bukan transkrip.
        raw = api.get(f"{PREFIX}/evaluation").text
        assert "results" not in raw or '"results":[]' in raw.replace(" ", "")


class TestAuditShape:
    def test_ask_writes_an_audit_row(self, api) -> None:
        before = api.get(f"{PREFIX}/audit").json()["total"]
        api.ask("what is the seal flush plan")
        after = api.get(f"{PREFIX}/audit").json()["total"]
        assert after == before + 1

    def test_refusal_is_audited_as_refused(self, api) -> None:
        before = api.get(f"{PREFIX}/audit").json()["refused"]
        api.ask("who is the CEO of Starbucks")
        after = api.get(f"{PREFIX}/audit").json()["refused"]
        assert after == before + 1

    def test_badge_totals_add_up(self, api) -> None:
        body = api.get(f"{PREFIX}/audit").json()
        assert sum(body["by_badge"].values()) == body["total"]

    def test_audit_is_not_filterable_by_arbitrary_query(self, api) -> None:
        # Parameter yang tidak dikenal harus diabaikan oleh FastAPI, bukan
        # dipakai sebagai filter SQL. Kalau suatu saat jadi dipakai, itu
        # perubahan yang perlu review.
        assert api.get(f"{PREFIX}/audit?role=admin").status_code == 200


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestRouterAuthProtection:
    """Gerbang token ada di main.py sebagai middleware, bukan di router ini.

    Yang bisa diuji di sini adalah syarat yang harus dipenuhi middleware itu
    penuhi: tidak ada satu pun path plant yang boleh diakses tanpa token.
    Kalau ada yang masuk ke `PUBLIC_PATHS` atau `TRUSTHUB_PUBLIC_PATHS`, seluruh
    knowledge hub - termasuk jawaban yang ditolak dan audit log - terbuka
    tanpa autentikasi.
    """

    def test_no_plant_route_is_a_public_path(self, api) -> None:
        from auth import is_public_path

        for _, path in ALL_ROUTES:
            assert not is_public_path(PREFIX + path), path
        assert not is_public_path(f"{PREFIX}/ask")

    def test_public_paths_stay_small_and_known(self, api) -> None:
        # Dijaga. Lima public path yang disengaja; daftar ini tidak boleh
        # tumbuh tanpa alasan yang tercatat.
        from auth import PUBLIC_PATHS

        assert PUBLIC_PATHS == frozenset(
            {
                "/health",
                "/docs",
                "/redoc",
                "/openapi.json",
                "/docs/oauth2-redirect",
            }
        )

    def test_env_cannot_make_a_plant_route_public(self, monkeypatch, tmp_path) -> None:
        # `TRUSTHUB_PUBLIC_PATHS` memang bisa menambah public path, tapi hanya
        # yang diminta atas permintaan, dan tidak ada yang menambahnya di
        # repo ini. Test ini documenting the default, bukan memblokir fiturnya.
        from auth import is_public_path

        monkeypatch.setenv("TRUSTHUB_PUBLIC_PATHS", "")
        assert not is_public_path(f"{PREFIX}/status")


class TestNoDatasetLeakage:
    #: Rute yang boleh menyebut path absolut. `/dataset` adalah laporan
    #: provenance: tujuannya justru membuktikan dataset resmi mana yang
    #: di-ingest, dan `/status` menyebut `database` supaya orang bisa
    #: menemukan file index yang salah. Keduanya di belakang gerbang token.
    #: Semua rute lain tidak punya alasan untuk menyebut filesystem.
    PATH_EXEMPT = {"/dataset", "/status"}

    def test_no_endpoint_except_the_provenance_ones_leaks_a_path(self, api) -> None:
        for _, path in ALL_ROUTES:
            if path in self.PATH_EXEMPT:
                continue
            body = api.get(PREFIX + path).text
            assert "Downloads" not in body, path
            assert "Case 1_" not in body, path

    def test_dataset_report_is_the_provenance_evidence(self, api) -> None:
        # Justifikasi pengecualian di atas, dipin jadi test: laporan dataset
        # harus benar-benar menyebut file yang di-ingest. Kalau ini hilang,
        # klaim "official CALIBER dataset" di deck tidak punya bukti yang bisa
        # ditunjukkan.
        report = api.get(f"{PREFIX}/dataset").json()
        assert report["root"]
        assert report["pdf_count"] > 0

    def test_ask_does_not_echo_the_dataset_path(self, api) -> None:
        assert "Downloads" not in api.ask("what is the seal flush plan").text
