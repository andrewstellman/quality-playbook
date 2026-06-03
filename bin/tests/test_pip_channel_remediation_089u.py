"""v1.5.7 089u — channel-aware `qpb_validate.py` remediation tests.

The validator's `FINDING_CATALOG` install-command and `verify_with`
strings vary with the adopter's invocation channel, communicated via
the `QPB_CHANNEL` env var:

- **unset / "clone"** — the canonical pre-089u clone form
  (`python3 <clone>/bin/install_skill.py …`, `python <root>/bin/
  qpb_validate.py <target>`). This must be **byte-identical** to the
  pre-089u output (back-compat).
- **"pip"** — `uvx quality-playbook install …` (and the `--force`
  variant), `uvx quality-playbook validate <target>`. Set by the
  `quality_playbook_cli` shim before invoking `install_skill.main()`,
  so any validator run inside the pip-channel flow emits the
  pip-correct remediation.
- **"npm"** (089v block C, now implemented; 089w aligned the
  surface to ``--ai-tool``) — emits the ``npx quality-playbook
  init --ai-tool=<tool>`` form. The full npm channel-remediation
  pins live in ``test_npm_channel_remediation_089v.py``; this
  089u file keeps only the pip + back-compat pins (its original
  scope).

**Mutation-bite evidence** (per ai_context/DEVELOPMENT_PROCESS.md):
delete the `_channel()` early-return on `"pip"` in `_platform_table`
(so the helper always returns the clone forms). Expected failure:
`test_pip_channel_emits_uvx_remediation` fails because the catalog
under `QPB_CHANNEL=pip` returns the clone string. Restore by
reverting. Bite executed PASS → FAIL → PASS during 089u development.
"""

from __future__ import annotations

import importlib
import os
import unittest


class ChannelAwareRemediation089uTests(unittest.TestCase):
    """Pin the channel-keyed remediation strings."""

    def setUp(self) -> None:
        # Remember the operator's actual QPB_CHANNEL (likely unset)
        # so we can restore it.
        self._prior_channel = os.environ.get("QPB_CHANNEL")

    def tearDown(self) -> None:
        if self._prior_channel is None:
            os.environ.pop("QPB_CHANNEL", None)
        else:
            os.environ["QPB_CHANNEL"] = self._prior_channel
        # Reload qpb_validate so the next test gets a catalog
        # consistent with whatever env it sets up.
        from bin import qpb_validate
        importlib.reload(qpb_validate)

    def _reload_catalog(self, channel: str | None) -> dict:
        if channel is None:
            os.environ.pop("QPB_CHANNEL", None)
        else:
            os.environ["QPB_CHANNEL"] = channel
        from bin import qpb_validate
        importlib.reload(qpb_validate)
        return qpb_validate.FINDING_CATALOG

    def test_unset_channel_emits_clone_form_byte_identical(self) -> None:
        """The canonical pre-089u clone strings — every platform
        slot in every install-* catalog entry — must be EXACTLY
        what the validator emits when QPB_CHANNEL is unset
        (back-compat default).

        This is the load-bearing back-compat pin: existing
        `qpb_validate` tests assert specific clone-form strings;
        this test confirms those strings are unchanged under the
        new channel-aware machinery."""
        catalog = self._reload_catalog(None)
        clone_mac = "python3 <clone>/bin/install_skill.py --into <target> --ai-tool <tool>"
        clone_win = "python <clone>\\bin\\install_skill.py --into <target> --ai-tool <tool>"
        revalidate = "python <root>/bin/qpb_validate.py <target>"

        for key in ("install_absent", "install_wrong_ai_tool"):
            with self.subTest(key=key):
                cmds = catalog[key]["commands"]
                self.assertEqual(cmds["macos"], clone_mac)
                self.assertEqual(cmds["linux"], clone_mac)
                self.assertEqual(cmds["windows_powershell"], clone_win)
                self.assertEqual(cmds["windows_cmd"], clone_win)
                self.assertEqual(catalog[key]["verify_with"], revalidate)

        for key in ("install_partial", "install_version_skew"):
            with self.subTest(key=key):
                cmds = catalog[key]["commands"]
                self.assertEqual(cmds["macos"], clone_mac + " --force")
                self.assertEqual(cmds["linux"], clone_mac + " --force")
                self.assertEqual(cmds["windows_powershell"], clone_win + " --force")
                self.assertEqual(cmds["windows_cmd"], clone_win + " --force")
                self.assertEqual(catalog[key]["verify_with"], revalidate)

    def test_pip_channel_emits_uvx_remediation(self) -> None:
        """With ``QPB_CHANNEL=pip`` set, the catalog must emit the
        ``uvx quality-playbook install …`` form for every platform
        slot, and ``uvx quality-playbook validate <target>`` for
        verify_with. (``uvx`` is cross-platform, so every platform
        key collapses to the same string.)

        Mutation candidate: remove the ``if channel == "pip"``
        branch in ``_platform_table``. Expected failure: this test
        fires because the catalog returns the clone string under
        ``QPB_CHANNEL=pip``."""
        catalog = self._reload_catalog("pip")
        pip_install = "uvx quality-playbook install --into <target> --ai-tool <tool>"
        pip_install_force = pip_install + " --force"
        pip_revalidate = "uvx quality-playbook validate <target>"

        # install_absent + install_wrong_ai_tool — non-force form.
        for key in ("install_absent", "install_wrong_ai_tool"):
            with self.subTest(key=key):
                for slot in ("macos", "linux", "windows_powershell",
                             "windows_cmd"):
                    self.assertEqual(
                        catalog[key]["commands"][slot], pip_install,
                        f"089u pip channel: {key}.{slot} must use "
                        f"the uvx form, not the clone form.",
                    )
                self.assertEqual(
                    catalog[key]["verify_with"], pip_revalidate,
                )

        # install_partial + install_version_skew — --force form.
        for key in ("install_partial", "install_version_skew"):
            with self.subTest(key=key):
                for slot in ("macos", "linux", "windows_powershell",
                             "windows_cmd"):
                    self.assertEqual(
                        catalog[key]["commands"][slot], pip_install_force,
                        f"089u pip channel: {key}.{slot} must use "
                        f"the uvx --force form, not the clone form.",
                    )

if __name__ == "__main__":
    unittest.main()
