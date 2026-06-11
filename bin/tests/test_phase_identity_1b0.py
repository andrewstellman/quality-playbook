"""v1.5.9 Phase 1B.0 — phase-identity source-of-truth regression test.

The harness acts on the worker's *current phase*. The worker exposes
its phase three ways — the ``::QPB:: kind:"phase"`` sentinel
(``qpb_phase`` / ``phase_identity``), the ``phase_start`` / ``phase_end``
events in ``run_state.jsonl`` (``run_state_lib``), and the
``heartbeat.ndjson`` ``phase`` field (the v1.5.9 harness). 1B.0 makes the
three derive their ``(number, name)`` pair from ONE shared table so they
agree BY CONSTRUCTION.

This is the deliverable's gate test: assert that a ``::QPB::`` sentinel,
a run-state ``phase_start`` event, and a heartbeat line emitted for the
SAME boundary all report the identical ``(number, name)`` pair — for
every phase — and that the keepalive ping reads its phase from the
canonical run-state position.

MUTATION-VERIFY EVIDENCE (in-tree per DEVELOPMENT_PROCESS.md §Mutation-
test discipline), v1.5.9 instruction 004 — TWO axes, both BITE-EXECUTED
(after purging __pycache__):

  Axis A — table value. In phase_identity._PHASES, change row 3 from
    3: ("code-review", "Code Review")  ->  3: ("XXX-drift", "Code Review")
  Observed: FAIL test_facade_emits_identical_number_name_across_three_
  surfaces (the hardcoded _EXPECTED_SLUG anchor catches 'XXX-drift' !=
  'code-review'). Restored -> OK. [The cross-surface checks ALONE can't
  catch this — all three surfaces read the one table and drift together,
  which is the by-construction guarantee; the hardcoded anchor is why
  the test still bites a table edit.]

  Axis B — drift reintroduction. In run_state_lib.emit_phase_transition's
  heartbeat branch, change ``phase=phase`` -> ``phase=(1 if phase != 1
  else 2)`` so the heartbeat is built from a DIFFERENT phase than the
  sentinel (simulating a reintroduced second source).
  Observed: FAIL test_facade_emits_identical_number_name_across_three_
  surfaces (heartbeat phase no longer matches the sentinel). Restored
  -> OK. [This is the regression the cross-surface agreement defends:
  any emitter computing its phase independently again.]
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = (
    _REPO_ROOT / "plugins" / "quality-playbook"
    / "skills" / "quality-playbook" / "scripts"
)


def _load(modname: str, filename: str):
    """Load a bundled script by file path (mirrors the 089x/090c/109
    test pattern — avoids going through bin/__init__.py)."""
    spec = importlib.util.spec_from_file_location(
        modname, str(_SCRIPTS_DIR / filename),
    )
    mod = importlib.util.module_from_spec(spec)
    # Register so any dataclass/typing introspection resolves.
    import sys
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


def _parse_sentinel(line: str) -> dict:
    prefix = "::QPB:: "
    assert line.startswith(prefix), f"not a ::QPB:: line: {line!r}"
    return json.loads(line[len(prefix):])


# Hardcoded ground truth — the canonical slugs the shared table MUST
# carry. Pinning these (not just cross-surface agreement) is what makes
# this test mutation-sensitive to a table-value change: the cross-surface
# checks alone can't catch a table edit (all three surfaces read the one
# table, so they drift together and still agree by construction — which
# is the whole point). These hardcoded values are the independent anchor.
_EXPECTED_SLUG = {
    0: "validation", 1: "exploration", 2: "generation", 3: "code-review",
    4: "spec-audit", 5: "reconciliation", 6: "verification",
}


class PhaseIdentitySourceOfTruthTests(unittest.TestCase):
    """1B.0 contract: sentinel ↔ run_state ↔ heartbeat agree on
    (number, name) by construction."""

    def setUp(self):
        self.pi = _load("pi_1b0_under_test", "phase_identity.py")
        self.qpb_phase = _load("qpb_phase_1b0_under_test", "qpb_phase.py")
        self.rsl = _load("run_state_1b0_under_test", "run_state_lib.py")

    # -- the headline gate -------------------------------------------------

    def test_facade_emits_identical_number_name_across_three_surfaces(self):
        """For EVERY phase + both states, the facade's sentinel, the
        run-state event, and the heartbeat line carry the identical
        ``(number, name)`` pair drawn from the shared table."""
        for phase in sorted(self.pi.PHASE_NUMBERS):
            if phase == 0:
                # run-state phase events are 1..6 (validation/phase-0 is
                # the install-validator surface, not a pipeline phase);
                # the sentinel + heartbeat still cover it (next test).
                continue
            for state in ("start", "done"):
                with tempfile.TemporaryDirectory() as d:
                    rs = Path(d) / "run_state.jsonl"
                    hb = Path(d) / "heartbeat.ndjson"
                    sentinel = self.rsl.emit_phase_transition(
                        run_state_path=rs, phase=phase, state=state,
                        heartbeat_path=hb, task_id="t-1",
                        ts="2026-01-01T00:00:00Z",
                    )
                    sp = _parse_sentinel(sentinel)
                    ev = self.rsl.read_events(rs)[-1]
                    hbline = json.loads(hb.read_text().splitlines()[-1])

                    expected = (phase, _EXPECTED_SLUG[phase])  # hardcoded anchor
                    # the shared table itself carries the canonical slug
                    self.assertEqual(self.pi.phase_identity(phase), expected)
                    # sentinel
                    self.assertEqual((sp["phase"], sp["name"]), expected)
                    # run-state event (carries number; name via table)
                    self.assertEqual(ev.fields["phase"], phase)
                    self.assertEqual(
                        (ev.fields["phase"],
                         self.pi.phase_slug(ev.fields["phase"])),
                        expected,
                    )
                    # heartbeat (carries the slug in `phase`)
                    self.assertEqual(
                        (phase, hbline["phase"]), expected
                    )
                    # event kind matches the state
                    self.assertEqual(
                        ev.event,
                        "phase_start" if state == "start" else "phase_end",
                    )

    def test_qpb_phase_sentinel_name_agrees_with_shared_table(self):
        """The standalone qpb_phase CLI formatter (the live sentinel
        emitter) draws its name from the same table — all 0..6."""
        for phase in sorted(self.pi.PHASE_NUMBERS):
            sp = _parse_sentinel(
                self.qpb_phase.format_sentinel(phase=phase, state="start")
            )
            self.assertEqual(sp["name"], self.pi.phase_slug(phase))
            self.assertEqual(sp["phase"], phase)

    def test_runstate_display_label_agrees_with_shared_table(self):
        """PROGRESS.md display labels (run_state_lib.write_progress_md)
        derive from the same shared table — no second copy."""
        # write_progress_md uses _phase_identity().phase_display(n);
        # assert the resolved module is the same identity and the
        # display labels are the shipped pipeline labels.
        pi = self.rsl._phase_identity()
        self.assertEqual(pi.phase_display(1), "Explore")
        self.assertEqual(pi.phase_display(2), "Generate")
        self.assertEqual(pi.phase_display(3), "Code Review")
        self.assertEqual(pi.phase_display(4), "Spec Audit")
        self.assertEqual(pi.phase_display(5), "Reconciliation")
        self.assertEqual(pi.phase_display(6), "Verify")

    # -- keepalive reads the canonical position ----------------------------

    def test_keepalive_reads_phase_from_run_state(self):
        """The mid-phase keepalive ping has no boundary/sentinel — it
        reads the current phase from run_state.jsonl (canonical) so it
        can't drift from the sentinel."""
        with tempfile.TemporaryDirectory() as d:
            rs = Path(d) / "run_state.jsonl"
            hb = Path(d) / "heartbeat.ndjson"
            # no phase open yet -> nothing to ping
            self.assertIsNone(
                self.rsl.emit_keepalive_heartbeat(
                    run_state_path=rs, heartbeat_path=hb)
            )
            # open phase 4
            self.rsl.emit_phase_transition(
                run_state_path=rs, phase=4, state="start",
                ts="2026-01-01T00:00:00Z",
            )
            ka = self.rsl.emit_keepalive_heartbeat(
                run_state_path=rs, heartbeat_path=hb,
                ts="2026-01-01T00:03:00Z",
            )
            self.assertEqual(ka["phase"], self.pi.phase_slug(4))
            self.assertEqual(ka["status"], "IN_PROGRESS")
            # current_phase reports 4 until phase_end closes it
            self.assertEqual(self.rsl.current_phase(rs), 4)
            self.rsl.emit_phase_transition(
                run_state_path=rs, phase=4, state="done",
                ts="2026-01-01T00:05:00Z",
            )
            self.assertIsNone(self.rsl.current_phase(rs))

    # -- gate sentinel shares the envelope writer (decision 4) -------------

    def test_gate_sentinel_uses_shared_envelope_writer(self):
        """quality_gate's gate sentinel goes through the shared
        ``format_qpb_envelope`` (single ::QPB:: line writer); the gate
        PAYLOAD stays its own (kind:"gate"), byte-identical to pre-1B.0."""
        qg = _load("quality_gate_1b0_under_test", "quality_gate.py")
        got = qg._format_gate_sentinel(
            gate_result="PASS", verdict_state="solid",
            ts="2026-05-26T00:00:00Z",
        )
        expected_envelope = self.pi.format_qpb_envelope({
            "v": 1, "kind": "gate", "gate_result": "PASS",
            "verdict_state": "solid", "ts": "2026-05-26T00:00:00Z",
        })
        self.assertEqual(got, expected_envelope)
        # And the byte-exact legacy shape is preserved.
        self.assertEqual(
            got,
            '::QPB:: {"v":1,"kind":"gate","gate_result":"PASS",'
            '"verdict_state":"solid","ts":"2026-05-26T00:00:00Z"}',
        )


if __name__ == "__main__":
    unittest.main()
