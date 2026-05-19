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

    def test_oserror_is_filesystem_error(self) -> None:
        # An OSError out of py_compile (sandbox / permissions / fd)
        # must NOT be misreported as a source parse failure.
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sandboxed.py"
            p.write_text("y = 2\n", encoding="utf-8")
            with mock.patch.object(
                    v.py_compile, "compile",
                    side_effect=OSError("sandbox: operation not permitted")):
                ok, detail = v._static_parse_ok(p)
            self.assertFalse(ok)
            self.assertIsNotNone(detail)
            self.assertIn("py_compile filesystem error:", detail)
            self.assertIn("OSError", detail)
            self.assertIn("sandbox: operation not permitted", detail)
            self.assertNotIn("parse failed", detail)

    def test_check_closure_propagates_distinct_detail(self) -> None:
        # End-to-end: a bundled_module that py_compile-OSErrors must
        # surface the filesystem-error detail through check_closure,
        # NOT "py_compile parse failed".
        with tempfile.TemporaryDirectory() as td:
            install_root = Path(td)
            # Lay down a minimal install so check_closure reaches the
            # static-parse branch for a bundled_module entry.
            bin_dir = install_root / "bin"
            bin_dir.mkdir(parents=True)
            (bin_dir / "__init__.py").write_text("", encoding="utf-8")
            with mock.patch.object(
                    v.py_compile, "compile",
                    side_effect=OSError("sandbox denied")):
                findings = v.check_closure(install_root)
            parse_failed = [
                f for f in findings
                if f.get("detail", "").startswith("py_compile parse failed")
            ]
            fs_err = [
                f for f in findings
                if "py_compile filesystem error" in f.get("detail", "")
            ]
            # No bundled_module should be reported as a parse failure
            # when the underlying cause is an OSError.
            self.assertEqual(
                parse_failed, [],
                f"OSError misreported as parse failure: {parse_failed}")
            self.assertTrue(
                fs_err,
                "expected at least one py_compile filesystem error "
                f"finding; got {[f.get('detail') for f in findings]}")


if __name__ == "__main__":
    unittest.main()
