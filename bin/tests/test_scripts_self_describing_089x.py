"""v1.5.7 089x — the meta-test that enforces the universal
no-args-safe + self-describing invariant for every ``bin/**/*.py``.

The 089x discoverability feature: a user can run ANY bin script
bare and learn what it does + how it fits in a playbook run,
without any side effects (no files written, no network hit, no
state mutated). This test discovers every ``bin/**/*.py`` and
asserts:

1. **Exit code 0** on no-args invocation.
2. **Stdout contains the version string** (``Quality Playbook
   v<version>``) — verifies the script went through
   ``_purpose.print_purpose`` or ``_purpose.print_attribution_
   banner``, both of which embed the version.
3. **Stdout contains the literal label** ``Role in a playbook
   run:`` — the per-script PURPOSE banner's role line.
4. **Stdout contains the attribution footer** (``by Andrew
   Stellman`` + the GitHub URL).
5. **NO files created or modified** in the temp cwd — the
   safety guarantee. Any script that writes a file on no-args is
   a 089x halt-condition violation.

**Invocation form**: ``python3 -m bin.<dotted-module-name>`` is
the canonical form (the form ``python3 -m bin.run_playbook
--help`` is documented as everywhere). It guarantees `bin` is
on sys.path so cross-module imports resolve uniformly.

**Mutation-bite** (per ai_context/DEVELOPMENT_PROCESS.md): remove
the ``if not _argv_list: print_purpose(...); return 0`` block
from any one script's main(). Expected failure: this test fires
for that script — either rc != 0 (because main() proceeded into
argparse and required-arg validation), or the stdout assertion
fails (because the script's normal output doesn't include the
purpose-banner format). Restored by reverting. Bite executed
PASS → FAIL → PASS during 089x development.

**Skipped scripts**: the meta-test discovers every ``bin/**/*.py``
EXCEPT:
- ``__init__.py`` (package marker; no executable content).
- The test files themselves (``bin/tests/test_*.py``,
  ``bin/skill_derivation/tests/*``).
- The shared helper ``bin/_purpose.py`` is included — its own
  ``__main__`` block prints the lib-form banner.
- Shell helpers (this test is Python-only — the discovery glob
  matches ``*.py``).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = REPO_ROOT / "bin"


def _discover_scripts() -> list[tuple[str, Path]]:
    """Discover every bin/**/*.py except tests + __init__. Return
    list of ``(dotted_module_name, path)`` tuples so the unittest
    output prints the module name."""
    scripts: list[tuple[str, Path]] = []
    for path in sorted(BIN_DIR.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT)
        parts = rel.with_suffix("").parts
        # Exclude __init__.py at any nesting level.
        if path.name == "__init__.py":
            continue
        # Exclude tests/ subtrees.
        if "tests" in parts:
            continue
        dotted = ".".join(parts)
        scripts.append((dotted, path))
    return scripts


# Module-level constant so the unittest report shows each script as
# a subTest with a stable name.
SCRIPTS = _discover_scripts()


class ScriptsSelfDescribing089xTests(unittest.TestCase):
    """Meta-test for the 089x universal no-args-safe + self-
    describing invariant."""

    # Sanity: there should be more than a handful of scripts. If
    # discovery returns 0 the test would vacuously pass.
    def test_discovery_returns_at_least_20_scripts(self) -> None:
        """Pin a lower bound on script count so a future repo
        restructure that hides bin/ from discovery is caught."""
        self.assertGreaterEqual(
            len(SCRIPTS), 20,
            f"089x meta-test: discovered only {len(SCRIPTS)} "
            f"bin/**/*.py scripts; expected ≥20. The discovery "
            f"glob may be broken — scripts: {[d for d, _ in SCRIPTS]}",
        )

    def test_every_script_is_no_args_safe_and_self_describing(
            self) -> None:
        """For every discovered bin script, run it with no args via
        ``python -m`` from a temp cwd, then assert exit 0 + stdout
        purpose-banner contents + no-side-effects."""
        version_re = re.compile(r"Quality Playbook v[0-9]+\.[0-9]+(?:\.[0-9]+)?\b")
        for dotted, path in SCRIPTS:
            with self.subTest(script=dotted):
                with tempfile.TemporaryDirectory(
                    prefix="qpb_089x_meta_"
                ) as tmp:
                    tmp_path = Path(tmp)
                    # Snapshot of tmp dir contents (recursive) BEFORE
                    # running the script; assert identical after.
                    before = sorted(p.relative_to(tmp_path)
                                    for p in tmp_path.rglob("*"))
                    # PYTHONPATH must include the repo root so
                    # `python -m bin.<name>` resolves from a temp
                    # cwd (otherwise `bin` isn't on sys.path).
                    env = os.environ.copy()
                    existing_pp = env.get("PYTHONPATH", "")
                    env["PYTHONPATH"] = (
                        str(REPO_ROOT) +
                        (os.pathsep + existing_pp if existing_pp else "")
                    )
                    proc = subprocess.run(
                        [sys.executable, "-m", dotted],
                        cwd=str(tmp_path),
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=30,
                    )
                    stdout = proc.stdout.decode("utf-8", errors="replace")
                    stderr = proc.stderr.decode("utf-8", errors="replace")
                    self.assertEqual(
                        proc.returncode, 0,
                        f"089x: `python -m {dotted}` (no args) must "
                        f"exit 0. rc={proc.returncode}. "
                        f"stdout:\n{stdout}\nstderr:\n{stderr}",
                    )
                    self.assertRegex(
                        stdout, version_re,
                        f"089x: stdout of `python -m {dotted}` "
                        f"(no args) must contain a "
                        f"`Quality Playbook v<ver>` line. "
                        f"stdout was:\n{stdout!r}",
                    )
                    self.assertIn(
                        "Role in a playbook run:", stdout,
                        f"089x: stdout of `python -m {dotted}` "
                        f"(no args) must contain the literal "
                        f"`Role in a playbook run:` label. "
                        f"stdout was:\n{stdout!r}",
                    )
                    self.assertIn(
                        "by Andrew Stellman", stdout,
                        f"089x: stdout of `python -m {dotted}` "
                        f"(no args) must contain the attribution "
                        f"footer (`by Andrew Stellman`). "
                        f"stdout was:\n{stdout!r}",
                    )
                    self.assertIn(
                        "https://github.com/andrewstellman/quality-playbook",
                        stdout,
                        f"089x: stdout of `python -m {dotted}` "
                        f"(no args) must contain the GitHub URL "
                        f"as part of the attribution footer.",
                    )
                    # Safety pin: no files created/modified in cwd.
                    after = sorted(p.relative_to(tmp_path)
                                   for p in tmp_path.rglob("*"))
                    self.assertEqual(
                        before, after,
                        f"089x: `python -m {dotted}` (no args) "
                        f"created or modified files in the temp "
                        f"cwd. The 089x invariant: no-args must be "
                        f"SAFE — no side effects. Before: {before!r} "
                        f"After: {after!r}",
                    )


if __name__ == "__main__":
    unittest.main()
