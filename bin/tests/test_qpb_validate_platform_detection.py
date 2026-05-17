"""v1.5.7 instruction 077 (addendum r3 §3.3.3 / acceptance #13) —
platform_kind() + Windows shell heuristic correctness.

The validator emits the platform-correct command, not a template the
agent must translate (addendum §3.3.4). That guarantee is only as
good as platform detection. These tests pin the §3.3.3 decision
matrix under mocked sys.platform / os.name and the Windows shell
heuristic under mocked env vars.
"""

from __future__ import annotations

import unittest
from unittest import mock

from bin import qpb_validate as v


class PlatformKindTests(unittest.TestCase):

    def test_macos(self) -> None:
        """sys.platform='darwin' -> 'macos'.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-077 —
        BITE EXECUTED during instruction-077 development:
          Mutation: in bin/qpb_validate.py:platform_kind(), change
          `if sys.platform == "darwin": return "macos"` to
          `return "linux"`.
          Observed failure (purged __pycache__ first):
            AssertionError: 'linux' != 'macos'
          Restoration: line restored; test PASS again.
        """
        with mock.patch.object(v.sys, "platform", "darwin"):
            self.assertEqual(v.platform_kind(), "macos")

    def test_linux(self) -> None:
        with mock.patch.object(v.sys, "platform", "linux"):
            self.assertEqual(v.platform_kind(), "linux")

    def test_windows_via_sys_platform(self) -> None:
        with mock.patch.object(v.sys, "platform", "win32"):
            self.assertEqual(v.platform_kind(), "windows")

    def test_windows_via_os_name_fallback(self) -> None:
        # sys.platform something exotic but os.name == 'nt'.
        with mock.patch.object(v.sys, "platform", "cygwin"), \
             mock.patch.object(v.os, "name", "nt"):
            self.assertEqual(v.platform_kind(), "windows")

    def test_unknown(self) -> None:
        with mock.patch.object(v.sys, "platform", "aix"), \
             mock.patch.object(v.os, "name", "posix"):
            self.assertEqual(v.platform_kind(), "unknown")


class WindowsShellKindTests(unittest.TestCase):

    def test_powershell_when_psmodulepath_set_msystem_unset(self) -> None:
        self.assertEqual(
            v.windows_shell_kind({"PSModulePath": r"C:\Modules",
                                  "COMSPEC": r"C:\Windows\system32\cmd.exe"}),
            "powershell")

    def test_cmd_when_only_comspec(self) -> None:
        self.assertEqual(
            v.windows_shell_kind({"COMSPEC": r"C:\Windows\system32\cmd.exe"}),
            "cmd")

    def test_git_bash_when_msystem_set(self) -> None:
        self.assertEqual(
            v.windows_shell_kind({"MSYSTEM": "MINGW64",
                                  "PSModulePath": r"C:\Modules"}),
            "git_bash")

    def test_ambiguous_when_no_signals(self) -> None:
        self.assertEqual(v.windows_shell_kind({}), "ambiguous")


if __name__ == "__main__":
    unittest.main()
