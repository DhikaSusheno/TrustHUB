"""API-token authentication and CORS origin policy for the TrustHub backend.

BUG-11 FIX: sebelumnya tidak ada autentikasi sama sekali dan CORS memakai
wildcard origin. Akibatnya halaman web mana pun yang dibuka di browser
korban bisa mengirim POST /propose_operation + /approve_operation +
/execute_operation dan menjalankan operasi sendiri tanpa persetujuan manusia.

Desain:
  - Token WAJIB ada. Kalau env TRUSTHUB_API_TOKEN tidak diisi, backend membuat
    token acak saat start (fail-closed) dan meng-log-nya sekali. Tidak pernah
    ada kondisi "tanpa auth".
  - Perbandingan token memakai secrets.compare_digest (timing-safe).
  - Preflight OPTIONS tidak pernah butuh token; itu duties CORS middleware.
"""

from __future__ import annotations

import base64
import logging
import os
import secrets
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

from cryptography.fernet import Fernet
from fastapi import HTTPException, Request
from fastapi.security import APIKeyHeader

_LOG = logging.getLogger("trusthub.auth")

TOKEN_HEADER = "X-TrustHub-Token"

# Path yang TIDAK memerlukan token.
#
# Sempit by design. Frontend tidak butuh satu pun entri di sini: semua
# request-nya lewat route handler proxy app/backend/[...path], yang
# menyuntikkan TRUSTHUB_API_TOKEN dari sisi server. .env.local.example juga
# menyuruh memakai NEXT_PUBLIC_BACKEND_URL=/backend, bukan backend langsung.
#
# Daftar lama (sebelum #62) membuat 19 entri publik, termasuk /graph/* yang
# membocorkan seluruh graph dan /api/github/auth/pat yang menulis kredensial.
# Enam entri di antaranya berisi placeholder FastAPI seperti
# "/api/github/repos/{owner}/{repo}/contents" - path tersebut tidak pernah
# cocok karena request nyata mengirim path yang sudah disubstitusi, jadi
# config-nya terlihat memberi akses publik tapi efeknya justru mengunci.
PUBLIC_PATHS = frozenset({
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/docs/oauth2-redirect",
})


def _extra_public_paths() -> frozenset:
    """
    Path tambahan yang diminta lewat env `TRUSTHUB_PUBLIC_PATHS`.

    Dipisah pisah dari PUBLIC_PATHS supaya jelas mana yang default aman dan
    mana yang opt-in. Dipisah juga dari parameter route: is_public_path()
    bekerja pada path konkret, bukan pada template FastAPI.
    """
    raw = os.environ.get("TRUSTHUB_PUBLIC_PATHS", "").strip()
    if not raw:
        return frozenset()
    items = {p.strip().rstrip("/") or "/" for p in raw.split(",") if p.strip()}
    return frozenset(items)

_ENV_TOKEN = os.environ.get("TRUSTHUB_API_TOKEN", "").strip()
API_TOKEN: str = _ENV_TOKEN if _ENV_TOKEN else secrets.token_urlsafe(32)

if not _ENV_TOKEN:
    _LOG.warning(
        "TRUSTHUB_API_TOKEN tidak disetel - backend membuat token acak. "
        "Token untuk development ini: %s",
        API_TOKEN,
    )
elif len(API_TOKEN) < 16:
    _LOG.warning(
        "TRUSTHUB_API_TOKEN terlalu pendek (<16 karakter) - disarankan pakai "
        "token acak yang panjang."
    )

# Fernet key untuk encrypt/decrypt token.
#
# Tiga sumber, berurutan prioritas:
#   1. env FERNET_KEY          - produksi / CI
#   2. file .fernet_key        - default development, dibuat sekali lalu dipakai ulang
#   3. (tidak ada lagi)        - dulu: Fernet acak per-proses
#
# Opsi 3 adalah bug, bukan sekadar fitur: key acak per-proses membuat
# SETIAP credential yang tersimpan (github_connections.access_token,
# llm_providers.api_key) tidak bisa dibuka lagi setelah restart. Gejalanya
# muncul jauh dari penyebabnya - user melihat "Credential tersimpan tidak
# bisa didekripsi" padahal tidak pernah melakukan apa-apa, karena backend
# yang mereka jalankan hari ini adalah proses ketiga. Karena itu key
# sekarang ditulis ke disk sekali dan dibaca ulang, jadi restart tidak
# memutus credential apa pun.
#
# File itu WAJIB di-gitignore (sudah). Isinya rahasia setara password API
# yang dienkripsi, jadi tidak boleh masuk riwayat git.
_FERNET_KEY_FILE = Path(__file__).resolve().parent / ".fernet_key"


def _build_fernet(raw: str) -> Fernet:
    """Bangun Fernet dari key base64 url-safe.

    Key Fernet yang valid adalah 32 byte url-safe base64 (44 karakter).
    Padding yang hilang dan spasi hasil copy-paste dinormalkan di sini.

    Hanya menerima bentuk base64. Bentuk mentah 32 byte dicoba oleh
    pemanggil, bukan di sini, supaya keputusan "key tidak valid" tetap punya
    satu sumber pesan error.

    Melempar ValueError kalau hasil dekodanya bukan 32 byte.
    """
    # Try to decode as base64 first
    key_bytes = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    if len(key_bytes) == 32:
        return Fernet(base64.urlsafe_b64encode(key_bytes).decode())
    raise ValueError("Fernet key must be 32 bytes")


def _load_or_create_fernet_key() -> str:
    """Baca key dari file .fernet_key, atau buat baru kalau file belum ada.

    File yang ADA tapi isinya rusak (kosong, terpotong, bukan key Fernet)
    sengaja membuat start gagal, bukan di-generate ulang. Bedanya penting:
    key itu sudah dipakai mengenkripsi credential yang tersimpan, jadi
    menggenerate diam-diem di sini akan menghapus credential itu tanpa
    jejak - persis bug yang fungsi ini dibuat untuk menutup. File yang
    dibuat aplikasi selalu berisi key, jadi file kosong mustahil terjadi
    di first-run.

    Kegagalan MENULIS ditelan: development tanpa credential tersimpan harus
    tetap bisa jalan, dan pesan errornya sudah menjelaskan konsekuensinya.
    """
    try:
        existing = _FERNET_KEY_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        existing = None
    except OSError as exc:
        # Tidak bisa dibaca (permission, lock Windows). Jangan regenerate:
        # mungkin isinya ada dan credential yang tersimpan bergantung padanya.
        raise RuntimeError(
            f"Tidak bisa membaca Fernet key dari {_FERNET_KEY_FILE} ({exc}). "
            "Perbaiki permission-nya, atau set FERNET_KEY di env untuk melewati "
            "file ini."
        ) from exc

    if existing is None:
        # First run: file belum ada, jadi belum ada credential yang bisa hilang.
        generated = Fernet.generate_key().decode()
        try:
            _FERNET_KEY_FILE.write_text(generated + "\n", encoding="utf-8")
        except OSError as exc:
            _LOG.warning(
                "Tidak bisa menyimpan Fernet key ke %s (%s). Credential yang "
                "disimpan hanya bisa dibaca selama proses ini hidup. Set "
                "FERNET_KEY di env untuk penyimpanan yang persisten.",
                _FERNET_KEY_FILE,
                exc,
            )
        return generated

    if not existing:
        raise RuntimeError(
            f"File Fernet key {_FERNET_KEY_FILE} ada tapi kosong. Ini hampir "
            "selalu berarti file-nya terpotong, bukan first-run - credential "
            "yang sudah disimpan tidak akan bisa didekripsi. Set FERNET_KEY di "
            "env dengan key yang benar, atau hapus file ini kalau memang belum "
            "pernah ada credential."
        )
    return existing


_FERNET_KEY = os.environ.get("FERNET_KEY", "").strip()
if _FERNET_KEY:
    try:
        _fernet = _build_fernet(_FERNET_KEY)
    except Exception:
        # Jika base64 decode gagal, coba sebagai raw key
        try:
            _fernet = Fernet(_FERNET_KEY.encode())
        except Exception:
            # FAIL CLOSED, bukan senyap.
            #
            # FERNET_KEY yang terisi tapi tidak valid selalu berarti salah
            # konfigurasi (typo/corrupt), jadi lebih baik gagal keras di awal
            # dengan pesan yang bisa ditindaklanjuti daripada kehilangan data
            # kredensial diam-diam.
            raise RuntimeError(
                "FERNET_KEY terisi tapi bukan key Fernet yang valid (harus 32 byte "
                "url-safe base64, 44 karakter). Key yang salah akan membuat SEMUA "
                "credential tersimpan tidak bisa dibuka. Perbaiki FERNET_KEY atau "
                "hapus variabelnya untuk mode development."
            ) from None
else:
    _fernet = _build_fernet(_load_or_create_fernet_key())
    _LOG.info(
        "FERNET_KEY tidak disetel - memakai key dari %s. Set FERNET_KEY di env "
        "untuk mesin yang lebih dari satu proses.",
        _FERNET_KEY_FILE,
    )


def encrypt_token(token: str) -> str:
    """Encrypt token untuk storage."""
    return _fernet.encrypt(token.encode()).decode()


class TokenDecryptError(ValueError):
    """Credential tersimpan tidak bisa didekripsi.

    Dilempar kalau nilai di DB bukan token Fernet yang valid, atau key
    yang dipakai menyimpannya berbeda dengan key sekarang. Terpisah dari
    InvalidToken kriptografi supaya pemanggil bisa membedakan "data rusak"
    dari "config salah" tanpa harus mem-parsing pesan error library.
    """


def decrypt_token(encrypted: str) -> str:
    """
    Decrypt token dari storage.

    Tidak pernah melempar exception library mentah. Fernet.InvalidToken
    (dan AttributeError kalau `encrypted` None) diterjemahkan ke
    TokenDecryptError, sehingga pemanggil punya satu titik tangkap.
    """
    if not encrypted:
        raise TokenDecryptError("credential tidak tersimpan (nilainya kosong)")
    try:
        return _fernet.decrypt(encrypted.encode()).decode()
    except TokenDecryptError:
        raise
    except Exception as exc:
        raise TokenDecryptError(
            "credential tidak bisa didekripsi: FERNET_KEY mungkin berbeda "
            "dari saat credential ini disimpan, atau nilainya rusak"
        ) from exc


def decrypt_stored_token(encrypted: str) -> str:
    """
    Decrypt credential yang dibaca dari database.

    Versi siap-HTTP: kegagalan decrypt pada credential tersimpan adalah
    masalah sisi server (key salah/rusak), bukan input klien. Tanpa pembungkus
    ini semua pemakaian decrypt_token() di main.py berujung 500 dengan
    traceback Fernet.InvalidToken — error 500 berisi stack trace library
    kepada klien, plus pesan yang tidak bisa ditindaklanjuti.

    -> 500 kalau key/config bermasalah, -> 400 kalau credential memang tidak
    pernah disimpan (provider/LLM key belum diisi).
    """
    if not encrypted:
        raise HTTPException(
            status_code=400,
            detail=(
                "Credential untuk operasi ini belum diisi. Simpan API key-nya "
                "dulu lewat pengaturan provider sebelum dipakai."
            ),
        )
    try:
        return decrypt_token(encrypted)
    except TokenDecryptError:
        raise HTTPException(
            status_code=500,
            detail=(
                "Credential tersimpan tidak bisa didekripsi. Pastikan FERNET_KEY "
                "di backend sama dengan saat credential disimpan, lalu simpan "
                "ulang API key-nya."
            ),
        ) from None


def decrypt_client_token(encrypted: str) -> str:
    """
    Decrypt nilai yang datang dari BODY request (input klien).

    Dipisah dari decrypt_stored_token() karena akibat kegagalannya berbeda:
    di sini nilainya bukan milik server, jadi credential yang tidak bisa
    dibuka adalah kesalahan pengirim -> 400 Bad Request.

    Endpoint yang memakai ini tidak pernah mengirim nilai terenkripsi ke
    klien (lihat list_llm_providers yang memilih kolom tanpa api_key), jadi
    setiap kegagalannya pasti berasal dari luar.
    """
    try:
        return decrypt_token(encrypted)
    except TokenDecryptError:
        raise HTTPException(
            status_code=400,
            detail=(
                "Nilai api_key pada request bukan credential terenkripsi yang "
                "valid. Kirim ulang nilai yang benar atau kosongkan field-nya."
            ),
        ) from None


_token_header_scheme = APIKeyHeader(name=TOKEN_HEADER, auto_error=False)

DEFAULT_ORIGINS = (
    "http://localhost:3000,"
    "http://127.0.0.1:3000,"
    "http://localhost:3001,"
    "http://127.0.0.1:3001"
)


def allowed_origins() -> List[str]:
    """Origin browser yang diizinkan. Tidak pernah '*'."""
    raw = os.environ.get("TRUSTHUB_ALLOWED_ORIGINS", "").strip()
    if not raw:
        raw = DEFAULT_ORIGINS
    origins = [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]
    return [o for o in origins if o != "*"] or list(DEFAULT_ORIGINS.split(","))


def is_public_path(path: str) -> bool:
    """
    True kalau path boleh diakses tanpa token.

    Trailing slash dinormalisasi supaya `/health/` dan `/health` dianggap sama,
    karena FastAPI bisa menerima keduanya lewat redirect.
    """
    if not path:
        return False
    normalized = path.rstrip("/") or "/"
    return normalized in PUBLIC_PATHS or normalized in _extra_public_paths()


def _extract_token(request: Request) -> Optional[str]:
    header = request.headers.get(TOKEN_HEADER)
    if header and header.strip():
        return header.strip()
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        candidate = authorization[7:].strip()
        if candidate:
            return candidate
    return None


def verify_token(candidate: Optional[str]) -> bool:
    """
    Timing-safe compare token kandidat terhadap API_TOKEN.

    Membandingkan sebagai bytes, bukan str: secrets.compare_digest pada str
    mewajibkan kedua sisinya ASCII dan akan melempar
        TypeError: comparing strings with non-ASCII characters is not supported
    begitu header token memuat satu pun karakter di luar ASCII (mis. "é").
    Karena pemanggilnya middleware yang tidak menangkap exception, header
    semacam itu dulu berujung 500, bukan 401. 500 di jalur auth juga mengubah
    respons menjadi tidak terduga dan berpotensi membocorkan traceback.

    UTF-8 encoding mengubah keduanya ke bytes — di sana compare_digest
    menerima konten apa pun dan tidak pernah melempar — sambil tetap
    mempertahankan perbandingan timing-safe.
    """
    if not candidate:
        return False
    return secrets.compare_digest(
        candidate.encode("utf-8"),
        API_TOKEN.encode("utf-8"),
    )


def require_api_key(request: Request) -> str:
    """
    FastAPI dependency untuk protecting route TERTENTU.

    CATATAN: enforcement utama ada di middleware global di main.py, yang
    mencakup semua route — jadi route mana pun sudah terlindungi tanpa
    dependency ini. Fungsi ini sengaja dipertahankan sebagai lapis pertahanan
    tambahan yang eksplisit (defense in depth) untuk route yang mau dilindungi
    dua kali, dan kini tercakup test di test_auth_token.py.

    Bukan pengganti middleware: middleware-lah yang menjamin route baru ikut
    terlindungi tanpa harus diubah.
    """
    token = _extract_token(request)
    if not verify_token(token):
        raise HTTPException(
            status_code=401,
            detail=(
                "Token API hilang atau tidak valid. Kirim header "
                f"'{TOKEN_HEADER}: <token>' atau 'Authorization: Bearer <token>'."
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token
