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
import ast
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


# 080b F2: structured-parser extraction calls that have NO
# legitimate use in the subprocess-the-shell-pipeline orchestrator
# (reimplementing the extraction in Python re-opens v1.3.23).
_FORBIDDEN_EXTRACTION_CALLS = {
    ("re", "findall"), ("re", "finditer"), ("re", "search"),
    ("re", "match"), ("re", "fullmatch"), ("re", "split"),
    ("ast", "parse"), ("json", "loads"), ("json", "load"),
    ("csv", "reader"), ("csv", "DictReader"),
    ("yaml", "safe_load"), ("yaml", "load"),
    ("tokenize", "tokenize"), ("tokenize", "generate_tokens"),
}
_SHELLS = {"bash", "sh", "/bin/bash", "/bin/sh", "/usr/bin/bash",
           "/usr/bin/sh"}


def _is_cases_txt(s: str) -> bool:
    """A saved mechanical artifact path (legitimate to read for the
    comparison) vs a source file (reading it in Python = the
    v1.3.23 extraction-substitution vector)."""
    return s.endswith("_cases.txt") or (
        "mechanical/" in s and s.endswith(".txt"))


def _verify_py_is_conformant(src: str) -> bool:
    """§6.6 "Council-of-One" anti-reimplementation lint — AST-based,
    strengthened in 080b after the 080 codex F2 attack (a decoy
    subprocess.run + pure-Python splitlines()/startswith() forgery
    defeated the old string-token heuristic).

    The conformant pattern is narrow: a verify.py drives every
    extraction through ``subprocess.run`` of the ORIGINAL recorded
    shell pipeline (a ``["bash"/"sh", "-c", "<pipeline>"]``-shaped
    argv) and only ever ``read_text()``s the saved ``*_cases.txt``
    artifact for the comparison. It NEVER reads a source file in
    Python and NEVER reimplements the extraction with regex /
    structured parsers. Conformant iff BOTH:
      (a) a real shell-pipeline subprocess is present — a list
          literal whose first element is bash/sh appears AND
          subprocess.run/Popen/check_output/check_call is called
          (a decoy ``subprocess.run(["true"])`` / ``["echo", …]``
          has no bash/sh list literal → fails this); AND
      (b) NO forbidden extraction signal:
          - any regex/ast/json/csv/yaml/tokenize extraction call
            (the _FORBIDDEN_EXTRACTION_CALLS set), or an
            xml.etree parse/fromstring; OR
          - any ``open("<lit>")`` / ``Path("<lit>").read_text()`` /
            ``.read_bytes()`` where ``<lit>`` is a string literal
            that is NOT a ``*_cases.txt`` artifact (reading a
            source file in Python is the extraction-substitution
            vector — the canonical form only reads the
            ``saved_path`` loop variable, never a source literal).

    Design note (080b): the lint does NOT denylist string methods
    (``.splitlines``/``.split``/``.startswith``) directly — the
    canonical §6.3 orchestrator legitimately calls
    ``saved.splitlines(keepends=True)`` for ``difflib``. Flagging
    those would false-positive the conformant sample (the
    instruction-080b halt-condition). The precise discriminators —
    "no real bash subprocess" and "reads a source-file literal" —
    catch the codex splitlines/startswith forgery (it reads
    ``Path("src/foo.c").read_text()`` and its only subprocess is a
    non-bash decoy) without that false-positive risk.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False

    shell_list_literal = False
    subprocess_called = False
    forbidden = False

    for node in ast.walk(tree):
        if isinstance(node, ast.List) and node.elts:
            first = node.elts[0]
            if (isinstance(first, ast.Constant)
                    and isinstance(first.value, str)
                    and first.value in _SHELLS):
                shell_list_literal = True
        if isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "subprocess"
                    and func.attr in ("run", "Popen",
                                      "check_output", "check_call")):
                subprocess_called = True
            if (isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and (func.value.id, func.attr)
                    in _FORBIDDEN_EXTRACTION_CALLS):
                forbidden = True
            if (isinstance(func, ast.Name) and func.id == "open"
                    and node.args):
                a0 = node.args[0]
                if (isinstance(a0, ast.Constant)
                        and isinstance(a0.value, str)
                        and not _is_cases_txt(a0.value)):
                    forbidden = True
            if (isinstance(func, ast.Attribute)
                    and func.attr in ("read_text", "read_bytes")):
                v = func.value
                if (isinstance(v, ast.Call)
                        and isinstance(v.func, ast.Name)
                        and v.func.id == "Path" and v.args
                        and isinstance(v.args[0], ast.Constant)
                        and isinstance(v.args[0].value, str)
                        and not _is_cases_txt(v.args[0].value)):
                    forbidden = True
            if (isinstance(func, ast.Attribute)
                    and func.attr in ("parse", "fromstring")):
                dumped = ast.dump(func.value)
                if "etree" in dumped or "ElementTree" in dumped:
                    forbidden = True

    has_real_subprocess = shell_list_literal and subprocess_called
    return has_real_subprocess and not forbidden


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


# 080b F2 — the exact codex attack: a DECOY subprocess.run plus a
# pure-Python splitlines()/startswith() extraction reading the
# SOURCE file. The 080 string-token lint returned conformant=True
# for this; the AST lint must return False.
_FORGED_DECOY_SPLITLINES = '''\
#!/usr/bin/env python3
import subprocess, sys
from pathlib import Path

def main() -> int:
    subprocess.run(["true"])  # decoy — result ignored
    src = Path("src/foo.c").read_text()
    fresh = "".join(l for l in src.splitlines(keepends=True)
                     if l.lstrip().startswith("case "))
    saved = Path("quality/mechanical/foo_cases.txt").read_text()
    return 0 if fresh == saved else 1

if __name__ == "__main__":
    sys.exit(main())
'''

# Forgery: open() the source file directly and walk lines manually
# (even with a real-looking bash decoy subprocess present).
_FORGED_OPEN_SOURCE = '''\
#!/usr/bin/env python3
import subprocess, sys

def main() -> int:
    subprocess.run(["bash", "-c", "echo decoy"])  # decoy bash
    lines = []
    with open("drivers/virtio/virtio_ring.c") as fh:
        for ln in fh:
            if ln.lstrip().startswith("case "):
                lines.append(ln)
    fresh = "".join(lines)
    with open("quality/mechanical/foo_cases.txt") as fh:
        saved = fh.read()
    return 0 if fresh == saved else 1

if __name__ == "__main__":
    sys.exit(main())
'''

# Forgery: ast.parse the source for extraction (structured parser).
_FORGED_AST_PARSE = '''\
#!/usr/bin/env python3
import ast, subprocess, sys
from pathlib import Path

def main() -> int:
    subprocess.run(["bash", "-c", "true"])  # decoy bash
    tree = ast.parse(Path("quality/mechanical/foo_cases.txt").read_text())
    fresh = str(len(list(ast.walk(tree))))
    saved = Path("quality/mechanical/foo_cases.txt").read_text()
    return 0 if fresh == saved else 1

if __name__ == "__main__":
    sys.exit(main())
'''


class VerifyPyAntiReimplementationLintTests(unittest.TestCase):

    def test_conformant_verify_py_passes_lint(self) -> None:
        """The §6.3 canonical orchestrator (real ["bash","-c",…]
        subprocess; reads only the saved_path loop variable; uses
        .splitlines(keepends=True) ONLY for difflib) must NOT be a
        false-positive under the strengthened AST lint (080b
        halt-condition guard)."""
        self.assertTrue(
            _verify_py_is_conformant(_CONFORMANT_VERIFY_PY),
            "the §6.3 canonical orchestrator must pass the "
            "anti-reimplementation lint (no string-method false "
            "positive on its difflib .splitlines())")

    def test_original_regex_forgery_still_fails_lint(self) -> None:
        """The 080 regex-only forgery (subset of the new lint) stays
        flagged: no bash subprocess AND re.findall."""
        self.assertFalse(
            _verify_py_is_conformant(_FORGED_VERIFY_PY),
            "pure-Python re.findall extraction MUST stay flagged")

    def test_lint_catches_splitlines_startswith_forgery(self) -> None:
        """The EXACT codex 080-F2 attack: decoy subprocess.run +
        pure-Python splitlines()/startswith() reading the SOURCE.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-080b —
        BITE EXECUTED during instruction-080b development:
          The bite is the regression itself: under the pre-080b
          string-token lint `_verify_py_is_conformant
          (_FORGED_DECOY_SPLITLINES)` returned True (the codex F2
          finding — worker-reproduced live before 080b). After the
          080b AST rewrite it returns False because (a) the only
          subprocess argv is `["true"]` (no bash/sh list literal →
          has_real_subprocess False) AND (b) it reads the source
          literal `Path("src/foo.c").read_text()` (not a
          *_cases.txt → forbidden True). Observed (purged
          __pycache__): test PASSES (lint returns False).
          Restoration: N/A — the forged sample is a fixed constant
          asserted live every run; reverting the lint body to the
          080 string-token form makes this test FAIL (returns
          True), restoring it makes it PASS (PASS→FAIL→PASS verified
          against the 080 lint body).
        """
        self.assertFalse(
            _verify_py_is_conformant(_FORGED_DECOY_SPLITLINES),
            "decoy subprocess + pure-Python splitlines/startswith "
            "extraction of the SOURCE MUST be flagged (the codex "
            "080-F2 attack)")

    def test_lint_catches_open_source_file_forgery(self) -> None:
        """open(<source>) + manual line walk, even with a real bash
        decoy subprocess present.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-080b —
        BITE EXECUTED: the forged sample carries a real
        `subprocess.run(["bash","-c","echo decoy"])` (so
        has_real_subprocess is True) but `open("drivers/virtio/
        virtio_ring.c")` is a non-*_cases.txt literal → forbidden
        True → lint returns False → test PASSES. Reverting the lint
        to the 080 string-token body (which only denylisted re.*)
        makes this return True → test FAILS; restoring → PASS
        (PASS→FAIL→PASS). __pycache__ purged between.
        """
        self.assertFalse(
            _verify_py_is_conformant(_FORGED_OPEN_SOURCE),
            "open(<source>) extraction MUST be flagged even with a "
            "decoy bash subprocess present")

    def test_lint_catches_ast_parse_forgery(self) -> None:
        """ast.parse used as the extraction (structured parser),
        with a decoy bash subprocess present.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-080b —
        BITE EXECUTED: `("ast","parse")` ∈ _FORBIDDEN_EXTRACTION_
        CALLS → forbidden True → lint returns False → test PASSES.
        Mutation: remove `("ast","parse")` from
        _FORBIDDEN_EXTRACTION_CALLS → lint returns True →
        test FAILS; restore → PASS (PASS→FAIL→PASS; __pycache__
        purged between mutate/restore).
        """
        self.assertFalse(
            _verify_py_is_conformant(_FORGED_AST_PARSE),
            "ast.parse extraction MUST be flagged (structured "
            "parser reimplementation)")


if __name__ == "__main__":
    unittest.main()
