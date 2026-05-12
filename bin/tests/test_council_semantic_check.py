"""Tests for bin/council_semantic_check.py (Phase 6 Layer-2 assembly)."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from bin import council_semantic_check as csc
from bin.council_config import DEFAULT_COUNCIL_MEMBERS


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _req_manifest_with_tiers(tiers: list[int]) -> str:
    records = []
    for idx, tier in enumerate(tiers, start=1):
        rec = {
            "id": f"REQ-{idx:03d}",
            "tier": tier,
            "functional_section": "Test",
            "description": f"Requirement {idx}",
        }
        if tier in (1, 2):
            rec["citation"] = {
                "document": "formal_docs/x.txt",
                "document_sha256": "a" * 64,
                "section": "2.4",
                "line": 3,
                "citation_excerpt": f"excerpt for REQ-{idx:03d}",
            }
        records.append(rec)
    return json.dumps(
        {
            "schema_version": "1.4.6",
            "generated_at": "2026-04-19T14:30:22Z",
            "records": records,
        }
    )


def _fixed_now() -> datetime:
    return datetime(2026, 4, 19, 14, 30, 22, tzinfo=timezone.utc)


class CollectTier12ReqsTests(unittest.TestCase):
    def test_missing_manifest_returns_empty_list(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertEqual(csc.collect_tier_12_reqs(Path(tmp)), [])

    def test_only_tier_12_reqs_included(self) -> None:
        with TemporaryDirectory() as tmp:
            q = Path(tmp)
            _write(q / "requirements_manifest.json", _req_manifest_with_tiers([1, 3, 2, 4, 5, 1]))
            reqs = csc.collect_tier_12_reqs(q)
            ids = [r.req_id for r in reqs]
            self.assertEqual(ids, ["REQ-001", "REQ-003", "REQ-006"])
            tiers = [r.tier for r in reqs]
            self.assertEqual(tiers, [1, 2, 1])

    def test_req_without_citation_is_skipped(self) -> None:
        """Layer-1 already flags missing citations; Layer-2 skips them."""
        with TemporaryDirectory() as tmp:
            q = Path(tmp)
            _write(
                q / "requirements_manifest.json",
                json.dumps({
                    "schema_version": "1.4.6",
                    "generated_at": "2026-04-19T14:30:22Z",
                    "records": [
                        {"id": "REQ-001", "tier": 1, "functional_section": "X"},
                        {
                            "id": "REQ-002",
                            "tier": 2,
                            "functional_section": "X",
                            "citation": {
                                "document": "formal_docs/x.txt",
                                "section": "1",
                                "citation_excerpt": "valid",
                            },
                        },
                    ],
                }),
            )
            ids = [r.req_id for r in csc.collect_tier_12_reqs(q)]
            self.assertEqual(ids, ["REQ-002"])

    def test_locator_rendering(self) -> None:
        with TemporaryDirectory() as tmp:
            q = Path(tmp)
            _write(q / "requirements_manifest.json", _req_manifest_with_tiers([2]))
            reqs = csc.collect_tier_12_reqs(q)
            self.assertEqual(reqs[0].citation_locator, "section=2.4 line=3")


class BuildPromptsForMemberTests(unittest.TestCase):
    def _reqs(self, n: int):
        return [
            csc.ReqRecord(
                req_id=f"REQ-{i:03d}",
                tier=1,
                description=f"REQ {i}",
                citation_excerpt=f"excerpt {i}",
                citation_document="formal_docs/x.txt",
                citation_locator="section=2.4",
            )
            for i in range(1, n + 1)
        ]

    def test_empty_reqs_returns_empty_list(self) -> None:
        self.assertEqual(csc.build_prompts_for_member("claude-opus-4.7", []), [])

    def test_under_threshold_one_prompt(self) -> None:
        prompts = csc.build_prompts_for_member("claude-opus-4.7", self._reqs(10))
        self.assertEqual(len(prompts), 1)
        self.assertIn("claude-opus-4.7", prompts[0])
        self.assertIn("REQ-001", prompts[0])
        self.assertIn("REQ-010", prompts[0])

    def test_threshold_inclusive_one_prompt(self) -> None:
        prompts = csc.build_prompts_for_member("gpt-5.4", self._reqs(15))
        self.assertEqual(len(prompts), 1)

    def test_over_threshold_triggers_batching(self) -> None:
        prompts = csc.build_prompts_for_member("gemini-2.5-pro", self._reqs(16))
        # 16 REQs, batch size 5 → ceil(16/5) = 4 prompts.
        self.assertEqual(len(prompts), 4)
        # Each prompt mentions the member identifier.
        for p in prompts:
            self.assertIn("gemini-2.5-pro", p)

    def test_batching_20_reqs(self) -> None:
        """Briefing acceptance: 20 Tier 1/2 REQs → ceil(20/5)=4 batches."""
        prompts = csc.build_prompts_for_member("gemini-2.5-pro", self._reqs(20))
        self.assertEqual(len(prompts), 4)

    def test_prompt_includes_schema_instructions(self) -> None:
        prompts = csc.build_prompts_for_member("claude-opus-4.7", self._reqs(1))
        self.assertIn("supports", prompts[0])
        self.assertIn("overreaches", prompts[0])
        self.assertIn("unclear", prompts[0])
        self.assertIn("JSON array", prompts[0])


class ParseMemberResponseTests(unittest.TestCase):
    def test_valid_response(self) -> None:
        response = json.dumps([
            {"req_id": "REQ-001", "verdict": "supports", "reasoning": "clear match"},
            {"req_id": "REQ-002", "verdict": "overreaches", "reasoning": "too strong"},
        ])
        entries = csc.parse_member_response("claude-opus-4.7", response, ["REQ-001", "REQ-002"])
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].reviewer, "claude-opus-4.7")
        self.assertEqual(entries[0].verdict, "supports")
        self.assertEqual(entries[1].verdict, "overreaches")

    def test_empty_reasoning_is_accepted(self) -> None:
        response = json.dumps([
            {"req_id": "REQ-001", "verdict": "unclear", "reasoning": ""},
        ])
        entries = csc.parse_member_response("gpt-5.4", response, ["REQ-001"])
        self.assertEqual(entries[0].notes, "")

    def test_missing_reasoning_defaults_to_empty(self) -> None:
        response = json.dumps([
            {"req_id": "REQ-001", "verdict": "supports"},
        ])
        entries = csc.parse_member_response("gpt-5.4", response, ["REQ-001"])
        self.assertEqual(entries[0].notes, "")

    def test_invalid_verdict_rejected(self) -> None:
        response = json.dumps([
            {"req_id": "REQ-001", "verdict": "maybe", "reasoning": ""},
        ])
        with self.assertRaises(csc.SemanticCheckError) as ctx:
            csc.parse_member_response("claude-opus-4.7", response, ["REQ-001"])
        self.assertIn("maybe", str(ctx.exception))

    def test_duplicate_req_rejected(self) -> None:
        response = json.dumps([
            {"req_id": "REQ-001", "verdict": "supports", "reasoning": ""},
            {"req_id": "REQ-001", "verdict": "overreaches", "reasoning": ""},
        ])
        with self.assertRaises(csc.SemanticCheckError) as ctx:
            csc.parse_member_response("gpt-5.4", response, ["REQ-001"])
        self.assertIn("duplicate", str(ctx.exception))

    def test_missing_expected_req_rejected(self) -> None:
        response = json.dumps([
            {"req_id": "REQ-001", "verdict": "supports", "reasoning": ""},
        ])
        with self.assertRaises(csc.SemanticCheckError) as ctx:
            csc.parse_member_response(
                "gpt-5.4", response, ["REQ-001", "REQ-002"]
            )
        self.assertIn("REQ-002", str(ctx.exception))

    def test_tolerates_prose_around_json(self) -> None:
        response = (
            "Sure, here's my review:\n"
            "```json\n"
            '[{"req_id": "REQ-001", "verdict": "supports", "reasoning": "x"}]\n'
            "```\n"
        )
        entries = csc.parse_member_response("claude-opus-4.7", response, ["REQ-001"])
        self.assertEqual(entries[0].req_id, "REQ-001")

    def test_non_array_response_rejected(self) -> None:
        response = '{"req_id": "REQ-001", "verdict": "supports"}'
        with self.assertRaises(csc.SemanticCheckError):
            csc.parse_member_response("gpt-5.4", response, ["REQ-001"])

    def test_non_object_element_rejected(self) -> None:
        response = '["not an object"]'
        with self.assertRaises(csc.SemanticCheckError):
            csc.parse_member_response("gpt-5.4", response, ["REQ-001"])


class AssembleReviewsTests(unittest.TestCase):
    def test_flat_output_preserves_order(self) -> None:
        responses = {
            "claude-opus-4.7": [
                csc.ReviewEntry("REQ-001", "claude-opus-4.7", "supports", ""),
                csc.ReviewEntry("REQ-002", "claude-opus-4.7", "supports", ""),
            ],
            "gpt-5.4": [
                csc.ReviewEntry("REQ-001", "gpt-5.4", "overreaches", "notes"),
            ],
        }
        flat = csc.assemble_reviews(responses)
        self.assertEqual(len(flat), 3)
        self.assertEqual(
            [(e.reviewer, e.req_id) for e in flat],
            [("claude-opus-4.7", "REQ-001"),
             ("claude-opus-4.7", "REQ-002"),
             ("gpt-5.4", "REQ-001")],
        )

    def test_reviewer_mismatch_raises(self) -> None:
        responses = {
            "claude-opus-4.7": [
                csc.ReviewEntry("REQ-001", "gpt-5.4", "supports", ""),
            ],
        }
        with self.assertRaises(csc.SemanticCheckError):
            csc.assemble_reviews(responses)


class WriteSemanticCheckTests(unittest.TestCase):
    def test_emits_valid_wrapper_with_reviews_array(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            reviews = [
                csc.ReviewEntry("REQ-001", "claude-opus-4.7", "supports", ""),
                csc.ReviewEntry("REQ-001", "gpt-5.4", "supports", "looks good"),
                csc.ReviewEntry("REQ-001", "gemini-2.5-pro", "unclear", "ambiguous"),
            ]
            path = csc.write_semantic_check(
                repo, reviews, schema_version="1.4.6", now=_fixed_now()
            )
            self.assertEqual(path.name, "citation_semantic_check.json")
            data = json.loads(path.read_text(encoding="utf-8"))
            # §9.1 wrapper: reviews not records.
            self.assertEqual(data["schema_version"], "1.4.6")
            self.assertEqual(data["generated_at"], "2026-04-19T14:30:22Z")
            self.assertIn("reviews", data)
            self.assertNotIn("records", data)
            self.assertEqual(len(data["reviews"]), 3)
            # Per-entry shape.
            self.assertEqual(
                set(data["reviews"][0].keys()),
                {"req_id", "reviewer", "verdict", "notes"},
            )

    def test_empty_reviews_still_writes_valid_wrapper(self) -> None:
        """Spec Gap run: zero Tier 1/2 REQs → empty reviews[] is valid."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            path = csc.write_semantic_check(
                repo, [], schema_version="1.4.6", now=_fixed_now()
            )
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["reviews"], [])


class CouncilConfigTests(unittest.TestCase):
    def test_roster_has_three_members(self) -> None:
        self.assertEqual(len(DEFAULT_COUNCIL_MEMBERS), 3)

    def test_members_are_stable_strings(self) -> None:
        # v1.5.7 Phase 6a roster: claude-opus-4.7, gpt-5.5, claude-sonnet-4.6.
        self.assertIn("claude-opus-4.7", DEFAULT_COUNCIL_MEMBERS)
        self.assertIn("gpt-5.5", DEFAULT_COUNCIL_MEMBERS)
        self.assertIn("claude-sonnet-4.6", DEFAULT_COUNCIL_MEMBERS)


class CLITests(unittest.TestCase):
    def test_main_exits_2_on_unbalanced_args(self) -> None:
        self.assertEqual(csc.main(["some-repo", "--member", "x"]), 2)

    def test_main_exits_2_on_empty_members(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertEqual(csc.main([tmp]), 2)

    def test_main_assembles_from_response_files(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / "quality" / "requirements_manifest.json",
                   _req_manifest_with_tiers([1]))
            response_path = repo / "claude.json"
            response_path.write_text(json.dumps([
                {"req_id": "REQ-001", "verdict": "supports", "reasoning": ""},
            ]))
            rc = csc.main([str(repo), "--member", "claude-opus-4.7",
                          "--response", str(response_path)])
            self.assertEqual(rc, 0)
            out_path = repo / "quality" / "citation_semantic_check.json"
            self.assertTrue(out_path.is_file())
            data = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["reviews"]), 1)

    def test_explicit_assemble_subcommand(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / "quality" / "requirements_manifest.json",
                   _req_manifest_with_tiers([2]))
            response = repo / "gpt.json"
            response.write_text(json.dumps([
                {"req_id": "REQ-001", "verdict": "supports", "reasoning": ""},
            ]))
            # v1.5.7 Phase 6a: use a current-roster member.
            rc = csc.main(["assemble", str(repo),
                          "--member", "gpt-5.5", "--response", str(response)])
            self.assertEqual(rc, 0)
            self.assertTrue((repo / "quality" / "citation_semantic_check.json").is_file())

    def test_assemble_rejects_typo_in_member_identifier(self) -> None:
        """Phase 7 r8: `claude-opus-4.6` (typo) is not in the canonical
        roster and must be rejected at CLI entry with return code 2 and a
        stderr message listing the expected members."""
        import io
        import contextlib
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / "quality" / "requirements_manifest.json",
                   _req_manifest_with_tiers([1]))
            for name in ("r1.json", "r2.json", "r3.json"):
                (repo / name).write_text(json.dumps([
                    {"req_id": "REQ-001", "verdict": "supports", "reasoning": ""},
                ]))
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                rc = csc._assemble_main([
                    str(repo),
                    "--member", "claude-opus-4.6",  # typo — canonical is 4.7
                    "--response", str(repo / "r1.json"),
                    "--member", "gpt-5.4",
                    "--response", str(repo / "r2.json"),
                    "--member", "gemini-2.5-pro",
                    "--response", str(repo / "r3.json"),
                ])
            self.assertEqual(rc, 2)
            err = buf.getvalue()
            self.assertIn("claude-opus-4.6", err)
            self.assertIn("expected one of", err)
            self.assertIn("claude-opus-4.7", err)

    def test_assemble_rejects_duplicate_member_identifiers(self) -> None:
        """Phase 7 r8: the same canonical identifier used twice would slip
        both responses past invariant #17's per-reviewer grouping."""
        import io
        import contextlib
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / "quality" / "requirements_manifest.json",
                   _req_manifest_with_tiers([1]))
            (repo / "a.json").write_text(json.dumps([
                {"req_id": "REQ-001", "verdict": "supports", "reasoning": ""},
            ]))
            (repo / "b.json").write_text(json.dumps([
                {"req_id": "REQ-001", "verdict": "overreaches", "reasoning": ""},
            ]))
            (repo / "c.json").write_text(json.dumps([
                {"req_id": "REQ-001", "verdict": "supports", "reasoning": ""},
            ]))
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                rc = csc._assemble_main([
                    str(repo),
                    "--member", "claude-opus-4.7",
                    "--response", str(repo / "a.json"),
                    "--member", "claude-opus-4.7",  # duplicate
                    "--response", str(repo / "b.json"),
                    # v1.5.7 Phase 6a roster: claude-sonnet-4.6.
                    "--member", "claude-sonnet-4.6",
                    "--response", str(repo / "c.json"),
                ])
            self.assertEqual(rc, 2)
            err = buf.getvalue()
            self.assertIn("duplicate", err)
            self.assertIn("claude-opus-4.7", err)


class PlanModeTests(unittest.TestCase):
    """Phase 7 r1: `semantic-check plan` emits per-member prompt files."""

    def test_plan_writes_one_file_per_member_under_threshold(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / "quality" / "requirements_manifest.json",
                   _req_manifest_with_tiers([1, 2, 1]))
            prompts, spec_gap = csc.plan_prompts(repo)
            self.assertEqual(spec_gap, Path())
            self.assertEqual(len(prompts), 3)  # one per Council member
            names = sorted(p.name for p in prompts)
            self.assertEqual(
                names,
                sorted([f"{m}.txt" for m in DEFAULT_COUNCIL_MEMBERS]),
            )
            # Each prompt contains the roster identifier and REQ content.
            for p in prompts:
                text = p.read_text(encoding="utf-8")
                self.assertIn("JSON array", text)
                self.assertIn("REQ-001", text)

    def test_plan_batches_when_over_threshold(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / "quality" / "requirements_manifest.json",
                   _req_manifest_with_tiers([1] * 20))
            prompts, _ = csc.plan_prompts(repo)
            # 20 REQs, 3 members, batch_size=5 → ceil(20/5)*3 = 12 files.
            self.assertEqual(len(prompts), 12)
            # File names include the batch suffix.
            for p in prompts:
                self.assertIn("-batch", p.name)

    def test_plan_spec_gap_writes_empty_reviews_file(self) -> None:
        """When there are no Tier 1/2 REQs, plan writes citation_semantic_check.json directly."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / "quality" / "requirements_manifest.json",
                   _req_manifest_with_tiers([3, 4, 5]))
            prompts, spec_gap = csc.plan_prompts(repo)
            self.assertEqual(prompts, [])
            self.assertTrue(spec_gap.is_file())
            data = json.loads(spec_gap.read_text(encoding="utf-8"))
            self.assertEqual(data["reviews"], [])

    def test_plan_cli_subcommand(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / "quality" / "requirements_manifest.json",
                   _req_manifest_with_tiers([1]))
            rc = csc.main(["plan", str(repo)])
            self.assertEqual(rc, 0)
            prompts_dir = repo / "quality" / csc.PROMPTS_SUBDIR
            self.assertTrue(prompts_dir.is_dir())
            self.assertEqual(
                sorted(p.name for p in prompts_dir.iterdir()),
                sorted([f"{m}.txt" for m in DEFAULT_COUNCIL_MEMBERS]),
            )

    def test_plan_cli_spec_gap_reports_skip(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / "quality" / "requirements_manifest.json",
                   _req_manifest_with_tiers([3]))
            # No --member flags; just the plan subcommand.
            rc = csc.main(["plan", str(repo)])
            self.assertEqual(rc, 0)
            self.assertTrue((repo / "quality" / "citation_semantic_check.json").is_file())

    def test_plan_prompts_clears_prior_batch_files_on_unbatched_rerun(self) -> None:
        """Phase 7 r7: a 20-REQ → 1-REQ rerun must leave only the three
        unbatched files, not the twelve batched files from the prior call."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            manifest_path = repo / "quality" / "requirements_manifest.json"

            # First call: 20 Tier 1 REQs → 4 batches × 3 members = 12 files.
            _write(manifest_path, _req_manifest_with_tiers([1] * 20))
            csc.plan_prompts(repo)
            prompts_dir = repo / "quality" / csc.PROMPTS_SUBDIR
            batched = sorted(p.name for p in prompts_dir.iterdir())
            self.assertEqual(len(batched), 12)
            self.assertTrue(all("-batch" in n for n in batched))

            # Second call: 1 Tier 1 REQ → 3 unbatched files.
            _write(manifest_path, _req_manifest_with_tiers([1]))
            csc.plan_prompts(repo)
            unbatched = sorted(p.name for p in prompts_dir.iterdir())
            self.assertEqual(
                unbatched,
                sorted([f"{m}.txt" for m in DEFAULT_COUNCIL_MEMBERS]),
            )
            # No stale -batchN.txt residue.
            self.assertFalse(any("-batch" in n for n in unbatched))

    def test_plan_prompts_clears_prompts_on_spec_gap_transition(self) -> None:
        """Phase 7 r7: when a repo transitions from Tier 1/2 content to Spec
        Gap, the Spec Gap branch must not leave stale prompt files behind."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            manifest_path = repo / "quality" / "requirements_manifest.json"

            # First call: 5 Tier 1/2 REQs → 3 unbatched files.
            _write(manifest_path, _req_manifest_with_tiers([1, 2, 1, 2, 1]))
            csc.plan_prompts(repo)
            prompts_dir = repo / "quality" / csc.PROMPTS_SUBDIR
            self.assertEqual(len(list(prompts_dir.iterdir())), 3)

            # Second call: 0 Tier 1/2 REQs → Spec Gap path. Prompts must be
            # cleared so the operator does not dispatch stale files.
            _write(manifest_path, _req_manifest_with_tiers([3, 4, 5]))
            csc.plan_prompts(repo)
            if prompts_dir.exists():
                self.assertEqual(list(prompts_dir.iterdir()), [])
            self.assertTrue(
                (repo / "quality" / "citation_semantic_check.json").is_file()
            )

    def test_plan_prompts_preserves_non_txt_operator_files(self) -> None:
        """Phase 7 r7: non-`.txt` files in the prompts dir (e.g. an operator
        note) must survive the clear-before-write."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            prompts_dir = repo / "quality" / csc.PROMPTS_SUBDIR
            prompts_dir.mkdir(parents=True)
            (prompts_dir / "notes.md").write_text("operator dispatch notes")

            _write(repo / "quality" / "requirements_manifest.json",
                   _req_manifest_with_tiers([1]))
            csc.plan_prompts(repo)

            self.assertTrue((prompts_dir / "notes.md").is_file())
            self.assertEqual(
                (prompts_dir / "notes.md").read_text(),
                "operator dispatch notes",
            )


if __name__ == "__main__":
    unittest.main()
