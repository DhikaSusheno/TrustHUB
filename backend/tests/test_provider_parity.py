"""Paritas registry provider LLM antara backend dan frontend.

Kenapa file sendiri: id provider dibentuk sebagai "{type}:{name}" oleh KEDUA
sisi, dan itu terjadi sebelum request dikirim - client menghitungnya untuk
menampilkan draft, lalu server menghitungnya lagi saat menyimpan. Kalau
selisih sekecil apa pun ada di salah satu daftar, baris yang sama terpecah
menjadi dua provider berbeda: draft di UI tidak pernah ketemu baris yang
disimpan, dan PATCH mengarah ke id yang tidak ada.

Efeknya tidak pernah menunjuk ke error yang benar. User melihat "provider
tidak ditemukan" padahal tidak pernah menyentuh provider itu, dan tidak ada
jejak di log mana pun karena dua request-nya sama-sama "valid".

Cara paling murah menjaga ini: baca file TypeScript-nya sebagai teks dan
bandingkan literal yang diekstrak. Tidak perlu menjalankan toolchain Node
dari pytest, dan test gagal dengan diff yang langsung menunjukkan tipe mana
yang hanya ada di satu sisi.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_LIB = REPO_ROOT / "frontend" / "lib" / "llmProviders.ts"


def _ts_object(source: str, name: str) -> dict[str, str]:
    """Nilai string dari objek literal satu baris di file .ts.

    Hanya bentuk yang dipakai file ini: satu properti per baris dengan nilai
    string. Cukup untuk daftar registry, dan cukup gagal keras kalau formatnya
    berubah - lebih baik test-nya meledak daripada diam-diam mengembalikan {}
    lalu membandingkan dua daftar kosong sebagai "sama".
    """
    match = re.search(
        rf"export const {name}[^=]*=\s*\{{(.*?)\n\}};", source, re.DOTALL
    )
    assert match, f"{name} tidak ditemukan atau formatnya berubah di {FRONTEND_LIB.name}"
    body = match.group(1)
    return {
        key: value
        for key, value in re.findall(r'"?([A-Za-z0-9_-]+)"?\s*:\s*"([^"]*)"', body)
    }


def _ts_string_array(source: str, name: str) -> list[str]:
    """Isi array string satu blok (untuk KNOWN_PROVIDER_TYPES)."""
    match = re.search(
        rf"export const {name}\s*=\s*\[(.*?)\]\s*as const;", source, re.DOTALL
    )
    assert match, f"{name} tidak ditemukan atau formatnya berubah di {FRONTEND_LIB.name}"
    return re.findall(r'"([^"]+)"', match.group(1))


@pytest.fixture(scope="module")
def frontend_source() -> str:
    assert FRONTEND_LIB.exists(), f"file frontend tidak ditemukan: {FRONTEND_LIB}"
    return FRONTEND_LIB.read_text(encoding="utf-8")


def test_provider_base_urls_are_identical(frontend_source: str):
    """Base URL default harus sama persis di kedua sisi.

    Selisih di sini paling berbahaya dari semua daftar: client menampilkan
    placeholder yang berbeda dari yang benar-benar dipakai server, jadi user
    mengetik URL yang terlihat di UI dan tidak pernah dipakai.
    """
    import main

    backend = dict(main.PROVIDER_BASE_URLS)
    frontend = _ts_object(frontend_source, "PROVIDER_BASE_URLS")

    only_backend = sorted(set(backend) - set(frontend))
    only_frontend = sorted(set(frontend) - set(backend))
    assert not only_backend, (
        f"tipe punya base_url di backend tapi tidak di frontend: {only_backend}\n"
        "Frontend akan menuntut base_url manual untuk tipe yang sebardonnay punya default."
    )
    assert not only_frontend, (
        f"tipe punya base_url di frontend tapi tidak di backend: {only_frontend}\n"
        "Backend akan menolak provider itu dengan 422 base_url wajib diisi."
    )

    mismatched = {
        key: (backend[key], frontend[key])
        for key in backend
        if backend[key] != frontend[key]
    }
    assert not mismatched, "base_url beda antara backend dan frontend: " + repr(mismatched)


def test_known_provider_types_are_identical(frontend_source: str):
    """Daftar tipe yang mengisi dropdown harus sama, urutan termasuk.

    Urutan penting karena dipakai KNOWN_PROVIDER_TYPES.includes() di client
    saat menebak kandidat normalisasi; urutan beda bisa membuat dua input yang
    berbeda mendarat ke tipe yang sama.
    """
    import main

    backend = list(main.KNOWN_PROVIDER_TYPES)
    frontend = _ts_string_array(frontend_source, "KNOWN_PROVIDER_TYPES")

    assert backend == frontend, (
        "KNOWN_PROVIDER_TYPES beda antara backend dan frontend.\n"
        f"  backend : {backend}\n"
        f"  frontend: {frontend}\n"
        "Hanya di backend = opsi tidak muncul di dropdown. "
        "Hanya di frontend = opsi muncul tapi backend tidak kenal."
    )


def test_undeletable_types_are_identical(frontend_source: str):
    """Tipe yang diblokir hapus harus sama, atau UI promesa yang backend tolak.

    Backend membalas 403 "Cannot delete built-in provider". Kalau UI tidak
    tahu, user menekan hapus lalu menunggu error yang sebenarnya sudah bisa
    diprediksi di client.
    """
    import main

    backend = set(main.UNDELETABLE_PROVIDER_TYPES)
    frontend = set(
        re.findall(
            r'"([^"]+)"',
            re.search(
                r"export const UNDELETABLE_TYPES[^=]*=\s*new Set<string>\(\[(.*?)\]\);",
                frontend_source,
                re.DOTALL,
            ).group(1),
        )
    )
    assert backend == frontend, (
        "UNDELETABLE_TYPES beda antara backend dan frontend.\n"
        f"  hanya backend : {sorted(backend - frontend)}\n"
        f"  hanya frontend: {sorted(frontend - backend)}"
    )


def test_type_aliases_are_identical(frontend_source: str):
    """Alias nama -> tipe kanonik harus sama di kedua sisi.

    Alias ini menentukan id provider, jadi kalau hanya ada di satu sisi, user
    yang mengetik "gemini" akan berakhir dengan id berbeda antara yang
    dihitung client dan yang disimpan server.
    """
    import main

    frontend = _ts_object(frontend_source, "PROVIDER_TYPE_ALIASES")
    backend = dict(main.PROVIDER_TYPE_ALIASES)

    assert backend == frontend, (
        "PROVIDER_TYPE_ALIASES beda antara backend dan frontend.\n"
        f"  backend : {backend}\n"
        f"  frontend: {frontend}"
    )


def test_every_alias_points_to_a_known_type():
    """Alias tidak boleh menunjuk tipe yang tidak ada di daftar.

    Alias ke tipe yang tidak dikenal berarti user mengetik "gemini", dapat
    "google" - tapi "google" tidak punya base_url default kalau sesamejak
    lupa menambahkannya, jadi hasilnya persis bug yang dihindari alias.
    """
    import main

    known = set(main.PROVIDER_BASE_URLS) | set(main.KNOWN_PROVIDER_TYPES)
    for alias, canonical in main.PROVIDER_TYPE_ALIASES.items():
        assert canonical in known, (
            f"alias {alias!r} -> {canonical!r}, tapi {canonical!r} bukan tipe yang dikenal"
        )
        # Alias harus idempoten:menormalkan hasil normalisasi lagi tidak
        # boleh mengubahnya, karena client memanggilnya dua kali.
        assert main.normalize_provider_type(canonical) == canonical


def test_sae_types_do_not_include_local_providers():
    """Tipe lokal tidak boleh masuk _PUBLIC_SAE_TYPES.

    Tipe di daftar itu akan menolak base_url loopback/RFC1918. Kalau lmstudio
    atau ollama ikut masuk, base_url default mereka sendiri ditolak - dan
    gejalanya "provider tidak bisa disimpan" untuk konfigurasi bawaan.
    """
    import main

    local_defaults = {
        ptype: url
        for ptype, url in main.PROVIDER_BASE_URLS.items()
        if main._is_local_provider({"type": ptype, "base_url": None})
    }
    leaked = sorted(set(local_defaults) & set(main._PUBLIC_SAE_TYPES))
    assert not leaked, (
        f"tipe lokal ini ikut masuk _PUBLIC_SAE_TYPES: {leaked}\n"
        "Base URL default-nya sendiri akan ditolak sebagai alamat privat."
    )


def test_local_provider_uses_type_default_when_base_url_absent():
    """Tipe lokal harus terbaca lokal walau base_url tidak tersimpan.

    Ini yang membuat LM Studio bisa chat tanpa API key. Kalau helper ini
    hanya membaca base_url yang tersimpan, provider bertipe "lmstudio"
    dengan base_url kosong akan terbaca bukan-lokal dan chat ditolak 400
    "Provider not configured with API key" - padahal LM Studio tidak punya
    key sama sekali.
    """
    import main

    for ptype in ("ollama", "lmstudio"):
        assert main._is_local_provider({"type": ptype, "base_url": None}) is True, (
            f"{ptype} harus terbaca lokal dari base_url default-nya"
        )
    # Tipe SaaS tidak boleh ikut terbaca lokal hanya karena punya default.
    for ptype in ("openai", "google", "groq"):
        assert main._is_local_provider({"type": ptype, "base_url": None}) is False
    # Tipe custom tanpa default dan tanpa base_url: tidak bisa dipastikan,
    # jadi diperlakukan butuh API key.
    assert main._is_local_provider({"type": "vllm", "base_url": None}) is False
