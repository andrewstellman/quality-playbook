"""v1.5.7 instruction 089 F8 — pin the qpb_validate.py `event=`
schema against references/qpb_validate_event_schema.md.

Two load-bearing assertions:
  1. The set of event names bin/qpb_validate.py actually emits ==
     the set documented in the schema doc (catches an added/removed
     event that wasn't documented, or stale doc rows).
  2. Every `validation_complete` emission carries the `status` and
     `findings` fields adopters pattern-match (the backward-compat
     anchor from the schema doc's policy section).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_QPB_ROOT = Path(__file__).resolve().parents[2]
_QPB_VALIDATE = _QPB_ROOT / "bin" / "qpb_validate.py"
_SCHEMA_DOC = _QPB_ROOT / "references" / "qpb_validate_event_schema.md"

_EMIT_LITERAL = re.compile(r'\bem\.emit\(\s*"([a-z_]+)"')
# The one dynamically-named emit: em.emit(info.pop("event"), **info)
# always produces event=info (see check_environment §6.5 infos).
_DYNAMIC_INFO = re.compile(r'em\.emit\(\s*info\.pop\("event"\)')
# Schema-doc table rows: | `event_name` | ...
_DOC_EVENT = re.compile(r'^\|\s*`([a-z_]+)`\s*\|')


class QpbValidateEventSchemaTests(unittest.TestCase):
    """Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160) — BITE EXECUTED during
    instruction-089 development:
      Mutation: in bin/qpb_validate.py rename `status=` to `state=`
        in the `em.emit("validation_complete", status="ok", ...)`
        call.
      Observed failure (purged __pycache__ first):
        FAIL: test_validation_complete_carries_status_and_findings
        AssertionError: a validation_complete emission is missing
          required field(s): {'status'}
      Mutation reverted; test passes.
    """

    def _source(self) -> str:
        return _QPB_VALIDATE.read_text(encoding="utf-8")

    def test_emitted_event_names_match_documented_set(self) -> None:
        src = self._source()
        emitted = set(_EMIT_LITERAL.findall(src))
        if _DYNAMIC_INFO.search(src):
            emitted.add("info")
        documented = set()
        for line in _SCHEMA_DOC.read_text(encoding="utf-8").splitlines():
            m = _DOC_EVENT.match(line)
            if m:
                documented.add(m.group(1))
        self.assertEqual(
            emitted, documented,
            f"qpb_validate.py event= names and the schema doc have "
            f"drifted. emitted-not-documented={sorted(emitted - documented)}; "
            f"documented-not-emitted={sorted(documented - emitted)}. "
            f"Update references/qpb_validate_event_schema.md to match "
            f"the emit call sites (or vice versa).")

    def test_validation_complete_carries_status_and_findings(self) -> None:
        src = self._source()
        # Accumulate each em.emit("validation_complete", ...) statement
        # (it spans until the balanced close paren) and assert the
        # required pattern-matched fields are present.
        idx = 0
        marker = 'em.emit("validation_complete"'
        seen = 0
        while True:
            i = src.find(marker, idx)
            if i == -1:
                break
            seen += 1
            # Walk to the matching ')' from the '(' after em.emit
            depth = 0
            j = src.index("(", i)
            k = j
            while k < len(src):
                c = src[k]
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            stmt = src[i:k + 1]
            missing = {
                f for f in ("status", "findings")
                if f"{f}=" not in stmt
            }
            self.assertEqual(
                missing, set(),
                f"a validation_complete emission is missing required "
                f"field(s): {missing} — adopters pattern-match "
                f"`event=validation_complete status=… findings=…`; "
                f"renames need a deprecation cycle (schema doc policy). "
                f"offending statement: {stmt!r}")
            idx = k + 1
        self.assertGreater(
            seen, 0,
            "no em.emit(\"validation_complete\", ...) call sites found "
            "— the scan anchor is stale; fix this test.")


if __name__ == "__main__":
    unittest.main()
