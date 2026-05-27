"""v1.5.7 117 — phase-progress visibility: the status layer must
parse the REAL embedded Mode A sentinel + the Mode B
``Phase N/6 (Name)`` run_playbook lines, AND surface
progress + last-activity in the list view.

The bug: ``status.parse_sentinels`` was anchored on
``^::QPB:: (\\{.+\\})$`` — it matched 109's bare-line fixture
form but missed every REAL ``claude --print --output-format
stream-json`` stream, where the 109 sentinel is emitted to
stdout, captured by Claude as the ``content`` of a
``tool_result`` event, and JSON-escaped inside the outer
event (no line ever starts with ``::QPB::``). The current-
phase column always showed "—" in real runs.

The fixture-vs-reality gap is what hid the bug: 109/110/111
tests used clean bare lines, so the regex passed; the live
AUP experiment was the first time the parser saw realistic
input.

117 fix:
  * ``parse_sentinels`` now walks every string inside each
    JSON-decoded event line and finds ``::QPB:: {...}``
    substrings. Falls back to a raw scan for non-JSON lines
    (preserves the 109 bare-line form for back-compat).
  * NEW ``_mode_b_phase_from_stream`` reads
    ``Phase N/6 (Name)`` lines from a run_playbook stream
    (Mode B has no ``::QPB::``).
  * ``_read_one_run_status`` tries the sentinel parse first
    and falls back to the Mode B parse. Adds ``elapsed_s``
    + ``last_activity_iso`` per run.
  * ``_summarize_harness_run`` adds ``progress`` (max phase
    across runs) + ``last_activity_iso`` (newest stream
    mtime) to the list-view row.

Coverage:
  * ``parse_sentinels`` against the REAL embedded fixture
    (copied from
    ``aup-experiment/20260527T145902Z/run-00/stream.ndjson``).
    Mutation-bite: revert the parser to the anchored
    ``_SENTINEL_RE.match`` and this test FAILS (returns no
    payloads).
  * Mode B ``_mode_b_phase_from_stream`` parses the last
    ``Phase N/6 (Name)`` line correctly.
  * ``_read_one_run_status`` populates current-phase for
    both modes, and the new elapsed/last-activity fields.
  * ``_summarize_harness_run`` populates progress +
    last-activity.
  * Bare-line back-compat preserved (109 fixture form still
    works).
  * ``render_stream_line`` still renders bare-line sentinels
    (the tail-rendering path is unchanged — it operates on
    one line at a time).
  * Module import side-effect-free (111 invariant).
  * Bundle-safety.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from bin.harness import status as ST


_REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# REAL embedded-sentinel fixture (copied verbatim from the AUP experiment)
# ---------------------------------------------------------------------------


# A real ``claude --print --output-format stream-json`` line: the
# 109 sentinel emitted to stdout by ``qpb_phase`` is captured by
# Claude as the ``content`` of a ``tool_result`` event AND
# duplicated in ``tool_use_result.stdout``. Both forms appear in
# the same event. Pre-117 the anchored ``^::QPB::`` regex matched
# NEITHER (the line starts with ``{``, not ``::QPB::``).
_REAL_EMBEDDED_LINE = (
    '{"type":"user","message":{"role":"user","content":[{'
    '"tool_use_id":"toolu_01PXjsTCoGhQEy2cgdTbE5Cc",'
    '"type":"tool_result","content":"::QPB:: {\\"v\\":1,'
    '\\"kind\\":\\"phase\\",\\"phase\\":1,\\"name\\":'
    '\\"exploration\\",\\"state\\":\\"start\\",\\"ts\\":'
    '\\"2026-05-27T15:01:22Z\\"}","is_error":false}]},'
    '"parent_tool_use_id":null,"session_id":'
    '"12c8f554-7928-4c15-b04b-45327af70259","uuid":'
    '"ce55d4ca-7821-4c67-b1c8-c051cc0b931c","timestamp":'
    '"2026-05-27T15:01:23.004Z","tool_use_result":{"stdout":'
    '"::QPB:: {\\"v\\":1,\\"kind\\":\\"phase\\",\\"phase\\":'
    '1,\\"name\\":\\"exploration\\",\\"state\\":\\"start\\",'
    '\\"ts\\":\\"2026-05-27T15:01:22Z\\"}","stderr":"",'
    '"interrupted":false,"isImage":false,'
    '"noOutputExpected":false}}'
)


def _embedded_sentinel_event(*, phase: int, name: str,
                                 state: str, ts: str) -> str:
    """Build a Claude stream-json event line carrying a
    ``::QPB::`` phase sentinel embedded in tool_result.content
    + tool_use_result.stdout. Mirrors the real shape so tests
    can vary the phase/name/state without hand-escaping."""
    payload_str = json.dumps({
        "v": 1, "kind": "phase", "phase": phase,
        "name": name, "state": state, "ts": ts,
    })
    sentinel_text = f"::QPB:: {payload_str}"
    event = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{
                "tool_use_id": "toolu_test",
                "type": "tool_result",
                "content": sentinel_text,
                "is_error": False,
            }],
        },
        "tool_use_result": {
            "stdout": sentinel_text,
            "stderr": "",
        },
    }
    return json.dumps(event)


# ---------------------------------------------------------------------------
# Task A — parse_sentinels against the REAL embedded shape
# ---------------------------------------------------------------------------


class ParseSentinelsEmbeddedFormTests(unittest.TestCase):
    """The 117 fix's primary contract: ``parse_sentinels``
    must find the ``::QPB::`` payload when it's embedded
    inside a Claude stream-json event's text fields."""

    def test_real_embedded_line_parses(self) -> None:
        """**THE 117 LOAD-BEARING TEST**: a real
        ``stream.ndjson`` line (copied verbatim from the AUP
        experiment) ⇒ ``parse_sentinels`` returns ONE
        ``kind:"phase"`` payload with phase=1,
        name="exploration", state="start".

        Pre-117 the anchored ``^::QPB::`` regex matched NEITHER
        the bare-line shape NOR the embedded shape — it
        required the line to start with ``::QPB::``, but the
        real line starts with ``{"type":"user"...``. The
        rewritten parser walks every string inside the JSON-
        decoded event tree and finds the embedded sentinel."""
        payloads = ST.parse_sentinels(_REAL_EMBEDDED_LINE)
        # Exactly one logical sentinel — even though the same
        # sentinel string appears twice in the event (once in
        # tool_result.content + once in tool_use_result.stdout),
        # the parser dedupes by payload equality.
        self.assertEqual(
            len(payloads), 1,
            f"117: parse_sentinels MUST find the embedded "
            f"sentinel exactly once (got {len(payloads)} "
            f"payloads: {payloads})",
        )
        p = payloads[0]
        self.assertEqual(p.get("kind"), "phase")
        self.assertEqual(p.get("phase"), 1)
        self.assertEqual(p.get("name"), "exploration")
        self.assertEqual(p.get("state"), "start")

    def test_mutation_bite_anchored_regex_misses_embedded(
            self) -> None:
        """**Pre-117 baseline** (proves the bug existed): the
        pre-117 anchored ``_SENTINEL_RE.match`` on a real
        embedded line returns NO match — the line starts with
        ``{``, not ``::QPB::``. Asserting this guarantees the
        117 test's mutation-bite asymmetry: the new parser
        finds the embedded sentinel; the old anchored regex
        could not. If a future refactor reintroduces the
        anchor, ``test_real_embedded_line_parses`` immediately
        fails."""
        import re
        anchored = re.compile(r"^::QPB:: (\{.+\})$")
        m = anchored.match(_REAL_EMBEDDED_LINE)
        self.assertIsNone(
            m,
            "117 mutation-bite proof: the pre-117 anchored "
            "regex must NOT match a real embedded line — if "
            "it did, the pre-117 parser would have worked and "
            "the bug wouldn't have existed.",
        )

    def test_progressive_phases_yield_progressive_sentinels(
            self) -> None:
        """A stream with multiple embedded sentinels (one
        per phase boundary) ⇒ ``parse_sentinels`` returns
        each in order. ``_read_one_run_status`` takes the
        LAST one for current-phase derivation."""
        lines = "\n".join([
            _embedded_sentinel_event(
                phase=1, name="exploration", state="start",
                ts="2026-05-27T15:01:22Z"),
            _embedded_sentinel_event(
                phase=1, name="exploration", state="done",
                ts="2026-05-27T15:30:00Z"),
            _embedded_sentinel_event(
                phase=2, name="generation", state="start",
                ts="2026-05-27T15:30:01Z"),
        ])
        payloads = ST.parse_sentinels(lines)
        self.assertEqual(len(payloads), 3)
        self.assertEqual(payloads[-1].get("phase"), 2)
        self.assertEqual(payloads[-1].get("state"), "start")

    def test_bare_line_form_still_works(self) -> None:
        """**Back-compat pin**: the 109 fixture bare-line form
        (``::QPB:: {...}`` as a literal line) must still be
        parsed. 117 adds the embedded form WITHOUT regressing
        the bare-line form — both are reached via the raw text
        scan (non-JSON lines fall through to it)."""
        bare = (
            '::QPB:: {"v":1,"kind":"phase","phase":2,'
            '"name":"generation","state":"done",'
            '"ts":"2026-05-27T15:00:00Z"}'
        )
        payloads = ST.parse_sentinels(bare)
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0].get("phase"), 2)
        self.assertEqual(payloads[0].get("name"), "generation")

    def test_malformed_inner_payload_skipped(self) -> None:
        """A line with ``::QPB:: {not-json}`` ⇒ payload skipped
        silently, not raised."""
        event = (
            '{"type":"user","message":{"content":[{"type":'
            '"tool_result","content":"::QPB:: {bogus}"}]}}'
        )
        payloads = ST.parse_sentinels(event)
        self.assertEqual(payloads, [])

    def test_empty_stream_returns_empty(self) -> None:
        self.assertEqual(ST.parse_sentinels(""), [])
        self.assertEqual(ST.parse_sentinels("   \n\n"), [])


# ---------------------------------------------------------------------------
# Task B — Mode B `Phase N/6 (Name)` parser
# ---------------------------------------------------------------------------


class ModeBPhaseFromStreamTests(unittest.TestCase):
    """Mode B run_playbook prints lines like
    ``10:59:05   Phase 1/6 (Explore): target``. The 117 fix
    adds ``_mode_b_phase_from_stream`` so the status layer can
    report current phase for Mode B too (no ::QPB:: sentinel
    in those streams)."""

    def test_last_phase_n_6_line_wins(self) -> None:
        """A Mode B stream with phases 1 → 2 → 3 ⇒ the last
        wins (current phase = 3)."""
        stream = (
            "10:59:05   Phase 1/6 (Explore): target\n"
            "  ...\n"
            "11:30:00   Phase 2/6 (Generate): target\n"
            "  ...\n"
            "12:00:00   Phase 3/6 (Review): target\n"
        )
        out = ST._mode_b_phase_from_stream(stream)
        self.assertIsNotNone(out)
        self.assertEqual(out["kind"], "phase")
        self.assertEqual(out["phase"], 3)
        # 117 normalizes to the 109 canonical name
        # (run_playbook says "Review"; 109 says "code-review").
        self.assertEqual(out["name"], "code-review")
        # No start/done in the Mode B banner — use a sentinel.
        self.assertEqual(out["state"], "running")

    def test_no_phase_line_returns_none(self) -> None:
        """A stream with no ``Phase N/6 (...)`` lines ⇒ None
        (so the caller knows to fall through to "—" or to
        whatever signal it has)."""
        self.assertIsNone(
            ST._mode_b_phase_from_stream(""))
        self.assertIsNone(
            ST._mode_b_phase_from_stream(
                "10:59:05   doing things\n"))

    def test_canonical_name_per_phase(self) -> None:
        """Each phase number maps to the 109 canonical name
        (exploration / generation / code-review / spec-audit /
        reconciliation / verification)."""
        cases = [
            (1, "exploration"),
            (2, "generation"),
            (3, "code-review"),
            (4, "spec-audit"),
            (5, "reconciliation"),
            (6, "verification"),
        ]
        for n, expected in cases:
            stream = f"  Phase {n}/6 (Whatever): target\n"
            out = ST._mode_b_phase_from_stream(stream)
            self.assertIsNotNone(out)
            self.assertEqual(
                out["name"], expected,
                f"phase {n} should normalize to "
                f"{expected!r}, got {out['name']!r}",
            )

    def test_malformed_phase_number_falls_through(
            self) -> None:
        """``Phase X/6 (Whatever)`` where X isn't a digit ⇒
        regex won't match (``\\d+``) so we return None."""
        out = ST._mode_b_phase_from_stream(
            "  Phase X/6 (Whatever): target\n")
        self.assertIsNone(out)


# ---------------------------------------------------------------------------
# Task A+B — _read_one_run_status integration
# ---------------------------------------------------------------------------


def _write_minimal_manifest(harness_run_dir: Path, *,
                              run_dir: Path,
                              stream_lines: "list[str]",
                              terminal_state: "str | None" = None,
                              started_at: str = "") -> Path:
    """Stand up a minimal harness-run with one run that has
    a stream.ndjson. Returns the path to the harness_run_dir."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "stream.ndjson").write_text(
        "\n".join(stream_lines) + "\n", encoding="utf-8")
    manifest = {
        "harness_run_dir": str(harness_run_dir),
        "plan": {"pools": {"claude": 1}},
        "runs": [{
            "index": 0, "description": "117 test",
            "repo": "https://github.com/x/y",
            "runner": "claude", "model": "opus",
            "channel": "clone", "mode": "A",
            "target_dir": str(run_dir / "target"),
            "run_dir": str(run_dir),
            "run_id": "r", "pid": None,
            "started_at": started_at,
            "stream_path": str(run_dir / "stream.ndjson"),
            "status_path": str(run_dir / "status.json"),
            "max_duration_s": 60.0,
            "expect": {},
            **({"terminal_state": terminal_state}
                if terminal_state else {}),
        }],
    }
    (harness_run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return harness_run_dir


class ReadOneRunStatusModeATests(unittest.TestCase):
    """``_read_one_run_status`` derives current-phase from the
    embedded sentinel; pre-117 it always showed "—" for real
    streams."""

    def test_mode_a_current_phase_populated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            harness_run = runs_root / "run-2026-05-27T15-00-00"
            harness_run.mkdir()
            run_dir = harness_run / "run-00"
            _write_minimal_manifest(
                harness_run,
                run_dir=run_dir,
                stream_lines=[
                    _embedded_sentinel_event(
                        phase=2, name="generation",
                        state="start",
                        ts="2026-05-27T15:30:00Z"),
                ],
            )
            runs = ST.read_run_status(harness_run)
            self.assertEqual(len(runs), 1)
            # **THE 117 LOAD-BEARING ASSERTION**: current_phase
            # populates, not "—".
            self.assertEqual(runs[0].current_phase, "P2")
            self.assertEqual(runs[0].current_phase_name,
                              "generation")
            self.assertEqual(runs[0].current_phase_state,
                              "start")

    def test_mode_b_current_phase_via_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            harness_run = runs_root / "run-2026-05-27T15-00-01"
            harness_run.mkdir()
            run_dir = harness_run / "run-00"
            _write_minimal_manifest(
                harness_run,
                run_dir=run_dir,
                stream_lines=[
                    "10:59:05   Phase 1/6 (Explore): target",
                    "11:30:00   Phase 3/6 (Review): target",
                ],
            )
            runs = ST.read_run_status(harness_run)
            self.assertEqual(runs[0].current_phase, "P3")
            self.assertEqual(runs[0].current_phase_name,
                              "code-review")
            self.assertEqual(runs[0].current_phase_state,
                              "running")

    def test_no_signal_degrades_to_dash(self) -> None:
        """No ``::QPB::`` sentinel AND no Mode B phase line
        ⇒ current_phase stays at "—" (graceful)."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            harness_run = runs_root / "run-2026-05-27T15-00-02"
            harness_run.mkdir()
            run_dir = harness_run / "run-00"
            _write_minimal_manifest(
                harness_run,
                run_dir=run_dir,
                stream_lines=["just some text"],
            )
            runs = ST.read_run_status(harness_run)
            self.assertEqual(runs[0].current_phase, "—")
            self.assertEqual(runs[0].current_phase_name, "—")


# ---------------------------------------------------------------------------
# Task C — list-view progress + last_activity (HarnessRunSummary)
# ---------------------------------------------------------------------------


class HarnessRunSummaryProgressTests(unittest.TestCase):
    """``HarnessRunSummary`` now exposes ``progress`` (max
    phase across runs) and ``last_activity_iso`` (newest
    stream mtime across runs). Both surface in
    ``format_harness_run_summary``."""

    def test_progress_takes_max_phase_across_runs(
            self) -> None:
        """Two runs, one at P1, one at P3 ⇒ progress=P3/P6
        (the front of the pack)."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            harness_run = runs_root / "run-2026-05-27T15-00-00"
            harness_run.mkdir()
            # Run 0: P1
            (harness_run / "run-00").mkdir()
            (harness_run / "run-00" / "stream.ndjson").write_text(
                _embedded_sentinel_event(
                    phase=1, name="exploration",
                    state="start",
                    ts="2026-05-27T15:01:00Z") + "\n",
                encoding="utf-8",
            )
            # Run 1: P3
            (harness_run / "run-01").mkdir()
            (harness_run / "run-01" / "stream.ndjson").write_text(
                _embedded_sentinel_event(
                    phase=3, name="code-review",
                    state="start",
                    ts="2026-05-27T16:00:00Z") + "\n",
                encoding="utf-8",
            )
            manifest = {
                "harness_run_dir": str(harness_run),
                "plan": {"pools": {"claude": 1}},
                "runs": [
                    {"index": i, "description": "x",
                     "repo": "y", "runner": "claude",
                     "model": "opus", "channel": "clone",
                     "mode": "A",
                     "target_dir": str(harness_run
                                         / f"run-0{i}"
                                         / "target"),
                     "run_dir": str(harness_run
                                      / f"run-0{i}"),
                     "run_id": f"r{i}", "pid": None,
                     "started_at": "",
                     "stream_path": str(harness_run
                                          / f"run-0{i}"
                                          / "stream.ndjson"),
                     "status_path": str(harness_run
                                          / f"run-0{i}"
                                          / "status.json"),
                     "max_duration_s": 60.0,
                     "expect": {}}
                    for i in (0, 1)
                ],
            }
            (harness_run / "manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            [summary] = ST.list_harness_runs(runs_root)
            self.assertEqual(summary.progress, "P3/P6")

    def test_progress_dash_when_no_run_has_phase(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            harness_run = runs_root / "run-2026-05-27T15-00-01"
            harness_run.mkdir()
            run_dir = harness_run / "run-00"
            _write_minimal_manifest(
                harness_run,
                run_dir=run_dir,
                stream_lines=["no sentinel here"],
            )
            [summary] = ST.list_harness_runs(runs_root)
            self.assertEqual(summary.progress, "—")

    def test_last_activity_reflects_stream_mtime(
            self) -> None:
        """The newest stream-write across all runs ⇒
        ``last_activity_iso`` is non-"—" and roughly equals
        the file mtime in ISO form."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            harness_run = runs_root / "run-2026-05-27T15-00-02"
            harness_run.mkdir()
            run_dir = harness_run / "run-00"
            _write_minimal_manifest(
                harness_run,
                run_dir=run_dir,
                stream_lines=["activity"],
            )
            [summary] = ST.list_harness_runs(runs_root)
            self.assertNotEqual(summary.last_activity_iso, "—")
            # ISO8601-ish (2026-...) — present means we set it.
            self.assertTrue(
                summary.last_activity_iso.startswith("2026"),
                f"expected ISO8601 timestamp, got "
                f"{summary.last_activity_iso!r}",
            )

    def test_format_includes_progress_and_active(self) -> None:
        """``format_harness_run_summary`` renders ``progress=``
        and ``active=`` so they show up in
        ``qpb_harness status``."""
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            harness_run = runs_root / "run-2026-05-27T15-00-03"
            harness_run.mkdir()
            run_dir = harness_run / "run-00"
            _write_minimal_manifest(
                harness_run,
                run_dir=run_dir,
                stream_lines=[
                    _embedded_sentinel_event(
                        phase=2, name="generation",
                        state="done",
                        ts="2026-05-27T15:30:00Z"),
                ],
            )
            [summary] = ST.list_harness_runs(runs_root)
            line = ST.format_harness_run_summary(summary)
            self.assertIn("progress=", line)
            self.assertIn("P2/P6", line)
            self.assertIn("active=", line)


# ---------------------------------------------------------------------------
# Task C — drill-down elapsed + last_activity (format_run_status)
# ---------------------------------------------------------------------------


class FormatRunStatusElapsedTests(unittest.TestCase):
    """``format_run_status`` now renders ``elapsed=`` and
    ``last=`` for the drill-down row."""

    def test_render_includes_elapsed_and_last(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            harness_run = runs_root / "run-2026-05-27T15-00-00"
            harness_run.mkdir()
            run_dir = harness_run / "run-00"
            _write_minimal_manifest(
                harness_run,
                run_dir=run_dir,
                stream_lines=[
                    _embedded_sentinel_event(
                        phase=1, name="exploration",
                        state="start",
                        ts="2026-05-27T15:01:00Z"),
                ],
                started_at="2026-05-27T15:00:00Z",
            )
            [rs] = ST.read_run_status(harness_run)
            line = ST.format_run_status(rs)
            self.assertIn("elapsed=", line)
            self.assertIn("last=", line)
            # The phase should also appear (the 117 fix's
            # whole point).
            self.assertIn("P1", line)
            self.assertIn("exploration", line)

    def test_elapsed_format_helper(self) -> None:
        """Pure helper: seconds → human-friendly string."""
        self.assertEqual(ST._format_elapsed(None), "—")
        self.assertEqual(ST._format_elapsed(42), "42s")
        self.assertEqual(ST._format_elapsed(125), "2m05s")
        self.assertEqual(ST._format_elapsed(3725), "1h02m")


# ---------------------------------------------------------------------------
# 111 invariant — module import is side-effect-free
# ---------------------------------------------------------------------------


class ImportSafetyTests(unittest.TestCase):

    def test_status_import_clean(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-c",
              "from bin.harness import status; "
              "assert callable(status.parse_sentinels)"],
            cwd=str(_REPO_ROOT),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(
            proc.returncode, 0,
            f"bin.harness.status import failed: "
            f"{proc.stderr[:400]!r}",
        )


# ---------------------------------------------------------------------------
# Bundle-safety: 117 lives under bin/harness/ (excluded)
# ---------------------------------------------------------------------------


class BundleSafety117Tests(unittest.TestCase):

    def test_status_changes_stay_under_harness(self) -> None:
        from bin.install_skill import _bundle_files
        repo_root = Path(__file__).resolve().parents[3]
        bundle = _bundle_files(repo_root)
        for _src, dst in bundle:
            p = str(dst)
            self.assertFalse(
                "harness" in p,
                f"117 must not leak bin/harness/ into the "
                f"bundle; saw {p}",
            )


if __name__ == "__main__":
    unittest.main()
