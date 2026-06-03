"""Pipeline-activation tests — v1.5.4 Phase 2.

For each of the five fixture role-map shapes from the v1.5.4 Phase 1
brief, assert which downstream pipelines activate. The contract Phase 2
ships is the activation outcome — that the four-pass skill-derivation
pipeline, the code-review pipeline, and the prose-to-code divergence
check each turn on / off based on the role map alone.

Activation surfaces tested:

  - **Four-pass pipeline** — gated at ``bin.skill_derivation.__main__``
    by ``has_skill_prose(role_map)``.
  - **Code-review pipeline** — Phase 3 in ``bin.run_playbook``; gated
    by ``_code_review_should_skip(repo_dir)`` returning ``None``.
  - **Prose-to-code LLM divergence** — gated by ``has_skill_tools(role_map)``
    flipping ``ProseToCodeLLMConfig.should_run``.

Fixture shapes (from ``bin/tests/test_role_tagging.py``):

  1. **pdf-style** — skill-prose + skill-reference + skill-tool, no code.
     Four-pass: on. Code-review: off. Prose-to-code: on.
  2. **Pure-Markdown skill** — skill-prose only.
     Four-pass: on. Code-review: off. Prose-to-code: off.
  3. **Pure-code project** — code only.
     Four-pass: off. Code-review: on. Prose-to-code: off.
  4. **QPB-style** — skill-prose + skill-reference + code, no skill-tools.
     Four-pass: on. Code-review: on. Prose-to-code: off.
  5. **Pre-played benchmark** — target's intrinsic surface plus a
     ``playbook-output`` carry-over. Activation reflects the target's
     intrinsic surface only; ``playbook-output`` does not turn anything
     on or off.

Tests are deterministic: each writes a hand-built role map to a temp
directory and queries the activation predicates. No LLM is invoked —
the contract under test is "did the right pipelines flip on", not
"what did the pipeline emit when it ran".
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bin import role_map as rm
from bin import run_playbook
from bin.skill_derivation import divergence_prose_to_code_llm as p2c_llm


# ---------------------------------------------------------------------------
# Fixture builders.
# ---------------------------------------------------------------------------


def _entry(path: str, role: str, size: int, **extra) -> dict:
    rec = {
        "path": path,
        "role": role,
        "size_bytes": size,
        "rationale": f"fixture entry for {path}",
    }
    rec.update(extra)
    return rec


def _make_role_map(files: list[dict], *, provenance: str = "git-ls-files") -> dict:
    base = {
        "schema_version": rm.SCHEMA_VERSION,
        "timestamp_start": "2026-04-29T00:00:00Z",
        "provenance": provenance,
        "files": files,
        "breakdown": rm.compute_breakdown(files),
    }
    base["summary"] = rm.summarize_role_map(base)
    return base


def _write_role_map(repo_dir: Path, role_map: dict) -> Path:
    """Write the role map to ``<repo>/quality/exploration_role_map.json``
    so the on-disk consumers (Phase 3 skip predicate, the four-pass
    dispatch helper) can find it."""
    quality = repo_dir / "quality"
    quality.mkdir(parents=True, exist_ok=True)
    out = quality / "exploration_role_map.json"
    out.write_text(json.dumps(role_map), encoding="utf-8")
    return out


# Activation predicate trio captured as a triple so each test asserts a
# single tuple match instead of three separate calls. Order matches
# (four-pass, code-review, prose-to-code).
def _activations(role_map: dict, repo_dir: Path) -> tuple[bool, bool, bool]:
    _write_role_map(repo_dir, role_map)
    four_pass_on = rm.has_skill_prose(role_map)
    # Site 2 helper inverts has_code: returns None when code path
    # should run, returns a skip-reason string when it should no-op.
    code_review_on = run_playbook._code_review_should_skip(repo_dir) is None
    prose_to_code_on = rm.has_skill_tools(role_map)
    return four_pass_on, code_review_on, prose_to_code_on


# ---------------------------------------------------------------------------
# Fixture 1 — pdf-style (skill-prose + skill-reference + skill-tool, no code).
# ---------------------------------------------------------------------------


class PdfStylePipelineActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.role_map = _make_role_map([
            _entry("SKILL.md", "skill-prose", 6000),
            _entry("references/forms.md", "skill-reference", 2000),
            _entry(
                "scripts/extract_form_field_info.py",
                "skill-tool",
                500,
                skill_prose_reference="SKILL.md:47",
            ),
            _entry(
                "scripts/render_pdf.py",
                "skill-tool",
                500,
                skill_prose_reference="references/forms.md:20",
            ),
        ])

    def test_activation_outcome(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertEqual(
                _activations(self.role_map, Path(tmp)),
                (True, False, True),
                "pdf-style: four-pass + prose-to-code on; code-review off",
            )

    def test_prose_to_code_config_should_run_is_true(self) -> None:
        cfg = p2c_llm.ProseToCodeLLMConfig(
            formal_path=Path("/tmp/unused"),
            output_path=Path("/tmp/unused"),
            progress_path=Path("/tmp/unused"),
            repo_root=Path("/tmp/unused"),
            sections_path=Path("/tmp/unused"),
            pass_spec_path=Path("/tmp/unused"),
            should_run=rm.has_skill_tools(self.role_map),
        )
        self.assertTrue(cfg.should_run)


# ---------------------------------------------------------------------------
# Fixture 2 — pure-Markdown skill (only skill-prose).
# ---------------------------------------------------------------------------


class PureMarkdownPipelineActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.role_map = _make_role_map([
            _entry("SKILL.md", "skill-prose", 4000),
        ])

    def test_activation_outcome(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertEqual(
                _activations(self.role_map, Path(tmp)),
                (True, False, False),
                "pure-markdown: four-pass on; code-review + prose-to-code off",
            )


# ---------------------------------------------------------------------------
# Fixture 3 — pure-code project (no skill surface).
# ---------------------------------------------------------------------------


class PureCodePipelineActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.role_map = _make_role_map([
            _entry("router.go", "code", 12000),
            _entry("middleware.go", "code", 6000),
            _entry("router_test.go", "test", 4000),
            _entry("README.md", "docs", 1500),
        ])

    def test_activation_outcome(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertEqual(
                _activations(self.role_map, Path(tmp)),
                (False, True, False),
                "pure-code: code-review on; four-pass + prose-to-code off",
            )

    def test_skill_derivation_short_circuits_with_no_skill_prose(self) -> None:
        # The four-pass dispatch loads the role map to decide whether
        # to enter pass A/B/C/D. has_skill_prose=False is the same
        # signal _main uses to no-op early.
        self.assertFalse(rm.has_skill_prose(self.role_map))


# ---------------------------------------------------------------------------
# Fixture 4 — QPB-style (skill-prose + skill-reference + code, no skill-tools).
# ---------------------------------------------------------------------------


class QpbStylePipelineActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.role_map = _make_role_map([
            _entry("SKILL.md", "skill-prose", 8000),
            _entry("agents/code-reviewer.md", "skill-prose", 1200),
            _entry(
                "references/exploration_patterns.md",
                "skill-reference",
                3000,
            ),
            _entry("bin/run_playbook.py", "code", 90000),
            _entry("bin/archive_lib.py", "code", 24000),
            _entry("bin/tests/test_archive_lib.py", "test", 8000),
        ])

    def test_activation_outcome(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertEqual(
                _activations(self.role_map, Path(tmp)),
                (True, True, False),
                "QPB-style: four-pass + code-review on; prose-to-code off "
                "(no skill-tools — bin/*.py is code, not skill-tool)",
            )


# ---------------------------------------------------------------------------
# Fixture 5 — pre-played benchmark (intrinsic code + playbook-output carry-over).
# ---------------------------------------------------------------------------


class PrePlayedBenchmarkPipelineActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.role_map = _make_role_map([
            # Target's intrinsic surface — pure code.
            _entry("src/parser.py", "code", 3000),
            _entry("src/serializer.py", "code", 2000),
            # Prior playbook output. Must NOT toggle any pipeline on.
            _entry("quality/EXPLORATION.md", "playbook-output", 4000),
            _entry(".github/skills/quality_gate.py", "playbook-output", 50000),
        ])

    def test_activation_outcome(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertEqual(
                _activations(self.role_map, Path(tmp)),
                (False, True, False),
                "pre-played benchmark: code-review on (intrinsic code); "
                "playbook-output does not activate skill or tool paths",
            )

    def test_playbook_output_only_target_activates_nothing(self) -> None:
        playbook_only = _make_role_map([
            _entry("quality/EXPLORATION.md", "playbook-output", 4000),
            _entry(".github/skills/quality_gate.py", "playbook-output", 50000),
        ])
        with TemporaryDirectory() as tmp:
            self.assertEqual(
                _activations(playbook_only, Path(tmp)),
                (False, False, False),
                "playbook-output only: every pipeline no-ops",
            )


# ---------------------------------------------------------------------------
# Site 2 — Phase 3 skip-predicate behavior on edge cases.
# ---------------------------------------------------------------------------


class CodeReviewSkipPredicateTests(unittest.TestCase):
    """v1.5.4 Phase 2 Site 2: ``_code_review_should_skip`` returns
    ``None`` (Phase 3 runs) when the role map is absent or unparsable.
    Pre-Phase-1 invocations and pre-iteration targets keep the v1.5.3
    behaviour — Phase 3 runs as before. A present-and-valid role map
    with zero ``code`` files returns a skip-reason string."""

    def test_no_role_map_returns_none(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertIsNone(
                run_playbook._code_review_should_skip(Path(tmp))
            )

    def test_unparsable_role_map_returns_none(self) -> None:
        with TemporaryDirectory() as tmp:
            quality = Path(tmp) / "quality"
            quality.mkdir()
            (quality / "exploration_role_map.json").write_text(
                "{ not json", encoding="utf-8"
            )
            self.assertIsNone(
                run_playbook._code_review_should_skip(Path(tmp))
            )

    def test_role_map_with_code_returns_none(self) -> None:
        rmap = _make_role_map([_entry("src/main.py", "code", 100)])
        with TemporaryDirectory() as tmp:
            _write_role_map(Path(tmp), rmap)
            self.assertIsNone(
                run_playbook._code_review_should_skip(Path(tmp))
            )

    def test_role_map_without_code_returns_skip_reason(self) -> None:
        rmap = _make_role_map([_entry("SKILL.md", "skill-prose", 1000)])
        with TemporaryDirectory() as tmp:
            _write_role_map(Path(tmp), rmap)
            reason = run_playbook._code_review_should_skip(Path(tmp))
            self.assertIsNotNone(reason)
            self.assertIn("Phase 3", reason)
            self.assertIn("zero", reason)


# ---------------------------------------------------------------------------
# Site 3 — prose-to-code LLM no-op contract.
# ---------------------------------------------------------------------------


class ProseToCodeLLMActivationTests(unittest.TestCase):
    """v1.5.4 Phase 2 Site 3: ``run_divergence_prose_to_code_llm``
    no-ops cleanly when ``config.should_run`` is False, irrespective
    of what the LLM runner would return. The skipped_reason must
    explicitly name skill-tool so operators can trace the gate."""

    def _make_config(self, *, should_run: bool) -> p2c_llm.ProseToCodeLLMConfig:
        return p2c_llm.ProseToCodeLLMConfig(
            formal_path=Path("/tmp/unused"),
            output_path=Path("/tmp/unused"),
            progress_path=Path("/tmp/unused"),
            repo_root=Path("/tmp/unused"),
            sections_path=Path("/tmp/unused"),
            pass_spec_path=Path("/tmp/unused"),
            should_run=should_run,
        )

    def test_should_run_false_short_circuits_with_skill_tool_reason(self) -> None:
        cfg = self._make_config(should_run=False)

        class _FailingRunner:
            def run(self, prompt):  # noqa: D401, ANN001
                raise AssertionError(
                    "runner.run must NOT be invoked when should_run is False"
                )

        result = p2c_llm.run_divergence_prose_to_code_llm(
            cfg, _FailingRunner()
        )
        self.assertEqual(result["calls_made"], 0)
        self.assertEqual(result["divergences_emitted"], 0)
        self.assertIn("skill-tool", result["skipped_reason"])


class _StubArgs:
    """Lightweight argparse.Namespace stand-in for run_one_phase tests.
    Only the attributes run_one_phase / build_phase_prompt actually
    read need to exist."""

    def __init__(self, **kwargs) -> None:
        # Defaults that satisfy run_one_phase + build_phase_prompt.
        self.no_seeds = False
        self.runner = "claude"
        self.model = None
        self.iterations = None
        self.phase_groups = None
        self.pace_seconds = 0
        self.full_run = False
        self.no_formal_docs = False
        self.no_stdout_echo = True
        self.verbose = False
        self.quiet = True
        self.progress_interval = 2
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# Site 1 — mock-based integration tests (Round 4 finding B2 closure).
# These confirm Pass A's run function is actually invoked / not invoked
# based on the role-map activation predicate, not just that the
# predicate returned True/False.
# ---------------------------------------------------------------------------


class Site1PassAInvocationTests(unittest.TestCase):
    """v1.5.4 Phase 2.1 — pin actual Pass A invocation against the role
    map so a regression that drops the activation guard fails the
    test, not just changes the predicate."""

    def _write_skill_md(self, repo_dir: Path) -> None:
        (repo_dir / "SKILL.md").write_text(
            "# Skill\n\n## Phase 1\nbody\n", encoding="utf-8"
        )

    def test_pure_code_target_skips_pass_a(self) -> None:
        from unittest import mock
        from bin.skill_derivation import __main__ as sd_main
        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp)
            role_map = _make_role_map([
                _entry("src/main.go", "code", 100),
            ])
            _write_role_map(repo_dir, role_map)
            with mock.patch.object(sd_main, "_run_pass_a") as ma, \
                 mock.patch.object(sd_main, "_run_pass_b") as mb, \
                 mock.patch.object(sd_main, "_run_pass_c") as mc, \
                 mock.patch.object(sd_main, "_run_pass_d") as md:
                exit_code = sd_main._main([str(repo_dir), "--pass", "all"])
            self.assertEqual(exit_code, 0)
            ma.assert_not_called()
            mb.assert_not_called()
            mc.assert_not_called()
            md.assert_not_called()

    def test_pdf_style_target_invokes_pass_a_with_role_map_files(self) -> None:
        """The role map enumerates SKILL.md + FORMS.md + REFERENCE.md
        at the repo root (no `references/` directory). Pass A's
        section enumerator must walk those role-map-tagged files
        rather than the conventional `references/*.md` glob.

        The test patches sections.enumerate_skill_and_references to
        capture its kwargs, runs the orchestrator's _main with
        --pass A so _enumerate_for_pass_a fires, and asserts the
        captured role_map_files list contains the tagged surface
        without the un-tagged one."""
        from unittest import mock
        from bin.skill_derivation import __main__ as sd_main
        from bin.skill_derivation import sections as sd_sections
        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp)
            self._write_skill_md(repo_dir)
            (repo_dir / "FORMS.md").write_text(
                "# Forms\n\n## Form intro\nbody\n", encoding="utf-8"
            )
            (repo_dir / "REFERENCE.md").write_text(
                "# Reference\n\n## Ref intro\nbody\n", encoding="utf-8"
            )
            (repo_dir / "NOT_TAGGED.md").write_text(
                "# Untagged\n\n## body\n", encoding="utf-8"
            )
            role_map = _make_role_map([
                _entry("SKILL.md", "skill-prose", 200),
                _entry("FORMS.md", "skill-reference", 100),
                _entry("REFERENCE.md", "skill-reference", 100),
            ])
            _write_role_map(repo_dir, role_map)

            captured: dict = {"role_map_files": None}

            def _capture_enum(skill_md, refs, repo_root, *, role_map_files=None):
                captured["role_map_files"] = role_map_files
                return []

            # Let _run_pass_a invoke _enumerate_for_pass_a (which is
            # the function under test) but block both
            # enumerate_skill_and_references' real work and the
            # downstream LLM call inside pass_a.run_pass_a so the test
            # stays deterministic and offline.
            with mock.patch.object(
                sd_sections, "enumerate_skill_and_references", _capture_enum
            ), mock.patch(
                "bin.skill_derivation.pass_a.run_pass_a", return_value=0
            ) as mock_pass_a:
                exit_code = sd_main._main([str(repo_dir), "--pass", "A"])
            self.assertEqual(exit_code, 0)
            mock_pass_a.assert_called_once()
            self.assertIsNotNone(captured["role_map_files"])
            tagged = {p.name for p in captured["role_map_files"]}
            # FORMS.md and REFERENCE.md must be in the role-map list
            # (SKILL.md is also tagged but is enumerated first via the
            # skill_md_path argument; either inclusion is acceptable as
            # the helper de-duplicates).
            self.assertIn("FORMS.md", tagged)
            self.assertIn("REFERENCE.md", tagged)
            self.assertNotIn("NOT_TAGGED.md", tagged)


# ---------------------------------------------------------------------------
# Site 2 — mock-based integration tests for Phase 3 invocation.
# ---------------------------------------------------------------------------


class Site2CodeReviewInvocationTests(unittest.TestCase):
    """Pin actual run_prompt invocation when Phase 3 runs / doesn't
    run, not just the predicate."""

    def _make_args(self) -> _StubArgs:
        return _StubArgs()

    def _phase3_log(self, repo_dir: Path) -> Path:
        return repo_dir / "phase3.log"

    def test_pure_skill_target_skips_phase_3_runner(self) -> None:
        from unittest import mock
        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp)
            quality = repo_dir / "quality"
            quality.mkdir()
            # Phase 3 gate prerequisites — these allow the gate to
            # pass; the role-map skip then short-circuits the LLM.
            for name in (
                "REQUIREMENTS.md", "QUALITY.md", "CONTRACTS.md",
                "RUN_CODE_REVIEW.md", "COVERAGE_MATRIX.md",
                "COMPLETENESS_REPORT.md", "RUN_INTEGRATION_TESTS.md",
                "RUN_SPEC_AUDIT.md", "RUN_TDD_TESTS.md",
            ):
                (quality / name).write_text("ok", encoding="utf-8")
            _write_role_map(repo_dir, _make_role_map([
                _entry("SKILL.md", "skill-prose", 1000),
            ]))
            with mock.patch.object(run_playbook, "run_prompt") as mp:
                ok = run_playbook.run_one_phase(
                    repo_dir, "3", ["3"], self._make_args(),
                    self._phase3_log(repo_dir), "20260429T000000Z",
                )
            self.assertTrue(ok)
            mp.assert_not_called()

    def test_mixed_target_invokes_phase_3_runner(self) -> None:
        """When the role map carries code files, run_prompt must be
        called — confirms the skip predicate isn't over-firing."""
        from unittest import mock
        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp)
            quality = repo_dir / "quality"
            quality.mkdir()
            for name in (
                "REQUIREMENTS.md", "QUALITY.md", "CONTRACTS.md",
                "RUN_CODE_REVIEW.md", "COVERAGE_MATRIX.md",
                "COMPLETENESS_REPORT.md", "RUN_INTEGRATION_TESTS.md",
                "RUN_SPEC_AUDIT.md", "RUN_TDD_TESTS.md",
            ):
                (quality / name).write_text("ok", encoding="utf-8")
            _write_role_map(repo_dir, _make_role_map([
                _entry("SKILL.md", "skill-prose", 1000),
                _entry("bin/main.py", "code", 500),
            ]))
            with mock.patch.object(
                run_playbook, "run_prompt", return_value=0
            ) as mp, mock.patch.object(run_playbook, "_log_phase_completion"):
                ok = run_playbook.run_one_phase(
                    repo_dir, "3", ["3"], self._make_args(),
                    self._phase3_log(repo_dir), "20260429T000000Z",
                )
            self.assertTrue(ok)
            mp.assert_called_once()


class Phase5SkippedReconciliationTests(unittest.TestCase):
    """v1.5.4 Phase 2.1 (Round 4 finding A3): when Site 2 skips
    Phase 3 on a no-code target, the Phase-3-skipped sentinel
    suppresses the Phase 4 / Phase 5 gate WARNs about missing
    code_reviews/ and BUGS.md."""

    def _quality(self, repo_dir: Path) -> Path:
        q = repo_dir / "quality"
        q.mkdir(parents=True, exist_ok=True)
        return q

    def test_phase3_skip_drops_sentinel_under_quality(self) -> None:
        """run_one_phase for Phase 3 against a no-code role map
        creates the sentinel; Phase 4 and Phase 5 gates read it."""
        from unittest import mock
        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp)
            q = self._quality(repo_dir)
            for name in (
                "REQUIREMENTS.md", "QUALITY.md", "CONTRACTS.md",
                "RUN_CODE_REVIEW.md", "COVERAGE_MATRIX.md",
                "COMPLETENESS_REPORT.md", "RUN_INTEGRATION_TESTS.md",
                "RUN_SPEC_AUDIT.md", "RUN_TDD_TESTS.md",
            ):
                (q / name).write_text("ok", encoding="utf-8")
            _write_role_map(repo_dir, _make_role_map([
                _entry("SKILL.md", "skill-prose", 1000),
            ]))
            with mock.patch.object(run_playbook, "run_prompt"):
                run_playbook.run_one_phase(
                    repo_dir, "3", ["3"], _StubArgs(),
                    repo_dir / "phase3.log", "20260429T000000Z",
                )
            self.assertTrue(
                run_playbook._phase3_skipped_sentinel(repo_dir).is_file(),
                "Phase 3 skip path must drop the sentinel",
            )

    def test_phase5_gate_suppresses_bugs_md_warn_on_no_code_target(self) -> None:
        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp)
            q = self._quality(repo_dir)
            (q / "PROGRESS.md").write_text(
                "- [x] Phase 4\n", encoding="utf-8"
            )
            sa = q / "spec_audits"
            sa.mkdir()
            (sa / "20260429-triage.md").write_text("ok", encoding="utf-8")
            (sa / "20260429-auditor-1.md").write_text("ok", encoding="utf-8")
            # No BUGS.md — but the sentinel says Phase 3 was correctly
            # skipped on a no-code target.
            run_playbook._phase3_skipped_sentinel(repo_dir).write_text(
                "skipped\n", encoding="utf-8"
            )
            gate = run_playbook.check_phase_gate(repo_dir, "5")
            self.assertTrue(gate.ok)
            joined = "\n".join(gate.messages)
            self.assertNotIn("no BUGS.md", joined)

    def test_phase5_gate_still_warns_when_sentinel_absent(self) -> None:
        """Negative control: without the sentinel, the gate must still
        WARN about missing BUGS.md so a genuinely-skipped Phase 3 on
        a code target is still surfaced."""
        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp)
            q = self._quality(repo_dir)
            (q / "PROGRESS.md").write_text(
                "- [x] Phase 4\n", encoding="utf-8"
            )
            sa = q / "spec_audits"
            sa.mkdir()
            (sa / "20260429-triage.md").write_text("ok", encoding="utf-8")
            (sa / "20260429-auditor-1.md").write_text("ok", encoding="utf-8")
            gate = run_playbook.check_phase_gate(repo_dir, "5")
            self.assertTrue(gate.ok)
            joined = "\n".join(gate.messages)
            self.assertIn("no BUGS.md", joined)

    def test_phase4_gate_suppresses_code_reviews_warn_on_no_code_target(
        self,
    ) -> None:
        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp)
            q = self._quality(repo_dir)
            (q / "REQUIREMENTS.md").write_text("ok", encoding="utf-8")
            (q / "RUN_SPEC_AUDIT.md").write_text("ok", encoding="utf-8")
            run_playbook._phase3_skipped_sentinel(repo_dir).write_text(
                "skipped\n", encoding="utf-8"
            )
            gate = run_playbook.check_phase_gate(repo_dir, "4")
            self.assertTrue(gate.ok)
            joined = "\n".join(gate.messages)
            self.assertNotIn("no code_reviews/", joined)


class MultiPhaseGroupCodeReviewSkipTests(unittest.TestCase):
    """v1.5.4 Phase 2.1 (Round 4 polish): when a multi-phase group
    such as `2+3` lands on a no-code target, run_one_phase_group drops
    Phase 3 BEFORE building the combined prompt and writes the
    Phase-3-skipped sentinel."""

    def test_filter_group_drops_phase_3_when_no_code(self) -> None:
        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp)
            _write_role_map(repo_dir, _make_role_map([
                _entry("SKILL.md", "skill-prose", 1000),
            ]))
            filtered, reason = run_playbook._filter_group_for_code_review_skip(
                repo_dir, ["2", "3", "4"]
            )
            self.assertEqual(filtered, ["2", "4"])
            self.assertIsNotNone(reason)
            self.assertIn("Phase 3", reason)

    def test_filter_group_preserves_when_code_present(self) -> None:
        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp)
            _write_role_map(repo_dir, _make_role_map([
                _entry("SKILL.md", "skill-prose", 1000),
                _entry("bin/x.py", "code", 500),
            ]))
            filtered, reason = run_playbook._filter_group_for_code_review_skip(
                repo_dir, ["2", "3", "4"]
            )
            self.assertEqual(filtered, ["2", "3", "4"])
            self.assertIsNone(reason)

    def test_filter_group_no_phase_3_is_passthrough(self) -> None:
        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp)
            _write_role_map(repo_dir, _make_role_map([
                _entry("SKILL.md", "skill-prose", 1000),
            ]))
            filtered, reason = run_playbook._filter_group_for_code_review_skip(
                repo_dir, ["4", "5"]
            )
            self.assertEqual(filtered, ["4", "5"])
            self.assertIsNone(reason)


class SentinelLifecycleTests(unittest.TestCase):
    """v1.5.4 Phase 2.2 (Round 5 Panel B2): the
    quality/.phase3-skipped-no-code-files sentinel is written when
    Phase 3 skips. It MUST be removed when Phase 3 subsequently runs
    against an updated role map that has code, otherwise downstream
    Phase 4 / 5 gates silently suppress their WARNs against this
    session's real artifacts."""

    def _seed_phase3_prereqs(self, repo_dir: Path) -> Path:
        q = repo_dir / "quality"
        q.mkdir(parents=True, exist_ok=True)
        for name in (
            "REQUIREMENTS.md", "QUALITY.md", "CONTRACTS.md",
            "RUN_CODE_REVIEW.md", "COVERAGE_MATRIX.md",
            "COMPLETENESS_REPORT.md", "RUN_INTEGRATION_TESTS.md",
            "RUN_SPEC_AUDIT.md", "RUN_TDD_TESTS.md",
        ):
            (q / name).write_text("ok", encoding="utf-8")
        return q

    def _write_stale_sentinel(self, repo_dir: Path) -> Path:
        sentinel = run_playbook._phase3_skipped_sentinel(repo_dir)
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text(
            "Phase 3 skipped (stale from prior run)\n", encoding="utf-8"
        )
        return sentinel

    def test_phase3_run_removes_stale_sentinel_in_run_one_phase(self) -> None:
        from unittest import mock
        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp)
            self._seed_phase3_prereqs(repo_dir)
            sentinel = self._write_stale_sentinel(repo_dir)
            self.assertTrue(sentinel.exists())
            # Role map carries code surface, so Phase 3 must run, not skip.
            _write_role_map(repo_dir, _make_role_map([
                _entry("SKILL.md", "skill-prose", 1000),
                _entry("bin/main.py", "code", 500),
            ]))
            with mock.patch.object(
                run_playbook, "run_prompt", return_value=0
            ), mock.patch.object(run_playbook, "_log_phase_completion"):
                ok = run_playbook.run_one_phase(
                    repo_dir, "3", ["3"], _StubArgs(),
                    repo_dir / "phase3.log", "20260429T000000Z",
                )
            self.assertTrue(ok)
            self.assertFalse(
                sentinel.exists(),
                "run_one_phase must remove the stale sentinel before "
                "Phase 3's LLM invocation",
            )

    def test_phase3_run_removes_stale_sentinel_in_run_one_phase_group(
        self,
    ) -> None:
        """The multi-phase group path lands here when --phase-groups
        wires Phase 3 alongside another phase (e.g. '2+3'). The
        cleanup must fire on this path too."""
        from unittest import mock
        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp)
            self._seed_phase3_prereqs(repo_dir)
            sentinel = self._write_stale_sentinel(repo_dir)
            self.assertTrue(sentinel.exists())
            _write_role_map(repo_dir, _make_role_map([
                _entry("SKILL.md", "skill-prose", 1000),
                _entry("bin/main.py", "code", 500),
            ]))
            monitor = mock.MagicMock()
            with mock.patch.object(
                run_playbook, "run_prompt", return_value=0
            ), mock.patch.object(run_playbook, "_log_phase_completion"):
                ok = run_playbook.run_one_phase_group(
                    repo_dir, ["3", "4"], [["3", "4"]], _StubArgs(),
                    repo_dir / "phase34.log",
                    "20260429T000000Z",
                    monitor,
                )
            self.assertTrue(ok)
            self.assertFalse(
                sentinel.exists(),
                "run_one_phase_group must remove the stale sentinel "
                "when Phase 3 survives the filter and the LLM runs",
            )

    def test_stale_sentinel_does_not_suppress_phase5_warn_after_phase3_run(
        self,
    ) -> None:
        """Regression pin for Round 5 Panel B2 finding.

        Reproduces the operator-impact scenario:
          1. Prior run: no-code role map → Phase 3 skipped → sentinel written.
          2. Role map updated to include code (operator added code).
          3. Phase 3 runs successfully (this iteration, mocked LLM).
          4. BUGS.md is genuinely missing (the mocked LLM didn't write one).
          5. Phase 5 gate runs.

        Without the cleanup, the stale sentinel from step 1 silently
        suppresses the BUGS.md WARN at step 5 and the operator
        advances through Phase 5 with no warning. With the cleanup,
        the sentinel is removed at step 3 and the gate WARNs
        correctly at step 5."""
        from unittest import mock
        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp)
            self._seed_phase3_prereqs(repo_dir)
            self._write_stale_sentinel(repo_dir)
            _write_role_map(repo_dir, _make_role_map([
                _entry("SKILL.md", "skill-prose", 1000),
                _entry("bin/main.py", "code", 500),
            ]))
            with mock.patch.object(
                run_playbook, "run_prompt", return_value=0
            ), mock.patch.object(run_playbook, "_log_phase_completion"):
                run_playbook.run_one_phase(
                    repo_dir, "3", ["3"], _StubArgs(),
                    repo_dir / "phase3.log", "20260429T000000Z",
                )
            # Set up the rest of Phase 5 gate's prerequisites so the
            # only remaining variable is BUGS.md presence.
            q = repo_dir / "quality"
            (q / "PROGRESS.md").write_text(
                "- [x] Phase 4\n", encoding="utf-8"
            )
            sa = q / "spec_audits"
            sa.mkdir()
            (sa / "20260429-triage.md").write_text("ok", encoding="utf-8")
            (sa / "20260429-auditor-1.md").write_text("ok", encoding="utf-8")
            # BUGS.md is deliberately missing — the mocked LLM never
            # wrote one. The Phase 5 gate must surface that.
            gate = run_playbook.check_phase_gate(repo_dir, "5")
            self.assertTrue(gate.ok)
            joined = "\n".join(gate.messages)
            self.assertIn(
                "no BUGS.md",
                joined,
                "Phase 5 gate must WARN about missing BUGS.md once "
                "the stale sentinel is removed; otherwise operators "
                "advance silently through a broken run.",
            )


class B1F4UnexpectedRoleDiagnosticTests(unittest.TestCase):
    """v1.5.4 Phase 3 Stage 3 (Round 5 finding B1-F4): files tagged
    with a role outside the Pass A input set (skill-prose,
    skill-reference) are silently dropped from enumeration. That's
    the right runtime behaviour, but operators who tagged something
    `docs` and expected Pass A to read it deserve a signal. Each
    excluded file logs a single `[role-map] note:` line on stderr."""

    def test_unexpected_roles_are_excluded_and_logged(self) -> None:
        from contextlib import redirect_stderr
        from io import StringIO
        from bin.skill_derivation import __main__ as sd_main
        with TemporaryDirectory() as tmp:
            target_dir = Path(tmp)
            role_map = _make_role_map([
                _entry("SKILL.md", "skill-prose", 1000),
                _entry("references/exp.md", "skill-reference", 500),
                _entry("docs/design.md", "docs", 800),
                _entry("config.toml", "config", 100),
                _entry("bin/main.py", "code", 5000),
            ])
            buf = StringIO()
            with redirect_stderr(buf):
                files = sd_main._role_map_skill_prose_files(role_map, target_dir)
            stderr = buf.getvalue()
            # Result list excludes docs / config / code.
            names = {p.name for p in files}
            self.assertEqual(names, {"SKILL.md", "exp.md"})
            # Diagnostics name each excluded file + its role.
            self.assertIn("docs/design.md", stderr)
            self.assertIn("'docs'", stderr)
            self.assertIn("config.toml", stderr)
            self.assertIn("'config'", stderr)
            self.assertIn("bin/main.py", stderr)
            self.assertIn("'code'", stderr)
            # Every diagnostic line carries the [role-map] tag.
            note_lines = [
                ln for ln in stderr.splitlines() if "[role-map]" in ln
            ]
            self.assertEqual(
                len(note_lines), 3,
                f"expected 3 [role-map] note lines (docs, config, code); "
                f"got {len(note_lines)}: {note_lines}",
            )

    def test_no_diagnostic_when_only_skill_inputs_present(self) -> None:
        from contextlib import redirect_stderr
        from io import StringIO
        from bin.skill_derivation import __main__ as sd_main
        with TemporaryDirectory() as tmp:
            role_map = _make_role_map([
                _entry("SKILL.md", "skill-prose", 1000),
                _entry("references/exp.md", "skill-reference", 500),
            ])
            buf = StringIO()
            with redirect_stderr(buf):
                sd_main._role_map_skill_prose_files(role_map, Path(tmp))
            self.assertNotIn("[role-map]", buf.getvalue())


class B1F6RoleMapFilesRoutingTests(unittest.TestCase):
    """v1.5.4 Phase 3 Stage 3 (Round 5 finding B1-F6): pin the
    asymmetric routing of ``role_map_files``. ``None`` falls back to
    the v1.5.3 hardcoded SKILL.md + references/*.md walk; ``[]``
    returns an empty section list deterministically. The activation
    predicate normally guards the empty case before Pass A reaches
    here, but the asymmetry is intentional for direct callers."""

    def _make_skill_repo(self, repo_dir: Path) -> Path:
        (repo_dir / "SKILL.md").write_text(
            "# Skill\n\n## P1\nbody\n", encoding="utf-8"
        )
        refs_dir = repo_dir / "references"
        refs_dir.mkdir()
        (refs_dir / "exp.md").write_text(
            "# Exp\n\n## E1\nbody\n", encoding="utf-8"
        )
        return repo_dir

    def test_enumerate_with_none_uses_v1_5_3_fallback(self) -> None:
        from bin.skill_derivation import sections as sd_sections
        with TemporaryDirectory() as tmp:
            repo_dir = self._make_skill_repo(Path(tmp))
            secs = sd_sections.enumerate_skill_and_references(
                repo_dir / "SKILL.md",
                repo_dir / "references",
                repo_dir,
                role_map_files=None,
            )
            docs = sorted({s.document for s in secs})
            # SKILL.md + references/exp.md (relative path may render as
            # "references/exp.md"; test tolerates either form).
            self.assertIn("SKILL.md", docs)
            self.assertTrue(
                any("exp.md" in d for d in docs),
                f"expected exp.md in fallback enumeration, got {docs}",
            )

    def test_enumerate_with_empty_list_returns_empty(self) -> None:
        from bin.skill_derivation import sections as sd_sections
        with TemporaryDirectory() as tmp:
            repo_dir = self._make_skill_repo(Path(tmp))
            secs = sd_sections.enumerate_skill_and_references(
                repo_dir / "SKILL.md",
                repo_dir / "references",
                repo_dir,
                role_map_files=[],
            )
            self.assertEqual(
                secs, [],
                "empty role_map_files must produce empty enumeration; "
                "the v1.5.3 fallback must NOT fire on []",
            )


class B3F2MultiPhaseCounterTests(unittest.TestCase):
    """v1.5.4 Phase 3 Stage 3 (Round 5 finding B3-F2): when a
    multi-phase group like ['2','3'] collapses to ['2'] because
    Phase 3 was filtered on a no-code target, the operator-facing
    X/Y counter must reflect the post-filter size, not the
    pre-filter one."""

    def _seed_phase2_prereqs(self, repo_dir: Path) -> Path:
        q = repo_dir / "quality"
        q.mkdir(parents=True, exist_ok=True)
        (q / "EXPLORATION.md").write_text("x\n" * 200, encoding="utf-8")
        return q

    def test_collapsed_group_shows_post_filter_counter(self) -> None:
        """A 2+3 group on a no-code target collapses to just Phase 2.
        The X/Y counter must read 1/1, not 1/2."""
        from unittest import mock
        from io import StringIO
        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp)
            self._seed_phase2_prereqs(repo_dir)
            _write_role_map(repo_dir, _make_role_map([
                _entry("SKILL.md", "skill-prose", 1000),
            ]))
            captured: list[str] = []

            def _fake_log(msg):
                captured.append(msg)
                return msg

            def _fake_logboth(_log_file, msg):
                # logboth's second arg is what was logged; record it.
                if isinstance(msg, str):
                    captured.append(msg)

            monitor = mock.MagicMock()
            with mock.patch.object(
                run_playbook.lib, "log", side_effect=_fake_log
            ), mock.patch.object(
                run_playbook.lib, "logboth", side_effect=_fake_logboth
            ), mock.patch.object(
                run_playbook, "run_prompt", return_value=0
            ), mock.patch.object(run_playbook, "_log_phase_completion"):
                ok = run_playbook.run_one_phase_group(
                    repo_dir, ["2", "3"], [["2", "3"]], _StubArgs(),
                    repo_dir / "phase23.log",
                    "20260429T000000Z",
                    monitor,
                )
            self.assertTrue(ok)
            joined = "\n".join(captured)
            self.assertIn(
                "Phase 1/1",
                joined,
                f"expected post-filter counter 'Phase 1/1' (only Phase 2 "
                f"survived the no-code filter); got log:\n{joined}",
            )
            self.assertNotIn(
                "Phase 1/2",
                joined,
                "pre-filter counter 'Phase 1/2' must not appear once the "
                "no-code filter has collapsed the group",
            )

    def test_uncollapsed_group_keeps_full_counter(self) -> None:
        """Negative control: when no filter applies (target HAS code),
        the X/Y counter stays at the pre-filter total. Confirms the
        fix doesn't shrink the counter unconditionally."""
        from unittest import mock
        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp)
            self._seed_phase2_prereqs(repo_dir)
            _write_role_map(repo_dir, _make_role_map([
                _entry("SKILL.md", "skill-prose", 1000),
                _entry("bin/main.py", "code", 500),
            ]))
            captured: list[str] = []

            def _fake_logboth(_log_file, msg):
                if isinstance(msg, str):
                    captured.append(msg)

            monitor = mock.MagicMock()
            # Single-phase invocation so we still hit the X/Y counter
            # path, but with no filter dropping anything.
            with mock.patch.object(
                run_playbook.lib, "logboth", side_effect=_fake_logboth
            ), mock.patch.object(
                run_playbook, "run_prompt", return_value=0
            ), mock.patch.object(run_playbook, "_log_phase_completion"):
                run_playbook.run_one_phase_group(
                    repo_dir, ["2"], [["2", "3"]], _StubArgs(),
                    repo_dir / "phase2.log",
                    "20260429T000000Z",
                    monitor,
                )
            joined = "\n".join(captured)
            self.assertIn(
                "Phase 1/2",
                joined,
                f"target has code → no filter → counter must show full "
                f"'Phase 1/2'; got log:\n{joined}",
            )


if __name__ == "__main__":
    unittest.main()
