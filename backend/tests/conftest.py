"""
Fixture bersama untuk seluruh test backend.

BUG-11 menambah autentikasi token ke semua route (kecuali /health, /docs,
/openapi.json). Test yang ada sebelumnya memakai TestClient tanpa header,
jadi setelah gerbang token dipasang semuanya dapat 401.

Daripada mengubah puluhan call site di test lama, fixture ini menyuntikkan
header token ke setiap request TestClient secara otomatis. Test yang memang
mau menguji penolakan token tetap bisa memakai TestClient langsung di luar
fixture, atau meng-override header secara eksplisit.
"""

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import auth  # noqa: E402

TEST_TOKEN = "test-suite-token-0123456789abcdef"
auth.API_TOKEN = TEST_TOKEN


@pytest.fixture(scope="session", autouse=True)
def schema_exists():
    """Bangun skema sebelum test pertama yang menyentuh main.py.

    DI TEMUKAN karena test ini lulus di mesin saya dan gagal di CI:

        test_valid_token_returns_200 -> sqlite3.OperationalError:
        no such table: llm_providers

    Penyebabnya bukan route-nya. `main.app` membangun skema di `lifespan`, dan
    lifespan hanya jalan kalau app dijalankan sebagai context manager:

        with TestClient(app) as client:   # lifespan jalan
        client = TestClient(app)          # lifespan TIDAK jalan

    `httpx.ASGITransport` yang dipakai test token-tanpa-header juga tidak
    menjalankan lifespan. Test yang mengembalikan 401 tetap hijau karena
    gerbang token menolak di middleware, sebelum route dieksekusi - jadi
    hanya test yang token-nya valid yang sampai ke body route dan baru saat
    itu tabelnya dibutuhkan.

    Di mesin saya `backend/trusthub.db` sudah ada dari run sebelumnya, jadi
    tabelnya kebetulan ada dan test-nya hijau. Di CI repo bersih tidak punya
    file itu (`.gitignore:8` menutup `*.db`), jadi tabelnya tidak ada dan test
    gagal. Test yang bergantung pada file sisa di mesin adalah test yang
    salah, jadi skema dibangun di sini.

    Isinya meniru `lifespan` di main.py: legacy `database.init_db()` dan v2
    `storage.init_db()`. `_restore_active_target()` sengaja tidak dipanggil -
    ia memulihkan state dari registry yang bukan bagian dari apa yang diuji.
    """
    import database
    import storage

    database.init_db()
    storage.init_db()
    yield


@pytest.fixture(autouse=True)
def inject_api_token(monkeypatch):
    from starlette.testclient import TestClient

    original_request = TestClient.request

    def request_with_token(self, *args, **kwargs):
        headers = dict(kwargs.get("headers") or {})
        headers.setdefault(auth.TOKEN_HEADER, auth.API_TOKEN)
        kwargs["headers"] = headers
        return original_request(self, *args, **kwargs)

    monkeypatch.setattr(TestClient, "request", request_with_token)
    yield
