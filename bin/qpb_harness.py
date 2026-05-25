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
    try:
        prep_result = _prepare.prepare(case, target_dir,
                                          ai_tool=args.runner)
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


def _cmd_tui(args: argparse.Namespace) -> int:
    """Launch the read-mostly Textual TUI (Phase 4)."""
    from bin.harness import tui as _tui

    root = Path(args.root).expanduser().resolve()
    snapshot_file = root / "control" / "queue.json"
    if not snapshot_file.is_file():
        print(f"ERROR: no manager snapshot at {snapshot_file}. "
              f"Start the manager first.", file=sys.stderr)
        return 2
    try:
        snapshot = json.loads(snapshot_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: failed to read snapshot: {exc}",
              file=sys.stderr)
        return 2
    try:
        app = _tui.build_app(snapshot)
    except RuntimeError as exc:
        # Textual isn't installed — fall back to printing the
        # data-shaping output so the operator still gets state.
        print(f"NOTE: {exc}", file=sys.stderr)
        for line in _tui.render_overview(snapshot):
            print(line)
        return 0
    app.run()
    return 0


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
        help="Open the Textual TUI (read-mostly client; Phase 4).",
    )
    p_tui.add_argument("--root", required=True,
                        help="Harness runner root.")
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
    if args.command == "manager":
        return _cmd_manager(args)
    if args.command == "tui":
        return _cmd_tui(args)
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
