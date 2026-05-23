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

    def test_python_pkg_import_to_dist_map_is_empty_in_089y(self) -> None:
        """v1.5.7 089y: adopters need ZERO third-party Python packages.
        The shipped runtime (installer / gate / validators /
        skill_derivation) is stdlib-only; the pre-089y
        `PYTHONPATH_PKG_IMPORT_TO_DIST` carried `tiktoken` and `yaml`
        (PyYAML) entries that nothing in the shipped code imports
        (tiktoken is dev-test-only; yaml has zero importers). 089y
        emptied the map so a fresh install validates `status=ok`
        with no `python_pkg_missing` findings.

        The python_pkg substitution machinery (FINDING_CATALOG entry
        `python_pkg_missing` + `command_for_platform` substitution)
        is preserved — a future required dep can be added by writing
        ONE entry to this map. The substitution test
        (`test_python_pkg_substitution_per_platform` above) exercises
        that machinery with a literal `pkg=` argument; this test
        pins the 089y contract: the map is empty.

        Mutation candidate: re-add `{"tiktoken": "tiktoken"}` to
        ``PYTHON_PKG_IMPORT_TO_DIST``. Expected failure: this test
        fires because the map is no longer empty."""
        self.assertEqual(
            v.PYTHON_PKG_IMPORT_TO_DIST, {},
            "089y: PYTHON_PKG_IMPORT_TO_DIST must be empty — adopters "
            "use no third-party Python packages. The shipped runtime "
            "is stdlib-only; verify any new entry against the actual "
            "imports in bin/ + .github/skills/quality_gate/.",
        )

        # The substitution mechanism still works with a literal pkg=
        # arg — kept so 089y can add a required dep cleanly later
        # without restructuring.
        unix = v.command_for_platform("python_pkg_missing", "macos",
                                      pkg="some_future_pkg")
        win = v.command_for_platform("python_pkg_missing",
                                     "windows-powershell", pkg="some_future_pkg")
        self.assertIn("some_future_pkg", unix)
        self.assertIn("some_future_pkg", win)
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


class PkgMgrAwareRemediationTests(unittest.TestCase):
    """Instruction 077b F2 — addendum r3 §3.3.3: the validator detects
    brew/apt/dnf/winget/choco and 'prefers commands that match what's
    actually installed' for python_version_too_old and
    ai_cli_not_on_path. The static (no-pkg_mgrs) path is retained as
    the acceptance #12/#14 fallback and must stay non-empty."""

    def test_python_version_too_old_uses_detected_pkg_mgr(self) -> None:
        """dnf is preferred over apt on Linux when both are detected;
        the OS-only hardcode codex flagged is gone.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-077b —
        BITE EXECUTED during instruction-077b development:
          Mutation: in bin/qpb_validate.py:_pkg_mgr_aware_command(),
          reorder the Linux branch so `if has("apt")` is tested
          BEFORE `if has("dnf")`.
          Observed failure (purged __pycache__ first):
            FAIL: test_python_version_too_old_uses_detected_pkg_mgr
            AssertionError: 'sudo apt install python3.12' != 'sudo dnf
            install python3.12'
            (assertEqual(actual, expected) prints first != second;
            after the swap actual==apt, expected==dnf — dnf must win
            when both present)
          Restoration: dnf-before-apt order restored; PASS again.
        """
        f = v.command_for_platform
        self.assertEqual(
            f("python_version_too_old", "linux",
              pkg_mgrs={"dnf": True, "apt": True}),
            "sudo dnf install python3.12")
        self.assertEqual(
            f("python_version_too_old", "linux",
              pkg_mgrs={"dnf": False, "apt": True}),
            "sudo apt install python3.12")
        self.assertIn(
            "python.org",
            f("python_version_too_old", "linux", pkg_mgrs={}))
        self.assertEqual(
            f("python_version_too_old", "macos", pkg_mgrs={"brew": True}),
            "brew install python@3.12")
        win_choco = f("python_version_too_old", "windows-cmd",
                      pkg_mgrs={"choco": True, "winget": True})
        self.assertEqual(win_choco, "choco install python --version=3.12.0")
        self.assertNotIn("&&", win_choco)
        self.assertNotIn("python3", win_choco.split())
        self.assertEqual(
            f("python_version_too_old", "windows-powershell",
              pkg_mgrs={"choco": False, "winget": True}),
            "winget install Python.Python.3.12")

    def test_install_ai_cli_uses_detected_pkg_mgr(self) -> None:
        """v1.5.7 089f necessary-consequence reconciliation: the
        Copilot CLI (`gh`/`copilot`/`github` tool key) remediation
        advice changed shape — GitHub deprecated `gh copilot` on
        2025-10-25; QPB now recommends the standalone `copilot` CLI
        first with the legacy `gh extension install github/gh-copilot`
        form as a secondary option during the grace period. The
        previous single-command assertions (e.g., "sudo apt install
        gh") were pinned to behavior that no longer exists; the new
        assertions check for substring presence of both the new and
        legacy install routes.
        """
        f = v.command_for_platform
        # Linux + apt: new CLI install-script preferred, apt+gh-extension grace-period fallback.
        linux_apt = f("ai_cli_not_on_path", "linux",
                      pkg_mgrs={"apt": True}, tool="gh")
        self.assertIn("gh.io/copilot-install", linux_apt,
                      "preferred new-CLI install route must be present")
        self.assertIn("sudo apt install gh", linux_apt,
                      "legacy apt fallback must remain available during grace period")
        self.assertIn("gh extension install github/gh-copilot", linux_apt)
        # Linux + dnf: same shape with dnf swapped in.
        linux_dnf = f("ai_cli_not_on_path", "linux",
                      pkg_mgrs={"dnf": True, "apt": False}, tool="gh")
        self.assertIn("gh.io/copilot-install", linux_dnf)
        self.assertIn("sudo dnf install gh", linux_dnf)
        self.assertIn("gh extension install github/gh-copilot", linux_dnf)
        # Windows + winget: new CLI preferred + legacy gh.cli fallback.
        win = f("ai_cli_not_on_path", "windows-cmd",
                pkg_mgrs={"winget": True}, tool="gh")
        self.assertIn("winget install GitHub.Copilot", win,
                      "preferred new-CLI winget install must be present")
        self.assertIn("winget install GitHub.cli", win,
                      "legacy gh.cli winget install must remain available")
        # Windows + choco: choco-install-gh as grace-period fallback.
        win_choco = f("ai_cli_not_on_path", "windows-powershell",
                      pkg_mgrs={"winget": False, "choco": True},
                      tool="gh")
        self.assertIn("copilot-cli", win_choco,
                      "preferred new-CLI mention must be present")
        self.assertIn("choco install gh", win_choco,
                      "legacy choco-install-gh must remain available")
        # Non-Copilot tools unchanged (claude, codex).
        self.assertIn(
            "docs.claude.com",
            f("ai_cli_not_on_path", "linux", pkg_mgrs={}, tool="claude"))
        self.assertIn(
            "openai/codex",
            f("ai_cli_not_on_path", "macos", pkg_mgrs={}, tool="codex"))

    def test_no_pkg_mgrs_falls_back_to_static_catalog(self) -> None:
        """Acceptance #12/#14 path: with no pkg_mgrs the static
        template is used and stays non-empty for every platform."""
        for code in ("python_version_too_old", "ai_cli_not_on_path"):
            for plat in ("macos", "linux", "windows-powershell",
                         "windows-cmd"):
                cmd = v.command_for_platform(code, plat)
                self.assertTrue(cmd.strip())
                self.assertNotIn("python3", cmd.split())


if __name__ == "__main__":
    unittest.main()
