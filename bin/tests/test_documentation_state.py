"""Tests for v1.5.6 P3 code-only-mode downgrade.

When `reference_docs/` (and `reference_docs/cite/`) carry no recognized
plaintext content, the playbook proceeds in code-only mode rather than
silently producing a low-quality run. The downgrade is observable via:

  - a `documentation_state` event in `quality/run_state.jsonl`
  - an opening section in `quality/EXPLORATION.md`
  - a "Documentation state: code_only" line in `quality/PROGRESS.md`

These tests exercise the helpers directly (no LLM invocation) plus a
static guard confirming `run_one_phase` calls them at phase=="1".
"""

from __future__ import annotations

import inspect
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bin import run_playbook


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class EvaluateDocumentationStateTests(unittest.TestCase):
    """`_evaluate_documentation_state` returns 'code_only' iff the
    reference_docs/ tree carries no recognized plaintext content."""

    def test_empty_reference_docs_triggers_downgrade(self) -> None:
        """Absent reference_docs/ → code_only."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            self.assertEqual(
                run_playbook._evaluate_documentation_state(tmp), "code_only"
            )

    def test_empty_reference_docs_dir_triggers_downgrade(self) -> None:
        """Present but empty reference_docs/ → code_only."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            (tmp / "reference_docs").mkdir()
            self.assertEqual(
                run_playbook._evaluate_documentation_state(tmp), "code_only"
            )

    def test_populated_reference_docs_no_downgrade(self) -> None:
        """A real .md file in reference_docs/ → with_docs."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            refs = tmp / "reference_docs"
            refs.mkdir()
            (refs / "design.md").write_text(
                "# Design notes\nReal content.\n", encoding="utf-8"
            )
            self.assertEqual(
                run_playbook._evaluate_documentation_state(tmp), "with_docs"
            )

    def test_cite_subfolder_with_content_counts(self) -> None:
        """Empty top-level reference_docs/ but populated reference_docs/cite/
        is NOT a downgrade — `cite/` content also counts as documentation
        (mirrors how `_reference_docs_plaintext` recurses)."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            cite = tmp / "reference_docs" / "cite"
            cite.mkdir(parents=True)
            (cite / "spec.md").write_text(
                "# Project spec\n", encoding="utf-8"
            )
            self.assertEqual(
                run_playbook._evaluate_documentation_state(tmp), "with_docs"
            )

    def test_readme_alone_does_not_count(self) -> None:
        """`reference_docs/README.md` is on the SKIPPED list — it
        shouldn't on its own promote a run out of code-only mode."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            refs = tmp / "reference_docs"
            refs.mkdir()
            (refs / "README.md").write_text("# README\n", encoding="utf-8")
            self.assertEqual(
                run_playbook._evaluate_documentation_state(tmp), "code_only"
            )


class EmitDocumentationStateEventTests(unittest.TestCase):

    def test_emits_event_to_run_state_jsonl(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            written = run_playbook._emit_documentation_state_event(
                tmp, "code_only", "reference_docs/ empty"
            )
            self.assertIsNotNone(written)
            self.assertTrue(written.is_file())
            line = written.read_text(encoding="utf-8").splitlines()[0]
            event = json.loads(line)
            self.assertEqual(event["event"], "documentation_state")
            self.assertEqual(event["state"], "code_only")
            self.assertEqual(event["reason"], "reference_docs/ empty")
            self.assertIn("ts", event)

    def test_event_appends_not_overwrites(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            run_playbook._emit_documentation_state_event(
                tmp, "code_only", "first"
            )
            run_playbook._emit_documentation_state_event(
                tmp, "code_only", "second"
            )
            jsonl = tmp / "quality" / "run_state.jsonl"
            lines = jsonl.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["reason"], "first")
            self.assertEqual(json.loads(lines[1])["reason"], "second")


class ProgressMdLineTests(unittest.TestCase):

    def test_adds_state_line_to_progress_md(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            progress = tmp / "PROGRESS.md"
            ok = run_playbook._add_documentation_state_to_progress(
                progress, "code_only"
            )
            self.assertTrue(ok)
            self.assertIn(
                "Documentation state: code_only",
                progress.read_text(encoding="utf-8"),
            )

    def test_idempotent(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            progress = tmp / "PROGRESS.md"
            run_playbook._add_documentation_state_to_progress(progress, "code_only")
            run_playbook._add_documentation_state_to_progress(progress, "code_only")
            text = progress.read_text(encoding="utf-8")
            self.assertEqual(
                text.count("Documentation state: code_only"),
                1,
                f"expected exactly one state line; got: {text!r}",
            )


class InjectExplorationSectionTests(unittest.TestCase):

    def test_prepends_section_to_exploration_md(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ex = tmp / "EXPLORATION.md"
            ex.write_text("# Original Phase 1 output\n", encoding="utf-8")
            ok = run_playbook._inject_code_only_section_into_exploration(ex)
            self.assertTrue(ok)
            text = ex.read_text(encoding="utf-8")
            self.assertTrue(
                text.startswith("## Documentation status: code-only mode"),
                f"section was not prepended: {text[:200]!r}",
            )
            self.assertIn(
                "references/code-only-mode.md", text,
                "prepended section must point at the canonical doc",
            )
            # Original content preserved.
            self.assertIn("# Original Phase 1 output", text)

    def test_idempotent(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ex = tmp / "EXPLORATION.md"
            ex.write_text("# Original\n", encoding="utf-8")
            run_playbook._inject_code_only_section_into_exploration(ex)
            after_first = ex.read_text(encoding="utf-8")
            run_playbook._inject_code_only_section_into_exploration(ex)
            after_second = ex.read_text(encoding="utf-8")
            self.assertEqual(after_first, after_second)

    def test_missing_exploration_md_returns_false(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ok = run_playbook._inject_code_only_section_into_exploration(
                tmp / "missing.md"
            )
            self.assertFalse(ok)


class CodeOnlyModeDocTests(unittest.TestCase):

    def test_code_only_mode_doc_loads(self) -> None:
        """Spec asked for `test_code_only_mode_doc_loads` — verify the
        doc parses and has expected sections."""
        path = REPO_ROOT / "references" / "code-only-mode.md"
        self.assertTrue(
            path.is_file(),
            f"expected references/code-only-mode.md at {path}",
        )
        text = path.read_text(encoding="utf-8")
        for section in (
            'What "code-only mode" means',
            "What to expect from a code-only run",
            "How to upgrade",
            "Cross-references",
        ):
            self.assertIn(
                section, text,
                f"references/code-only-mode.md missing section: {section!r}",
            )


class RunOnePhaseHookTests(unittest.TestCase):
    """Static guards confirming `run_one_phase` invokes the
    documentation-state helpers when phase=='1'. Behavioral coverage
    of run_one_phase end-to-end requires an LLM and is out of scope;
    inspecting the source is the load-bearing check."""

    def test_run_one_phase_calls_evaluate_at_phase_1(self) -> None:
        source = inspect.getsource(run_playbook.run_one_phase)
        self.assertIn(
            "_evaluate_documentation_state(repo_dir)", source,
            "run_one_phase must call _evaluate_documentation_state at phase=='1' entry",
        )

    def test_run_one_phase_emits_event_for_code_only(self) -> None:
        source = inspect.getsource(run_playbook.run_one_phase)
        self.assertIn("_emit_documentation_state_event", source)
        self.assertIn("_add_documentation_state_to_progress", source)
        self.assertIn("_inject_code_only_section_into_exploration", source)


if __name__ == "__main__":
    unittest.main()
