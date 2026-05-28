"""v1.5.7 125 — machine-global per-provider concurrency cap +
in-flight registry + Task-A.0 lifetime-slot fix.

The pre-125 harness had two related concurrency bugs that
together caused an Anthropic weekly-limit incident:

  Task A.0 — release-at-spawn (per-plan over-fan-out): the
    108 detached launcher releases the per-runner semaphore
    when ``_launch_one_run_detached`` RETURNS at Popen time.
    Since that's microseconds, ``pools={claude:2}`` capped
    the spawn *rate* (a no-op) not concurrent *execution*. A
    cross-runner plan with 4 claude runs launched all 4
    simultaneously.

  Task B — cross-plan blindness: per-plan pools never
    accounted across run-plan invocations, so two
    simultaneous ``run-plan`` calls could each launch up to
    their cap. Total concurrent provider calls blew past any
    single provider's rate limit.

125 fixes both via a machine-global file-locked registry:

  * **Lifetime slot**: the registry holds an entry from
    launch until terminal (the collector calls
    ``release_run_slot``). Task A.0's release-at-spawn is
    replaced by release-at-terminal.
  * **Global per-provider cap**: ``acquire_run_slot`` checks
    a configurable per-provider cap against ALL active
    entries on the machine — not just the current plan's.
    Per-plan ``pools`` still apply on top (whichever is
    tighter wins).
  * **Visibility**: ``qpb_harness status`` shows the
    operator-facing summary line ("in-flight: anthropic 2/2
    openai 1/3 …"). ``status --global`` lists every
    in-flight run from the registry.

Coverage (Task D):

  Registry (`inflight_registry`):
    * provider-by-runner map (claude→anthropic, etc.)
    * acquire reserves with pid=0; update_pid stamps the
      real pid; release removes the entry
    * dead-pid entries are reaped on the next read
    * concurrent writes are flock-safe (two processes can't
      both acquire when only one slot remains)
    * spec parsing merges defaults

  Caps:
    * **Task A.0 mutation-bite**: with plan_pool_cap=2 and 2
      slots already held under the same harness-run-dir +
      runner, a third acquire WAITS and timeouts via
      ``max_wait_s``. (Pre-125 release-at-spawn ⇒ acquire
      would succeed and the test FAILS.)
    * **Task B mutation-bite**: with the global anthropic
      cap at N and N anthropic entries already across
      DIFFERENT harness-run-dirs, a new anthropic acquire
      from yet another harness-run-dir WAITS. A different
      provider proceeds. (Pre-125 no global check ⇒ acquire
      fires and the test FAILS.)
    * Releasing a slot lets the queued acquire proceed.

  CLI / status:
    * ``--max-per-provider`` parses through to the registry
      defaults.
    * ``status`` always prints the global summary line.
    * ``status --global`` lists every active entry.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import argparse
import io
import os
import threading
import time
import unittest
import unittest.mock as mock
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from bin.harness import inflight_registry as IR


def _registry_in(tmp: Path) -> Path:
    """Per-test registry path so tests don't interfere with
    each other or the operator's real registry."""
    return tmp / "inflight.json"


# ---------------------------------------------------------------------------
# Registry — provider map + spec parsing
# ---------------------------------------------------------------------------


class ProviderMapTests(unittest.TestCase):

    def test_provider_for_known_runners(self) -> None:
        self.assertEqual(
            IR.provider_for_runner("claude"), "anthropic")
        self.assertEqual(
            IR.provider_for_runner("codex"), "openai")
        self.assertEqual(
            IR.provider_for_runner("copilot"), "github")
        self.assertEqual(
            IR.provider_for_runner("cursor"), "cursor")

    def test_provider_for_unknown_runner_passes_through(
            self) -> None:
        # Unknown runner name maps to itself so a custom
        # runner gets its own cap bucket.
        self.assertEqual(
            IR.provider_for_runner("xrunner"), "xrunner")


class SpecParseTests(unittest.TestCase):

    def test_parse_merges_with_defaults(self) -> None:
        spec = IR.parse_max_per_provider_spec(
            "anthropic=1,openai=5")
        self.assertEqual(spec["anthropic"], 1)
        self.assertEqual(spec["openai"], 5)
        # Defaults preserved for providers not mentioned.
        self.assertEqual(
            spec["github"],
            IR.DEFAULT_MAX_PER_PROVIDER["github"])

    def test_parse_empty_returns_defaults(self) -> None:
        self.assertEqual(
            IR.parse_max_per_provider_spec(None),
            dict(IR.DEFAULT_MAX_PER_PROVIDER))
        self.assertEqual(
            IR.parse_max_per_provider_spec(""),
            dict(IR.DEFAULT_MAX_PER_PROVIDER))

    def test_parse_skips_malformed_tokens(self) -> None:
        # Garbage tokens don't blow up the launch site.
        spec = IR.parse_max_per_provider_spec(
            "anthropic=1,garbage,openai=foo,github=2")
        self.assertEqual(spec["anthropic"], 1)
        self.assertEqual(spec["github"], 2)
        # openai=foo is skipped → keeps default.
        self.assertEqual(
            spec["openai"],
            IR.DEFAULT_MAX_PER_PROVIDER["openai"])


# ---------------------------------------------------------------------------
# Acquire / update / release — basic lifecycle
# ---------------------------------------------------------------------------


class AcquireUpdateReleaseTests(unittest.TestCase):

    def test_acquire_creates_entry_with_pid_zero(self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            reg = _registry_in(tmp)
            IR.acquire_run_slot(
                runner="claude",
                harness_run_dir=tmp / "h1",
                run_index=0,
                started_at="2026-05-27T00:00:00Z",
                max_per_provider={"anthropic": 2},
                registry_path=reg,
            )
            entries = IR.read_active_runs(registry_path=reg)
            self.assertEqual(len(entries), 1)
            e = entries[0]
            self.assertEqual(e["pid"], 0)
            self.assertEqual(e["runner"], "claude")
            self.assertEqual(e["provider"], "anthropic")

    def test_update_pid_replaces_placeholder(self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            reg = _registry_in(tmp)
            IR.acquire_run_slot(
                runner="claude",
                harness_run_dir=tmp / "h1",
                run_index=0,
                started_at="2026-05-27T00:00:00Z",
                max_per_provider={"anthropic": 2},
                registry_path=reg,
            )
            # Use this test's pid — guaranteed alive.
            IR.update_pid(
                harness_run_dir=tmp / "h1",
                run_index=0,
                pid=os.getpid(),
                registry_path=reg,
            )
            entries = IR.read_active_runs(registry_path=reg)
            self.assertEqual(entries[0]["pid"], os.getpid())

    def test_release_removes_entry(self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            reg = _registry_in(tmp)
            IR.acquire_run_slot(
                runner="claude",
                harness_run_dir=tmp / "h1",
                run_index=0,
                started_at="2026-05-27T00:00:00Z",
                max_per_provider={"anthropic": 2},
                registry_path=reg,
            )
            self.assertEqual(
                len(IR.read_active_runs(registry_path=reg)), 1)
            IR.release_run_slot(
                harness_run_dir=tmp / "h1",
                run_index=0,
                registry_path=reg,
            )
            self.assertEqual(
                len(IR.read_active_runs(registry_path=reg)), 0)

    def test_release_idempotent(self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            reg = _registry_in(tmp)
            # No prior acquire — release is a no-op.
            IR.release_run_slot(
                harness_run_dir=tmp / "h1",
                run_index=0,
                registry_path=reg,
            )
            self.assertEqual(
                IR.read_active_runs(registry_path=reg), [])


# ---------------------------------------------------------------------------
# Dead-pid reaping
# ---------------------------------------------------------------------------


class DeadPidReapTests(unittest.TestCase):
    """A run's pid is dead ⇒ its entry is inactive and gets
    pruned on the next ``read_active_runs``. Otherwise a
    crashed run would burn its slot until the registry file
    is hand-edited."""

    def test_dead_pid_entry_pruned_on_read(self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            reg = _registry_in(tmp)
            IR.acquire_run_slot(
                runner="claude",
                harness_run_dir=tmp / "h1",
                run_index=0,
                started_at="2026-05-27T00:00:00Z",
                max_per_provider={"anthropic": 2},
                registry_path=reg,
            )
            # Stamp a pid that is GUARANTEED dead (>>
            # max-pid). _pid_alive returns False for
            # ProcessLookupError.
            IR.update_pid(
                harness_run_dir=tmp / "h1",
                run_index=0,
                pid=999999999,
                registry_path=reg,
            )
            self.assertEqual(
                IR.read_active_runs(registry_path=reg), [])


# ---------------------------------------------------------------------------
# Task A.0 mutation-bite — per-plan pool cap is held for the
# run's lifetime (not released at spawn).
# ---------------------------------------------------------------------------


class PerPlanPoolLifetimeSlotTests(unittest.TestCase):
    """**Task A.0 mutation-bite**: with plan_pool_cap=2 + 2
    slots already held under one harness-run-dir + runner, a
    third acquire WAITS. Pre-125 (release-at-spawn) the
    third would acquire immediately and this test would
    FAIL. ``max_wait_s`` + ``TimeoutError`` proves the wait
    is real (not a slow no-op)."""

    def test_third_acquire_waits_when_plan_pool_full(
            self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            reg = _registry_in(tmp)
            # Hold 2 slots in the same plan + runner.
            for i in range(2):
                IR.acquire_run_slot(
                    runner="claude",
                    harness_run_dir=tmp / "h1",
                    run_index=i,
                    started_at="2026-05-27T00:00:00Z",
                    max_per_provider={"anthropic": 10},
                    plan_pool_cap=2,
                    registry_path=reg,
                )
                IR.update_pid(
                    harness_run_dir=tmp / "h1",
                    run_index=i, pid=os.getpid(),
                    registry_path=reg,
                )
            with self.assertRaises(TimeoutError):
                IR.acquire_run_slot(
                    runner="claude",
                    harness_run_dir=tmp / "h1",
                    run_index=2,
                    started_at="2026-05-27T00:00:00Z",
                    max_per_provider={"anthropic": 10},
                    plan_pool_cap=2,
                    registry_path=reg,
                    poll_interval_s=0.01,
                    max_wait_s=0.2,
                )

    def test_release_unblocks_queued_acquire(self) -> None:
        """After a release, the queued acquire fires
        promptly — proving the wait was real AND that
        release frees the slot for the next acquirer."""
        with TemporaryDirectory() as td:
            tmp = Path(td)
            reg = _registry_in(tmp)
            for i in range(2):
                IR.acquire_run_slot(
                    runner="claude",
                    harness_run_dir=tmp / "h1",
                    run_index=i,
                    started_at="2026-05-27T00:00:00Z",
                    max_per_provider={"anthropic": 10},
                    plan_pool_cap=2,
                    registry_path=reg,
                )
                IR.update_pid(
                    harness_run_dir=tmp / "h1",
                    run_index=i, pid=os.getpid(),
                    registry_path=reg,
                )
            done = threading.Event()
            err: "list[BaseException]" = []

            def _waiter() -> None:
                try:
                    IR.acquire_run_slot(
                        runner="claude",
                        harness_run_dir=tmp / "h1",
                        run_index=2,
                        started_at="2026-05-27T00:00:00Z",
                        max_per_provider={"anthropic": 10},
                        plan_pool_cap=2,
                        registry_path=reg,
                        poll_interval_s=0.02,
                    )
                    done.set()
                except BaseException as e:  # pragma: no cover
                    err.append(e)
                    done.set()

            t = threading.Thread(target=_waiter)
            t.start()
            # Give the waiter a couple polls to confirm
            # it's actually blocked.
            time.sleep(0.1)
            self.assertFalse(done.is_set(),
                              "waiter should still be blocked")
            IR.release_run_slot(
                harness_run_dir=tmp / "h1", run_index=0,
                registry_path=reg,
            )
            self.assertTrue(done.wait(timeout=2.0),
                             "waiter did not unblock after "
                             "release within 2s")
            t.join(timeout=1.0)
            self.assertFalse(err, f"waiter raised: {err}")
            # Final state: 2 active (index 1 + new index 2).
            self.assertEqual(
                len(IR.read_active_runs(registry_path=reg)),
                2)


# ---------------------------------------------------------------------------
# Task B mutation-bite — global per-provider cap across plans
# ---------------------------------------------------------------------------


class GlobalPerProviderCapTests(unittest.TestCase):
    """**Task B mutation-bite**: the global cap counts
    entries across ALL harness-run-dirs. With anthropic
    cap=2 and 2 anthropic entries already across DIFFERENT
    harness-run-dirs, a new anthropic acquire from yet
    another harness-run-dir WAITS. Pre-125 (no global check)
    it would acquire immediately and this test would
    FAIL."""

    def test_over_cap_acquire_waits_across_plans(self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            reg = _registry_in(tmp)
            # Two anthropic entries under DIFFERENT plans.
            for i, plan in enumerate(("h1", "h2")):
                IR.acquire_run_slot(
                    runner="claude",
                    harness_run_dir=tmp / plan,
                    run_index=0,
                    started_at="2026-05-27T00:00:00Z",
                    max_per_provider={"anthropic": 2},
                    registry_path=reg,
                )
                IR.update_pid(
                    harness_run_dir=tmp / plan,
                    run_index=0, pid=os.getpid(),
                    registry_path=reg,
                )
            # Third anthropic acquire from a third plan
            # MUST wait — global cap of 2 hit.
            with self.assertRaises(TimeoutError):
                IR.acquire_run_slot(
                    runner="claude",
                    harness_run_dir=tmp / "h3",
                    run_index=0,
                    started_at="2026-05-27T00:00:00Z",
                    max_per_provider={"anthropic": 2},
                    registry_path=reg,
                    poll_interval_s=0.01,
                    max_wait_s=0.2,
                )

    def test_different_provider_proceeds_under_its_cap(
            self) -> None:
        """The cap is PER-PROVIDER. Maxing out anthropic
        does NOT block an openai acquire under openai's
        cap."""
        with TemporaryDirectory() as td:
            tmp = Path(td)
            reg = _registry_in(tmp)
            for i in range(2):
                IR.acquire_run_slot(
                    runner="claude",
                    harness_run_dir=tmp / f"h{i}",
                    run_index=0,
                    started_at="2026-05-27T00:00:00Z",
                    max_per_provider={
                        "anthropic": 2, "openai": 3},
                    registry_path=reg,
                )
                IR.update_pid(
                    harness_run_dir=tmp / f"h{i}",
                    run_index=0, pid=os.getpid(),
                    registry_path=reg,
                )
            # openai (codex) acquire under openai's cap
            # of 3 — proceeds even though anthropic is
            # maxed.
            IR.acquire_run_slot(
                runner="codex",
                harness_run_dir=tmp / "h-oai",
                run_index=0,
                started_at="2026-05-27T00:00:00Z",
                max_per_provider={
                    "anthropic": 2, "openai": 3},
                registry_path=reg,
                poll_interval_s=0.01,
                max_wait_s=0.5,
            )
            counts = IR.counts_by_provider(registry_path=reg)
            self.assertEqual(counts.get("anthropic"), 2)
            self.assertEqual(counts.get("openai"), 1)


# ---------------------------------------------------------------------------
# Lock safety — two threads racing for one remaining slot
# ---------------------------------------------------------------------------


class LockSafetyTests(unittest.TestCase):
    """Two threads race for ONE remaining slot. flock + the
    read/write-under-lock contract MUST ensure exactly one
    wins (and the other blocks until a slot frees). Pre-flock
    or wrong-lock-order ⇒ both could see the slot as free
    and both write, leaving the file with 2 entries +
    blowing the cap."""

    def test_only_one_thread_acquires_under_contention(
            self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            reg = _registry_in(tmp)
            # Hold 1 anthropic slot; cap=2 ⇒ one slot left.
            IR.acquire_run_slot(
                runner="claude",
                harness_run_dir=tmp / "h0",
                run_index=0,
                started_at="2026-05-27T00:00:00Z",
                max_per_provider={"anthropic": 2},
                registry_path=reg,
            )
            IR.update_pid(
                harness_run_dir=tmp / "h0",
                run_index=0, pid=os.getpid(),
                registry_path=reg,
            )

            winners: "list[str]" = []
            losers: "list[str]" = []
            barrier = threading.Barrier(2)

            def _attempt(plan_name: str) -> None:
                # Sync both threads to maximize race window.
                barrier.wait()
                try:
                    IR.acquire_run_slot(
                        runner="claude",
                        harness_run_dir=tmp / plan_name,
                        run_index=0,
                        started_at="2026-05-27T00:00:00Z",
                        max_per_provider={"anthropic": 2},
                        registry_path=reg,
                        poll_interval_s=0.01,
                        max_wait_s=0.5,
                    )
                    winners.append(plan_name)
                except TimeoutError:
                    losers.append(plan_name)

            t1 = threading.Thread(
                target=_attempt, args=("h1",))
            t2 = threading.Thread(
                target=_attempt, args=("h2",))
            t1.start(); t2.start()
            t1.join(); t2.join()

            # Exactly one wins, exactly one loses.
            self.assertEqual(len(winners), 1,
                              f"winners={winners} "
                              f"losers={losers}")
            self.assertEqual(len(losers), 1,
                              f"winners={winners} "
                              f"losers={losers}")
            # And the registry has exactly 2 entries (the
            # original h0 + the winner).
            self.assertEqual(
                len(IR.read_active_runs(registry_path=reg)),
                2)


# ---------------------------------------------------------------------------
# Task C — global summary visibility
# ---------------------------------------------------------------------------


class GlobalSummaryTests(unittest.TestCase):

    def test_summary_renders_per_provider_counts_with_caps(
            self) -> None:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            reg = _registry_in(tmp)
            # 2 anthropic + 1 openai active.
            IR.acquire_run_slot(
                runner="claude",
                harness_run_dir=tmp / "h1",
                run_index=0,
                started_at="2026-05-27T00:00:00Z",
                max_per_provider={"anthropic": 2},
                registry_path=reg,
            )
            IR.update_pid(
                harness_run_dir=tmp / "h1",
                run_index=0, pid=os.getpid(),
                registry_path=reg,
            )
            IR.acquire_run_slot(
                runner="claude",
                harness_run_dir=tmp / "h2",
                run_index=0,
                started_at="2026-05-27T00:00:00Z",
                max_per_provider={"anthropic": 2},
                registry_path=reg,
            )
            IR.update_pid(
                harness_run_dir=tmp / "h2",
                run_index=0, pid=os.getpid(),
                registry_path=reg,
            )
            IR.acquire_run_slot(
                runner="codex",
                harness_run_dir=tmp / "h-oai",
                run_index=0,
                started_at="2026-05-27T00:00:00Z",
                max_per_provider={"openai": 3},
                registry_path=reg,
            )
            IR.update_pid(
                harness_run_dir=tmp / "h-oai",
                run_index=0, pid=os.getpid(),
                registry_path=reg,
            )

            line = IR.format_global_summary(
                registry_path=reg,
                max_per_provider={"anthropic": 2,
                                    "openai": 3,
                                    "github": 3},
            )
            self.assertIn("anthropic 2/2", line)
            self.assertIn("openai 1/3", line)
            self.assertIn("github 0/3", line)

    def test_summary_empty_registry(self) -> None:
        with TemporaryDirectory() as td:
            reg = _registry_in(Path(td))
            line = IR.format_global_summary(
                registry_path=reg,
                max_per_provider={"anthropic": 2},
            )
            # No counts → 0/cap for known providers.
            self.assertIn("anthropic 0/2", line)


# ---------------------------------------------------------------------------
# CLI — --max-per-provider parses through; status prints
# the global summary; --global lists entries.
# ---------------------------------------------------------------------------


class CLIIntegrationTests(unittest.TestCase):
    """Lightweight integration with ``bin.qpb_harness`` —
    confirm the flag is wired through to the registry +
    that status always prints the summary."""

    def test_status_prints_global_summary_line(self) -> None:
        from bin import qpb_harness as Q
        with TemporaryDirectory() as td:
            tmp = Path(td)
            reg = _registry_in(tmp)
            with mock.patch.dict(
                    os.environ,
                    {"QPB_HARNESS_REGISTRY": str(reg)}):
                # Empty registry — still prints the summary.
                ns = argparse.Namespace(
                    harness_run_dir=None,
                    runs_root=str(tmp / "harness-runs"),
                    global_view=False,
                )
                buf = io.StringIO()
                with redirect_stdout(buf):
                    Q._cmd_status(ns)
                self.assertIn("in-flight:", buf.getvalue())

    def test_status_global_lists_active_entries(self) -> None:
        from bin import qpb_harness as Q
        with TemporaryDirectory() as td:
            tmp = Path(td)
            reg = _registry_in(tmp)
            with mock.patch.dict(
                    os.environ,
                    {"QPB_HARNESS_REGISTRY": str(reg)}):
                IR.acquire_run_slot(
                    runner="claude",
                    harness_run_dir=tmp / "h1",
                    run_index=0,
                    started_at="2026-05-27T00:00:00Z",
                    max_per_provider={"anthropic": 2},
                    registry_path=reg,
                )
                IR.update_pid(
                    harness_run_dir=tmp / "h1",
                    run_index=0, pid=os.getpid(),
                    registry_path=reg,
                )
                ns = argparse.Namespace(
                    harness_run_dir=None,
                    runs_root=str(tmp / "harness-runs"),
                    global_view=True,
                )
                buf = io.StringIO()
                with redirect_stdout(buf):
                    Q._cmd_status(ns)
                out = buf.getvalue()
                self.assertIn("anthropic", out)
                self.assertIn("claude", out)
                self.assertIn(str(os.getpid()), out)


# ---------------------------------------------------------------------------
# Bundle safety — the registry module + 125 changes must not
# leak into the shipped install bundle (harness is dev-only).
# ---------------------------------------------------------------------------


class BundleSafety125Tests(unittest.TestCase):

    def test_inflight_registry_not_in_bundle(self) -> None:
        from bin.install_skill import _bundle_files
        repo_root = Path(__file__).resolve().parents[3]
        bundle = _bundle_files(repo_root)
        for src, dest in bundle:
            self.assertNotIn(
                "harness", str(dest),
                f"harness leak in bundle: {src} → {dest}")
            self.assertNotIn(
                "inflight_registry", str(dest),
                f"125 registry leak in bundle: "
                f"{src} → {dest}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
