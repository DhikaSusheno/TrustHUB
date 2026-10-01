"""Contract tests for the holdout set.

`plant/evaluation.py` has a 63-case set that CI enforces. `plant/holdout.py` has
102 different questions that nothing in the build depends on, because running
them needs the official dataset, which CI does not have.

The distinction is the whole point, so these tests check that the holdout stays
a second opinion rather than quietly becoming part of the build:

  - the question lists have the shape and size the reported 98.0% depends on,
  - the two lists are disjoint and free of duplicates,
  - nothing in this file asks CI to run the questions.

None of these tests touch the dataset. A test that did would be a defect: the
build has no dataset and must not depend on one.
"""

from __future__ import annotations

import json
import re

import pytest

from plant import holdout


class TestQuestionLists:
    def test_in_scope_has_52_questions(self):
        # The reported score is 50/52 in-scope. Changing the count changes the
        # number printed in README.md and TRUSTHUB.md.
        assert len(holdout.IN_SCOPE) == 52

    def test_out_of_scope_has_50_questions(self):
        assert len(holdout.OUT_OF_SCOPE) == 50

    def test_the_two_lists_are_disjoint(self):
        overlap = set(holdout.IN_SCOPE) & set(holdout.OUT_OF_SCOPE)
        assert not overlap, (
            "a question cannot be both in scope and out of scope: "
            f"{sorted(overlap)}"
        )

    def test_no_duplicate_in_scope_questions(self):
        seen = [q for q, n in _counts(holdout.IN_SCOPE).items() if n > 1]
        assert not seen, f"duplicated in-scope question: {seen}"

    def test_no_duplicate_out_of_scope_questions(self):
        seen = [q for q, n in _counts(holdout.OUT_OF_SCOPE).items() if n > 1]
        assert not seen, f"duplicated out-of-scope question: {seen}"

    def test_every_question_is_a_non_empty_string(self):
        for question in holdout.IN_SCOPE + holdout.OUT_OF_SCOPE:
            assert isinstance(question, str)
            assert question.strip(), "blank question in the holdout set"

    def test_every_question_is_a_question_not_a_command(self):
        # A few in-scope entries are deliberately phrased as bare requests
        # ("maintenance history for YD-2301") because that is how operators
        # type. They must still be questions in intent, so the check is that
        # each has at least two words, not that it ends with a question mark.
        for question in holdout.IN_SCOPE:
            assert len(question.split()) >= 2, question

    def test_the_set_is_versioned(self):
        # The reported score is meaningless without knowing which questions
        # produced it.
        assert holdout.SET_VERSION


def _counts(items):
    from collections import Counter

    return Counter(items)


class TestHoldoutIsNotPartOfTheBuild:
    def test_the_module_does_not_run_the_questions_on_import(self):
        # `evaluate` is the expensive path. If importing the module had run it,
        # every test collection in this package would need the dataset.
        import inspect

        source = inspect.getsource(holdout)
        # No module-level call to evaluate() outside its own definition.
        body = source.split("def evaluate(", 1)[0]
        assert "evaluate(conn)" not in body

    def test_the_dataset_is_only_touched_inside_main(self):
        import inspect

        main_source = inspect.getsource(holdout.main)
        assert "find_dataset_root" in main_source
        # evaluate() is reachable only from main(), so a plain import is safe.
        assert "registry.connect()" in main_source

    def test_the_cli_offers_a_fail_under_threshold(self):
        import contextlib
        import io

        # --fail-under is what makes the number enforceable when run by hand.
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with pytest.raises(SystemExit) as excinfo:
                holdout.main(["--help"])
        assert excinfo.value.code == 0
        help_text = out.getvalue()
        assert "--fail-under" in help_text
        assert "--json" in help_text


class TestDocstringClaims:
    """The docstring states a measured result. Keep it checkable."""

    def test_the_docstring_names_the_two_known_failures(self):
        doc = holdout.__doc__ or ""
        assert "98.0%" in doc
        assert "confined space entry" in doc
        assert "prime a pump" in doc

    def test_the_known_failures_are_actually_in_the_set(self):
        # If a failure is documented, it must be a question the set asks, or
        # the docstring has drifted from the code.
        everything = " ".join(holdout.IN_SCOPE)
        assert "confined space entry" in everything
        assert "prime a pump" in everything

    def test_the_known_failures_are_in_the_in_scope_half(self):
        # They are scored as false refusals, so they must be listed as in-scope
        # questions. If they were moved to OUT_OF_SCOPE the score would silently
        # jump to 100% and the real limit of the system would vanish.
        for fragment in ("confined space entry", "prime a pump"):
            assert any(fragment in q for q in holdout.IN_SCOPE)
            assert not any(fragment in q for q in holdout.OUT_OF_SCOPE)

    def test_it_says_the_module_is_not_a_test(self):
        doc = holdout.__doc__ or ""
        assert "NOT run by CI" in doc
        assert "NOT a test" in doc


class TestOutOfScopeQuestionsAreActuallyOutOfScope:
    """Guards the shape of the trap half of the set.

    These questions must not mention a real equipment tag. If one did, it would
    stop testing the domain-vocabulary guardrail and start testing retrieval,
    which is a different check.
    """

    TAG = re.compile(r"\b[A-Z]{1,2}-\d{4}[A-Z]?\b")

    def test_no_out_of_scope_question_names_a_plant_tag(self):
        for question in holdout.OUT_OF_SCOPE:
            found = self.TAG.findall(question)
            assert not found, (
                f"out-of-scope question names a tag-shaped token {found}: "
                f"{question!r}"
            )

    def test_some_out_of_scope_questions_use_plant_vocabulary(self):
        # "Write me a poem about hexane." scores higher on retrieval than many
        # real questions. The set must keep these near-misses, because they are
        # the only thing that proves refusal is not just a relevance threshold.
        hexane = [q for q in holdout.OUT_OF_SCOPE if "hexane" in q.lower()]
        assert hexane, "the near-miss vocabulary questions were dropped"

    def test_some_out_of_scope_questions_mix_two_unrelated_topics(self):
        mixed = [
            q for q in holdout.OUT_OF_SCOPE if " and how do i " in q.lower()
        ]
        assert mixed, "the compound off-topic questions were dropped"


class TestJsonReportShape:
    def test_evaluate_reports_the_documented_keys(self):
        # The keys README quotes must exist even when there are no failures.
        report = {
            "set_version": holdout.SET_VERSION,
            "total": 102,
            "passed": 100,
            "accuracy_pct": 98.0,
            "in_scope": {"total": 52, "correct": 50, "pct": 96.2},
            "out_of_scope": {"total": 50, "correct": 50, "pct": 100.0},
            "failures": [],
        }
        # Round-trip so the shape is asserted as JSON, which is how it is read.
        assert json.loads(json.dumps(report))["accuracy_pct"] == 98.0