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

    # --- v1.6.0 instruction 033: the three-lane disclosures reach the gate ----
    # Panelist B (B-4): step 2 requires the `unconfirmed` provenance to flow
    # manifest -> show -> gate WARN -> Stage-1 playback. It reached the show and
    # stopped, so a headless run grounded entirely on the model's own unconfirmed
    # read passed this gate in silence — the same shape as the virtio Tier-4
    # collapse this check exists for: not a wrong answer, an unstated one.

    def _clean(self, **extra):
        payload = {"classifier_status": "wired-ok", "zero_citable": False,
                   "citable_count": 1, "records": []}
        payload.update(extra)
        self._write(payload)

    def test_unconfirmed_citations_warn(self):
        self._clean(unconfirmed_citable_count=2)
        fails, warns, out = self._run()
        self.assertEqual((fails, warns), (0, 1))
        self.assertIn("unconfirmed_citable_count=2", out)
        self.assertIn("model's own read alone", out)

    def test_documents_awaiting_the_operator_warn(self):
        self._clean(awaiting_confirmation_count=3)
        fails, warns, out = self._run()
        self.assertEqual((fails, warns), (0, 1))
        self.assertIn("awaiting_confirmation_count=3", out)

    def test_unread_documents_warn_once_the_classifier_is_wired(self):
        # Panelist B (B2-3). The corpus-level sibling of the four counters above.
        self._clean(unread_count=7)
        fails, warns, out = self._run()
        self.assertEqual((fails, warns), (0, 1))
        self.assertIn("unread_count=7", out)
        self.assertIn("never read", out)

    def test_unread_does_not_double_alarm_an_unwired_run(self):
        # When the classifier is not wired, `classifier_status` already says
        # nothing was read; repeating it as `unread_count` would be the same alarm
        # twice and would train the reader to skip both.
        self._write({"classifier_status": "unwired", "zero_citable": True,
                     "citable_count": 0, "unread_count": 7, "records": []})
        fails, warns, out = self._run()
        self.assertEqual(fails, 0)
        self.assertEqual(warns, 2, "classifier_status + zero_citable, not three")
        self.assertNotIn("unread_count=7", out)

    def test_a_refused_promotion_warns(self):
        self._clean(refused_promotions=["reference_docs/cve_spec.md"])
        fails, warns, out = self._run()
        self.assertEqual((fails, warns), (0, 1))
        self.assertIn("cve_spec.md", out)
        self.assertIn("name the signal", out)

    def test_a_superseded_control_file_warns(self):
        self._clean(conversion_note="reference_docs/qpb_promote.txt is not applied")
        fails, warns, out = self._run()
        self.assertEqual((fails, warns), (0, 1))
        self.assertIn("qpb_promote.txt", out)

    def test_a_clean_manifest_is_silent(self):
        # The control: none of the four new WARNs fires on a healthy run, so they
        # stay signal rather than noise.
        self._clean()
        fails, warns, _out = self._run()
        self.assertEqual((fails, warns), (0, 0))

    def test_zero_and_absent_are_both_silent(self):
        # An absent key (a pre-033 manifest) and an explicit zero must behave the
        # same — "no unconfirmed citations" is not a finding.
        for extra in ({}, {"unconfirmed_citable_count": 0,
                           "awaiting_confirmation_count": 0,
                           "refused_promotions": [], "conversion_note": ""}):
            self._clean(**extra)
            fails, warns, _o = self._run()
            self.assertEqual((fails, warns), (0, 0), extra)
        self._clean(unread_count=0)
        self.assertEqual(self._run()[:2], (0, 0))

    def test_the_new_warns_never_fail(self):
        self._clean(unconfirmed_citable_count=5, awaiting_confirmation_count=5,
                    refused_promotions=["a.md"], conversion_note="x")
        fails, warns, _o = self._run()
        self.assertEqual(fails, 0)
        self.assertEqual(warns, 4)

    def test_carries_a_verdict_category(self):
        # Every check_* must carry a verdict category (the gate's test suite
        # asserts this; pin it for the new check too).
        self.assertTrue(
            hasattr(quality_gate.check_classification_manifest, "_VERDICT_CATEGORY"))


if __name__ == "__main__":
    unittest.main()
