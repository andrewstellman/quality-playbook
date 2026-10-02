"""v1.6.1 [S] + [W] — parent-witness rule for per-phase subagents, and
the claims rules reference.

[S] Why: on 2026-05-16 a delegated run hand-wrote
``quality/results/quality-gate.log`` reading PASS while the real gate
failed, and the parent trusted it. v1.6.1 allows per-phase subagents
only if the PARENT re-runs the gate after every Phase 6 with
``qpb_gate_witness.py`` and stops on a mismatch. These tests pin:

  * the witness script's behaviour on a fabricated log (exit 1,
    ``MISMATCH``), a matching log (exit 0), and a missing log (exit 2);
  * the conditional rule text in SKILL.md (Mode A), the Claude agent
    file, the general agent file, and references/orchestrator_protocol.md;
  * the witness script ships in the install bundle.

[W] pins that references/claims_rules.md exists, carries its rules, and
is referenced from SKILL.md and the BUGS.md / writeup guidance.

Mutation-bite evidence (executed during v1.6.1 [S] development):
  M1: in qpb_gate_witness.main, replace ``if diffs:`` with
      ``if False:`` → test_fabricated_pass_log_is_mismatch FAILS
      (rc 0, no MISMATCH). Restored → PASS.
  M2: in SKILL.md, rename "Parent-witness rule" to "Subagent rule" →
      test_skill_md_mode_a_carries_conditional_rule FAILS. Restored →
      PASS.
  v1.6.1 [council-2] (each mutation run against this file, then
  restored):
  M3: ``if state_diff is not None:`` -> ``if False:`` -> 3 FAIL (shallow
      probe, sentinel-state, no-verdict-state log).
  M4: ``if total_without_warn(...) != ...:`` -> ``if False:`` -> 3 FAIL
      (edited FAIL / DECISION / CLEANUP count).
  M5: WARN-strip regex widened to also drop ``, N CLEANUP`` -> FAIL
      test_edited_cleanup_count_is_mismatch; widened to drop
      ``N DECISION`` -> FAIL test_edited_decision_count_is_mismatch.
  M6: log sentinel ignored (``log_state = None``) -> FAIL
      test_fabricated_sentinel_state_is_mismatch.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SKILL_DIR = _REPO / "plugins" / "quality-playbook" / "skills" / "quality-playbook"
_WITNESS = _SKILL_DIR / "scripts" / "qpb_gate_witness.py"
_GATE = _SKILL_DIR / "scripts" / "quality_gate.py"
_SKILL_MD = _REPO / "SKILL.md"
_AGENT_CLAUDE = _SKILL_DIR / "agents" / "quality-playbook-claude.agent.md"
_AGENT_GENERAL = _SKILL_DIR / "agents" / "quality-playbook.agent.md"
_ORCH = _REPO / "references" / "orchestrator_protocol.md"
_CLAIMS = _REPO / "references" / "claims_rules.md"
_PHASE2_GUIDE = _REPO / "references" / "phase2_generation_guide.md"

_FAKE_PASS_LOG = "Total: 0 FAIL, 0 WARN\nRESULT: GATE PASSED\nexit=0\n"


def _run_witness(target: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_WITNESS), str(target)],
        capture_output=True, text=True, timeout=600,
    )


def _make_target(tmp: Path) -> Path:
    """A minimal target whose real gate FAILs (empty quality/)."""
    target = tmp / "target"
    (target / "quality" / "results").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(target)], check=False,
                   capture_output=True)
    return target


def _slice(text: str, header: str, stop: str) -> str:
    start = text.index(header)
    end = text.find(stop, start + len(header))
    return text[start:] if end == -1 else text[start:end]


class GateWitnessScriptTests(unittest.TestCase):

    def test_fabricated_pass_log_is_mismatch(self) -> None:
        """Log claims RESULT: GATE PASSED; the real gate FAILs on this
        fixture → exit 1 with a MISMATCH line."""
        with tempfile.TemporaryDirectory() as td:
            target = _make_target(Path(td))
            log = target / "quality" / "results" / "quality-gate.log"
            log.write_text(_FAKE_PASS_LOG, encoding="utf-8")
            r = _run_witness(target)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("MISMATCH", r.stdout)
            self.assertIn("RESULT: GATE FAILED", r.stdout)
            # The witness must not rewrite the subagent's log.
            self.assertEqual(log.read_text(encoding="utf-8"), _FAKE_PASS_LOG)

    def test_matching_log_is_exit_0(self) -> None:
        """Log produced by the real gate (the phase6_auditor.md
        invocation form) → exit 0, MATCH."""
        with tempfile.TemporaryDirectory() as td:
            target = _make_target(Path(td))
            g = subprocess.run([sys.executable, str(_GATE), "."],
                               cwd=str(target), capture_output=True,
                               text=True, timeout=600)
            log = target / "quality" / "results" / "quality-gate.log"
            log.write_text(g.stdout + g.stderr + f"exit={g.returncode}\n",
                           encoding="utf-8")
            r = _run_witness(target)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("MATCH:", r.stdout)
            self.assertNotIn("MISMATCH", r.stdout)

    def test_missing_log_is_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = _make_target(Path(td))
            r = _run_witness(target)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("LOG MISSING", r.stdout)

    def test_verdict_lines_takes_last_occurrence(self) -> None:
        sys.path.insert(0, str(_WITNESS.parent))
        try:
            import qpb_gate_witness as w  # type: ignore[import]
        finally:
            sys.path.pop(0)
        text = ("Total: 9 FAIL, 0 WARN\nRESULT: GATE FAILED — 9\n"
                "noise\n  Total: 0 FAIL, 1 WARN\nRESULT: GATE PASSED\n")
        self.assertEqual(w.verdict_lines(text),
                         ("Total: 0 FAIL, 1 WARN", "RESULT: GATE PASSED"))
        self.assertEqual(w.verdict_lines("nothing"), (None, None))

    # v1.6.1 [council-1] (Council A1, B gaps 1-2).
    def _real_log(self, target: Path) -> str:
        g = subprocess.run([sys.executable, str(_GATE), "."],
                           cwd=str(target), capture_output=True,
                           text=True, timeout=600)
        text = g.stdout + g.stderr + f"exit={g.returncode}\n"
        (target / "quality" / "results" / "quality-gate.log").write_text(
            text, encoding="utf-8")
        return text

    def test_agents_md_written_after_log_is_match(self) -> None:
        """Council A1: the orchestrator writes AGENTS.md after the gate
        passes; that drops the WARN count by one. The witness must not
        report MISMATCH for it."""
        with tempfile.TemporaryDirectory() as td:
            target = _make_target(Path(td))
            log_text = self._real_log(target)
            self.assertIn("AGENTS.md not written yet", log_text)
            (target / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
            r = _run_witness(target)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("MATCH:", r.stdout)
            self.assertNotIn("MISMATCH", r.stdout)
            self.assertIn("the WARN count differs", r.stdout)
            # Both full Total: lines are still printed, and they differ.
            totals = [ln.strip() for ln in r.stdout.splitlines()
                      if ln.strip().startswith("Total:")]
            self.assertEqual(len(totals), 2, r.stdout)
            self.assertNotEqual(totals[0], totals[1])

    def test_copied_total_with_fabricated_result_is_mismatch(self) -> None:
        """Council B gap 1: a hand-written log that copies the real
        Total: line but claims RESULT: GATE PASSED (the 2026-05-16
        shape) is caught by the RESULT comparison alone."""
        with tempfile.TemporaryDirectory() as td:
            target = _make_target(Path(td))
            real = self._real_log(target)
            total = [ln for ln in real.splitlines()
                     if ln.startswith("Total:")][-1]
            log = target / "quality" / "results" / "quality-gate.log"
            log.write_text(f"{total}\nRESULT: GATE PASSED\nexit=0\n",
                           encoding="utf-8")
            r = _run_witness(target)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("MISMATCH: RESULT: line(s) differ", r.stdout)

    def test_gate_with_no_verdict_lines_is_mismatch(self) -> None:
        """Council B gap 2: the gate crashed or printed nothing ->
        exit 1 with the no-verdict MISMATCH, even if the log looks
        fine."""
        sys.path.insert(0, str(_WITNESS.parent))
        try:
            import qpb_gate_witness as w  # type: ignore[import]
        finally:
            sys.path.pop(0)
        import io
        from contextlib import redirect_stdout
        from unittest import mock
        with tempfile.TemporaryDirectory() as td:
            target = _make_target(Path(td))
            (target / "quality" / "results" / "quality-gate.log").write_text(
                _FAKE_PASS_LOG, encoding="utf-8")
            buf = io.StringIO()
            with mock.patch.object(w, "run_gate",
                                   return_value="Traceback: boom\n"), \
                    redirect_stdout(buf):
                rc = w.main([str(target)])
            self.assertEqual(rc, 1, buf.getvalue())
            self.assertIn("MISMATCH: the gate printed no Total:/RESULT: "
                          "verdict lines", buf.getvalue())

    def test_total_without_warn_keeps_fail_counts(self) -> None:
        sys.path.insert(0, str(_WITNESS.parent))
        try:
            import qpb_gate_witness as w  # type: ignore[import]
        finally:
            sys.path.pop(0)
        self.assertEqual(
            w.total_without_warn(
                "Total: 3 FAIL (1 substantive, 2 record-keeping), 7 WARN"),
            "Total: 3 FAIL (1 substantive, 2 record-keeping)")
        self.assertEqual(w.total_without_warn("Total: 1 DECISION, 8 WARN"),
                         "Total: 1 DECISION")
        self.assertNotEqual(w.total_without_warn("Total: 1 FAIL, 6 WARN"),
                            w.total_without_warn("Total: 2 FAIL, 6 WARN"))
        self.assertIsNone(w.total_without_warn(None))

    # v1.6.1 [council-2] (Council A-r2 N1, B-r2 should-fix).
    def _tree_target(self, td: str, tree: dict) -> Path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            from test_quality_gate_gates import write_tree
        finally:
            sys.path.pop(0)
        target = _make_target(Path(td))
        write_tree(target, tree)
        return target

    def _write_log(self, target: Path, text: str) -> None:
        (target / "quality" / "results" / "quality-gate.log").write_text(
            text, encoding="utf-8")

    @staticmethod
    def _zero_bug_tree() -> dict:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            from test_quality_gate_gates import minimal_zero_bug_tree
        finally:
            sys.path.pop(0)
        return minimal_zero_bug_tree()

    @staticmethod
    def _decisions_tree() -> dict:
        """Real gate: Total: 1 DECISION, 1 CLEANUP, N WARN (exit 0). The
        CLEANUP is the missing run-metadata file (record-keeping)."""
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            from test_gate_verdict_honesty_v161 import build_reproduced_tree
        finally:
            sys.path.pop(0)
        tree = build_reproduced_tree({"BUG-001": "REQ-001"}, ["REQ-003"])
        del tree["quality/results/run-2026-01-01T00-00-00.json"]
        return tree

    def test_shallow_pass_with_fabricated_solid_log_is_mismatch(self) -> None:
        """Council A-r2 N1 probe: the real gate passes but the run looks
        shallow (zero bugs, verdict_state "shallow"); a hand-written log
        claims a solid pass with 0 WARN. RESULT and the non-WARN Total
        counts agree, so only the verdict-state comparison catches it."""
        with tempfile.TemporaryDirectory() as td:
            target = self._tree_target(td, self._zero_bug_tree())
            self.assertIn('"verdict_state":"shallow"',
                          self._real_log(target))
            self._write_log(target, "[PASS] GATE PASSED\n"
                            "Total: 0 FAIL, 0 WARN\n"
                            "RESULT: GATE PASSED\nexit=0\n")
            r = _run_witness(target)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("MISMATCH: verdict state differs (lead line",
                          r.stdout)

    def test_fabricated_sentinel_state_is_mismatch(self) -> None:
        """A log that carries a ::QPB:: gate sentinel is judged on the
        sentinel's verdict_state (here "solid" vs the gate's "shallow")."""
        with tempfile.TemporaryDirectory() as td:
            target = self._tree_target(td, self._zero_bug_tree())
            real = self._real_log(target)
            self._write_log(target, real.replace(
                '"verdict_state":"shallow"', '"verdict_state":"solid"'))
            r = _run_witness(target)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("MISMATCH: verdict state differs (::QPB:: "
                          "gate_result/verdict_state", r.stdout)

    def test_shallow_agents_md_written_later_is_match(self) -> None:
        """AGENTS.md written after the log changes the WARN count only;
        the verdict state stays "shallow" -> MATCH, and the MATCH line
        does not claim WARNs never change the verdict."""
        with tempfile.TemporaryDirectory() as td:
            tree = self._zero_bug_tree()
            del tree["AGENTS.md"]
            target = self._tree_target(td, tree)
            self._real_log(target)
            (target / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
            r = _run_witness(target)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn(
                "MATCH: the WARN count differs, but the RESULT: line, the "
                "FAIL / DECISION / CLEANUP counts and the verdict state "
                "equal the gate's.", r.stdout)
            self.assertNotIn("do not change the verdict", r.stdout)

    def test_log_without_sentinel_matching_lead_line_is_match(self) -> None:
        """Pre-1.6.1 log shape (no ::QPB:: line): the lead line is the
        verdict state, and it matches -> MATCH."""
        with tempfile.TemporaryDirectory() as td:
            target = self._tree_target(td, self._zero_bug_tree())
            real = self._real_log(target)
            self._write_log(target, "\n".join(
                ln for ln in real.splitlines()
                if not ln.startswith("::QPB::")) + "\n")
            r = _run_witness(target)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("MATCH:", r.stdout)
            self.assertNotIn("MISMATCH", r.stdout)

    def test_log_without_sentinel_or_lead_line_is_mismatch(self) -> None:
        """Total: and RESULT: copied verbatim, but no verdict-state line
        at all -> the log cannot be witnessed."""
        with tempfile.TemporaryDirectory() as td:
            target = self._tree_target(td, self._zero_bug_tree())
            real = self._real_log(target)
            self._write_log(target, "\n".join(
                ln for ln in real.splitlines()
                if not ln.startswith(("::QPB::", "[PASS] GATE",
                                      "[WARN] GATE", "[FAIL] GATE")))
                + "\n")
            r = _run_witness(target)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("MISMATCH: quality-gate.log has no ::QPB:: gate "
                          "sentinel and no [PASS]/[WARN]/[FAIL] GATE lead "
                          "line, so its verdict state cannot be witnessed",
                          r.stdout)

    def _edited_total_is_mismatch(self, tree, old: str, new: str) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = (_make_target(Path(td)) if tree is None
                      else self._tree_target(td, tree))
            real = self._real_log(target)
            total = [ln for ln in real.splitlines()
                     if ln.startswith("Total:")][-1]
            self.assertIn(old, total)
            self._write_log(target, real.replace(
                total, total.replace(old, new, 1)))
            r = _run_witness(target)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("MISMATCH: Total: line(s) differ", r.stdout)

    def test_edited_fail_count_is_mismatch(self) -> None:
        """Council B-r2: only the FAIL count is edited (RESULT, lead line
        and sentinel untouched) -> MISMATCH on Total:."""
        with tempfile.TemporaryDirectory() as td:
            target = _make_target(Path(td))
            real = self._real_log(target)
        total = [ln for ln in real.splitlines() if ln.startswith("Total:")][-1]
        n_fail = total.split()[1]
        self._edited_total_is_mismatch(None, f"Total: {n_fail} FAIL",
                                       f"Total: {int(n_fail) + 1} FAIL")

    def test_edited_decision_count_is_mismatch(self) -> None:
        self._edited_total_is_mismatch(self._decisions_tree(),
                                       "1 DECISION,", "2 DECISION,")

    def test_edited_cleanup_count_is_mismatch(self) -> None:
        self._edited_total_is_mismatch(self._decisions_tree(),
                                       "1 CLEANUP,", "0 CLEANUP,")

    def test_witness_ships_in_install_bundle(self) -> None:
        from bin.install_skill import _bundle_files
        dests = {str(d) for _s, d in _bundle_files(_SKILL_DIR)}
        self.assertIn("bin/qpb_gate_witness.py", dests)


class ParentWitnessRuleTextTests(unittest.TestCase):
    """The conditional rule appears in every surface an orchestrating
    agent reads."""

    def _assert_rule(self, text: str, label: str) -> None:
        self.assertIn("parent-witness rule", text.lower(),
                      f"{label}: missing the parent-witness rule")
        self.assertIn("qpb_gate_witness.py", text,
                      f"{label}: must name the witness script")
        self.assertIn("MISMATCH", text,
                      f"{label}: must say to stop on MISMATCH")
        self.assertRegex(text.lower(), r"cannot spawn sub-?agents",
                         f"{label}: must carry the nesting rule")

    def test_skill_md_mode_a_carries_conditional_rule(self) -> None:
        mode_a = _slice(_SKILL_MD.read_text(encoding="utf-8"),
                        "### Mode A — skill-direct walkthrough (UI-context)",
                        "\n### Mode B —")
        self.assertIn("**Parent-witness rule (per-phase subagents).**", mode_a)
        self._assert_rule(mode_a, "SKILL.md Mode A")
        self.assertIn("2026-05-16", mode_a,
                      "the why-text must still cite the 2026-05-16 failure")

    def test_claude_agent_file_carries_conditional_rule(self) -> None:
        self._assert_rule(_AGENT_CLAUDE.read_text(encoding="utf-8"),
                          "quality-playbook-claude.agent.md")

    def test_general_agent_file_carries_conditional_rule(self) -> None:
        self._assert_rule(_AGENT_GENERAL.read_text(encoding="utf-8"),
                          "quality-playbook.agent.md")

    def test_orchestrator_protocol_carries_rule_in_phase6_gate(self) -> None:
        text = _ORCH.read_text(encoding="utf-8")
        self._assert_rule(text, "orchestrator_protocol.md")
        phase6 = _slice(text, "- **Phase 6 (Verify):**", "\n### ")
        self.assertIn("qpb_gate_witness.py", phase6,
                      "the witness run must be part of the Phase 6 "
                      "post-phase verification gate")
        self.assertIn("not required for the gate to pass", text,
                      "AGENTS.md must be described as written after the "
                      "gate passes and not required by it")

    def test_witness_runs_before_agents_md(self) -> None:
        """v1.6.1 [council-1] (Council A1): every surface that tells the
        parent to run the witness says to run it before AGENTS.md."""
        for path in (_AGENT_CLAUDE, _AGENT_GENERAL):
            self.assertIn("Run it before you write AGENTS.md.",
                          path.read_text(encoding="utf-8"), path.name)
        orch = _ORCH.read_text(encoding="utf-8")
        self.assertIn("Run the witness before you write AGENTS.md.", orch)
        self.assertIn("AFTER the parent's witness run", orch)

    def test_old_automation_only_ban_is_gone(self) -> None:
        for p in (_AGENT_CLAUDE, _AGENT_GENERAL, _SKILL_MD):
            text = p.read_text(encoding="utf-8")
            self.assertNotIn("AUTOMATION ONLY", text, str(p))
            self.assertNotIn(
                "DO NOT use this file for interactive coding sessions",
                text, str(p))


class ClaimsRulesTests(unittest.TestCase):

    def test_claims_rules_exists_with_rules(self) -> None:
        text = _CLAIMS.read_text(encoding="utf-8")
        for marker in ("Tangible", "Objective", "R1.", "R2.", "R3.",
                       "R6.", "R7.", "R8.", "Pre-output checklist",
                       "significantly", "ensure",
                       "supplied by Andrew Stellman (2026-10-01)"):
            self.assertIn(marker, text, marker)

    def test_claims_rules_referenced_from_skill_md_table(self) -> None:
        text = _SKILL_MD.read_text(encoding="utf-8")
        table = text[text.index("## Reference Files"):]
        self.assertIn("| `references/claims_rules.md` |", table)

    def test_claims_rules_referenced_from_bugs_and_writeup_guidance(self) -> None:
        text = _PHASE2_GUIDE.read_text(encoding="utf-8")
        self.assertIn(
            "Apply `references/claims_rules.md` before writing any "
            "BUGS.md entry.", text)
        self.assertIn(
            "Apply `references/claims_rules.md` before writing each "
            "writeup.", text)


if __name__ == "__main__":
    unittest.main()
