"""v1.6.1 [G] — gate verdict honesty.

Motivating run (2026-10-01, QPB 1.6.0 on collective/icalendar): 90 bugs,
each with a regression test, a fix and executed red and green logs. The
gate printed `RESULT: GATE FAILED — 7 substantive issue(s)` and the
verdict said the run "can't be trusted", because six requirement-
overreach FAILs and a missing post-gate AGENTS.md fell to the generic
fallback, which named only the first failing file.

These tests build the same shape in a temp dir ("every bug reproduced;
the gate fails only on requirement overreach + AGENTS.md") and pin:
the `── Bug evidence ──` block, the curated overreach / tier-mismatch
narration, dependent-bug listing, the fourth gate state (GATE PASSED
WITH DECISIONS NEEDED, exit 0), the generic fallback naming every file,
stale Council reviews (req_hash), `.rst` in reference_docs/cite/, and
the grouped reviewer WARNs.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_quality_gate_gates import (  # noqa: E402
    SCRIPT_PATH,
    V150_VIRTIO_EXCERPT,
    V150_VIRTIO_EXCERPT_TEXT,
    V150_VIRTIO_SHA,
    add_one_bug,
    minimal_zero_bug_tree,
    quality_gate,
    run_gate,
    write_tree,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

REVIEWERS = ("claude-opus-4.7", "gpt-5.5", "claude-sonnet-4.6")


def _wrap(records, key="records"):
    return json.dumps({
        "schema_version": "1.4.6",
        "generated_at": "2026-04-19T14:30:22Z",
        key: records,
    })


def _req_record(rid):
    return {
        "id": rid,
        "title": f"Title {rid}",
        "description": f"Description {rid}",
        "tier": 2,
        "functional_section": "Device initialization",
        "citation": {
            "document": "formal_docs/virtio-excerpt.txt",
            "document_sha256": V150_VIRTIO_SHA,
            "section": "2.4",
            "citation_excerpt": V150_VIRTIO_EXCERPT,
        },
    }


def build_reproduced_tree(bug_reqs, overreach_reqs, *, agents_md=False):
    """Every bug has a regression patch, a fix patch, a writeup, and RED
    and GREEN logs; every REQ has a valid tier-2 citation and three
    Council reviews; the REQs in ``overreach_reqs`` get 2/3 `overreaches`.
    AGENTS.md is absent by default (the icalendar shape)."""
    version = "1.4.4"
    tree = minimal_zero_bug_tree(version)
    if not agents_md:
        del tree["AGENTS.md"]
    bug_ids = sorted(bug_reqs)
    for bid in bug_ids:
        add_one_bug(tree, version, bid)
    tree["quality/BUGS.md"] = "# Bugs\n\n" + "".join(
        f"### {b}: Example\n\nDescription.\n\n" for b in bug_ids
    )
    tdd = json.loads(tree["quality/results/tdd-results.json"])
    template = tdd["bugs"][0]
    tdd["bugs"] = [
        dict(template, id=b, requirement=bug_reqs[b],
             writeup_path=f"quality/writeups/{b}.md")
        for b in bug_ids
    ]
    tdd["summary"].update(total=len(bug_ids), verified=len(bug_ids))
    tree["quality/results/tdd-results.json"] = json.dumps(tdd)
    tree["formal_docs/virtio-excerpt.txt"] = V150_VIRTIO_EXCERPT_TEXT
    tree["quality/formal_docs_manifest.json"] = _wrap([{
        "source_path": "formal_docs/virtio-excerpt.txt",
        "document_sha256": V150_VIRTIO_SHA,
        "tier": 2,
    }])
    req_ids = sorted(set(bug_reqs.values()) | set(overreach_reqs))
    recs = [_req_record(r) for r in req_ids]
    tree["quality/requirements_manifest.json"] = _wrap(recs)
    tree["quality/bugs_manifest.json"] = _wrap([{
        "id": b, "title": "t", "severity": "LOW",
        "divergence_description": "d", "documented_intent": "i",
        "code_behavior": "c", "disposition": "code-fix",
        "disposition_rationale": "r", "req_id": bug_reqs[b],
        "proposed_fix": "f", "fix_type": "code",
    } for b in bug_ids])
    reviews = []
    for rec in recs:
        rid = rec["id"]
        for idx, member in enumerate(REVIEWERS):
            verdict = (
                "overreaches" if rid in overreach_reqs and idx < 2
                else "supports"
            )
            reviews.append({
                "req_id": rid, "reviewer": member, "verdict": verdict,
                "notes": f"{member} on {rid}",
                "req_hash": quality_gate.req_review_hash(rec),
            })
    tree["quality/citation_semantic_check.json"] = _wrap(reviews, "reviews")
    tree["quality/INDEX.md"] = "# Run Index\n\n```json\n" + json.dumps({
        "run_timestamp_start": "2026-04-19T14:30:22Z",
        "run_timestamp_end": "2026-04-19T14:45:22Z",
        "duration_seconds": 900, "qpb_version": "1.4.6",
        "target_repo_path": ".", "target_repo_git_sha": "abc123",
        "target_role_breakdown": None, "phases_executed": [],
        "summary": {"requirements": {}, "bugs": {}, "gate_verdict": "pass"},
        "artifacts": [],
    }) + "\n```\n"
    return tree


def _sentinel(stdout):
    lines = [ln for ln in stdout.splitlines() if ln.startswith("::QPB:: ")]
    return json.loads(lines[-1][len("::QPB:: "):])


class _GateFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "proj"
        self.repo.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def gate(self, tree):
        write_tree(self.repo, tree)
        return run_gate(self.repo)


class ReproducedButOverreachTests(_GateFixture):
    """Every bug reproduced; FAILs only on overreach (one REQ with
    dependent bugs, one without) + missing AGENTS.md."""

    def setUp(self):
        super().setUp()
        tree = build_reproduced_tree(
            {"BUG-001": "REQ-001", "BUG-002": "REQ-002",
             "BUG-003": "REQ-002"},
            ["REQ-002", "REQ-003"],
        )
        self.out, self.code = self.gate(tree)

    def test_bug_evidence_block_says_reproduced_n_of_n(self):
        self.assertIn(
            "[FAIL] GATE FAILED\n── Bug evidence ──\n"
            "Reproduced: 3 of 3 bugs. Each has a regression test that "
            "fails on the current code and passes with its fix (red and "
            "green logs checked: 6 of 6).\n",
            self.out,
        )
        self.assertIn(
            "It does not show the expected behaviour is right or that the "
            "bug is unreported upstream", self.out,
        )
        self.assertIn(
            "The gate result below is about other checks; none of them is "
            "about these logs.", self.out,
        )

    def test_dependent_bugs_listed_by_id(self):
        self.assertIn(
            "2 bugs rest on a requirement the reviewers questioned (still "
            "reproduced; read the requirement note before relying on the "
            "expected behaviour): BUG-002, BUG-003 (REQ-002)", self.out,
        )
        self.assertIn(
            "record_id=REQ-002: semantic check majority overreaches", self.out,
        )
        self.assertIn(
            "confirmed bug(s) resting on REQ-002: BUG-002, BUG-003", self.out,
        )

    def test_dependent_overreach_keeps_gate_failed(self):
        self.assertEqual(self.code, 1)
        self.assertIn(
            "Total: 2 FAIL (1 substantive, 0 record-keeping, "
            "1 operator-decision), ", self.out,
        )
        self.assertIn(
            "RESULT: GATE FAILED — 1 substantive issue(s) must be fixed",
            self.out,
        )

    def test_overreach_gets_curated_message_and_lines(self):
        self.assertIn("• [requirement_overreach] (2 FAILs)", self.out)
        self.assertIn(
            "2 requirement(s) say more than the passage they quote; at "
            "least two of three reviewers agreed. This is about how the "
            "requirement is written, not about the code.", self.out,
        )
        self.assertIn(
            "Bugs that rest on these requirements: BUG-002, BUG-003 "
            "(REQ-002).", self.out,
        )
        self.assertNotIn("[generic]", self.out)
        # The failing lines are listed under the category, without a
        # "FAIL:" prefix (fail() lines stay grep-parseable).
        self.assertRegex(
            self.out,
            r"\n      - citation_semantic_check\.json: record_id=REQ-003: "
            r"semantic check majority overreaches",
        )
        self.assertNotIn("FAIL: citation_semantic_check.json", self.out)

    def test_reason_does_not_say_untrustworthy(self):
        self.assertNotIn("can be trusted", self.out)
        self.assertNotIn("decides whether this run's results", self.out)
        self.assertIn(
            "Result: it did not pass the checkpoint — the bugs are "
            "reproduced; what failed is the paperwork behind 2 "
            "requirements.", self.out,
        )

    def test_agents_md_is_warn_not_fail(self):
        self.assertIn(
            "WARN: AGENTS.md not written yet — the orchestrator writes it "
            "after the gate passes; it does not affect the findings.",
            self.out,
        )
        self.assertNotIn("AGENTS.md missing (required at project root)",
                         self.out)

    def test_operator_decisions_file_missing_warns(self):
        self.assertIn(
            "WARN: OPERATOR_DECISIONS.md missing — 2 requirement(s) were "
            "questioned (REQ-002, REQ-003)", self.out,
        )

    def test_sentinel_machine_fields(self):
        payload = _sentinel(self.out)
        self.assertEqual(payload["gate_result"], "FAIL")
        self.assertEqual(payload["bug_evidence"], "reproduced")
        self.assertEqual(payload["bugs"], 3)
        self.assertEqual(payload["bugs_reproduced"], 3)
        self.assertEqual(payload["bugs_on_flagged_reqs"], 2)
        # Existing keys are untouched.
        for key in ("v", "kind", "verdict_state", "ts"):
            self.assertIn(key, payload)


class DecisionsNeededTests(_GateFixture):
    """Overreach only on a REQ no confirmed bug rests on -> exit 0."""

    def test_decisions_needed_passes_with_exit_zero(self):
        tree = build_reproduced_tree(
            {"BUG-001": "REQ-001", "BUG-002": "REQ-002"}, ["REQ-003"],
        )
        out, code = self.gate(tree)
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"\nTotal: 1 DECISION, \d+ WARN\n")
        self.assertIn(
            "RESULT: GATE PASSED WITH DECISIONS NEEDED — 1 requirement "
            "decision(s)\n", out,
        )
        self.assertIn(
            "[WARN] GATE PASSED -- 1 requirement decision(s) need you", out,
        )
        self.assertIn("Bugs that rest on these requirements: none.", out)
        self.assertIn("no confirmed bug rests on REQ-003", out)
        self.assertEqual(_sentinel(out)["gate_result"], "DECISIONS")
        self.assertEqual(_sentinel(out)["bugs_on_flagged_reqs"], 0)

    def test_unlinked_bug_keeps_overreach_substantive(self):
        """A confirmed bug with no req_id in bugs_manifest.json means the
        gate cannot prove no bug rests on the REQ -> stays GATE FAILED."""
        tree = build_reproduced_tree({"BUG-001": "REQ-001"}, ["REQ-003"])
        manifest = json.loads(tree["quality/bugs_manifest.json"])
        del manifest["records"][0]["req_id"]
        tree["quality/bugs_manifest.json"] = json.dumps(manifest)
        out, code = self.gate(tree)
        self.assertEqual(code, 1, out)
        self.assertIn("cannot rule out a bug resting on REQ-003", out)

    def test_operator_decisions_file_present_passes(self):
        tree = build_reproduced_tree({"BUG-001": "REQ-001"}, ["REQ-003"])
        tree["quality/OPERATOR_DECISIONS.md"] = "# Decisions\n"
        out, code = self.gate(tree)
        self.assertEqual(code, 0, out)
        self.assertIn("PASS: OPERATOR_DECISIONS.md present", out)
        self.assertNotIn("OPERATOR_DECISIONS.md missing", out)


class Council1GateTests(_GateFixture):
    """v1.6.1 [council-1]: Council round-1 findings A2, A3, A5, A6, A7
    and B gaps 3-4, end to end through the real gate."""

    def _stale_manifest_zero_bug_tree(self):
        """BUGS.md has zero bugs; bugs_manifest.json still carries a
        BUG-001 -> REQ-001 record; REQ-001 overreaches (2/3)."""
        tree = minimal_zero_bug_tree("1.4.4")
        tree["formal_docs/virtio-excerpt.txt"] = V150_VIRTIO_EXCERPT_TEXT
        tree["quality/formal_docs_manifest.json"] = _wrap([{
            "source_path": "formal_docs/virtio-excerpt.txt",
            "document_sha256": V150_VIRTIO_SHA, "tier": 2,
        }])
        rec = _req_record("REQ-001")
        tree["quality/requirements_manifest.json"] = _wrap([rec])
        tree["quality/citation_semantic_check.json"] = _wrap([{
            "req_id": "REQ-001", "reviewer": m,
            "verdict": "overreaches" if i < 2 else "supports",
            "notes": "n", "req_hash": quality_gate.req_review_hash(rec),
        } for i, m in enumerate(REVIEWERS)], "reviews")
        tree["quality/INDEX.md"] = build_reproduced_tree(
            {"BUG-001": "REQ-001"}, [])["quality/INDEX.md"]
        tree["quality/bugs_manifest.json"] = _wrap([{
            "id": "BUG-001", "title": "t", "severity": "LOW",
            "divergence_description": "d", "documented_intent": "i",
            "code_behavior": "c", "disposition": "code-fix",
            "disposition_rationale": "r", "req_id": "REQ-001",
            "proposed_fix": "f", "fix_type": "code",
        }])
        return tree

    def test_zero_bugs_stale_manifest_is_operator_decision(self):
        """Council A3: with zero confirmed bugs, a stale bugs_manifest
        record is not a confirmed bug resting on the REQ."""
        out, code = self.gate(self._stale_manifest_zero_bug_tree())
        self.assertEqual(code, 0, out)
        self.assertIn("No confirmed bugs in this run.", out)
        self.assertIn("no confirmed bug rests on REQ-001 — operator "
                      "decision", out)
        self.assertNotIn("confirmed bug(s) resting on", out)
        self.assertIn("RESULT: GATE PASSED WITH DECISIONS NEEDED", out)

    def test_decisions_pass_heading_and_verdict_state(self):
        """Council A5 + A6 / C2: a decisions pass is headed 'What needs
        your decision:' (never 'Why it failed') and its sentinel says
        verdict_state "decisions", matching the lead line."""
        tree = build_reproduced_tree({"BUG-001": "REQ-001"}, ["REQ-003"])
        out, code = self.gate(tree)
        self.assertEqual(code, 0, out)
        self.assertIn("[WARN] GATE PASSED -- 1 requirement decision(s) "
                      "need you", out)
        self.assertIn("\nWhat needs your decision:\n", out)
        self.assertNotIn("Why it failed", out)
        self.assertIn("(see 'What needs your decision' above)", out)
        payload = _sentinel(out)
        self.assertEqual(payload["gate_result"], "DECISIONS")
        self.assertEqual(payload["verdict_state"], "decisions")

    def test_bug_to_req_linkage_filters(self):
        """Council B gap 3 (+ A2): a known-issue record pointing at a
        flagged REQ is not listed; a manifest record for a bug BUGS.md
        does not confirm is not listed; a tier-3 REQ carrying a citation
        counts as questioned in the Bug evidence block. The known-issue
        bug has no usable req_id, so the overreach narration says the
        gate cannot rule it out instead of "none"."""
        tree = build_reproduced_tree(
            {"BUG-001": "REQ-001", "BUG-002": "REQ-004",
             "BUG-003": "REQ-002"},
            ["REQ-002"],
        )
        manifest = json.loads(tree["quality/bugs_manifest.json"])
        for rec in manifest["records"]:
            if rec["id"] == "BUG-003":
                rec["classification"] = "known-issue"
        manifest["records"].append(
            dict(manifest["records"][0], id="BUG-009", req_id="REQ-002"))
        tree["quality/bugs_manifest.json"] = json.dumps(manifest)
        reqs = json.loads(tree["quality/requirements_manifest.json"])
        for rec in reqs["records"]:
            if rec["id"] == "REQ-004":
                rec["tier"] = 3
        tree["quality/requirements_manifest.json"] = json.dumps(reqs)
        reviews = json.loads(tree["quality/citation_semantic_check.json"])
        reviews["reviews"] = [r for r in reviews["reviews"]
                              if r["req_id"] != "REQ-004"]
        tree["quality/citation_semantic_check.json"] = json.dumps(reviews)
        out, code = self.gate(tree)
        self.assertEqual(code, 1, out)
        block = out[out.index("── Bug evidence ──"):out.index("\n\n",
                    out.index("── Bug evidence ──"))]
        self.assertIn(
            "1 bug rest on a requirement the reviewers questioned (still "
            "reproduced; read the requirement note before relying on the "
            "expected behaviour): BUG-002 (REQ-004)", block)
        self.assertNotIn("BUG-003", block)
        self.assertNotIn("BUG-009", block)
        self.assertNotIn("confirmed bug(s) resting on REQ-002", out)
        # Council A2: narration does not claim "none".
        self.assertNotIn("Bugs that rest on these requirements: none.", out)
        self.assertIn(
            "Bugs that rest on these requirements: unknown — 1 confirmed "
            "bug has no usable req_id in bugs_manifest.json (missing, or "
            "the record is marked known-issue), so the gate cannot rule it "
            "out.", out)
        # v1.6.1 [council-2] (A-r2 N2): BUG-003 has a req_id; the FAIL
        # line names the known-issue cause too.
        self.assertIn(
            "; 1 confirmed bug(s) have no usable req_id in "
            "bugs_manifest.json (missing, or the record is marked "
            "known-issue), so the gate cannot rule out a bug resting on "
            "REQ-002", out)
        self.assertNotIn("have no req_id", out)

    def test_multi_repo_lines_name_their_repo(self):
        """Council A7 / B gap 4: with two repos, each listed FAIL line
        is prefixed with its repo."""
        with tempfile.TemporaryDirectory() as td:
            dirs = []
            for name in ("alpha", "beta"):
                d = Path(td) / name
                d.mkdir()
                write_tree(d, build_reproduced_tree(
                    {"BUG-001": "REQ-001"}, ["REQ-003"]))
                dirs.append(d)
            out, code = run_gate(dirs[1], args=(str(dirs[0]),))
        self.assertEqual(code, 0, out)
        for name in ("alpha", "beta"):
            self.assertIn(
                f"      - [{name}] citation_semantic_check.json: "
                f"record_id=REQ-003: semantic check majority overreaches",
                out)


class Council2GateTests(_GateFixture):
    """v1.6.1 [council-2]: Council round-2 findings A-r2 N3 and C-r2
    nit 2, end to end through the real gate."""

    def test_multi_repo_overreach_narration_per_repo(self):
        """A-r2 N3 probe: alpha has a bug with no req_id and a flagged
        REQ-003; beta has a flagged REQ-003 and no such bug. The
        narration counts 2 repo:REQ pairs and gives each repo its own
        bugs text."""
        with tempfile.TemporaryDirectory() as td:
            dirs = []
            for name in ("alpha", "beta"):
                d = Path(td) / name
                d.mkdir()
                tree = build_reproduced_tree(
                    {"BUG-001": "REQ-001"}, ["REQ-003"])
                if name == "alpha":
                    manifest = json.loads(tree["quality/bugs_manifest.json"])
                    del manifest["records"][0]["req_id"]
                    tree["quality/bugs_manifest.json"] = json.dumps(manifest)
                write_tree(d, tree)
                dirs.append(d)
            out, code = run_gate(dirs[1], args=(str(dirs[0]),))
        self.assertEqual(code, 1, out)
        self.assertIn(
            "    2 requirement(s) say more than the passage they quote", out)
        self.assertIn(
            "Bugs that rest on these requirements: [alpha] unknown — 1 "
            "confirmed bug has no usable req_id in bugs_manifest.json "
            "(missing, or the record is marked known-issue), so the gate "
            "cannot rule it out; [beta] none.", out)

    def test_mixed_decisions_and_cleanup_pass_separates_record_keeping(self):
        """C-r2 nit 2: on a decisions pass with a record-keeping FAIL,
        the record-keeping FAIL is under its own heading (not under
        'What needs your decision:'), and 'What to do next' names it."""
        tree = build_reproduced_tree({"BUG-001": "REQ-001"}, ["REQ-003"])
        del tree["quality/results/run-2026-01-01T00-00-00.json"]
        out, code = self.gate(tree)
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"\nTotal: 1 DECISION, 1 CLEANUP, \d+ WARN\n")
        decision = _slice_between(out, "\nWhat needs your decision:\n",
                                  "\nAudit record-keeping gaps:\n")
        self.assertIn("record_id=REQ-003", decision)
        self.assertNotIn("run-metadata", decision)
        gaps = _slice_between(out, "\nAudit record-keeping gaps:\n",
                              "── What happened ──")
        self.assertIn("run-metadata JSON missing", gaps)
        self.assertNotIn("record_id=REQ-003", gaps)
        self.assertNotIn("Why it failed", out)
        nxt = out[out.index("── What to do next ──"):]
        self.assertIn(
            "Then tidy the 1 audit record-keeping gap(s) listed in 'Audit "
            "record-keeping gaps' above.", nxt)

    def test_decisions_only_pass_has_no_record_keeping_heading(self):
        tree = build_reproduced_tree({"BUG-001": "REQ-001"}, ["REQ-003"])
        out, code = self.gate(tree)
        self.assertEqual(code, 0, out)
        self.assertNotIn("Audit record-keeping gaps", out)
        self.assertNotIn("Then tidy the", out)


def _slice_between(text, start, stop):
    i = text.index(start)
    return text[i:text.index(stop, i + len(start))]


class FinalVerdictUnitTests(unittest.TestCase):
    def test_decisions_only(self):
        total, result, code = quality_gate._compute_final_verdict(
            [(quality_gate.VERDICT_OPERATOR_DECISION, "x")] * 2, 3,
        )
        self.assertEqual(total, "Total: 2 DECISION, 3 WARN")
        self.assertEqual(
            result,
            "RESULT: GATE PASSED WITH DECISIONS NEEDED — 2 requirement "
            "decision(s)",
        )
        self.assertEqual(code, 0)

    def test_decisions_plus_cleanup(self):
        total, result, code = quality_gate._compute_final_verdict(
            [(quality_gate.VERDICT_OPERATOR_DECISION, "x"),
             (quality_gate.VERDICT_RECORD_KEEPING, "y")], 0,
        )
        self.assertEqual(total, "Total: 1 DECISION, 1 CLEANUP, 0 WARN")
        self.assertTrue(result.endswith(
            "1 requirement decision(s), 1 audit record-keeping gap(s)"))
        self.assertEqual(code, 0)

    def test_pre_161_lines_unchanged_without_decisions(self):
        self.assertEqual(
            quality_gate._compute_final_verdict(
                [(quality_gate.VERDICT_SUBSTANTIVE, "a"),
                 (quality_gate.VERDICT_RECORD_KEEPING, "b")], 1)[0],
            "Total: 2 FAIL (1 substantive, 1 record-keeping), 1 WARN",
        )
        self.assertEqual(
            quality_gate._compute_final_verdict(
                [(quality_gate.VERDICT_RECORD_KEEPING, "b")], 0)[1],
            "RESULT: GATE PASSED WITH CLEANUP NEEDED — 1 audit "
            "record-keeping gap(s)",
        )


def _capture(func, *args, **kwargs):
    buf = io.StringIO()
    with redirect_stdout(buf):
        func(*args, **kwargs)
    return buf.getvalue()


class VerdictPresentationUnitTests(unittest.TestCase):
    def setUp(self):
        quality_gate._reset_counters()

    def tearDown(self):
        quality_gate._reset_counters()

    def test_generic_fallback_lists_every_file(self):
        msgs = [
            "requirements_manifest.json: record_id=REQ-016: weird thing",
            "requirements_manifest.json: record_id=REQ-017: weird thing",
            "use_cases_manifest.json: record_id=UC-01: odd",
        ]
        text = quality_gate._narrate_fail_category(
            quality_gate._FAIL_GENERIC, msgs,
            quality_gate._summarize_bug_evidence([], ledger=[]),
        )
        self.assertIn(
            "These checks failed: requirements_manifest.json, "
            "use_cases_manifest.json.", text,
        )

    def test_failing_lines_capped_with_more(self):
        records = [
            (quality_gate.VERDICT_SUBSTANTIVE, f"file{i}.json: broke {i}")
            for i in range(12)
        ]
        out = _capture(quality_gate._emit_operator_verdict,
                       records, [], [], 1, run_provenance=[])
        self.assertIn("      - file9.json: broke 9\n", out)
        self.assertNotIn("      - file10.json", out)
        self.assertIn("      +2 more\n", out)

    def test_tier_mismatch_narration(self):
        msgs = [
            "requirements_manifest.json: record_id=REQ-016: is tier 3 but "
            "carries a citation block (citations are for Tier 1/2 only per "
            "schemas.md §10 invariant #1)",
        ]
        self.assertEqual(
            quality_gate._classify_fail(msgs[0]),
            quality_gate._FAIL_REQ_TIER_MISMATCH,
        )
        text = quality_gate._narrate_fail_category(
            quality_gate._FAIL_REQ_TIER_MISMATCH, msgs,
            quality_gate._summarize_bug_evidence([], ledger=[]),
        )
        self.assertTrue(text.startswith(
            "1 requirement(s) quote a document but are still marked as "
            "code-derived (tier 3). This usually comes from the "
            "expert-review (Feature H) step."), text)
        self.assertIn("Fix: set the tier to the cited document's tier, or "
                      "remove the citation.", text)

    def _ledger(self, **kw):
        entry = {
            "repo": "r", "q": None, "bug_ids": ["BUG-001", "BUG-002"],
            "bug_count": 2, "tdd_ok": {"BUG-001": True, "BUG-002": True},
            "logs_ok": 4, "no_regression_patch": set(), "bug_req": {},
            "questioned_reqs": {}, "noted_reqs": set(),
        }
        entry.update(kw)
        return [entry]

    def test_states(self):
        s = quality_gate._summarize_bug_evidence
        self.assertEqual(s([], ledger=self._ledger())["state"], "reproduced")
        partial = s([], ledger=self._ledger(
            tdd_ok={"BUG-001": True, "BUG-002": False}, logs_ok=3))
        self.assertEqual(partial["state"], "partial")
        self.assertEqual(partial["unreproduced"], ["BUG-002"])
        lines = quality_gate._bug_evidence_lines(
            partial, other_checks_failed=True)
        self.assertIn("No red and green evidence the gate accepted: "
                      "BUG-002.", lines)
        unverified = [(quality_gate.VERDICT_SUBSTANTIVE,
                       "tdd-results.json missing (2 bugs require it)")]
        self.assertEqual(
            s(unverified, ledger=self._ledger())["state"], "not_reproduced")
        none = s([], ledger=self._ledger(bug_ids=[], bug_count=0))
        self.assertEqual(none["state"], "none")
        self.assertEqual(
            quality_gate._bug_evidence_lines(none, other_checks_failed=True),
            ["No confirmed bugs in this run."],
        )

    def test_overclaim_blocks_reproduced_and_other_checks_line(self):
        overclaim = [(quality_gate.VERDICT_SUBSTANTIVE,
                      "1 TDD receipt(s) overclaim: tagged RED/GREEN")]
        summary = quality_gate._summarize_bug_evidence(
            overclaim, ledger=self._ledger())
        self.assertEqual(summary["state"], "partial")
        lines = quality_gate._bug_evidence_lines(
            summary, other_checks_failed=True)
        self.assertNotIn(
            "The gate result below is about other checks; none of them is "
            "about these logs.", lines)

    def test_patch_missing_named_not_logs(self):
        """Council A4: red and green logs accepted, no regression-test
        patch -> the line names the missing patch; singular agreement."""
        summary = quality_gate._summarize_bug_evidence([], ledger=self._ledger(
            no_regression_patch={"BUG-002"}))
        self.assertEqual(summary["state"], "partial")
        lines = quality_gate._bug_evidence_lines(
            summary, other_checks_failed=True)
        self.assertIn(
            "Red and green logs accepted, but no regression-test patch in "
            "quality/patches/: BUG-002.", lines)
        self.assertFalse(
            any(ln.startswith("No red and green evidence") for ln in lines),
            lines)
        self.assertTrue(any(ln.startswith(
            "For the 1 reproduced bug, this shows") for ln in lines), lines)

    def test_two_repo_ledger_prefixes_ids(self):
        """Council B gap 4: two repos' BUG-001 stay apart."""
        a = self._ledger(repo="alpha", bug_req={"BUG-001": "REQ-002"},
                         questioned_reqs={"REQ-002": "overreach"},
                         tdd_ok={"BUG-001": True, "BUG-002": False})
        b = self._ledger(repo="beta", bug_req={"BUG-001": "REQ-002"},
                         questioned_reqs={"REQ-002": "overreach"})
        summary = quality_gate._summarize_bug_evidence([], ledger=a + b)
        self.assertEqual(summary["unreproduced"], ["alpha:BUG-002"])
        self.assertEqual(summary["on_flagged"], [
            ("alpha:REQ-002", ["alpha:BUG-001"]),
            ("beta:REQ-002", ["beta:BUG-001"]),
        ])

    def test_failing_lines_repo_prefix_only_when_multi_repo(self):
        """Council A7: [repo] prefix only when more than one repo ran."""
        records = [(quality_gate.VERDICT_SUBSTANTIVE, "x.json: broke")] * 2
        quality_gate._new_bug_evidence("alpha")
        quality_gate._new_bug_evidence("beta")
        out = _capture(quality_gate._emit_operator_verdict, records, [], [],
                       1, run_provenance=[], fail_repos=["alpha", "beta"])
        self.assertIn("      - [alpha] x.json: broke\n", out)
        self.assertIn("      - [beta] x.json: broke\n", out)
        quality_gate._reset_counters()
        quality_gate._new_bug_evidence("alpha")
        out = _capture(quality_gate._emit_operator_verdict, records[:1], [],
                       [], 1, run_provenance=[], fail_repos=["alpha"])
        self.assertIn("      - x.json: broke\n", out)
        self.assertNotIn("[alpha]", out)

    def test_cleanup_heading_unchanged(self):
        """Council A5: only the decisions pass changes heading; CLEANUP
        keeps 'Why it failed:'."""
        records = [(quality_gate.VERDICT_RECORD_KEEPING, "x.json: gap")]
        out = _capture(quality_gate._emit_operator_verdict, records, [], [],
                       0, run_provenance=[])
        self.assertIn("\nWhy it failed:\n", out)
        self.assertNotIn("What needs your decision", out)
        self.assertIn("(see 'Why it failed' above — these are audit "
                      "record-keeping issues", out)

    def test_verdict_state_decisions(self):
        """Council A6 / C2: verdict_state has a "decisions" value, also
        when a shallow tell is present (the lead line is the decisions
        marker either way)."""
        dec = [(quality_gate.VERDICT_OPERATOR_DECISION, "x")]
        cvs = quality_gate._compute_verdict_state
        self.assertEqual(cvs(0, dec, [], []), "decisions")
        self.assertEqual(cvs(0, dec, [], ["proj"]), "decisions")
        self.assertEqual(cvs(1, dec, [], []), "failed")
        self.assertEqual(cvs(0, [], [], ["proj"]), "shallow")
        self.assertEqual(cvs(0, [], [], []), "solid")

    def test_generic_fallback_names_checks_without_colon(self):
        """Council C5: messages with no ':' are named by their leading
        words, deduped, never repeated whole."""
        msgs = [
            "BUGS.md missing",
            "functional test file missing (test_functional.*, "
            "functional_test.*, FunctionalSpec.*)",
            "BUGS.md missing",
            "spec_audits/ directory missing",
        ]
        text = quality_gate._narrate_fail_category(
            quality_gate._FAIL_GENERIC, msgs,
            quality_gate._summarize_bug_evidence([], ledger=[]),
        )
        self.assertIn(
            "These checks failed: BUGS.md, functional test file, "
            "spec_audits/ directory.", text)
        self.assertNotIn("test_functional.*", text)

    def test_check_name_real_messages(self):
        """C-r2 nit 1: the real colon-less FAIL messages Reviewer C
        quoted from the archived 1.5.8 runs. A stop token ends the name
        (no word cap then); the word cap applies only without one."""
        cn = quality_gate._check_name
        self.assertEqual(cn(
            "No writeups have inline fix diffs (section 6 'The fix' must "
            "include a ```diff block)"), "No writeups have inline fix diffs")
        self.assertEqual(cn("PROGRESS.md version 'v1.5.8' != '1.6.0'"),
                         "PROGRESS.md version")
        self.assertEqual(cn(
            "Directory version '1.5.8' != skill version '1.6.0' — possible "
            "cross-run contamination"), "Directory version")
        self.assertEqual(cn("No writeups for 3 confirmed bug(s)"),
                         "No writeups for 3 confirmed bug(s)")
        self.assertEqual(cn("summary missing 'total' count"), "summary")
        self.assertEqual(cn("version 1.5 != 1.6"), "version 1.5")
        self.assertEqual(
            cn("one two three four five six seven eight nine ten eleven"),
            "one two three four five six seven eight nine ten")
        self.assertEqual(cn("x.json: broke"), "x.json")

    def test_failure_reason_names_colon_less_check(self):
        """B-r2 nit 2: the second _check_name call site
        (_failure_reason's "N other check(s) (...)")."""
        records = [(quality_gate.VERDICT_SUBSTANTIVE,
                    "PROGRESS.md version 'v1.5.8' != '1.6.0'")]
        reason = quality_gate._failure_reason(
            records, quality_gate._summarize_bug_evidence([], ledger=[]))
        self.assertIn("1 other check (PROGRESS.md version)", reason)

    def test_reproduced_bugs_plural(self):
        """B-r2 nit 3: 'For the 2 reproduced bugs' (plural)."""
        summary = quality_gate._summarize_bug_evidence([], ledger=self._ledger(
            bug_ids=["BUG-001", "BUG-002", "BUG-003"], bug_count=3,
            tdd_ok={"BUG-001": True, "BUG-002": True, "BUG-003": True},
            no_regression_patch={"BUG-003"}))
        lines = quality_gate._bug_evidence_lines(
            summary, other_checks_failed=True)
        self.assertTrue(any(ln.startswith(
            "For the 2 reproduced bugs, this shows") for ln in lines), lines)

    def test_reset_counters_clears_fail_repos(self):
        """B-r2 nit 4: a second in-process run must not inherit the
        first run's per-FAIL repo labels."""
        quality_gate._new_bug_evidence("alpha")
        with redirect_stdout(io.StringIO()):
            quality_gate.fail("x.json: broke")
        self.assertEqual(quality_gate._FAIL_REPOS, ["alpha"])
        quality_gate._reset_counters()
        self.assertEqual(quality_gate._FAIL_REPOS, [])

    def test_noted_reqs_listed_separately(self):
        summary = quality_gate._summarize_bug_evidence([], ledger=self._ledger(
            bug_req={"BUG-002": "REQ-009"}, noted_reqs={"REQ-009"}))
        lines = quality_gate._bug_evidence_lines(
            summary, other_checks_failed=False)
        self.assertIn(
            "1 bug rest on a requirement noted by one reviewer: "
            "BUG-002 (REQ-009)", lines)

    def test_reviewer_warns_grouped(self):
        warns = [
            "citation_semantic_check.json: record_id=REQ-001: 1/3 reviewer "
            "(a) flagged as `overreaches` — surfaced for human review; not a "
            "gate failure unless ≥2 agree",
            "citation_semantic_check.json: record_id=REQ-004: 1/3 reviewer "
            "(b) flagged as `overreaches` — surfaced for human review; not a "
            "gate failure unless ≥2 agree",
            "citation_semantic_check.json: record_id=REQ-002: 1/3 "
            "reviewer(s) flagged as `unclear` (c) — surfaced for human review",
            "integration-results.json not present",
        ]
        lines = quality_gate._group_reviewer_warns(warns)
        self.assertEqual(lines, [
            "integration-results.json not present",
            "2 requirement(s) flagged as `overreaches` by one reviewer (not "
            "a gate failure): REQ-001, REQ-004",
            "1 requirement(s) flagged as `unclear` by a reviewer (not a gate "
            "failure): REQ-002",
        ])


class StaleReviewTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.q = Path(self._tmp.name) / "quality"
        self.q.mkdir()
        quality_gate._reset_counters()
        self.rec = _req_record("REQ-001")
        (self.q / "requirements_manifest.json").write_text(_wrap([self.rec]))

    def tearDown(self):
        self._tmp.cleanup()
        quality_gate._reset_counters()

    def _reviews(self, req_hash):
        rows = []
        for m in REVIEWERS:
            row = {"req_id": "REQ-001", "reviewer": m, "verdict": "supports",
                   "notes": ""}
            if req_hash is not None:
                row["req_hash"] = req_hash
            rows.append(row)
        (self.q / "citation_semantic_check.json").write_text(
            _wrap(rows, "reviews"))

    def _run(self):
        quality_gate.FAIL = quality_gate.WARN = 0
        out = _capture(quality_gate.check_v1_5_0_semantic_check, self.q)
        return quality_gate.FAIL, quality_gate.WARN, out

    def test_current_hash_counts(self):
        self._reviews(quality_gate.req_review_hash(self.rec))
        fails, warns, out = self._run()
        self.assertEqual((fails, warns), (0, 0), out)

    def test_rewritten_req_makes_reviews_stale(self):
        old = dict(self.rec, title="An earlier wording")
        self._reviews(quality_gate.req_review_hash(old))
        fails, _warns, out = self._run()
        self.assertEqual(fails, 1, out)
        self.assertIn("record_id=REQ-001: fewer than 3 reviews (0 present)",
                      out)
        self.assertIn("review predates a rewrite of REQ-001", out)

    def test_missing_hash_warns_once_not_fail(self):
        self._reviews(None)
        fails, warns, out = self._run()
        self.assertEqual((fails, warns), (0, 1), out)
        self.assertIn("3 review entries carry no req_hash", out)

    def test_hash_covers_title_conditions_and_excerpt(self):
        base = quality_gate.req_review_hash(self.rec)
        self.assertRegex(base, r"^[0-9a-f]{64}$")
        for change in (
            {"title": "x"},
            {"conditions_of_satisfaction": "y"},
            {"citation": dict(self.rec["citation"], citation_excerpt="z")},
        ):
            self.assertNotEqual(
                base, quality_gate.req_review_hash(dict(self.rec, **change)),
                change,
            )
        # Fields outside the canonical set do not change the hash.
        self.assertEqual(
            base, quality_gate.req_review_hash(dict(self.rec, tier=1)))

    def test_writer_stamps_matching_hash(self):
        from bin import council_semantic_check as csc
        entries = [csc.ReviewEntry(req_id="REQ-001", reviewer=m,
                                   verdict="supports", notes="")
                   for m in REVIEWERS]
        path = csc.write_semantic_check(self.q.parent, entries,
                                        schema_version="1.6.1")
        data = json.loads(path.read_text())
        self.assertEqual(
            {r["req_hash"] for r in data["reviews"]},
            {quality_gate.req_review_hash(self.rec)},
        )
        fails, warns, out = self._run()
        self.assertEqual((fails, warns), (0, 0), out)


class RstCiteTests(unittest.TestCase):
    def test_rst_in_cite_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            cite = repo / "reference_docs" / "cite"
            cite.mkdir(parents=True)
            (cite / "virtio.rst").write_text("Title\n=====\n\nBody.\n")
            quality_gate.FAIL = 0
            out = _capture(quality_gate.check_v1_5_0_cite_extensions, repo)
            self.assertEqual(quality_gate.FAIL, 0, out)
            self.assertNotIn("unsupported extension", out)
            (cite / "spec.pdf").write_text("x")
            out = _capture(quality_gate.check_v1_5_0_cite_extensions, repo)
            self.assertIn("allows only .txt, .md, .rst", out)


class GateStateConsumerTests(unittest.TestCase):
    """The fourth RESULT line reaches every pattern-matching consumer."""

    _LINE = ("RESULT: GATE PASSED WITH DECISIONS NEEDED — 6 requirement "
             "decision(s)")

    def test_archive_lib_maps_to_pass_with_decisions(self):
        from bin import archive_lib as al
        m = al._GATE_RESULT_PATTERN.search("Total: 6 DECISION, 1 WARN\n"
                                           + self._LINE + "\n")
        self.assertEqual(m.group(1), "PASSED WITH DECISIONS NEEDED")
        self.assertEqual(al._GATE_RESULT_TO_VERDICT[m.group(1)],
                         "pass-with-decisions")

    def test_index_enum_accepts_pass_with_decisions(self):
        from bin import validate_phase_artifacts as vpa
        self.assertIn("pass-with-decisions", vpa._INDEX_VALID_VERDICTS)

    def test_run_playbook_reader_returns_decisions_line(self):
        from bin.run_playbook import _gate_pass, _read_gate_verdict_from_log
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "quality-gate.log"
            log.write_text("Total: 6 DECISION, 1 WARN\n" + self._LINE
                           + "\n\n--- Operator Verdict ---\n"
                           "::QPB:: {\"gate_result\":\"DECISIONS\"}\n")
            line = _read_gate_verdict_from_log(log)
            self.assertEqual(line, self._LINE)
            self.assertTrue(_gate_pass(line, Path(tmp)))


if __name__ == "__main__":
    unittest.main()
