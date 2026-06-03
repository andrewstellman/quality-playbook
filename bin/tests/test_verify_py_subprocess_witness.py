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

================================================================
ANTI-REIMPLEMENTATION LINT SCOPE — BEST-EFFORT.
This lint is **NOT a security boundary** (v1.5.7 instruction
080d; operator decision after the 080 → 080b → 080c arms race).
================================================================

Three rounds of codex review confirmed that statically detecting
"is this Python reimplementing the extraction" is **undecidable**
in the general case — Python offers unbounded dynamic dispatch
(`importlib.import_module`, `getattr`, `__import__`, `exec`,
`eval`, `operator.attrgetter`, C-extension shims, attribute
indirection, runtime-assembled callable names). Each round closed
one evasion class and codex found another (080 splitlines/
startswith → 080b import-alias → 080c from-import-AS-submodule +
importlib + getattr). The lint is therefore scoped to catch
honest reimplementation and common forgery classes, NOT to be an
exhaustive adversarial boundary.

**Catches:** honest reimplementation; regex calls
(`re.findall`/`finditer`/`search`/`match`/`split`);
string-method extraction after `open(<source>)`; `open(<source>)`
/ `Path("<source-literal>").read_text()` non-`*_cases.txt` reads;
direct/`import-X-as-Y`-aliased calls to
`xml.etree`/`json`/`csv`/`yaml`/`ast`/`tokenize` parsers;
decoy-non-bash-subprocess; missing real `["bash"/"sh", …]`
pipeline.

**Does NOT catch (known, by design):**
`from xml.etree import ElementTree as ET; ET.parse(...)`
(submodule from-import-AS chain); `importlib.import_module(
"json").loads(...)`; `getattr(json, "loads")(...)`; `exec` /
`eval`-constructed callables; C-extension indirection;
runtime-assembled callable names.

**The load-bearing v1.3.23 defense is STRUCTURAL, not this lint.**
`quality_gate.py:check_mechanical()` subprocess-invokes the
agent-authored `verify.py` from the target root and propagates
its exit code; genuine protection comes from `verify.py`'s
`EXTRACTIONS` re-running `subprocess.run(["bash","-c",
"<original-shell-pipeline>"])` against actual source bytes
(080 + 080c F1, codex-confirmed). This lint is a useful sanity
check for *accidental* reimplementation; it is explicitly
**not the trust path**, and its incompleteness against an
adversarial forger is intentional and accepted.
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


# 080c F2: canonical-module → dangerous-callable map. These
# structured parsers have NO legitimate use in the
# subprocess-the-shell-pipeline orchestrator; using any of them to
# build the comparison's "fresh" side reimplements the extraction in
# Python and re-opens the v1.3.23 attack surface. Keyed by the FULL
# dotted module path so import-alias resolution (below) can map any
# local naming (`import xml.etree.ElementTree as ET`,
# `from json import loads as L`, …) back to the canonical module.
_DANGEROUS = {
    "re": {"findall", "finditer", "search", "match", "fullmatch",
           "split"},
    "ast": {"parse", "literal_eval"},
    "json": {"loads", "load"},
    "csv": {"reader", "DictReader"},
    "yaml": {"safe_load", "load", "full_load", "unsafe_load"},
    "tokenize": {"tokenize", "generate_tokens"},
    "xml.etree.ElementTree": {"parse", "fromstring", "iterparse",
                              "XML", "XMLParser"},
    "xml.etree.cElementTree": {"parse", "fromstring", "iterparse",
                               "XML", "XMLParser"},
}
_SHELLS = {"bash", "sh", "/bin/bash", "/bin/sh", "/usr/bin/bash",
           "/usr/bin/sh"}


def _is_cases_txt(s: str) -> bool:
    """A saved mechanical artifact path (legitimate to read for the
    comparison) vs a source file (reading it in Python = the
    v1.3.23 extraction-substitution vector)."""
    return s.endswith("_cases.txt") or (
        "mechanical/" in s and s.endswith(".txt"))


def _dotted_name(node) -> "str | None":
    """Flatten a Name / Attribute chain to ``"a.b.c"`` (or None)."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _verify_py_is_conformant(src: str) -> bool:
    # BEST-EFFORT — see the module docstring's "ANTI-REIMPLEMENTATION
    # LINT SCOPE" section; this is NOT a security boundary (080d,
    # operator decision). Do NOT iterate it to chase dynamic-dispatch
    # evasions — that arms race is undecidable; the load-bearing
    # v1.3.23 defense is the gate's subprocess re-extraction, not
    # this check.
    """§6.6 "Council-of-One" anti-reimplementation lint — AST-based
    with proper IMPORT-ALIAS TRACKING (080c, after the 080b codex F2
    alias-evasion: ``import xml.etree.ElementTree as ET;
    ET.fromstring(...)`` slipped past the old ast.dump substring
    heuristic).

    **BEST-EFFORT, NOT a security boundary (080d).** Statically
    proving Python does not reimplement the extraction is
    undecidable. KNOWN UNCOVERED evasion classes, accepted by
    design: ``from xml.etree import ElementTree as ET;
    ET.parse(...)`` (submodule from-import-AS chain);
    ``importlib.import_module("json").loads(...)``;
    ``getattr(json, "loads")(...)``; ``exec``/``eval``-constructed
    callables; C-extension indirection; runtime-assembled callable
    names. This lint catches honest/accidental reimplementation +
    the enumerated common forgery classes; the trust path is the
    structural subprocess re-extraction (module docstring).

    Walk-imports-first: build alias maps (local name → canonical
    module / callable) covering ``import M``, ``import M as A``,
    ``import a.b.c``, ``from M import f``, ``from M import f as g``.
    Then resolve every call through those maps so a dangerous
    extraction callable (regex / ast / json / csv / yaml / tokenize /
    xml.etree — the _DANGEROUS map) is flagged regardless of local
    naming.

    Conformant iff BOTH:
      (a) a real shell-pipeline subprocess is present — a list
          literal whose first element is bash/sh appears AND a
          subprocess (alias-resolved) run/Popen/check_* call is made
          (a decoy ``subprocess.run(["true"])`` has no bash/sh list
          literal → fails this); AND
      (b) NO forbidden extraction signal:
          - any alias-resolved call to a _DANGEROUS module callable
            (covers `import xml.etree.ElementTree as ET;
            ET.fromstring`, `from json import loads as L; L(...)`,
            bare dotted `xml.etree.ElementTree.parse`, …); OR
          - any ``open("<lit>")`` / ``Path("<lit>").read_text()`` /
            ``.read_bytes()`` where ``<lit>`` is a string literal
            that is NOT a ``*_cases.txt`` artifact (reading a source
            file in Python is the extraction-substitution vector).

    Design note: the lint does NOT denylist string methods
    (``.splitlines``/``.split``/``.startswith``) — the canonical §6.3
    orchestrator legitimately calls ``saved.splitlines(keepends=True)``
    for ``difflib``; flagging those would false-positive the
    conformant sample (the 080b/080c halt-condition guard). The
    precise discriminators — "no real bash subprocess", "dangerous
    parser call (alias-resolved)", "source-file literal read" —
    catch every codex evasion without that false-positive risk.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False

    # ---- pass 1: import-alias maps ----
    module_alias = {}        # local name → canonical module path
    callable_alias = {}      # local name → (canonical module, callable)
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                module_alias[a.asname or a.name] = a.name
        elif isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                callable_alias[a.asname or a.name] = (n.module, a.name)
    subprocess_names = {ln for ln, canon in module_alias.items()
                        if canon == "subprocess"}
    subprocess_names.add("subprocess")
    _DANGEROUS_FNS = {fn for fns in _DANGEROUS.values() for fn in fns}

    # ---- pass 2: calls + shell literal + source reads ----
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
        if not isinstance(node, ast.Call):
            continue
        func = node.func

        # subprocess.run/Popen/check_* (alias-resolved)
        if (isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id in subprocess_names
                and func.attr in ("run", "Popen",
                                  "check_output", "check_call")):
            subprocess_called = True

        # dangerous dotted call: <modpart>.<fn>
        d = _dotted_name(func)
        if d and "." in d:
            modpart, fn = d.rsplit(".", 1)
            canon = module_alias.get(modpart, modpart)
            if fn in _DANGEROUS.get(canon, ()):
                forbidden = True

        # bare from-import callable: f(...) where f is a dangerous
        # callable alias (`from xml.etree.ElementTree import parse`)
        if isinstance(func, ast.Name) and func.id in callable_alias:
            cmod, cfn = callable_alias[func.id]
            if cfn in _DANGEROUS.get(cmod, ()) or cfn in _DANGEROUS_FNS:
                forbidden = True

        # open("<src-literal>")
        if (isinstance(func, ast.Name) and func.id == "open"
                and node.args):
            a0 = node.args[0]
            if (isinstance(a0, ast.Constant)
                    and isinstance(a0.value, str)
                    and not _is_cases_txt(a0.value)):
                forbidden = True

        # Path("<src-literal>").read_text()/read_bytes()
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


# 080c F2 — the EXACT codex-080b-F2 alias evasion + new alias forms.
# Isolated so the SOLE forbidden signal is the alias-resolved
# ET.fromstring call (reads only the saved *_cases.txt + a built
# string — no source-literal read, so the source-read rule does NOT
# redundantly mask the alias-tracking path the bite pins).
_FORGED_XML_AS_ET = '''\
#!/usr/bin/env python3
import subprocess, sys
import xml.etree.ElementTree as ET
from pathlib import Path

def main() -> int:
    subprocess.run(["bash", "-c", "true"])  # decoy bash
    saved = Path("quality/mechanical/foo_cases.txt").read_text()
    fresh = str(ET.fromstring("<r>" + saved + "</r>"))
    return 0 if fresh == saved else 1

if __name__ == "__main__":
    sys.exit(main())
'''

_FORGED_FROM_XML_IMPORT_PARSE = '''\
#!/usr/bin/env python3
import subprocess, sys
from xml.etree.ElementTree import parse as P

def main() -> int:
    subprocess.run(["bash", "-c", "true"])  # decoy bash
    fresh = str(P("src/foo.c"))
    with open("quality/mechanical/foo_cases.txt") as fh:
        saved = fh.read()
    return 0 if fresh == saved else 1

if __name__ == "__main__":
    sys.exit(main())
'''

# Isolated so the SOLE forbidden signal is the alias-resolved
# J.loads call (reads only the saved *_cases.txt; the json.loads
# argument is a built string, not a source-literal read).
_FORGED_JSON_AS_J = '''\
#!/usr/bin/env python3
import subprocess, sys, json as J
from pathlib import Path

def main() -> int:
    subprocess.run(["bash", "-c", "true"])  # decoy bash
    saved = Path("quality/mechanical/foo_cases.txt").read_text()
    fresh = str(J.loads("[" + str(len(saved)) + "]"))
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
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-080c —
        BITE EXECUTED: `"parse" ∈ _DANGEROUS["ast"]` → the
        alias-resolved dangerous-call rule sets forbidden=True →
        lint returns False → test PASSES. Mutation: remove `"parse"`
        from `_DANGEROUS["ast"]` → lint returns True → test FAILS;
        restore → PASS (PASS→FAIL→PASS; __pycache__ purged between
        mutate/restore).
        """
        self.assertFalse(
            _verify_py_is_conformant(_FORGED_AST_PARSE),
            "ast.parse extraction MUST be flagged (structured "
            "parser reimplementation)")

    def test_lint_catches_xml_etree_as_ET_evasion(self) -> None:
        """The EXACT codex-080b-F2 alias evasion: `import
        xml.etree.ElementTree as ET; ET.fromstring(...)`. Under the
        080b ast.dump substring heuristic this returned True (the
        finding); the 080c import-alias tracker resolves ET →
        xml.etree.ElementTree → False.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-080c —
        BITE EXECUTED during instruction-080c development:
          Reproduced the codex-080b-F2 attack live: pre-080c
          (ast.dump-substring xml branch) `_verify_py_is_conformant
          (_FORGED_XML_AS_ET)` returned True (alias evasion — the
          codex finding). After the 080c walk-imports-first alias
          tracker it returns False (module_alias['ET'] →
          'xml.etree.ElementTree'; fromstring ∈ _DANGEROUS). Bite:
          delete the `module_alias[a.asname or a.name] = a.name`
          line → ET unresolved → returns True → test FAILS; restore
          → False → PASS (PASS→FAIL→PASS, __pycache__ purged).
        """
        self.assertFalse(
            _verify_py_is_conformant(_FORGED_XML_AS_ET),
            "import xml.etree.ElementTree as ET; ET.fromstring(...) "
            "MUST be flagged — the exact codex-080b-F2 alias evasion")

    def test_lint_catches_from_xml_import_parse_evasion(self) -> None:
        """`from xml.etree.ElementTree import parse as P; P(...)` —
        bare aliased callable.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-080c —
        BITE EXECUTED: callable_alias['P'] =
        ('xml.etree.ElementTree','parse'); 'parse' ∈
        _DANGEROUS['xml.etree.ElementTree'] → forbidden → False →
        PASS. Mutation: drop the ImportFrom branch that populates
        callable_alias → bare P() unresolved → returns True → test
        FAILS; restore → False → PASS (PASS→FAIL→PASS, __pycache__
        purged).
        """
        self.assertFalse(
            _verify_py_is_conformant(_FORGED_FROM_XML_IMPORT_PARSE),
            "from xml.etree.ElementTree import parse as P; P(...) "
            "MUST be flagged (aliased from-import callable)")

    def test_lint_catches_json_loads_alias_evasion(self) -> None:
        """`import json as J; J.loads(...)` — aliased module call.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-080c —
        BITE EXECUTED: module_alias['J']='json'; 'loads' ∈
        _DANGEROUS['json'] via the alias-resolved dotted-call rule →
        forbidden → False → PASS. Mutation: remove 'loads' from
        _DANGEROUS['json'] → returns True → test FAILS; restore →
        False → PASS (PASS→FAIL→PASS, __pycache__ purged).
        """
        self.assertFalse(
            _verify_py_is_conformant(_FORGED_JSON_AS_J),
            "import json as J; J.loads(...) MUST be flagged "
            "(aliased dangerous-module call)")

    def test_lint_known_limitations_documented(self) -> None:
        """080d (option C) structural pin: the honest best-effort
        scoping must stay in BOTH the module docstring AND the
        _verify_py_is_conformant docstring, so a future commit
        cannot silently delete it and re-present the lint as an
        exhaustive security boundary. (Not a mutation-bite test —
        it IS the regression pin; deleting either scoping block
        fails this directly.)"""
        import sys as _sys
        mod_doc = _sys.modules[__name__].__doc__ or ""
        fn_doc = _verify_py_is_conformant.__doc__ or ""
        for label, doc in (("module docstring", mod_doc),
                           ("_verify_py_is_conformant docstring",
                            fn_doc)):
            lowered = doc.lower()
            self.assertIn(
                "best-effort", lowered,
                f"{label} must mark the lint BEST-EFFORT (080d "
                f"option C — operator decision)")
            self.assertIn(
                "not a security boundary", lowered,
                f"{label} must state the lint is NOT a security "
                f"boundary (080d)")
            # at least one explicitly-named known uncovered evasion
            self.assertTrue(
                any(tok in doc for tok in
                    ("importlib", "getattr", "from-import-AS",
                     "from xml.etree import ElementTree as ET",
                     "exec", "eval")),
                f"{label} must enumerate >=1 known uncovered "
                f"evasion class (importlib / getattr / "
                f"from-import-AS-submodule / exec / eval) so the "
                f"limits are honest up-front")
        # the structural-defense pointer must be present (the lint
        # is explicitly NOT the trust path)
        self.assertIn("structural", mod_doc.lower())
        self.assertTrue(
            "subprocess" in mod_doc.lower()
            and "trust path" in mod_doc.lower(),
            "module docstring must point at the structural "
            "subprocess re-extraction as the load-bearing v1.3.23 "
            "defense (the lint is NOT the trust path)")


if __name__ == "__main__":
    unittest.main()
