"""v1.5.7 instruction 089 F4 / bootstrap BUG-001 regression tests.

_static_parse_ok must distinguish a real SOURCE parse failure
(py_compile.PyCompileError / SyntaxError) from a FILESYSTEM/sandbox
failure (OSError). Pre-089 both were caught together and
check_closure emitted the single "py_compile parse failed" detail,
misreporting a permissions/sandbox error as syntactic corruption
(REQ-001: Phase 0 closure diagnostics must distinguish the two).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bin import qpb_validate as v


class StaticParseClassificationTests(unittest.TestCase):
    """Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160) — BITE EXECUTED during
    instruction-089 development:
      Mutation: in bin/qpb_validate.py::_static_parse_ok, swap the
        two except handlers so OSError returns the "parse failed"
        detail and PyCompileError/SyntaxError returns the
        "filesystem error" detail.
      Observed failure (purged __pycache__ first):
        FAIL: test_oserror_is_filesystem_error
        AssertionError: 'py_compile filesystem error: ...' not found
          — detail was the flipped 'py_compile parse failed: ...'
      Mutation reverted; tests pass.
    """

    def test_valid_source_returns_ok_none(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "good.py"
            p.write_text("x = 1\n", encoding="utf-8")
            ok, detail = v._static_parse_ok(p)
            self.assertTrue(ok)
            self.assertIsNone(detail)

    def test_syntax_error_is_parse_failed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "broken.py"
            p.write_text("def (oops:\n", encoding="utf-8")
            ok, detail = v._static_parse_ok(p)
            self.assertFalse(ok)
            self.assertIsNotNone(detail)
            self.assertTrue(detail.startswith("py_compile parse failed:"),
                            f"expected parse-failure detail, got {detail!r}")
            self.assertNotIn("filesystem error", detail)

    def test_oserror_on_source_read_is_benign(self) -> None:
        # v1.5.7 090q: an OSError on the source-read step (the only
        # I/O step _static_parse_ok now performs, after the rewrite
        # from py_compile.compile to the builtin compile()) is BENIGN
        # — the source we couldn't read isn't a parse defect; the
        # canonical readability check (`_readable_file`) runs upstream
        # in `_check_install_closure`. Pre-090q this test asserted
        # the opposite ("py_compile filesystem error" → False) — that
        # contract was wrong: the 2026-05-24 Ory Keto run3 Phase-0
        # false-failed because a sandbox-denied compile-cache write
        # was misreported as an install defect. 090q switches to the
        # builtin compile() (no disk I/O) and reclassifies residual
        # OSErrors as benign. SyntaxError remains fatal.
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sandboxed.py"
            p.write_text("y = 2\n", encoding="utf-8")
            with mock.patch.object(
                    Path, "read_bytes",
                    side_effect=OSError("exotic filesystem read failure")):
                ok, detail = v._static_parse_ok(p)
            self.assertTrue(
                ok,
                f"v1.5.7 090q: OSError on source-read must be BENIGN "
                f"(the canonical readability check runs upstream). "
                f"Got ok={ok}, detail={detail!r}.",
            )
            self.assertIsNotNone(detail)
            self.assertIn("benign", detail)
            self.assertIn("090q", detail)
            self.assertNotIn("parse failed", detail)

    def test_check_closure_does_not_misreport_oserror_as_parse_failure(
            self) -> None:
        # v1.5.7 090q: end-to-end pin — a bundled_module whose
        # source-read OSErrors must NOT surface as "py_compile parse
        # failed". Pre-090q this asserted that a "py_compile
        # filesystem error" finding WAS emitted; post-090q the
        # OSError is benign (the file's parse-check returns OK) so
        # the closure passes for that file. The remaining
        # 'install_partial' findings come from missing modules in the
        # synthetic minimal install — those are correct (they ARE
        # missing).
        with tempfile.TemporaryDirectory() as td:
            install_root = Path(td)
            # Lay down a minimal install so check_closure reaches the
            # static-parse branch for a bundled_module entry.
            bin_dir = install_root / "bin"
            bin_dir.mkdir(parents=True)
            (bin_dir / "__init__.py").write_text("", encoding="utf-8")
            with mock.patch.object(
                    Path, "read_bytes",
                    side_effect=OSError("sandbox denied")):
                findings = v.check_closure(install_root)
            parse_failed = [
                f for f in findings
                if f.get("detail", "").startswith("py_compile parse failed")
            ]
            self.assertEqual(
                parse_failed, [],
                f"OSError misreported as parse failure: {parse_failed}",
            )
            # And no "filesystem error" findings either — 090q
            # removed that classification entirely (the detail
            # string is benign now).
            fs_err = [
                f for f in findings
                if "py_compile filesystem error" in f.get("detail", "")
            ]
            self.assertEqual(
                fs_err, [],
                f"v1.5.7 090q removed the 'py_compile filesystem "
                f"error' classification (OSError is benign now); "
                f"got: {fs_err}",
            )


if __name__ == "__main__":
    unittest.main()
