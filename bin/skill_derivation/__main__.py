"""bin/skill_derivation/__main__.py — CLI entry point for the four-pass pipeline.

Usage:
    python3 -m bin.skill_derivation <target_dir> [options]

Options:
    --pass A|B|C|D|all          Pass to run; "all" runs A->B->C->D in
                                sequence with B4 upstream-status gate
                                enforced at each transition.
    --resume                    Resume from cursor (default behavior).
                                Pass --no-resume to start fresh.
    --runner claude|copilot     LLM runner for Pass A. Default:
                                claude (subprocess `claude --print
                                --model sonnet`).
    --pace-seconds N            Sleep N seconds between LLM calls in
                                Pass A. Used to throttle against rate
                                limits.
    --role-map-path PATH        Path to exploration_role_map.json
                                (v1.5.4). Default:
                                <target_dir>/quality/exploration_role_map.json.
                                Required by Pass C.
    --skill-md PATH             Path to SKILL.md. Default:
                                <target_dir>/SKILL.md.
    --references-dir PATH       Path to references/. Default:
                                <target_dir>/references.
    --pass-spec-path PATH       Path to the per-pass spec doc for the
                                recovery preamble. Default:
                                ~/Documents/AI-Driven Development/
                                Quality Playbook/Reviews/
                                QPB_v1.5.3_Phase3b_Brief.md
    --no-resume                 Start passes from scratch.

The orchestration enforces the B4 upstream-status gate: when --pass
all is used, Pass B refuses to start unless Pass A reached
status="complete"; Pass C refuses unless Pass B is complete; Pass D
refuses unless Pass C is complete. Refusal raises
protocol.UpstreamIncompleteError with a diagnostic naming the
downstream pass that refused.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

from bin.skill_derivation import (
    pass_a,
    pass_b,
    pass_c,
    pass_d,
    protocol,
    sections,
)
from bin.skill_derivation.runners import make_runner


# v1.5.4 Phase 3.6.9 Section C Step 5 (Round 7 deferral): the
# pass-spec brief is used as the LLM compaction-recovery context. The
# v1.5.3-era hardcoded path
# (``~/Documents/AI-Driven Development/.../QPB_v1.5.3_Phase3b_Brief.md``)
# was machine-specific to the development workspace and does not
# resolve on a fresh QPB install. The v1.5.4 default points to the
# in-repo design doc (which captures the same recovery-preamble
# content the v1.5.3 brief did, plus the v1.5.4 redesign rationale).
# The path is computed relative to this module so it resolves on any
# QPB checkout. Operators can override with ``--pass-spec-path``.
_DEFAULT_PASS_SPEC_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "design"
    / "QPB_v1.5.4_Design.md"
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python3 -m bin.skill_derivation",
        description=(
            "QPB v1.5.4 four-pass skill-derivation pipeline. Reads "
            "quality/exploration_role_map.json (produced by Phase 1) "
            "and runs Pass A through Pass D over the files tagged "
            "skill-prose / skill-reference; activation gated by "
            "bin.role_map.has_skill_prose. Produces draft REQs, "
            "mechanical citations, formal REQ records, and a coverage "
            "audit. See docs/design/QPB_v1.5.4_Design.md Part 1 for "
            "the activation contract and "
            "docs/design/QPB_v1.5.4_Implementation_Plan.md for phase "
            "sequencing."
        ),
    )
    parser.add_argument("target_dir", type=Path)
    parser.add_argument(
        "--pass",
        dest="pass_choice",
        choices=("A", "B", "C", "D", "all"),
        default="all",
        help='Which pass to run. "all" runs A->B->C->D in sequence.',
    )
    parser.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        default=True,
        help="Start passes from scratch (default: resume from cursor).",
    )
    parser.add_argument(
        "--runner",
        choices=("claude", "copilot", "codex", "cursor"),
        default="claude",
        help=(
            "LLM runner for Pass A. claude (default) wraps "
            "`claude --print`; copilot wraps `gh copilot --prompt`; "
            "codex wraps `codex exec --full-auto`; cursor wraps "
            "`cursor agent --print --force`."
        ),
    )
    parser.add_argument(
        "--pace-seconds",
        type=int,
        default=0,
        help="Sleep N seconds between Pass A LLM calls.",
    )
    parser.add_argument("--role-map-path", type=Path, default=None)
    parser.add_argument("--skill-md", type=Path, default=None)
    parser.add_argument("--references-dir", type=Path, default=None)
    parser.add_argument(
        "--pass-spec-path",
        type=Path,
        default=_DEFAULT_PASS_SPEC_PATH,
    )
    # Phase 5 Stage 0 (DQ-5-1): expose --phase, --part, --model so
    # later stages can drive Phase 4 modules from the same CLI.
    parser.add_argument(
        "--phase",
        type=int,
        choices=[3, 4],
        default=3,
        help=(
            "Phase to run. 3 = standard four-pass derivation "
            "(Pass A->B->C->D, current default). 4 = divergence "
            "detection over Phase 3's output (requires Phase 3 "
            "outputs at <target>/quality/phase3/)."
        ),
    )
    parser.add_argument(
        "--part",
        choices=("a1", "a2", "a3", "b", "c", "d", "all"),
        default="all",
        help=(
            "Specific part to run (--phase 4 only). a1=internal-prose, "
            "a2=prose-to-code-mechanical, a3=prose-to-code-llm, "
            "b=execution, c=gate-enforcement, d=bug-production+inbox, "
            "all=run sequence A1..D. Ignored for --phase 3."
        ),
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=(
            "Override the runner's default model. For --runner claude: "
            "'sonnet' (default), 'opus'. For --runner copilot: "
            "'claude-sonnet-4.6' (default), 'claude-opus-4.6'. For "
            "--runner codex: any model in ~/.codex/config.toml's catalog "
            "(e.g., 'gpt-5-codex'); empty default lets codex pick from "
            "its own config. For --runner cursor: any model accepted "
            "by `cursor agent --model` (e.g., 'sonnet-4', 'gpt-5'); "
            "empty default lets cursor pick from its own account/config."
        ),
    )
    return parser.parse_args(argv)


def _phase3_dir(target_dir: Path) -> Path:
    return target_dir / "quality" / "phase3"


# v1.5.4 Phase 3.6.9 Section C Step 1: the role-map roles that
# contribute to Pass A's skill-derivation input set are sourced from
# bin.role_map.SKILL_PROSE_ROLES rather than a duplicated local
# constant. Round 1 fixed an analogous duplication
# (derive_legacy_project_type bin↔gate); the same discipline applies
# here. SKILL_PROSE_ROLES is the single source of truth.


def _role_map_skill_prose_files(
    role_map: Optional[dict], target_dir: Path
) -> Optional[list[Path]]:
    """Return the list of absolute paths the Phase-1 role map tagged as
    ``skill-prose`` or ``skill-reference``, in role-map order.

    Return values, by case:

    - **``None``** — the role map is absent or unparsable. Callers
      pass ``None`` through to ``sections.enumerate_skill_and_references``,
      which falls back to the v1.5.3 hardcoded enumeration (SKILL.md
      plus ``references/*.md``).
    - **``[]``** — the role map exists but contains zero files tagged
      ``skill-prose`` or ``skill-reference``. ``enumerate_skill_and_references``
      will produce an empty section list. The activation predicate
      (``has_skill_prose``) gates this case before it reaches Pass A,
      but the asymmetry is here so callers that bypass the predicate
      get a deterministic empty result rather than the v1.5.3 fallback.
    - **non-empty list[Path]** — every absolute path the role map
      tagged ``skill-prose`` or ``skill-reference``.

    v1.5.4 Phase 3 Stage 3 (Round 5 finding B1-F4): files tagged with
    roles outside ``bin.role_map.SKILL_PROSE_ROLES`` are silently
    dropped from the return list, but each one prints a single
    ``[role-map] note:``
    line on stderr naming the file path and its actual role so an
    operator who tagged something ``docs`` and expected Pass A to read
    it has a signal. No gate failure, no exception — the diagnostic is
    advisory.
    """
    from bin import role_map as _role_map  # noqa: WPS433
    if not isinstance(role_map, dict):
        return None
    files = role_map.get("files") or []
    if not isinstance(files, list):
        return None
    out: list[Path] = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        path = entry.get("path")
        if role in _role_map.SKILL_PROSE_ROLES:
            if isinstance(path, str) and path.strip():
                out.append((target_dir / path).resolve())
            continue
        # B1-F4 diagnostic: tell the operator that a role-map entry
        # with an "interesting" role (anything not in the Pass A input
        # set AND not in the conventional infrastructure-bucket roles)
        # was excluded. The check fires for every non-input role so
        # `code`, `test`, `docs`, etc. all get a line — adopters who
        # tag intentionally see a single advisory line per file rather
        # than a silent black hole.
        if isinstance(path, str) and path.strip() and role is not None:
            print(
                f"[role-map] note: {path!r} tagged {role!r}; excluded "
                "from Pass A input (skill-prose / skill-reference only)",
                file=sys.stderr,
            )
    return out


def _enumerate_for_pass_a(args: argparse.Namespace, target_dir: Path) -> Path:
    """Run section enumeration over the role-map's skill-prose +
    skill-reference surface and write pass_a_sections.json. Returns
    the path to the sections JSON.

    v1.5.4 Phase 2.1 (Round 4 Council finding C1): file enumeration is
    driven by ``quality/exploration_role_map.json`` so targets whose
    skill surface lives outside the conventional ``references/``
    directory (e.g. pdf-1.5.3's FORMS.md and REFERENCE.md at the
    repository root) are correctly walked. When the role map is absent
    (pre-Phase-1 / pre-iteration targets), enumeration falls back to
    the v1.5.3 behaviour: SKILL.md plus ``references/*.md``.
    """
    skill_md = args.skill_md or (target_dir / "SKILL.md")
    refs = (
        args.references_dir
        if args.references_dir is not None
        else target_dir / "references"
    )
    role_map_data = _resolve_role_map_for_dispatch(args, target_dir)
    role_map_files = _role_map_skill_prose_files(role_map_data, target_dir)
    secs = sections.enumerate_skill_and_references(
        skill_md,
        refs if refs.is_dir() else None,
        target_dir,
        role_map_files=role_map_files,
    )
    out = _phase3_dir(target_dir) / "pass_a_sections.json"
    sections.write_sections_json(secs, out)
    return out


class _PacingRunner:
    """Wraps an LLMRunner with a sleep between calls."""

    def __init__(self, inner, pace_seconds: int) -> None:
        self._inner = inner
        self._pace = pace_seconds
        self._call_count = 0

    def run(self, prompt: str):
        if self._call_count > 0 and self._pace > 0:
            time.sleep(self._pace)
        self._call_count += 1
        return self._inner.run(prompt)


def _run_pass_a(args: argparse.Namespace, target_dir: Path) -> int:
    sections_path = _enumerate_for_pass_a(args, target_dir)
    p3 = _phase3_dir(target_dir)
    refs_dir = (
        args.references_dir
        if args.references_dir is not None
        else target_dir / "references"
    )
    config = pass_a.PassAConfig(
        drafts_path=p3 / "pass_a_drafts.jsonl",
        progress_path=p3 / "pass_a_progress.json",
        sections_path=sections_path,
        pass_spec_path=args.pass_spec_path,
        document_root=target_dir,
        uc_drafts_path=p3 / "pass_a_use_case_drafts.jsonl",
        req_template_path=Path(__file__).parent / "prompts" / "pass_a_section.md",
        uc_template_path=Path(__file__).parent / "prompts" / "pass_a_uc_section.md",
        references_dir=refs_dir if refs_dir.is_dir() else None,
    )
    inner_runner = make_runner(args.runner, model=args.model)
    runner = (
        _PacingRunner(inner_runner, args.pace_seconds)
        if args.pace_seconds > 0
        else inner_runner
    )
    return pass_a.run_pass_a(
        config,
        runner,
        config.req_template_path,
        resume=args.resume,
    )


def _run_pass_b(args: argparse.Namespace, target_dir: Path) -> int:
    p3 = _phase3_dir(target_dir)
    refs_dir = (
        args.references_dir
        if args.references_dir is not None
        else target_dir / "references"
    )
    skill_md = args.skill_md or (target_dir / "SKILL.md")
    config = pass_b.PassBConfig(
        drafts_path=p3 / "pass_a_drafts.jsonl",
        citations_path=p3 / "pass_b_citations.jsonl",
        progress_path=p3 / "pass_b_progress.json",
        skill_md_path=skill_md,
        references_dir=refs_dir if refs_dir.is_dir() else None,
        document_root=target_dir,
        pass_a_progress_path=p3 / "pass_a_progress.json",
    )
    return pass_b.run_pass_b(config, resume=args.resume)


def _run_pass_c(args: argparse.Namespace, target_dir: Path) -> int:
    p3 = _phase3_dir(target_dir)
    role_map_path = (
        args.role_map_path
        if args.role_map_path is not None
        else target_dir / "quality" / "exploration_role_map.json"
    )
    config = pass_c.PassCConfig(
        citations_path=p3 / "pass_b_citations.jsonl",
        uc_drafts_path=p3 / "pass_a_use_case_drafts.jsonl",
        formal_path=p3 / "pass_c_formal.jsonl",
        formal_use_cases_path=p3 / "pass_c_formal_use_cases.jsonl",
        progress_path=p3 / "pass_c_progress.json",
        pass_b_progress_path=p3 / "pass_b_progress.json",
        role_map_path=role_map_path,
    )
    return pass_c.run_pass_c(config, resume=args.resume)


def _run_pass_d(args: argparse.Namespace, target_dir: Path) -> dict:
    p3 = _phase3_dir(target_dir)
    config = pass_d.PassDConfig(
        drafts_path=p3 / "pass_a_drafts.jsonl",
        uc_drafts_path=p3 / "pass_a_use_case_drafts.jsonl",
        formal_path=p3 / "pass_c_formal.jsonl",
        formal_use_cases_path=p3 / "pass_c_formal_use_cases.jsonl",
        sections_path=p3 / "pass_a_sections.json",
        audit_path=p3 / "pass_d_audit.json",
        section_coverage_path=p3 / "pass_d_section_coverage.json",
        council_inbox_path=p3 / "pass_d_council_inbox.json",
        progress_path=p3 / "pass_d_progress.json",
        pass_c_progress_path=p3 / "pass_c_progress.json",
    )
    return pass_d.run_pass_d(config, resume=args.resume)


def _run_phase4(args: argparse.Namespace, target_dir: Path) -> int:
    """Phase 5 Stage 0 dispatcher: drives Phase 4 modules per --part.

    --part a1: internal-prose divergence (divergence_internal.py)
    --part a2: prose-to-code mechanical (divergence_prose_to_code_mechanical.py)
    --part a3: prose-to-code LLM (divergence_prose_to_code_llm.py)
    --part b: execution divergence (divergence_execution.py)
    --part d: bug production + Phase 4 inbox (divergence_to_bugs.py + phase4_inbox.py)
    --part all: a1 -> a2 -> b -> d in sequence (a3 NOT in 'all'; LLM
                pacing makes it inappropriate for the default sweep)
    --part c: skill-project gate enforcement runs as part of the
              quality_gate.py check sequence; not driven via this CLI.
              We accept --part c so the argparse choice list is
              non-confusing, but emit an info message and exit 0.
    """
    from bin.skill_derivation import (
        divergence_internal,
        divergence_prose_to_code_mechanical,
        divergence_prose_to_code_llm,
        divergence_execution,
        divergence_to_bugs,
        phase4_inbox,
    )
    p3 = _phase3_dir(target_dir)
    p3.mkdir(parents=True, exist_ok=True)
    sections_path = p3 / "pass_a_sections.json"
    formal_path = p3 / "pass_c_formal.jsonl"
    formal_uc_path = p3 / "pass_c_formal_use_cases.jsonl"
    parts_to_run = (
        ("a1", "a2", "b", "d") if args.part == "all" else (args.part,)
    )
    un_anchored_uc_ids: tuple = ()
    for part in parts_to_run:
        if part == "a1":
            print(
                "=== Phase 4 Part A.1: internal-prose divergence ===",
                file=sys.stderr,
            )
            cfg = divergence_internal.InternalDivergenceConfig(
                formal_path=formal_path,
                formal_use_cases_path=formal_uc_path,
                sections_path=sections_path,
                document_root=target_dir,
                output_path=p3 / "pass_e_internal_divergences.jsonl",
            )
            result = divergence_internal.run_divergence_internal(cfg)
            un_anchored_uc_ids = tuple(result.get("un_anchored_uc_ids") or ())
            print(f"Part A.1 summary: {result}", file=sys.stderr)
        elif part == "a2":
            print(
                "=== Phase 4 Part A.2: mechanical prose-to-code ===",
                file=sys.stderr,
            )
            cfg = divergence_prose_to_code_mechanical.ProseToCodeMechanicalConfig(
                formal_path=formal_path,
                output_path=p3 / "pass_e_prose_to_code_divergences.jsonl",
                repo_root=target_dir,
                sections_path=sections_path,
                skipped_uc_ids=un_anchored_uc_ids,
            )
            result = divergence_prose_to_code_mechanical.run_divergence_prose_to_code_mechanical(cfg)
            print(f"Part A.2 summary: {result}", file=sys.stderr)
        elif part == "a3":
            print(
                "=== Phase 4 Part A.3: LLM-driven prose-to-code ===",
                file=sys.stderr,
            )
            # v1.5.4 Phase 2 Site 3: activate iff the Phase-1 role map
            # tagged skill-tool files. Replaces the v1.5.3
            # project_type=='Hybrid' gate.
            from bin import role_map as _role_map
            role_map_path = (
                args.role_map_path
                if args.role_map_path is not None
                else _role_map.default_path(target_dir)
            )
            loaded = _role_map.load_role_map(role_map_path)
            should_run = _role_map.has_skill_tools(loaded)
            cfg = divergence_prose_to_code_llm.ProseToCodeLLMConfig(
                formal_path=formal_path,
                output_path=p3 / "pass_e_prose_to_code_divergences.jsonl",
                progress_path=p3 / "pass_e_prose_to_code_progress.json",
                repo_root=target_dir,
                should_run=should_run,
                sections_path=sections_path,
                pass_spec_path=args.pass_spec_path,
                skipped_uc_ids=un_anchored_uc_ids,
                pace_seconds=args.pace_seconds,
            )
            inner_runner = make_runner(args.runner, model=args.model)
            result = divergence_prose_to_code_llm.run_divergence_prose_to_code_llm(
                cfg, inner_runner, resume=args.resume,
            )
            print(f"Part A.3 summary: {result}", file=sys.stderr)
        elif part == "b":
            print(
                "=== Phase 4 Part B: execution divergence ===",
                file=sys.stderr,
            )
            # v1.5.6 fix-up 071 BUG-002: archive_run() writes to
            # quality/previous_runs/, not target_dir/previous_runs/.
            # Pre-fix this resolved to a directory archive_run never
            # populates, so the execution-divergence loader silently
            # passed None to the consumer for every legitimate
            # archived run — hiding archived evidence from divergence
            # analysis.
            prev_runs = target_dir / "quality" / "previous_runs"
            cfg = divergence_execution.ExecutionDivergenceConfig(
                formal_path=formal_path,
                previous_runs_dir=prev_runs if prev_runs.is_dir() else None,
                output_path=p3 / "pass_e_execution_divergences.jsonl",
                sections_path=sections_path,
            )
            result = divergence_execution.run_divergence_execution(cfg)
            print(f"Part B summary: {result}", file=sys.stderr)
        elif part == "c":
            print(
                "=== Phase 4 Part C: gate enforcement runs via "
                "quality_gate.py; skipping ===", file=sys.stderr,
            )
        elif part == "d":
            print(
                "=== Phase 4 Part D: BUG production + inbox ===",
                file=sys.stderr,
            )
            # Ensure all three divergence files exist (touch empty if absent).
            for fname in (
                "pass_e_internal_divergences.jsonl",
                "pass_e_prose_to_code_divergences.jsonl",
                "pass_e_execution_divergences.jsonl",
            ):
                (p3 / fname).touch()
            bugs_cfg = divergence_to_bugs.DivergenceToBugsConfig(
                internal_path=p3 / "pass_e_internal_divergences.jsonl",
                prose_to_code_path=p3 / "pass_e_prose_to_code_divergences.jsonl",
                execution_path=p3 / "pass_e_execution_divergences.jsonl",
                output_path=p3 / "pass_e_bugs.jsonl",
            )
            bugs_result = divergence_to_bugs.run_divergence_to_bugs(bugs_cfg)
            print(f"Part D.1 summary: {bugs_result}", file=sys.stderr)
            inbox_cfg = phase4_inbox.Phase4InboxConfig(
                internal_path=p3 / "pass_e_internal_divergences.jsonl",
                prose_to_code_path=p3 / "pass_e_prose_to_code_divergences.jsonl",
                execution_path=p3 / "pass_e_execution_divergences.jsonl",
                bugs_path=p3 / "pass_e_bugs.jsonl",
                phase4_inbox_path=p3 / "pass_e_council_inbox.json",
                phase3_inbox_path=p3 / "pass_d_council_inbox.json",
                formal_path=formal_path,
                formal_use_cases_path=formal_uc_path,
            )
            inbox_result = phase4_inbox.build_phase4_inbox(inbox_cfg)
            print(f"Part D.2 inbox summary: {inbox_result}", file=sys.stderr)
            backfill_result = phase4_inbox.backfill_triage_batch_key(inbox_cfg)
            print(f"Part D.2 backfill summary: {backfill_result}", file=sys.stderr)
    return 0


def _resolve_role_map_for_dispatch(args: argparse.Namespace, target_dir: Path):
    """Load the Phase-1 role map for dispatch-time activation decisions.

    Returns the parsed role-map dict, or ``None`` when the role map is
    absent or unparsable. Pass-specific runners may still raise their
    own errors when they require the role map (Pass C does); this helper
    only services activation gates that need to short-circuit cleanly
    on empty-side targets.
    """
    from bin import role_map as _role_map  # noqa: WPS433
    role_map_path = (
        args.role_map_path
        if args.role_map_path is not None
        else _role_map.default_path(target_dir)
    )
    return _role_map.load_role_map(role_map_path)


def _main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    target_dir = args.target_dir.resolve()
    p3 = _phase3_dir(target_dir)
    p3.mkdir(parents=True, exist_ok=True)

    if args.phase == 4:
        return _run_phase4(args, target_dir)

    # v1.5.4 Phase 2 Site 1: four-pass skill-derivation pipeline
    # activates iff the Phase-1 role map reports a skill-prose surface.
    # When the target has zero skill-prose files (e.g. a pure-code
    # benchmark), the pipeline no-ops cleanly without invoking any
    # LLM passes.
    #
    # Backward-compat asymmetry (Phase 2.1 / Round 4 finding A3):
    # Site 1 (here) and Site 3 (Phase 4 prose-to-code) treat "no role
    # map" as "skip" — the four-pass pipeline is new in v1.5.4 and
    # has no v1.5.3 behaviour to preserve. Site 2 (run_playbook Phase 3
    # code review) treats "no role map" as "run as before" so v1.5.3
    # pre-iteration targets keep producing BUGS.md without operator
    # intervention. See docs/design/QPB_v1.5.4_Implementation_Plan.md
    # Phase 2 for the contract.
    from bin import role_map as _role_map  # noqa: WPS433
    role_map_data = _resolve_role_map_for_dispatch(args, target_dir)
    if not _role_map.has_skill_prose(role_map_data):
        print(
            "=== bin.skill_derivation: role map shows no skill-prose "
            "surface; four-pass pipeline no-ops ===",
            file=sys.stderr,
        )
        return 0

    if args.pass_choice in ("A", "all"):
        print(f"=== Pass A: naive coverage on {target_dir} ===", file=sys.stderr)
        _run_pass_a(args, target_dir)

    if args.pass_choice in ("B", "all"):
        print("=== Pass B: mechanical citation extraction ===", file=sys.stderr)
        _run_pass_b(args, target_dir)

    if args.pass_choice in ("C", "all"):
        print("=== Pass C: formal REQ + UC production ===", file=sys.stderr)
        _run_pass_c(args, target_dir)

    if args.pass_choice in ("D", "all"):
        print("=== Pass D: coverage audit + council inbox ===", file=sys.stderr)
        summary = _run_pass_d(args, target_dir)
        print(f"Pass D summary: {summary}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(_main())
