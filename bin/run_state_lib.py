"""Read/write/validate helpers for the v1.5.5 run-state event log.

This module implements the file-tool-driven "state IS the filesystem"
substrate described in `docs/design/QPB_v1.5.5_Design.md` and specified
in `references/run_state_schema.md`. It is consumed by the playbook AI
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

# Regex used by Phase 1's artifact validator to detect a finding section
# header. Matches:
#   - ``## Finding ...`` (or ``## Findings ...`` — substring match)
#   - ``## Open Exploration Findings`` (the SKILL.md-prescribed exact
#     heading at SKILL.md:1133, 1209, 1260)
#   - ``## N.`` for any digit-prefixed numbered heading
# v1.5.6 BUG-004: pre-fix the regex rejected ``## Open Exploration Findings``,
# the heading SKILL.md tells Phase 1 to write. EXPLORATION.md files
# produced by SKILL-conformant runs were marked invalid by this validator
# even though they matched the documented Phase 1 contract.
_FINDING_SECTION_RE = re.compile(
    r"^##\s+(Finding|Open Exploration Findings|\d+\.)",
    re.MULTILINE,
)

# Regex used by Phase 6's artifact validator to detect a ``BUG-`` entry
# header in BUGS.md.
_BUG_ENTRY_RE = re.compile(r"^##\s+BUG-", re.MULTILINE)


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
        path = quality_dir / "EXPLORATION.md"
        if not path.is_file():
            return (False, f"missing artifact: {path}")
        text = path.read_text(encoding="utf-8", errors="ignore")
        # v1.5.6 BUG-005: align Phase 1 completion threshold with the
        # Phase 2 startup gate (run_playbook.check_phase_gate phase=2,
        # which requires EXPLORATION.md ≥120 lines). The pre-v1.5.6
        # 200-byte threshold was strictly weaker — a Phase-1-complete
        # artifact could pass this validator yet immediately fail the
        # Phase 2 startup check, leaving the run wedged in a
        # "phase 1 done, phase 2 won't start" state. The same
        # 120-line threshold now applies to both gates.
        line_count = len(text.splitlines())
        if line_count < 120:
            return (
                False,
                f"{path} has {line_count} lines; Phase 2 startup gate "
                f"requires at least 120",
            )
        if not _FINDING_SECTION_RE.search(text):
            return (
                False,
                f"{path} contains no finding section header "
                f"(expected '## Finding', '## Open Exploration Findings', "
                f"or '## N.')",
            )
        return (True, "")

    if phase == 2:
        # v1.5.6 BUG-014 (Conclusion C from instruction-019 investigation):
        # the v1.5.5 design's triage model (EXPLORATION_MERGED.md,
        # triage.md) was never adopted by the shipped SKILL.md /
        # orchestrator_protocol.md / agent files — they document Phase 2
        # as Generate, producing a 9-artifact contract plus one
        # functional-test file. Validate the shipped Generate contract
        # so a successful Phase 2 cannot fail this validator. The
        # canonical Generate contract is documented in
        # references/orchestrator_protocol.md (Phase 2 row, fixed by
        # cluster 3 / commit 7ab8ef4) and SKILL.md Phase 2 prose.
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
        path = quality_dir / "RUN_CODE_REVIEW.md"
        if not path.is_file():
            return (False, f"missing artifact: {path}")
        return (True, "")

    if phase == 4:
        requirements = quality_dir / "REQUIREMENTS.md"
        coverage = quality_dir / "COVERAGE_MATRIX.md"
        if not requirements.is_file():
            return (False, f"missing artifact: {requirements}")
        if requirements.stat().st_size == 0:
            return (False, f"{requirements} is empty")
        if not coverage.is_file():
            return (False, f"missing artifact: {coverage}")
        # v1.5.5 Council R2 P1.3: if the four-pass skill-derivation
        # pipeline ran (quality/phase3/ exists), each pass's canonical
        # output must be present and non-empty. Spec/Code projects that
        # skip skill-derivation produce no quality/phase3/ directory;
        # the conditional preserves backward compatibility for those.
        phase3_dir = quality_dir / "phase3"
        if phase3_dir.is_dir():
            pass_artifacts = (
                phase3_dir / "pass_a_drafts.jsonl",
                phase3_dir / "pass_b_citations.jsonl",
                phase3_dir / "pass_c_formal.jsonl",
                phase3_dir / "pass_d_council_inbox.json",
            )
            for artifact in pass_artifacts:
                if not artifact.is_file():
                    return (False, f"missing artifact: {artifact}")
                if artifact.stat().st_size == 0:
                    return (False, f"{artifact} is empty")
        return (True, "")

    if phase == 5:
        path = quality_dir / "results" / "quality-gate.log"
        if not path.is_file():
            return (False, f"missing artifact: {path}")
        if path.stat().st_size == 0:
            return (False, f"{path} is empty")
        return (True, "")

    # phase == 6
    bugs = quality_dir / "BUGS.md"
    index = quality_dir / "INDEX.md"
    if not bugs.is_file():
        return (False, f"missing artifact: {bugs}")
    if bugs.stat().st_size == 0:
        return (False, f"{bugs} is empty")
    bugs_text = bugs.read_text(encoding="utf-8", errors="ignore")
    if not _BUG_ENTRY_RE.search(bugs_text):
        return (
            False,
            f"{bugs} contains no '## BUG-' entry header",
        )
    if not index.is_file():
        return (False, f"missing artifact: {index}")
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
        if ev != "_index" and declared_types and ev not in declared_types:
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

    phase_names = {
        1: "Exploration",
        2: "Triage",
        3: "Investigation",
        4: "Skill-derivation",
        5: "Verification",
        6: "Release readiness",
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
