"""v1.5.7 instruction 077 (addendum r3 §3.3.2 / acceptance #12) —
remediation-catalog completeness.

Guards against adding a new §3.2 check-type without a remediation
path: every `kind` used across INSTALL_CLOSURE / INSTALL_SCAFFOLDING
/ INSTALL_ENVIRONMENT must map to >=1 finding code in the §3.3.2
catalog, and every catalog entry must produce a non-empty command
for every platform.
"""

from __future__ import annotations

import shlex
import unittest

from bin import qpb_validate as v

_PLATFORMS = ("macos", "linux", "windows-powershell", "windows-cmd")
_EXPECTED_FINDING_CODES = {
    "install_absent", "install_partial", "install_wrong_ai_tool",
    "install_version_skew", "scaffolding_missing_gitignore",
    "scaffolding_missing_reference_docs", "python_version_too_old",
    "python_pkg_missing", "ai_cli_not_on_path",
    "bash_unavailable_mechanical_required",
    "bash_unavailable_mechanical_not_required",
    "validator_invoked_from_clone", "multiple_ai_tool_markers",
    # v1.5.7 instruction 084 (A-20 reframed): the 14th code. Live
    # ship-validation (codex click, 2026-05-18) showed an agent
    # mis-reading a stale quality/ tree as a resumable run; this
    # blocked-severity finding makes the validator say so.
    "stale_quality_dir",
}


class RemediationCatalogTests(unittest.TestCase):

    def test_catalog_has_exactly_14_codes(self) -> None:
        """§3.3.2 was a 13-code catalog through v1.5.7-083b; instruction
        084 (A-20 reframed) adds the 14th, `stale_quality_dir`. NOTE:
        addendum §13's "13 codes" prose is now stale — that is an
        orchestrator/addendum-owned doc-currency follow-up (the worker
        must not modify the canonical addendum spec); the catalog
        itself is the source of truth and this pin tracks it."""
        self.assertEqual(set(v.FINDING_CATALOG), _EXPECTED_FINDING_CODES)
        self.assertEqual(len(v.FINDING_CATALOG), 14)

    def test_every_manifest_kind_maps_to_a_finding_code(self) -> None:
        """Every kind in the three manifests has >=1 catalog code.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-077 —
        BITE EXECUTED during instruction-077 development:
          Mutation: delete the "agent_file": [...] entry from
          bin/qpb_validate.py:KIND_TO_FINDING_CODES.
          Observed failure (purged __pycache__ first):
            FAIL: test_every_manifest_kind_maps_to_a_finding_code
            AssertionError: None is not true : kind 'agent_file' has
            no finding code in the §3.3.2 catalog
          Restoration: entry restored; test PASS again.
        """
        kinds = set()
        for e in v.INSTALL_CLOSURE:
            kinds.add(e["kind"])
        for e in v.INSTALL_SCAFFOLDING:
            kinds.add(e["kind"])
        for e in v.INSTALL_ENVIRONMENT:
            kinds.add(e["kind"])
        for kind in sorted(kinds):
            codes = v.KIND_TO_FINDING_CODES.get(kind)
            self.assertTrue(
                codes,
                f"kind {kind!r} has no finding code in the §3.3.2 catalog")
            for code in codes:
                self.assertIn(
                    code, v.FINDING_CATALOG,
                    f"kind {kind!r} maps to unknown finding code {code!r}")

    def test_every_catalog_entry_has_command_for_every_platform(self) -> None:
        for code in v.FINDING_CATALOG:
            for plat in _PLATFORMS:
                cmd = v.command_for_platform(code, plat)
                self.assertIsInstance(cmd, str)
                self.assertTrue(
                    cmd.strip(),
                    f"{code}/{plat} produced an empty command")

    def test_default_platform_resolves(self) -> None:
        """platform=None resolves to the host platform (no raise)."""
        for code in v.FINDING_CATALOG:
            self.assertTrue(v.command_for_platform(code))

    def test_unix_commands_shlex_parse(self) -> None:
        """Acceptance #12/#14 overlap: every Unix-form command parses
        via shlex.split without raising (balanced quoting)."""
        for code in v.FINDING_CATALOG:
            for plat in ("macos", "linux"):
                cmd = v.command_for_platform(code, plat)
                try:
                    shlex.split(cmd)
                except ValueError as exc:
                    self.fail(f"{code}/{plat} not shlex-parseable: "
                              f"{exc} :: {cmd!r}")

    def test_unknown_platform_raises(self) -> None:
        with self.assertRaises(ValueError):
            v.command_for_platform("install_absent", "solaris")


if __name__ == "__main__":
    unittest.main()
