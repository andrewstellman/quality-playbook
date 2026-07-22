#!/usr/bin/env python3
"""quality_gate.py — Post-run validation gate for Quality Playbook artifacts.

Mechanically checks artifact conformance issues that model self-attestation
persistently misses. Now the sole gate script; the earlier quality_gate.sh
(bash) has been retired. See quality_gate/test_quality_gate.py for the test
suite.

Usage:
    ./quality_gate.py .                          # Check current directory (benchmark mode)
    ./quality_gate.py --general .                # Check with relaxed thresholds
    ./quality_gate.py virtio                     # Check named repo (from repos/)
    ./quality_gate.py --all                      # Check all current-version repos
    ./quality_gate.py --version 1.3.27 virtio    # Check specific version

Exit codes:
    0 — GATE PASSED, or GATE PASSED WITH CLEANUP NEEDED (only audit
        record-keeping gaps remain; the review completed and its
        findings stand — see the v1.5.7 089c F15 taxonomy block below)
    1 — GATE FAILED (one or more substantive issues — the work itself
        wasn't done correctly)

Runs on Python 3.8+ with only the standard library.
"""

import functools
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# Allow soft import of bin/citation_verifier for v1.5.1 byte-equality checks.
# The verifier may live at one of several locations depending on where the
# gate was installed:
#   1. <QPB-clone>/bin/citation_verifier.py — gate runs from the source tree
#      (gate path: <clone>/.github/skills/quality_gate/quality_gate.py;
#      bin/ is three parents up from SCRIPT_DIR).
#   2. <install-root>/bin/citation_verifier.py — gate installed alongside
#      bin/ at the install root (v1.5.6 BUG-005 fix; bin/install_skill.py
#      and repos/setup_repos.sh both bundle bin/citation_verifier.py here).
#   3. <install-root>/bin/citation_verifier.py via the nested-skills path
#      (.github/skills/quality_gate.py — SCRIPT_DIR is .github/skills, and
#      bin/ is two parents up).
# When none of these resolve, byte-equality is skipped with a WARN rather
# than a hard FAIL — the gate continues with reduced enforcement.
_CITATION_VERIFIER = None
_VERIFIER_SEARCH_ROOTS = [
    SCRIPT_DIR.parent.parent.parent,  # source-clone layout (pre-208)
    SCRIPT_DIR,                       # gate + bin/ siblings (uncommon)
    SCRIPT_DIR.parent.parent,         # nested-skills layout (.github/skills/quality_gate.py)
]
# v1.5.8 instruction 208: in the post-208 QPB clone the canonical
# citation_verifier.py lives alongside quality_gate.py in
# skills/quality-playbook/scripts/ (i.e. SCRIPT_DIR itself).
# Try the sibling-script form first so the byte-equality
# citation check resolves in the post-208 clone.
_sibling_verifier = SCRIPT_DIR / "citation_verifier.py"
if _sibling_verifier.is_file():
    try:
        if str(SCRIPT_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPT_DIR))
        import citation_verifier as _CITATION_VERIFIER  # noqa: E402
    except Exception:  # noqa: BLE001
        _CITATION_VERIFIER = None
if _CITATION_VERIFIER is None:
    for _candidate_root in _VERIFIER_SEARCH_ROOTS:
        _verifier_file = _candidate_root / "bin" / "citation_verifier.py"
        if _verifier_file.is_file():
            try:
                if str(_candidate_root) not in sys.path:
                    sys.path.insert(0, str(_candidate_root))
                from bin import citation_verifier as _CITATION_VERIFIER  # noqa: E402
                break
            except Exception:  # noqa: BLE001 — missing / misinstalled bin/ is tolerable
                _CITATION_VERIFIER = None
                continue

# Global counters — reset per invocation via main(). Tests that call check_repo
# directly should reset these in setUp.
FAIL = 0
WARN = 0


# ---------------------------------------------------------------------------
# v1.5.7 instruction 089c (F15) — three-state verdict taxonomy.
#
# Round 2 ship-validation surfaced an adopter-UX defect: the old binary
# GATE PASSED / GATE FAILED verdict treated audit record-keeping
# incompleteness (a manifest field missing, a sidecar absent, a
# cross-site pattern tag not applied) IDENTICALLY to substantive failure
# (the review never ran, specs absent, a verdict fabricated). An adopter
# reading "GATE FAILED — 44 check(s)" could not tell "your code is
# broken in 44 ways" from "your audit trail is incomplete in 44 ways".
# Both Round 2 runs (haiku/click, codex/express) completed real Phase
# 0-6 work and found real TDD-verified bugs but were tagged GATE FAILED
# purely on artifact-completeness gaps.
#
# Every check function is now classified into exactly one category:
#
#   "substantive"    — failure means the WORK WASN'T DONE CORRECTLY:
#                      the review didn't complete; EXPLORATION / specs /
#                      BUGS / writeups / patches are missing; the
#                      mechanical verifier was never invoked or failed;
#                      TDD red->green evidence is absent; the Phase 5
#                      verdict is missing/fabricated; layout drift hides
#                      artifacts. These BLOCK the gate (exit 1).
#
#   "record_keeping" — failure means the WORK HAPPENED but the AUDIT
#                      TRAIL HAS GAPS: a manifest record is missing a
#                      field (disposition / functional_section / tier);
#                      a sidecar or per-bug challenge record is absent;
#                      a cross-site pattern tag or role-map breakdown
#                      field is missing; bugs↔patches bookkeeping is
#                      out of sync. The bugs are real and reviewed; the
#                      paperwork is incomplete. These DON'T block — they
#                      surface as cleanup (exit 0).
#
# Classification is per CHECK FUNCTION via the @verdict_category(...)
# decorator (recorded as the function's _VERDICT_CATEGORY attribute).
# The decorator pushes the category onto _CHECK_CATEGORY_STACK for the
# duration of the call so fail()s emitted by nested helpers
# (_v150_manifest, validate_cardinality_gate, _check_citation_block,
# _check_exploration_sections, ...) inherit the enclosing check's
# category. A fail() MAY override per call via fail(..., category=...).
#
# Default rule (089c Task 1): a genuinely ambiguous check is classified
# "substantive" — better to FAIL than to PASS-WITH-CLEANUP a real
# defect. The record_keeping set is deliberately narrow and tracks the
# Round 2 evidence + the F15 illustrative output: bugs↔patches
# consistency, the v1.5.0 / v1.5.3 manifest field-completeness checks,
# the challenge-gate coverage check, the v1.5.2 cardinality
# (cross-site-pattern-tag) gate, run-metadata, and role-map
# well-formedness. Everything else (artifact existence, BUGS heading,
# TDD sidecar/logs, integration/recheck sidecars, use-cases, mechanical
# verification, patches, writeups, verdict shape, workspace drift,
# version stamps, cross-run contamination, cite-extensions, INDEX.md
# (invariant #10 — absent INDEX is substantive), semantic check, the
# Phase-4 skill-coverage checks) stays substantive.
#
# Verdict (main()): zero FAILs -> GATE PASSED (exit 0). Any substantive
# FAIL -> GATE FAILED (exit 1). Only record_keeping FAILs -> GATE
# PASSED WITH CLEANUP NEEDED (exit 0 — cleanup is not a hard failure).
# The exact RESULT: line strings are LOAD-BEARING; downstream consumers
# (phase_prompts/phase6{,_auditor}.md witness contract,
# bin/validate_phase_artifacts.py, references/what_just_happened.md
# State CN, the gate test suite) pattern-match on them.
# ---------------------------------------------------------------------------

VERDICT_SUBSTANTIVE = "substantive"
VERDICT_RECORD_KEEPING = "record_keeping"
_VALID_VERDICT_CATEGORIES = (VERDICT_SUBSTANTIVE, VERDICT_RECORD_KEEPING)

# (category, rendered_message) for every fail() emitted this run. Reset
# with the counters. main() splits this for the three-state verdict.
_FAIL_RECORDS = []

# v1.5.7 090v: every warn() message recorded for the operator verdict-
# explanation layer (additive presentation only — see
# ``_emit_operator_verdict``). The WARN counter (`WARN`) remains the
# authoritative count; this list adds the message bodies so the
# verdict layer can partition WARNs into actionable vs benign-back-
# compat via the curated allowlist (Task D). Reset with the counters.
_WARN_RECORDS: list[str] = []

# v1.5.7 090w: per-repo run provenance for the operator verdict-
# explanation layer. Each entry captures:
#   - ``repo``: repo name (matches ``_ZERO_BUG_REPOS`` shape).
#   - ``runner_detected``: runner detected from the EXECUTION
#     environment (verified — CODEX_THREAD_ID / COPILOT_AGENT_
#     SESSION_ID / CLAUDECODE → codex / copilot / claude-code, or
#     ``unknown`` when none are set).
#   - ``model_self_reported``: the ``model`` field from
#     ``quality/results/run-*.json`` if present (LABELED as
#     self-report — demonstrably unreliable; NATS run2 wrote
#     "gpt-5.2" when the actual model was gpt-5.4).
#   - ``bug_count_gate``: the gate's own confirmed bug count for
#     this repo (verified — derived from BUG-NNN headings in
#     BUGS.md).
#   - ``bug_count_self_reported``: the ``bug_count`` field from
#     run-metadata if present, else ``None``. NATS run2 wrote 0
#     when the gate counted 3 (stale-metadata mismatch).
# The verdict block renders one provenance block per entry with
# explicit confidence labels (verified vs self-reported); a
# self-report vs gate mismatch is flagged informationally.
_RUN_PROVENANCE: list[dict] = []

# Category context stack. @verdict_category pushes on call entry and
# pops on exit; fail() reads the top (or an explicit category= override;
# or VERDICT_SUBSTANTIVE when the stack is empty — conservative default).
_CHECK_CATEGORY_STACK = []


def verdict_category(category):
    """Decorator: record a check function's F15 verdict category and,
    for the duration of each call, push it onto _CHECK_CATEGORY_STACK so
    fail()s from nested helpers inherit it. See the classification
    policy block above. `category` must be one of
    _VALID_VERDICT_CATEGORIES (raises ValueError otherwise — a typo'd
    category is a hard programming error, not a silent mis-classify)."""
    if category not in _VALID_VERDICT_CATEGORIES:
        raise ValueError(
            f"verdict_category: {category!r} not in "
            f"{_VALID_VERDICT_CATEGORIES}"
        )

    def _decorate(fn):
        @functools.wraps(fn)
        def _wrapped(*args, **kwargs):
            _CHECK_CATEGORY_STACK.append(category)
            try:
                return fn(*args, **kwargs)
            finally:
                _CHECK_CATEGORY_STACK.pop()

        # Expose the classification on BOTH the wrapper and the
        # underlying fn so introspection works regardless of which the
        # caller holds (the test suite asserts every check carries one).
        _wrapped._VERDICT_CATEGORY = category
        fn._VERDICT_CATEGORY = category
        return _wrapped

    return _decorate


def _compute_verdict_state(exit_code, fail_records,
                             warn_records, zero_bug_repos):
    """v1.5.7 109 — pure helper that returns the verdict-state
    slug ("solid" | "shallow" | "failed") matching the operator-
    verdict lead line in ``_emit_operator_verdict``.

    Extracted so the 109 ``::QPB::`` gate-result sentinel can
    emit the same state without re-running the lead-line
    rendering. The two callers (lead line + sentinel) MUST stay
    aligned — divergence would mean the operator sees one state
    on screen and the harness extracts a different one from the
    sentinel. The lead-line in ``_emit_operator_verdict`` calls
    this so the alignment is structural.
    """
    if exit_code != 0:
        return "failed"
    weak_model = _has_weak_model_signal(
        fail_records, zero_bug_repos, warn_records
    )
    is_shallow_pass = (
        bool(zero_bug_repos)
        or any("no test functions found" in w for w in warn_records)
        or weak_model
    )
    return "shallow" if is_shallow_pass else "solid"


def _resolve_phase_identity():
    """v1.5.9 1B.0: anchored resolver for the shared
    ``phase_identity`` module — the single writer of the
    ``::QPB:: {json}`` envelope line. quality_gate.py ships at the
    install ROOT (not under ``bin/``), so the path-load fallback
    tries this file's own directory (dev/source layout, where
    phase_identity sits beside it in ``scripts/``) AND a ``bin/``
    subdirectory (installed root layout, where bundled modules live
    under ``<install>/bin/``). Never touches a foreign sibling.
    """
    try:
        from bin import phase_identity as _pi  # type: ignore[import]
        return _pi
    except ImportError:
        pass
    try:
        import phase_identity as _pi  # type: ignore[no-redef, import]
        return _pi
    except ImportError:
        pass
    import importlib.util as _ilu
    _here = Path(__file__).resolve().parent
    for _cand in (_here / "phase_identity.py",
                   _here / "bin" / "phase_identity.py"):
        if _cand.is_file():
            _ps = _ilu.spec_from_file_location(
                "_quality_gate_phase_identity", _cand,
            )
            if _ps is not None and _ps.loader is not None:
                _pi = _ilu.module_from_spec(_ps)
                sys.modules[_ps.name] = _pi
                _ps.loader.exec_module(_pi)
                return _pi
    raise ImportError(
        "quality_gate: cannot resolve phase_identity — path-load "
        f"fallback targets under {_here} are missing."
    )


def _format_gate_sentinel(*, gate_result: str,
                            verdict_state: str,
                            ts: "str | None" = None) -> str:
    """v1.5.7 109 — return the single ``::QPB:: {json}`` line
    for the gate-result sentinel. Unit-testable; the gate calls
    this once at the end of main(), after the operator-verdict
    block.

    Format mirrors the ``kind:"phase"`` sentinel emitted by
    ``bin/qpb_phase.py`` (same v=1 envelope, different kind):
    ``::QPB:: {"v":1,"kind":"gate","gate_result":"PASS",
    "verdict_state":"solid","ts":"2026-05-26T..."}``.

    v1.5.9 1B.0: the one-line ``::QPB::`` envelope is now written by
    the shared ``phase_identity.format_qpb_envelope`` (single writer
    of that line shape). The gate PAYLOAD stays this function's own
    concern — only the envelope is unified, a deliberately lighter
    touch than the phase side (design decision 4).

    For LIVE DISPLAY ONLY. The harness's authoritative gate
    result for grading stays ``facts.rerun_installed_gate``
    (the collector's re-run, two-sourced per design §C); this
    sentinel does NOT become a grading input.
    """
    payload = {
        "v": 1,
        "kind": "gate",
        "gate_result": gate_result,
        "verdict_state": verdict_state,
        "ts": ts or _utc_now_iso(),
    }
    return _resolve_phase_identity().format_qpb_envelope(payload)


def _utc_now_iso() -> str:
    """v1.5.7 109 — UTC ISO-8601 in the format the harness uses
    elsewhere (Zulu suffix, no microseconds). Stdlib-only."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _compute_final_verdict(fail_records, warn_count):
    """v1.5.7 089c (F15) — pure three-state verdict decision.

    `fail_records` is the (category, message) ledger
    (quality_gate._FAIL_RECORDS shape). Returns
    ``(total_line, result_line, exit_code)``:

      - zero fails                  -> GATE PASSED                  exit 0
      - any substantive fail        -> GATE FAILED                  exit 1
      - only record_keeping fails   -> GATE PASSED WITH CLEANUP
                                       NEEDED                       exit 0

    The RESULT: line strings are LOAD-BEARING — phase_prompts/
    phase6{,_auditor}.md's witness contract, bin/validate_phase_
    artifacts.py, references/what_just_happened.md's State CN, and the
    gate test suite all pattern-match them. Kept pure (no globals, no
    printing) so the three-state logic is unit-testable directly
    without constructing a full repo fixture (089c Task 7)."""
    n_total = len(fail_records)
    n_sub = sum(1 for r in fail_records if r[0] == VERDICT_SUBSTANTIVE)
    n_clean = sum(
        1 for r in fail_records if r[0] == VERDICT_RECORD_KEEPING
    )
    if n_total == 0:
        return (
            f"Total: 0 FAIL, {warn_count} WARN",
            "RESULT: GATE PASSED",
            0,
        )
    if n_sub > 0:
        # Any substantive failure blocks. Break out the cleanup count
        # so the operator sees how much of the total is record-keeping.
        return (
            f"Total: {n_total} FAIL "
            f"({n_sub} substantive, {n_clean} record-keeping), "
            f"{warn_count} WARN",
            f"RESULT: GATE FAILED — {n_sub} substantive "
            f"issue(s) must be fixed",
            1,
        )
    # Only record-keeping fails remain: the review completed and its
    # findings stand on their own; the audit trail just has gaps. This
    # is NOT a hard failure (exit 0) — adopters/CI must be able to tell
    # "audit paperwork incomplete" apart from "the work is broken".
    return (
        f"Total: {n_clean} CLEANUP, {warn_count} WARN",
        f"RESULT: GATE PASSED WITH CLEANUP NEEDED — "
        f"{n_clean} audit record-keeping gap(s)",
        0,
    )


# ============================================================
# v1.5.7 090v — Operator verdict-explanation layer
#
# Additive presentation over already-computed accumulators
# (_FAIL_RECORDS / _WARN_RECORDS / _ZERO_BUG_REPOS). Printed
# AFTER the load-bearing ``total_line`` + ``result_line`` lines.
# Touches ZERO check logic; never changes ``exit_code``.
#
# Spec: docs/design/QPB_v1.6.x_Verdict_Explanation_Proposal.md
# (the 1.5.7 slice; v1.6.x expansion E1–E6 deferred).
#
# Hard rule: the "try a stronger model" recommendation is gated
# specifically on a weak-model/fabrication signal (a 090s
# hollow-test FAIL or a 090p overclaim FAIL). A pure environment-
# failure run (setup-failure reds only, no fabrication signal)
# gets the environment message and NEVER the stronger-model
# line. Getting this wrong gives actively harmful advice.
# ============================================================

# FAIL signatures the curated cluster (Task B). Each maps to a
# plain-English narration. Order is significant: a FAIL is
# classified against the first matching key. Substrings only —
# the legacy FAIL strings are load-bearing and not re-worded
# here.
_FAIL_NOOP_FUNCTIONAL = "noop_functional_test"
_FAIL_TDD_OVERCLAIM = "tdd_overclaim"
_FAIL_SETUP_FAILURE_RED = "setup_failure_red"
# v1.5.7 090x: bugs-found-but-unverified — bugs are present in
# BUGS.md but the TDD-proof artifacts (tdd-results.json /
# red-green logs / regression-test patches / test_regression.*)
# are absent ENTIRELY. Distinct from ``_FAIL_TDD_OVERCLAIM`` (090v
# / 089o): overclaim = GREEN claimed without runner output;
# bugs_unverified = the run never produced verification artifacts
# at all. Both can co-occur; each curated message emits when its
# signature is present. Attribution is intentionally NOT routed
# to the weak-model bucket — a capable model can produce this
# shape (discovery without verification = incomplete run, not
# cut-corners). The 2026-05-25 NATS run2 gpt-5.4 fixture is the
# motivating shape.
_FAIL_BUGS_UNVERIFIED = "bugs_unverified"
_FAIL_MISSING_ARTIFACT = "missing_artifact"
_FAIL_GENERIC = "generic"

# Substring-match table; first match wins.
#
# v1.5.7 090x: the ``bugs_unverified`` cluster is placed BEFORE the
# broader ``missing_artifact`` cluster so a precise keyed signature
# (e.g. "tdd-results.json missing (" — emitted only with a bug
# count) routes to ``bugs_unverified`` rather than falling through
# to the generic "missing required" message. These signatures are
# keyed to the FAIL emit strings in:
#   * check_tdd_sidecar     — tdd-results.json missing
#   * check_tdd_logs        — red-phase / green-phase log missing
#   * check_patches         — test_regression.* / regression-test
#                              patch missing
_FAIL_CLASSIFIER: "tuple[tuple[str, str], ...]" = (
    # 090s — no-op / all-trivial functional test.
    ("trivial / no-assertion stubs", _FAIL_NOOP_FUNCTIONAL),
    # 089o / 090p — TDD claimed RED/GREEN over a by-inspection body.
    ("body admits non-execution", _FAIL_TDD_OVERCLAIM),
    ("TDD receipt(s) overclaim", _FAIL_TDD_OVERCLAIM),
    # 090p — RED rejected as setup/build/dependency/collection failure.
    ("setup/dependency/build/collection failure", _FAIL_SETUP_FAILURE_RED),
    ("rejected as setup/dependency/build failures", _FAIL_SETUP_FAILURE_RED),
    # 090x — bugs present but TDD-proof artifacts absent
    # (BUG-NNN headings exist, but tdd-results.json / red-green
    # logs / regression-test patches / test_regression.* are
    # missing). Each signature is keyed to a specific FAIL emit
    # string. The 2026-05-25 NATS run2 gpt-5.4 fixture: 3 bugs +
    # no TDD artifacts. ORDERING NOTE: must precede the
    # ``missing_artifact`` broad cluster below — these strings
    # contain "missing", and we want the keyed signature to win.
    ("tdd-results.json missing (", _FAIL_BUGS_UNVERIFIED),
    ("confirmed bug(s) missing red-phase log",
     _FAIL_BUGS_UNVERIFIED),
    ("No red-phase logs found", _FAIL_BUGS_UNVERIFIED),
    ("bug(s) with fix patches missing green-phase log",
     _FAIL_BUGS_UNVERIFIED),
    ("test_regression.* missing — required when bugs exist",
     _FAIL_BUGS_UNVERIFIED),
    ("No regression-test patches found", _FAIL_BUGS_UNVERIFIED),
    # Missing required artifact — the generic "X missing" / "missing
    # required" / "required" cluster (intentionally broad — the
    # generic-fallback path still covers anything we miss).
    ("missing required", _FAIL_MISSING_ARTIFACT),
    (" missing (required at ", _FAIL_MISSING_ARTIFACT),
    ("missing (required ", _FAIL_MISSING_ARTIFACT),
)


def _classify_fail(message: str) -> str:
    """Return the curated category for a FAIL message, or
    ``_FAIL_GENERIC`` if no curated message applies (graceful
    fallback per the spec)."""
    for needle, category in _FAIL_CLASSIFIER:
        if needle in message:
            return category
    return _FAIL_GENERIC


# Benign WARN allowlist (Task D). Conservative — every entry is a
# WARN that is documented in-source as a back-compat / intended-
# default / "not a defect" notice. Substring match against the
# WARN message body; first match wins. Anything NOT on this list
# stays prominent (we never collapse an unknown WARN).
_BENIGN_WARN_ALLOWLIST: "tuple[str, ...]" = (
    # 089 F9 — intended backward-compat path, documented "not a
    # defect" (see quality_gate.py ~:4692/4734).
    "intended backward-compat path",
    # schemas.md §3.10 — legacy bugs_manifest auto-defaulting.
    "legacy manifest detected",
    # Pre-W4 back-compat — older runs appended probe assertions to
    # verify.sh (see quality_gate.py ~:1858/3088).
    "pre-W4 back-compat",
    # Skill version detection on legacy SKILL.md / PROGRESS.md.
    "Cannot detect skill version from SKILL.md",
)


def _is_benign_warn(message: str) -> bool:
    """Return True iff the WARN matches the curated benign
    allowlist. Conservative: an unknown WARN is NEVER demoted."""
    return any(needle in message for needle in _BENIGN_WARN_ALLOWLIST)


def _has_weak_model_signal(fail_records, zero_bug_repos,
                            warn_records) -> bool:
    """Return True iff the run carries a fabrication / hollow-tell
    signal that justifies the 'try a stronger reasoning model'
    recommendation (Task C hard rule). Signals:

    * Any FAIL classified as no-op functional or TDD overclaim
      (the 090s hollow shape or the 090p overclaim-by-omission).
    * A zero-bug repo coincident with a 090s WARN about test
      functions missing (the thin-exploration tell).
    """
    for _cat, msg in fail_records:
        cat = _classify_fail(msg)
        if cat in (_FAIL_NOOP_FUNCTIONAL, _FAIL_TDD_OVERCLAIM):
            return True
    # Thin-exploration tell: zero-bug AND a 090s no-test-functions
    # WARN present in the same run. The WARN alone (without the
    # zero-bug shape) is not a fabrication signal — the test file
    # might just use a helper-only shape the detector doesn't
    # recognize (see quality_gate.py ~:3003).
    if zero_bug_repos:
        for w in warn_records:
            if "no test functions found" in w:
                return True
    return False


def _has_environment_signal(fail_records) -> bool:
    """Return True iff the run carries a setup-failure RED that
    routes the operator to fix the environment (Task C). May
    coexist with a weak-model signal in mixed-failure runs."""
    for _cat, msg in fail_records:
        if _classify_fail(msg) == _FAIL_SETUP_FAILURE_RED:
            return True
    return False


# v1.5.7 090w — Run provenance (verified runner + labeled
# self-reported model + gate-counted bugs).
#
# Motivated by the 2026-05-25 NATS run2 (gpt-5.4/medium via Codex
# desktop): the run found 3 real bugs but ``quality/results/run-*.json``
# still read ``"model": "gpt-5.2"`` and ``"bug_count": 0`` (the agent
# wrote the template at the start and never updated it). Operators want
# real provenance, but echoing the self-reported fields raw would print
# confidently-wrong provenance. The fix: surface provenance with
# explicit confidence labels, prefer gate-derived facts, and flag
# self-report/gate mismatches.
#
# These environment variables are the SAME ones the dual-env test
# harness keys off (see ``CODEX_THREAD_ID``/``COPILOT_AGENT_SESSION_ID``/
# ``CLAUDECODE`` references in bin/tests). When more than one is set,
# all detected runners are returned (joined with "+") so a mixed
# environment is honestly reported, not collapsed to a guess.
_RUNNER_ENV_MARKERS: "tuple[tuple[str, str], ...]" = (
    ("CODEX_THREAD_ID", "codex"),
    ("COPILOT_AGENT_SESSION_ID", "copilot"),
    ("CLAUDECODE", "claude-code"),
)


def _detect_runner_from_env(env: "dict | None" = None) -> str:
    """Return the runner detected from the execution environment.

    Returns one of ``codex``/``copilot``/``claude-code``/``unknown``,
    OR a "+"-joined string when more than one marker is present.
    `env` defaults to ``os.environ`` (real execution); tests pass an
    explicit dict.
    """
    if env is None:
        env = os.environ
    detected = [name for var, name in _RUNNER_ENV_MARKERS
                if env.get(var)]
    if not detected:
        return "unknown"
    if len(detected) == 1:
        return detected[0]
    return "+".join(detected)


def _capture_run_provenance(q, repo_name: str, bug_count: int) -> None:
    """Read ``quality/results/run-*.json`` (self-reported), combine
    with the env-detected runner + the gate's bug count, and append
    one entry to ``_RUN_PROVENANCE``. Defensive: missing /
    unparseable / odd shapes still record a provenance entry (with
    ``model_self_reported=None`` /
    ``bug_count_self_reported=None``) — provenance is informational
    only and never fails the gate.

    The existing ``check_run_metadata`` is the FAIL/WARN-emitting
    validator; this helper is read-only and additive — it never
    emits FAIL/WARN, never alters ``exit_code``.
    """
    results_dir = _resolve_artifact_path(q, "results")
    import glob as _glob
    matches = _glob.glob(str(results_dir / "run-*.json"))
    model_self_reported: "str | None" = None
    bug_count_self_reported: "int | None" = None
    if matches:
        # Pick the lexicographically-last (the ISO-style timestamp
        # makes lexsort equivalent to chronological). When
        # check_run_metadata WARNs on multiple files, we still get
        # SOME provenance — provenance is informational.
        data = load_json(Path(sorted(matches)[-1]))
        if isinstance(data, dict):
            raw_model = data.get("model")
            if isinstance(raw_model, str) and raw_model.strip():
                model_self_reported = raw_model.strip()
            raw_bc = data.get("bug_count")
            if isinstance(raw_bc, int):
                bug_count_self_reported = raw_bc
    _RUN_PROVENANCE.append({
        "repo": repo_name,
        "runner_detected": _detect_runner_from_env(),
        "model_self_reported": model_self_reported,
        "bug_count_gate": bug_count,
        "bug_count_self_reported": bug_count_self_reported,
    })


def _format_provenance_lines(entry: dict) -> "list[str]":
    """Render a provenance entry as a list of lines for the verdict
    block. The format mirrors the spec example shape:

        Runner:  codex (detected from environment)
        Model:   gpt-5.2 (self-reported by the agent — not verified)
        Bugs:    3 found (gate-counted)   [run-metadata self-reported: 0 — mismatch]
    """
    lines: list[str] = []
    runner = entry.get("runner_detected") or "unknown"
    if runner == "unknown":
        lines.append(
            f"  Runner:  {runner} (no AI-CLI environment marker "
            f"detected)"
        )
    else:
        lines.append(
            f"  Runner:  {runner} (detected from environment)"
        )
    model = entry.get("model_self_reported")
    if model:
        lines.append(
            f"  Model:   {model} (self-reported by the agent — "
            f"not verified)"
        )
    else:
        lines.append("  Model:   not recorded")
    gate_bc = entry.get("bug_count_gate", 0)
    self_bc = entry.get("bug_count_self_reported")
    bug_line = f"  Bugs:    {gate_bc} found (gate-counted)"
    if self_bc is not None and self_bc != gate_bc:
        bug_line += (
            f"   [run-metadata self-reported: {self_bc} — "
            f"mismatch; run metadata was not updated]"
        )
    lines.append(bug_line)
    return lines


# Narration table — keyed by classifier category; emits plain-
# English explanation + remediation. Wording per the spec
# (docs/design/QPB_v1.6.x_Verdict_Explanation_Proposal.md §1.5.7).
_FAIL_NARRATION = {
    _FAIL_NOOP_FUNCTIONAL: (
        "The functional test contains no real assertions — the "
        "test functions exist but their bodies don't actually "
        "check anything. A test that asserts nothing can't fail, "
        "so a PASS proves nothing about the code. Add at least "
        "one assertion-bearing test (Go: `t.Error` / `t.Fatal` "
        "/ `require.*` / `assert.*`; Python: `assert <expr>` / "
        "`self.assert*` / `pytest.raises`), then re-run."
    ),
    _FAIL_TDD_OVERCLAIM: (
        "The run claims its bug-fix tests passed, but it never "
        "actually ran them (no runner output), or the test it "
        "ran isn't the one tied to the bug. A GREEN claim "
        "without real execution isn't proof — these bugs are "
        "unconfirmed. Re-run so the tests actually execute "
        "(capture real runner output), or honestly mark them "
        "NOT_RUN (which WARN-passes per the honest-skip path)."
    ),
    _FAIL_SETUP_FAILURE_RED: (
        "A test failed because the environment couldn't "
        "build/run it (e.g. missing dependency, no network for "
        "module fetch, test binary failed to compile) — not "
        "because the AI found a defect. Fix the environment "
        "(install missing tooling, restore network or pre-fetch "
        "dependencies, verify the build), then re-run Phases "
        "5–6."
    ),
    _FAIL_MISSING_ARTIFACT: (
        "A required artifact (file or section) the gate expects "
        "is missing or malformed. The check name above identifies "
        "which artifact; produce it (or fix its content) and "
        "re-run."
    ),
    # v1.5.7 090x — pulled forward from the v1.6.x E1 long-tail
    # because the incomplete-verification shape is high-frequency
    # (the 2026-05-25 NATS run2 gpt-5.4 fixture: 3 real bugs, no
    # TDD proof, generic-fallback message). Attribution stays in
    # the "neither weak-model nor environment" attribution path —
    # this is an incomplete run, NOT a cut-corners run.
    _FAIL_BUGS_UNVERIFIED: (
        "This run found bug(s) but didn't verify them — there's "
        "no TDD proof (missing tdd-results.json / red-green logs "
        "/ regression-test patches / test_regression.*). A found "
        "bug without a red→green test isn't confirmed: the fix "
        "might be wrong, or the \"bug\" might not be real. "
        "Either complete the verification step so the tests "
        "actually run, or treat these as code-review "
        "candidates, not confirmed bugs."
    ),
}


def _emit_operator_verdict(fail_records, warn_records, zero_bug_repos,
                            exit_code, run_provenance=None):
    """v1.5.7 090v — print the operator-facing verdict-explanation
    block AFTER ``total_line`` + ``result_line``.

    Purely additive: the load-bearing strings and ``exit_code`` are
    untouched (the caller has already printed them and is keeping
    the return value). Subsumes the standalone 090s zero-bug NOTE
    by folding the message into the shallow-pass narration when
    applicable.

    v1.5.7 090w: optional ``run_provenance`` (list of dicts from
    ``_capture_run_provenance``) renders the "── Run provenance ──"
    section — verified runner (env-detected), labeled self-reported
    model, gate-counted bugs with a stale-metadata mismatch flag.
    Provenance is informational only; never changes pass/fail
    semantics.

    Spec: docs/design/QPB_v1.6.x_Verdict_Explanation_Proposal.md
    """
    weak_model = _has_weak_model_signal(
        fail_records, zero_bug_repos, warn_records
    )
    env_failure = _has_environment_signal(fail_records)
    # "Shallow" PASS: exit_code == 0 (no FAIL) but a hollow-shape
    # tell is present. Zero-bug alone is a shallow tell (per 090s).
    # v1.5.7 109: the shallow-vs-solid decision moved into
    # _compute_verdict_state so the 109 ::QPB:: gate sentinel
    # emits the SAME state slug the lead line prints (no
    # divergence between operator-facing render + harness-facing
    # sentinel — they share one helper).
    verdict_state = _compute_verdict_state(
        exit_code, fail_records, warn_records, zero_bug_repos,
    )
    is_shallow_pass = (verdict_state == "shallow")

    # === Section 1: lead verdict line ===
    # v1.5.7 185 FINDING-27: ASCII verdict markers
    # ([PASS]/[WARN]/[FAIL]) replace the pre-185 emoji
    # markers (✅/⚠️/❌). On Windows the stream-captured
    # stdout path uses cp1252 codec and crashes print()
    # with UnicodeEncodeError on the emoji. The dual-form
    # (emoji + ASCII) verdict lead lines are consumed by
    # bin/run_playbook.py's gate-verdict reader (185 FINDING-28;
    # the old Python harness's facts parser was removed in v1.5.9 2E).
    print("")
    print("--- Operator Verdict ---")
    if exit_code != 0:
        lead = "[FAIL] GATE FAILED"
    elif is_shallow_pass:
        lead = "[WARN] GATE PASSED -- but this run looks shallow"
    else:
        lead = "[PASS] GATE PASSED -- this run looks solid"
    print(lead)

    # === Section 2: plain-English "why + what to do" for FAILs ===
    if fail_records:
        # Group FAILs by curated category to avoid repeating the
        # same narration N times. Preserve first-seen order so
        # the operator reads the explanations in the order the
        # checks fired.
        seen: list[str] = []
        per_category_msgs: dict[str, list[str]] = {}
        for _cat, msg in fail_records:
            classified = _classify_fail(msg)
            if classified not in per_category_msgs:
                per_category_msgs[classified] = []
                seen.append(classified)
            per_category_msgs[classified].append(msg)
        print("")
        print("Why it failed:")
        for category in seen:
            msgs = per_category_msgs[category]
            label = (
                f"  • [{category}] ({len(msgs)} FAIL{'s' if len(msgs) > 1 else ''})"
            )
            print(label)
            narration = _FAIL_NARRATION.get(category)
            if narration is None:
                # Generic fallback — name the failing check from
                # the first message so the operator has a pointer.
                first = msgs[0].strip()
                # Strip leading line-number prefix if present.
                short = first.split(":", 1)[0] if ":" in first else first
                narration = (
                    f"This check failed: {short}. See the line "
                    f"above for the specific check output; the "
                    f"v1.6.x verdict-explanation expansion will "
                    f"add a curated message for this code."
                )
            print(f"    {narration}")

    # === Section 3: shallow-PASS narration + three-bucket attribution ===
    #
    # Bucket precedence (per spec §1.5.7 "Three-bucket attribution"):
    # buckets are NOT mutually exclusive — emit every applicable. The
    # "try a stronger reasoning model" line is gated to the weak-model
    # bucket ONLY (hard rule — mis-attribution gives actively harmful
    # advice on a pure environment-failure run).
    #
    # The shallow-PASS narration subsumes the standalone 090s zero-bug
    # NOTE so the message appears here, not duplicated. The "ZERO
    # confirmed bugs" / "hollow / shallow run" / "Ory Keto run4" /
    # "v1.5.7 090s" tokens are preserved verbatim so the
    # ZeroBugVerdictQualifierTests pins still hold.
    if is_shallow_pass:
        print("")
        shallow_bits = []
        if zero_bug_repos:
            n = len(zero_bug_repos)
            names = ", ".join(zero_bug_repos)
            repo_word = "repo" if n == 1 else "repos"
            shallow_bits.append(
                f"{n} {repo_word} ({names}) found ZERO confirmed bugs"
            )
        if any("no test functions found" in w for w in warn_records):
            shallow_bits.append(
                "the functional test file carries no recognised "
                "test functions"
            )
        detail = "; ".join(shallow_bits) if shallow_bits else (
            "a hollow-shape signal fired"
        )
        print(
            f"This run looks shallow: {detail}. A clean codebase "
            f"can legitimately have zero bugs, but a hollow / "
            f"shallow run also produces zero bugs (the 2026-05-25 "
            f"Ory Keto run4 shape — a fabricated EXPLORATION.md + "
            f"a no-op functional test + no bugs). Before trusting "
            f"this PASS, verify the run actually explored: "
            f"EXPLORATION.md cites real code paths; the role-map "
            f"enumerates the in-scope files; Phase 4 spec audits "
            f"ran against real specs. (v1.5.7 090s detection + "
            f"090v narration.)"
        )
    if weak_model:
        print("")
        print("Attribution: weak-model artifact")
        print(
            "  These results look like they came from a model "
            "that cut corners — they are not trustworthy. "
            "Re-run with a stronger reasoning model at higher "
            "effort before relying on this."
        )
    if env_failure:
        print("")
        print("Attribution: environment / setup problem")
        print(
            "  This run couldn't complete because the test "
            "environment failed — not because of the AI's "
            "analysis. Fix the environment (install missing "
            "tooling, restore network or pre-fetch dependencies, "
            "verify the build), then re-run Phases 5–6. "
            "Do NOT swap models; the model is not the problem."
        )
    if (not weak_model and not env_failure and not is_shallow_pass
            and exit_code == 0):
        print("")
        print(
            "Attribution: no shallow / fabrication signals "
            "detected — verdict reads as a real PASS."
        )

    # === Section 4: benign-WARN demotion ===
    if warn_records:
        actionable = [w for w in warn_records if not _is_benign_warn(w)]
        benign = [w for w in warn_records if _is_benign_warn(w)]
        if benign:
            n = len(benign)
            notice_word = "notice" if n == 1 else "notices"
            print("")
            print(
                f"({n} operational {notice_word} — safe to ignore: "
                f"documented back-compat / intended-default WARNs)"
            )
        if actionable:
            n = len(actionable)
            warn_word = "WARN" if n == 1 else "WARNs"
            print("")
            print(f"{n} actionable {warn_word} above — review:")
            # Quote a short prefix of each so the operator can
            # spot the topic without scrolling.
            for w in actionable:
                excerpt = w.strip().splitlines()[0][:120]
                print(f"  • {excerpt}")

    # === Section 5: run provenance (v1.5.7 090w) ===
    #
    # One block per repo. The runner is VERIFIED (env-detected via
    # the AI-CLI marker variables — the same ones the dual-env test
    # harness keys off). The model is SELF-REPORTED (read from
    # ``quality/results/run-*.json`` — demonstrably unreliable per
    # the 2026-05-25 NATS run2 dogfood where the agent wrote
    # "gpt-5.2" when the actual model was gpt-5.4; explicit confidence
    # label is load-bearing). The bug count is GATE-COUNTED
    # (verified — derived from BUG-NNN headings); a self-reported
    # bug_count that disagrees triggers an informational mismatch
    # flag. Provenance is informational only; never changes
    # pass/fail.
    if run_provenance:
        print("")
        print("── Run provenance ──")
        multi = len(run_provenance) > 1
        for entry in run_provenance:
            if multi:
                print(f"[{entry.get('repo', '<unknown repo>')}]")
            for line in _format_provenance_lines(entry):
                print(line)

    # === Section 6: newcomer orientation (v1.5.7 090y) ===
    #
    # Two plain-English sections written for someone who downloaded
    # QPB, ran it, and has no idea what they're looking at — zero
    # QPB knowledge assumed.
    #
    # Motivated by the 2026-05-25 Keto run6 (Copilot/gpt-5.3-codex):
    # the gate FAILED and an operator reading the output could see
    # *that* it failed but had **no idea what happened or what to
    # do next**.
    #
    # HARD RULE (per the instruction's "Branch correctly" pin):
    # the "stronger reasoning model" next-step appears ONLY for the
    # ``weak_model`` attribution. An honest coverage/artifact fail
    # (no attribution) MUST NOT tell the user to swap models.
    # Mutation-bite pinned by test_honest_fail_does_not_recommend_
    # stronger_model in test_what_happened_next_090y.py.
    _emit_what_happened_what_next(
        fail_records=fail_records,
        warn_records=warn_records,
        zero_bug_repos=zero_bug_repos,
        exit_code=exit_code,
        is_shallow_pass=is_shallow_pass,
        weak_model=weak_model,
        env_failure=env_failure,
        run_provenance=run_provenance,
    )

    print("───────────────────────────────────────────")


def _emit_what_happened_what_next(*, fail_records, warn_records,
                                    zero_bug_repos, exit_code,
                                    is_shallow_pass, weak_model,
                                    env_failure, run_provenance):
    """v1.5.7 090y — emit the "What happened" + "What to do next"
    newcomer-oriented sections at the END of the operator verdict
    block.

    Reads only the same accumulators the rest of the block uses
    (no new state; purely presentation). Determines which
    classifier categories fired so "What to do next" can branch
    correctly between weak_model / incomplete_verification /
    honest-fail / CLEANUP / shallow / solid.
    """
    # ----- Classifier reuse: determine which FAIL categories fired
    fired_categories: set[str] = set()
    for _cat, msg in fail_records:
        fired_categories.add(_classify_fail(msg))
    bugs_unverified_fired = _FAIL_BUGS_UNVERIFIED in fired_categories
    # Detect CLEANUP path (only record-keeping fails exist).
    cleanup_only = False
    if fail_records:
        substantive_count = sum(
            1 for cat, _msg in fail_records
            if cat == VERDICT_SUBSTANTIVE
        )
        cleanup_only = substantive_count == 0
    # Bug counts (gate-counted) — used to enrich the solid path.
    total_bug_count = 0
    if run_provenance:
        total_bug_count = sum(
            entry.get("bug_count_gate", 0) for entry in run_provenance
        )

    # ===== Section 6.1: "What happened" =====
    print("")
    print("── What happened ──")
    # Universal QPB-orientation lines (zero-jargon).
    print(
        "Quality Playbook reviewed this project's code in six "
        "phases — exploring it, deriving what it's supposed to "
        "do, reviewing the code against that, and verifying "
        "findings with tests."
    )
    print(
        "The gate is the final quality checkpoint that decides "
        "whether this run's results are trustworthy."
    )
    # State-specific summary line.
    if cleanup_only and exit_code == 0:
        # CLEANUP path — must read as a pass, not a fail.
        # (Instruction 090y Task A: "It passed, with some
        # bookkeeping gaps to tidy up".)
        print(
            "Result: it passed the checkpoint, with some "
            "bookkeeping gaps to tidy up (see 'Why it failed' "
            "above — these are audit record-keeping issues, "
            "not real defects)."
        )
    elif exit_code != 0:
        # ❌ FAILED — name the plain reason class.
        if bugs_unverified_fired:
            reason = (
                "the AI found issues but didn't verify them "
                "with tests"
            )
        elif weak_model:
            reason = (
                "the AI appears to have cut corners (low-effort "
                "test or unrun proofs)"
            )
        elif env_failure:
            reason = (
                "the test environment broke before the AI could "
                "complete its checks"
            )
        else:
            reason = (
                "the gate flagged quality issues that need "
                "fixing before this run can be trusted"
            )
        print(f"Result: it did not pass the checkpoint — {reason}.")
    elif is_shallow_pass:
        # ⚠️ shallow — name the why.
        shallow_reason_bits = []
        if zero_bug_repos:
            shallow_reason_bits.append("found no issues")
        if any("no test functions found" in w for w in warn_records):
            shallow_reason_bits.append(
                "the functional test file has no real tests"
            )
        if not shallow_reason_bits:
            shallow_reason_bits.append("hollow-shape signal fired")
        why = "; ".join(shallow_reason_bits)
        print(
            f"Result: it passed the checkpoint, but it looks "
            f"like it didn't dig deep ({why}) — treat the "
            f"result with caution."
        )
    else:
        # ✅ solid
        suffix = ""
        if total_bug_count > 0:
            issue_word = "issue" if total_bug_count == 1 else "issues"
            suffix = f" and verified {total_bug_count} {issue_word}"
        print(
            f"Result: it completed and passed cleanly{suffix}."
        )

    # ===== Section 6.2: "What to do next" =====
    print("")
    print("── What to do next ──")
    if cleanup_only and exit_code == 0:
        # CLEANUP — "Mostly good — a few bookkeeping artifacts
        # need tidying; see 'Why it failed' for which."
        print(
            "Mostly good — a few bookkeeping artifacts need "
            "tidying; see 'Why it failed' above for which "
            "audit records are missing."
        )
    elif exit_code != 0:
        # ❌ failed — BRANCH on attribution. Per the instruction's
        # "Branch correctly" pin: the "stronger model" advice
        # appears ONLY for the weak_model attribution. An honest
        # coverage/artifact fail must NOT tell the user to swap
        # models.
        if weak_model:
            print(
                "This looks like the AI cut corners — re-run "
                "with a stronger reasoning model at higher "
                "effort."
            )
        elif bugs_unverified_fired:
            print(
                "The AI found issues but didn't verify them "
                "with red/green tests — re-run to complete the "
                "test step, or treat the findings in "
                "quality/BUGS.md as candidates to check by "
                "hand."
            )
        elif env_failure:
            print(
                "The test environment failed (not the AI's "
                "analysis). Fix the environment (install "
                "missing tooling, restore network or pre-fetch "
                "dependencies, verify the build) then re-run. "
                "Do NOT swap models — the model is not the "
                "problem here."
            )
        else:
            # Honest fail — no attribution. The 2026-05-25 Keto
            # run6 shape. NEVER recommend stronger model here.
            n_fail = sum(
                1 for cat, _msg in fail_records
                if cat == VERDICT_SUBSTANTIVE
            )
            issue_word = "issue" if n_fail == 1 else "issues"
            extra = ""
            if total_bug_count > 0:
                extra = (
                    " The issues it did find are in "
                    "quality/BUGS.md."
                )
            print(
                f"The gate flagged {n_fail} {issue_word} with "
                f"this run — see 'Why it failed' above; address "
                f"those and re-run.{extra}"
            )
    elif is_shallow_pass:
        # ⚠️ shallow — verify the exploration, consider stronger
        # model. (Distinct from ❌ weak_model: shallow is a PASS,
        # and the stronger-model advice here is a "consider",
        # not a directive.)
        print(
            "Verify the run actually explored: look at "
            "quality/EXPLORATION.md (does it cite real code "
            "paths?) and quality/BUGS.md (what did it actually "
            "find?). Consider re-running with a stronger "
            "reasoning model for a deeper review."
        )
    else:
        # ✅ solid
        if total_bug_count > 0:
            issue_word = "issue" if total_bug_count == 1 else "issues"
            print(
                f"Review the {total_bug_count} confirmed "
                f"{issue_word} in quality/BUGS.md; proposed "
                f"fixes and their tests are in "
                f"quality/patches/ and quality/results/."
            )
        else:
            print(
                "Review quality/BUGS.md for confirmed issues; "
                "proposed fixes and their tests are in "
                "quality/patches/ and quality/results/."
            )


# v1.5.2 — REQ Pattern field (Lever 2)
VALID_PATTERN_VALUES = frozenset({"whitelist", "parity", "compensation"})

_REQ_PATTERN_RE = re.compile(
    r"^\s*-\s*Pattern:\s*(\S+)\s*$", re.IGNORECASE | re.MULTILINE
)


def extract_req_pattern(req_block):
    """Return the REQ's pattern tag from a REQUIREMENTS.md block, or None.

    Raises ValueError when the block carries an invalid pattern value. Valid
    values are VALID_PATTERN_VALUES. Absent field returns None.
    """
    m = _REQ_PATTERN_RE.search(req_block)
    if not m:
        return None
    value = m.group(1).strip()
    if value not in VALID_PATTERN_VALUES:
        raise ValueError(
            "Invalid REQ pattern '{}'. Expected one of: {}".format(
                value, sorted(VALID_PATTERN_VALUES)
            )
        )
    return value


# v1.5.2 — cardinality gate (Lever 3)

VALID_REASON_CLASSES = frozenset({
    "out-of-scope",
    "deprecated",
    "platform-gated",
    "handled-upstream",
    "intentionally-partial",
})

_CELL_ID_RE = re.compile(r"^REQ-\d+/cell-[A-Za-z0-9_]+-[A-Za-z0-9_]+$")

_COVERS_RE = re.compile(
    r"^\s*-\s*Covers:\s*\[(.*?)\]\s*$", re.IGNORECASE | re.MULTILINE
)

_CONSOLIDATION_RE = re.compile(
    r"^\s*-\s*Consolidation rationale:\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# v1.5.7 089d (F22): canonical BUG-NNN heading pattern.
#
# The canonical source is bin/run_state_lib.BUG_HEADING_PATTERN_STR
# (see that constant for rationale). quality_gate.py is INSTALLED
# STANDALONE into adopters' .github/skills/quality_gate/ and CANNOT
# import bin/run_state_lib (same Option-B-additive-duplication
# constraint as _INSTALL_MARKER_DIRS — see those lines above). The
# string literal below MUST match bin/run_state_lib.BUG_HEADING_PATTERN_STR
# exactly; the equality is pinned by
# bin/tests/test_bug_heading_pattern_pinned.py.
#
# Pre-089d this pattern was `^###\s+BUG-(\d+):` — digit-only with
# required colon. The canonical form below accepts BUG-001 +
# BUG-H1/M1/L1 (historical severity-prefixed IDs) + BUG-001-fix-2
# (hyphenated-suffix variants), and treats the title `: <text>` as
# optional. Widening to the canonical form was the 089d F22 fix.
_BUG_HEADING_PATTERN_STR_CANONICAL = (
    r"^###\s+BUG-([A-Za-z0-9][A-Za-z0-9\-]*)(?::\s+.+)?\s*$"
)
_BUG_HEADING_RE = re.compile(
    _BUG_HEADING_PATTERN_STR_CANONICAL, re.MULTILINE,
)

# v1.5.2 (C13.8/Fix 1) — evidence locator for present:true grid cells.
# Relative path (no leading '/'), single colon, line number (>=1) or
# range ``N-M`` with both endpoints >=1. Rejects: absolute paths,
# multi-slash roots, URLs, line zero, zero-endpoint ranges.
_EVIDENCE_RE = re.compile(r"^(?!/)[^:]+:[1-9]\d*(-[1-9]\d*)?$")


def _parse_covers(bug_block):
    m = _COVERS_RE.search(bug_block)
    if not m:
        return []
    raw = m.group(1).strip()
    if not raw:
        return []
    items = [s.strip() for s in raw.split(",")]
    return [s for s in items if s]


def _parse_consolidation_rationale(bug_block):
    m = _CONSOLIDATION_RE.search(bug_block)
    if not m:
        return None
    text = m.group(1).strip()
    return text or None


def _split_bug_blocks(bugs_md_text):
    """Return list of (bug_id, body) pairs."""
    positions = [(m.start(), m.group(1)) for m in _BUG_HEADING_RE.finditer(bugs_md_text)]
    result = []
    for idx, (start, bug_id) in enumerate(positions):
        end = positions[idx + 1][0] if idx + 1 < len(positions) else len(bugs_md_text)
        result.append(("BUG-{}".format(bug_id), bugs_md_text[start:end]))
    return result


def _bug_primary_requirement(block):
    m = re.search(
        r"^\s*-\s*Primary requirement:\s*(REQ-\d+)", block, re.MULTILINE | re.IGNORECASE
    )
    return m.group(1) if m else None


def _load_json_or_none(path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_text_safe(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


_REQ_HEADING_RE = re.compile(r"^###\s+(REQ-\d+):", re.MULTILINE)


def _enumerate_pattern_tagged_reqs(req_text):
    """Return {req_id: pattern} for every ### REQ-NNN: block in REQUIREMENTS.md
    that carries a ``- Pattern: <value>`` line.

    Raises ValueError if any block's pattern value is not in
    VALID_PATTERN_VALUES (delegated to extract_req_pattern()). Blocks without a
    Pattern field are omitted from the result (they're not pattern-tagged).
    """
    if not req_text:
        return {}
    positions = [(m.start(), m.group(1)) for m in _REQ_HEADING_RE.finditer(req_text)]
    result = {}
    for idx, (start, req_id) in enumerate(positions):
        end = positions[idx + 1][0] if idx + 1 < len(positions) else len(req_text)
        block = req_text[start:end]
        pattern = extract_req_pattern(block)
        if pattern is not None:
            result[req_id] = pattern
    return result


# v1.5.2 (C13.7/Fix 2) — per-site UC detection.
# Phase 1's Cartesian UC rule emits UC-N.a / UC-N.b / ... for REQs where both
# eligibility gates match. Any REQ block in REQUIREMENTS.md that cites such
# per-site UCs MUST carry a Pattern field — otherwise Phase 2 silently dropped
# it. The regex is deliberately narrow: one lowercase letter suffix only, word
# boundaries on both sides, so bare UC-N and over-suffixed UC-N.a.bad are not
# mistaken for per-site references.
_PER_SITE_UC_RE = re.compile(r"\bUC-\d+\.[a-z]\b")


def _enumerate_per_site_uc_reqs(req_text):
    """Return {req_id: sorted_list_of_uc_ids} for every ### REQ-NNN: block
    that cites at least one per-site UC reference (UC-N.a / UC-N.b / ...).

    REQ blocks without per-site UC references are omitted from the result.
    Each returned UC list is deduplicated and lexically sorted.
    """
    if not req_text:
        return {}
    positions = [(m.start(), m.group(1)) for m in _REQ_HEADING_RE.finditer(req_text)]
    result = {}
    for idx, (start, req_id) in enumerate(positions):
        end = positions[idx + 1][0] if idx + 1 < len(positions) else len(req_text)
        block = req_text[start:end]
        ucs = sorted(set(_PER_SITE_UC_RE.findall(block)))
        if ucs:
            result[req_id] = ucs
    return result


def validate_cardinality_gate(repo_dir):
    """Run the v1.5.2 cardinality reconciliation gate.

    Returns a list of failure strings. An empty list means the gate passed.
    Caller decides how to surface failures (print / fail()).

    Inputs expected in repo_dir/quality/:
      - REQUIREMENTS.md (source of pattern-tagged REQs)
      - BUGS.md (source of Covers: annotations)
      - compensation_grid.json (source of cell set per REQ)
      - compensation_grid_downgrades.json (optional; source of downgrade cells)
    """
    failures = []
    q = Path(repo_dir) / "quality"

    req_text = _read_text_safe(q / "REQUIREMENTS.md")

    # Enumerate pattern-tagged and per-site-UC REQs up front so the
    # downstream cross-checks can run regardless of whether a grid file
    # exists. A REQ that cites per-site UCs but lacks Pattern is a failure
    # independent of grid presence (in fact, if Pattern is missing there is
    # no grid precisely because Pattern is the trigger for producing one).
    try:
        pattern_tagged = _enumerate_pattern_tagged_reqs(req_text)
    except ValueError as exc:
        failures.append("REQUIREMENTS.md: {}".format(exc))
        pattern_tagged = {}
    try:
        per_site = _enumerate_per_site_uc_reqs(req_text)
    except ValueError as exc:
        failures.append("REQUIREMENTS.md: {}".format(exc))
        per_site = {}

    # Cross-check (C13.7/Fix 2): every REQ that cites per-site UCs (UC-N.a,
    # UC-N.b, ...) in REQUIREMENTS.md MUST carry a Pattern field. Per-site UCs
    # are the structural signal emitted by Phase 1's Cartesian UC rule; if the
    # signal is there but Pattern is missing, Phase 2 silently dropped it and
    # the v1.4.5 regression vector is live again. Runs regardless of grid
    # presence because missing Pattern is exactly what would cause the grid
    # to be absent in the first place.
    for req_id, uc_ids in per_site.items():
        if req_id not in pattern_tagged:
            failures.append(
                "cardinality gate: {} has per-site UCs ({}) in REQUIREMENTS.md "
                "but is missing the Pattern field — Phase 1 Cartesian UC rule "
                "requires Pattern tagging for cross-site REQs (see "
                "phase1_prompt confirmation checklist item 6)".format(
                    req_id, ", ".join(uc_ids)
                )
            )

    grid_path = q / "compensation_grid.json"
    grid = _load_json_or_none(grid_path)
    if grid is None:
        # No grid file: only a problem if any pattern-tagged REQs exist.
        if _REQ_PATTERN_RE.search(req_text):
            failures.append(
                "cardinality gate: pattern-tagged REQs exist but "
                "quality/compensation_grid.json is missing"
            )
        return failures

    reqs = grid.get("reqs") or {}
    if not isinstance(reqs, dict):
        failures.append("compensation_grid.json: 'reqs' is not an object")
        return failures

    # Cross-check: every pattern-tagged REQ in REQUIREMENTS.md must appear in
    # the grid. Omitting a pattern-tagged REQ from the grid was a v1.5.2 escape
    # hatch (silently skipped by the per-REQ reconcile loop); close it here.
    for req_id, req_pattern in pattern_tagged.items():
        if req_id not in reqs:
            failures.append(
                "cardinality gate: {} is pattern-tagged '{}' in REQUIREMENTS.md "
                "but has no entry in compensation_grid.json".format(req_id, req_pattern)
            )

    # Load BUGS.md and index covers by REQ
    bugs_text = _read_text_safe(q / "BUGS.md")
    covers_by_req = {}
    for bug_id, block in _split_bug_blocks(bugs_text):
        covers = _parse_covers(block)
        if len(covers) >= 2:
            if not _parse_consolidation_rationale(block):
                failures.append(
                    "{}: Covers has {} entries but 'Consolidation rationale:' is missing or empty".format(
                        bug_id, len(covers)
                    )
                )
        for cell_id in covers:
            if not _CELL_ID_RE.match(cell_id):
                failures.append(
                    "{}: malformed cell ID '{}' (expected REQ-N/cell-<item>-<site>)".format(
                        bug_id, cell_id
                    )
                )
                continue
            req_id = cell_id.split("/", 1)[0]
            covers_by_req.setdefault(req_id, set()).add(cell_id)

    # Load downgrades and validate each record
    downgrades = _load_json_or_none(q / "compensation_grid_downgrades.json") or {"downgrades": []}
    downgrade_cells_by_req = {}
    for rec in downgrades.get("downgrades", []):
        rid = rec.get("cell_id", "")
        if not _CELL_ID_RE.match(rid):
            failures.append("downgrade record: malformed cell_id '{}'".format(rid))
            continue
        # A downgrade record only counts toward reconciliation once every
        # validation below passes. A malformed record emits diagnostic
        # failure strings AND stays out of downgrade_cells_by_req, so the
        # per-REQ uncovered-cells calculation still flags the cell.
        rec_ok = True
        for field in ("authority_ref", "site_citation", "reason_class", "falsifiable_claim"):
            value = rec.get(field)
            if not value or not isinstance(value, str) or not value.strip():
                failures.append(
                    "downgrade record {}: missing or empty field '{}'".format(rid, field)
                )
                rec_ok = False
        reason = rec.get("reason_class", "")
        if reason and reason not in VALID_REASON_CLASSES:
            failures.append(
                "downgrade record {}: reason_class '{}' not in {}".format(
                    rid, reason, sorted(VALID_REASON_CLASSES)
                )
            )
            rec_ok = False
        if not rec_ok:
            continue
        req_id = rid.split("/", 1)[0]
        downgrade_cells_by_req.setdefault(req_id, set()).add(rid)

    # Reconcile per-REQ
    for req_id, entry in reqs.items():
        pattern = entry.get("pattern")
        if pattern not in {"whitelist", "parity", "compensation"}:
            failures.append(
                "compensation_grid.json: {} has invalid or missing pattern '{}'".format(
                    req_id, pattern
                )
            )
            continue
        cells = entry.get("cells") or []
        # v1.5.2 (C13.8/Fix 2): pre-validate each cell's 'present' field is a
        # strict bool. Non-bool values (string "true", int 1, None, missing key)
        # would otherwise fall between the 'is False' absent-cell branch and
        # the 'is not True' present-cell evidence branch, escaping both checks.
        # Same silent-bypass family as B1 — diagnose AND skip the cell, do not
        # let it count toward coverage accounting.
        valid_cells = []
        for c in cells:
            if not isinstance(c, dict):
                continue
            present = c.get("present")
            if not isinstance(present, bool):
                cell_id = c.get("cell_id") or "<no cell_id>"
                failures.append(
                    "{}: cell {} 'present' must be boolean true or false; got {!r}".format(
                        req_id, cell_id, present
                    )
                )
                continue
            valid_cells.append(c)

        grid_cell_ids = {c.get("cell_id") for c in valid_cells}
        grid_cell_ids.discard(None)
        # Only absent cells require coverage. Identity check is safe now —
        # every element of valid_cells has 'present' as a strict bool.
        absent_cells = {
            c.get("cell_id") for c in valid_cells
            if c.get("present") is False
        }
        absent_cells.discard(None)

        # v1.5.2 (C13.6/B2): present:true cells must carry a non-empty
        # 'evidence' field in file:line form. Without this, a reviewer or LLM
        # can claim any cell is present, supply nothing, and the gate accepts
        # it — the bypass Round 5 Council called the highest remaining risk.
        for c in valid_cells:
            if c.get("present") is not True:
                continue
            cell_id = c.get("cell_id") or "<no cell_id>"
            evidence = c.get("evidence")
            if not evidence or not isinstance(evidence, str) or not evidence.strip():
                failures.append(
                    "{}: present:true requires non-empty 'evidence' field with file:line citation".format(cell_id)
                )
                continue
            if not _EVIDENCE_RE.match(evidence.strip()):
                failures.append(
                    "{}: 'evidence' must be file:line (e.g. 'path/to.c:123' or 'path/to.c:120-140'); got {!r}".format(
                        cell_id, evidence
                    )
                )

        covered = covers_by_req.get(req_id, set())
        downgraded = downgrade_cells_by_req.get(req_id, set())
        uncovered = absent_cells - covered - downgraded

        if uncovered:
            failures.append(
                "{}: uncovered cells — {}".format(req_id, ", ".join(sorted(uncovered)))
            )

        # Every covered cell must be in the grid
        stray = (covered | downgraded) - grid_cell_ids
        if stray:
            failures.append(
                "{}: Covers/downgrade cells not in grid — {}".format(
                    req_id, ", ".join(sorted(stray))
                )
            )

    return failures


def _reset_counters():
    global FAIL, WARN
    FAIL = 0
    WARN = 0
    # v1.5.7 089c (F15): clear the per-fail category ledger and the
    # category context stack so a fresh main()/check_repo run starts
    # clean (tests that call check_repo directly must reset too).
    _FAIL_RECORDS.clear()
    _CHECK_CATEGORY_STACK.clear()
    # v1.5.7 090s Task B: also clear the zero-bug-repos tracker so
    # the verdict qualifier doesn't carry stale state across runs.
    _ZERO_BUG_REPOS.clear()
    # v1.5.7 090v: also clear the WARN ledger so the operator verdict
    # layer reads only this run's WARNs.
    _WARN_RECORDS.clear()
    # v1.5.7 090w: clear the per-repo run-provenance ledger so the
    # verdict layer reads only this run's provenance.
    _RUN_PROVENANCE.clear()
    # v1.5.10 058 (D2): clear the per-repo multi-language disclosure
    # ledger so the post-RESULT disclosure block reads only this run.
    _LANGUAGE_DISCLOSURES.clear()


def fail(msg, reason=None, *, line=None, category=None):
    """Emit a structured failure line and increment FAIL.

    Phase 5 r3 format: `<path>[:<line>]: <reason>` — no "FAIL:" label, so
    output is grep-parseable as `^[^:]+:[0-9]*:? .+$`. The prefix `FAIL:` is
    deliberately removed; the global FAIL counter (summarised in main()) is
    the authoritative count of failures per run.

    Preferred forms:
        fail("quality/INDEX.md", "file missing")
            -> "  quality/INDEX.md: file missing"
        fail("quality/INDEX.md", "missing required field 'x'", line=42)
            -> "  quality/INDEX.md:42: missing required field 'x'"

    Legacy single-arg form (transitional; still supported — most v1.4.x
    messages already embed a path-like token):
        fail("BUGS.md missing or not a file")
            -> "  BUGS.md missing or not a file"

    v1.5.7 089c (F15): every fail is tagged with a verdict category
    ("substantive" | "record_keeping"). When `category` is None the
    enclosing @verdict_category check's category is used (top of
    _CHECK_CATEGORY_STACK); when the stack is empty the conservative
    default VERDICT_SUBSTANTIVE applies (an un-decorated caller's failure
    is treated as blocking, never silently downgraded to cleanup).
    main() splits _FAIL_RECORDS by category for the three-state verdict.
    """
    global FAIL
    if reason is None:
        rendered = f"  {msg}"
    elif line is None:
        rendered = f"  {msg}: {reason}"
    else:
        rendered = f"  {msg}:{line}: {reason}"
    print(rendered)
    FAIL += 1
    if category is None:
        category = (
            _CHECK_CATEGORY_STACK[-1]
            if _CHECK_CATEGORY_STACK
            else VERDICT_SUBSTANTIVE
        )
    elif category not in _VALID_VERDICT_CATEGORIES:
        raise ValueError(
            f"fail(): category {category!r} not in "
            f"{_VALID_VERDICT_CATEGORIES}"
        )
    _FAIL_RECORDS.append((category, rendered.strip()))


def pass_(msg):
    print(f"  PASS: {msg}")


def warn(msg):
    global WARN
    print(f"  WARN: {msg}")
    WARN += 1
    # v1.5.7 090v: record the message body for the operator verdict-
    # explanation layer. The print + counter above are the load-
    # bearing legacy behaviour (downstream consumers parse the print
    # stream and the counter feeds total_line); the list is purely
    # presentation-layer fuel.
    _WARN_RECORDS.append(msg)


def info(msg):
    print(f"  INFO: {msg}")


# --- JSON helpers (proper parsing, not grep-style) ---


def load_json(path):
    """Parse JSON file. Return parsed value, or None on any error."""
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def has_key(data, key):
    """True if `data` is a dict containing `key`."""
    return isinstance(data, dict) and key in data


def get_str(data, key):
    """Return data[key] if it's a string, else empty string."""
    if not isinstance(data, dict):
        return ""
    val = data.get(key)
    return val if isinstance(val, str) else ""


def count_per_bug_field(bugs_list, field):
    """Count bugs in list that have `field` set."""
    if not isinstance(bugs_list, list):
        return 0
    return sum(1 for b in bugs_list if isinstance(b, dict) and field in b)


# --- File helpers ---


# v1.5.7 fix F-4a: dropped the v1.5.4 dual-layout workspace tolerance.
# Canonical artifact paths are top-level quality/<name>/ per README
# spec. The companion check_no_workspace_dir below fails loudly if
# workspace/ exists at all (even empty), so spec drift becomes visible —
# instruction 031 F-4 amendment extended the original "exists with
# content" check to also fail on empty workspace/ directories
# (claude-opus-4.6/express produced an empty workspace/ left over
# from a runner pass with nothing to move, which still trained
# subsequent iterations on the wrong layout via in-context retrieval).


def _resolve_artifact_path(quality_dir, name):
    """Return the canonical path for an intermediate artifact directory
    or file under quality/. Path is always top-level quality/<name>
    per README spec. Returns the path even when it doesn't exist so
    callers that test ``.is_dir()`` / ``.is_file()`` get a False
    rather than an exception.

    ``name`` may be a single segment (``"results"``) or a path with
    segments (``"results/tdd-results.json"``)."""
    return quality_dir / name


@verdict_category(VERDICT_SUBSTANTIVE)
def check_no_workspace_dir(q):
    """v1.5.7 fix F-4a (Phase 6 gate): artifacts must be at canonical
    quality/<name>/ paths, NOT quality/workspace/<name>/. The
    workspace/ layout was tolerated through v1.5.6 but is non-spec per
    README; agents writing there are following stale prose. Fail
    loudly so the spec drift becomes visible.

    v1.5.7 fix F-4 amendment (instruction 031): also fail when
    quality/workspace/ exists as an empty directory. Model-comparison
    evidence (claude-opus-4.6/express) showed an empty workspace/
    directory left over from a runner pass with nothing to move.
    Empty workspace/ is a breadcrumb that trains future-iteration
    agents on the wrong layout even when nothing's there yet."""
    print("[Workspace Drift]")
    workspace = q / "workspace"
    if not workspace.exists():
        pass_("no non-canonical quality/workspace/ tree present")
        return
    if not workspace.is_dir():
        fail(
            "quality/workspace",
            f"exists but is not a directory: {workspace}",
        )
        return
    children = list(workspace.iterdir())
    if children:
        contents = sorted(p.name for p in children)
        fail(
            "quality/workspace/",
            f"contains {contents} — artifacts must be at canonical "
            f"quality/<name>/ paths per README spec. Move contents "
            f"to top-level quality/ and remove workspace/.",
        )
        return
    # Empty workspace/ — breadcrumb that trains agents on wrong layout.
    fail(
        "quality/workspace/",
        "exists as an empty directory. Empty workspace/ trains "
        "agents to write artifacts there. Remove the directory "
        "entirely.",
    )


_VERDICT_HEADING_RE = re.compile(r"^##\s+Verdict\s*$", re.MULTILINE)
# v1.5.7 instruction 032 NCF-1: regex matching any level-2 `## ` heading
# (any text after `## `). Used to find ALL level-2 headings so the
# verdict-shape check can assert (a) exactly one `## Verdict` and
# (b) `## Verdict` is the terminal `## ` heading (no other `## `
# heading appears after it).
_ANY_LEVEL2_HEADING_RE = re.compile(r"^##\s+\S.*$", re.MULTILINE)
# v1.5.7 instruction 032 NCF-9: "TBD" removed — `phrase.lower()` is
# called below before substring matching, so an uppercase "TBD" entry
# was redundant with the lowercase "tbd" entry.
_VERDICT_PLACEHOLDER_PHRASES = (
    "verdict is rendered",
    "verdict will be",
    "verdict will follow",
    "placeholder",
    "to be determined",
    "tbd",
)


# v1.5.7 089d (F24): classification rationale — kept SUBSTANTIVE.
# check_verdict_shape rejects COMPLETENESS_REPORT.md when the
# `## Verdict` heading is missing OR when its value is missing /
# placeholder ("verdict is rendered…", "tbd", etc.) OR when a
# trailing level-2 heading shifts `## Verdict` off the terminal
# position. Each of these failure modes means Phase 5 reconciliation
# did NOT declare a verdict — the audit lacks its final
# PASS/FAIL judgment. That is "the work wasn't done correctly"
# (no verdict exists), not "the audit completed but the paperwork
# has gaps". The opus-bootstrap baseline 4 FAILs include
# `## Verdict` missing on its self-bootstrap COMPLETENESS_REPORT.md,
# but the substantive reading (Phase 5 didn't finish writing the
# verdict block) is correct — flipping to RECORD_KEEPING would
# silently downgrade a fabricated-PASS-style failure.
@verdict_category(VERDICT_SUBSTANTIVE)
def check_verdict_shape(q):
    """v1.5.7 Fix 8 (instruction 031) + instruction 032 NCF-1: Phase 5
    must end COMPLETENESS_REPORT.md with the canonical verdict shape:

        ## Verdict

        PASS

    or

        ## Verdict

        FAIL

    Model-comparison evidence (instruction 031): verdict prose varies
    wildly across models (`## Verdict`, `## Status`, `VERDICT: PASS`,
    prose-only, placeholder text like "verdict is rendered after
    Phase 6"). The strict shape gives operators a single grep target
    and gives the gate something concrete to enforce.

    Instruction 032 NCF-1: also require that `## Verdict` appears
    EXACTLY ONCE and is the LAST level-2 heading in the file (terminal
    position). Without this, a stale earlier `## Verdict\\n\\nPASS` block
    silently passes even when a later `## Postmortem` (or another
    `## Verdict`) heading contradicts it.

    FAIL outcomes:
    - COMPLETENESS_REPORT.md missing entirely.
    - `## Verdict` heading absent (e.g., agent wrote `## Status`).
    - More than one `## Verdict` heading (NCF-1: duplicate-heading
      rejection).
    - A level-2 heading appears after the `## Verdict` heading
      (NCF-1: non-terminal-position rejection).
    - Next non-blank line after the heading is not exactly `PASS`
      or `FAIL` (case-sensitive; `Passed`, `PASSED`, `PASS!`,
      `**PASS**` all fail).
    - Next non-blank line is empty (heading present, no value
      follows — NCF-5: empty-body rejection).
    - Next non-blank line contains a placeholder phrase ("verdict
      is rendered", "tbd", "placeholder", etc.).
    """
    print("[Verdict Shape]")
    cr = q / "COMPLETENESS_REPORT.md"
    if not cr.is_file():
        fail(
            "quality/COMPLETENESS_REPORT.md",
            "missing — Phase 5 must produce this file with a "
            "canonical ## Verdict / PASS|FAIL section.",
        )
        return
    try:
        text = cr.read_text(encoding="utf-8", errors="replace")
    except OSError:
        fail("quality/COMPLETENESS_REPORT.md", "unreadable")
        return
    # v1.5.7 instruction 032 NCF-1/NCF-2: enumerate ALL level-2
    # headings to enforce single-and-terminal position (NCF-1) plus
    # the bite tests that exercise the duplicate-heading and
    # non-terminal-heading branches (NCF-2). The `_ANY_LEVEL2_HEADING_RE`
    # pattern matches `## Anything`; the `_VERDICT_HEADING_RE` pattern
    # matches `## Verdict` exactly. Together they let the function
    # answer "is this the only `## Verdict`?" and "is it the last
    # `## ` heading in the file?".
    all_headings = [
        (m.start(), m.group(0))
        for m in _ANY_LEVEL2_HEADING_RE.finditer(text)
    ]
    verdict_matches = list(_VERDICT_HEADING_RE.finditer(text))
    if not verdict_matches:
        fail(
            "quality/COMPLETENESS_REPORT.md",
            "missing the canonical `## Verdict` heading. Phase 5 "
            "reconciliation must add it (exact form: `## Verdict` "
            "on its own line, followed by a blank line and then "
            "`PASS` or `FAIL`).",
        )
        return
    if len(verdict_matches) > 1:
        positions = [m.start() for m in verdict_matches]
        fail(
            "quality/COMPLETENESS_REPORT.md",
            f"contains {len(verdict_matches)} `## Verdict` headings "
            f"(byte offsets {positions}). Phase 5 must emit exactly "
            f"one canonical verdict block; duplicate headings can "
            f"silently disagree.",
        )
        return
    verdict_match = verdict_matches[0]
    # Terminal-position check: the verdict heading must be the LAST
    # `## ` heading in the file. Any `## Postmortem`, `## Followups`,
    # `## Other` etc. heading after it shifts the verdict block away
    # from its terminal position.
    if all_headings and all_headings[-1][0] != verdict_match.start():
        trailing_headings = [
            h_text for h_start, h_text in all_headings
            if h_start > verdict_match.start()
        ]
        fail(
            "quality/COMPLETENESS_REPORT.md",
            f"`## Verdict` is not the last level-2 heading. "
            f"Headings appear after it: {trailing_headings}. The "
            f"canonical shape requires the verdict block to be "
            f"terminal so an operator can grep the file's tail for "
            f"the verdict.",
        )
        return
    # Find the next non-blank line after the verdict heading.
    after = text[verdict_match.end():]
    next_line = ""
    for line in after.splitlines():
        if line.strip():
            next_line = line.strip()
            break
    if not next_line:
        # v1.5.7 instruction 032 NCF-5: empty-body rejection now
        # explicitly bite-tested.
        fail(
            "quality/COMPLETENESS_REPORT.md",
            "has `## Verdict` heading but no verdict value follows. "
            "Add `PASS` or `FAIL` on the next non-blank line.",
        )
        return
    # Placeholder-phrase detection — case-insensitive across the
    # whole next line, because agents sometimes embed the phrase in
    # explanatory prose.
    lowered = next_line.lower()
    for phrase in _VERDICT_PLACEHOLDER_PHRASES:
        if phrase.lower() in lowered:
            fail(
                "quality/COMPLETENESS_REPORT.md",
                f"verdict line is a placeholder stub: "
                f"{next_line!r}. Phase 5 must render an actual "
                f"PASS or FAIL verdict, not deferred text.",
            )
            return
    if next_line == "PASS" or next_line == "FAIL":
        pass_(f"COMPLETENESS_REPORT.md verdict shape canonical ({next_line})")
        return
    fail(
        "quality/COMPLETENESS_REPORT.md",
        f"verdict line is {next_line!r} — must be exactly `PASS` "
        f"or `FAIL` (uppercase, no surrounding text or emphasis).",
    )


@verdict_category(VERDICT_RECORD_KEEPING)
def check_bugs_md_patches_consistency(q, bug_count, bug_ids):
    """v1.5.7 Fix 7 (instruction 031): the patches/ directory and
    BUGS.md must be consistent — patches without corresponding bug
    entries indicate Phase 3 finalization didn't update BUGS.md.

    Model-comparison evidence (claude-haiku-4.5/zod: 14 patches / 0
    bugs; claude-haiku-4.5/casbin: 16/0; gpt-5.4-mini/zod: 8/0;
    gpt-5.4-mini/axum: 6/0) showed agents producing evidence-bearing
    patches while leaving BUGS.md empty.

    Hard fail: bugs_count == 0 AND patches_count > 0 (the model-
    comparison failure mode). When BUGS.md has entries, every patch
    must have its bug ID in BUGS.md; orphan IDs fail. No upper bound
    on per-bug patch count — multi-patch workflows (one bug requiring
    multiple fix patches in different files) are legitimate.

    v1.5.7 instruction 032 NCF-4: patch-file counting uses a set
    union across the two globs so a file matching both
    (`*-fix*.patch` AND `*-regression-test*.patch`) is counted once,
    not twice. The intervening `*` wildcard in `*-fix*.patch` would
    otherwise inflate the count for hybrid-named files.

    v1.5.7 instruction 032 NCF-7: dropped the `patches_count <=
    bug_count * 2` upper bound. The upper bound false-positives on
    legitimate split-patch workflows (e.g., one bug requiring fixes
    in 3 different files = 3 fix patches + 1 regression test = 4
    patches for 1 bug). The orphan-ID check already detects patches
    for bugs not in BUGS.md, which is the real defect signal.
    """
    print("[BUGS.md / patches consistency]")
    patches_dir = q / "patches"
    if not patches_dir.is_dir():
        # No patches — no consistency to check. Other gates will
        # complain if patches are missing for confirmed bugs.
        info("No patches/ directory — consistency check skipped")
        return
    # v1.5.7 instruction 032 NCF-4: set union deduplicates files
    # matching both globs. The `*` in `*-fix*.patch` can match a
    # file named `BUG-NNN-regression-test-fix.patch` (or any other
    # file whose name happens to contain both "-fix" and
    # "-regression-test"), which would otherwise be counted twice.
    fix_patches = set(patches_dir.glob("*-fix*.patch"))
    regr_patches = set(patches_dir.glob("*-regression-test*.patch"))
    # v1.5.7 instruction 033 Halt-5: filter out malformed-name patches
    # (files matching the glob but not starting with `BUG-NNN` / `BUG-HNN`
    # / `BUG-MNN` / `BUG-LNN`) BEFORE counting and orphan-ID inference.
    # Pre-Halt-5 a file like `misc-cleanup-fix.patch` was counted toward
    # patches_count but silently skipped by the BUG-NNN regex below, so
    # it could mask the consistency check. The filter promotes "stray
    # malformed file present" to "consistency check skipped" rather than
    # "silently accepted".
    patch_re = re.compile(r"^(BUG-(?:[HML][0-9]+|[0-9]+))[-.]")
    glob_matched = sorted(fix_patches | regr_patches)
    all_patches = [p for p in glob_matched if patch_re.match(p.name)]
    malformed_patches = sorted(
        p.name for p in glob_matched if not patch_re.match(p.name)
    )
    if malformed_patches:
        # Surface the malformed names as a WARN so operators can
        # rename or remove them before the next run; the consistency
        # check itself only considers BUG-NNN-named patches below.
        warn(
            f"quality/patches/ contains {len(malformed_patches)} "
            f"file(s) matching the patch glob but not the canonical "
            f"BUG-NNN naming convention: {malformed_patches}. The "
            f"consistency check ignores them. Rename or remove them "
            f"so the gate has unambiguous patch inventory."
        )
    patches_count = len(all_patches)
    if patches_count == 0:
        info("No fix/regression patches present — consistency check skipped")
        return
    if bug_count == 0:
        # The model-comparison failure mode: patches without bugs.
        patch_names = sorted(p.name for p in all_patches)
        fail(
            "quality/BUGS.md",
            f"lists 0 bug entries but quality/patches/ contains "
            f"{patches_count} patch file(s): {patch_names}. Each "
            f"confirmed bug should produce at least 1 patch. "
            f"Mismatch suggests Phase 3 finalization didn't update "
            f"BUGS.md with the bugs that produced these patches.",
        )
        return
    # BUGS.md has entries — check patch IDs vs bug IDs.
    patch_ids = set()
    for p in all_patches:
        m = patch_re.match(p.name)
        if m:
            patch_ids.add(m.group(1))
    orphan_patch_ids = sorted(patch_ids - set(bug_ids))
    if orphan_patch_ids:
        fail(
            "quality/BUGS.md",
            f"missing entries for patch IDs {orphan_patch_ids} — "
            f"patches exist at quality/patches/ for these IDs but "
            f"BUGS.md has no ### BUG-NNN heading for them. Each "
            f"confirmed bug must be reflected in BUGS.md.",
        )
        return
    # v1.5.7 instruction 032 NCF-7: upper bound dropped. Multi-patch
    # workflows (one bug requiring several fix patches across files)
    # are legitimate; the orphan-ID check already catches the real
    # defect (patches for bugs not in BUGS.md).
    pass_(
        f"BUGS.md ({bug_count} bug(s)) and patches/ "
        f"({patches_count} patch(es)) are consistent"
    )


def has_file_matching(directory, patterns):
    """True if any file in `directory` (non-recursive) matches any glob pattern."""
    if not directory.is_dir():
        return False
    for pat in patterns:
        for _ in directory.glob(pat):
            return True
    return False


def count_files_matching(directory, pattern):
    """Count files in `directory` (non-recursive) matching glob pattern."""
    if not directory.is_dir():
        return 0
    return sum(1 for _ in directory.glob(pattern))


def first_file_matching(directory, patterns):
    """Return first matching path or None."""
    if not directory.is_dir():
        return None
    for pat in patterns:
        for p in directory.glob(pat):
            return p
    return None


def file_contains(path, pattern):
    """True if any line in file matches pattern (regex string or compiled)."""
    if not path.is_file():
        return False
    if isinstance(pattern, str):
        pattern = re.compile(pattern)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if pattern.search(line):
                    return True
    except OSError:
        pass
    return False


def read_first_line_stripped(path):
    """Return first line of file with whitespace stripped."""
    if not path.is_file():
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            line = f.readline()
    except OSError:
        return ""
    return re.sub(r"\s", "", line)


def read_full_text(path):
    """Return the full file body as text, or '' on any IO error.

    v1.5.7 089o: the TDD-receipt overclaim check needs the WHOLE
    receipt body (not just the first-line tag) to scan for non-
    execution markers. read_first_line_stripped covers the tag;
    this covers the body."""
    if not path.is_file():
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


# v1.5.7 089o (#329): non-execution markers. A TDD receipt whose
# first-line tag is RED or GREEN asserts the test was actually
# run; if its agent-authored summary ALSO contains one of these
# phrases it is an overclaim — a by-inspection prediction
# mislabeled as an empirical result — and the gate FAILs it. The
# 2026-05-21 gson run recorded all 15 receipts RED/GREEN with
# bodies reading "VERIFIED BY INSPECTION (sandbox cannot compile
# gson; Maven is not available)" on a machine where Maven was
# installed and on PATH. Matched case-insensitively as substrings
# against the receipt's SUMMARY REGION only (v1.5.7 089q D1 —
# see _receipt_summary_region; the runner transcript is off-
# limits). NOT matched against NOT_RUN receipts — NOT_RUN + an
# honest non-execution explanation is exactly correct (the 089m
# honest-skip WARN path).
# v1.5.7 089q (D1): NARROWED to unambiguous self-admissions only.
# The 089o list also carried runner-output-collision phrases —
# "cannot compile", "can't compile", "not available", "no maven",
# "no test runner", "cannot run" / "could not run" / "couldn't run"
# — which legitimately appear in REAL runner/compiler output. A
# red-phase TDD test that genuinely doesn't compile yet (the
# canonical RED scenario) emits "cannot compile"; runner stderr
# emits "module X not available". Matching those as raw substrings
# FAILed the exact honest case 089o exists to protect. 089q keeps
# ONLY phrases an agent writes when narrating that it did NOT run
# the test — phrases that do not occur in ordinary runner output —
# AND scans them only in the agent-authored summary region (see
# _receipt_summary_region). The false-negatives this narrowing
# opens up are closed by the D2 positive-execution-evidence
# requirement, not by a broad marker net.
_TDD_OVERCLAIM_MARKERS = (
    "by inspection",
    "verified by inspection",
    "did not execute",
    "not executed",
    "without running",
    "without executing",
    "predictions, not observations",
    "i assumed",
    "sandbox cannot",
)

# v1.5.7 089q (D2): affirmative execution signatures. When the
# Phase 5 probe shows the runner available, a RED/GREEN receipt
# MUST carry at least one of these — structured evidence the test
# was actually run. The documented receipt format
# (references/phase2_generation_guide.md log-capture template)
# mandates a `Command:` line and an `Exit code:` line, so a
# legitimately-executed receipt always has them; the runner-
# transcript tokens are a secondary signal for receipts that don't
# follow the exact template. None of these occur in a by-inspection
# / paraphrased-prediction narration, so a paraphrase-evasion
# receipt (no marker, no transcript) is caught by their absence.
_TDD_EXECUTION_SIGNATURES = (
    "command:",            # documented log-format Command: line
    "exit code:",          # documented log-format Exit code: line
    "exit_code:",
    "tests run:",          # JUnit / Maven Surefire summary
    "build success",       # Maven
    "build failure",       # Maven
    "test session starts",  # pytest session banner
    "test result:",        # cargo test summary
    "--- fail:",           # go test
    "--- pass:",           # go test
)


def _receipt_summary_region(body):
    """Return the agent-authored leading narration of a TDD receipt
    — the lines AFTER the first-line status tag and BEFORE the
    first runner-transcript boundary (a ``` fence, or a line
    starting ``Command:`` / ``Exit code:`` / ``--- Test output``).

    v1.5.7 089q (D1): overclaim markers are scanned ONLY here, so a
    phrase like "cannot compile" quoted from genuine runner output
    in the transcript region cannot trigger a false overclaim
    FAIL. The summary region is where an agent writes a by-
    inspection admission; the transcript region is captured tool
    output and is off-limits to the marker scan."""
    region = []
    for i, line in enumerate(body.splitlines()):
        if i == 0:
            continue  # the first-line status tag
        stripped = line.strip()
        low = stripped.lower()
        if (stripped.startswith("```")
                or low.startswith("command:")
                or low.startswith("exit code:")
                or low.startswith("exit_code:")
                or low.startswith("--- test output")):
            break
        region.append(line)
    return "\n".join(region)


def _first_overclaim_marker(body):
    """Return the first non-execution marker found in the receipt's
    agent-authored summary region (case-insensitive), or None.
    Used to FAIL a RED/GREEN receipt whose summary admits the test
    was not actually run. v1.5.7 089q (D1): scans only
    _receipt_summary_region, never the runner transcript."""
    low = _receipt_summary_region(body).lower()
    for marker in _TDD_OVERCLAIM_MARKERS:
        if marker in low:
            return marker
    return None


def _has_execution_signature(body):
    """True if the receipt body carries at least one affirmative
    execution signature (v1.5.7 089q D2) — structured evidence the
    test was actually run. Scanned over the WHOLE body (the
    signature lives in the transcript region, exactly where the
    summary-region marker scan does NOT look)."""
    low = body.lower()
    return any(sig in low for sig in _TDD_EXECUTION_SIGNATURES)


# v1.5.7 090p: gate-level RED-validity check. A red receipt counts
# as a valid RED only if its log shows the test actually executed
# and failed — a test-level/assertion failure — NOT a
# setup/build/dependency/collection failure. The 2026-05-24 Ory
# Keto run2 (cold Go caches + network-restricted sandbox) reported
# `RESULT: GATE PASSED` on three reds whose bodies were
# `FAIL [setup failed]` / `lookup proxy.golang.org: no such host`
# — a dependency-resolution failure proved nothing about whether
# the bug exists, but the gate accepted any non-zero exit as a
# satisfied red. 090p closes this hole mechanically (090o's prose-
# side env-vs-real-RED guard is the prompt-side companion; 090p
# is the gate-level backstop because run2 proved prose alone
# doesn't bind).
#
# Conservative-direction guard: only reject reds matching a KNOWN
# setup-failure signature AND lacking a recognized "genuine
# test-level failure" signature. A non-zero red that is neither
# (e.g. an unknown ecosystem's runner output) stays a genuine red
# — the safety direction per 089m–q is "under-escalate ambiguity,
# never wrongly fail an honest run." See _is_red_setup_failure
# below for the exact decision rule.

_RED_SETUP_FAILURE_SIGNATURES = (
    # Go (the run2 trigger).
    "[setup failed]",
    "no such host",                 # proxy.golang.org / DNS
    "dependency resolution failed",
    "cannot find package",
    "build failed",
    "go: download",                  # go: download X: ...
    "go: github.com/",               # go: github.com/.../...: cannot find module
    "go: module ",
    # pytest (collection-time failures).
    "internalerror",                # pytest infra crash
    "errors during collection",
    "collection error",
    "modulenotfounderror",
    "importerror",
    # Maven / Gradle / Java (build-side failures preceding any test run).
    "could not resolve dependencies",
    "unresolved dependency",
    "build failure",                # also a Maven success-line sibling — paired with no genuine-fail signature below
    # Generic (cargo / npm / others — best-effort).
    "could not compile",
    "could not download",
    "network is unreachable",
    "connection refused",
    "connection timed out",
)

_RED_GENUINE_FAILURE_SIGNATURES = (
    # Go — the canonical test-level failure shape.
    "--- fail: test",
    # pytest — the test-ran-and-failed nodeid line ("FAILED <path>::<test>").
    "failed test",                  # pytest "FAILED test_x.py::test_y" line (case-insensitive)
    "failed — ",               # em-dash form
    # JUnit / Maven Surefire — explicit test-failure lines (not build failures).
    "tests run:",                   # Surefire summary line; per 089q is an execution signature, also a genuine-test-ran marker
    # cargo — explicit test-failure line.
    "thread '",                     # "thread '<test name>' panicked at"
)


def _is_red_setup_failure(body):
    """v1.5.7 090p Task A: True iff the red-receipt body looks like a
    setup/build/dependency/collection failure — i.e. NOT a genuine
    test-level assertion failure.

    Decision rule (conservative direction per 089m–q):
      * If the body contains ANY ``_RED_GENUINE_FAILURE_SIGNATURES``
        substring → the test ran and failed (genuine RED); return
        False even if a setup-failure substring is also present
        (the runner output may legitimately mention "build failure"
        in a multi-package run where some packages built and others
        failed-after-running).
      * Else, if the body contains ANY
        ``_RED_SETUP_FAILURE_SIGNATURES`` substring → reject as
        setup-failure; return True.
      * Else → unrecognized shape; default to NOT a setup failure
        (genuine red — under-escalate ambiguity per 089m–q).

    Matched case-insensitive substring against the WHOLE body
    (these signatures appear in real runner output, not in agent-
    authored narration; the 089q summary-region scoping does not
    apply here).
    """
    if not isinstance(body, str):
        return False
    low = body.lower()
    # First, look for a genuine test-level failure signature. If
    # present, this is NOT a setup failure regardless of any other
    # signal (the test actually ran and failed).
    for sig in _RED_GENUINE_FAILURE_SIGNATURES:
        if sig in low:
            return False
    # Otherwise, look for setup-failure signatures.
    for sig in _RED_SETUP_FAILURE_SIGNATURES:
        if sig in low:
            return True
    return False


# v1.5.7 090p Task B: extract the regression test's name from a
# `BUG-NNN-regression-test.patch` file. Patterns recognize the
# canonical Go (`func TestXxx(t *testing.T)`) and pytest
# (`def test_xxx(`) test-definition lines that the patch adds.
# Returns a list of test names (a patch may add more than one).
# Conservative direction: if no name can be extracted, downstream
# code falls back to the weaker "red and green use the same
# targeted selector, not a bare whole-package run" check.

import re as _090p_re

_REGRESSION_TEST_NAME_PATTERNS = (
    # Go: `+func TestXxx(t *testing.T)` (also tolerate `func (s *Suite) TestXxx`).
    _090p_re.compile(
        r"^\+\s*func(?:\s*\([^)]*\))?\s+(Test[A-Za-z0-9_]+)\s*\(",
        _090p_re.MULTILINE,
    ),
    # pytest: `+def test_xxx(`
    _090p_re.compile(
        r"^\+\s*def\s+(test_[A-Za-z0-9_]+)\s*\(",
        _090p_re.MULTILINE,
    ),
)


def _extract_regression_test_names(patch_text):
    """Return a sorted list of unique test-function names ADDED by
    the regression-test patch. Handles Go `func TestXxx(...)` and
    pytest `def test_xxx(...)` patterns scanned over patch-add
    lines (`^+` prefix). Returns [] if nothing matches — caller
    falls back to a conservative same-selector / no-bare-package
    check.
    """
    if not isinstance(patch_text, str):
        return []
    names = set()
    for pat in _REGRESSION_TEST_NAME_PATTERNS:
        for m in pat.finditer(patch_text):
            names.add(m.group(1))
    return sorted(names)


def _red_log_references_test_name(body, test_names):
    """True iff the receipt body explicitly references at least one
    of the patch-derived test names — in either the `Command:` line
    (e.g. `go test -run TestXxx`, `pytest -k test_xxx`, an explicit
    test-node id) or in the runner transcript (e.g. `--- FAIL:
    TestXxx`, `FAILED test_x.py::test_xxx`). Case-insensitive
    substring scan over the WHOLE body.
    """
    if not isinstance(body, str) or not test_names:
        return False
    low = body.lower()
    return any(name.lower() in low for name in test_names)


def _is_bare_package_run(body):
    """v1.5.7 090p Task B (conservative fallback): True iff the
    receipt's `Command:` line looks like a bare whole-package run —
    no targeted test selector. Recognizes the run2 shape
    `go test ./pkg` with NO `-run` flag, `pytest pkg/` with no
    `-k`/nodeid, `cargo test` with no test-name filter, etc.

    Used only when `_extract_regression_test_names` returned no
    names (patch format the extractor doesn't recognize) — falls
    back to "red and green must at least use the same targeted
    selector, not a bare whole-package run."
    """
    if not isinstance(body, str):
        return False
    cmd_line = ""
    for ln in body.splitlines():
        ls = ln.strip().lower()
        if ls.startswith("command:"):
            cmd_line = ls[len("command:"):].strip()
            break
    if not cmd_line:
        return False
    # Tokens that ARE targeted selectors.
    if any(tok in cmd_line for tok in (
        "-run ", "-run=",            # go
        "-k ", "-k=",                # pytest
        "::test_", "::Test",         # pytest nodeids
        "--test ",                   # cargo
    )):
        return False
    # Heuristic for bare-package shapes (the run2 trigger):
    if cmd_line.startswith("go test ") or " go test " in cmd_line:
        return True
    if cmd_line.startswith("pytest") and "::" not in cmd_line:
        return True
    if cmd_line.startswith("cargo test"):
        return True
    return False


# v1.5.7 090g: phrases that mark a green NOT_RUN as legitimate
# because the bug has no in-tree fix (e.g. an upgrade-only CVE
# where the only remediation is a dependency bump). A receipt
# body containing any of these downgrades the runner-available
# NOT_RUN escalation from FAIL to WARN. The phrases are
# deliberately specific — generic "skipped" or "blocked" don't
# match, because the agent could use those to evade execution
# of an in-tree fix. The agent has to explicitly assert the
# no-in-tree-fix nature.
_NO_IN_TREE_FIX_MARKERS = (
    "no in-tree fix",
    "no in tree fix",  # space variant
    "upgrade-only",
    "upgrade only",  # space variant
    "upstream upgrade",
    "upstream-upgrade",  # hyphen variant
    "no in-tree remediation",
    "no in tree remediation",
    "remediation is an upstream",  # template phrasing
    "remediation is upstream",
    "third-party-only patch",
    "third party only patch",
)


def _has_no_in_tree_fix_marker(body):
    """v1.5.7 090g: True if the receipt body documents a legitimate
    no-in-tree-fix reason (upgrade-only CVE, third-party patch,
    etc.). Used to downgrade green NOT_RUN from FAIL to WARN when
    the runner is available — the green cycle legitimately can't
    run because there's nothing to apply in-tree.

    The marker list is deliberately specific — generic "skipped"
    or "blocked" don't match. The agent has to make the
    no-in-tree-fix claim explicitly in the receipt body."""
    if not body:
        return False
    low = body.lower()
    return any(m in low for m in _NO_IN_TREE_FIX_MARKERS)


# v1.5.7 089q (D3): the phase5_env.log requirement is a NEW v1.5.7
# (089o) artifact contract. Version-gate it so a pre-089o archived
# or replayed run — which never produced phase5_env.log — does not
# spuriously FAIL. Mirrors the gate's existing legacy-tolerance
# pattern (absent newer artifacts on a pre-version run = legacy,
# no-op rather than FAIL).
_PHASE5_ENV_CONTRACT_VERSION = (1, 5, 7)


def _parse_version_tuple(version_str):
    """Parse a dotted version string ("1.5.7", "1.5.7.2") into a
    tuple of ints, or None if it has no leading numeric component."""
    if not version_str:
        return None
    m = re.match(r"\s*([0-9]+(?:\.[0-9]+)*)", str(version_str))
    if not m:
        return None
    try:
        return tuple(int(p) for p in m.group(1).split("."))
    except ValueError:
        return None


def _run_predates_phase5_env_contract(tdd_data, q):
    """v1.5.7 089q (D3): True when the run's skill/playbook version
    is older than the 089o phase5_env.log contract (< 1.5.7), so a
    missing phase5_env.log should WARN rather than FAIL.

    Version source order: tdd-results.json `skill_version` (already
    parsed into ``tdd_data``), then PROGRESS.md `Skill version:`.
    If the version cannot be determined, return True — the
    conservative, non-breaking choice (consistent with the gate's
    legacy-tolerance pattern: an undeterminable run is treated as
    legacy rather than hard-FAILed; a current run missing its
    version stamp fails the dedicated version-stamp checks
    elsewhere)."""
    version_str = ""
    if isinstance(tdd_data, dict):
        version_str = get_str(tdd_data, "skill_version")
    if not version_str:
        progress_md = q / "PROGRESS.md"
        if progress_md.is_file():
            version_str = read_skill_value_line(
                progress_md, "Skill version:"
            )
    parsed = _parse_version_tuple(version_str)
    if parsed is None:
        return True  # undeterminable → treat as legacy (non-breaking)
    return parsed < _PHASE5_ENV_CONTRACT_VERSION


def _phase5_probe_succeeded(log_text):
    """Heuristic read of quality/results/phase5_env.log: did the
    test-runner version probe SUCCEED (runner available)?

    Returns True only on positive evidence of success, False on
    positive evidence of failure, None when genuinely ambiguous.

    v1.5.7 089o Task 2: the caller escalates a NOT_RUN run to FAIL
    ONLY on a confident True — so ambiguity (None) and a failed
    probe (False) both keep the honest-skip path at WARN (089m
    philosophy: never FAIL an honest NOT_RUN). An explicit exit
    code is the strongest signal; failing that, command-not-found-
    style markers indicate failure and a version string with no
    failure marker indicates success.

    TODO(v1.6.x — 089q D4): this heuristic is coarse — first
    `Exit code` line wins, the version+digits fallback is loose,
    and there is one global per-run signal with no per-bug /
    per-runner mapping. Accepted as a v1.5.7 risk because the
    ambiguous→None→WARN escape prevents false FAILs. The v1.6.x
    verdict-fidelity track hardens it: per-runner probe mapping +
    tighter multi-attempt parsing."""
    if not log_text or not log_text.strip():
        return None
    low = log_text.lower()
    # Strongest signal: an explicit captured exit code.
    m = re.search(r"exit[ _]?code[ :=]+(\d+)", low)
    if m:
        return m.group(1) == "0"
    # No explicit exit code — fall back to markers.
    failure_markers = (
        "command not found",
        "not found",
        "no such file",
        "cannot execute",
        "permission denied",
        "is not recognized",  # Windows "X is not recognized as ..."
    )
    if any(fm in low for fm in failure_markers):
        return False
    # A version line ("X version 1.2.3" / "v1.2.3") with no failure
    # marker is positive evidence the probe ran and the runner is
    # present.
    if re.search(r"version", low) and re.search(r"\d+\.\d+", low):
        return True
    return None


def validate_iso_date(date_str):
    """Return one of: 'valid', 'placeholder', 'future', 'bad_format', 'empty'.

    Placeholders are checked before format so that 'YYYY-MM-DD' is reported
    as 'placeholder' rather than 'bad_format'. The bash version's order was
    flipped, causing 'YYYY-MM-DD' to be misreported — both still FAIL but the
    Python version gives the clearer message.
    """
    if not date_str:
        return "empty"
    if date_str in ("YYYY-MM-DD", "0000-00-00"):
        return "placeholder"
    date_part = date_str[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_part):
        return "bad_format"
    if len(date_str) > 10 and not re.fullmatch(r"T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})?", date_str[10:]):
        return "bad_format"
    today = date.today().isoformat()
    if date_part > today:
        return "future"
    return "valid"


def detect_skill_version(locations):
    """Read `version:` value from the first existing SKILL.md-like file."""
    for loc in locations:
        if loc.is_file():
            try:
                with open(loc, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        m = re.match(r"^\s*(?:version:|\*\*Version:\*\*)\s*([0-9]+(?:\.[0-9]+)+)\b",
                                     line, re.IGNORECASE)
                        if m:
                            return m.group(1)
            except OSError:
                continue
    return ""


# v1.5.10 instruction 052 (the SKILL.md trim): the trim moves per-phase detail
# into lazy-loaded references/*.md reachable from SKILL.md via the
# ``See `references/X.md` `` pointer dialect (the SAME regex the
# bin/tests/test_skill_md_size.py pointer test uses — NOT a second `Read` form).
# The reference-resolves invariant guards against a trim that points at a file
# it forgot to create / mis-names, and against a reference cycle.
_SKILL_REF_POINTER = re.compile(r"See `(references/[^`]+\.md)`")


def validate_skill_reference_resolves(skill_md_path):
    """Verify every ``See `references/X.md` `` pointer in SKILL.md — and
    transitively in the reference files those point to — resolves to an existing
    file under the skill's ``references/`` dir, with cycle detection. Returns a
    list of problem strings (empty list == clean). Pure: no global-counter side
    effects, so callers (the gate CLI sub-mode + the regression test) share it
    without disturbing the per-repo gate output contract."""
    skill_md_path = Path(skill_md_path)
    if not skill_md_path.is_file():
        return ["SKILL.md not found at %s" % skill_md_path]
    skill_dir = skill_md_path.parent
    problems = []
    visited = set()
    stack = []  # files on the current DFS path -> cycle detector

    def _walk(path):
        if path in stack:
            cyc = " -> ".join([p.name for p in stack] + [path.name])
            problems.append("reference cycle detected: %s" % cyc)
            return
        if path in visited:
            return
        visited.add(path)
        stack.append(path)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:  # noqa: BLE001
            problems.append("cannot read %s (%s)" % (path.name, exc))
            stack.pop()
            return
        for rel in _SKILL_REF_POINTER.findall(text):
            target = skill_dir / rel
            if not target.is_file():
                problems.append(
                    "%s points at `%s` which does not exist" % (path.name, rel))
                continue
            _walk(target)
        stack.pop()

    _walk(skill_md_path)
    return problems


def read_skill_value_line(path, prefix):
    """Mimic: grep -m1 'prefix' FILE | sed 's/.*prefix *//' | tr -d ' '."""
    if not path.is_file():
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if prefix in line:
                    v = re.sub(rf".*{re.escape(prefix)}\s*", "", line, count=1)
                    return v.replace(" ", "").rstrip("\n").rstrip("\r")
    except OSError:
        pass
    return ""


# v1.5.7 instruction 054 (A-10): adopter install marker dirs + the
# bundled bin/. QPB installs its own skill tree (incl. post-050 Python
# closure modules) under one of these markers; both file-tree walkers
# below MUST skip them or QPB's own .py files poison language
# detection / source counts in non-Python adopter projects — the gson
# opus-4.6 Mode-A reproduction, 2026-05-16 (detect_project_language
# returned "py" for a Java project because Python is checked before
# Java and QPB's bundled bin/*.py were found first).
#
# Canonical source of the marker list is
# bin/install_skill.AI_TOOL_MAP.values(); intentionally DUPLICATED
# here (Option B, additive — per the instruction-053 precedent)
# because quality_gate.py is deployed STANDALONE into an adopter's
# .github/skills/quality_gate/ and CANNOT import bin/install_skill.py
# (the installer is not part of the bundled gate).
# TODO(v1.5.7.x): consolidate the three exclusion-set copies (this,
# count_source_files below, and classify_project.DEFAULT_IGNORE_DIRS)
# behind one shared constant once a gate-standalone-safe shared
# module exists.
_INSTALL_MARKER_DIRS = frozenset({
    ".claude", ".cursor", ".github", ".continue",
    ".codex", ".windsurf", ".cline", ".aider", "bin",
})


def detect_project_languages(repo_dir):
    """Return the testable code-language counts for ``repo_dir`` as a list
    of ``(lang, count)`` tuples ranked most-files-first, tiebroken by
    ``language_order`` (earliest wins). Walks up to 5 dirs deep, counting
    only known language extensions. v1.5.10 instruction 058 (D1).

    ``detect_project_language`` is a thin delegate returning element
    ``[0]`` of this ranking, so the singular winner and the plural
    ranking **cannot drift** — same walk / extension set / excludes /
    tiebreak by construction. The winner is byte-identical to the
    pre-058 implementation (regression-pinned across every baseline repo
    + vaelii + a narrow-margin fixture).

    Only ``language_order`` (testable code) extensions are counted —
    Markdown / shell / edn and other non-code content are **never**
    surfaced as a (testable) language, so disclosure/override never offer
    a non-testable target. Returns ``[]`` when no known source extension
    is found.

    v1.5.10 (instruction 056): dominant-language-by-count (most files
    wins) replaced ordered first-match. First-match returned the earliest
    language in ``language_order`` whose extension appeared *anywhere*,
    so a Clojure repo with a few stray ``.py`` build scripts detected as
    Python (``py`` precedes — and ``clj`` was absent entirely). Counting
    instead means a handful of shallow stray scripts can't out-vote the
    real source.

    Depth 5 (was 3): standard Leiningen/Maven layout puts source at
    ``src/main/clojure/<ns>/<ns>.clj`` — depth 5. At depth <=3 a Clojure
    project with only deep source plus a few shallow ``.py`` STILL
    mis-detects (sandbox: vaelii is clj-6 vs py-3 at <=3 but clj-128 vs
    py-3 at <=5). Only ``language_order`` extensions are counted, so
    ``.md`` / ``.sh`` / ``.edn`` never become candidates.

    [056 Council B] Build-output dirs (dist/build/out/target) are
    excluded so a TypeScript project's compiled ``.js`` can't out-count
    its ``.ts`` (ordered first-match was immune because ``ts`` precedes
    ``js``; dominant-count is not). Accepted tradeoff: an adopter repo
    whose tooling ``.py`` outnumber its real source within depth 5 could
    flip to ``py`` — judged acceptable because real source normally
    dominates and the depth-5 walk reaches deep source. The QPB
    install-marker dirs + bundled ``bin/`` stay excluded
    (``_INSTALL_MARKER_DIRS``) so QPB's own Python closure never poisons
    detection (instruction 054).
    """
    language_order = [
        ("go", ".go"),
        ("py", ".py"),
        ("java", ".java"),
        ("kt", ".kt"),
        ("rs", ".rs"),
        ("ts", ".ts"),
        ("js", ".js"),
        ("scala", ".scala"),
        ("c", ".c"),
        ("clj", ".clj"),
        ("clj", ".cljc"),
        ("clj", ".cljs"),
        ("agc", ".agc"),
    ]
    # [056 Council B] build-output dirs excluded so compiled artifacts
    # don't out-count real source under dominant-by-count.
    excluded = ({"vendor", "node_modules", ".git", "quality", "repos",
                 "dist", "build", "out", "target"} | _INSTALL_MARKER_DIRS)

    ext_to_lang = {}
    order_index = {}
    for idx, (lang, ext) in enumerate(language_order):
        ext_to_lang[ext] = lang
        order_index.setdefault(lang, idx)
    known_exts = set(ext_to_lang)

    counts = {}
    stack = [(Path(repo_dir), 1)]
    while stack:
        curr, depth = stack.pop()
        try:
            for entry in os.scandir(curr):
                name = entry.name
                if entry.is_dir(follow_symlinks=False):
                    if name in excluded:
                        continue
                    if depth < 5:
                        stack.append((Path(entry.path), depth + 1))
                elif entry.is_file(follow_symlinks=False):
                    dot = name.rfind(".")
                    if dot >= 0 and name[dot:] in known_exts:
                        lang = ext_to_lang[name[dot:]]
                        counts[lang] = counts.get(lang, 0) + 1
        except (OSError, PermissionError):
            continue

    if not counts:
        return []
    # Most files wins; tiebreak = earliest in language_order. Sorting
    # ascending on (-count, order_index) puts the same winner at [0] that
    # the pre-058 ``max(counts, key=(count, -order_index))`` produced.
    return sorted(counts.items(), key=lambda kv: (-kv[1], order_index[kv[0]]))


def detect_project_language(repo_dir):
    """Return the dominant testable language (the winner of
    :func:`detect_project_languages`), or "" when none is found. Thin
    delegate (v1.5.10 instruction 058 D1) so the singular and plural
    detectors cannot drift; the winner stays byte-identical to the 056
    implementation."""
    ranked = detect_project_languages(repo_dir)
    return ranked[0][0] if ranked else ""


# v1.5.10 instruction 058 (D3): the detected/override testable language ->
# the test-file extensions the gate accepts for it. Lifted to module scope
# (was local to check_test_file_extension) so BOTH the extension check AND
# main's --language validator read one source — an unknown / non-testable
# --language value is a usage error (exit 2) precisely because it is not a
# key here.
_LANG_TO_VALID = {
    "go": "go",
    "py": "py",
    "java": "java",
    "kt": "kt java",
    "rs": "rs",
    "ts": "ts",
    "js": "js ts",
    "scala": "scala",
    "c": "c py sh",
    "clj": "clj cljc cljs",
    "agc": "py sh",
}


# v1.5.10 instruction 058 (D5): the multi-language disclosure fires only
# when >=2 testable languages EACH clear both a minimum share and a
# minimum file count, so a stray handful of files in a second language
# never triggers noise. Boundary is >=-inclusive (exactly 10% AND exactly
# 5 files fires).
_DISCLOSURE_MIN_RATIO = 0.10
_DISCLOSURE_MIN_FILES = 5


def languages_over_disclosure_threshold(ranked):
    """Given the ranked ``[(lang, count), ...]`` from
    :func:`detect_project_languages`, return the sublist of languages that
    each clear ``>=_DISCLOSURE_MIN_RATIO`` of the testable total AND
    ``>=_DISCLOSURE_MIN_FILES`` files. Denominator is
    ``sum(counts.values())`` from ``detect_project_languages`` (NOT
    ``count_source_files`` — a different walker). v1.5.10 058 (D5)."""
    total = sum(count for _, count in ranked)
    if total <= 0:
        return []
    return [
        (lang, count)
        for lang, count in ranked
        if count >= _DISCLOSURE_MIN_FILES
        and (count / total) >= _DISCLOSURE_MIN_RATIO
    ]


def _disclosure_fires(ranked):
    """True when >=2 testable languages clear the disclosure threshold."""
    return len(languages_over_disclosure_threshold(ranked)) >= 2


def _maybe_record_language_disclosure(repo_dir, repo_name, language=None):
    """v1.5.10 058 (D2/D5): when >=2 testable languages clear the
    disclosure threshold, record a per-repo disclosure entry for emission
    after the final RESULT line. ``language`` (the --language override),
    when set, is the tested language; otherwise the detected winner is."""
    repo_dir = Path(repo_dir)
    if not repo_dir.is_dir():
        return
    over = languages_over_disclosure_threshold(detect_project_languages(repo_dir))
    if len(over) < 2:
        return
    tested = language or over[0][0]
    untested = [lang for lang, _ in over if lang != tested]
    _LANGUAGE_DISCLOSURES.append({
        "repo": repo_name,
        "detected": over,
        "tested": tested,
        "untested": untested,
    })


def _emit_language_disclosures(disclosures):
    """v1.5.10 058 (D2): print the per-repo multi-language disclosure
    block(s) AFTER the load-bearing RESULT/verdict lines (additive; the
    ::QPB:: sentinel still trails). Fixed format so an operator — and the
    regression tests — can rely on it."""
    for d in disclosures:
        detected = ", ".join(f"{lang}={count}" for lang, count in d["detected"])
        untested = ", ".join(d["untested"]) or "(none)"
        hint_lang = d["untested"][0] if d["untested"] else "<lang>"
        print("")
        print(f"LANGUAGES DETECTED (testable) [{d['repo']}]: {detected}")
        print(f"TESTED: {d['tested']}")
        print(f"TESTABLE LANGUAGES NOT TESTED: {untested}")
        print(
            f"To run QPB on {hint_lang}: re-run with --language {hint_lang} "
            f"(this ARCHIVES the current quality/ folder)"
        )


def count_source_files(repo_dir):
    """Count source files up to 4 dirs deep, excluding vendor/node_modules/etc."""
    src_count = 0
    exts = {".go", ".py", ".java", ".kt", ".rs", ".ts", ".js", ".scala",
            ".c", ".h", ".clj", ".cljc", ".cljs", ".agc"}
    # v1.5.7 instruction 054 (A-10): `repos` added here for parity
    # with detect_project_language (it had `repos`, this walker did
    # not — the slight pre-existing inconsistency the instruction
    # called out). `repos/` is QPB's benchmark-targets dir, never
    # adopter source. _INSTALL_MARKER_DIRS skips QPB's own install
    # tree so its bundled .py files are not counted as adopter source.
    excluded = {"vendor", "node_modules", ".git", "quality", "repos"} | _INSTALL_MARKER_DIRS

    def walk(base, current_depth, max_depth):
        nonlocal src_count
        try:
            for entry in os.scandir(base):
                name = entry.name
                if entry.is_dir(follow_symlinks=False):
                    if current_depth < max_depth and name not in excluded:
                        walk(entry.path, current_depth + 1, max_depth)
                elif entry.is_file(follow_symlinks=False):
                    dot = name.rfind(".")
                    if dot >= 0 and name[dot:] in exts:
                        src_count += 1
        except (OSError, PermissionError):
            pass

    walk(str(repo_dir), 1, 4)
    return src_count


# --- Section checks ---


@verdict_category(VERDICT_SUBSTANTIVE)
def check_file_existence(repo_dir, q, strictness):
    """File existence section (benchmark 40)."""
    print("[File Existence]")
    for f in ["BUGS.md", "REQUIREMENTS.md", "QUALITY.md", "PROGRESS.md",
              "COVERAGE_MATRIX.md", "COMPLETENESS_REPORT.md"]:
        if (q / f).is_file():
            pass_(f"{f} exists")
        else:
            fail(f"{f} missing")

    for f in ["CONTRACTS.md", "RUN_CODE_REVIEW.md", "RUN_SPEC_AUDIT.md",
              "RUN_INTEGRATION_TESTS.md", "RUN_TDD_TESTS.md"]:
        if (q / f).is_file():
            pass_(f"{f} exists")
        else:
            fail(f"{f} missing")

    if has_file_matching(q, ["test_functional.*", "functional_test.*",
                             "FunctionalSpec.*", "FunctionalTest.*",
                             "functional.test.*"]):
        pass_("functional test file exists")
    else:
        fail("functional test file missing (test_functional.*, functional_test.*, FunctionalSpec.*, FunctionalTest.*, functional.test.*)")

    if (repo_dir / "AGENTS.md").is_file():
        pass_("AGENTS.md exists")
    else:
        fail("AGENTS.md missing (required at project root)")

    if (q / "EXPLORATION.md").is_file():
        pass_("EXPLORATION.md exists")
        _check_exploration_sections(q / "EXPLORATION.md")
    else:
        fail("EXPLORATION.md missing")

    cr_dir = _resolve_artifact_path(q, "code_reviews")
    if cr_dir.is_dir() and has_file_matching(cr_dir, ["*.md"]):
        pass_("code_reviews/ has .md files")
    else:
        fail("code_reviews/ missing or empty")

    sa_dir = _resolve_artifact_path(q, "spec_audits")
    if sa_dir.is_dir():
        triage_count = count_files_matching(sa_dir, "*triage*")
        auditor_count = count_files_matching(sa_dir, "*auditor*")
        if triage_count > 0:
            pass_("spec_audits/ has triage file")
        else:
            fail("spec_audits/ missing triage file")
        if auditor_count > 0:
            pass_(f"spec_audits/ has {auditor_count} auditor file(s)")
        else:
            fail("spec_audits/ missing individual auditor files")

        if triage_count > 0:
            has_probes = False
            if (sa_dir / "triage_probes.sh").is_file():
                has_probes = True
                pass_("triage_probes.sh exists (executable triage evidence)")
            elif (_resolve_artifact_path(q, "mechanical/verify.sh")).is_file() and \
                 file_contains(_resolve_artifact_path(q, "mechanical/verify.sh"), r"probe|triage|auditor"):
                # Pre-W4 back-compat only: older runs appended probe
                # assertions to the bash verify.sh. W4 (080) makes
                # verify.py a fixed-purpose extraction orchestrator —
                # NOT a host for ad-hoc probe assertions — so the
                # canonical location is spec_audits/triage_probes.sh
                # (see references/phase2_generation_guide.md).
                has_probes = True
                pass_("verify.sh contains triage probe assertions (pre-W4 back-compat)")
            if not has_probes:
                msg = "No executable triage evidence found (expected spec_audits/triage_probes.sh; pre-W4 runs may carry probe assertions in mechanical/verify.sh)"
                if strictness == "benchmark":
                    fail(msg)
                else:
                    warn(msg)
    else:
        fail("spec_audits/ directory missing")


@verdict_category(VERDICT_SUBSTANTIVE)
def check_bugs_heading(q):
    """BUGS.md heading-format section (benchmark 39).

    Returns (bug_count, bug_ids).
    """
    print("[BUGS.md Heading Format]")
    bugs_md = q / "BUGS.md"
    if not bugs_md.is_file():
        fail("BUGS.md missing")
        return 0, []

    try:
        bugs_content = bugs_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        bugs_content = ""
    lines = bugs_content.splitlines()

    correct_headings = sum(1 for ln in lines
                           if re.match(r"^### BUG-([HML]|[0-9])[0-9]*", ln))
    wrong_headings = sum(1 for ln in lines
                         if re.match(r"^## BUG-", ln)
                         and not re.match(r"^### BUG-", ln))
    deep_headings = sum(1 for ln in lines
                        if re.match(r"^#{4,} BUG-([HML]|[0-9])", ln))
    bold_headings = sum(1 for ln in lines
                        if re.match(r"^\*\*BUG-([HML]|[0-9])", ln))
    bullet_headings = sum(1 for ln in lines
                          if re.match(r"^- BUG-([HML]|[0-9])", ln))

    bug_count = correct_headings

    if (correct_headings > 0 and wrong_headings == 0 and deep_headings == 0
            and bold_headings == 0 and bullet_headings == 0):
        pass_(f"All {correct_headings} bug headings use ### BUG-NNN format")
    else:
        if wrong_headings > 0:
            fail(f"{wrong_headings} heading(s) use ## instead of ###")
        if deep_headings > 0:
            fail(f"{deep_headings} heading(s) use #### or deeper instead of ###")
        if bold_headings > 0:
            fail(f"{bold_headings} heading(s) use **BUG- format")
        if bullet_headings > 0:
            fail(f"{bullet_headings} heading(s) use - BUG- format")
        if correct_headings == 0 and wrong_headings == 0:
            if re.search(r"^##\s+(No confirmed bugs|Zero confirmed bugs)\s*$",
                         bugs_content, re.MULTILINE | re.IGNORECASE):
                pass_("Zero-bug run — no headings expected")
            else:
                bug_count = wrong_headings + deep_headings + bold_headings + bullet_headings
                warn("No ### BUG-NNN headings found in BUGS.md")
        else:
            bug_count = correct_headings + wrong_headings + bold_headings + bullet_headings

    # Extract canonical bug IDs: BUG-NNN or BUG-HNN / BUG-MNN / BUG-LNN
    raw = re.findall(r"BUG-(?:[HML][0-9]+|[0-9]+)", bugs_content)
    filtered = [b for b in raw if re.fullmatch(r"BUG-(?:[HML][0-9]+|[0-9]+)", b)]
    bug_ids = sorted(set(filtered))

    return bug_count, bug_ids


@verdict_category(VERDICT_SUBSTANTIVE)
def check_tdd_sidecar(q, bug_count):
    """TDD sidecar JSON (benchmarks 14, 41)."""
    print("[TDD Sidecar JSON]")
    json_path = _resolve_artifact_path(q, "results/tdd-results.json")

    if bug_count <= 0:
        info("Zero bugs — tdd-results.json not required")
        return None

    if not json_path.is_file():
        fail(f"tdd-results.json missing ({bug_count} bugs require it)")
        return None

    pass_(f"tdd-results.json exists ({bug_count} bugs)")

    data = load_json(json_path)
    if data is None:
        # File exists but unparsable — fail all root key checks
        for key in ["schema_version", "skill_version", "date", "project",
                    "bugs", "summary"]:
            fail(f"missing root key '{key}'")
        fail("schema_version is 'missing', expected '1.1'")
        return None

    for key in ["schema_version", "skill_version", "date", "project",
                "bugs", "summary"]:
        if has_key(data, key):
            pass_(f"has '{key}'")
        else:
            fail(f"missing root key '{key}'")

    sv = get_str(data, "schema_version")
    if sv == "1.1":
        pass_("schema_version is '1.1'")
    else:
        fail(f"schema_version is '{sv or 'missing'}', expected '1.1'")

    bugs_list = data.get("bugs") if isinstance(data, dict) else None
    if not isinstance(bugs_list, list):
        bugs_list = []

    for field in ["id", "requirement", "red_phase", "green_phase",
                  "verdict", "fix_patch_present", "writeup_path"]:
        fcount = count_per_bug_field(bugs_list, field)
        if fcount >= bug_count:
            pass_(f"per-bug field '{field}' present ({fcount}x)")
        elif fcount > 0:
            warn(f"per-bug field '{field}' found {fcount}x, expected {bug_count}")
        else:
            fail(f"per-bug field '{field}' missing entirely")

    # Non-canonical field names (at any level — check root and bugs)
    bad_fields = ["bug_id", "bug_name", "status", "phase", "result"]
    for bad in bad_fields:
        found = has_key(data, bad) or any(
            has_key(b, bad) for b in bugs_list if isinstance(b, dict)
        )
        if found:
            fail(f"non-canonical field '{bad}' found (use standard field names)")

    summary = data.get("summary") if isinstance(data, dict) else None
    if not isinstance(summary, dict):
        summary = {}
    for skey in ["total", "verified", "confirmed_open", "red_failed", "green_failed"]:
        if skey in summary:
            pass_(f"summary has '{skey}'")
        else:
            fail(f"summary missing '{skey}' count")

    # Date validation
    tdd_date = get_str(data, "date")
    status = validate_iso_date(tdd_date)
    if status == "empty":
        fail("tdd-results.json date field missing or empty")
    elif status == "bad_format":
        fail(f"tdd-results.json date '{tdd_date}' is not ISO 8601 (YYYY-MM-DD)")
    elif status == "placeholder":
        fail(f"tdd-results.json date is placeholder '{tdd_date}'")
    elif status == "future":
        fail(f"tdd-results.json date '{tdd_date}' is in the future")
    else:
        pass_(f"tdd-results.json date '{tdd_date}' is valid")

    # Verdict enum
    allowed_verdicts = {"TDD verified", "red failed", "green failed",
                        "confirmed open", "deferred"}
    bad_verdicts = 0
    for b in bugs_list:
        if isinstance(b, dict) and "verdict" in b:
            v = b.get("verdict")
            if v not in allowed_verdicts:
                bad_verdicts += 1
    if bad_verdicts == 0:
        pass_("all verdict values are canonical")
    else:
        fail(f"{bad_verdicts} non-canonical verdict value(s)")

    return data


@verdict_category(VERDICT_SUBSTANTIVE)
def check_tdd_logs(q, bug_count, bug_ids, tdd_data):
    """TDD log files and sidecar-to-log cross-validation."""
    print("[TDD Log Files]")
    if bug_count <= 0:
        info("Zero bugs — TDD log files not required")
        return

    patches_dir = _resolve_artifact_path(q, "patches")
    results_dir = _resolve_artifact_path(q, "results")
    valid_tags = {"RED", "GREEN", "NOT_RUN", "ERROR"}

    red_found = 0
    red_missing = 0
    green_found = 0
    green_missing = 0
    green_expected = 0
    red_bad_tag = 0
    green_bad_tag = 0
    # v1.5.7 089m (#326 cheap half): count bugs with at least one
    # NOT_RUN TDD receipt so we can emit a WARN when the red/green
    # cycle was honestly skipped (legitimate state — `RUN_TDD_TESTS.md`
    # documents NOT_RUN as the "test execution skipped" tag — but
    # the gate must surface that the empirical red→green proof
    # didn't happen, so adopters don't read GATE PASSED as more
    # than it covers).
    bugs_with_not_run = 0
    # v1.5.7 090g: green NOT_RUN whose body documents "no in-tree
    # fix" (e.g. upgrade-only CVEs like "remediation is upstream
    # upgrade to v1.5.9+"). These get WARN even when probe_ok is
    # True — there's no in-tree fix to apply, so the green cycle
    # legitimately can't run regardless of runner availability.
    # Red NOT_RUN with probe_ok=True remains FAIL: reproducing
    # the bug doesn't require a fix.
    bugs_with_documented_no_in_tree_fix = 0
    # v1.5.7 089o (#329): receipts tagged RED/GREEN whose SUMMARY
    # admits non-execution ("by inspection" etc.) — overclaims.
    # Each entry is (bug_id, phase, marker).
    overclaim_receipts = []
    # v1.5.7 089q (D2): every RED/GREEN receipt, with whether its
    # body carries an affirmative execution signature. Each entry
    # is (bug_id, phase, has_execution_signature). After the loop,
    # when the Phase 5 probe shows the runner available, a RED/
    # GREEN receipt with no signature is an overclaim-by-omission.
    red_green_receipts = []

    for bid in bug_ids:
        red_log = results_dir / f"{bid}.red.log"
        red_tag = None
        if red_log.is_file():
            red_found += 1
            red_body = read_full_text(red_log)
            red_tag = read_first_line_stripped(red_log)
            if red_tag not in valid_tags:
                red_bad_tag += 1
            # 089o: a RED/GREEN tag asserts real execution. If the
            # summary admits non-execution, that's an overclaim →
            # FAIL. 089q D2: also record whether the receipt
            # carries an execution signature.
            if red_tag in ("RED", "GREEN"):
                marker = _first_overclaim_marker(red_body)
                if marker is not None:
                    overclaim_receipts.append((bid, "red", marker))
                red_green_receipts.append(
                    (bid, "red", _has_execution_signature(red_body))
                )
        else:
            red_missing += 1

        green_tag = None
        fix_patch = first_file_matching(patches_dir, [f"{bid}-fix*.patch"])
        if fix_patch is not None:
            green_expected += 1
            green_log = results_dir / f"{bid}.green.log"
            if green_log.is_file():
                green_found += 1
                green_body = read_full_text(green_log)
                green_tag = read_first_line_stripped(green_log)
                if green_tag not in valid_tags:
                    green_bad_tag += 1
                if green_tag in ("RED", "GREEN"):
                    marker = _first_overclaim_marker(green_body)
                    if marker is not None:
                        overclaim_receipts.append((bid, "green", marker))
                    red_green_receipts.append(
                        (bid, "green",
                         _has_execution_signature(green_body))
                    )
            else:
                green_missing += 1

        # 089m: a bug counts as "TDD-not-executed" if either its
        # red receipt OR its green receipt (when expected) is
        # NOT_RUN. Both ends of the red→green cycle need to have
        # actually executed for the cycle to count as proven.
        if red_tag == "NOT_RUN" or green_tag == "NOT_RUN":
            bugs_with_not_run += 1
            # v1.5.7 090g: a green NOT_RUN whose body documents a
            # legitimate no-in-tree-fix reason (upgrade-only CVE,
            # third-party-only patch, etc.) is a WARN even when
            # the runner is available — there's nothing to apply
            # to make the test pass in-tree. Red NOT_RUN never
            # qualifies (reproducing the bug doesn't need a fix);
            # only a green NOT_RUN whose RED ran clean and whose
            # green body explicitly says "no in-tree fix" gets
            # the WARN downgrade.
            if (green_tag == "NOT_RUN" and red_tag != "NOT_RUN"
                    and green_log.is_file()
                    and _has_no_in_tree_fix_marker(read_full_text(green_log))):
                bugs_with_documented_no_in_tree_fix += 1

    if red_missing == 0 and red_found > 0:
        pass_(f"All {red_found} confirmed bug(s) have red-phase logs")
    elif red_found > 0:
        fail(f"{red_missing} confirmed bug(s) missing red-phase log (BUG-NNN.red.log)")
    else:
        fail("No red-phase logs found (every confirmed bug needs quality/results/BUG-NNN.red.log)")

    if green_expected > 0:
        if green_missing == 0:
            pass_(f"All {green_found} bug(s) with fix patches have green-phase logs")
        else:
            fail(f"{green_missing} bug(s) with fix patches missing green-phase log (BUG-NNN.green.log)")
    else:
        info("No fix patches found — green-phase logs not required")

    if red_bad_tag > 0:
        fail(f"{red_bad_tag} red-phase log(s) missing valid first-line status tag (expected RED/GREEN/NOT_RUN/ERROR)")
    elif red_found > 0:
        pass_("All red-phase logs have valid status tags")
    if green_bad_tag > 0:
        fail(f"{green_bad_tag} green-phase log(s) missing valid first-line status tag (expected RED/GREEN/NOT_RUN/ERROR)")
    elif green_found > 0:
        pass_("All green-phase logs have valid status tags")

    # v1.5.7 090p — GATE-LEVEL TDD RED VALIDITY: a red must be a
    # genuine test-level failure, not a setup/build/dependency/
    # collection failure; and the red/green must exercise the bug's
    # named regression test (or, conservatively, the same targeted
    # selector — not a bare whole-package run).
    #
    # The 2026-05-24 Ory Keto run2 (cold Go caches, network-
    # restricted sandbox) reported GATE PASSED on TDD proofs of this
    # shape: red `FAIL [setup failed] / lookup proxy.golang.org: no
    # such host` (Exit 1) + green `ok pkg 0.398s` (Exit 0), with
    # both red and green running an identical generic `go test
    # ./ketoapi` regardless of where the bug actually lived. The
    # gate accepted this because (1) any non-zero exit was a
    # "satisfied red" and (2) there was no requirement that red/
    # green exercise the bug's specific regression test. 090p
    # closes both holes mechanically — 090o's phase5.md env-vs-
    # real-RED guard is the prompt-side companion; 090p is the
    # gate-level backstop because run2 proved prose alone doesn't
    # bind.
    #
    # Routing rule: a red rejected as setup-failure is treated as
    # NOT_RUN(environment) for the verdict-shape (090o
    # remediation routes the operator to fix the environment and
    # re-run Phases 5–6); the existing 089m NOT_RUN escalation
    # (WARN if probe failed/ambiguous; FAIL if probe shows runner
    # available — overclaim) then governs downstream. The bug
    # does NOT count as TDD-proven.
    #
    # Conservative direction (per 089m–q): only rejection of a red
    # matching a KNOWN setup-failure signature; an unrecognized
    # non-zero red stays a genuine red (don't wrongly fail honest
    # assertion-failure reds).

    invalid_red_setup_failures = []           # (bid, signature_excerpt)
    untied_red_green = []                     # (bid, reason)
    bugs_invalidated_by_090p = set()          # bids whose TDD is rejected by 090p

    for bid in bug_ids:
        red_log = results_dir / f"{bid}.red.log"
        green_log = results_dir / f"{bid}.green.log"
        if not red_log.is_file():
            continue
        red_body = read_full_text(red_log)
        red_tag = read_first_line_stripped(red_log)
        # 090p does NOT apply to NOT_RUN reds — those are already
        # routed through the 089m honesty path. 090p targets the
        # RED tag specifically (a claimed test-level failure).
        if red_tag != "RED":
            continue

        # Task A: is this red a setup-failure shape?
        if _is_red_setup_failure(red_body):
            invalid_red_setup_failures.append((bid, red_log.name))
            bugs_invalidated_by_090p.add(bid)
            # Don't double-fire the named-test check for the same
            # bug — Task A's rejection already invalidates it.
            continue

        # Task B: does the red/green exercise the bug's named
        # regression test? Try to extract test names from the
        # regression-test patch; if extraction returns nothing,
        # fall back to "not a bare whole-package run" + "red and
        # green use the same targeted selector."
        regression_patch = first_file_matching(
            patches_dir,
            [f"{bid}-regression-test*.patch", f"{bid}-regression*.patch"],
        )
        test_names = []
        if regression_patch is not None:
            try:
                patch_text = read_full_text(regression_patch)
            except Exception:
                patch_text = ""
            test_names = _extract_regression_test_names(patch_text)

        # Need a green log to check the green side.
        green_body = (
            read_full_text(green_log) if green_log.is_file() else None
        )

        if test_names:
            # Strong form: red and green must both reference at
            # least one of the patch-derived test names.
            red_refs = _red_log_references_test_name(red_body, test_names)
            if not red_refs:
                untied_red_green.append((
                    bid,
                    f"red log {red_log.name} does not reference any "
                    f"patch-derived test name "
                    f"({', '.join(test_names[:3])}"
                    f"{'…' if len(test_names) > 3 else ''})",
                ))
                bugs_invalidated_by_090p.add(bid)
            if green_body is not None:
                green_refs = _red_log_references_test_name(
                    green_body, test_names,
                )
                if not green_refs:
                    untied_red_green.append((
                        bid,
                        f"green log {green_log.name} does not reference "
                        f"any patch-derived test name "
                        f"({', '.join(test_names[:3])}"
                        f"{'…' if len(test_names) > 3 else ''})",
                    ))
                    bugs_invalidated_by_090p.add(bid)
        else:
            # Conservative fallback: red and green must not be bare
            # whole-package runs.
            if _is_bare_package_run(red_body):
                untied_red_green.append((
                    bid,
                    f"red log {red_log.name} is a bare whole-package "
                    f"run with no targeted test selector; cannot tie "
                    f"to the bug's regression test",
                ))
                bugs_invalidated_by_090p.add(bid)
            if green_body is not None and _is_bare_package_run(green_body):
                untied_red_green.append((
                    bid,
                    f"green log {green_log.name} is a bare whole-"
                    f"package run with no targeted test selector",
                ))
                bugs_invalidated_by_090p.add(bid)

    # Emit per-bug failures with specific guidance.
    for bid, log_name in invalid_red_setup_failures:
        fail(
            f"{log_name}: tagged RED but body is a setup/dependency/"
            f"build/collection failure (e.g. '[setup failed]', 'no "
            f"such host', 'dependency resolution failed', "
            f"ImportError, collection ERROR). A red that fails "
            f"because deps won't resolve proves nothing about "
            f"whether the bug exists — the red→green transition "
            f"is explained by deps becoming resolvable, not by the "
            f"fix. v1.5.7 090p: setup-failure reds are NOT valid "
            f"TDD evidence. Treat as NOT_RUN(environment) per the "
            f"089m policy + 090o phase5 remediation: prepare the "
            f"build / fix the environment, then re-run Phases 5–6 "
            f"so the test can actually execute."
        )
    for bid, reason in untied_red_green:
        fail(
            f"{bid}: TDD red/green does not exercise the bug's "
            f"specific regression test — {reason}. v1.5.7 090p: a "
            f"red/green that does not exercise the bug's named "
            f"regression test is not a valid TDD proof (the run "
            f"could have passed for any number of reasons unrelated "
            f"to the bug). Add a targeted selector (Go `-run "
            f"<TestName>`, pytest `-k <name>` or nodeid) that "
            f"matches the test added by "
            f"`quality/patches/{bid}-regression-test.patch`."
        )
    if invalid_red_setup_failures:
        fail(
            f"{len(invalid_red_setup_failures)} TDD red receipt(s) "
            f"rejected as setup/dependency/build failures (v1.5.7 "
            f"090p — not valid REDs)."
        )
    if untied_red_green:
        fail(
            f"{len(untied_red_green)} TDD receipt(s) not tied to a "
            f"bug-specific regression test (v1.5.7 090p)."
        )

    # v1.5.7 089o/089q: resolve the Phase 5 runner-probe artifact
    # and its outcome ONCE, up front — both the 089q D2 positive-
    # evidence check and the 089m/089o NOT_RUN handling below
    # depend on whether the probe showed the runner available.
    phase5_env_log = results_dir / "phase5_env.log"
    phase5_env_present = phase5_env_log.is_file()
    probe_ok = (
        _phase5_probe_succeeded(read_full_text(phase5_env_log))
        if phase5_env_present else None
    )

    # v1.5.7 089o (#329) Task 1: FAIL on RED/GREEN overclaim. A
    # receipt tagged RED or GREEN asserts the test was actually
    # executed; a SUMMARY that admits non-execution ("by
    # inspection", etc.) under that tag is a prediction mislabeled
    # as an observation. This is the dishonest combination 089m's
    # NOT_RUN WARN could not catch (the gson run mislabeled 15
    # by-inspection receipts RED/GREEN so the first-line tag never
    # said NOT_RUN). The remedy for an agent that can't execute is
    # to run it for real OR tag NOT_RUN honestly (→ WARN, still
    # passes) — so this FAIL targets only the overclaim, never
    # honesty.
    if overclaim_receipts:
        for bid, phase, marker in overclaim_receipts:
            tag = "RED" if phase == "red" else "GREEN"
            # NB: the substring "but body admits non-execution" is
            # kept contiguous on one source line — the v1.5.7 089p
            # recap drift guard (test_recap_tdd_signal_drift_089p)
            # greps quality_gate.py source for it.
            fail(
                f"{bid}.{phase}.log tagged {tag} "
                f"but body admits non-execution"
                f" (\"{marker}\"). A RED/GREEN tag "
                f"asserts the test was actually run. Run the test "
                f"for real (capture real runner output) or mark the "
                f"receipt NOT_RUN (which WARN-passes per the honest-"
                f"skip path)."
            )
        fail(
            f"{len(overclaim_receipts)} TDD receipt(s) overclaim: "
            f"tagged RED/GREEN over a by-inspection / non-execution "
            f"body. A RED/GREEN tag must be backed by real test "
            f"execution."
        )

    # v1.5.7 089q (D2): overclaim BY OMISSION. The D1 narrowing
    # above only catches a receipt that NARRATES non-execution in
    # a recognizable phrase — a paraphrased inspection-only receipt
    # ("derived analytically", "confirmed from reading the source")
    # slips past it. So: when the Phase 5 probe shows the runner
    # demonstrably available (probe_ok is True), a RED/GREEN
    # receipt MUST carry an affirmative execution signature
    # (Command:/Exit code: line, runner transcript token). A
    # RED/GREEN receipt with no signature, while the runner was
    # available, is asserting an execution that left no trace →
    # FAIL. Honesty preserved (089m): this requirement applies
    # ONLY when probe_ok is True — a failed/ambiguous probe
    # (False/None) requires NO evidence, so NOT_RUN stays the
    # honest WARN/PASS path. A receipt already FAILed for a D1
    # marker is not double-counted here.
    if probe_ok is True:
        _d1_flagged = {(b, p) for b, p, _ in overclaim_receipts}
        omission_receipts = [
            (b, p) for b, p, has_sig in red_green_receipts
            if not has_sig and (b, p) not in _d1_flagged
        ]
        for bid, phase in omission_receipts:
            tag = "RED" if phase == "red" else "GREEN"
            fail(
                f"{bid}.{phase}.log tagged {tag} but carries no "
                f"runner output (overclaim by omission). The Phase "
                f"5 probe shows the test runner IS available, so a "
                f"{tag} tag must be backed by a real execution "
                f"signature (a Command:/Exit code: line or runner "
                f"transcript). Run the test for real and capture "
                f"its output, or mark the receipt NOT_RUN."
            )
        if omission_receipts:
            fail(
                f"{len(omission_receipts)} TDD receipt(s) overclaim "
                f"by omission: tagged RED/GREEN with the runner "
                f"available but no captured runner output."
            )

    # v1.5.7 089o (#329) Task 2 + 089q (D3): phase5_env.log probe
    # substantiation. A run with confirmed bugs must capture the
    # test-runner probe (mvn -version / pytest --version / cargo
    # --version / go version, with stdout+stderr+exit code) to
    # quality/results/phase5_env.log BEFORE any RED/GREEN/NOT_RUN
    # determination — this is what forces the agent to actually
    # check runner availability rather than assume it. 089q D3:
    # phase5_env.log is a NEW v1.5.7 (089o) artifact contract —
    # version-gate it so pre-089o archived/replayed runs (which
    # never produced it) do not spuriously FAIL.
    if not phase5_env_present:
        if _run_predates_phase5_env_contract(tdd_data, q):
            warn(
                "phase5_env.log absent — this run predates the "
                "v1.5.7 089o Phase 5 test-runner-probe contract "
                "(pre-1.5.7 runs never produced it). Not a failure "
                "for a legacy run; a current-version run would "
                "FAIL here."
            )
        else:
            # NB: the substring "phase5_env.log is missing" is kept
            # contiguous on one source line — the v1.5.7 089p recap
            # drift guard (test_recap_tdd_signal_drift_089p) greps
            # quality_gate.py source for it.
            fail(
                "Phase 5 must probe the test runner and capture "
                "`<tool> --version` (stdout+stderr+exit code) to "
                "quality/results/phase5_env.log before any "
                "RED/GREEN/NOT_RUN determination — "
                "phase5_env.log is missing."
            )
    else:
        pass_("phase5_env.log present (test-runner probe captured)")

    # v1.5.7 089m (#326 cheap half) + 089o Task 2: handle NOT_RUN
    # receipts. NOT_RUN is an honestly-marked legitimate state — an
    # environment that genuinely can't build records NOT_RUN per
    # quality/RUN_TDD_TESTS.md — so the BASE case is WARN, the gate
    # still PASSES. 089o escalates ONLY the contradicted case: if
    # phase5_env.log shows the runner WAS available (a clean
    # version probe) yet receipts are NOT_RUN, that's the assume-
    # unavailable root cause — escalate to FAIL. An ambiguous or
    # failed probe keeps the honest-skip WARN (089m unchanged).
    if bugs_with_not_run > 0:
        # probe_ok was resolved once, up front (089o/089q).
        # v1.5.7 090g: separate the documented-no-in-tree-fix
        # NOT_RUN bugs (legitimate WARN even when probe_ok=True)
        # from the rest (FAIL when probe_ok=True).
        bugs_with_undocumented_not_run = (
            bugs_with_not_run - bugs_with_documented_no_in_tree_fix
        )
        if probe_ok is True and bugs_with_undocumented_not_run > 0:
            # NB: the substring "phase5_env.log shows the test runner IS available"
            # is kept contiguous on one source line — the v1.5.7 089p
            # recap drift guard (test_recap_tdd_signal_drift_089p) greps
            # quality_gate.py source for it.
            fail(
                f"{bugs_with_undocumented_not_run} of "
                f"{len(bug_ids)} confirmed bug(s) have receipts "
                f"marked NOT_RUN, but phase5_env.log shows the test runner IS available"
                f" (the version probe succeeded). Run the red/green "
                f"cycle — NOT_RUN is only honest when the probe "
                f"itself failed OR when the green receipt "
                f"documents a no-in-tree fix (e.g. upgrade-only "
                f"CVE). Quote the failing probe output if the "
                f"runner genuinely cannot run, or include a 'no "
                f"in-tree fix' / 'upstream upgrade' marker in "
                f"the green receipt body."
            )
        if bugs_with_documented_no_in_tree_fix > 0:
            warn(
                f"{bugs_with_documented_no_in_tree_fix} of "
                f"{len(bug_ids)} confirmed bug(s) have green "
                f"NOT_RUN receipts documenting no in-tree fix "
                f"(e.g. upgrade-only CVEs). The red phase ran "
                f"empirically; the green cycle skipped because "
                f"the fix is out-of-tree. Operator action is "
                f"the documented upstream upgrade. (v1.5.7 090g.)"
            )
        if probe_ok is not True and bugs_with_undocumented_not_run > 0:
            warn(
                f"TDD red/green cycle not executed for "
                f"{bugs_with_undocumented_not_run} of {len(bug_ids)} "
                f"confirmed bug(s) (receipts marked NOT_RUN). "
                f"These bugs are patch-applicable and reasoned, "
                f"but not empirically proven by a failing-then-"
                f"passing test. Run quality/RUN_TDD_TESTS.md to "
                f"complete the red/green cycle."
            )

    # Sidecar-to-log cross-validation (BUG-M18)
    if tdd_data is not None and isinstance(tdd_data, dict):
        bugs_list = tdd_data.get("bugs") or []
        if not isinstance(bugs_list, list):
            bugs_list = []
        # Index bugs by id for lookup
        bug_by_id = {}
        for b in bugs_list:
            if isinstance(b, dict) and isinstance(b.get("id"), str):
                bug_by_id[b["id"]] = b

        xv_checked = 0
        xv_mismatch = 0

        for bid in bug_ids:
            bug_obj = bug_by_id.get(bid)
            sidecar_red = get_str(bug_obj, "red_phase") if bug_obj else ""
            sidecar_green = get_str(bug_obj, "green_phase") if bug_obj else ""

            red_log = results_dir / f"{bid}.red.log"
            if sidecar_red and red_log.is_file():
                log_tag = read_first_line_stripped(red_log)
                xv_checked += 1
                if sidecar_red == "fail" and log_tag != "RED":
                    xv_mismatch += 1
                    fail(f"{bid}: sidecar red_phase='{sidecar_red}' but log first-line is '{log_tag}' (expected RED)")
                elif sidecar_red == "pass" and log_tag != "GREEN":
                    xv_mismatch += 1
                    fail(f"{bid}: sidecar red_phase='{sidecar_red}' but log first-line is '{log_tag}' (expected GREEN)")

            green_log = results_dir / f"{bid}.green.log"
            if sidecar_green and green_log.is_file():
                log_tag = read_first_line_stripped(green_log)
                xv_checked += 1
                if sidecar_green == "pass" and log_tag != "GREEN":
                    xv_mismatch += 1
                    fail(f"{bid}: sidecar green_phase='{sidecar_green}' but log first-line is '{log_tag}' (expected GREEN)")
                elif sidecar_green == "fail" and log_tag != "RED":
                    xv_mismatch += 1
                    fail(f"{bid}: sidecar green_phase='{sidecar_green}' but log first-line is '{log_tag}' (expected RED)")

        if xv_checked > 0 and xv_mismatch == 0:
            pass_(f"Sidecar-to-log cross-validation passed ({xv_checked} checks)")
        elif xv_checked == 0:
            info("Sidecar-to-log cross-validation: no matching pairs to check")

    # TDD_TRACEABILITY.md
    if red_found > 0:
        if (q / "TDD_TRACEABILITY.md").is_file():
            pass_(f"TDD_TRACEABILITY.md exists ({red_found} bugs with red-phase results)")
        else:
            fail("TDD_TRACEABILITY.md missing (mandatory when bugs have red-phase results)")


@verdict_category(VERDICT_SUBSTANTIVE)
def check_integration_sidecar(q, strictness):
    """Integration sidecar JSON section."""
    print("[Integration Sidecar JSON]")
    ij = _resolve_artifact_path(q, "results/integration-results.json")

    if not ij.is_file():
        if strictness == "benchmark":
            warn("integration-results.json not present")
        else:
            info("integration-results.json not present (optional in general mode)")
        return

    data = load_json(ij)

    for key in ["schema_version", "skill_version", "date", "project",
                "recommendation", "groups", "summary", "uc_coverage"]:
        if has_key(data, key):
            pass_(f"has '{key}'")
        else:
            fail(f"missing key '{key}'")

    summary = data.get("summary") if isinstance(data, dict) else None
    if not isinstance(summary, dict):
        summary = {}
    for iskey in ["total_groups", "passed", "failed", "skipped"]:
        if iskey in summary:
            pass_(f"integration summary has '{iskey}'")
        else:
            fail(f"integration summary missing required sub-key '{iskey}'")

    isv = get_str(data, "schema_version")
    if isv == "1.1":
        pass_("integration schema_version is '1.1'")
    else:
        fail(f"integration schema_version is '{isv or 'missing'}', expected '1.1'")

    int_date = get_str(data, "date")
    if int_date:  # match bash: if [ -n "$int_date" ]
        status = validate_iso_date(int_date)
        if status == "bad_format":
            fail(f"integration-results.json date '{int_date}' is not ISO 8601 (YYYY-MM-DD)")
        elif status == "placeholder":
            fail(f"integration-results.json date is placeholder '{int_date}'")
        elif status == "future":
            fail(f"integration-results.json date '{int_date}' is in the future")
        else:
            pass_(f"integration-results.json date '{int_date}' is valid")

    rec = get_str(data, "recommendation")
    if rec in ("SHIP", "FIX BEFORE MERGE", "BLOCK"):
        pass_(f"recommendation '{rec}' is canonical")
    elif rec:
        fail(f"recommendation '{rec}' is non-canonical (must be SHIP/FIX BEFORE MERGE/BLOCK)")
    else:
        fail("recommendation missing")

    # groups[].result enum
    allowed_results = {"pass", "fail", "skipped", "error"}
    bad_results = 0
    groups = data.get("groups") if isinstance(data, dict) else None
    if isinstance(groups, list):
        for g in groups:
            if isinstance(g, dict) and "result" in g:
                if g.get("result") not in allowed_results:
                    bad_results += 1
    if bad_results == 0:
        pass_("all groups[].result values are canonical")
    else:
        fail(f"{bad_results} non-canonical groups[].result value(s) (must be pass/fail/skipped/error)")

    # uc_coverage value enum
    allowed_uc = {"covered_pass", "covered_fail", "not_mapped"}
    bad_uc = 0
    uc_cov = data.get("uc_coverage") if isinstance(data, dict) else None
    if isinstance(uc_cov, dict):
        for v in uc_cov.values():
            if v not in allowed_uc:
                bad_uc += 1
    if bad_uc == 0:
        pass_("all uc_coverage values are canonical")
    else:
        fail(f"{bad_uc} non-canonical uc_coverage value(s) (must be covered_pass/covered_fail/not_mapped)")


@verdict_category(VERDICT_SUBSTANTIVE)
def check_recheck_sidecar(q):
    """Recheck sidecar JSON (schema 1.0, uses 'results' key not 'bugs')."""
    print("[Recheck Sidecar JSON]")
    rj = _resolve_artifact_path(q, "results/recheck-results.json")
    rs = _resolve_artifact_path(q, "results/recheck-summary.md")

    if not rj.is_file():
        info("recheck-results.json not present (only required when recheck mode was run)")
        return

    pass_("recheck-results.json exists")
    data = load_json(rj)

    # SKILL.md recheck template uses 'results' as the array key, not 'bugs'.
    for key in ["schema_version", "skill_version", "date", "project",
                "results", "summary"]:
        if has_key(data, key):
            pass_(f"recheck has '{key}'")
        else:
            fail(f"recheck missing root key '{key}'")

    rsv = get_str(data, "schema_version")
    if rsv == "1.0":
        pass_("recheck schema_version is '1.0'")
    else:
        fail(f"recheck schema_version is '{rsv or 'missing'}', expected '1.0'")

    rdate = get_str(data, "date")
    if rdate:
        status = validate_iso_date(rdate)
        if status == "bad_format":
            fail(f"recheck-results.json date '{rdate}' is not ISO 8601 (YYYY-MM-DD)")
        elif status == "placeholder":
            fail(f"recheck-results.json date is placeholder '{rdate}'")
        elif status == "future":
            fail(f"recheck-results.json date '{rdate}' is in the future")
        else:
            pass_(f"recheck-results.json date '{rdate}' is valid")

    if rs.is_file():
        pass_("recheck-summary.md exists")
    else:
        fail("recheck-summary.md missing (required companion to recheck-results.json)")


def check_heartbeat_sidecar(q):
    """v1.5.9 1B — heartbeat.ndjson conformance (present only under the
    harness; the file sits beside quality/ in the run-dir). Carries the
    harness Council disciplines into the gate surface:
      * C-3 — every line pins a known ``schema_version`` (``"1"`` legacy or
        ``"2"`` current; Postel) (silent-drift guard);
      * A-1 — clean O_APPEND NDJSON framing: one valid JSON object per
        line, never a torn line;
      * the progress/terminal status enum + terminal-sentinel discipline.
    A-2 (absolute dispatch paths) is enforced dispatch-side in
    qpb_harness_tick.py, not re-checked here. NON-BLOCKING (``warn``):
    heartbeat is orchestration metadata, never a grading input
    (design §Dispatch — the gate verdict does not depend on it)."""
    print("[Heartbeat NDJSON]")
    hb = q.parent / "heartbeat.ndjson"
    if not hb.is_file():
        info("heartbeat.ndjson not present (only emitted under the harness)")
        return
    pass_("heartbeat.ndjson present (harness-orchestrated run)")
    try:
        # 189-class: heartbeat.ndjson is EXTERNAL worker content — read with
        # errors="replace" so a stray non-UTF-8 byte can't crash the gate on
        # a cp1252 host.
        lines = [ln for ln in hb.read_text(
                     encoding="utf-8", errors="replace").splitlines()
                 if ln.strip()]
    except OSError:
        warn("heartbeat.ndjson could not be read")
        return
    if not lines:
        warn("heartbeat.ndjson is empty (worker emitted no heartbeats)")
        return
    progress = {"STARTING", "IN_PROGRESS", "COMPLETED", "FAILED"}
    terminal = {"COMPLETED", "FAILED", "ABANDONED"}
    bad_json = bad_ver = bad_status = 0
    last_obj = None
    for ln in lines:
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError:
            bad_json += 1
            continue
        last_obj = obj
        if obj.get("schema_version") not in ("1", "2"):
            bad_ver += 1
        if obj.get("status") not in progress | terminal:
            bad_status += 1
    if bad_json:
        warn(f"{bad_json} heartbeat line(s) are not valid JSON "
             f"(A-1 NDJSON framing)")
    else:
        pass_("all heartbeat lines are valid JSON (A-1 framing intact)")
    if bad_ver:
        warn(f"{bad_ver} heartbeat line(s) carry an unrecognized "
             f"schema_version (not '1' or '2') (C-3 drift)")
    else:
        pass_("all heartbeat lines pin schema_version in {'1','2'} (C-3)")
    if bad_status:
        warn(f"{bad_status} heartbeat line(s) carry an unknown status value")
    if isinstance(last_obj, dict) and last_obj.get("status") in terminal:
        if last_obj.get("result_file") and last_obj.get("summary"):
            pass_("terminal sentinel present (status + result_file + summary)")
        else:
            warn("terminal heartbeat missing result_file/summary")
    else:
        info("no terminal sentinel yet (run in flight or orphaned)")


@verdict_category(VERDICT_SUBSTANTIVE)
def check_use_cases(repo_dir, q, strictness):
    """Use case identifier section (benchmarks 43, 48)."""
    print("[Use Cases]")
    req_md = q / "REQUIREMENTS.md"
    if not req_md.is_file():
        fail("REQUIREMENTS.md missing")
        return

    try:
        req_content = req_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        req_content = ""

    # uc_ids: count of lines matching UC-N (bash grep -cE counts lines)
    uc_ids = sum(1 for ln in req_content.splitlines()
                 if re.search(r"UC-[0-9]+", ln))
    uc_unique = len(set(re.findall(r"UC-[0-9]+", req_content)))

    src_count = count_source_files(repo_dir) if repo_dir.is_dir() else 0
    min_uc = 3 if src_count < 5 else 5

    if uc_unique >= min_uc:
        pass_(f"Found {uc_unique} distinct UC identifiers ({uc_ids} total references, {src_count} source files)")
    elif uc_unique > 0:
        connector = "for" if strictness == "general" else "required for"
        msg = f"Only {uc_unique} distinct UC identifiers (minimum {min_uc} {connector} {src_count} source files)"
        if strictness == "general":
            warn(msg)
        else:
            fail(msg)
    else:
        fail("No canonical UC-NN identifiers in REQUIREMENTS.md")


@verdict_category(VERDICT_SUBSTANTIVE)
def check_test_file_extension(repo_dir, q, language=None):
    """Test file extension matches project language (benchmark 47).

    v1.5.10 instruction 058 (D3): when ``language`` (the ``--language``
    override) is set, the gate validates the functional/regression test
    files against the **override's** accepted extensions instead of the
    detected language, and records ``ran_on = <override>``. The override is
    threaded from ``main`` -> ``check_repo`` -> here so the gate validates
    what the agent was actually told to target, not the plurality language
    — editing this function body alone would leave the gate validating the
    *detected* language while the agent tested the *override*."""
    print("[Test File Extension]")
    func_test = first_file_matching(q, ["test_functional.*", "functional_test.*",
                                        "FunctionalSpec.*", "FunctionalTest.*",
                                        "functional.test.*"])
    reg_test = first_file_matching(q, ["test_regression.*"])

    if func_test is None:
        warn("No functional test file found across the supported naming matrix")
        return

    ext = func_test.suffix.lstrip(".") if func_test.suffix else ""
    if language:
        # --language override: validate against the requested language,
        # not the detected plurality, and record ran_on so the operator
        # sees which language this run actually targeted.
        detected_lang = language
        info(f"--language override active: ran_on={language}")
    else:
        detected_lang = detect_project_language(repo_dir) if repo_dir.is_dir() else ""

    if not detected_lang:
        info(f"Cannot detect project language — skipping extension check (test_functional.{ext})")
        return

    lang_to_valid = _LANG_TO_VALID
    valid_ext = lang_to_valid.get(detected_lang, "")
    valid_list = valid_ext.split()
    primary = valid_list[0] if valid_list else ""

    if ext in valid_list:
        pass_(f"{func_test.name} matches project language ({detected_lang})")
    else:
        fail(f"{func_test.name} does not match project language ({detected_lang}) — expected .{primary}")

    if reg_test is not None:
        reg_ext = reg_test.suffix.lstrip(".") if reg_test.suffix else ""
        if reg_ext in valid_list:
            pass_(f"test_regression.{reg_ext} matches project language ({detected_lang})")
        else:
            fail(f"test_regression.{reg_ext} does not match project language ({detected_lang}) — expected .{primary}")


# v1.5.7 instruction 090s: Task A — reject a functional test file
# whose test functions are ALL trivial / no-assertion stubs. Motivated
# by the 2026-05-25 Ory Keto run4 (Copilot in VS Code auto-mode =
# gpt-5.3-codex): the agent fabricated a hollow run that the gate
# PASSED — `quality/test_functional.go` was literally
# `func TestFunctionalBaseline(t *testing.T) {}` (empty body, no
# assertions), zero confirmed bugs, and the gate's functional-test
# check only verified the file existed and matched the project
# language. 090s closes the mechanically-catchable part: a file
# where EVERY test function is trivial / no-assertion FAILs.
#
# Conservative direction (per 089m–q "under-escalate ambiguity"):
# only FAIL when ALL test functions in the file are trivial. A file
# with at least one real assertion-bearing test PASSES. This catches
# the run4 hollow shape without touching legitimate test files (table-
# driven tests, helper-only files, sub-test patterns).
#
# Detection is regex-based — pragmatic, not full-AST. The
# assertion-pattern lists below MAY be extended as new ecosystems
# surface, but should stay anchored to call-site shapes that have
# zero false-positive overlap with non-assertion code.

_GO_ASSERTION_PATTERNS: tuple[str, ...] = (
    r"\bt\.Error\b",
    r"\bt\.Errorf\b",
    r"\bt\.Fatal\b",
    r"\bt\.Fatalf\b",
    r"\bt\.Fail\b",
    r"\bt\.FailNow\b",
    r"\bt\.Skip\b",            # Skip is a real signal (intentional)
    r"\brequire\.",            # testify/require
    r"\bassert\.",             # testify/assert
    r"\bassertions\.",         # testify/assertions
    r"\bg\.Expect\b",          # ginkgo/gomega
    r"\bExpect\(.+\)\.To\b",   # ginkgo/gomega
)

# Python: tautological assertions (`assertTrue(True)`, `assertEqual(1, 1)`,
# `assert True`) are stripped BEFORE the real-assertion scan so a body
# containing ONLY tautologies counts as trivial.
_PYTHON_ASSERTION_PATTERNS: tuple[str, ...] = (
    r"\bself\.assert[A-Z]\w*\b",  # unittest-style (assertEqual, assertTrue, ...)
    r"\bself\.fail\b",
    r"\bpytest\.raises\b",
    r"\bpytest\.fail\b",
    r"\bpytest\.warns\b",
    r"\bunittest\.skip\b",
    # Bare `assert <expr>` with expr that isn't a constant-True
    # tautology (filtered upstream — see `_body_has_real_assertion`).
    r"\bassert\s+",
)

# Python tautology patterns — STRIPPED before the real-assertion scan.
# These are the no-op forms a hollow run could insert to look like a
# test without actually testing anything.
_PYTHON_TAUTOLOGY_PATTERNS: tuple[str, ...] = (
    r"\bself\.assertTrue\(\s*True\s*\)",
    r"\bself\.assertFalse\(\s*False\s*\)",
    r"\bself\.assertEqual\(\s*(\d+)\s*,\s*\1\s*\)",
    r"\bself\.assertEqual\(\s*(\"[^\"]*\")\s*,\s*\1\s*\)",
    r"\bself\.assertIs\(\s*True\s*,\s*True\s*\)",
    r"\bassert\s+True\b",
    r"\bassert\s+1\s*==\s*1\b",
)

# Clojure (v1.5.10 instruction 056): a real `clojure.test` assertion is
# an `(is ...)` or `(are ...)` form. Like Go, there is no tautology
# stripping — `(is ...)` is an explicit assertion-call shape (and the
# skip-guard `(is false "BUG-NNN ...")`, clojure.test's xfail-substitute,
# is intentionally a real signal). A `(deftest ...)` whose body has no
# `(is ...)`/`(are ...)` is the hollow shape this check fails.
_CLOJURE_ASSERTION_PATTERNS: tuple[str, ...] = (
    r"\(is\b",
    r"\(are\b",
)


def _clojure_test_function_bodies(source: str) -> list[str]:
    """Return the full text of every ``(deftest name ...)`` form in a
    Clojure test file, via balanced-paren matching. Pragmatic — does
    not skip parens inside strings/comments (adequate for the
    hollow-test detection this serves; the `(deftest ...)` shape is
    unambiguous enough). v1.5.10 instruction 056."""
    bodies: list[str] = []
    pattern = re.compile(r"\(deftest\b")
    for m in pattern.finditer(source):
        start = m.start()  # the opening paren of `(deftest`
        depth = 0
        i = start
        while i < len(source):
            c = source[i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    bodies.append(source[start:i + 1])
                    break
            i += 1
    return bodies


def _go_test_function_bodies(source: str) -> list[str]:
    """Return the body text of every ``func Test*(t *testing.T) { ... }``
    in a Go test file. Handles nested braces via a simple depth
    counter. (Pragmatic — not a full Go parser; rejects strings/
    comments containing braces is out of scope here, but the
    test-body shape is unambiguous enough that this is fine for the
    run4 hollow-test pattern this check exists to detect.)"""
    bodies: list[str] = []
    # `func TestX(...)` opener — also tolerate method-form
    # `func (s *Suite) TestX(...)`.
    pattern = re.compile(
        r"\bfunc\s*(?:\([^)]*\)\s*)?Test\w+\s*\([^)]*\)\s*\{"
    )
    for m in pattern.finditer(source):
        start = m.end() - 1  # The opening `{`
        depth = 0
        i = start
        while i < len(source):
            c = source[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    bodies.append(source[start + 1:i])
                    break
            i += 1
    return bodies


def _python_test_function_bodies(source: str) -> list[str]:
    """Return the body text of every ``def test_*`` in a Python test
    file. Uses indentation to find the end of each function block.
    Pragmatic — not a full Python parser; close enough for the
    no-op detection 090s targets."""
    bodies: list[str] = []
    lines = source.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^(\s*)def\s+test_\w+\s*\(", lines[i])
        if m:
            indent = m.group(1)
            body_lines: list[str] = []
            j = i + 1
            while j < len(lines):
                line = lines[j]
                if line.strip() == "":
                    body_lines.append(line)
                    j += 1
                    continue
                line_indent_match = re.match(r"^\s*", line)
                line_indent = line_indent_match.group(0) if line_indent_match else ""
                if len(line_indent) <= len(indent):
                    break  # dedent — end of body
                body_lines.append(line)
                j += 1
            bodies.append("\n".join(body_lines))
            i = j
        else:
            i += 1
    return bodies


def _body_has_real_assertion(body: str, lang: str) -> bool:
    """True iff a test-function body contains at least one real
    assertion call (after stripping tautologies for Python). For
    Go, a tautology like `t.Error()` with no message is still a
    real assertion-call shape (it's an explicit fail signal), so
    Go has no tautology stripping. Unknown languages return True
    (pass-through — don't over-fire on unrecognized shapes per
    089m–q)."""
    if lang == "go":
        for pat in _GO_ASSERTION_PATTERNS:
            if re.search(pat, body):
                return True
        return False
    if lang == "py":
        # Strip Python tautologies first so a body containing ONLY
        # `assertTrue(True)` / `assert True` / `assertEqual(1, 1)`
        # counts as trivial.
        normalized = body
        for pat in _PYTHON_TAUTOLOGY_PATTERNS:
            normalized = re.sub(pat, "", normalized)
        for pat in _PYTHON_ASSERTION_PATTERNS:
            if re.search(pat, normalized):
                return True
        return False
    if lang == "clj":
        # No tautology stripping (mirrors Go): an `(is ...)`/`(are ...)`
        # call is an explicit assertion shape. v1.5.10 instruction 056.
        for pat in _CLOJURE_ASSERTION_PATTERNS:
            if re.search(pat, body):
                return True
        return False
    # Unrecognized language: pass-through (conservative direction).
    return True


@verdict_category(VERDICT_SUBSTANTIVE)
def check_functional_test_has_assertions(q):
    """v1.5.7 090s Task A: FAIL when the functional test file's
    test functions are ALL trivial / no-assertion stubs (the
    2026-05-25 Ory Keto run4 hollow shape — empty
    `TestFunctionalBaseline`). Conservative: a file with ≥1
    assertion-bearing test passes; unrecognized languages
    pass-through (don't over-fire).

    Anchored to `quality/test_functional.{go,py,...}` only — the
    canonical functional-test file path; regression test files
    (`quality/test_regression.*`) are out of scope (they're
    auto-generated from patches, with their own coverage checks)."""
    print("[Functional Test Content]")
    func_test = first_file_matching(
        q, ["test_functional.*", "functional_test.*",
            "FunctionalSpec.*", "FunctionalTest.*",
            "functional.test.*"],
    )
    if func_test is None:
        # No file → the existing extension check already warns; this
        # check has nothing to evaluate.
        info("No functional test file — content check skipped")
        return

    ext = func_test.suffix.lstrip(".") if func_test.suffix else ""
    # v1.5.10 instruction 056: `clj` added so a hollow Clojure
    # functional test (a `(deftest ...)` with no `(is ...)`) is caught
    # rather than pass-through-skipped.
    lang_map = {"go": "go", "py": "py", "clj": "clj"}
    lang = lang_map.get(ext)
    if not lang:
        # Unrecognized language → pass-through per the conservative
        # direction (don't over-fire on shapes the detector doesn't
        # know).
        info(
            f"{func_test.name}: language {ext!r} not in the 090s "
            f"no-op detection set — content check skipped "
            f"(conservative pass-through; 090s targets Go + Python + "
            f"Clojure)",
        )
        return

    try:
        source = func_test.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        warn(
            f"{func_test.name}: could not read for content check: "
            f"{type(exc).__name__}: {exc}",
        )
        return

    if lang == "go":
        bodies = _go_test_function_bodies(source)
    elif lang == "clj":
        bodies = _clojure_test_function_bodies(source)
    else:
        bodies = _python_test_function_bodies(source)

    if not bodies:
        # No `func Test*` / `def test_*` patterns found — the file
        # exists but doesn't carry any conventional test function.
        # This is a DIFFERENT shape from "all test functions are
        # trivial" (the load-bearing 090s pattern). Conservative
        # direction (per 089m–q): WARN, not FAIL — adopters with
        # helper-only files / non-canonical test naming should not
        # be wrongly failed. The "all-trivial" check below catches
        # the actual run4 shape (a real `func Test*` with an empty
        # body).
        warn(
            f"{func_test.name}: no test functions found "
            f"(expected `func Test*` for Go, `def test_*` for "
            f"Python, or `(deftest ...)` for Clojure). The file exists "
            f"and matches the language "
            f"but doesn't carry conventional test functions; check "
            f"whether the assertions live in an unconventional "
            f"shape this detector doesn't recognize. v1.5.7 090s."
        )
        return

    real_count = sum(1 for b in bodies
                     if _body_has_real_assertion(b, lang))
    if real_count == 0:
        fail(
            f"{func_test.name}: ALL {len(bodies)} test function(s) "
            f"are trivial / no-assertion stubs (the 2026-05-25 Ory "
            f"Keto run4 hollow shape). A functional test file with "
            f"no real assertions doesn't prove anything about the "
            f"codebase. Add at least one assertion-bearing test "
            f"(Go: `t.Error` / `t.Fatal` / `require.*` / `assert.*`; "
            f"Python: a real `assert <expr>` / `self.assert*` / "
            f"`pytest.raises`; Clojure: `(is ...)` / `(are ...)`). "
            f"v1.5.7 090s.",
        )
    else:
        pass_(
            f"{func_test.name}: {real_count} of {len(bodies)} test "
            f"function(s) carry real assertions (v1.5.7 090s "
            f"no-op detection)"
        )


# v1.5.7 instruction 090s: Task B — track repos with zero confirmed
# bugs so the gate verdict can be loudly qualified. A clean codebase
# may legitimately have zero bugs, but a hollow / shallow run also
# produces zero bugs; the qualification line tells the operator to
# verify the run actually explored before trusting the PASS. Does
# NOT change pass/fail semantics — only adds a prominent line
# adjacent to RESULT:.
_ZERO_BUG_REPOS: list[str] = []


# v1.5.10 instruction 058 (D2): per-repo multi-language disclosure blocks,
# accumulated during check_repo and emitted AFTER the load-bearing
# RESULT/verdict lines (additive — mirrors the _emit_operator_verdict /
# ::QPB:: post-RESULT precedent; never alters RESULT strings). Each entry
# is {"repo", "detected": [(lang,count),...], "tested", "untested": [...]}.
_LANGUAGE_DISCLOSURES: list[dict] = []


@verdict_category(VERDICT_SUBSTANTIVE)
def check_terminal_gate(q):
    """Terminal Gate section in PROGRESS.md."""
    print("[Terminal Gate]")
    progress_md = q / "PROGRESS.md"
    if not progress_md.is_file():
        return
    pat = re.compile(r"^#+ *Terminal", re.IGNORECASE | re.MULTILINE)
    if file_contains(progress_md, pat):
        pass_("PROGRESS.md has Terminal Gate section")
    else:
        fail("PROGRESS.md missing Terminal Gate section")


@verdict_category(VERDICT_SUBSTANTIVE)
def check_mechanical(q):
    """Mechanical verification section."""
    print("[Mechanical Verification]")
    mech_dir = _resolve_artifact_path(q, "mechanical")
    if not mech_dir.is_dir():
        info("No mechanical/ directory")
        return
    # v1.5.7 instruction 080c (closes 080b codex F1). W4 (§6): the
    # gate now ACTUALLY INVOKES the mechanical verifier — re-running
    # the ORIGINAL shell pipeline fresh is the v1.3.23 witness; the
    # 080b presence-only check never re-ran anything (codex F1).
    # Prefer verify.py (W4 Python orchestrator); fall back to
    # verify.sh (pre-W4 back-compat); if neither exists but
    # *_cases.txt extraction artifacts do, mechanical verification is
    # required and missing → FAIL; an empty mechanical/ is
    # non-conformant. The verifier runs from the target repo root
    # (q.parent — verify.py's recorded paths like
    # quality/mechanical/<f>_cases.txt and the source files the shell
    # pipeline reads are relative to it). The verifier's exit code IS
    # the gate verdict; its stdout/stderr is surfaced on failure so
    # adopters see WHAT failed, not just "verification failed".
    target_root = q.parent
    verify_py = mech_dir / "verify.py"
    verify_sh = mech_dir / "verify.sh"
    if verify_py.is_file():
        pass_("verify.py exists")
        verifier_cmd = [sys.executable, "quality/mechanical/verify.py"]
        which = "verify.py"
    elif verify_sh.is_file():
        pass_("verify.sh exists (pre-W4 back-compat)")
        verifier_cmd = ["bash", "quality/mechanical/verify.sh"]
        which = "verify.sh"
    else:
        if list(mech_dir.glob("*_cases.txt")):
            fail("verify.py or verify.sh expected but neither found; "
                 "cases.txt files exist, so mechanical verification is "
                 "required for this project.")
        else:
            fail("mechanical/ exists but verify.py missing")
        return

    try:
        proc = subprocess.run(
            verifier_cmd, cwd=str(target_root),
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
        )
    except subprocess.TimeoutExpired:
        fail(f"{which} timed out after 300s — mechanical verification "
             f"did not complete")
        return
    except OSError as exc:
        fail(f"{which} could not be executed: {exc}")
        return
    if proc.returncode == 0:
        pass_(f"{which} ran clean (exit 0)")
    else:
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        fail(f"{which} FAILED (exit {proc.returncode}) — mechanical "
             f"artifact mismatch or extraction error. "
             f"stdout: {out[:800]} | stderr: {err[:400]}")

    # Receipt cross-check (unchanged). The gate's own fresh invocation
    # above is the authoritative pass/fail; these receipts additionally
    # prove the agent ran the verifier at the Phase-2a immediate gate /
    # Phase 6 (verification.md §35/§37 benchmarks depend on them).
    mv_log = _resolve_artifact_path(q, "results/mechanical-verify.log")
    mv_exit = _resolve_artifact_path(q, "results/mechanical-verify.exit")
    if mv_log.is_file() and mv_exit.is_file():
        try:
            exit_code = mv_exit.read_text(encoding="utf-8", errors="replace")
        except OSError:
            exit_code = ""
        exit_code = re.sub(r"\s", "", exit_code)
        if exit_code == "0":
            pass_("mechanical-verify.exit is 0")
        else:
            fail(f"mechanical-verify.exit is '{exit_code}', expected 0")
    else:
        fail("Verification receipt files missing")


@verdict_category(VERDICT_SUBSTANTIVE)
def check_patches(q, bug_count, bug_ids, strictness):
    """Patches section (benchmark 44)."""
    print("[Patches]")
    if bug_count <= 0:
        return

    patches_dir = _resolve_artifact_path(q, "patches")

    # Regression test file — required when bugs exist
    reg_test_file = None
    if q.is_dir():
        reg_files = sorted(q.glob("test_regression.*"))
        if reg_files:
            reg_test_file = reg_files[0]

    if reg_test_file is not None:
        pass_(f"test_regression.* exists ({bug_count} confirmed bugs require it)")
    else:
        msg = "test_regression.* missing — required when bugs exist (SKILL.md artifact contract)"
        if strictness == "benchmark":
            fail(msg)
        else:
            warn(msg)

    reg_patch_count = 0
    fix_patch_count = 0
    reg_patch_missing = 0
    for bid in bug_ids:
        if first_file_matching(patches_dir, [f"{bid}-regression*.patch"]) is not None:
            reg_patch_count += 1
        else:
            reg_patch_missing += 1
        if first_file_matching(patches_dir, [f"{bid}-fix*.patch"]) is not None:
            fix_patch_count += 1

    if reg_patch_missing == 0 and reg_patch_count > 0:
        pass_(f"{reg_patch_count} regression-test patch(es) for {bug_count} bug(s)")
    elif reg_patch_count > 0:
        fail(f"{reg_patch_missing} bug(s) missing regression-test patch")
    else:
        fail("No regression-test patches found (quality/patches/BUG-NNN-regression-test.patch required)")

    if fix_patch_count > 0:
        pass_(f"{fix_patch_count} fix patch(es)")
    else:
        warn("0 fix patches (fix patches are optional but strongly encouraged)")

    total_patches = reg_patch_count + fix_patch_count
    info(f"Total: {total_patches} patch file(s) in quality/patches/")


# Unfilled-template sentinel phrases produced by the Phase 5 writeup stub.
# Presence of any of these strings in a writeup is strong evidence that the
# template was emitted without hydrating its content fields from BUGS.md.
# See bin/run_playbook.py::phase5_prompt for the generating prompt.
_WRITEUP_TEMPLATE_SENTINELS = (
    "is a confirmed code bug in ``",
    "The affected implementation lives at ``",
    "Patch path: ``",
    "- Regression test: ``",
    "- Regression patch: ``",
)

# Matches a ```diff fenced block and captures its body for content inspection.
_WRITEUP_DIFF_BLOCK_RE = re.compile(r"```diff\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def _writeup_diff_is_non_empty(text):
    """True if any ```diff block in ``text`` contains at least one unified-diff
    line (a `+` or `-` that is not the `+++`/`---` file-header prefix)."""
    for block in _WRITEUP_DIFF_BLOCK_RE.findall(text):
        for line in block.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("+++") or stripped.startswith("---"):
                continue
            if stripped.startswith(("+", "-")):
                return True
    return False


@verdict_category(VERDICT_SUBSTANTIVE)
def check_writeups(q, bug_count):
    """Bug writeups section (benchmark 30)."""
    print("[Bug Writeups]")
    if bug_count <= 0:
        return

    writeups_dir = _resolve_artifact_path(q, "writeups")
    writeup_count = 0
    writeup_diff_count = 0
    empty_diff_writeups = []
    sentinel_writeups = []
    if writeups_dir.is_dir():
        writeup_files = sorted(p for p in writeups_dir.glob("BUG-*.md") if p.is_file())
        writeup_count = len(writeup_files)
        for wf in writeup_files:
            try:
                text = wf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # Presence test uses the same regex as the content test so the
            # two can never disagree on whether a fence exists. Case-insensitive
            # match accepts ```diff / ```Diff / ```DIFF uniformly — operators
            # routinely uppercase the fence tag and the gate must not silently
            # skip those writeups (the content non-emptiness check would then
            # never fire, producing a confusing "no inline fix diffs" FAIL on a
            # writeup that visibly contains a unified diff).
            if _WRITEUP_DIFF_BLOCK_RE.search(text):
                writeup_diff_count += 1
                if not _writeup_diff_is_non_empty(text):
                    empty_diff_writeups.append(wf.name)
            if any(s in text for s in _WRITEUP_TEMPLATE_SENTINELS):
                sentinel_writeups.append(wf.name)

    if writeup_count >= bug_count:
        pass_(f"{writeup_count} writeup(s) for {bug_count} bug(s)")
    elif writeup_count > 0:
        fail(f"{writeup_count} writeup(s) for {bug_count} bug(s) — all confirmed bugs require writeups (SKILL.md line 1454)")
    else:
        fail(f"No writeups for {bug_count} confirmed bug(s)")

    if writeup_count > 0:
        if writeup_diff_count >= writeup_count:
            pass_(f"All {writeup_diff_count} writeup(s) have inline fix diffs")
        elif writeup_diff_count > 0:
            fail(f"Only {writeup_diff_count}/{writeup_count} writeup(s) have inline fix diffs (all require section 6 diff)")
        else:
            fail("No writeups have inline fix diffs (section 6 'The fix' must include a ```diff block)")

        # Non-empty-diff content check. A ```diff fence with no `+`/`-` body
        # is a template stub — the legacy presence-only check let these pass.
        if empty_diff_writeups:
            preview = ", ".join(empty_diff_writeups[:5])
            suffix = f" (+{len(empty_diff_writeups) - 5} more)" if len(empty_diff_writeups) > 5 else ""
            fail(
                f"{len(empty_diff_writeups)} writeup(s) have empty ```diff blocks "
                f"(fence present, no +/- lines): {preview}{suffix}"
            )
        else:
            pass_("All writeup ```diff blocks contain unified-diff content")

        # Template-sentinel check. Any of these strings remaining in a writeup
        # means the Phase 5 stub was emitted without hydrating from BUGS.md.
        if sentinel_writeups:
            preview = ", ".join(sentinel_writeups[:5])
            suffix = f" (+{len(sentinel_writeups) - 5} more)" if len(sentinel_writeups) > 5 else ""
            fail(
                f"{len(sentinel_writeups)} writeup(s) contain unfilled template "
                f"sentinels (empty backticks after 'is a confirmed code bug in', "
                f"'The affected implementation lives at', 'Patch path:', "
                f"'Regression test:', or 'Regression patch:'): {preview}{suffix}"
            )
        else:
            pass_("No writeups contain unfilled template sentinels")


# v1.5.7 089d (F24): classification rationale — kept SUBSTANTIVE.
# check_version_stamps FAILs when SKILL.md, PROGRESS.md, and the
# JSON sidecars disagree on `skill_version`. Naively this looks
# like record-keeping (the audit happened, the paperwork is
# mis-stamped) but the failure mode it catches is cross-run
# contamination — an INDEX from one version mixed with artifacts
# from another. That cross-version mix means the audit isn't
# COHERENT: the gate cannot tell which version's contract to
# enforce, and downstream consumers (compensation grid by version,
# v1.5.x schema features, benchmark replay) silently mis-apply
# rules. Per the opus-bootstrap analysis, "version stamps drifted
# across runs" looks like paperwork but is actually substrate
# corruption — keep as substantive so the gate hard-FAILs rather
# than silently downgrading to cleanup. Instruction 089d "Things
# to NOT do": "Don't bump version stamps in tracked files to
# silence F24 baseline FAILs (that defeats the cross-run-
# contamination check by design)."
@verdict_category(VERDICT_SUBSTANTIVE)
def check_version_stamps(repo_dir, q):
    """Version stamp consistency (benchmark 26). Returns detected skill_version."""
    print("[Version Stamps]")
    skill_version = detect_skill_version([
        repo_dir / "SKILL.md",
        repo_dir / ".claude" / "skills" / "quality-playbook" / "SKILL.md",
        repo_dir / ".github" / "skills" / "SKILL.md",
        repo_dir / ".github" / "skills" / "quality-playbook" / "SKILL.md",
        SCRIPT_DIR / ".." / "SKILL.md",
        SCRIPT_DIR / "SKILL.md",
    ])

    if not skill_version:
        warn("Cannot detect skill version from SKILL.md")
        return skill_version

    progress_md = q / "PROGRESS.md"
    if progress_md.is_file():
        pv = read_skill_value_line(progress_md, "Skill version:")
        if pv == skill_version:
            pass_(f"PROGRESS.md version matches ({skill_version})")
        elif pv:
            fail(f"PROGRESS.md version '{pv}' != '{skill_version}'")
        else:
            warn("PROGRESS.md missing Skill version field")

    json_path = _resolve_artifact_path(q, "results/tdd-results.json")
    if json_path.is_file():
        data = load_json(json_path)
        tv = get_str(data, "skill_version")
        if tv == skill_version:
            pass_("tdd-results.json skill_version matches")
        elif tv:
            fail(f"tdd-results.json skill_version '{tv}' != '{skill_version}'")

    return skill_version


@verdict_category(VERDICT_SUBSTANTIVE)
def check_cross_run_contamination(repo_dir, q, version_arg, skill_version):
    """Cross-run contamination detection."""
    print("[Cross-Run Contamination]")
    repo_name = repo_dir.name
    if skill_version and version_arg:
        matches = re.findall(r"[0-9]+\.[0-9]+\.[0-9]+", repo_name)
        dir_version = matches[-1] if matches else ""
        if dir_version and dir_version != skill_version:
            fail(f"Directory version '{dir_version}' != skill version '{skill_version}' — possible cross-run contamination")
        else:
            pass_("No version mismatch detected")

    json_path = _resolve_artifact_path(q, "results/tdd-results.json")
    if json_path.is_file() and skill_version:
        data = load_json(json_path)
        json_sv = get_str(data, "skill_version")
        if json_sv and json_sv != skill_version:
            fail(f"tdd-results.json skill_version '{json_sv}' != SKILL.md '{skill_version}' — stale artifacts from prior run?")


def _check_exploration_sections(path):
    """Check that EXPLORATION.md contains all required section titles."""
    required_sections = [
        "## Open Exploration Findings",
        "## Quality Risks",
        "## Pattern Applicability Matrix",
        "## Candidate Bugs for Phase 2",
        "## Gate Self-Check",
    ]
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        fail(f"EXPLORATION.md unreadable: {exc}")
        return
    for section in required_sections:
        if section not in content:
            fail(f"EXPLORATION.md missing required section: {section!r}")


@verdict_category(VERDICT_RECORD_KEEPING)
def check_run_metadata(q):
    """Validate the run-metadata sidecar JSON (run-YYYY-MM-DDTHH-MM-SS.json)."""
    print("[Run Metadata]")
    results_dir = _resolve_artifact_path(q, "results")
    pattern = str(results_dir / "run-*.json")
    import glob as _glob
    matches = _glob.glob(pattern)
    if not matches:
        fail("run-metadata JSON missing (expected quality/results/run-YYYY-MM-DDTHH-MM-SS.json)")
        return
    if len(matches) > 1:
        warn(f"Multiple run-metadata files found: {len(matches)}")
    filename_re = re.compile(r"run-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.json$")
    for path in matches:
        if not filename_re.search(path):
            fail(f"run-metadata filename does not match expected format: {path}")
        data = load_json(Path(path))
        if data is None:
            fail(f"run-metadata JSON parse error: {path}")
            continue
        required_fields = ("schema_version", "skill_version", "project", "model", "runner", "start_time")
        for field in required_fields:
            if not data.get(field):
                fail(f"run-metadata missing or empty field: {field!r}")
    pass_("run-metadata JSON present")


# --- Per-repo entry point ---


# ---------------------------------------------------------------------------
# v1.5.1 Layer-1 mechanical invariants (schemas.md §10).
#
# Each check gracefully no-ops on pre-v1.5.1 runs (absent manifests = legacy
# repo; nothing to enforce). When the v1.5.1 artifacts are present every
# invariant below is enforced mechanically and FAILs with a specific
# <path>: <reason> message so the operator can fix the single artifact
# without re-running the whole playbook.
# ---------------------------------------------------------------------------

_V150_VALID_DISPOSITIONS = (
    "code-fix",
    "spec-fix",
    "upstream-spec-issue",
    "mis-read",
    "deferred",
)
_V150_VALID_FIX_TYPES = ("code", "spec", "both")
_V150_ILLEGAL_FIX_PAIRS = {
    ("code-fix", "spec"),
    ("spec-fix", "code"),
    ("upstream-spec-issue", "code"),
    ("mis-read", "both"),
}
_V150_SUPPORTED_EXTENSIONS = (".txt", ".md")
# v1.5.4 Part 1 / Round 1 Council finding C2-1: INDEX schema is now
# version-routed. New runs MUST emit schema_version "2.0" with
# target_role_breakdown; legacy archives carry schema_version "1.0"
# (or no schema_version at all) with target_project_type. The fields
# common to both schemas live in _V150_INDEX_COMMON_FIELDS; the
# version-specific fields live in their own tuples and are picked at
# validation time.
#
# v1.5.4 Round 2 Council finding C1: SCHEMA_VERSION_CURRENT pins the
# version this gate understands. Future schemas (>2.0) refuse with an
# explicit error rather than silently downgrading to legacy. When a
# v1.5.5+ run bumps the schema, also bump this constant; otherwise the
# new gate version will reject the new INDEX shape on purpose.
SCHEMA_VERSION_CURRENT = "2.0"
_V150_INDEX_COMMON_FIELDS = (
    "run_timestamp_start",
    "run_timestamp_end",
    "duration_seconds",
    "qpb_version",
    "target_repo_path",
    "target_repo_git_sha",
    "phases_executed",
    "summary",
    "artifacts",
)
_V150_INDEX_LEGACY_FIELDS = ("target_project_type",)
_V154_INDEX_CURRENT_FIELDS = ("target_role_breakdown",)
# Legacy alias: a small number of pre-iteration tests still import
# _V150_REQUIRED_INDEX_FIELDS expecting a single tuple. Preserve the
# alias under the v1.5.4-current contract; the version-routed
# enforcement happens inside check_v1_5_0_index_md.
_V150_REQUIRED_INDEX_FIELDS = (
    _V150_INDEX_COMMON_FIELDS + _V154_INDEX_CURRENT_FIELDS
)
_V150_REQUIRED_SUMMARY_KEYS = ("requirements", "bugs", "gate_verdict")


# ---------------------------------------------------------------------------
# v1.5.3 — schema extensions (schemas.md §3.6–§3.10, §4.1, §6.1, §8.1, §10
# invariants #21–#23). Field-presence detection (§3.10) toggles the
# v1.5.3 invariants on per-manifest, NOT a schema_version comparison.
# ---------------------------------------------------------------------------

_V153_VALID_SOURCE_TYPES = (
    "code-derived",
    "skill-section",
    "reference-file",
    "execution-observation",
    # v1.5.6 (QG-fail-2 from the v1.5.6 self-bootstrap): REQs derived from
    # operator-supplied informal documentation under the target repo's
    # `reference_docs/` tree. Distinct from `reference-file`, which
    # schemas.md §3.7 ties to QPB-shipped reference files under
    # `references/`. The Phase 2 LLM disambiguates the two evidence
    # sources by name; the schema and gate now match.
    "docs-derived",
    # v1.6.0 (Feature D): REQ confirmed/corrected/added by the operator in a
    # requirements validation interview. Transcript-as-citable-source —
    # REQ.citation points into quality/review_sessions/<TS>-<topic>.md.
    # skill_section stays absent/null (invariant #21), which the sibling
    # check_v1_5_3_skill_section_consistency already enforces for every
    # non-'skill-section' source_type.
    "operator-confirmation",
)
_V153_VALID_DIVERGENCE_TYPES = (
    "code-spec",
    "internal-prose",
    "prose-to-code",
    "execution",
)
_V153_VALID_FORMAL_DOC_ROLES = (
    "external-spec",
    "project-spec",
    "skill-self-spec",
    "skill-reference",
)

# DQ-3 (v1.5.3 Phase 3 / Round 2 Council): the v1.5.3 field-presence
# detection key set is module-level so a regression test can pin it
# against schemas.md's enum-bearing field list. A future schema
# addition (e.g., a fifth v1.5.3-only field) that updates ONLY this
# constant without updating the test's literal will fail the regression
# test, forcing lockstep maintenance and surfacing the change for
# explicit review.
_V153_FIELD_KEYS = frozenset({"source_type", "divergence_type", "role"})


# v1.5.7 instruction 089 (F9 — bootstrap WARN investigation, KEEP
# decision): the formal_docs / requirements / bugs "legacy manifest
# detected" WARNs are a DELIBERATE, documented backward-compat shim,
# NOT v1.5.6-era cruft. The v1.5.3 schema extension (schemas.md
# §3.6–§3.10) added the role / source_type / divergence_type fields
# (_V153_FIELD_KEYS). A manifest carrying NONE of them is "pre-v1.5.3
# shaped"; the gate applies the schemas.md §3.10 documented defaults
# (role→external-spec, source_type→code-derived, divergence_type→
# code-spec) and WARN+skips strict validation rather than hard-FAILing
# a repo last audited before v1.5.3. KEEP rationale: removing the shim
# would hard-FAIL every pre-v1.5.3 manifest — a breaking change
# inappropriate for the v1.5.7 patch-stabilization line; adopters on
# old manifests would have to re-run Phase 2 with no warning. The
# WARN text is clarified (089) to say the documented default was
# applied (not a defect); behavior unchanged. When v1.6.0 drops
# pre-v1.5.3 manifest compat, remove this shim + the three checks'
# legacy branches and add a CHANGELOG breaking-change note.
def _is_v1_5_3_shaped(manifest):
    """Return True iff any record in *manifest* carries a v1.5.3 field.

    Walks the records (or `reviews`) once. Presence of any key in
    _V153_FIELD_KEYS on any record toggles strict-mode validation per
    schemas.md §3.10. Empty / unparsable manifests return False so
    legacy fixtures stay on the soft-warn path.

    DQ-3 design note: the checked-key set is sourced from
    _V153_FIELD_KEYS (a module-level frozenset) rather than hardcoded
    in this function's body. A regression test in
    test_quality_gate.py::TestV153FieldKeysContract pins
    _V153_FIELD_KEYS against the literal `{"source_type",
    "divergence_type", "role"}` so a future maintainer adding a
    v1.5.3-only field to the schema cannot silently miss updating the
    detection helper.
    """
    if not isinstance(manifest, dict):
        return False
    records = manifest.get("records")
    if not isinstance(records, list):
        records = manifest.get("reviews") if isinstance(
            manifest.get("reviews"), list
        ) else []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if not _V153_FIELD_KEYS.isdisjoint(rec.keys()):
            return True
    return False


def _v150_manifest(q, name):
    """Return the parsed top-level JSON object or None if absent/invalid."""
    path = q / name
    if not path.is_file():
        return None
    data = load_json(path)
    if isinstance(data, dict):
        return data
    fail(f"{path.name}: not a valid JSON object (schemas.md §1.6)")
    return None


@verdict_category(VERDICT_SUBSTANTIVE)
def check_v1_5_0_cite_extensions(repo_dir):
    """§10 invariant #9 — reference_docs/cite/ contains only .txt/.md.

    v1.5.2 collapsed the old formal_docs/+informal_docs/ split into a single
    reference_docs/ tree with reference_docs/cite/ holding citable material.
    The plaintext-only constraint now applies to that cite folder; the check
    retains the v1.5.0 invariant ancestry (hence the _v1_5_0_ name prefix).
    """
    folder = repo_dir / "reference_docs" / "cite"
    if not folder.is_dir():
        return
    any_file = False
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        any_file = True
        if path.name == "README.md":
            continue
        if path.name.endswith(".meta.json"):
            continue
        # v1.5.6 (QG-fail-1 from the v1.5.6 self-bootstrap): `.gitkeep`
        # is the documented sentinel that pins `reference_docs/cite/`
        # in version control even when adopters have no citable
        # plaintext yet. The pre-flight expects it to exist; the gate
        # must not reject it.
        if path.name == ".gitkeep":
            continue
        ext = path.suffix.lower()
        if ext not in _V150_SUPPORTED_EXTENSIONS:
            rel = path.relative_to(repo_dir).as_posix()
            fail(
                f"{rel}: unsupported extension {ext or '(none)'} under reference_docs/cite/ "
                "(schemas.md §2 allows only .txt, .md; §10 invariant #9)"
            )
    if any_file:
        pass_("reference_docs/cite/: all files use supported extensions")


@verdict_category(VERDICT_RECORD_KEEPING)
def check_v1_5_0_manifest_wrappers(q):
    """§10 invariant #13 — manifest wrapper shape.

    Four record-shaped manifests (formal_docs / requirements / use_cases /
    bugs) use `records`; citation_semantic_check.json uses `reviews`
    (schemas.md §9.1). Every manifest must carry schema_version +
    generated_at as non-empty strings.
    """
    record_shaped = (
        "formal_docs_manifest.json",
        "requirements_manifest.json",
        "use_cases_manifest.json",
        "bugs_manifest.json",
    )
    for name in record_shaped:
        data = _v150_manifest(q, name)
        if data is None:
            continue
        for key in ("schema_version", "generated_at"):
            if not isinstance(data.get(key), str) or not data[key]:
                fail(f"{name}: missing or empty top-level {key!r} (schemas.md §1.6)")
        if not isinstance(data.get("records"), list):
            fail(f"{name}: missing or non-array top-level 'records' (schemas.md §1.6)")
        if "reviews" in data:
            fail(
                f"{name}: has 'reviews' key — reserved for citation_semantic_check.json "
                "per schemas.md §9.1 / §10 invariant #13"
            )
        else:
            pass_(f"{name}: manifest wrapper valid")

    data = _v150_manifest(q, "citation_semantic_check.json")
    if data is not None:
        for key in ("schema_version", "generated_at"):
            if not isinstance(data.get(key), str) or not data[key]:
                fail(
                    f"citation_semantic_check.json: missing or empty top-level {key!r} "
                    "(schemas.md §1.6)"
                )
        if not isinstance(data.get("reviews"), list):
            fail(
                "citation_semantic_check.json: missing or non-array top-level 'reviews' "
                "(schemas.md §9.1 — semantic check uses 'reviews', not 'records')"
            )
        if "records" in data:
            fail(
                "citation_semantic_check.json: has 'records' key — semantic check uses "
                "'reviews' per schemas.md §9.1 / §10 invariant #13"
            )
        else:
            pass_("citation_semantic_check.json: manifest wrapper valid")


def _check_citation_block(repo_dir, req_id, citation, formal_docs_by_path, req_tier):
    excerpt = citation.get("citation_excerpt")
    if not isinstance(excerpt, str) or not excerpt:
        fail(
            "requirements_manifest.json",
            f"record_id={req_id}: citation has empty or missing citation_excerpt "
            "(schemas.md §10 invariant #4)",
        )
        return
    doc_path_str = citation.get("document")
    if not isinstance(doc_path_str, str) or not doc_path_str:
        fail(
            "requirements_manifest.json",
            f"record_id={req_id}: citation missing 'document' field",
        )
        return
    section = citation.get("section")
    line = citation.get("line")
    has_section = isinstance(section, str) and section.strip()
    has_line = isinstance(line, int) and not isinstance(line, bool)
    if not has_section and not has_line:
        fail(
            "requirements_manifest.json",
            f"record_id={req_id}: citation has no section or line locator "
            "(page alone is insufficient; schemas.md §10 invariant #4)",
        )
        return

    fd_rec = formal_docs_by_path.get(doc_path_str)
    if fd_rec is None:
        fail(
            "requirements_manifest.json",
            f"record_id={req_id}: citation document {doc_path_str!r} "
            "not in formal_docs_manifest.json (schemas.md §10 invariant #2)",
        )
        return
    fd_tier = fd_rec.get("tier")
    if fd_tier != req_tier:
        fail(
            "requirements_manifest.json",
            f"record_id={req_id}: tier={req_tier} does not match cited FORMAL_DOC "
            f"tier={fd_tier!r} (schemas.md §10 invariant #14)",
        )
    fd_sha = fd_rec.get("document_sha256")
    cite_sha = citation.get("document_sha256")
    if isinstance(fd_sha, str) and isinstance(cite_sha, str) and fd_sha != cite_sha:
        fail(
            "requirements_manifest.json",
            f"record_id={req_id}: citation.document_sha256 does not match FORMAL_DOC "
            "(schemas.md §10 invariant #3 — citation_stale)",
        )

    if _CITATION_VERIFIER is None:
        warn(
            f"requirements_manifest.json: record_id={req_id}: byte-equality skipped — "
            "bin/citation_verifier unavailable on this install"
        )
        return

    doc_path = repo_dir / doc_path_str
    if not doc_path.is_file():
        fail(
            "requirements_manifest.json",
            f"record_id={req_id}: citation document not on disk: {doc_path_str}",
        )
        return
    try:
        bytes_ = doc_path.read_bytes()
        fresh = _CITATION_VERIFIER.extract_excerpt(
            bytes_, doc_path.suffix.lower(), section if has_section else None,
            line if has_line else None,
        )
    except _CITATION_VERIFIER.CitationResolutionError as exc:
        fail(
            "requirements_manifest.json",
            f"record_id={req_id}: citation location does not resolve in "
            f"{doc_path_str}: {exc.message} (schemas.md §10 invariant #4)",
        )
        return
    except Exception as exc:  # noqa: BLE001 — fail with a real message
        fail(
            "requirements_manifest.json",
            f"record_id={req_id}: citation verifier errored: {exc}",
        )
        return

    if fresh != excerpt:
        fail(
            "requirements_manifest.json",
            f"record_id={req_id}: citation_excerpt is not byte-equal to fresh "
            f"extraction from {doc_path_str} "
            "(schemas.md §10 invariant #11 — Layer-1 anti-hallucination)",
        )


@verdict_category(VERDICT_RECORD_KEEPING)
def check_v1_5_0_requirements_manifest(repo_dir, q):
    """§10 invariants #1, #4, #8, #11, #14 — REQ shape, citation gating, functional_section."""
    req_data = _v150_manifest(q, "requirements_manifest.json")
    if req_data is None:
        return
    records = req_data.get("records")
    if not isinstance(records, list):
        return  # wrapper check already reported
    fd_data = _v150_manifest(q, "formal_docs_manifest.json")
    formal_docs_by_path = {}
    if fd_data and isinstance(fd_data.get("records"), list):
        for rec in fd_data["records"]:
            if isinstance(rec, dict) and isinstance(rec.get("source_path"), str):
                formal_docs_by_path[rec["source_path"]] = rec

    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            fail(
                "requirements_manifest.json",
                f"record_id=<#{idx}>: not a JSON object",
            )
            continue
        req_id = rec.get("id", f"<#{idx}>")

        fs = rec.get("functional_section")
        if not isinstance(fs, str) or not fs.strip():
            fail(
                "requirements_manifest.json",
                f"record_id={req_id}: has empty or missing functional_section "
                "(schemas.md §10 invariant #8)",
            )

        tier = rec.get("tier")
        citation = rec.get("citation")
        if tier in (1, 2):
            if not isinstance(citation, dict):
                fail(
                    "requirements_manifest.json",
                    f"record_id={req_id}: is tier {tier} but has no citation block "
                    "(schemas.md §10 invariant #1)",
                )
                continue
            _check_citation_block(repo_dir, req_id, citation, formal_docs_by_path, tier)
        elif tier in (3, 4, 5):
            if citation is not None:
                fail(
                    "requirements_manifest.json",
                    f"record_id={req_id}: is tier {tier} but carries a citation block "
                    "(citations are for Tier 1/2 only per schemas.md §10 invariant #1)",
                )
        elif tier is None:
            fail(
                "requirements_manifest.json",
                f"record_id={req_id}: missing 'tier' field",
            )
        else:
            fail(
                "requirements_manifest.json",
                f"record_id={req_id}: has invalid tier {tier!r} (expected integer 1–5)",
            )

        # v1.5.2: validate the optional `pattern` field on the REQ record.
        pattern = rec.get("pattern")
        if pattern is not None and pattern not in VALID_PATTERN_VALUES:
            fail(
                "requirements_manifest.json",
                f"record_id={req_id}: has invalid pattern {pattern!r} "
                f"(expected one of {sorted(VALID_PATTERN_VALUES)})",
            )

    pass_("requirements_manifest.json: v1.5.1 Layer-1 REQ checks complete")


_V157_CANONICAL_SEVERITIES = ("HIGH", "MEDIUM", "LOW")


@verdict_category(VERDICT_RECORD_KEEPING)
def check_v1_5_0_bugs_manifest(q):
    """§10 invariants #7, #12 — disposition completeness + legal fix_type × disposition.

    v1.5.7 fix Q3: also emits a WARN per record whose `severity`
    field is non-canonical case. The canonical case per schemas.md
    §3.3 is uppercase (HIGH / MEDIUM / LOW). Non-canonical values
    (`high`, `Medium`, `low`, etc.) are auto-normalized at read-time
    elsewhere in the codebase but the raw record drift here is
    surfaced as WARN — auto-normalize + warn is the operator-friendly
    choice (tightening to FAIL would break adopters with legacy
    lowercase entries; ignoring the drift lets it spread).
    """
    data = _v150_manifest(q, "bugs_manifest.json")
    if data is None:
        return
    records = data.get("records")
    if not isinstance(records, list):
        return
    severity_drift: list[tuple[str, str]] = []
    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            continue
        bug_id = rec.get("id", f"<#{idx}>")
        # v1.5.7 fix Q3: severity-case check (WARN, not FAIL).
        sev_raw = rec.get("severity")
        if isinstance(sev_raw, str) and sev_raw.strip():
            sev_normalized = sev_raw.strip().upper()
            if sev_normalized in _V157_CANONICAL_SEVERITIES and sev_raw.strip() != sev_normalized:
                severity_drift.append((bug_id, sev_raw))
        disp = rec.get("disposition")
        if disp not in _V150_VALID_DISPOSITIONS:
            fail(
                "bugs_manifest.json",
                f"record_id={bug_id}: has invalid or missing disposition {disp!r} "
                f"(schemas.md §10 invariant #7, valid: "
                f"{', '.join(_V150_VALID_DISPOSITIONS)})",
            )
            continue
        rationale = rec.get("disposition_rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            fail(
                "bugs_manifest.json",
                f"record_id={bug_id}: has empty or missing disposition_rationale "
                "(schemas.md §10 invariant #7)",
            )
        ft = rec.get("fix_type")
        if ft not in _V150_VALID_FIX_TYPES:
            fail(
                "bugs_manifest.json",
                f"record_id={bug_id}: has invalid or missing fix_type {ft!r}",
            )
            continue
        if (disp, ft) in _V150_ILLEGAL_FIX_PAIRS:
            fail(
                "bugs_manifest.json",
                f"record_id={bug_id}: illegal disposition × fix_type combination "
                f"({disp}, {ft}) per schemas.md §3.4 / §10 invariant #12",
            )

    if severity_drift:
        # v1.5.7 fix Q3: surface non-canonical severity case as WARN so
        # the drift is visible without breaking back-compat. Pre-Q3 the
        # field went through `.upper()` silently for the challenge-gate
        # check — drift accumulated invisibly across runs.
        examples = ", ".join(
            f"{bug_id}={sev!r}" for bug_id, sev in severity_drift[:5]
        )
        more = f" (+ {len(severity_drift) - 5} more)" if len(severity_drift) > 5 else ""
        warn(
            f"bugs_manifest.json: {len(severity_drift)} BUG record(s) "
            f"have non-canonical severity case (schemas.md §3.3 mandates "
            f"HIGH / MEDIUM / LOW uppercase): {examples}{more}. Auto-"
            f"normalized for downstream checks; rewrite the records to "
            f"the canonical case to silence the warning."
        )

    pass_("bugs_manifest.json: v1.5.1 Layer-1 BUG checks complete")


# v1.5.7 instruction 090j: triage precision guardrails — D1 reachability,
# D2 KNOWN-ISSUE classification, D3 tighter security-HIGH bar. Surfaced by
# the 2026-05-23 OpenFGA Mode-A dogfood: 0/3 HIGH findings were real
# (BUG-003 missed an upstream tryCache guard; BUG-006 missed an upstream
# userType filter AND cited a CVE whose affected range doesn't include
# v1.5.7; BUG-009 was a verbatim CVE restatement, no in-tree defect).
# This check is the v1.5.7 band-aid — same-agent triage rules enforced at
# the manifest. The fresh-context FP-audit sub-agent + first-class NFR
# derivation are reserved for v1.6.0.

# Heuristic substrings (case-insensitive) that say "the audited version
# is within the cited CVE's affected range." When `cve_reference` is set
# and `cve_version_applies` is missing/None, the gate looks for any of
# these substrings in `reachability_analysis` as a fallback — adopters
# who write the prose but forget the boolean flag should not be
# auto-failed. If neither the boolean nor the prose marker is present,
# the gate FAILs per D3.
_CVE_APPLIES_PROSE_MARKERS: tuple[str, ...] = (
    "version is within the affected range",
    "version is within the cited",
    "audited version is in the affected range",
    "in the affected range",
    "cve applies",
    "cve_version_applies=true",
)
_HIGH_MED_SEVERITIES: frozenset = frozenset({"HIGH", "MEDIUM"})


def _has_cve_applies_prose_marker(text: str) -> bool:
    """True iff a reachability_analysis string contains a phrase that
    clearly asserts the audited version is within the cited CVE's
    affected range."""
    if not isinstance(text, str):
        return False
    lowered = text.lower()
    return any(m in lowered for m in _CVE_APPLIES_PROSE_MARKERS)


@verdict_category(VERDICT_RECORD_KEEPING)
def check_v1_5_7_090j_triage_precision(q):
    """v1.5.7 090j — D1 (reachability) + D2 (KNOWN-ISSUE) + D3 (security-HIGH).

    For each record in ``bugs_manifest.json`` classified as a `bug` (or
    absent classification — default is `bug`):

      * D1: severity HIGH/MEDIUM requires a non-empty
        ``reachability_analysis`` field — FAIL absent. severity LOW
        requires it too but absence is a WARN, not a FAIL.
      * D2: when ``cve_reference`` is set, ``classification`` must be
        ``known-issue`` OR the record MUST carry a non-empty
        ``reachability_analysis`` documenting the in-tree code path
        (i.e. the finding was independently located, not advisory-only).
        FAIL otherwise.
      * D3: when ``cve_reference`` is set AND severity is HIGH, the
        record MUST also have ``cve_version_applies == true`` (or, as a
        prose fallback, a `reachability_analysis` substring stating the
        audited version is within the CVE's affected range). FAIL if
        ``cve_version_applies`` is missing or false AND the prose
        fallback is absent.

    Records with ``classification == "known-issue"`` are excluded from
    these checks (advisory notes are recorded for adopter awareness;
    they are not bugs).

    Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160) — bites are documented
    inline in the test class
    ``TestTriagePrecisionGuardrails090j``:
      D1: drop the ``reachability_analysis`` field from a HIGH bug →
        fail. Restoring the field re-greens the test.
      D2: keep ``cve_reference`` but drop ``classification`` ⇒
        default `bug` ⇒ advisory-only-without-reachability FAILs.
      D3: HIGH + ``cve_reference`` + ``cve_version_applies=False`` →
        fail. Flip to True → pass.
    """
    data = _v150_manifest(q, "bugs_manifest.json")
    if data is None:
        return
    records = data.get("records")
    if not isinstance(records, list):
        return

    d1_fails: list[str] = []
    d1_warns: list[str] = []
    d2_fails: list[str] = []
    d3_fails: list[str] = []

    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            continue
        bug_id = rec.get("id", f"<#{idx}>")
        classification = rec.get("classification", "bug")
        # Records explicitly classified as known-issue/advisory-note
        # are recorded for adopter awareness and excluded from these
        # bug-precision checks. (They remain subject to the other
        # bugs_manifest checks.)
        if classification == "known-issue":
            continue

        sev_raw = rec.get("severity")
        sev = sev_raw.strip().upper() if isinstance(sev_raw, str) else ""
        reach = rec.get("reachability_analysis")
        reach_present = isinstance(reach, str) and bool(reach.strip())
        cve_ref = rec.get("cve_reference")
        cve_set = isinstance(cve_ref, str) and bool(cve_ref.strip())
        cve_applies = rec.get("cve_version_applies")

        # D1: reachability analysis required on HIGH/MEDIUM bugs.
        if sev in _HIGH_MED_SEVERITIES and not reach_present:
            d1_fails.append(
                f"record_id={bug_id} severity={sev}: missing or empty "
                f"`reachability_analysis` (v1.5.7 090j D1 — show the "
                f"upstream-guard / filter / early-return / compensation "
                f"search performed before confirming the bug; if the "
                f"finding has no in-tree defect, reclassify as "
                f"classification=known-issue)"
            )
        elif sev == "LOW" and not reach_present:
            d1_warns.append(
                f"record_id={bug_id} severity=LOW: missing "
                f"`reachability_analysis` (v1.5.7 090j D1 recommended; "
                f"WARN, not FAIL, on LOW)"
            )

        # D2: advisory-only finding classified as bug.
        if cve_set and not reach_present:
            d2_fails.append(
                f"record_id={bug_id} cve_reference={cve_ref!r}: an "
                f"advisory/CVE-cited finding with no "
                f"`reachability_analysis` cannot be classification=bug "
                f"(v1.5.7 090j D2 — reclassify as "
                f"classification=known-issue, or add a reachability "
                f"analysis that locates the in-tree code defect)"
            )

        # D3: security-HIGH bar — CVE-cited HIGH requires version
        # applicability evidence.
        if sev == "HIGH" and cve_set:
            applies_true = (cve_applies is True)
            prose_fallback = (
                reach_present and _has_cve_applies_prose_marker(reach)
            )
            if not (applies_true or prose_fallback):
                d3_fails.append(
                    f"record_id={bug_id} severity=HIGH "
                    f"cve_reference={cve_ref!r}: missing "
                    f"`cve_version_applies=true` AND no prose marker "
                    f"in `reachability_analysis` asserting the audited "
                    f"version is within the CVE's affected range "
                    f"(v1.5.7 090j D3 — security-HIGH on a CVE basis "
                    f"requires the audited version to be verified IN "
                    f"the CVE's affected range; otherwise downgrade "
                    f"severity or reclassify as "
                    f"classification=known-issue)"
                )

    # Emit per-rule failures.
    for msg in d1_fails:
        fail("bugs_manifest.json", msg)
    for msg in d2_fails:
        fail("bugs_manifest.json", msg)
    for msg in d3_fails:
        fail("bugs_manifest.json", msg)
    for msg in d1_warns:
        warn(msg)

    if not (d1_fails or d2_fails or d3_fails):
        pass_(
            "bugs_manifest.json: v1.5.7 090j triage precision "
            "(D1 reachability + D2 known-issue + D3 security-HIGH) "
            "complete"
        )


@verdict_category(VERDICT_SUBSTANTIVE)
def check_v1_5_0_index_md(q):
    """§10 invariant #10 — quality/INDEX.md exists with all §11 required fields.

    v1.5.4 Part 1 / Round 1 Council finding C2-1 + Round 2 Council
    finding C1: routes by INDEX payload.schema_version with explicit
    handling for each case so future schemas don't silently downgrade.

      - ``schema_version == SCHEMA_VERSION_CURRENT`` (currently
        ``"2.0"``) → the v1.5.4 contract; target_role_breakdown
        required (null is legitimate for the stub before Phase 1).
      - ``schema_version == "1.0"`` → legacy v1.5.3 archive;
        target_project_type required; one WARN emitted.
      - ``schema_version`` absent/empty AND payload carries
        target_project_type without target_role_breakdown → legacy
        WARN (heuristic fallback for pre-schema-version archives).
      - ``schema_version`` absent/empty AND payload doesn't match the
        legacy heuristic → current path; the run is treated as a
        v1.5.4 stub that simply hasn't populated schema_version yet,
        and target_role_breakdown is required.
      - any other ``schema_version`` (e.g. ``"3.0"`` from a future
        gate) → explicit FAIL "newer than supported" so the operator
        knows to upgrade the gate or downgrade the run.

    This keeps historical archives under quality/previous_runs/
    legible without rewriting them retroactively while keeping the
    gate strict on current runs.
    """
    path = q / "INDEX.md"
    v150_artifacts = (
        "formal_docs_manifest.json",
        "requirements_manifest.json",
        "use_cases_manifest.json",
        "bugs_manifest.json",
        "citation_semantic_check.json",
    )
    is_v150_run = any((q / name).is_file() for name in v150_artifacts)
    if not path.is_file():
        if is_v150_run:
            fail(
                "quality/INDEX.md does not exist (required on every v1.5.1 run per "
                "schemas.md §10 invariant #10)"
            )
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)
    if not match:
        fail("quality/INDEX.md: no fenced JSON block found (schemas.md §11)")
        return
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        fail(f"quality/INDEX.md: fenced JSON block invalid: {exc}")
        return
    if not isinstance(payload, dict):
        fail("quality/INDEX.md: fenced JSON block is not a JSON object")
        return

    # Schema-version routing for INDEX.md (v1.5.4 Round 2 Council
    # finding C1). Four cases, handled explicitly so future schemas
    # don't silently downgrade to legacy:
    #   1. schema_version == "1.0"                       -> legacy WARN
    #   2. schema_version absent/empty AND the payload   -> legacy WARN
    #      carries target_project_type but not              (heuristic
    #      target_role_breakdown                             fallback for
    #                                                        pre-schema-
    #                                                        version
    #                                                        archives)
    #   3. schema_version == SCHEMA_VERSION_CURRENT      -> current path
    #   4. schema_version absent/empty AND the payload
    #      doesn't fit case 2                            -> current path
    #                                                       (FAIL on
    #                                                        missing
    #                                                        target_role_breakdown
    #                                                        because the
    #                                                        run is
    #                                                        ambiguous and
    #                                                        v1.5.4 is the
    #                                                        live shape)
    #   5. any other schema_version                      -> explicit FAIL
    #                                                       "newer than
    #                                                        supported"
    schema_version = payload.get("schema_version")
    if schema_version == "1.0":
        is_legacy = True
    elif schema_version in (None, ""):
        is_legacy = (
            "target_project_type" in payload
            and "target_role_breakdown" not in payload
        )
    elif schema_version == SCHEMA_VERSION_CURRENT:
        is_legacy = False
    else:
        fail(
            f"quality/INDEX.md: schema_version {schema_version!r} is "
            f"newer than this gate supports (current: "
            f"{SCHEMA_VERSION_CURRENT!r}). Upgrade the gate or "
            "downgrade the run."
        )
        return

    if is_legacy:
        warn(
            f"quality/INDEX.md: schema_version={schema_version!r} treated as "
            "legacy v1.5.3 archive (target_project_type contract). v1.5.4+ "
            f"runs MUST emit schema_version={SCHEMA_VERSION_CURRENT!r} with "
            "target_role_breakdown."
        )
        required = _V150_INDEX_COMMON_FIELDS + _V150_INDEX_LEGACY_FIELDS
    else:
        required = _V150_INDEX_COMMON_FIELDS + _V154_INDEX_CURRENT_FIELDS

    for key in required:
        if key not in payload:
            fail(f"quality/INDEX.md: missing required field {key!r} (schemas.md §11)")
            continue
        val = payload[key]
        if isinstance(val, str) and not val:
            fail(f"quality/INDEX.md: field {key!r} is empty string (schemas.md §11)")
    summary = payload.get("summary")
    # v1.5.7 089e (BUG-011): non-dict `summary` (string / null / list /
    # anything other than a JSON object) is a §11 contract violation —
    # schemas.md:1128 says `summary | object | yes`. Pre-089e the
    # `if isinstance(summary, dict)` guard silently skipped the
    # required-keys loop and the trailing `pass_` fired anyway, so the
    # gate soft-passed `summary: "pending"` / `summary: null` /
    # `summary: []` while validate_phase_artifacts FAILed them. Mirror
    # the validator's FAIL message shape (bin/validate_phase_artifacts.
    # py:_validate_index). Early-return so the trailing pass_ doesn't
    # claim "§11 fields present" against a structurally-broken INDEX.
    if not isinstance(summary, dict):
        fail(
            f"quality/INDEX.md: §11 'summary' must be a JSON object "
            f"(got {type(summary).__name__!r}; schemas.md:1128 requires "
            f"`summary | object | yes`)"
        )
        return
    for sub in _V150_REQUIRED_SUMMARY_KEYS:
        if sub not in summary:
            fail(
                f"quality/INDEX.md: summary missing {sub!r} sub-key "
                "(schemas.md §11)"
            )
    # v1.5.10 058 (D2): conditional multi-language disclosure fields. When
    # >=2 testable languages clear the disclosure threshold, the persisted
    # §11 summary MUST carry languages_detected / ran_on /
    # untested_testable_languages. This is gated on the SAME is_legacy
    # exemption used above (archived legacy-schema runs predate the field
    # and are not re-failed) and is NOT added to
    # _V150_REQUIRED_SUMMARY_KEYS (that loop is unconditional and would
    # FAIL every single-language and archived run). Detection is on the
    # repo (q.parent); a single-language repo never fires it, so existing
    # single-language runs are unaffected.
    if not is_legacy and _disclosure_fires(detect_project_languages(q.parent)):
        for sub in (
            "languages_detected", "ran_on", "untested_testable_languages",
        ):
            if sub not in summary:
                fail(
                    f"quality/INDEX.md: summary missing {sub!r} sub-key — "
                    "required because >=2 testable languages clear the "
                    "disclosure threshold (schemas.md §11; v1.5.10 058)"
                )
            elif summary[sub] in (None, "", []):
                fail(
                    f"quality/INDEX.md: summary {sub!r} is empty — multi-"
                    "language disclosure requires a value (schemas.md §11; "
                    "v1.5.10 058)"
                )
    pass_("quality/INDEX.md: §11 fields present")


_V150_VALID_VERDICTS = ("supports", "overreaches", "unclear")


@verdict_category(VERDICT_SUBSTANTIVE)
def check_v1_5_0_semantic_check(q):
    """§10 invariant #17 — Council-of-Three majority-overreaches rule.

    Layer-2 semantic check (Phase 6). Gate does NOT re-run the semantic
    review; it parses quality/citation_semantic_check.json and applies
    the majority-overreaches rule:

      - ≥2 of 3 `overreaches` for the same Tier 1/2 REQ → FAIL.
      - isolated 1/3 `overreaches` or `unclear` → WARN.
      - <3 reviews for any Tier 1/2 REQ → FAIL (schemas.md §9.4).
      - review entry for a Tier 3/4/5 REQ → FAIL (only Tier 1/2 are
        semantically reviewable since they carry citations).

    When requirements_manifest.json has zero Tier 1/2 REQs the
    citation_semantic_check.json file is still expected (emitted with
    empty reviews[]); its absence in that case warns rather than
    fails to avoid breaking Spec Gap runs.
    """
    req_data = _v150_manifest(q, "requirements_manifest.json")
    tier_by_req = {}
    if req_data and isinstance(req_data.get("records"), list):
        for rec in req_data["records"]:
            if isinstance(rec, dict):
                rid = rec.get("id")
                tier = rec.get("tier")
                if isinstance(rid, str) and isinstance(tier, int) and not isinstance(tier, bool):
                    tier_by_req[rid] = tier
    tier_12_req_ids = {rid for rid, t in tier_by_req.items() if t in (1, 2)}

    sc_path = q / "citation_semantic_check.json"
    if not sc_path.is_file():
        if tier_12_req_ids:
            fail(
                "quality/citation_semantic_check.json",
                "file missing (schemas.md §10 invariant #17 requires a semantic "
                "check for every Tier 1/2 REQ)",
            )
        else:
            # Spec Gap: no Tier 1/2 REQs to review. File is expected but its
            # absence doesn't break the invariant since there's nothing to
            # enforce. Warn so the orchestrator knows to emit the empty file.
            warn(
                "quality/citation_semantic_check.json: file missing; no Tier 1/2 "
                "REQs present so invariant #17 has nothing to enforce — emit an "
                "empty reviews[] for contract completeness"
            )
        return

    data = _v150_manifest(q, "citation_semantic_check.json")
    if data is None:
        return  # wrapper check already reported the failure
    reviews = data.get("reviews")
    if not isinstance(reviews, list):
        return  # wrapper check already reported

    by_req = {}
    seen_reviewers = {}
    for idx, entry in enumerate(reviews):
        if not isinstance(entry, dict):
            fail(
                "citation_semantic_check.json",
                f"reviews[#{idx}]: not a JSON object",
            )
            continue
        rid = entry.get("req_id")
        reviewer = entry.get("reviewer")
        verdict = entry.get("verdict")
        notes = entry.get("notes")
        if not isinstance(rid, str) or not rid:
            fail(
                "citation_semantic_check.json",
                f"reviews[#{idx}]: missing or non-string req_id",
            )
            continue
        if not isinstance(reviewer, str) or not reviewer:
            fail(
                "citation_semantic_check.json",
                f"record_id={rid}: missing or non-string reviewer",
            )
            continue
        if verdict not in _V150_VALID_VERDICTS:
            fail(
                "citation_semantic_check.json",
                f"record_id={rid}: reviewer={reviewer!r} invalid verdict "
                f"{verdict!r}; expected one of {_V150_VALID_VERDICTS}",
            )
            continue
        if not isinstance(notes, str):
            fail(
                "citation_semantic_check.json",
                f"record_id={rid}: reviewer={reviewer!r} notes must be a string",
            )
            continue
        # §9.4 common-mistake: tier check — review entries must belong to
        # Tier 1/2 REQs only.
        tier = tier_by_req.get(rid)
        if tier is None:
            fail(
                "citation_semantic_check.json",
                f"record_id={rid}: reviewer={reviewer!r} reviews a REQ that does "
                "not exist in requirements_manifest.json",
            )
            continue
        if tier not in (1, 2):
            fail(
                "citation_semantic_check.json",
                f"record_id={rid}: reviewer={reviewer!r} reviews a tier-{tier} "
                "REQ; semantic check applies to Tier 1/2 only (schemas.md §9.4)",
            )
            continue
        # Detect duplicate (req_id, reviewer) pairs — a typo that would slip a
        # vote past the majority computation.
        pair_key = seen_reviewers.setdefault(rid, set())
        if reviewer in pair_key:
            fail(
                "citation_semantic_check.json",
                f"record_id={rid}: duplicate review from reviewer={reviewer!r}",
            )
            continue
        pair_key.add(reviewer)
        by_req.setdefault(rid, []).append(entry)

    # §9.4: every Tier 1/2 REQ needs at least 3 reviews.
    for rid in sorted(tier_12_req_ids):
        entries = by_req.get(rid, [])
        if len(entries) < 3:
            fail(
                "citation_semantic_check.json",
                f"record_id={rid}: fewer than 3 reviews ({len(entries)} present) "
                "— schemas.md §9.4 requires one entry per council member for "
                "every Tier 1/2 REQ",
            )
            continue
        overreach_count = sum(1 for e in entries if e.get("verdict") == "overreaches")
        unclear_count = sum(1 for e in entries if e.get("verdict") == "unclear")
        if overreach_count >= 2:
            reviewers_flagged = ", ".join(
                sorted(
                    str(e.get("reviewer"))
                    for e in entries
                    if e.get("verdict") == "overreaches"
                )
            )
            fail(
                "citation_semantic_check.json",
                f"record_id={rid}: semantic check majority overreaches "
                f"({overreach_count}/{len(entries)} reviewers flagged: "
                f"{reviewers_flagged}) — schemas.md §10 invariant #17",
            )
        elif overreach_count == 1:
            flagged = next(
                str(e.get("reviewer"))
                for e in entries
                if e.get("verdict") == "overreaches"
            )
            warn(
                f"citation_semantic_check.json: record_id={rid}: 1/{len(entries)} "
                f"reviewer ({flagged}) flagged as `overreaches` — surfaced for "
                "human review; not a gate failure unless ≥2 agree"
            )
        if unclear_count >= 1 and overreach_count == 0:
            flagged = ", ".join(
                sorted(
                    str(e.get("reviewer"))
                    for e in entries
                    if e.get("verdict") == "unclear"
                )
            )
            warn(
                f"citation_semantic_check.json: record_id={rid}: "
                f"{unclear_count}/{len(entries)} reviewer(s) flagged as "
                f"`unclear` ({flagged}) — surfaced for human review"
            )

    if not tier_12_req_ids:
        pass_(
            "citation_semantic_check.json: no Tier 1/2 REQs to review "
            "(invariant #17 vacuously satisfied)"
        )
    else:
        pass_(
            f"citation_semantic_check.json: §10 invariant #17 checks complete "
            f"for {len(tier_12_req_ids)} Tier 1/2 REQ(s)"
        )


# --- v1.5.1 Item 5.2: challenge-gate coverage invariant -------------------

# Canonical verdict-line regex from Impl-Plan Item 5.2. Matches a top-level
# "**Verdict:** CONFIRMED/DOWNGRADED/REJECTED" line as a stand-alone line.
_CHALLENGE_VERDICT_RE = re.compile(
    r"^\*\*Verdict:\*\*\s+(CONFIRMED|DOWNGRADED|REJECTED)\s*$",
    re.MULTILINE,
)
# Legacy final-verdict form used by challenge records generated before the
# canonical regex was specified (including the preserved virtio-1.4.6
# evidence at repos/benchmark-1.5.0/virtio-1.4.6/quality/challenge/).
# The briefing says "this invariant only verifies the challenge ran" — the
# legacy form unambiguously records a final verdict, so it satisfies the
# invariant's intent without requiring operators to regenerate baseline
# artifacts. New v1.5.1+ runs should prefer the canonical form.
_CHALLENGE_VERDICT_LEGACY_RE = re.compile(
    r"^\*\*(CONFIRMED|DOWNGRADED|REJECTED)\.?\*\*",
    re.MULTILINE,
)

# Trigger-pattern keyword tables (case-insensitive substring matching).
_CHALLENGE_SECURITY_SEVERITIES = frozenset({"CRITICAL", "HIGH"})
_CHALLENGE_SECURITY_KEYWORDS = (
    "credential", "secret", "auth", "injection", "xss", "csrf",
    "ssrf", "privilege", "bypass", "leak",
)
_CHALLENGE_SIBLING_KEYWORDS = (
    "sibling", "parallel", "parity", "contrasted with", "same concern",
    "in contrast", "other path", "other branch",
)
_CHALLENGE_MISSING_KEYWORDS = (
    "never", "does not", "doesn't", "missing", "absent", "fails to",
)
_CHALLENGE_DESIGN_KEYWORDS = (
    "todo", "why", "ooda", "design decision",
)
_CHALLENGE_ITERATION_KEYWORDS = (
    "gap", "unfiltered", "parity", "adversarial", "iteration",
)


def _bug_writeup_text(q, bug_id):
    """Return lowercased writeup text for ``bug_id`` (empty string if absent).

    Writeups live at quality/writeups/BUG-NNN.md. Reading failures are
    treated as empty text — the invariant still runs on the manifest fields
    (title / summary / source) which are present independently.
    """
    path = _resolve_artifact_path(q, f"writeups/{bug_id}.md")
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return ""


def _bug_req_has_tier_12_citation(req_id, requirements_records):
    """True iff req_id resolves to a REQ with a non-empty citation and
    tier in {1, 2}. Used by the "No spec basis" trigger pattern."""
    if not req_id or not isinstance(requirements_records, list):
        return False
    for rec in requirements_records:
        if not isinstance(rec, dict):
            continue
        if rec.get("id") != req_id:
            continue
        if rec.get("tier") not in (1, 2):
            return False
        citation = rec.get("citation")
        if isinstance(citation, dict) and citation:
            return True
        return False
    return False


def _contains_any(text, keywords):
    """Case-insensitive substring OR across a keyword tuple."""
    if not text:
        return False
    lowered = text.lower()
    return any(kw in lowered for kw in keywords)


def _classify_bug_triggers(rec, q, requirements_records):
    """Return the list of trigger-pattern names that fired for one bug.
    Empty list means the bug does not require a challenge record.

    Patterns mirror Impl-Plan Item 5.2 verbatim. Input aliasing:
      - title: prefers rec['title'], falls back to rec['summary'].
      - requirement: prefers rec['requirement'], falls back to rec['req_id']
        (v1.4.x uses req_id; v1.5.1+ converges on requirement).
      - source_comments: optional, older runs may omit it.
      - source / discovery_phase: substring-matched against the
        iteration-derived keyword list.
    """
    fired = []

    bug_id = rec.get("id", "")
    title = rec.get("title") or rec.get("summary") or ""
    severity = (rec.get("severity") or "").upper()
    writeup = _bug_writeup_text(q, bug_id) if bug_id else ""
    title_plus_writeup = f"{title}\n{writeup}"

    # 1. Security-class.
    if severity in _CHALLENGE_SECURITY_SEVERITIES and _contains_any(
        title_plus_writeup, _CHALLENGE_SECURITY_KEYWORDS
    ):
        fired.append("security-class")

    # 2. No spec basis.
    requirement = rec.get("requirement") or rec.get("req_id")
    has_valid_citation = _bug_req_has_tier_12_citation(requirement, requirements_records)
    if not requirement or not has_valid_citation:
        fired.append("no-spec-basis")

    # 3. Sibling-path divergence.
    if _contains_any(writeup, _CHALLENGE_SIBLING_KEYWORDS):
        fired.append("sibling-path-divergence")

    # 4. Missing functionality.
    if _contains_any(writeup, _CHALLENGE_MISSING_KEYWORDS):
        fired.append("missing-functionality")

    # 5. Design-decision comment (optional field).
    source_comments = rec.get("source_comments")
    if isinstance(source_comments, str) and _contains_any(
        source_comments, _CHALLENGE_DESIGN_KEYWORDS
    ):
        fired.append("design-decision-comment")

    # 6. Iteration-derived.
    source = rec.get("source") or ""
    discovery_phase = rec.get("discovery_phase") or ""
    iter_haystack = f"{source}\n{discovery_phase}"
    if _contains_any(iter_haystack, _CHALLENGE_ITERATION_KEYWORDS):
        fired.append("iteration-derived")

    return fired


def _challenge_record_has_verdict(path):
    """True iff the file exists and contains either the canonical or
    legacy verdict line per the invariant's accept set."""
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    if _CHALLENGE_VERDICT_RE.search(text):
        return True
    if _CHALLENGE_VERDICT_LEGACY_RE.search(text):
        return True
    return False


@verdict_category(VERDICT_RECORD_KEEPING)
def check_challenge_gate_coverage(q):
    """v1.5.1 Item 5.2 — every bug whose fingerprints trigger the challenge
    gate must have a quality/challenge/BUG-NNN-challenge.md with a valid
    verdict line.

    N/A when quality/bugs_manifest.json is absent (zero-bug runs can't
    have un-challenged bugs). Runs on the current quality/ tree only;
    no cross-run state.
    """
    data = _v150_manifest(q, "bugs_manifest.json")
    if data is None:
        # N/A — the plan explicitly says "invariant is N/A if the file is
        # absent". Consistent with other quality_gate invariants that silently
        # skip when their input isn't present.
        return
    records = data.get("records")
    if not isinstance(records, list):
        return

    reqs_data = _v150_manifest(q, "requirements_manifest.json") or {}
    req_records = reqs_data.get("records") if isinstance(reqs_data, dict) else None

    challenge_dir = q / "challenge"
    triggered = 0
    missing = []   # list of (bug_id, [pattern names]) for bugs with no record
    bad_verdict = []  # list of (bug_id, [pattern names]) for record w/o verdict

    for rec in records:
        if not isinstance(rec, dict):
            continue
        bug_id = rec.get("id")
        if not bug_id:
            continue
        fired = _classify_bug_triggers(rec, q, req_records)
        if not fired:
            continue
        triggered += 1
        record_path = challenge_dir / f"{bug_id}-challenge.md"
        if not record_path.is_file():
            missing.append((bug_id, fired))
        elif not _challenge_record_has_verdict(record_path):
            bad_verdict.append((bug_id, fired))

    if missing:
        for bug_id, fired in missing:
            fail(
                "quality/challenge/",
                f"{bug_id}: challenge record missing (triggered by: {', '.join(fired)}) "
                f"— expected {bug_id}-challenge.md with a **Verdict:** line",
            )
    if bad_verdict:
        for bug_id, fired in bad_verdict:
            fail(
                f"quality/challenge/{bug_id}-challenge.md",
                f"missing or malformed verdict line (triggered by: {', '.join(fired)}) "
                "— expected a line matching `^\\*\\*Verdict:\\*\\*\\s+(CONFIRMED|DOWNGRADED|REJECTED)` "
                "or the legacy final-verdict form",
            )

    if triggered == 0:
        pass_("challenge gate coverage: no bug triggered the challenge gate (vacuous)")
    elif not missing and not bad_verdict:
        pass_(
            f"challenge gate coverage: {triggered} triggered bug(s) all have valid "
            "challenge records"
        )


@verdict_category(VERDICT_RECORD_KEEPING)
def check_v1_5_3_formal_doc_role_validation(q):
    """schemas.md §10 invariant #23 — FORMAL_DOC.role on v1.5.3-shaped manifests.

    Legacy manifest (no v1.5.3 fields anywhere): one WARN, then skip.
    v1.5.3-shaped: every record MUST have role populated with a member of
    formal_doc_role (§3.6).
    """
    data = _v150_manifest(q, "formal_docs_manifest.json")
    if data is None:
        return
    records = data.get("records")
    if not isinstance(records, list):
        return  # wrapper check already reported
    if not _is_v1_5_3_shaped(data):
        warn(
            "formal_docs_manifest.json: legacy manifest detected "
            "(pre-v1.5.3 manifest shape — no role/source_type/"
            "divergence_type fields); applying the schemas.md §3.10 "
            "documented default FORMAL_DOC.role='external-spec' and "
            "skipping v1.5.3 strict role validation. This is the "
            "intended backward-compat path (089 F9 KEEP), not a defect"
        )
        return
    any_fail = False
    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            continue
        rec_id = rec.get("source_path", f"<#{idx}>")
        role = rec.get("role")
        if role not in _V153_VALID_FORMAL_DOC_ROLES:
            fail(
                "formal_docs_manifest.json",
                f"record_id={rec_id}: missing or invalid role {role!r} on "
                f"v1.5.3-shaped manifest (schemas.md §10 invariant #23, valid: "
                f"{', '.join(_V153_VALID_FORMAL_DOC_ROLES)})",
            )
            any_fail = True
    if not any_fail:
        pass_("formal_docs_manifest.json: v1.5.3 role validation complete")


@verdict_category(VERDICT_RECORD_KEEPING)
def check_v1_5_3_source_type_validation(q):
    """schemas.md §10 invariants #21 (first part) — REQ.source_type presence.

    Legacy manifest: one WARN, then skip.
    v1.5.3-shaped: every REQ MUST have source_type populated with a member
    of req_source_type (§3.7).
    """
    data = _v150_manifest(q, "requirements_manifest.json")
    if data is None:
        return
    records = data.get("records")
    if not isinstance(records, list):
        return
    if not _is_v1_5_3_shaped(data):
        warn(
            "requirements_manifest.json: legacy manifest detected "
            "(pre-v1.5.3 manifest shape — no role/source_type/"
            "divergence_type fields); applying the schemas.md §3.10 "
            "documented default REQ.source_type='code-derived' and "
            "skipping v1.5.3 strict source_type validation. This is "
            "the intended backward-compat path (089 F9 KEEP), not a "
            "defect"
        )
        return
    any_fail = False
    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            continue
        req_id = rec.get("id", f"<#{idx}>")
        source_type = rec.get("source_type")
        if source_type not in _V153_VALID_SOURCE_TYPES:
            fail(
                "requirements_manifest.json",
                f"record_id={req_id}: missing or invalid source_type "
                f"{source_type!r} on v1.5.3-shaped manifest "
                f"(schemas.md §10 invariant #21, valid: "
                f"{', '.join(_V153_VALID_SOURCE_TYPES)})",
            )
            any_fail = True
    if not any_fail:
        pass_("requirements_manifest.json: v1.5.3 source_type validation complete")


@verdict_category(VERDICT_RECORD_KEEPING)
def check_v1_5_3_skill_section_consistency(q):
    """schemas.md §10 invariant #21 (second part) — skill_section consistency.

    On a v1.5.3-shaped requirements manifest, REQs with
    source_type == 'skill-section' MUST have non-empty skill_section;
    REQs with any other source_type value MUST have skill_section absent
    or null (per §1.5: optional fields may be omitted or present as null).
    Populated skill_section paired with non-skill-section source_type FAILs.

    Legacy manifests are skipped silently here -- the source_type check
    already emitted the single WARN for the manifest.

    Deliberate piggyback (Round 2 Council, item 1): this is the one
    documented exception to the "exactly one WARN per check function"
    convention used by the other three v1.5.3 invariants. Both
    check_v1_5_3_source_type_validation and this check share
    requirements_manifest.json, so emitting a second WARN here would
    double-warn for the same legacy file. The piggyback is locked in
    by test_legacy_manifest_silently_skips in
    TestV153SkillSectionConsistency -- a future maintainer reading the
    brief and adding a WARN for consistency would break that test.
    """
    data = _v150_manifest(q, "requirements_manifest.json")
    if data is None:
        return
    records = data.get("records")
    if not isinstance(records, list):
        return
    if not _is_v1_5_3_shaped(data):
        return  # source_type check handled the soft warn for this manifest
    any_fail = False
    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            continue
        req_id = rec.get("id", f"<#{idx}>")
        source_type = rec.get("source_type")
        skill_section = rec.get("skill_section")
        if source_type == "skill-section":
            if not isinstance(skill_section, str) or not skill_section.strip():
                fail(
                    "requirements_manifest.json",
                    f"record_id={req_id}: source_type='skill-section' but "
                    f"skill_section is empty or missing "
                    "(schemas.md §10 invariant #21)",
                )
                any_fail = True
        else:
            if skill_section is not None and skill_section != "":
                fail(
                    "requirements_manifest.json",
                    f"record_id={req_id}: skill_section={skill_section!r} "
                    f"populated but source_type={source_type!r} is not "
                    "'skill-section' (schemas.md §10 invariant #21)",
                )
                any_fail = True
    if not any_fail:
        pass_("requirements_manifest.json: v1.5.3 skill_section consistency complete")


@verdict_category(VERDICT_RECORD_KEEPING)
def check_v1_5_3_divergence_type_validation(q):
    """schemas.md §10 invariant #22 — BUG.divergence_type on v1.5.3-shaped manifests.

    Legacy manifest: one WARN, then skip.
    v1.5.3-shaped: every BUG MUST have divergence_type populated with a
    member of bug_divergence_type (§3.8).
    """
    data = _v150_manifest(q, "bugs_manifest.json")
    if data is None:
        return
    records = data.get("records")
    if not isinstance(records, list):
        return
    if not _is_v1_5_3_shaped(data):
        warn(
            "bugs_manifest.json: legacy manifest detected; treating absent "
            "BUG.divergence_type as 'code-spec' per schemas.md §3.10 backward-compat rule"
        )
        return
    any_fail = False
    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            continue
        bug_id = rec.get("id", f"<#{idx}>")
        divergence_type = rec.get("divergence_type")
        if divergence_type not in _V153_VALID_DIVERGENCE_TYPES:
            fail(
                "bugs_manifest.json",
                f"record_id={bug_id}: missing or invalid divergence_type "
                f"{divergence_type!r} on v1.5.3-shaped manifest "
                f"(schemas.md §10 invariant #22, valid: "
                f"{', '.join(_V153_VALID_DIVERGENCE_TYPES)})",
            )
            any_fail = True
    if not any_fail:
        pass_("bugs_manifest.json: v1.5.3 divergence_type validation complete")


_V153_COUNCIL_INBOX_ITEM_TYPES = frozenset({
    "rejected-draft",
    "tier-5-demotion",
    "zero-req-section",
    "weak-rationale",
})


@verdict_category(VERDICT_RECORD_KEEPING)
def check_v1_5_3_council_inbox_validation(q):
    """Skill-derivation Pass D 3b BLOCK-4 cross-reference + DQ-5
    structural validation (v1.5.7 fix Q4: this is the
    skill-derivation four-pass pipeline's Pass D, NOT the playbook's
    Phase 3 Code Review — naming kept as `phase3/` on disk for
    historical v1.5.3 compatibility; the directory name pre-dates
    the v1.5.4 phase rename).

    Validates quality/phase3/pass_d_council_inbox.json against the
    DQ-5 schema AND verifies that every Pass D rejection / Tier-5
    demotion has a matching council-inbox item. Without the
    cross-reference invariant, a syntactically-valid but functionally
    -empty inbox could pass while pass_d_audit.json shows 30+
    rejections -- the inbox population could silently break and the
    gate would not catch it.

    Two failure modes:
      1. Structural -- malformed item record, invalid item_type,
         missing required field per the DQ-5 schema.
      2. Cross-reference -- pass_d_audit.json entry with outcome in
         {rejected, demoted_to_tier_5} has no matching item in the
         inbox.

    Skill-derivation artifact set is at <repo>/quality/phase3/, NOT
    at the top-level <repo>/quality/. The check returns silently if
    the phase3 directory does not exist (the project is Code-only
    or the skill-derivation pipeline has not been run yet — this is
    DIFFERENT from the playbook's Phase 3 not having run).
    """
    phase3_dir = _resolve_artifact_path(q, "phase3")
    if not phase3_dir.is_dir():
        return  # skill-derivation pipeline not run; not in scope here
    inbox_path = phase3_dir / "pass_d_council_inbox.json"
    audit_path = phase3_dir / "pass_d_audit.json"
    if not inbox_path.is_file():
        return  # skill-derivation Pass D partially run; skip silently

    inbox_data = load_json(inbox_path)
    if not isinstance(inbox_data, dict):
        fail(f"{inbox_path.name}: not a valid JSON object")
        return

    # Structural validation.
    schema_version = inbox_data.get("schema_version")
    if schema_version != "1.0":
        fail(
            f"{inbox_path.name}: schema_version {schema_version!r} "
            "does not match the DQ-5 spec value '1.0'"
        )
    items = inbox_data.get("items")
    if not isinstance(items, list):
        fail(f"{inbox_path.name}: 'items' is missing or not a list")
        return

    required_fields = {
        "item_type",
        "draft_idx",
        "section_idx",
        "section_heading",
        "rationale",
        "context_excerpt",
        "provisional_disposition",
    }
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            fail(f"{inbox_path.name}: item #{idx} is not a JSON object")
            continue
        missing = required_fields - set(item.keys())
        if missing:
            fail(
                f"{inbox_path.name}: item #{idx} is missing required "
                f"DQ-5 fields: {sorted(missing)}"
            )
        if item.get("item_type") not in _V153_COUNCIL_INBOX_ITEM_TYPES:
            fail(
                f"{inbox_path.name}: item #{idx} has invalid item_type "
                f"{item.get('item_type')!r} (valid: "
                f"{sorted(_V153_COUNCIL_INBOX_ITEM_TYPES)})"
            )
        rationale = item.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            fail(
                f"{inbox_path.name}: item #{idx} has empty or missing "
                "rationale"
            )

    # Cross-reference invariant: every rejected / demoted audit entry
    # must have a matching inbox item by (draft_idx, item_type).
    if audit_path.is_file():
        audit_data = load_json(audit_path)
        if isinstance(audit_data, dict):
            inbox_pairs = {
                (item.get("draft_idx"), item.get("item_type"))
                for item in items
                if isinstance(item, dict)
            }
            for entry in audit_data.get("rejected", []) or []:
                if not isinstance(entry, dict):
                    continue
                pair = (entry.get("draft_idx"), "rejected-draft")
                if pair not in inbox_pairs:
                    fail(
                        f"{inbox_path.name}: pass_d_audit.json shows "
                        f"rejected draft_idx={entry.get('draft_idx')} "
                        "but there is no matching rejected-draft item "
                        "in the council inbox (BLOCK-4 cross-reference "
                        "invariant violation)"
                    )
            for entry in audit_data.get("demoted_to_tier_5", []) or []:
                if not isinstance(entry, dict):
                    continue
                pair = (entry.get("draft_idx"), "tier-5-demotion")
                if pair not in inbox_pairs:
                    fail(
                        f"{inbox_path.name}: pass_d_audit.json shows "
                        f"tier-5 demotion at draft_idx={entry.get('draft_idx')} "
                        "but there is no matching tier-5-demotion item "
                        "in the council inbox"
                    )

    pass_(f"{inbox_path.name}: v1.5.3 council inbox validation complete")


# ---------------------------------------------------------------------------
# Phase 4 skill-project gate enforcement checks (DQ-4-4).
#
# These four checks fire when the target's role map shows skill-prose
# surface; they SKIP (informational `INFO: skipped` line, no fail
# counter increment) on pure-code targets. The check that always runs
# is check_role_map_consistency.
#
# v1.5.4 Part 1: the legacy Code/Skill/Hybrid string is now derived
# from the Phase-1 role map at <q>/exploration_role_map.json. The
# mapping mirrors bin/role_map.py::derive_legacy_project_type. If the
# role map is absent, all four checks SKIP silently — Phase 1 has not
# been run yet on this target. The gate ships into target repos as a
# stdlib-only script and cannot import bin/role_map; the small amount
# of role-map awareness it needs is inlined below.
# ---------------------------------------------------------------------------


def _load_role_map(q):
    """Return the parsed exploration_role_map.json dict, or None when
    absent / unparsable. v1.5.4 inline replacement for the prior
    project_type.json reader."""
    return load_json(q / "exploration_role_map.json")


def _role_map_has_role(role_map, role_set):
    if not isinstance(role_map, dict):
        return False
    files = role_map.get("files") or []
    if not isinstance(files, list):
        return False
    for entry in files:
        if isinstance(entry, dict) and entry.get("role") in role_set:
            return True
    return False


def _phase4_project_type(q):
    """Return the v1.5.3-equivalent classification string ('Code' /
    'Skill' / 'Hybrid') derived from the Phase-1 role map, or None
    when the role map is absent / unparsable.

    Mapping (mirrors bin/role_map.derive_legacy_project_type):
      - has skill-prose AND has code  -> 'Hybrid'
      - has skill-prose, no code      -> 'Skill'
      - no skill-prose                -> 'Code'

    v1.5.7 fix Q1/Q5 (option c): when the role map is absent, fall
    back to artifact-shape detection rather than returning None
    (which made Phase 4 skill-derivation gate checks emit
    "skip (project_type=None)" INFO lines that LOOKED like missed
    work). The fallback is conservative — it only returns 'Code'
    when the absence-of-skill signal is strong (no SKILL.md at the
    target root AND no references/ directory). Otherwise returns
    None so the gate's skip diagnostic surfaces "role map not yet
    produced" honestly rather than guessing Skill/Hybrid.
    """
    role_map = _load_role_map(q)
    if role_map is None:
        return _phase4_project_type_from_artifact_shape(q)
    skill = _role_map_has_role(role_map, ("skill-prose", "skill-reference"))
    code = _role_map_has_role(role_map, ("code",))
    if skill and code:
        return "Hybrid"
    if skill:
        return "Skill"
    return "Code"


def _phase4_project_type_from_artifact_shape(q):
    """v1.5.7 Q1/Q5 (option c) fallback: derive a project-type from
    target-repo shape when the Phase-1 role map is absent.

    Conservative: returns 'Code' ONLY when both skill-indicator paths
    are absent (no root SKILL.md, no references/ directory at the
    repo root). Otherwise returns None — the gate then emits a
    "role map not yet produced" SKIP rather than guessing.

    The repo root is the parent of the quality/ directory (q itself
    IS quality/).
    """
    repo_root = q.parent if q.name == "quality" else q
    has_skill_md = (repo_root / "SKILL.md").is_file()
    has_references = (repo_root / "references").is_dir()
    if not has_skill_md and not has_references:
        return "Code"
    return None


@verdict_category(VERDICT_SUBSTANTIVE)
def check_skill_section_req_coverage(repo_dir, q):
    """Skill / Hybrid: every operational SKILL.md section per
    pass_d_section_coverage.json has ≥1 promoted REQ. Meta-allowlist
    sections are exempt (their section_kind == 'meta').

    SKIPS for Code projects."""
    print("[Phase 4: skill-section REQ coverage]")
    classification = _phase4_project_type(q)
    if classification == "Code":
        info(
            "check_skill_section_req_coverage: skip — not applicable for "
            "Code projects (skill-derivation Pass D only fires on Skill / "
            "Hybrid targets)"
        )
        return
    if classification not in ("Skill", "Hybrid"):
        info(
            "check_skill_section_req_coverage: skip — role map absent "
            "and project shape is ambiguous (no clear Code signal); "
            "run Phase 1 to produce exploration_role_map.json then "
            "rerun the gate"
        )
        return
    coverage_path = _resolve_artifact_path(q, "phase3/pass_d_section_coverage.json")
    data = load_json(coverage_path)
    if not isinstance(data, dict):
        info(
            "check_skill_section_req_coverage: skip "
            "(pass_d_section_coverage.json missing or unparsable)"
        )
        return
    failures = 0
    for s in data.get("sections", []) or []:
        if not isinstance(s, dict):
            continue
        kind = s.get("section_kind")
        if kind != "operational":
            continue
        promoted = s.get("drafts_promoted", 0) or 0
        if promoted < 1:
            heading = s.get("heading") or "<unknown>"
            document = s.get("document") or "SKILL.md"
            section_idx = s.get("section_idx")
            fail(
                f"{document}",
                f"section #{section_idx} {heading!r} has 0 promoted "
                "REQs and is not in the meta allowlist "
                "(check_skill_section_req_coverage)",
            )
            failures += 1
    if failures == 0:
        pass_("check_skill_section_req_coverage: every operational section has ≥1 promoted REQ")


@verdict_category(VERDICT_SUBSTANTIVE)
def check_reference_file_req_coverage(repo_dir, q):
    """Skill / Hybrid: every reference file under references/ has ≥1
    REQ citing it OR a `<!-- non-normative -->` marker in its first
    5 lines.

    SKIPS for Code projects."""
    print("[Phase 4: reference-file REQ coverage]")
    classification = _phase4_project_type(q)
    if classification == "Code":
        info(
            "check_reference_file_req_coverage: skip — not applicable "
            "for Code projects (no references/ directory expected)"
        )
        return
    if classification not in ("Skill", "Hybrid"):
        info(
            "check_reference_file_req_coverage: skip — role map absent "
            "and project shape is ambiguous; run Phase 1 first"
        )
        return
    references_dir = repo_dir / "references"
    if not references_dir.is_dir():
        info("check_reference_file_req_coverage: skip (no references/ directory)")
        return
    formal_path = _resolve_artifact_path(q, "phase3/pass_c_formal.jsonl")
    if not formal_path.is_file():
        info(
            "check_reference_file_req_coverage: skip "
            "(pass_c_formal.jsonl missing — skill-derivation Pass C "
            "not run yet; this is the four-pass skill-derivation "
            "pipeline's Pass C output, not the playbook's Phase 3 "
            "Code Review output)"
        )
        return
    cited_documents = set()
    for line in formal_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict):
            continue
        sd = rec.get("source_document")
        if isinstance(sd, str):
            cited_documents.add(sd)
    failures = 0
    for ref in sorted(references_dir.glob("*.md")):
        rel = f"references/{ref.name}"
        if rel in cited_documents:
            continue
        # Non-normative marker check (first 5 lines).
        head = ref.read_text(encoding="utf-8", errors="replace").splitlines()[:5]
        if any("<!-- non-normative -->" in line.lower() for line in head):
            continue
        fail(
            rel,
            "no REQ cites this reference file and no <!-- non-normative --> "
            "marker in its first 5 lines (check_reference_file_req_coverage)",
        )
        failures += 1
    if failures == 0:
        pass_("check_reference_file_req_coverage: every reference file has ≥1 citing REQ or non-normative marker")


@verdict_category(VERDICT_SUBSTANTIVE)
def check_hybrid_cross_cutting_reqs(repo_dir, q):
    """Hybrid only: ≥1 REQ has triangulated evidence —
    `source_type=skill-section` AND its acceptance_criteria references
    a code artifact mentioned in another REQ with
    `source_type=code-derived`.

    SKIPS for Skill or Code projects."""
    print("[Phase 4: hybrid cross-cutting REQs]")
    classification = _phase4_project_type(q)
    if classification == "Code":
        info(
            "check_hybrid_cross_cutting_reqs: skip — not applicable "
            "for Code projects (cross-cutting triangulation requires "
            "both skill-section and code-derived REQs)"
        )
        return
    if classification == "Skill":
        info(
            "check_hybrid_cross_cutting_reqs: skip — not applicable "
            "for Skill projects (no code-derived REQs to triangulate "
            "against)"
        )
        return
    if classification != "Hybrid":
        info(
            "check_hybrid_cross_cutting_reqs: skip — role map absent "
            "and project shape is ambiguous; run Phase 1 first"
        )
        return
    formal_path = _resolve_artifact_path(q, "phase3/pass_c_formal.jsonl")
    if not formal_path.is_file():
        info(
            "check_hybrid_cross_cutting_reqs: skip "
            "(pass_c_formal.jsonl missing — skill-derivation Pass C "
            "not run yet; this is the four-pass skill-derivation "
            "pipeline's Pass C output, not the playbook's Phase 3 "
            "Code Review output)"
        )
        return
    skill_section_reqs = []
    code_derived_artifacts = set()
    for line in formal_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict):
            continue
        st = rec.get("source_type")
        if st == "skill-section":
            skill_section_reqs.append(rec)
        elif st == "code-derived":
            ac = (rec.get("acceptance_criteria") or "")
            cite = (rec.get("citation_excerpt") or "")
            for token in re.findall(
                r"\b([\w./-]+\.(?:py|sh|json))\b", ac + " " + cite
            ):
                code_derived_artifacts.add(token)
    if not code_derived_artifacts:
        # On a Hybrid project that hasn't yet produced any code-derived
        # REQs, the cross-cutting check has nothing to triangulate
        # against. INFO + skip rather than fail (the absence is the
        # diagnostic).
        info(
            "check_hybrid_cross_cutting_reqs: skip "
            "(no code-derived REQs in pass_c_formal.jsonl yet)"
        )
        return
    triangulated = 0
    for rec in skill_section_reqs:
        ac = (rec.get("acceptance_criteria") or "") + " " + (
            rec.get("citation_excerpt") or ""
        )
        if any(art in ac for art in code_derived_artifacts):
            triangulated += 1
            if triangulated >= 1:
                break
    if triangulated >= 1:
        pass_(
            f"check_hybrid_cross_cutting_reqs: triangulated evidence "
            f"present (≥{triangulated} skill-section REQ references a "
            "code-derived artifact)"
        )
    else:
        fail(
            "pass_c_formal.jsonl",
            "Hybrid project has no triangulated REQ pair "
            "(skill-section REQ referencing a code-derived artifact); "
            "check_hybrid_cross_cutting_reqs",
        )


@verdict_category(VERDICT_RECORD_KEEPING)
def check_role_map_consistency(repo_dir, q):
    """All projects: exploration_role_map.json (when present) parses as
    a JSON object, declares schema_version '1.0', carries a 'files'
    list and a 'breakdown.percentages' dict with the four expected
    share keys.

    SKIPS silently when the role map is absent — Phase 1 has not been
    run yet on this target. v1.5.4 Part 1 replacement for the v1.5.3
    check_project_type_consistency, which keyed on
    quality/project_type.json (now retired)."""
    print("[Phase 4: role-map consistency]")
    rm_path = q / "exploration_role_map.json"
    if not rm_path.is_file():
        info(
            "check_role_map_consistency: skip "
            "(exploration_role_map.json absent — Phase 1 not run yet)"
        )
        return
    data = load_json(rm_path)
    if not isinstance(data, dict):
        fail(
            f"{rm_path.relative_to(q.parent)}",
            "exploration_role_map.json is not a valid JSON object",
        )
        return
    if data.get("schema_version") != "1.0":
        fail(
            f"{rm_path.relative_to(q.parent)}",
            f"schema_version {data.get('schema_version')!r} is not '1.0' "
            "(check_role_map_consistency)",
        )
        return
    files = data.get("files")
    if not isinstance(files, list):
        fail(
            f"{rm_path.relative_to(q.parent)}",
            "'files' is not a list (check_role_map_consistency)",
        )
        return
    breakdown = data.get("breakdown")
    if not isinstance(breakdown, dict):
        fail(
            f"{rm_path.relative_to(q.parent)}",
            "'breakdown' is not an object (check_role_map_consistency)",
        )
        return
    percentages = breakdown.get("percentages")
    if not isinstance(percentages, dict):
        fail(
            f"{rm_path.relative_to(q.parent)}",
            "'breakdown.percentages' is not an object "
            "(check_role_map_consistency)",
        )
        return
    missing = [
        k for k in ("skill_share", "code_share", "tool_share", "other_share")
        if k not in percentages
    ]
    if missing:
        fail(
            f"{rm_path.relative_to(q.parent)}",
            f"breakdown.percentages missing keys: {missing} "
            "(check_role_map_consistency)",
        )
        return
    derived = _phase4_project_type(q) or "Unknown"
    pass_(
        f"{rm_path.relative_to(q.parent)}: role map well-formed "
        f"(legacy-derived project type {derived!r}; "
        "check_role_map_consistency)"
    )


@verdict_category(VERDICT_RECORD_KEEPING)
def check_v1_5_2_cardinality_gate(repo_dir):
    """v1.5.2 Lever 3: Phase 5 cardinality reconciliation gate.

    Surfaces every failure from validate_cardinality_gate() as a fail() entry.
    """
    failures = validate_cardinality_gate(repo_dir)
    if not failures:
        pass_("compensation_grid.json: v1.5.2 cardinality gate clean")
        return
    for msg in failures:
        fail("compensation_grid.json", msg)


def check_v1_5_0_gate_invariants(repo_dir, q):
    """Dispatcher that runs every Layer-1 mechanical check from schemas.md §10."""
    check_v1_5_0_cite_extensions(repo_dir)
    check_v1_5_0_manifest_wrappers(q)
    check_v1_5_0_requirements_manifest(repo_dir, q)
    check_v1_5_0_bugs_manifest(q)
    # v1.5.7 instruction 090j: triage precision guardrails (D1 reachability
    # + D2 known-issue + D3 security-HIGH bar). Runs after the v1.5.0
    # disposition / fix_type checks so the manifest is shape-validated
    # before the precision rules examine it.
    check_v1_5_7_090j_triage_precision(q)
    check_v1_5_0_index_md(q)
    # Phase 6 invariant #17 runs after requirements_manifest so it sees
    # shape-validated REQ records.
    check_v1_5_0_semantic_check(q)
    # v1.5.1 Item 5.2: challenge-gate coverage runs last. It depends on
    # requirements_manifest.json for the "No spec basis" pattern but
    # does not redo schema checks that the prior invariants already cover.
    check_challenge_gate_coverage(q)
    # v1.5.2 Lever 3: cardinality reconciliation gate.
    check_v1_5_2_cardinality_gate(repo_dir)
    # v1.5.3 Phase 2: schema extensions for skill-aware projects (Code projects
    # with legacy manifests hit the soft-warn path; v1.5.3-shaped manifests
    # validate strictly per schemas.md §10 invariants #21–#23).
    check_v1_5_3_formal_doc_role_validation(q)
    check_v1_5_3_source_type_validation(q)
    check_v1_5_3_skill_section_consistency(q)
    check_v1_5_3_divergence_type_validation(q)
    # v1.5.3 Phase 3b: council inbox structural + cross-reference
    # validation (DQ-5 + BLOCK-4). No-op for Code projects (phase3
    # directory is absent).
    check_v1_5_3_council_inbox_validation(q)
    # v1.5.3 Phase 4 (DQ-4-4): skill-project gate enforcement. The
    # first three SKIP for code-only projects (no skill-prose surface
    # in the role map); check_role_map_consistency runs for all
    # projects. v1.5.4 Part 1: project_type derived from the Phase-1
    # role map instead of the retired project_type.json.
    check_skill_section_req_coverage(repo_dir, q)
    check_reference_file_req_coverage(repo_dir, q)
    check_hybrid_cross_cutting_reqs(repo_dir, q)
    check_role_map_consistency(repo_dir, q)


# v1.5.7 instruction 047 Item 3 (A-5): mechanical net for the
# Phase-1→Phase-2 asymmetry-promotion gap. Regex over EXPLORATION.md.
_ASYMMETRY_PROSE_RE = re.compile(
    r"compensates?\s+for"
    r"|relies?\s+entirely\s+on"
    r"|present\s+in\b.{0,80}?\bbut\s+not\s+in\b"
    r"|implements?\b.{0,80}?\bbut\b.{0,40}?\b(?:do(?:es)?n.?t|lacks?)\b",
    re.IGNORECASE | re.DOTALL,
)


@verdict_category(VERDICT_SUBSTANTIVE)
def check_compensation_asymmetry_promotion(q):
    """v1.5.7 instruction 047 Item 3 (A-5) — WARN-only net for the
    Phase-1→Phase-2 promotion gap: an architectural asymmetry noticed
    in EXPLORATION.md prose ("X compensates for Y", "Z relies
    entirely on W", "present in … but not in …", "implements … but
    … doesn't") that never became a `Pattern:`-tagged REQ has no
    cells for the v1.5.2 compensation-grid BUG-default and silently
    never produces BUGs in Phase 3 (the v1.5.1 RING_RESET /
    v1.5.7 virtio gap).

    Conservative + non-fatal: if EXPLORATION.md contains
    compensation-asymmetry prose, REQUIREMENTS.md must carry at least
    ONE `- Pattern:` line. WARN (never FAIL) — the prompt-side
    Asymmetry-Promotion Rule is the primary fix; this is the
    belt-and-suspenders mechanical signal so a silent escape is at
    least visible at gate time.
    """
    print("[Asymmetry promotion (A-5)]")
    expl = q / "EXPLORATION.md"
    reqs = q / "REQUIREMENTS.md"
    if not expl.is_file():
        info("EXPLORATION.md absent — asymmetry-promotion check skipped")
        return
    try:
        expl_text = expl.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        info(f"EXPLORATION.md unreadable ({exc}) — check skipped")
        return
    if not _ASYMMETRY_PROSE_RE.search(expl_text):
        pass_("no compensation-asymmetry prose in EXPLORATION.md")
        return
    reqs_text = ""
    if reqs.is_file():
        try:
            reqs_text = reqs.read_text(encoding="utf-8", errors="replace")
        except OSError:
            reqs_text = ""
    pattern_tag_count = len(_REQ_PATTERN_RE.findall(reqs_text))
    if pattern_tag_count == 0:
        warn(
            "EXPLORATION.md notes an architectural asymmetry "
            "(compensation/parity framing) but REQUIREMENTS.md has "
            "ZERO `Pattern:`-tagged REQs — the asymmetry was likely "
            "demoted to prose instead of promoted to a multi-site "
            "Pattern:-tagged REQ (A-5 / Phase-1 Asymmetry-Promotion "
            "Rule). Without a pattern-tagged REQ the v1.5.2 "
            "compensation-grid BUG-default has no cells and the "
            "asymmetry never produces BUGs in Phase 3."
        )
    else:
        pass_(
            f"asymmetry prose present and {pattern_tag_count} "
            f"Pattern:-tagged REQ(s) found in REQUIREMENTS.md"
        )


# ---------------------------------------------------------------------------
# v1.6.0 Feature C — REQUIREMENTS.md render contract.
#
# Before v1.6.0 the gate validated requirements_manifest.json and never
# looked at the rendered document, so every render defect was invisible to
# every mechanical check QPB had. The seven defect classes these checks pin
# (C-1..C-7) were each observed in the 2026-06-19 chi/express/virtio runs.
#
# Design: docs/design/QPB_v1.6.0_Design.md §5.3.
# Contract prose: references/phase2_generation_guide.md
#                 § "REQUIREMENTS.md render contract".
#
# The manifest stays the source of truth; these checks assert the rendered
# document is a faithful, coherent presentation of it.
# ---------------------------------------------------------------------------

# `### REQ-NNN: Title` — the canonical marker format. This regex is the
# enforcement leg of a three-way binding: the same rule is authored in
# references/requirements_pipeline.md § "Requirement heading format" and
# references/phase2_generation_guide.md § "Requirement heading format".
# Kept in sync with those two — a change here is incomplete without them.
_RENDER_REQ_HEADING_RE = re.compile(
    r"^###\s+(REQ-(\d+))\s*:\s*(.*)$", re.MULTILINE
)
_RENDER_LEVEL2_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)

# The attribution stamp emitted per references/phase2_generation_guide.md
# § "Version stamp". C-7: chi stamped v1.5.3 on a v1.5.8 run because the
# guide's template carried a hardcoded literal.
_RENDER_STAMP_RE = re.compile(
    r"Generated by\s+\[?Quality Playbook\]?[^\n]*?\bv([0-9]+(?:\.[0-9]+)+)"
)

# C-5: derivation internals that must never reach the adopter-facing render.
# The metadata belongs in requirements_manifest.json. Design §5.3 check 4
# seeds this deny-list with `Asymmetry-promotion`, `cluster:` and pass names.
#
# Each entry is (compiled_pattern, human_label). Word-boundary anchored
# rather than bare substring: a target whose own domain vocabulary includes
# the word "cluster" (Kubernetes, databases, storage) must be able to state
# its requirements. The pattern must match the *annotation* form, not the
# English word.
_RENDER_INTERNAL_PATTERNS = (
    (re.compile(r"Asymmetry-promotion"), "Asymmetry-promotion"),
    (re.compile(r"<!--[^>]*\bcluster\s*:"), "cluster: annotation"),
    (re.compile(r"^\s*[-*]?\s*cluster\s*:", re.MULTILINE), "cluster: annotation"),
    (re.compile(r"REQUIREMENTS_pre_narrative|pre_narrative"), "pre_narrative"),
    # Pass names — the derivation's own vocabulary for its internal stages.
    # Anchored to the forms the pipeline actually emits. A bare "Pass A"
    # is NOT enough: a compiler or assembler target legitimately has
    # requirements about "Pass A" of its own pipeline, and blocking that
    # would be the render contract over-firing on a correct document.
    (re.compile(r"\bnarrative pass\b", re.IGNORECASE), "narrative-pass name"),
    (re.compile(r"\bcontract-extraction v\d", re.IGNORECASE), "pipeline pass name"),
    (
        re.compile(r"\b(?:derivation|skill[- ]derivation)\s+Pass\s+[A-E]\b", re.IGNORECASE),
        "derivation pass name",
    ),
    (re.compile(r"\bPass\s+[A-E]/[A-E]\s+disposition\b", re.IGNORECASE),
     "derivation pass name"),
)

# Inline code spans are quoted material for the same reason fenced blocks
# are: a REQ about an HTML sanitizer has to be able to write `<!--`.
_RENDER_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")

# Level-2 headings that are canonical non-functional parts of the eight-part
# architecture. Everything else at level 2 is treated as a functional section.
#
# `definitions` is in this list and bare `terms` deliberately is not, and the
# asymmetry is a judgment call rather than an oversight: any name here buys a
# defect-to-pass bypass (a functional section so named escapes the intro-prose
# and singleton checks), so the list is priced by how likely the word is to be
# a real domain section heading. "Definitions" is a canonical IEEE 830 §1.3
# part name; "Terms" is an ordinary domain noun ("Payment terms"), and it was
# removed for exactly that reason (self-Council instr 002). Do not re-widen
# this list without pricing the same trade.
#
# Anchored with \Z (whole-heading match) rather than \b. A heading like
# "Requirements" is structural; "Functional Requirements" or "Requirements
# for the parser" is a functional section that merely starts with the word.
# The classifier also refuses to call any heading structural if it actually
# contains REQ headings — see _render_classify_sections. Without that
# belt-and-braces pair, a document rendering every REQ under a flat
# `## Requirements` heading silently opts out of the entire section
# discipline (intro prose, singleton merge, cross-cutting), which is exactly
# what §5.2 exists to prevent.
_RENDER_STRUCTURAL_HEADING_RE = re.compile(
    r"^(project\s+)?(overview|actors?(\s*(&|and)\s*roles?)?|use\s*cases?|"
    r"glossary(\s*(&|and|/)\s*definitions)?|definitions|"
    r"cross[-\s]?cutting(\s+concerns)?|traceability(\s+appendix)?|"
    r"non[-\s]?functional(\s+\w+)*|nfr(\s+\w+)*|requirements?)\s*\Z",
    re.IGNORECASE,
)

# Fenced code blocks are quoted material, not the document's own voice. A
# requirement about a template engine must be able to show an HTML comment.
#
# Deliberately a line scanner over the full CommonMark fence grammar rather
# than a regex over the shape most recently observed. The naive
# ```...``` pair this replaced was a bypass in four independent ways
# (self-Council rounds 3-4): tilde fences were missed entirely, a closing
# pair was required so an unterminated fence left the rest of the document
# scanned as prose, longer runs mis-paired, and it was not line-anchored.
# Each one alone reproduces the flat-document bypass in full, and each also
# fails good documents in the opposite direction — a conforming spec that
# quotes a `~~~` block got failed for the REQ headings inside it.
#
# Four rounds of this Council each fixed the shape it was shown and stopped
# at the boundary of the demonstration. Enumerating the grammar once is the
# way out of that loop.
# Info-string rules are per-delimiter, and getting them wrong inverts the
# fence polarity rather than merely rejecting an opener: the line CommonMark
# treats as the closer becomes the scanner's opener, so live document prose
# after the block gets blanked while the fenced content is scanned. That is
# a bypass, not just a false positive (self-Council round 5, B-6).
#
#   - a BACKTICK fence's info string may not contain a backtick, but may
#     contain tildes;
#   - a TILDE fence's info string may contain anything, backticks included.
_RENDER_FENCE_OPEN_RE = re.compile(
    r"^[ \t]*(?:(?P<btick>`{3,})(?P<binfo>[^`]*)|(?P<tilde>~{3,})(?P<tinfo>.*))$"
)

# HTML blocks that suppress Markdown structure the same way a code fence
# does — a `## Heading` inside one is literal text, not a heading.
#
# All seven CommonMark HTML block types. Type 1 (raw-text elements, closed
# by their end tag), type 2 (comments), types 3/4/5 (processing
# instructions, declarations, CDATA — each closed by its own terminator),
# and types 6/7 (block-level tags and any complete tag alone on its line,
# both closed by a blank line).
#
# Types 3/4/5 were excluded as "vanishingly unlikely in a requirements
# document" and were, exactly like type 7 before them, a full FAIL=0 bypass
# (self-Council round 7): `<?php`, `<!DOCTYPE` and `<![CDATA[` each hid the
# three §5.2 mandatory sections while the gate reported all three present.
# Round 7 adjudicated them non-blocking and shipped; they are modelled here
# anyway, because leaving a known permissive divergence in place is how the
# previous three rounds each began.
#
# Type 7 was excluded in 94c7e3d on the stated grounds that it "would
# swallow ordinary inline HTML an adopter might legitimately use". That
# rationale was wrong, and the exclusion was a full bypass (self-Council
# round 6, B-8): `<span>` around each of the three §5.2 mandatory sections
# scored FAIL=0 with all three reported present, while a reader of the
# rendered document sees none of them. Type 7 requires the tag to be ALONE
# on its line and preceded by a blank line, so inline HTML in running prose
# (`see <br> here`) is not affected — the concern that motivated the
# exclusion does not arise.
#
# The general rule this encodes: a divergence from the reference grammar
# may be conservative (see less structure, fail more documents) but never
# permissive. A permissive divergence is a bypass wearing a rationale.
_RENDER_HTML_RAWTEXT_OPEN_RE = re.compile(
    r"^[ \t]*<(?P<tag>pre|script|style|textarea)\b", re.IGNORECASE
)
_RENDER_HTML_RAWTEXT_CLOSE_RE = re.compile(
    r"</(?P<tag>pre|script|style|textarea)\s*>", re.IGNORECASE
)
# Type 6 — the CommonMark block-tag list. Closed by a blank line.
_RENDER_HTML_BLOCK_TAGS = (
    "address|article|aside|base|basefont|blockquote|body|caption|center|col|"
    "colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|"
    "footer|form|frame|frameset|h1|h2|h3|h4|h5|h6|head|header|hr|html|"
    "iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|"
    "option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|"
    "title|tr|track|ul"
)
_RENDER_HTML_TYPE6_OPEN_RE = re.compile(
    rf"^[ \t]*</?(?:{_RENDER_HTML_BLOCK_TAGS})(?:\s|/?>|$)", re.IGNORECASE
)
# Type 7 — ANY complete open or closing tag alone on its line. Unlike type
# 6 it may not interrupt a paragraph, so the scanner requires a preceding
# blank line. That restriction is why blanking it does not touch inline
# HTML in running prose.
_RENDER_HTML_TYPE7_OPEN_RE = re.compile(
    r"^[ \t]*(?:"
    r"<[A-Za-z][A-Za-z0-9-]*(?:\s+[^<>]*?)?/?>"   # complete open tag
    r"|</[A-Za-z][A-Za-z0-9-]*\s*>"               # complete closing tag
    r")[ \t]*$"
)

# Types 3, 4 and 5 — each opens with its own marker and closes on its own
# terminator rather than at a blank line.
_RENDER_HTML_TYPE345 = (
    (re.compile(r"^[ \t]*<\?"), "?>"),                       # 3: processing instruction
    (re.compile(r"^[ \t]*<![A-Za-z]"), ">"),                  # 4: declaration
    (re.compile(r"^[ \t]*<!\[CDATA\["), "]]>"),              # 5: CDATA
)



def _render_blank_fences(text, blank_html_comments=True):
    """Blank fenced code blocks, preserving length so offsets stay valid.

    Structure detection must run over this, not the raw text: a ``##`` line
    inside a code fence is quoted material, not a heading. Counting it lets
    a handful of lines inside one fence satisfy the entire §5.2 mandatory-
    part list AND synthesize a functional section, so a completely flat
    requirement list scores clean.

    Handles the full fence grammar: backtick and tilde delimiters, runs of
    three or more, a closer at least as long as its opener, indentation,
    and an unterminated fence (which runs to end of document per
    CommonMark). A fence delimiter of the other character, or a shorter
    run, does not close the block.
    """
    blanked, _unterminated = _render_blank_fences_ex(
        text, blank_html_comments=blank_html_comments
    )
    return blanked


def _render_blank_fences_ex(text, blank_html_comments=True):
    """As :func:`_render_blank_fences`, also reporting an unterminated fence.

    Returns ``(blanked_text, unterminated_line_number_or_None)``. An
    unterminated fence swallows the rest of the document, which would make
    the whole render contract silently inert — the caller FAILs on it
    rather than certifying a document it cannot actually read.
    """
    out = []
    fence_char = None
    fence_len = 0
    opened_at = None
    html_tag = None       # type 1: raw-text element, closed by its end tag
    html_until_blank = False  # types 2, 6 and 7: closed by a blank line
    html_terminator = None   # types 3/4/5: closed by their own terminator
    html_opened_at = None    # line of an unterminated types 1/3/4/5 block
    prev_blank = True  # start of document counts as a preceding blank line
    for line_no, line in enumerate(text.split("\n"), start=1):
        if html_tag is not None:
            out.append(" " * len(line))
            m = _RENDER_HTML_RAWTEXT_CLOSE_RE.search(line)
            if m and m.group("tag").lower() == html_tag:
                html_tag = None
                html_opened_at = None
            continue
        if html_terminator is not None:
            out.append(" " * len(line))
            if html_terminator in line:
                html_terminator = None
                html_opened_at = None
                prev_blank = False
            continue
        if html_until_blank:
            out.append(" " * len(line))
            if not line.strip():
                html_until_blank = False
                prev_blank = True
            continue
        if fence_char is None:
            m = _RENDER_HTML_RAWTEXT_OPEN_RE.match(line)
            if m:
                tag = m.group("tag").lower()
                close = _RENDER_HTML_RAWTEXT_CLOSE_RE.search(line)
                # A single-line <pre>…</pre> opens and closes at once.
                if not (close and close.group("tag").lower() == tag):
                    html_tag = tag
                    html_opened_at = line_no
                out.append(" " * len(line))
                continue
            stripped = line.strip()
            is_comment = stripped.startswith("<!--")
            type345 = None
            if not is_comment:
                for pattern, terminator in _RENDER_HTML_TYPE345:
                    if pattern.match(line):
                        type345 = terminator
                        break
            if type345 is not None:
                # Opens and closes on the same line when its terminator is
                # already present.
                if type345 not in line:
                    html_terminator = type345
                    html_opened_at = line_no
                out.append(" " * len(line))
                prev_blank = False
                continue
            # Type 7 (any complete tag alone on its line) may not interrupt
            # a paragraph, so it requires a preceding blank line. Types 2
            # and 6 may. That restriction is exactly why blanking type 7
            # leaves inline HTML in running prose alone.
            is_type7 = (
                prev_blank
                and not is_comment
                and _RENDER_HTML_TYPE7_OPEN_RE.match(line)
                and not _RENDER_HTML_TYPE6_OPEN_RE.match(line)
            )
            if (
                (is_comment and blank_html_comments)
                or (not is_comment and _RENDER_HTML_TYPE6_OPEN_RE.match(line))
                or is_type7
            ):
                # Types 2, 6 and 7 all run until a blank line. A type-2
                # comment that closes on its own line still ends its block
                # at the next blank line, per CommonMark.
                if not (is_comment and "-->" in stripped):
                    html_until_blank = True
                out.append(" " * len(line))
                prev_blank = False
                continue
            m = _RENDER_FENCE_OPEN_RE.match(line)
            if m:
                run = m.group("btick") or m.group("tilde")
                fence_char = run[0]
                fence_len = len(run)
                opened_at = line_no
                out.append(" " * len(line))
                prev_blank = False
                continue
            out.append(line)
            prev_blank = not line.strip()
        else:
            stripped = line.strip()
            # A closer must use the same character and be at least as long
            # as its opener; a shorter run, or the other delimiter, does not
            # close the block.
            is_closer = (
                stripped
                and set(stripped) == {fence_char}
                and len(stripped) >= fence_len
            )
            out.append(" " * len(line))
            if is_closer:
                fence_char = None
                fence_len = 0
                opened_at = None
    # An unterminated HTML block swallows the rest of the document exactly
    # as an unterminated fence does, and the caller FAILs on either.
    unterminated = [x for x in (opened_at, html_opened_at) if x is not None]
    return "\n".join(out), (min(unterminated) if unterminated else None)

_RENDER_TITLE_MAX = 120

# The render contract is a v1.6.0+ obligation. Runs produced by earlier
# skill versions rendered to a different (unspecified) contract and must not
# be retroactively failed — 49 archived trees under repos/ and metrics/
# carry the `### REQ-NNN:` heading shape, which long predates v1.6.0, so
# heading shape alone is not a version test.
_RENDER_CONTRACT_MIN_VERSION = (1, 6, 0)


def _render_version_tuple(text):
    """Parse a dotted version string into a comparable tuple, or None."""
    if not text:
        return None
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", str(text))
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))


def _render_run_predates_contract(q, skill_version):
    """True when this run was produced before the render contract existed.

    Prefers the run's OWN recorded version (PROGRESS.md `Skill version:`)
    over the ambient SKILL.md, because the question is "which skill rendered
    these artifacts", not "which skill is installed now".
    """
    recorded = None
    progress = q / "PROGRESS.md"
    if progress.is_file():
        recorded = read_skill_value_line(progress, "Skill version:")
    version = _render_version_tuple(recorded) or _render_version_tuple(skill_version)
    if version is None:
        return False, None
    return version < _RENDER_CONTRACT_MIN_VERSION, version


def _render_scan_internals(text):
    """Return human-readable descriptions of derivation internals in `text`.

    Fenced code blocks are blanked (length-preserving, so reported line
    numbers stay accurate) before scanning: a REQ about a template engine or
    an HTML sanitizer has to be able to quote an HTML comment.
    """
    # blank_html_comments=False: an HTML comment in the render is
    # itself the C-5 defect this scan reports, so it must stay visible.
    scanned = _render_blank_fences(text, blank_html_comments=False)
    scanned = _RENDER_INLINE_CODE_RE.sub(
        lambda m: re.sub(r"[^\n]", " ", m.group(0)), scanned
    )
    found = []
    for m in re.finditer(r"<!--", scanned):
        found.append(f"HTML comment at line {scanned[: m.start()].count(chr(10)) + 1}")
        break
    for pattern, label in _RENDER_INTERNAL_PATTERNS:
        m = pattern.search(scanned)
        if m:
            line_no = scanned[: m.start()].count("\n") + 1
            found.append(f"{label} at line {line_no}")
    return found


def _render_overview_body(text, level2):
    """Return the prose F-1 may live in.

    That is the Overview section, plus any dedicated coverage/gaps section —
    §8 says the statement goes *in* the Overview, but a renderer that gives
    it its own heading has satisfied the intent, and failing that would be
    the contract over-firing on a correct document.
    """
    bounds = [off for _h, off in level2] + [len(text)]
    collected = []
    for idx, (heading, off) in enumerate(level2):
        if re.match(
            r"^((project\s+)?overview|coverage(\s+and\s+.*)?|known\s+gaps)\b",
            heading,
            re.IGNORECASE,
        ):
            body = text[off: bounds[idx + 1]]
            collected.append(body.split("\n", 1)[1] if "\n" in body else "")
    return "\n".join(collected)


def _render_named_section_body(text, level2, heading_pattern):
    """Return the body of the first level-2 section whose heading matches.

    Returns None when no such heading exists, so callers can distinguish
    "absent" from "present but empty".
    """
    bounds = [off for _h, off in level2] + [len(text)]
    for idx, (heading, off) in enumerate(level2):
        if re.match(heading_pattern, heading, re.IGNORECASE):
            body = text[off: bounds[idx + 1]]
            return body.split("\n", 1)[1] if "\n" in body else ""
    return None


# v1.6.0 instruction 006 (Design §5.2 item 4): the requirements are grouped
# by an organizing principle the derivation *chooses* per system (IEEE 830
# §5.3 menu), not a fixed "functional" mandate. The render contract checks
# only that a principle is NAMED with a RATIONALE (presence, not whether the
# choice is optimal — that is Feature D Stage 1 + the Well-organized rubric,
# matrix row 4c). These patterns detect the stated choice at the top of the
# section list.
_RENDER_PRINCIPLE_RE = re.compile(
    r"organiz(?:ed|ing)\s+(?:these\s+|the\s+|its\s+)?(?:requirements?\s+)?"
    r"(?:by|around|according to)\b"
    r"|grouped\s+(?:these\s+|the\s+)?(?:requirements?\s+)?by\b"
    r"|organizing\s+principle\b"
    r"|sections?\s+are\s+organized\b",
    re.IGNORECASE,
)
_RENDER_PRINCIPLE_RATIONALE_RE = re.compile(
    r"\bbecause\b|\bsince\b|\bas this\b|\bas it\b|\bto reflect\b|"
    r"\breflect(?:s|ing)\b|\bso that\b|\bwhich lets\b|\bgiven that\b",
    re.IGNORECASE,
)


def _render_organizing_principle_stated(text, first_section_offset):
    """Detect the stated organizing principle (Design §5.2 item 4, row 4b).

    Looks in the zone before the first requirement section (the "top of the
    section list") for a paragraph that *names* an organizing principle and
    carries a *rationale*. Returns (named: bool, rationale: bool). Rationale
    is checked only within the paragraph that names the principle, so a
    "because" elsewhere in the Overview cannot satisfy it.
    """
    zone = text[:first_section_offset] if first_section_offset is not None else text
    named = False
    rationale = False
    for para in re.split(r"\n\s*\n", zone):
        if _RENDER_PRINCIPLE_RE.search(para):
            named = True
            if _RENDER_PRINCIPLE_RATIONALE_RE.search(para):
                rationale = True
                break
    return named, rationale


def _render_classify_sections(text, level2):
    """Split level-2 headings into (structural, functional).

    A heading is structural only if it both matches the structural-name
    pattern AND contains no REQ headings. The second condition is what makes
    the classifier robust to a document that parks all its REQs under a
    generically-named heading.
    """
    bounds = [off for _h, off in level2] + [len(text)]
    functional = []
    for idx, (heading, off) in enumerate(level2):
        body = text[off: bounds[idx + 1]]
        has_reqs = bool(_RENDER_REQ_HEADING_RE.search(body))
        if not has_reqs:
            continue
        if _RENDER_STRUCTURAL_HEADING_RE.match(heading):
            # A canonical structural part (Overview, Use cases, …) that
            # holds REQs is not thereby a functional section — parking
            # every requirement under `## Overview` must not synthesize
            # one. Leaving it out means `functional` ends up empty, which
            # the caller reports as its own FAIL.
            continue
        functional.append((heading, off))
    return functional


def _render_req_headings(text):
    """Return [(req_id, number:int, title, start_offset)] in document order.

    Runs over fence-blanked text so a REQ heading quoted inside a code
    block is not mistaken for a real one.
    """
    out = []
    for m in _RENDER_REQ_HEADING_RE.finditer(_render_blank_fences(text)):
        out.append((m.group(1), int(m.group(2)), m.group(3).strip(), m.start()))
    return out


def _render_tool_contract_ids(q):
    """REQ ids whose references[] point exclusively into quality/.

    These are QPB's own run-layout invariants (C-1), not requirements of
    the audited system. Returns None when no manifest is available.
    """
    data = _v150_manifest(q, "requirements_manifest.json")
    if not data:
        return None
    records = data.get("records")
    if not isinstance(records, list):
        return None
    ids = set()
    for rec in records:
        if not isinstance(rec, dict):
            continue
        refs = rec.get("references") or []
        if not isinstance(refs, list) or not refs:
            continue
        if all(str(r).startswith("quality/") for r in refs):
            rid = rec.get("id")
            if rid:
                ids.add(str(rid))
    return ids


def _render_product_req_count(q):
    """Count **product** REQ records in requirements_manifest.json.

    Product = total REQ records minus the tool-contract ones (whose
    references[] point exclusively into quality/, C-1). This is what the
    render contract expects to see as `### REQ-NNN:` headings in
    REQUIREMENTS.md; a tool-contract-only manifest renders to
    RUN_CONTRACT.md instead and is not a product-render failure.

    Returns None when no manifest is available — the contract then cannot
    prove requirements exist, so the caller keeps the INFO skip rather than
    FAILing without evidence (Design §5.3 "fail closed on a
    manifest-vs-render marker mismatch").
    """
    data = _v150_manifest(q, "requirements_manifest.json")
    if not data:
        return None
    records = data.get("records")
    if not isinstance(records, list):
        return None
    tool_ids = _render_tool_contract_ids(q) or set()
    n = 0
    for rec in records:
        if not isinstance(rec, dict):
            continue
        rid = rec.get("id")
        if not rid:
            continue
        if str(rid) in tool_ids:
            continue
        n += 1
    return n


@verdict_category(VERDICT_SUBSTANTIVE)
def check_render_contract(repo_dir, q, skill_version=None):
    """v1.6.0 Feature C — the mechanical render-contract checks.

    Implements the six checks of Design §5.3, the mandatory-part list of
    §5.2, and the F-1 advisory of §8.

    Inert in two cases, both deliberate:

    - the run recorded a skill version below the contract's floor (read
      from PROGRESS.md, falling back to the detected SKILL.md version) —
      earlier runs rendered to a different, unspecified contract;
    - REQUIREMENTS.md carries no `### REQ-NNN:` headings at all, so there
      is no contract-shaped render to check. REQ headings at the *wrong*
      level WARN rather than passing silently, so a heading-level
      regression cannot disable the contract unnoticed.
    """
    print("[Render Contract]")
    req_md = q / "REQUIREMENTS.md"
    if not req_md.is_file():
        info("REQUIREMENTS.md not present — render contract not applicable")
        return
    text = _read_text_safe(req_md)
    # Checked before anything else: everything after an unterminated fence
    # is inside the code block, so REQ headings below it are invisible and
    # the contract would silently go inert on a document it cannot read.
    # Refuse to certify rather than pass by default.
    _blanked, unterminated_fence = _render_blank_fences_ex(text)
    if unterminated_fence is not None:
        fail(
            "REQUIREMENTS.md",
            f"unterminated code fence or HTML block opened at line "
            f"{unterminated_fence} — everything after it is inside that "
            "block, so the render contract cannot read the rest of the "
            "document. Close it.",
        )
        return
    # The version gate runs BEFORE the headings check: the whole contract is
    # a v1.6.0+ obligation, so a pre-contract run is inert regardless of the
    # marker shape it happens to carry. This MUST precede the fail-closed
    # no-headings branch below — otherwise a genuine pre-v1.6.0 archived run
    # (populated manifest, old-format render with no '### REQ-NNN:' headings)
    # would FAIL against a contract it has no obligation to meet, the exact
    # regression the inertness guards protect against.
    predates, detected = _render_run_predates_contract(q, skill_version)
    if predates:
        info(
            f"run recorded skill version {detected[0]}.{detected[1]}."
            f"{detected[2]} — the render contract is a v"
            f"{_RENDER_CONTRACT_MIN_VERSION[0]}.{_RENDER_CONTRACT_MIN_VERSION[1]}."
            f"{_RENDER_CONTRACT_MIN_VERSION[2]}+ obligation, skipped"
        )
        return

    headings = _render_req_headings(text)
    if not headings:
        # A heading-level regression in the renderer would otherwise turn
        # the entire contract off with no operator signal, so say so louder
        # than INFO when REQ headings exist at the wrong level.
        if re.search(r"^#{2,6}\s+REQ-\d+\s*:", text, re.MULTILINE):
            warn(
                "REQUIREMENTS.md has REQ headings, but none at the '### "
                "REQ-NNN:' level the render contract requires "
                "(references/requirements_pipeline.md § 'Requirement heading "
                "format') — the entire render contract is inert on this "
                "document"
            )
        else:
            # Design §5.3 "fail closed on a manifest-vs-render marker
            # mismatch": the manifest already proves whether requirements
            # exist, so the contract must not go inert just because the
            # generator used the wrong marker (e.g. '**REQ-NNN:**' bold
            # instead of '### REQ-NNN:'). A populated manifest with an
            # unparseable render is the same situation as an unterminated
            # fence — refuse to certify rather than pass by default.
            product_reqs = _render_product_req_count(q)
            if product_reqs:
                fail(
                    "REQUIREMENTS.md",
                    f"requirements_manifest.json holds {product_reqs} product "
                    "REQ record(s), but REQUIREMENTS.md carries zero '### "
                    "REQ-NNN:' headings — the requirements were not rendered in "
                    "contract shape (most likely the wrong marker format, e.g. "
                    "'**REQ-NNN:**' bold instead of '### REQ-NNN:'). The whole "
                    "render contract cannot read this document. Render each "
                    "requirement as a '### REQ-NNN: Title' heading — see "
                    "references/requirements_pipeline.md § 'Requirement heading "
                    "format' and references/phase2_generation_guide.md § "
                    "'Requirement heading format'.",
                )
            elif product_reqs == 0:
                info(
                    "REQUIREMENTS.md carries no '### REQ-NNN:' headings and "
                    "requirements_manifest.json holds no product REQ records — "
                    "nothing to render, render contract not applicable"
                )
            else:
                # Manifest unavailable: cannot prove requirements exist, so
                # skip rather than FAIL without evidence.
                info(
                    "REQUIREMENTS.md carries no '### REQ-NNN:' headings and "
                    "requirements_manifest.json is unavailable — not a "
                    "contract-shaped render, render contract skipped"
                )
        return

    # -- Check 1 (C-2): REQ IDs strictly sequential in document order. -----
    numbers = [n for (_rid, n, _t, _o) in headings]
    expected = list(range(1, len(numbers) + 1))
    if numbers == expected:
        pass_(f"REQ IDs sequential in document order (REQ-001..REQ-{len(numbers):03d})")
    else:
        first_bad = next(
            (i for i, (a, b) in enumerate(zip(numbers, expected)) if a != b),
            0,
        )
        fail(
            "REQUIREMENTS.md",
            f"REQ IDs are not sequential in document order: expected "
            f"REQ-{expected[first_bad]:03d} at document position "
            f"{first_bad + 1}, found {headings[first_bad][0]} "
            f"(order: {', '.join(h[0] for h in headings[:8])}"
            f"{'...' if len(headings) > 8 else ''}). "
            "Phase E.6 renumbers to document order — see "
            "references/requirements_pipeline.md § E.6.",
        )

    # -- Check 2 (C-1): no tool-contract REQs in the product spec. ---------
    tool_ids = _render_tool_contract_ids(q)
    if tool_ids is None:
        info(
            "requirements_manifest.json unavailable — tool-contract "
            "split not checked"
        )
    else:
        rendered_ids = {h[0] for h in headings}
        leaked = sorted(tool_ids & rendered_ids)
        if leaked:
            fail(
                "REQUIREMENTS.md",
                f"{len(leaked)} tool-contract REQ(s) rendered into the "
                f"product spec: {', '.join(leaked)}. REQs whose references[] "
                "point exclusively into quality/ are QPB run-layout "
                "invariants, not requirements of the audited system — "
                "render them to quality/RUN_CONTRACT.md "
                "(references/phase2_generation_guide.md § 'Split the "
                "product spec from the tool contract').",
            )
        else:
            # Deliberately does NOT claim the REQs were "routed to
            # RUN_CONTRACT.md" — that is the next branch's job to verify,
            # and this line is printed before it runs.
            pass_(
                "no tool-contract REQs in REQUIREMENTS.md "
                f"({len(tool_ids)} tool-contract REQ(s) in the manifest)"
            )
        if tool_ids:
            run_contract = q / "RUN_CONTRACT.md"
            if not run_contract.is_file():
                fail(
                    "RUN_CONTRACT.md",
                    f"absent, but {len(tool_ids)} tool-contract REQ(s) exist "
                    "in requirements_manifest.json — they must render "
                    "somewhere (v1.6.0 Design §5.1).",
                )
            else:
                rc_ids = {h[0] for h in _render_req_headings(_read_text_safe(run_contract))}
                missing = sorted(tool_ids - rc_ids)
                if missing:
                    fail(
                        "RUN_CONTRACT.md",
                        f"missing {len(missing)} tool-contract REQ(s): "
                        f"{', '.join(missing)}. The split relocates these "
                        "records; it must not drop them.",
                    )
                else:
                    pass_(
                        f"RUN_CONTRACT.md carries all {len(tool_ids)} "
                        "tool-contract REQ(s)"
                    )
                # RUN_CONTRACT.md is a generated Markdown artifact like any
                # other: it carries the same stamp obligation and the same
                # no-internals rule. Without this, C-7 and C-5 could ship
                # undetected in the very artifact this release introduces.
                rc_text = _read_text_safe(run_contract)
                rc_stamp = _RENDER_STAMP_RE.search(rc_text)
                if not rc_stamp:
                    fail(
                        "RUN_CONTRACT.md",
                        "no 'Generated by Quality Playbook v<version>' "
                        "attribution stamp (mandatory on every generated "
                        "Markdown file).",
                    )
                elif skill_version and rc_stamp.group(1) != skill_version:
                    fail(
                        "RUN_CONTRACT.md",
                        f"generator stamp says v{rc_stamp.group(1)} but the "
                        f"skill version is v{skill_version} (C-7).",
                    )
                rc_internals = _render_scan_internals(rc_text)
                if rc_internals:
                    fail(
                        "RUN_CONTRACT.md",
                        "derivation internals leaked into the rendered "
                        "document: " + "; ".join(rc_internals) + ".",
                    )

    # -- Check 3 (C-3, C-4): required parts + section discipline. ----------
    # Fence-blanked: a `##` line inside a code fence is quoted material.
    structure_text, _unterminated = _render_blank_fences_ex(text)
    level2 = [
        (m.group(1).strip(), m.start())
        for m in _RENDER_LEVEL2_RE.finditer(structure_text)
    ]
    has_overview = any(
        re.match(r"^(project\s+)?overview\b", h, re.IGNORECASE) for h, _ in level2
    )
    if has_overview:
        pass_("Overview section present")
    else:
        fail(
            "REQUIREMENTS.md",
            "no Overview section. The Overview is mandatory on every run "
            "regardless of target size (v1.6.0 Design §5.2 item 2; "
            "references/requirements_pipeline.md § E.1).",
        )

    # §5.2 makes eight parts canonical, four of them unconditionally
    # mandatory. Checking only Overview and cross-cutting left a document
    # that dumps every REQ into one undifferentiated bucket — no actors, no
    # use cases, no traceability — scoring clean, which is precisely the
    # "flat list, not a coherent document" shape §5.2 exists to reject.
    for label, pattern in (
        ("Actors & roles", r"^actors?\b"),
        ("Use cases", r"^use\s*cases?\b"),
        ("Traceability appendix", r"^traceability\b"),
    ):
        if any(re.match(pattern, h, re.IGNORECASE) for h, _ in level2):
            pass_(f"{label} section present")
        else:
            fail(
                "REQUIREMENTS.md",
                f"no {label} section. The eight-part document architecture "
                "makes it mandatory on every run (v1.6.0 Design §5.2).",
            )

    functional = _render_classify_sections(structure_text, level2)

    # A document that HAS requirements but no requirement section at all has
    # opted out of the entire section discipline below. That is a FAIL in
    # its own right, not a reason to skip the checks silently.
    if not functional:
        fail(
            "REQUIREMENTS.md",
            f"{len(headings)} REQ heading(s) but no requirement section — "
            "every requirement sits outside the section structure, so "
            "section discipline (section overview, singleton merge, "
            "cross-cutting concerns) cannot apply. Group the requirements "
            "into sections under the chosen organizing principle "
            "(v1.6.0 Design §5.2 item 4).",
        )

    # -- §5.2 item 4 / matrix row 4b: the organizing principle must be
    # NAMED with a rationale at the top of the section list. The derivation
    # chooses the principle (IEEE 830 §5.3 menu); the contract checks only
    # that a choice is stated, not whether it is optimal (that is Feature D
    # Stage 1 + the Well-organized rubric — matrix row 4c, judgment-only).
    if functional:
        first_section_offset = min(off for _h, off in functional)
        named, rationale = _render_organizing_principle_stated(
            structure_text, first_section_offset)
        if not named:
            fail(
                "REQUIREMENTS.md",
                "no organizing principle stated at the top of the section "
                "list. The derivation must name the principle it grouped the "
                "requirements by (feature, use case, user class, mode, object, "
                "interface, functional hierarchy, or a justified combination) "
                "and give a one-paragraph rationale — e.g. 'Organized by user "
                "journey because this is a workflow system.' (v1.6.0 Design "
                "§5.2 item 4; references/requirements_pipeline.md § E — "
                "Choosing the organizing principle).",
            )
        elif not rationale:
            fail(
                "REQUIREMENTS.md",
                "an organizing principle is named but carries no rationale. "
                "State in the same paragraph *why* this principle fits this "
                "system (a 'because'/'since' clause) — the choice and its "
                "reason are what the operator validates in the Feature D "
                "interview (v1.6.0 Design §5.2 item 4).",
            )
        else:
            pass_("organizing principle named with a rationale")
    # Count REQs per functional section by document offset.
    bounds = [off for _h, off in level2] + [len(structure_text)]
    section_req_counts = {}
    section_intro_ok = {}
    for h, off in functional:
        idx = [o for _x, o in level2].index(off)
        end = bounds[idx + 1]
        body = text[off:end]
        section_req_counts[h] = len(_render_req_headings(body))
        # Intro prose = non-blank, non-heading text between the section
        # heading and its first REQ heading.
        first_req = _RENDER_REQ_HEADING_RE.search(body)
        head_zone = body[: first_req.start()] if first_req else body
        head_zone = head_zone.split("\n", 1)[1] if "\n" in head_zone else ""
        intro = "\n".join(
            ln for ln in head_zone.splitlines() if ln.strip() and not ln.lstrip().startswith("#")
        ).strip()
        section_intro_ok[h] = len(intro) >= 40

    if functional:
        no_intro = sorted(h for h in section_intro_ok if not section_intro_ok[h])
        if no_intro:
            fail(
                "REQUIREMENTS.md",
                f"{len(no_intro)} requirement section(s) lack a section "
                f"overview stating the theme that unifies their requirements "
                f"under the chosen organizing principle: "
                f"{', '.join(repr(h) for h in no_intro[:5])}"
                f"{'...' if len(no_intro) > 5 else ''} "
                "(v1.6.0 Design §5.2 item 4).",
            )
        else:
            pass_(f"all {len(functional)} requirement section(s) carry a section overview")

        singletons = sorted(h for h, c in section_req_counts.items() if c == 1)
        if singletons:
            # A singleton is admissible with an explicit one-line
            # justification; look for it in the section's intro zone.
            unjustified = []
            for h in singletons:
                idx = [x for x, _o in level2].index(h)
                off = level2[idx][1]
                body = structure_text[off: bounds[idx + 1]]
                # Search only the intro zone (heading -> first REQ), not the
                # whole section: otherwise a REQ title or condition of
                # satisfaction containing "only requirement" silently
                # satisfies the escape hatch. The justification is a
                # statement the section makes about itself.
                first_req = _RENDER_REQ_HEADING_RE.search(body)
                intro_zone = body[: first_req.start()] if first_req else body
                if not re.search(
                    r"singleton|stands? alone|standing alone|single[- ]REQ|"
                    r"only requirement|deliberately (its own|separate)",
                    intro_zone,
                    re.IGNORECASE,
                ):
                    unjustified.append(h)
            if unjustified:
                fail(
                    "REQUIREMENTS.md",
                    f"{len(unjustified)} requirement section(s) hold exactly "
                    f"one REQ with no justification for standing alone: "
                    f"{', '.join(repr(h) for h in unjustified[:6])}"
                    f"{'...' if len(unjustified) > 6 else ''}. "
                    "Merge into a related section or carry a one-line "
                    "justification (v1.6.0 Design §5.2 item 4 — the "
                    "express six-singleton shape).",
                )
            else:
                pass_(f"{len(singletons)} singleton section(s) carry justifications")
        else:
            pass_("no degenerate singleton requirement sections")

        if len(functional) > 1:
            has_cc = any(
                re.match(r"^cross[-\s]?cutting", h, re.IGNORECASE) for h, _ in level2
            )
            if has_cc:
                pass_("Cross-cutting concerns section present")
            else:
                fail(
                    "REQUIREMENTS.md",
                    f"no Cross-cutting concerns section, but the document has "
                    f"{len(functional)} requirement sections — mandatory at >1 "
                    "(v1.6.0 Design §5.2 item 6; references/"
                    "requirements_pipeline.md § E.3).",
                )

    # -- Check 4 (C-5): no derivation internals in the render. -------------
    internals = _render_scan_internals(text)
    if internals:
        fail(
            "REQUIREMENTS.md",
            "derivation internals leaked into the rendered document: "
            + "; ".join(internals)
            + ". This metadata belongs in requirements_manifest.json, not "
            "in the adopter-facing spec (v1.6.0 Design §5.3 check 4).",
        )
    else:
        pass_("no derivation internals in the rendered document")

    # -- Check 5 (C-6): REQ title discipline. ------------------------------
    long_titles = [(rid, len(t)) for (rid, _n, t, _o) in headings if len(t) > _RENDER_TITLE_MAX]
    dotted = [rid for (rid, _n, t, _o) in headings if t.endswith(".")]
    if long_titles:
        fail(
            "REQUIREMENTS.md",
            f"{len(long_titles)} REQ title(s) exceed {_RENDER_TITLE_MAX} "
            f"characters: "
            + ", ".join(f"{rid} ({n} chars)" for rid, n in long_titles[:5])
            + f"{'...' if len(long_titles) > 5 else ''}. A REQ title is a "
            "noun-phrase statement of the contract, not a full normative "
            "sentence (v1.6.0 Design §5.3 check 5).",
        )
    else:
        pass_(f"all {len(headings)} REQ titles within {_RENDER_TITLE_MAX} characters")
    if dotted:
        fail(
            "REQUIREMENTS.md",
            f"{len(dotted)} REQ title(s) end with a terminal period: "
            + ", ".join(dotted[:6])
            + f"{'...' if len(dotted) > 6 else ''}. Titles are noun phrases, "
            "not sentences (v1.6.0 Design §5.3 check 5).",
        )
    else:
        pass_("no REQ title carries a terminal period")

    # -- Check 6 (C-7): generator stamp matches the single version source. --
    stamp = _RENDER_STAMP_RE.search(text)
    if not stamp:
        fail(
            "REQUIREMENTS.md",
            "no 'Generated by Quality Playbook v<version>' attribution "
            "stamp (references/phase2_generation_guide.md § 'Version "
            "stamp' — mandatory on every generated Markdown file).",
        )
    elif skill_version and stamp.group(1) != skill_version:
        fail(
            "REQUIREMENTS.md",
            f"generator stamp says v{stamp.group(1)} but the skill version "
            f"is v{skill_version}. The stamp must be read from SKILL.md "
            "metadata.version, never copied as a literal from the "
            "generation guide (C-7 regression pin).",
        )
    else:
        pass_(f"generator stamp matches skill version (v{stamp.group(1)})")

    # -- F-1 (advisory, WARN only): coverage-and-gaps statement. -----------
    # Never FAILs — its purpose is to make thin coverage visible to the
    # operator, and to give the validation interview its Stage-1 opener.
    # Scoped to the Overview, not the whole document: a stray "not covered"
    # in a traceability appendix is not a coverage disclosure. §8 also
    # requires the statement be non-empty, so a bare heading does not pass.
    overview_body = _render_overview_body(structure_text, level2)
    gaps_match = re.search(
        r"(coverage\s+and\s+(known\s+)?gaps|known\s+gaps|not\s+covered|"
        r"did\s+not\s+cover|out\s+of\s+reach|deliberately\s+(did\s+not|"
        r"excluded))",
        overview_body,
        re.IGNORECASE,
    )
    if gaps_match:
        # Non-emptiness: require substantive prose after the cue phrase,
        # not just the phrase itself.
        tail = overview_body[gaps_match.start():].strip()
        if len(tail) >= 80:
            pass_("coverage-and-gaps statement present in the Overview")
        else:
            warn(
                "REQUIREMENTS.md Overview names coverage-and-gaps but the "
                "statement is empty or near-empty — the operator gets a "
                "heading, not a disclosure (v1.6.0 F-1; advisory)"
            )
    else:
        warn(
            "REQUIREMENTS.md Overview carries no coverage-and-gaps statement "
            "— the operator has no signal about what the derivation chose "
            "not to cover (v1.6.0 F-1; advisory, never a FAIL)"
        )

    # -- Glossary / definitions (advisory, WARN only). ---------------------
    # IEEE 830 §1.3 gives definitions their own slot because terminology
    # drift is a top requirements defect class, and terminology stability is
    # what the readability rubric's Consistent dimension scores.
    #
    # Deliberately modelled on the F-1 check above and bound by the same
    # rule: this emits warn() and info() ONLY. It has no fail() path, by
    # construction rather than by luck — a target whose vocabulary is
    # genuinely unambiguous does not need a glossary, and a run that
    # produced good requirements must not be failed for omitting one. The
    # three v1.6.0 regeneration fixtures carry no glossary and must keep
    # passing; see test_render_contract_v160.GlossarySlotTests.
    glossary_body = _render_named_section_body(
        structure_text, level2, r"^(glossary|definitions|terms(\s|$)|"
        r"glossary\s*(&|and|/)\s*definitions)"
    )
    if glossary_body is None:
        warn(
            "REQUIREMENTS.md has no glossary/definitions section — domain "
            "terms are undefined, which is the terminology-drift defect "
            "class IEEE 830 §1.3 exists for (v1.6.0; advisory, never a FAIL)"
        )
    elif len(glossary_body.strip()) < 40:
        warn(
            "REQUIREMENTS.md glossary section is empty or near-empty — the "
            "reader gets a heading, not definitions (v1.6.0; advisory, "
            "never a FAIL)"
        )
    else:
        pass_("glossary/definitions section present")


# ---------------------------------------------------------------------------
# v1.6.0 Feature D / F-2a — operator_confirmations.jsonl append-only durability.
#
# The interview's write-back is durable across runs only if the derivation
# cannot destroy it. schemas.md §9.5.2: a run that deletes, truncates, or
# shortens quality/operator_confirmations.jsonl FAILs the gate. "Append-only"
# reduces to one checkable property — the current file has the prior file as a
# byte prefix — enforced against a prior snapshot at
# quality/operator_confirmations.prior.jsonl when a re-derivation left one.
#
# The gate re-declares this rather than importing run_state_lib, matching the
# module's existing self-containment convention (see BUG_HEADING_PATTERN_STR).
# ---------------------------------------------------------------------------

_OPCONF_REQUIRED_FIELDS = (
    "ts", "move", "req_title", "conditions_of_satisfaction",
    "operator_statement", "session_id",
)
_OPCONF_MOVES = ("confirm", "correct", "add", "drop", "defer")


def _opconf_is_append_only(prior_text, current_text):
    """True iff current_text is an append-only extension of prior_text.

    Mirror of run_state_lib.confirmations_append_only; kept inline so the
    gate imports nothing. A truncation, rewrite, or reorder breaks the prefix.
    """
    if not prior_text:
        return True
    normalized = prior_text if prior_text.endswith("\n") else prior_text + "\n"
    if current_text == prior_text:
        return True
    return current_text.startswith(normalized)


def _operator_confirmed_req_ids(q):
    """REQ ids in the manifest whose source_type is operator-confirmation.

    These are the REQs an interview produced; their existence in the manifest
    is the cross-reference that makes the durability guarantee enforceable
    without a snapshot — see check_operator_confirmations_append_only.
    """
    data = _v150_manifest(q, "requirements_manifest.json")
    if not data:
        return []
    records = data.get("records")
    if not isinstance(records, list):
        return []
    return [
        r.get("id") for r in records
        if isinstance(r, dict) and r.get("source_type") == "operator-confirmation"
    ]


@verdict_category(VERDICT_SUBSTANTIVE)
def check_operator_confirmations_append_only(q):
    """v1.6.0 F-2a — operator_confirmations.jsonl durability + shape.

    Two enforcement mechanisms, because the durability guarantee has two
    halves (self-Council instr 003, Panelists A and D):

    1. **Manifest-consistency (needs no snapshot).** If the manifest carries
       operator-confirmation REQs, the durable log MUST be present and
       non-empty — those REQs assert an interview produced confirmations, so
       a re-derivation that keeps the REQs but deletes or empties their
       backing has destroyed the operator's work. This closes the
       "delete/empty the whole file" hole that a prior-snapshot-only check
       missed: an absent file is not automatically "no interview ran".

    2. **Append-only prefix (needs a snapshot).** When a re-derivation left
       a .prior.jsonl snapshot, the live file must have it as a byte prefix
       — catching truncation, rewrite, and reorder even across runs where
       the manifest no longer names the confirmed REQs. The protocol
       instructs a re-derivation to write that snapshot before rewriting
       quality/ (references/requirements_interview.md).

    Substantive, not record-keeping: a lost confirmation is lost operator
    work, which is the whole point of F-2a.
    """
    print("[Operator Confirmations]")
    path = q / "operator_confirmations.jsonl"
    confirmed_ids = _operator_confirmed_req_ids(q)

    if not path.is_file():
        if confirmed_ids:
            fail(
                "operator_confirmations.jsonl",
                f"absent, but requirements_manifest.json carries "
                f"{len(confirmed_ids)} operator-confirmation REQ(s) "
                f"({', '.join(str(i) for i in confirmed_ids[:5])}"
                f"{'...' if len(confirmed_ids) > 5 else ''}) — the operator's "
                "confirmations have no durable backing. A re-derivation that "
                "kept the REQs but dropped the log destroyed the durability "
                "record (F-2a; schemas.md §9.5.2).",
            )
        else:
            info("operator_confirmations.jsonl not present — no interview has run")
        return

    text = _read_text_safe(path)
    records = 0
    shape_ok = True
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        records += 1
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            fail(
                "operator_confirmations.jsonl",
                f"line {lineno} is not valid JSON — a durability log that "
                "cannot be parsed cannot protect the operator's work "
                "(schemas.md §9.5)",
            )
            shape_ok = False
            continue
        if not isinstance(obj, dict):
            fail("operator_confirmations.jsonl",
                 f"line {lineno} is not a JSON object (schemas.md §9.5.1)")
            shape_ok = False
            continue
        # Type-check, not mere presence: a null or non-string required field
        # passes a presence check but is not what the sanctioned writer
        # (run_state_lib.append_confirmation) produces (Panelists B, D).
        for field in _OPCONF_REQUIRED_FIELDS:
            val = obj.get(field)
            if not isinstance(val, str) or not val.strip():
                fail("operator_confirmations.jsonl",
                     f"line {lineno} field {field!r} must be a non-empty "
                     f"string, got {val!r} (schemas.md §9.5.1)")
                shape_ok = False
        move = obj.get("move")
        if isinstance(move, str) and move not in _OPCONF_MOVES:
            fail("operator_confirmations.jsonl",
                 f"line {lineno} move={move!r} is not one of "
                 f"{_OPCONF_MOVES} (schemas.md §9.5.1)")
            shape_ok = False

    # Mechanism 1: manifest names confirmed REQs but the log is empty.
    if confirmed_ids and records == 0:
        fail(
            "operator_confirmations.jsonl",
            f"is empty, but requirements_manifest.json carries "
            f"{len(confirmed_ids)} operator-confirmation REQ(s) — the "
            "confirmations were dropped (F-2a; schemas.md §9.5.2).",
        )
        shape_ok = False

    # Mechanism 2: append-only prefix vs a prior snapshot, when one exists.
    prior_path = q / "operator_confirmations.prior.jsonl"
    if prior_path.is_file():
        prior_text = _read_text_safe(prior_path)
        if _opconf_is_append_only(prior_text, text):
            pass_(
                f"operator_confirmations.jsonl is append-only vs. its prior "
                f"snapshot ({records} record(s))"
            )
        else:
            fail(
                "operator_confirmations.jsonl",
                "is NOT an append-only extension of its prior snapshot — a "
                "re-derivation truncated, overwrote, or reordered the "
                "operator's confirmations (F-2a; schemas.md §9.5.2). The "
                "operator's work must survive re-derivation.",
            )
    elif shape_ok:
        pass_(
            f"operator_confirmations.jsonl well-formed ({records} record(s)"
            + (f", backing {len(confirmed_ids)} confirmed REQ(s)"
               if confirmed_ids else "")
            + ")"
        )


# The six Wiegers dimensions the interview defect log organizes by, plus the
# dimension-6 addition. The log must speak this vocabulary — it is the same
# one the readability rubric and the Council score against (one vocabulary,
# three consumers).
_REQ_REVIEW_DIMENSIONS = (
    "complete", "consistent", "unambiguous", "verifiable",
    "well-organized", "honest",
)
_REQ_REVIEW_MOVES = ("confirm", "correct", "add", "drop", "defer")


@verdict_category(VERDICT_SUBSTANTIVE)
def check_requirements_review(q):
    """v1.6.0 Feature D — REQUIREMENTS_REVIEW.md shape, when present.

    Conditional: the interview defect log exists only after an interview
    runs, so absence is silent. When present it must be non-empty and speak
    the shared Wiegers vocabulary (Design §6, the readability rubric) — a
    defect log that invents its own dimension names defeats the "one
    vocabulary, three consumers" design.
    """
    print("[Requirements Review]")
    path = q / "REQUIREMENTS_REVIEW.md"
    if not path.is_file():
        info("REQUIREMENTS_REVIEW.md not present — no interview has run")
        return
    text = _read_text_safe(path)
    if len(text.strip()) < 40:
        fail(
            "REQUIREMENTS_REVIEW.md",
            "is empty or near-empty — an interview that ran should have "
            "recorded its confirms/corrections/adds (Design §6)",
        )
        return
    lowered = text.lower()
    def _mentions(tokens):
        return any(re.search(rf"\b{re.escape(tok)}\b", lowered) for tok in tokens)
    if not _mentions(_REQ_REVIEW_DIMENSIONS):
        fail(
            "REQUIREMENTS_REVIEW.md",
            "names none of the Wiegers dimensions "
            f"({', '.join(_REQ_REVIEW_DIMENSIONS)}) — the defect log must "
            "organize by Wiegers attribute, the same vocabulary the "
            "readability rubric and Council use (Design §6)",
        )
        return
    if not _mentions(_REQ_REVIEW_MOVES):
        warn(
            "REQUIREMENTS_REVIEW.md records no interview move "
            "(confirm/correct/add/drop/defer) — expected at least one "
            "(Design §6; advisory)"
        )
        return
    pass_("REQUIREMENTS_REVIEW.md present, organized by Wiegers attribute")


def check_repo(repo_dir, version_arg, strictness, language=None):
    """Run all checks for one repo. Writes output via pass_/fail_/warn/info.

    v1.5.10 058 (D3): ``language`` is the ``--language`` override threaded
    from ``main`` so the extension check validates the override (not the
    detected plurality) and the disclosure block records it as tested."""
    repo_dir = Path(repo_dir)
    if str(repo_dir) == ".":
        repo_dir = Path.cwd()
    repo_name = repo_dir.name
    q = repo_dir / "quality"

    print("")
    print(f"=== {repo_name} ===")

    check_file_existence(repo_dir, q, strictness)
    bug_count, bug_ids = check_bugs_heading(q)
    tdd_data = check_tdd_sidecar(q, bug_count)
    check_tdd_logs(q, bug_count, bug_ids, tdd_data)
    check_integration_sidecar(q, strictness)
    check_recheck_sidecar(q)
    check_heartbeat_sidecar(q)
    check_use_cases(repo_dir, q, strictness)
    check_test_file_extension(repo_dir, q, language=language)
    # v1.5.7 090s Task A: functional-test content check (anti-no-op).
    check_functional_test_has_assertions(q)
    # v1.5.7 090s Task B: track zero-bug repos for the verdict
    # qualifier (a clean codebase MAY have zero bugs, but so does a
    # hollow run — the qualifier tells the operator to verify the
    # run actually explored before trusting the PASS).
    if bug_count == 0:
        _ZERO_BUG_REPOS.append(repo_name)
    # v1.5.7 090w: capture run provenance (env-detected runner +
    # self-reported model + gate-counted bugs vs self-reported
    # bug_count) for the verdict block. Read-only / never emits
    # FAIL/WARN — provenance is informational.
    _capture_run_provenance(q, repo_name, bug_count)
    check_terminal_gate(q)
    check_mechanical(q)
    check_patches(q, bug_count, bug_ids, strictness)
    check_writeups(q, bug_count)
    check_bugs_md_patches_consistency(q, bug_count, bug_ids)
    check_verdict_shape(q)
    check_no_workspace_dir(q)
    skill_version = check_version_stamps(repo_dir, q)
    # v1.6.0 Feature C: the rendered REQUIREMENTS.md render contract.
    # Runs after check_version_stamps because check 6 (C-7 generator
    # stamp) compares against the skill_version it detects.
    check_render_contract(repo_dir, q, skill_version)
    # v1.6.0 Feature D: the interview's durability artifact and defect log,
    # both conditional (silent unless an interview has run).
    check_operator_confirmations_append_only(q)
    check_requirements_review(q)
    check_cross_run_contamination(repo_dir, q, version_arg, skill_version)
    check_run_metadata(q)
    check_compensation_asymmetry_promotion(q)
    check_v1_5_0_gate_invariants(repo_dir, q)

    # v1.5.10 058 (D2): record the per-repo multi-language disclosure (if
    # >=2 testable languages clear the threshold) for emission after the
    # final RESULT/verdict lines.
    _maybe_record_language_disclosure(repo_dir, repo_name, language)

    print("")


# --- Main ---


def main(argv=None):
    _reset_counters()
    if argv is None:
        argv = sys.argv[1:]

    # v1.5.10 instr 052: dedicated SKILL.md reference-resolves check. Kept as a
    # standalone sub-mode (not wired into the per-repo FAIL flow) so it never
    # perturbs the heavily-pinned gate output contract; CI runs it via the
    # bin/tests regression test, an operator via this flag.
    if "--check-skill-references" in argv:
        candidates = [
            SCRIPT_DIR / ".." / "SKILL.md", SCRIPT_DIR / "SKILL.md",
            Path("SKILL.md"),
            Path(".claude") / "skills" / "quality-playbook" / "SKILL.md",
            Path(".github") / "skills" / "SKILL.md",
            Path(".github") / "skills" / "quality-playbook" / "SKILL.md",
        ]
        skill_md = next((c for c in candidates if c.is_file()), candidates[0])
        problems = validate_skill_reference_resolves(skill_md)
        if problems:
            print("SKILL reference integrity: FAIL (%s)" % skill_md)
            for p in problems:
                print("  - %s" % p)
            return 1
        print("SKILL reference integrity: PASS — all `See references/X.md` "
              "pointers in %s resolve (no missing files, no cycles)" % skill_md)
        return 0

    repo_dirs = []
    version = ""
    check_all = False
    strictness = "benchmark"
    language_override = ""

    expect_version = False
    expect_language = False
    for arg in argv:
        if expect_version:
            version = arg
            expect_version = False
            continue
        if expect_language:
            # v1.5.10 058 (D3): --language <lang> override.
            language_override = arg
            expect_language = False
            continue
        if arg == "--version":
            expect_version = True
        elif arg == "--language":
            expect_language = True
        elif arg == "--all":
            check_all = True
        elif arg == "--benchmark":
            strictness = "benchmark"
        elif arg == "--general":
            strictness = "general"
        else:
            repo_dirs.append(arg)

    # v1.5.10 058 (D3): validate the override against the known testable
    # languages (the _LANG_TO_VALID keys). Unknown / non-testable value ->
    # usage error, exit 2 (distinct from the exit-1 "no repos" usage).
    if language_override and language_override not in _LANG_TO_VALID:
        print(
            f"Usage error: --language {language_override!r} is not a known "
            f"testable language. Choices: {', '.join(sorted(_LANG_TO_VALID))}"
        )
        return 2

    if not version:
        version = detect_skill_version([
            SCRIPT_DIR / ".." / "SKILL.md",
            SCRIPT_DIR / "SKILL.md",
            Path("SKILL.md"),
            Path(".claude") / "skills" / "quality-playbook" / "SKILL.md",
            Path(".github") / "skills" / "SKILL.md",
            Path(".github") / "skills" / "quality-playbook" / "SKILL.md",
        ])

    # Resolve repos
    if check_all:
        for entry in sorted(SCRIPT_DIR.glob(f"*-{version}")):
            if (entry / "quality").is_dir():
                repo_dirs.append(str(entry))
    elif len(repo_dirs) == 1 and repo_dirs[0] == ".":
        repo_dirs = [str(Path.cwd())]
    else:
        resolved = []
        for name in repo_dirs:
            p = Path(name)
            if (p / "quality").is_dir():
                resolved.append(name)
            elif (SCRIPT_DIR / f"{name}-{version}").is_dir():
                resolved.append(str(SCRIPT_DIR / f"{name}-{version}"))
            elif (SCRIPT_DIR / name).is_dir():
                resolved.append(str(SCRIPT_DIR / name))
            else:
                print(f"WARNING: Cannot find repo '{name}'")
        repo_dirs = resolved

    if not repo_dirs:
        print(f"Usage: {sys.argv[0]} [--version V] [--all | repo1 repo2 ... | .]")
        return 1

    print("=== Quality Gate — Post-Run Validation ===")
    print(f"Version:    {version or 'unknown'}")
    print(f"Strictness: {strictness}")
    print(f"Repos:      {len(repo_dirs)}")

    for rd in repo_dirs:
        check_repo(rd, version, strictness, language=language_override or None)

    print("")
    print("===========================================")
    total_line, result_line, exit_code = _compute_final_verdict(
        _FAIL_RECORDS, WARN
    )
    print(total_line)
    print(result_line)
    # v1.5.7 090v: operator verdict-explanation layer. ADDITIVE
    # presentation over the already-computed accumulators
    # (_FAIL_RECORDS / _WARN_RECORDS / _ZERO_BUG_REPOS) — printed
    # AFTER total_line + result_line; never reformats / replaces
    # them and never changes exit_code (load-bearing per the
    # downstream witness contract). Subsumes the standalone 090s
    # zero-bug NOTE by folding the message into the shallow-pass
    # narration; the 090s zero-bug semantics still appear, just
    # inside the new block. Spec:
    # docs/design/QPB_v1.6.x_Verdict_Explanation_Proposal.md.
    _emit_operator_verdict(
        _FAIL_RECORDS, _WARN_RECORDS, _ZERO_BUG_REPOS, exit_code,
        run_provenance=_RUN_PROVENANCE,
    )
    # v1.5.10 058 (D2): multi-language disclosure block(s) — additive,
    # AFTER the load-bearing RESULT/verdict lines and BEFORE the trailing
    # ::QPB:: sentinel (so the sentinel stays the last line parsers anchor
    # on). Never alters RESULT strings or exit_code.
    _emit_language_disclosures(_LANGUAGE_DISCLOSURES)
    # v1.5.7 109: emit the deterministic ::QPB:: gate-result
    # sentinel for the Test Harness status layer (107/108) to
    # parse. ONE line, AFTER the load-bearing total_line /
    # result_line / verdict block — those are byte-identical and
    # the existing verdict parsers (Phase-6 witness,
    # what_just_happened, the harness fact extractors) anchor on
    # their specific line patterns, unaffected by this additive
    # line. For live display only: the harness's authoritative
    # gate result for grading stays facts.rerun_installed_gate.
    _gate_result = (
        "FAIL" if exit_code != 0
        else ("CLEANUP" if "CLEANUP NEEDED" in result_line
              else "PASS")
    )
    _verdict_state = _compute_verdict_state(
        exit_code, _FAIL_RECORDS, _WARN_RECORDS, _ZERO_BUG_REPOS,
    )
    print(_format_gate_sentinel(
        gate_result=_gate_result, verdict_state=_verdict_state,
    ))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
