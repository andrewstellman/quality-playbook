"""v1.5.7 156 — NPM channels (NPM_LOCAL_TGZ + NPM_REGISTRY) must
invoke the install subprocess with ``cwd=<target_dir>`` so the npm
shim's auto-injected ``--into <cwd>`` resolves to the right place.

The 2026-05-29 ship-readiness retest demonstrated the bug end-to-end:
codex Mode B runs (``harness_runs/20260529T235425Z/run-03`` and
``20260529T201847Z/run-02``) reported ``verdict=None`` with
``facts_error: installed quality_gate.py not found under
.../target``. install.log named ``target=/Users/.../QPB`` (the
harness's source tree, where the operator's own tooling had already
installed the skill) → every file copy ``status=skipped`` → the run
target got nothing.

Root cause: ``install_skill_channel`` set ``cwd=None`` for all
non-CLONE channels. The npm shim (``bin/quality-playbook.js
::translateArgv``) auto-injects ``--into <cwd>`` for the install
verb (an end-user "install into here" convenience that becomes a
foot-gun in the harness's batch case). With cwd inherited from the
harness, ``--into`` resolved to QPB's source tree.

Fix shape (Option 2 per the instruction): set
``cwd=str(target_dir)`` for NPM channels. The argv itself stays
unchanged (Option 1 — passing explicit ``--into`` — would conflict
with the shim's auto-injection and result in a duplicate ``--into``
in the final Python argv). PIP channels are unchanged (they pass
``--into <target>`` explicitly via build_install_command and don't
depend on cwd). CLONE is unchanged (uses ``_qpb_clone_root()``).
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from bin.harness import prepare as P
from bin.harness.schema import InstallChannel


# ---------------------------------------------------------------------------
# install_skill_channel cwd convention
# ---------------------------------------------------------------------------


def _run_install(channel: InstallChannel, target_dir: Path,
                 *, local_artifact: Path | None = None
                 ) -> mock.MagicMock:
    """Drive ``install_skill_channel`` with subprocess.run mocked;
    return the patch so the caller can inspect call args. Forces the
    subprocess to "succeed" (returncode=0)."""
    mock_proc = mock.MagicMock(
        returncode=0, stdout="ok\n", stderr="")
    with mock.patch.object(P.subprocess, "run",
                            return_value=mock_proc) as m_run:
        P.install_skill_channel(
            channel, target_dir, ai_tool="codex",
            local_artifact=local_artifact,
        )
    return m_run


class NpmChannelCwdTests(unittest.TestCase):

    def test_npm_local_tgz_uses_target_dir_as_cwd(self) -> None:
        # Mutation-bite target: dropping the
        # `elif channel in (NPM_LOCAL_TGZ, NPM_REGISTRY)` branch makes
        # cwd revert to None → assertion fails.
        target = Path("/tmp/test-156-target")
        m_run = _run_install(
            InstallChannel.NPM_LOCAL_TGZ, target,
            local_artifact=Path("/tmp/quality-playbook.tgz"))
        self.assertEqual(m_run.call_count, 1)
        self.assertEqual(m_run.call_args.kwargs["cwd"], str(target))

    def test_npm_registry_uses_target_dir_as_cwd(self) -> None:
        # Symmetric fix for NPM_REGISTRY.
        target = Path("/tmp/test-156-target")
        m_run = _run_install(InstallChannel.NPM_REGISTRY, target)
        self.assertEqual(m_run.call_count, 1)
        self.assertEqual(m_run.call_args.kwargs["cwd"], str(target))

    def test_pip_local_wheel_keeps_none_cwd(self) -> None:
        # Negative-space coverage: PIP channels pass --into <target>
        # explicitly in build_install_command; cwd stays None.
        m_run = _run_install(
            InstallChannel.PIP_LOCAL_WHEEL,
            Path("/tmp/test-156-target"),
            local_artifact=Path("/tmp/x.whl"))
        self.assertIsNone(m_run.call_args.kwargs["cwd"])

    def test_pip_registry_keeps_none_cwd(self) -> None:
        m_run = _run_install(
            InstallChannel.PIP_REGISTRY,
            Path("/tmp/test-156-target"))
        self.assertIsNone(m_run.call_args.kwargs["cwd"])

    def test_clone_channel_still_uses_qpb_clone_root(self) -> None:
        m_run = _run_install(
            InstallChannel.CLONE,
            Path("/tmp/test-156-target"))
        # CLONE's cwd is _qpb_clone_root() — not None, not the
        # target. Confirm by computing the expected value.
        self.assertEqual(m_run.call_args.kwargs["cwd"],
                         str(P._qpb_clone_root()))


# ---------------------------------------------------------------------------
# build_install_command argv shape preserved (negative-space coverage)
# ---------------------------------------------------------------------------


class NpmArgvShapeUnchangedTests(unittest.TestCase):
    """v1.5.7 156 chose Option 2 (cwd-only) rather than Option 1
    (insert --into into the argv). The argv that install_skill_channel
    passes to subprocess.run must therefore be IDENTICAL to pre-156 —
    same `init --ai-tool=<tool>` shape. Asserting this protects
    against a future "let's also add --into for safety" change that
    would conflict with the shim's auto-injection."""

    def test_npm_local_tgz_argv_uses_init_verb_no_into(self) -> None:
        cmd = P.build_install_command(
            InstallChannel.NPM_LOCAL_TGZ,
            Path("/tmp/test-156-target"),
            ai_tool="codex",
            local_artifact=Path("/tmp/quality-playbook.tgz"),
        )
        self.assertIn("init", cmd)
        self.assertIn("--ai-tool=codex", cmd)
        # The shim auto-injects --into <cwd>; harness must NOT also
        # pass --into (would duplicate in the final Python argv).
        self.assertNotIn("--into", cmd)
        self.assertNotIn("install", cmd)

    def test_npm_registry_argv_uses_init_verb_no_into(self) -> None:
        cmd = P.build_install_command(
            InstallChannel.NPM_REGISTRY,
            Path("/tmp/test-156-target"),
            ai_tool="codex", install_version="1.5.7",
        )
        self.assertIn("init", cmd)
        self.assertIn("--ai-tool=codex", cmd)
        self.assertNotIn("--into", cmd)
        self.assertNotIn("install", cmd)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
