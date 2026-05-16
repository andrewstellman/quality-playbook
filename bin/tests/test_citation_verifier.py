"""Tests for bin/citation_verifier.py (schemas.md §5.4 and §5.5)."""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bin import citation_verifier as cv


# ---------------------------------------------------------------------------
# Shared fixture text — a tiny plaintext document exercising the extraction
# algorithm at known anchor points.
#
# Line numbers (1-based) of interest:
#   L1: "Intro"
#   L2: ""
#   L3: "2.4 Device initialization"
#   L4: "The driver MUST..."
#   L10: "RESET has completed."
#   L11: ""
#   L12: "2.5 Reserved"
#   L13: "Reserved..."
# ---------------------------------------------------------------------------

_FIXTURE_TXT = (
    "Intro\n"
    "\n"
    "2.4 Device initialization\n"
    "The driver MUST perform the following steps, in order, before the\n"
    "device is considered operational. Each step has specific precondition\n"
    "and failure-recovery semantics which the driver MUST honor.\n"
    "On failure of VIRTIO_F_VERSION_1 feature negotiation, the device\n"
    "MUST reset itself and MUST NOT accept further driver writes until\n"
    "RESET has completed.\n"
    "\n"
    "2.5 Reserved\n"
    "Reserved for future versions of the specification.\n"
)

_FIXTURE_EXPECTED_24_EXCERPT = (
    "2.4 Device initialization\n"
    "The driver MUST perform the following steps, in order, before the\n"
    "device is considered operational. Each step has specific precondition\n"
    "and failure-recovery semantics which the driver MUST honor.\n"
    "On failure of VIRTIO_F_VERSION_1 feature negotiation, the device\n"
    "MUST reset itself and MUST NOT accept further driver writes until\n"
    "RESET has completed."
)


class ExtractExcerptTests(unittest.TestCase):
    """§5.4 deterministic excerpt extraction."""

    def test_txt_happy_path_by_section(self) -> None:
        excerpt = cv.extract_excerpt(
            _FIXTURE_TXT.encode("utf-8"),
            ".txt",
            "2.4",
            None,
        )
        self.assertEqual(excerpt, _FIXTURE_EXPECTED_24_EXCERPT)

    def test_txt_happy_path_by_line(self) -> None:
        excerpt = cv.extract_excerpt(
            _FIXTURE_TXT.encode("utf-8"),
            ".txt",
            None,
            3,
        )
        self.assertEqual(excerpt, _FIXTURE_EXPECTED_24_EXCERPT)

    def test_line_ending_determinism(self) -> None:
        """\\n, \\r\\n, and \\r variants all produce byte-identical excerpts."""
        unix = _FIXTURE_TXT.encode("utf-8")
        windows = _FIXTURE_TXT.replace("\n", "\r\n").encode("utf-8")
        mac_classic = _FIXTURE_TXT.replace("\n", "\r").encode("utf-8")
        e1 = cv.extract_excerpt(unix, ".txt", None, 3)
        e2 = cv.extract_excerpt(windows, ".txt", None, 3)
        e3 = cv.extract_excerpt(mac_classic, ".txt", None, 3)
        self.assertEqual(e1, e2)
        self.assertEqual(e1, e3)
        self.assertEqual(e1, _FIXTURE_EXPECTED_24_EXCERPT)

    def test_ten_line_cap(self) -> None:
        """A 30-line non-blank paragraph returns exactly 10 lines."""
        lines = [f"line {i}" for i in range(1, 31)]
        doc = ("\n".join(lines)).encode("utf-8")
        excerpt = cv.extract_excerpt(doc, ".txt", None, 1)
        self.assertEqual(excerpt.count("\n"), 9)  # 10 lines joined by "\n"
        self.assertEqual(excerpt.splitlines(), lines[:10])

    def test_blank_line_boundary_exact(self) -> None:
        """A 4-line paragraph followed by a blank returns exactly 4 lines."""
        doc = "one\ntwo\nthree\nfour\n\ntail\n".encode("utf-8")
        excerpt = cv.extract_excerpt(doc, ".txt", None, 1)
        self.assertEqual(excerpt, "one\ntwo\nthree\nfour")

    def test_anchor_at_eof_returns_single_line(self) -> None:
        doc = "alpha\nbeta\ngamma".encode("utf-8")
        excerpt = cv.extract_excerpt(doc, ".txt", None, 3)
        self.assertEqual(excerpt, "gamma")

    def test_blank_anchor_fails(self) -> None:
        with self.assertRaises(cv.CitationResolutionError) as ctx:
            cv.extract_excerpt(_FIXTURE_TXT.encode("utf-8"), ".txt", None, 2)
        self.assertEqual(ctx.exception.code, cv.ERROR_BLANK_ANCHOR)

    def test_line_past_eof_fails(self) -> None:
        with self.assertRaises(cv.CitationResolutionError) as ctx:
            cv.extract_excerpt(_FIXTURE_TXT.encode("utf-8"), ".txt", None, 999)
        self.assertEqual(ctx.exception.code, cv.ERROR_LOCATOR_OUT_OF_RANGE)

    def test_line_zero_or_negative_fails(self) -> None:
        with self.assertRaises(cv.CitationResolutionError) as ctx:
            cv.extract_excerpt(_FIXTURE_TXT.encode("utf-8"), ".txt", None, 0)
        self.assertEqual(ctx.exception.code, cv.ERROR_LOCATOR_OUT_OF_RANGE)

    def test_no_locator_fails(self) -> None:
        with self.assertRaises(cv.CitationResolutionError) as ctx:
            cv.extract_excerpt(_FIXTURE_TXT.encode("utf-8"), ".txt", None, None)
        self.assertEqual(ctx.exception.code, cv.ERROR_LOCATOR_MISSING)

    def test_empty_section_string_fails(self) -> None:
        with self.assertRaises(cv.CitationResolutionError) as ctx:
            cv.extract_excerpt(_FIXTURE_TXT.encode("utf-8"), ".txt", "", None)
        self.assertEqual(ctx.exception.code, cv.ERROR_LOCATOR_MISSING)

    def test_bom_tolerance(self) -> None:
        """A leading UTF-8 BOM is stripped; other bytes are preserved."""
        with_bom = b"\xef\xbb\xbf" + _FIXTURE_TXT.encode("utf-8")
        excerpt = cv.extract_excerpt(with_bom, ".txt", None, 3)
        self.assertEqual(excerpt, _FIXTURE_EXPECTED_24_EXCERPT)

    def test_bom_only_at_position_zero(self) -> None:
        """A BOM byte sequence mid-file stays; it is not stripped."""
        # Line 1 "hello", line 2 blank, line 3 starts with U+FEFF, line 4 "tail".
        # Python str "\ufeff" encodes to UTF-8 bytes b"\xef\xbb\xbf" mid-file.
        doc = "hello\n\n\ufeffworld\ntail".encode("utf-8")
        # Sanity: BOM bytes exist mid-file (not stripped by _decode_document).
        self.assertEqual(doc[:5], b"hello")
        self.assertIn(b"\xef\xbb\xbf", doc[5:])
        # Anchor at line 1 returns only "hello" (next line is blank).
        excerpt_first = cv.extract_excerpt(doc, ".txt", None, 1)
        self.assertEqual(excerpt_first, "hello")
        # Anchor at line 3 preserves the mid-file BOM character.
        excerpt_mid = cv.extract_excerpt(doc, ".txt", None, 3)
        self.assertTrue(excerpt_mid.startswith("\ufeff"))
        self.assertIn("world", excerpt_mid)

    def test_invalid_utf8_fails(self) -> None:
        doc = b"valid\n\xff\xfe not utf-8\n"
        with self.assertRaises(cv.CitationResolutionError) as ctx:
            cv.extract_excerpt(doc, ".txt", None, 1)
        self.assertEqual(ctx.exception.code, cv.ERROR_INVALID_UTF8)

    def test_line_authoritative_over_section_when_both_provided(self) -> None:
        """When both line and section are given, line wins (verify_citation emits a warning)."""
        # section "2.4" resolves to line 3; but we pass line=11 (the "2.5 Reserved" header).
        excerpt = cv.extract_excerpt(
            _FIXTURE_TXT.encode("utf-8"),
            ".txt",
            "2.4",
            11,
        )
        self.assertEqual(excerpt.splitlines()[0], "2.5 Reserved")

    def test_unsupported_extension_fails(self) -> None:
        with self.assertRaises(cv.CitationResolutionError) as ctx:
            cv.extract_excerpt(b"hello", ".rtf", "1", None)
        self.assertEqual(ctx.exception.code, cv.ERROR_UNSUPPORTED_EXTENSION)


class ResolveSectionTests(unittest.TestCase):
    """§5.5 deterministic section resolution."""

    def test_markdown_heading_matches(self) -> None:
        lines = [
            "# Introduction",
            "",
            "Body text here.",
            "",
            "## 2.4 Device initialization",
            "",
            "More body text.",
        ]
        self.assertEqual(cv.resolve_section(lines, ".md", "2.4"), 5)

    def test_markdown_body_does_not_match(self) -> None:
        """`2.4` appearing in body text does NOT match without leading `#`."""
        lines = [
            "# Overview",
            "",
            "Section 2.4 covers device initialization per the spec.",
            "2.4 is also mentioned here",
            "but without the hash-prefix it is body text.",
        ]
        with self.assertRaises(cv.CitationResolutionError) as ctx:
            cv.resolve_section(lines, ".md", "2.4")
        self.assertEqual(ctx.exception.code, cv.ERROR_SECTION_NOT_FOUND)

    def test_markdown_matches_with_trailing_title(self) -> None:
        """`## 2.4 Device initialization` resolves under section "2.4"."""
        lines = ["## 2.4 Device initialization"]
        self.assertEqual(cv.resolve_section(lines, ".md", "2.4"), 1)

    def test_markdown_requires_space_after_hashes(self) -> None:
        lines = ["##2.4 No space"]
        with self.assertRaises(cv.CitationResolutionError) as ctx:
            cv.resolve_section(lines, ".md", "2.4")
        self.assertEqual(ctx.exception.code, cv.ERROR_SECTION_NOT_FOUND)

    def test_markdown_allows_h1_through_h6(self) -> None:
        for prefix in ("#", "##", "###", "####", "#####", "######"):
            lines = [f"{prefix} 7.2 Test"]
            self.assertEqual(cv.resolve_section(lines, ".md", "7.2"), 1)

    def test_plaintext_matches_bare_and_with_title(self) -> None:
        lines = ["2.4 Device initialization"]
        self.assertEqual(cv.resolve_section(lines, ".txt", "2.4"), 1)

    def test_plaintext_lstrips_indent(self) -> None:
        lines = ["   2.4 Device initialization"]
        self.assertEqual(cv.resolve_section(lines, ".txt", "2.4"), 1)

    def test_plaintext_body_does_not_match(self) -> None:
        lines = ["Section 2.4 covers device initialization."]
        with self.assertRaises(cv.CitationResolutionError) as ctx:
            cv.resolve_section(lines, ".txt", "2.4")
        self.assertEqual(ctx.exception.code, cv.ERROR_SECTION_NOT_FOUND)

    def test_zero_matches_fail(self) -> None:
        lines = ["Alpha", "Bravo"]
        with self.assertRaises(cv.CitationResolutionError) as ctx:
            cv.resolve_section(lines, ".txt", "9.9")
        self.assertEqual(ctx.exception.code, cv.ERROR_SECTION_NOT_FOUND)

    def test_two_matches_fail(self) -> None:
        lines = [
            "2.4 First occurrence",
            "unrelated line",
            "2.4 Second occurrence",
        ]
        with self.assertRaises(cv.CitationResolutionError) as ctx:
            cv.resolve_section(lines, ".txt", "2.4")
        self.assertEqual(ctx.exception.code, cv.ERROR_SECTION_AMBIGUOUS)

    def test_regex_injection_is_escaped(self) -> None:
        """`section="2.4.*"` must not match "2.4 ..." body via regex wildcard."""
        lines = [
            "2.4 Real heading",
            "2.4.* Literal heading",
        ]
        # "2.4.*" as a literal should match only the second line.
        self.assertEqual(cv.resolve_section(lines, ".txt", "2.4.*"), 2)

    def test_dot_in_section_matches_literal_dot_only(self) -> None:
        """`section="2.4"` must not match `2X4` via regex `.`."""
        lines = [
            "2X4 body content",
            "2.4 Real heading",
        ]
        self.assertEqual(cv.resolve_section(lines, ".txt", "2.4"), 2)

    def test_section_with_dash_and_letters(self) -> None:
        lines = ["A.2-bis Appendix Two Bis"]
        self.assertEqual(cv.resolve_section(lines, ".txt", "A.2-bis"), 1)


class VerifyCitationTests(unittest.TestCase):
    """End-to-end verify_citation convenience entry point."""

    def _write_doc(self, root: Path, relative: str, text: str) -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        return path

    def test_happy_path_returns_fresh_excerpt(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc_path = self._write_doc(root, "formal_docs/x.txt", _FIXTURE_TXT)
            sha = hashlib.sha256(doc_path.read_bytes()).hexdigest()
            formal_doc = {"source_path": "formal_docs/x.txt", "document_sha256": sha, "tier": 2}
            citation = {
                "document": "formal_docs/x.txt",
                "document_sha256": sha,
                "section": "2.4",
            }
            result = cv.verify_citation(citation, formal_doc, root)
            self.assertTrue(result.ok, result.error_message)
            self.assertEqual(result.excerpt, _FIXTURE_EXPECTED_24_EXCERPT)
            self.assertEqual(result.warnings, ())

    def test_byte_equal_check_passes_when_excerpt_matches(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc_path = self._write_doc(root, "formal_docs/x.txt", _FIXTURE_TXT)
            sha = hashlib.sha256(doc_path.read_bytes()).hexdigest()
            formal_doc = {"source_path": "formal_docs/x.txt", "document_sha256": sha, "tier": 2}
            citation = {
                "document": "formal_docs/x.txt",
                "document_sha256": sha,
                "section": "2.4",
                "citation_excerpt": _FIXTURE_EXPECTED_24_EXCERPT,
            }
            result = cv.verify_citation(citation, formal_doc, root)
            self.assertTrue(result.ok, result.error_message)

    def test_byte_equal_check_rejects_tampered_excerpt(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc_path = self._write_doc(root, "formal_docs/x.txt", _FIXTURE_TXT)
            sha = hashlib.sha256(doc_path.read_bytes()).hexdigest()
            formal_doc = {"source_path": "formal_docs/x.txt", "document_sha256": sha, "tier": 2}
            citation = {
                "document": "formal_docs/x.txt",
                "document_sha256": sha,
                "section": "2.4",
                "citation_excerpt": "A totally made-up paraphrase that reads well.",
            }
            result = cv.verify_citation(citation, formal_doc, root)
            self.assertFalse(result.ok)
            self.assertEqual(result.error_code, cv.ERROR_EXCERPT_MISMATCH)
            self.assertEqual(result.excerpt, _FIXTURE_EXPECTED_24_EXCERPT)

    def test_document_not_found(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            formal_doc = {"source_path": "formal_docs/missing.txt", "document_sha256": "0" * 64, "tier": 2}
            citation = {
                "document": "formal_docs/missing.txt",
                "document_sha256": "0" * 64,
                "line": 1,
            }
            result = cv.verify_citation(citation, formal_doc, root)
            self.assertFalse(result.ok)
            self.assertEqual(result.error_code, cv.ERROR_DOCUMENT_NOT_FOUND)

    def test_hash_mismatch_against_formal_doc(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_doc(root, "formal_docs/x.txt", _FIXTURE_TXT)
            formal_doc = {
                "source_path": "formal_docs/x.txt",
                "document_sha256": "f" * 64,  # wrong
                "tier": 2,
            }
            citation = {
                "document": "formal_docs/x.txt",
                "document_sha256": "f" * 64,
                "section": "2.4",
            }
            result = cv.verify_citation(citation, formal_doc, root)
            self.assertFalse(result.ok)
            self.assertEqual(result.error_code, cv.ERROR_HASH_MISMATCH)

    def test_line_vs_section_mismatch_emits_warning_but_succeeds(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc_path = self._write_doc(root, "formal_docs/x.txt", _FIXTURE_TXT)
            sha = hashlib.sha256(doc_path.read_bytes()).hexdigest()
            formal_doc = {"source_path": "formal_docs/x.txt", "document_sha256": sha, "tier": 2}
            citation = {
                "document": "formal_docs/x.txt",
                "document_sha256": sha,
                "section": "2.4",  # resolves to line 3
                "line": 11,        # "2.5 Reserved"
            }
            result = cv.verify_citation(citation, formal_doc, root)
            self.assertTrue(result.ok, result.error_message)
            self.assertEqual(result.excerpt.splitlines()[0], "2.5 Reserved")
            self.assertEqual(len(result.warnings), 1)
            self.assertIn("line 11", result.warnings[0])
            self.assertIn("section", result.warnings[0])


class VerifyCitationPathTraversalTests(unittest.TestCase):
    """v1.5.6 fix-up 058 — BUG-011 (HIGH) path traversal in verify_citation.

    Pre-fix: `Path(root) / source_path` silently let the right side win
    when absolute, and `../` traversal escaped root. A tampered manifest
    could turn this into an out-of-tree file-read primitive.
    """

    def _write_doc(self, root: Path, relative: str, text: str) -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        return path

    def test_absolute_path_outside_root_rejected(self) -> None:
        with TemporaryDirectory() as tmp_root, TemporaryDirectory() as tmp_outside:
            root = Path(tmp_root)
            outside = Path(tmp_outside)
            secret = self._write_doc(outside, "secret.txt", "out-of-root content")
            formal_doc = {"source_path": str(secret), "document_sha256": "0" * 64, "tier": 2}
            citation = {"document": str(secret), "document_sha256": "0" * 64, "line": 1}
            result = cv.verify_citation(citation, formal_doc, root)
            self.assertFalse(result.ok)
            self.assertEqual(result.error_code, cv.ERROR_DOCUMENT_OUT_OF_ROOT)
            # The error message should NOT include the file's content (no read happened).
            self.assertNotIn("out-of-root content", result.error_message or "")

    def test_relative_traversal_outside_root_rejected(self) -> None:
        with TemporaryDirectory() as tmp_parent:
            parent = Path(tmp_parent)
            root = parent / "root"
            root.mkdir()
            self._write_doc(parent, "secret.txt", "out-of-root content")
            formal_doc = {"source_path": "../secret.txt", "document_sha256": "0" * 64, "tier": 2}
            citation = {"document": "../secret.txt", "document_sha256": "0" * 64, "line": 1}
            result = cv.verify_citation(citation, formal_doc, root)
            self.assertFalse(result.ok)
            self.assertEqual(result.error_code, cv.ERROR_DOCUMENT_OUT_OF_ROOT)

    def test_nested_traversal_outside_root_rejected(self) -> None:
        with TemporaryDirectory() as tmp_parent:
            parent = Path(tmp_parent)
            root = parent / "root" / "deep"
            root.mkdir(parents=True)
            self._write_doc(parent, "secret.txt", "out-of-root content")
            formal_doc = {"source_path": "../../secret.txt", "document_sha256": "0" * 64, "tier": 2}
            citation = {"document": "../../secret.txt", "document_sha256": "0" * 64, "line": 1}
            result = cv.verify_citation(citation, formal_doc, root)
            self.assertFalse(result.ok)
            self.assertEqual(result.error_code, cv.ERROR_DOCUMENT_OUT_OF_ROOT)

    def test_symlink_escape_rejected(self) -> None:
        with TemporaryDirectory() as tmp_parent:
            parent = Path(tmp_parent)
            root = parent / "root"
            root.mkdir()
            outside_target = parent / "secret.txt"
            outside_target.write_bytes(b"out-of-root content")
            link_path = root / "link.txt"
            try:
                link_path.symlink_to(outside_target)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink not supported in this environment: {exc}")
            formal_doc = {"source_path": "link.txt", "document_sha256": "0" * 64, "tier": 2}
            citation = {"document": "link.txt", "document_sha256": "0" * 64, "line": 1}
            result = cv.verify_citation(citation, formal_doc, root)
            self.assertFalse(result.ok)
            self.assertEqual(result.error_code, cv.ERROR_DOCUMENT_OUT_OF_ROOT)

    def test_in_root_path_still_accepted(self) -> None:
        """Containment check must not regress the happy path."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc_path = self._write_doc(root, "formal_docs/x.txt", _FIXTURE_TXT)
            sha = hashlib.sha256(doc_path.read_bytes()).hexdigest()
            formal_doc = {"source_path": "formal_docs/x.txt", "document_sha256": sha, "tier": 2}
            citation = {"document": "formal_docs/x.txt", "document_sha256": sha, "section": "2.4"}
            result = cv.verify_citation(citation, formal_doc, root)
            self.assertTrue(result.ok, result.error_message)


class RstSupportTests(unittest.TestCase):
    """v1.5.7 instruction 060 (A-12): `.rst` is a supported plaintext
    extension end-to-end. reStructuredText (Linux-kernel / Python
    ecosystem; e.g. the VIRTIO 1.2 spec virtio.rst) is treated as
    plaintext — no `.rst` parser. Byte-equality (§5.4) is
    format-agnostic; section resolution (§5.5) uses the plaintext
    branch (matches the title TEXT line, ignoring `=====`/`-----`
    underline rows)."""

    _RST = (
        b"Test Spec\n"
        b"=========\n"
        b"\n"
        b"Section content goes here.\n"
        b"\n"
        b"Sub Heading\n"
        b"-----------\n"
        b"\n"
        b"More body text.\n"
    )

    def test_rst_extension_normalized(self) -> None:
        """`_normalize_extension('.rst')` returns '.rst' WITHOUT
        raising (pre-060 it hard-raised unsupported_extension —
        codex 058 halt-condition #2).

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-060
        A-12:
          Mutation: revert bin/citation_verifier.py:_SUPPORTED_EXTENSIONS
          to `frozenset({".md", ".txt"})` (remove '.rst').
          Expected failure: THIS test fails — `_normalize_extension`
          raises CitationResolutionError(ERROR_UNSUPPORTED_EXTENSION,
          "extension '.rst' is not supported; expected one of .md,
          .txt, .rst"), so the assertEqual is never reached (the
          call raises). The
          test_rst_section_resolution_plaintext_match /
          _line_locator / _underline_not_required tests fail too
          (resolve_section's section path also calls
          _normalize_extension).
          Restoration: re-add '.rst'; all RstSupportTests pass.
          Bite executed during instruction-060 development;
          PASS→FAIL→PASS confirmed (__pycache__ purged between
          mutate and restore).
        """
        self.assertEqual(cv._normalize_extension(".rst"), ".rst")
        self.assertEqual(cv._normalize_extension("RST"), ".rst")
        # Unsupported extensions still hard-reject (allow-list intact).
        with self.assertRaises(cv.CitationResolutionError) as ctx:
            cv._normalize_extension(".pdf")
        self.assertEqual(ctx.exception.code, cv.ERROR_UNSUPPORTED_EXTENSION)

    def test_rst_section_resolution_plaintext_match(self) -> None:
        """`resolve_section` finds an `.rst` section by matching the
        title TEXT line via the plaintext branch (same lstrip+literal
        pattern as `.txt`)."""
        lines = self._RST.decode("utf-8").splitlines()
        self.assertEqual(cv.resolve_section(lines, ".rst", "Test Spec"), 1)
        self.assertEqual(
            cv.resolve_section(lines, ".rst", "Sub Heading"), 6
        )

    def test_rst_line_locator_extracts_excerpt(self) -> None:
        """A `line` locator into a `.rst` doc extracts identically to
        `.txt`/`.md` (the extract_excerpt line path is
        format-agnostic and never calls _normalize_extension)."""
        self.assertEqual(
            cv.extract_excerpt(self._RST, ".rst", None, 4),
            "Section content goes here.",
        )
        self.assertEqual(
            cv.extract_excerpt(self._RST, ".rst", None, 9),
            "More body text.",
        )

    def test_rst_section_underline_not_required(self) -> None:
        """Citing an `.rst` section by its TITLE resolves to the
        title TEXT line — the `=====`/`-----` underline below it is
        NOT required for, and does not interfere with, resolution
        (the documented weaker-but-correct `.rst` section semantics,
        schemas.md §5.5). The adopter cites the human-readable title
        ("Test Spec"), exactly as they would for `.md`/`.txt`."""
        lines = self._RST.decode("utf-8").splitlines()
        anchor = cv.resolve_section(lines, ".rst", "Test Spec")
        self.assertEqual(anchor, 1)
        self.assertEqual(lines[anchor - 1], "Test Spec")     # title line
        self.assertEqual(lines[anchor], "=========")         # underline below it
        # A title with no underline at all still resolves (the
        # underline is decorative, not load-bearing for resolution).
        no_underline = ["Intro", "", "Plain body, no === row.", ""]
        self.assertEqual(
            cv.resolve_section(no_underline, ".rst", "Intro"), 1
        )


if __name__ == "__main__":
    unittest.main()
