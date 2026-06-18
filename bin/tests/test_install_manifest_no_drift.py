"""v1.5.7 instruction 077 (addendum r3 §3.2 / acceptance #11) —
INSTALL_CLOSURE must not drift from install_skill._bundle_files().

This is the load-bearing guard the whole Phase 0 validator depends
on: if the validator's bundled-file manifest silently diverges from
what the installer actually copies, the validator passes while the
install is broken — the exact failure class the validator exists to
kill (addendum §12 row 1). The r1 and r2 §3.2 enumerations were both
hand-written-from-memory and both wrong (caught by the 076 and 076b
Councils); r3 §3.2 is machine-derived from this very function. This
test pins that derivation so it cannot rot.

Acceptance #11 is scoped to INSTALL_CLOSURE *only* — INSTALL_
SCAFFOLDING and INSTALL_ENVIRONMENT have a different production code
path (the AGENTS.md `cp` block / host environment), so a separate
non-drift test asserts they stay disjoint from the closure rather
than equal to _bundle_files().
"""

from __future__ import annotations

import unittest
from pathlib import Path

# v1.5.8 instruction 208: bundle source root moved into the plugin
# skill folder.
_QPB_ROOT = (
    Path(__file__).resolve().parents[2] / "plugins" / "quality-playbook" / "skills" / "quality-playbook"
)


class InstallClosureNoDriftTests(unittest.TestCase):

    def test_install_closure_matches_bundle_files(self) -> None:
        """set(INSTALL_CLOSURE paths) == set(_bundle_files() dsts).

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-077 —
        BITE EXECUTED during instruction-077 development:
          Mutation: delete the
          {"path": "references/verification.md", ...} entry from
          bin/qpb_validate.py:INSTALL_CLOSURE.
          Observed failure (purged __pycache__ first):
            FAIL: test_install_closure_matches_bundle_files
            AssertionError: Items in the first set but not the
            second:
            'references/verification.md' : INSTALL_CLOSURE drift vs
            _bundle_files(): missing_from_manifest=
            {'references/verification.md'} phantom_in_manifest=set()
          Restoration: entry restored; test PASS again (47 == 47,
          symmetric difference empty).
        """
        from bin.install_skill import _bundle_files
        from bin.qpb_validate import INSTALL_CLOSURE

        expected = set(str(dst) for _src, dst in _bundle_files(_QPB_ROOT))
        actual = set(entry["path"] for entry in INSTALL_CLOSURE)
        missing = expected - actual
        phantom = actual - expected
        self.assertEqual(
            expected, actual,
            "INSTALL_CLOSURE drift vs _bundle_files(): "
            f"missing_from_manifest={missing} "
            f"phantom_in_manifest={phantom}")

    def test_install_closure_count_is_54(self) -> None:
        """47 through v1.5.7-085; 086 (A-26) bundled 3 more bin/*.py
        (qpb_config / run_state_lib / validate_phase_artifacts) → 50;
        v1.5.7 089 F8 adds references/qpb_validate_event_schema.md
        (auto-bundled by _bundle_files()'s references/* glob) → 51;
        v1.5.7 089x adds bin/_purpose.py (the shared purpose-banner +
        version-reader + attribution-banner helper) → 52; v1.5.7 090k
        adds bin/qpb_validate.py so the Phase 0 validator self-
        resolves at the install root after the 2026-05-24 openfga-
        run3 Mode-A dogfood → 53; v1.5.7 090u adds skill-template.
        gitignore at the top level so the
        ``scaffolding_missing_gitignore`` remediation points at a real
        file on a channel install (root cause of the 2026-05-25 Keto
        run5 + NATS run2 Phase-0 friction) → 54. A count check still
        catches an accidental duplicate the set comparison would
        mask. NOTE: addendum §3.2's "47 entries" prose is now
        five-times stale — an orchestrator/addendum-owned doc-
        currency follow-up (the worker must not modify the canonical
        addendum); the live _bundle_files() closure is the source of
        truth and the drift test pins INSTALL_CLOSURE to it."""
        # v1.5.7 109: 54 → 55 (bin/qpb_phase.py shipped for the
        # SKILL.md phase-boundary sentinel).
        # v1.5.7 132: 55 → 57 (+ai_context/TOOLKIT.md explicit entry,
        # +references/DOC_GATHERING_PROMPT.md moved here from repo root
        # so it auto-ships via the references/*.md glob).
        # v1.5.9 1B.0: 57 → 58 (+bin/phase_identity.py — shared phase
        # number→name table + ::QPB:: envelope writer imported by
        # qpb_phase / quality_gate / run_state_lib).
        # v1.5.9 1B: 58 → 59 (+bin/qpb_heartbeat.py — worker-side
        # heartbeat emit helper the SKILL.md heartbeat section calls).
        # v1.5.10 052 (SKILL.md trim): 59 → 63 (+references/recheck_mode.md,
        # +references/phase7_guide.md, +references/phase5_reconciliation_guide.md,
        # +references/artifact_contract.md — sections extracted from SKILL.md to
        # lazy-loaded references; more may follow as the trim proceeds).
        from bin.qpb_validate import INSTALL_CLOSURE
        self.assertEqual(len(INSTALL_CLOSURE), 63)
        paths = [e["path"] for e in INSTALL_CLOSURE]
        self.assertEqual(len(paths), len(set(paths)),
                         "duplicate path in INSTALL_CLOSURE")

    def test_scaffolding_and_environment_disjoint_from_closure(self) -> None:
        """INSTALL_SCAFFOLDING / INSTALL_ENVIRONMENT must not leak
        into the drift-tested closure (addendum §3.2 / acceptance
        #11 decoupling — the 076b a1 self-contradiction fix)."""
        from bin.qpb_validate import (
            INSTALL_CLOSURE, INSTALL_SCAFFOLDING, INSTALL_ENVIRONMENT)
        closure_paths = set(e["path"] for e in INSTALL_CLOSURE)
        scaffold_paths = set(e["path"] for e in INSTALL_SCAFFOLDING)
        self.assertEqual(closure_paths & scaffold_paths, set(),
                         "scaffolding path leaked into INSTALL_CLOSURE")
        # environment entries are kind-only (no "path") — assert that
        # invariant so a future path= addition can't silently couple.
        for e in INSTALL_ENVIRONMENT:
            self.assertNotIn("path", e,
                             f"INSTALL_ENVIRONMENT entry has a path: {e}")
        self.assertEqual(len(INSTALL_SCAFFOLDING), 3)
        # v1.5.7 089y: was 5 (python_version, tiktoken, yaml,
        # cli_on_path, bash_available); 089y dropped the two
        # python_pkg entries because the shipped runtime imports
        # neither (tiktoken is dev-test-only, yaml has zero
        # importers). New count: 3.
        self.assertEqual(len(INSTALL_ENVIRONMENT), 3)


if __name__ == "__main__":
    unittest.main()
