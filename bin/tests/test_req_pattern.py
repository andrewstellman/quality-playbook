#!/usr/bin/env python3
"""Tests for quality_gate.extract_req_pattern (v1.5.2, Lever 2 REQ Pattern field)."""

import sys
import unittest
from pathlib import Path

# v1.5.10 instruction 052 (repo-hygiene): relocated from
# .github/skills/quality_gate/tests/ into bin/tests/. quality_gate.py canonical
# source is the 209 plugins/ scripts dir, falling back to the 208 skills/ path.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = (_REPO_ROOT / "plugins" / "quality-playbook"
                / "skills" / "quality-playbook" / "scripts")
if not (_SCRIPTS_DIR / "quality_gate.py").is_file():
    _SCRIPTS_DIR = _REPO_ROOT / "skills" / "quality-playbook" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import quality_gate  # noqa: E402


class ReqPatternTests(unittest.TestCase):
    def test_absent_returns_none(self):
        block = "### REQ-001: do a thing\n- Summary: foo\n"
        self.assertIsNone(quality_gate.extract_req_pattern(block))

    def test_whitelist_accepted(self):
        block = "### REQ-010: feature bits\n- Pattern: whitelist\n"
        self.assertEqual(quality_gate.extract_req_pattern(block), "whitelist")

    def test_parity_accepted(self):
        block = "### REQ-020: encode/decode parity\n- Pattern: parity\n"
        self.assertEqual(quality_gate.extract_req_pattern(block), "parity")

    def test_compensation_accepted(self):
        block = "### REQ-030: filter compensation\n- Pattern: compensation\n"
        self.assertEqual(quality_gate.extract_req_pattern(block), "compensation")

    def test_invalid_raises(self):
        block = "### REQ-010: x\n- Pattern: bogus\n"
        with self.assertRaises(ValueError):
            quality_gate.extract_req_pattern(block)

    def test_case_insensitive_key(self):
        block = "### REQ-010: x\n- pattern: whitelist\n"
        self.assertEqual(quality_gate.extract_req_pattern(block), "whitelist")


if __name__ == "__main__":
    unittest.main()
