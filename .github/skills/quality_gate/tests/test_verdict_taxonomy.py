"""v1.5.7 instruction 089c (F15) — three-state verdict taxonomy tests.

Pins the gate's substantive-vs-record-keeping classification and the
three-state verdict decision so a future edit cannot silently:
  - regress GATE PASSED WITH CLEANUP NEEDED back to GATE FAILED (the
    exact adopter-UX defect F15 closed: a record-keeping-incomplete
    run that found real TDD-verified bugs must NOT look like a
    substantive failure), or
  - drop / mis-set a check function's verdict category.

Run:
    python3 -m unittest discover .github/skills/quality_gate/tests

Import shim mirrors test_quality_gate.py (insert the package dir so
`import quality_gate` resolves to the module file).
"""

from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE_DIR))
import quality_gate  # noqa: E402

S = quality_gate.VERDICT_SUBSTANTIVE
R = quality_gate.VERDICT_RECORD_KEEPING


class ComputeFinalVerdictTests(unittest.TestCase):
    """The pure three-state decision (_compute_final_verdict) — the
    function main() uses to print the load-bearing RESULT: line."""

    def test_zero_fails_emits_gate_passed(self) -> None:
        """No fails → RESULT: GATE PASSED, exit 0 (unchanged contract).

        Mutation-test evidence (ai_context/DEVELOPMENT_PROCESS.md:
        152-160), instruction-089c F15:
          Mutation: in quality_gate._compute_final_verdict, change the
          zero-fail branch's return exit code 0 → 1.
          Expected failure: THIS test fails at
            assertEqual(exit_code, 0) → AssertionError: 1 != 0.
          Restoration: revert to 0; test passes.
          Bite executed during 089c development; PASS→FAIL→PASS
          confirmed (__pycache__ purged between mutate and restore).
        """
        total, result, code = quality_gate._compute_final_verdict([], 4)
        self.assertEqual(result, "RESULT: GATE PASSED")
        self.assertEqual(total, "Total: 0 FAIL, 4 WARN")
        self.assertEqual(code, 0)

    def test_record_keeping_only_emits_passed_with_cleanup(self) -> None:
        """Only record_keeping fails → RESULT: GATE PASSED WITH CLEANUP
        NEEDED, exit 0 (NOT GATE FAILED) — the F15 fix.

        Mutation-test evidence (ai_context/DEVELOPMENT_PROCESS.md:
        152-160), instruction-089c F15:
          Mutation: in _compute_final_verdict, make the
          record-keeping-only branch return exit code 1 (regressing
          cleanup to a hard failure).
          Expected failure: THIS test fails at
            assertEqual(code, 0) → AssertionError: 1 != 0.
          Restoration: revert to 0; passes.
          Bite executed during 089c development; PASS→FAIL→PASS
          confirmed.
        """
        records = [(R, "bugs_manifest.json: missing disposition"),
                   (R, "challenge/: BUG-3 record missing"),
                   (R, "REQ-4 missing functional_section")]
        total, result, code = quality_gate._compute_final_verdict(records, 2)
        self.assertEqual(
            result,
            "RESULT: GATE PASSED WITH CLEANUP NEEDED — "
            "3 audit record-keeping gap(s)",
        )
        self.assertEqual(total, "Total: 3 CLEANUP, 2 WARN")
        self.assertEqual(code, 0)

    def test_any_substantive_fail_emits_gate_failed(self) -> None:
        """Any substantive fail (even mixed with record_keeping) →
        RESULT: GATE FAILED, exit 1; the count names substantive only.

        Mutation-test evidence (ai_context/DEVELOPMENT_PROCESS.md:
        152-160), instruction-089c F15:
          Mutation: in _compute_final_verdict, change the substantive
          guard `if n_sub > 0:` → `if False:` so a mixed result falls
          through to the cleanup branch.
          Expected failure: THIS test fails at
            assertEqual(code, 1) → AssertionError: 0 != 1
          (and the RESULT assertion). Restoration: revert; passes.
          Bite executed during 089c development; PASS→FAIL→PASS
          confirmed.
        """
        mixed = [(S, "EXPLORATION.md missing"),
                 (R, "bugs_manifest.json: missing disposition")]
        total, result, code = quality_gate._compute_final_verdict(mixed, 1)
        self.assertEqual(
            result, "RESULT: GATE FAILED — 1 substantive issue(s) must be fixed"
        )
        self.assertEqual(
            total, "Total: 2 FAIL (1 substantive, 1 record-keeping), 1 WARN"
        )
        self.assertEqual(code, 1)
        # Pure-substantive also FAILs.
        _, result2, code2 = quality_gate._compute_final_verdict(
            [(S, "a"), (S, "b")], 0
        )
        self.assertEqual(
            result2, "RESULT: GATE FAILED — 2 substantive issue(s) must be fixed"
        )
        self.assertEqual(code2, 1)


class CheckClassificationTests(unittest.TestCase):
    """Every check function carries a valid F15 verdict category, and
    a representative sample is pinned to its exact classification."""

    def _check_callables(self):
        # Top-level check_* callables minus the two pure dispatchers
        # (they emit no fail() of their own; their leaves are decorated).
        skip = {"check_repo", "check_v1_5_0_gate_invariants"}
        out = {}
        for name in dir(quality_gate):
            if not name.startswith("check_"):
                continue
            obj = getattr(quality_gate, name)
            if callable(obj) and name not in skip:
                out[name] = obj
        return out

    def test_every_check_function_has_verdict_category(self) -> None:
        """No check_* function may lack a `_VERDICT_CATEGORY` in
        {substantive, record_keeping} — classification is non-optional
        for the three-state taxonomy (089c halt condition).

        Mutation-test evidence (ai_context/DEVELOPMENT_PROCESS.md:
        152-160), instruction-089c F15:
          Mutation: remove the @verdict_category decorator from
          quality_gate.check_terminal_gate.
          Expected failure: THIS test fails — check_terminal_gate
          appears in `undecorated` →
            AssertionError: ['check_terminal_gate'] != []
          Restoration: re-add the decorator; passes.
          Bite executed during 089c development; PASS→FAIL→PASS
          confirmed (__pycache__ purged between mutate and restore).
        """
        undecorated = []
        bad = []
        for name, fn in self._check_callables().items():
            cat = getattr(fn, "_VERDICT_CATEGORY", None)
            if cat is None:
                undecorated.append(name)
            elif cat not in (S, R):
                bad.append((name, cat))
        self.assertEqual(undecorated, [],
                         f"check functions missing _VERDICT_CATEGORY: "
                         f"{undecorated}")
        self.assertEqual(bad, [],
                         f"check functions with invalid category: {bad}")
        # Sanity: there really are many checks (guards against the
        # introspection silently matching nothing).
        self.assertGreater(len(self._check_callables()), 25)

    def test_known_check_classifications_are_pinned(self) -> None:
        """Spot-pin the substantive-vs-record-keeping call for a
        representative sample so flipping one is caught (the
        instruction-089c mutation example).

        Mutation-test evidence (ai_context/DEVELOPMENT_PROCESS.md:
        152-160), instruction-089c F15:
          Mutation: change check_file_existence's decorator from
          @verdict_category(VERDICT_SUBSTANTIVE) to
          @verdict_category(VERDICT_RECORD_KEEPING) (mis-classify a
          substantive existence check as cleanup — exactly the defect
          F15's classification guards against).
          Expected failure: THIS test fails at
            assertEqual(cat('check_file_existence'), S) →
            AssertionError: 'record_keeping' != 'substantive'
          Restoration: revert the decorator; test passes.
          Bite executed during 089c development; PASS→FAIL→PASS
          confirmed (__pycache__ purged between mutate and restore).
        """
        def cat(n):
            return getattr(getattr(quality_gate, n), "_VERDICT_CATEGORY", None)

        # Substantive: failure means the work itself wasn't done.
        for n in ("check_file_existence", "check_verdict_shape",
                  "check_mechanical", "check_tdd_logs",
                  "check_v1_5_0_index_md"):
            self.assertEqual(cat(n), S, f"{n} must be substantive")
        # Record-keeping: the work happened; the audit trail has gaps.
        for n in ("check_v1_5_0_bugs_manifest",
                  "check_challenge_gate_coverage",
                  "check_bugs_md_patches_consistency",
                  "check_run_metadata", "check_role_map_consistency",
                  "check_v1_5_2_cardinality_gate"):
            self.assertEqual(cat(n), R, f"{n} must be record_keeping")


class FailCategoryThreadingTests(unittest.TestCase):
    """fail() resolves its category from the @verdict_category stack,
    defaults to substantive when un-decorated (conservative), honors an
    explicit override, and rejects an invalid explicit category."""

    def setUp(self) -> None:
        quality_gate._reset_counters()

    def tearDown(self) -> None:
        quality_gate._reset_counters()

    def _cats(self):
        return [c for c, _ in quality_gate._FAIL_RECORDS]

    def test_undecorated_fail_defaults_substantive(self) -> None:
        """A fail() with no enclosing @verdict_category and no explicit
        category is recorded substantive — never silently downgraded
        to cleanup (the conservative default; 089c Task 1 rule).

        Mutation-test evidence (ai_context/DEVELOPMENT_PROCESS.md:
        152-160), instruction-089c F15:
          Mutation: in quality_gate.fail(), change the empty-stack
          fallback `else VERDICT_SUBSTANTIVE` → `else
          VERDICT_RECORD_KEEPING`.
          Expected failure: THIS test fails at
            assertEqual(self._cats(), [S]) →
            AssertionError: ['record_keeping'] != ['substantive']
          Restoration: revert; passes. Bite executed during 089c
          development; PASS→FAIL→PASS confirmed.
        """
        with contextlib.redirect_stdout(io.StringIO()):
            quality_gate.fail("some/path", "an undecorated failure")
        self.assertEqual(self._cats(), [S])

    def test_decorated_fail_inherits_stack_category(self) -> None:
        """A fail() emitted inside a @verdict_category(record_keeping)
        function (and its nested helpers) is recorded record_keeping."""
        @quality_gate.verdict_category(R)
        def _fake_record_keeping_check():
            quality_gate.fail("manifest.json", "missing field")  # nested
            quality_gate.fail("manifest.json", "another gap")

        with contextlib.redirect_stdout(io.StringIO()):
            _fake_record_keeping_check()
        self.assertEqual(self._cats(), [R, R])
        self.assertEqual(_fake_record_keeping_check._VERDICT_CATEGORY, R)

    def test_explicit_category_override_and_validation(self) -> None:
        """fail(category=...) overrides the stack; an invalid explicit
        category raises ValueError (a typo'd category is a hard
        programming error, not a silent mis-classify)."""
        with contextlib.redirect_stdout(io.StringIO()):
            quality_gate.fail("x", "y", category=R)
        self.assertEqual(self._cats(), [R])
        with self.assertRaises(ValueError):
            with contextlib.redirect_stdout(io.StringIO()):
                quality_gate.fail("x", "y", category="not-a-category")
        # verdict_category() itself rejects an invalid category.
        with self.assertRaises(ValueError):
            quality_gate.verdict_category("bogus")

    def test_reset_counters_clears_ledger_and_stack(self) -> None:
        """_reset_counters() empties _FAIL_RECORDS and the category
        stack so a fresh run starts clean (089c)."""
        with contextlib.redirect_stdout(io.StringIO()):
            quality_gate.fail("a", "b", category=S)
        self.assertEqual(len(quality_gate._FAIL_RECORDS), 1)
        quality_gate._reset_counters()
        self.assertEqual(quality_gate._FAIL_RECORDS, [])
        self.assertEqual(quality_gate._CHECK_CATEGORY_STACK, [])


if __name__ == "__main__":
    unittest.main()
