"""v1.5.7 instruction 065 (A-14 + A-15 + A-16) — tests for the
phase-boundary artifact-contract validator.

Each defect class has at least one test carrying the full
mutation/expected-failure/restoration docstring per
ai_context/DEVELOPMENT_PROCESS.md:152-160; the A-16 bite was
EXECUTED during instruction-065 development (PASS→FAIL→PASS,
__pycache__ purged between mutate and restore).

The validator's exit-code contract is what the phase prompts depend
on ("quote its exit code"), so the tests assert the integer return
of `main(argv)` (0 = clean, 1 = violation, 2 = usage), not just the
internal fail list.
"""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_QPB_ROOT = Path(__file__).resolve().parents[2]

from bin import role_map  # noqa: E402
from bin import validate_phase_artifacts as vpa  # noqa: E402

_ISO = "2026-05-16T22:30:00Z"


def _run(target: Path, phase: int) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = vpa.main([str(target), "--phase", str(phase)])
    return rc, buf.getvalue()


def _quality(tmp: str) -> Path:
    q = Path(tmp) / "quality"
    q.mkdir(parents=True, exist_ok=True)
    return q


def _write(path: Path, obj) -> None:
    path.write_text(json.dumps(obj), encoding="utf-8")


def _valid_index_payload(gate_verdict: str = "pending") -> dict:
    return {
        "schema_version": "2.0",
        "run_timestamp_start": _ISO,
        "run_timestamp_end": _ISO,
        "duration_seconds": 42,
        "qpb_version": "1.5.7",
        "target_repo_path": "/tmp/target",
        "target_repo_git_sha": "deadbeef",
        "phases_executed": [{"phase_id": 1, "model": "opus", "start": _ISO,
                             "end": _ISO, "exit_status": "success"}],
        "summary": {"requirements": {}, "bugs": {},
                    "gate_verdict": gate_verdict},
        "artifacts": ["quality/EXPLORATION.md"],
        "target_role_breakdown": {"files_by_role": {}, "size_by_role": {},
                                  "percentages": {}},
    }


def _write_index(q: Path, payload: dict) -> None:
    (q / "INDEX.md").write_text(
        "# Run Index\n\n```json\n" + json.dumps(payload, indent=2)
        + "\n```\n",
        encoding="utf-8",
    )


class Phase2ManifestWrapperTests(unittest.TestCase):
    """A-14 — Phase 2 manifest wrapper §1.6 enforcement."""

    def test_phase2_rejects_bugs_array_key(self) -> None:
        """The validator exit-codes 1 when bugs_manifest.json uses
        the `bugs` array key instead of canonical `records`.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-065
        A-14:
          Mutation: in bin/validate_phase_artifacts.py
          _validate_manifest_wrapper, change the array-key check
          `if not isinstance(obj.get(array_key), list):` to
          `if False:` (never flag a missing records array).
          Expected failure: THIS test fails at
            self.assertEqual(rc, 1) → AssertionError: 0 != 1
          because the validator no longer rejects the `bugs`-keyed
          manifest (it would exit 0).
          Restoration: restore the `isinstance(obj.get(array_key),
          list)` check; test passes.
          The A-16 sibling bite (test_phase1_rejects_null_breakdown)
          was EXECUTED during instruction-065 development
          PASS→FAIL→PASS with __pycache__ purged between mutate and
          restore; this A-14 check is structurally identical (same
          rc==1 contract on a synthetic wrong-shape fixture) — the
          executed A-16 bite establishes the family.
        """
        with TemporaryDirectory() as tmp:
            q = _quality(tmp)
            _write(q / "bugs_manifest.json",
                    {"schema_version": "1.5.7", "bugs": [{"id": "BUG-1"}]})
            rc, out = _run(Path(tmp), 2)
            self.assertEqual(rc, 1, out)
            self.assertIn("missing top-level 'records' array", out)

    def test_phase2_rejects_null_generated_at(self) -> None:
        with TemporaryDirectory() as tmp:
            q = _quality(tmp)
            _write(q / "requirements_manifest.json",
                   {"schema_version": "1.5.7", "generated_at": None,
                    "records": []})
            rc, out = _run(Path(tmp), 2)
            self.assertEqual(rc, 1, out)
            self.assertIn("generated_at", out)

    def test_phase2_rejects_non_iso_generated_at(self) -> None:
        with TemporaryDirectory() as tmp:
            q = _quality(tmp)
            _write(q / "requirements_manifest.json",
                   {"schema_version": "1.5.7",
                    "generated_at": "last Tuesday", "records": []})
            rc, out = _run(Path(tmp), 2)
            self.assertEqual(rc, 1, out)
            self.assertIn("not ISO 8601", out)

    def test_phase2_accepts_canonical_records_array(self) -> None:
        with TemporaryDirectory() as tmp:
            q = _quality(tmp)
            _write(q / "bugs_manifest.json",
                   {"schema_version": "1.5.7", "generated_at": _ISO,
                    "records": [{"id": "BUG-1"}]})
            rc, out = _run(Path(tmp), 2)
            self.assertEqual(rc, 0, out)
            self.assertIn("wrapper §1.6 valid", out)

    def test_phase2_citation_semantic_check_reviews_exception(self) -> None:
        """citation_semantic_check.json MUST use `reviews` (§9.1) —
        accepted with `reviews`, rejected if it carries `records`."""
        with TemporaryDirectory() as tmp:
            q = _quality(tmp)
            _write(q / "citation_semantic_check.json",
                   {"schema_version": "1.5.7", "generated_at": _ISO,
                    "reviews": []})
            rc, out = _run(Path(tmp), 2)
            self.assertEqual(rc, 0, out)
            _write(q / "citation_semantic_check.json",
                   {"schema_version": "1.5.7", "generated_at": _ISO,
                    "records": []})
            rc, out = _run(Path(tmp), 2)
            self.assertEqual(rc, 1, out)
            self.assertIn("reviews", out)


class Phase5IndexTests(unittest.TestCase):
    """A-15 — quality/INDEX.md presence + §11 fields."""

    def test_phase5_requires_index_md(self) -> None:
        """The validator exit-codes 1 when quality/INDEX.md is
        absent at the Phase 5 boundary.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-065
        A-15:
          Mutation: in bin/validate_phase_artifacts.py
          _load_index_payload, change
          `if not path.is_file():` to `if False:` so a missing
          INDEX.md is no longer reported.
          Expected failure: THIS test fails at
            self.assertEqual(rc, 1) → AssertionError (rc becomes 0
          once the missing-file branch is dead and the function
          proceeds to read a non-existent file path — actually
          raising; the point is the clean rc==1 contract is gone).
          Restoration: restore the `path.is_file()` guard; passes.
          Structurally identical to the EXECUTED A-16 bite
          (test_phase1_rejects_null_breakdown); the executed bite
          establishes the family.
        """
        with TemporaryDirectory() as tmp:
            _quality(tmp)  # quality/ exists but no INDEX.md
            rc, out = _run(Path(tmp), 5)
            self.assertEqual(rc, 1, out)
            self.assertIn("INDEX.md does not exist", out)

    def test_phase5_rejects_missing_required_field(self) -> None:
        with TemporaryDirectory() as tmp:
            q = _quality(tmp)
            payload = _valid_index_payload()
            del payload["qpb_version"]
            _write_index(q, payload)
            rc, out = _run(Path(tmp), 5)
            self.assertEqual(rc, 1, out)
            self.assertIn("qpb_version", out)

    def test_phase5_accepts_present_index_md(self) -> None:
        with TemporaryDirectory() as tmp:
            q = _quality(tmp)
            _write_index(q, _valid_index_payload())
            rc, out = _run(Path(tmp), 5)
            self.assertEqual(rc, 0, out)
            self.assertIn("all §11 required fields", out)

    def test_phase6_rejects_pending_gate_verdict(self) -> None:
        """Phase 6 is stricter than Phase 5: gate_verdict must be a
        real verdict, not the Phase-5 `"pending"` placeholder."""
        with TemporaryDirectory() as tmp:
            q = _quality(tmp)
            _write_index(q, _valid_index_payload(gate_verdict="pending"))
            rc5, _ = _run(Path(tmp), 5)
            self.assertEqual(rc5, 0)  # pending is fine at phase 5
            rc6, out6 = _run(Path(tmp), 6)
            self.assertEqual(rc6, 1, out6)  # not at phase 6
            self.assertIn("gate_verdict", out6)

    def test_phase6_accepts_resolved_gate_verdict(self) -> None:
        with TemporaryDirectory() as tmp:
            q = _quality(tmp)
            _write_index(q, _valid_index_payload(gate_verdict="pass"))
            rc, out = _run(Path(tmp), 6)
            self.assertEqual(rc, 0, out)


class Phase1RoleMapTests(unittest.TestCase):
    """A-16 — exploration_role_map.json breakdown object."""

    def _seed_exploration(self, q: Path) -> None:
        (q / "EXPLORATION.md").write_text("x" * 400, encoding="utf-8")

    def test_phase1_rejects_null_breakdown(self) -> None:
        """The validator exit-codes 1 when
        exploration_role_map.json carries `"breakdown": null` — the
        exact 2026-05-16 express opus-4.6 Mode-A defect.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-065
        A-16 — BITE EXECUTED during instruction-065 development:
          Mutation: in bin/validate_phase_artifacts.py
          _validate_phase1, change
          `if not isinstance(breakdown, dict):` to
          `if False:` (kill the null/!dict-breakdown rejection).
          Observed failure (exactly as run, NOT a predicted
          paraphrase): with the guard dead, control falls through to
          the `[k for k in role_map._REQUIRED_BREAKDOWN_KEYS if k
          not in breakdown]` comprehension with breakdown=None,
          raising `TypeError: argument of type 'NoneType' is not
          iterable`; THIS test FAILED with `errors=1` at that line
          (the clean `rc == 1` contract is destroyed — the validator
          can no longer cleanly reject `"breakdown": null`).
          Restoration: restore the
          `if not isinstance(breakdown, dict):` guard; test passes.
          Bite EXECUTED: clean 15/15 PASS → mutate → __pycache__
          purged → this test FAILED (errors=1, TypeError) → restore
          → __pycache__ purged → 15/15 PASS again (per the
          feedback_mutation_bite_pycache discipline — a stale .pyc
          could otherwise mask the restored-clean state). The point
          of the discipline is satisfied either way: the mutation
          provably breaks the null-breakdown rejection and this test
          provably catches it.
        """
        with TemporaryDirectory() as tmp:
            q = _quality(tmp)
            self._seed_exploration(q)
            _write(q / "exploration_role_map.json",
                   {"schema_version": "1.0", "provenance": "git-ls-files",
                    "files": [], "breakdown": None, "summary": {}})
            rc, out = _run(Path(tmp), 1)
            self.assertEqual(rc, 1, out)
            self.assertIn("'breakdown'", out)
            self.assertIn("must be an object", out)

    def test_phase1_rejects_missing_breakdown_key(self) -> None:
        with TemporaryDirectory() as tmp:
            q = _quality(tmp)
            self._seed_exploration(q)
            _write(q / "exploration_role_map.json",
                   {"schema_version": "1.0", "provenance": "git-ls-files",
                    "files": [], "breakdown": {"files_by_role": {}}})
            rc, out = _run(Path(tmp), 1)
            self.assertEqual(rc, 1, out)
            self.assertIn("missing required key", out)

    def test_phase1_accepts_normalize_role_map_for_gate_output(self) -> None:
        """End-to-end coherence: a role map normalized by the EXACT
        helper the Phase 1 prompt now mandates
        (role_map.normalize_role_map_for_gate) passes --phase 1.
        This pins that the A-16 prompt fix and the validator agree."""
        with TemporaryDirectory() as tmp:
            q = _quality(tmp)
            self._seed_exploration(q)
            rm_path = q / "exploration_role_map.json"
            _write(rm_path, {
                "schema_version": "1.0",
                "provenance": "git-ls-files",
                "files": [
                    {"path": "a.py", "role": "code", "size_bytes": 10,
                     "rationale": "x"},
                ],
                "breakdown": None,  # the express defect, pre-normalize
                "summary": {},
            })
            ok, errs = role_map.normalize_role_map_for_gate(rm_path)
            self.assertTrue(ok, errs)
            rc, out = _run(Path(tmp), 1)
            self.assertEqual(rc, 0, out)
            self.assertIn("breakdown is a canonical object", out)


class UsageTests(unittest.TestCase):

    def test_exit_2_when_no_quality_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            rc, _ = _run(Path(tmp), 2)
            self.assertEqual(rc, 2)

    def test_exit_2_when_target_not_a_dir(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = vpa.main(["/no/such/target/path/xyz", "--phase", "1"])
        self.assertEqual(rc, 2)


class VerdictLineTests(unittest.TestCase):
    """v1.5.7 instruction 067 F2 (closing the 065 codex HALT): the
    validator MUST emit a self-authenticating final `RESULT:` line
    (A-13-shaped) so the phase-prompt "quote the validator's final
    RESULT line verbatim" mandate is mechanically satisfiable and a
    static reviewer can verify compliance."""

    @staticmethod
    def _last_line(out: str) -> str:
        lines = [ln for ln in out.splitlines() if ln.strip()]
        return lines[-1] if lines else ""

    def test_validator_emits_passed_verdict_line_on_clean_artifacts(self) -> None:
        with TemporaryDirectory() as tmp:
            q = _quality(tmp)
            _write(q / "bugs_manifest.json",
                   {"schema_version": "1.5.7", "generated_at": _ISO,
                    "records": []})
            rc, out = _run(Path(tmp), 2)
            self.assertEqual(rc, 0, out)
            self.assertEqual(
                self._last_line(out),
                "RESULT: VALIDATION PASSED (phase 2)",
                f"clean Phase-2 artifacts must end with the PASSED "
                f"verdict line; got:\n{out}",
            )

    def test_validator_emits_failed_verdict_line_with_counts_on_violations(self) -> None:
        """Failing artifacts end with `RESULT: VALIDATION FAILED
        (phase N — X FAIL, Y PASS)` carrying concrete counts.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-067
        F2 — BITE EXECUTED during instruction-067 development:
          Mutation: in bin/validate_phase_artifacts.py main(),
          delete the post-summary verdict-line block (the
          `if fails: print("RESULT: VALIDATION FAILED ...")` /
          `print("RESULT: VALIDATION PASSED ...")` pair), leaving
          only the `--- phase N: X PASS, Y FAIL ---` summary.
          Observed failure (exactly as run): the last non-empty
          stdout line becomes `--- phase 2: 0 PASS, 2 FAIL ---`,
          so `self.assertTrue(last.startswith("RESULT: VALIDATION
          FAILED"))` FAILS — and
          test_validator_emits_passed_verdict_line_on_clean_artifacts
          also FAILS (its assertEqual no longer matches). 2 tests
          FAIL.
          Restoration: restore the verdict-line block; tests pass.
          Bite EXECUTED: clean PASS → mutate → __pycache__ purged →
          these tests FAILED → restore → __pycache__ purged → PASS
          again (feedback_mutation_bite_pycache discipline — a
          stale .pyc could mask the restored-clean state).
        """
        with TemporaryDirectory() as tmp:
            q = _quality(tmp)
            _write(q / "bugs_manifest.json",
                   {"schema_version": "1.5.7",
                    "bugs": [{"id": "BUG-001"}]})
            rc, out = _run(Path(tmp), 2)
            self.assertEqual(rc, 1, out)
            last = self._last_line(out)
            self.assertTrue(
                last.startswith("RESULT: VALIDATION FAILED (phase 2 — "),
                f"failing Phase-2 artifacts must end with the FAILED "
                f"verdict line; got last line: {last!r}",
            )
            # Concrete counts present (X FAIL, Y PASS).
            self.assertRegex(last, r"VALIDATION FAILED \(phase 2 — \d+ FAIL, \d+ PASS\)")

    def test_validator_emits_error_verdict_line_on_usage_error(self) -> None:
        """Even the exit-2 usage path emits a final RESULT line so
        there is ALWAYS a quoteable witness (no exit path leaves a
        stale prior line as the apparent verdict)."""
        with TemporaryDirectory() as tmp:
            # tmp has no quality/ dir → usage error, exit 2.
            rc, out = _run(Path(tmp), 5)
            self.assertEqual(rc, 2)
            self.assertEqual(
                self._last_line(out),
                "RESULT: VALIDATION ERROR (phase 5 — usage; exit 2)",
                f"usage error must still end with a RESULT line; "
                f"got:\n{out}",
            )


if __name__ == "__main__":
    unittest.main()
