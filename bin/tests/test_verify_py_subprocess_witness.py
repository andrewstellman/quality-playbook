"""v1.5.7 instruction 080 (W4 — addendum r3 §6.6): the generated
`quality/mechanical/verify.py` is an ORCHESTRATOR that subprocesses
the ORIGINAL shell extraction pipeline and diffs its stdout against
the saved artifact. Reimplementing the extraction in Python is
FORBIDDEN — Python was the v1.3.23 attack vector (the model authors
both the extraction and the saved file).

Three checks per §6.6:
  1. subprocess-of-shell-pipeline works (exit 0 on match);
  2. v1.3.23 mutation bite: tamper the saved *_cases.txt → exit 1
     with a diff (the regression catch);
  3. anti-Python-reimplementation lint: a model-authored verify.py
     that does pure-Python extraction (no subprocess of the shell
     pipeline) is flagged non-conformant.

`bash` is required for checks 1-2 (the §6.3 sample shells out to
`bash -c "<pipeline>"`); skipped if unavailable (Windows host
without Git Bash — addendum §6.5).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_BASH = shutil.which("bash")

# The canonical §6.3 orchestrator, parameterised over one extraction.
_CONFORMANT_VERIFY_PY = '''\
#!/usr/bin/env python3
"""Mechanical artifact integrity check — auto-generated at Phase 1.

CRITICAL: ORCHESTRATION only. Reimplementing the extraction in
Python is FORBIDDEN — it re-opens the v1.3.23 attack surface."""
import sys
import subprocess
from pathlib import Path

EXTRACTIONS = [
    (
        "quality/mechanical/foo_cases.txt",
        ["bash", "-c", "grep -E '^\\\\s*case ' src/foo.c"],
        ["src/foo.c"],
    ),
]

def main() -> int:
    failures = 0
    for saved_path, cmd, sources in EXTRACTIONS:
        for src in sources:
            if not Path(src).is_file():
                print(f"FAIL: source file {src} missing")
                failures += 1
                continue
        result = subprocess.run(cmd, capture_output=True, text=True,
                                check=False)
        if result.returncode != 0:
            print(f"FAIL: extraction exited {result.returncode} "
                  f"for {saved_path}")
            failures += 1
            continue
        fresh = result.stdout
        saved = Path(saved_path).read_text(encoding="utf-8")
        if fresh != saved:
            print(f"FAIL: {saved_path} mismatch")
            import difflib
            for line in difflib.unified_diff(
                saved.splitlines(keepends=True),
                fresh.splitlines(keepends=True),
                fromfile=f"saved:{saved_path}", tofile="fresh"):
                print(line, end="")
            failures += 1
    if failures:
        print("Mechanical verification FAILED")
        return 1
    print("Mechanical verification OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
'''

# The FORBIDDEN form: pure-Python regex extraction, NO subprocess of
# the shell pipeline (the v1.3.23 attack vector — model authors both
# the extraction logic and the saved file).
_FORGED_VERIFY_PY = '''\
#!/usr/bin/env python3
import re
import sys
from pathlib import Path

def main() -> int:
    src = Path("src/foo.c").read_text()
    fresh = "".join(re.findall(r"^\\s*case .*$", src, re.M))
    saved = Path("quality/mechanical/foo_cases.txt").read_text()
    return 0 if fresh == saved else 1

if __name__ == "__main__":
    sys.exit(main())
'''


def _verify_py_is_conformant(src: str) -> bool:
    """The §6.6 "Council-of-One" anti-reimplementation lint. A
    conformant verify.py drives each extraction through
    ``subprocess.run`` of the recorded shell pipeline; a verify.py
    that reimplements the extraction in Python (``re.findall`` /
    ``re.finditer`` / ``re.search`` over source text, or reads the
    source file and parses it itself, with NO subprocess of the
    shell pipeline) is non-conformant (re-opens v1.3.23)."""
    has_subprocess = "subprocess.run(" in src
    reimplements = any(
        tok in src
        for tok in ("re.findall(", "re.finditer(", "re.search(")
    )
    # Conformant iff it shells out AND does not substitute a
    # pure-Python regex reimplementation for the subprocess.
    return has_subprocess and not reimplements


def _make_project(td: str, saved_contents: str) -> Path:
    root = Path(td)
    (root / "src").mkdir(parents=True)
    (root / "src" / "foo.c").write_text(
        "int f(int x){\n"
        "  switch(x){\n"
        "  case 1: return 1;\n"
        "  case 2: return 2;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (root / "quality" / "mechanical").mkdir(parents=True)
    (root / "quality" / "mechanical" / "foo_cases.txt").write_text(
        saved_contents, encoding="utf-8")
    (root / "quality" / "mechanical" / "verify.py").write_text(
        _CONFORMANT_VERIFY_PY, encoding="utf-8")
    return root


def _grep_truth(root: Path) -> str:
    """What the recorded shell pipeline actually produces — the
    witness the saved file must equal."""
    r = subprocess.run(
        ["bash", "-c", "grep -E '^\\s*case ' src/foo.c"],
        cwd=root, capture_output=True, text=True, check=False)
    return r.stdout


@unittest.skipUnless(_BASH, "bash unavailable (addendum §6.5 — "
                            "Windows host without Git Bash)")
class VerifyPySubprocessWitnessTests(unittest.TestCase):

    def test_verify_py_subprocess_runs_shell_pipeline(self) -> None:
        with TemporaryDirectory() as td:
            root = _make_project(td, "")
            # Saved file = exactly what the shell pipeline emits.
            truth = _grep_truth(root)
            (root / "quality" / "mechanical" / "foo_cases.txt").write_text(
                truth, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "quality/mechanical/verify.py"],
                cwd=root, capture_output=True, text=True, check=False)
            self.assertEqual(
                proc.returncode, 0,
                f"verify.py should exit 0 when the saved artifact "
                f"matches the re-run shell pipeline.\n"
                f"stdout:{proc.stdout}\nstderr:{proc.stderr}")
            self.assertIn("Mechanical verification OK", proc.stdout)

    def test_verify_py_v1_3_23_mutation_bite(self) -> None:
        """Tamper the saved *_cases.txt with a hallucinated case →
        verify.py re-runs the real shell pipeline and exits 1 with a
        diff. This IS the v1.3.23 regression catch.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-080 —
        BITE EXECUTED during instruction-080 development:
          The test itself is the bite: it writes the real
          shell-pipeline output to foo_cases.txt, then appends a
          hallucinated `  case 999:` line (the forgery), then runs
          verify.py.
          Observed (purged __pycache__ first): verify.py exited 1;
          stdout contained "FAIL: quality/mechanical/foo_cases.txt
          mismatch" + a unified diff showing the spurious
          `+  case 999:` line; "Mechanical verification FAILED".
          Restoration: N/A (no source mutated — the bite is the
          forged-artifact scenario, asserted live every run).
        """
        with TemporaryDirectory() as td:
            root = _make_project(td, "")
            truth = _grep_truth(root)
            forged = truth + "  case 999:  // hallucinated\n"
            (root / "quality" / "mechanical" / "foo_cases.txt").write_text(
                forged, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "quality/mechanical/verify.py"],
                cwd=root, capture_output=True, text=True, check=False)
            self.assertEqual(
                proc.returncode, 1,
                f"verify.py MUST exit 1 on a forged artifact "
                f"(v1.3.23 catch).\nstdout:{proc.stdout}")
            self.assertIn("mismatch", proc.stdout)
            self.assertIn("Mechanical verification FAILED", proc.stdout)
            self.assertIn("999", proc.stdout)  # the diff shows the forgery


class VerifyPyAntiReimplementationLintTests(unittest.TestCase):

    def test_conformant_verify_py_passes_lint(self) -> None:
        self.assertTrue(
            _verify_py_is_conformant(_CONFORMANT_VERIFY_PY),
            "the §6.3 canonical orchestrator must pass the "
            "anti-reimplementation lint")

    def test_forged_pure_python_extraction_fails_lint(self) -> None:
        """A model-authored verify.py that reimplements the
        extraction in pure Python (re.findall over the source, no
        subprocess of the shell pipeline) is the forbidden v1.3.23
        form and MUST be flagged.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-080 —
        BITE EXECUTED during instruction-080 development:
          Mutation: change `_FORGED_VERIFY_PY` to additionally
          include a `subprocess.run([...])` call (making it look
          conformant while still re.findall-extracting).
          Observed (purged __pycache__ first): with both
          subprocess.run AND re.findall present the lint still
          returns False (the `not reimplements` clause fails on
          re.findall) → test_forged_... still PASSES (correctly
          flags it); reverting to the no-subprocess forged form
          keeps it flagged via the `has_subprocess` clause. The
          lint catches BOTH the no-subprocess and the
          subprocess+reimplementation evasions.
          Restoration: _FORGED_VERIFY_PY restored to the pure-re
          form; lint returns False; test PASS.
        """
        self.assertFalse(
            _verify_py_is_conformant(_FORGED_VERIFY_PY),
            "a pure-Python re.findall extraction (no subprocess of "
            "the recorded shell pipeline) MUST be flagged "
            "non-conformant — it re-opens the v1.3.23 attack surface")


if __name__ == "__main__":
    unittest.main()
