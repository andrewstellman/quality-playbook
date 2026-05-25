"""v1.5.7 instruction 090p — gate-level TDD RED validity.

Two new mechanical checks in ``quality_gate.check_tdd_logs``:

  Task A — reject setup/dependency/build/collection failure reds as
  valid REDs. The 2026-05-24 Ory Keto run2 (cold Go caches, network-
  restricted sandbox) reported GATE PASSED on three reds whose
  bodies were ``FAIL [setup failed]`` / ``lookup proxy.golang.org:
  no such host`` (Exit 1) + identical generic ``go test ./ketoapi``
  greens (Exit 0). A red that fails because deps won't resolve
  proves nothing about whether the bug exists — the red→green
  transition is explained by deps becoming resolvable, not by the
  fix. 090p rejects such reds and routes them through the existing
  089m NOT_RUN(environment) policy + 090o's phase5 remediation
  pointer.

  Task B — the red/green must exercise the bug's named regression
  test, not a bare/generic package run. Run2's three bugs were all
  "verified" by the identical generic ``go test ./ketoapi`` — but
  BUG-002 lived in ``internal/persistence/sql``, not ``ketoapi``,
  and the regression test for it was never actually invoked. 090p
  extracts the test name from
  ``quality/patches/BUG-NNN-regression-test.patch`` (Go
  ``func TestXxx``, pytest ``def test_xxx``) and requires the red
  AND green to reference that name. Falls back conservatively to
  "red and green must use the same targeted selector, not a bare
  whole-package run" when no name can be extracted.

Test surfaces (all in this file):

  * **Regression anchors from run2**: the three setup-failed reds
    + generic greens are detected as invalid (setup-failure red
    via Task A; bare-package green via Task B).
  * **Genuine run1 receipts still pass**: a real
    ``--- FAIL: TestBuildPlannerQueryRelationFilterUsesEquality
    Constraint`` red + green ``ok`` that runs the named test is
    accepted as a valid TDD proof — 090p does NOT regress honest
    receipts.
  * **Mutation bites** (in docstrings):
      - Drop the setup-failure rejection (e.g. remove
        `_RED_SETUP_FAILURE_SIGNATURES`'s `"[setup failed]"`
        entry) → the run2 setup-failed red is wrongly accepted →
        this test FAILs.
      - Drop the named-test tie / bare-package detection → the
        generic green for BUG-002 is wrongly accepted → this test
        FAILs.

The instruction's conservative-direction rule is also pinned:
  * Unknown/ambiguous red shapes default to genuine RED (no
    over-fire) — verified by ``test_unrecognized_red_shape_not_
    rejected``.
  * A genuine assertion failure that happens to also mention a
    setup-failure substring (multi-package run where some packages
    build and others fail-after-running) stays a genuine RED —
    the ``_RED_GENUINE_FAILURE_SIGNATURES`` precedence rule.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


# Reuse the shared fixture helpers.
sys.path.insert(0, str(Path(__file__).parent))
from test_quality_gate import (  # noqa: E402
    minimal_zero_bug_tree,
    add_one_bug,
    write_tree,
    run_gate,
    today_iso,
    quality_gate,
    FixtureBase,
)


# ---------------------------------------------------------------------------
# Run2 fixtures — the Ory Keto setup-failed reds + generic greens.
# These MUST be rejected by 090p (Task A + Task B).
# ---------------------------------------------------------------------------

_RUN2_RED_LOG = """\
RED
Command: GOCACHE=/tmp/ory-keto-gocache GOMODCACHE=/tmp/ory-keto-gomodcache go test ./ketoapi
Exit code: 1
ketoapi/enc_string.go:10:2: dependency resolution failed in restricted sandbox: lookup proxy.golang.org: no such host
FAIL\tgithub.com/ory/keto/ketoapi [setup failed]
FAIL
"""

_RUN2_GREEN_LOG = """\
GREEN
Command: GOCACHE=/tmp/ory-keto-gocache GOMODCACHE=/tmp/ory-keto-gomodcache go test ./ketoapi
Exit code: 0
ok  \tgithub.com/ory/keto/ketoapi\t0.398s
"""

# Run2 emitted a regression-test patch for each bug, but for BUG-002
# the test lived in `internal/persistence/sql/`, not `ketoapi/` — so
# the generic `go test ./ketoapi` runs the wrong package's tests.
_RUN2_BUG002_REGRESSION_PATCH = """\
--- /dev/null
+++ b/internal/persistence/sql/relation_pagination_test.go
@@ -0,0 +1,12 @@
+package sql
+
+import "testing"
+
+func TestBuildPlannerQueryRelationFilterUsesEqualityConstraint(t *testing.T) {
+\tt.Helper()
+\t// regression for BUG-002: relation-pagination IS NULL bug
+\t_ = "stub"
+}
"""


# ---------------------------------------------------------------------------
# Run1 (genuine) fixtures — a real test-level failure red + named
# green. These MUST still pass under 090p.
# ---------------------------------------------------------------------------

_RUN1_RED_LOG = """\
RED
Command: go test -run TestBuildPlannerQueryRelationFilterUsesEqualityConstraint ./internal/persistence/sql
Exit code: 1
--- FAIL: TestBuildPlannerQueryRelationFilterUsesEqualityConstraint (0.02s)
    relation_pagination_test.go:42: expected eq filter on relation, got IS NULL
FAIL\tgithub.com/ory/keto/internal/persistence/sql\t0.034s
"""

_RUN1_GREEN_LOG = """\
GREEN
Command: go test -run TestBuildPlannerQueryRelationFilterUsesEqualityConstraint ./internal/persistence/sql
Exit code: 0
ok  \tgithub.com/ory/keto/internal/persistence/sql\t0.041s
"""

_RUN1_REGRESSION_PATCH = _RUN2_BUG002_REGRESSION_PATCH  # same regression test


# ---------------------------------------------------------------------------
# Helpers used at the unit-helper layer (not the full-gate layer).
# ---------------------------------------------------------------------------


class Helpers090pTests(unittest.TestCase):
    """Unit tests for the new gate helpers — exercises the decision
    rules in isolation."""

    # --- _is_red_setup_failure ---

    def test_setup_failed_signature_rejected(self) -> None:
        self.assertTrue(
            quality_gate._is_red_setup_failure(_RUN2_RED_LOG),
            "the run2 '[setup failed]' / 'no such host' red must be "
            "classified as setup-failure (Task A regression anchor)",
        )

    def test_no_such_host_signature_rejected(self) -> None:
        body = (
            "RED\nCommand: go test ./pkg\nExit code: 1\n"
            "dial tcp: lookup proxy.golang.org: no such host\n"
        )
        self.assertTrue(quality_gate._is_red_setup_failure(body))

    def test_pytest_collection_error_rejected(self) -> None:
        body = (
            "RED\nCommand: pytest tests/\nExit code: 2\n"
            "ERROR tests/test_foo.py - ImportError: No module named 'x'\n"
            "errors during collection\n"
        )
        self.assertTrue(quality_gate._is_red_setup_failure(body))

    def test_genuine_go_assertion_failure_kept(self) -> None:
        """The canonical Go test-failure shape must NOT be rejected
        as setup-failure. Mutation bite: remove the
        `_RED_GENUINE_FAILURE_SIGNATURES` precedence → this test
        would fail when a multi-package run mentions 'build
        failure' in passing."""
        self.assertFalse(
            quality_gate._is_red_setup_failure(_RUN1_RED_LOG),
            "the genuine '--- FAIL: TestBuildPlannerQuery...' red "
            "must NOT be classified as setup-failure",
        )

    def test_genuine_signature_wins_over_setup_substring(self) -> None:
        """Conservative direction: if both a genuine-test-failure
        signature AND a setup-failure substring are present (a
        multi-package run where some packages failed-after-running
        and others had 'build failure'), the genuine signature
        wins — the test ran and failed."""
        body = (
            "RED\nCommand: go test ./...\nExit code: 1\n"
            "FAIL\tbuild failure\n"
            "--- FAIL: TestFoo (0.01s)\n"
            "    something_test.go:5: expected X got Y\n"
        )
        self.assertFalse(quality_gate._is_red_setup_failure(body))

    def test_unrecognized_red_shape_not_rejected(self) -> None:
        """Conservative direction (per 089m–q): an unrecognized
        non-zero red stays a genuine red. Don't wrongly fail
        honest reds whose runner doesn't match a known signature."""
        body = (
            "RED\nCommand: some-custom-runner --check\nExit code: 1\n"
            "validation failed: some custom message\n"
        )
        self.assertFalse(quality_gate._is_red_setup_failure(body))

    # --- _extract_regression_test_names ---

    def test_extract_go_test_function_name(self) -> None:
        names = quality_gate._extract_regression_test_names(
            _RUN1_REGRESSION_PATCH,
        )
        self.assertIn(
            "TestBuildPlannerQueryRelationFilterUsesEqualityConstraint",
            names,
        )

    def test_extract_pytest_test_function_name(self) -> None:
        patch = (
            "--- /dev/null\n+++ b/tests/test_x.py\n"
            "@@ -0,0 +1,3 @@\n"
            "+def test_something_specific(self):\n"
            "+    assert 1 == 0\n"
        )
        names = quality_gate._extract_regression_test_names(patch)
        self.assertIn("test_something_specific", names)

    def test_extract_returns_empty_on_unrecognized_patch(self) -> None:
        names = quality_gate._extract_regression_test_names(
            "--- /dev/null\n+++ b/x.txt\n+random content\n",
        )
        self.assertEqual(names, [])

    # --- _is_bare_package_run ---

    def test_run2_generic_go_test_is_bare(self) -> None:
        self.assertTrue(
            quality_gate._is_bare_package_run(_RUN2_GREEN_LOG),
            "run2 generic 'go test ./ketoapi' (no -run flag) must "
            "be classified as a bare whole-package run (Task B "
            "fallback regression anchor)",
        )

    def test_targeted_go_test_not_bare(self) -> None:
        self.assertFalse(
            quality_gate._is_bare_package_run(_RUN1_GREEN_LOG),
            "run1 'go test -run TestXxx ./pkg' has a targeted "
            "selector and is NOT a bare whole-package run",
        )

    def test_pytest_nodeid_not_bare(self) -> None:
        body = (
            "GREEN\nCommand: pytest tests/test_foo.py::test_bar\n"
            "Exit code: 0\n"
        )
        self.assertFalse(quality_gate._is_bare_package_run(body))


# ---------------------------------------------------------------------------
# Full-gate regression anchors — the load-bearing tests the
# instruction's Task C demands.
# ---------------------------------------------------------------------------


class Run2FixturesMustNotPassAsTDDProven090p(FixtureBase):
    """The run2 fixtures (setup-failed reds + identical generic
    greens) must NOT yield GATE PASSED / TDD-proven under 090p."""

    def _write_run2_fixture(self, bug_id: str = "BUG-001") -> None:
        tree = minimal_zero_bug_tree()
        add_one_bug(tree, bug_id=bug_id)
        # Overwrite the default red/green logs with the run2 shapes.
        tree[f"quality/results/{bug_id}.red.log"] = _RUN2_RED_LOG
        tree[f"quality/results/{bug_id}.green.log"] = _RUN2_GREEN_LOG
        # Provide a regression-test patch for the bug — Task B will
        # extract the test name and require both logs to reference it.
        tree[f"quality/patches/{bug_id}-regression-test.patch"] = (
            _RUN2_BUG002_REGRESSION_PATCH
        )
        self.write(tree)

    def test_run2_setup_failed_red_fails_gate(self) -> None:
        """Mutation bite: revert the setup-failure rejection (remove
        '[setup failed]' from `_RED_SETUP_FAILURE_SIGNATURES`) →
        the run2 setup-failed red is wrongly accepted → this test
        FAILs (the gate would pass on invalid TDD evidence).
        """
        self._write_run2_fixture()
        stdout, code = self.gate()
        self.assertNotEqual(
            code, 0,
            f"090p Task A regression anchor: the run2 '[setup "
            f"failed]' red must NOT yield GATE PASSED. exit={code}\n"
            f"stdout:\n{stdout}",
        )
        self.assertIn(
            "setup/dependency/build/collection failure", stdout,
            "expected 090p Task A failure message about setup-"
            "failure reds",
        )
        self.assertIn("090p", stdout)

    def test_run2_bare_package_green_flagged_when_no_test_names(
            self) -> None:
        """When the patch doesn't carry an extractable test name (the
        conservative-fallback path), the green's bare-package shape
        is the trigger. Use a regression-test patch with no recognized
        test-function pattern to force the fallback path."""
        tree = minimal_zero_bug_tree()
        add_one_bug(tree, bug_id="BUG-001")
        # Use a genuine RED (not setup-failed) so Task A doesn't
        # short-circuit Task B for this bug.
        tree["quality/results/BUG-001.red.log"] = (
            "RED\n"
            "Command: go test ./ketoapi\n"
            "Exit code: 1\n"
            "--- FAIL: TestSomething (0.01s)\n"
        )
        tree["quality/results/BUG-001.green.log"] = _RUN2_GREEN_LOG
        # Regression-test patch with no Go func / pytest def — forces
        # the conservative `_is_bare_package_run` fallback.
        tree["quality/patches/BUG-001-regression-test.patch"] = (
            "--- /dev/null\n+++ b/README.md\n@@ -0,0 +1,1 @@\n"
            "+regression-test placeholder\n"
        )
        self.write(tree)
        stdout, code = self.gate()
        self.assertNotEqual(
            code, 0,
            f"090p Task B fallback regression anchor: a bare "
            f"whole-package green must be flagged when no patch-"
            f"derived test name is available. exit={code}\n"
            f"stdout:\n{stdout}",
        )
        self.assertIn(
            "bare whole-package run", stdout,
            "expected 090p Task B fallback message about bare "
            "whole-package runs",
        )

    def test_run2_generic_green_flagged_when_patch_names_extracted(
            self) -> None:
        """The strong form of Task B (named-test tie via patch-derived
        names): when the regression-test patch carries a recognizable
        Go ``func TestXxx`` line, the red AND green logs must
        REFERENCE that test name. A generic ``go test ./ketoapi`` that
        doesn't mention ``TestBuildPlannerQuery…`` is rejected
        because the run could have passed for reasons unrelated to
        the bug.

        Fixture shape: a GENUINE red (assertion-failure with a
        ``--- FAIL: TestSomethingElse`` line — not the test the
        patch added, and not a setup failure) so Task A doesn't
        short-circuit + a generic-package green that doesn't
        reference the patch-added test name. This forces Task B's
        strong-form ``_red_log_references_test_name`` path to fire
        for BOTH the red (different test name) and green (no test
        name at all).

        Mutation bite: drop the named-test tie (remove the
        ``_red_log_references_test_name`` call from the gate) → the
        red/green get wrongly accepted → this test FAILs.
        """
        tree = minimal_zero_bug_tree()
        add_one_bug(tree, bug_id="BUG-001")
        # GENUINE red — has `--- FAIL: TestSomethingElse` so Task A
        # does NOT classify it as setup-failure. But the test that
        # ran (TestSomethingElse) is NOT the one the patch added
        # (TestBuildPlannerQuery…), so Task B's named-test-tie path
        # rejects it.
        tree["quality/results/BUG-001.red.log"] = (
            "RED\n"
            "Command: go test ./ketoapi\n"
            "Exit code: 1\n"
            "--- FAIL: TestSomethingElse (0.02s)\n"
            "    ketoapi_test.go:5: unrelated assertion failure\n"
            "FAIL\tgithub.com/ory/keto/ketoapi\t0.034s\n"
        )
        # Generic green from run2 — `go test ./ketoapi` with no
        # reference to the patch-added test name.
        tree["quality/results/BUG-001.green.log"] = _RUN2_GREEN_LOG
        # Regression-test patch that DOES carry an extractable Go
        # `func TestBuildPlannerQuery…` line.
        tree["quality/patches/BUG-001-regression-test.patch"] = (
            _RUN2_BUG002_REGRESSION_PATCH
        )
        self.write(tree)
        stdout, code = self.gate()
        self.assertNotEqual(
            code, 0,
            f"090p Task B strong-form regression anchor: a green "
            f"log that doesn't reference the patch-derived test "
            f"name must be rejected even when the red is genuine. "
            f"exit={code}\nstdout:\n{stdout}",
        )
        # The strong-form Task B failure message must mention the
        # patch-derived test name reference requirement.
        self.assertIn(
            "does not reference any patch-derived test name",
            stdout,
            f"expected the 090p Task B strong-form message about "
            f"patch-derived test names; got:\n{stdout}",
        )
        # And it must specifically cite TestBuildPlannerQuery… (the
        # name extracted from _RUN2_BUG002_REGRESSION_PATCH).
        self.assertIn(
            "TestBuildPlannerQueryRelationFilterUsesEqualityConstraint",
            stdout,
        )


class GenuineRun1ReceiptsStillPass090p(FixtureBase):
    """Conservative-direction pin: a genuine assertion-failure red
    + named-test green must still pass under 090p — the
    instruction's halt-condition is 'do not wrongly fail honest
    reds'."""

    def test_genuine_run1_red_green_passes(self) -> None:
        tree = minimal_zero_bug_tree()
        add_one_bug(tree, bug_id="BUG-001")
        tree["quality/results/BUG-001.red.log"] = _RUN1_RED_LOG
        tree["quality/results/BUG-001.green.log"] = _RUN1_GREEN_LOG
        tree["quality/patches/BUG-001-regression-test.patch"] = (
            _RUN1_REGRESSION_PATCH
        )
        self.write(tree)
        stdout, code = self.gate()
        self.assertEqual(
            code, 0,
            f"090p must NOT regress honest TDD receipts. The run1 "
            f"genuine '--- FAIL: TestBuildPlannerQuery...' red + "
            f"named-test green must still pass GATE PASSED.\n"
            f"exit={code}\nstdout:\n{stdout}",
        )

    def test_default_zero_bug_tree_passes(self) -> None:
        """Confirm 090p doesn't false-fire on the default zero-bug
        tree — no red/green logs to validate, nothing to reject."""
        tree = minimal_zero_bug_tree()
        self.write(tree)
        stdout, code = self.gate()
        self.assertEqual(
            code, 0,
            f"090p must not false-fire on zero-bug runs. "
            f"exit={code}\nstdout:\n{stdout}",
        )

    def test_default_one_bug_tree_passes(self) -> None:
        """Confirm 090p doesn't false-fire on the default one-bug
        fixture (synthetic 'Command: test' / 'Exit code: 1' logs;
        no patch test-name extractable; not a bare whole-package
        run by command-line shape)."""
        tree = minimal_zero_bug_tree()
        add_one_bug(tree, bug_id="BUG-001")
        self.write(tree)
        stdout, code = self.gate()
        self.assertEqual(
            code, 0,
            f"090p must not false-fire on the default one-bug "
            f"fixture. exit={code}\nstdout:\n{stdout}",
        )


if __name__ == "__main__":
    unittest.main()
