"""Discovery model dari upstream provider.

Kenapa file ini ada: MODEL_SUGGESTIONS di frontend adalah daftar tebakan, dan
tebakan cepat basi. Ollama lokal tidak punya "gpt-4o", OpenRouter punya ratusan
model yang tidak akan pernah masuk hardcode, dan model yang DIHAPUS vendor
masih nempel di registry. Endpoint /api/llm/discover-models adalah satu-satunya
jalur yang benar, jadi bentuk respons yang diverse diuji di sini.

Yang paling rawan diuji adalah _parse_upstream_model_ids: kalau bentuk JSON
yang tidak dikenali dilewati diam-diam, UI menampilkan "0 model" padahal
server menyediakannya, dan user menyimpulkan endpoint-nya salah padahal cuma
formatnya beda.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import auth  # noqa: E402

auth.API_TOKEN = "discover-test-token-0123456789abcdef"


# ---------------------------------------------------------------------------
# Bentuk respons /models
# ---------------------------------------------------------------------------


def test_parse_openai_shape():
    import main

    got = main._parse_upstream_model_ids(
        {"object": "list", "data": [{"id": "gpt-4o", "object": "model"}]}
    )
    assert got == ["gpt-4o"]


def test_parse_ollama_native_shape():
    # /api/tags Ollama pakai "name", bukan "id". Kalau hanya "id" yang dibaca,
    # discovery Ollama selalu kosong padahal modelnya ada.
    import main

    got = main._parse_upstream_model_ids(
        {"models": [{"name": "qwen2.5-coder:7b", "size": 123}]}
    )
    assert got == ["qwen2.5-coder:7b"]


def test_parse_plain_string_list():
    # Beberapa gateway lokal membalas {"models": ["a", "b"]} tanpa pembungkus
    # objek per model.
    import main

    got = main._parse_upstream_model_ids({"models": ["a", "b"]})
    assert got == ["a", "b"]


def test_parse_anthropic_shape_uses_data():
    import main

    got = main._parse_upstream_model_ids(
        {"data": [{"id": "claude-sonnet-4-20250514", "type": "model"}]}
    )
    assert got == ["claude-sonnet-4-20250514"]


def test_parse_collects_all_present_keys():
    # Server yang mencampur tidak boleh dikasih hasil kosong hanya karena satu
    # kunci tidak berisi apa-apa.
    import main

    got = main._parse_upstream_model_ids({"data": [], "models": ["x", "y"]})
    assert got == ["x", "y"]


def test_parse_dedupes_and_ignores_empty():
    import main

    got = main._parse_upstream_model_ids(
        {"data": [{"id": "a"}, {"id": "a"}, {"id": "  "}, {"name": "b"}]}
    )
    assert got == ["a", "b"]


def test_parse_bare_list():
    import main

    assert main._parse_upstream_model_ids([{"id": "m1"}, "m2"]) == ["m1", "m2"]


def test_parse_unrecognized_shape_returns_empty():
    import main

    # Bentuk yang benar-benar asing harus kosong, bukan exception: endpointnya
    # mungkin hidup, cuma tidak pakai schema yang dikenal.
    assert main._parse_upstream_model_ids({"error": "nope"}) == []


def test_parse_result_is_sorted_case_insensitively():
    import main

    got = main._parse_upstream_model_ids({"data": [{"id": "Zeta"}, {"id": "alpha"}]})
    assert got == ["alpha", "Zeta"]


# ---------------------------------------------------------------------------
# Kegagalan transport, bukan status HTTP
# ---------------------------------------------------------------------------


class _DeadClient:
    """Client yang gagal seperti server lokal yang belum siap."""

    def __init__(self, exc):
        self._exc = exc

    async def post(self, *args, **kwargs):
        raise self._exc


@pytest.mark.asyncio
async def test_upstream_timeout_becomes_502_with_hint():
    import httpx
    from fastapi import HTTPException

    import main

    client = _DeadClient(httpx.ReadTimeout("too slow"))
    with pytest.raises(HTTPException) as excinfo:
        await main._post_upstream(client, "http://localhost:11434/api/chat", {})
    assert excinfo.value.status_code == 502
    # httpx melempar di luar jalur status, jadi tanpa pembungkus ini user hanya
    # melihat "Internal Server Error" sementara penyebab sebenarnya (model
    # lokal masih loading, proses belum hidup) hilang di traceback server.
    assert "60 detik" in excinfo.value.detail
    assert "localhost:11434" in excinfo.value.detail


@pytest.mark.asyncio
async def test_upstream_connect_error_becomes_502():
    import httpx
    from fastapi import HTTPException

    import main

    client = _DeadClient(httpx.ConnectError("refused"))
    with pytest.raises(HTTPException) as excinfo:
        await main._post_upstream(client, "http://localhost:1/v1/chat/completions", {})
    assert excinfo.value.status_code == 502
    assert "Gagal menghubungi" in excinfo.value.detail


@pytest.mark.asyncio
async def test_upstream_post_passes_headers_through():
    import main

    seen: dict = {}

    class _Ok:
        async def post(self, url, json=None, headers=None, timeout=None):
            seen.update(url=url, json=json, headers=headers, timeout=timeout)
            return "resp"

    result = await main._post_upstream(
        _Ok(), "http://x/v1/chat/completions", {"a": 1}, {"Authorization": "Bearer k"}
    )
    assert result == "resp"
    assert seen["headers"] == {"Authorization": "Bearer k"}
    assert seen["json"] == {"a": 1}


# ---------------------------------------------------------------------------
# Suffix /v1
# ---------------------------------------------------------------------------


def test_ollama_base_drops_v1_for_discovery():
    # Sama seperti llm_chat: /api/tags ada di root Ollama, bukan di /v1.
    # Tanpa ini discovery ke Ollama 404 padahal servernya hidup.
    import main

    assert (
        main._ollama_base({"base_url": "http://localhost:11434/v1"})
        == "http://localhost:11434"
    )
    assert (
        main._ollama_base({"base_url": None, "type": "ollama"})
        == "http://localhost:11434"
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    """Server tiruan yang merekam header dan path yang benar-benar ditanya."""

    route: dict[str, object] = {}
    seen: list[tuple[str, str, dict[str, str]]] = []

    def do_GET(self):  # noqa: N802 - nama dipaksa BaseHTTPRequestHandler
        type(self).seen.append(
            (self.path, self.headers.get("Authorization") or "", dict(self.headers))
        )
        status, body = type(self).route.get(self.path, (404, {"error": "no route"}))
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):  # noqa: D102 - bisu, output test tidak perlu
        pass


@pytest.fixture()
def upstream():
    """Server OpenAI-compatible tiruan, dibinding ke loopback port acak."""
    _Handler.route = {}
    _Handler.seen = []
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, _Handler
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from starlette.testclient import TestClient

    # Loopback harus boleh: tanpa ini guard alamat privat menolak base_url
    # lokal dan test tidak pernah sampai ke server tiruan.
    monkeypatch.setenv("TRUSTHUB_ALLOW_PRIVATE_UPSTREAM", "1")

    import database
    import main

    # main.py mengimpor DB_PATH sebagai nama, jadi keduanya harus dipatch ke
    # file yang sama. Tanpa ini test menulis ke trusthub.db milik user yang
    # sedang dipakai backend yang sedang berjalan.
    db = tmp_path / "discover.db"
    monkeypatch.setattr(main, "DB_PATH", db)
    monkeypatch.setattr(database, "DB_PATH", db)
    database.init_db()

    return TestClient(main.app)


def test_discovery_requires_token(client):
    # Header token disuntik otomatis oleh fixture di conftest.py; di sini
    # sengaja ditimpа dengan nilai salah untuk menguji penolakannya.
    r = client.post(
        "/api/llm/discover-models",
        json={"type": "openai"},
        headers={auth.TOKEN_HEADER: "token-salah"},
    )
    assert r.status_code == 401


def test_discovery_rejects_request_without_type_or_provider(client):
    # Tanpa provider_id DAN tanpa type, backend tidak tahu endpoint mana yang
    # harus ditanya. Menebak default OpenAI di sini sama dengan mengirim
    # request tanpa diminta, jadi tolak.
    r = client.post("/api/llm/discover-models", json={})
    assert r.status_code == 400
    assert "provider_id" in r.json()["detail"]


def test_discovery_uses_draft_before_saving(client, upstream):
    # Ini kasus yang paling penting: daftar model harus bisa diambil SEBELUM
    # provider disimpan. Kalau tidak, user harus menyimpan provider dengan
    # daftar model kosong dulu - dan chat tidak jalan sebelum model diisi,
    # jadi tidak ada jalan keluar.
    server, handler = upstream
    handler.route = {"/v1/models": (200, {"data": [{"id": "model-a"}, {"id": "model-b"}]})}
    r = client.post(
        "/api/llm/discover-models",
        json={
            "type": "openai-compatible",
            "base_url": f"http://127.0.0.1:{server.server_port}/v1",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["models"] == ["model-a", "model-b"]
    assert body["count"] == 2


def test_discovery_sends_bearer_token(client, upstream):
    server, handler = upstream
    handler.route = {"/v1/models": (200, {"data": [{"id": "m"}]})}
    r = client.post(
        "/api/llm/discover-models",
        json={
            "type": "openai-compatible",
            "base_url": f"http://127.0.0.1:{server.server_port}/v1",
            "api_key": "sk-secret-123",
        },
    )
    assert r.status_code == 200
    auth_headers = [h[1] for h in handler.seen]
    assert "Bearer sk-secret-123" in auth_headers


def test_discovery_anthropic_uses_x_api_key(client, upstream):
    # /v1/models Anthropic menolak Authorization saja; butuh x-api-key plus
    # anthropic-version. Tanpa keduanya provider membalas 401 dan user diberi
    # kesimpulan salah soal api_key-nya.
    server, handler = upstream
    handler.route = {"/v1/models": (200, {"data": [{"id": "claude-x"}]})}
    r = client.post(
        "/api/llm/discover-models",
        json={
            "type": "anthropic",
            "base_url": f"http://127.0.0.1:{server.server_port}/v1",
            "api_key": "sk-ant-123",
        },
    )
    assert r.status_code == 200, r.text
    _, _, raw_headers = handler.seen[0]
    assert raw_headers.get("x-api-key") == "sk-ant-123"
    assert raw_headers.get("anthropic-version") == "2023-06-01"


def test_discovery_ollama_uses_api_tags(client, upstream):
    server, handler = upstream
    handler.route = {"/api/tags": (200, {"models": [{"name": "qwen2.5-coder:7b"}]})}
    r = client.post(
        "/api/llm/discover-models",
        json={
            "type": "ollama",
            "base_url": f"http://127.0.0.1:{server.server_port}/v1",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["models"] == ["qwen2.5-coder:7b"]
    # Path yang benar-benar ditanya harus /api/tags, bukan /v1/models.
    assert handler.seen[0][0] == "/api/tags"


def test_discovery_public_type_without_key_is_rejected(client, upstream):
    # Tanpa key, hanya server lokal yang masuk akal - aturan yang sama dengan
    # llm_chat. Melewatkannya di sini membuat endpoint ini jalur untuk
    # menebak-nebak layanan internal tanpa kredensial.
    #
    # Host-nya publik, bukan loopback: kalau base_url-nya lokal, provider
    # memang sah tanpa key dan penolakannya akan jadi bug. Yang diuji di sini
    # justru kasus "vendor hosting tanpa key", jadi host-nya yang menentukan.
    _, handler = upstream
    r = client.post(
        "/api/llm/discover-models",
        json={
            "type": "openai",
            "base_url": "https://api.contoh-tidak-ada.invalid/v1",
        },
    )
    assert r.status_code == 400
    assert "API key" in r.json()["detail"]
    assert handler.seen == [], "tidak boleh ada request yang terkirim"


def test_discovery_local_type_without_key_is_allowed(client, upstream):
    # Kebalikannya juga wajib: LM Studio dan router lokal tidak punya API key
    # sama sekali. Menolaknya membuat "lokal, tanpa key" jadi tidak bisa
    # dipakai sama sekali.
    server, handler = upstream
    handler.route = {"/v1/models": (200, {"data": [{"id": "lokal-1"}]})}
    r = client.post(
        "/api/llm/discover-models",
        json={
            "type": "openai-compatible",
            "base_url": f"http://127.0.0.1:{server.server_port}/v1",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["models"] == ["lokal-1"]


def test_discovery_upstream_error_is_reported_verbatim(client, upstream):
    # 401 dari provider harus kelihatan sebagai 401 provider, bukan 500 kosong.
    # Kalau disembunyikan, user tidak bisa membedakan key salah dari base_url
    # salah - dua masalah dengan perbaikan yang sama sekali berbeda.
    server, handler = upstream
    handler.route = {"/v1/models": (401, {"error": {"message": "invalid api key"}})}
    r = client.post(
        "/api/llm/discover-models",
        json={
            "type": "openai-compatible",
            "base_url": f"http://127.0.0.1:{server.server_port}/v1",
            "api_key": "sk-wrong",
        },
    )
    assert r.status_code == 502
    assert "invalid api key" in r.json()["detail"]


def test_discovery_non_json_body_says_so(client, upstream, monkeypatch):
    # Server hidup tapi membalas HTML (mis. base_url salah path). Pesannya
    # harus menyebut base_url, karena itu penyebab yang paling sering.
    server, handler = upstream

    def _html(self):
        body = b"<html>nope</html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # Goes through monkeypatch so it is undone at teardown. Assigning straight
    # onto the class would leak into every test that runs after this one and
    # the failure would land in an unrelated test.
    monkeypatch.setattr(handler, "do_GET", _html)
    r = client.post(
        "/api/llm/discover-models",
        json={
            "type": "openai-compatible",
            "base_url": f"http://127.0.0.1:{server.server_port}/v1",
        },
    )
    assert r.status_code == 502
    assert "base_url" in r.json()["detail"]


def test_discovery_uses_stored_provider_when_only_id_given(client, upstream):
    # Konfigurasi tersimpan dipakai kalau draft tidak menimpanya, supaya
    # tombol di panel provider tidak perlu kirim base_url/api_key.
    server, handler = upstream
    handler.route = {"/v1/models": (200, {"data": [{"id": "stored-model"}]})}
    created = client.post(
        "/api/llm/providers",
        json={
            "name": "lokal",
            "type": "openai-compatible",
            "base_url": f"http://127.0.0.1:{server.server_port}/v1",
            "models": [],
        },
    )
    assert created.status_code == 200, created.text
    r = client.post(
        "/api/llm/discover-models",
        json={"provider_id": "openai-compatible:lokal"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["models"] == ["stored-model"]


def test_discovery_unknown_provider_id_is_404(client):
    r = client.post(
        "/api/llm/discover-models",
        json={"provider_id": "openai:tidak-ada"},
    )
    assert r.status_code == 404


def test_discovery_does_not_persist_anything(client, upstream):
    # Endpoint ini hanya MEMBACA. Kalau diam-diam menulis daftar ke
    # registry, user kehilangan model lama yang sengaja ditahan tanpa pernah
    # ada dialog konfirmasi.
    server, handler = upstream
    handler.route = {"/v1/models": (200, {"data": [{"id": "baru-1"}]})}
    client.post(
        "/api/llm/providers",
        json={
            "name": "lokal",
            "type": "openai-compatible",
            "base_url": f"http://127.0.0.1:{server.server_port}/v1",
            "models": ["lama-1"],
        },
    )
    client.post(
        "/api/llm/discover-models",
        json={"provider_id": "openai-compatible:lokal"},
    )
    listed = client.get("/api/llm/providers").json()
    saved = next(p for p in listed["providers"] if p["id"] == "openai-compatible:lokal")
    assert saved["models"] == ["lama-1"], "discovery tidak boleh menulis ke registry"
