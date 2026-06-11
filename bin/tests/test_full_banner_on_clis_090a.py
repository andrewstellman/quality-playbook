"""v1.5.7 090a — pin the full attribution banner on user-facing
CLI no-args + ``--help``; pin its ABSENCE on library no-args.

090a revises the 089x banner split: the full 80-wide attribution
banner (name + two-line tagline + GitHub URL + Apache license)
now appears on every user-facing CLI's no-args invocation AND at
the top of its ``--help`` output (both stdout). Pre-090a only
the lightweight one-line footer was shown on those paths;
the full ceremonial banner was reserved for install-success +
Mode-B run start/end (and stayed there — 090a only ADDS the
new CLI emission, doesn't move the existing ones).

**Libraries (``kind="library"``) are explicitly out of scope** —
they keep the lightweight purpose banner + footer. The
full ceremonial banner on every library's bare-run would be
repetitive noise (libraries aren't user-invoked commands; the
CLI-vs-library line is the 090a design point).

This test pins BOTH directions:
- For every named CLI: full banner appears on no-args stdout
  AND on ``--help`` stdout.
- For at least two library modules: full banner is ABSENT on
  no-args stdout (the lightweight footer is sufficient).

**Mutation bites** (per ai_context/DEVELOPMENT_PROCESS.md):
- Remove a CLI's ``print_command_intro`` / ``print_help_banner``
  call → ``test_every_cli_shows_full_banner_on_noargs`` (or the
  --help twin) fails for that CLI.
- Add the full banner to a library's ``__main__`` block (e.g.
  swap ``print_purpose`` for ``print_command_intro`` in
  ``role_map``) →
  ``test_libraries_do_not_show_full_banner_on_noargs`` fails.

Both bites executed PASS → FAIL → PASS during 090a development.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


# Distinctive substrings from the FULL 80-wide attribution banner
# (089l text; 090a doesn't change BANNER_TEXT). Either substring on
# its own would catch most regressions; checking both makes
# false-positives effectively impossible.
_BANNER_TAGLINE = "AI code review is good. Quality engineering is better."
_BANNER_LICENSE_LINE = "Licensed under the Apache License"


# 16 user-facing CLIs per 089x Task 2 (qpb_config also uses
# kind="command" since 089x; the 090a instruction's rule is
# "the ones whose print_purpose is called with kind=command",
# so it comes along).
CLI_DOTTED_NAMES = [
    "bin.install_skill",
    "bin.run_playbook",
    "bin.qpb_validate",
    "bin.classify_project",
    "bin.quality_playbook",
    "bin.reference_docs_ingest",
    "bin.validate_phase_artifacts",
    "bin.metrics_reconstruction",
    "bin.regression_replay",
    "bin.visualize_calibration",
    "bin.archive_lib",
    "bin.council_semantic_check",
    "bin.migrate_v1_5_0_layout",
    "bin.build_channel_package",
    "bin.bootstrap_self_audit_docs",
    "bin.qpb_config",
    "bin.skill_derivation",
    # v1.5.9 1B: worker-side heartbeat CLI + orchestrator-side harness
    # tick CLI (both self-describe via the same _purpose banner).
    "bin.qpb_heartbeat",
    "bin.qpb_harness_tick",
]

# Library modules that must NOT show the full banner. Sampling
# two is enough to bite the "added to a library" regression;
# every other library is covered by the 089x meta-test (which
# asserts they don't crash and emit the expected purpose
# banner).
LIBRARY_DOTTED_NAMES = [
    "bin.role_map",
    "bin.benchmark_lib",
]


def _run_module(dotted: str, *extra_args: str,
                 timeout: int = 30):
    """Run ``python -m <dotted>`` from a temp cwd with
    PYTHONPATH=REPO_ROOT. Returns ``(returncode, stdout, stderr)``."""
    env = os.environ.copy()
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(REPO_ROOT)
        + (os.pathsep + existing_pp if existing_pp else "")
    )
    with tempfile.TemporaryDirectory(prefix="qpb_090a_") as tmp:
        proc = subprocess.run(
            [sys.executable, "-m", dotted, *extra_args],
            cwd=str(tmp),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", errors="replace"),
        proc.stderr.decode("utf-8", errors="replace"),
    )


class FullBannerOnClis090aTests(unittest.TestCase):
    """Pin the 090a contract: full banner on CLI no-args + --help;
    NOT on libraries."""

    def test_every_cli_shows_full_banner_on_noargs(self) -> None:
        """For every user-facing CLI, ``python -m bin.<name>`` (no
        args) prints the full attribution banner to stdout. Both
        the tagline AND the Apache license line must appear."""
        for dotted in CLI_DOTTED_NAMES:
            with self.subTest(cli=dotted):
                rc, stdout, stderr = _run_module(dotted)
                self.assertEqual(
                    rc, 0,
                    f"090a: `python -m {dotted}` (no args) must "
                    f"exit 0. rc={rc} stdout=\n{stdout}\nstderr=\n"
                    f"{stderr}",
                )
                self.assertIn(
                    _BANNER_TAGLINE, stdout,
                    f"090a: no-args stdout of `python -m {dotted}` "
                    f"must contain the full-banner tagline.\n"
                    f"stdout=\n{stdout}",
                )
                self.assertIn(
                    _BANNER_LICENSE_LINE, stdout,
                    f"090a: no-args stdout of `python -m {dotted}` "
                    f"must contain the full-banner Apache license "
                    f"line.\nstdout=\n{stdout}",
                )

    def test_every_cli_shows_full_banner_on_help(self) -> None:
        """For every user-facing CLI, ``python -m bin.<name> --help``
        prints the full attribution banner to stdout above
        argparse's usage/description/epilog."""
        for dotted in CLI_DOTTED_NAMES:
            with self.subTest(cli=dotted):
                rc, stdout, stderr = _run_module(dotted, "--help")
                # argparse exits 0 after emitting --help.
                self.assertEqual(
                    rc, 0,
                    f"090a: `python -m {dotted} --help` must exit "
                    f"0. rc={rc} stderr=\n{stderr}",
                )
                self.assertIn(
                    _BANNER_TAGLINE, stdout,
                    f"090a: --help stdout of `python -m {dotted}` "
                    f"must contain the full-banner tagline.\n"
                    f"stdout=\n{stdout}",
                )
                self.assertIn(
                    _BANNER_LICENSE_LINE, stdout,
                    f"090a: --help stdout of `python -m {dotted}` "
                    f"must contain the full-banner Apache license "
                    f"line.\nstdout=\n{stdout}",
                )
                # The banner must appear ABOVE the help content.
                # Most CLIs use argparse (whose help starts with
                # `usage: `); a few have hand-rolled help (e.g.
                # quality_playbook's top-level lists "Subcommands:")
                # and bootstrap_self_audit_docs prints a one-line
                # "Usage:" hint. The contract is "banner first,
                # help content after" — verify the banner's
                # tagline appears in the FIRST QUARTER of stdout
                # so any of those help shapes work.
                banner_idx = stdout.find(_BANNER_TAGLINE)
                self.assertLess(
                    banner_idx, len(stdout) // 4 + len(_BANNER_TAGLINE),
                    f"090a: full banner must appear at the TOP of "
                    f"--help stdout (banner index {banner_idx}, "
                    f"stdout length {len(stdout)}). stdout=\n{stdout}",
                )

    def test_libraries_do_not_show_full_banner_on_noargs(self) -> None:
        """For at least two library modules, ``python -m bin.<lib>``
        (no args) MUST NOT contain the full-banner tagline.

        The 090a CLI-vs-library line is deliberate: libraries
        aren't user-invoked commands and the full ceremonial box
        on every internal library's bare-run would be repetitive
        noise. Libraries keep the lightweight purpose banner +
        attribution footer (the 089x contract)."""
        for dotted in LIBRARY_DOTTED_NAMES:
            with self.subTest(lib=dotted):
                rc, stdout, stderr = _run_module(dotted)
                self.assertEqual(
                    rc, 0,
                    f"library {dotted} must exit 0 on no-args. "
                    f"rc={rc} stderr=\n{stderr}",
                )
                self.assertNotIn(
                    _BANNER_TAGLINE, stdout,
                    f"090a: library {dotted} no-args stdout must "
                    f"NOT contain the full-banner tagline (would "
                    f"violate the CLI-vs-library line). "
                    f"stdout=\n{stdout}",
                )
                self.assertNotIn(
                    _BANNER_LICENSE_LINE, stdout,
                    f"090a: library {dotted} no-args stdout must "
                    f"NOT contain the full-banner Apache license "
                    f"line. stdout=\n{stdout}",
                )


if __name__ == "__main__":
    unittest.main()
