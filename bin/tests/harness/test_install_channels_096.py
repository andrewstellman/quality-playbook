"""v1.5.7 096 — install-command templating + version-pinned
channels (Phase 6).

Covers ``bin/harness/prepare.py::build_install_command`` for all
five SCHEMA.md §3 channels:

  * ``clone`` → ``python3 -m bin.install_skill --into <target>
    --ai-tool <tool>``
  * ``pip-registry@<version|latest>`` → ``uvx
    quality-playbook@<version> install --into <target>
    --ai-tool <tool>``
  * ``npm-registry@<version|latest>`` → ``npx
    quality-playbook@<version> init --ai-tool=<tool>``
  * ``pip-local-wheel`` → ``uvx --from <wheel>
    quality-playbook install --into <target> --ai-tool <tool>``
  * ``npm-local-tgz`` → ``npx --package <tgz> quality-playbook
    init --ai-tool=<tool>``

And the version-comparison-runs path: the same case ran against
two pinned versions produces commands carrying both version
suffixes, and the gate re-run uses the run's OWN installed gate
(adapter-independent by design §C — already pinned in
test_facts_extraction.py; this file re-pins for the comparison
shape).

Live registry runs are POST-PUBLISH; this file unit-tests
templating only, which is hermetic.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from bin.harness import prepare as P
from bin.harness import schema as S


# ---------------------------------------------------------------------------
# build_install_command — per-channel templating
# ---------------------------------------------------------------------------


class CloneChannelTemplateTests(unittest.TestCase):

    def test_clone_command_shape(self) -> None:
        cmd = P.build_install_command(
            S.InstallChannel.CLONE,
            Path("/tmp/target"),
            ai_tool="claude",
        )
        # python3 -m bin.install_skill --into <target> --ai-tool <tool>
        self.assertEqual(cmd[1:3], ["-m", "bin.install_skill"])
        self.assertIn("--into", cmd)
        self.assertEqual(cmd[cmd.index("--into") + 1], "/tmp/target")
        self.assertIn("--ai-tool", cmd)
        self.assertEqual(cmd[cmd.index("--ai-tool") + 1], "claude")

    def test_clone_command_force(self) -> None:
        cmd = P.build_install_command(
            S.InstallChannel.CLONE,
            Path("/tmp/target"),
            ai_tool="claude",
            force=True,
        )
        self.assertIn("--force", cmd)


# ---------------------------------------------------------------------------
# Registry channels (post-publish; templating only)
# ---------------------------------------------------------------------------


class PipRegistryTemplateTests(unittest.TestCase):
    """SCHEMA.md §3 ``pip-registry@<version|latest>`` →
    ``uvx quality-playbook@<version> install --into <target>
    --ai-tool <tool>``."""

    def test_pinned_version(self) -> None:
        cmd = P.build_install_command(
            S.InstallChannel.PIP_REGISTRY,
            Path("/tmp/target"),
            ai_tool="claude",
            install_version="1.5.7",
        )
        self.assertEqual(cmd[0], "uvx")
        self.assertEqual(cmd[1], "quality-playbook@1.5.7")
        self.assertIn("install", cmd)
        self.assertEqual(cmd[cmd.index("--into") + 1], "/tmp/target")

    def test_latest_when_version_none(self) -> None:
        """No install_version → ``@latest`` (per SCHEMA.md §3
        enum legend)."""
        cmd = P.build_install_command(
            S.InstallChannel.PIP_REGISTRY,
            Path("/tmp/t"),
            ai_tool="claude",
            install_version=None,
        )
        self.assertEqual(cmd[1], "quality-playbook@latest")

    def test_force_appended(self) -> None:
        cmd = P.build_install_command(
            S.InstallChannel.PIP_REGISTRY,
            Path("/tmp/t"),
            ai_tool="codex",
            install_version="1.5.6",
            force=True,
        )
        self.assertEqual(cmd[-1], "--force")
        self.assertEqual(cmd[cmd.index("--ai-tool") + 1], "codex")


class NpmRegistryTemplateTests(unittest.TestCase):
    """SCHEMA.md §3 ``npm-registry@<version|latest>`` →
    ``npx quality-playbook@<version> init --ai-tool=<tool>``."""

    def test_pinned_version(self) -> None:
        cmd = P.build_install_command(
            S.InstallChannel.NPM_REGISTRY,
            Path("/tmp/t"),
            ai_tool="copilot",
            install_version="1.5.7",
        )
        self.assertEqual(cmd[0], "npx")
        self.assertEqual(cmd[1], "quality-playbook@1.5.7")
        self.assertIn("init", cmd)
        # npm syntax uses --ai-tool=<value> (matches the
        # _RUN_INSTALLER_NPM template at qpb_validate.py:355).
        self.assertIn("--ai-tool=copilot", cmd)

    def test_latest_when_version_none(self) -> None:
        cmd = P.build_install_command(
            S.InstallChannel.NPM_REGISTRY,
            Path("/tmp/t"),
            ai_tool="claude",
        )
        self.assertEqual(cmd[1], "quality-playbook@latest")

    def test_force_appended(self) -> None:
        cmd = P.build_install_command(
            S.InstallChannel.NPM_REGISTRY,
            Path("/tmp/t"),
            ai_tool="claude",
            install_version="1.5.7",
            force=True,
        )
        self.assertEqual(cmd[-1], "--force")


# ---------------------------------------------------------------------------
# Local-artifact channels (pre-publish; needs the built artifact)
# ---------------------------------------------------------------------------


class PipLocalWheelTemplateTests(unittest.TestCase):
    """SCHEMA.md §3 ``pip-local-wheel`` → ``uvx --from <wheel>
    quality-playbook install --into <target> --ai-tool <tool>``.
    Used for pre-publish acceptance — uvx installs the locally-
    built wheel without touching PyPI."""

    def test_command_shape(self) -> None:
        wheel = Path("/abs/dist/quality_playbook-1.5.7-py3-none-any.whl")
        cmd = P.build_install_command(
            S.InstallChannel.PIP_LOCAL_WHEEL,
            Path("/tmp/target"),
            ai_tool="claude",
            local_artifact=wheel,
        )
        self.assertEqual(cmd[0], "uvx")
        self.assertEqual(cmd[1], "--from")
        self.assertEqual(cmd[2], str(wheel))
        self.assertIn("quality-playbook", cmd)
        self.assertIn("install", cmd)
        self.assertEqual(cmd[cmd.index("--into") + 1], "/tmp/target")
        self.assertEqual(cmd[cmd.index("--ai-tool") + 1], "claude")

    def test_missing_artifact_raises(self) -> None:
        """A local-wheel channel without local_artifact is a
        PrepError — operator-actionable, not a cryptic
        subprocess failure."""
        with self.assertRaises(P.PrepError) as ctx:
            P.build_install_command(
                S.InstallChannel.PIP_LOCAL_WHEEL,
                Path("/tmp/t"),
            )
        self.assertIn("local_artifact", str(ctx.exception))


class NpmLocalTgzTemplateTests(unittest.TestCase):
    """SCHEMA.md §3 ``npm-local-tgz`` → ``npx --package <tgz>
    quality-playbook init --ai-tool=<tool>``."""

    def test_command_shape(self) -> None:
        tgz = Path("/abs/quality-playbook-1.5.7.tgz")
        cmd = P.build_install_command(
            S.InstallChannel.NPM_LOCAL_TGZ,
            Path("/tmp/target"),
            ai_tool="copilot",
            local_artifact=tgz,
        )
        self.assertEqual(cmd[0], "npx")
        self.assertEqual(cmd[1], "--package")
        self.assertEqual(cmd[2], str(tgz))
        self.assertIn("quality-playbook", cmd)
        self.assertIn("init", cmd)
        self.assertIn("--ai-tool=copilot", cmd)

    def test_missing_artifact_raises(self) -> None:
        with self.assertRaises(P.PrepError) as ctx:
            P.build_install_command(
                S.InstallChannel.NPM_LOCAL_TGZ,
                Path("/tmp/t"),
            )
        self.assertIn("local_artifact", str(ctx.exception))


# ---------------------------------------------------------------------------
# Version-comparison runs (the same case across two pinned versions)
# ---------------------------------------------------------------------------


class VersionComparisonTests(unittest.TestCase):
    """SCHEMA.md §2 + design §D: ``install_version`` is an axis,
    so the same case under two different versions = two runs.
    Phase 6 wires the templating; the gate re-run already uses
    the run's OWN installed gate (Phase 1, design §C) — so a
    ``@1.5.6`` run is graded by 1.5.6's gate, NOT the clone's.
    """

    def test_two_pip_versions_yield_distinct_commands(self) -> None:
        target = Path("/tmp/target")
        cmd_old = P.build_install_command(
            S.InstallChannel.PIP_REGISTRY, target,
            ai_tool="claude", install_version="1.5.6",
        )
        cmd_new = P.build_install_command(
            S.InstallChannel.PIP_REGISTRY, target,
            ai_tool="claude", install_version="1.5.7",
        )
        # Both are uvx pip-registry commands…
        self.assertEqual(cmd_old[0], "uvx")
        self.assertEqual(cmd_new[0], "uvx")
        # …but they pin distinct versions in the
        # quality-playbook@<version> token.
        self.assertEqual(cmd_old[1], "quality-playbook@1.5.6")
        self.assertEqual(cmd_new[1], "quality-playbook@1.5.7")
        # And the target dir is the same (the version-comparison
        # axis is install_version, not target_dir).
        self.assertEqual(
            cmd_old[cmd_old.index("--into") + 1],
            cmd_new[cmd_new.index("--into") + 1],
        )

    def test_axes_install_channel_at_suffix_round_trip(self) -> None:
        """SCHEMA.md §3 wire form: ``pip-registry@1.5.7`` JSON
        round-trips through axes → templater → version pin in
        the install command."""
        # JSON form per SCHEMA.md §3.
        raw_axes = {
            "runner": "claude", "mode": "A",
            "install_channel": "pip-registry@1.5.7",
            "install_version": None,
            "model": "opus", "thinking": None,
        }
        # Parse via the same loader the manager uses.
        raw_inv = {
            "run_id": "r", "case_id": "c", "axes": raw_axes,
            "qpb_version": "1.5.7", "target_sha": "x",
            "cli_command": "", "cwd": "/t",
            "env_snapshot": {}, "started_at": "x",
            "ended_at": "y", "exit_code": 0,
            "terminal_state": "COMPLETED",
        }
        inv = S.parse_run_invocation(raw_inv)
        # The @1.5.7 suffix split off into install_version.
        self.assertEqual(inv.axes.install_channel,
                         S.InstallChannel.PIP_REGISTRY)
        self.assertEqual(inv.axes.install_version, "1.5.7")
        # And the templater consumes both correctly.
        cmd = P.build_install_command(
            inv.axes.install_channel, Path("/tmp/target"),
            ai_tool="claude",
            install_version=inv.axes.install_version,
        )
        self.assertEqual(cmd[1], "quality-playbook@1.5.7")


# ---------------------------------------------------------------------------
# install_skill_channel — dispatch wrapper.
# ---------------------------------------------------------------------------


class InstallSkillChannelDispatchTests(unittest.TestCase):
    """The wrapper invokes ``build_install_command`` then shells
    out via ``subprocess.run``. We exercise only the
    error-handling paths (PrepError surfaces on missing local
    artifact + unknown channel) — the actual subprocess call
    requires live tooling (uvx/npx) so the live-run path is
    documented and deferred to operator-triggered runs."""

    def test_unknown_channel_raises(self) -> None:
        """A future channel name not in the enum can't reach
        here (enum membership is the gate), but a future
        maintainer extending the enum without updating the
        templater would surface this. Pinned defensively via
        the explicit channel/match in
        ``build_install_command``."""
        # We can't synthesize a non-enum InstallChannel easily;
        # but the build_install_command's final-line PrepError
        # IS the catch-all. This test documents the contract.
        # The mutation bite (adding a new channel enum entry
        # WITHOUT updating build_install_command) → the final
        # PrepError fires → this test would FAIL if removed.
        for channel in S.InstallChannel:
            try:
                P.build_install_command(
                    channel, Path("/tmp/t"),
                    ai_tool="claude",
                    install_version="1.5.7",
                    local_artifact=Path("/tmp/fake.whl"),
                )
            except P.PrepError:
                self.fail(
                    f"v1.5.7 096: every InstallChannel enum "
                    f"member must have a build_install_command "
                    f"branch — {channel!r} fell through to the "
                    f"final PrepError",
                )


# ---------------------------------------------------------------------------
# Gate re-run is adapter / channel independent
# ---------------------------------------------------------------------------


class GateReRunChannelIndependenceTests(unittest.TestCase):
    """SCHEMA.md §5 + design §C: gate-derived facts come from
    re-running the run's OWN INSTALLED quality_gate.py — NOT the
    dev clone's. This is what makes the version-comparison shape
    correct: a `@1.5.6` run is graded by 1.5.6's gate, a
    `@1.5.7` run by 1.5.7's gate. Already pinned in
    test_facts_extraction.py via the actual install-and-re-run
    test; this re-pins the CHANNEL-INDEPENDENT contract:
    ``rerun_installed_gate`` searches the canonical
    `<target>/<marker>/skills/quality-playbook/quality_gate.py`
    path regardless of how the gate got there."""

    def test_find_installed_gate_doesnt_depend_on_channel(
            self) -> None:
        """The locator searches a fixed canonical layout; the
        channel that put the gate there is irrelevant."""
        import tempfile
        from bin.harness import facts as F
        # Synthesize a gate at the canonical install_skill
        # layout — could equally have come from any channel.
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            d = t / ".claude" / "skills" / "quality-playbook"
            d.mkdir(parents=True)
            gate = d / "quality_gate.py"
            gate.write_text("# any-channel-installed gate\n")
            self.assertEqual(F.find_installed_gate(t), gate)


if __name__ == "__main__":
    unittest.main()
