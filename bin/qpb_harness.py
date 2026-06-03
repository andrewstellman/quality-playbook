"""qpb_harness — QPB Test Harness entry point (Phase 1 substrate).

v1.5.7 091 Phase 1: minimal entry that can drive ONE case end-to-
end through the harness substrate (``bin/harness/{schema, prepare,
runner, facts}``). The scheduler / manager daemon / Textual TUI
land in Phases 3–4; this file stays a single-run primitive for
now.

Self-describing on no-args per the 089x convention (matches
``qpb_validate.py``'s pattern). NEVER bundled into the install
closure (see ``bin/install_skill.py::_bundle_files()`` — allowlist
explicitly excludes ``bin/qpb_harness.py``).

Usage (Phase 1):
  python3 -m bin.qpb_harness                    # purpose banner + summary
  python3 -m bin.qpb_harness run \\
      --case-id ACC-001 \\
      --cases-file repos/security-test-cases/cases.json \\
      --runner claude --model opus \\
      --target-dir /tmp/harness-target \\
      --run-dir /tmp/harness-run/ACC-001/20260525T194300Z \\
      --max-duration-s 1200
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple


_HARNESS_NAME = "qpb_harness"
_HARNESS_SUMMARY = (
    "QPB Test Harness (v1.5.7 091 Phase 1 substrate)"
)
_HARNESS_ROLE = (
    "Run one acceptance or security_eval case end-to-end and "
    "produce normalized facts.json receipts. NOT bundled into the "
    "adopter install closure."
)
_HARNESS_USAGE_HINT = (
    "python3 -m bin.qpb_harness run --case-id <ID> "
    "--cases-file <cases.json> --runner claude --model <model> "
    "--target-dir <dir> --run-dir <dir>"
)


def _print_intro_minimal() -> None:
    """Self-describing no-args output. Tries the 089x-canonical
    helpers first; if unavailable (the harness module isn't
    bundled, so a degenerate environment is plausible), falls
    back to a plain print."""
    try:
        from bin._purpose import print_command_intro
        print_command_intro(
            name=_HARNESS_NAME,
            summary=_HARNESS_SUMMARY,
            role=_HARNESS_ROLE,
            usage_hint=_HARNESS_USAGE_HINT,
        )
    except ImportError:
        print(f"{_HARNESS_NAME} — {_HARNESS_SUMMARY}")
        print(_HARNESS_ROLE)
        print(f"Usage: {_HARNESS_USAGE_HINT}")


def _utc_now_run_id() -> str:
    """SCHEMA.md §2 run_id convention: UTC YYYYMMDDTHHMMSSZ."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _cmd_run(args: argparse.Namespace) -> int:
    """Run one case end-to-end through the Phase 1 substrate."""
    # Heavy imports deferred so the no-args banner path is cheap +
    # so a broken `bin.harness` doesn't break the banner.
    from bin.harness import facts as _facts
    from bin.harness import prepare as _prepare
    from bin.harness import runner as _runner
    from bin.harness import schema as _schema

    cases_path = Path(args.cases_file).expanduser().resolve()
    if not cases_path.is_file():
        print(f"ERROR: cases file not found: {cases_path}",
              file=sys.stderr)
        return 2
    cases = _schema.load_cases_file(cases_path)
    case = next((c for c in cases if c.id == args.case_id), None)
    if case is None:
        print(f"ERROR: case id {args.case_id!r} not found in "
              f"{cases_path}", file=sys.stderr)
        return 2

    target_dir = Path(args.target_dir).expanduser().resolve()
    run_dir = Path(args.run_dir).expanduser().resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    run_id = args.run_id or _utc_now_run_id()
    runner = _schema.Runner(args.runner)
    mode = _schema.Mode(args.mode)
    channel = _schema.InstallChannel(args.install_channel)
    axes = _schema.RunAxes(
        runner=runner,
        mode=mode,
        install_channel=channel,
        install_version=args.install_version,
        model=args.model,
        thinking=args.thinking,
    )

    # ----- PREPARE -----
    # v1.5.7 096 Phase 6: pass axes so prepare routes the install
    # step by channel + version (clone / pip-registry@<v> /
    # npm-registry@<v> / pip-local-wheel / npm-local-tgz). The
    # local_artifact arg is wired through to the qpb_harness CLI
    # as --install-artifact; pre-publish operators pass the freshly-
    # built wheel/tgz here.
    local_artifact = (
        Path(args.install_artifact).expanduser().resolve()
        if args.install_artifact else None
    )
    try:
        prep_result = _prepare.prepare(
            case, target_dir, ai_tool=args.runner,
            axes=axes, local_artifact=local_artifact,
        )
    except _prepare.PrepError as exc:
        # SCHEMA.md §6: prep failure → ABORTED_PREP terminal state.
        # Write a minimal invocation.json so the receipt is
        # auditable.
        inv = _schema.RunInvocation(
            run_id=run_id,
            case_id=case.id,
            axes=axes,
            qpb_version=_qpb_version(),
            target_sha="",
            cli_command="",
            cwd=str(target_dir),
            env_snapshot={},
            started_at=datetime.now(timezone.utc).isoformat(),
            ended_at=datetime.now(timezone.utc).isoformat(),
            exit_code=-1,
            terminal_state=_schema.TerminalState.ABORTED_PREP,
            scrubbed_docs_manifest=None,
            leakage_gate=("ABORTED" if exc.leakage_terms else None),
        )
        (run_dir / "invocation.json").write_text(
            json.dumps(_schema.run_invocation_to_json(inv), indent=2)
            + "\n", encoding="utf-8",
        )
        print(f"ABORTED_PREP: {exc.reason}", file=sys.stderr)
        return 3

    # ----- LAUNCH -----
    spec = _runner.LaunchSpec(
        target_dir=prep_result.target_dir,
        run_dir=run_dir,
        axes=axes,
        case_id=case.id,
        run_id=run_id,
        max_duration_s=float(args.max_duration_s),
        prompt=case.inputs.run_prompt or "Run the Quality Playbook on this project.",
    )
    launch = _runner.launch_run(spec)

    # ----- INVOCATION RECEIPT -----
    inv = _schema.RunInvocation(
        run_id=run_id,
        case_id=case.id,
        axes=axes,
        qpb_version=_qpb_version(),
        target_sha=prep_result.target_sha,
        cli_command=launch.cli_command,
        cwd=launch.cwd,
        env_snapshot=launch.env_snapshot,
        started_at=launch.started_at,
        ended_at=launch.ended_at,
        exit_code=launch.exit_code,
        terminal_state=launch.terminal_state,
        scrubbed_docs_manifest=prep_result.scrubbed_docs_manifest,
        leakage_gate=prep_result.leakage_gate,
    )
    (run_dir / "invocation.json").write_text(
        json.dumps(_schema.run_invocation_to_json(inv), indent=2)
        + "\n", encoding="utf-8",
    )

    # ----- FACTS (two-sourced) -----
    if launch.terminal_state == _schema.TerminalState.COMPLETED:
        try:
            transcript = launch.stream_path.read_text(
                encoding="utf-8", errors="ignore",
            )
            facts = _facts.extract_facts(
                target_dir=prep_result.target_dir,
                axes=axes,
                transcript=transcript,
                exit_code=launch.exit_code,
                raw_receipt=launch.stream_path.name,
            )
            (run_dir / "facts.json").write_text(
                json.dumps(_schema.run_facts_to_json(facts), indent=2)
                + "\n", encoding="utf-8",
            )
        except _facts.FactsError as exc:
            print(f"facts extraction failed: {exc}",
                  file=sys.stderr)
            # Don't fail the whole run — invocation.json is still
            # the load-bearing receipt; facts.json is a derived
            # artifact and a missing facts file just means the
            # grader treats every assertion as "fact unknown".
    print(f"Run complete: {run_dir}", file=sys.stderr)
    return 0 if launch.terminal_state == _schema.TerminalState.COMPLETED else 1


def _qpb_version() -> str:
    """Read QPB version from SKILL.md frontmatter (matches the
    installer's convention). Best-effort — falls back to
    ``"unknown"``."""
    try:
        skill_md = Path(__file__).resolve().parents[1] / "SKILL.md"
        for line in skill_md.read_text(encoding="utf-8").splitlines()[:20]:
            if line.startswith("version:"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "unknown"


_LAUNCH_BANNER_RULE = "=" * 64


def _format_pools_for_banner(pools: "dict[str, int]") -> str:
    """v1.5.7 158 Task A: render ``{"claude":3,"codex":2}`` as
    ``claude=3 codex=2`` for the banner's pool-summary line.
    Order: by insertion (which is the order the plan author wrote
    them); falls back gracefully on a non-mapping input."""
    if not isinstance(pools, dict):
        return ""
    return " ".join(f"{k}={v}" for k, v in pools.items())


def _relpath_for_banner(p: Path) -> str:
    """v1.5.7 158 Task A: render the harness-run dir as a path
    relative to the operator's likely cwd when possible — easier to
    scan and copy-paste than the absolute form. Falls back to the
    absolute path string if the relative computation fails (e.g.,
    the dir is outside cwd's tree)."""
    try:
        rel = p.relative_to(Path.cwd())
        return str(rel)
    except ValueError:
        return str(p)


def _render_launch_banner(
        harness_run_dir: Path,
        collector_pid: "int | None",
        run_count: int,
        pools: "dict[str, int]",
        *,
        per_run_entries: "list[dict] | None" = None,
        log_file_path: "Path | None" = None,
        foreground: bool = False,
        watchdog_pid: "int | None" = None,
        ) -> str:
    """v1.5.7 158 (revised): render the done-banner the orchestrator
    prints at the end of ``run-plan``. Plain ASCII, copy-pasteable.
    Goes to STDERR; STDOUT carries just the relative path for
    scripted use.

    v1.5.7 158-revised additions:
      * Per-run command lines (``per_run_entries``) — one line per
        planned run, with ``#N repo runner/model`` + a
        copy-pasteable per-run status command.
      * ``tail -f <log>`` line (auto-detach default) or a
        "running in foreground" note (``--foreground`` opt-out).
      * "Whole-suite commands:" / "Per-run commands:" section
        headers to make the banner navigable.

    v1.5.7 172: ``watchdog_pid`` adds a second daemon-pid token
    next to the collector pid so the operator sees both processes
    were spawned (and what to grep for if either dies).
    """
    rel = _relpath_for_banner(harness_run_dir)
    pool_str = _format_pools_for_banner(pools)
    collector_line = (
        f"  collector pid {collector_pid}"
        if collector_pid is not None else "  collector spawned"
    )
    # v1.5.7 172: watchdog appended to the same line for compactness.
    if watchdog_pid is not None:
        collector_line += f"  watchdog pid {watchdog_pid}"
    elif watchdog_pid is None and collector_pid is not None:
        collector_line += "  watchdog spawned"
    lines = [
        _LAUNCH_BANNER_RULE,
        f"  Launched: {run_count} runs"
        + (f"  pools: {pool_str}" if pool_str else ""),
        f"  {rel}",
        f"{collector_line}  this shell can close safely",
        "",
        "Whole-suite commands:",
        f"  python3 -m bin.qpb_harness tui {rel}",
        f"  python3 -m bin.qpb_harness status {rel}",
        f"  python3 -m bin.qpb_harness kill {rel}",
    ]
    # Per-run section (revised Task B).
    if per_run_entries:
        lines.append("")
        lines.append("Per-run commands:")
        for entry in per_run_entries:
            idx = entry.get("index", 0)
            repo = entry.get("repo", "?")
            repo_tail = repo.rstrip("/").split("/")[-1] or repo
            runner = entry.get("runner", "?")
            model = entry.get("model", "?")
            lines.append(
                f"  #{idx:<2} {repo_tail:18} {runner}/{model}  "
                f"  python3 -m bin.qpb_harness status "
                f"{rel}/run-{idx:02d}")
    # Log/foreground line (revised Task C).
    lines.append("")
    if foreground:
        lines.append(
            "Live orchestrator log:"
            "  (running in foreground; output is on this shell)")
    elif log_file_path is not None:
        lines.append("Live orchestrator log:")
        lines.append(f"  tail -f {log_file_path}")
    lines.append(_LAUNCH_BANNER_RULE)
    return "\n".join(lines)


def _at_least_one_running(manifest_path: Path) -> bool:
    """v1.5.7 180-followup-6 FINDING-10: a manifest with all-
    FAILED entries doesn't mean the launch succeeded — it just
    means the launch tried and recorded the failures. The post-
    launch check requires at least one entry with state=RUNNING
    (or PENDING — same intent: not yet terminal)."""
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    for entry in manifest.get("runs", []):
        if entry.get("state") in ("RUNNING", "PENDING"):
            return True
    return False


def _surface_all_failed_at_launch(manifest_path: Path) -> None:
    """v1.5.7 180-followup-6 FINDING-10: structured per-run
    terminal_reason table for the operator. Pre-fix the
    operator had to hunt through harness.log to find why no
    runs were actually running. The table goes to stderr."""
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"(could not read manifest {manifest_path}: "
              f"{exc})", file=sys.stderr)
        return
    runs = manifest.get("runs", [])
    if not runs:
        print("(manifest has no runs)", file=sys.stderr)
        return
    terminal_count = sum(
        1 for r in runs
        if r.get("state") not in ("RUNNING", "PENDING"))
    print(
        f"ERROR: launch failed — {terminal_count}/{len(runs)} "
        f"runs in manifest are terminal at deadline:",
        file=sys.stderr)
    for r in runs:
        idx = r.get("index", "?")
        target = r.get("target", r.get("run_dir", "?"))
        if isinstance(target, str) and "/" in target:
            target = target.rsplit("/", 1)[-1]
        runner_name = r.get("runner", "?")
        model = r.get("model", "?")
        state = r.get("state", "?")
        reason = r.get("terminal_reason", "(no reason)")
        if state in ("RUNNING", "PENDING"):
            # Highlight the survivor so the operator sees it.
            print(f"  #{idx} {target} ({runner_name}/{model}): "
                  f"{state}", file=sys.stderr)
        else:
            print(f"  #{idx} {target} ({runner_name}/{model}): "
                  f"{state} — {reason}", file=sys.stderr)


def _cmd_run_plan(args: argparse.Namespace) -> int:
    """v1.5.7 099 — simplified plan-runner entry. Reads a flat
    plan.json, creates a timestamped harness-run folder, runs
    each run gated per-runner by ``pools``, writes the
    SUMMARY.md table.

    v1.5.7 101: also builds the local artifacts the plan needs
    (pip wheel / npm tgz) into ``<harness-run>/artifacts/`` once
    per harness run before any launches. Optional ``--wheel`` /
    ``--tgz`` overrides skip the build and copy a pre-built
    artifact into the folder instead. A build failure aborts
    cleanly (no runs are launched against a failed build).
    """
    from bin.harness import plan_runner as _plan

    plan_path = Path(args.plan_file).expanduser().resolve()
    if not plan_path.is_file():
        print(f"ERROR: plan file not found: {plan_path}",
              file=sys.stderr)
        return 2
    # v1.5.7 149 (A0.1): default --runs-root None → ./harness_runs/,
    # created on demand (the QPB output convention).
    runs_root = Path(
        args.runs_root or "harness_runs").expanduser().resolve()
    runs_root.mkdir(parents=True, exist_ok=True)
    try:
        plan = _plan.load_plan(plan_path)
    except _plan.PlanError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # v1.5.7 158 (revised): auto-detach as default. The orchestrator
    # self-daemonizes so the operator's shell returns immediately;
    # stdout/stderr go to /tmp/qpb-harness-<TS>.log. Pass
    # ``--foreground`` to opt out (useful for debugging).
    #
    # Already in the detached child? (QPB_HARNESS_DETACHED set by
    # our own fork) — skip the fork to avoid infinite recursion.
    foreground = bool(getattr(args, "foreground", False))
    detached_child = bool(os.environ.get("QPB_HARNESS_DETACHED"))
    if (not foreground) and (not detached_child):
        from datetime import datetime as _dt, timezone as _tz
        from bin.harness import _platform as _platform_mod
        forced_run_id = _dt.now(_tz.utc).strftime(
            "%Y%m%dT%H%M%SZ")
        predicted_hrd = runs_root / forced_run_id
        # v1.5.7 180: use _platform.get_orchestrator_log_path
        # for cross-platform temp dir resolution (Windows can't
        # open ``/tmp/...``).
        log_path = _platform_mod.get_orchestrator_log_path(
            forced_run_id)
        per_run_entries = [
            {"index": pr.index, "repo": pr.repo,
             "runner": pr.runner.value, "model": pr.model}
            for pr in plan.runs
        ]
        # v1.5.7 180: cross-platform detach. POSIX path forks +
        # setsid + dup2 stdio + returns 0 in the child. Windows
        # path Popen-spawns a fresh ``qpb_harness run-plan ...``
        # invocation with QPB_HARNESS_DETACHED=1 in the env so
        # the spawn block is skipped on re-entry, then returns
        # the child pid (parent never sees 0).
        child_env = {
            "QPB_HARNESS_DETACHED": "1",
            "QPB_HARNESS_FORCED_RUN_ID": forced_run_id,
        }
        if _platform_mod.IS_WINDOWS:
            # v1.5.7 180 FIX (FINDING-2): re-invoke via the
            # Python interpreter, NOT raw sys.argv. sys.argv[0]
            # is the .py path which Windows ``CreateProcess``
            # rejects with WinError 193 (``%1 is not a valid
            # Win32 application``). The canonical re-invocation
            # form is the same shape the operator used:
            # ``python -m bin.qpb_harness <subcommand> ...``.
            # QPB_HARNESS_DETACHED in the spawned env short-
            # circuits the spawn block on re-entry.
            child_args = (
                [sys.executable, "-m", "bin.qpb_harness"]
                + sys.argv[1:]
            )
            spawn_env = {**os.environ, **child_env}
        else:
            # POSIX: same process continues; args ignored.
            child_args = []
            spawn_env = child_env
        pid = _platform_mod.spawn_detached(
            child_args, log_path=log_path, env=spawn_env)
        if pid != 0:
            # v1.5.7 180-followup-3 FINDING-4 + 180-followup-4
            # FINDING-6: spawn-then-verify. The parent must
            # confirm the child reached POST-LAUNCH state — not
            # just "child is alive at T+1.5s" — before printing
            # the success banner.
            #
            # The child's lifecycle:
            #   T+0       process spawns
            #   T+~0.5    creates predicted_hrd (mkdir -p)
            #   T+0.5..N  artifact build (npm pack, pip wheel)
            #             — can fail (FINDING-5 npm WinError 2)
            #   T+N       run_plan_detached writes manifest.json
            #   T+N+      collector/watchdog spawn; returns to
            #             caller
            #
            # ``manifest.json`` is the post-launch marker —
            # written only AFTER artifact build + all runs
            # transitioned to PENDING in the manifest. Pre-
            # FINDING-6 the verify just checked predicted_hrd
            # at T+1.5s; the run-dir exists by then even when
            # the child dies during artifact build. Banner was
            # a lie.
            #
            # Now: poll for manifest.json AND at least one
            # state=RUNNING entry, with a deadline.
            # v1.5.7 180-followup-6 FINDING-10: pre-fix the
            # check was "manifest exists" — but a manifest with
            # all-FAILED entries (Andrew's 5th Windows fire saw
            # 4/4 FAILED with SIGKILL AttributeError) PASSED the
            # check. Strengthened to also require an active
            # state=RUNNING entry; on deadline-exceeded with
            # all-terminal entries, surface the per-run
            # terminal_reason values to stderr.
            import time as _time
            _DEADLINE_S = float(
                os.environ.get(
                    "QPB_HARNESS_SPAWN_DEADLINE_S", "60"))
            _POLL_S = 0.5
            expected_manifest = (
                predicted_hrd / "manifest.json")
            deadline_at = _time.monotonic() + _DEADLINE_S
            reason: "Optional[str]" = None
            while _time.monotonic() < deadline_at:
                if not _platform_mod.pid_alive(pid):
                    reason = (
                        f"child (pid={pid}) died before "
                        f"writing manifest.json")
                    break
                if expected_manifest.is_file():
                    if _at_least_one_running(expected_manifest):
                        break  # honest banner allowed
                    # Manifest exists but no RUNNING — wait;
                    # runs may still be transitioning.
                _time.sleep(_POLL_S)
            else:
                # Deadline expired. Two failure modes:
                # (a) manifest exists with all-terminal entries
                #     → surface terminal_reason per run.
                # (b) manifest doesn't exist → child stalled
                #     somewhere before writing it.
                if expected_manifest.is_file():
                    reason = (
                        f"child (pid={pid}) wrote manifest.json "
                        f"but no run reached state=RUNNING "
                        f"within {_DEADLINE_S:.0f}s deadline. "
                        f"All runs are terminal at launch.")
                else:
                    reason = (
                        f"child (pid={pid}) did not write "
                        f"manifest.json within "
                        f"{_DEADLINE_S:.0f}s deadline")
            if reason is not None:
                print(
                    f"ERROR: spawned child failed startup: "
                    f"{reason}",
                    file=sys.stderr)
                # If the manifest is on disk, surface the per-
                # run terminal_reason table FIRST — the most
                # actionable signal for the operator.
                if expected_manifest.is_file():
                    _surface_all_failed_at_launch(
                        expected_manifest)
                print(
                    "Log contents:",
                    file=sys.stderr)
                try:
                    # v1.5.7 189 FINDING-44: errors="replace"
                    # + catch UnicodeDecodeError. Pre-189 a
                    # cp1252 byte (0x97 em-dash) from child
                    # startup output crashed the orchestrator
                    # itself and masked the real failure.
                    with open(log_path, "r",
                              encoding="utf-8",
                              errors="replace") as lf:
                        tail = lf.read()[-4000:]
                    print(tail, file=sys.stderr)
                except (OSError, UnicodeDecodeError) as exc:
                    print(f"(could not read log {log_path}: "
                          f"{exc})", file=sys.stderr)
                harness_log = predicted_hrd / "harness.log"
                if harness_log.is_file():
                    try:
                        # v1.5.7 189 FINDING-44: same fallback
                        # at the harness.log surface site.
                        with open(harness_log, "r",
                                  encoding="utf-8",
                                  errors="replace") as hlf:
                            print("--- harness.log tail ---",
                                  file=sys.stderr)
                            print(hlf.read()[-2000:],
                                  file=sys.stderr)
                    except (OSError, UnicodeDecodeError):
                        pass
                return 1
            # Child reached post-launch state. Banner is
            # honest.
            banner = _render_launch_banner(
                predicted_hrd, collector_pid=None,
                run_count=len(plan.runs), pools=plan.pools,
                per_run_entries=per_run_entries,
                log_file_path=log_path,
                foreground=False,
            )
            print(banner, file=sys.stderr)
            print(_relpath_for_banner(predicted_hrd))
            return 0
        # Child (POSIX): setsid + dup2 already done by
        # spawn_detached; env overrides applied. Continue
        # inline with the orchestrator's real work.

    wheel_override = (
        Path(args.wheel).expanduser().resolve()
        if getattr(args, "wheel", None) else None
    )
    tgz_override = (
        Path(args.tgz).expanduser().resolve()
        if getattr(args, "tgz", None) else None
    )
    # v1.5.7 174 Phase 5: removed --max-per-provider CLI spec
    # parsing (was 125 inflight_registry territory). Per-plan
    # pools are the only concurrency knob in the pool-only
    # model.
    try:
        outcomes = _plan.run_plan(
            plan, runs_root,
            wheel_override=wheel_override,
            tgz_override=tgz_override,
        )
    except _plan.BuildError as exc:
        print(f"ERROR: build failed — {exc}", file=sys.stderr)
        return 3
    # v1.5.7 108: in production (detached) mode, run_plan
    # returns RUNNING placeholders + spawns the collector. The
    # operator gets the harness-run dir + collector pid so
    # they can check status without a blocking parent.
    collector_pid = _plan._LAST_COLLECTOR_PID.pop("pid", None)
    # v1.5.7 172: watchdog pid surfaced alongside the collector.
    watchdog_pid = _plan._LAST_WATCHDOG_PID.pop("pid", None)
    if collector_pid is not None:
        # Find the harness-run dir from the first run's
        # receipts — runs_root contains exactly one new
        # timestamped dir per invocation.
        harness_run_dirs = sorted(
            (d for d in runs_root.iterdir() if d.is_dir()),
            key=lambda d: d.stat().st_mtime,
        )
        latest = (harness_run_dirs[-1]
                  if harness_run_dirs else runs_root)
        # v1.5.7 158 Task A + C: launch UX banner. The banner goes
        # to STDERR (human-readable scannable next-step output);
        # STDOUT carries ONLY the relative harness-run path so
        # scripted callers can do
        # ``HRD=$(qpb_harness <plan>)`` without parsing the banner.
        # Replaces the pre-158 two-line terse output ("harness-run
        # dir: ..." + "collector pid ...; check status with ...").
        print(_render_launch_banner(
            latest, collector_pid,
            run_count=len(outcomes), pools=plan.pools,
            watchdog_pid=watchdog_pid),
              file=sys.stderr)
        print(_relpath_for_banner(latest))  # stdout — script-parseable
        return 0
    # fake_run / synchronous path (existing 099-107 callers).
    met = sum(1 for o in outcomes if o.result == "MET")
    total = len(outcomes)
    print(f"Plan complete: {met}/{total} MET", file=sys.stderr)
    return 0 if met == total else 1


def _default_runs_root() -> Path:
    """v1.5.7 149: the QPB convention default — ``./harness_runs/``
    (underscore, plural), the single primary output location that
    tui/status/tail/run-plan all use when no explicit ``--runs-root``
    is given. run-plan creates it on demand; tui/status/tail read
    from it. (Pre-149 this tried ``./repos/`` → ``./harness-runs/``
    → cwd; that conflated benchmark SOURCES with run OUTPUT — 149
    splits them: outputs → harness_runs/, sources → repos/.)
    Operators with legacy content pass ``--runs-root`` explicitly."""
    return Path("harness_runs")


class _ResolvedTuiPath(NamedTuple):
    """v1.5.7 149 A0: a resolved read-path for status/tui/--dump plus
    ``from_default`` — True means the caller passed no path and
    ``_default_runs_root()`` supplied it. Callers use this to decide
    whether an absent dir is a hard error (explicit path → exit 2) or
    a soft "no runs yet" (default → exit 0)."""

    path: Path
    from_default: bool


# v1.5.7 160: timestamp path shortcuts. Operators currently type
# `harness_runs/<TS>` for every command; the shortcut lets them type
# just `<TS>` (the timestamp the 158 banner surfaced prominently) or
# `<TS>/run-NN`. Conservative: only triggers when (a) the path does
# NOT exist literally and (b) the pattern matches exactly. So a real
# directory named `20260530T134322Z` in cwd (unlikely) still wins.
_RE_TS_SHORTCUT = re.compile(
    r"^\d{8}T\d{6}Z(?:/run-\d+)?$")


def _looks_like_timestamp_shortcut(s: str) -> bool:
    """v1.5.7 160: True iff ``s`` matches ``<TS>`` or
    ``<TS>/run-NN`` (the two shortcut forms _resolve_tui_path
    expands by prepending the runs-root). The regex matches the
    same ``\\d{8}T\\d{6}Z`` timestamp shape as 152's
    ``_RE_HARNESS_RUN_NAME``."""
    return bool(_RE_TS_SHORTCUT.fullmatch(s))


def _resolve_tui_path(args: argparse.Namespace) -> _ResolvedTuiPath:
    """v1.5.7 135: resolve the single positional path for
    tui/status, falling back to the deprecated flags
    (``--runs-root`` for both; ``--dump-path`` for tui) then the
    default runs-root. Positional wins. v1.5.7 149 A0: returns
    ``(path, from_default)`` so callers can soften the absent-dir
    error when the default helper supplied the path.

    v1.5.7 160: timestamp path shortcut. When the raw positional
    matches the ``<TS>`` or ``<TS>/run-NN`` pattern AND the literal
    path doesn't exist AND the ``<runs-root>/<TS>...`` prepend
    exists, resolve to the prepended path. Halt #4: respects an
    explicitly-passed ``--runs-root`` (composes
    ``<--runs-root>/<TS>`` instead of always using
    ``harness_runs/``)."""
    raw = (
        getattr(args, "path", None)
        or getattr(args, "dump_path", None)
        or getattr(args, "runs_root", None)
        or getattr(args, "root", None)
    )
    if raw:
        literal = Path(raw).expanduser()
        # 160: timestamp shortcut. Only triggers when the literal
        # path doesn't exist AND the pattern matches. Honors an
        # explicit --runs-root (composes correctly per Halt #4).
        if (not literal.exists()
                and _looks_like_timestamp_shortcut(raw)):
            base = getattr(args, "runs_root", None)
            base_path = (Path(base).expanduser() if base
                         else _default_runs_root())
            shortcut = base_path / raw
            if shortcut.exists():
                return _ResolvedTuiPath(
                    shortcut.resolve(), False)
        return _ResolvedTuiPath(
            literal.resolve(), False)
    return _ResolvedTuiPath(_default_runs_root(), True)


def _cmd_status(args: argparse.Namespace) -> int:
    """v1.5.7 110 + 135: read-only status view over a single
    positional path, classified by directory shape:
      RUNS_ROOT   → table of in-flight + recent harness-runs.
      HARNESS_RUN → per-repo drill-down (index, repo,
                    runner/model, state, phase, result, pid).
      RUN_NN      → a single-run status block (135 — new).

    v1.5.7 125: the global per-provider in-flight summary prints
    at the top of every invocation; ``--global`` lists every
    in-flight run from the registry. ``--runs-root`` is a
    deprecated alias for the positional path.
    """
    from bin.harness import status as _status
    # v1.5.7 174 Phase 5: removed inflight_registry's global
    # in-flight summary and --global view (was 125 territory).
    # Concurrency is now per-plan; cross-plan view obsoleted.
    if getattr(args, "global_view", False):
        print("--global is obsoleted by v1.5.7 174 pool-only "
              "concurrency model; cross-plan registry removed",
              file=sys.stderr)
        return 0

    path, from_default = _resolve_tui_path(args)
    try:
        kind = _status.classify_tui_path(path)
    except FileNotFoundError:
        if from_default:
            # v1.5.7 149 A0: the default runs-root simply doesn't
            # exist yet (no runs written) — a soft empty state, not
            # an error. Matches the empty-RUNS_ROOT UX below.
            print(f"No harness-runs under {path}", file=sys.stderr)
            return 0
        print(f"ERROR: {path} is not a directory", file=sys.stderr)
        return 2
    except ValueError:
        # v1.5.7 153 Task B: a ``run-NN``-shaped dir with no spawn
        # markers is a PENDING/queued run (scheduler created the
        # dir before the worker spawned, then Ctrl-C). The
        # classifier correctly says "no markers" — the run-NN name
        # itself is the marker the CLI uses. Treat it as RUN_NN so
        # the single-run path renders the synthesized row.
        if _status._RE_RUN_NN.fullmatch(path.name):
            kind = _status.TuiPathKind.RUN_NN
        else:
            # v1.5.7 135: an existing-but-unclassifiable dir (no
            # manifest, no run markers, not a run-NN name) is
            # treated as an empty runs-root, preserving the
            # pre-135 graceful "No harness-runs under X" for a
            # fresh/empty runs-root rather than erroring.
            kind = _status.TuiPathKind.RUNS_ROOT

    if kind is _status.TuiPathKind.RUN_NN:
        # v1.5.7 135: single-run status block. 153 Task A:
        # synthesizes from on-disk artifacts when the manifest
        # doesn't list it; None only on a phantom dir.
        rs = _status.read_one_run_status_for_dir(path)
        if rs is None:
            print(
                f"ERROR: {path} is not a usable run dir",
                file=sys.stderr,
            )
            return 2
        print(f"run: {path.parent.name}/{path.name}")
        print("")
        print(_status.format_run_status(rs))
        if rs.last_note:
            print(f"     note: {rs.last_note}")
        return 0

    if kind is _status.TuiPathKind.HARNESS_RUN:
        runs = _status.read_run_status(path)
        if not runs:
            # v1.5.7 153 Task A: enumeration is manifest-INDEPENDENT,
            # so an empty list now means "no run-NN dirs at all" —
            # not just "no manifest." The old "(empty manifest)"
            # wording was misleading on Ctrl-C'd harness-runs.
            print(f"harness-run dir: {path} (no run dirs)",
                  file=sys.stderr)
            return 0
        print(f"harness-run dir: {path}")
        print("")
        # v1.5.7 160 Task B + C: state-grouped output (RUNNING /
        # PENDING / COMPLETED / FAILED) with counts + a dead-pid
        # warning inline on RUNNING rows whose pid is no longer
        # alive. format_run_status (the per-row verbose form) stays
        # in use for RUN_NN drill-downs (line 549 above).
        print(_status.format_runs_grouped(runs))
        return 0

    # RUNS_ROOT — list all harness-runs.
    summaries = _status.list_harness_runs(path)
    if not summaries:
        print(f"No harness-runs under {path}", file=sys.stderr)
        return 0
    print(f"runs-root: {path}")
    print(
        "harness-run                    "
        "started-at             "
        "runs  R  D  F  T AP  P  collector"
    )
    for s in summaries:
        print(_status.format_harness_run_summary(s))
    return 0


def _cmd_tail(args: argparse.Namespace) -> int:
    """v1.5.7 110 + 122: tail a run's ``stream.ndjson``
    (optionally ``-f`` to follow). By default each line goes
    through ``status.render_stream_line`` — Claude
    stream-json events become clean log lines, ``::QPB::``
    sentinels render human-readably, non-Claude plain text
    passes through. ``--raw`` emits verbatim lines for
    debugging the wire format.
    """
    from bin.harness import status as _status

    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        print(f"ERROR: {run_dir} is not a directory",
              file=sys.stderr)
        return 2

    # v1.5.7 135: classifier-aware error when given the wrong
    # kind of dir. tail needs a RUN_NN dir; a HARNESS_RUN /
    # RUNS_ROOT dir gets a message naming what to tail instead.
    try:
        kind = _status.classify_tui_path(run_dir)
    except (FileNotFoundError, ValueError):
        kind = None  # fall through to the stream.ndjson check
    if kind is _status.TuiPathKind.HARNESS_RUN:
        manifest = _status._safe_json(run_dir / "manifest.json") or {}
        runs = manifest.get("runs", [])
        parts = []
        for i, e in enumerate(runs):
            name = Path(e.get("run_dir", "")).name or f"run-{i:02d}"
            repo = e.get("repo", "?").rsplit("/", 1)[-1]
            parts.append(
                f"{name} ({repo} "
                f"{e.get('runner', '?')}/{e.get('model', '?')})")
        listing = ", ".join(parts) or "(none in manifest)"
        first = (Path(runs[0].get("run_dir", "")).name
                 if runs else "run-00")
        print(
            f"qpb_harness tail: '{run_dir}' is a harness-run dir, "
            f"not a run. Specify which run to tail; available: "
            f"{listing}. Example: qpb_harness tail "
            f"'{run_dir}'/{first} -f",
            file=sys.stderr,
        )
        return 2
    if kind is _status.TuiPathKind.RUNS_ROOT:
        print(
            f"qpb_harness tail: '{run_dir}' is a runs-root dir. "
            f"Specify a specific run to tail (path of the form "
            f"<runs-root>/<harness-run>/run-NN).",
            file=sys.stderr,
        )
        return 2

    stream_path = run_dir / "stream.ndjson"
    if not stream_path.is_file():
        print(
            f"NOTE: {stream_path} doesn't exist yet "
            f"(run hasn't launched, or stream wasn't "
            f"captured)",
            file=sys.stderr,
        )
        return 0
    rendered = not bool(getattr(args, "raw", False))
    try:
        for line in _status.tail_stream(
                run_dir,
                follow=bool(getattr(args, "follow", False)),
                rendered=rendered,
        ):
            print(line)
    except KeyboardInterrupt:
        return 0
    return 0


def _cmd_collect(args: argparse.Namespace) -> int:
    """v1.5.7 108: collect a harness-run. Reads
    ``<harness-run>/manifest.json`` + iterates every entry,
    polling AI-CLI PIDs + grading each as it terminates,
    rewriting SUMMARY.md incrementally. Idempotent — safe
    to re-run if the auto-spawned collector died.

    Used both as the auto-spawned collector (by
    ``_run_plan_detached``) and as an operator-facing manual
    re-entry (``qpb_harness collect <dir>``).
    """
    from bin.harness import plan_runner as _plan

    harness_run_dir = (
        Path(args.harness_run_dir).expanduser().resolve()
    )
    if not (harness_run_dir / "manifest.json").is_file():
        print(
            f"ERROR: no manifest.json under {harness_run_dir}",
            file=sys.stderr,
        )
        return 2
    try:
        outcomes = _plan.collect_harness_run(harness_run_dir)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    met = sum(1 for o in outcomes if o.result == "MET")
    total = len(outcomes)
    print(f"Collected {total} run(s): {met}/{total} MET",
          file=sys.stderr)
    return 0 if met == total else 1


def _cmd_watchdog(args: argparse.Namespace) -> int:
    """v1.5.7 172: watchdog daemon. Auto-spawned alongside the
    detached collector; can also be invoked manually for an
    abandoned harness-run (operator recovery)."""
    from bin.harness import watchdog as _wd

    harness_run_dir = (
        Path(args.harness_run_dir).expanduser().resolve()
    )
    if not (harness_run_dir / "manifest.json").is_file():
        print(
            f"ERROR: no manifest.json under {harness_run_dir}",
            file=sys.stderr,
        )
        return 2
    return _wd.run_watchdog(harness_run_dir)


def _cmd_manager(args: argparse.Namespace) -> int:
    """Start the manager daemon (Phase 4 substrate).

    Initialises the manager, recovers orphaned runs, consumes
    any queued commands ONCE, writes the snapshot, then exits.
    A full daemon loop with periodic ticking is the operator-
    deployment shape; for Phase 4 the single-tick entry is
    enough to demonstrate the queue + recovery + control-file
    contract end-to-end.
    """
    from bin.harness import manager as _manager
    from bin.harness import scheduler as _sched

    root = Path(args.root).expanduser().resolve()
    config = None
    if args.config:
        cfg_path = Path(args.config).expanduser().resolve()
        if cfg_path.is_file():
            try:
                raw = json.loads(cfg_path.read_text(encoding="utf-8"))
                config = _sched.config_from_dict(
                    raw.get("scheduler") or raw,
                )
            except (OSError, json.JSONDecodeError) as exc:
                print(f"ERROR: failed to read config: {exc}",
                      file=sys.stderr)
                return 2
    mgr = _manager.Manager(root=root, config=config)
    try:
        mgr.start()
    except _manager.ManagerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    print(f"manager started (pid={os.getpid()})", file=sys.stderr)
    try:
        mgr.consume_commands()
        mgr.write_queue_snapshot()
        snapshot = mgr.snapshot()
        print(json.dumps({
            "queue_length": snapshot["scheduler"]["queue_length"],
            "in_flight_total": snapshot["scheduler"]["in_flight_total"],
            "paused": snapshot["paused"],
            "recovered": [d for d in snapshot["recent_done"]
                          if "recovered_at" in d],
        }, indent=2))
    finally:
        mgr.shutdown()
    return 0


def _kill_label(rs) -> str:
    """v1.5.7 147: a one-line descriptor for a kill target —
    ``run-NN (repo runner/model, pid=N, elapsed=MMmSSs)``."""
    name = rs.run_dir.name
    repo = rs.repo.rstrip("/").rsplit("/", 1)[-1] or rs.repo
    el = rs.elapsed_s
    if isinstance(el, (int, float)) and el:
        elapsed = f"{int(el // 60)}m{int(el % 60):02d}s"
    else:
        elapsed = "—"
    return (f"{name} ({repo} {rs.runner}/{rs.model}, "
            f"pid={rs.pid}, elapsed={elapsed})")


def _cmd_kill(args: argparse.Namespace) -> int:
    """v1.5.7 147: operator-initiated kill of a run (RUN_NN) or all
    running runs in a harness-run (HARNESS_RUN). SIGKILL by default;
    ``--graceful`` sends a single SIGTERM (no escalation). Prompts
    unless ``-y``. RUNS_ROOT is rejected (too broad)."""
    import signal as _signal
    from bin.harness import status as _status
    from bin.harness import runner as _runner

    # v1.5.7 160: timestamp path shortcut for kill (same UX as
    # status/tui/tail via _resolve_tui_path). `<TS>` or
    # `<TS>/run-NN` expands to `<runs-root>/<TS>...` when the
    # literal path doesn't exist and the shortcut path does.
    raw_path = args.path
    literal = Path(raw_path).expanduser()
    if (not literal.exists()
            and _looks_like_timestamp_shortcut(raw_path)):
        shortcut = _default_runs_root() / raw_path
        if shortcut.exists():
            literal = shortcut
    path = literal.resolve()
    try:
        kind = _status.classify_tui_path(path)
    except FileNotFoundError:
        print(f"ERROR: {path} is not a directory", file=sys.stderr)
        return 2
    except ValueError as exc:
        # v1.5.7 153 Task B: a PENDING (queued, never-spawned) run-NN
        # dir genuinely has no markers — the classifier is right to
        # raise — but the run-NN name itself IS the marker for the
        # kill UX. Treat it as RUN_NN; the synthesized RunStatus
        # below will say state=PENDING and the kill is a no-op +
        # informational ("not running: PENDING").
        if _status._RE_RUN_NN.fullmatch(path.name):
            kind = _status.TuiPathKind.RUN_NN
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
    if kind is _status.TuiPathKind.RUNS_ROOT:
        print("ERROR: kill across an entire runs-root is too broad; "
              "pick a harness-run (<runs-root>/<harness-run>) or a "
              "specific run (.../run-NN).", file=sys.stderr)
        return 2

    # v1.5.7 180-followup-6 FINDING-9: signal.SIGKILL does not
    # exist on Windows. Lazy-resolve with AttributeError guard so
    # the --graceful path keeps using SIGTERM (which IS Windows-
    # available) and the default force-kill path passes None to
    # kill_run (which lazy-resolves inside _platform).
    if getattr(args, "graceful", False):
        sig = _signal.SIGTERM
        signame = "SIGTERM"
    else:
        try:
            sig = _signal.SIGKILL
            signame = "SIGKILL"
        except AttributeError:
            sig = None  # Windows: lazy-resolved to TerminateProcess
            signame = "TerminateProcess"

    targets: "list[tuple[Path, str]]" = []
    skipped: "list[tuple[str, str]]" = []
    # v1.5.7 188 FINDING-41: PENDING rows on a harness-run
    # kill must be cancelled in the manifest (terminal_state=
    # CANCELLED), not skipped — otherwise the collector's
    # post-186 PENDING-retry loop auto-launches them once a
    # slot frees, which is the OPPOSITE of "kill stops this
    # plan." Pending cancellation has no pid to SIGKILL; it's
    # a manifest-level state transition.
    pending_to_cancel: "list[tuple[int, str]]" = []
    if kind is _status.TuiPathKind.RUN_NN:
        # v1.5.7 153 Task A: synthesizes from on-disk artifacts
        # when manifest is missing/incomplete; None only on a
        # phantom dir.
        rs = _status.read_one_run_status_for_dir(path)
        if rs is None:
            print(f"ERROR: {path} is not a usable run dir",
                  file=sys.stderr)
            return 2
        if rs.state == "RUNNING":
            targets.append((path, _kill_label(rs)))
        elif rs.state == "PENDING":
            pending_to_cancel.append(
                (rs.index, _kill_label(rs)))
        else:
            skipped.append((_kill_label(rs),
                            f"not running: {rs.state}"))
    else:  # HARNESS_RUN — kill every RUNNING + cancel every PENDING.
        for rs in _status.read_run_status(path):
            if rs.state == "RUNNING":
                targets.append((rs.run_dir, _kill_label(rs)))
            elif rs.state == "PENDING":
                pending_to_cancel.append(
                    (rs.index, _kill_label(rs)))
            else:
                skipped.append((_kill_label(rs),
                                f"not running: {rs.state}"))

    if not targets and not pending_to_cancel:
        print(
            "No running runs to kill and no pending runs "
            "to cancel.")
        for label, reason in skipped:
            # v1.5.7 160 Task D: ✗ for skip (no-op).
            print(f"  ✗ {label} ({reason})")
        return 0

    if not getattr(args, "yes", False):
        if targets:
            print(f"About to KILL (sending {signame}):")
            for _rd, label in targets:
                print(f"  {label}")
        # v1.5.7 188 FINDING-41: surface pending cancellations
        # in the same confirmation prompt so the operator sees
        # exactly what "kill <harness-run>" will affect.
        if pending_to_cancel:
            print("About to CANCEL (pending, never launched):")
            for _idx, label in pending_to_cancel:
                print(f"  {label}")
        try:
            resp = input("Type 'y' to confirm: ")
        except EOFError:
            resp = ""
        if resp.strip() != "y":
            print("no runs killed or cancelled")
            return 0

    killed: "list[tuple[str, str]]" = []
    rc = 0
    graceful_hung = False
    for run_dir, label in targets:
        try:
            res = _runner.kill_run(run_dir, sig=sig)
        except _runner.KillError as exc:
            skipped.append((label, str(exc)))
            continue
        except Exception as exc:  # pragma: no cover - unexpected
            print(f"ERROR killing {label}: {exc}", file=sys.stderr)
            rc = 3
            continue
        if res.was_alive:
            note = (f"sent {signame} to pid {res.pid}; "
                    f"new terminal_state=KILLED")
            if res.still_alive_after_grace:
                note += " — process did not exit within 5s"
                graceful_hung = True
            killed.append((label, note))
        else:
            killed.append((label, "pid already dead; recorded KILLED"))

    # v1.5.7 188 FINDING-41: cancel each PENDING entry. The
    # harness-run dir lives at the parent of any RUN_NN path or
    # IS the path for HARNESS_RUN — for HARNESS_RUN kind we use
    # ``path`` directly; for RUN_NN the only pending case is
    # the path itself (a single PENDING row), and its parent is
    # the harness-run dir.
    cancelled: "list[tuple[str, str]]" = []
    cancel_errored: "list[tuple[str, str]]" = []
    if pending_to_cancel:
        from bin.harness import plan_runner as _pr
        if kind is _status.TuiPathKind.HARNESS_RUN:
            harness_run_dir = path
        else:
            harness_run_dir = path.parent
        for run_index, label in pending_to_cancel:
            try:
                _pr.cancel_pending_run(
                    harness_run_dir, run_index)
                cancelled.append(
                    (label,
                     "cancelled by operator before launch"))
            except _pr.CancelPendingError as exc:
                cancel_errored.append((label, str(exc)))
            except Exception as exc:  # pragma: no cover
                cancel_errored.append((label, repr(exc)))
                rc = 3

    # v1.5.7 160 Task D + 188: ✓/✗ symbols for visible kill /
    # cancel outcomes. Unicode (modern terminals); ASCII
    # fallback could be added behind a flag in a follow-up.
    if killed:
        print("Killed:")
        for label, note in killed:
            print(f"  ✓ {label}: {note}")
    if cancelled:
        print("Cancelled:")
        for label, note in cancelled:
            print(f"  ✓ {label}: {note}")
    if cancel_errored:
        print("Cancel errors:")
        for label, reason in cancel_errored:
            print(f"  ✗ {label}: {reason}")
    if skipped:
        print("Skipped:")
        for label, reason in skipped:
            print(f"  ✗ {label} ({reason})")
    if graceful_hung:
        print("  If you want to force-kill, re-run without "
              "--graceful (sends SIGKILL).")
    return rc


def _cmd_force_run(args: argparse.Namespace) -> int:
    """v1.5.7 186 FINDING-33: force-launch one or many
    PENDING runs OUT OF POOL.

    Single-row form: ``path`` is a ``run-NN`` directory under
    a harness-run. Launches that single row, bypassing the
    pool acquire. No confirmation prompt by default (the
    operator typed ``force-run`` explicitly); ``--confirm``
    adds the prompt.

    Whole-dir form: ``path`` is a harness-run directory.
    Prints the count of PENDING rows + live runner counts,
    prompts ``y/N`` once, then launches all PENDING rows in
    parallel.
    """
    from bin.harness import plan_runner as _pr
    from bin.harness import status as _status_mod
    raw_path = Path(args.path).expanduser().resolve()
    if not raw_path.exists():
        print(f"ERROR: path {raw_path} not found",
              file=sys.stderr)
        return 2
    # Classify path: single run-NN OR whole harness-run dir.
    if raw_path.is_dir() and raw_path.name.startswith("run-"):
        # Single-row form. The harness-run dir is the parent.
        harness_run_dir = raw_path.parent
        try:
            run_index = int(raw_path.name.split("-")[1])
        except (IndexError, ValueError):
            print(
                f"ERROR: cannot parse run-index from "
                f"{raw_path.name!r}",
                file=sys.stderr)
            return 2
        if getattr(args, "confirm", False):
            try:
                resp = input(
                    f"Force-run {raw_path.name} out of pool? "
                    f"[y/N]: ").strip().lower()
            except EOFError:
                resp = ""
            if resp != "y":
                print("aborted")
                return 0
        try:
            result = _pr.force_launch_pending_run(
                harness_run_dir, run_index)
        except _pr.ForceRunError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(
            f"Force-launched run-{run_index:02d} "
            f"({result['runner']}/{result['model']}); "
            f"pid={result['pid']}; live {result['runner']} "
            f"count now {result['live_count_after']}")
        return 0
    # Whole-dir form.
    harness_run_dir = raw_path
    manifest_path = harness_run_dir / "manifest.json"
    if not manifest_path.is_file():
        print(
            f"ERROR: {harness_run_dir} has no manifest.json — "
            f"not a harness-run directory",
            file=sys.stderr)
        return 2
    try:
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ERROR: cannot read manifest: {exc!r}",
              file=sys.stderr)
        return 2
    pending = [
        e for e in manifest.get("runs", [])
        if e.get("state") == "PENDING"
    ]
    if not pending:
        print(
            f"No PENDING rows in "
            f"{harness_run_dir.name}; nothing to force-run.")
        return 0
    # Per-runner live count snapshot.
    live_per_runner: "dict[str, int]" = {}
    for e in manifest.get("runs", []):
        if e.get("state") in ("RUNNING", "ACQUIRING"):
            r = e.get("runner")
            if isinstance(r, str):
                live_per_runner[r] = (
                    live_per_runner.get(r, 0) + 1)
    print(
        f"Force-run all {len(pending)} PENDING rows in "
        f"{harness_run_dir.name}?")
    print(
        f"  Live per runner: "
        f"{dict(sorted(live_per_runner.items())) or '(none)'}")
    try:
        resp = input("Confirm [y/N]: ").strip().lower()
    except EOFError:
        resp = ""
    if resp != "y":
        print("aborted")
        return 0
    results = _pr.force_launch_all_pending_in_dir(
        harness_run_dir)
    succeeded = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]
    print(
        f"Launched {len(succeeded)}/{len(results)} PENDING "
        f"rows; failed {len(failed)}.")
    for r in succeeded:
        print(
            f"  OK run-{r['index']:02d} "
            f"({r['runner']}/{r['model']}); pid={r['pid']}")
    for r in failed:
        print(
            f"  FAIL run-{r['index']:02d}: {r['error']}")
    return 0 if not failed else 1


def _cmd_tui_dump(path: Path, kind, *,
                    max_lines: int = 2000,
                    rendered: bool = True) -> int:
    """v1.5.7 121 + 135: render a TUI page to stdout
    non-interactively. Works WITHOUT textual installed —
    delegates to the pure text formatters in ``bin.harness.tui``
    (which read via status.py and don't touch textual).

    v1.5.7 135: the page is chosen by the classified ``kind`` of
    the single positional ``path`` (RUNS_ROOT→runs list,
    HARNESS_RUN→detail, RUN_NN→output), not a separate
    --dump-mode + --dump-path. ``max_lines``/``rendered`` apply
    only to the RUN_NN output page."""
    from bin.harness import tui as _tui
    from bin.harness import status as _status
    if kind is _status.TuiPathKind.RUNS_ROOT:
        text = _tui.format_runs_list_as_text(path)
    elif kind is _status.TuiPathKind.HARNESS_RUN:
        text = _tui.format_detail_as_text(path)
    else:  # RUN_NN
        text = _tui.format_output_as_text(
            path, max_lines=max_lines, rendered=rendered)
    print(text)
    return 0


def _cmd_tui(args: argparse.Namespace) -> int:
    """v1.5.7 119: launch the live status TUI over 110/117's
    ``bin/harness/status.py`` model layer. Default is the
    Textual app (scrollable/mouse-aware output with follow-
    tail + auto-refresh on a ~2s timer); ``--curses`` forces
    the dependency-free 111/116/117-era stdlib-curses
    implementation.

    Three navigation levels: harness-runs list → run detail →
    live output. Read-only. The Textual app exits cleanly on
    Ctrl+C / q; the curses wrapper restores the terminal on
    exit AND on any uncaught exception.

    When ``textual`` isn't importable and ``--curses`` wasn't
    requested, prints an actionable install message and falls
    back to the curses path so the operator never gets a
    hard failure.

    Pre-111, this subcommand opened the 094 manager TUI over
    ``<root>/control/queue.json``. The 094 manager path was
    superseded by 108's detach + auto-collector model;
    ``--root`` is retained as a deprecated alias that maps to
    ``--runs-root`` for compatibility with operator muscle
    memory.
    """
    from bin.harness import tui as _tui
    from bin.harness import status as _status

    # v1.5.7 135: one positional path, classified by directory
    # shape. Replaces the --runs-root / --dump-mode / --dump-path
    # triple (still accepted as deprecated aliases via
    # _resolve_tui_path).
    path, from_default = _resolve_tui_path(args)
    try:
        kind = _status.classify_tui_path(path)
    except FileNotFoundError:
        if from_default:
            # v1.5.7 149 A0: default runs-root absent ⇒ no runs yet
            # (soft empty state, exit 0), not a hard error.
            sys.stderr.write(f"No harness-runs under {path}\n")
            return 0
        sys.stderr.write(f"qpb_harness tui: {path} is not a "
                         f"directory\n")
        return 2
    except ValueError:
        # v1.5.7 135: existing-but-unclassifiable dir → empty
        # runs-root (graceful), matching _cmd_status. Only a
        # non-existent path errors (FileNotFoundError above).
        kind = _status.TuiPathKind.RUNS_ROOT

    # --dump is now a boolean toggle (135). The old enum forms
    # (runs|detail|output) are still accepted but the path's
    # shape is authoritative — warn if a passed enum disagrees.
    dump = getattr(args, "dump", None)
    if dump is not None:
        _expected = {
            _status.TuiPathKind.RUNS_ROOT: "runs",
            _status.TuiPathKind.HARNESS_RUN: "detail",
            _status.TuiPathKind.RUN_NN: "output",
        }[kind]
        if isinstance(dump, str) and dump != _expected:
            sys.stderr.write(
                f"qpb_harness tui: --dump {dump} disagrees with "
                f"the path's shape ({kind.value} ⇒ {_expected}); "
                f"using {_expected}.\n")
        return _cmd_tui_dump(
            path, kind,
            max_lines=int(getattr(args, "lines", 2000)),
            rendered=not bool(getattr(args, "raw", False)),
        )

    # Interactive: derive the runs-root the TUI navigates from the
    # classified path, plus (v1.5.7 139, closes 135 FLAG 3) the
    # initial-focus so the TUI opens at the page the path indicates
    # — RUN_NN → output page, HARNESS_RUN → detail page, RUNS_ROOT
    # → runs-list (top). The existing q/esc back-nav walks UP from
    # the deep-entry page to its parent(s). (135's interim stderr
    # "navigate into …" hint is gone — deep-entry makes it moot.)
    initial_focus: "Optional[tuple]" = None
    if kind is _status.TuiPathKind.RUNS_ROOT:
        runs_root = path
    elif kind is _status.TuiPathKind.HARNESS_RUN:
        runs_root = path.parent
        initial_focus = (kind, path)
    else:  # RUN_NN
        runs_root = path.parent.parent
        initial_focus = (kind, path)

    # v1.5.7 119: Textual by default; curses on --curses or
    # textual ImportError.
    force_curses = bool(getattr(args, "curses", False))
    if force_curses:
        return _tui.launch_status_tui(
            runs_root, initial_focus=initial_focus)
    try:
        import textual  # noqa: F401 — availability probe only
    except ImportError:
        sys.stderr.write(
            "qpb_harness tui: 'textual' not installed; falling "
            "back to the stdlib-curses TUI.\n"
            "To get the richer Textual UI (scroll/mouse/follow"
            "-tail + auto-refresh), run:\n"
            "  pip install textual\n"
            "or install the harness extra:\n"
            "  pip install 'quality-playbook[harness]'\n"
        )
        return _tui.launch_status_tui(
            runs_root, initial_focus=initial_focus)
    return _tui.launch_textual_tui(
        runs_root, initial_focus=initial_focus)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=_HARNESS_NAME,
        description=_HARNESS_SUMMARY + " — " + _HARNESS_ROLE,
    )
    sub = p.add_subparsers(dest="command")

    p_run = sub.add_parser(
        "run", help="Run one case end-to-end (Phase 1 substrate).",
    )
    p_run.add_argument("--case-id", required=True)
    p_run.add_argument("--cases-file", required=True)
    p_run.add_argument("--target-dir", required=True,
                        help="Where to clone the worktree. Must not exist.")
    p_run.add_argument("--run-dir", required=True,
                        help="Where to write receipts (invocation/status/"
                             "stream/facts).")
    p_run.add_argument("--run-id", default=None,
                        help="Override run_id (default: UTC now).")
    p_run.add_argument("--runner", default="claude",
                        choices=("claude", "copilot", "codex", "cursor"),
                        help="Phase 1 supports 'claude' only.")
    p_run.add_argument("--mode", default="A", choices=("A", "B"))
    p_run.add_argument("--install-channel", default="clone",
                        choices=("clone", "pip-local-wheel",
                                  "npm-local-tgz", "pip-registry",
                                  "npm-registry"),
                        help="Phase 1 supports 'clone' only.")
    p_run.add_argument("--install-version", default=None)
    p_run.add_argument("--model", required=True)
    p_run.add_argument("--thinking", default=None,
                        choices=(None, "low", "medium", "high", "xhigh"))
    p_run.add_argument("--max-duration-s", default=1800.0,
                        type=float,
                        help="Kill the run after this many seconds (default 1800).")
    p_run.add_argument("--install-artifact", default=None,
                        help="v1.5.7 096: path to the local artifact "
                             "(wheel for pip-local-wheel, tgz for "
                             "npm-local-tgz). Required for those "
                             "channels; ignored otherwise.")

    # v1.5.7 099 simplified plan-runner.
    p_plan = sub.add_parser(
        "run-plan",
        help=("Run a simplified harness plan (v1.5.7 099): one "
              "flat plan.json → one timestamped output folder → "
              "one SUMMARY.md table."),
    )
    p_plan.add_argument("plan_file",
                          help="Path to the plan.json document.")
    p_plan.add_argument("--runs-root", default=None,
                          help="Root directory for harness-run "
                               "output folders (gitignored by "
                               "convention). Default: "
                               "./harness_runs/ (created if "
                               "missing).")
    p_plan.add_argument("--wheel", default=None,
                          help=("v1.5.7 101: pre-built pip wheel "
                                "path to use for pip-local-wheel "
                                "runs (still copied into "
                                "<harness-run>/artifacts/). When "
                                "absent: build a fresh wheel."))
    p_plan.add_argument("--tgz", default=None,
                          help=("v1.5.7 101: pre-built npm tgz "
                                "path to use for npm-local-tgz "
                                "runs (still copied into "
                                "<harness-run>/artifacts/). When "
                                "absent: build a fresh tgz."))
    # v1.5.7 174 Phase 5: removed --max-per-provider. The
    # pool-only model uses per-plan ``pools`` exclusively;
    # cross-plan concurrency is deliberately not tracked.
    p_plan.add_argument(
        "--foreground", action="store_true", default=False,
        help=(
            "v1.5.7 158 (revised): keep the orchestrator in the "
            "foreground (skip the default auto-detach fork). "
            "Default behavior is auto-detach: the orchestrator "
            "self-daemonizes, the operator's shell returns "
            "immediately, and stdout/stderr are redirected to "
            "<tempdir>/qpb-harness-<TS>.log (POSIX: /tmp; "
            "Windows: %%TEMP%%). Pass --foreground for "
            "debugging "
            "when you want the orchestrator's progress log "
            "inline."),
    )

    # v1.5.7 108: collect — invoked by the auto-spawned
    # detached collector AND as the operator's manual
    # re-entry. Idempotent.
    p_collect = sub.add_parser(
        "collect",
        help=("v1.5.7 108: collect a detached harness-run "
              "(reap PIDs + grade + update SUMMARY). Safe to "
              "re-run if the auto-spawned collector died."),
    )
    p_collect.add_argument(
        "harness_run_dir",
        help="Path to the harness-run directory.",
    )

    # v1.5.7 172: watchdog daemon — auto-spawned alongside the
    # collector; safety net for collector-side bugs in the
    # schedule-then-collect contract (e.g. BUG-008/009 family).
    p_watchdog = sub.add_parser(
        "watchdog",
        help=("v1.5.7 172: poll for orphan runs (manifest says "
              "RUNNING, pid dead, stream stale) and fire collect "
              "under a file lock to self-heal."),
    )
    p_watchdog.add_argument(
        "harness_run_dir",
        help="Path to the harness-run directory.",
    )

    # v1.5.7 110: status (no-arg + per-harness-run) + tail.
    p_status = sub.add_parser(
        "status",
        help=("v1.5.7 110: list in-flight + recent harness-"
              "runs OR drill into one harness-run's per-repo "
              "state, current phase, result, pid-liveness."),
    )
    p_status.add_argument(
        "path", nargs="?", default=None,
        help=("v1.5.7 135: a runs-root, a harness-run dir, OR a "
              "run-NN dir — the view is inferred from the path's "
              "shape (run-NN shows a single-run block). Omit to "
              "default to ./repos/ (else ./harness-runs/)."),
    )
    p_status.add_argument(
        "--runs-root", default=None,
        help=("DEPRECATED (v1.5.7 135): pass the path positionally "
              "instead. Still accepted — treated as the positional "
              "path when none is given."),
    )
    p_status.add_argument(
        "--global", dest="global_view", action="store_true",
        help=(
            "v1.5.7 125: list EVERY in-flight run from the "
            "global registry (across all harness-runs on this "
            "machine). The global per-provider summary line "
            "is always printed; this flag adds the full "
            "registry listing."),
    )

    p_tail = sub.add_parser(
        "tail",
        help=("v1.5.7 110: print a run's live stream.ndjson "
              "with sentinel lines rendered human-readably. "
              "``--follow`` keeps polling for new content "
              "(tail -f semantics)."),
    )
    p_tail.add_argument(
        "run_dir",
        help=("Path to the run-NN directory inside a harness-run "
              "(contains stream.ndjson). v1.5.7 135: if given a "
              "harness-run or runs-root dir instead, a "
              "classifier-aware error lists the available runs."),
    )
    p_tail.add_argument(
        "-f", "--follow", action="store_true",
        help="Poll for new content (tail -f).",
    )
    p_tail.add_argument(
        "--raw", action="store_true",
        help=("v1.5.7 122: emit verbatim stream lines (no "
              "Claude stream-json templating, no ::QPB:: "
              "sentinel translation). For debugging the "
              "wire format. Default is rendered."),
    )

    p_kill = sub.add_parser(
        "kill",
        help=("v1.5.7 147: kill a run (run-NN) or all running runs "
              "in a harness-run. SIGKILL by default; --graceful "
              "sends a single SIGTERM. Prompts unless -y."),
    )
    p_kill.add_argument(
        "path",
        help=("run-NN dir → kill that run; harness-run dir → kill "
              "all RUNNING runs; runs-root → error (too broad)."),
    )
    p_kill.add_argument(
        "-y", "--yes", action="store_true",
        help="Skip the confirmation prompt.",
    )
    p_kill.add_argument(
        "--graceful", action="store_true",
        help=("Send a single SIGTERM instead of SIGKILL (no "
              "escalation; re-run without --graceful to "
              "force-kill)."),
    )

    # v1.5.7 186 FINDING-33: force-run subcommand.
    p_force_run = sub.add_parser(
        "force-run",
        help=("v1.5.7 186: launch a PENDING run OUT OF POOL "
              "(bypasses _try_acquire_pool_slot). Single-row "
              "form: pass a run-NN dir. Whole-dir form: pass "
              "a harness-run dir; all PENDING rows under it "
              "launch in parallel after a single confirmation "
              "prompt."),
    )
    p_force_run.add_argument(
        "path",
        help=("run-NN dir → force-launch that single PENDING "
              "row, no prompt. harness-run dir → force-launch "
              "all PENDING rows after a single y/N prompt."),
    )
    p_force_run.add_argument(
        "--confirm", action="store_true",
        help=("Single-row form: add a confirmation prompt "
              "(default is no prompt — the operator typed "
              "force-run explicitly). Ignored for the whole-"
              "dir form which always prompts."),
    )

    # Phase 4 subcommands.
    p_mgr = sub.add_parser(
        "manager",
        help="Start the manager daemon (Phase 4).",
    )
    p_mgr.add_argument("--root", required=True,
                        help="Harness runner root (e.g. "
                             "repos/security-test-cases).")
    p_mgr.add_argument("--config", default=None,
                        help="Optional scheduler config JSON.")

    p_tui = sub.add_parser(
        "tui",
        help=("v1.5.7 119: open the live status TUI (Textual "
              "by default — scroll/mouse/follow-tail + auto-"
              "refresh) over the 110 status.py model layer. "
              "Three nav levels: harness-runs → run detail → "
              "live output. Use --curses for the 111-era "
              "stdlib-curses fallback (no extra dependency)."),
    )
    # v1.5.7 135: single positional path, classified by directory
    # shape (RUNS_ROOT / HARNESS_RUN / RUN_NN) → the TUI opens at /
    # --dump renders the corresponding page. Replaces the
    # --runs-root / --dump-mode / --dump-path flag triple (those
    # stay accepted, deprecated, below).
    p_tui.add_argument(
        "path", nargs="?", default=None,
        help=("v1.5.7 135: a runs-root, a harness-run dir, or a "
              "run-NN dir — the page is inferred from the path's "
              "shape. Omit to default to ./repos/ (else "
              "./harness-runs/, else cwd)."),
    )
    p_tui.add_argument(
        "--runs-root", default=None,
        help=("DEPRECATED (v1.5.7 135): pass the path positionally "
              "instead. Still accepted — treated as the positional "
              "path when none is given."),
    )
    p_tui.add_argument(
        "--root", default=None,
        help=("v1.5.7 111: deprecated alias for --runs-root "
              "(pre-111 the tui subcommand opened the 094 "
              "manager TUI over <root>/control/queue.json; "
              "that path was superseded by 108's detached "
              "collector model)."),
    )
    p_tui.add_argument(
        "--curses", action="store_true",
        help=("v1.5.7 119: force the stdlib-curses TUI (the "
              "111/116/117 implementation). Default is the "
              "Textual app; this flag opts back into the "
              "dependency-free fallback."),
    )
    # v1.5.7 121: non-interactive page renderer. Works
    # WITHOUT textual installed — re-uses the pure view-model
    # builders + plain-text formatters. The testability hook
    # for verifying TUI rendering headlessly.
    # v1.5.7 135: --dump is now a BOOLEAN toggle — the page is
    # inferred from the positional path's shape. `--dump` alone →
    # headless render of the classified page. Back-compat: the old
    # `--dump runs|detail|output` enum strings are still accepted
    # (nargs="?" captures them) but the path's structure is
    # authoritative (a stderr warning fires if they disagree).
    p_tui.add_argument(
        "--dump", nargs="?", const=True, default=None,
        help=("v1.5.7 135: render the page for the positional path "
              "to stdout (plain text) and exit, instead of "
              "launching the interactive TUI. Works WITHOUT "
              "textual installed. (DEPRECATED forms: `--dump "
              "runs|detail|output` still accepted; the path's "
              "shape wins.)"),
    )
    p_tui.add_argument(
        "--dump-path", default=None,
        help=("DEPRECATED (v1.5.7 135): pass the path positionally "
              "instead. Still accepted as the positional path for "
              "`--dump detail`/`--dump output`."),
    )
    p_tui.add_argument(
        "--lines", type=int, default=2000,
        help=("v1.5.7 121: max output lines for `--dump "
              "output` (default 2000, tail-anchored). Caps "
              "the rendered tail so a long stream renders "
              "in bounded time."),
    )
    p_tui.add_argument(
        "--raw", action="store_true",
        help=("v1.5.7 122: with `--dump output`, emit "
              "verbatim wire-format lines (Claude stream-"
              "json events as raw JSON; ::QPB:: sentinels "
              "as their bare forms). Default is rendered."),
    )
    return p


_KNOWN_SUBCOMMANDS = frozenset({
    "run", "run-plan", "collect", "status", "tail",
    "manager", "tui", "kill",
    # v1.5.7 186 FINDING-36a: force-run subcommand.
    "force-run",
    # v1.5.7 180 followup: watchdog subcommand.
    "watchdog",
})


def _maybe_plan_file_shortcut(argv: "list[str]") -> "list[str]":
    """v1.5.7 149: plan-file shortcut. Rewrite
    ``<plan.json> [<runs-root>] [flags...]`` →
    ``run-plan <plan.json> [--runs-root <runs-root>] [flags...]``.

    Conservative — triggers ONLY when ALL hold: argv non-empty;
    argv[0] is NOT a known subcommand (explicit subcommand wins);
    argv[0] ends ``.json`` AND is an existing file; and
    ``load_plan`` parses it without raising. Any failure leaves
    argv unchanged → argparse produces its normal error (right for
    typos like ``rinplan plan.json`` or a bogus ``.json``).
    """
    if not argv or argv[0] in _KNOWN_SUBCOMMANDS:
        return argv
    first = argv[0]
    if not first.endswith(".json"):
        return argv
    path = Path(first)
    if not path.is_file():
        return argv
    try:
        from bin.harness.plan_runner import load_plan
        load_plan(path)  # read-only validation
    except Exception:
        # PlanError / OSError / JSONDecodeError — not a valid plan;
        # let argparse error normally.
        return argv
    rest = list(argv[1:])
    new = ["run-plan", str(path)]
    if rest and not rest[0].startswith("-"):
        new += ["--runs-root", rest[0]]
        rest = rest[1:]
    new += rest
    return new


def main(argv: "list[str] | None" = None) -> int:
    argv_list = list(sys.argv[1:] if argv is None else argv)
    if not argv_list:
        # 089x — self-describing no-args.
        _print_intro_minimal()
        return 0
    # v1.5.7 149: plan-file shortcut (before argparse dispatch).
    argv_list = _maybe_plan_file_shortcut(argv_list)
    parser = _build_parser()
    args = parser.parse_args(argv_list)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "run-plan":
        return _cmd_run_plan(args)
    if args.command == "collect":
        return _cmd_collect(args)
    if args.command == "watchdog":
        return _cmd_watchdog(args)
    if args.command == "status":
        return _cmd_status(args)
    if args.command == "tail":
        return _cmd_tail(args)
    if args.command == "kill":
        return _cmd_kill(args)
    if args.command == "force-run":
        return _cmd_force_run(args)
    if args.command == "manager":
        return _cmd_manager(args)
    if args.command == "tui":
        return _cmd_tui(args)
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
