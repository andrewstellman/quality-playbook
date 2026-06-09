"""v1.5.9 instruction 210 — tick idempotency / heartbeat helper
correctness.

Stdlib-only — runs the `bin/qpb_heartbeat.py` shim as a subprocess
and inspects the resulting NDJSON. Covers the four cases from the
instruction § 1C.3 deliverable:

  1. Calling `emit` twice with identical args produces TWO distinct
     lines (each has a unique `ts`); not one, not a corruption, not
     a crash. Append-only-NDJSON invariant.
  2. Missing `--task-id` AND no QPB_TASK_ID env var → exit code 2.
  3. Invalid `--status` value (argparse choices rejects this →
     exit code 64 (the script's bad-invocation remap of argparse 2).
     Schema-validate-time invalid status is a different path — the
     script's argparse `choices=` blocks invalid status at parse
     time before the validator ever runs.
  4. A terminal heartbeat written after a progress heartbeat is the
     LAST line of the file (ordering invariant).

**Scope limit (documented per instruction).** The TICK idempotency
proper — "running the same harness tick twice → no observable change
after the first" — is a state-machine property that requires
spinning up a run-dir + state-machine state, which is Phase 1D
end-to-end validation territory. For Phase 1C, this test covers ONLY
the helper-script append discipline. Per the instruction § 1C.3 last
paragraph.

**Mode A no-op semantics.** The instruction's reconciliation: the
helper's `--mode-a-noop` flag opts into silent no-op when BOTH
inputs are unresolvable. Without that flag, the script exits 2 on
missing input. Both behaviors are tested.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

_QPB_ROOT = Path(__file__).resolve().parents[2]
_SHIM = _QPB_ROOT / "bin" / "qpb_heartbeat.py"


def _run_shim(args: "list[str]", *, env_overrides: "dict[str, str] | None" = None,
              cwd: "Path | None" = None) -> subprocess.CompletedProcess:
    """Run the bin/qpb_heartbeat.py shim as a subprocess.

    Sanitizes the environment so QPB_TASK_ID and QPB_HEARTBEAT_PATH
    are NOT set unless env_overrides supplies them — otherwise the
    operator's running shell could pollute the test.
    """
    env = {
        k: v for k, v in os.environ.items()
        if k not in ("QPB_TASK_ID", "QPB_HEARTBEAT_PATH")
    }
    if env_overrides:
        env.update(env_overrides)
    cmd = [sys.executable, str(_SHIM), *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd or _QPB_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )


class TestHeartbeatHelperIdempotency(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)
        self.heartbeat_path = self.tmp_dir / "heartbeat.ndjson"
        self.task_id = str(uuid.uuid4())

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_double_emit_produces_two_distinct_lines(self) -> None:
        """Case 1: calling emit twice with identical args → two
        distinct JSON lines (each has its own `ts`). Append-only
        invariant; no crash, no corruption, no single-line merge.
        """
        args = [
            "emit",
            "--phase", "Phase 1",
            "--step", "explore",
            "--status", "IN_PROGRESS",
            "--task-id", self.task_id,
            "--heartbeat-path", str(self.heartbeat_path),
        ]
        result1 = _run_shim(args)
        self.assertEqual(
            result1.returncode, 0,
            f"first emit failed: stderr={result1.stderr}",
        )
        result2 = _run_shim(args)
        self.assertEqual(
            result2.returncode, 0,
            f"second emit failed: stderr={result2.stderr}",
        )

        lines = self.heartbeat_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            len(lines), 2,
            f"expected 2 lines after 2 emits; got {len(lines)}: "
            f"{lines}",
        )

        parsed = [json.loads(line) for line in lines]
        for p in parsed:
            self.assertEqual(p["task_id"], self.task_id)
            self.assertEqual(p["schema_version"], "1")
            self.assertEqual(p["phase"], "Phase 1")
            self.assertEqual(p["step"], "explore")
            self.assertEqual(p["status"], "IN_PROGRESS")

    def test_missing_task_id_exits_2(self) -> None:
        """Case 2: missing --task-id AND no QPB_TASK_ID env var →
        exit code 2 with a clear error message. The Mode A no-op
        path is NOT triggered because the --mode-a-noop flag wasn't
        passed.
        """
        result = _run_shim([
            "emit",
            "--phase", "Phase 1",
            "--step", "explore",
            "--status", "STARTING",
            "--heartbeat-path", str(self.heartbeat_path),
        ])
        self.assertEqual(
            result.returncode, 2,
            f"expected exit 2; got {result.returncode}. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertIn("--task-id", result.stderr)

    def test_missing_heartbeat_path_exits_2(self) -> None:
        """Symmetric to case 2: missing --heartbeat-path AND no env
        var → exit 2.
        """
        result = _run_shim([
            "emit",
            "--phase", "Phase 1",
            "--step", "explore",
            "--status", "STARTING",
            "--task-id", self.task_id,
        ])
        self.assertEqual(result.returncode, 2)
        self.assertIn("--heartbeat-path", result.stderr)

    def test_mode_a_noop_silent_when_both_unresolvable(self) -> None:
        """Mode A no-op contract: --mode-a-noop + neither input
        resolvable → exit 0 silently. This is the Mode A
        interactive case where the worker calls qpb_heartbeat
        because the phase prompt says to, but no harness is
        orchestrating.
        """
        result = _run_shim([
            "emit",
            "--mode-a-noop",
            "--phase", "Phase 1",
            "--step", "explore",
            "--status", "STARTING",
        ])
        self.assertEqual(
            result.returncode, 0,
            f"Mode A no-op should exit 0; got {result.returncode}. "
            f"stderr={result.stderr!r}",
        )
        # No file should have been written.
        self.assertFalse(
            self.heartbeat_path.exists(),
            "Mode A no-op must not write anything",
        )

    def test_mode_a_noop_does_not_swallow_partial_input(self) -> None:
        """Mode A no-op is NOT a free pass: if --task-id is set but
        --heartbeat-path is not (or vice versa), the helper still
        exits 2. Catches "harness configured TASK_ID but forgot
        HEARTBEAT_PATH" mistakes.
        """
        # task_id set, heartbeat_path unset
        result = _run_shim([
            "emit",
            "--mode-a-noop",
            "--phase", "Phase 1",
            "--step", "explore",
            "--status", "STARTING",
            "--task-id", self.task_id,
        ])
        self.assertEqual(
            result.returncode, 2,
            f"partial input under --mode-a-noop should still exit "
            f"2; got {result.returncode}",
        )

    def test_invalid_status_exits_64(self) -> None:
        """Case 3: argparse choices= blocks an invalid --status at
        parse time. The script remaps argparse SystemExit(2) to 64
        (bad invocation). Schema-validate-time invalid status would
        be exit 3, but the parser never lets that path execute.
        """
        result = _run_shim([
            "emit",
            "--phase", "Phase 1",
            "--step", "explore",
            "--status", "BOGUS",
            "--task-id", self.task_id,
            "--heartbeat-path", str(self.heartbeat_path),
        ])
        self.assertEqual(
            result.returncode, 64,
            f"expected exit 64 (bad invocation); got "
            f"{result.returncode}. stderr={result.stderr!r}",
        )

    def test_terminal_appears_as_last_line(self) -> None:
        """Case 4: terminal heartbeat written after a progress
        heartbeat is the LAST line of the file (ordering
        invariant). Append-only guarantees ordering.
        """
        progress_args = [
            "emit",
            "--phase", "Phase 6",
            "--step", "verify",
            "--status", "IN_PROGRESS",
            "--task-id", self.task_id,
            "--heartbeat-path", str(self.heartbeat_path),
        ]
        terminal_args = [
            "terminal",
            "--status", "COMPLETED",
            "--result-file", "quality/SUMMARY.md",
            "--summary", "all phases complete",
            "--task-id", self.task_id,
            "--heartbeat-path", str(self.heartbeat_path),
        ]
        self.assertEqual(_run_shim(progress_args).returncode, 0)
        self.assertEqual(_run_shim(terminal_args).returncode, 0)

        lines = self.heartbeat_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        last = json.loads(lines[-1])
        self.assertEqual(last["status"], "COMPLETED")
        self.assertEqual(last["result_file"], "quality/SUMMARY.md")
        self.assertEqual(last["summary"], "all phases complete")
        self.assertNotIn(
            "phase", last,
            "terminal sentinel must NOT carry phase/step (oneOf "
            "branch 2 of the heartbeat schema)",
        )

    def test_env_var_resolution(self) -> None:
        """Env vars QPB_TASK_ID + QPB_HEARTBEAT_PATH resolve when
        no flags are passed.
        """
        env_path = self.tmp_dir / "env_heartbeat.ndjson"
        result = _run_shim(
            [
                "emit",
                "--phase", "Phase 2",
                "--step", "generate",
                "--status", "STARTING",
            ],
            env_overrides={
                "QPB_TASK_ID": self.task_id,
                "QPB_HEARTBEAT_PATH": str(env_path),
            },
        )
        self.assertEqual(
            result.returncode, 0,
            f"env-var resolution failed: stderr={result.stderr!r}",
        )
        self.assertTrue(env_path.exists())
        line = env_path.read_text(encoding="utf-8").strip()
        parsed = json.loads(line)
        self.assertEqual(parsed["task_id"], self.task_id)


if __name__ == "__main__":
    unittest.main()
