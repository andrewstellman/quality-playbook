"""v1.5.7 instruction 077 (addendum r3 §3.3.2/§3.3.3 / acceptance
#14) — per-platform command runnability.

The agent lifts the validator's `command` field verbatim and runs it
on the detected platform (addendum §3.3.4: no translation, no
free-form construction). So the emitted commands must be
platform-correct:

* Unix forms parse via shlex.split without raising.
* No Windows form contains the bare token `python3` (the Windows
  interpreter is `python` or `py -3`).
* No windows_cmd form contains `&&` (cmd.exe chaining is the exact
  portability footgun the addendum §1.1 install-path incident was
  rooted in; the addendum forbids it in cmd forms).
* Backslash path separators are preserved in Windows install/path
  commands.
* python_pkg_missing resolves the <pkg> substitution per platform
  (python3 on Unix, py -3 on Windows).
"""

from __future__ import annotations

import shlex
import unittest

from bin import qpb_validate as v

_WINDOWS_KEYS = ("windows-powershell", "windows-cmd")
# Codes whose command is a real shell command (not an informational
# directive / URL pointer) — the python3/&& lint applies to these.
_SHELL_COMMAND_CODES = {
    "install_absent", "install_partial", "install_wrong_ai_tool",
    "install_version_skew", "scaffolding_missing_gitignore",
    "scaffolding_missing_reference_docs", "python_pkg_missing",
}


class RemediationCommandRunnabilityTests(unittest.TestCase):

    def test_no_bare_python3_in_any_windows_form(self) -> None:
        """No Windows command tokenizes to a bare `python3`.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-077 —
        BITE EXECUTED during instruction-077 development:
          Mutation: in bin/qpb_validate.py change _RUN_INSTALLER_WIN
          from `python <clone>\\bin\\install_skill.py ...` to
          `python3 <clone>\\bin\\install_skill.py ...`.
          Observed failure (purged __pycache__ first):
            FAIL: test_no_bare_python3_in_any_windows_form
            AssertionError: 'python3' unexpectedly found in
            ['python3', '<clone>/bin/install_skill.py', '--into',
            '<target>', '--ai-tool', '<tool>'] :
            install_absent/windows-powershell has a bare 'python3'
            token: 'python3 \\bin\\install_skill.py ...' — Windows
            uses 'python' or 'py -3'
          Restoration: literal restored to `python`; test PASS again.
        """
        for code in v.FINDING_CATALOG:
            for plat in _WINDOWS_KEYS:
                cmd = v.command_for_platform(code, plat)
                tokens = cmd.replace("\\", "/").split()
                self.assertNotIn(
                    "python3", tokens,
                    f"{code}/{plat} has a bare 'python3' token: {cmd!r} "
                    "— Windows uses 'python' or 'py -3'")

    def test_no_double_ampersand_in_cmd_forms(self) -> None:
        for code in v.FINDING_CATALOG:
            cmd = v.command_for_platform(code, "windows-cmd")
            self.assertNotIn(
                "&&", cmd,
                f"{code}/windows-cmd contains '&&' (forbidden for "
                f"cmd.exe forms): {cmd!r}")

    def test_windows_install_paths_use_backslashes(self) -> None:
        """The installer/path commands address Windows paths with
        backslash separators (placeholders are substituted with real
        backslash paths at emit time)."""
        for code in ("install_absent", "install_partial",
                     "install_version_skew", "install_wrong_ai_tool",
                     "scaffolding_missing_gitignore",
                     "scaffolding_missing_reference_docs"):
            for plat in _WINDOWS_KEYS:
                cmd = v.command_for_platform(code, plat)
                self.assertIn("\\", cmd,
                              f"{code}/{plat} lost backslash separators: "
                              f"{cmd!r}")

    def test_unix_shell_commands_shlex_parse(self) -> None:
        for code in v.FINDING_CATALOG:
            for plat in ("macos", "linux"):
                cmd = v.command_for_platform(code, plat)
                try:
                    shlex.split(cmd)
                except ValueError as exc:
                    self.fail(f"{code}/{plat} not shlex-parseable: "
                              f"{exc} :: {cmd!r}")

    def test_python_pkg_substitution_per_platform(self) -> None:
        unix = v.command_for_platform("python_pkg_missing", "macos",
                                      pkg="tiktoken")
        win = v.command_for_platform("python_pkg_missing",
                                     "windows-powershell", pkg="tiktoken")
        self.assertIn("tiktoken", unix)
        self.assertIn("tiktoken", win)
        self.assertTrue(unix.startswith("python3 -m pip"),
                        f"unix pkg command unexpected: {unix!r}")
        self.assertTrue(win.startswith("py -3 -m pip"),
                        f"windows pkg command unexpected: {win!r}")
        self.assertNotIn("<pkg>", unix)
        self.assertNotIn("<pkg>", win)

    def test_shell_command_codes_are_real_commands(self) -> None:
        """The codes the python3/&& lint applies to actually produce
        a shell command token on Unix (sanity that the lint isn't
        vacuously skipping everything)."""
        for code in _SHELL_COMMAND_CODES:
            cmd = v.command_for_platform(code, "macos")
            first = shlex.split(cmd)[0]
            self.assertIn(first, {"python3", "cat", "mkdir"},
                          f"{code} unexpected leading token: {cmd!r}")


if __name__ == "__main__":
    unittest.main()
