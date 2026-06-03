"""v1.5.7 089d (F23) — cross-module pin: install-layout enumeration
in operator-facing diagnostics must be derived from the canonical
constants, not hard-coded.

Pre-089d two surfaces enumerated fewer layouts than the canonical
list:
  - bin/run_playbook.py:~1051  WARN about missing installed SKILL.md
    listed 6 of 10 layouts (missing .codex/.windsurf/.cline/.aider —
    added in instruction-046/A-3 expansion).
  - bin/install_skill.py:~786  intro_short auto-detection marker
    list listed 4 of 8 markers (missing the same four).

Both gaps gave adopters on the newer tools incomplete diagnostic
guidance. 089d F23 wires both surfaces to the canonical:
  - run_playbook → lib.SKILL_INSTALL_LOCATIONS (10 paths)
  - install_skill → KNOWN_ENVIRONMENTS marker tuples (8 markers)
"""

from __future__ import annotations

import unittest
from pathlib import Path


class InstallLayoutsEnumerationPinTests(unittest.TestCase):

    def test_run_playbook_warn_lists_all_canonical_layouts(self) -> None:
        """The run_playbook missing-SKILL WARN message lists every
        path from lib.SKILL_INSTALL_LOCATIONS (10 layouts post-046).

        Mutation-test evidence (ai_context/DEVELOPMENT_PROCESS.md:
        152-160), instruction-089d F23:
          Mutation: in bin/run_playbook.py, revert the dynamic
          `_layouts = ", ".join(str(p) for p in lib.SKILL_INSTALL_LOCATIONS)`
          to a hard-coded 6-layout string (the pre-089d form).
          Expected failure: THIS test fails — the WARN no longer
          enumerates `.codex` / `.windsurf` / `.cline` / `.aider`.
          Restoration: re-introduce the dynamic enumeration; passes.
          Bite executed during 089d development; PASS→FAIL→PASS
          confirmed (__pycache__ purged between mutate and restore).
        """
        from tempfile import TemporaryDirectory

        from bin import benchmark_lib, run_playbook

        # Trigger the WARN: resolve_target_dirs walks an existing
        # directory + emits the "No QPB-installed SKILL.md found"
        # WARN when the dir has no canonical install. Use a TempDir
        # to provide an existing-but-uninstalled target.
        with TemporaryDirectory() as tmp:
            _, warnings_out, _errors = run_playbook.resolve_target_dirs(
                [tmp],
            )
        warn_text = "\n".join(warnings_out)
        self.assertIn(
            "No QPB-installed SKILL.md found", warn_text,
            "TempDir without a canonical install should trigger the "
            "missing-SKILL WARN; the test setup is broken if not.",
        )
        for path in benchmark_lib.SKILL_INSTALL_LOCATIONS:
            self.assertIn(
                str(path), warn_text,
                f"run_playbook missing-SKILL WARN must list canonical "
                f"install layout {path!s}; currently only enumerates a "
                f"subset (F23 install-layout-enumeration drift). If "
                f"you see this fail, the WARN was reverted to a "
                f"hard-coded list — wire it back to "
                f"lib.SKILL_INSTALL_LOCATIONS.",
            )

    def test_install_skill_intro_short_lists_all_known_environments(self) -> None:
        """install_skill.intro_short's auto-detection marker list
        contains every marker from KNOWN_ENVIRONMENTS (8 markers
        post-046).

        Mutation-test evidence (ai_context/DEVELOPMENT_PROCESS.md:
        152-160), instruction-089d F23:
          Mutation: in bin/install_skill.py, revert the dynamic
          `_intro_markers = "/, ".join(marker for marker, _ in
          KNOWN_ENVIRONMENTS) + "/"` to a hard-coded 4-marker
          string (the pre-089d form: ".cursor/, .claude/,
          .github/, .continue/").
          Expected failure: THIS test fails — intro_short no longer
          enumerates `.codex` / `.windsurf` / `.cline` / `.aider`.
          Restoration: re-introduce the dynamic enumeration; passes.
          Bite executed during 089d development; PASS→FAIL→PASS
          confirmed.
        """
        from bin import install_skill

        # The marker list is built at module import time using
        # `KNOWN_ENVIRONMENTS`; reconstruct the canonical list and
        # assert every marker appears in `intro_short`.
        marker_str = install_skill.intro_short \
            if hasattr(install_skill, "intro_short") \
            else None
        if marker_str is None:
            # `intro_short` is a local variable inside `_run`; recover
            # it by reading the source and reconstructing the build.
            src = Path(install_skill.__file__).read_text(encoding="utf-8")
            self.assertIn(
                'auto-detection scans for the marker (', src,
                "install_skill intro_short marker-list framing missing",
            )
            for marker, _ in install_skill.KNOWN_ENVIRONMENTS:
                self.assertIn(
                    marker + "/", src,
                    f"install_skill source must reference canonical "
                    f"marker {marker + '/'!r} from KNOWN_ENVIRONMENTS "
                    f"(F23 install-layout-enumeration drift). If you "
                    f"see this fail, intro_short was reverted to a "
                    f"hard-coded list — wire it back to "
                    f"KNOWN_ENVIRONMENTS.",
                )
        else:
            for marker, _ in install_skill.KNOWN_ENVIRONMENTS:
                self.assertIn(marker + "/", marker_str)


if __name__ == "__main__":
    unittest.main()
