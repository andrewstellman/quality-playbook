"""v1.5.7 097 Task B — real-gate integration test.

The pre-097 fact-extraction tests used hand-written canonical
stdout fixtures. Fixture drift risk: if the gate's verdict-
block strings change and the canonical fixtures don't, the
harness silently mis-extracts facts on real runs — and the
harness IS the acceptance oracle.

This test runs the **actual** ``quality_gate.py`` over real
``quality/`` artifact trees (one per verdict state) and asserts
the extracted ``RunFacts`` match the expected shape, including
the new 097 ``substantive_fail_count`` / ``record_keeping_fail_
count`` fields. End-to-end via:

  1. ``install_skill.install(...)`` writes the run's OWN
     installed gate into a temp target.
  2. Build a fixture ``quality/`` tree for each of the four
     verdict states (solid / shallow / cleanup / failed).
  3. ``rerun_installed_gate(target, axes=...)`` runs the gate.
  4. ``parse_gate_stdout`` extracts the facts.
  5. Assertions pin gate_result + verdict_state + attribution
     + the new substantive/rk counts + the env-set provenance
     runner line.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from bin.harness import facts as F
from bin.harness import schema as S


_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / ".github" / "skills"
                        / "quality_gate" / "tests"))
# Reuse the canonical fixture builders from the gate test suite.
from test_quality_gate import (  # noqa: E402
    minimal_zero_bug_tree,
    add_one_bug,
    write_tree,
)


def _mk_axes(runner: S.Runner = S.Runner.CLAUDE) -> S.RunAxes:
    return S.RunAxes(
        runner=runner, mode=S.Mode.A,
        install_channel=S.InstallChannel.CLONE,
        model="test-model",
    )


_REAL_PY_FUNCTIONAL_TEST = """\
import unittest

class FunctionalTests(unittest.TestCase):
    def test_thing(self):
        self.assertEqual(1 + 1, 2)
"""


def _install_skill_into(target: Path) -> None:
    """Install the QPB skill into ``target`` via the same path
    `bin.install_skill.install` uses in production. The installed
    quality_gate.py is what `rerun_installed_gate` will execute."""
    from bin import install_skill
    install_skill.install(into=target, ai_tool="claude",
                            no_smoke=True)


def _populate_solid_tree(target: Path) -> None:
    """A solid ✅ PASS: one confirmed bug + real assertion-bearing
    functional test + complete TDD evidence."""
    tree = minimal_zero_bug_tree()
    add_one_bug(tree, bug_id="BUG-001")
    tree["quality/test_functional.py"] = _REAL_PY_FUNCTIONAL_TEST
    tree["quality/PROGRESS.md"] = (
        "# Progress\n\nSkill version: 1.4.4\n\n"
        "## Phases\n- [x] Phase 1\n- [x] Phase 2\n- [x] Phase 3\n"
        "- [x] Phase 4\n- [x] Phase 5\n- [x] Phase 6\n"
        "## Terminal Gate Verification\n"
    )
    write_tree(target, tree)


def _populate_shallow_tree(target: Path) -> None:
    """A shallow ⚠️ PASS: zero bugs + real-assertion functional
    test (so 090s doesn't FAIL) — drives the zero-bug shallow
    signal."""
    tree = minimal_zero_bug_tree()
    tree["quality/test_functional.py"] = _REAL_PY_FUNCTIONAL_TEST
    tree["quality/PROGRESS.md"] = (
        "# Progress\n\nSkill version: 1.4.4\n\n"
        "## Phases\n- [x] Phase 1\n- [x] Phase 2\n- [x] Phase 3\n"
        "- [x] Phase 4\n- [x] Phase 5\n- [x] Phase 6\n"
        "## Terminal Gate Verification\n"
    )
    write_tree(target, tree)


def _populate_failed_tree(target: Path) -> None:
    """A ❌ FAILED run: BUG-001 present in BUGS.md but no TDD
    artifacts (the 090x bugs_unverified shape). Drives multiple
    substantive FAILs."""
    tree = minimal_zero_bug_tree()
    tree["quality/BUGS.md"] = (
        "# Bugs\n\n### BUG-001: Example\nDescription.\n"
    )
    tree["quality/test_functional.py"] = _REAL_PY_FUNCTIONAL_TEST
    tree["quality/PROGRESS.md"] = (
        "# Progress\n\nSkill version: 1.4.4\n\n"
        "## Phases\n- [x] Phase 1\n- [x] Phase 2\n- [x] Phase 3\n"
        "- [x] Phase 4\n- [x] Phase 5\n- [x] Phase 6\n"
        "## Terminal Gate Verification\n"
    )
    write_tree(target, tree)


class RealGateIntegrationTests(unittest.TestCase):
    """v1.5.7 097 Task B: run the actual gate over real fixture
    trees and assert the extracted RunFacts.

    These tests are slower than the parse-fixture tests because
    they spawn a real subprocess + install the skill (~3s each).
    They land in the segregated harness suite so they're CI'd
    but don't block the release gate (Implementation Plan §4).
    """

    def _run_gate_extract_facts(
            self, populate_fn, *,
            runner: S.Runner = S.Runner.CLAUDE):
        """Common helper: build a fixture tree, install the
        gate, re-run it, return (gate_facts, verdict_facts,
        provenance_facts, stdout)."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            # Build the tree FIRST (some files like
            # quality/test_functional.py live at target root),
            # then install the skill on top (it adds
            # .claude/skills/quality-playbook/ etc.).
            populate_fn(target)
            (target / ".github").mkdir(exist_ok=True)
            _install_skill_into(target)
            axes = _mk_axes(runner=runner)
            stdout = F.rerun_installed_gate(
                target, axes=axes, timeout_s=60.0,
            )
            gate, verdict, prov = F.parse_gate_stdout(stdout)
            return gate, verdict, prov, stdout

    def test_solid_run_extracts_solid_facts(self) -> None:
        """A one-bug clean run → gate_result=PASS,
        verdict_state=solid, attribution=none,
        substantive_fail_count=0, record_keeping_fail_count=0."""
        gate, verdict, _prov, stdout = self._run_gate_extract_facts(
            _populate_solid_tree,
        )
        self.assertEqual(
            gate.gate_result, S.GateResult.PASS,
            f"v1.5.7 097 Task B: solid tree → PASS. "
            f"stdout tail:\n{stdout[-500:]}",
        )
        self.assertEqual(gate.substantive_fail_count, 0)
        self.assertEqual(gate.record_keeping_fail_count, 0)
        self.assertEqual(verdict.verdict_state, S.VerdictState.SOLID)
        self.assertEqual(verdict.attribution, S.Attribution.NONE)

    def test_shallow_run_extracts_shallow_facts(self) -> None:
        """A zero-bug PASS → gate_result=PASS,
        verdict_state=shallow, substantive_fail_count=0."""
        gate, verdict, _prov, _stdout = self._run_gate_extract_facts(
            _populate_shallow_tree,
        )
        self.assertEqual(gate.gate_result, S.GateResult.PASS)
        self.assertEqual(gate.substantive_fail_count, 0)
        self.assertEqual(verdict.verdict_state, S.VerdictState.SHALLOW)

    def test_failed_run_extracts_failed_facts_with_counts(
            self) -> None:
        """A bugs-unverified shape → gate_result=FAIL,
        verdict_state=failed, substantive_fail_count > 0.
        Pins that the count is parsed from the gate's own
        ``Total: N FAIL (M substantive, K record-keeping)``
        line — the 097 de-circularization contract."""
        gate, verdict, _prov, stdout = self._run_gate_extract_facts(
            _populate_failed_tree,
        )
        self.assertEqual(
            gate.gate_result, S.GateResult.FAIL,
            f"v1.5.7 097: bugs-unverified shape FAILs. "
            f"stdout tail:\n{stdout[-500:]}",
        )
        self.assertGreater(
            gate.substantive_fail_count, 0,
            f"v1.5.7 097 Task B: a failing run must carry a "
            f"non-zero substantive_fail_count parsed from the "
            f"Total: line. Got "
            f"{gate.substantive_fail_count}.\n"
            f"gate_total={gate.gate_total}",
        )
        self.assertEqual(verdict.verdict_state, S.VerdictState.FAILED)

    def test_real_gate_provenance_runner_with_env_set(self) -> None:
        """The provenance runner line surfaces the env-set vendor
        marker. With axes.runner=CLAUDE, the harness sets
        CLAUDECODE=1 before re-running the gate; the rendered
        ``Runner: claude-code (detected …)`` line is what
        parse_gate_stdout picks up.

        Mutation bite: drop the env clear-and-set in
        ``rerun_installed_gate`` → provenance.detected_runner
        falls back to the harness's own env (test runner) →
        this test FAILs because detected_runner is no longer
        'claude-code'."""
        _gate, _verdict, prov, stdout = self._run_gate_extract_facts(
            _populate_solid_tree, runner=S.Runner.CLAUDE,
        )
        self.assertEqual(
            prov.detected_runner, "claude-code",
            f"v1.5.7 097 Task B: with axes.runner=CLAUDE the "
            f"installed gate's provenance line must report "
            f"detected_runner=claude-code. Got "
            f"{prov.detected_runner!r}.\n"
            f"stdout tail:\n{stdout[-1000:]}",
        )
        # And the canonical "── Run provenance ──" header
        # appears (load-bearing 090w pin re-checked on real
        # output).
        self.assertIn("── Run provenance ──", stdout)
        self.assertIn("(detected from environment)", stdout)

    def test_real_gate_provenance_codex_env(self) -> None:
        """Same as above for CODEX axis — pins that the env
        is RE-SET per-runner (the gate's
        ``_RUNNER_ENV_MARKERS`` keys off CODEX_THREAD_ID)."""
        _gate, _verdict, prov, _stdout = self._run_gate_extract_facts(
            _populate_solid_tree, runner=S.Runner.CODEX,
        )
        self.assertEqual(prov.detected_runner, "codex")

    def test_substantive_count_zero_on_clean_pass(self) -> None:
        """A clean PASS (Total: 0 FAIL, M WARN) has both counts
        == 0 — the 097 parser falls back to 0 when the Total
        line has no substantive/record-keeping breakdown."""
        gate, _v, _p, _s = self._run_gate_extract_facts(
            _populate_solid_tree,
        )
        self.assertEqual(gate.substantive_fail_count, 0)
        self.assertEqual(gate.record_keeping_fail_count, 0)


if __name__ == "__main__":
    unittest.main()
