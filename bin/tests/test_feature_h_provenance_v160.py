"""v1.6.0 Feature H (Design §8b) — guard 2: agent-validation provenance + the
write-restriction (security-critical).

This is the foundational, fully-mechanical slice of Feature H (instruction 012):
the `agent-validation` req_source_type and the enforcement that a persona can
NEVER launder an injected requirement into the human-only, append-only,
highest-trust `operator_confirmations.jsonl` ledger. The rest of Feature H
(persona orchestration + tool-allowlist isolation, guards 1/3/4, merge, revert,
off-switch, target-agnostic harness, and the live gap-finding run) is scoped in
the instruction-012 output for follow-up.

Covers acceptance-oracle item 5 (provenance mutation): `agent-validation` records
are schema-valid and distinguishable from `operator-confirmation`; a persona
attempting to write an operator-confirmation record / to
`operator_confirmations.jsonl` is rejected.
"""

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = (
    REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))

import quality_gate  # noqa: E402
import run_state_lib  # noqa: E402


class AgentValidationEnumTests(unittest.TestCase):
    def test_agent_validation_is_a_valid_source_type(self):
        self.assertIn("agent-validation", quality_gate._V153_VALID_SOURCE_TYPES)

    def test_agent_validation_is_distinct_from_operator_confirmation(self):
        # Downstream must not coalesce the two — they are different enum values.
        self.assertNotEqual("agent-validation", "operator-confirmation")
        self.assertIn("operator-confirmation", quality_gate._V153_VALID_SOURCE_TYPES)
        self.assertIn("agent-validation", quality_gate._V153_VALID_SOURCE_TYPES)


class WriteRestrictionTests(unittest.TestCase):
    """Guard 2: a persona may write ONLY agent-validation into the manifest and
    may NEVER append to operator_confirmations.jsonl (human-interview-only)."""

    def _tmp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        return Path(d.name) / "operator_confirmations.jsonl"

    def test_append_confirmation_rejects_an_agent_validation_record(self):
        path = self._tmp()
        record = {
            "ts": "2026-07-22T00:00:00Z", "move": "add",
            "req_title": "injected", "conditions_of_satisfaction": "x",
            "operator_statement": "forged", "session_id": "s",
            "source_type": "agent-validation",  # <-- the forbidden provenance
        }
        with self.assertRaises(ValueError) as ctx:
            run_state_lib.append_confirmation(path, record)
        self.assertIn("agent-validation", str(ctx.exception))
        # Nothing was written — the ledger stays absent.
        self.assertFalse(path.exists())

    def test_append_confirmation_still_accepts_a_human_record(self):
        # The restriction must not break the legitimate human-interview writer.
        path = self._tmp()
        record = {
            "ts": "2026-07-22T00:00:00Z", "move": "confirm",
            "req_title": "real", "conditions_of_satisfaction": "y",
            "operator_statement": "I confirm this.", "session_id": "s",
        }
        run_state_lib.append_confirmation(path, record)
        self.assertTrue(path.exists())
        self.assertEqual(len(run_state_lib.read_confirmations(path)), 1)

    def test_write_restriction_is_load_bearing(self):
        # Mutation-style: the human record above lacks source_type and is
        # accepted; only the explicit agent-validation provenance is refused —
        # proving the guard keys on the provenance, not on some incidental field.
        path = self._tmp()
        human = {
            "ts": "t", "move": "correct", "req_title": "r",
            "conditions_of_satisfaction": "c", "operator_statement": "o",
            "session_id": "s",
        }
        run_state_lib.append_confirmation(path, human)  # ok
        poisoned = dict(human, source_type="agent-validation")
        with self.assertRaises(ValueError):
            run_state_lib.append_confirmation(path, poisoned)


if __name__ == "__main__":
    unittest.main()
