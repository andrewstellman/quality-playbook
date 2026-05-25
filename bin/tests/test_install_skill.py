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
import os
import re
import shutil
import subprocess
import sys
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

    def test_citation_verifier_bundled_in_install(self) -> None:
        """v1.5.6 BUG-005: bin/citation_verifier.py must land at the
        install destination so quality_gate.py's soft-import resolves
        at install time and the v1.5.1 byte-equality citation check
        actually runs. Pre-fix the verifier was never copied — every
        installed gate fell back to the WARN path."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "explicit-install"
            rc, out = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            verifier_path = target / "bin" / "citation_verifier.py"
            self.assertTrue(
                verifier_path.is_file(),
                f"bin/citation_verifier.py missing at install destination "
                f"({verifier_path}); quality_gate.py's v1.5.1 byte-equality "
                f"check will silently fall back to WARN. Output: {out}",
            )
            self.assertIn(
                "bin/citation_verifier.py", out,
                "expected event=copy file=...bin/citation_verifier.py line "
                "in installer output",
            )

    def test_installed_gate_can_import_citation_verifier(self) -> None:
        """v1.5.6 BUG-005: the installed gate must be able to soft-import
        bin/citation_verifier without falling back to WARN. Confirms the
        _VERIFIER_SEARCH_ROOTS scan in quality_gate.py picks up the
        bundled verifier from the install destination."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "explicit-install"
            rc, out = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            gate_path = target / "quality_gate.py"
            self.assertTrue(gate_path.is_file(), out)
            probe = (
                "import importlib.util, pathlib, sys; "
                "p = pathlib.Path(sys.argv[1]); "
                "spec = importlib.util.spec_from_file_location('installed_quality_gate', p); "
                "mod = importlib.util.module_from_spec(spec); "
                "spec.loader.exec_module(mod); "
                "print('present' if mod._CITATION_VERIFIER is not None else 'missing')"
            )
            env = os.environ.copy()
            # Remove PYTHONPATH so the source clone's bin/ doesn't satisfy
            # the import — we want to verify the BUNDLED verifier resolves.
            env.pop("PYTHONPATH", None)
            result = subprocess.run(
                [sys.executable, "-c", probe, str(gate_path)],
                cwd=target,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(
                result.returncode, 0,
                f"probe failed: stdout={result.stdout!r} stderr={result.stderr!r}",
            )
            self.assertIn(
                "present", result.stdout,
                f"installed gate could not soft-import citation_verifier; "
                f"_CITATION_VERIFIER stayed None. stdout={result.stdout!r} "
                f"stderr={result.stderr!r}",
            )

    def test_reference_docs_ingest_bundled_in_install(self) -> None:
        """v1.5.7 fix F-1: bin/reference_docs_ingest.py must land at the
        install destination so Phase 1's `python -m bin.reference_docs_ingest`
        invocation resolves. Pre-fix every benchmark target hard-stopped at
        Phase 1 with ModuleNotFoundError because the script lived only in
        the QPB clone, not at the install root."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "explicit-install"
            rc, out = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            ingest_path = target / "bin" / "reference_docs_ingest.py"
            self.assertTrue(
                ingest_path.is_file(),
                f"bin/reference_docs_ingest.py missing at install destination "
                f"({ingest_path}); Phase 1 will hard-stop with "
                f"ModuleNotFoundError. Output: {out}",
            )
            # benchmark_lib is a transitive dep (reference_docs_ingest
            # imports it at module load) — both must be present or Phase 1
            # fails at ImportError before it can run.
            benchmark_lib_path = target / "bin" / "benchmark_lib.py"
            self.assertTrue(
                benchmark_lib_path.is_file(),
                f"bin/benchmark_lib.py missing at install destination "
                f"({benchmark_lib_path}); reference_docs_ingest module load "
                f"will fail. Output: {out}",
            )
            self.assertIn(
                "bin/reference_docs_ingest.py", out,
                "expected event=copy file=...bin/reference_docs_ingest.py line "
                "in installer output",
            )

    def test_installed_reference_docs_ingest_is_importable(self) -> None:
        """v1.5.7 fix F-1: after install, the bundled
        bin/reference_docs_ingest.py must load as a module
        (`python -m bin.reference_docs_ingest --help`) from the install
        destination. Catches the case where the module file lands but its
        transitive imports (benchmark_lib) are missing."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "explicit-install"
            rc, out = _capture_install(target=target, source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            env = os.environ.copy()
            # Remove PYTHONPATH so the source clone's bin/ doesn't satisfy
            # the import — we want to verify the BUNDLED module + its
            # transitive deps resolve at the install destination.
            env.pop("PYTHONPATH", None)
            result = subprocess.run(
                [sys.executable, "-m", "bin.reference_docs_ingest", "--help"],
                cwd=target,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(
                result.returncode, 0,
                f"bin.reference_docs_ingest --help failed at install "
                f"destination: stdout={result.stdout!r} stderr={result.stderr!r}",
            )

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
            # v1.5.6 instruction 064: refusal shape changed from
            # event=refuse reason=no-environment-detected to a
            # two-event recovery-guidance pair.
            self.assertIn("event=detection_failed", out)
            self.assertIn("event=install_complete", out)
            self.assertIn("status=failed", out)
            self.assertIn("reason=no_marker_directory_found", out)
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
            # v1.5.6 instruction 064: refusal shape changed; new events
            # carry the same target= field but split into a detection
            # failure + install_complete pair with recovery guidance.
            self.assertIn("event=detection_failed", out)
            self.assertIn("event=install_complete", out)
            self.assertIn("reason=no_marker_directory_found", out)
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
                "bundle_presence",  # v1.5.7 BUG-003
            ):
                self.assertIn(
                    f"check={check} status=passed", out,
                    f"smoke check {check} did not pass; output: {out}",
                )

    def test_smoke_check_bundle_presence_catches_missing_member(self) -> None:
        """v1.5.7 BUG-003 bite: if a bundle member is missing or empty
        at the install destination, the new bundle-presence smoke check
        fails with a diagnostic naming the missing file. Pre-fix the
        smoke check covered only quality_gate.py + SKILL.md frontmatter
        + exploration_patterns.md — silent gaps elsewhere in the bundle
        slipped through."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            target = tmp / "install"
            # Initial clean install (smoke skipped — we'll run it
            # ourselves after sabotaging a bundle member).
            rc, _ = _capture_install(
                target=target, source_root=REPO_ROOT, no_smoke=True,
            )
            self.assertEqual(rc, 0)
            # Sabotage a bundle member that the old smoke check would
            # NOT have noticed (the old 3 checks don't touch
            # agents/quality-playbook.agent.md).
            sabotaged = target / "agents" / "quality-playbook.agent.md"
            self.assertTrue(
                sabotaged.is_file(),
                "sabotage precondition: agents/quality-playbook.agent.md "
                "must be in the install bundle",
            )
            sabotaged.unlink()
            # Re-run JUST the bundle-presence smoke check.
            buf = io.StringIO()
            emitter = install_skill.Emitter(verbose=False, stream=buf)
            ok = install_skill.smoke_check_bundle_presence(
                target, REPO_ROOT, emitter,
            )
            output = buf.getvalue()
            self.assertFalse(
                ok,
                f"expected bundle smoke check to fail; output: {output}",
            )
            self.assertIn("status=failed", output)
            self.assertIn("agents/quality-playbook.agent.md", output)

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
            if top in ("SKILL.md", "quality_gate.py",
                       "skill-template.gitignore"):
                # v1.5.7 090u: skill-template.gitignore joined the
                # top-level bundle so the
                # ``scaffolding_missing_gitignore`` remediation can
                # point at <root>/skill-template.gitignore on a
                # channel install (root cause of the 2026-05-25 Keto
                # run5 + NATS run2 Phase-0 friction).
                regions_seen.add(top)
            elif top in ("references", "phase_prompts", "agents", "bin"):
                # v1.5.6 BUG-005: bin/ joined the bundle to ship
                # citation_verifier.py at the install destination so
                # quality_gate.py's soft-import resolves there instead
                # of falling back to WARN.
                regions_seen.add(top)
            else:
                self.fail(
                    f"unexpected top-level destination region: {top!r} "
                    f"(in {dst!r}). Seven regions are supported: "
                    f"SKILL.md, quality_gate.py, "
                    f"skill-template.gitignore, references/, "
                    f"phase_prompts/, agents/, bin/."
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
            {"SKILL.md", "quality_gate.py",
             "skill-template.gitignore", "references",
             "phase_prompts", "agents", "bin"},
            f"expected all seven bundle regions (v1.5.7 090u added "
            f"skill-template.gitignore); got {regions_seen}",
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


class AiToolFlagTests(unittest.TestCase):
    """v1.5.6 instruction 064: --ai-tool <name> flag bypasses
    marker-directory auto-detection and installs to the canonical
    subdirectory for the named tool. Created the marker directory
    if it doesn't exist (Cursor and Copilot don't always create
    their config folder on first project open)."""

    def test_ai_tool_cursor_creates_marker_and_installs(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            self.assertFalse((tmp / ".cursor").exists(), "marker should not pre-exist")
            rc, out = _capture_install(into=tmp, ai_tool="cursor", source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            self.assertTrue((tmp / ".cursor").is_dir(), "marker .cursor/ should be created")
            install_dir = tmp / ".cursor" / "skills" / "quality-playbook"
            self.assertTrue((install_dir / "SKILL.md").is_file())
            self.assertIn("event=ai_tool_explicit", out)
            self.assertIn("ai_tool=cursor", out)
            self.assertIn("marker_created=yes", out)

    def test_ai_tool_claude_creates_marker_and_installs(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            rc, out = _capture_install(into=tmp, ai_tool="claude", source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            self.assertTrue((tmp / ".claude" / "skills" / "quality-playbook" / "SKILL.md").is_file())
            self.assertIn("ai_tool=claude", out)

    def test_ai_tool_copilot_alias_maps_to_github(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            rc, out = _capture_install(into=tmp, ai_tool="copilot", source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            install_dir = tmp / ".github" / "skills" / "quality-playbook"
            self.assertTrue((install_dir / "SKILL.md").is_file())
            self.assertIn("ai_tool=copilot", out)
            self.assertIn("marker=.github", out)

        # Same with --ai-tool github (alias for copilot).
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            rc, out = _capture_install(into=tmp, ai_tool="github", source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            self.assertTrue((tmp / ".github" / "skills" / "quality-playbook" / "SKILL.md").is_file())
            self.assertIn("ai_tool=github", out)
            self.assertIn("marker=.github", out)

    def test_ai_tool_continue_creates_marker_and_installs(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            rc, out = _capture_install(into=tmp, ai_tool="continue", source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            self.assertTrue((tmp / ".continue" / "skills" / "quality-playbook" / "SKILL.md").is_file())
            self.assertIn("ai_tool=continue", out)
            self.assertIn("marker=.continue", out)

    def test_ai_tool_and_target_mutually_exclusive(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            rc, out = _capture_install(
                target=tmp / "explicit-path",
                ai_tool="cursor",
                source_root=REPO_ROOT,
            )
            self.assertEqual(rc, 64)
            self.assertIn("event=refuse", out)
            self.assertIn("target-and-ai-tool-mutually-exclusive", out)

    def test_no_marker_no_ai_tool_no_target_emits_recovery_guidance(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            # No markers, no flags — just --into a bare directory.
            rc, out = _capture_install(into=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 64)
            self.assertIn("event=detection_failed", out)
            self.assertIn("event=install_complete", out)
            self.assertIn("status=failed", out)
            self.assertIn("reason=no_marker_directory_found", out)
            # The verbose-prose recovery block should be available when
            # verbose=True; here we use the default (non-verbose) path,
            # so the structured events are what we assert on.

    def test_intro_message_emitted_on_successful_install(self) -> None:
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            rc, out = _capture_install(into=tmp, ai_tool="cursor", source_root=REPO_ROOT)
            self.assertEqual(rc, 0, out)
            # event=intro must be the FIRST emitted event.
            first_event = next(
                line for line in out.splitlines() if line.startswith("event=")
            )
            self.assertTrue(
                first_event.startswith("event=intro"),
                f"expected event=intro first, got: {first_event}",
            )

    def test_intro_message_emitted_on_detection_failure(self) -> None:
        """The intro should still emit even when detection later fails —
        helps adopters understand what happened before the refusal."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            rc, out = _capture_install(into=tmp, source_root=REPO_ROOT)
            self.assertEqual(rc, 64)
            self.assertIn("event=intro", out)
            # And intro precedes detection_failed.
            intro_pos = out.find("event=intro")
            failed_pos = out.find("event=detection_failed")
            self.assertGreater(intro_pos, -1)
            self.assertGreater(failed_pos, -1)
            self.assertLess(intro_pos, failed_pos)

    def test_argparse_ai_tool_choices(self) -> None:
        """argparse rejects bogus --ai-tool values."""
        import io as _io
        from contextlib import redirect_stderr
        with redirect_stderr(_io.StringIO()):
            with self.assertRaises(SystemExit):
                install_skill.main(["--ai-tool", "bogus-tool"])

    def test_install_function_target_ai_tool_mutex(self) -> None:
        """v1.5.6 fix-up 067 PS-5: argparse-level mutex (--target AND
        --ai-tool both passed via CLI) was tested at
        test_ai_tool_and_target_mutually_exclusive. The function-level
        mutex — calling install(target=X, ai_tool=Y, ...) directly —
        was not, so a programmatic caller could bypass the CLI guard.
        Pin the function-level mutex too."""
        with TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            rc, out = _capture_install(
                target=tmp / "explicit-path",
                ai_tool="cursor",
                source_root=REPO_ROOT,
            )
            self.assertEqual(rc, 64, out)
            self.assertIn("event=refuse", out)
            self.assertIn("target-and-ai-tool-mutually-exclusive", out)


class BundleManifestClosureTests(unittest.TestCase):
    """v1.5.7 instruction 050 A-6.2: install_skill._bundle_files()
    must bundle the full quality_playbook closure so an adopter
    Mode-A run hitting Phase 4's `python3 -m bin.quality_playbook
    semantic-check ...` (phase_prompts/phase4.md:26,43) resolves at
    the install destination instead of ModuleNotFoundError
    (self-bootstrap masked this — cwd is the QPB clone).

    Closure traced (AST) from quality_playbook.py's imports + each
    module's transitive `from .` imports; benchmark_lib was bundled
    in 049 (A-6.1).

    Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160): delete the
    instruction-050 A-6.2 closure block from
    bin/install_skill.py:_bundle_files() (the `qpb_init_src` +
    `for _mod_name in (...)` loop after the benchmark_lib_src block).
    Expected failure: this test fails listing every missing closure
    dest (bin/__init__.py + the six bin/<module>.py). Restore the
    block → passes. Bite verified during instruction 050 development.

    The expected set is a LIST (not a hardcoded count) so a future
    closure addition is added here without a brittle count assertion.
    """

    # 6 modules + __init__.py. benchmark_lib.py is intentionally NOT
    # listed — it is bundled by the separate 049 A-6.1 block; this
    # test pins ONLY the instruction-050 closure additions.
    EXPECTED_CLOSURE_DESTS = (
        "bin/__init__.py",
        "bin/quality_playbook.py",
        "bin/archive_lib.py",
        "bin/council_semantic_check.py",
        "bin/migrate_v1_5_0_layout.py",
        "bin/role_map.py",
        "bin/council_config.py",
    )

    def test_bundle_includes_quality_playbook_closure(self) -> None:
        manifest = install_skill._bundle_files(REPO_ROOT)
        dests = {str(dest) for _src, dest in manifest}
        missing = [
            d for d in self.EXPECTED_CLOSURE_DESTS if d not in dests
        ]
        self.assertEqual(
            missing, [],
            "install_skill._bundle_files() is missing quality_playbook "
            f"closure entries: {missing}. Adopter Mode-A Phase-4 "
            "semantic-check would ModuleNotFoundError. (A-6.2)",
        )

    def test_closure_src_paths_resolve_in_real_qpb_tree(self) -> None:
        """Each bundled closure entry's source path must exist in the
        QPB tree — _bundle_files only appends when src.is_file(), so a
        present manifest entry implies a real source; pin that for
        the closure."""
        manifest = install_skill._bundle_files(REPO_ROOT)
        by_dest = {str(d): s for s, d in manifest}
        for dest in self.EXPECTED_CLOSURE_DESTS:
            self.assertIn(dest, by_dest)
            self.assertTrue(
                Path(by_dest[dest]).is_file(),
                f"closure manifest entry {dest} points at missing "
                f"source {by_dest[dest]}",
            )


if __name__ == "__main__":
    unittest.main()
