"""Phase 6 end-to-end pipeline integration test.

Exercises the Layer-2 wire from `collect_tier_12_reqs` through
`build_prompts_for_member` (skipping the actual LLM round-trip) to
`parse_member_response` + `assemble_reviews` + `write_semantic_check`,
and finally the gate check `check_v1_5_0_semantic_check`.

Two scenarios:

1. Small Tier 1/2 set (1 REQ, 3 reviewers, unanimous supports) — the
   Phase 6 happy path on virtio-style content.
2. 20-REQ set that triggers batching (≥15 threshold). Verifies that
   prompt count scales correctly and that the assembled reviews[]
   array contains every expected entry.

These are the "sanity check that Phase 6 works end-to-end" per the
Phase 6 kickoff Task 5; the formal multi-repo benchmark belongs in
Phase 7.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from bin import council_semantic_check as csc
from bin.council_config import DEFAULT_COUNCIL_MEMBERS

# Import the gate module from its package directory so we exercise the
# real check function rather than a re-implementation.
# v1.5.8 instruction 208: quality_gate.py moved to skills/quality-playbook/scripts/.
_GATE_DIR = Path(__file__).resolve().parents[2] / "skills" / "quality-playbook" / "scripts"
if str(_GATE_DIR) not in sys.path:
    sys.path.insert(0, str(_GATE_DIR))
import quality_gate  # noqa: E402


def _req_record(req_id, tier, excerpt):
    return {
        "id": req_id,
        "tier": tier,
        "functional_section": "Device initialization",
        "description": f"REQ {req_id} description",
        "citation": {
            "document": "formal_docs/virtio-excerpt.txt",
            "document_sha256": "a" * 64,
            "section": "2.4",
            "line": 142,
            "citation_excerpt": excerpt,
        },
    }


def _seed_requirements(quality_dir, records):
    quality_dir.mkdir(parents=True, exist_ok=True)
    (quality_dir / "requirements_manifest.json").write_text(
        json.dumps({
            "schema_version": "1.4.6",
            "generated_at": "2026-04-19T14:30:22Z",
            "records": records,
        }),
        encoding="utf-8",
    )


def _member_response(reqs, verdict="supports"):
    """Build a synthetic per-member response array."""
    return json.dumps([
        {"req_id": r.req_id, "verdict": verdict, "reasoning": ""}
        for r in reqs
    ])


class Phase6VirtioMiniHappyPath(unittest.TestCase):
    """Small Tier 1/2 set → prompts → synthetic responses → gate passes."""

    def test_end_to_end_single_req(self):
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            quality_dir = repo / "quality"
            _seed_requirements(quality_dir, [
                _req_record("REQ-017", 1, "A device MUST reset itself...")
            ])

            # Collect Tier 1/2 REQs from the manifest.
            reqs = csc.collect_tier_12_reqs(quality_dir)
            self.assertEqual(len(reqs), 1)
            self.assertEqual(reqs[0].req_id, "REQ-017")

            # Build one prompt per Council member (<15 REQs → no batching).
            responses_by_member = {}
            for member in DEFAULT_COUNCIL_MEMBERS:
                prompts = csc.build_prompts_for_member(member, reqs)
                self.assertEqual(len(prompts), 1)
                # Simulate the member returning a supports verdict.
                entries = csc.parse_member_response(
                    member, _member_response(reqs, "supports"),
                    [r.req_id for r in reqs],
                )
                responses_by_member[member] = entries

            reviews = csc.assemble_reviews(responses_by_member)
            self.assertEqual(len(reviews), 3)  # 1 REQ × 3 reviewers

            path = csc.write_semantic_check(repo, reviews, schema_version="1.4.6")
            self.assertTrue(path.is_file())

            # Gate check passes.
            quality_gate.FAIL = 0
            quality_gate.WARN = 0
            buf = io.StringIO()
            with redirect_stdout(buf):
                quality_gate.check_v1_5_0_semantic_check(quality_dir)
            self.assertEqual(quality_gate.FAIL, 0, buf.getvalue())
            self.assertEqual(quality_gate.WARN, 0, buf.getvalue())

    def test_end_to_end_majority_overreach_fails_gate(self):
        """Two of three reviewers flag overreaches → gate FAILs invariant #17."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            quality_dir = repo / "quality"
            _seed_requirements(quality_dir, [
                _req_record("REQ-017", 1, "Overreaching claim")
            ])
            reqs = csc.collect_tier_12_reqs(quality_dir)

            # Two overreaches, one supports.
            verdicts = ["overreaches", "overreaches", "supports"]
            responses_by_member = {
                member: csc.parse_member_response(
                    member,
                    json.dumps([{
                        "req_id": reqs[0].req_id,
                        "verdict": verdict,
                        "reasoning": f"{member} verdict",
                    }]),
                    [reqs[0].req_id],
                )
                for member, verdict in zip(DEFAULT_COUNCIL_MEMBERS, verdicts)
            }
            reviews = csc.assemble_reviews(responses_by_member)
            csc.write_semantic_check(repo, reviews, schema_version="1.4.6")

            quality_gate.FAIL = 0
            buf = io.StringIO()
            with redirect_stdout(buf):
                quality_gate.check_v1_5_0_semantic_check(quality_dir)
            self.assertGreaterEqual(quality_gate.FAIL, 1)
            self.assertIn("REQ-017", buf.getvalue())
            self.assertIn("invariant #17", buf.getvalue())


class Phase6BatchingEndToEnd(unittest.TestCase):
    """20 Tier 1/2 REQs → prompts batched at 5/batch → 60 reviews total."""

    def test_twenty_req_batching_assembles_60_reviews(self):
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            quality_dir = repo / "quality"
            records = [
                _req_record(f"REQ-{i:03d}", 1 if i % 2 else 2, f"excerpt {i}")
                for i in range(1, 21)
            ]
            _seed_requirements(quality_dir, records)

            reqs = csc.collect_tier_12_reqs(quality_dir)
            self.assertEqual(len(reqs), 20)

            responses_by_member = {}
            for member in DEFAULT_COUNCIL_MEMBERS:
                prompts = csc.build_prompts_for_member(member, reqs)
                # 20 REQs, batch_size=5 → ceil(20/5) = 4 prompts per member.
                self.assertEqual(len(prompts), 4)
                # Synthetic responses: concatenate one entry per REQ, matching
                # the batch partition. Since parse_member_response validates
                # the entire expected set at once, build a single response
                # covering all 20 REQs (stable sorted).
                sorted_reqs = sorted(reqs, key=lambda r: r.req_id)
                entries = csc.parse_member_response(
                    member,
                    _member_response(sorted_reqs, "supports"),
                    [r.req_id for r in sorted_reqs],
                )
                responses_by_member[member] = entries

            reviews = csc.assemble_reviews(responses_by_member)
            # 20 REQs × 3 reviewers = 60 entries.
            self.assertEqual(len(reviews), 60)

            csc.write_semantic_check(repo, reviews, schema_version="1.4.6")

            # Verify the gate passes: every Tier 1/2 REQ has 3 reviews, all
            # supports.
            quality_gate.FAIL = 0
            quality_gate.WARN = 0
            buf = io.StringIO()
            with redirect_stdout(buf):
                quality_gate.check_v1_5_0_semantic_check(quality_dir)
            self.assertEqual(quality_gate.FAIL, 0, buf.getvalue())
            self.assertEqual(quality_gate.WARN, 0, buf.getvalue())


class Phase6SpecGapEndToEnd(unittest.TestCase):
    """Spec Gap run (only Tier 3/4/5 REQs) → empty reviews[], gate passes."""

    def test_spec_gap_end_to_end(self):
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            quality_dir = repo / "quality"
            # 3 REQs, all Tier 3+ — no citations, nothing to review.
            records = [
                {"id": f"REQ-{i:03d}", "tier": t, "functional_section": "X",
                 "description": f"R {i}"}
                for i, t in enumerate([3, 4, 5], start=1)
            ]
            _seed_requirements(quality_dir, records)

            reqs = csc.collect_tier_12_reqs(quality_dir)
            self.assertEqual(reqs, [])

            # Orchestrator still writes the file with an empty reviews[]
            # (per §9 contract completeness).
            csc.write_semantic_check(repo, [], schema_version="1.4.6")

            quality_gate.FAIL = 0
            buf = io.StringIO()
            with redirect_stdout(buf):
                quality_gate.check_v1_5_0_semantic_check(quality_dir)
            self.assertEqual(quality_gate.FAIL, 0, buf.getvalue())


if __name__ == "__main__":
    unittest.main()
