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
import sys
from datetime import datetime, timezone
from pathlib import Path


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
    runs_root = Path(args.runs_root).expanduser().resolve()
    runs_root.mkdir(parents=True, exist_ok=True)
    try:
        plan = _plan.load_plan(plan_path)
    except _plan.PlanError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    wheel_override = (
        Path(args.wheel).expanduser().resolve()
        if getattr(args, "wheel", None) else None
    )
    tgz_override = (
        Path(args.tgz).expanduser().resolve()
        if getattr(args, "tgz", None) else None
    )
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
        print(f"harness-run dir: {latest}", file=sys.stderr)
        print(
            f"collector pid {collector_pid}; check status with"
            f" `python3 -m bin.qpb_harness status`",
            file=sys.stderr,
        )
        return 0
    # fake_run / synchronous path (existing 099-107 callers).
    met = sum(1 for o in outcomes if o.result == "MET")
    total = len(outcomes)
    print(f"Plan complete: {met}/{total} MET", file=sys.stderr)
    return 0 if met == total else 1


def _cmd_status(args: argparse.Namespace) -> int:
    """v1.5.7 110: read-only status view.

    No args / ``--runs-root <DIR>``: table of in-flight + recent
    harness-runs (dir, age, R/D/F/T/AP/P counts, collector-
    live?). With a harness-run dir: per-repo drill-down (index,
    repo, runner/model, state, current phase + state + last
    note, result, pid(live?)).
    """
    from bin.harness import status as _status

    harness_run_dir = getattr(args, "harness_run_dir", None)
    if harness_run_dir:
        target = Path(harness_run_dir).expanduser().resolve()
        if not (target / "manifest.json").is_file():
            print(
                f"ERROR: no manifest.json under {target} "
                f"(not a harness-run dir, or no run-plan has "
                f"been launched there)",
                file=sys.stderr,
            )
            return 2
        runs = _status.read_run_status(target)
        if not runs:
            print(
                f"harness-run dir: {target} (empty manifest)",
                file=sys.stderr,
            )
            return 0
        print(f"harness-run dir: {target}")
        print("")
        for rs in runs:
            print(_status.format_run_status(rs))
            if rs.last_note:
                print(f"     note: {rs.last_note}")
        return 0

    # No drill-down: list all harness-runs.
    runs_root = Path(
        getattr(args, "runs_root", "harness-runs")
    ).expanduser().resolve()
    summaries = _status.list_harness_runs(runs_root)
    if not summaries:
        print(
            f"No harness-runs under {runs_root}",
            file=sys.stderr,
        )
        return 0
    print(f"runs-root: {runs_root}")
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


def _cmd_tui_dump(args: argparse.Namespace,
                     runs_root: Path) -> int:
    """v1.5.7 121: render a TUI page to stdout
    non-interactively. Works WITHOUT textual installed —
    delegates to the pure text formatters in
    ``bin.harness.tui`` (which read via status.py and don't
    touch textual).

    Returns 0 on success, 2 on missing args (e.g. detail/
    output without --dump-path)."""
    from bin.harness import tui as _tui
    mode = args.dump
    if mode == "runs":
        text = _tui.format_runs_list_as_text(runs_root)
    elif mode == "detail":
        path = getattr(args, "dump_path", None)
        if not path:
            sys.stderr.write(
                "qpb_harness tui --dump detail: requires "
                "--dump-path <harness-run-dir>\n"
            )
            return 2
        text = _tui.format_detail_as_text(
            Path(path).expanduser().resolve())
    elif mode == "output":
        path = getattr(args, "dump_path", None)
        if not path:
            sys.stderr.write(
                "qpb_harness tui --dump output: requires "
                "--dump-path <run-NN-dir>\n"
            )
            return 2
        lines = int(getattr(args, "lines", 2000))
        # v1.5.7 122: --raw flips off the renderer; default
        # is rendered (clean log lines).
        rendered = not bool(getattr(args, "raw", False))
        text = _tui.format_output_as_text(
            Path(path).expanduser().resolve(),
            max_lines=lines,
            rendered=rendered,
        )
    else:  # pragma: no cover - argparse choices guard
        sys.stderr.write(f"unknown --dump mode: {mode}\n")
        return 2
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

    runs_root_raw = (
        getattr(args, "runs_root", None)
        or getattr(args, "root", None)
        or "harness-runs"
    )
    runs_root = Path(runs_root_raw).expanduser().resolve()

    # v1.5.7 121: --dump <page> non-interactive render.
    # Works WITHOUT textual installed — re-uses the pure
    # view-model builders. The testability hook.
    dump_mode = getattr(args, "dump", None)
    if dump_mode:
        return _cmd_tui_dump(args, runs_root)

    # v1.5.7 119: Textual by default; curses on --curses or
    # textual ImportError.
    force_curses = bool(getattr(args, "curses", False))
    if force_curses:
        return _tui.launch_status_tui(runs_root)
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
        return _tui.launch_status_tui(runs_root)
    return _tui.launch_textual_tui(runs_root)


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
    p_plan.add_argument("--runs-root", default="harness-runs",
                          help="Root directory for harness-run "
                               "output folders (gitignored by "
                               "convention).")
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

    # v1.5.7 110: status (no-arg + per-harness-run) + tail.
    p_status = sub.add_parser(
        "status",
        help=("v1.5.7 110: list in-flight + recent harness-"
              "runs OR drill into one harness-run's per-repo "
              "state, current phase, result, pid-liveness."),
    )
    p_status.add_argument(
        "harness_run_dir", nargs="?", default=None,
        help=("Optional harness-run directory for the per-repo "
              "drill-down view. Omit for the runs-root list."),
    )
    p_status.add_argument(
        "--runs-root", default="harness-runs",
        help=("Root directory containing harness-run folders "
              "(default: harness-runs). Ignored when a "
              "harness-run-dir is provided."),
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
        help="Path to the run-NN directory inside a harness-run.",
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
    p_tui.add_argument(
        "--runs-root", default="harness-runs",
        help=("Root directory containing harness-run folders "
              "(default: harness-runs)."),
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
    p_tui.add_argument(
        "--dump", choices=["runs", "detail", "output"],
        default=None,
        help=("v1.5.7 121: render a specific TUI page to "
              "stdout (plain text) and exit. Works WITHOUT "
              "textual installed. Options: `runs` (uses "
              "--runs-root), `detail` (uses --dump-path "
              "<harness-run-dir>), `output` (uses --dump-path "
              "<harness-run-dir>/run-NN, with optional --lines)."),
    )
    p_tui.add_argument(
        "--dump-path", default=None,
        help=("v1.5.7 121: path for `--dump detail` (harness-"
              "run dir) or `--dump output` (run-NN dir)."),
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


def main(argv: "list[str] | None" = None) -> int:
    argv_list = list(sys.argv[1:] if argv is None else argv)
    if not argv_list:
        # 089x — self-describing no-args.
        _print_intro_minimal()
        return 0
    parser = _build_parser()
    args = parser.parse_args(argv_list)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "run-plan":
        return _cmd_run_plan(args)
    if args.command == "collect":
        return _cmd_collect(args)
    if args.command == "status":
        return _cmd_status(args)
    if args.command == "tail":
        return _cmd_tail(args)
    if args.command == "manager":
        return _cmd_manager(args)
    if args.command == "tui":
        return _cmd_tui(args)
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
