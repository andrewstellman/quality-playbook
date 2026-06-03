"""v1.5.7 092 — security grader tests.

Covers ``bin/harness/grade_security.py``:

  EvidenceExtractionTests — file_cited / symbol_cited /
    behavior_cited against synthetic BUGS.md + writeups text.
  OutcomeClassificationTests — DETECTED / PARTIAL / MISSED
    routing per the file-AND-(symbol-OR-behavior) policy.
  BlockedRoutingTests — F-note 3 (LOCKED): `run_meta.blocked`
    → outcome=BLOCKED, NEVER MISSED. **Mutation-bite present.**
  MissingArtifactsTests — quality/ tree absent → MISSED with
    explanatory note (no crash).
  AuditableEvidenceTests — grading.evidence dict carries the
    per-criterion flags + answer_key reference so a human
    reviewer can audit the auto-grade.
  TopLevelGraderTests — rejects acceptance cases.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bin.harness import grade_security as GS
from bin.harness import schema as S


def _mk_security_case(*, file: str = "setuptools/package_index.py",
                       symbol: str = "_resolve_download_filename",
                       behavior: str = (
                           "URL-derived filename joined via "
                           "os.path.join discards tmpdir when name is "
                           "absolute; insufficient sanitization "
                           "allows arbitrary file write outside tmpdir"
                       ),
                       cwe: str = "CWE-22") -> S.Case:
    return S.Case(
        id="SEC-T", type=S.CaseType.SECURITY_EVAL, title="t",
        inputs=S.CaseInputs(
            repo_url="u", prep=S.PrepPolicy.SECURITY,
            vulnerable_parent="abc",
        ),
        answer_key=S.AnswerKey(
            cwe=cwe, vulnerable_parent="abc",
            file=file, symbol=symbol, behavior=behavior,
        ),
    )


def _mk_facts(*, blocked: bool = False,
              stop_reason: "str | None" = None) -> S.RunFacts:
    return S.RunFacts(
        phase0=S.Phase0Facts(status="ok", probe_attempts=1,
                                first_probe_ok=True),
        verdict=S.VerdictFacts(
            verdict_state=S.VerdictState.SOLID,
            attribution=S.Attribution.NONE,
            recommends_stronger_model=False,
            bugs_unverified_present=False,
        ),
        provenance=S.ProvenanceFacts(
            detected_runner="claude-code",
            selfreport_model_label="opus",
            gate_bug_count=1, reported_bug_count=1,
            provenance_mismatch=False,
        ),
        gate=S.GateFacts(
            gate_total="Total: 0 FAIL, 0 WARN",
            gate_result=S.GateResult.PASS,
            cleanup_gaps=0,
        ),
        install=S.InstallSurfaceFacts(
            banner_rendered=True,
            gitignore_remediation_followed=True,
        ),
        run_meta=S.RunMetaFacts(
            blocked=blocked, stop_reason=stop_reason,
            exit_code=0, timings={},
            raw_receipt="stream.ndjson",
        ),
    )


def _write_quality_tree(td: Path, *, bugs_md: str = "",
                         writeup_body: str = "") -> Path:
    """Write a minimal quality/ tree with BUGS.md + a single
    writeup. Returns the quality_dir path."""
    q = td / "quality"
    q.mkdir()
    (q / "BUGS.md").write_text(bugs_md)
    if writeup_body:
        (q / "writeups").mkdir()
        (q / "writeups" / "BUG-001.md").write_text(writeup_body)
    return q


# ---------------------------------------------------------------------------
# Evidence extraction
# ---------------------------------------------------------------------------


class EvidenceExtractionTests(unittest.TestCase):

    def test_file_cited_by_full_path(self) -> None:
        case = _mk_security_case()
        text = "Found a bug in setuptools/package_index.py."
        self.assertTrue(GS._file_cited(text, case.answer_key))

    def test_file_cited_by_basename(self) -> None:
        case = _mk_security_case()
        text = "The bug is in package_index.py at line 200."
        self.assertTrue(GS._file_cited(text, case.answer_key))

    def test_file_not_cited(self) -> None:
        case = _mk_security_case()
        text = "Looked at some unrelated module."
        self.assertFalse(GS._file_cited(text, case.answer_key))

    def test_symbol_cited_verbatim(self) -> None:
        case = _mk_security_case()
        text = "The _resolve_download_filename function is unsafe."
        self.assertTrue(GS._symbol_cited(text, case.answer_key))

    def test_symbol_cited_via_locus_token(self) -> None:
        """The heuristic tokenises `locus` into individual
        identifier-like names and looks for them in the text."""
        # CASE-001 shape: locus = "PackageIndex._resolve_download_
        # filename / _download_url" → token _download_url
        case = S.Case(
            id="SEC-T", type=S.CaseType.SECURITY_EVAL, title="t",
            inputs=S.CaseInputs(
                repo_url="u", prep=S.PrepPolicy.SECURITY,
                vulnerable_parent="abc",
            ),
            answer_key=S.AnswerKey(
                cwe="CWE-22", vulnerable_parent="abc",
                file="x.py", symbol="<unspecified>",
                behavior="<unspecified>",
                locus=("PackageIndex._resolve_download_filename "
                        "/ _download_url"),
            ),
        )
        text = "Bug is in _download_url path-handling logic."
        self.assertTrue(GS._symbol_cited(text, case.answer_key))

    def test_behavior_cited_two_keyword_hits(self) -> None:
        """≥ 2 distinctive token hits → behavior_cited True."""
        case = _mk_security_case()
        text = (
            "The function constructs the filename from a URL, "
            "then passes it to os.path.join which doesn't "
            "sanitize correctly. Result is an arbitrary file "
            "write outside the tmpdir."
        )
        self.assertTrue(GS._behavior_cited(text, case.answer_key))

    def test_behavior_one_keyword_hit_not_enough(self) -> None:
        """A single common-word match must NOT trigger
        behavior_cited (the 2-hit threshold prevents
        coincidental matches)."""
        case = _mk_security_case()
        text = "We talked about filename handling in general."
        self.assertFalse(GS._behavior_cited(text, case.answer_key))


# ---------------------------------------------------------------------------
# Outcome classification
# ---------------------------------------------------------------------------


class OutcomeClassificationTests(unittest.TestCase):

    def test_detected_when_file_AND_symbol_cited(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            q = _write_quality_tree(Path(td),
                bugs_md=(
                    "# Bugs\n\n"
                    "### BUG-001: setuptools/package_index.py "
                    "_resolve_download_filename mishandles "
                    "filenames.\n"
                ),
            )
            grading = GS.grade_security(
                _mk_security_case(), _mk_facts(), q, "rid",
            )
            self.assertEqual(grading.outcome, "DETECTED")
            self.assertTrue(grading.evidence["file_cited"])
            self.assertTrue(grading.evidence["symbol_cited"])

    def test_detected_when_file_AND_behavior_cited(self) -> None:
        """File cited + 2+ behavior tokens cited → DETECTED
        even without the verbatim symbol."""
        with tempfile.TemporaryDirectory() as td:
            q = _write_quality_tree(Path(td),
                bugs_md=(
                    "# Bugs\n\n"
                    "### BUG-001: package_index.py constructs "
                    "filename from URL via os.path.join, "
                    "allowing arbitrary file write outside "
                    "tmpdir when path is absolute.\n"
                ),
            )
            grading = GS.grade_security(
                _mk_security_case(), _mk_facts(), q, "rid",
            )
            self.assertEqual(grading.outcome, "DETECTED")

    def test_partial_when_only_file_cited(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            q = _write_quality_tree(Path(td),
                bugs_md=(
                    "# Bugs\n\n"
                    "### BUG-001: package_index.py has some bug.\n"
                ),
            )
            grading = GS.grade_security(
                _mk_security_case(), _mk_facts(), q, "rid",
            )
            self.assertEqual(grading.outcome, "PARTIAL")
            self.assertTrue(grading.evidence["file_cited"])
            self.assertFalse(grading.evidence["symbol_cited"])

    def test_missed_when_nothing_cited(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            q = _write_quality_tree(Path(td),
                bugs_md=(
                    "# Bugs\n\n"
                    "### BUG-001: Unrelated bug in other_module.py.\n"
                ),
            )
            grading = GS.grade_security(
                _mk_security_case(), _mk_facts(), q, "rid",
            )
            self.assertEqual(grading.outcome, "MISSED")

    def test_missed_when_empty_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            q = _write_quality_tree(Path(td), bugs_md="")
            grading = GS.grade_security(
                _mk_security_case(), _mk_facts(), q, "rid",
            )
            self.assertEqual(grading.outcome, "MISSED")
            self.assertIn("no findings", (grading.note or "").lower()  # type: ignore[union-attr]
                          + " " + str(grading.note or "").lower())


# ---------------------------------------------------------------------------
# F-note 3: BLOCKED ⇒ N/A
# ---------------------------------------------------------------------------


class BlockedRoutingTests(unittest.TestCase):

    def test_blocked_run_routes_to_BLOCKED_never_MISSED(self) -> None:
        """v1.5.7 092 F-note 3 MUTATION BITE: a BLOCKED run
        (AUP/usage-policy stop) routes to outcome=BLOCKED, NEVER
        to MISSED. Even if the agent produced no findings (which
        on a normal run would be MISSED), the BLOCKED status is
        the dominant signal.

        Mutation bite: drop the early-return on
        `facts.run_meta.blocked` → an AUP-stopped run that
        produced no quality/ findings would auto-grade MISSED,
        which is a false-detection-failure (the agent didn't
        miss the bug — the run never finished). This test FAILs
        if that path is taken.
        """
        facts_blocked = _mk_facts(blocked=True,
                                    stop_reason="policy refusal")
        with tempfile.TemporaryDirectory() as td:
            q = _write_quality_tree(Path(td), bugs_md="")
            grading = GS.grade_security(
                _mk_security_case(), facts_blocked, q, "rid",
            )
            self.assertEqual(
                grading.outcome, "BLOCKED",
                "v1.5.7 092 F-note 3: a BLOCKED run MUST NOT "
                "auto-grade MISSED. The agent didn't miss the "
                "bug — the run never finished.",
            )
            self.assertTrue(grading.blocked)
            self.assertIn("AUP", grading.note or "")
            self.assertIn("N/A", grading.note or "")

    def test_blocked_even_when_findings_present(self) -> None:
        """BLOCKED is dominant: even if BUGS.md somehow has the
        right finding, BLOCKED status overrides — the run didn't
        complete legitimately."""
        facts_blocked = _mk_facts(blocked=True,
                                    stop_reason="cannot help")
        with tempfile.TemporaryDirectory() as td:
            q = _write_quality_tree(Path(td),
                bugs_md=("### BUG-001: setuptools/package_index.py "
                          "_resolve_download_filename"),
            )
            grading = GS.grade_security(
                _mk_security_case(), facts_blocked, q, "rid",
            )
            self.assertEqual(grading.outcome, "BLOCKED")


# ---------------------------------------------------------------------------
# Missing quality/ tree
# ---------------------------------------------------------------------------


class MissingArtifactsTests(unittest.TestCase):

    def test_missing_quality_dir_yields_missed_with_note(
            self) -> None:
        """A missing quality/ tree → outcome=MISSED with a note
        explaining the agent produced no canonical evidence
        surface. Defensive direction (NO crash)."""
        with tempfile.TemporaryDirectory() as td:
            grading = GS.grade_security(
                _mk_security_case(), _mk_facts(),
                Path(td) / "nonexistent_quality", "rid",
            )
            self.assertEqual(grading.outcome, "MISSED")
            self.assertIn("absent", grading.note or "")


# ---------------------------------------------------------------------------
# Audit evidence
# ---------------------------------------------------------------------------


class AuditableEvidenceTests(unittest.TestCase):

    def test_evidence_dict_carries_per_criterion_flags(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            q = _write_quality_tree(Path(td),
                bugs_md=("### BUG-001: package_index.py "
                          "_resolve_download_filename"),
            )
            grading = GS.grade_security(
                _mk_security_case(), _mk_facts(), q, "rid",
            )
            self.assertIn("file_cited", grading.evidence)
            self.assertIn("symbol_cited", grading.evidence)
            self.assertIn("behavior_cited", grading.evidence)
            self.assertIn("answer_key", grading.evidence)
            # And answer_key reference for the auditor:
            self.assertEqual(
                grading.evidence["answer_key"]["cwe"], "CWE-22",
            )

    def test_grading_reviewed_starts_false(self) -> None:
        """F-note 4: auto-grade always lands with
        `reviewed:false`; human review sets it later."""
        with tempfile.TemporaryDirectory() as td:
            q = _write_quality_tree(Path(td), bugs_md="")
            grading = GS.grade_security(
                _mk_security_case(), _mk_facts(), q, "rid",
            )
            self.assertFalse(grading.reviewed)
            self.assertIsNone(grading.human_verdict)


# ---------------------------------------------------------------------------
# Top-level grader entry
# ---------------------------------------------------------------------------


class TopLevelGraderTests(unittest.TestCase):

    def test_rejects_acceptance_case(self) -> None:
        acc = S.Case(
            id="ACC-T", type=S.CaseType.ACCEPTANCE, title="t",
            inputs=S.CaseInputs(
                repo_url="u", prep=S.PrepPolicy.ACCEPTANCE,
            ),
            expected=[],
        )
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(GS.SecurityGraderError) as ctx:
                GS.grade_security(
                    acc, _mk_facts(), Path(td), "rid",
                )
            self.assertIn("non-security_eval", str(ctx.exception))

    def test_grading_json_serializes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            q = _write_quality_tree(Path(td), bugs_md="")
            grading = GS.grade_security(
                _mk_security_case(), _mk_facts(), q, "rid",
            )
            import json
            as_json = grading.to_json()
            json.dumps(as_json)
            self.assertEqual(as_json["case_id"], "SEC-T")
            self.assertEqual(as_json["case_type"], "security_eval")
            self.assertIn(as_json["outcome"],
                          ("DETECTED", "PARTIAL", "MISSED", "BLOCKED"))


if __name__ == "__main__":
    unittest.main()
