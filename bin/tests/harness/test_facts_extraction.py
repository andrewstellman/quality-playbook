"""v1.5.7 091 — two-sourced fact extraction tests.

Covers ``bin/harness/facts.py``:

  * ``parse_gate_stdout`` — pins the 090v/090w/090x verdict-block
    parsing against the canonical gate output (a fixture stdout
    captured from the actual gate format, NOT a re-implementation).
  * ``parse_transcript`` — pins the live-behavior heuristics
    (phase0_first_probe, banner_rendered,
    gitignore_remediation_followed, blocked/stop_reason).
  * ``find_installed_gate`` — locates the run's OWN installed gate
    under the canonical marker directories.
  * ``rerun_installed_gate`` — end-to-end re-run of an installed
    gate, verifying the harness sets the vendor env var and the
    re-run's stdout matches the run's original verdict (the
    load-bearing two-sourced guarantee).

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bin.harness import facts as F
from bin.harness import schema as S


REPO_ROOT = Path(__file__).resolve().parents[3]


def _mk_axes(runner: S.Runner = S.Runner.CLAUDE,
             channel: S.InstallChannel = S.InstallChannel.CLONE,
             model: str = "test-model") -> S.RunAxes:
    return S.RunAxes(
        runner=runner, mode=S.Mode.A,
        install_channel=channel, model=model,
    )


# ---------------------------------------------------------------------------
# parse_gate_stdout — the 090v/090w/090x string pinning
# ---------------------------------------------------------------------------


# Canonical gate stdout fixture. This is what the 090v + 090w + 090x
# verdict block emits for a shallow PASS with provenance + a benign
# WARN — taken straight from the gate's own format, so a future
# format change (e.g. someone reformats the verdict block) would
# show up here as a fact-parse regression.
_CANONICAL_SHALLOW_STDOUT = """\
=== Quality Gate — Post-Run Validation ===
Version:    1.5.7
Strictness: benchmark
Repos:      1

=== testproj ===
[Functional Test Content]
  WARN: test_functional.py: no test functions found

===========================================
Total: 0 FAIL, 1 WARN
RESULT: GATE PASSED

─── Operator Verdict ──────────────────────
⚠️ GATE PASSED — but this run looks shallow

This run looks shallow: 1 repo (testproj) found ZERO confirmed bugs. \
A clean codebase can legitimately have zero bugs, but a hollow / shallow \
run also produces zero bugs (the 2026-05-25 Ory Keto run4 shape — a \
fabricated EXPLORATION.md + a no-op functional test + no bugs). (v1.5.7 \
090s detection + 090v narration.)

── Run provenance ──
  Runner:  claude-code (detected from environment)
  Model:   opus (self-reported by the agent — not verified)
  Bugs:    0 found (gate-counted)
───────────────────────────────────────────
"""


_CANONICAL_NATS_RUN2_MISMATCH_STDOUT = """\
=== Quality Gate ===
Total: 0 FAIL, 0 WARN
RESULT: GATE PASSED

─── Operator Verdict ──────────────────────
⚠️ GATE PASSED — but this run looks shallow

This run looks shallow: …

── Run provenance ──
  Runner:  codex (detected from environment)
  Model:   gpt-5.2 (self-reported by the agent — not verified)
  Bugs:    3 found (gate-counted)   [run-metadata self-reported: 0 — mismatch; run metadata was not updated]
───────────────────────────────────────────
"""


_CANONICAL_BUGS_UNVERIFIED_STDOUT = """\
===========================================
Total: 3 FAIL (3 substantive, 0 record-keeping), 0 WARN
RESULT: GATE FAILED — 3 substantive issue(s) must be fixed

─── Operator Verdict ──────────────────────
❌ GATE FAILED

Why it failed:
  • [bugs_unverified] (3 FAILs)
    This run found bug(s) but didn't verify them — there's no \
TDD proof.

── Run provenance ──
  Runner:  codex (detected from environment)
  Model:   gpt-5.4 (self-reported by the agent — not verified)
  Bugs:    3 found (gate-counted)
───────────────────────────────────────────
"""


class ParseGateStdoutTests(unittest.TestCase):

    def test_shallow_pass_with_provenance(self) -> None:
        gate, verdict, prov = F.parse_gate_stdout(
            _CANONICAL_SHALLOW_STDOUT,
        )
        self.assertEqual(gate.gate_result, S.GateResult.PASS)
        self.assertIn("Total: 0 FAIL, 1 WARN", gate.gate_total)
        self.assertEqual(verdict.verdict_state, S.VerdictState.SHALLOW)
        self.assertEqual(verdict.attribution, S.Attribution.NONE)
        self.assertFalse(verdict.recommends_stronger_model)
        self.assertFalse(verdict.bugs_unverified_present)
        self.assertEqual(prov.detected_runner, "claude-code")
        self.assertEqual(prov.selfreport_model_label, "opus")
        self.assertEqual(prov.gate_bug_count, 0)
        self.assertIsNone(prov.reported_bug_count)
        self.assertFalse(prov.provenance_mismatch)

    def test_nats_run2_mismatch_provenance(self) -> None:
        """The 090w regression anchor: gate 3 vs self-reported 0
        → ``provenance_mismatch=True`` AND both counts captured."""
        _gate, _verdict, prov = F.parse_gate_stdout(
            _CANONICAL_NATS_RUN2_MISMATCH_STDOUT,
        )
        self.assertTrue(prov.provenance_mismatch)
        self.assertEqual(prov.gate_bug_count, 3)
        self.assertEqual(prov.reported_bug_count, 0)

    def test_bugs_unverified_failure(self) -> None:
        """090x bugs_unverified shape → ``❌ failed`` lead +
        ``attribution=incomplete_verification`` +
        ``bugs_unverified_present=True``."""
        gate, verdict, _prov = F.parse_gate_stdout(
            _CANONICAL_BUGS_UNVERIFIED_STDOUT,
        )
        self.assertEqual(gate.gate_result, S.GateResult.FAIL)
        self.assertEqual(verdict.verdict_state, S.VerdictState.FAILED)
        self.assertEqual(verdict.attribution,
                         S.Attribution.INCOMPLETE_VERIFICATION)
        self.assertTrue(verdict.bugs_unverified_present)

    def test_unrecognized_stdout_raises_factserror(self) -> None:
        """A stdout that doesn't carry the canonical Total: /
        RESULT: lines is a re-run-of-the-wrong-gate signal —
        ``FactsError`` rather than silent garbage."""
        with self.assertRaises(F.FactsError):
            F.parse_gate_stdout("not a gate stdout")


# ---------------------------------------------------------------------------
# parse_transcript — the live-behavior heuristics
# ---------------------------------------------------------------------------


class ParseTranscriptTests(unittest.TestCase):

    def test_phase0_first_probe_on_clean_run(self) -> None:
        transcript = (
            "Some agent prose...\n"
            "event=validation_complete status=ok\n"
            "Continuing with phase 1...\n"
        )
        phase0, install, blocked, stop = F.parse_transcript(transcript)
        self.assertEqual(phase0.status, "ok")
        self.assertEqual(phase0.probe_attempts, 1)
        self.assertTrue(phase0.first_probe_ok)
        self.assertFalse(blocked)
        self.assertIsNone(stop)

    def test_phase0_bare_path_failure_disables_first_probe(
            self) -> None:
        """090t regression: a bare ``python3 bin/qpb_validate.py``
        from repo root fails on a channel install, and the agent
        retries from the install root. ``first_probe_ok=False``
        even when the final attempt succeeds."""
        transcript = (
            "$ python3 bin/qpb_validate.py .\n"
            "[Errno 2] No such file or directory: "
            "'bin/qpb_validate.py'\n"
            "$ python3 .github/skills/quality-playbook/bin/"
            "qpb_validate.py .\n"
            "event=validation_complete status=ok\n"
        )
        phase0, _install, _blocked, _stop = F.parse_transcript(transcript)
        self.assertFalse(phase0.first_probe_ok)

    def test_banner_rendered_via_canonical_rule(self) -> None:
        """The 80-wide ═══ rule (U+2550, 090n) is the
        Markdown-inert signal."""
        transcript = (
            "═" * 80 + "\n"
            "  Quality Playbook — by Andrew Stellman\n"
            "═" * 80 + "\n"
        )
        _phase0, install, _blocked, _stop = F.parse_transcript(
            transcript,
        )
        self.assertTrue(install.banner_rendered)

    def test_gitignore_canonical_remediation_followed(self) -> None:
        transcript = (
            "Running the gitignore remediation:\n"
            "$ cat /opt/playbook/skill-template.gitignore >> "
            "/tmp/target/.gitignore\n"
            "Done.\n"
        )
        _phase0, install, _blocked, _stop = F.parse_transcript(
            transcript,
        )
        self.assertTrue(install.gitignore_remediation_followed)

    def test_gitignore_improvisation_not_followed(self) -> None:
        """The 090u motivating case: agent improvised
        ``printf "\\nquality/\\n" >> .gitignore`` instead of the
        canonical form → ``gitignore_remediation_followed=False``."""
        transcript = (
            "$ printf \"\\nquality/\\n\" >> .gitignore\n"
        )
        _phase0, install, _blocked, _stop = F.parse_transcript(
            transcript,
        )
        self.assertFalse(install.gitignore_remediation_followed)

    def test_blocked_stop_reason_captured(self) -> None:
        transcript = (
            "User: Run the playbook.\n"
            "Agent: I cannot help with that as it goes against "
            "my policy.\n"
        )
        _phase0, _install, blocked, stop = F.parse_transcript(
            transcript,
        )
        self.assertTrue(blocked)
        self.assertIsNotNone(stop)
        self.assertIn("policy", stop.lower())


# ---------------------------------------------------------------------------
# find_installed_gate / rerun_installed_gate
# ---------------------------------------------------------------------------


class FindInstalledGateTests(unittest.TestCase):

    def test_finds_install_skill_marker_layout(self) -> None:
        """install_skill.py layout: <target>/.claude/skills/quality-
        playbook/quality_gate.py."""
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            d = t / ".claude" / "skills" / "quality-playbook"
            d.mkdir(parents=True)
            gate = d / "quality_gate.py"
            gate.write_text("# fake gate\n")
            self.assertEqual(F.find_installed_gate(t), gate)

    def test_finds_setup_repos_flat_layout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            d = t / ".github" / "skills"
            d.mkdir(parents=True)
            gate = d / "quality_gate.py"
            gate.write_text("# fake gate\n")
            self.assertEqual(F.find_installed_gate(t), gate)

    def test_raises_when_no_gate_present(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(F.FactsError) as ctx:
                F.find_installed_gate(Path(td))
            self.assertIn("not found", str(ctx.exception))


class RerunInstalledGateE2ETests(unittest.TestCase):
    """Load-bearing two-sourced check: re-run the run's OWN
    installed quality_gate.py over the run's final ``quality/``
    artifacts AND parse the resulting stdout into facts.

    Uses a TINY synthetic target tree (no real adopter repo) — the
    gate produces a FAIL on an empty target (missing artifacts);
    we don't care about the verdict, only that the re-run path
    works end-to-end AND the harness sets the vendor env var so
    ``provenance.detected_runner`` reflects the configured runner.
    """

    def test_rerun_sets_vendor_env_for_runner_detection(self) -> None:
        # Install a real QPB skill into a temp target so the
        # installed gate is the real one (this is the canonical
        # "run's OWN installed gate" path).
        from bin import install_skill
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            (target / ".github").mkdir()
            install_skill.install(into=target, ai_tool="claude",
                                    no_smoke=True)
            # Re-run with CLAUDE runner — vendor env CLAUDECODE=1
            # must reach the subprocess.
            axes = _mk_axes(runner=S.Runner.CLAUDE)
            stdout = F.rerun_installed_gate(
                target, axes=axes, timeout_s=60.0,
            )
            # The gate emits canonical lines even when the target
            # is empty (it FAILs on missing artifacts).
            self.assertIn("RESULT:", stdout)
            # And the provenance section reflects the vendor env
            # we set: ``Runner: claude-code (detected ...)``
            # — confirms the harness correctly set CLAUDECODE.
            self.assertIn(
                "claude-code", stdout,
                f"v1.5.7 091: the re-run must set the vendor env "
                f"var so the gate detects 'claude-code'. Got:\n"
                f"{stdout[-2000:]}",
            )

    def test_rerun_with_codex_axes_detects_codex(self) -> None:
        """The same fixture re-run with axes.runner=CODEX
        produces ``detected_runner=codex`` — the harness re-sets
        the env per-runner."""
        from bin import install_skill
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            (target / ".github").mkdir()
            install_skill.install(into=target, ai_tool="claude",
                                    no_smoke=True)
            axes = _mk_axes(runner=S.Runner.CODEX)
            stdout = F.rerun_installed_gate(
                target, axes=axes, timeout_s=60.0,
            )
            self.assertIn("codex", stdout,
                          "v1.5.7 091: CODEX axis must set "
                          "CODEX_THREAD_ID so the gate reports "
                          "codex as detected_runner.")


# ---------------------------------------------------------------------------
# extract_facts — combined two-sourced path with injected stdout
# ---------------------------------------------------------------------------


class ExtractFactsCombinedTests(unittest.TestCase):

    def test_combines_gate_stdout_and_transcript(self) -> None:
        """The harness calls ``extract_facts(gate_stdout=...)``
        from tests; the combined output carries both gate-derived
        (verdict/gate/provenance) AND live-behavior (phase0/install)
        facts."""
        transcript = (
            "═" * 80 + "\nbanner...\n" + "═" * 80 + "\n"
            "event=validation_complete status=ok\n"
            "$ cat /opt/skill-template.gitignore >> .gitignore\n"
        )
        axes = _mk_axes()
        facts = F.extract_facts(
            target_dir=Path("/ignored"), axes=axes,
            transcript=transcript, exit_code=0,
            gate_stdout=_CANONICAL_SHALLOW_STDOUT,
        )
        # Gate-derived.
        self.assertEqual(facts.gate.gate_result, S.GateResult.PASS)
        self.assertEqual(facts.verdict.verdict_state,
                         S.VerdictState.SHALLOW)
        self.assertEqual(facts.provenance.detected_runner,
                         "claude-code")
        # Live-behavior.
        self.assertTrue(facts.phase0.first_probe_ok)
        self.assertTrue(facts.install.banner_rendered)
        self.assertTrue(facts.install.gitignore_remediation_followed)
        # Run meta.
        self.assertEqual(facts.run_meta.exit_code, 0)
        self.assertFalse(facts.run_meta.blocked)


if __name__ == "__main__":
    unittest.main()
