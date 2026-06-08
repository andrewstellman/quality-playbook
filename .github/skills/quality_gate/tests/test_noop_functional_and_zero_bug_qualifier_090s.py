"""v1.5.7 instruction 090s — gate: reject no-op / no-assertion
functional tests + loudly qualify a zero-bug verdict.

Motivated by the 2026-05-25 Ory Keto run4 (Copilot in VS Code auto-
mode = gpt-5.3-codex). The agent fabricated a hollow run that the
gate PASSED: hand-written generic EXPLORATION.md / REQUIREMENTS.md,
zero confirmed bugs, and a no-op functional test —
`quality/test_functional.go` was literally
``func TestFunctionalBaseline(t *testing.T) {}`` (empty body, no
assertions). The gate reported ``Total: 0 FAIL, 4 WARN → GATE
PASSED`` because (a) zero-bug satisfies every TDD/patch/writeup
check vacuously, and (b) the functional-test check only verified
the file exists and matches the language.

090s closes the two mechanically-catchable parts:

  Task A — `check_functional_test_has_assertions` FAILs when the
    functional test file's test functions are ALL trivial /
    no-assertion stubs. Conservative direction: a file with ≥1
    real assertion-bearing test passes; unrecognized languages
    pass-through.

  Task B — A zero-bug run's verdict is loudly qualified by a
    `NOTE:` line immediately after the RESULT: line, telling the
    operator to verify the run actually explored before trusting
    the PASS. Does NOT change pass/fail semantics.

Test surfaces:

  HelpersTests (unit) — `_go_test_function_bodies`,
    `_python_test_function_bodies`, `_body_has_real_assertion`
    for Go + Python + unrecognized lang.

  GateFunctionalTestContentTests (full-gate) — run4 regression
    anchors (empty Go test + `assertTrue(True)`-only Python test
    both FAIL); don't-over-fire pins (real assertions pass; mixed
    real+stub passes; unrecognized lang passes).

  ZeroBugVerdictQualifierTests (full-gate) — a zero-bug run emits
    the `NOTE:` qualifier in the gate output; a non-zero-bug run
    does NOT (no false-fire); pass/fail semantics unchanged.

  ScopeGuardTests — SKILL.md untouched.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))
from test_quality_gate import (  # noqa: E402
    minimal_zero_bug_tree,
    add_one_bug,
    write_tree,
    run_gate,
    quality_gate,
    FixtureBase,
)


# ---------------------------------------------------------------------------
# Run4 fixture shapes — the hollow functional tests that pre-090s
# passed the gate vacuously.
# ---------------------------------------------------------------------------

_RUN4_EMPTY_GO_TEST = """\
package quality

import "testing"

func TestFunctionalBaseline(t *testing.T) {
}
"""

_RUN4_TAUTOLOGY_PYTHON_TEST = """\
import unittest

class FunctionalBaselineTests(unittest.TestCase):
    def test_baseline(self):
        self.assertTrue(True)

    def test_another(self):
        assert True
"""

_REAL_GO_TEST = """\
package quality

import "testing"

func TestFunctionalBaseline(t *testing.T) {
\tif 1 + 1 != 2 {
\t\tt.Errorf("expected 2, got %d", 1+1)
\t}
}
"""

_REAL_PYTHON_TEST = """\
def test_baseline():
    result = compute(2, 3)
    assert result == 5

def test_another():
    assert "x" in {"x", "y"}
"""

_MIXED_GO_TEST = """\
package quality

import "testing"

func TestStub(t *testing.T) {
}

func TestReal(t *testing.T) {
\tif false {
\t\tt.Fatal("expected true")
\t}
}
"""


# ---------------------------------------------------------------------------
# Unit tests — helper functions in isolation.
# ---------------------------------------------------------------------------


class HelpersTests(unittest.TestCase):

    # --- _go_test_function_bodies ---

    def test_go_extract_single_empty_body(self) -> None:
        bodies = quality_gate._go_test_function_bodies(_RUN4_EMPTY_GO_TEST)
        self.assertEqual(len(bodies), 1)
        # Body should be empty/whitespace only.
        self.assertEqual(bodies[0].strip(), "")

    def test_go_extract_body_with_assertion(self) -> None:
        bodies = quality_gate._go_test_function_bodies(_REAL_GO_TEST)
        self.assertEqual(len(bodies), 1)
        self.assertIn("t.Errorf", bodies[0])

    def test_go_extract_two_test_functions(self) -> None:
        bodies = quality_gate._go_test_function_bodies(_MIXED_GO_TEST)
        self.assertEqual(len(bodies), 2)
        self.assertEqual(bodies[0].strip(), "")  # TestStub
        self.assertIn("t.Fatal", bodies[1])      # TestReal

    def test_go_extract_method_form_test(self) -> None:
        """`func (s *Suite) TestFoo(t *testing.T)` is a valid test
        shape (testify suites); the body extractor must handle it."""
        source = (
            "package x\n\n"
            "import \"testing\"\n\n"
            "func (s *Suite) TestSomething(t *testing.T) {\n"
            "\trequire.Equal(t, 1, 1)\n"
            "}\n"
        )
        bodies = quality_gate._go_test_function_bodies(source)
        self.assertEqual(len(bodies), 1)
        self.assertIn("require.Equal", bodies[0])

    def test_go_extract_handles_nested_braces(self) -> None:
        source = (
            "package x\n\n"
            "func TestNested(t *testing.T) {\n"
            "\tfor i := 0; i < 3; i++ {\n"
            "\t\tif i == 1 {\n"
            "\t\t\tt.Fatal(\"i=1\")\n"
            "\t\t}\n"
            "\t}\n"
            "}\n"
        )
        bodies = quality_gate._go_test_function_bodies(source)
        self.assertEqual(len(bodies), 1)
        self.assertIn("t.Fatal", bodies[0])
        # The braces are balanced; the extractor should have
        # captured everything up to the function's closing brace.
        self.assertIn("for i :=", bodies[0])

    # --- _python_test_function_bodies ---

    def test_python_extract_two_tautology_bodies(self) -> None:
        bodies = quality_gate._python_test_function_bodies(
            _RUN4_TAUTOLOGY_PYTHON_TEST,
        )
        self.assertEqual(len(bodies), 2)
        self.assertIn("self.assertTrue(True)", bodies[0])
        self.assertIn("assert True", bodies[1])

    def test_python_extract_two_real_bodies(self) -> None:
        bodies = quality_gate._python_test_function_bodies(_REAL_PYTHON_TEST)
        self.assertEqual(len(bodies), 2)
        self.assertIn("assert result == 5", bodies[0])
        self.assertIn('assert "x" in', bodies[1])

    # --- _body_has_real_assertion ---

    def test_go_empty_body_no_assertion(self) -> None:
        self.assertFalse(
            quality_gate._body_has_real_assertion("", "go"),
        )

    def test_go_t_errorf_is_assertion(self) -> None:
        self.assertTrue(
            quality_gate._body_has_real_assertion(
                "\tt.Errorf(\"oops\")\n", "go",
            ),
        )

    def test_go_require_is_assertion(self) -> None:
        self.assertTrue(
            quality_gate._body_has_real_assertion(
                "\trequire.Equal(t, 1, 1)\n", "go",
            ),
        )

    def test_python_assert_true_is_tautology(self) -> None:
        """`assert True` is stripped before the real-assertion
        scan; counts as trivial."""
        self.assertFalse(
            quality_gate._body_has_real_assertion(
                "    assert True\n", "py",
            ),
        )

    def test_python_assert_true_via_self_is_tautology(self) -> None:
        self.assertFalse(
            quality_gate._body_has_real_assertion(
                "    self.assertTrue(True)\n", "py",
            ),
        )

    def test_python_assert_equal_tautology(self) -> None:
        self.assertFalse(
            quality_gate._body_has_real_assertion(
                "    self.assertEqual(1, 1)\n", "py",
            ),
        )

    def test_python_real_assert_passes(self) -> None:
        self.assertTrue(
            quality_gate._body_has_real_assertion(
                "    assert result == 5\n", "py",
            ),
        )

    def test_python_real_unittest_assert_passes(self) -> None:
        self.assertTrue(
            quality_gate._body_has_real_assertion(
                "    self.assertEqual(result, expected)\n", "py",
            ),
        )

    def test_python_pytest_raises_passes(self) -> None:
        self.assertTrue(
            quality_gate._body_has_real_assertion(
                "    with pytest.raises(ValueError):\n"
                "        do_thing()\n",
                "py",
            ),
        )

    def test_unrecognized_language_passes_through(self) -> None:
        """Conservative direction: unrecognized language returns
        True (pass-through) — don't over-fire on shapes the
        detector doesn't know."""
        self.assertTrue(
            quality_gate._body_has_real_assertion(
                "(some non-go-non-python content)", "rb",
            ),
        )


# ---------------------------------------------------------------------------
# Full-gate regression anchors — Task A (no-op detection).
# ---------------------------------------------------------------------------


class GateFunctionalTestContentTests(FixtureBase):

    def _make_tree_with_func_test(self, content: str, ext: str = "go",
                                  add_bug: bool = True) -> dict:
        """Construct a one-bug tree with the given functional-test
        content + extension. ``add_bug=False`` produces a zero-bug
        tree (for the zero-bug-qualifier tests)."""
        tree = minimal_zero_bug_tree()
        if add_bug:
            add_one_bug(tree, bug_id="BUG-001")
        # The minimal tree includes a .py functional test by default —
        # remove it and add our shape.
        for canonical in ("quality/test_functional.py",
                          "quality/test_functional.go"):
            tree.pop(canonical, None)
        tree[f"quality/test_functional.{ext}"] = content
        # PROGRESS.md must show 6 phases — borrow the standard form.
        tree["quality/PROGRESS.md"] = (
            "# Progress\n\nSkill version: 1.4.4\n\n"
            "## Phases\n- [x] Phase 1\n- [x] Phase 2\n- [x] Phase 3\n"
            "- [x] Phase 4\n- [x] Phase 5\n- [x] Phase 6\n"
            "## Terminal Gate Verification\n"
        )
        # Make detect_project_language find Go. The default tree
        # only has main.py (Python); add a Go file for the Go
        # fixtures so the language detector picks Go.
        if ext == "go":
            tree["main.go"] = "package main\nfunc main() {}\n"
            tree.pop("main.py", None)
            # Also swap the inherited Python regression test for a
            # Go one so the existing test-file-extension check
            # doesn't fire on the language mismatch, AND so the
            # patches check finds the test_regression.* artifact
            # (both unrelated to 090s).
            tree.pop("quality/test_regression.py", None)
            tree["quality/test_regression.go"] = "package quality\n"
            tree["quality/test_regression_test.go"] = (
                "package quality\n"
            )
        return tree

    def test_run4_empty_go_test_fails_gate(self) -> None:
        """v1.5.7 090s Task A regression anchor: the exact run4
        shape — an empty `TestFunctionalBaseline` Go test — must
        FAIL the gate.

        Mutation bite: revert the `check_functional_test_has_
        assertions` registration in check_repo OR change the
        all-trivial detection to accept the empty body → this test
        FAILs because the gate exits 0 on the hollow shape.
        """
        tree = self._make_tree_with_func_test(_RUN4_EMPTY_GO_TEST, "go")
        self.write(tree)
        stdout, code = self.gate()
        self.assertNotEqual(
            code, 0,
            f"v1.5.7 090s: the run4 empty `TestFunctionalBaseline` "
            f"Go test must FAIL the gate. exit={code}\n"
            f"stdout:\n{stdout}",
        )
        self.assertIn(
            "trivial / no-assertion stubs", stdout,
            "expected 090s Task A failure message",
        )
        self.assertIn("090s", stdout)

    def test_run4_tautology_python_test_fails_gate(self) -> None:
        """The Python variant: all test functions are
        `assertTrue(True)` / `assert True` tautologies → FAIL."""
        tree = self._make_tree_with_func_test(
            _RUN4_TAUTOLOGY_PYTHON_TEST, "py",
        )
        self.write(tree)
        stdout, code = self.gate()
        self.assertNotEqual(code, 0)
        self.assertIn("trivial / no-assertion stubs", stdout)

    def test_real_go_test_passes_gate(self) -> None:
        """Don't-over-fire pin: a real Go functional test with an
        actual `t.Errorf` assertion must PASS."""
        tree = self._make_tree_with_func_test(_REAL_GO_TEST, "go")
        self.write(tree)
        stdout, code = self.gate()
        self.assertEqual(
            code, 0,
            f"v1.5.7 090s must NOT over-fire on legitimate test "
            f"files. A real `t.Errorf` Go test must PASS. exit={code}\n"
            f"stdout:\n{stdout}",
        )
        self.assertIn("carry real assertions", stdout)

    def test_real_python_test_passes_gate(self) -> None:
        tree = self._make_tree_with_func_test(_REAL_PYTHON_TEST, "py")
        self.write(tree)
        stdout, code = self.gate()
        self.assertEqual(code, 0)

    def test_mixed_stub_plus_real_passes_gate(self) -> None:
        """Conservative direction: a file with ≥1 real
        assertion-bearing test PASSES, even if other tests in the
        same file are stubs."""
        tree = self._make_tree_with_func_test(_MIXED_GO_TEST, "go")
        self.write(tree)
        stdout, code = self.gate()
        self.assertEqual(
            code, 0,
            f"v1.5.7 090s conservative-direction pin: a file with "
            f"≥1 real assertion-bearing test must PASS even if other "
            f"tests in the same file are stubs. exit={code}\n"
            f"stdout:\n{stdout}",
        )
        # Should report "1 of 2 test function(s) carry real
        # assertions" or similar.
        self.assertIn("of 2 test function(s) carry real assertions",
                      stdout)

    def test_unrecognized_language_passes_through(self) -> None:
        """A test file in an unrecognized language → INFO
        (pass-through), no FAIL."""
        # The default minimal tree's `test_functional.py` is a
        # `# test\n` comment — no test functions; my updated check
        # emits a WARN not a FAIL for that case.
        tree = minimal_zero_bug_tree()
        add_one_bug(tree, bug_id="BUG-001")
        # Use an unrecognized extension. detect_project_language
        # falls back; the 090s check pass-through covers the
        # extension mismatch.
        tree.pop("quality/test_functional.py", None)
        tree["quality/test_functional.rb"] = (
            "describe 'something' do\n"
            "  it 'works' do\n"
            "    expect(1).to eq(1)\n"
            "  end\n"
            "end\n"
        )
        tree["quality/PROGRESS.md"] = (
            "# Progress\n\nSkill version: 1.4.4\n\n"
            "## Phases\n- [x] Phase 1\n- [x] Phase 2\n- [x] Phase 3\n"
            "- [x] Phase 4\n- [x] Phase 5\n- [x] Phase 6\n"
            "## Terminal Gate Verification\n"
        )
        self.write(tree)
        stdout, code = self.gate()
        # The unrecognized lang itself doesn't fail the 090s check,
        # but the test_file_extension check may fail for other
        # reasons (project language mismatch). What matters is the
        # 090s pass-through message:
        self.assertIn(
            "not in the 090s no-op detection set", stdout,
            "expected 090s pass-through for unrecognized language",
        )

    def test_no_test_functions_warns_not_fails(self) -> None:
        """Conservative pin: a file with no `def test_*` /
        `func Test*` patterns is a different shape from
        all-trivial. WARN (not FAIL) — adopters with helper-only
        files / non-canonical shapes shouldn't be wrongly failed.
        """
        tree = self._make_tree_with_func_test(
            "package quality\n// no tests here\n",
            "go",
        )
        self.write(tree)
        stdout, code = self.gate()
        # WARN is allowed; FAIL is not.
        self.assertEqual(
            code, 0,
            f"v1.5.7 090s: a file with no test functions must WARN "
            f"not FAIL (different shape from all-trivial). "
            f"exit={code}\nstdout:\n{stdout}",
        )
        self.assertIn("no test functions found", stdout)


# ---------------------------------------------------------------------------
# Full-gate Task B — zero-bug verdict qualifier.
# ---------------------------------------------------------------------------


class ZeroBugVerdictQualifierTests(FixtureBase):

    def test_zero_bug_run_emits_qualifier(self) -> None:
        """v1.5.7 090s Task B: a zero-bug run's verdict is loudly
        qualified by a `NOTE:` line after RESULT:.

        Mutation bite: remove the `_ZERO_BUG_REPOS` tracking or the
        post-verdict NOTE: emission → this test FAILs because the
        qualifier line doesn't appear.
        """
        tree = minimal_zero_bug_tree()
        # No add_one_bug — zero-bug run.
        tree["quality/PROGRESS.md"] = (
            "# Progress\n\nSkill version: 1.4.4\n\n"
            "## Phases\n- [x] Phase 1\n- [x] Phase 2\n- [x] Phase 3\n"
            "- [x] Phase 4\n- [x] Phase 5\n- [x] Phase 6\n"
            "## Terminal Gate Verification\n"
        )
        self.write(tree)
        stdout, code = self.gate()
        self.assertEqual(
            code, 0,
            f"v1.5.7 090s: a zero-bug run's pass/fail semantics are "
            f"UNCHANGED — the qualifier is additive. exit={code}",
        )
        # The NOTE: qualifier line must appear with the canonical
        # framing.
        self.assertIn("ZERO confirmed bugs", stdout)
        self.assertIn("hollow / shallow run", stdout)
        self.assertIn("Ory Keto run4", stdout)
        self.assertIn("090s", stdout)

    def test_one_bug_run_does_not_emit_qualifier(self) -> None:
        """Don't-over-fire pin: a run with confirmed bugs does NOT
        emit the zero-bug qualifier."""
        tree = minimal_zero_bug_tree()
        add_one_bug(tree, bug_id="BUG-001")
        tree["quality/PROGRESS.md"] = (
            "# Progress\n\nSkill version: 1.4.4\n\n"
            "## Phases\n- [x] Phase 1\n- [x] Phase 2\n- [x] Phase 3\n"
            "- [x] Phase 4\n- [x] Phase 5\n- [x] Phase 6\n"
            "## Terminal Gate Verification\n"
        )
        self.write(tree)
        stdout, code = self.gate()
        self.assertEqual(code, 0)
        self.assertNotIn(
            "ZERO confirmed bugs", stdout,
            "the zero-bug qualifier must NOT fire on a run with "
            "confirmed bugs",
        )

    def test_zero_bug_qualifier_preserves_pass_fail_semantics(
            self) -> None:
        """The RESULT: line strings remain load-bearing — they MUST
        NOT be modified by the 090s qualifier addition. A zero-bug
        run that otherwise passes still emits the canonical
        `RESULT: GATE PASSED` string."""
        tree = minimal_zero_bug_tree()
        tree["quality/PROGRESS.md"] = (
            "# Progress\n\nSkill version: 1.4.4\n\n"
            "## Phases\n- [x] Phase 1\n- [x] Phase 2\n- [x] Phase 3\n"
            "- [x] Phase 4\n- [x] Phase 5\n- [x] Phase 6\n"
            "## Terminal Gate Verification\n"
        )
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("RESULT: GATE PASSED", stdout)
        # And it's a real PASS — pass/fail unchanged.
        self.assertEqual(code, 0)


# ---------------------------------------------------------------------------
# Scope guard.
# ---------------------------------------------------------------------------


class ScopeGuard090sTests(unittest.TestCase):

    def test_skill_md_not_touched_by_090s(self) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        text = (repo_root / "skills" / "quality-playbook" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "v1.5.7 090s", text,
            "SKILL.md must not carry 090s anchors (32K BPE ceiling).",
        )


if __name__ == "__main__":
    unittest.main()
