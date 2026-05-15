from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock
import subprocess

from bin import benchmark_lib as lib


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class BenchmarkLibTests(unittest.TestCase):
    def test_detect_skill_version_reads_root_skill(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            write(temp_path / "SKILL.md", "version: 9.8.7\n")
            self.assertEqual(lib.detect_skill_version(temp_path), "9.8.7")

    def test_detect_repo_skill_version_reads_installed_copy(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            write(temp_path / ".github" / "skills" / "SKILL.md", "version: 1.4.2\n")
            self.assertEqual(lib.detect_repo_skill_version(temp_path), "1.4.2")

    def test_detect_repo_skill_version_falls_back_to_claude_and_root(self) -> None:
        """v1.5.7 BUG-001/002: nested install layouts are unambiguous
        QPB locations (no frontmatter check needed); the root SKILL.md
        is the ambiguous case and requires `name: quality-playbook`
        frontmatter for the helper to recognize it as QPB-installed."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # Nested install layout: no frontmatter identity required.
            write(temp_path / ".claude" / "skills" / "quality-playbook" / "SKILL.md", "version: 2.0.0\n")
            self.assertEqual(lib.detect_repo_skill_version(temp_path), "2.0.0")

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # Root SKILL.md MUST have `name: quality-playbook` frontmatter
            # to qualify (v1.5.7 BUG-001/002 — pre-fix, ANY root SKILL.md
            # was accepted, including a target project's own non-QPB
            # skill).
            write(
                temp_path / "SKILL.md",
                "---\nname: quality-playbook\nversion: 3.0.0\n---\n",
            )
            self.assertEqual(lib.detect_repo_skill_version(temp_path), "3.0.0")

        with TemporaryDirectory() as temp_dir:
            self.assertEqual(lib.detect_repo_skill_version(Path(temp_dir)), "")

    def test_detect_repo_skill_version_rejects_non_qpb_root_skill_md(self) -> None:
        """v1.5.7 BUG-001/002 bite: a root SKILL.md without
        `name: quality-playbook` frontmatter (i.e., a target project's
        own skill that happens to share the filename) must NOT be
        treated as QPB-installed. Pre-fix this returned the target's
        version string spuriously."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            write(
                temp_path / "SKILL.md",
                "---\nname: target-project-skill\nversion: 9.9.9\n---\n",
            )
            self.assertEqual(
                lib.detect_repo_skill_version(temp_path), "",
                "non-QPB root SKILL.md must not be detected as installed",
            )

    def test_find_installed_skill_returns_first_hit(self) -> None:
        """v1.5.6 BUG-002 + v1.5.7 BUG-001/002:
        SKILL_INSTALL_LOCATIONS leads with the repo-root SKILL.md to
        match the runtime canonical order. The root SKILL.md case
        requires `name: quality-playbook` frontmatter to qualify as
        QPB-installed (v1.5.7 BUG-001/002 identity check)."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            root_skill = temp_path / "SKILL.md"
            gh_skill = temp_path / ".github" / "skills" / "SKILL.md"
            write(
                root_skill,
                "---\nname: quality-playbook\nversion: 2.0.0\n---\n",
            )
            write(gh_skill, "version: 1.0.0\n")
            # Root SKILL.md is searched first (canonical order).
            self.assertEqual(lib.find_installed_skill(temp_path), root_skill)

    def test_find_installed_skill_skips_non_qpb_root_skill_md(self) -> None:
        """v1.5.7 BUG-001/002 bite: when the root SKILL.md is a target's
        own non-QPB skill, the helper must skip it and fall through to
        the next canonical install layout. Pre-fix the root SKILL.md
        won the lookup unconditionally and the runner treated the
        target's own skill as if it were QPB-installed."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            root_skill = temp_path / "SKILL.md"
            gh_skill = temp_path / ".github" / "skills" / "SKILL.md"
            # Root SKILL.md is the target's own skill — NOT QPB's.
            write(
                root_skill,
                "---\nname: target-project-skill\nversion: 2.0.0\n---\n",
            )
            # Nested install layout has the actual QPB skill.
            write(gh_skill, "version: 1.0.0\n")
            # Helper must skip the non-QPB root and pick the nested one.
            self.assertEqual(lib.find_installed_skill(temp_path), gh_skill)

    def test_find_installed_skill_falls_through_to_github_when_root_absent(self) -> None:
        """When root SKILL.md is absent, the next canonical hit
        (.claude/skills/quality-playbook/SKILL.md) takes over; absent
        that, .github/skills/SKILL.md (flat Copilot)."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            gh_skill = temp_path / ".github" / "skills" / "SKILL.md"
            write(gh_skill, "version: 1.0.0\n")
            # No root SKILL.md, no .claude install — flat Copilot wins.
            self.assertEqual(lib.find_installed_skill(temp_path), gh_skill)

    def test_find_installed_skill_resolves_cursor_install(self) -> None:
        """v1.5.6 BUG-008: Cursor adopters install to
        .cursor/skills/quality-playbook/SKILL.md; the helper must find it."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cursor_skill = temp_path / ".cursor" / "skills" / "quality-playbook" / "SKILL.md"
            write(cursor_skill, "version: 1.5.6\n")
            self.assertEqual(lib.find_installed_skill(temp_path), cursor_skill)

    def test_find_installed_skill_resolves_continue_install(self) -> None:
        """v1.5.6 BUG-008: same guarantee for Continue."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cont_skill = temp_path / ".continue" / "skills" / "quality-playbook" / "SKILL.md"
            write(cont_skill, "version: 1.5.6\n")
            self.assertEqual(lib.find_installed_skill(temp_path), cont_skill)

    def test_find_installed_skill_returns_none_when_absent(self) -> None:
        with TemporaryDirectory() as temp_dir:
            self.assertIsNone(lib.find_installed_skill(Path(temp_dir)))

    def test_find_functional_and_regression_tests_skip_generated_dirs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir) / "virtio-1.4.2"
            write(repo_dir / "quality" / "node_modules" / "test_functional.py", "ignored")
            write(repo_dir / "quality" / "target" / "test_regression.py", "ignored")
            functional = repo_dir / "quality" / "test_functional.py"
            regression = repo_dir / "quality" / "test_regression.py"
            write(functional, "ok")
            write(regression, "ok")

            self.assertEqual(lib.find_functional_test(repo_dir), functional)
            self.assertEqual(lib.find_regression_test(repo_dir), regression)

    def _init_repo(self, repo_dir: Path) -> None:
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)

    def test_cleanup_repo_reverts_tracked_changes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            self._init_repo(repo_dir)
            tracked = repo_dir / "tracked.txt"
            write(tracked, "original\n")
            subprocess.run(["git", "add", "tracked.txt"], cwd=repo_dir, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            write(tracked, "changed\n")
            self.assertTrue(lib.cleanup_repo(repo_dir))
            self.assertEqual(tracked.read_text(encoding="utf-8"), "original\n")

    def test_cleanup_repo_never_touches_protected_run_output_paths(self) -> None:
        """Bootstrap self-audit regression: run outputs under quality/ etc. must survive cleanup."""
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            self._init_repo(repo_dir)

            # Commit originals for both a protected-path file and a non-protected one.
            protected = repo_dir / "quality" / "EXPLORATION.md"
            non_protected = repo_dir / "README.md"
            write(protected, "PRIOR\n")
            write(non_protected, "original readme\n")
            subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Simulate Phase-1 artifacts + an incidental agent edit.
            write(protected, "FRESH PHASE 1 OUTPUT\n")
            write(non_protected, "agent edited this\n")

            result = lib.cleanup_repo(repo_dir)

            # Non-protected file reverted; protected file untouched.
            self.assertTrue(result, "should report that something was tidied")
            self.assertEqual(non_protected.read_text(encoding="utf-8"), "original readme\n")
            self.assertEqual(protected.read_text(encoding="utf-8"), "FRESH PHASE 1 OUTPUT\n")

    def test_cleanup_repo_returns_false_when_only_protected_paths_changed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            self._init_repo(repo_dir)
            protected = repo_dir / "quality" / "EXPLORATION.md"
            write(protected, "PRIOR\n")
            subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            write(protected, "FRESH RUN\n")
            self.assertFalse(lib.cleanup_repo(repo_dir), "should stay silent when only protected paths changed")
            self.assertEqual(protected.read_text(encoding="utf-8"), "FRESH RUN\n")

    def test_cleanup_repo_all_four_protected_prefixes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            self._init_repo(repo_dir)
            protected_files = [
                repo_dir / "quality" / "BUGS.md",
                repo_dir / "control_prompts" / "phase1.output.txt",
                repo_dir / "previous_runs" / "20260418-000000" / "quality" / "BUGS.md",
                repo_dir / "docs_gathered" / "spec.md",
            ]
            for p in protected_files:
                write(p, "original\n")
            subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            for p in protected_files:
                write(p, "modified\n")

            self.assertFalse(lib.cleanup_repo(repo_dir))
            for p in protected_files:
                self.assertEqual(p.read_text(encoding="utf-8"), "modified\n",
                                 f"{p} should not have been reverted")

    def test_parse_porcelain_path_handles_rename_and_plain(self) -> None:
        self.assertEqual(lib._parse_porcelain_path(" M README.md"), "README.md")
        self.assertEqual(lib._parse_porcelain_path("M  README.md"), "README.md")
        self.assertEqual(lib._parse_porcelain_path("R  old.txt -> new.txt"), "new.txt")
        self.assertIsNone(lib._parse_porcelain_path("??"))

    def test_is_protected_recognizes_all_four_prefixes(self) -> None:
        self.assertTrue(lib._is_protected("quality/BUGS.md"))
        self.assertTrue(lib._is_protected("quality/results/tdd-results.json"))
        self.assertTrue(lib._is_protected("control_prompts/phase1.output.txt"))
        self.assertTrue(lib._is_protected("previous_runs/20260418/quality/BUGS.md"))
        self.assertTrue(lib._is_protected("docs_gathered/spec.md"))
        self.assertFalse(lib._is_protected("README.md"))
        self.assertFalse(lib._is_protected("src/main.py"))
        # Defensive: a file whose name starts with "quality" but isn't under
        # quality/ is NOT protected.
        self.assertFalse(lib._is_protected("qualityscore.txt"))

    def test_count_matching_lines_uses_regex(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "requirements.md"
            write(path, "### REQ-001\n### REQ-002\nno match\nREQ-xyz\n")
            self.assertEqual(lib.count_matching_lines(path, r"### REQ-"), 2)
            self.assertEqual(lib.count_matching_lines(path, r"REQ-[0-9]{3}"), 2)

    def test_count_bug_writeups_counts_matching_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            write(repo_dir / "quality" / "writeups" / "BUG-001.md", "a")
            write(repo_dir / "quality" / "writeups" / "BUG-002.md", "b")
            write(repo_dir / "quality" / "writeups" / "NOTE.md", "c")
            self.assertEqual(lib.count_bug_writeups(repo_dir), 2)

    def test_print_summary_produces_expected_columns(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir) / "chi-1.4.2"
            for artifact in [
                "quality/REQUIREMENTS.md",
                "quality/BUGS.md",
                "quality/TDD_TRACEABILITY.md",
                "quality/RUN_INTEGRATION_TESTS.md",
            ]:
                write(repo_dir / artifact, "[Tier 1]\n[Tier 2]\n[Tier 3]\n### REQ-001\n### UC-01\nTDD verified\n")
            write(repo_dir / "quality" / "test_functional.py", "ok")
            write(repo_dir / "quality" / "test_regression.py", "ok")

            output = lib.print_summary([repo_dir])

            self.assertIn("=== Artifact Summary ===", output)
            self.assertIn("Repo", output)
            self.assertIn("REQS", output)
            self.assertIn("BUGS", output)
            self.assertIn("chi-1.4.2", output)
            self.assertIn("=== Quality Checks ===", output)

    def test_tier_counts_read_from_manifest_not_requirements_md(self) -> None:
        """v1.5.7 Issue 3 (chi-surfaced) regression. The Artifact
        Summary's T1/T2/T3 columns must come from
        requirements_manifest.json's integer `tier` field, NOT a
        `[Tier N]` substring regex over REQUIREMENTS.md prose (which
        never matched the canonical `- **Tier:** N` record format, so
        a 16-Tier-3 run printed 0 0 0).

        Mutation contract: reverting build_summary_rows to
        `count_matching_lines(requirements_file, r"\\[Tier N\\]")`
        makes this fail — REQUIREMENTS.md here uses the real
        `- **Tier:** N` prose and contains zero `[Tier N]` literals,
        so the old regex yields 0/0/0 while the manifest says 1/2/3.
        """
        import json
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir) / "chi-1.5.1"
            # REQUIREMENTS.md in the *real* canonical prose format —
            # the old [Tier N] regex finds nothing here.
            write(
                repo_dir / "quality" / "REQUIREMENTS.md",
                "### REQ-001\n- **Tier:** 1\n\n### REQ-002\n- **Tier:** 2\n"
                "\n### REQ-003\n- **Tier:** 2\n\n### REQ-004\n"
                "- **Tier:** 3\n\n### REQ-005\n- **Tier:** 3\n\n"
                "### REQ-006\n- **Tier:** 3\n",
            )
            write(
                repo_dir / "quality" / "requirements_manifest.json",
                json.dumps(
                    {
                        "schema_version": "1.5.3",
                        "generated_at": "2026-05-15T00:00:00Z",
                        "records": [
                            {"id": "REQ-001", "tier": 1},
                            {"id": "REQ-002", "tier": 2},
                            {"id": "REQ-003", "tier": 2},
                            {"id": "REQ-004", "tier": 3},
                            {"id": "REQ-005", "tier": 3},
                            {"id": "REQ-006", "tier": 3},
                        ],
                    }
                ),
            )

            self.assertEqual(
                lib._count_req_tiers_from_manifest(repo_dir / "quality"),
                (1, 2, 3),
                "tier counts must come from the manifest's integer "
                "`tier` field",
            )

            rows = lib.build_summary_rows([repo_dir])
            self.assertEqual(len(rows), 1)
            self.assertEqual(
                (rows[0].tier1, rows[0].tier2, rows[0].tier3),
                (1, 2, 3),
                "build_summary_rows must surface the manifest tier "
                "counts in the Artifact Summary row",
            )

            output = lib.print_summary([repo_dir])
            self.assertIn("=== Artifact Summary ===", output)

    def test_tier_counts_zero_when_manifest_absent_or_bad(self) -> None:
        """Graceful fallback: no manifest, or unparseable manifest,
        yields (0, 0, 0) rather than crashing the summary."""
        import json
        with TemporaryDirectory() as temp_dir:
            quality = Path(temp_dir) / "quality"
            # No manifest at all.
            self.assertEqual(
                lib._count_req_tiers_from_manifest(quality), (0, 0, 0)
            )
            # Unparseable manifest.
            write(quality / "requirements_manifest.json", "{ not json")
            self.assertEqual(
                lib._count_req_tiers_from_manifest(quality), (0, 0, 0)
            )
            # Well-formed but no records list.
            write(
                quality / "requirements_manifest.json",
                json.dumps({"schema_version": "1.5.3"}),
            )
            self.assertEqual(
                lib._count_req_tiers_from_manifest(quality), (0, 0, 0)
            )

    def test_log_and_logboth_format_and_write(self) -> None:
        message = lib.log("hello")
        self.assertRegex(message, r"^\d{2}:\d{2}:\d{2} hello$")

        with TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "runner.log"
            # v1.5.1 Item 2.1: isatty() gate is gone; logboth unconditionally
            # writes to the log file regardless of stdout state. Suppress
            # stdout echo explicitly so this test stays terse.
            lib.logboth(log_file, "stored line", echo=False)
            self.assertEqual(log_file.read_text(encoding="utf-8"), "stored line\n")

    def test_logboth_isatty_gate_removed_default_echoes_to_stdout(self) -> None:
        """v1.5.1 Item 2.1: the prior isatty() echo gate silently suppressed
        stdout when the operator piped the run through `tee`. The default
        behavior is now to always echo; the --no-stdout-echo escape hatch
        (via set_default_echo) is the explicit opt-out."""
        import io as _io
        from contextlib import redirect_stdout

        # Ensure we start from the default state no matter what prior tests
        # left behind.
        original = lib.get_default_echo()
        lib.set_default_echo(True)
        try:
            with TemporaryDirectory() as temp_dir:
                log_file = Path(temp_dir) / "runner.log"
                buf = _io.StringIO()
                # StringIO.isatty() returns False — the prior implementation
                # would have suppressed the echo. The new implementation must
                # echo regardless.
                with redirect_stdout(buf):
                    lib.logboth(log_file, "streamed line")
                self.assertIn("streamed line", buf.getvalue())
                self.assertEqual(
                    log_file.read_text(encoding="utf-8"), "streamed line\n"
                )
        finally:
            lib.set_default_echo(original)

    def test_logboth_echo_false_still_suppresses_stdout(self) -> None:
        import io as _io
        from contextlib import redirect_stdout

        with TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "runner.log"
            buf = _io.StringIO()
            with redirect_stdout(buf):
                lib.logboth(log_file, "silent line", echo=False)
            self.assertEqual(buf.getvalue(), "")
            self.assertEqual(
                log_file.read_text(encoding="utf-8"), "silent line\n"
            )

    def test_logboth_echo_true_always_prints(self) -> None:
        import io as _io
        from contextlib import redirect_stdout

        original = lib.get_default_echo()
        lib.set_default_echo(False)
        try:
            with TemporaryDirectory() as temp_dir:
                log_file = Path(temp_dir) / "runner.log"
                buf = _io.StringIO()
                # Even with the module default off, explicit echo=True prints.
                with redirect_stdout(buf):
                    lib.logboth(log_file, "forced line", echo=True)
                self.assertIn("forced line", buf.getvalue())
        finally:
            lib.set_default_echo(original)

    def test_set_default_echo_flips_module_state(self) -> None:
        original = lib.get_default_echo()
        try:
            lib.set_default_echo(False)
            self.assertFalse(lib.get_default_echo())
            lib.set_default_echo(True)
            self.assertTrue(lib.get_default_echo())
        finally:
            lib.set_default_echo(original)

    def test_version_resolution_helpers_are_gone(self) -> None:
        """Version-based repo resolution has been removed; positional args are now paths."""
        for name in ("REPOS_DIR", "SHORT_VERSIONED_DIR_PATTERN",
                     "find_repo_dir", "resolve_repos", "repo_short_name",
                     "version_key"):
            self.assertFalse(hasattr(lib, name), f"lib.{name} should have been removed")


class CountUseCasesTests(unittest.TestCase):
    """v1.5.4 F-3 (Bootstrap_Findings 2026-04-30): UC count must come
    from the use_cases_manifest.json record set, not from a grep of
    REQUIREMENTS.md for `### UC-`. The grep silently undercounts when
    the LLM uses a different rendering convention even though the
    manifest is correct."""

    def test_uses_manifest_record_count_when_manifest_present(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            requirements = repo_dir / "quality" / "REQUIREMENTS.md"
            # Only ONE UC visible to the old grep pattern.
            write(requirements, "### REQ-001\n### UC-001\n")
            manifest = repo_dir / "quality" / "use_cases_manifest.json"
            write(
                manifest,
                '{"schema_version":"1.5.3","generated_at":"2026-04-30T00:00:00Z",'
                '"records":[{"id":"UC-001"},{"id":"UC-002"},{"id":"UC-003"}]}',
            )
            # Manifest wins: 3 records, not the 1 the grep would find.
            self.assertEqual(lib._count_use_cases(repo_dir, requirements), 3)

    def test_falls_back_to_grep_when_manifest_absent(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            requirements = repo_dir / "quality" / "REQUIREMENTS.md"
            write(requirements, "### REQ-001\n### UC-001\n### UC-002\n")
            # No manifest on disk → grep fallback returns 2.
            self.assertEqual(lib._count_use_cases(repo_dir, requirements), 2)

    def test_falls_back_to_grep_when_manifest_malformed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            requirements = repo_dir / "quality" / "REQUIREMENTS.md"
            write(requirements, "### UC-001\n### UC-002\n### UC-003\n")
            manifest = repo_dir / "quality" / "use_cases_manifest.json"
            write(manifest, "not json {{{")
            # Malformed JSON falls through silently to grep (3).
            self.assertEqual(lib._count_use_cases(repo_dir, requirements), 3)

    def test_falls_back_to_grep_when_records_key_missing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            requirements = repo_dir / "quality" / "REQUIREMENTS.md"
            write(requirements, "### UC-001\n")
            manifest = repo_dir / "quality" / "use_cases_manifest.json"
            # Wrapper present but `records` missing — fall back to grep.
            write(manifest, '{"schema_version":"1.5.3","generated_at":"x"}')
            self.assertEqual(lib._count_use_cases(repo_dir, requirements), 1)

    def test_zero_record_manifest_returns_zero_not_grep(self) -> None:
        """An empty `records` array is an authoritative zero — must not
        silently fall through to the grep, otherwise the manifest's
        explicit `[]` would be ignored. This pins the precedence
        contract: presence-of-records-key is the trigger."""
        with TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir)
            requirements = repo_dir / "quality" / "REQUIREMENTS.md"
            write(requirements, "### UC-001\n### UC-002\n")
            manifest = repo_dir / "quality" / "use_cases_manifest.json"
            write(
                manifest,
                '{"schema_version":"1.5.3","generated_at":"x","records":[]}',
            )
            self.assertEqual(lib._count_use_cases(repo_dir, requirements), 0)


if __name__ == "__main__":
    unittest.main()
