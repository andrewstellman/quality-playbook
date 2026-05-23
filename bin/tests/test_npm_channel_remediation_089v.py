"""v1.5.7 089v + 089w — npm channel-remediation tests for ``qpb_validate.py``.

089u wired the pip channel into ``qpb_validate.py``'s
``FINDING_CATALOG``; the ``npm`` branch was stubbed to fall through
to the clone form with an in-source TODO. 089v completed the npm
branch; 089w aligned its surface to the same ``--ai-tool`` flag
pip + the Python installer use (one vocabulary across both
channels and all docs). ``QPB_CHANNEL=npm`` now emits

    npx quality-playbook init --ai-tool=<tool>             (install)
    npx quality-playbook init --ai-tool=<tool> --force     (force variant)
    npx quality-playbook validate <target>                  (verify_with)

…in every platform slot (npx is cross-platform, so every
mac/linux/windows_* slot collapses to the same string).

This test file pins:

1. ``QPB_CHANNEL=npm`` emits the npx form in every install-* catalog
   entry × every platform slot.
2. ``QPB_CHANNEL=npm`` ``verify_with`` is the npx validate form.
3. The pip channel (089u) is byte-for-byte unchanged — regression
   pin so a future channel refactor that breaks pip back-compat
   fires immediately. (The 089u file already pins clone-unset
   back-compat; this file adds the explicit pip-still-unchanged
   pin alongside the new npm pins.)

**Mutation-bite evidence** (per ai_context/DEVELOPMENT_PROCESS.md):
delete the ``if channel == "npm"`` branch in ``_platform_table``
(so the helper falls through to the clone form for npm again).
Expected failure: ``test_npm_channel_emits_npx_install_form``
fails because the catalog under ``QPB_CHANNEL=npm`` returns the
clone string. Restore by reverting. Bite executed
PASS → FAIL → PASS during 089v development.
"""

from __future__ import annotations

import importlib
import os
import unittest


class NpmChannelRemediation089vTests(unittest.TestCase):
    """Pin the npm-channel remediation strings and the pip-channel
    regression."""

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

    # --- npm pins ---

    def test_npm_channel_emits_npx_install_form(self) -> None:
        """With ``QPB_CHANNEL=npm``, every install-* catalog entry's
        every platform slot must emit ``npx quality-playbook init
        --ai-tool=<tool>`` (or the ``--force`` variant for the
        partial/version-skew entries). 089w: the flag is
        ``--ai-tool`` — same vocabulary as the pip channel and the
        Python installer; the shim does NOT recognize any other
        flag spelling for the tool name.

        Mutation candidate: remove the ``if channel == "npm"``
        branch in ``_platform_table``. Expected failure: this test
        fires because the catalog returns the clone string under
        ``QPB_CHANNEL=npm``."""
        catalog = self._reload_catalog("npm")
        npm_install = "npx quality-playbook init --ai-tool=<tool>"
        npm_install_force = npm_install + " --force"

        # install_absent + install_wrong_ai_tool — non-force form.
        for key in ("install_absent", "install_wrong_ai_tool"):
            with self.subTest(key=key):
                for slot in ("macos", "linux", "windows_powershell",
                             "windows_cmd"):
                    self.assertEqual(
                        catalog[key]["commands"][slot], npm_install,
                        f"089v npm channel: {key}.{slot} must use "
                        f"the npx form, not the clone or pip form.",
                    )

        # install_partial + install_version_skew — --force form.
        for key in ("install_partial", "install_version_skew"):
            with self.subTest(key=key):
                for slot in ("macos", "linux", "windows_powershell",
                             "windows_cmd"):
                    self.assertEqual(
                        catalog[key]["commands"][slot],
                        npm_install_force,
                        f"089v npm channel: {key}.{slot} must use "
                        f"the npx --force form.",
                    )

    def test_npm_channel_verify_with_is_npx_validate_form(self) -> None:
        """The ``verify_with`` string under ``QPB_CHANNEL=npm`` must
        be ``npx quality-playbook validate <target>`` — the same
        verb surface the Node shim exposes."""
        catalog = self._reload_catalog("npm")
        npm_revalidate = "npx quality-playbook validate <target>"
        for key in ("install_absent", "install_partial",
                    "install_wrong_ai_tool", "install_version_skew"):
            with self.subTest(key=key):
                self.assertEqual(
                    catalog[key]["verify_with"], npm_revalidate,
                    f"089v npm channel: {key}.verify_with must use "
                    f"the npx validate form.",
                )

    # --- pip regression pin (089u back-compat across 089v changes) ---

    def test_pip_channel_still_emits_uvx_form_after_089v(self) -> None:
        """Re-pin the 089u pip-channel behavior after 089v lands the
        npm branch — the npm wiring must NOT regress the pip form
        in any catalog entry × platform slot.

        Mutation candidate: swap the ``if channel == "pip"`` and
        ``if channel == "npm"`` branches in ``_platform_table``.
        Expected failure: this test fires because the pip form
        now returns the npx string."""
        catalog = self._reload_catalog("pip")
        pip_install = "uvx quality-playbook install --into <target> --ai-tool <tool>"
        pip_install_force = pip_install + " --force"
        pip_revalidate = "uvx quality-playbook validate <target>"

        for key in ("install_absent", "install_wrong_ai_tool"):
            with self.subTest(key=key):
                for slot in ("macos", "linux", "windows_powershell",
                             "windows_cmd"):
                    self.assertEqual(
                        catalog[key]["commands"][slot], pip_install,
                    )
                self.assertEqual(
                    catalog[key]["verify_with"], pip_revalidate,
                )

        for key in ("install_partial", "install_version_skew"):
            with self.subTest(key=key):
                for slot in ("macos", "linux", "windows_powershell",
                             "windows_cmd"):
                    self.assertEqual(
                        catalog[key]["commands"][slot],
                        pip_install_force,
                    )


if __name__ == "__main__":
    unittest.main()
