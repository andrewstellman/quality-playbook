"""v1.5.7 191 FINDING-50 — schemas.md not shipped + no prose
citations in shipped .md files.

The running skill does not consult schemas.md at execution time;
quality_gate.py implements the schema's invariants in code, and
adopters never read schemas.md to drive the agent. The 82K file
stays at the repo root as a maintainer / design-contract
reference but is NOT shipped in the channel bundle.

Three-kind classification taxonomy:
- A (code comment): .py source comment — LEAVE
- B (prose pointer, substance inline): .md citation where
  surrounding prose states the rule completely — STRIP
- C (prose pointer, no substance): .md citation where substance
  is only in schemas.md — INLINE OR REWRITE

After 191, every shipped .md file (under
`quality_playbook_cli/_bundle/`) has ZERO `schemas.md` prose
citations. Kind-A code comments in .py files remain (by design).
"""
from __future__ import annotations

import pathlib
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]
_BUNDLE = _REPO / "quality_playbook_cli" / "_bundle"


class SchemasMdBundleExclusionTests(unittest.TestCase):
    """schemas.md MUST NOT appear in the channel bundle. The
    file lives at the repo root only."""

    def test_schemas_md_not_in_bundle_root(self) -> None:
        """`_bundle/schemas.md` must not exist after staging."""
        path = _BUNDLE / "schemas.md"
        self.assertFalse(
            path.exists(),
            f"schemas.md should not ship in the bundle — found "
            f"at {path}. Re-stage via "
            f"`python3 bin/build_channel_package.py --stage`.")

    def test_schemas_md_not_anywhere_in_bundle_tree(
            self) -> None:
        """No file named `schemas.md` (or `Schemas.md`, case-
        insensitive) anywhere under _bundle/."""
        if not _BUNDLE.exists():
            self.skipTest(
                "_bundle/ not staged — run "
                "`python3 bin/build_channel_package.py --stage`")
        hits = [
            p for p in _BUNDLE.rglob("*")
            if p.is_file()
            and p.name.lower() == "schemas.md"
        ]
        self.assertEqual(
            hits, [], f"schemas.md found in bundle at {hits}")


class SchemasMdNotInShippedProseTests(unittest.TestCase):
    """Every shipped `.md` file under `_bundle/` carries ZERO
    `schemas.md` prose citations. Kind-A code comments in .py
    files are exempt — adopters don't read gate source code."""

    def test_no_schemas_md_pointer_in_shipped_prose(
            self) -> None:
        """Walk every `.md` file under `_bundle/` and confirm
        none mention `schemas.md`. A non-empty list means the
        FINDING-50 strip incomplete."""
        if not _BUNDLE.exists():
            self.skipTest(
                "_bundle/ not staged — run "
                "`python3 bin/build_channel_package.py --stage`")
        offenders: list[tuple[str, int, str]] = []
        for path in _BUNDLE.rglob("*.md"):
            text = path.read_text(encoding="utf-8",
                                    errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if "schemas.md" in line:
                    rel = str(path.relative_to(_REPO))
                    offenders.append((rel, i, line.strip()))
        self.assertEqual(
            offenders, [],
            "Found schemas.md prose citations in shipped .md "
            "files (must be zero per FINDING-50). Offenders: "
            + "\n".join(
                f"  {r}:{n}  {s[:120]}"
                for r, n, s in offenders))

    def test_root_tree_shipped_md_files_also_clean(
            self) -> None:
        """Source-of-truth check: the root-tree `.md` files that
        the stager copies into `_bundle/` must also be clean.
        Otherwise re-staging would re-introduce the citations."""
        root_files = [
            "SKILL.md",
            "references/phase2_generation_guide.md",
            "references/phase1_exploration_guide.md",
            "references/phase6_verify_guide.md",
            "references/challenge_gate.md",
            "references/runners_and_models.md",
            "references/run_state_schema.md",
            "references/role_map_queries.md",
            "references/code-only-mode.md",
            "phase_prompts/phase2.md",
            "phase_prompts/phase3.md",
            "phase_prompts/phase4.md",
            "phase_prompts/phase5.md",
            "phase_prompts/phase6.md",
            "phase_prompts/phase6_auditor.md",
        ]
        offenders: list[tuple[str, int, str]] = []
        for rel in root_files:
            path = _REPO / rel
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8",
                                    errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if "schemas.md" in line:
                    offenders.append((rel, i, line.strip()))
        self.assertEqual(
            offenders, [],
            "Found schemas.md prose citations in root-tree "
            "shipped sources. Strip per FINDING-50 + re-stage. "
            "Offenders: " + "\n".join(
                f"  {r}:{n}  {s[:120]}"
                for r, n, s in offenders))


class SchemasMdAuditLogTests(unittest.TestCase):
    """The audit log at `quality/audits/191_schemas_md_
    classification.md` is the worker's proof of the kind-
    A/B/C classification."""

    def test_schemas_md_audit_log_exists(self) -> None:
        path = (_REPO / "quality" / "audits"
                / "191_schemas_md_classification.md")
        self.assertTrue(
            path.exists(),
            f"missing 191 audit log at {path}")

    def test_audit_log_documents_three_kind_taxonomy(
            self) -> None:
        """Audit log must mention all three kinds (A/B/C) and
        confirm the kind-A code-comment exemption."""
        path = (_REPO / "quality" / "audits"
                / "191_schemas_md_classification.md")
        text = path.read_text(encoding="utf-8").lower()
        self.assertIn("kind-a", text)
        self.assertIn("kind-b", text)
        self.assertIn("kind-c", text)


if __name__ == "__main__":
    unittest.main()
