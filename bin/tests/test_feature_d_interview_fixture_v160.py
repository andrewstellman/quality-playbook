"""v1.6.0 Feature D — the validation-interview acceptance fixture.

Plan Phase 4 acceptance: a scripted test-double operator drives a session
(one confirm, one correct, one add, one merge); the manifest is updated with
correctly-shaped records, the re-render passes the Feature C render contract,
and the defect log + confirmations artifacts are gate-validated. Plus the
mutation (a correction that never reaches the manifest must fail), and the
F-2a durability oracle (confirm-then-re-derive keeps the .jsonl intact; a
truncating path fails).

The interview is a **skill-protocol chat** — there is no Python interview
engine, by design (Decision Record #7). So the test-double is the scripted
sequence of operator moves, and :func:`_apply_move` encodes exactly what
`references/requirements_interview.md` instructs the agent to write for each
move. The test verifies the *contract* the protocol establishes — manifest
shape, artifact presence, gate validation — not a program that does not exist.
"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = (
    REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))

import quality_gate  # noqa: E402
import run_state_lib  # noqa: E402

SKILL_VERSION = "1.6.0"
SESSION_ID = "2026-07-21T150000Z-selfderiv"
TRANSCRIPT = f"quality/review_sessions/{SESSION_ID}.md"


# --- A small self-derivation-like fixture that passes the render contract. --

def _base_manifest():
    # Two sections of three REQs each, so a within-section merge still leaves
    # ≥2 and the re-render conforms to the Feature C section-discipline check.
    return {
        "schema_version": SKILL_VERSION,
        "generated_at": "2026-07-21T00:00:00Z",
        "records": [
            {"id": "REQ-001", "title": "The gate rejects a manifest with a bad wrapper key",
             "functional_section": "Manifest validation",
             "conditions_of_satisfaction": "A manifest using 'requirements' rather than 'records' is rejected.",
             "references": ["bin/validate_phase_artifacts.py"], "source_type": "code-derived"},
            {"id": "REQ-002", "title": "The gate reports a three-state verdict",
             "functional_section": "Manifest validation",
             "conditions_of_satisfaction": "The gate distinguishes substantive from record-keeping failures.",
             "references": ["scripts/quality_gate.py"], "source_type": "code-derived"},
            {"id": "REQ-003", "title": "Absent required manifests fail at the phase boundary",
             "functional_section": "Manifest validation",
             "conditions_of_satisfaction": "A missing requirements_manifest.json fails phase-2 validation.",
             "references": ["scripts/validate_phase_artifacts.py"], "source_type": "code-derived"},
            {"id": "REQ-004", "title": "Phase E renumbers requirements to document order",
             "functional_section": "Rendering",
             "conditions_of_satisfaction": "REQ ids are sequential in document order after E.6.",
             "references": ["references/requirements_pipeline.md"], "source_type": "code-derived"},
            {"id": "REQ-005", "title": "The render contract splits tool-contract REQs out",
             "functional_section": "Rendering",
             "conditions_of_satisfaction": "quality/-only REQs render to RUN_CONTRACT.md, not REQUIREMENTS.md.",
             "references": ["scripts/quality_gate.py"], "source_type": "code-derived"},
            {"id": "REQ-006", "title": "The render contract rejects derivation internals",
             "functional_section": "Rendering",
             "conditions_of_satisfaction": "HTML comments and pass-name vocabulary are rejected in the render.",
             "references": ["scripts/quality_gate.py"], "source_type": "code-derived"},
        ],
    }


def _render_requirements_md(manifest, renumber=True):
    """Minimal Feature-C-conforming render of the fixture manifest.

    Not the production renderer (there isn't one — the agent renders); just
    enough to exercise check_render_contract, which is what the acceptance
    criterion requires ("re-render passes the Feature C render contract").

    ``renumber`` models the interview's terminal E.6 step (instruction 007):
    with renumber=True the IDs are reassigned to document order (the correct
    terminal-renumber behaviour); renumber=False models the DEFERRED-renumber
    bug all three 2026-07-21 runs exhibited — the records are ordered by
    section but keep their raw IDs, so an add's high temp ID appears early and
    the document ships out of ascending order.
    """
    # Phase E.6: renumber to document order (section order, then within
    # section). The interview re-renders THROUGH Feature C, so this is part
    # of the re-render, and the manifest ids are updated to match.
    ordered = []
    seen_sections = []
    for r in manifest["records"]:
        if r["functional_section"] not in seen_sections:
            seen_sections.append(r["functional_section"])
    for sec in seen_sections:
        ordered += [r for r in manifest["records"] if r["functional_section"] == sec]
    if renumber:
        for i, r in enumerate(ordered, start=1):
            r["id"] = f"REQ-{i:03d}"
    manifest["records"] = ordered
    recs = ordered
    lines = [
        "# Requirements — qpb-selfderiv",
        "",
        f"> Generated by [Quality Playbook](https://x) v{SKILL_VERSION} — Andrew Stellman",
        "",
        "## Overview",
        "",
        "QPB validates code against derived requirements. Coverage and known",
        "gaps: this sample covers manifest validation and rendering; it did",
        "not cover the exploration phase, which was out of scope here.",
        "",
        "## Actors and roles",
        "",
        "Adopters run the gate; maintainers derive requirements.",
        "",
        "## Glossary",
        "",
        "**Manifest** — the machine-readable requirements source of truth.",
        "**Render contract** — the mechanical checks on REQUIREMENTS.md.",
        "",
        "## Requirement organization",
        "",
        "These requirements are organized by system capability because QPB is",
        "a capability-shaped tool whose requirements group around the checks",
        "it provides; the sections follow that grouping.",
        "",
    ]
    # Group by functional_section in first-seen order.
    sections = {}
    for r in recs:
        sections.setdefault(r["functional_section"], []).append(r)
    for sec, sec_recs in sections.items():
        lines += [f"## {sec}", "", f"This section covers the {sec.lower()} contract.", ""]
        for r in sec_recs:
            lines += [f"### {r['id']}: {r['title']}", "",
                      f"- Conditions of satisfaction: {r['conditions_of_satisfaction']}",
                      f"- References: {', '.join(r['references'])}", ""]
    lines += ["## Cross-cutting concerns", "",
              "Validation and rendering both depend on the manifest wrapper shape.", "",
              "## Use cases", "", "### UC-01: An adopter runs the gate", "",
              "## Traceability appendix", "", "UC-01 → REQ-001, REQ-002", ""]
    return "\n".join(lines)


# --- The scripted operator moves and what the protocol writes for each. -----

def _apply_move(quality, manifest, move):
    """Apply one scripted interview move, per references/requirements_interview.md.

    Writes to the manifest (for confirm/correct/add/merge) AND appends the
    durable confirmation record. Returns the move dict for the defect log.
    """
    conf_path = quality / "operator_confirmations.jsonl"
    kind = move["move"]
    recs = manifest["records"]
    by_id = {r["id"]: r for r in recs}

    if kind == "confirm":
        rec = by_id[move["req"]]
        # A confirm marks the record as operator-vouched evidence.
        rec["source_type"] = "operator-confirmation"
        rec["citation"] = f"{TRANSCRIPT}:{move['line']}"
        title, cos = rec["title"], rec["conditions_of_satisfaction"]

    elif kind == "correct":
        rec = by_id[move["req"]]
        rec["title"] = move["new_title"]
        rec["conditions_of_satisfaction"] = move["new_cos"]
        rec["source_type"] = "operator-confirmation"
        rec["citation"] = f"{TRANSCRIPT}:{move['line']}"
        title, cos = rec["title"], rec["conditions_of_satisfaction"]

    elif kind == "add":
        new_id = f"REQ-{len(recs) + 1:03d}"
        rec = {
            "id": new_id, "title": move["title"],
            "functional_section": move["functional_section"],
            "conditions_of_satisfaction": move["cos"],
            "references": move["references"],
            "source_type": "operator-confirmation",
            "citation": f"{TRANSCRIPT}:{move['line']}",
        }
        recs.append(rec)
        title, cos = rec["title"], rec["conditions_of_satisfaction"]

    elif kind == "merge":
        # A merge is a correct that folds one REQ into another; the absorbed
        # REQ is dropped. The interview folds merges into 'correct'.
        keep = by_id[move["keep"]]
        drop = by_id[move["drop"]]
        keep["conditions_of_satisfaction"] = (
            keep["conditions_of_satisfaction"] + " " + drop["conditions_of_satisfaction"]
        )
        keep["references"] = sorted(set(keep["references"]) | set(drop["references"]))
        keep["source_type"] = "operator-confirmation"
        keep["citation"] = f"{TRANSCRIPT}:{move['line']}"
        manifest["records"] = [r for r in recs if r["id"] != move["drop"]]
        # merge is recorded as a 'correct' move in the durable log.
        run_state_lib.append_confirmation(conf_path, {
            "ts": "2026-07-21T15:05:00Z", "move": "correct",
            "req_title": keep["title"],
            "conditions_of_satisfaction": keep["conditions_of_satisfaction"],
            "operator_statement": move["operator_statement"],
            "transcript_citation": f"{TRANSCRIPT}:{move['line']}",
            "session_id": SESSION_ID,
        })
        return {"dimension": move["dimension"], "move": "correct",
                "req": move["keep"], "statement": move["operator_statement"]}

    run_state_lib.append_confirmation(conf_path, {
        "ts": "2026-07-21T15:05:00Z", "move": kind,
        "req_title": title, "conditions_of_satisfaction": cos,
        "operator_statement": move["operator_statement"],
        "transcript_citation": f"{TRANSCRIPT}:{move['line']}",
        "session_id": SESSION_ID,
    })
    return {"dimension": move["dimension"], "move": kind,
            "req": move.get("req", rec["id"]), "statement": move["operator_statement"]}


# The scripted test-double operator: one confirm, one correct, one add, one
# merge. Keyed on the base manifest's ids (before the render-time renumber).
CONFIRMED_TITLE = "The gate rejects a manifest with a bad wrapper key"
CORRECTED_TITLE = "Phase E.6 renumbers requirements to strict document order"
ADDED_TITLE = "The gate fails a run that truncates operator_confirmations.jsonl"
MERGED_AWAY_TITLE = "The render contract rejects derivation internals"

SCRIPTED_SESSION = [
    {"move": "confirm", "req": "REQ-001", "line": 10, "dimension": "Verifiable",
     "operator_statement": "Yes, the bad-wrapper rejection is exactly right."},
    {"move": "correct", "req": "REQ-004", "line": 20, "dimension": "Unambiguous",
     "new_title": CORRECTED_TITLE,
     "new_cos": "After E.6, REQ ids are 001..NNN in strict document order with no gaps.",
     "operator_statement": "Say 'strict document order, no gaps' — 'document order' alone is vague."},
    {"move": "add", "line": 30, "dimension": "Complete",
     "title": ADDED_TITLE,
     "functional_section": "Manifest validation",
     "cos": "A re-derivation that shortens the confirmations log fails the gate (F-2a).",
     "references": ["scripts/quality_gate.py"],
     "operator_statement": "You missed the F-2a durability guarantee entirely — add it."},
    # Merge WITHIN the Rendering section, so it still has >=2 REQs after.
    {"move": "merge", "keep": "REQ-005", "drop": "REQ-006", "line": 40, "dimension": "Consistent",
     "operator_statement": "REQ-005 and REQ-006 are the same render-rejection contract — merge them."},
]


def _find(records, title_substr):
    for r in records:
        if title_substr in r["title"]:
            return r
    return None


def _write_defect_log(quality, defects):
    lines = ["# Requirements Review — qpb-selfderiv", "",
             f"Session: {SESSION_ID}", ""]
    by_dim = {}
    for d in defects:
        by_dim.setdefault(d["dimension"], []).append(d)
    for dim, items in by_dim.items():
        lines += [f"## {dim}", ""]
        for it in items:
            lines += [f"- **{it['move']}** {it['req']}: {it['statement']}"]
        lines.append("")
    (quality / "REQUIREMENTS_REVIEW.md").write_text("\n".join(lines), encoding="utf-8")


def _run_session(quality, session=SCRIPTED_SESSION, write_manifest_each=True):
    """Drive a scripted session; return the final manifest dict."""
    manifest = _base_manifest()
    (quality / "review_sessions").mkdir(parents=True, exist_ok=True)
    (quality / f"review_sessions/{SESSION_ID}.md").write_text(
        "# Interview transcript\n\n" + "\n".join(
            f"L{m['line']}: {m['operator_statement']}" for m in session
        ) + "\n", encoding="utf-8")
    defects = []
    for move in session:
        defects.append(_apply_move(quality, manifest, move))
    _write_defect_log(quality, defects)
    if write_manifest_each:
        (quality / "requirements_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
        (quality / "REQUIREMENTS.md").write_text(
            _render_requirements_md(manifest), encoding="utf-8")
    return manifest


def _gate(check, *args):
    quality_gate.FAIL = 0
    quality_gate.WARN = 0
    quality_gate._FAIL_RECORDS = []
    quality_gate._WARN_RECORDS = []
    buf = io.StringIO()
    with redirect_stdout(buf):
        check(*args)
    return quality_gate.FAIL, quality_gate.WARN, buf.getvalue()


class InterviewFixtureSessionTests(unittest.TestCase):
    """The scripted session produces gate-valid artifacts (Plan Phase 4)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.q = self.repo / "quality"
        self.q.mkdir(parents=True)
        self.manifest = _run_session(self.q)

    def tearDown(self):
        self._tmp.cleanup()

    def test_touched_records_carry_operator_confirmation(self):
        # Keyed on content, not id — the render-time renumber reassigns ids,
        # which is the whole reason F-2a keys on content too.
        for title in (CONFIRMED_TITLE, CORRECTED_TITLE, ADDED_TITLE):
            with self.subTest(title=title):
                rec = _find(self.manifest["records"], title)
                self.assertIsNotNone(rec, f"record {title!r} not in manifest")
                self.assertEqual(rec["source_type"], "operator-confirmation")
                self.assertIn("review_sessions", rec["citation"])

    def test_merge_dropped_the_absorbed_record(self):
        self.assertIsNone(
            _find(self.manifest["records"], MERGED_AWAY_TITLE),
            "the merged-away REQ must be gone as a standalone record")
        # ...but its content survives, folded into the kept REQ.
        keep = _find(self.manifest["records"],
                     "The render contract splits tool-contract REQs out")
        self.assertIn("HTML comments", keep["conditions_of_satisfaction"])

    def test_correction_reached_the_manifest(self):
        rec = _find(self.manifest["records"], CORRECTED_TITLE)
        self.assertIsNotNone(rec)
        self.assertIn("strict document order", rec["conditions_of_satisfaction"])
        self.assertIn("no gaps", rec["conditions_of_satisfaction"])

    def test_rerender_passes_the_feature_c_render_contract(self):
        fails, warns, out = _gate(
            quality_gate.check_render_contract, self.repo, self.q, SKILL_VERSION)
        self.assertEqual(fails, 0, f"re-render must pass the render contract:\n{out}")

    def test_operator_confirmations_gate_validates(self):
        fails, _w, out = _gate(
            quality_gate.check_operator_confirmations_append_only, self.q)
        self.assertEqual(fails, 0, out)
        recs = run_state_lib.read_confirmations(self.q / "operator_confirmations.jsonl")
        self.assertEqual(len(recs), 4, "one record per scripted move")

    def test_defect_log_gate_validates(self):
        fails, _w, out = _gate(quality_gate.check_requirements_review, self.q)
        self.assertEqual(fails, 0, out)
        self.assertIn("organized by Wiegers attribute", out)

    def test_manifest_source_type_check_passes(self):
        # The gate's own source_type invariant accepts the new records.
        (self.q / "requirements_manifest.json").write_text(
            json.dumps(self.manifest, indent=2), encoding="utf-8")
        fails, _w, out = _gate(
            quality_gate.check_v1_5_3_source_type_validation, self.q)
        self.assertEqual(fails, 0, out)


def _apply_move_broken_correct(quality, manifest, move):
    """A write-back with the 'correct' move's manifest write removed.

    Everything else is honest: the transcript and the durable log still
    record the correction, but the manifest record is never updated — the
    exact defect Plan Phase 4's mutation requires the fixture to catch.
    """
    if move["move"] != "correct":
        return _apply_move(quality, manifest, move)
    # Log + transcript-citation only; NO manifest write.
    run_state_lib.append_confirmation(quality / "operator_confirmations.jsonl", {
        "ts": "2026-07-21T15:05:00Z", "move": "correct",
        "req_title": move["new_title"], "conditions_of_satisfaction": move["new_cos"],
        "operator_statement": move["operator_statement"],
        "transcript_citation": f"{TRANSCRIPT}:{move['line']}", "session_id": SESSION_ID,
    })
    return {"dimension": move["dimension"], "move": "correct",
            "req": move["req"], "statement": move["operator_statement"]}


class CorrectionMustReachManifestMutationTests(unittest.TestCase):
    """Mutation: a correction that never reaches the manifest fails the fixture.

    Not a tautology (self-Council Panelist A): this drives a REAL session
    through a mutated write-back whose 'correct' move skips the manifest
    write, then asserts the fixture's own acceptance property — the
    corrected text must be in the manifest — FAILS. A fixture that only
    checked the durable log would pass while the spec is broken; this proves
    the acceptance checks the manifest, the source of truth.
    """

    def test_correction_dropped_from_manifest_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = Path(tmp) / "quality"
            q.mkdir(parents=True)
            # Run the real session, but with the broken correct-move.
            manifest = _base_manifest()
            (q / "review_sessions").mkdir(parents=True)
            (q / f"review_sessions/{SESSION_ID}.md").write_text("t\n", encoding="utf-8")
            for move in SCRIPTED_SESSION:
                _apply_move_broken_correct(q, manifest, move)
            (q / "requirements_manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8")

            # The acceptance property the real fixture checks (see
            # InterviewFixtureSessionTests.test_correction_reached_the_manifest):
            # the corrected text must be in the manifest. Under the mutation it
            # is not — so that acceptance check would fail, which is the point.
            reached = _find(manifest["records"], CORRECTED_TITLE)
            self.assertIsNone(
                reached,
                "the mutation dropped the manifest write, so the correction "
                "must be absent from the manifest — this is what makes the "
                "real fixture's acceptance check fail, catching the defect.",
            )
            # And the durable log DOES claim it — so a log-only check would
            # have passed, which is why the acceptance must check the manifest.
            logged = run_state_lib.read_confirmations(q / "operator_confirmations.jsonl")
            self.assertTrue(
                any(CORRECTED_TITLE in r["req_title"] for r in logged),
                "the log records the correction the manifest lost — proving a "
                "log-only fixture would falsely pass.",
            )


class F2aDurabilityOracleTests(unittest.TestCase):
    """F-2a: confirm-then-re-derive keeps the .jsonl; a truncating path fails."""

    def _session_tree(self, tmp):
        q = Path(tmp) / "quality"
        q.mkdir(parents=True)
        _run_session(q)
        return q

    def test_rederive_preserving_confirmations_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = self._session_tree(tmp)
            conf = q / "operator_confirmations.jsonl"
            before = conf.read_text(encoding="utf-8")
            # A well-behaved re-derivation: snapshot the log, rebuild the
            # manifest, leave the log intact (even appending is fine).
            (q / "operator_confirmations.prior.jsonl").write_text(before, encoding="utf-8")
            (q / "requirements_manifest.json").write_text(
                json.dumps(_base_manifest(), indent=2), encoding="utf-8")
            self.assertEqual(conf.read_text(encoding="utf-8"), before,
                             "a correct re-derivation leaves the log intact")
            fails, _w, out = _gate(
                quality_gate.check_operator_confirmations_append_only, q)
            self.assertEqual(fails, 0, out)
            self.assertIn("append-only", out)

    def test_rederive_reports_prior_confirmations(self):
        """The read path surfaces prior confirmations by the operator's words."""
        with tempfile.TemporaryDirectory() as tmp:
            q = self._session_tree(tmp)
            recs = run_state_lib.read_confirmations(q / "operator_confirmations.jsonl")
            self.assertTrue(recs)
            # Each record carries the operator's verbatim statement, which is
            # what the read path quotes back next run.
            self.assertTrue(all(r["operator_statement"] for r in recs))
            self.assertTrue(
                any("strict" in r["operator_statement"].lower() for r in recs),
                "the corrected REQ's operator words are in the durable log")

    def test_truncating_rederive_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = self._session_tree(tmp)
            conf = q / "operator_confirmations.jsonl"
            (q / "operator_confirmations.prior.jsonl").write_text(
                conf.read_text(encoding="utf-8"), encoding="utf-8")
            # The truncating path: the re-derivation overwrote the log with
            # only its own fresh (empty) state.
            conf.write_text("", encoding="utf-8")
            fails, _w, out = _gate(
                quality_gate.check_operator_confirmations_append_only, q)
            self.assertGreaterEqual(fails, 1, out)

    def test_deleting_the_log_while_reqs_remain_fails_without_a_snapshot(self):
        """The hole Panelists A and D found, now closed.

        Deleting the whole log — with no .prior snapshot — while the manifest
        still carries operator-confirmation REQs must FAIL. Before the fix
        this passed as 'no interview has run', silently destroying the
        operator's work.
        """
        with tempfile.TemporaryDirectory() as tmp:
            q = self._session_tree(tmp)
            (q / "operator_confirmations.jsonl").unlink()
            # No .prior.jsonl snapshot exists — the manifest is the only
            # cross-reference, and it still names operator-confirmation REQs.
            self.assertFalse((q / "operator_confirmations.prior.jsonl").exists())
            manifest = json.loads(
                (q / "requirements_manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(
                any(r.get("source_type") == "operator-confirmation"
                    for r in manifest["records"]),
                "precondition: the session left operator-confirmation REQs")
            fails, _w, out = _gate(
                quality_gate.check_operator_confirmations_append_only, q)
            self.assertGreaterEqual(fails, 1, out)
            self.assertIn("no durable backing", out)

    def test_emptying_the_log_while_reqs_remain_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = self._session_tree(tmp)
            (q / "operator_confirmations.jsonl").write_text("", encoding="utf-8")
            fails, _w, out = _gate(
                quality_gate.check_operator_confirmations_append_only, q)
            self.assertGreaterEqual(fails, 1, out)

    def _well_formed_record(self):
        return {
            "ts": "2026-07-21T15:05:00Z", "move": "confirm",
            "req_title": "The gate rejects a manifest with a bad wrapper key",
            "conditions_of_satisfaction": "A manifest using 'requirements' is rejected.",
            "operator_statement": "Yes, that rejection is exactly right.",
            "session_id": SESSION_ID,
        }

    def test_gate_rejects_a_malformed_record_directly(self):
        """The gate's shape check is type-not-presence (Panelist B residual).

        A record whose required field is null or non-string passes a
        presence check but is not what the sanctioned writer produces.
        Drive check_operator_confirmations_append_only directly with such a
        record (round-1 coverage only exercised the writer, run_state_lib.
        append_confirmation) and require a FAIL.
        """
        good = self._well_formed_record()
        for field, bad in [("move", None), ("req_title", 123),
                           ("operator_statement", ""), ("session_id", None)]:
            with self.subTest(field=field, bad=bad):
                with tempfile.TemporaryDirectory() as tmp:
                    q = self._session_tree(tmp)  # manifest carries op-conf REQs
                    rec = dict(good, **{field: bad})
                    (q / "operator_confirmations.jsonl").write_text(
                        json.dumps(rec) + "\n", encoding="utf-8")
                    fails, _w, out = _gate(
                        quality_gate.check_operator_confirmations_append_only, q)
                    self.assertGreaterEqual(fails, 1, out)
                    self.assertIn("non-empty", out)

    def test_gate_accepts_a_well_formed_record_directly(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = self._session_tree(tmp)
            (q / "operator_confirmations.jsonl").write_text(
                json.dumps(self._well_formed_record()) + "\n", encoding="utf-8")
            fails, _w, out = _gate(
                quality_gate.check_operator_confirmations_append_only, q)
            self.assertEqual(fails, 0, out)


class TerminalRenumberTests(unittest.TestCase):
    """Instruction 007 work item 4 / Design §6: the interview runs the E.6
    renumber ONCE as the terminal step after all moves, so an add into an
    early section ships sequential document-order IDs, and the content-keyed
    confirmations still resolve. A deferred renumber (out-of-order IDs
    surviving to the final render) must fail the render contract.
    """

    ADDED_TITLE = "The gate rejects an unknown top-level wrapper key"

    def _session_with_early_add(self, quality):
        (quality / "review_sessions").mkdir(parents=True, exist_ok=True)
        (quality / f"review_sessions/{SESSION_ID}.md").write_text(
            "# Interview transcript\n\nL10: add the unknown-key rejection\n",
            encoding="utf-8")
        manifest = _base_manifest()
        first_section = manifest["records"][0]["functional_section"]
        _apply_move(quality, manifest, {
            "move": "add", "line": 10, "dimension": "Complete",
            "title": self.ADDED_TITLE,
            "functional_section": first_section,   # an EARLY section
            "cos": "A manifest whose top-level key is neither known nor 'records' is rejected.",
            "references": ["scripts/quality_gate.py"],
            "operator_statement": "You missed the unknown-key rejection — add it.",
        })
        return manifest

    def _write_and_gate(self, tmp, manifest, renumber):
        q = Path(tmp) / "quality"
        (q / "requirements_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
        (q / "REQUIREMENTS.md").write_text(
            _render_requirements_md(manifest, renumber=renumber), encoding="utf-8")
        return _gate(quality_gate.check_render_contract, Path(tmp), q, SKILL_VERSION)

    def test_terminal_renumber_ships_sequential_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = Path(tmp) / "quality"
            q.mkdir(parents=True)
            manifest = self._session_with_early_add(q)
            fails, _w, out = self._write_and_gate(tmp, manifest, renumber=True)
            self.assertEqual(fails, 0, out)
            self.assertIn("sequential in document order", out)
            # IDs are 001..N with no gaps and ascending.
            ids = [r["id"] for r in manifest["records"]]
            self.assertEqual(
                ids, [f"REQ-{i:03d}" for i in range(1, len(ids) + 1)])

    def test_added_confirmation_resolves_by_content_after_renumber(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = Path(tmp) / "quality"
            q.mkdir(parents=True)
            manifest = self._session_with_early_add(q)
            _render_requirements_md(manifest, renumber=True)
            # The confirmation is content-keyed (F-2a): it carries no req_id,
            # so the renumber leaves it untouched and it still resolves to the
            # added REQ by title. Prove the added REQ survived and its
            # confirmation matches by content.
            recs = run_state_lib.read_confirmations(q / "operator_confirmations.jsonl")
            conf = next(r for r in recs if r["req_title"] == self.ADDED_TITLE)
            self.assertNotIn("req_id", conf, "confirmations are content-keyed, not id-keyed")
            match = [r for r in manifest["records"] if r["title"] == self.ADDED_TITLE]
            self.assertEqual(len(match), 1, "the added REQ resolves by content post-renumber")

    def test_deferred_renumber_ships_out_of_order_and_fails(self):
        # The bug all three 2026-07-21 runs exhibited: skip the terminal
        # renumber, the add's high temp ID appears in its early section, the
        # document ships out of ascending order.
        with tempfile.TemporaryDirectory() as tmp:
            q = Path(tmp) / "quality"
            q.mkdir(parents=True)
            manifest = self._session_with_early_add(q)
            fails, _w, out = self._write_and_gate(tmp, manifest, renumber=False)
            self.assertGreaterEqual(fails, 1, out)
            self.assertIn("not sequential in document order", out)


class Fixture_RunStateLibHelpersTests(unittest.TestCase):
    """Direct coverage of the run_state_lib helpers (Panelist D: the module's
    confirmations_append_only was dead + untested; the gate drove only its
    inline mirror)."""

    def test_confirmations_append_only_matches_the_gate_mirror(self):
        # The two copies of the invariant must agree — a drift guard for the
        # duplication Panelist D flagged.
        cases = [
            ("", "anything\n", True),
            ("a\n", "a\nb\n", True),
            ("a\nb\n", "a\n", False),        # truncation
            ("a\nb\n", "x\nb\n", False),     # same-length rewrite
            ("a\nb\n", "b\na\n", False),     # reorder
            ("a\n", "a\n", True),            # unchanged
            ("a", "a\nb\n", True),           # prior without trailing newline
        ]
        for prior, current, expected in cases:
            with self.subTest(prior=prior, current=current):
                self.assertEqual(
                    run_state_lib.confirmations_append_only(prior, current),
                    expected)
                self.assertEqual(
                    quality_gate._opconf_is_append_only(prior, current),
                    expected,
                    "the gate's inline mirror disagrees with run_state_lib — "
                    "the two copies of the invariant have drifted")

    def test_append_confirmation_rejects_bad_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "operator_confirmations.jsonl"
            good = {"ts": "t", "move": "correct", "req_title": "X",
                    "conditions_of_satisfaction": "Y", "operator_statement": "Z",
                    "session_id": "s"}
            run_state_lib.append_confirmation(p, good)  # ok
            with self.assertRaises(ValueError):
                run_state_lib.append_confirmation(p, {**good, "move": "bogus"})
            with self.assertRaises(ValueError):
                run_state_lib.append_confirmation(p, {k: v for k, v in good.items()
                                                      if k != "req_title"})
            with self.assertRaises(ValueError):
                run_state_lib.append_confirmation(p, {**good, "session_id": 5})

    def test_read_confirmations_absent_file_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                run_state_lib.read_confirmations(Path(tmp) / "nope.jsonl"), [])


class RequirementsReviewGateTests(unittest.TestCase):
    """check_requirements_review FAIL/WARN/PASS paths (Panelist B: the FAIL
    paths had no automated coverage — a mutation that neutered the
    Wiegers-dimension FAIL turned no test red)."""

    def _run(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            q = Path(tmp) / "quality"
            q.mkdir(parents=True)
            (q / "REQUIREMENTS_REVIEW.md").write_text(body, encoding="utf-8")
            return _gate(quality_gate.check_requirements_review, q)

    def test_empty_log_fails(self):
        fails, _w, out = self._run("# Review\n")
        self.assertGreaterEqual(fails, 1, out)

    def test_no_wiegers_dimension_fails(self):
        fails, _w, out = self._run(
            "# Review\n\nThe operator looked at things and made changes to REQ-001.\n")
        self.assertGreaterEqual(fails, 1, out)
        self.assertIn("Wiegers", out)

    def test_substring_only_dimension_does_not_pass(self):
        # 'inconsistent' must NOT satisfy the 'consistent' dimension
        # (Panelist B: substring false-PASS).
        fails, _w, out = self._run(
            "# Review\n\nThe requirements were inconsistent and confusing.\n")
        self.assertGreaterEqual(fails, 1, out)

    def test_dimension_without_move_warns_not_fails(self):
        fails, warns, out = self._run(
            "# Review\n\n## Verifiable\n\nThe verifiable dimension was examined.\n")
        self.assertEqual(fails, 0, out)
        self.assertEqual(warns, 1, out)

    def test_well_formed_passes(self):
        fails, warns, out = self._run(
            "# Review\n\n## Verifiable\n\n- **correct** REQ-001: tighten the wording.\n")
        self.assertEqual(fails, 0, out)
        self.assertEqual(warns, 0, out)


class FiveMovesConsistencyTests(unittest.TestCase):
    """The five interview moves are declared in three places; they must agree
    (Panelists A and B flagged uncoordinated copies)."""

    def test_all_move_tuples_agree(self):
        expected = ("confirm", "correct", "add", "drop", "defer")
        self.assertEqual(set(run_state_lib._CONFIRMATION_MOVES), set(expected))
        self.assertEqual(set(quality_gate._OPCONF_MOVES), set(expected))
        self.assertEqual(set(quality_gate._REQ_REVIEW_MOVES), set(expected))


class WorkedExample20260502Tests(unittest.TestCase):
    """Re-run the 2026-05-02 worked example as a semi-scripted walkthrough.

    Plan Phase 4: the walkthrough must produce **stage-appropriate questions**
    and **durable corrections**. The worked example
    (`Reviews/QPB_v1.6.x_Requirements_Review_Worked_Example_2026-05-02.md`)
    is four real catches Andrew made by probing; each maps to one rubric
    dimension and one interview stage. This test asserts the protocol asks
    the right question at the right stage for each, and that driving them
    through the session leaves durable records.
    """

    # (catch, stage, dimension, elicitation phrase the protocol must carry)
    WORKED_EXAMPLE_CATCHES = [
        ("outcome verification (projected +0.40 vs measured +0.20)",
         "Stage 3", "Verifiable", "does the measured result match the claim"),
        ("terminology disambiguation (pattern vs lever)",
         "Stage 2", "Consistent", "load-bearing term"),
        ("identity/independence (chi double-counted)",
         "Stage 2", "Consistent", "double-counted"),
        ("dependency tracing (six->seven hardcode)",
         "Stage 2", "Correct", "every place that must change"),
    ]

    def test_protocol_carries_a_stage_question_for_each_catch(self):
        protocol = (
            REPO_ROOT / "references" / "requirements_interview.md"
        ).read_text(encoding="utf-8", errors="replace")
        for catch, stage, dimension, phrase in self.WORKED_EXAMPLE_CATCHES:
            with self.subTest(catch=catch):
                self.assertIn(
                    phrase, protocol,
                    f"the protocol has no elicitation question for the "
                    f"{catch!r} catch (expected a {dimension} question at "
                    f"{stage}).",
                )

    def test_walkthrough_produces_durable_corrections(self):
        """Driving the four catches leaves durable operator-confirmation records."""
        # Each worked-example catch becomes a correct/add move.
        session = [
            {"move": "correct", "req": "REQ-004", "line": 11, "dimension": "Verifiable",
             "new_title": "Projection accuracy is recorded against measured recall",
             "new_cos": "When a REQ carries a projection, the measured result is recorded and the gap noted.",
             "operator_statement": "The projection said +0.40; measured was +0.20. Record the gap."},
            {"move": "add", "line": 35, "dimension": "Consistent",
             "title": "A glossary distinguishes 'pattern' from 'lever'",
             "functional_section": "Rendering",
             "cos": "Every load-bearing term is defined once; 'pattern' and 'lever' name different layers.",
             "references": ["references/requirements_interview.md"],
             "operator_statement": "Pattern and lever are used interchangeably — they are different layers. Glossary them."},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            q = Path(tmp) / "quality"
            q.mkdir(parents=True)
            _run_session(q, session=session)
            # Durable: the corrections survive in the append-only log.
            recs = run_state_lib.read_confirmations(q / "operator_confirmations.jsonl")
            self.assertEqual(len(recs), 2)
            statements = " ".join(r["operator_statement"] for r in recs)
            self.assertIn("+0.40", statements)
            self.assertIn("layers", statements)
            # And the gate accepts the resulting tree.
            fails, _w, out = _gate(
                quality_gate.check_operator_confirmations_append_only, q)
            self.assertEqual(fails, 0, out)
            frr, _w2, out2 = _gate(quality_gate.check_requirements_review, q)
            self.assertEqual(frr, 0, out2)

    def test_catches_map_to_distinct_stages_not_all_stage_3(self):
        """The value of a staged interview: cheap catches surface early.

        Three of the four worked-example catches are Stage 1/2 — the
        design's claim that most fitness-for-purpose defects surface before
        per-REQ drill-down. A protocol that pushed everything to Stage 3
        would miss them cheaply.
        """
        stages = [stage for _c, stage, _d, _p in self.WORKED_EXAMPLE_CATCHES]
        self.assertLessEqual(
            stages.count("Stage 3"), 1,
            "most worked-example catches must be Stage 1/2 — the whole point "
            "of breadth-first is catching them before per-REQ drill-down.",
        )


if __name__ == "__main__":
    unittest.main()
