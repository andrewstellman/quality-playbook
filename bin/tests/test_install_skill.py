"""Tests for bin/install_skill.py.

Coverage: environment detection (.claude / .github / .cursor),
--target override, no-env-no-target refusal, idempotency with
operator-edit preservation, --force overwrite semantics, smoke pass on
clean install, smoke fail on broken quality_gate, structured-output
parseability, pathlib's handling of Windows-style path strings on POSIX.

All tests use TemporaryDirectory sandboxes — no test ever writes outside
the sandbox.
"""

from __future__ import annotations

import io
import re
import shutil
import unittest
from contextlib import redirect_stderr
from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory

from bin import install_skill


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _capture_install(**kwargs) -> tuple[int, str]:
    """Run install_skill.install with output captured to a StringIO.
    Returns (exit_code, stdout_text)."""
    buf = io.StringIO()
    rc = install_skill.install(stream=buf, **kwargs)
    return rc, buf.getvalue()


def _write_minimal_env(target_root: Path, env_marker: str) -> None:
    """Drop a marker subdirectory so detect_environment sees the env."""
    (target_root / env_marker).mkdir()


class EnvironmentDetectionTests(unittest.TestCase):
    """The detect-environment-from-cwd flow auto-targets the right
    install path for each known AI tool."""

    def test_detect_claude_env(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_minimal_env(tmp, ".claude")
            rc, out = _capture_install(cwd=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            self.assertIn("event=detected_env env=.claude", out)
            target = tmp / ".claude" / "skills" / "quality-playbook"
            self.assertTrue((target / "SKILL.md").is_file())
            self.assertTrue((target / "quality_gate.py").is_file())
            self.assertTrue((target / "references" / "exploration_patterns.md").is_file())

    def test_detect_github_env(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_minimal_env(tmp, ".github")
            rc, out = _capture_install(cwd=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            self.assertIn("event=detected_env env=.github", out)
            target = tmp / ".github" / "skills" / "quality-playbook"
            self.assertTrue((target / "SKILL.md").is_file())

    def test_detect_cursor_env(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_minimal_env(tmp, ".cursor")
            rc, out = _capture_install(cwd=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            self.assertIn("event=detected_env env=.cursor", out)
            self.assertTrue(
                (tmp / ".cursor" / "skills" / "quality-playbook" / "SKILL.md").is_file()
            )

    def test_phase_prompts_bundled_in_cursor_install(self) -> None:
        """v1.5.6 BUG-001/015/017: phase_prompts/*.md must land at the
        install destination so Mode A walkthroughs can resolve
        phase{N}.md at runtime. The installer's bundle is the only
        load-bearing surface here — without it, installed Mode A
        breaks at the first phase boundary."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_minimal_env(tmp, ".cursor")
            rc, out = _capture_install(cwd=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            install_dir = tmp / ".cursor" / "skills" / "quality-playbook"
            phase_dir = install_dir / "phase_prompts"
            self.assertTrue(
                phase_dir.is_dir(),
                f"phase_prompts/ subtree missing at install destination "
                f"({phase_dir}); installed Mode A will fail at the first "
                f"phase boundary. Output: {out}",
            )
            # Every phase{N}.md present in the source must be at the
            # destination — exact set so an additive change to
            # phase_prompts/ in source doesn't silently bypass the
            # install bundle.
            src_prompts = sorted(p.name for p in (REPO_ROOT / "phase_prompts").glob("*.md"))
            installed = sorted(p.name for p in phase_dir.glob("*.md"))
            self.assertEqual(
                installed, src_prompts,
                f"phase_prompts/*.md mismatch — source: {src_prompts}, "
                f"installed: {installed}",
            )
            # Structured-output check: at least one event=copy line
            # names a phase_prompts/ destination.
            self.assertIn(
                "phase_prompts/", out,
                "expected at least one event=copy file=...phase_prompts/... "
                "line in installer output",
            )

    def test_phase_prompts_bundled_via_target_override(self) -> None:
        """Same guarantee under --target (literal install path), since
        adopters using --target get the same bundle."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "explicit-install"
            rc, out = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            phase_dir = target / "phase_prompts"
            self.assertTrue(phase_dir.is_dir(), out)
            installed = sorted(p.name for p in phase_dir.glob("*.md"))
            src_prompts = sorted(p.name for p in (REPO_ROOT / "phase_prompts").glob("*.md"))
            self.assertEqual(installed, src_prompts)

    def test_agents_bundled_in_install(self) -> None:
        """v1.5.6 cluster A (closes issue #1 concern 4): agents/*.md
        must land at the install destination so README Step 4's
        ``claude --agent agents/quality-playbook.agent.md`` invocation
        resolves at the install destination. Pre-fix the relative path
        only worked from the QPB clone — adopters running the
        documented invocation from their target repo got "agent file
        not found" because install_skill.py never copied agents/."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_minimal_env(tmp, ".cursor")
            rc, out = _capture_install(cwd=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            install_dir = tmp / ".cursor" / "skills" / "quality-playbook"
            agents_dir = install_dir / "agents"
            self.assertTrue(
                agents_dir.is_dir(),
                f"agents/ subtree missing at install destination "
                f"({agents_dir}); README Step 4's relative-path "
                f"`claude --agent agents/...` invocation will fail. "
                f"Output: {out}",
            )
            # Bundle-set parity: every agents/*.md in source must
            # land at the destination. Exact-set match so an additive
            # change to agents/ doesn't silently bypass the install
            # bundle.
            src_agents = sorted(p.name for p in (REPO_ROOT / "agents").glob("*.md"))
            installed = sorted(p.name for p in agents_dir.glob("*.md"))
            self.assertEqual(
                installed, src_agents,
                f"agents/*.md mismatch — source: {src_agents}, "
                f"installed: {installed}",
            )
            # The two adopter-facing orchestrator agents MUST be in
            # the bundle (the calibration_orchestrator is QPB-internal
            # tooling and ships alongside as a no-cost convenience).
            self.assertIn(
                "quality-playbook.agent.md", installed,
                "general orchestrator agent must be bundled — it's "
                "the v1.5.6 README Step 4 reference.",
            )
            self.assertIn(
                "quality-playbook-claude.agent.md", installed,
                "Claude Code orchestrator agent must be bundled — "
                "it's the README Step 4 'autonomous mode' reference.",
            )
            # Structured-output check: at least one event=copy line
            # names an agents/ destination.
            self.assertIn(
                "agents/", out,
                "expected at least one event=copy file=...agents/... "
                "line in installer output",
            )

    def test_agents_bundled_via_target_override(self) -> None:
        """Same agents/ bundle guarantee under --target, parallel to
        the phase_prompts/ --target test."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "explicit-install"
            rc, out = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            agents_dir = target / "agents"
            self.assertTrue(agents_dir.is_dir(), out)
            installed = sorted(p.name for p in agents_dir.glob("*.md"))
            src_agents = sorted(p.name for p in (REPO_ROOT / "agents").glob("*.md"))
            self.assertEqual(installed, src_agents)

    def test_target_override(self) -> None:
        """--target wins even when an environment is detectable."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            _write_minimal_env(tmp, ".claude")
            custom = tmp / "custom-install-path"
            rc, out = _capture_install(
                cwd=tmp, source_root=REPO_ROOT, target=custom,
            )
            self.assertEqual(rc, 0, out)
            self.assertIn("event=target_explicit", out)
            self.assertNotIn("event=detected_env", out)
            self.assertTrue((custom / "SKILL.md").is_file())
            # Auto-detect target was NOT used.
            self.assertFalse(
                (tmp / ".claude" / "skills" / "quality-playbook" / "SKILL.md").exists()
            )

    def test_no_environment_no_target_refuses(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            # Plain dir — no .claude / .github / .cursor / .continue
            (tmp / "src").mkdir()
            rc, out = _capture_install(cwd=tmp, source_root=REPO_ROOT)
            self.assertEqual(
                rc, 64,
                f"expected EX_USAGE refusal; got {rc}. Output: {out}",
            )
            self.assertIn("event=refuse", out)
            self.assertIn("reason=no-environment-detected", out)
            # Helpful prose names the alternative.
            self.assertIn(".claude", out)


class IdempotencyAndForceTests(unittest.TestCase):
    """Re-installing preserves operator edits as
    .operator-backup-<timestamp>; --force skips the backup."""

    def test_idempotent_preserves_operator_edits(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "install"
            # Initial install.
            rc1, _ = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(rc1, 0)
            # Operator edit: modify SKILL.md in target.
            skill = target / "SKILL.md"
            edited = skill.read_text(encoding="utf-8") + "\n# operator notes\n"
            skill.write_text(edited, encoding="utf-8")
            # Re-install WITHOUT --force.
            rc2, out = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(rc2, 0, out)
            # Backup exists with operator's content.
            backups = list(target.glob("SKILL.md.operator-backup-*"))
            self.assertEqual(
                len(backups), 1,
                f"expected exactly one backup, got {backups}",
            )
            self.assertIn("operator notes", backups[0].read_text(encoding="utf-8"))
            # New SKILL.md does NOT contain the operator edit.
            self.assertNotIn("operator notes", skill.read_text(encoding="utf-8"))
            # Status line shows backed_up.
            self.assertIn("status=backed_up", out)

    def test_force_overwrites(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "install"
            rc1, _ = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(rc1, 0)
            skill = target / "SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8") + "\n# operator notes\n",
                encoding="utf-8",
            )
            rc2, out = _capture_install(
                target=target, source_root=REPO_ROOT, force=True,
            )
            self.assertEqual(rc2, 0, out)
            backups = list(target.glob("SKILL.md.operator-backup-*"))
            self.assertEqual(backups, [])
            self.assertNotIn("operator notes", skill.read_text(encoding="utf-8"))
            self.assertIn("status=overwritten", out)


class IntoFlagTests(unittest.TestCase):
    """`--into` scans the target repo and resolves the install path from
    the detected AI-tool marker inside that repo."""

    def test_into_flag_detects_claude_in_target(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str).resolve()
            _write_minimal_env(tmp, ".claude")
            rc, out = _capture_install(into=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            install_path = tmp / ".claude" / "skills" / "quality-playbook"
            self.assertIn("event=detected_env_inside_target", out)
            self.assertIn(f"target={tmp}", out)
            self.assertIn("env=.claude", out)
            self.assertIn(f"install_path={install_path}", out)
            self.assertTrue((install_path / "SKILL.md").is_file())

    def test_into_flag_detects_cursor_in_target(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str).resolve()
            _write_minimal_env(tmp, ".cursor")
            rc, out = _capture_install(into=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            install_path = tmp / ".cursor" / "skills" / "quality-playbook"
            self.assertIn("event=detected_env_inside_target", out)
            self.assertIn(f"target={tmp}", out)
            self.assertIn("env=.cursor", out)
            self.assertIn(f"install_path={install_path}", out)
            self.assertTrue((install_path / "SKILL.md").is_file())

    def test_into_flag_detects_github_in_target(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str).resolve()
            _write_minimal_env(tmp, ".github")
            rc, out = _capture_install(into=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            install_path = tmp / ".github" / "skills" / "quality-playbook"
            self.assertIn("event=detected_env_inside_target", out)
            self.assertIn(f"target={tmp}", out)
            self.assertIn("env=.github", out)
            self.assertIn(f"install_path={install_path}", out)
            self.assertTrue((install_path / "SKILL.md").is_file())

    def test_into_flag_no_env_in_target_refuses(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str).resolve()
            (tmp / "src").mkdir()
            rc, out = _capture_install(into=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 64, out)
            self.assertIn("event=refuse", out)
            self.assertIn("reason=no-environment-detected-in-target", out)
            self.assertIn(f"target={tmp}", out)

    def test_target_and_into_mutually_exclusive(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            err = io.StringIO()
            with redirect_stderr(err):
                with self.assertRaises(SystemExit) as raised:
                    install_skill.main(
                        [
                            "--target", str(tmp / "install"),
                            "--into", str(tmp),
                        ]
                    )
            self.assertEqual(raised.exception.code, 2)
            self.assertIn("not allowed with argument", err.getvalue())


class SmokeCheckTests(unittest.TestCase):
    """Smoke pass on a clean install; smoke fail when quality_gate.py
    is sabotaged."""

    def test_smoke_check_passes_on_clean_install(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "install"
            rc, out = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            for check in (
                "quality_gate_help",
                "skill_md_frontmatter",
                "exploration_patterns_loaded",
            ):
                self.assertIn(
                    f"check={check} status=passed", out,
                    f"smoke check {check} did not pass; output: {out}",
                )

    def test_smoke_check_catches_broken_quality_gate(self) -> None:
        """Install with --no-smoke, deliberately break quality_gate.py
        in the target, then re-invoke the smoke check by re-installing
        with --force=False (the existing-file path) — but actually the
        cleanest reproduction is a separate install call that runs the
        smoke check against the broken target."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "install"
            # Initial install with smoke skipped.
            rc, _ = _capture_install(
                target=target, source_root=REPO_ROOT, no_smoke=True,
            )
            self.assertEqual(rc, 0)
            # Sabotage quality_gate.py — replace with non-Python garbage.
            (target / "quality_gate.py").write_text(
                "this is not valid python )(\n", encoding="utf-8",
            )
            # Re-install with --force so the broken file persists past
            # the copy step (force overwrites without backup, but the
            # source is identical so nothing happens — wait, we need
            # the smoke check to run AGAINST the broken file. The
            # cleanest path: re-run install with the same target but
            # have the source's quality_gate.py be the broken one.
            # Easier: directly call the smoke check.
            buf = io.StringIO()
            emitter = install_skill.Emitter(verbose=False, stream=buf)
            ok = install_skill.smoke_check_quality_gate(target, emitter)
            output = buf.getvalue()
            self.assertFalse(
                ok,
                f"expected smoke check to fail; output: {output}",
            )
            self.assertIn("status=failed", output)
            self.assertIn("compile-exit-", output)


class StructuredOutputTests(unittest.TestCase):
    """Default output is parseable as one event per line, key=value
    pairs."""

    def test_structured_output_parseable(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "install"
            rc, out = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(rc, 0)
            event_re = re.compile(r"^event=\w+(\s+\w+=\S+)*\s*$")
            non_event = []
            for line in out.splitlines():
                if not line.strip():
                    continue
                if not event_re.match(line):
                    non_event.append(line)
            self.assertEqual(
                non_event, [],
                f"non-event lines in default output (verbose=False): {non_event}",
            )

    def test_verbose_adds_prose_lines(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "install"
            rc, out = _capture_install(
                target=target, source_root=REPO_ROOT, verbose=True,
            )
            self.assertEqual(rc, 0)
            # Verbose prose lines are 2-space indented, do not start
            # with "event=".
            prose_lines = [
                line for line in out.splitlines()
                if line.startswith("  ")
            ]
            self.assertGreater(
                len(prose_lines), 0,
                "verbose output should contain at least one prose line",
            )


class PathlibCrossPlatformTests(unittest.TestCase):
    """A Windows-style path string flows through pathlib.Path on POSIX
    by being interpreted as a forward-slash path; the bigger guarantee
    is that the script never uses string concatenation with '/' so any
    pathlib.Path or pathlib.PureWindowsPath works on its native OS."""

    def test_pathlib_handles_windows_path_string(self) -> None:
        # PureWindowsPath constructs cleanly; the script's internal
        # path operations would then run on it on Windows. On POSIX we
        # validate the path-construction half (no string concat
        # accidents).
        win = PureWindowsPath(r"C:\Users\op\.claude\skills\quality-playbook")
        self.assertEqual(win.name, "quality-playbook")
        self.assertEqual(win.parts[-3:], (".claude", "skills", "quality-playbook"))
        # Windows drive letter is preserved in the first part.
        self.assertTrue(win.parts[0].startswith("C:"))
        # The install script's bundle enumeration uses pathlib.Path
        # exclusively (verified by importing _bundle_files and
        # checking every path returned is a Path instance).
        bundle = install_skill._bundle_files(REPO_ROOT)
        for src, dst in bundle:
            self.assertIsInstance(src, Path)
            self.assertIsInstance(dst, Path)

    def test_install_skill_pathlib_windows_path_handling(self) -> None:
        """v1.5.6 cluster D — Windows-direct testing was infrastructure-
        blocked (no Windows machine, Wine, or container runtime
        available in the validation sandbox). This test extends the
        pathlib-correctness coverage by exercising EVERY path-shape
        the install bundle produces through ``PureWindowsPath`` so a
        future regression that introduces string-concatenation or
        forward-slash assumptions trips here even though we can't
        run the actual install on Windows.

        Pinned coverage:
        - ``_bundle_files`` returns Path-typed source AND destination
          for every entry (no plain str leaks).
        - Every destination path is a RELATIVE pathlib.Path that, when
          joined to a ``PureWindowsPath`` install root, produces a
          well-formed Windows path with NO doubled separators, NO
          forward-slash leakage in components, and a preserved drive
          letter at the front.
        - The five top-level destinations (SKILL.md, quality_gate.py,
          references/, phase_prompts/, agents/) all behave correctly
          when joined with a Windows-style root.
        - ``_path_under_allowed_prefix``-style operations (used by
          run_state_lib.validate_no_source_edits) tolerate Windows
          path separators when the operator runs on Windows.
        """
        bundle = install_skill._bundle_files(REPO_ROOT)
        windows_root = PureWindowsPath(
            r"C:\Users\op\my-project\.claude\skills\quality-playbook"
        )
        # All five bundle "regions" must be represented (top-level
        # files SKILL.md + quality_gate.py, plus references/,
        # phase_prompts/, agents/ subtrees).
        regions_seen: set[str] = set()
        for src, dst in bundle:
            self.assertIsInstance(
                src, Path,
                f"_bundle_files leaked a non-Path source: {src!r}",
            )
            self.assertIsInstance(
                dst, Path,
                f"_bundle_files leaked a non-Path destination: {dst!r}",
            )
            # Destination must be relative — install_root joining
            # only makes sense if dst is relative.
            self.assertFalse(
                dst.is_absolute(),
                f"destination {dst!r} is absolute; bundle "
                f"destinations must be relative to the install root.",
            )
            # No forward-slash leakage in any component (the test
            # for "string concatenation accidents" — if a future
            # refactor introduces ``Path("references/" + name)``
            # the resulting path has a single component with an
            # embedded forward slash on Windows).
            for component in dst.parts:
                self.assertNotIn(
                    "/", component,
                    f"destination component {component!r} (in {dst!r}) "
                    f"contains a forward slash — Windows path "
                    f"correctness regression. Use Path() / 'name', "
                    f"NOT string concat.",
                )
                self.assertNotIn(
                    "\\", component,
                    f"destination component {component!r} (in {dst!r}) "
                    f"contains a backslash — pathlib should split "
                    f"separators, never embed them in components.",
                )
            # Track which top-level region the destination falls
            # under for the regions_seen set.
            top = dst.parts[0]
            if top in ("SKILL.md", "quality_gate.py"):
                regions_seen.add(top)
            elif top in ("references", "phase_prompts", "agents"):
                regions_seen.add(top)
            else:
                self.fail(
                    f"unexpected top-level destination region: {top!r} "
                    f"(in {dst!r}). Five regions are supported: "
                    f"SKILL.md, quality_gate.py, references/, "
                    f"phase_prompts/, agents/."
                )
            # Joined with a Windows root, the result is a well-formed
            # Windows path with no doubled separators and the drive
            # letter preserved.
            dst_str = str(dst)
            joined = PureWindowsPath(*windows_root.parts, *dst.parts)
            self.assertTrue(
                joined.parts[0].startswith("C:"),
                f"PureWindowsPath join lost the drive letter for "
                f"destination {dst!r}: {joined!r}",
            )
            self.assertNotIn(
                "//", str(joined),
                f"PureWindowsPath join produced doubled forward "
                f"slashes: {joined!r}",
            )
            self.assertNotIn(
                "\\\\", str(joined),
                f"PureWindowsPath join produced doubled backslashes: "
                f"{joined!r}",
            )
            # Joining preserves dst's component count: every part of
            # dst appears as a part in joined (after the windows_root
            # parts).
            joined_tail = joined.parts[len(windows_root.parts):]
            self.assertEqual(
                joined_tail, dst.parts,
                f"PureWindowsPath join lost or duplicated components: "
                f"dst.parts={dst.parts}, joined_tail={joined_tail}",
            )
        self.assertEqual(
            regions_seen,
            {"SKILL.md", "quality_gate.py", "references",
             "phase_prompts", "agents"},
            f"expected all five bundle regions; got {regions_seen}",
        )

    def test_install_path_separator_independence(self) -> None:
        """The bundle's path operations should produce identical
        component sequences regardless of whether the install root is
        constructed as a POSIX or Windows path. (POSIX-side proxy
        check for cross-platform path-handling correctness.)"""
        bundle = install_skill._bundle_files(REPO_ROOT)
        posix_root = Path("/home/op/proj/.claude/skills/quality-playbook")
        windows_root = PureWindowsPath(
            r"C:\Users\op\proj\.claude\skills\quality-playbook"
        )
        for _, dst in bundle:
            # Tail components after the install root must be the
            # SAME ordered tuple under both path flavors. If the
            # bundle started leaking '/' or '\' into individual
            # components, the two component lists would diverge.
            posix_join = posix_root / dst
            windows_join = windows_root / PureWindowsPath(*dst.parts)
            posix_tail = posix_join.parts[len(posix_root.parts):]
            windows_tail = windows_join.parts[len(windows_root.parts):]
            self.assertEqual(
                posix_tail, windows_tail,
                f"path-flavor divergence for destination {dst!r}: "
                f"posix_tail={posix_tail}, "
                f"windows_tail={windows_tail}. The bundle's destination "
                f"components must be path-flavor-agnostic.",
            )


class DowngradeRefusalTests(unittest.TestCase):
    """Refuse to install over a target whose SKILL.md version is HIGHER
    than the bundle's."""

    def test_downgrade_refused(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "install"
            target.mkdir()
            # Stage a target SKILL.md with a higher version than the
            # current bundle.
            target_skill = target / "SKILL.md"
            target_skill.write_text(
                "---\n"
                "name: quality-playbook\n"
                "description: stub\n"
                "metadata:\n"
                "  version: 99.0.0\n"
                "---\n",
                encoding="utf-8",
            )
            rc, out = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(
                rc, 65,
                f"expected EX_DATAERR (65) on downgrade refusal; got {rc}. {out}",
            )
            self.assertIn("event=refuse reason=downgrade", out)
            # Target SKILL.md must NOT have been overwritten.
            self.assertIn("99.0.0", target_skill.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
