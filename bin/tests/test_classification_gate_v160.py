"""v1.6.0 Feature G (instruction 024) — the classification-manifest gate check.

`check_classification_manifest(q)` makes a degraded reference-doc classification
LOUD: it WARNs (never FAILs) when the LLM classifier was unwired/failed
(classifier_status != "wired-ok") or when the corpus yielded no citable doc
(zero_citable), and stays inert when Feature G ingest never ran.
"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = (
    REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))

import quality_gate  # noqa: E402


class ClassificationGateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.q = Path(self._tmp.name) / "quality"
        self.q.mkdir(parents=True)

    def _write(self, payload):
        (self.q / "classification_manifest.json").write_text(
            json.dumps(payload), encoding="utf-8")

    def _run(self):
        quality_gate.FAIL = 0
        quality_gate.WARN = 0
        quality_gate._FAIL_RECORDS = []
        quality_gate._WARN_RECORDS = []
        buf = io.StringIO()
        with redirect_stdout(buf):
            quality_gate.check_classification_manifest(self.q)
        return quality_gate.FAIL, quality_gate.WARN, buf.getvalue()

    def test_inert_when_manifest_absent(self):
        fails, warns, _ = self._run()
        self.assertEqual((fails, warns), (0, 0))

    def test_clean_wired_ok_with_citable_is_silent(self):
        self._write({"classifier_status": "wired-ok", "zero_citable": False,
                     "citable_count": 2, "records": []})
        fails, warns, _ = self._run()
        self.assertEqual((fails, warns), (0, 0))

    def test_unwired_warns(self):
        self._write({"classifier_status": "unwired", "zero_citable": False,
                     "citable_count": 1, "records": []})
        fails, warns, out = self._run()
        self.assertEqual(fails, 0)
        self.assertEqual(warns, 1)
        self.assertIn("classifier_status='unwired'", out)
        self.assertIn("degraded", out)

    def test_error_warns(self):
        self._write({"classifier_status": "error", "classifier_error": "boom",
                     "zero_citable": False, "citable_count": 1, "records": []})
        fails, warns, out = self._run()
        self.assertEqual((fails, warns), (0, 1))
        self.assertIn("classifier_status='error'", out)

    def test_zero_citable_warns(self):
        self._write({"classifier_status": "wired-ok", "zero_citable": True,
                     "citable_count": 0, "records": []})
        fails, warns, out = self._run()
        self.assertEqual((fails, warns), (0, 1))
        self.assertIn("zero_citable", out)
        self.assertIn("code-derived", out)

    def test_unwired_and_zero_citable_both_warn(self):
        # The exact virtio-run collapse: no classifier AND no citable doc.
        self._write({"classifier_status": "unwired", "zero_citable": True,
                     "citable_count": 0, "records": []})
        fails, warns, _ = self._run()
        self.assertEqual(fails, 0)
        self.assertEqual(warns, 2)

    def test_never_fails(self):
        for payload in (
            {"classifier_status": "unwired", "zero_citable": True, "records": []},
            {"classifier_status": "error", "zero_citable": True, "records": []},
        ):
            self._write(payload)
            fails, _w, _o = self._run()
            self.assertEqual(fails, 0, payload)

    def test_carries_a_verdict_category(self):
        # Every check_* must carry a verdict category (the gate's test suite
        # asserts this; pin it for the new check too).
        self.assertTrue(
            hasattr(quality_gate.check_classification_manifest, "_VERDICT_CATEGORY"))


if __name__ == "__main__":
    unittest.main()
