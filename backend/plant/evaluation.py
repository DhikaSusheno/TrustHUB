"""Runner evaluation set: mengukur akurasi, bukan cuma kehaccioan.

Kenapa modul ini ada
--------------------
Case Book CALIBER Case 1 menuntut dua hal yang tidak bisa dijawab dengan
"demo-nya kelihatan bagus":

  1. Output AI harus divalidasi.
  2. Harus ada test set akurasi yang angkanya bisa dicantumkan di deck.

Modul ini menyediakan keduanya. Dia menjalankan 32 pertanyaan dengan ekspektasi
yang dikunci, menghitung akurasi per kategori, dan mencetak tabel yang bisa
disalin langsung ke slide.

Yang diukur
-----------
Lima metrik, dipilih karena masing-masing bisa gagal tanpa terlihat di demo:

  answered        apakah sistem menjawab saat memang harus menjawab
  refused         apakah sistem menolak saat memang harus menolak
  badge_floor     apakah badge setidaknya sehati yang diharapkan. Badge yang
                  lebih konservatif dihargai, badge yang lebih longgar
                  dihitung gagal - sistem yang terlalu percaya diri pada
                  jawaban yang benar tetap sistem yang salah.
  grounded        apakah jawaban memuat fakta yang diharapkan, dihitung dari
                  data, bukan dari tebakan
  sourced         apakah jawaban menyertakan dokumen sumber

Ekspektasi berasal dari evaluation_set.json. Angka di sana dibaca langsung dari
dataset resmi, jadi test ini gagal kalau ingest atau ekstraksi rusak - bukan
cuma kalau bahasaJXnya berubah.

Cara pakai
----------
    python -m plant.evaluation              # ringkas + tabel per kategori
    python -m plant.evaluation --json       # untuk CI
    python -m plant.evaluation --verbose    # tampilkan jawaban lengkap
    python -m plant.evaluation --fail-under 90

Nilai yang akan dicantumkan di deck diambil dari `accuracy.json` yang dicetak
script ini, bukan dari run manual. Kalau angkanya di slide berbeda dari angka
di file, slide-nya yang salah.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

from . import ask as ask_mod
from . import dataset as dataset_mod
from . import registry, trust

SET_PATH = Path(__file__).resolve().parent / "evaluation_set.json"

#: Urutan badge dari paling dipercaya ke paling ditolak. Badge yang "lebih
#: rendah" dari ekspektasi boleh, karena kehati-hatian tidak pernah salah.
BADGE_RANK = {
    trust.TRUSTED: 3,
    trust.VERIFY: 2,
    trust.DO_NOT_EXECUTE: 1,
}

#: Alasan penolakan yang harus cocok. Dicek longgar: guardrail menulis
#: kalimat sendiri, dan yang penting adalah jalurnya, bukan redaksinya.
REFUSAL_MARKERS = {
    "unknown document reference": ("not in this dataset", "does not exist", "no document"),
    "unknown equipment tag": (
        "not part of this dataset",
        "not in this dataset",
        "unknown equipment",
        "no equipment",
    ),
    "relevance floor": (
        "do not cover this question",
        "no document in the indexed dataset",
        "not about any equipment",
    ),
    "non-knowledge intent": ("does not write",),
}


def load_set(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or SET_PATH).read_text(encoding="utf-8"))


def _check_badge(actual: str, expected: str | None) -> bool:
    if not expected:
        return True
    return BADGE_RANK.get(actual, 0) >= BADGE_RANK.get(expected, 0)


def _check_refusal_reason(answer: str, expected: str | None) -> bool:
    if not expected:
        return True
    markers = REFUSAL_MARKERS.get(expected)
    if markers is None:
        return True
    low = (answer or "").lower()
    return any(marker in low for marker in markers)


def _check_contains(answer: str, needles: list[str] | None) -> list[str]:
    low = (answer or "").lower()
    return [n for n in (needles or []) if n.lower() not in low]


def run_case(conn: sqlite3.Connection, case: dict[str, Any]) -> dict[str, Any]:
    question = case["question"]
    result = ask_mod.answer(conn, question)
    answer = result.answer or ""
    sources = result.sources or []

    checks: dict[str, bool] = {}
    failures: list[str] = []

    if case.get("expects_refused"):
        checks["refused"] = result.refused
        if not result.refused:
            failures.append("answered a question that had to be refused")
        else:
            if not _check_refusal_reason(answer, case.get("refusal_reason")):
                failures.append(
                    f"refused, but not for the expected reason "
                    f"({case.get('refusal_reason')})"
                )
            if result.badge != trust.DO_NOT_EXECUTE:
                failures.append(f"refused but badge is {result.badge}")
    else:
        checks["answered"] = not result.refused
        if result.refused:
            failures.append(f"refused an in-scope question: {answer[:90]}")
        else:
            missing = _check_contains(answer, case.get("answer_contains"))
            if missing:
                checks["grounded"] = False
                failures.append(f"answer is missing expected facts: {missing}")
            else:
                checks["grounded"] = True

            expected_tag = case.get("expects_equipment_tag")
            if expected_tag and result.equipment_tag != expected_tag:
                failures.append(
                    f"tag is {result.equipment_tag!r}, expected {expected_tag!r}"
                )

            expected_kind = case.get("expects_kind")
            if expected_kind and result.kind != expected_kind:
                failures.append(
                    f"kind is {result.kind!r}, expected {expected_kind!r}"
                )

            expected_type = case.get("expects_source_doc_type")
            if expected_type:
                got = {str(s.get("doc_type")) for s in sources}
                if expected_type not in got:
                    failures.append(
                        f"no {expected_type} source, got {sorted(got) or 'none'}"
                    )
                else:
                    checks["sourced"] = True

            if "expects_verbatim" in case and result.verbatim != case["expects_verbatim"]:
                failures.append(
                    f"verbatim is {result.verbatim}, expected {case['expects_verbatim']}"
                )

            # Badge check only matters when the question was actually answered.
            # A refusal is judged by the refusal branch above.
            if not _check_badge(result.badge, case.get("expects_badge")):
                failures.append(
                    f"badge {result.badge!r} is weaker than expected "
                    f"{case.get('expects_badge')!r}"
                )
            else:
                checks["badge_floor"] = True

    return {
        "id": case["id"],
        "category": case.get("category", "uncategorised"),
        "question": question,
        "expected_refused": bool(case.get("expects_refused")),
        "actual_refused": bool(result.refused),
        "expected_badge": case.get("expects_badge"),
        "actual_badge": result.badge,
        "trust_score": round(float(result.trust_score or 0.0), 3),
        "kind": result.kind,
        "equipment_tag": result.equipment_tag,
        "source_count": len(sources),
        "source_doc_types": sorted({str(s.get("doc_type")) for s in sources}),
        "verbatim": bool(result.verbatim),
        "passed": not failures,
        "failures": failures,
        "answer": answer,
    }


def evaluate(conn: sqlite3.Connection) -> dict[str, Any]:
    spec = load_set()
    cases = spec["cases"]
    results: list[dict[str, Any]] = []
    started = time.perf_counter()
    for case in cases:
        results.append(run_case(conn, case))
    elapsed = time.perf_counter() - started

    passed = sum(1 for r in results if r["passed"])
    by_category: dict[str, dict[str, int]] = {}
    for r in results:
        bucket = by_category.setdefault(r["category"], {"total": 0, "passed": 0})
        bucket["total"] += 1
        bucket["passed"] += 1 if r["passed"] else 0

    # Refusal behaviour is the headline number: a knowledge hub that answers
    # everything is not trustworthy, it is fluent. Reported separately so the
    # deck can state it directly.
    expect_refuse = [r for r in results if r["expected_refused"]]
    expect_answer = [r for r in results if not r["expected_refused"]]
    correct_refusals = sum(1 for r in expect_refuse if r["actual_refused"])
    correct_answers = sum(1 for r in expect_answer if not r["actual_refused"])

    return {
        "spec_version": spec.get("version"),
        "total": len(results),
        "passed": passed,
        "accuracy_pct": round(100.0 * passed / len(results), 1) if results else 0.0,
        "refusal": {
            "expected": len(expect_refuse),
            "correct": correct_refusals,
            "pct": round(100.0 * correct_refusals / len(expect_refuse), 1)
            if expect_refuse
            else 0.0,
        },
        "answer": {
            "expected": len(expect_answer),
            "correct": correct_answers,
            "pct": round(100.0 * correct_answers / len(expect_answer), 1)
            if expect_answer
            else 0.0,
        },
        "by_category": by_category,
        "elapsed_seconds": round(elapsed, 2),
        "results": results,
    }


def _print_report(report: dict[str, Any], verbose: bool) -> None:
    print("=" * 78)
    print("TrustHUB Plant Knowledge Hub - evaluation")
    print("=" * 78)
    print(f"cases        : {report['passed']}/{report['total']} passed")
    print(f"accuracy     : {report['accuracy_pct']}%")
    print(
        f"refused right: {report['refusal']['correct']}/{report['refusal']['expected']} "
        f"({report['refusal']['pct']}%)"
    )
    print(
        f"answered ok  : {report['answer']['correct']}/{report['answer']['expected']} "
        f"({report['answer']['pct']}%)"
    )
    print(f"elapsed      : {report['elapsed_seconds']}s")

    print("\nper category:")
    for name in sorted(report["by_category"]):
        bucket = report["by_category"][name]
        flag = "" if bucket["passed"] == bucket["total"] else "   <-- FAIL"
        print(
            f"  {name:<24} {bucket['passed']:>2}/{bucket['total']:<2}"
            f"  ({100.0 * bucket['passed'] / bucket['total']:5.1f}%){flag}"
        )

    failed = [r for r in report["results"] if not r["passed"]]
    if failed:
        print(f"\n{len(failed)} failing case(s):")
        for r in failed:
            print(f"\n  [{r['id']}] {r['question']}")
            print(f"      expected refused={r['expected_refused']} "
                  f"badge={r['expected_badge']} | got refused={r['actual_refused']} "
                  f"badge={r['actual_badge']} score={r['trust_score']}")
            for reason in r["failures"]:
                print(f"      - {reason}")
            if verbose:
                print(f"      answer: {(r['answer'] or '')[:600]}")

    if verbose:
        print("\nall cases:")
        for r in report["results"]:
            mark = "OK " if r["passed"] else "XX "
            print(
                f"  {mark}[{r['id']:<11}] {r['question'][:58]:<60} "
                f"{r['actual_badge']:<14} {r['trust_score']:.3f} src={r['source_count']}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m plant.evaluation",
        description="Run the CALIBER Case 1 accuracy test set.",
    )
    parser.add_argument("--json", action="store_true", help="print JSON to stdout")
    parser.add_argument("--verbose", "-v", action="store_true", help="full detail")
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="exit 1 if accuracy is below this percentage",
    )
    parser.add_argument(
        "--out",
        help="also write the full report to this path (default: none)",
    )
    args = parser.parse_args(argv)

    try:
        root = dataset_mod.find_dataset_root()
    except dataset_mod.DatasetNotFound as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    conn = registry.connect()
    try:
        indexed = conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]
        if not indexed:
            print(
                "error: plant index is empty. Run `python -m plant.fetch_dataset` first.",
                file=sys.stderr,
            )
            return 2
        report = evaluate(conn)
    finally:
        conn.close()

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nwritten: {out}")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_report(report, args.verbose)

    if args.fail_under is not None and report["accuracy_pct"] < args.fail_under:
        print(
            f"\nFAIL: accuracy {report['accuracy_pct']}% is below the required "
            f"{args.fail_under}%",
            file=sys.stderr,
        )
        return 1
    return 0 if report["accuracy_pct"] == 100.0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
