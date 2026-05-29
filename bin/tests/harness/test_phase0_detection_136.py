"""v1.5.7 136 (resumed, Option B) — honest phase-0 probe detection.

The 2026-05-29 acceptance run's two substantively-correct opus runs
(gson, express) graded NOT-MET only because `phase0_first_probe`
was False. Diagnosis (the halted 136) found the binary
"prompt OR regex" framing missed a third axis:

  1. The validator emits `event=validation_complete nonce=<UUID>
     status=…` (the §3.4 anti-fabrication run-nonce), but the
     pre-136 `_RE_PHASE0_OK` expected `…complete status=ok` with no
     nonce between — so it matched only the AGENTS.md:212
     instructional QUOTE, resolving `status="ok"` by ACCIDENT.
  2. `first_probe_ok` required `probe_attempts == 1`, but a fresh
     target's designed remediation flow legitimately needs 3 probes
     (blocked → remediable → ok), so it was always False.

Option B (reviewer-ruled): nonce-tolerant regexes + distinct-nonce
counting + a new `first_probe_ok` semantic — reached `ok`, no
bare-path failure, and any extra probes were legitimate remediation
(blocked/remediable), NOT bare-path retries.

These pin: regex nonce-tolerance (both forms), the real-probe
matcher ignoring narration, the 3-probe blocked-remediable-ok
positive case, narration not inflating the count, bare-path staying
False, and the live gson/express transcripts.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from bin.harness import facts as F


# A narration line (AGENTS.md:212 style — NO nonce) + a deduped
# pair of stream lines per real probe (tool_use echo + tool_result).
_NARRATION = (
    "Do NOT proceed past Phase 0 until "
    "`event=validation_complete status=ok` — see AGENTS.md.\n")


def _probe(nonce: str, status: str, findings: int = 0) -> str:
    line = (f"tool <tool> event=validation_complete nonce={nonce} "
            f"status={status} findings={findings}\n")
    return line + line  # appears twice in a real stream


def _gson_like() -> str:
    return (
        _NARRATION
        + _probe("aaa111", "blocked", 1)
        + _probe("bbb222", "remediable", 3)
        + _probe("ccc333", "ok", 0)
    )


class RegexNonceToleranceTests(unittest.TestCase):

    def test_ok_matches_nonce_bearing_and_bare(self) -> None:
        self.assertTrue(F._RE_PHASE0_OK.search(
            "event=validation_complete nonce=abc123 status=ok"))
        self.assertTrue(F._RE_PHASE0_OK.search(
            "event=validation_complete status=ok"))

    def test_remediable_and_blocked_nonce_tolerant(self) -> None:
        self.assertTrue(F._RE_PHASE0_REMEDIABLE.search(
            "event=validation_complete nonce=x status=remediable"))
        self.assertTrue(F._RE_PHASE0_BLOCKED.search(
            "event=validation_complete nonce=y status=blocked"))

    def test_probe_matcher_requires_nonce_ignores_narration(
            self) -> None:
        # The real-probe matcher must NEVER match the AGENTS.md quote.
        self.assertIsNone(F._RE_PHASE0_PROBE.search(
            "event=validation_complete status=ok"))
        m = F._RE_PHASE0_PROBE.search(
            "event=validation_complete nonce=abc status=ok")
        self.assertIsNotNone(m)
        self.assertEqual(m.group("nonce"), "abc")
        self.assertEqual(m.group("status"), "ok")


class FirstProbeOkSemanticTests(unittest.TestCase):

    def test_three_probe_remediation_flow_is_first_probe_ok(
            self) -> None:
        """The gson/express case: blocked → remediable → ok across 3
        real probes ⇒ first_probe_ok=True (the NEW semantic)."""
        ph, _i, _b, _s = F.parse_transcript(_gson_like())
        self.assertEqual(ph.status, "ok")
        self.assertEqual(ph.probe_attempts, 3)
        self.assertTrue(ph.first_probe_ok)

    def test_narration_quote_not_counted_as_probe(self) -> None:
        """A transcript with the AGENTS.md narration + ONE real ok
        probe counts 1 probe (not 2) — narration never inflates."""
        txt = _NARRATION + _probe("only1", "ok", 0)
        ph, _i, _b, _s = F.parse_transcript(txt)
        self.assertEqual(ph.probe_attempts, 1)
        self.assertEqual(ph.status, "ok")
        self.assertTrue(ph.first_probe_ok)

    def test_single_clean_real_probe_is_first_probe_ok(self) -> None:
        ph, _i, _b, _s = F.parse_transcript(_probe("n1", "ok", 0))
        self.assertEqual(ph.probe_attempts, 1)
        self.assertTrue(ph.first_probe_ok)

    def test_bare_path_failure_with_nonce_probes_is_false(
            self) -> None:
        """A bare-path failure → False regardless of a later clean
        probe (090t guard preserved under the new semantic)."""
        txt = (
            "$ python3 bin/qpb_validate.py .\n"
            "[Errno 2] No such file or directory: "
            "'bin/qpb_validate.py'\n"
            + _probe("recover", "ok", 0)
        )
        ph, _i, _b, _s = F.parse_transcript(txt)
        self.assertFalse(ph.first_probe_ok)

    def test_final_blocked_probe_is_not_first_probe_ok(self) -> None:
        """A run that never reaches ok (blocked → blocked) is False
        and status=blocked (final real probe wins, not narration)."""
        txt = _NARRATION + _probe("b1", "blocked", 2) \
            + _probe("b2", "blocked", 2)
        ph, _i, _b, _s = F.parse_transcript(txt)
        self.assertEqual(ph.status, "blocked")
        self.assertFalse(ph.first_probe_ok)

    def test_distinct_nonce_dedupe(self) -> None:
        """Each real probe appears twice in a stream; counting is by
        DISTINCT nonce, so the doubled lines count once each."""
        ph, _i, _b, _s = F.parse_transcript(_gson_like())
        self.assertEqual(ph.probe_attempts, 3)  # not 6


class Pre136FallbackTests(unittest.TestCase):
    """No-nonce transcripts (older streams / bare-form fixtures)
    keep pre-136 behavior."""

    def test_bare_clean_run_first_probe_ok(self) -> None:
        ph, _i, _b, _s = F.parse_transcript(
            "event=validation_complete status=ok\n")
        self.assertEqual(ph.probe_attempts, 1)
        self.assertTrue(ph.first_probe_ok)

    def test_bare_path_failure_disables_first_probe(self) -> None:
        txt = (
            "$ python3 bin/qpb_validate.py .\n"
            "[Errno 2] No such file or directory: "
            "'bin/qpb_validate.py'\n"
            "event=validation_complete status=ok\n"
        )
        ph, _i, _b, _s = F.parse_transcript(txt)
        self.assertFalse(ph.first_probe_ok)


class LiveTranscriptTests(unittest.TestCase):
    """The diagnostic cases that motivated 136. Skips when the
    transient run dir is absent (repos/ is gitignored)."""

    _BASE = Path(__file__).resolve().parents[3] / (
        "repos/20260528T235659Z")

    @unittest.skipUnless(
        (_BASE / "run-00/stream.ndjson").is_file(),
        "live gson/express streams not present (transient repos/)")
    def test_real_gson_and_express_are_first_probe_ok(self) -> None:
        for run in ("run-00", "run-01"):
            txt = (self._BASE / run / "stream.ndjson").read_text(
                encoding="utf-8", errors="replace")
            ph, _i, _b, _s = F.parse_transcript(txt)
            self.assertEqual(ph.status, "ok", run)
            self.assertEqual(ph.probe_attempts, 3, run)
            self.assertTrue(ph.first_probe_ok, run)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
