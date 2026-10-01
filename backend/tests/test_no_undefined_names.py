"""Pemeriksaan statis: nama yang dipakai tapi tidak pernah didefinisikan.

Latar belakang: backend/main.py pernah lolos `py_compile` dan `pytest`
sambil menyimpan belasan nama yang tidak ada - FastAPI, HTTPException,
asynccontextmanager, field_validator, PROVIDER_BASE_URLS, _as_provider_dict,
dan sebagian nama endpoint. Modul gagal di `import`, jadi backend tidak
pernah start sama sekali, dan tidak satu pun test yang bisa menangkapnya
karena semuanya butuh modul yang sudah bisa diimpor.

Urutannya penting: `pytest tests/` baru bisa jalan kalau main.py bisa
diimpor, sementara import itu sendiri yang jadi masalahnya. Karena itu
pemeriksaan ini tidak butuh main.py - dia hanya mem-parse AST-nya, jadi
tetap jalan meski modulnya rusak.

Logikanya dijalankan oleh tools/find_undefined.py; test ini hanya
menempelkan exit code-nya ke suite.
"""

import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPT = BACKEND_DIR / "tools" / "find_undefined.py"


def test_no_undefined_names_in_backend():
    """Tidak boleh ada modul backend yang punya Name-load tanpa definisi.

    Nama yang didefinisikan LAIN di modul (import, fungsi, class, parameter)
    dihitung benar, jadi positif palsu hanya muncul untuk kode mati - yang
    justru kelas bug yang sama: blok yang menempel ke fungsi sebelumnya
    sehingga tidak pernah dieksekusi tapi tetap menyimpan referensi rusak.

    Dicakup dengan --all, bukan cuma main.py, karena modul baru yang ditulis
    nanti punya risiko yang sama dan tidak ada yang memanggil pemeriksa ini
    secara manual.
    """
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--all"],
        capture_output=True,
        text=True,
        cwd=BACKEND_DIR,
    )
    assert result.returncode == 0, (
        "ada modul yang memakai nama tidak terdefinisi:\n" + result.stdout
    )


def test_main_imports_and_registers_routes():
    """Guard paling bawah: modul harus bisa diimpor dan punya route.

    Diletakkan pertama karena kalau ini gagal, SEMUA test lain yang
    menyentuh main.py ikut gagal dengan error yang sama. Pesan yang paling
    berguna disitulah, bukan AttributeError di tengah test lain.
    """
    import main

    paths = {getattr(r, "path", "") for r in main.app.routes}
    # Rute yang dipanggil frontend. Hilangnya salah satu berarti tombol di
    # UI jadi 404 tanpa jejak di backend.
    for required in (
        "/health",
        "/api/llm/providers",
        "/api/llm/chat",
        "/api/llm/explain",
        "/api/llm/review",
        "/api/llm/refactor",
        "/api/llm/discover-models",
        "/api/github/auth/url",
        "/api/github/repos/{owner}/{repo}/tree",
    ):
        assert required in paths, f"route hilang: {required}"
