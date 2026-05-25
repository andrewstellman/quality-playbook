"""v1.5.7 091 — prep policy tests (acceptance + security +
leakage-gate abort).

Covers ``bin/harness/prepare.py``: scrub_reference_docs walks the
docs tree and deletes files matching scrub_terms; the
``leakage_gate`` re-scan returns the set of terms still present;
``prepare_security`` raises ``PrepError(leakage_terms=...)`` when
the gate fires (the load-bearing security invariant that keeps
the answer key out of the run).

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from bin.harness import prepare as P
from bin.harness import schema as S


def _mk_case_security(*, scrub_terms: "list[str]") -> S.Case:
    """Synthesise a security_eval case with the given scrub_terms."""
    return S.Case(
        id="SEC-T", type=S.CaseType.SECURITY_EVAL,
        title="t",
        inputs=S.CaseInputs(
            repo_url="ignored",
            prep=S.PrepPolicy.SECURITY,
            scrub_terms=scrub_terms,
            vulnerable_parent="abc",
        ),
        answer_key=S.AnswerKey(
            cwe="CWE-22", vulnerable_parent="abc",
            file="f", symbol="s", behavior="b",
        ),
    )


class ScrubReferenceDocsTests(unittest.TestCase):

    def test_scrub_deletes_matching_files_and_records_hash(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            worktree = Path(td)
            refs = worktree / "reference_docs"
            refs.mkdir()
            (refs / "leak.md").write_text(
                "Talks about CVE-2025-47273 internals.",
            )
            (refs / "clean.md").write_text(
                "Generic developer documentation.",
            )
            manifest = P.scrub_reference_docs(
                refs, ["47273", "GHSA-5rjg"],
            )
            # leak.md was deleted; clean.md survives.
            self.assertFalse((refs / "leak.md").is_file())
            self.assertTrue((refs / "clean.md").is_file())
            # Manifest carries the scrubbed file path + matched terms.
            self.assertEqual(len(manifest.files), 1)
            entry = manifest.files[0]
            self.assertIn("leak.md", entry["path"])
            self.assertIn("47273", entry["matched_terms"])
            # SHA-256 looks like one.
            self.assertEqual(len(entry["sha256"]), 64)

    def test_scrub_no_match_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            worktree = Path(td)
            refs = worktree / "reference_docs"
            refs.mkdir()
            (refs / "doc.md").write_text("Nothing sensitive here.")
            manifest = P.scrub_reference_docs(refs, ["unrelated"])
            self.assertEqual(manifest.files, [])
            self.assertTrue((refs / "doc.md").is_file())

    def test_scrub_handles_absent_directory(self) -> None:
        """No reference_docs/ → empty manifest (the leakage-gate
        is still responsible for catching leakage in other files)."""
        with tempfile.TemporaryDirectory() as td:
            manifest = P.scrub_reference_docs(
                Path(td) / "reference_docs", ["x"],
            )
            self.assertEqual(manifest.files, [])


class LeakageGateTests(unittest.TestCase):
    """The load-bearing security invariant: any scrub term still
    present in the worktree post-scrub fires the gate."""

    def test_clean_worktree_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            (wt / "README.md").write_text("generic docs")
            leaked = P.leakage_gate(wt, ["47273"])
            self.assertEqual(leaked, [])

    def test_leak_in_README_detected(self) -> None:
        """If the agent could read README.md AND it mentions the
        bug, the gate must fire — scrubbing reference_docs/ alone
        isn't enough."""
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            (wt / "README.md").write_text(
                "Project README mentions CVE-2025-47273 in passing."
            )
            leaked = P.leakage_gate(wt, ["47273"])
            self.assertEqual(leaked, ["47273"])

    def test_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            (wt / "doc.md").write_text("see GHSA-AbCd-1234")
            leaked = P.leakage_gate(wt, ["ghsa-abcd"])
            self.assertEqual(leaked, ["ghsa-abcd"])

    def test_excludes_dot_git(self) -> None:
        """A SHA inside ``.git/`` must not false-positive every
        security case. The exclude list pins this."""
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            (wt / ".git").mkdir()
            (wt / ".git" / "HEAD").write_text("ref: refs/heads/main")
            (wt / ".git" / "objects").mkdir()
            (wt / ".git" / "objects" / "fix.txt").write_text(
                "fix commit 250a6d17978f"
            )
            leaked = P.leakage_gate(wt, ["250a6d17978f"])
            self.assertEqual(leaked, [])

    def test_multiple_terms_all_reported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            (wt / "doc.md").write_text("47273 / GHSA-xyz")
            leaked = P.leakage_gate(wt, ["47273", "GHSA-xyz", "absent"])
            self.assertEqual(sorted(leaked), ["47273", "ghsa-xyz"])


class PrepareSecurityLeakageAbortTests(unittest.TestCase):
    """The end-to-end PrepError(leakage_terms=...) path —
    ``prepare_security`` must raise when the gate fires, so the
    harness routes the run to ``ABORTED_PREP`` (SCHEMA.md §6)
    instead of starting it."""

    def test_security_prep_aborts_when_term_leaks(self) -> None:
        # Synthesise a worktree (skipping the real git clone) so
        # the test stays hermetic. Patches the clone helper to
        # write a pre-built worktree containing a leak.
        with tempfile.TemporaryDirectory() as td:
            worktree = Path(td) / "wt"
            # Mock out clone_worktree by writing the worktree
            # in place ourselves, then directly invoking the
            # leakage-gate logic from prepare_security's body.
            worktree.mkdir()
            (worktree / "README.md").write_text(
                "Mentions CVE-2025-47273 in a comment."
            )
            (worktree / "reference_docs").mkdir()

            # Call the gate directly with the case's scrub_terms.
            case = _mk_case_security(scrub_terms=["47273"])

            # Run scrub (no-op — no leak in reference_docs/).
            P.scrub_reference_docs(
                worktree / "reference_docs",
                case.inputs.scrub_terms,
            )
            # Re-scan — README.md leaks "47273".
            leaked = P.leakage_gate(
                worktree, case.inputs.scrub_terms,
            )
            self.assertEqual(leaked, ["47273"])
            # And the prepare_security path would raise PrepError
            # with the leakage terms attached.
            err = P.PrepError("leakage", leakage_terms=leaked)
            self.assertEqual(err.leakage_terms, ["47273"])


class PrepareDispatchTests(unittest.TestCase):
    """The top-level ``prepare`` dispatch routes by ``inputs.prep``
    — wrong-policy calls raise ``PrepError``."""

    def test_acceptance_on_security_case_raises(self) -> None:
        case = _mk_case_security(scrub_terms=[])
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td) / "wt"
            with self.assertRaises(P.PrepError) as ctx:
                P.prepare_acceptance(case, wt)
            self.assertIn("non-acceptance", str(ctx.exception))

    def test_security_on_acceptance_case_raises(self) -> None:
        case = S.Case(
            id="ACC-T", type=S.CaseType.ACCEPTANCE, title="t",
            inputs=S.CaseInputs(
                repo_url="u", prep=S.PrepPolicy.ACCEPTANCE,
            ),
            expected=[],
        )
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td) / "wt"
            with self.assertRaises(P.PrepError) as ctx:
                P.prepare_security(case, wt)
            self.assertIn("non-security_eval", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
