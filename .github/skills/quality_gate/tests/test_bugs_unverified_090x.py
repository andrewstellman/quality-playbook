"""v1.5.7 instruction 090x — `bugs_unverified` curated verdict
message: pulled forward from the v1.6.x E1 long-tail because the
incomplete-verification shape is high-frequency.

Motivated by the 2026-05-25 NATS run2 gpt-5.4/medium (Codex
desktop). A capable model found 3 real bugs (incl. BUG-001, a
known NATS security issue) but skipped Phase 5 verification (no
``tdd-results.json``, no red/green logs, fix-only patches with
no regression tests, a ``t.Skip()`` placeholder functional test).
The gate correctly FAILed — but the most informative failure
fell into the 090v ``[generic]`` bucket as a bare
``This check failed: tdd-results.json missing (3 bugs require
it).`` The operator should instead read a plain ``found bugs but
didn't verify them — treat as code-review candidates``.

The category is distinct from 090v ``tdd_overclaim``: overclaim
= a GREEN was *claimed without running*; ``bugs_unverified`` =
the TDD artifacts are *absent entirely* (the run never
attempted / finished verification).

**Attribution discipline**: ``bugs_unverified`` does NOT route
to the weak-model bucket. A capable model can produce this
shape — incomplete run, NOT cut-corners. The "try a stronger
reasoning model" line MUST NOT emit on a ``bugs_unverified``-
only run; it only emits when a separate 090s hollow-test or
090p overclaim signal is independently present.

Test surfaces:

  ClassifierTests — _classify_fail routes each keyed FAIL
    string to ``_FAIL_BUGS_UNVERIFIED``; unrelated strings
    still route to their existing categories.
  NarrationTests — _FAIL_NARRATION carries the curated text;
    "found bug" / "code-review candidates" / "TDD proof"
    substrings present.
  WeakModelAttributionTests — bugs_unverified ALONE does NOT
    fire _has_weak_model_signal (THE HARD-RULE PIN); a co-
    occurring overclaim DOES fire it (overclaim drives the
    weak-model bucket, not bugs_unverified).
  VerdictBlockIntegrationTests — end-to-end through the gate:
    a NATS run2-shape tree (bugs + missing TDD artifacts)
    emits the curated message in the verdict block AND does
    NOT emit the stronger-model recommendation. A zero-bug
    tree never fires bugs_unverified. Load-bearing preservation
    (total_line / result_line / exit_code unchanged).
  ScopeGuardTests — SKILL.md / phase_prompts untouched; rest
    of E1 NOT pulled forward.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from io import StringIO
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))
from test_quality_gate import (  # noqa: E402
    minimal_zero_bug_tree,
    quality_gate,
    FixtureBase,
)


# Each keyed FAIL string from the gate emit sites that should
# route to ``_FAIL_BUGS_UNVERIFIED``. The leading "  " prefix
# mirrors the fail() rendering; _classify_fail substring-matches,
# so the prefix is incidental.
_BUGS_UNVERIFIED_FAIL_STRINGS = (
    "tdd-results.json missing (3 bugs require it)",
    "1 confirmed bug(s) missing red-phase log (BUG-001.red.log)",
    ("No red-phase logs found (every confirmed bug needs "
     "quality/results/BUG-NNN.red.log)"),
    "1 bug(s) with fix patches missing green-phase log "
    "(BUG-NNN.green.log)",
    ("test_regression.* missing — required when bugs exist "
     "(SKILL.md artifact contract)"),
    ("No regression-test patches found "
     "(quality/patches/BUG-NNN-regression-test.patch required)"),
)


# ---------------------------------------------------------------------------
# Classifier — keyed FAIL signatures route to _FAIL_BUGS_UNVERIFIED.
# ---------------------------------------------------------------------------


class ClassifierTests(unittest.TestCase):

    def test_each_keyed_signature_routes_to_bugs_unverified(
            self) -> None:
        """Every keyed FAIL signature in the gate's emit sites
        (tdd-results / red-green logs / regression patches /
        test_regression.*) routes to ``_FAIL_BUGS_UNVERIFIED``.

        Mutation bite: drop any entry from ``_FAIL_CLASSIFIER`` →
        that string falls through to the generic-fallback bucket
        → this test FAILs.
        """
        for s in _BUGS_UNVERIFIED_FAIL_STRINGS:
            cat = quality_gate._classify_fail(s)
            self.assertEqual(
                cat, quality_gate._FAIL_BUGS_UNVERIFIED,
                f"v1.5.7 090x: FAIL string {s!r} must route to "
                f"_FAIL_BUGS_UNVERIFIED; got {cat!r}",
            )

    def test_keyed_signatures_precede_missing_artifact_cluster(
            self) -> None:
        """Ordering pin: strings containing 'missing' that are part
        of the bugs_unverified cluster MUST route to bugs_unverified,
        NOT to ``_FAIL_MISSING_ARTIFACT`` (the broader 'missing
        required' cluster matched later in the table).

        Mutation bite: reorder ``_FAIL_CLASSIFIER`` so the
        ``missing_artifact`` entries precede the bugs_unverified
        cluster → ``tdd-results.json missing (...)`` routes to
        missing_artifact instead → this test FAILs.
        """
        cat = quality_gate._classify_fail(
            "tdd-results.json missing (3 bugs require it)",
        )
        self.assertEqual(
            cat, quality_gate._FAIL_BUGS_UNVERIFIED,
            "v1.5.7 090x: ``tdd-results.json missing (...)`` must "
            "route to bugs_unverified, NOT missing_artifact "
            "(precedence pin).",
        )

    def test_unrelated_strings_still_route_correctly(self) -> None:
        """Don't-over-fire pin: existing categories (overclaim,
        no-op, setup-failure, missing_artifact, generic) still
        route as before — bugs_unverified didn't widen the
        match surface."""
        cases = [
            ("body admits non-execution", quality_gate._FAIL_TDD_OVERCLAIM),
            ("trivial / no-assertion stubs",
             quality_gate._FAIL_NOOP_FUNCTIONAL),
            ("setup/dependency/build/collection failure",
             quality_gate._FAIL_SETUP_FAILURE_RED),
            ("AGENTS.md missing (required at project root)",
             quality_gate._FAIL_MISSING_ARTIFACT),
            ("unfamiliar check failed", quality_gate._FAIL_GENERIC),
        ]
        for msg, expected in cases:
            self.assertEqual(
                quality_gate._classify_fail(msg), expected,
                f"v1.5.7 090x must not perturb existing routing for "
                f"{msg!r}",
            )


# ---------------------------------------------------------------------------
# Narration — curated text content.
# ---------------------------------------------------------------------------


class NarrationTests(unittest.TestCase):

    def test_bugs_unverified_narration_present_and_curated(self) -> None:
        """``_FAIL_NARRATION[_FAIL_BUGS_UNVERIFIED]`` carries the
        curated wording: 'found bug(s) but didn't verify them' +
        'code-review candidates' + 'TDD proof' substring.

        Mutation bite: remove the entry from ``_FAIL_NARRATION``
        → the verdict block falls through to the generic
        fallback ('v1.6.x verdict-explanation expansion will add
        a curated message for this code') → this test FAILs.
        """
        narration = quality_gate._FAIL_NARRATION.get(
            quality_gate._FAIL_BUGS_UNVERIFIED,
        )
        self.assertIsNotNone(
            narration,
            "v1.5.7 090x: _FAIL_NARRATION must carry an entry "
            "for _FAIL_BUGS_UNVERIFIED.",
        )
        self.assertIn("found bug", narration)
        self.assertIn("code-review candidates", narration)
        self.assertIn("TDD proof", narration)


# ---------------------------------------------------------------------------
# Attribution HARD RULE — bugs_unverified does NOT trigger weak-model.
# ---------------------------------------------------------------------------


class WeakModelAttributionTests(unittest.TestCase):

    def test_bugs_unverified_alone_does_NOT_fire_weak_model(
            self) -> None:
        """v1.5.7 090x HARD RULE (per spec): a bugs_unverified-
        only FAIL set MUST NOT fire the weak-model signal — a
        capable model can produce an incomplete run, and the
        stronger-model recommendation would be actively wrong.

        Mutation bite: extend ``_has_weak_model_signal`` to also
        route on ``_FAIL_BUGS_UNVERIFIED`` → this test FAILs and
        the NATS run2 gpt-5.4 case wrongly gets the stronger-
        model line.
        """
        self.assertFalse(quality_gate._has_weak_model_signal(
            fail_records=[
                ("substantive",
                 "tdd-results.json missing (3 bugs require it)"),
                ("substantive",
                 "No regression-test patches found"),
            ],
            zero_bug_repos=[],
            warn_records=[],
        ))

    def test_bugs_unverified_PLUS_overclaim_fires_weak_model(
            self) -> None:
        """If a 090p overclaim FAIL is independently present
        ALONGSIDE bugs_unverified, weak-model fires — driven by
        the overclaim, not by bugs_unverified."""
        self.assertTrue(quality_gate._has_weak_model_signal(
            fail_records=[
                ("substantive",
                 "tdd-results.json missing (3 bugs require it)"),
                ("substantive",
                 "BUG-001.red.log tagged RED but body admits "
                 "non-execution"),
            ],
            zero_bug_repos=[],
            warn_records=[],
        ))


# ---------------------------------------------------------------------------
# Verdict block integration — end-to-end through _emit_operator_verdict.
# ---------------------------------------------------------------------------


class VerdictBlockIntegrationTests(unittest.TestCase):

    def _emit(self, fail_records, **kw):
        """Helper: call _emit_operator_verdict with the given
        fail_records and capture stdout."""
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            quality_gate._emit_operator_verdict(
                fail_records=fail_records,
                warn_records=kw.get("warn_records", []),
                zero_bug_repos=kw.get("zero_bug_repos", []),
                exit_code=kw.get("exit_code", 1),
            )
            return sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

    def test_nats_run2_shape_emits_curated_message_not_generic(
            self) -> None:
        """v1.5.7 090x NATS run2 regression anchor: 3 bugs + no
        TDD artifacts → the verdict block emits the curated
        ``bugs_unverified`` message (with the 'found bug' / 'code-
        review candidates' tokens), NOT the generic fallback.

        Mutation bite: drop the keyed signature entries from
        ``_FAIL_CLASSIFIER`` → the FAILs route to generic-
        fallback → the curated phrases disappear → this test
        FAILs.
        """
        captured = self._emit([
            ("substantive",
             "tdd-results.json missing (3 bugs require it)"),
            ("substantive",
             ("No regression-test patches found "
              "(quality/patches/BUG-NNN-regression-test.patch "
              "required)")),
            ("substantive",
             ("test_regression.* missing — required when bugs "
              "exist (SKILL.md artifact contract)")),
        ])
        # Curated message tokens present.
        self.assertIn("found bug", captured)
        self.assertIn("code-review candidates", captured)
        # And the generic-fallback marker is NOT present (no
        # FAIL fell through to generic).
        self.assertNotIn(
            "v1.6.x verdict-explanation expansion will add",
            captured,
            "v1.5.7 090x: NATS run2 shape must emit the curated "
            "bugs_unverified message, NOT the generic-fallback "
            "narration.",
        )

    def test_nats_run2_shape_does_NOT_emit_stronger_model_line(
            self) -> None:
        """v1.5.7 090x HARD RULE end-to-end: a bugs_unverified-only
        FAIL set must NOT trigger the 'try a stronger reasoning
        model' recommendation. NATS run2 gpt-5.4 is a capable
        model; the issue is an incomplete run.

        Mutation bite: route ``_FAIL_BUGS_UNVERIFIED`` into the
        weak-model bucket → the stronger-model line wrongly
        appears → this test FAILs.
        """
        captured = self._emit([
            ("substantive",
             "tdd-results.json missing (3 bugs require it)"),
            ("substantive",
             ("No regression-test patches found "
              "(quality/patches/BUG-NNN-regression-test.patch "
              "required)")),
        ])
        self.assertNotIn(
            "stronger reasoning model", captured,
            "v1.5.7 090x HARD RULE: a bugs_unverified-only FAIL "
            "set MUST NOT trigger the stronger-model "
            "recommendation. Got:\n" + captured,
        )
        # And the weak-model bucket MUST NOT fire.
        self.assertNotIn(
            "Attribution: weak-model artifact", captured,
        )

    def test_co_occurring_overclaim_DOES_emit_stronger_model_line(
            self) -> None:
        """Companion to the hard rule: when an overclaim is
        independently present, the stronger-model line emits —
        driven by the overclaim, not by bugs_unverified."""
        captured = self._emit([
            ("substantive",
             "tdd-results.json missing (3 bugs require it)"),
            ("substantive",
             ("BUG-001.red.log tagged RED but body admits "
              "non-execution (\"by inspection\")")),
        ])
        self.assertIn("Attribution: weak-model artifact", captured)
        self.assertIn("stronger reasoning model", captured)
        # Both curated narrations present.
        self.assertIn("found bug", captured)
        self.assertIn("never actually ran them", captured)

    def test_zero_bug_run_does_NOT_fire_bugs_unverified(self) -> None:
        """Don't-over-fire pin: a zero-bug shallow PASS never
        fires bugs_unverified — that category requires the
        bugs-present FAIL cluster."""
        captured = self._emit(
            fail_records=[],  # zero-bug PASS, no FAILs
            zero_bug_repos=["testproj"],
            warn_records=[],
            exit_code=0,
        )
        # Curated bugs_unverified tokens absent.
        self.assertNotIn("found bug", captured)
        self.assertNotIn("code-review candidates", captured)


# ---------------------------------------------------------------------------
# End-to-end through the actual gate (subprocess) — NATS run2 shape.
# ---------------------------------------------------------------------------


class NatsRun2RegressionAnchorTests(FixtureBase):
    """Construct the NATS run2 shape (bugs present + TDD artifacts
    absent) by minimally tweaking ``minimal_zero_bug_tree`` and
    asserting the curated message + no stronger-model line."""

    def _nats_run2_shape_tree(self) -> dict:
        """A tree carrying BUG-NNN bugs in BUGS.md but NO TDD
        artifacts (no tdd-results.json, no red/green logs, no
        regression-test patches, no test_regression.*). This is
        the 2026-05-25 NATS run2 gpt-5.4 shape — discovery
        without verification."""
        tree = minimal_zero_bug_tree()
        # Bug heading present (load-bearing — the gate counts
        # BUG-NNN headings to know bugs exist).
        tree["quality/BUGS.md"] = (
            "# Bugs\n\n"
            "### BUG-001: Example bug\n\nDescription.\n"
        )
        # NB: we intentionally do NOT call add_one_bug — that
        # ships tdd-results.json / red+green logs / regression
        # test + patches. The NATS run2 shape has the bug
        # heading and nothing else.
        tree["quality/PROGRESS.md"] = (
            "# Progress\n\nSkill version: 1.4.4\n\n"
            "## Phases\n- [x] Phase 1\n- [x] Phase 2\n- [x] Phase 3\n"
            "- [x] Phase 4\n- [x] Phase 5\n- [x] Phase 6\n"
            "## Terminal Gate Verification\n"
        )
        return tree

    def test_nats_run2_full_gate_emits_bugs_unverified(self) -> None:
        """Full-gate end-to-end: a NATS run2-shape tree runs the
        gate, the verdict block carries the curated
        ``bugs_unverified`` narration ('found bug' / 'code-review
        candidates'), and the gate FAILs (the FAILs are real)."""
        self.write(self._nats_run2_shape_tree())
        stdout, code = self.gate()
        self.assertNotEqual(
            code, 0,
            f"v1.5.7 090x: NATS run2 shape must FAIL the gate "
            f"(real failures present). exit={code}",
        )
        self.assertIn("❌ GATE FAILED", stdout)
        self.assertIn(
            "found bug", stdout,
            "v1.5.7 090x: the curated bugs_unverified narration "
            "must appear in the verdict block on a NATS run2-"
            "shape run.",
        )
        self.assertIn("code-review candidates", stdout)

    def test_nats_run2_full_gate_does_NOT_emit_stronger_model_line(
            self) -> None:
        """Full-gate end-to-end: the NATS run2 gpt-5.4 case
        (capable model, incomplete run) must NOT surface the
        stronger-model recommendation. This is the HARD RULE
        in production."""
        self.write(self._nats_run2_shape_tree())
        stdout, _code = self.gate()
        self.assertNotIn(
            "stronger reasoning model", stdout,
            "v1.5.7 090x HARD RULE: the NATS run2 shape (capable "
            "model, incomplete run) must NOT surface the stronger-"
            "model recommendation. Got stdout:\n" + stdout,
        )

    def test_load_bearing_total_line_unchanged(self) -> None:
        """The 090v load-bearing discipline still holds with 090x
        active: ``Total: N FAIL, M WARN`` (or three-state variant)
        is byte-identical in stdout."""
        self.write(self._nats_run2_shape_tree())
        stdout, _code = self.gate()
        # Match the FAILed three-state form (089c).
        self.assertRegex(
            stdout,
            re.compile(
                r"^Total: \d+ FAIL "
                r"\(\d+ substantive, \d+ record-keeping\), "
                r"\d+ WARN$",
                re.MULTILINE,
            ),
        )

    def test_load_bearing_result_line_unchanged(self) -> None:
        """``RESULT: GATE FAILED — N substantive issue(s) must be
        fixed`` byte-identical (089c three-state)."""
        self.write(self._nats_run2_shape_tree())
        stdout, _code = self.gate()
        self.assertRegex(
            stdout,
            re.compile(
                r"^RESULT: GATE FAILED — \d+ substantive "
                r"issue\(s\) must be fixed$",
                re.MULTILINE,
            ),
        )


# ---------------------------------------------------------------------------
# Scope guards.
# ---------------------------------------------------------------------------


class ScopeGuard090xTests(unittest.TestCase):

    def test_skill_md_not_touched_by_090x(self) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        text = (repo_root / "skills" / "quality-playbook" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "090x", text,
            "SKILL.md must not carry 090x anchors — gate output only.",
        )

    def test_phase_prompts_not_touched_by_090x(self) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        phase_dir = repo_root / "phase_prompts"
        for phase_file in sorted(phase_dir.glob("phase*.md")):
            text = phase_file.read_text(encoding="utf-8")
            self.assertNotIn(
                "090x", text,
                f"{phase_file.name} must not carry 090x anchors.",
            )


if __name__ == "__main__":
    unittest.main()
