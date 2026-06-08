"""v1.5.7 instruction 090w — run-provenance line in the 090v
operator verdict block: verified runner (env-detected) +
labeled self-reported model + gate-counted bug count with a
stale-metadata mismatch flag.

Motivated by the 2026-05-25 NATS run2 (gpt-5.4/medium via Codex
desktop). The run found 3 real bugs (incl. BUG-001, a known
actively-discussed NATS security issue) — but
``quality/results/run-*.json`` still read ``"model": "gpt-5.2"``
and ``"bug_count": 0``: the agent wrote the metadata template at
the START and never updated it. So the self-reported model AND
bug count were BOTH wrong. Operators want real provenance, but
echoing the self-report raw would print confidently-wrong
provenance — worse than nothing. The fix: surface provenance with
explicit confidence labels, prefer gate-derived facts over
self-report, and flag self-report/gate mismatches.

Architecture: 090w is purely additive on top of the 090v verdict
block. Adds a small env-runner-detection helper
(``_detect_runner_from_env``), a per-repo provenance accumulator
(``_RUN_PROVENANCE``), a read-only capture helper
(``_capture_run_provenance`` invoked from ``check_repo`` — never
emits FAIL/WARN), and a new "── Run provenance ──" section in
``_emit_operator_verdict``. ``total_line`` / ``result_line`` /
``exit_code`` are byte-identical / unchanged.

Test surfaces:

  RunnerDetectionTests — ``_detect_runner_from_env`` returns
    ``codex`` / ``copilot`` / ``claude-code`` / ``unknown``, and
    a "+"-joined string when multiple markers are set.
  ProvenanceCaptureTests — ``_capture_run_provenance`` reads
    self-reported fields defensively (missing/odd run-metadata
    is fine — no FAIL/WARN, no crash).
  ProvenanceRenderingTests — ``_format_provenance_lines``
    renders the canonical 3-line shape with the load-bearing
    "self-reported by the agent — not verified" label (mutation
    bite); renders the mismatch flag when self-reported
    bug_count differs from gate count (NATS run2 regression
    anchor: gate 3 vs reported 0); no mismatch flag on matching
    counts; "not recorded" when model is absent.
  VerdictBlockIntegrationTests — end-to-end through the gate:
    the verdict block carries the "── Run provenance ──"
    header; provenance is informational only (mismatch does NOT
    fail/change exit_code); missing run-metadata still renders
    provenance gracefully (runner-from-env + Model: not recorded
    + gate-counted bugs).
  LoadBearingPreservationTests — total_line + result_line are
    byte-identical, exit_code unchanged with provenance present.
  ScopeGuardTests — SKILL.md / phase prompts untouched.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))
from test_quality_gate import (  # noqa: E402
    minimal_zero_bug_tree,
    add_one_bug,
    quality_gate,
    FixtureBase,
)


_REAL_PY_FUNCTIONAL_TEST = """\
import unittest

class FunctionalTests(unittest.TestCase):
    def test_thing(self):
        self.assertEqual(1 + 1, 2)
"""


def _one_bug_tree_with_metadata(model: "str | None" = "gpt-test",
                                 bug_count_field: "int | None" = None):
    """One-bug tree with a real assertion in the functional test
    (so no 090s shallow signal fires) and customizable run-metadata
    (model + optional ``bug_count``)."""
    tree = minimal_zero_bug_tree()
    add_one_bug(tree, bug_id="BUG-001")
    tree["quality/test_functional.py"] = _REAL_PY_FUNCTIONAL_TEST
    tree["quality/PROGRESS.md"] = (
        "# Progress\n\nSkill version: 1.4.4\n\n"
        "## Phases\n- [x] Phase 1\n- [x] Phase 2\n- [x] Phase 3\n"
        "- [x] Phase 4\n- [x] Phase 5\n- [x] Phase 6\n"
        "## Terminal Gate Verification\n"
    )
    run_metadata = {
        "schema_version": "1.0",
        "skill_version": "1.4.4",
        "project": "testproj",
        "runner": "test-runner",
        "start_time": "2026-01-01T00:00:00Z",
    }
    if model is not None:
        run_metadata["model"] = model
    if bug_count_field is not None:
        run_metadata["bug_count"] = bug_count_field
    # Override the existing run-metadata file written by
    # minimal_zero_bug_tree (which has "model": "test-model").
    tree["quality/results/run-2026-01-01T00-00-00.json"] = json.dumps(
        run_metadata
    )
    return tree


# ---------------------------------------------------------------------------
# Runner detection — env vars → runner label.
# ---------------------------------------------------------------------------


class RunnerDetectionTests(unittest.TestCase):

    def test_codex_thread_id_detects_codex(self) -> None:
        result = quality_gate._detect_runner_from_env(
            {"CODEX_THREAD_ID": "abc123"},
        )
        self.assertEqual(result, "codex")

    def test_copilot_session_id_detects_copilot(self) -> None:
        result = quality_gate._detect_runner_from_env(
            {"COPILOT_AGENT_SESSION_ID": "session-xyz"},
        )
        self.assertEqual(result, "copilot")

    def test_claudecode_detects_claude_code(self) -> None:
        result = quality_gate._detect_runner_from_env(
            {"CLAUDECODE": "1"},
        )
        self.assertEqual(result, "claude-code")

    def test_empty_env_returns_unknown(self) -> None:
        result = quality_gate._detect_runner_from_env({})
        self.assertEqual(result, "unknown")

    def test_empty_string_marker_does_not_detect(self) -> None:
        """A marker present but empty-string-valued is treated as
        absent — conservative direction."""
        result = quality_gate._detect_runner_from_env(
            {"CODEX_THREAD_ID": ""},
        )
        self.assertEqual(result, "unknown")

    def test_multiple_markers_returns_plus_joined(self) -> None:
        """When more than one marker is set (e.g. test harness in
        ambient mode), all detected runners are returned joined —
        the env is reported honestly rather than collapsed to a
        guess. Order matches ``_RUNNER_ENV_MARKERS``."""
        result = quality_gate._detect_runner_from_env({
            "CODEX_THREAD_ID": "x",
            "COPILOT_AGENT_SESSION_ID": "x",
            "CLAUDECODE": "1",
        })
        # All three present → ordered list joined with "+".
        self.assertEqual(result, "codex+copilot+claude-code")


# ---------------------------------------------------------------------------
# Provenance rendering — line shape with confidence labels.
# ---------------------------------------------------------------------------


class ProvenanceRenderingTests(unittest.TestCase):

    def test_canonical_three_line_shape(self) -> None:
        """A well-formed provenance entry renders the 3-line shape:
        Runner / Model / Bugs."""
        lines = quality_gate._format_provenance_lines({
            "repo": "testproj",
            "runner_detected": "codex",
            "model_self_reported": "gpt-5.2",
            "bug_count_gate": 3,
            "bug_count_self_reported": None,
        })
        self.assertEqual(len(lines), 3)
        self.assertIn("Runner:", lines[0])
        self.assertIn("codex", lines[0])
        self.assertIn("detected from environment", lines[0])
        self.assertIn("Model:", lines[1])
        self.assertIn("gpt-5.2", lines[1])
        self.assertIn("Bugs:", lines[2])
        self.assertIn("3 found (gate-counted)", lines[2])

    def test_self_reported_label_is_present_on_model_line(
            self) -> None:
        """v1.5.7 090w MUTATION BITE: the self-reported model MUST
        carry the explicit "self-reported by the agent — not
        verified" label so an operator never reads the model line
        as authoritative.

        Mutation bite: drop the label string from
        ``_format_provenance_lines`` (e.g. render the model as a
        bare ``Model: gpt-5.2``) → this test FAILs because the
        label substring is absent. Provenance must NEVER present a
        self-report as verified.
        """
        lines = quality_gate._format_provenance_lines({
            "repo": "any",
            "runner_detected": "codex",
            "model_self_reported": "gpt-5.2",
            "bug_count_gate": 0,
            "bug_count_self_reported": None,
        })
        model_line = next(ln for ln in lines if "Model:" in ln)
        self.assertIn(
            "self-reported by the agent — not verified",
            model_line,
            "v1.5.7 090w: the self-reported model line MUST carry "
            "the 'self-reported by the agent — not verified' "
            "confidence label. Provenance that presents self-"
            "report as verified is worse than no provenance "
            "(NATS run2: self-reported gpt-5.2, real gpt-5.4).",
        )

    def test_missing_model_renders_not_recorded(self) -> None:
        """When run-metadata has no ``model`` field, the line
        renders ``Model: not recorded`` — never a misleading
        empty/None token."""
        lines = quality_gate._format_provenance_lines({
            "repo": "any",
            "runner_detected": "codex",
            "model_self_reported": None,
            "bug_count_gate": 0,
            "bug_count_self_reported": None,
        })
        model_line = next(ln for ln in lines if "Model:" in ln)
        self.assertIn("not recorded", model_line)
        # And the "self-reported — not verified" label MUST NOT
        # appear (nothing was self-reported).
        self.assertNotIn("self-reported by the agent", model_line)

    def test_nats_run2_mismatch_flag_appears(self) -> None:
        """The NATS run2 regression anchor: gate 3 vs self-reported
        0 → the bug line carries the stale-metadata mismatch flag.

        Mutation bite: comment out the mismatch branch → this test
        FAILs because the flag is absent.
        """
        lines = quality_gate._format_provenance_lines({
            "repo": "nats-test",
            "runner_detected": "codex",
            "model_self_reported": "gpt-5.2",
            "bug_count_gate": 3,
            "bug_count_self_reported": 0,
        })
        bug_line = next(ln for ln in lines if "Bugs:" in ln)
        self.assertIn("3 found (gate-counted)", bug_line)
        self.assertIn(
            "run-metadata self-reported: 0", bug_line,
            "v1.5.7 090w: NATS run2 regression anchor — a gate-vs-"
            "self-reported bug-count mismatch MUST surface the "
            "stale-metadata flag on the bug line.",
        )
        self.assertIn("mismatch", bug_line)

    def test_matching_bug_counts_no_mismatch_flag(self) -> None:
        """Don't-over-fire pin: matching counts → no flag, clean
        bug line."""
        lines = quality_gate._format_provenance_lines({
            "repo": "any",
            "runner_detected": "codex",
            "model_self_reported": "gpt-5.2",
            "bug_count_gate": 3,
            "bug_count_self_reported": 3,
        })
        bug_line = next(ln for ln in lines if "Bugs:" in ln)
        self.assertNotIn(
            "mismatch", bug_line,
            "matching counts must not trigger the mismatch flag.",
        )
        self.assertNotIn("self-reported:", bug_line)

    def test_unknown_runner_renders_explanation(self) -> None:
        """An ``unknown`` runner renders the explanation ('no
        AI-CLI environment marker detected') so the operator
        understands the absence, not just a bare 'unknown'."""
        lines = quality_gate._format_provenance_lines({
            "repo": "any",
            "runner_detected": "unknown",
            "model_self_reported": None,
            "bug_count_gate": 0,
            "bug_count_self_reported": None,
        })
        runner_line = next(ln for ln in lines if "Runner:" in ln)
        self.assertIn("unknown", runner_line)
        self.assertIn("no AI-CLI environment marker", runner_line)


# ---------------------------------------------------------------------------
# Provenance capture — read-only, defensive.
# ---------------------------------------------------------------------------


class ProvenanceCaptureTests(FixtureBase):
    """Direct exercises of ``_capture_run_provenance`` — verify
    it's defensive against missing / odd run-metadata and never
    emits FAIL/WARN (provenance is informational only)."""

    def setUp(self) -> None:
        super().setUp()
        # Clear module state so tests don't interfere.
        quality_gate._RUN_PROVENANCE.clear()

    def test_well_formed_metadata_captured(self) -> None:
        self.write(_one_bug_tree_with_metadata(model="gpt-5.4",
                                                 bug_count_field=3))
        quality_gate._capture_run_provenance(
            self.repo / "quality", "testproj", bug_count=3,
        )
        self.assertEqual(len(quality_gate._RUN_PROVENANCE), 1)
        entry = quality_gate._RUN_PROVENANCE[0]
        self.assertEqual(entry["repo"], "testproj")
        self.assertEqual(entry["model_self_reported"], "gpt-5.4")
        self.assertEqual(entry["bug_count_gate"], 3)
        self.assertEqual(entry["bug_count_self_reported"], 3)

    def test_missing_run_metadata_captured_gracefully(self) -> None:
        """No run-metadata file → entry still captured with
        ``model_self_reported=None`` / ``bug_count_self_reported=None``.
        No crash, no FAIL/WARN."""
        tree = minimal_zero_bug_tree()
        # Drop the run-metadata file entirely.
        del tree["quality/results/run-2026-01-01T00-00-00.json"]
        self.write(tree)
        # Pre-WARN count (we'll assert no new WARN emitted).
        pre_warn = quality_gate.WARN
        quality_gate._capture_run_provenance(
            self.repo / "quality", "testproj", bug_count=0,
        )
        self.assertEqual(len(quality_gate._RUN_PROVENANCE), 1)
        entry = quality_gate._RUN_PROVENANCE[0]
        self.assertIsNone(entry["model_self_reported"])
        self.assertIsNone(entry["bug_count_self_reported"])
        self.assertEqual(entry["bug_count_gate"], 0)
        # Crucially: no WARN emitted (provenance is informational
        # — the existing check_run_metadata is the validator).
        self.assertEqual(
            quality_gate.WARN, pre_warn,
            "v1.5.7 090w: _capture_run_provenance must be silent "
            "on missing metadata (informational only).",
        )

    def test_malformed_metadata_captured_gracefully(self) -> None:
        """run-metadata that's a string / list / number / non-JSON
        → entry captured with ``None`` fields. No crash."""
        tree = minimal_zero_bug_tree()
        tree["quality/results/run-2026-01-01T00-00-00.json"] = (
            "not even json at all"
        )
        self.write(tree)
        quality_gate._capture_run_provenance(
            self.repo / "quality", "testproj", bug_count=0,
        )
        entry = quality_gate._RUN_PROVENANCE[0]
        self.assertIsNone(entry["model_self_reported"])
        self.assertIsNone(entry["bug_count_self_reported"])

    def test_non_string_model_field_treated_as_absent(self) -> None:
        """run-metadata ``"model": 42`` → treated as absent
        (defensive: only string models surface)."""
        tree = _one_bug_tree_with_metadata(model=None)
        # Inject a non-string model.
        tree["quality/results/run-2026-01-01T00-00-00.json"] = (
            json.dumps({
                "schema_version": "1.0", "skill_version": "1.4.4",
                "project": "x", "model": 42, "runner": "r",
                "start_time": "2026-01-01T00:00:00Z",
            })
        )
        self.write(tree)
        quality_gate._capture_run_provenance(
            self.repo / "quality", "testproj", bug_count=0,
        )
        entry = quality_gate._RUN_PROVENANCE[0]
        self.assertIsNone(entry["model_self_reported"])


# ---------------------------------------------------------------------------
# End-to-end verdict block integration — the gate runs and the
# "── Run provenance ──" section appears with the expected content.
# ---------------------------------------------------------------------------


class VerdictBlockIntegrationTests(FixtureBase):

    def test_verdict_block_carries_provenance_header(self) -> None:
        """The 090w "── Run provenance ──" header appears in
        stdout AFTER the 090v block fires."""
        self.write(_one_bug_tree_with_metadata(model="gpt-5.4",
                                                 bug_count_field=3))
        stdout, _code = self.gate()
        self.assertIn("── Run provenance ──", stdout)
        self.assertIn("Runner:", stdout)
        self.assertIn("Model:", stdout)
        self.assertIn("Bugs:", stdout)

    def test_provenance_does_not_change_pass_fail(self) -> None:
        """v1.5.7 090w halt condition: provenance is informational
        only — a self-report-vs-gate MISMATCH does NOT fail the
        gate or change exit_code.

        Mutation bite: route the mismatch flag into a ``fail(...)``
        call → this test FAILs because the gate exits non-zero on
        what should be a clean pass.
        """
        # NATS run2 shape: gate counts 1 bug, self-report says 0 →
        # mismatch flag fires in provenance, but pass/fail
        # semantics MUST be unchanged.
        self.write(_one_bug_tree_with_metadata(
            model="gpt-5.4", bug_count_field=0,
        ))
        stdout, code = self.gate()
        self.assertEqual(
            code, 0,
            f"v1.5.7 090w: a bug-count mismatch is INFORMATIONAL "
            f"only — must not change exit_code. Got exit={code}\n"
            f"stdout:\n{stdout}",
        )
        # And the mismatch flag IS surfaced in the provenance
        # block.
        self.assertIn("mismatch", stdout)

    def test_missing_run_metadata_provenance_still_renders(self) -> None:
        """Missing run-metadata → the existing check FAILs the gate
        (that's check_run_metadata's job, NOT 090w's). Provenance
        still renders gracefully with ``Model: not recorded`` and
        the gate-counted bug count."""
        tree = minimal_zero_bug_tree()
        del tree["quality/results/run-2026-01-01T00-00-00.json"]
        self.write(tree)
        stdout, _code = self.gate()
        self.assertIn("── Run provenance ──", stdout)
        self.assertIn("Model:   not recorded", stdout)

    def test_self_reported_label_in_full_gate_output(self) -> None:
        """The full gate run carries the "self-reported by the
        agent — not verified" label in the rendered output."""
        self.write(_one_bug_tree_with_metadata(model="gpt-5.4",
                                                 bug_count_field=3))
        stdout, _code = self.gate()
        self.assertIn(
            "self-reported by the agent — not verified", stdout,
            f"v1.5.7 090w: the rendered gate output must carry the "
            f"self-reported model confidence label. Got:\n{stdout}",
        )


# ---------------------------------------------------------------------------
# Load-bearing preservation — provenance must not perturb the
# canonical total_line / result_line / exit_code.
# ---------------------------------------------------------------------------


class LoadBearingPreservationTests(FixtureBase):

    def test_total_line_byte_identical_with_provenance(self) -> None:
        self.write(_one_bug_tree_with_metadata(model="gpt-5.4",
                                                 bug_count_field=3))
        stdout, _code = self.gate()
        self.assertRegex(
            stdout,
            re.compile(r"^Total: \d+ FAIL, \d+ WARN$",
                       re.MULTILINE),
        )

    def test_result_line_byte_identical_with_provenance(self) -> None:
        self.write(_one_bug_tree_with_metadata(model="gpt-5.4",
                                                 bug_count_field=3))
        stdout, code = self.gate()
        self.assertEqual(code, 0)
        self.assertRegex(
            stdout,
            re.compile(r"^RESULT: GATE PASSED$", re.MULTILINE),
        )

    def test_exit_code_unchanged_with_provenance_mismatch(self) -> None:
        """Re-emphasises the halt condition: a mismatch flag
        appearing in the provenance block MUST NOT alter
        exit_code."""
        self.write(_one_bug_tree_with_metadata(
            model="gpt-5.4", bug_count_field=999,  # gross mismatch
        ))
        stdout, code = self.gate()
        # The mismatch surfaces…
        self.assertIn("mismatch", stdout)
        # …but exit_code is unaffected (the run is otherwise
        # clean).
        self.assertEqual(code, 0)


# ---------------------------------------------------------------------------
# Scope guards.
# ---------------------------------------------------------------------------


class ScopeGuard090wTests(unittest.TestCase):

    def test_skill_md_not_touched_by_090w(self) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        text = (repo_root / "skills" / "quality-playbook" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "090w", text,
            "SKILL.md must not carry 090w anchors — 090w is gate "
            "output, not skill prose.",
        )

    def test_phase_prompts_not_touched_by_090w(self) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        phase_dir = repo_root / "phase_prompts"
        for phase_file in sorted(phase_dir.glob("phase*.md")):
            text = phase_file.read_text(encoding="utf-8")
            self.assertNotIn(
                "090w", text,
                f"{phase_file.name} must not carry 090w anchors.",
            )


if __name__ == "__main__":
    unittest.main()
