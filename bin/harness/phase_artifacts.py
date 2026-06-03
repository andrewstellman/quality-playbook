"""v1.5.7 168: canonical phase→artifact map + the two consumers that
read it (``infer_phase_from_artifacts`` and ``phase_yn_grid``).

Single source of truth. Previously the same mapping was duplicated
across two functions:

- ``bin/harness/status.py::_PHASE_ARTIFACTS`` (the TUI/status's
  ``_infer_phase_from_artifacts``).
- ``bin/harness/plan_runner.py::capture_phase_yn`` (the SUMMARY
  table's per-phase Y/N fallback).

Both maps had the same defect class (BUG-004 + BUG-007 in the
2026-05-30 QPB-on-QPB bootstrap): they assigned Phase-2 Generate
outputs (``QUALITY.md``, ``COMPLETENESS_REPORT.md``,
``RUN_CODE_REVIEW.md``, ``RUN_SPEC_AUDIT.md``, ``RUN_TDD_TESTS.md``)
to higher phases — so a run that finished only Phase 2 was reported
as Phase 5 (status.py) or P3-P6=Y (plan_runner.py).

The canonical truth is the runner's own Phase-3 prerequisite gate
at ``bin/run_playbook.py:1522-1530`` (the Phase-2 outputs that must
exist before Phase 3 starts):

    REQUIREMENTS.md, QUALITY.md, CONTRACTS.md, RUN_CODE_REVIEW.md,
    COVERAGE_MATRIX.md, COMPLETENESS_REPORT.md,
    RUN_INTEGRATION_TESTS.md, RUN_SPEC_AUDIT.md, RUN_TDD_TESTS.md

Anything in that list is a Phase-2 output. Phases 3-6 each have
exactly one fixed-path marker (or none for Phase 4, whose
``spec_audits/<date>-triage.md`` shape is glob-only and intentionally
NOT artifact-inferable — under-report beats over-report).

Any phase-map change MUST update ``PHASE_ARTIFACTS`` here AND any
inline test fixtures that mirror it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


# Source of truth — keyed by phase number.
# Tuple of artifact names (relative to ``quality_dir``); a phase is
# considered "evidenced" if ANY of its named artifacts exists. An
# empty tuple means "no fixed-path marker; not artifact-inferable"
# (Phase 4, per the BUG-004 fix design).
PHASE_ARTIFACTS: "dict[int, tuple[str, ...]]" = {
    # Phase 0 (Prep): early-run indicators. v1.5.7 178: lets Tier 3
    # detect that a Mode A run is in setup/early-Phase-1 work even
    # when the agent hasn't emitted qpb_phase yet. These artifacts
    # appear in the first 0-5 minutes (PROGRESS.md is updated as
    # the agent works; RUN_INDEX.md is created by the qpb_validate
    # bootstrap; formal_docs_manifest.json by the v1.5.3 doc-
    # gathering step). EXPLORATION.md — the Phase-1-DONE marker —
    # doesn't appear until ~10 min. Pre-178 Tier 3 returned None
    # for this window and status showed phase=— for 5-10 min.
    # Per 168's highest-phase-wins semantic, Phase 0 only fires
    # when NO higher phase has artifacts present (i.e., before
    # EXPLORATION.md exists).
    0: (
        "PROGRESS.md",
        "RUN_INDEX.md",
        "formal_docs_manifest.json",
    ),
    # Phase 1: run_playbook.py:1297 — the Phase-2 gate fails unless
    # quality/EXPLORATION.md exists, so it's the Phase-1 boundary.
    1: ("EXPLORATION.md",),
    # Phase 2 (Generate): the full Phase-3 prerequisite gate at
    # run_playbook.py:1522-1530. Pre-168 the status.py map listed
    # only REQUIREMENTS.md/CONTRACTS.md/COVERAGE_MATRIX.md (a
    # subset), while plan_runner.py's capture_phase_yn fallback
    # mis-mapped these to P3-P6. The full Phase-2 set IS:
    2: (
        "REQUIREMENTS.md",
        "CONTRACTS.md",
        "COVERAGE_MATRIX.md",
        "QUALITY.md",                 # BUG-004
        "COMPLETENESS_REPORT.md",     # BUG-004
        "RUN_CODE_REVIEW.md",         # BUG-004 / BUG-007
        "RUN_SPEC_AUDIT.md",          # BUG-007
        "RUN_TDD_TESTS.md",           # BUG-007
        "RUN_INTEGRATION_TESTS.md",
    ),
    # Phase 3 (Review): BUGS.md is the bugs-found landing. RUN_CODE_-
    # REVIEW.md is NOT Phase 3 — it's a Phase-2 Generate output (per
    # the Phase-3 prerequisite gate). BUG-004/007 fix.
    3: ("BUGS.md",),
    # Phase 4 (Spec audit): no fixed-path single-file marker —
    # `spec_audits/<date>-triage.md` is glob-only. Intentionally
    # not artifact-inferable; falls back to the transcript signal
    # only. Under-report beats over-report (REQ-004).
    4: (),
    # Phase 5 (TDD): results/tdd-results.json is the Phase-5-
    # exclusive marker.
    5: ("results/tdd-results.json",),
    # Phase 6 (Gate): the gate writes its verdict to
    # quality/results/gate-report-latest.json (a results/ subdir,
    # like Phase 5's marker).
    6: ("results/gate-report-latest.json",),
}


def _phase_has_artifact(quality_dir: Path, phase: int) -> bool:
    """True iff ANY artifact for ``phase`` is a regular file under
    ``quality_dir``. Phase 4 (empty tuple) is always False — not
    artifact-inferable by design."""
    artifacts = PHASE_ARTIFACTS.get(phase, ())
    return any(
        (quality_dir / name).is_file() for name in artifacts)


def infer_phase_from_artifacts(
        quality_dir: Optional[Path]) -> Optional[int]:
    """Return the highest phase whose artifacts are present in
    ``quality_dir``, or ``None`` if no phase's artifacts are
    present / ``quality_dir`` is None or absent. Phase 4 is never
    returned here (empty tuple = not artifact-inferable); a run
    that completed Phase 4 but not Phase 5/6 is reported as the
    highest phase with a fixed-path marker (likely Phase 3 OR
    Phase 2, depending on what's on disk)."""
    if quality_dir is None or not quality_dir.is_dir():
        return None
    for phase in sorted(PHASE_ARTIFACTS.keys(), reverse=True):
        if _phase_has_artifact(quality_dir, phase):
            return phase
    return None


def phase_yn_grid_artifact(
        quality_dir: Optional[Path]) -> "dict[int, bool]":
    """Return ``{phase_number: artifact_present_bool}`` for phases
    1..6 — the artifact-presence half of ``capture_phase_yn``'s
    grid. Caller combines with transcript signals via OR. Phase 4
    (empty tuple) always reports False (not artifact-inferable;
    caller falls back to the transcript only)."""
    if quality_dir is None or not quality_dir.is_dir():
        return {phase: False for phase in PHASE_ARTIFACTS}
    return {
        phase: _phase_has_artifact(quality_dir, phase)
        for phase in PHASE_ARTIFACTS
    }
