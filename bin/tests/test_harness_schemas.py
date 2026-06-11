"""v1.5.9 Phase 1B — cross-skill harness schema consistency.

The heartbeat schema is the load-bearing contract between the QPB worker
skill (which emits heartbeat.ndjson) and the harness skill (which reads
it). Both ship a copy; they MUST be byte-identical or the two sides can
silently drift (Council finding C-3 — silent drift risk). This test pins
byte-equality so a one-sided edit fails loudly.

MUTATION-VERIFY EVIDENCE (in-tree per DEVELOPMENT_PROCESS.md §Mutation-
test discipline), v1.5.9 instruction 005:
  Mutation: append a space to the harness-side heartbeat.schema.json.
  Observed: test_heartbeat_schema_byte_identical_across_skills FAILs
    (byte lengths / content differ). Restored → OK.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKER_SCHEMA = (
    _REPO_ROOT / "plugins" / "quality-playbook" / "skills"
    / "quality-playbook" / "schemas" / "heartbeat.schema.json")
_HARNESS_SCHEMA = (
    _REPO_ROOT / "plugins" / "quality-playbook-harness" / "skills"
    / "quality-playbook-harness" / "schemas" / "heartbeat.schema.json")


class HarnessSchemaConsistencyTests(unittest.TestCase):

    def test_both_heartbeat_schemas_exist(self):
        self.assertTrue(_WORKER_SCHEMA.is_file(),
                        f"worker-side heartbeat schema missing: {_WORKER_SCHEMA}")
        self.assertTrue(_HARNESS_SCHEMA.is_file(),
                        f"harness-side heartbeat schema missing: {_HARNESS_SCHEMA}")

    def test_heartbeat_schema_byte_identical_across_skills(self):
        """The two copies must be byte-for-byte identical — the cross-skill
        contract (Council C-3). A one-sided edit is a silent-drift bug."""
        worker_bytes = _WORKER_SCHEMA.read_bytes()
        harness_bytes = _HARNESS_SCHEMA.read_bytes()
        self.assertEqual(
            worker_bytes, harness_bytes,
            "heartbeat.schema.json differs between the worker skill and the "
            "harness skill — they must be byte-identical (Council C-3 silent-"
            "drift contract). Sync the two copies.")

    def test_heartbeat_schema_is_valid_json_with_required_fields(self):
        schema = json.loads(_WORKER_SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema.get("type"), "object")
        # the four always-required top-level fields
        self.assertEqual(set(schema.get("required", [])),
                         {"ts", "task_id", "schema_version", "status"})
        # schema_version pinned to "1"
        self.assertEqual(
            schema["properties"]["schema_version"]["enum"], ["1"])
        # progress vs terminal oneOf branches present
        self.assertEqual(len(schema.get("oneOf", [])), 2)


if __name__ == "__main__":
    unittest.main()
