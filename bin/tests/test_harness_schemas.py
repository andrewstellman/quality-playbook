"""v1.5.9 instruction 210 — harness skill schema invariants.

Stdlib-only (no jsonschema dep) — matches the existing bin/tests/
toolchain. Run via:

    python3 -m pytest bin/tests/test_harness_schemas.py -v

Covers six assertions per the instruction § Phase 1C deliverables:

  1. All four harness-side schemas parse as valid JSON Schema draft-07.
  2. The worker-side heartbeat schema also parses.
  3. The two heartbeat schemas are BYTE-IDENTICAL (open both, compare
     bytes — not content equivalence; Council finding C-3).
  4. Every schema declares `task_id` as a string with format `uuid`.
  5. Every schema declares `schema_version` as a string property.
  6. Mutation-verification expectation: adding any whitespace to one
     heartbeat schema causes assertion 3 to fail. The mutation is
     not performed here; see the instruction § H Mutation
     verification for how this test fails on a deliberate byte-flip.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

_QPB_ROOT = Path(__file__).resolve().parents[2]
_HARNESS_SCHEMAS_DIR = (
    _QPB_ROOT / "plugins" / "quality-playbook-harness"
    / "skills" / "quality-playbook-harness" / "schemas"
)
_WORKER_SCHEMAS_DIR = (
    _QPB_ROOT / "plugins" / "quality-playbook"
    / "skills" / "quality-playbook" / "schemas"
)

_HARNESS_SCHEMA_FILES = (
    _HARNESS_SCHEMAS_DIR / "plan.schema.json",
    _HARNESS_SCHEMAS_DIR / "job_manifest.schema.json",
    _HARNESS_SCHEMAS_DIR / "heartbeat.schema.json",
    _HARNESS_SCHEMAS_DIR / "result.schema.json",
)
_WORKER_HEARTBEAT_SCHEMA = _WORKER_SCHEMAS_DIR / "heartbeat.schema.json"
_HARNESS_HEARTBEAT_SCHEMA = _HARNESS_SCHEMAS_DIR / "heartbeat.schema.json"


class TestHarnessSchemas(unittest.TestCase):
    def test_harness_schemas_parse(self) -> None:
        """Assertion 1: all four harness-side schemas parse as JSON."""
        for schema_path in _HARNESS_SCHEMA_FILES:
            with self.subTest(schema=str(schema_path)):
                self.assertTrue(
                    schema_path.is_file(),
                    f"schema file missing: {schema_path}",
                )
                with open(schema_path, encoding="utf-8") as fh:
                    data = json.load(fh)
                # Draft-07 declaration check (a soft validity check —
                # stdlib doesn't ship a JSON Schema validator, so we
                # assert the $schema field instead of running full
                # meta-schema validation).
                self.assertEqual(
                    data.get("$schema"),
                    "http://json-schema.org/draft-07/schema#",
                    f"{schema_path} missing draft-07 $schema declaration",
                )

    def test_worker_heartbeat_schema_parses(self) -> None:
        """Assertion 2: the worker-side heartbeat schema parses."""
        self.assertTrue(_WORKER_HEARTBEAT_SCHEMA.is_file())
        with open(_WORKER_HEARTBEAT_SCHEMA, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(
            data.get("$schema"),
            "http://json-schema.org/draft-07/schema#",
        )

    def test_heartbeat_schemas_byte_identical(self) -> None:
        """Assertion 3: byte-identity between the two heartbeat
        schemas (Council finding C-3 silent drift guard).

        Mutation verification: adding any whitespace to one of the
        two files — even a trailing newline — causes this assertion
        to fail. The instruction's § H mutation example for this
        test deliberately flips one byte to confirm the test catches
        it.
        """
        self.assertTrue(_WORKER_HEARTBEAT_SCHEMA.is_file())
        self.assertTrue(_HARNESS_HEARTBEAT_SCHEMA.is_file())
        worker_bytes = _WORKER_HEARTBEAT_SCHEMA.read_bytes()
        harness_bytes = _HARNESS_HEARTBEAT_SCHEMA.read_bytes()
        self.assertEqual(
            worker_bytes,
            harness_bytes,
            "heartbeat schemas DIVERGE byte-for-byte — Council "
            "finding C-3 silent drift; fix by copying one onto the "
            "other and re-committing.",
        )

    def test_task_id_uuid_format(self) -> None:
        """Assertion 4: every schema declares `task_id` as
        type=string + format=uuid AND lists it in the schema's
        `required` array (per panelist C Q2-required-gap from the
        v210 self-Council review). The A2A-ready contract requires
        task_id to be MANDATORY, not just declared.
        """
        all_schemas = list(_HARNESS_SCHEMA_FILES) + [
            _WORKER_HEARTBEAT_SCHEMA,
        ]
        for schema_path in all_schemas:
            with self.subTest(schema=str(schema_path)):
                with open(schema_path, encoding="utf-8") as fh:
                    data = json.load(fh)
                props = data.get("properties", {}) or {}
                required = data.get("required", []) or []
                self.assertIn(
                    "task_id", props,
                    f"{schema_path}: missing 'task_id' property",
                )
                task_id_prop = props["task_id"]
                self.assertEqual(
                    task_id_prop.get("type"), "string",
                    f"{schema_path}: task_id.type must be 'string'",
                )
                self.assertEqual(
                    task_id_prop.get("format"), "uuid",
                    f"{schema_path}: task_id.format must be 'uuid'",
                )
                self.assertIn(
                    "task_id", required,
                    f"{schema_path}: 'task_id' must appear in the "
                    f"schema's required[] array "
                    f"(A2A-ready contract: mandatory, not just "
                    f"declared)",
                )

    def test_schema_version_string_typed(self) -> None:
        """Assertion 5: every schema declares `schema_version` as
        type=string AND lists it in the schema's `required` array
        (per panelist C Q2-required-gap from the v210 self-Council
        review).
        """
        all_schemas = list(_HARNESS_SCHEMA_FILES) + [
            _WORKER_HEARTBEAT_SCHEMA,
        ]
        for schema_path in all_schemas:
            with self.subTest(schema=str(schema_path)):
                with open(schema_path, encoding="utf-8") as fh:
                    data = json.load(fh)
                props = data.get("properties", {}) or {}
                required = data.get("required", []) or []
                self.assertIn(
                    "schema_version", props,
                    f"{schema_path}: missing 'schema_version' property",
                )
                sv_prop = props["schema_version"]
                self.assertEqual(
                    sv_prop.get("type"), "string",
                    f"{schema_path}: schema_version.type must be "
                    "'string'",
                )
                self.assertIn(
                    "schema_version", required,
                    f"{schema_path}: 'schema_version' must appear "
                    f"in the schema's required[] array "
                    f"(A2A-ready contract)",
                )


if __name__ == "__main__":
    unittest.main()
