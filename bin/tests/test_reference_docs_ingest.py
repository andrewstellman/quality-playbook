"""Tests for bin.reference_docs_ingest (v1.5.2)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from bin import reference_docs_ingest as rdi


def _scaffold(tmp: Path, *, skill_version: str = "1.5.2") -> Path:
    """Write a minimal SKILL.md at tmp so benchmark_lib.detect_skill_version resolves."""
    skill = tmp / "SKILL.md"
    skill.write_text(
        f"---\nname: quality-playbook\nmetadata:\n  version: {skill_version}\n---\n",
        encoding="utf-8",
    )
    return tmp


class ReferenceDocsIngestTests(unittest.TestCase):
    def test_empty_reference_docs_yields_empty_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root = _scaffold(Path(d))
            (root / "reference_docs" / "cite").mkdir(parents=True)
            manifest = rdi.ingest(root)
            self.assertEqual(manifest["records"], [])
            self.assertIn("schema_version", manifest)

    def test_cite_file_produces_record_with_tier_1_default(self):
        with tempfile.TemporaryDirectory() as d:
            root = _scaffold(Path(d))
            cite = root / "reference_docs" / "cite"
            cite.mkdir(parents=True)
            (cite / "spec.md").write_text("# Project Spec\n\nFoo bar.\n", encoding="utf-8")
            manifest = rdi.ingest(root)
            self.assertEqual(len(manifest["records"]), 1)
            rec = manifest["records"][0]
            self.assertEqual(rec["source_path"], "reference_docs/cite/spec.md")
            self.assertEqual(rec["tier"], 1)
            self.assertTrue(rec["citation_excerpt"])

    def test_html_tier_marker_upgrades_to_tier_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = _scaffold(Path(d))
            cite = root / "reference_docs" / "cite"
            cite.mkdir(parents=True)
            (cite / "rfc.md").write_text(
                "<!-- qpb-tier: 2 -->\n# External RFC\n\nBody.\n", encoding="utf-8"
            )
            manifest = rdi.ingest(root)
            self.assertEqual(manifest["records"][0]["tier"], 2)

    def test_hash_tier_marker_upgrades_to_tier_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = _scaffold(Path(d))
            cite = root / "reference_docs" / "cite"
            cite.mkdir(parents=True)
            (cite / "rfc.txt").write_text(
                "# qpb-tier: 2\nContent line.\n", encoding="utf-8"
            )
            manifest = rdi.ingest(root)
            self.assertEqual(manifest["records"][0]["tier"], 2)

    def test_top_level_file_is_not_cited(self):
        with tempfile.TemporaryDirectory() as d:
            root = _scaffold(Path(d))
            ref = root / "reference_docs"
            ref.mkdir()
            (ref / "design-notes.md").write_text("Freeform notes.\n", encoding="utf-8")
            manifest = rdi.ingest(root)
            self.assertEqual(manifest["records"], [])
            tier4 = rdi.load_tier4_context(root)
            self.assertEqual(len(tier4), 1)
            self.assertEqual(tier4[0][0], "reference_docs/design-notes.md")

    def test_dotfiles_are_skipped(self):
        """v1.5.4 Phase 3.9.1 BUG 2 regression pin: surfaced during the
        2026-04-30 empirical bootstrap test. .gitkeep files (and other
        dotfiles like .DS_Store) are sentinel placeholders protecting
        otherwise-empty tracked directories — not citable content.
        Pre-fix, _collect walked them, hit the extension gate with
        suffix='', and raised IngestError("unsupported extension ''")
        aborting Phase 1 ingest. Fix: skip dotfiles before the
        extension check. The .md content should still ingest cleanly
        alongside."""
        with tempfile.TemporaryDirectory() as d:
            root = _scaffold(Path(d))
            ref = root / "reference_docs"
            cite = ref / "cite"
            cite.mkdir(parents=True)
            # Sentinel placeholders that the QPB .gitignore !-rules
            # explicitly preserve. _collect must skip them silently.
            (ref / ".gitkeep").write_text("", encoding="utf-8")
            (cite / ".gitkeep").write_text("", encoding="utf-8")
            # A real citable doc alongside.
            (cite / "spec.md").write_text(
                "# Project Spec\n\nThe canonical doc.\n",
                encoding="utf-8",
            )
            # Should NOT raise; should produce exactly the spec.md record.
            manifest = rdi.ingest(root)
            self.assertEqual(len(manifest["records"]), 1)
            self.assertEqual(
                manifest["records"][0]["source_path"],
                "reference_docs/cite/spec.md",
            )
            # And no Tier-4 records for .gitkeep either.
            tier4 = rdi.load_tier4_context(root)
            self.assertEqual(tier4, [])

    def test_ds_store_is_skipped(self):
        """Negative control for the dotfile skip: .DS_Store (macOS
        Finder metadata) reaching _collect would also raise on the
        extension gate. The dotfile-skip rule covers it generically."""
        with tempfile.TemporaryDirectory() as d:
            root = _scaffold(Path(d))
            ref = root / "reference_docs"
            ref.mkdir()
            (ref / ".DS_Store").write_bytes(b"\x00\x01\x02")
            (ref / "notes.md").write_text("Freeform notes.\n", encoding="utf-8")
            manifest = rdi.ingest(root)
            self.assertEqual(manifest["records"], [])  # Tier 4, not citable
            tier4 = rdi.load_tier4_context(root)
            self.assertEqual(len(tier4), 1)
            self.assertEqual(tier4[0][0], "reference_docs/notes.md")

    def test_readme_files_are_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            root = _scaffold(Path(d))
            ref = root / "reference_docs"
            ref.mkdir()
            (ref / "README.md").write_text("adopter-local notes\n", encoding="utf-8")
            (ref / "cite").mkdir()
            (ref / "cite" / "README.md").write_text("cite readme\n", encoding="utf-8")
            manifest = rdi.ingest(root)
            self.assertEqual(manifest["records"], [])
            self.assertEqual(rdi.load_tier4_context(root), [])

    def test_unsupported_extension_rejected_with_hint(self):
        with tempfile.TemporaryDirectory() as d:
            root = _scaffold(Path(d))
            cite = root / "reference_docs" / "cite"
            cite.mkdir(parents=True)
            (cite / "spec.pdf").write_bytes(b"%PDF-1.4\n")
            with self.assertRaises(rdi.IngestError) as ctx:
                rdi.ingest(root)
            self.assertIn("pdftotext", str(ctx.exception))

    def test_tier4_context_sorted_and_returns_all_top_level(self):
        with tempfile.TemporaryDirectory() as d:
            root = _scaffold(Path(d))
            ref = root / "reference_docs"
            (ref / "cite").mkdir(parents=True)
            (ref / "b.md").write_text("b\n", encoding="utf-8")
            (ref / "a.md").write_text("a\n", encoding="utf-8")
            (ref / "cite" / "spec.md").write_text("spec\n", encoding="utf-8")
            paths = [p for p, _ in rdi.load_tier4_context(root)]
            self.assertEqual(paths, [
                "reference_docs/a.md",
                "reference_docs/b.md",
            ])

    def test_manifest_written_to_quality_directory(self):
        with tempfile.TemporaryDirectory() as d:
            root = _scaffold(Path(d))
            cite = root / "reference_docs" / "cite"
            cite.mkdir(parents=True)
            (cite / "spec.md").write_text("spec body\n", encoding="utf-8")
            rdi.ingest(root)
            out = root / "quality" / "formal_docs_manifest.json"
            self.assertTrue(out.is_file())
            manifest = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["records"]), 1)

    def test_manifest_record_uses_document_sha256_field_name(self):
        """Producer↔consumer schema contract: schemas.md §1.6 names the field
        ``document_sha256``; quality_gate.py reads ``document_sha256`` for the
        §10 invariant #3 (citation_stale) check. A stray ``sha256`` key would
        silently disable that check (Round 7 Finding D)."""
        with tempfile.TemporaryDirectory() as d:
            root = _scaffold(Path(d))
            cite = root / "reference_docs" / "cite"
            cite.mkdir(parents=True)
            (cite / "spec.md").write_text("# Spec\n\nBody.\n", encoding="utf-8")
            rdi.ingest(root)
            manifest = json.loads(
                (root / "quality" / "formal_docs_manifest.json").read_text(encoding="utf-8")
            )
            rec = manifest["records"][0]
            self.assertIn("document_sha256", rec)
            self.assertNotIn("sha256", rec)
            self.assertRegex(rec["document_sha256"], r"^[0-9a-f]{64}$")


class ParseTierMarkerTests(unittest.TestCase):
    """Option 1.5: 'malformed != absent'. A file is considered to carry an
    intended tier marker only when some line contains 'qpb-tier'. Absent →
    default Tier 1. Present → must match regex and sit on first non-blank
    line; else raise."""

    # (a) Missing marker (no qpb-tier substring anywhere) → Tier 1, no error.
    def test_a_missing_marker_defaults_to_tier_1(self):
        text = "# Project Spec\n\nBody line.\n"
        self.assertEqual(rdi._parse_tier_marker(text), 1)

    # (b) Marker at wrong position → raises.
    def test_b_marker_not_on_first_non_blank_line_raises(self):
        text = "# Project Spec\n<!-- qpb-tier: 2 -->\nBody.\n"
        with self.assertRaises(rdi.IngestError) as ctx:
            rdi._parse_tier_marker(text)
        msg = str(ctx.exception)
        self.assertIn("first non-blank line", msg)
        self.assertIn("qpb-tier", msg)

    def test_b_marker_on_late_line_raises_even_with_blank_leading_lines(self):
        text = "\n\nprose first\n<!-- qpb-tier: 2 -->\n"
        with self.assertRaises(rdi.IngestError):
            rdi._parse_tier_marker(text)

    # (c) Malformed marker syntax on first non-blank line → raises.
    def test_c_malformed_tier_value_raises(self):
        text = "<!-- qpb-tier: 3 -->\nBody.\n"
        with self.assertRaises(rdi.IngestError) as ctx:
            rdi._parse_tier_marker(text)
        self.assertIn("malformed tier marker", str(ctx.exception))

    def test_c_malformed_syntax_missing_colon_raises(self):
        text = "# qpb-tier 2\nBody.\n"
        with self.assertRaises(rdi.IngestError):
            rdi._parse_tier_marker(text)

    def test_c_malformed_syntax_non_integer_raises(self):
        text = "<!-- qpb-tier: bogus -->\nBody.\n"
        with self.assertRaises(rdi.IngestError):
            rdi._parse_tier_marker(text)

    # (d) Valid marker at position 1 in a short file and in a long file → parses.
    def test_d_valid_marker_short_file(self):
        text = "<!-- qpb-tier: 2 -->\n"
        self.assertEqual(rdi._parse_tier_marker(text), 2)

    def test_d_valid_marker_long_file(self):
        body_lines = "\n".join("line {}".format(i) for i in range(200))
        text = "# qpb-tier: 2\n" + body_lines + "\n"
        self.assertEqual(rdi._parse_tier_marker(text), 2)

    def test_d_valid_marker_after_blank_leading_lines(self):
        # Blank lines before the marker are not "prose before marker" —
        # the marker is still the first non-blank line.
        text = "\n\n   \n<!-- qpb-tier: 2 -->\nContent.\n"
        self.assertEqual(rdi._parse_tier_marker(text), 2)

    # (e) Explicit default for entirely untagged files.
    def test_e_file_with_no_qpb_tier_substring_returns_tier_1(self):
        text = (
            "# Linux kernel coding style\n\n"
            "This is what K&R would have written if they had been forced\n"
            "to work on a kernel for twenty years.\n"
        )
        self.assertEqual(rdi._parse_tier_marker(text), 1)

    # ---- Body-mention exemption (Round 6 Finding 3, C13.8/Fix 3) ----
    # C13.6/A2's Option 1.5 over-tightened: any line containing the substring
    # 'qpb-tier' (including prose) was treated as an intended marker attempt.
    # Three claude-sonnet-4.6 panels flagged this. The refined contract: only
    # body lines that match _TIER_MARKER_RE are misplaced markers; prose
    # mentions are allowed.

    def test_body_mention_of_qpb_tier_does_not_raise_when_valid_marker_present(self):
        """Valid first-line marker plus body prose mentioning 'qpb-tier'
        without full marker syntax must parse cleanly."""
        text = "<!-- qpb-tier: 2 -->\nThis doc uses qpb-tier markers for classification.\n"
        self.assertEqual(rdi._parse_tier_marker(text), 2)

    def test_body_mention_of_qpb_tier_does_not_raise_when_no_first_line_marker(self):
        """No first-line marker, body prose mentioning 'qpb-tier' without
        full marker syntax → default Tier 1, no exception."""
        text = "# Title\nThis doc uses qpb-tier markers.\n"
        self.assertEqual(rdi._parse_tier_marker(text), 1)

    def test_misplaced_full_marker_still_raises(self):
        """Positive control: a body line that matches _TIER_MARKER_RE is a
        real misplaced marker and must still raise. Protects against the
        Option 1.5 bypass being re-opened by an over-loosened fix."""
        text = "# Title\n<!-- qpb-tier: 2 -->\n"
        with self.assertRaises(rdi.IngestError) as ctx:
            rdi._parse_tier_marker(text)
        self.assertIn("first non-blank line", str(ctx.exception))

    def test_misplaced_marker_with_first_line_marker_present_still_raises(self):
        """Positive control: two valid markers — second is misplaced — must
        still raise. The body-marker scan runs regardless of whether the
        first non-blank line is itself a valid marker."""
        text = "<!-- qpb-tier: 2 -->\n<!-- qpb-tier: 1 -->\n"
        with self.assertRaises(rdi.IngestError):
            rdi._parse_tier_marker(text)


class Tier4IngestScopeTests(unittest.TestCase):
    """v1.5.6 codex bootstrap fix (065) — BUG-003 (HIGH).

    load_tier4_context() pre-fix called _collect() which used
    _iter_candidates() / rglob('*'), so a nested archive like
    reference_docs/nested/archive/notes.md got ingested as Tier 4
    despite REQ-003 saying only top-level plaintext + cite/ should
    be ingested. Phase 1 context could be polluted by historical
    archives sitting under reference_docs/ subdirectories.
    """

    def test_bug_003_tier4_context_excludes_nested_non_cite_archives(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            refs = repo / "reference_docs"
            (refs / "cite").mkdir(parents=True)
            (refs / "top.md").write_text("top\n", encoding="utf-8")
            (refs / "nested" / "archive").mkdir(parents=True)
            (refs / "nested" / "archive" / "notes.md").write_text(
                "nested\n", encoding="utf-8"
            )
            self.assertEqual(
                rdi.load_tier4_context(repo),
                [("reference_docs/top.md", "top\n")],
                "Tier 4 ingest must include only top-level plaintext; "
                "cite/ files are formal-doc/Tier 1-2 territory handled "
                "elsewhere; nested archives must NOT pollute Phase 1 context",
            )

    def test_bug_003_tier4_context_skips_readme_and_dotfiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            refs = repo / "reference_docs"
            refs.mkdir()
            (refs / "README.md").write_text("ignored\n", encoding="utf-8")
            (refs / ".hidden.md").write_text("hidden\n", encoding="utf-8")
            (refs / "design.md").write_text("# Design\n", encoding="utf-8")
            self.assertEqual(
                rdi.load_tier4_context(repo),
                [("reference_docs/design.md", "# Design\n")],
            )

    def test_bug_003_tier4_context_returns_empty_when_no_reference_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.assertEqual(rdi.load_tier4_context(repo), [])

    def test_ingest_does_not_touch_nested_non_cite_files(self) -> None:
        """v1.5.6 fix-up 067 C-7: BUG-003 broader closure. Pre-fix
        _iter_candidates() used rglob('*'), so a nested non-cite
        .pdf aborted Phase 1 ingest with `unsupported_extension`,
        and nested plaintext got loaded into memory and processed.
        The fix scopes _iter_candidates to top-level files of
        reference_docs/ AND top-level files of reference_docs/cite/
        only — the two-tier flat structure documented at REQ-003.
        """
        # Need a SKILL.md so benchmark_lib.detect_skill_version
        # resolves; ingest() reads version metadata from it.
        with tempfile.TemporaryDirectory() as tmp:
            repo = _scaffold(Path(tmp))
            refs = repo / "reference_docs"
            cite = refs / "cite"
            cite.mkdir(parents=True)
            (refs / "spec.md").write_text("# Top-level Tier 4\n", encoding="utf-8")
            (cite / "formal.md").write_text(
                "<!-- qpb-tier: 1 -->\n# Formal cite\n", encoding="utf-8"
            )
            # Nested non-cite content — must be IGNORED.
            (refs / "nested" / "archive").mkdir(parents=True)
            (refs / "nested" / "archive" / "skip.md").write_text(
                "# Nested archive (should be ignored)\n", encoding="utf-8"
            )
            (refs / "nested" / "junk.pdf").write_bytes(b"%PDF-1.4 fake\n")

            # ingest() must succeed (does NOT abort on the nested .pdf).
            manifest = rdi.ingest(repo)
            self.assertIsNotNone(manifest)
            # Manifest records are limited to cite/formal.md (only
            # cite/ records appear in the formal-doc manifest).
            cite_paths = sorted(
                rec.get("source_path", "")
                for rec in manifest.get("records", [])
            )
            self.assertEqual(cite_paths, ["reference_docs/cite/formal.md"])

            # collect_documents returns only the two top-level entries.
            collected = rdi.collect_documents(repo)
            collected_paths = sorted(rec.rel_path for rec in collected)
            self.assertEqual(
                collected_paths,
                ["reference_docs/cite/formal.md", "reference_docs/spec.md"],
                "_iter_candidates / collect_documents must NOT recurse into "
                "nested/archive/ — that's the BUG-003 broader closure",
            )

            # load_tier4_context returns only the top-level non-cite file.
            tier4 = rdi.load_tier4_context(repo)
            tier4_paths = sorted(p for p, _ in tier4)
            self.assertEqual(tier4_paths, ["reference_docs/spec.md"])


if __name__ == "__main__":
    unittest.main()
