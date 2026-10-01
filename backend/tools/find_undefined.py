"""Cari nama yang dipakai tapi tidak didefinisikan di sebuah modul.

Dipakai untuk fix cepat: repo ini punya beberapa helper yang hilang,
dan satu per satu ditemukan lewat traceback wastes time. Script ini statically
cek semua Name-load terhadap (module globals + imports + builtins).

Dapat dipakai untuk satu file atau seluruh modul backend:

    python tools/find_undefined.py                # main.py saja
    python tools/find_undefined.py cortex.py      # satu file
    python tools/find_undefined.py --all          # semua modul backend
"""
import ast
import builtins
import pathlib
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_TARGET = BACKEND_DIR / "main.py"

# Modul yang tidak dicek di --all: test memakai fixture/assert yang memang
# bawaan pytest, dan `__init__` hanya berisi re-export.
#
# SKIP_NAMES, bukan SKIP_DIRS, karena --all memakai glob("*.py") yang datanya
# flat: yang tersedia hanya nama file, tidak pernah nama direktori. Versi
# sebelumnya membandingkan p.name dengan himpunan nama DIREKTORI, jadi
# requirements.py ikut terperiksa dan test_*.py ikut terperiksa - bukan
# karena disengaja, tapi karena pengecekan itu tidak pernah bisa kena.
SKIP_NAMES = {"__init__.py", "conftest.py", "setup.py"}


def check(target: pathlib.Path) -> tuple[int, dict[str, list[int]]]:
    """Kembalikan (jumlah masalah, {nama: [baris]}) untuk satu file."""
    tree = ast.parse(target.read_text(encoding="utf-8"), filename=str(target))

    defined: set[str] = set(dir(builtins)) | {"__name__", "__file__", "__doc__"}
    loaded: dict[str, list[int]] = {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store):
                defined.add(node.id)
            else:
                loaded.setdefault(node.id, []).append(node.lineno)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                defined.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.arg):
            defined.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            defined.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            defined.update(node.names)
        # attribute chain & comprehensions bring their own scopes
        elif isinstance(node, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    defined.add(sub.id)
                elif isinstance(sub, ast.arg):
                    defined.add(sub.arg)

    missing = {
        name: lines for name, lines in loaded.items() if name not in defined
    }

    if not missing:
        print(f"OK  {target.name}: tidak ada nama undefined")
        return 0

    print(f"ERR {target.name}: {len(missing)} nama undefined\n")
    for name in sorted(missing):
        lines = sorted(set(missing[name]))
        shown = ", ".join(str(n) for n in lines[:8])
        more = f" (+{len(lines) - 8} lain)" if len(lines) > 8 else ""
        print(f"    {name:32} baris {shown}{more}")
    return 1


def _targets(argv: list[str]) -> list[pathlib.Path]:
    if "--all" in argv:
        return sorted(
            p for p in BACKEND_DIR.glob("*.py") if p.name not in SKIP_NAMES
        )
    if argv:
        return [BACKEND_DIR / argv[0] if not pathlib.Path(argv[0]).is_absolute()
                else pathlib.Path(argv[0])]
    return [DEFAULT_TARGET]


def main() -> int:
    targets = _targets(sys.argv[1:])
    failures = 0
    for target in targets:
        if not target.exists():
            print(f"ERR {target}: file tidak ada")
            failures += 1
            continue
        try:
            failures += check(target)
        except SyntaxError as exc:
            print(f"ERR {target.name}: tidak bisa di-parse ({exc})")
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
