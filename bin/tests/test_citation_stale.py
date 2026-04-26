"""Producer↔consumer round-trip for the §10 invariant #3 (citation_stale) check.

Round 7 Finding D: ``bin/reference_docs_ingest.py`` (producer) wrote the
formal-doc hash under key ``sha256``, while ``.github/skills/quality_gate.py``
(consumer) read ``document_sha256``. The mismatch silently disabled the
citation-staleness invariant — both sides looked correct in isolation, but
together the check was a no-op. These tests bind the two sides to the same
key by exercising the full round-trip:

  1. Run ``rdi.ingest()`` on a fixture (producer emits ``document_sha256``).
  2. Build a minimal ``requirements_manifest.json`` whose Tier-1 citation
     carries a *stale* ``document_sha256``.
  3. Invoke the gate's ``check_v1_5_0_requirements_manifest`` and assert
     the citation_stale failure line is emitted.

If the producer reverts to writing ``sha256`` (or the consumer is renamed),
the consumer's ``fd_rec.get("document_sha256")`` returns ``None``, the
isinstance gate at quality_gate.py:1749 short-circuits, and the assertion
on the citation_stale message fails. That is the test that would have
caught Finding D in CI.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from bin import reference_docs_ingest as rdi

_QPB_ROOT = Path(__file__).resolve().parents[2]
_GATE_DIR = _QPB_ROOT / ".github" / "skills" / "quality_gate"
if str(_GATE_DIR) not in sys.path:
    sys.path.insert(0, str(_GATE_DIR))
import quality_gate  # noqa: E402


def _scaffold(tmp: Path, *, skill_version: str = "1.5.2") -> Path:
    """Match the convention in test_reference_docs_ingest.py."""
    (tmp / "SKILL.md").write_text(
        f"---\nname: quality-playbook\nmetadata:\n  version: {skill_version}\n---\n",
        encoding="utf-8",
    )
    return tmp


def _run_check(func, *args, **kwargs):
    quality_gate.FAIL = 0
    quality_gate.WARN = 0
    buf = io.StringIO()
    with redirect_stdout(buf):
        func(*args, **kwargs)
    return quality_gate.FAIL, quality_gate.WARN, buf.getvalue()


class CitationStaleRoundTrip(unittest.TestCase):
    def test_producer_hash_is_consumed_under_document_sha256_key(self):
        """Stale citation hash → invariant #3 fail line emitted.

        Setup: producer writes a hash for the spec; the requirements manifest
        deliberately carries a different (zero) hash. The gate must see both
        hashes (under the contract key) and emit the citation_stale fail.
        """
        with tempfile.TemporaryDirectory() as d:
            root = _scaffold(Path(d))
            cite = root / "reference_docs" / "cite"
            cite.mkdir(parents=True)
            spec_path = cite / "spec.md"
            spec_path.write_text(
                "# Spec\n\n## Section A\n\nOriginal body line one.\n",
                encoding="utf-8",
            )
            rdi.ingest(root)

            fd_manifest_path = root / "quality" / "formal_docs_manifest.json"
            fd_manifest = json.loads(fd_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(len(fd_manifest["records"]), 1)
            fd_rec = fd_manifest["records"][0]
            producer_hash = fd_rec["document_sha256"]
            source_path = fd_rec["source_path"]

            stale_hash = "0" * 64
            self.assertNotEqual(producer_hash, stale_hash)

            req_manifest = {
                "schema_version": "1.5.2",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "records": [
                    {
                        "id": "REQ-001",
                        "tier": 1,
                        "functional_section": "test",
                        "citation": {
                            "document": source_path,
                            "section": "Section A",
                            "citation_excerpt": "Original body line one.",
                            "document_sha256": stale_hash,
                        },
                    }
                ],
            }
            (root / "quality" / "requirements_manifest.json").write_text(
                json.dumps(req_manifest), encoding="utf-8"
            )

            fails, _, out = _run_check(
                quality_gate.check_v1_5_0_requirements_manifest, root, root / "quality"
            )
            self.assertGreaterEqual(fails, 1)
            self.assertIn("citation.document_sha256 does not match FORMAL_DOC", out)
            self.assertIn("invariant #3", out)
            self.assertIn("citation_stale", out)
            self.assertIn("record_id=REQ-001", out)

    def test_matching_producer_hash_does_not_trigger_citation_stale(self):
        """Negative control: when the requirements citation carries the same
        hash the producer emitted, invariant #3 must NOT fail. Guards against
        a future fix that satisfies the positive test by always failing."""
        with tempfile.TemporaryDirectory() as d:
            root = _scaffold(Path(d))
            cite = root / "reference_docs" / "cite"
            cite.mkdir(parents=True)
            (cite / "spec.md").write_text(
                "# Spec\n\n## Section A\n\nOriginal body line one.\n",
                encoding="utf-8",
            )
            rdi.ingest(root)

            fd_rec = json.loads(
                (root / "quality" / "formal_docs_manifest.json").read_text(encoding="utf-8")
            )["records"][0]

            req_manifest = {
                "schema_version": "1.5.2",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "records": [
                    {
                        "id": "REQ-001",
                        "tier": 1,
                        "functional_section": "test",
                        "citation": {
                            "document": fd_rec["source_path"],
                            "section": "Section A",
                            "citation_excerpt": "Original body line one.",
                            "document_sha256": fd_rec["document_sha256"],
                        },
                    }
                ],
            }
            (root / "quality" / "requirements_manifest.json").write_text(
                json.dumps(req_manifest), encoding="utf-8"
            )

            _, _, out = _run_check(
                quality_gate.check_v1_5_0_requirements_manifest, root, root / "quality"
            )
            self.assertNotIn("citation_stale", out)
            self.assertNotIn("invariant #3", out)

    def test_post_ingest_source_mutation_triggers_citation_stale(self):
        """Production failure mode: ingest, then mutate the source file.

        Models the real-world scenario where a spec gets updated upstream but
        nobody re-runs `reference_docs_ingest`. The producer's stored hash
        (frozen at ingest time) must diverge from the now-mutated source's
        hash, and the gate must emit citation_stale on the next run.
        """
        with tempfile.TemporaryDirectory() as d:
            root = _scaffold(Path(d))
            cite = root / "reference_docs" / "cite"
            cite.mkdir(parents=True)
            spec_path = cite / "spec.md"
            original_body = "# Spec\n\n## Section A\n\nOriginal body line one.\n"
            spec_path.write_text(original_body, encoding="utf-8")
            rdi.ingest(root)

            # Capture the producer hash AT INGEST TIME — this is what the
            # citation in the requirements manifest will quote.
            fd_manifest_path = root / "quality" / "formal_docs_manifest.json"
            fd_rec = json.loads(fd_manifest_path.read_text(encoding="utf-8"))["records"][0]
            ingest_time_hash = fd_rec["document_sha256"]
            source_path = fd_rec["source_path"]

            # Build a requirements manifest using the ingest-time hash.
            # This is the citation that was correct at the moment it was authored.
            req_manifest = {
                "schema_version": "1.5.2",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "records": [
                    {
                        "id": "REQ-001",
                        "tier": 1,
                        "functional_section": "test",
                        "citation": {
                            "document": source_path,
                            "section": "Section A",
                            "citation_excerpt": "Original body line one.",
                            "document_sha256": ingest_time_hash,
                        },
                    }
                ],
            }
            (root / "quality" / "requirements_manifest.json").write_text(
                json.dumps(req_manifest), encoding="utf-8"
            )

            # NOW mutate the source document AFTER ingest, simulating an
            # upstream edit that nobody propagated through re-ingest.
            spec_path.write_text(
                "# Spec\n\n## Section A\n\nMUTATED body line one.\n",
                encoding="utf-8",
            )

            # Re-run ingest so the formal_docs_manifest reflects the new
            # source hash — but the requirements manifest still quotes the
            # OLD ingest-time hash. This is the divergence the gate must catch.
            rdi.ingest(root)

            new_fd_rec = json.loads(fd_manifest_path.read_text(encoding="utf-8"))["records"][0]
            post_mutation_hash = new_fd_rec["document_sha256"]
            self.assertNotEqual(ingest_time_hash, post_mutation_hash,
                                "Test setup error: mutation did not change the hash")

            fails, _, out = _run_check(
                quality_gate.check_v1_5_0_requirements_manifest, root, root / "quality"
            )
            self.assertGreaterEqual(fails, 1)
            self.assertIn("citation.document_sha256 does not match FORMAL_DOC", out)
            self.assertIn("invariant #3", out)
            self.assertIn("citation_stale", out)
            self.assertIn("record_id=REQ-001", out)


if __name__ == "__main__":
    unittest.main()
