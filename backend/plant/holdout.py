"""Holdout question set: a second opinion on the locked evaluation set.

`plant/evaluation.py` runs 63 locked cases that are enforced by the build. This
file runs 102 different questions that nothing in the repository depends on.

The distinction matters. `evaluation_set.json` is a fixture: it is asserted, it
fails CI when accuracy drops, and it was written by the same people who tuned
the thresholds. That makes it a regression guard, not independent evidence. The
questions here were written afterwards, in one sitting, to check whether the
behaviour generalises past the wording that was tuned on.

It needs the official dataset, so it is NOT run by CI and is NOT a test. Run it
manually against a populated index:

    python -m plant.holdout --fail-under 95

Measured against the official dataset: **100 of 102, 98.0%.**

The two failures are known and are not fixed here on purpose:

  - "What are the safety steps for confined space entry in the plant?"
  - "How do I prime a pump before start-up?"

Both are questions that genuinely are about this plant but name no equipment
unit, so the domain-vocabulary guardrail refuses them. The dataset contains no
confined-space procedure and no priming instruction, so refusing is defensible;
treating them as failures anyway is the honest reading, because a technician
asking either question gets no help and no explanation of why. They are the
measured edge of the domain gate, not a bug in it.

Keeping them as failures is the point of a holdout. If they were quietly
reclassified as expected refusals, the number would read 100% and the known
limit of the system would disappear from the record.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from plant import ask, dataset as dataset_mod, registry

SET_VERSION = "1.0"

# 52 questions that are about this plant and should be answered.
IN_SCOPE: list[str] = [
    "How to replace the gland packing on YD-2301?",
    "What is the drawing number for the hexane feed pump?",
    "How often is calibration due for the recycle gas compressor?",
    "What are the safety steps for confined space entry in the plant?",
    "Which unit has the most work orders?",
    "Show me the preventive maintenance plan for CT-7801.",
    "What is the operating temperature of the catalyst reduction reactor?",
    "How do I reset a tripped interlock on YD-2301?",
    "What spare parts does the hexane feed pump need?",
    "What is the torque specification for the pump motor alignment?",
    "Give me the revision history of the GA drawing for LV-6701.",
    "What is the functional location of the solvent heater?",
    "How many breakdowns happened in the fractionation area?",
    "What is the emergency shutdown procedure for the recycle gas compressor?",
    "Explain the nitrogen inerting step before steam on for the polymer fluid bed dryer.",
    "What is the trip setpoint for PSLL-1201?",
    "How do I lubricate the chain sprocket on the polymer fluid bed dryer?",
    "What is the cause of failure for the solvent heater?",
    "What is the plot plan for LV-6701?",
    "Give me the datasheet for EA-5601.",
    "What safety precautions are required before opening the reflux accumulator drum?",
    "How to do cold alignment check for the hexane feed pump?",
    "What is the cause and effect matrix for the reflux accumulator drum FA-8901?",
    "How do I change the gland packing on YD-2301?",
    "Which equipment fails most often?",
    "What is the trip setpoint for TSHH-1201?",
    "What vibration limit is specified for VSHH-1201?",
    "Total downtime for LV-6701",
    "How do I raise the trip setpoint for VSHH-1201 above 12 mm/s?",
    "maintenance history for YD-2301",
    "total repair cost for the whole plant",
    "compare downtime between GA-1201A and EA-5601",
    "How do I prime a pump before start-up?",
    "What is the correct way to drain a heat exchanger?",
    "Give me the list of critical equipment.",
    "What is the inspection interval for the cooling tower cell fan?",
    "How is the solvent heater interlocked?",
    "Show me the corrective actions taken on the recycle gas compressor.",
    "What is the difference between preventive and corrective work orders?",
    "What is the approval status of the datasheet for CT-7801?",
    "How many work orders were preventive last year?",
    "What is the corrective action for the packing seal failure on EA-5601?",
    "What is the root cause of the fouling deposit breakdown on FA-8901?",
    "Which equipment has the lowest downtime?",
    "What is the total number of breakdowns across the plant?",
    "What documents exist for KC-4501?",
    "Give me the one point lesson about trunnion bearing inspection.",
    "What is the drum float switch setpoint?",
    "How do I safely open the reflux accumulator drum?",
    "What is the nitrogen blanketing procedure for FA-8901?",
    "Describe the chain sprocket lubrication procedure.",
    "What is the emergency procedure if the reactor temperature runs away?",
]

# 50 questions with nothing to do with a plant document, all of which must be
# refused. Several are near-misses on purpose: they use plant vocabulary
# ("hexane", "valves") inside a request the hub cannot and should not serve.
OUT_OF_SCOPE: list[str] = [
    "Who is the president of Indonesia?",
    "How do I make a good cup of coffee?",
    "What is the derivative of sin x?",
    "How do I install Ubuntu on a laptop?",
    "What is the tallest building in the world?",
    "How do I play chess?",
    "Write me a haiku about pumps.",
    "What is the boiling point of water?",
    "How do I book a flight to Singapore?",
    "What is machine learning?",
    "How do I grow tomatoes indoors?",
    "What is the exchange rate today?",
    "Recommend a movie to watch.",
    "How do I train for a marathon?",
    "What is the difference between RAM and ROM?",
    "Who invented the telephone?",
    "How do I fix a leaking kitchen tap?",
    "What is the capital of Australia?",
    "How do I reset my laptop password?",
    "Write a cover letter for a data analyst job.",
    "How do I open a bank account?",
    "Summarise the plot of Hamlet.",
    "How do I learn Python programming?",
    "What is the population of Tokyo?",
    "Explain quantum entanglement to me.",
    "Who won the World Cup in 1998?",
    "What is the best restaurant in Bandung?",
    "How do I change a car tyre?",
    "Write an email to my manager.",
    "What is 2 plus 2?",
    "Tell me a joke about engineers.",
    "How do I apply for a scholarship?",
    "What is the meaning of life?",
    "How do I file my taxes online?",
    "How do I configure a Kubernetes cluster?",
    "Write me a poem about hexane.",
    "What is the weather in Jakarta tomorrow?",
    "who is the CEO of Starbucks?",
    "give me the recipe for nasi goreng",
    "What is the capital of France and how do I fix a bicycle brake?",
    "Translate this to French please.",
    "Draft an email to the vendor.",
    "What is the boiling point of milk?",
    "Who is my dentist?",
    "How do I start a podcast?",
    "What is the score of last night's game?",
    "Compose a limereme about valves.",
    "How do I apply for a visa?",
    "What is the speed of light?",
    "Help me write my thesis introduction.",
]


def evaluate(conn) -> dict[str, Any]:
    """Run every question through the real answer path and score the outcome."""
    results: list[dict[str, Any]] = []

    for question in IN_SCOPE:
        answer = ask.answer(conn, question)
        results.append(
            {
                "question": question,
                "scope": "in_scope",
                "expected_refused": False,
                "refused": answer.refused,
                "badge": answer.badge,
                "passed": not answer.refused,
            }
        )

    for question in OUT_OF_SCOPE:
        answer = ask.answer(conn, question)
        results.append(
            {
                "question": question,
                "scope": "out_of_scope",
                "expected_refused": True,
                "refused": answer.refused,
                "badge": answer.badge,
                "passed": answer.refused,
            }
        )

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failures = [r for r in results if not r["passed"]]

    def bucket(scope: str) -> dict[str, Any]:
        subset = [r for r in results if r["scope"] == scope]
        ok = sum(1 for r in subset if r["passed"])
        return {
            "total": len(subset),
            "correct": ok,
            "pct": round(100.0 * ok / len(subset), 1) if subset else 0.0,
        }

    return {
        "set_version": SET_VERSION,
        "total": total,
        "passed": passed,
        "accuracy_pct": round(100.0 * passed / total, 1) if total else 0.0,
        "in_scope": bucket("in_scope"),
        "out_of_scope": bucket("out_of_scope"),
        "failures": failures,
    }


def _print_report(report: dict[str, Any]) -> None:
    for failure in report["failures"]:
        verb = "in-scope blocked" if failure["scope"] == "in_scope" else "out-of-scope answered"
        print(f"  XX {verb}: {failure['question'][:64]}")
    print()
    print(
        f"HOLDOUT: {report['in_scope']['total']} in-scope + "
        f"{report['out_of_scope']['total']} out-of-scope = {report['total']} cases"
    )
    print(
        f"errors: {report['total'] - report['passed']}  ->  "
        f"accuracy {report['accuracy_pct']:.1f}%"
    )
    print(
        f"  in-scope {report['in_scope']['correct']}/{report['in_scope']['total']}"
        f"   out-of-scope {report['out_of_scope']['correct']}/{report['out_of_scope']['total']}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m plant.holdout",
        description="Run the 102-question holdout set (requires the dataset).",
    )
    parser.add_argument("--json", action="store_true", help="print JSON to stdout")
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="exit 1 if accuracy is below this percentage",
    )
    parser.add_argument("--out", help="also write the full report to this path")
    args = parser.parse_args(argv)

    try:
        dataset_mod.find_dataset_root()
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
        _print_report(report)

    if args.fail_under is not None and report["accuracy_pct"] < args.fail_under:
        print(
            f"error: accuracy {report['accuracy_pct']:.1f}% is below "
            f"--fail-under {args.fail_under}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())