"""v1.5.7 150 — `npx --yes` for npm-local-tgz install (root cause of
the chi-codex ABORTED_PREP chain).

146's install.log surfaced the real cause: npx prompts `Need to
install the following packages … Ok to proceed? (y)` for a tarball
not already in the prefix cache, and the captured subprocess has no
TTY → it blocks on stdin forever → the prep timeout fires. `--yes`
skips the prompt. `--prefer-offline` (142) stays as a secondary
optimization. The flag is npx-specific, so it must NOT leak into the
pip channels.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from bin.harness import prepare as P
from bin.harness.schema import InstallChannel

TGZ = Path("/abs/quality-playbook-1.5.7.tgz")
WHL = Path("/abs/quality_playbook-1.5.7-py3-none-any.whl")


def _npm_cmd():
    return P.build_install_command(
        InstallChannel.NPM_LOCAL_TGZ, Path("/tmp/t"),
        ai_tool="claude", local_artifact=TGZ)


class NpxYesFlagTests(unittest.TestCase):

    def test_npm_local_tgz_argv_contains_yes_before_package(
            self) -> None:
        """--yes present AND before --package. Mutation-bite: drop
        --yes ⇒ this fails (and the install hangs on the prompt)."""
        cmd = _npm_cmd()
        self.assertIn("--yes", cmd)
        self.assertLess(cmd.index("--yes"), cmd.index("--package"))

    def test_npm_local_tgz_keeps_prefer_offline_too(self) -> None:
        """Both --yes and --prefer-offline present before --package
        (guards the 142 + 150 invariants together). Mutation-bite:
        drop --prefer-offline ⇒ this fails."""
        cmd = _npm_cmd()
        self.assertIn("--prefer-offline", cmd)
        self.assertLess(cmd.index("--yes"), cmd.index("--package"))
        self.assertLess(cmd.index("--prefer-offline"),
                        cmd.index("--package"))

    def test_other_channels_do_not_get_yes(self) -> None:
        """--yes is npx-specific; pip/clone channels must NOT get it.
        Mutation-bite: a refactor that sprays --yes everywhere ⇒
        this fails."""
        pip = P.build_install_command(
            InstallChannel.PIP_LOCAL_WHEEL, Path("/tmp/t"),
            ai_tool="claude", local_artifact=WHL)
        self.assertNotIn("--yes", pip)
        clone = P.build_install_command(
            InstallChannel.CLONE, Path("/tmp/t"), ai_tool="claude")
        self.assertNotIn("--yes", clone)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
