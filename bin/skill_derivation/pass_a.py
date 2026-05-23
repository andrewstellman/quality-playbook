"""pass_a.py — Pass A driver (naive coverage, section-iterative).

Reads pass_a_sections.json (produced by sections.enumerate_sections),
walks the section tree, fires the LLM runner once per non-skipped
section, parses the JSONL response, and appends to
pass_a_drafts.jsonl. Cursor + progress per the per-pass execution
protocol.

Skipped sections (meta-allowlist or screaming) emit a single
`{section_idx, skipped: true, skip_reason}` record directly without
firing the LLM.

Throughput tripwire: per-section elapsed time recorded in each
record's _metadata.elapsed_ms. If more than 5 sections complete per
minute (i.e., any section completes in under 12 seconds), the driver
halts with a diagnostic. Sub-12-second LLM responses on substantive
sections indicate stub generation under context pressure (the
"plausible junk" failure mode).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional

from bin.skill_derivation import protocol, sections
from bin.skill_derivation.runners import LLMRunner, RunnerResult


def _tag_cross_references(
    records: list[dict],
    section_text: str,
    references_basenames: "frozenset[str]",
) -> None:
    """Phase 3b A.3: tag REQ records with detected cross-references
    to reference files. Mutates records in place. UC records and
    skip/no_reqs accounting markers are left untouched.
    """
    if not references_basenames:
        return
    refs = sections.detect_cross_references(
        section_text, references_basenames=references_basenames
    )
    if not refs:
        return
    for rec in records:
        if "draft_idx" in rec:  # REQ records only; UCs and markers skipped
            rec["cross_references"] = refs


# Throughput tripwire threshold. Sub-this elapsed time on a
# substantive section indicates stub generation under context pressure.
# Phase 3c live-run tuning: lowered from 12_000ms (original SKILL.md-
# calibrated floor) to 2_500ms based on QPB live-run evidence that
# reference-file sub-sections legitimately complete in 3-12s. The
# original 12s floor trip-fired on section 39 (11890ms, "The two-
# round challenge") and section 44 (4542ms, "Where Scenarios Come
# From"), both of which produced 5+ substantive REQ drafts on resume.
# The 2.5s floor still catches the pathological "plausible junk"
# failure mode (responses under 2s typically lack any content) while
# allowing legit fast responses on small reference-file sub-sections.
MIN_PLAUSIBLE_ELAPSED_MS = 2_500


# Default tail-context budget (preceding + following section snippets,
# in lines, capped). Tail context helps the LLM disambiguate where the
# section sits in the document; too much context inflates token usage.
DEFAULT_TAIL_CONTEXT_LINES = 30


@dataclass
class PassAConfig:
    drafts_path: Path
    progress_path: Path
    sections_path: Path
    pass_spec_path: Path  # for the recovery preamble
    document_root: Path  # repo root; documents are read by joining their relative paths
    starting_draft_idx: int = 0
    tail_context_lines: int = DEFAULT_TAIL_CONTEXT_LINES
    # Phase 3b A.1: parallel JSONL artifact for UC drafts. Default
    # convention: pass_a_use_case_drafts.jsonl next to the REQ drafts.
    uc_drafts_path: Optional[Path] = None
    starting_uc_draft_idx: int = 0
    # Per-section-kind prompt template paths. The driver picks based
    # on the section's section_kind ("operational" -> req template;
    # "execution-mode" -> uc template).
    req_template_path: Optional[Path] = None
    uc_template_path: Optional[Path] = None
    # Phase 3b A.3: cross-reference detection. The driver runs the
    # regex over each section's body text and tags REQ records with
    # the list of referenced files. Pass C uses this to flag
    # potential internal-prose divergences for Phase 4. Pass the
    # references_dir (e.g., target_dir/references); the driver
    # collects basenames for the false-positive filter.
    references_dir: Optional[Path] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_section_text(
    document_root: Path, section: dict, *, tail_context_lines: int
) -> tuple[str, str]:
    """Return (section_body, tail_context) for a section dict.

    section_body is the lines from line_start..line_end (inclusive).
    tail_context is the preceding + following N lines clipped at
    document boundaries -- used to give the LLM a sense of where the
    section sits relative to neighbors.
    """
    doc_path = document_root / section["document"]
    text = doc_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    line_start = section["line_start"]  # 1-based
    line_end = section["line_end"]      # exclusive (per enumerate_sections)
    body_lines = lines[line_start - 1 : line_end]

    pre_start = max(0, (line_start - 1) - tail_context_lines)
    pre = lines[pre_start : line_start - 1]
    post_end = min(len(lines), line_end + tail_context_lines)
    post = lines[line_end:post_end]

    body = "\n".join(body_lines)
    tail_context = (
        "[preceding context]\n"
        + "\n".join(pre[-tail_context_lines:])
        + "\n\n[following context]\n"
        + "\n".join(post[:tail_context_lines])
    )
    return body, tail_context


def _render_prompt(
    template_path: Path,
    *,
    section: dict,
    section_text: str,
    tail_context: str,
    starting_draft_idx: int,
    config: PassAConfig,
    starting_uc_draft_idx: int = 0,
) -> str:
    template = template_path.read_text(encoding="utf-8")
    recovery = protocol.render_recovery_preamble(
        pass_spec_path=config.pass_spec_path,
        progress_file_path=config.progress_path,
    )
    # Both REQ and UC templates accept the same kwargs; UC template
    # additionally substitutes {starting_uc_draft_idx}. The REQ
    # template ignores extra kwargs because str.format is permissive
    # only when the unused kwarg name doesn't appear; safest to call
    # .format() with the union of fields and let the template pick.
    fields = dict(
        recovery_preamble=recovery,
        document=section["document"],
        section_heading=section["heading"],
        heading_level=section["heading_level"],
        section_idx=section["section_idx"],
        line_start=section["line_start"],
        line_end=section["line_end"],
        section_text=section_text,
        tail_context=tail_context,
        starting_draft_idx=starting_draft_idx,
        starting_uc_draft_idx=starting_uc_draft_idx,
    )
    # Use a forgiving format so a template that doesn't reference
    # starting_uc_draft_idx (the REQ template) doesn't break.
    return template.format_map(_PermissiveDict(fields))


class _PermissiveDict(dict):
    """Format-mapping that returns the keyed value if present, else
    the placeholder verbatim. Lets the REQ template ignore the UC-only
    `starting_uc_draft_idx` placeholder without erroring."""

    def __missing__(self, key):
        return "{" + key + "}"


def _parse_jsonl_response(stdout: str, *, expected_section_idx: int) -> list[dict]:
    """Parse the LLM's JSONL output into a list of dicts.

    Tolerant: skips blank lines, skips non-JSON lines (logs them),
    accepts both `no_reqs` markers and full draft REQ records.
    """
    out: list[dict] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # Strip surrounding code fences if the model wrapped output
        # despite the prompt instruction.
        if line.startswith("```"):
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict):
            continue
        # Tag the record with the expected section_idx if missing,
        # but trust the model when it set one.
        rec.setdefault("section_idx", expected_section_idx)
        out.append(rec)
    return out


class TripwireFired(RuntimeError):
    """Raised when per-section throughput exceeds the plausible ceiling."""


def _check_tripwire(elapsed_ms: int, *, section: dict) -> None:
    if section.get("skip_reason"):
        return  # skipped sections don't run the LLM
    if elapsed_ms < MIN_PLAUSIBLE_ELAPSED_MS:
        raise TripwireFired(
            f"Pass A throughput tripwire: section_idx={section['section_idx']} "
            f"({section['heading']!r}) completed in {elapsed_ms}ms, below the "
            f"{MIN_PLAUSIBLE_ELAPSED_MS}ms plausibility floor. Sub-12s LLM "
            f"responses on substantive sections indicate stub generation "
            f"under context pressure. Halt and inspect drafts for templated "
            f"output before resuming."
        )


def run_pass_a(
    config: PassAConfig,
    runner: LLMRunner,
    template_path: Path,
    *,
    resume: bool = True,
) -> int:
    """Drive Pass A end-to-end.

    Returns the number of sections processed in this invocation
    (including skipped sections, which are emitted as records but do
    not fire the LLM).

    Phase 3b A.1: when the section's section_kind == "execution-mode"
    AND config.uc_template_path is set, the UC prompt template is
    used (which produces both REQ and UC records). Records are
    routed to two JSONL streams by shape: records with `draft_idx`
    -> drafts_path; records with `uc_draft_idx` -> uc_drafts_path.
    Sections with section_kind == "operational" use the standard REQ
    template (the original Phase 3a behavior).
    """
    sections_data = json.loads(config.sections_path.read_text(encoding="utf-8"))
    section_list = sections_data["sections"]
    total = len(section_list)

    # Resume: figure out the starting cursor from disk.
    cursor = (
        protocol.verify_and_resume(
            config.drafts_path, config.progress_path, idx_field="section_idx"
        )
        if resume
        else 0
    )

    state = protocol.ProgressState(
        pass_="A",
        unit="section",
        cursor=cursor,
        total=total,
        status="running",
        last_updated=_utc_now_iso(),
    )
    protocol.write_progress_atomic(config.progress_path, state)

    # Recompute next draft_idx and uc_draft_idx from disk so resumes
    # produce a consistent index space.
    next_draft_idx = config.starting_draft_idx + _count_existing_draft_idxs(
        config.drafts_path
    )
    next_uc_draft_idx = config.starting_uc_draft_idx + (
        _count_existing_uc_draft_idxs(config.uc_drafts_path)
        if config.uc_drafts_path is not None
        else 0
    )

    # Pick the actual prompt template per call. config.req_template_path
    # / uc_template_path take precedence over the legacy positional
    # `template_path` argument so tests can pass paths via config.
    req_template = config.req_template_path or template_path
    uc_template = config.uc_template_path  # may be None for operational-only runs

    # Phase 3b A.3: collect reference-file basenames once for the
    # cross-reference detection's false-positive filter.
    references_basenames = sections.collect_reference_basenames(
        config.references_dir
    )

    processed = 0
    for section in section_list:
        if section["section_idx"] < cursor:
            continue

        # section_kind defaults to "operational" if absent (older
        # pass_a_sections.json files at schema_version 1.0).
        section_kind = section.get("section_kind", "operational")

        if section.get("skip_reason"):
            protocol.append_jsonl(
                config.drafts_path,
                {
                    "section_idx": section["section_idx"],
                    "skipped": True,
                    "skip_reason": section["skip_reason"],
                    "_metadata": {"elapsed_ms": 0},
                },
            )
        else:
            section_text, tail_context = _read_section_text(
                config.document_root,
                section,
                tail_context_lines=config.tail_context_lines,
            )

            use_uc_template = (
                section_kind == "execution-mode"
                and uc_template is not None
                and config.uc_drafts_path is not None
            )
            chosen_template = uc_template if use_uc_template else req_template

            prompt = _render_prompt(
                chosen_template,
                section=section,
                section_text=section_text,
                tail_context=tail_context,
                starting_draft_idx=next_draft_idx,
                starting_uc_draft_idx=next_uc_draft_idx,
                config=config,
            )
            result = runner.run(prompt)
            _check_tripwire(result.elapsed_ms, section=section)
            records = _parse_jsonl_response(
                result.stdout, expected_section_idx=section["section_idx"]
            )
            if not records:
                protocol.append_jsonl(
                    config.drafts_path,
                    {
                        "section_idx": section["section_idx"],
                        "no_reqs": True,
                        "rationale": "LLM produced no parseable JSONL output",
                        "_metadata": {
                            "elapsed_ms": result.elapsed_ms,
                            "returncode": result.returncode,
                        },
                    },
                )
            else:
                _tag_cross_references(
                    records, section_text, references_basenames
                )
                for rec in records:
                    rec.setdefault("_metadata", {})
                    rec["_metadata"]["elapsed_ms"] = result.elapsed_ms
                    # Route by record shape: uc_draft_idx -> UC stream;
                    # draft_idx -> REQ stream; neither -> REQ stream
                    # (e.g., no_reqs markers).
                    if (
                        "uc_draft_idx" in rec
                        and isinstance(rec["uc_draft_idx"], int)
                        and config.uc_drafts_path is not None
                    ):
                        next_uc_draft_idx = max(
                            next_uc_draft_idx, rec["uc_draft_idx"] + 1
                        )
                        protocol.append_jsonl(config.uc_drafts_path, rec)
                    else:
                        if "draft_idx" in rec and isinstance(rec["draft_idx"], int):
                            next_draft_idx = max(
                                next_draft_idx, rec["draft_idx"] + 1
                            )
                        protocol.append_jsonl(config.drafts_path, rec)

        cursor = section["section_idx"] + 1
        state = protocol.ProgressState(
            pass_="A",
            unit="section",
            cursor=cursor,
            total=total,
            status="running",
            last_updated=_utc_now_iso(),
        )
        protocol.write_progress_atomic(config.progress_path, state)
        processed += 1

    state = protocol.ProgressState(
        pass_="A",
        unit="section",
        cursor=total,
        total=total,
        status="complete",
        last_updated=_utc_now_iso(),
    )
    protocol.write_progress_atomic(config.progress_path, state)
    return processed


def _count_existing_draft_idxs(drafts_path: Path) -> int:
    """Count records on disk that carry a draft_idx (i.e., real REQs,
    not skip/no_reqs markers). Used to compute the next draft_idx
    after a resume.
    """
    if not drafts_path.is_file():
        return 0
    count = 0
    for line in drafts_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and "draft_idx" in rec:
            count += 1
    return count


def _count_existing_uc_draft_idxs(uc_drafts_path: Optional[Path]) -> int:
    """Count UC records on disk. Symmetric to _count_existing_draft_idxs."""
    if uc_drafts_path is None or not uc_drafts_path.is_file():
        return 0
    count = 0
    for line in uc_drafts_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and "uc_draft_idx" in rec:
            count += 1
    return count


# v1.5.7 089x: every bin/*.py is safe + self-describing on no-args.
if __name__ == "__main__":
    try:
        from bin._purpose import print_purpose as _print_purpose
    except ImportError:
        from _purpose import print_purpose as _print_purpose  # type: ignore[no-redef]
    _print_purpose(
        name='skill_derivation.pass_a',
        summary=(
            "Skill-derivation pass A — initial requirements curation from "
            "Phase 1 exploration output. "
        ),
        role=(
            "Entry point for the skill-derivation `pass_a` stage; called "
            "by the skill-derivation orchestrator "
            "(bin/skill_derivation/__main__.py). "
        ),
        kind="library",
    )
    import sys as _sys
    _sys.exit(0)
