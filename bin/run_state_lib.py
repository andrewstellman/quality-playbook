"""Read/write/validate helpers for the v1.5.6 run-state event log.

This module implements the file-tool-driven "state IS the filesystem"
substrate originally specified in `docs/design/QPB_v1.5.5_Design.md`
(run-state schema + phase-boundary cross-validation rules) and
expanded in `docs/design/QPB_v1.5.6_Design.md` (Phase 1 13-check gate
per instruction 066, plus the post-fixup cross-surface coherence work
in instruction 070). The schema is documented at
`references/run_state_schema.md`. It is consumed by the playbook AI
(append events as phases progress) and by the orchestrator AI (read
events to drive resume semantics + cycle-level coordination).

Public API:

- ``Event`` — frozen dataclass wrapping a single event line.
- ``read_events`` — parse a ``run_state.jsonl`` file in order, raising on
  malformed JSON or missing required fields.
- ``last_in_progress_phase`` — return the phase number of the last
  ``phase_start`` not yet matched by a ``phase_end``.
- ``validate_phase_artifacts`` — apply the per-phase cross-validation
  rules from the schema doc against a ``quality/`` directory.
- ``validate_run_state_file`` — apply the format invariants from the
  schema doc (``_index`` first line, valid JSON per line, required
  fields, event-type whitelist, phase-marker uniqueness).
- ``write_progress_md`` — atomically rewrite ``quality/PROGRESS.md`` from
  an event list.
- ``append_event`` — append a single JSON event line to a
  ``run_state.jsonl`` file.

Pure stdlib. No third-party dependencies. Functions either return or
raise; there are no print statements and no logging integration.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# Schema-required core fields on every event line.
_REQUIRED_FIELDS: tuple[str, ...] = ("ts", "event")

# Per-schema-doc valid phase numbers.
_VALID_PHASES: frozenset[int] = frozenset({1, 2, 3, 4, 5, 6})

# v1.5.6 BUG-005 (codex bootstrap, 2026-05-08): Phase 1 validator
# enforces the full SKILL.md:1257-1273 entry gate (13 checks). The
# old single-regex check covered approximately 1 of those 13 — a
# 120-line placeholder with one ``## Open Exploration Findings``
# heading and no analytical content passed validation, recreating
# the v1.5.5-era "phase reported complete with shallow output"
# failure mode the validator was added to catch.

# Required exact section headings under EXPLORATION.md (checks 2-7).
_REQUIRED_PHASE1_HEADINGS: tuple[str, ...] = (
    "## Open Exploration Findings",
    "## Quality Risks",
    "## Pattern Applicability Matrix",
    "## Candidate Bugs for Phase 2",
    "## Gate Self-Check",
)
_PATTERN_DEEP_DIVE_PREFIX = "## Pattern Deep Dive — "
_MIN_PATTERN_DEEP_DIVES = 3  # check 5

# Per-section analytical minima (checks 9-13).
_MIN_OPEN_EXPLORATION_FINDINGS = 8         # check 9
_MIN_MULTILOCATION_FINDINGS = 3            # check 10
_MIN_FULL_PATTERNS = 3                     # check 11 lower bound
_MAX_FULL_PATTERNS = 4                     # check 11 upper bound
_MIN_MULTIFUNCTION_DEEP_DIVES = 2          # check 12
_MIN_CANDIDATE_BUGS_EXPLORATION_RISKS = 2  # check 13a
_MIN_CANDIDATE_BUGS_DEEP_DIVE = 1          # check 13b

# Regex catalog. Permissive on the file:line citation form so a wide
# variety of canonical formats parse correctly:
#   bin/run_playbook.py:1568-1574
#   bin/run_playbook.py:1583
#   .github/skills/quality_gate/quality_gate.py:118
_FILE_LINE_CITATION_RE = re.compile(
    r"\b([\w./\-]+\.[A-Za-z0-9]{1,8}):(\d+(?:[-,\d]*)?)"
)
# Numbered top-level entries in a section (e.g. ``1.``, ``2.`` at line
# start). Used to slice a section into per-entry sub-sections for
# checks 9, 10, and 13.
_NUMBERED_ENTRY_RE = re.compile(r"^(\d+)\.\s", re.MULTILINE)
# Backtick-quoted identifier-shaped tokens. Used by check 12 to detect
# multi-function pattern deep dives.
_IDENTIFIER_TOKEN_RE = re.compile(r"`([A-Za-z_][A-Za-z_0-9.]*)`")
# Pattern Applicability Matrix is a Markdown table. Each data row's
# decision column carries either ``FULL`` or ``SKIP``, optionally
# wrapped in backticks. Match a standalone ``FULL`` token (word boundary)
# inside a table cell — i.e., between pipes, optionally surrounded by
# backticks/whitespace.
_FULL_CELL_RE = re.compile(
    r"\|\s*`?(FULL)`?\s*\|"
)
# PROGRESS.md Phase 1 line.
_PROGRESS_PHASE1_DONE_RE = re.compile(
    r"^-\s*\[x\]\s*Phase\s*1\b", re.MULTILINE
)
# Stage label inside a Candidate Bugs entry.
_CANDIDATE_STAGE_RE = re.compile(
    r"^\s*-\s*Stage\s*:\s*(.+)$", re.MULTILINE | re.IGNORECASE
)

@dataclass(frozen=True)
class Event:
    """A single parsed event from a ``run_state.jsonl`` file.

    ``ts`` and ``event`` are split out as named fields because every
    event has them; ``fields`` carries everything else from the raw JSON
    object so callers can introspect type-specific keys without losing
    forward-compatibility for unknown fields.
    """

    ts: str
    event: str
    fields: dict[str, Any] = field(default_factory=dict)


def read_events(jsonl_path: Path) -> list[Event]:
    """Read a ``run_state.jsonl`` file and return events in file order.

    Raises:
        FileNotFoundError: ``jsonl_path`` does not exist.
        OSError: file cannot be read.
        ValueError: a line is not valid JSON, a line is not a JSON
            object, or a line is missing the required ``ts`` / ``event``
            fields.
    """
    if not jsonl_path.is_file():
        raise FileNotFoundError(f"run_state.jsonl not found: {jsonl_path}")

    text = jsonl_path.read_text(encoding="utf-8")
    events: list[Event] = []
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            # Skip blank lines defensively. The schema is append-only one
            # JSON object per line, but a trailing newline at EOF is
            # common and harmless.
            continue
        try:
            obj = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Malformed JSON on line {lineno} of {jsonl_path}: {exc.msg}"
            ) from exc
        if not isinstance(obj, dict):
            raise ValueError(
                f"Line {lineno} of {jsonl_path} is not a JSON object"
            )
        for required in _REQUIRED_FIELDS:
            if required not in obj:
                raise ValueError(
                    f"Line {lineno} of {jsonl_path} missing required "
                    f"field {required!r}"
                )
        ts = obj["ts"]
        ev = obj["event"]
        if not isinstance(ts, str) or not isinstance(ev, str):
            raise ValueError(
                f"Line {lineno} of {jsonl_path}: 'ts' and 'event' must "
                f"be strings"
            )
        extras = {k: v for k, v in obj.items() if k not in _REQUIRED_FIELDS}
        events.append(Event(ts=ts, event=ev, fields=extras))
    return events


def last_in_progress_phase(events: list[Event]) -> Optional[int]:
    """Return the phase number of the last ``phase_start`` without a
    matching ``phase_end``.

    Returns None if every ``phase_start`` has a corresponding
    ``phase_end`` (or if no phase has started yet). The scan walks the
    event list in order, tracking which phases are open; the result is
    the most-recently-started open phase.
    """
    open_phases: list[int] = []
    for event in events:
        if event.event == "phase_start":
            phase = event.fields.get("phase")
            if isinstance(phase, int):
                open_phases.append(phase)
        elif event.event == "phase_end":
            phase = event.fields.get("phase")
            if isinstance(phase, int) and phase in open_phases:
                # Remove the matching open phase. Schema invariant 6
                # forbids duplicates, so removing the first match is
                # correct in well-formed files.
                open_phases.remove(phase)
    if not open_phases:
        return None
    return open_phases[-1]


def _slice_h2_section(text: str, heading: str) -> str:
    """Return the body of the ``## <heading>`` section, ending at the
    next ``## `` heading (any sibling top-level section) or EOF.

    Returns an empty string when the heading is absent.
    """
    pattern = re.compile(
        rf"(?ms)^{re.escape(heading)}\s*$\n(.*?)(?=^## |\Z)"
    )
    m = pattern.search(text)
    return m.group(1) if m else ""


def _slice_h2_sections_by_prefix(text: str, prefix: str) -> list[tuple[str, str]]:
    """Return a list of ``(full_heading, body)`` for every ``## `` section
    whose heading starts with ``prefix``."""
    pattern = re.compile(
        rf"(?ms)^({re.escape(prefix)}.*?)\s*$\n(.*?)(?=^## |\Z)"
    )
    return [(m.group(1), m.group(2)) for m in pattern.finditer(text)]


def _slice_numbered_entries(section_body: str) -> list[str]:
    """Return per-entry sub-strings of a section that's structured as a
    numbered list (``1.``, ``2.``, ... at line start). Each returned
    string runs from one numbered entry to the next."""
    matches = list(_NUMBERED_ENTRY_RE.finditer(section_body))
    if not matches:
        return []
    entries: list[str] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(section_body)
        entries.append(section_body[start:end])
    return entries


def _distinct_file_line_citations(text: str) -> set[tuple[str, str]]:
    """Return the set of ``(file, line-or-range)`` citations in ``text``."""
    return {(m.group(1), m.group(2)) for m in _FILE_LINE_CITATION_RE.finditer(text)}


def _validate_phase1(quality_dir: Path) -> tuple[bool, str]:
    """v1.5.6 BUG-005 (codex bootstrap): enforce all 13 SKILL.md:1257-1273
    Phase 2 entry-gate checks.

    Aggregates failures into a multi-line message rather than
    short-circuiting on the first one. The ``(bool, str)`` interface
    is unchanged.
    """
    failures: list[str] = []

    path = quality_dir / "EXPLORATION.md"
    if not path.is_file():
        return (False, f"missing artifact: {path}")

    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    # Check 1: ≥120 lines.
    if len(lines) < 120:
        failures.append(
            f"Phase 1 gate: EXPLORATION.md has {len(lines)} lines; "
            f"required ≥120; see SKILL.md:1259."
        )

    # Checks 2-4, 6, 7: required exact headings (Open Exploration Findings,
    # Quality Risks, Pattern Applicability Matrix, Candidate Bugs for Phase 2,
    # Gate Self-Check). Pattern Deep Dive count is check 5 below.
    for heading in _REQUIRED_PHASE1_HEADINGS:
        if not re.search(rf"(?m)^{re.escape(heading)}\s*$", text):
            failures.append(
                f"Phase 1 gate: missing required heading '{heading}'; "
                f"see SKILL.md:1260-1265."
            )

    # Check 5: ≥3 Pattern Deep Dive sections.
    deep_dives = _slice_h2_sections_by_prefix(text, _PATTERN_DEEP_DIVE_PREFIX)
    if len(deep_dives) < _MIN_PATTERN_DEEP_DIVES:
        failures.append(
            f"Phase 1 gate: pattern deep dives — required ≥{_MIN_PATTERN_DEEP_DIVES} "
            f"'## Pattern Deep Dive — ' sections, found {len(deep_dives)}; "
            f"see SKILL.md:1263."
        )

    # Check 8: PROGRESS.md exists and Phase 1 is marked [x].
    progress_path = quality_dir / "PROGRESS.md"
    if not progress_path.is_file():
        failures.append(
            f"Phase 1 gate: missing artifact: {progress_path}; "
            f"see SKILL.md:1266."
        )
    else:
        progress_text = progress_path.read_text(encoding="utf-8", errors="ignore")
        if not _PROGRESS_PHASE1_DONE_RE.search(progress_text):
            failures.append(
                f"Phase 1 gate: PROGRESS.md does not have Phase 1 marked "
                f"as completed (expected '- [x] Phase 1 ...'); "
                f"see SKILL.md:1266."
            )

    # Check 9: ≥8 numbered findings with file:line citations under
    # ## Open Exploration Findings.
    open_findings_body = _slice_h2_section(text, "## Open Exploration Findings")
    finding_entries = _slice_numbered_entries(open_findings_body)
    findings_with_citations = [
        e for e in finding_entries if _FILE_LINE_CITATION_RE.search(e)
    ]
    if len(findings_with_citations) < _MIN_OPEN_EXPLORATION_FINDINGS:
        failures.append(
            f"Phase 1 gate: open exploration findings — required "
            f"≥{_MIN_OPEN_EXPLORATION_FINDINGS} with file:line citations, "
            f"found {len(findings_with_citations)}; see SKILL.md:1267."
        )

    # Check 10: ≥3 of those findings cite ≥2 distinct file:line locations.
    multilocation_findings = sum(
        1 for e in findings_with_citations
        if len(_distinct_file_line_citations(e)) >= 2
    )
    if multilocation_findings < _MIN_MULTILOCATION_FINDINGS:
        failures.append(
            f"Phase 1 gate: multi-location findings — required "
            f"≥{_MIN_MULTILOCATION_FINDINGS} findings tracing ≥2 distinct "
            f"file:line locations, found {multilocation_findings}; "
            f"see SKILL.md:1268."
        )

    # Check 11: Pattern Applicability Matrix has 3-4 FULL rows (inclusive).
    matrix_body = _slice_h2_section(text, "## Pattern Applicability Matrix")
    full_count = len(_FULL_CELL_RE.findall(matrix_body))
    if not (_MIN_FULL_PATTERNS <= full_count <= _MAX_FULL_PATTERNS):
        if full_count < _MIN_FULL_PATTERNS:
            qual = "too low — exploration didn't pick enough patterns"
        else:
            qual = "too high — exploration ran every pattern instead of selecting"
        failures.append(
            f"Phase 1 gate: pattern matrix FULL count — required "
            f"{_MIN_FULL_PATTERNS}-{_MAX_FULL_PATTERNS} (inclusive), "
            f"found {full_count} ({qual}); see SKILL.md:1269."
        )

    # Check 12: ≥2 Pattern Deep Dive sections cite ≥2 distinct identifier
    # tokens (multi-function traces).
    multifunction_deep_dives = 0
    for _heading, body in deep_dives:
        identifiers = {m.group(1) for m in _IDENTIFIER_TOKEN_RE.finditer(body)}
        # Fall-back signal: distinct file:line citations also count
        # toward the multi-function threshold (a deep dive that cites
        # bin/run_playbook.py:1560-1575 and bin/run_playbook.py:1583-1595
        # is tracing two distinct functions even if the body doesn't
        # backtick-quote their names).
        citations = _distinct_file_line_citations(body)
        if len(identifiers) >= 2 or len(citations) >= 2:
            multifunction_deep_dives += 1
    if multifunction_deep_dives < _MIN_MULTIFUNCTION_DEEP_DIVES:
        failures.append(
            f"Phase 1 gate: multi-function pattern deep dives — required "
            f"≥{_MIN_MULTIFUNCTION_DEEP_DIVES} sections citing ≥2 distinct "
            f"identifiers or file:line refs, found {multifunction_deep_dives}; "
            f"see SKILL.md:1270."
        )

    # Check 13: Candidate Bugs source mix — ≥2 from exploration/risks AND
    # ≥1 from pattern deep dive.
    candidate_body = _slice_h2_section(text, "## Candidate Bugs for Phase 2")
    candidate_entries = _slice_numbered_entries(candidate_body)
    n_exploration_risks = 0
    n_deep_dive = 0
    # v1.5.6 fix-up 067 PS-4: track per-entry stage labels so the
    # failure message can name which entries are missing or
    # malformed Stage: lines, not just the aggregate count.
    per_entry_stages: list[tuple[int, str]] = []
    for idx, entry in enumerate(candidate_entries, start=1):
        stage_match = _CANDIDATE_STAGE_RE.search(entry)
        if not stage_match:
            per_entry_stages.append((idx, "<missing Stage: line>"))
            continue
        stage = stage_match.group(1).lower()
        per_entry_stages.append((idx, stage_match.group(1).strip()))
        from_exp_or_risks = (
            "open exploration" in stage
            or "quality risks" in stage
            or "risks" in stage
        )
        # Treat anything with content beyond "open exploration" / "quality
        # risks" / "risks" tokens as deep-dive-sourced. Combo entries
        # like "open exploration + Pattern Name" count toward both
        # buckets.
        residual = stage
        for token in ("open exploration", "quality risks", "risks", "+", ","):
            residual = residual.replace(token, " ")
        from_deep_dive = bool(residual.strip())
        if from_exp_or_risks:
            n_exploration_risks += 1
        if from_deep_dive:
            n_deep_dive += 1
    if (
        n_exploration_risks < _MIN_CANDIDATE_BUGS_EXPLORATION_RISKS
        or n_deep_dive < _MIN_CANDIDATE_BUGS_DEEP_DIVE
    ):
        per_entry_lines = "\n".join(
            f"  Entry {idx}: {stage}" for idx, stage in per_entry_stages
        )
        if not per_entry_lines:
            per_entry_lines = "  (no candidate-bug entries detected)"
        failures.append(
            f"Phase 1 gate: candidate bugs source mix — required "
            f"≥{_MIN_CANDIDATE_BUGS_EXPLORATION_RISKS} from exploration/risks "
            f"AND ≥{_MIN_CANDIDATE_BUGS_DEEP_DIVE} from pattern deep dive, "
            f"found {n_exploration_risks} from exploration/risks AND "
            f"{n_deep_dive} from pattern deep dive; see SKILL.md:1271. "
            f"Per-entry stages:\n{per_entry_lines}"
        )

    if failures:
        return (False, "\n".join(failures))
    return (True, "")


def validate_phase_artifacts(quality_dir: Path, phase: int) -> tuple[bool, str]:
    """Verify that the per-phase expected artifacts are present and
    well-formed under ``quality_dir``.

    Implements the cross-validation rules from
    ``references/run_state_schema.md`` (the "Cross-validation rules"
    table). On success returns ``(True, "")``; on failure returns
    ``(False, reason)`` where ``reason`` is a human-readable string
    suitable for an ``error`` event ``message`` field.
    """
    if phase not in _VALID_PHASES:
        return (False, f"phase {phase!r} is not in 1..6")

    if phase == 1:
        return _validate_phase1(quality_dir)

    if phase == 2:
        # v1.5.6 BUG-014 (Conclusion C from instruction-019 investigation):
        # the v1.5.5 design's triage model (EXPLORATION_MERGED.md,
        # triage.md) was never adopted by the shipped SKILL.md /
        # orchestrator_protocol.md / agent files — they document Phase 2
        # as Generate, producing a 9-markdown + 2-manifest + 1
        # functional-test contract.
        #
        # v1.5.6 fix-up 071 BUG-003: extended to enforce the JSON
        # manifests SKILL.md:1312-1322 and phase_prompts/phase2.md
        # declare as Phase 2 outputs (requirements_manifest.json,
        # use_cases_manifest.json). Pre-fix the validator silently
        # tolerated a Phase 2 with the markdown deliverables but no
        # manifests, deferring the failure to the Phase 6 final gate
        # — the same UX failure mode instruction 066 closed at
        # Phase 1. Same logic applies here: phase boundaries should
        # reject incomplete artifact sets at the boundary, not defer.
        required_fixed = (
            "REQUIREMENTS.md",
            "QUALITY.md",
            "CONTRACTS.md",
            "COVERAGE_MATRIX.md",
            "COMPLETENESS_REPORT.md",
            "RUN_CODE_REVIEW.md",
            "RUN_INTEGRATION_TESTS.md",
            "RUN_SPEC_AUDIT.md",
            "RUN_TDD_TESTS.md",
            "requirements_manifest.json",
            "use_cases_manifest.json",
        )
        for name in required_fixed:
            candidate = quality_dir / name
            if not candidate.is_file():
                return (False, f"missing artifact: {candidate}")
            if candidate.stat().st_size == 0:
                return (False, f"{candidate} is empty")
        # test_functional.<ext> — the extension varies by the target's
        # primary language (e.g. .py, .js, .go, .rb), so we glob for
        # any test_functional.* file. At least one must exist and be
        # non-empty; multiple is fine (a polyglot project may emit
        # several).
        functional_tests = sorted(quality_dir.glob("test_functional.*"))
        if not functional_tests:
            return (
                False,
                f"missing artifact: {quality_dir}/test_functional.<ext> "
                f"(no test_functional.* file found)",
            )
        if not any(p.stat().st_size > 0 for p in functional_tests):
            return (
                False,
                f"all test_functional.* files under {quality_dir} are empty",
            )
        return (True, "")

    if phase == 3:
        # v1.5.6 cluster B: shipped Phase 3 = Code Review per
        # references/orchestrator_protocol.md (cluster 3 fixed prose)
        # and SKILL.md. Required artifact: quality/code_reviews/
        # contains at least one review file. The pre-cluster-B check
        # for RUN_CODE_REVIEW.md was the v1.5.5 design's Phase 2-side
        # mapping — RUN_CODE_REVIEW.md is actually a Phase 2 Generate
        # output (the protocol document), not the Phase 3 review
        # results. The reviews live under code_reviews/.
        code_reviews_dir = quality_dir / "code_reviews"
        if not code_reviews_dir.is_dir():
            return (
                False,
                f"missing artifact: {code_reviews_dir}/ "
                f"(Phase 3 must produce at least one review file in "
                f"code_reviews/)",
            )
        review_files = [p for p in code_reviews_dir.glob("*") if p.is_file()]
        if not review_files:
            return (
                False,
                f"{code_reviews_dir}/ exists but contains no review "
                f"files (Phase 3 must produce at least one)",
            )
        # Conditional: if BUGS.md exists with confirmed bugs, every
        # confirmed bug must have a regression-test patch under
        # quality/patches/. The orchestrator_protocol.md contract
        # says "if bugs were confirmed", so we only enforce when
        # BUGS.md has at least one ### BUG- heading.
        #
        # v1.5.6 fix-up 071 BUG-004: enumerate the BUG IDs and require
        # a per-bug regression-test patch (one BUG-NNN-regression-test.patch
        # per BUG-NNN). Pre-fix the check only verified that AT LEAST
        # ONE regression-test patch existed — a Phase 3 with N bugs
        # and 1 patch passed the validator while the missing N-1
        # patches were left for the final gate to catch.
        bugs_md = quality_dir / "BUGS.md"
        if bugs_md.is_file():
            bugs_text = bugs_md.read_text(encoding="utf-8", errors="ignore")
            # Match archive_lib._BUG_HEADING_PATTERN's titled-and-bare
            # form so future BUG-NNN-suffix forms (e.g., BUG-001-fix-2)
            # are handled consistently.
            bug_id_re = re.compile(
                r"^###\s+BUG-([A-Za-z0-9][A-Za-z0-9\-]*)(?::\s+.+)?\s*$",
                re.MULTILINE,
            )
            bug_ids_p3 = sorted({m.group(1) for m in bug_id_re.finditer(bugs_text)})
            if bug_ids_p3:
                patches_dir = quality_dir / "patches"
                if not patches_dir.is_dir():
                    return (
                        False,
                        f"BUGS.md has confirmed BUG entries but "
                        f"{patches_dir}/ is missing (every confirmed "
                        f"bug needs a regression-test patch)",
                    )
                missing_patches: list[str] = []
                for bug_id in bug_ids_p3:
                    patch_path = patches_dir / f"BUG-{bug_id}-regression-test.patch"
                    if not patch_path.is_file():
                        missing_patches.append(f"BUG-{bug_id}")
                if missing_patches:
                    return (
                        False,
                        f"missing regression-test patches in "
                        f"{patches_dir}/ for: {', '.join(missing_patches)} "
                        f"(every confirmed BUG needs a "
                        f"BUG-NNN-regression-test.patch)",
                    )
        return (True, "")

    if phase == 4:
        # v1.5.6 cluster B: shipped Phase 4 = Spec Audit per
        # references/orchestrator_protocol.md and SKILL.md.
        # Required artifact: quality/spec_audits/ contains at least
        # one triage file AND at least one individual auditor file.
        # Mechanical limitation: from filenames alone we can't always
        # tell a triage file from an auditor file — both are typically
        # YYYY-MM-DD-<name>.md. The orchestrator_protocol.md contract
        # uses the convention "...-triage.md" for the triage file and
        # "...-auditor-N.md" for the per-auditor files, so we look
        # for both name patterns. Falling back to ≥2 files when
        # neither pattern matches keeps backward-compat with older
        # bootstrap runs that used different naming conventions; the
        # quality_gate.py at Phase 6 enforces deeper conformance.
        spec_audits_dir = quality_dir / "spec_audits"
        if not spec_audits_dir.is_dir():
            return (
                False,
                f"missing artifact: {spec_audits_dir}/ "
                f"(Phase 4 must produce at least one triage file "
                f"and at least one auditor file)",
            )
        spec_files = [p for p in spec_audits_dir.glob("*.md") if p.is_file()]
        if not spec_files:
            return (
                False,
                f"{spec_audits_dir}/ exists but contains no .md files "
                f"(Phase 4 must produce at least one triage + one "
                f"auditor file)",
            )
        triage_files = [p for p in spec_files if "triage" in p.name.lower()]
        auditor_files = [p for p in spec_files if "auditor" in p.name.lower()]
        # If neither naming convention is used, fall back to the
        # weaker "≥2 files" check. orchestrator_protocol.md mandates
        # both file types; quality_gate.py at Phase 6 enforces deeper
        # conformance.
        if not triage_files and not auditor_files:
            if len(spec_files) < 2:
                return (
                    False,
                    f"{spec_audits_dir}/ has fewer than 2 .md files "
                    f"(Phase 4 must produce at least one triage + "
                    f"one auditor file). Use the "
                    f"YYYY-MM-DD-triage.md / YYYY-MM-DD-auditor-N.md "
                    f"naming convention so the validator can recognize "
                    f"them.",
                )
        elif not triage_files:
            return (
                False,
                f"{spec_audits_dir}/ contains auditor files but no "
                f"triage file (look for *-triage.md)",
            )
        elif not auditor_files:
            return (
                False,
                f"{spec_audits_dir}/ contains a triage file but no "
                f"auditor files (look for *-auditor-*.md)",
            )
        # v1.5.6 fix-up 071 BUG-005: Phase 4 also produces executable
        # triage probes + a semantic-check artifact. Required artifact
        # presence (not content) — Tier-3-only runs still produce an
        # empty-but-valid citation_semantic_check.json. Added AFTER
        # the existing flexible triage/auditor file detection so the
        # backward-compat naming-convention surface is preserved.
        probes_path = spec_audits_dir / "triage_probes.sh"
        if not probes_path.is_file():
            return (
                False,
                f"missing artifact: {probes_path} "
                f"(Phase 4 must produce executable triage probes)",
            )
        semantic_path = quality_dir / "citation_semantic_check.json"
        if not semantic_path.is_file():
            return (
                False,
                f"missing artifact: {semantic_path} "
                f"(Phase 4 must produce a semantic-check artifact, "
                f"even if empty for Tier-3-only runs)",
            )
        return (True, "")

    if phase == 5:
        # v1.5.6 cluster B: shipped Phase 5 = Reconciliation per
        # references/orchestrator_protocol.md and SKILL.md. Required
        # artifacts (conditional on confirmed bugs):
        #   - quality/results/tdd-results.json exists.
        #   - quality/writeups/BUG-NNN.md exists per confirmed bug.
        #   - quality/results/BUG-NNN.red.log exists per confirmed bug.
        # The pre-cluster-B Phase 5 check (quality-gate.log) was the
        # v1.5.5 design's Phase 6-side mapping; that artifact is now
        # tracked at Phase 6 instead.
        bugs_md = quality_dir / "BUGS.md"
        if not bugs_md.is_file():
            # No BUGS.md → nothing for Phase 5 to reconcile. This
            # matches the contract's "if bugs were confirmed" caveat.
            return (True, "")
        bugs_text = bugs_md.read_text(encoding="utf-8", errors="ignore")
        # v1.5.6 fix-up 071 BUG-006: match archive_lib._BUG_HEADING_PATTERN's
        # titled-and-bare form for consistency (also handles future
        # hyphenated suffix BUG IDs like BUG-001-fix-2).
        bug_id_re = re.compile(
            r"^###\s+BUG-([A-Za-z0-9][A-Za-z0-9\-]*)(?::\s+.+)?\s*$",
            re.MULTILINE,
        )
        bug_ids = sorted({m.group(1) for m in bug_id_re.finditer(bugs_text)})
        if not bug_ids:
            # BUGS.md exists but contains no confirmed bugs.
            return (True, "")
        # tdd-results.json — required at Phase 5 when bugs are confirmed.
        tdd_path = quality_dir / "results" / "tdd-results.json"
        if not tdd_path.is_file():
            return (False, f"missing artifact: {tdd_path}")
        if tdd_path.stat().st_size == 0:
            return (False, f"{tdd_path} is empty")
        # Per-bug writeups + red-phase logs — required at Phase 5
        # for every confirmed bug.
        patches_dir = quality_dir / "patches"
        results_dir = quality_dir / "results"
        missing_green: list[str] = []
        for bug_id in bug_ids:
            writeup = quality_dir / "writeups" / f"BUG-{bug_id}.md"
            if not writeup.is_file():
                return (
                    False,
                    f"missing writeup for BUG-{bug_id}: {writeup}",
                )
            red_log = results_dir / f"BUG-{bug_id}.red.log"
            if not red_log.is_file():
                return (
                    False,
                    f"missing red-phase log for BUG-{bug_id}: {red_log}",
                )
            # v1.5.6 fix-up 071 BUG-006: green-log check per fix-bearing
            # bug. If a BUG-NNN-fix.patch exists, the matching
            # BUG-NNN.green.log MUST also exist (red+green receipts
            # for the TDD reconciliation cycle). Red-only is acceptable
            # for code-review-only bugs that don't propose a fix patch.
            fix_patch = patches_dir / f"BUG-{bug_id}-fix.patch"
            if fix_patch.is_file():
                green_log = results_dir / f"BUG-{bug_id}.green.log"
                if not green_log.is_file():
                    missing_green.append(f"BUG-{bug_id}")
        if missing_green:
            return (
                False,
                f"missing green-phase logs for fix-bearing bugs: "
                f"{', '.join(missing_green)} "
                f"(Phase 5 reconciliation requires red AND green "
                f"receipts when a fix patch exists)",
            )
        return (True, "")

    # phase == 6
    # v1.5.6 cluster B: shipped Phase 6 = Verify per
    # references/orchestrator_protocol.md and SKILL.md. Required
    # artifacts: quality/results/quality-gate.log exists non-empty;
    # quality/PROGRESS.md marks Phase 6 complete with a Terminal
    # Gate Verification section. The pre-cluster-B Phase 6 check
    # (BUGS.md + INDEX.md) was the v1.5.5 design's mapping —
    # BUGS.md is a Phase 3 output and INDEX.md was never adopted
    # in the shipped contract.
    gate_log = quality_dir / "results" / "quality-gate.log"
    if not gate_log.is_file():
        return (False, f"missing artifact: {gate_log}")
    if gate_log.stat().st_size == 0:
        return (False, f"{gate_log} is empty")
    progress = quality_dir / "PROGRESS.md"
    if not progress.is_file():
        return (False, f"missing artifact: {progress}")
    progress_text = progress.read_text(encoding="utf-8", errors="ignore")
    if "Terminal Gate Verification" not in progress_text:
        return (
            False,
            f"{progress} does not contain a 'Terminal Gate Verification' "
            f"section (required at Phase 6 completion)",
        )
    return (True, "")


def validate_no_source_edits(
    target_dir: Path,
    allowed_prefixes: tuple[str, ...] = ("quality/",),
) -> tuple[bool, list[str]]:
    """Verify that no files outside the allowed prefixes were modified
    during the run.

    The Codex bootstrap run on 2026-05-02 went off-rails in Phase 5,
    editing five source files outside ``quality/`` before being killed.
    Phase 5's job is to write proposed-fix patches to
    ``quality/patches/<BUG-NNN>-fix.patch`` — never to apply them. This
    helper is the run-end post-condition that catches any drift: it
    shells out to ``git status --porcelain`` in ``target_dir`` and
    flags any tracked or untracked path whose final destination is not
    under one of ``allowed_prefixes``.

    Returns:
        ``(True, [])`` if every change is inside an allowed prefix (or
        ``target_dir`` is not a git repo, or has no changes at all).
        ``(False, [violations])`` if any non-allowed paths are dirty;
        ``violations`` lists the offending repo-relative paths in the
        order ``git status`` reports them, deduplicated.

    Notes:
        - Renames count by their new path (``R  old -> new`` flags
          ``new`` only — what matters is where content lands, not where
          it came from). In ``-z`` output the destination appears
          first in the entry; the source is the next NUL-delimited
          field. The parser counts the destination only.
        - Untracked files (``?? path``) count as violations if they're
          outside the allowed prefixes; Phase 5 producing a stray
          ``patch.rej`` at the repo root is the kind of drift this
          catches.
        - The default allowed prefix is ``quality/``. Callers can pass
          additional prefixes (e.g. operator-allowed scratch dirs) via
          ``allowed_prefixes``; entries should be repo-relative paths
          ending in ``/``.

    Limitations (deliberate trade-offs — caller is responsible for
    defense-in-depth if these matter):

        - **Gitignored files silently pass.** ``git status --porcelain``
          honors ``.gitignore``, so a Phase 5 that drops a file matched
          by an ignore rule (e.g. ``*.log``, ``*.rej`` at the repo
          root) won't be flagged. We do NOT pass
          ``--ignored=traditional`` because the QPB repo's own
          ``.gitignore`` excludes ``repos/`` and other large trees,
          which would flood the violations list with non-actionable
          entries during self-audit. If a caller needs to catch
          ignored-file drift, run ``git ls-files --others --ignored
          --exclude-standard`` separately and treat results outside
          allowed prefixes as violations.
        - **Silent pass when ``git`` is missing or ``target_dir`` is
          not a git repo.** In both cases the helper returns
          ``(True, [])`` — the contract is "no source tree to protect"
          rather than "verified clean." For QPB self-audit this should
          be impossible (QPB is always a git repo and ``git`` is
          always installed), so the silent pass is acceptable for the
          intended use case. Callers that need to distinguish
          "verified clean" from "could not verify" should check
          ``(target_dir / '.git').exists()`` and ``shutil.which('git')``
          before calling.
        - **Non-UTF-8 filenames will raise UnicodeDecodeError.**
          ``subprocess.run(text=True)`` decodes ``git status`` output
          via the system encoding. Filenames containing latin-1 bytes
          (rare but possible on archived corpora) will crash the
          helper rather than be flagged. Acceptable for the QPB
          self-audit case; callers operating on arbitrary archives
          should wrap the call.
    """
    import subprocess

    if not target_dir.is_dir():
        raise FileNotFoundError(f"target_dir does not exist: {target_dir}")

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "-z"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        # git not installed — treat as "no source tree to protect."
        return (True, [])

    if result.returncode != 0:
        # Most likely "not a git repository" — no source tree to
        # protect. stderr is preserved for debugging via the run-state
        # error event the caller writes.
        return (True, [])

    # -z output is NUL-terminated entries; renames pack two paths into
    # one entry separated by a NUL (XY old\0new\0), so we walk the
    # raw stream rather than splitlines().
    raw = result.stdout
    if not raw:
        return (True, [])

    violations: list[str] = []
    seen: set[str] = set()
    parts = raw.split("\x00")
    i = 0
    while i < len(parts):
        entry = parts[i]
        if not entry:
            i += 1
            continue
        # Each entry is "XY path"; X and Y are status chars, then space,
        # then the path. For renames/copies (X in {R, C}), the next NUL-
        # delimited field is the OLD path. The destination is what we
        # care about.
        if len(entry) < 3:
            i += 1
            continue
        status = entry[:2]
        path = entry[3:]
        is_rename_or_copy = status[0] in ("R", "C") or status[1] in ("R", "C")
        if is_rename_or_copy and i + 1 < len(parts):
            # path is the new (destination); the next part is the old
            # source — skip it for the violation check.
            i += 2
        else:
            i += 1
        if not _path_under_allowed_prefix(path, allowed_prefixes):
            if path not in seen:
                violations.append(path)
                seen.add(path)

    return (not violations, violations)


def _path_under_allowed_prefix(
    path: str, allowed_prefixes: tuple[str, ...]
) -> bool:
    """Return True iff ``path`` (repo-relative, slash-separated) starts
    with any of ``allowed_prefixes``. A trailing-slash convention is
    enforced on the prefixes so e.g. ``quality_other/`` does not match
    ``quality/``."""
    for prefix in allowed_prefixes:
        # Be strict: caller-supplied prefixes are expected to end in "/"
        # but we tolerate the missing slash for ergonomics.
        normalized = prefix if prefix.endswith("/") else prefix + "/"
        if path.startswith(normalized):
            return True
    return False


def validate_run_state_file(
    jsonl_path: Path,
) -> tuple[bool, list[str]]:
    """Apply the schema-doc format invariants to a ``run_state.jsonl``
    file.

    Returns ``(ok, violations)``. ``ok`` is True iff ``violations`` is
    empty. ``violations`` is a list of human-readable strings, one per
    finding, suitable for either logging or for surfacing as a series of
    findings in a Council review.

    Invariants checked (per schema doc §"Format invariants"):

    1. ``_index`` is line 1.
    2. Every line is valid JSON (one object per line).
    3. Every event has ``ts`` and ``event`` fields.
    4. Every ``event`` value appears in ``_index.event_types``.
    5. (Append-only is not statically checkable; not validated here.)
    6. ``phase_start`` and ``phase_end`` events for a given phase appear
       at most once per run.
    7. (``run_start`` second / ``run_end`` last is checked when both
       events are present.)
    """
    violations: list[str] = []

    if not jsonl_path.is_file():
        violations.append(f"file not found: {jsonl_path}")
        return (False, violations)

    text = jsonl_path.read_text(encoding="utf-8")
    raw_lines = [line for line in text.splitlines() if line.strip()]
    if not raw_lines:
        violations.append(f"{jsonl_path} is empty")
        return (False, violations)

    parsed: list[tuple[int, dict[str, Any]]] = []
    for lineno, raw_line in enumerate(raw_lines, start=1):
        try:
            obj = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            violations.append(
                f"line {lineno}: malformed JSON ({exc.msg})"
            )
            continue
        if not isinstance(obj, dict):
            violations.append(f"line {lineno}: not a JSON object")
            continue
        for required in _REQUIRED_FIELDS:
            if required not in obj:
                violations.append(
                    f"line {lineno}: missing required field "
                    f"{required!r}"
                )
        parsed.append((lineno, obj))

    if not parsed:
        return (False, violations)

    # Invariant 1: _index is line 1.
    first_lineno, first_obj = parsed[0]
    if first_obj.get("event") != "_index":
        violations.append(
            f"line {first_lineno}: first event must be '_index', "
            f"got {first_obj.get('event')!r}"
        )

    # Pull the event-type whitelist from _index for invariant 4. If the
    # first event is not _index or has no event_types, the whitelist is
    # empty and every subsequent event will fail invariant 4 — that is
    # the correct behaviour because the file is structurally broken.
    declared_types: set[str] = set()
    if first_obj.get("event") == "_index":
        types = first_obj.get("event_types")
        if isinstance(types, list):
            declared_types = {t for t in types if isinstance(t, str)}
        else:
            violations.append(
                f"line {first_lineno}: _index.event_types is missing "
                f"or not an array"
            )

    # Invariants 4 and 6.
    seen_phase_starts: set[int] = set()
    seen_phase_ends: set[int] = set()
    for lineno, obj in parsed:
        ev = obj.get("event")
        if not isinstance(ev, str):
            continue
        # C-4 (Council 2026-05-08): pre-fix this had `and declared_types`,
        # which short-circuited the whitelist check when declared_types
        # was empty. The comment above (`every subsequent event will
        # fail invariant 4`) documented the intent, but the code
        # silently SKIPPED the check. A malformed run_state.jsonl with
        # `_index.event_types: []` passed invariant 4 for every event.
        # The check now runs unconditionally — empty whitelist correctly
        # fails every subsequent non-_index event.
        if ev != "_index" and ev not in declared_types:
            violations.append(
                f"line {lineno}: event {ev!r} is not declared in "
                f"_index.event_types"
            )
        if ev == "phase_start":
            phase = obj.get("phase")
            if isinstance(phase, int):
                if phase in seen_phase_starts:
                    violations.append(
                        f"line {lineno}: duplicate phase_start for "
                        f"phase={phase}"
                    )
                seen_phase_starts.add(phase)
        elif ev == "phase_end":
            phase = obj.get("phase")
            if isinstance(phase, int):
                if phase in seen_phase_ends:
                    violations.append(
                        f"line {lineno}: duplicate phase_end for "
                        f"phase={phase}"
                    )
                seen_phase_ends.add(phase)

    # Invariant 7: when both run_start and run_end are present, check
    # their positional convention.
    run_start_idx = None
    run_end_idx = None
    for idx, (_, obj) in enumerate(parsed):
        ev = obj.get("event")
        if ev == "run_start" and run_start_idx is None:
            run_start_idx = idx
        elif ev == "run_end":
            run_end_idx = idx  # last wins
    if run_start_idx is not None and run_start_idx != 1:
        violations.append(
            f"run_start should appear on line 2 (after _index); "
            f"found at position {run_start_idx + 1}"
        )
    if run_end_idx is not None and run_end_idx != len(parsed) - 1:
        violations.append(
            f"run_end should be the last event; found at position "
            f"{run_end_idx + 1} of {len(parsed)}"
        )

    return (len(violations) == 0, violations)


def write_progress_md(
    quality_dir: Path,
    events: list[Event],
    current_phase: Optional[int],
) -> None:
    """Atomically rewrite ``quality/PROGRESS.md`` from the events log.

    Layout follows ``references/run_state_schema.md`` §"PROGRESS.md
    format": header (started/benchmark/lever/runner/playbook_version),
    phase checklist with summary stats per complete phase and an
    ``(in progress, started <ts>)`` annotation on the current phase, a
    "Recent events" tail of the last 10 events, and an "Artifacts
    produced" list.

    Atomic via tempfile-then-rename in the same directory; readers will
    only ever see a fully-written PROGRESS.md.
    """
    quality_dir.mkdir(parents=True, exist_ok=True)
    target = quality_dir / "PROGRESS.md"

    index_event = next(
        (e for e in events if e.event == "_index"), None
    )
    run_start_event = next(
        (e for e in events if e.event == "run_start"), None
    )

    started_ts = ""
    benchmark = ""
    lever_state = ""
    runner = ""
    playbook_version = ""
    if index_event is not None:
        started_ts = index_event.fields.get("started_at") or index_event.ts
        benchmark = str(index_event.fields.get("benchmark") or "")
        lever_state = str(index_event.fields.get("lever_state") or "")
    if run_start_event is not None:
        runner = str(run_start_event.fields.get("runner") or "")
        playbook_version = str(
            run_start_event.fields.get("playbook_version") or ""
        )

    lines: list[str] = []
    lines.append("# QPB Run Progress")
    lines.append("")
    lines.append(
        f"**Started:** {started_ts}  **Benchmark:** {benchmark}  "
        f"**Lever:** {lever_state}"
    )
    lines.append(
        f"**Runner:** {runner}  **Playbook version:** {playbook_version}"
    )
    lines.append("")
    lines.append("## Phases")
    lines.append("")

    phase_starts: dict[int, Event] = {}
    phase_ends: dict[int, Event] = {}
    for event in events:
        phase = event.fields.get("phase")
        if not isinstance(phase, int):
            continue
        if event.event == "phase_start" and phase not in phase_starts:
            phase_starts[phase] = event
        elif event.event == "phase_end":
            phase_ends[phase] = event

    # v1.5.6 cluster B: phase_names matches the shipped pipeline
    # documented in SKILL.md and references/orchestrator_protocol.md
    # (Phase 1=Explore / 2=Generate / 3=Code Review / 4=Spec Audit /
    # 5=Reconciliation / 6=Verify). The pre-cluster-B labels were
    # the v1.5.5 design's never-shipped Triage-model names — same
    # drift class as BUG-014 (validator) and BUG-009/019 (orchestrator
    # docs), now reconciled.
    phase_names = {
        1: "Explore",
        2: "Generate",
        3: "Code Review",
        4: "Spec Audit",
        5: "Reconciliation",
        6: "Verify",
    }

    for phase in range(1, 7):
        name = phase_names[phase]
        if phase in phase_ends:
            end_event = phase_ends[phase]
            duration = end_event.fields.get("duration_seconds")
            key_counts = end_event.fields.get("key_counts") or {}
            summary_parts: list[str] = []
            if duration is not None:
                summary_parts.append(_format_duration(duration))
            if isinstance(key_counts, dict):
                for k, v in key_counts.items():
                    summary_parts.append(f"{k}={v}")
            summary = ", ".join(summary_parts)
            if summary:
                lines.append(
                    f"- [x] Phase {phase} — {name} ({summary})"
                )
            else:
                lines.append(f"- [x] Phase {phase} — {name}")
        elif current_phase is not None and phase == current_phase:
            start_event = phase_starts.get(phase)
            started_at = (
                start_event.ts if start_event is not None else ""
            )
            lines.append(
                f"- [ ] Phase {phase} — {name} "
                f"*(in progress, started {started_at})*"
            )
        else:
            lines.append(f"- [ ] Phase {phase} — {name}")

    lines.append("")
    lines.append("## Recent events (last 10)")
    lines.append("")
    recent = events[-10:] if len(events) > 10 else list(events)
    for event in reversed(recent):
        # Render in reverse chronological order to match the schema
        # doc's example (most recent first).
        lines.append(f"- {event.ts} — {_summarize_event(event)}")
    lines.append("")
    lines.append("## Artifacts produced")
    lines.append("")
    seen_paths: set[str] = set()
    artifacts: list[tuple[str, Optional[int]]] = []
    for event in events:
        if event.event != "artifact_written":
            continue
        rel = event.fields.get("relative_path")
        if not isinstance(rel, str) or rel in seen_paths:
            continue
        seen_paths.add(rel)
        size = event.fields.get("byte_size")
        artifacts.append(
            (rel, size if isinstance(size, int) else None)
        )
    for rel, size in artifacts:
        if size is not None:
            lines.append(f"- {rel} ({size:,} bytes)")
        else:
            lines.append(f"- {rel}")

    if not artifacts:
        # Keep the section non-empty so downstream readers can rely on
        # it always existing. A bullet placeholder is friendlier than a
        # blank section.
        lines.append("- (none yet)")

    output = "\n".join(lines) + "\n"
    _atomic_write(target, output)


def append_event(jsonl_path: Path, event_obj: dict) -> None:
    """Append one event as a single JSON line.

    Validates that ``ts`` and ``event`` are present (and strings). Does
    NOT validate against ``_index.event_types`` — that is the caller's
    responsibility, and conflating the two would couple this helper to
    the file's prior state.

    Raises:
        ValueError: ``event_obj`` is missing ``ts`` or ``event``, or
            either is not a string.
    """
    if not isinstance(event_obj, dict):
        raise ValueError("event_obj must be a dict")
    for required in _REQUIRED_FIELDS:
        if required not in event_obj:
            raise ValueError(
                f"event_obj missing required field {required!r}"
            )
    if not isinstance(event_obj["ts"], str):
        raise ValueError("event_obj['ts'] must be a string")
    if not isinstance(event_obj["event"], str):
        raise ValueError("event_obj['event'] must be a string")
    line = json.dumps(event_obj, sort_keys=False, separators=(",", ":"))
    if "\n" in line:
        # Defensive: separators=(',', ':') already prevents embedded
        # newlines from json.dumps itself, but a caller could have
        # passed a string containing a newline that we'd encode as the
        # escape sequence ``\n``. That's safe; this guard is here to
        # make the intent explicit.
        raise ValueError(
            "encoded event line contains a literal newline; refusing "
            "to corrupt JSONL framing"
        )
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


# --- Internal helpers -------------------------------------------------------


def _format_duration(seconds: float) -> str:
    """Render a wall-clock duration as ``MM:SS`` or ``HH:MM:SS``."""
    try:
        total = int(round(float(seconds)))
    except (TypeError, ValueError):
        return f"{seconds}s"
    if total < 0:
        total = 0
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _summarize_event(event: Event) -> str:
    """Render one event for the PROGRESS.md "Recent events" section."""
    if event.event == "phase_start":
        phase = event.fields.get("phase")
        return f"phase_start phase={phase}"
    if event.event == "phase_end":
        phase = event.fields.get("phase")
        counts = event.fields.get("key_counts") or {}
        if isinstance(counts, dict) and counts:
            extras = " ".join(f"{k}={v}" for k, v in counts.items())
            return f"phase_end phase={phase} {extras}"
        return f"phase_end phase={phase}"
    if event.event == "artifact_written":
        rel = event.fields.get("relative_path", "?")
        return f"artifact_written {rel}"
    if event.event == "run_start":
        runner = event.fields.get("runner", "?")
        return f"run_start runner={runner}"
    if event.event == "run_end":
        status = event.fields.get("status", "?")
        return f"run_end status={status}"
    return event.event


def _atomic_write(target: Path, content: str) -> None:
    """Write ``content`` to ``target`` atomically (tempfile + rename).

    Tempfile is created in the same directory so ``os.replace`` is a
    same-filesystem rename and therefore atomic per POSIX.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path_str = tempfile.mkstemp(
        prefix=".progress.",
        suffix=".md.tmp",
        dir=str(target.parent),
    )
    temp_path = Path(temp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temp_path, target)
    except BaseException:
        # Clean up the tempfile if anything went wrong before the
        # rename. After a successful rename, temp_path no longer exists.
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        raise
