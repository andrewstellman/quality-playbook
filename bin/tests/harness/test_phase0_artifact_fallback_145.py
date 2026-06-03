"""v1.5.7 145 — witness status/findings + Phase-0 artifact fallback
(closes 143 A′).

143 found a harness observability gap: non-Claude runners (copilot
/ codex / cursor) emit boxed-TUI streams that don't capture the
validator's ``event=validation_complete status=… findings=…``
stdout, so ``facts.parse_transcript`` saw zero probes and defaulted
to ``blocked`` / not-ok even when the validator actually ran clean
(keto: 6 disk witnesses + a terminal Phase-6 verdict, zero
``event=`` lines in the stream).

145 (A) persists ``status=``/``findings=`` to the validator witness
``<target>/quality/.qpb_validation_<ts>_<nonce>.txt`` and (B) makes
``parse_transcript`` fall back to those witnesses for Phase-0 facts
when the stream has no probes. Stream probes always win when
present; pre-145 witnesses (no ``status=``) are silently skipped.
Same shape as 137's gate-log artifact fallback.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bin.harness.facts import (
    parse_transcript, _phase0_probes_from_witnesses)


def _witness(qdir: Path, ts: str, nonce: str, *,
             status: "str | None" = None, findings: int = 0) -> None:
    body = (f"nonce={nonce}\ntimestamp={ts}\ncwd=/x\n"
            f"argv=['/x']\nplatform=macos\n"
            f"invocation_context=installed\n")
    if status is not None:
        body += f"status={status}\nfindings={findings}\n"
    (qdir / f".qpb_validation_{ts}_{nonce}.txt").write_text(
        body, encoding="utf-8")


def _qdir(td: str) -> Path:
    q = Path(td) / "quality"
    q.mkdir(parents=True, exist_ok=True)
    return q


# ---------------------------------------------------------------------------
# witness parsing
# ---------------------------------------------------------------------------


class WitnessParseTests(unittest.TestCase):

    def test_witness_carries_status_field(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            q = _qdir(td)
            _witness(q, "20260529T040600Z", "aaa",
                     status="remediable", findings=3)
            probes, bare = _phase0_probes_from_witnesses(Path(td))
            self.assertEqual(probes, ["remediable"])
            self.assertFalse(bare)

    def test_pre145_witness_silently_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            q = _qdir(td)
            _witness(q, "20260529T040600Z", "old", status=None)
            probes, bare = _phase0_probes_from_witnesses(Path(td))
            self.assertEqual(probes, [])
            self.assertFalse(bare)

    def test_witness_distinct_nonce_dedup(self) -> None:
        # 4 witness files, 3 unique nonces (one nonce repeated) → 3.
        with tempfile.TemporaryDirectory() as td:
            q = _qdir(td)
            _witness(q, "20260529T040600Z", "n1", status="blocked", findings=1)
            _witness(q, "20260529T040610Z", "n2", status="remediable", findings=2)
            _witness(q, "20260529T040620Z", "n2", status="remediable", findings=2)
            _witness(q, "20260529T040630Z", "n3", status="ok", findings=0)
            probes, _ = _phase0_probes_from_witnesses(Path(td))
            self.assertEqual(probes, ["blocked", "remediable", "ok"])

    def test_no_quality_dir_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            probes, bare = _phase0_probes_from_witnesses(Path(td))
            self.assertEqual((probes, bare), ([], False))


# ---------------------------------------------------------------------------
# parse_transcript artifact fallback
# ---------------------------------------------------------------------------


class ArtifactFallbackTests(unittest.TestCase):

    def test_fallback_fires_when_stream_has_no_events(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            q = _qdir(td)
            _witness(q, "20260529T040600Z", "a", status="blocked", findings=1)
            _witness(q, "20260529T040610Z", "b", status="remediable", findings=3)
            _witness(q, "20260529T040620Z", "c", status="ok", findings=0)
            ph, _i, _b, _s = parse_transcript("", target_dir=Path(td))
            self.assertEqual(ph.status, "ok")
            self.assertEqual(ph.probe_attempts, 3)
            self.assertTrue(ph.first_probe_ok)

    def test_stream_events_still_win_over_artifact_fallback(
            self) -> None:
        """Precedence: a stream probe present ⇒ witnesses ignored.
        Mutation-bite: drop the `not real_probes` guard (always use
        witnesses) ⇒ this returns the blocked witness ⇒ fails."""
        with tempfile.TemporaryDirectory() as td:
            q = _qdir(td)
            _witness(q, "20260529T040600Z", "w", status="blocked", findings=9)
            ph, _i, _b, _s = parse_transcript(
                "event=validation_complete nonce=strm status=ok\n",
                target_dir=Path(td))
            self.assertEqual(ph.status, "ok")
            self.assertEqual(ph.probe_attempts, 1)  # the stream probe, not the witness
            self.assertTrue(ph.first_probe_ok)

    def test_zero_witnesses_falls_through_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            _qdir(td)  # empty quality/ dir, no witnesses
            ph, _i, _b, _s = parse_transcript("", target_dir=Path(td))
            self.assertEqual(ph.status, "blocked")
            self.assertFalse(ph.first_probe_ok)

    def test_target_dir_none_preserves_pre145_behavior(self) -> None:
        ph, _i, _b, _s = parse_transcript("")  # no target_dir
        self.assertEqual(ph.status, "blocked")
        self.assertFalse(ph.first_probe_ok)

    def test_bare_path_fail_witness_disables_first_probe(self) -> None:
        """A bare-path-fail witness demotes first_probe_ok even with a
        later ok — preserves the 136 v2 Halt #3 invariant via the
        artifact path."""
        with tempfile.TemporaryDirectory() as td:
            q = _qdir(td)
            _witness(q, "20260529T040600Z", "a", status="bare-path-fail", findings=1)
            _witness(q, "20260529T040610Z", "b", status="ok", findings=0)
            ph, _i, _b, _s = parse_transcript("", target_dir=Path(td))
            self.assertFalse(ph.first_probe_ok)


# ---------------------------------------------------------------------------
# end-to-end: validator writes the new witness fields
# ---------------------------------------------------------------------------


class ValidatorWitnessFormatTests(unittest.TestCase):

    def test_witness_file_contains_status_field(self) -> None:
        """Invoke the real validator against a temp target; its
        witness must carry both status= and findings=."""
        with tempfile.TemporaryDirectory() as td:
            proc = subprocess.run(
                [sys.executable, "-m", "bin.qpb_validate", td],
                capture_output=True, text=True,
                cwd=str(Path(__file__).resolve().parents[3]))
            self.assertIn(proc.returncode, (0, 1, 2))  # any validator verdict
            witnesses = list(
                (Path(td) / "quality").glob(".qpb_validation_*.txt"))
            self.assertTrue(witnesses, "validator wrote no witness")
            content = witnesses[0].read_text(encoding="utf-8")
            self.assertIn("status=", content)
            self.assertIn("findings=", content)


class KetoRealWitnessTests(unittest.TestCase):
    """The 143 diagnostic run. Its witnesses are PRE-145 (no
    status=), so the fallback must skip them gracefully. (A future
    post-145 copilot run would write status-bearing witnesses; this
    test gets tightened then.)"""

    _KETO = Path(__file__).resolve().parents[3] / (
        "repos/20260529T040543Z/run-03/target")

    @unittest.skipUnless(
        (_KETO / "quality").is_dir(),
        "live keto run-03 target not present (transient repos/)")
    def test_keto_pre145_witnesses_skipped_gracefully(self) -> None:
        probes, bare = _phase0_probes_from_witnesses(self._KETO)
        # pre-145 witnesses carry no status= → all skipped, no crash.
        self.assertEqual(probes, [])
        self.assertFalse(bare)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
