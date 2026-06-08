"""Phase 7 variation fixtures — deliberately-broken test cases.

Each fixture under bin/tests/fixtures/phase7_variations/<variation>/ is a
partial v1.5.1 target repo: formal_docs/ with a plaintext + sidecar,
quality/formal_docs_manifest.json, and quality/requirements_manifest.json.
The test driver copies the fixture into a tempdir, runs the relevant
Phase 5+6 gate checks, and asserts the expected failure lines (or
clean-pass, for the non-failure variation).

Three variations, per Implementation Plan §Phase 7 line 238-241:

  malformed_citation/      — Tier 1 REQ whose citation_excerpt does NOT
                             match the source text. Invariant #11
                             byte-equality check must FAIL.
  stale_spec/              — Tier 1 REQ with a correct excerpt but the
                             citation.document_sha256 is stale. Invariant
                             #3 citation_stale check must FAIL.
  empty_informal_docs/     — Fully conforming fixture plus an empty
                             informal_docs/ folder (README only, which
                             the gate skips). Must PASS cleanly — Tier 4
                             absence is a valid Spec Gap state.
"""

from __future__ import annotations

import io
import shutil
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

_FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures" / "phase7_variations"
# v1.5.8 instruction 208: quality_gate.py moved to skills/quality-playbook/scripts/.
_GATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "skills" / "quality-playbook" / "scripts"
)
if str(_GATE_DIR) not in sys.path:
    sys.path.insert(0, str(_GATE_DIR))
import quality_gate  # noqa: E402


def _copy_fixture(name: str, dst: Path) -> Path:
    """Copy fixture tree into dst/target; return the target path."""
    src = _FIXTURES_ROOT / name
    target = dst / "target"
    shutil.copytree(src, target)
    return target


def _run_check(func, *args, **kwargs):
    """Reset counters, capture output, return (fails, warns, stdout)."""
    quality_gate.FAIL = 0
    quality_gate.WARN = 0
    buf = io.StringIO()
    with redirect_stdout(buf):
        func(*args, **kwargs)
    return quality_gate.FAIL, quality_gate.WARN, buf.getvalue()


class Phase7MalformedCitation(unittest.TestCase):
    """Fixture: Tier 1 REQ with a fabricated citation_excerpt."""

    def test_byte_equality_check_rejects_fabricated_excerpt(self):
        with TemporaryDirectory() as tmp:
            repo = _copy_fixture("malformed_citation", Path(tmp))
            q = repo / "quality"
            fails, _, out = _run_check(
                quality_gate.check_v1_5_0_requirements_manifest, repo, q
            )
            self.assertGreaterEqual(fails, 1)
            # Byte-equality failure message names invariant #11.
            self.assertIn("byte-equal", out)
            self.assertIn("invariant #11", out)
            # Failure line uses the Phase 6 r0 record_id= format.
            self.assertIn("record_id=REQ-001", out)
            # Target file is named.
            self.assertIn("formal_docs/spec.txt", out)


class Phase7StaleSpec(unittest.TestCase):
    """Fixture: Tier 1 REQ citation carries an old document_sha256."""

    def test_hash_mismatch_reports_citation_stale(self):
        with TemporaryDirectory() as tmp:
            repo = _copy_fixture("stale_spec", Path(tmp))
            q = repo / "quality"
            fails, _, out = _run_check(
                quality_gate.check_v1_5_0_requirements_manifest, repo, q
            )
            self.assertGreaterEqual(fails, 1)
            # Hash mismatch invariant.
            self.assertIn("invariant #3", out)
            self.assertIn("citation_stale", out)
            self.assertIn("record_id=REQ-001", out)


class Phase7EmptyInformalDocs(unittest.TestCase):
    """Fixture: conforming repo with an empty informal_docs/ folder."""

    def test_full_gate_dispatcher_passes_with_empty_informal_docs(self):
        """Spec Gap for Tier 4 is valid — the full dispatcher must not FAIL."""
        with TemporaryDirectory() as tmp:
            repo = _copy_fixture("empty_informal_docs", Path(tmp))
            q = repo / "quality"
            # INDEX.md is required by invariant #10 when v1.5.1 manifests
            # are present. Stub one in so the fixture isolates the
            # informal_docs/ check rather than the INDEX check.
            (q / "INDEX.md").write_text(
                "# Run Index — phase7-empty-informal\n\n"
                "```json\n"
                '{"run_timestamp_start": "2026-04-20T12:00:00Z",'
                '"run_timestamp_end": "2026-04-20T12:00:00Z",'
                '"duration_seconds": 0,"qpb_version": "1.4.6",'
                '"target_repo_path": ".","target_repo_git_sha": "unknown",'
                '"target_role_breakdown": null,"phases_executed": [],'
                '"summary": {"requirements": {}, "bugs": {}, "gate_verdict": "pass"},'
                '"artifacts": []}'
                "\n```\n",
                encoding="utf-8",
            )
            # Emit the empty semantic-check wrapper so invariant #17 passes.
            (q / "citation_semantic_check.json").write_text(
                '{"schema_version": "1.4.6", "generated_at": "2026-04-20T12:00:00Z", '
                '"reviews": [{"req_id": "REQ-001", "reviewer": "claude-opus-4.7", '
                '"verdict": "supports", "notes": ""},'
                '{"req_id": "REQ-001", "reviewer": "gpt-5.4", "verdict": "supports", '
                '"notes": ""},'
                '{"req_id": "REQ-001", "reviewer": "gemini-2.5-pro", "verdict": "supports", '
                '"notes": ""}]}',
                encoding="utf-8",
            )
            fails, _, out = _run_check(
                quality_gate.check_v1_5_0_gate_invariants, repo, q
            )
            self.assertEqual(fails, 0, f"Expected clean pass, got:\n{out}")

    def test_plaintext_extensions_accept_readme_in_empty_informal_docs(self):
        with TemporaryDirectory() as tmp:
            repo = _copy_fixture("empty_informal_docs", Path(tmp))
            fails, _, out = _run_check(
                quality_gate.check_v1_5_0_cite_extensions, repo
            )
            self.assertEqual(fails, 0, out)

    def test_cite_extensions_accept_readme_in_empty_cite_dir(self):
        """reference_docs/cite/ with only a README must pass cleanly.

        v1.5.2 moved the plaintext-only invariant from formal_docs/+informal_docs/
        to reference_docs/cite/. The check must still skip README.md and emit no
        extension-violation failures when the cite folder is otherwise empty.
        """
        with TemporaryDirectory() as tmp:
            repo = _copy_fixture("empty_cite_dir", Path(tmp))
            fails, _, out = _run_check(
                quality_gate.check_v1_5_0_cite_extensions, repo
            )
            self.assertEqual(fails, 0, out)


if __name__ == "__main__":
    unittest.main()
