"""Ambil dataset CALIBER Case 1 dan bangun indeks lokal.

Kenapa file ini ada
-------------------
Dataset "Case 1_ Manufacturing Knowledge Hub" milik panitia CALIBER dan
TIDAK boleh ikut commit ke repository publik. Kalau ikut, LICENSE-nya berubah
tempat dan itu pelanggaran penggunaan data. Tapi sistem harus tetap bisa
direproduksi reviewer, jadi yang di-commit adalah script ini: reviewer
menjalankan satu perintah, dataset muncul di tempat yang diharapkan, indeks
dibangun, dan semua metadata bisa diverifikasi ulang.

Perintah
--------
    python -m plant.fetch_dataset            # deteksi + ingest ke DB lokal
    python -m plant.fetch_dataset --check    # hanya validasi, tidak menulis
    python -m plant.fetch_dataset --print-tree

Cara dataset sampai ke mesin ini
--------------------------------
Tiga sumber, dicoba berurutan. Tidak ada URL publik untuk dataset ini - ia
dibagikan lewat portal peserta CALIBER.

  1. Environment variable TRUSTHUB_DATASET_ROOT
  2. Folder backend/dataset/ di dalam repo (untuk yang mengunduh manual)
  3. Pencarian otomatis di folder Downloads / Desktop / Documents

Kalau tidak ketemu, script berhenti dengan pesan yang menyebutkan ke mana
harus meletakkan foldernya, bukan membuat dataset palsu. Dataset kosong yang
dibuat sendiri akan menghasilkan demo yang terlihat jalan padahal tidak
menguji apa pun - itu kegagalan yang lebih buruk daripada berhenti dini.

Struktur dataset yang diharapkan
-------------------------------
    <root>/
      Set_01_GA-1201A_HEXANE_FEED_PUMP/
        Equipment Datasheet - GA-1201A.pdf
        GA Drawing - GA-1201A.pdf
        Interlock Logic Diagram - GA-1201A.pdf
        Plot Plan - GA-1201A.png
        OPL-GA-1201A-01 - ....pdf
        ...
      Set_02_.../
      Set_08_.../
      Maintenance History (All Equipment).xlsx
      Failure Breakdown (All Equipment).xlsx

Workbook "Explanation" pada dataset menjelaskan struktur dan isinya, termasuk
bahwa Equipment_Tag adalah "JOIN KEY to all other documents". Petunjuk itu
yang membuat seluruh 95 dokumen bisa diikat ke 8 equipment dan ke 211 work
order dengan satu foreign key yang berasal dari data, bukan dari tebakan.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import dataset, registry

EXPECTED_DOC_TYPES = {
    "datasheet": 8,
    "ga": 8,
    "interlock": 8,
    "plot_plan": 8,
    "opl": 55,
}


def print_tree(root: Path, limit: int = 40) -> None:
    print(f"dataset root: {root}")
    files = dataset.iter_dataset_files(root)
    print(f"files found  : {len(files)}")
    by_dir: dict[str, int] = {}
    for f in files:
        rel = f.relative_to(root)
        by_dir[str(rel.parent)] = by_dir.get(str(rel.parent), 0) + 1
    for name in sorted(by_dir):
        print(f"  {by_dir[name]:>3d}  {name}")
    print("\nfirst files:")
    for f in files[:limit]:
        print("  ", f.relative_to(root))


def print_report(report: "dataset.DatasetReport") -> None:
    print(f"dataset root : {report.root}")
    print(f"pdf / png    : {report.pdf_count} / {report.png_count}")
    if report.xlsx_path:
        print(f"workbook     : {Path(report.xlsx_path).name}")
    print(f"work orders  : {report.wo_total}")
    print(f"breakdowns   : {report.breakdown_total}")
    print(f"downtime     : {report.downtime_hours} hours")
    print(f"total cost   : IDR {report.total_cost_idr:,.0f}")
    print(f"breakdown $  : IDR {report.breakdown_cost_idr:,.0f}")
    if report.date_range:
        print(f"date range   : {report.date_range}")

    print("\ndocuments per type:")
    for doc_type in sorted(report.by_doc_type):
        print(f"  {doc_type:<12} {report.by_doc_type[doc_type]}")
    total_opl = sum(report.opl_counts.values()) if report.opl_counts else 0
    print(f"  {'opl':<12} {total_opl}")

    print("\nOPL per equipment (should be 7 each):")
    for tag in sorted(report.opl_counts):
        count = report.opl_counts[tag]
        flag = "" if count == 7 else f"   <-- {count}, expected 7"
        print(f"  {tag:<10} {count}{flag}")

    if report.missing_opl:
        print("\nGAPS:")
        for tag, numbers in sorted(report.missing_opl.items()):
            listed = ", ".join(str(n) for n in numbers)
            print(f"  {tag}: OPL nomor [{listed}] tidak ada di dataset")
        print(
            "  Celah ini nyata, bukan kesalahan ekstraksi. Sistem harus "
            "menolak pertanyaan tentang dokumen yang hilang, bukan "
            "menggantinya dengan dokumen lain - itu justru demo "
            "trustworthiness yang paling berguna untuk ditulis di deck."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m plant.fetch_dataset",
        description="Validate and index the CALIBER Case 1 dataset.",
    )
    parser.add_argument(
        "--root",
        help="Path to the dataset folder. Overrides TRUSTHUB_DATASET_ROOT.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate only. Do not write to the database.",
    )
    parser.add_argument(
        "--print-tree",
        action="store_true",
        help="List the discovered files grouped by folder.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full dataset report as JSON.",
    )
    args = parser.parse_args(argv)

    if args.root:
        root = Path(args.root).expanduser().resolve()
        if not root.is_dir():
            print(f"error: --root {root} is not a directory", file=sys.stderr)
            return 2
    else:
        try:
            root = dataset.find_dataset_root()
        except dataset.DatasetNotFound as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    if args.print_tree:
        print_tree(root)
        return 0

    try:
        report = dataset.dataset_report(root)
    except dataset.DatasetNotFound as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, default=str))
        return 0

    print_report(report)

    if report.problems:
        print("\nPROBLEMS FOUND:")
        for problem in report.problems:
            print(f"  - {problem}")
        print(
            "\nDataset punya masalah. Sistem tetap bisa dijalankan, tapi "
            "pertanyaan yang bergantung pada dokumen bermasalah akan "
            "ditolak. Itu perilaku yang diinginkan: lebih baik menolak "
            "daripada mengarang."
        )
    else:
        print("\nvalidation: OK, no problems found")

    if args.check:
        print("\n--check given: database not written.")
        return 0

    print("\nbuilding index ...")
    conn = registry.connect()
    try:
        stats = registry.ingest_all(conn, root)
    finally:
        conn.close()
    print(f"indexed     : {json.dumps(stats)}")
    print(f"database    : {registry.db_path()}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
