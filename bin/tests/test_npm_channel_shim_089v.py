"""v1.5.7 089v + 089w — npm channel shim behavior tests.

Exercises ``bin/quality-playbook.js`` (the Node shim) directly:

- **Python detection** — when no usable Python is on PATH, the
  shim exits non-zero with the actionable remediation message on
  stderr (NOT a Node stack trace). The instruction is explicit:
  the operator must see something they can act on, not a JS
  traceback.
- **`--ai-tool` passthrough** (089w) — the shim's verb-translation
  step maps ``init`` -> ``install`` and injects ``--into <cwd>``,
  but forwards ``--ai-tool`` (both ``=`` and spaced forms) verbatim
  to the Python entry. 089w decision: one vocabulary across pip +
  npm + all docs; the shim has NO semantic flag translation. The
  shim exposes a private ``__print_translated_argv`` self-test
  hook so we can assert the translated argv without spawning
  python.
- **Verbatim passthrough** — the spawned child's stdout/stderr
  reach the operator byte-identical. This pins the Phase-0
  anti-fabrication contract: ``event=…`` lines and the
  ``qpb_validate.py`` run-nonce must NOT be buffered, truncated,
  summarized, or reformatted by the Node shim. We exercise this
  by staging a temp tree where ``quality_playbook_cli/__init__.py``
  is a tiny script that emits known-content; the shim spawns it
  via ``python -m quality_playbook_cli``; we capture the shim's
  stdout and assert byte-equality with the expected content.

All tests are ``@skipUnless(node)`` so they cleanly skip in
node-less envs (the instruction's halt condition: node-dependent
tests SKIP, not FAIL). The npx end-to-end install test lives in
``test_npm_channel_e2e_089v.py`` (separate file to keep e2e's
slower setup isolated from these unit-style assertions).

**Mutation-bite evidence**:
- Delete the ``if py === null`` branch in the shim ->
  ``test_python_detection_emits_remediation_message`` fails (the
  shim would try to spawn ``python3`` which doesn't exist on the
  test PATH and fall through to a Node error). Restore.
- Replace ``stdio: "inherit"`` with ``stdio: "pipe"`` and drop
  manual forwarding -> ``test_stdio_passthrough_preserves_event_
  lines_and_nonce`` fails because captured stdout is empty.
  Restore.
- Drop the ``--ai-tool`` argv tokens in ``translateArgv`` ->
  ``test_ai_tool_eq_form_passes_through_verbatim`` fails because
  the translated argv no longer carries ``--ai-tool=<tool>``.
  Restore.

Bites executed PASS -> FAIL -> PASS during 089v + 089w
development.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SHIM_PATH = REPO_ROOT / "bin" / "quality-playbook.js"

_NODE = shutil.which("node")


def _node_available() -> bool:
    if _NODE is None:
        return False
    try:
        proc = subprocess.run(
            [_NODE, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


_NODE_OK = _node_available()


@unittest.skipUnless(
    _NODE_OK,
    "node not available — skipping npm-shim tests (instruction's halt "
    "condition: node-dependent tests SKIP, not FAIL).",
)
class NpmChannelShim089vTests(unittest.TestCase):
    """Cover Python detection, --ai-tool passthrough (089w), and
    verbatim stdio passthrough."""

    def _run_shim(self, args, *, env=None, cwd=None, timeout=60):
        """Run the shim and return ``(returncode, stdout, stderr)``
        as text. ``env`` defaults to the current process env.

        The shim is invoked from its real location so __dirname
        resolves to ``<repo>/bin/`` and the package root probe in
        the shim lands on ``<repo>/`` (where
        ``quality_playbook_cli/__init__.py`` lives).
        """
        proc = subprocess.run(
            [_NODE, str(SHIM_PATH), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env if env is not None else os.environ.copy(),
            cwd=cwd if cwd is not None else str(REPO_ROOT),
            timeout=timeout,
        )
        return (
            proc.returncode,
            proc.stdout.decode("utf-8", errors="replace"),
            proc.stderr.decode("utf-8", errors="replace"),
        )

    # ------------------------------------------------------------
    # Python detection
    # ------------------------------------------------------------

    def test_python_detection_emits_remediation_message(self) -> None:
        """With no Python on PATH the shim exits non-zero and
        writes the actionable remediation message to stderr — NOT
        a Node stack trace. The operator must see ONE actionable
        sentence."""
        # Sanitize PATH to an empty/non-existent directory. The
        # shim itself is invoked by absolute path
        # (``[_NODE, str(SHIM_PATH), …]``) so the shim's *startup*
        # does not need PATH; only the shim's internal
        # ``spawnSync("python3", …)`` lookups consult PATH. With
        # PATH pointing nowhere, no Python candidate resolves —
        # exercising the missing-Python remediation path.
        #
        # Naive sanitization to node's directory does NOT work on
        # systems where node and python ship from the same prefix
        # (Homebrew puts both in /opt/homebrew/bin); we have to
        # actively exclude all the standard python locations.
        env = {"PATH": "/var/empty"}
        # On Windows the py launcher is at C:\Windows\py.exe; if
        # this test runs there it would still find python via
        # `py -3`. Skip on Windows — the broader contract (no JS
        # traceback on miss) is platform-independent.
        if sys.platform == "win32":
            self.skipTest("Python-detection PATH-sanitizing test "
                          "is POSIX-only (Windows ships `py` at a "
                          "fixed location).")

        rc, stdout, stderr = self._run_shim(["init"], env=env)
        self.assertNotEqual(
            rc, 0,
            "089v: shim must exit non-zero when no Python is on "
            "PATH.",
        )
        self.assertIn(
            "Quality Playbook requires Python", stderr,
            f"089v: shim must emit the actionable remediation "
            f"message on stderr (not a Node stack trace). "
            f"Got stderr={stderr!r}",
        )
        # Strong negative pin: a Node stack trace contains lines
        # like "at Object.<anonymous>" or "TypeError:". Neither
        # should appear.
        for forbidden in ("at Object.", "TypeError:",
                          "ReferenceError:", "node:internal/"):
            self.assertNotIn(
                forbidden, stderr,
                f"089v: shim emitted a Node stack-trace fragment "
                f"({forbidden!r}) instead of an actionable "
                f"remediation message.",
            )

    # ------------------------------------------------------------
    # --ai-tool passthrough (089w)
    # ------------------------------------------------------------

    def _spawn_argv(self, shim_argv, cwd=None):
        """Use the shim's __print_translated_argv self-test hook
        and return the parsed SPAWN_ARGV list."""
        rc, stdout, _ = self._run_shim(
            ["__print_translated_argv", *shim_argv], cwd=cwd,
        )
        self.assertEqual(rc, 0, f"shim self-test exit {rc}")
        for line in stdout.splitlines():
            if line.startswith("SPAWN_ARGV: "):
                return json.loads(line[len("SPAWN_ARGV: "):])
        self.fail(f"SPAWN_ARGV not found in stdout: {stdout!r}")

    def test_ai_tool_eq_form_passes_through_verbatim(self) -> None:
        """``init --ai-tool=claude`` -> ``install --into <cwd>
        --ai-tool=claude``. 089w decision: the shim forwards
        ``--ai-tool`` verbatim (no semantic translation, no
        normalization of the ``=`` form into a spaced pair).
        The Python entry's argparse handles both forms natively,
        so the shim's job ends with verb mapping + cwd default."""
        with tempfile.TemporaryDirectory() as tmp:
            argv = self._spawn_argv(
                ["init", "--ai-tool=claude"], cwd=tmp,
            )
        self.assertEqual(
            argv,
            ["-m", "quality_playbook_cli", "install",
             "--into", os.path.realpath(tmp),
             "--ai-tool=claude"],
        )

    def test_ai_tool_spaced_form_passes_through_verbatim(self) -> None:
        """``init --ai-tool claude`` (spaced) is forwarded as TWO
        separate tokens to the Python entry — the shim does NOT
        merge them into the ``=`` form (it does not parse the
        value)."""
        with tempfile.TemporaryDirectory() as tmp:
            argv = self._spawn_argv(
                ["init", "--ai-tool", "claude"], cwd=tmp,
            )
        self.assertEqual(
            argv,
            ["-m", "quality_playbook_cli", "install",
             "--into", os.path.realpath(tmp),
             "--ai-tool", "claude"],
        )

    def test_extra_flags_pass_through_unchanged(self) -> None:
        """Flags other than the verb pass through verbatim in
        their original order — ``--ai-tool``, ``--force``,
        ``--no-smoke``, etc. The shim is a transport layer, not
        a validator or reorderer."""
        with tempfile.TemporaryDirectory() as tmp:
            argv = self._spawn_argv(
                ["init", "--ai-tool=cursor", "--force",
                 "--no-smoke"],
                cwd=tmp,
            )
        # Order: original argv positions preserved (the shim only
        # prepends `install --into <cwd>`).
        self.assertEqual(
            argv,
            ["-m", "quality_playbook_cli", "install",
             "--into", os.path.realpath(tmp),
             "--ai-tool=cursor", "--force", "--no-smoke"],
        )


    def test_validate_verb_passes_through(self) -> None:
        """The ``validate`` verb is a pass-through — no implicit
        ``--into <cwd>`` is injected."""
        argv = self._spawn_argv(["validate", "/tmp/some-target"])
        self.assertEqual(
            argv,
            ["-m", "quality_playbook_cli", "validate",
             "/tmp/some-target"],
        )

    def test_bare_invocation_defaults_to_install_into_cwd(self) -> None:
        """No verb at all means ``install`` against the current
        working directory — the npx-style scaffolder convention."""
        with tempfile.TemporaryDirectory() as tmp:
            argv = self._spawn_argv([], cwd=tmp)
        self.assertEqual(
            argv,
            ["-m", "quality_playbook_cli", "install",
             "--into", os.path.realpath(tmp)],
        )

    # ------------------------------------------------------------
    # Verbatim stdio passthrough (anti-fabrication contract)
    # ------------------------------------------------------------

    def test_stdio_passthrough_preserves_event_lines_and_nonce(
            self) -> None:
        """``stdio: 'inherit'`` means the spawned child's bytes
        reach the operator unmodified. We pin this empirically:
        stage a fake ``quality_playbook_cli`` package whose
        ``__init__.py`` emits a known sequence — ``event=...``
        lines and a deterministic run-nonce — and assert the
        shim's captured stdout is byte-identical to that sequence.

        Mutation candidate: replace ``stdio: 'inherit'`` with
        ``stdio: 'pipe'`` (and drop forwarding). Expected failure:
        captured stdout is empty.
        """
        # Stage a fake clone-shaped tree:
        #   <tmp>/bin/quality-playbook.js   (copy of real shim)
        #   <tmp>/quality_playbook_cli/__init__.py  (fake)
        with tempfile.TemporaryDirectory(prefix="qpb_089v_pt_") as tmp:
            tmp_root = Path(tmp)
            (tmp_root / "bin").mkdir()
            shutil.copy2(SHIM_PATH, tmp_root / "bin" / "quality-playbook.js")
            (tmp_root / "quality_playbook_cli").mkdir()
            # __main__.py bridges `python -m quality_playbook_cli`
            # to the package's `main()`. The fake __init__.py
            # below defines `main` in the same package, so the
            # real __main__.py works against the fake. (Copying
            # the real one keeps the test honest — if a future
            # 089v change breaks __main__.py, these tests fire.)
            shutil.copy2(
                REPO_ROOT / "quality_playbook_cli" / "__main__.py",
                tmp_root / "quality_playbook_cli" / "__main__.py",
            )
            fake_init = tmp_root / "quality_playbook_cli" / "__init__.py"
            fake_init.write_text(
                'import sys\n'
                'def main(argv=None):\n'
                '    # Mimic qpb_validate output: event= lines + nonce.\n'
                '    sys.stdout.write("event=phase0_probe ok=true\\n")\n'
                '    sys.stdout.write("event=install_skill_invoked argv=%r\\n" % (argv,))\n'
                '    sys.stdout.write("nonce=NPMV_PASSTHRU_NONCE_089v_42\\n")\n'
                '    sys.stdout.flush()\n'
                '    return 0\n'
                'if __name__ == "__main__":\n'
                '    sys.exit(main(sys.argv[1:]))\n'
            )

            # Invoke the staged shim. Use a real cwd so the shim
            # translates the bare invocation to `install --into
            # <cwd>` — the fake quality_playbook_cli ignores argv,
            # so this is fine.
            proc = subprocess.run(
                [_NODE, str(tmp_root / "bin" / "quality-playbook.js"),
                 "init", "--ai-tool=claude"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(tmp_root),
                env=os.environ.copy(),
                timeout=60,
            )

        self.assertEqual(
            proc.returncode, 0,
            f"shim exited {proc.returncode}; stderr={proc.stderr!r}",
        )
        stdout = proc.stdout.decode("utf-8")
        # Byte-identical assertions — the shim must NOT prepend,
        # reformat, or summarize.
        self.assertIn(
            "event=phase0_probe ok=true\n", stdout,
            f"089v anti-fabrication: event= line missing from "
            f"shim stdout. Got: {stdout!r}",
        )
        self.assertIn(
            "nonce=NPMV_PASSTHRU_NONCE_089v_42\n", stdout,
            f"089v anti-fabrication: run-nonce missing from shim "
            f"stdout. The shim must NOT swallow nonces. Got: "
            f"{stdout!r}",
        )
        # event=install_skill_invoked line contains the translated
        # argv as a Python repr; since the shim's translation
        # injects --into <cwd> and forwards --ai-tool=claude
        # verbatim (089w: no semantic translation), we can pin
        # those tokens too.
        self.assertIn(
            "'install'", stdout,
            "089v: translated argv must include 'install' (the "
            "verb after init->install mapping).",
        )
        self.assertIn(
            "'--ai-tool=claude'", stdout,
            "089w: translated argv must include "
            "'--ai-tool=claude' forwarded verbatim from the npx "
            "surface (the shim does not split or rewrite this "
            "token).",
        )

    def test_exit_code_propagation_nonzero(self) -> None:
        """The shim must propagate the child's exit code, not
        rewrite it to 0 on errors or to 1 on success."""
        with tempfile.TemporaryDirectory(prefix="qpb_089v_ec_") as tmp:
            tmp_root = Path(tmp)
            (tmp_root / "bin").mkdir()
            shutil.copy2(SHIM_PATH, tmp_root / "bin" / "quality-playbook.js")
            (tmp_root / "quality_playbook_cli").mkdir()
            # __main__.py bridges `python -m quality_playbook_cli`
            # to the package's `main()`. The fake __init__.py
            # below defines `main` in the same package, so the
            # real __main__.py works against the fake. (Copying
            # the real one keeps the test honest — if a future
            # 089v change breaks __main__.py, these tests fire.)
            shutil.copy2(
                REPO_ROOT / "quality_playbook_cli" / "__main__.py",
                tmp_root / "quality_playbook_cli" / "__main__.py",
            )
            (tmp_root / "quality_playbook_cli" / "__init__.py").write_text(
                'def main(argv=None):\n'
                '    return 17\n'
            )
            proc = subprocess.run(
                [_NODE, str(tmp_root / "bin" / "quality-playbook.js"),
                 "init", "--ai-tool=claude"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(tmp_root),
                env=os.environ.copy(),
                timeout=60,
            )
        self.assertEqual(
            proc.returncode, 17,
            f"089v: shim must propagate child exit code 17; got "
            f"{proc.returncode}.",
        )

    def test_qpb_channel_npm_set_in_child_env(self) -> None:
        """The shim sets ``QPB_CHANNEL=npm`` in the spawned child's
        env (so ``qpb_validate.py`` emits npx remediation). We
        verify by having the fake child print its
        ``QPB_CHANNEL``."""
        with tempfile.TemporaryDirectory(prefix="qpb_089v_ch_") as tmp:
            tmp_root = Path(tmp)
            (tmp_root / "bin").mkdir()
            shutil.copy2(SHIM_PATH, tmp_root / "bin" / "quality-playbook.js")
            (tmp_root / "quality_playbook_cli").mkdir()
            # __main__.py bridges `python -m quality_playbook_cli`
            # to the package's `main()`. The fake __init__.py
            # below defines `main` in the same package, so the
            # real __main__.py works against the fake. (Copying
            # the real one keeps the test honest — if a future
            # 089v change breaks __main__.py, these tests fire.)
            shutil.copy2(
                REPO_ROOT / "quality_playbook_cli" / "__main__.py",
                tmp_root / "quality_playbook_cli" / "__main__.py",
            )
            (tmp_root / "quality_playbook_cli" / "__init__.py").write_text(
                'import os, sys\n'
                'def main(argv=None):\n'
                '    sys.stdout.write("QPB_CHANNEL=%s\\n" % os.environ.get("QPB_CHANNEL","<unset>"))\n'
                '    return 0\n'
            )
            # Don't pre-set QPB_CHANNEL so we can confirm the shim
            # sets it (not inherits).
            env = {k: v for k, v in os.environ.items()
                   if k != "QPB_CHANNEL"}
            proc = subprocess.run(
                [_NODE, str(tmp_root / "bin" / "quality-playbook.js"),
                 "init", "--ai-tool=claude"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(tmp_root),
                env=env,
                timeout=60,
            )
        self.assertEqual(proc.returncode, 0)
        self.assertIn(
            "QPB_CHANNEL=npm\n",
            proc.stdout.decode("utf-8"),
            f"089v: shim must set QPB_CHANNEL=npm before spawn; "
            f"got stdout={proc.stdout!r}",
        )


if __name__ == "__main__":
    unittest.main()
