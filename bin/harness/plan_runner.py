"""QPB Test Harness — simple plan-runner (v1.5.7 099).

The owner-simplified model per the design's ⚠️ SIMPLIFIED RUNNER
MODEL section (2026-05-26): collapse the case/run-plan/SCHEMA
split into ONE input file → ONE self-contained output folder →
ONE summary table. SUPERSEDES the manager+scheduler execution
model FOR THE ONE-SHOT ``run-plan`` WORKFLOW (this module's
domain). The ``qpb_harness manager`` subcommand is a separate,
still-active daemon-queue model with its own concurrency
mechanism (``scheduler.py`` config) — see ``bin/harness/manager.py``'s
docstring for that flow's domain. The two flows DO NOT share
concurrency state: this flow's machine-global per-provider cap
(v1.5.7 125) lives in ``inflight_registry.py``, NOT in the
scheduler.

Input file (`plan.json`):

    {
      "pools": { "claude": 2, "codex": 1, "copilot": 1 },
      "runs": [
        { "description": "Finds + verifies gson dup-key bug",
          "repo": "gson", "ref": "<pre-fix-sha>",
          "runner": "claude", "model": "opus",
          "channel": "pip-local-wheel",
          "expect": { "gate_result": "PASS",
                       "verdict_state": "solid",
                       "no_false_pass": true } },
        ...
      ]
    }

`expect` is a **flat map** `assertion -> value`. A **list value
means "one of"** (membership). Assertion names = the §F closed
vocabulary already enumerated in ``AcceptanceAssertion``.

Output folder layout (timestamped, under a gitignored runs-root):

    <harness-run>/                      ← created per harness run
    ├── SUMMARY.md                      ← the run_playbook-style table
    ├── plan.json                       ← copy of the input
    ├── run-00/
    │   ├── target/                     ← cloned repo + QPB installed
    │   ├── invocation.json
    │   ├── stream.ndjson               ← raw — never committed
    │   ├── facts.json
    │   ├── grading.json
    │   └── summary.md
    ├── run-01/  ...
    └── run-02/  ...

Per-run five steps:
  1. clone ``repo@ref`` into ``run-NN/target/``
  2. install via ``channel`` (clone / pip-local-wheel /
     npm-local-tgz / pip-registry@<v> / npm-registry@<v>)
  3. launch ``runner+model`` (Mode A) via ``runner.launch_run``
  4. extract facts (re-run the run's INSTALLED gate) + grade
     against the flat ``expect``
  5. write receipts + capture per-phase Y/N for the table

Parallelism is gated per-runner via ``scheduler.Scheduler`` keyed
by runner (a custom ``Vendor``-like mapping that respects the
``pools`` header).

**Result semantics (load-bearing)**: ``result`` is MET when every
``expect`` assertion matches the extracted facts — so a run whose
``expect`` says ``gate_result:FAIL`` is MET *when the gate fails*.
The ``gate`` column shows QPB's verdict; the ``result`` column
shows whether QPB behaved as predicted. A run that didn't
terminate COMPLETED (FAILED/TIMED_OUT/BLOCKED/ABORTED_PREP)
grades ``N/A``, never silently MET.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import (
    FIRST_COMPLETED, Future, ThreadPoolExecutor, wait)
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from bin.harness.grade_acceptance import (
    _FACT_EXTRACTORS,
    AcceptanceGrading,
    AssertionResult,
)
from bin.harness.schema import (
    AcceptanceAssertion,
    InstallChannel,
    Mode,
    RunAxes,
    Runner,
    RunFacts,
    TerminalState,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PlanError(ValueError):
    """The plan.json document violates the simplified-runner
    contract. Carries the offending field path."""


class BuildError(RuntimeError):
    """v1.5.7 101: a required local artifact (wheel/tgz) build
    failed (or an override path was missing/unreadable). The
    plan-runner aborts the harness run cleanly when this is
    raised — no runs are launched against a failed/missing
    build."""


# ---------------------------------------------------------------------------
# v1.5.7 106: launch-mode constants
# ---------------------------------------------------------------------------


# The Mode A full-pipeline launch prompt. Pre-106, the harness
# sent a bare "Run the Quality Playbook on this project." — that
# does NOT match SKILL.md:413's "run all phases" trigger, so the
# agent did the DEFAULT single-phase-at-a-time behavior
# (SKILL.md:403), completed Phase 1, and ended its turn waiting
# for a human "continue." Result on the first live 4-repo run:
# 0/4 MET — gson stopped after Phase 1; keto stopped after Phase
# 2 ("The exact prompt is: `Run quality playbook phase 3.`").
# This prompt explicitly hits the all-phases trigger, scopes it
# unattended, and excludes the 4 iteration strategies that
# SKILL.md:141 chains onto a bare full run (the acceptance
# harness wants phases 1-6 + gate only).
_MODE_A_FULL_RUN_PROMPT = (
    "Run the full Quality Playbook pipeline on this project: "
    "run all phases (1 through 6) sequentially in a single "
    "session and then run the quality gate. Do not stop "
    "between phases and do not wait for confirmation — this "
    "is an unattended run. Do not run the iteration "
    "strategies (gap / unfiltered / parity / adversarial); "
    "stop after the Phase 6 gate."
)

# v1.5.7 106: default per-run max-duration raised from 1800s
# (30 min) to 7200s (120 min). A full 6-phase Mode A run is
# substantially longer than the 2 phases that timed express out
# at 1800s. Operators can override per-run via the optional
# ``max_duration_s`` plan field; this constant is the default
# when the field is absent.
_DEFAULT_MAX_DURATION_S = 7200.0


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PlanRun:
    """One run in the plan. The array INDEX is the identity
    (`description` is the human justification; no `id`)."""
    index: int
    description: str
    repo: str
    ref: str
    runner: Runner
    model: str
    channel: InstallChannel
    install_version: "Optional[str]" = None
    prep: str = "acceptance"           # acceptance | security
    docs: str = "gather"               # path or "gather" (no-op)
    expect: "dict[str, Any]" = field(default_factory=dict)
    # v1.5.7 100: extra argv tokens passed VERBATIM to the runner
    # CLI at the runner-appropriate position (the harness does
    # NOT interpret them). Example for codex low thinking:
    # ``["-c", "model_reasoning_effort=\"low\""]``. Absent/empty
    # ⇒ no extra tokens.
    parameters: "list[str]" = field(default_factory=list)
    # v1.5.7 106: per-run launch mode. "A" (default) ⇒ the
    # AI-CLI agent reads SKILL.md + drives phases itself, with
    # ``parameters`` routed to the per-runner CLI argv. "B" ⇒
    # ``bin/run_playbook`` drives the phases against the
    # target's channel-installed skill, with ``parameters``
    # routed to run_playbook's argv (so `["--phase", "3"]`
    # selects Phase 3 in Mode B).
    mode: Mode = Mode.A
    # v1.5.7 106: optional per-run max-duration override
    # (seconds). When None, ``_execute_one_run_production`` uses
    # ``_DEFAULT_MAX_DURATION_S`` (7200s = 120 min) — the value
    # raised from 1800s so a full Mode A 6-phase pipeline can
    # finish unattended.
    max_duration_s: "Optional[float]" = None
    # v1.5.7 107: optional per-run shared workspace. When set,
    # the run targets ``workspace_root`` instead of cloning
    # into ``run-NN/target``. First run in a shared sequence
    # preps the workspace (clone + install); subsequent runs
    # reuse it as-is (no re-clone, no re-install, no wipe of
    # the existing ``quality/`` tree — phase N can read phase
    # N-1's artifacts). The run's own receipts still write
    # under ``run-NN/``; only the TARGET is shared.
    workspace_root: "Optional[str]" = None
    # v1.5.7 106 (fix): optional per-run Mode A launch prompt
    # override. When None, ``_execute_one_run_production`` uses
    # ``_MODE_A_FULL_RUN_PROMPT`` (the default that drives
    # phases 1-6 + gate, unattended, no iteration strategies).
    # When set, the override REPLACES the default verbatim —
    # the operator can drive a single phase ("Run quality
    # playbook phase 2."), test odd prompts, or A/B-test
    # phrasings without changing the constant. Mode B is
    # unaffected: run_playbook always builds its own phase
    # prompt sequence and the per-run prompt does not reach the
    # subprocess (Mode B's LaunchSpec.prompt is a sentinel
    # string that's never consumed).
    prompt: "Optional[str]" = None
    # v1.5.7 138: optional per-run override for the install_skill
    # prep timeout (seconds). When None, the prep step uses
    # install_skill_channel's 300s default — fine for
    # pip-local-wheel, but codex's npm-local-tgz on a cold cache
    # exceeds it (npm fetch + extract + dependency resolve). When
    # set, overrides the default for THIS run only.
    prep_timeout_s: "Optional[float]" = None


@dataclass
class Plan:
    """The parsed plan file."""
    pools: "dict[str, int]"
    runs: "list[PlanRun]"


@dataclass
class RunOutcome:
    """Per-run aggregate after execution. Feeds SUMMARY.md."""
    index: int
    description: str
    repo: str
    runner: str
    model: str
    phase_yn: "dict[str, str]"   # "P0".."P6" → "Y"/"N"/"-"
    gate_verdict: str            # "PASSED" / "FAILED" / "CLEANUP" / "N/A"
    result: str                  # "MET" / "NOT-MET" / "N/A"
    terminal_state: str          # the SCHEMA.md §6 terminal
    grading: "Optional[dict]" = None
    facts: "Optional[dict]" = None


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


_VALID_PREP_VALUES = {"acceptance", "security"}


def _parse_run(idx: int, raw: dict) -> PlanRun:
    """Parse one run dict per the simplified plan format."""
    if not isinstance(raw, dict):
        raise PlanError(
            f"runs[{idx}]: expected dict; got "
            f"{type(raw).__name__}"
        )
    for required in ("description", "repo", "ref", "runner",
                       "model", "channel"):
        if required not in raw:
            raise PlanError(
                f"runs[{idx}]: missing required field {required!r}"
            )
    try:
        runner = Runner(raw["runner"])
    except ValueError:
        raise PlanError(
            f"runs[{idx}].runner: {raw['runner']!r} not in "
            f"{[r.value for r in Runner]}"
        )
    # Channel may carry the @<version> suffix per design §D.
    channel_raw = raw["channel"]
    install_version: "Optional[str]" = None
    if "@" in channel_raw:
        bare, _at, suffix = channel_raw.partition("@")
        install_version = suffix
        channel_str = bare
    else:
        channel_str = channel_raw
    try:
        channel = InstallChannel(channel_str)
    except ValueError:
        raise PlanError(
            f"runs[{idx}].channel: {channel_raw!r} not in "
            f"{[c.value for c in InstallChannel]}"
        )
    prep = raw.get("prep", "acceptance")
    if prep not in _VALID_PREP_VALUES:
        raise PlanError(
            f"runs[{idx}].prep: {prep!r} not in "
            f"{sorted(_VALID_PREP_VALUES)}"
        )
    expect = raw.get("expect", {})
    if not isinstance(expect, dict):
        raise PlanError(
            f"runs[{idx}].expect: must be a flat map "
            f"assertion->value (NOT a list of triples); got "
            f"{type(expect).__name__}"
        )
    # Validate every `expect` key is in the §F vocabulary.
    valid_assertions = {a.value for a in AcceptanceAssertion}
    for key in expect:
        if key not in valid_assertions:
            raise PlanError(
                f"runs[{idx}].expect: unknown assertion "
                f"{key!r}; legal names are the §F vocabulary "
                f"{sorted(valid_assertions)}"
            )
    # v1.5.7 100: optional per-run `parameters` (array of argv
    # tokens passed verbatim to the runner CLI). Accept either a
    # JSON array of strings (the documented form) or a single
    # string which is shlex.split into tokens (the optional nicety).
    parameters_raw = raw.get("parameters", [])
    parameters: list[str]
    if isinstance(parameters_raw, str):
        parameters = shlex.split(parameters_raw)
    elif isinstance(parameters_raw, list):
        for j, tok in enumerate(parameters_raw):
            if not isinstance(tok, str):
                raise PlanError(
                    f"runs[{idx}].parameters[{j}]: must be a "
                    f"string (argv token); got "
                    f"{type(tok).__name__}"
                )
        parameters = list(parameters_raw)
    else:
        raise PlanError(
            f"runs[{idx}].parameters: must be a list of argv "
            f"tokens (strings) or a single string (shlex-split); "
            f"got {type(parameters_raw).__name__}"
        )
    # v1.5.7 106: optional per-run `mode` ("A" default; "B" ⇒
    # run_playbook drives the phases).
    mode_raw = raw.get("mode", "A")
    if mode_raw not in ("A", "B"):
        raise PlanError(
            f"runs[{idx}].mode: must be 'A' or 'B'; got "
            f"{mode_raw!r}"
        )
    mode_value = Mode.A if mode_raw == "A" else Mode.B
    # v1.5.7 106: optional per-run `max_duration_s` override.
    max_duration_raw = raw.get("max_duration_s", None)
    max_duration_value: "Optional[float]"
    if max_duration_raw is None:
        max_duration_value = None
    elif isinstance(max_duration_raw, (int, float)):
        if max_duration_raw <= 0:
            raise PlanError(
                f"runs[{idx}].max_duration_s: must be > 0; got "
                f"{max_duration_raw!r}"
            )
        max_duration_value = float(max_duration_raw)
    else:
        raise PlanError(
            f"runs[{idx}].max_duration_s: must be a positive "
            f"number or absent; got "
            f"{type(max_duration_raw).__name__}"
        )
    # v1.5.7 106 (fix): optional per-run Mode A launch prompt
    # override. Absent ⇒ default _MODE_A_FULL_RUN_PROMPT.
    # Present + non-string OR empty/whitespace ⇒ PlanError.
    prompt_raw = raw.get("prompt", None)
    prompt_value: "Optional[str]"
    if prompt_raw is None:
        prompt_value = None
    elif isinstance(prompt_raw, str):
        if not prompt_raw.strip():
            raise PlanError(
                f"runs[{idx}].prompt: empty/whitespace string "
                f"is not a valid override; omit the field to "
                f"use the default prompt"
            )
        prompt_value = prompt_raw
    else:
        raise PlanError(
            f"runs[{idx}].prompt: must be a string or absent; "
            f"got {type(prompt_raw).__name__}"
        )
    # v1.5.7 138: optional per-run `prep_timeout_s` override for
    # the install step. Same shape/validation as max_duration_s.
    prep_timeout_raw = raw.get("prep_timeout_s", None)
    prep_timeout_value: "Optional[float]"
    if prep_timeout_raw is None:
        prep_timeout_value = None
    elif isinstance(prep_timeout_raw, (int, float)):
        if prep_timeout_raw <= 0:
            raise PlanError(
                f"runs[{idx}].prep_timeout_s: must be > 0; got "
                f"{prep_timeout_raw!r}"
            )
        prep_timeout_value = float(prep_timeout_raw)
    else:
        raise PlanError(
            f"runs[{idx}].prep_timeout_s: must be a positive "
            f"number or absent; got "
            f"{type(prep_timeout_raw).__name__}"
        )
    # v1.5.7 107: optional per-run `workspace_root` (path-as-
    # string). Absent ⇒ standard `run-NN/target` behavior.
    # Present ⇒ first run clones+installs into it; later runs
    # reuse without clobbering.
    workspace_root_raw = raw.get("workspace_root", None)
    workspace_root_value: "Optional[str]"
    if workspace_root_raw is None:
        workspace_root_value = None
    elif isinstance(workspace_root_raw, str):
        if not workspace_root_raw.strip():
            raise PlanError(
                f"runs[{idx}].workspace_root: empty string is "
                f"not a valid path; omit the field or supply "
                f"a real path"
            )
        workspace_root_value = workspace_root_raw
    else:
        raise PlanError(
            f"runs[{idx}].workspace_root: must be a path string "
            f"or absent; got "
            f"{type(workspace_root_raw).__name__}"
        )
    return PlanRun(
        index=idx,
        description=raw["description"],
        repo=raw["repo"],
        ref=raw["ref"],
        runner=runner,
        model=raw["model"],
        channel=channel,
        install_version=install_version,
        prep=prep,
        docs=raw.get("docs", "gather"),
        expect=expect,
        parameters=parameters,
        mode=mode_value,
        max_duration_s=max_duration_value,
        workspace_root=workspace_root_value,
        prompt=prompt_value,
        prep_timeout_s=prep_timeout_value,
    )


def parse_plan(raw: dict) -> Plan:
    """Parse a plan.json document into a ``Plan``. The pools
    header is optional (default: empty → no per-runner cap, only
    the global cap)."""
    if not isinstance(raw, dict):
        raise PlanError(
            f"plan: top-level must be a dict; got "
            f"{type(raw).__name__}"
        )
    pools_raw = raw.get("pools", {})
    if not isinstance(pools_raw, dict):
        raise PlanError(
            f"plan.pools: must be a dict; got "
            f"{type(pools_raw).__name__}"
        )
    pools: dict[str, int] = {}
    for k, v in pools_raw.items():
        if not isinstance(v, int) or v < 0:
            raise PlanError(
                f"plan.pools.{k}: must be a non-negative int; "
                f"got {v!r}"
            )
        pools[k] = v
    runs_raw = raw.get("runs")
    if not isinstance(runs_raw, list):
        raise PlanError(
            "plan.runs: must be a list of run dicts"
        )
    runs = [_parse_run(i, r) for i, r in enumerate(runs_raw)]
    return Plan(pools=pools, runs=runs)


def load_plan(path: Path) -> Plan:
    """Read + parse a plan file."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return parse_plan(raw)


# ---------------------------------------------------------------------------
# Grading the flat `expect` map
# ---------------------------------------------------------------------------


def grade_expect(plan_run: PlanRun, facts: RunFacts,
                  axes: RunAxes) -> AcceptanceGrading:
    """Grade the flat `expect` map against the extracted facts.

    Semantics: an entry ``assertion: value`` means "the observed
    fact for `assertion` must equal `value`". A LIST value means
    "the observed fact must be IN the list" (membership).

    Reuses the §F fact-extractors from grade_acceptance.py — same
    functions, different entry shape.
    """
    grading = AcceptanceGrading(
        case_id=f"run-{plan_run.index:02d}",
        run_id=str(plan_run.index),
        case_type="acceptance",
    )
    for assertion, expected in plan_run.expect.items():
        extractor = _FACT_EXTRACTORS.get(assertion)
        if extractor is None:
            grading.assertions.append(AssertionResult(
                assertion=assertion,
                comparator="==",
                expected=expected,
                observed=None,
                passed=False,
                detail=(
                    f"assertion {assertion!r} not in §F "
                    f"vocabulary"
                ),
            ))
            continue
        observed = extractor(facts, axes)
        if isinstance(expected, list):
            passed = observed in expected
            comp = "in"
        else:
            passed = observed == expected
            comp = "=="
        grading.assertions.append(AssertionResult(
            assertion=assertion,
            comparator=comp,
            expected=expected,
            observed=observed,
            passed=passed,
            detail=(
                f"{assertion} = {observed!r} "
                f"({comp} {expected!r}) — "
                f"{'PASS' if passed else 'FAIL'}"
            ),
        ))
    grading.n_total = len(grading.assertions)
    grading.n_passed = sum(1 for a in grading.assertions if a.passed)
    grading.n_failed = grading.n_total - grading.n_passed
    grading.verdict = (
        "MET" if grading.n_failed == 0 else "NOT-MET"
    )
    return grading


# ---------------------------------------------------------------------------
# Per-phase Y/N capture
# ---------------------------------------------------------------------------


# Phase markers in the transcript / artifact tree that signal a
# phase ran. Best-effort — the table column shows Y/N/- per phase.
_PHASE_MARKER_RES: "dict[str, list[re.Pattern]]" = {
    "P0": [re.compile(r"event=validation_complete\s+status="),
           re.compile(r"phase[ _]0", re.IGNORECASE)],
    "P1": [re.compile(r"EXPLORATION\.md|phase[ _]1",
                       re.IGNORECASE)],
    "P2": [re.compile(r"REQUIREMENTS\.md|phase[ _]2",
                       re.IGNORECASE)],
    "P3": [re.compile(r"RUN_CODE_REVIEW\.md|phase[ _]3",
                       re.IGNORECASE)],
    "P4": [re.compile(r"RUN_SPEC_AUDIT\.md|phase[ _]4",
                       re.IGNORECASE)],
    "P5": [re.compile(r"phase[ _]?5[ _]?env\.log|"
                        r"RUN_TDD_TESTS\.md|phase[ _]5",
                       re.IGNORECASE)],
    "P6": [re.compile(r"phase[ _]6|COMPLETENESS_REPORT\.md",
                       re.IGNORECASE)],
}


def capture_phase_yn(transcript: str,
                      quality_dir: "Optional[Path]" = None
                      ) -> "dict[str, str]":
    """Best-effort per-phase Y/N from the transcript + (optional)
    artifact-presence check on the run's quality/ tree. A phase
    is Y if EITHER source signals it; N if neither does AND the
    transcript looks complete; "-" if the run didn't get that
    far (no transcript content past that point).
    """
    # v1.5.7 168: delegate artifact-presence lookup to the canonical
    # phase_artifacts helper. Pre-168 the inline map here mis-mapped
    # Phase-2 Generate outputs (RUN_CODE_REVIEW.md, RUN_SPEC_AUDIT.md,
    # RUN_TDD_TESTS.md, COMPLETENESS_REPORT.md) to P3-P6, so a run
    # that finished only Phase 2 was reported as P3-P6=Y (BUG-007).
    # The helper encodes the canonical Phase-3 prerequisite gate from
    # run_playbook.py:1522-1530 as the single source of truth shared
    # with status.py::_infer_phase_from_artifacts (BUG-004).
    from bin.harness import phase_artifacts as _pa
    artifact_grid = _pa.phase_yn_grid_artifact(quality_dir)
    out: dict[str, str] = {}
    transcript_lower = transcript or ""
    for phase, patterns in _PHASE_MARKER_RES.items():
        hit = any(p.search(transcript_lower) for p in patterns)
        if not hit:
            # _PHASE_MARKER_RES keys are "P1".."P6"; the helper
            # uses int keys. Convert; non-conformant keys (none
            # at present) fall through with hit=False.
            try:
                phase_num = int(phase[1:])
            except (ValueError, IndexError):
                phase_num = -1
            if artifact_grid.get(phase_num):
                hit = True
        out[phase] = "Y" if hit else "N"
    return out


# ---------------------------------------------------------------------------
# v1.5.7 101: local-artifact autobuild (pip wheel / npm tgz)
# ---------------------------------------------------------------------------


@dataclass
class BuilderHooks:
    """v1.5.7 101: injection point for the wheel/tgz builders.

    Tests pass mock callables (no real `python -m build` /
    `npm pack` — those are slow and out-of-scope for unit tests).
    v1.5.7 102: when no builder is injected, the default helpers
    ``_default_build_wheel`` / ``_default_build_tgz`` SHELL OUT
    to the live build commands per design §D's pre-publish lane:
      * wheel: ``python3 bin/build_channel_package.py --stage`` +
        ``python3 -m build --wheel --outdir <artifacts>``;
      * tgz: ``npm pack --pack-destination <artifacts>``.
    Tests for the default code path (102) patch ``subprocess.run``
    so the live builds don't actually run in unit tests.

    Each callable accepts the harness-run's ``artifacts`` dir and
    returns the path of the built file (which must live inside
    that dir). Non-zero exit ⇒ raise with the captured stderr;
    ``build_artifacts`` wraps that in ``BuildError`` and aborts
    the harness run cleanly.
    """
    build_wheel: "Optional[Callable[[Path], Path]]" = None
    build_tgz: "Optional[Callable[[Path], Path]]" = None


def _sha256_of(path: Path) -> str:
    """SHA-256 of a file, streamed in 64 KiB chunks so large
    artifacts (multi-MB wheels) don't blow memory."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _repo_root() -> Path:
    """The QPB clone root — the cwd from which
    ``build_channel_package.py``, ``python -m build``, and
    ``npm pack`` all run. ``plan_runner.py`` lives at
    ``<root>/bin/harness/plan_runner.py``."""
    return Path(__file__).resolve().parents[2]


def _run_build_step(cmd: "list[str]", *, cwd: Path,
                     step_label: str) -> "subprocess.CompletedProcess":
    """Run one build step and raise with captured stderr on
    non-zero. The caller catches and re-raises as the right
    `<kind> build failed: …` so the BuildError message points
    at the actual subprocess output."""
    proc = subprocess.run(
        cmd, cwd=str(cwd),
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"{step_label} exited {proc.returncode}: "
            f"{(proc.stderr or proc.stdout or '').strip()[-1200:]}"
        )
    return proc


def _default_build_wheel(artifacts_dir: Path) -> Path:
    """v1.5.7 102: real wheel build. Stages the QPB bundle via
    ``bin/build_channel_package.py --stage`` (matches the design
    §D pre-publish lane), then runs ``python -m build --wheel
    --outdir <artifacts_dir>`` from the clone root. Returns the
    produced ``.whl`` path inside ``artifacts_dir``.

    Subprocess failures raise RuntimeError with the captured
    stderr; ``build_artifacts`` wraps that into ``BuildError``
    so the caller aborts the harness run cleanly.
    """
    repo_root = _repo_root()
    _run_build_step(
        [sys.executable, "bin/build_channel_package.py", "--stage"],
        cwd=repo_root, step_label="build_channel_package --stage",
    )
    _run_build_step(
        [sys.executable, "-m", "build", "--wheel",
         "--outdir", str(artifacts_dir)],
        cwd=repo_root, step_label="python -m build --wheel",
    )
    wheels = sorted(Path(artifacts_dir).glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(
            f"expected exactly one .whl in {artifacts_dir} after "
            f"python -m build; found {len(wheels)}: "
            f"{[w.name for w in wheels]}"
        )
    return wheels[0]


def _default_build_tgz(artifacts_dir: Path) -> Path:
    """v1.5.7 102: real tgz build. Runs ``npm pack
    --pack-destination <artifacts_dir>`` from the clone root.
    npm pack's ``prepack`` hook stages the npm bundle if the
    package.json wires it; the QPB repo's top-level package.json
    is what npm operates on.

    Returns the produced ``.tgz`` path inside ``artifacts_dir``.
    Subprocess failure raises RuntimeError with the captured
    stderr.
    """
    repo_root = _repo_root()
    _run_build_step(
        ["npm", "pack", "--pack-destination", str(artifacts_dir)],
        cwd=repo_root, step_label="npm pack",
    )
    tarballs = sorted(Path(artifacts_dir).glob("*.tgz"))
    if len(tarballs) != 1:
        raise RuntimeError(
            f"expected exactly one .tgz in {artifacts_dir} after "
            f"npm pack; found {len(tarballs)}: "
            f"{[t.name for t in tarballs]}"
        )
    return tarballs[0]


def _required_local_channels(plan: Plan) -> "set[InstallChannel]":
    """Scan the plan's run channels for those requiring a
    locally-built artifact. ``pip-local-wheel`` ⇒ wheel;
    ``npm-local-tgz`` ⇒ tgz. Clone + registry channels need no
    build."""
    needed: set[InstallChannel] = set()
    for r in plan.runs:
        if r.channel == InstallChannel.PIP_LOCAL_WHEEL:
            needed.add(InstallChannel.PIP_LOCAL_WHEEL)
        elif r.channel == InstallChannel.NPM_LOCAL_TGZ:
            needed.add(InstallChannel.NPM_LOCAL_TGZ)
    return needed


def build_artifacts(harness_run_dir: Path, plan: Plan, *,
                     builder: "Optional[BuilderHooks]" = None,
                     wheel_override: "Optional[Path]" = None,
                     tgz_override: "Optional[Path]" = None,
                     ) -> "dict[InstallChannel, dict]":
    """v1.5.7 101: build (or copy from override) the local
    artifacts the plan needs, into ``<harness-run>/artifacts/``.

    Returns ``{channel: {path, filename, sha256}}`` for each
    artifact actually placed. Channels that no run needs are
    absent. If the plan needs no local artifacts at all, returns
    an empty dict and writes no manifest.

    Build-step contract:
      * One build per artifact per harness run (the bundle is
        identical across runs at one HEAD — there's no point
        rebuilding per run).
      * Overrides (``wheel_override`` / ``tgz_override``) are
        copied into the artifacts dir verbatim, then the build
        is skipped — so reproducibility is preserved (the
        harness-run folder still contains the exact artifact
        each run installed from).
      * On ANY failure (default-builder NotImplementedError, an
        override path that doesn't exist, a fake builder raising
        for the build-failure test) → raise BuildError so the
        caller aborts the harness run without launching any
        runs.

    Writes ``<artifacts>/manifest.json`` with the full provenance
    so the operator can audit which exact artifacts a harness
    run installed from.
    """
    needed = _required_local_channels(plan)
    if not needed:
        return {}
    builder = builder or BuilderHooks()
    artifacts_dir = harness_run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    out: dict[InstallChannel, dict] = {}

    def _resolve_artifact(
        channel: InstallChannel,
        override: "Optional[Path]",
        build_fn: "Optional[Callable[[Path], Path]]",
        default_fn: "Callable[[Path], Path]",
        kind: str,
    ) -> Path:
        if override is not None:
            src = Path(override).expanduser().resolve()
            if not src.is_file():
                raise BuildError(
                    f"{kind} override not found: {src}"
                )
            dst = artifacts_dir / src.name
            shutil.copy2(src, dst)
            return dst
        try:
            built = (build_fn or default_fn)(artifacts_dir)
        except BuildError:
            raise
        except Exception as exc:
            raise BuildError(
                f"{kind} build failed: {exc}"
            ) from exc
        built = Path(built).resolve()
        if not str(built).startswith(
                str(artifacts_dir.resolve())):
            raise BuildError(
                f"{kind} build returned path outside the "
                f"artifacts dir: {built}"
            )
        if not built.is_file():
            raise BuildError(
                f"{kind} build returned a non-existent path: "
                f"{built}"
            )
        return built

    if InstallChannel.PIP_LOCAL_WHEEL in needed:
        whl = _resolve_artifact(
            InstallChannel.PIP_LOCAL_WHEEL,
            wheel_override,
            builder.build_wheel,
            _default_build_wheel,
            "wheel",
        )
        out[InstallChannel.PIP_LOCAL_WHEEL] = {
            "path": str(whl),
            "filename": whl.name,
            "sha256": _sha256_of(whl),
        }

    if InstallChannel.NPM_LOCAL_TGZ in needed:
        tgz = _resolve_artifact(
            InstallChannel.NPM_LOCAL_TGZ,
            tgz_override,
            builder.build_tgz,
            _default_build_tgz,
            "tgz",
        )
        out[InstallChannel.NPM_LOCAL_TGZ] = {
            "path": str(tgz),
            "filename": tgz.name,
            "sha256": _sha256_of(tgz),
        }

    # Manifest for operator-facing audit + production-path's
    # invocation.json absorption.
    (artifacts_dir / "manifest.json").write_text(
        json.dumps({
            channel.value: info for channel, info in out.items()
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    return out


# ---------------------------------------------------------------------------
# Per-runner concurrency gate (pools-aware semaphore)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# v1.5.7 104: progress logging (operator visibility, no TUI)
# ---------------------------------------------------------------------------


class _ProgressLog:
    """v1.5.7 104: thread-safe step-level progress logger.

    Writes each line to THREE sinks:
      * ``stderr`` — live operator visibility (the operator sees
        the AI-CLIs running but the harness itself was silent
        before 104).
      * ``<harness-run>/harness.log`` — one line per state
        transition across ALL runs in the harness-run.
      * ``<run-dir>/run.log`` — same line, scoped to one run
        (so an operator inspecting `run-NN/` sees only that
        run's transitions).

    Format: ``[HH:MM:SS] [<tag>] <message>``. The tag is either
    ``harness-run`` for harness-level events or
    ``run-NN <repo-tail> <runner>/<model>`` for per-run events.

    Outcomes / SUMMARY are NOT affected by this — it's purely
    additive operator-facing output. Concurrent run threads
    serialize through ``_lock`` so log lines don't interleave.
    """

    def __init__(self, harness_run_dir: Path) -> None:
        self.harness_log = harness_run_dir / "harness.log"
        self._lock = threading.Lock()
        self.harness_log.touch()

    def log(self, message: str, *,
             run_dir: "Optional[Path]" = None,
             tag: str = "harness-run") -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        line = f"[{ts}] [{tag}] {message}"
        with self._lock:
            print(line, file=sys.stderr, flush=True)
            with open(self.harness_log, "a",
                       encoding="utf-8") as f:
                f.write(line + "\n")
            if run_dir is not None:
                run_log = run_dir / "run.log"
                with open(run_log, "a", encoding="utf-8") as f:
                    f.write(line + "\n")


def _run_tag(plan_run: PlanRun) -> str:
    """Compact per-run tag for log lines:
    ``run-NN <repo-tail> <runner>/<model>``. The repo tail is the
    last path segment of the URL (e.g. ``gson`` / ``chi`` /
    ``keto``)."""
    repo_tail = plan_run.repo.rstrip("/").split("/")[-1] or plan_run.repo
    return (f"run-{plan_run.index:02d} {repo_tail} "
            f"{plan_run.runner.value}/{plan_run.model}")


# ---------------------------------------------------------------------------
# Per-runner concurrency gate (pools-aware semaphore)
# ---------------------------------------------------------------------------


class _PoolGate:
    """A per-runner semaphore set. Each `acquire(runner)` blocks
    until that runner's pool has capacity; `release(runner)`
    returns capacity. Different runners are independent.

    Simpler than reusing `scheduler.Scheduler` directly — the
    plan-runner doesn't need cooldown, queue snapshots, or the
    pure-state-machine shape; it just needs "wait until my
    runner has slot".
    """

    def __init__(self, pools: "dict[str, int]") -> None:
        self._sems: dict[str, threading.Semaphore] = {
            r: threading.Semaphore(max(1, n))
            for r, n in pools.items()
        }
        self._lock = threading.Lock()

    def acquire(self, runner: str) -> None:
        with self._lock:
            sem = self._sems.get(runner)
            if sem is None:
                sem = threading.Semaphore(1)
                self._sems[runner] = sem
        sem.acquire()

    def release(self, runner: str) -> None:
        sem = self._sems.get(runner)
        if sem is not None:
            sem.release()


# ---------------------------------------------------------------------------
# The plan runner
# ---------------------------------------------------------------------------


def _utc_now_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _is_workspace_prepared(target_dir: Path) -> bool:
    """v1.5.7 107: is ``target_dir`` already a prepared QPB
    workspace? Reuses ``benchmark_lib.find_installed_skill`` —
    the canonical detector that searches the 10 install
    layouts for QPB's SKILL.md. Returns False when the dir
    doesn't exist OR isn't a directory OR contains no
    QPB-installed skill.

    The 105-hardened ``clone_worktree`` raises if dest exists,
    so 107's shared-workspace logic checks here FIRST and
    skips the clone/install when the workspace is already
    prepared (later runs in a sequential phase-by-phase
    sequence reuse the workspace verbatim — no clobbering of
    the prior phases' ``quality/`` tree).
    """
    if not target_dir.exists() or not target_dir.is_dir():
        return False
    try:
        from bin import benchmark_lib as _bl
    except ImportError:
        return False
    return _bl.find_installed_skill(target_dir) is not None


def _resolve_workspace_sha(target_dir: Path) -> str:
    """v1.5.7 107: when reusing an already-prepared workspace,
    we still want ``invocation.json.target_sha`` populated so
    the receipt is auditable. ``git rev-parse HEAD`` against
    the workspace; empty string if the workspace isn't a git
    checkout (e.g. operator pointed at a non-git tree)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(target_dir),
            capture_output=True, text=True, check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, FileNotFoundError):
        return ""


@dataclass
class PlanRunnerHooks:
    """Test-injection point: a fake/echo runner + stub gate +
    canned facts. When None (production), the real harness
    modules (`prepare`/`runner`/`facts`/`grade_acceptance`) are
    used. Each hook receives the PlanRun and returns the
    appropriate object.
    """
    fake_run: "Optional[Callable[[PlanRun, Path], dict]]" = None


def _gate_verdict_str(terminal: TerminalState,
                       facts: "Optional[RunFacts]") -> str:
    """Map terminal_state + gate facts → the gate column label
    for SUMMARY.md."""
    if terminal != TerminalState.COMPLETED:
        return "N/A"
    if facts is None:
        return "N/A"
    return {
        "PASS": "PASSED",
        "CLEANUP": "CLEANUP",
        "FAIL": "FAILED",
    }.get(facts.gate.gate_result.value, "?")


def _execute_one_run(plan_run: PlanRun, harness_run_dir: Path,
                      hooks: PlanRunnerHooks,
                      artifact_map: "Optional[dict[InstallChannel, dict]]" = None,
                      log: "Optional[_ProgressLog]" = None,
                      ) -> RunOutcome:
    """Execute one run end-to-end. Returns the RunOutcome that
    drives the SUMMARY.md row.

    v1.5.7 101: ``artifact_map`` carries the harness-run's local
    artifacts (``{channel: {path, filename, sha256}}``). When the
    run's channel matches an entry, the per-run install would
    use that artifact and the provenance is captured to
    ``<run-dir>/artifact_used.json`` (which the production
    invocation.json absorbs once the live launch path is wired).
    Tests assert against this receipt to verify per-run wiring.

    v1.5.7 104: ``log`` is an optional ``_ProgressLog`` for
    step-level operator visibility (stderr + harness.log +
    per-run run.log). Outcomes are unchanged with or without
    logging.
    """
    run_dir = harness_run_dir / f"run-{plan_run.index:02d}"
    run_dir.mkdir(parents=True, exist_ok=True)
    target_dir = run_dir / "target"
    tag = _run_tag(plan_run)

    # v1.5.7 101: per-run artifact provenance. Even on the fake
    # path the receipt is written so tests can verify the wiring
    # contract; on the production path the same data is absorbed
    # into invocation.json (Task B).
    artifact_map = artifact_map or {}
    local_artifact_info = artifact_map.get(plan_run.channel)
    if local_artifact_info is not None:
        (run_dir / "artifact_used.json").write_text(
            json.dumps({
                "channel": plan_run.channel.value,
                **local_artifact_info,
            }, indent=2) + "\n",
            encoding="utf-8",
        )

    # Test-injection path: a fake runner short-circuits the
    # clone+install+launch+facts cycle by returning a synthetic
    # result dict. This is what the tests use.
    if hooks.fake_run is not None:
        if log is not None:
            log.log("fake_run (test fast-path)",
                     run_dir=run_dir, tag=tag)
        try:
            result = hooks.fake_run(plan_run, run_dir)
        except Exception as exc:
            return RunOutcome(
                index=plan_run.index,
                description=plan_run.description,
                repo=plan_run.repo,
                runner=plan_run.runner.value,
                model=plan_run.model,
                phase_yn={f"P{i}": "-" for i in range(7)},
                gate_verdict="N/A",
                result="N/A",
                terminal_state=TerminalState.ABORTED_PREP.value,
                grading={"error": str(exc)},
            )
        # Result dict shape:
        #   terminal_state: TerminalState value
        #   facts: RunFacts | None
        #   transcript: str | ""
        #   axes: RunAxes
        terminal = TerminalState(result.get(
            "terminal_state", TerminalState.COMPLETED.value,
        ))
        facts = result.get("facts")
        transcript = result.get("transcript", "")
        axes = result["axes"]
        phase_yn = capture_phase_yn(transcript, None)
        if terminal == TerminalState.COMPLETED and facts is not None:
            grading = grade_expect(plan_run, facts, axes)
            result_label = grading.verdict  # MET / NOT-MET
        else:
            grading = None
            result_label = "N/A"
            # Phases beyond the failure point read "-".
            if terminal != TerminalState.COMPLETED:
                for p in ("P3", "P4", "P5", "P6"):
                    if phase_yn.get(p) == "N":
                        phase_yn[p] = "-"
        # Persist receipts.
        if facts is not None:
            from bin.harness.schema import run_facts_to_json
            (run_dir / "facts.json").write_text(
                json.dumps(run_facts_to_json(facts), indent=2)
                + "\n", encoding="utf-8",
            )
        if grading is not None:
            (run_dir / "grading.json").write_text(
                json.dumps(grading.to_json(), indent=2) + "\n",
                encoding="utf-8",
            )
        outcome = RunOutcome(
            index=plan_run.index,
            description=plan_run.description,
            repo=plan_run.repo,
            runner=plan_run.runner.value,
            model=plan_run.model,
            phase_yn=phase_yn,
            gate_verdict=_gate_verdict_str(terminal, facts),
            result=result_label,
            terminal_state=terminal.value,
            grading=grading.to_json() if grading else None,
            facts=(__import__("bin.harness.schema",
                                fromlist=["run_facts_to_json"])
                    .run_facts_to_json(facts) if facts else None),
        )
        if log is not None:
            log.log(
                f"DONE: gate={outcome.gate_verdict} "
                f"result={outcome.result}",
                run_dir=run_dir, tag=tag,
            )
        return outcome

    # v1.5.7 103: production path — real clone → install →
    # launch → facts → grade. ``hooks.fake_run`` (above) stays an
    # OPTIONAL fast-path for unit tests; absent the hook, the
    # real composition runs. The AI-CLI subprocess in
    # ``runner.launch_run`` is the only thing tests stub (via
    # `unittest.mock.patch`); everything else — clone, install,
    # the installed-gate re-run, the grader — runs for real.
    return _execute_one_run_production(
        plan_run, harness_run_dir, run_dir, target_dir,
        artifact_map=artifact_map,
        local_artifact_info=local_artifact_info,
        log=log, tag=tag,
    )


def _prep_error_fields(exc) -> "dict":
    """v1.5.7 146: the prep_error block for invocation.json /
    grading.json — the reason plus (on an install timeout/failure)
    the install.log path + tail, so a post-mortem doesn't require
    re-reading the log."""
    out: "dict" = {"prep_error": exc.reason}
    path = getattr(exc, "install_log_path", None)
    if path:
        out["install_log_path"] = path
        out["install_log_tail"] = getattr(exc, "install_log_tail", [])
    return out


def _aborted_prep_log_msg(exc) -> str:
    """v1.5.7 146: the run.log/harness.log ABORTED_PREP line — the
    reason plus a 5-line inline install.log tail + full-log path, so
    a `tail run.log` shows the install's last words inline."""
    msg = f"ABORTED_PREP: {exc.reason}"
    tail = getattr(exc, "install_log_tail", None)
    if tail:
        last = "\n".join(f"    {ln}" for ln in tail[-5:])
        msg += f"\n  Last 5 lines of install.log:\n{last}"
        path = getattr(exc, "install_log_path", None)
        if path:
            msg += f"\n  Full install log: {path}"
    return msg


def _execute_one_run_production(
        plan_run: PlanRun, harness_run_dir: Path,
        run_dir: Path, target_dir: Path, *,
        artifact_map: "dict[InstallChannel, dict]",
        local_artifact_info: "Optional[dict]",
        log: "Optional[_ProgressLog]" = None,
        tag: "Optional[str]" = None,
) -> RunOutcome:
    """v1.5.7 103: real per-run composition.

    Steps:
      1. Build a synthetic Case + RunAxes from the PlanRun.
      2. ``prepare.prepare`` clones the repo, populates docs per
         prep policy, and installs the skill via the run's
         channel (passing the folder-local artifact when
         applicable per 101). PrepError ⇒ terminal
         ``ABORTED_PREP``, ``result=N/A``; the invocation
         receipt records the reason.
      3. ``runner.launch_run`` runs the AI-CLI as a detached
         subprocess with the run's parameters (100) and the
         appropriate stdin/argv prompt route (095). Tests patch
         this to write a canned ``quality/`` tree and return
         COMPLETED — the only stub-able piece in the
         composition.
      4. On COMPLETED: ``facts.extract_facts`` re-runs the run's
         INSTALLED gate over the produced ``quality/`` tree (the
         two-sourced extraction per design §C); ``grade_expect``
         (existing 099 helper) grades the plan's flat ``expect``
         map against the extracted facts. Result is MET/NOT-MET.
      5. Non-COMPLETED terminals (FAILED, TIMED_OUT, BLOCKED) ⇒
         ``result=N/A`` (never silently MET); the receipts +
         transcript still land so the operator can debug.

    Receipts written into ``run-NN/``:
      * ``invocation.json`` — RunInvocation serialized, with a
        non-standard ``local_artifact`` field carrying the 101
        wheel/tgz provenance (path + filename + sha256) when
        applicable, and a non-standard ``prep_error`` field on
        ABORTED_PREP.
      * ``facts.json`` — on COMPLETED only.
      * ``grading.json`` — on COMPLETED only.
      * (``stream.ndjson`` is written by ``runner.launch_run``.)
    """
    from bin import _purpose as _purpose_mod
    from bin.harness import facts as _facts_mod
    from bin.harness import prepare as _prepare_mod
    from bin.harness import runner as _runner_mod
    from bin.harness.schema import (
        Case, CaseInputs, CaseType, PrepPolicy, RunInvocation,
        run_facts_to_json, run_invocation_to_json,
    )

    # Build synthetic Case + RunAxes (the plan-runner doesn't use
    # cases.json — every per-run identity is the plan index).
    case_type = (CaseType.SECURITY_EVAL
                  if plan_run.prep == "security"
                  else CaseType.ACCEPTANCE)
    prep_policy = (PrepPolicy.SECURITY
                    if plan_run.prep == "security"
                    else PrepPolicy.ACCEPTANCE)
    case = Case(
        id=f"plan-{plan_run.index:02d}",
        type=case_type,
        title=plan_run.description,
        inputs=CaseInputs(
            repo_url=plan_run.repo,
            prep=prep_policy,
            target_ref=plan_run.ref,
            reference_docs_source=_prepare_mod._resolve_docs_source(
                plan_run.docs, plan_run.repo,
                harness_run_dir.parent),
        ),
        expected=[],
    )
    axes = RunAxes(
        runner=plan_run.runner,
        mode=plan_run.mode,
        install_channel=plan_run.channel,
        install_version=plan_run.install_version,
        model=plan_run.model,
    )

    run_id = _utc_now_run_id()
    local_artifact = (
        Path(local_artifact_info["path"])
        if local_artifact_info else None
    )
    qpb_version = _purpose_mod.get_version()
    phase_yn_all_dashes = {f"P{i}": "-" for i in range(7)}

    def _now_iso() -> str:
        return datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    def _log(msg: str) -> None:
        # No-op when log is absent (some unit tests call the
        # production helper directly without a logger).
        if log is not None:
            log.log(msg, run_dir=run_dir, tag=tag or "run")

    # ----- STEP 1: PREPARE (clone + docs + install) -----
    # v1.5.7 107: when `workspace_root` is set, use it as the
    # target instead of `run-NN/target`. The first run in a
    # shared-workspace sequence preps it (clone + install);
    # subsequent runs detect the installed skill and reuse the
    # workspace as-is (no re-clone, no re-install, no wipe of
    # the existing ``quality/`` tree — phase N reads phase
    # N-1's artifacts). The 105-hardened ``clone_worktree``
    # raises if dest exists, so we check first and skip prep
    # cleanly.
    started_at = _now_iso()
    if plan_run.workspace_root is not None:
        actual_target_dir = (
            Path(plan_run.workspace_root)
            .expanduser().resolve()
        )
        workspace_already_prepared = _is_workspace_prepared(
            actual_target_dir
        )
    else:
        actual_target_dir = target_dir
        workspace_already_prepared = False

    if workspace_already_prepared:
        _log(
            f"reuse workspace {actual_target_dir} "
            f"(skill already installed; no clone/install)"
        )
        target_sha = _resolve_workspace_sha(actual_target_dir)
        prep_result = _prepare_mod.PrepResult(
            target_dir=actual_target_dir,
            target_sha=target_sha,
            scrubbed_docs_manifest=None,
            leakage_gate=None,
        )
    else:
        _log(f"clone {plan_run.repo}@{plan_run.ref}")
        _log(f"install ({plan_run.channel.value})")
        # If workspace_root is set + empty-existing-dir, clear
        # it so clone_worktree (105) can create it; if non-
        # empty without an installed skill, that's an operator
        # error — fall through to prepare() and let
        # clone_worktree raise its standard message.
        if (plan_run.workspace_root is not None
                and actual_target_dir.exists()
                and actual_target_dir.is_dir()
                and not any(actual_target_dir.iterdir())):
            actual_target_dir.rmdir()
        try:
            prep_result = _prepare_mod.prepare(
                case, actual_target_dir,
                ai_tool=plan_run.runner.value,
                axes=axes,
                local_artifact=local_artifact,
                prep_timeout_s=plan_run.prep_timeout_s,
                install_log_path=run_dir / "install.log",
            )
        except _prepare_mod.PrepError as exc:
            ended_at = _now_iso()
            inv_dict = {
                "run_id": run_id,
                "case_id": case.id,
                "axes": {
                    "runner": axes.runner.value,
                    "mode": axes.mode.value,
                    "install_channel":
                        axes.install_channel.value,
                    "install_version": axes.install_version,
                    "model": axes.model,
                    "thinking": axes.thinking,
                },
                "qpb_version": qpb_version,
                "target_sha": "",
                "cli_command": "",
                "cwd": str(actual_target_dir),
                "env_snapshot": {},
                "started_at": started_at,
                "ended_at": ended_at,
                "exit_code": -1,
                "terminal_state":
                    TerminalState.ABORTED_PREP.value,
                "scrubbed_docs_manifest": None,
                "leakage_gate": (
                    "ABORTED" if exc.leakage_terms else None
                ),
                "local_artifact": local_artifact_info,
                **_prep_error_fields(exc),
            }
            (run_dir / "invocation.json").write_text(
                json.dumps(inv_dict, indent=2) + "\n",
                encoding="utf-8",
            )
            _log(_aborted_prep_log_msg(exc))
            _log("DONE: gate=N/A result=N/A")
            return RunOutcome(
                index=plan_run.index,
                description=plan_run.description,
                repo=plan_run.repo,
                runner=plan_run.runner.value,
                model=plan_run.model,
                phase_yn=phase_yn_all_dashes,
                gate_verdict="N/A",
                result="N/A",
                terminal_state=TerminalState.ABORTED_PREP.value,
                grading=_prep_error_fields(exc),
            )

    # ----- STEP 2: LAUNCH (detached AI-CLI subprocess) -----
    # v1.5.7 106: Mode A uses the full-pipeline prompt that
    # actually triggers all-phases-in-one-session (the bare
    # pre-106 prompt produced 0/4 MET on the first live run).
    # Mode B doesn't use a prompt (run_playbook builds its own
    # phase-prompt sequence); we still set it for the
    # invocation receipt's cli_command field but it never
    # reaches the subprocess.
    effective_max_duration_s = (
        plan_run.max_duration_s
        if plan_run.max_duration_s is not None
        else _DEFAULT_MAX_DURATION_S
    )
    # v1.5.7 106 (fix): per-run `prompt` override in Mode A
    # replaces the default verbatim. Operator can drive a
    # single phase ("Run quality playbook phase 2.") for the
    # 107 sequential-phase-by-phase pattern, or test odd
    # prompts. Mode B is unaffected (run_playbook builds its
    # own phase prompts).
    if plan_run.mode == Mode.A:
        launch_prompt = (
            plan_run.prompt if plan_run.prompt
            else _MODE_A_FULL_RUN_PROMPT
        )
    else:
        launch_prompt = "(Mode B — run_playbook drives the phases)"
    launch_spec = _runner_mod.LaunchSpec(
        target_dir=prep_result.target_dir,
        run_dir=run_dir,
        axes=axes,
        case_id=case.id,
        run_id=run_id,
        max_duration_s=effective_max_duration_s,
        prompt=launch_prompt,
        parameters=(plan_run.parameters or None),
    )
    _log(
        f"launch {plan_run.runner.value}/{plan_run.model} "
        f"(mode={plan_run.mode.value}, "
        f"max_duration={int(effective_max_duration_s)}s)"
    )
    launch = _runner_mod.launch_run(launch_spec)
    terminal = launch.terminal_state
    _log(
        f"launched (pid={launch.pid}, terminal={terminal.value}) "
        f"stream={launch.stream_path}"
    )

    # ----- STEP 3: INVOCATION RECEIPT -----
    inv = RunInvocation(
        run_id=run_id,
        case_id=case.id,
        axes=axes,
        qpb_version=qpb_version,
        target_sha=prep_result.target_sha,
        cli_command=launch.cli_command,
        cwd=launch.cwd,
        env_snapshot=launch.env_snapshot,
        started_at=launch.started_at,
        ended_at=launch.ended_at,
        exit_code=launch.exit_code,
        terminal_state=terminal,
        scrubbed_docs_manifest=prep_result.scrubbed_docs_manifest,
        leakage_gate=prep_result.leakage_gate,
    )
    inv_dict = run_invocation_to_json(inv)
    inv_dict["local_artifact"] = local_artifact_info
    (run_dir / "invocation.json").write_text(
        json.dumps(inv_dict, indent=2) + "\n",
        encoding="utf-8",
    )

    # ----- STEP 4: FACTS + GRADE (only on COMPLETED) -----
    facts: "Optional[RunFacts]" = None
    grading = None
    result_label = "N/A"
    transcript = ""
    if terminal == TerminalState.COMPLETED:
        try:
            transcript = launch.stream_path.read_text(
                encoding="utf-8", errors="ignore",
            )
        except OSError:
            transcript = ""
        _log("facts (re-run installed gate)")
        try:
            facts = _facts_mod.extract_facts(
                target_dir=prep_result.target_dir,
                axes=axes,
                transcript=transcript,
                exit_code=launch.exit_code,
                raw_receipt=launch.stream_path.name,
            )
            (run_dir / "facts.json").write_text(
                json.dumps(run_facts_to_json(facts), indent=2)
                + "\n", encoding="utf-8",
            )
            _log("grade")
            grading = grade_expect(plan_run, facts, axes)
            (run_dir / "grading.json").write_text(
                json.dumps(grading.to_json(), indent=2) + "\n",
                encoding="utf-8",
            )
            result_label = grading.verdict  # MET / NOT-MET
        except _facts_mod.FactsError as exc:
            # Gate re-run failed (e.g. installed gate missing).
            # Treat as N/A and record the reason; the
            # invocation.json is still the load-bearing receipt.
            _log(f"facts error: {exc}")
            grading = {"facts_error": str(exc)}
            result_label = "N/A"

    # ----- STEP 5: PHASE Y/N + OUTCOME -----
    quality_dir = prep_result.target_dir / "quality"
    phase_yn = capture_phase_yn(transcript, quality_dir)
    if terminal != TerminalState.COMPLETED:
        # Phases past the failure point read "-" rather than "N"
        # — they didn't get a chance.
        for p in ("P3", "P4", "P5", "P6"):
            if phase_yn.get(p) == "N":
                phase_yn[p] = "-"
    gate_verdict = _gate_verdict_str(terminal, facts)
    _log(f"DONE: gate={gate_verdict} result={result_label}")
    return RunOutcome(
        index=plan_run.index,
        description=plan_run.description,
        repo=plan_run.repo,
        runner=plan_run.runner.value,
        model=plan_run.model,
        phase_yn=phase_yn,
        gate_verdict=gate_verdict,
        result=result_label,
        terminal_state=terminal.value,
        grading=(grading.to_json() if hasattr(grading, "to_json")
                  else grading),
        facts=(run_facts_to_json(facts) if facts else None),
    )


# ---------------------------------------------------------------------------
# v1.5.7 108: detached launch + background collector
# ---------------------------------------------------------------------------


def _pid_is_alive(pid: int) -> bool:
    """v1.5.7 108: liveness check for orphaned AI-CLI processes
    (the collector polls these — it can't ``waitpid`` because
    the AI-CLIs are children of the now-exited run_plan parent).
    Wrapped so tests can patch it cleanly.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we can't signal it. Treat as
        # alive — it's not gone.
        return True
    except OSError:
        return False
    return True


def _launch_one_run_detached(
        plan_run: PlanRun, harness_run_dir: Path,
        run_dir: Path, target_dir: Path, *,
        artifact_map: "dict[InstallChannel, dict]",
        local_artifact_info: "Optional[dict]",
        log: "Optional[_ProgressLog]" = None,
        tag: "Optional[str]" = None,
) -> dict:
    """v1.5.7 108: spawn-only half of the per-run flow. Does
    prepare (clone+install, or reuse workspace_root per 107),
    spawns the detached AI-CLI via ``runner.launch_run_async``,
    writes a RUNNING-state ``invocation.json`` placeholder, and
    returns a ManifestEntry dict that the collector picks up.

    Does NOT wait for the AI-CLI to finish. The detached
    collector (``collect_harness_run``) polls the PID via
    ``_pid_is_alive`` and grades the run when the process
    terminates.

    Returns ``None`` when prepare fails — the manifest entry
    records ABORTED_PREP terminal state so the collector skips
    it on a later sweep.
    """
    from bin import _purpose as _purpose_mod
    from bin.harness import prepare as _prepare_mod
    from bin.harness import runner as _runner_mod
    from bin.harness.schema import (
        Case, CaseInputs, CaseType, PrepPolicy,
    )

    case_type = (CaseType.SECURITY_EVAL
                  if plan_run.prep == "security"
                  else CaseType.ACCEPTANCE)
    prep_policy = (PrepPolicy.SECURITY
                    if plan_run.prep == "security"
                    else PrepPolicy.ACCEPTANCE)
    case = Case(
        id=f"plan-{plan_run.index:02d}",
        type=case_type,
        title=plan_run.description,
        inputs=CaseInputs(
            repo_url=plan_run.repo,
            prep=prep_policy,
            target_ref=plan_run.ref,
            reference_docs_source=_prepare_mod._resolve_docs_source(
                plan_run.docs, plan_run.repo,
                harness_run_dir.parent),
        ),
        expected=[],
    )
    axes = RunAxes(
        runner=plan_run.runner,
        mode=plan_run.mode,
        install_channel=plan_run.channel,
        install_version=plan_run.install_version,
        model=plan_run.model,
    )
    run_id = _utc_now_run_id()
    local_artifact = (
        Path(local_artifact_info["path"])
        if local_artifact_info else None
    )
    qpb_version = _purpose_mod.get_version()
    effective_max_duration_s = (
        plan_run.max_duration_s
        if plan_run.max_duration_s is not None
        else _DEFAULT_MAX_DURATION_S
    )

    def _log(msg: str) -> None:
        if log is not None:
            log.log(msg, run_dir=run_dir, tag=tag or "run")

    # ----- PREPARE (clone/install or reuse workspace_root) -----
    if plan_run.workspace_root is not None:
        actual_target_dir = (
            Path(plan_run.workspace_root)
            .expanduser().resolve()
        )
        workspace_already_prepared = _is_workspace_prepared(
            actual_target_dir
        )
    else:
        actual_target_dir = target_dir
        workspace_already_prepared = False

    started_at = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    if workspace_already_prepared:
        _log(
            f"reuse workspace {actual_target_dir} "
            f"(skill already installed; no clone/install)"
        )
        target_sha = _resolve_workspace_sha(actual_target_dir)
        prep_target_dir = actual_target_dir
    else:
        _log(f"clone {plan_run.repo}@{plan_run.ref}")
        _log(f"install ({plan_run.channel.value})")
        if (plan_run.workspace_root is not None
                and actual_target_dir.exists()
                and actual_target_dir.is_dir()
                and not any(actual_target_dir.iterdir())):
            actual_target_dir.rmdir()
        try:
            prep_result = _prepare_mod.prepare(
                case, actual_target_dir,
                ai_tool=plan_run.runner.value,
                axes=axes,
                local_artifact=local_artifact,
                prep_timeout_s=plan_run.prep_timeout_s,
                install_log_path=run_dir / "install.log",
            )
            prep_target_dir = prep_result.target_dir
            target_sha = prep_result.target_sha
        except _prepare_mod.PrepError as exc:
            # Prep failed — emit ABORTED_PREP manifest entry so
            # the collector knows to skip the wait + run grade
            # with N/A. The receipts mirror the synchronous
            # ABORTED_PREP path.
            ended_at = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            inv_dict = {
                "run_id": run_id,
                "case_id": case.id,
                "axes": {
                    "runner": axes.runner.value,
                    "mode": axes.mode.value,
                    "install_channel":
                        axes.install_channel.value,
                    "install_version": axes.install_version,
                    "model": axes.model,
                    "thinking": axes.thinking,
                },
                "qpb_version": qpb_version,
                "target_sha": "",
                "cli_command": "",
                "cwd": str(actual_target_dir),
                "env_snapshot": {},
                "started_at": started_at,
                "ended_at": ended_at,
                "exit_code": -1,
                "terminal_state":
                    TerminalState.ABORTED_PREP.value,
                "scrubbed_docs_manifest": None,
                "leakage_gate": (
                    "ABORTED" if exc.leakage_terms else None
                ),
                "local_artifact": local_artifact_info,
                **_prep_error_fields(exc),
            }
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "invocation.json").write_text(
                json.dumps(inv_dict, indent=2) + "\n",
                encoding="utf-8",
            )
            _log(_aborted_prep_log_msg(exc))
            return {
                "index": plan_run.index,
                "description": plan_run.description,
                "repo": plan_run.repo,
                "runner": plan_run.runner.value,
                "model": plan_run.model,
                "channel": plan_run.channel.value,
                "mode": plan_run.mode.value,
                "target_dir": str(actual_target_dir),
                "run_dir": str(run_dir),
                "run_id": run_id,
                "pid": None,
                "started_at": started_at,
                "terminal_state":
                    TerminalState.ABORTED_PREP.value,
                **_prep_error_fields(exc),
                "status_path": str(run_dir / "status.json"),
            }

    # ----- LAUNCH (detached AI-CLI spawn) -----
    if plan_run.mode == Mode.A:
        launch_prompt = (
            plan_run.prompt if plan_run.prompt
            else _MODE_A_FULL_RUN_PROMPT
        )
    else:
        launch_prompt = "(Mode B — run_playbook drives the phases)"
    # v1.5.7 123: materialize a PRISTINE QPB worktree at HEAD
    # for Mode B runs ONLY, so run_playbook's source-guard
    # (`_check_qpb_source_unchanged`) sees a clean tree and
    # doesn't abort Phase 1 — even when the live harness clone
    # has uncommitted dev changes (the AUP-experiment's
    # Mode B failure mode). Lifecycle: created at launch
    # here, removed at collect time in
    # `_collect_one_run_detached`. Mode A doesn't go through
    # run_playbook → doesn't need a pristine worktree.
    pristine_root: "Optional[Path]" = None
    if plan_run.mode == Mode.B:
        try:
            pristine_root = (
                _runner_mod._materialize_pristine_qpb_tree())
            _log(
                f"123: pristine QPB worktree materialized at "
                f"{pristine_root} for Mode B run "
                f"(immune to live dev-tree dirtiness)"
            )
        except _runner_mod.RunnerError as exc:
            _log(
                f"123: pristine worktree materialization "
                f"failed: {exc} — falling back to live clone "
                f"(may abort at Phase 1 if dev tree is dirty)"
            )
    launch_spec = _runner_mod.LaunchSpec(
        target_dir=prep_target_dir,
        run_dir=run_dir,
        axes=axes,
        case_id=case.id,
        run_id=run_id,
        max_duration_s=effective_max_duration_s,
        prompt=launch_prompt,
        parameters=(plan_run.parameters or None),
        pristine_root=pristine_root,
    )
    _log(
        f"launch {plan_run.runner.value}/{plan_run.model} "
        f"(mode={plan_run.mode.value}, "
        f"max_duration={int(effective_max_duration_s)}s)"
    )
    spawn = _runner_mod.launch_run_async(launch_spec)
    _log(
        f"launched (pid={spawn.pid}) — detached; collector "
        f"will reap. stream={spawn.stream_path}"
    )

    # Write the RUNNING-state invocation.json placeholder so a
    # status observer (110 layer) sees something coherent
    # before the collector finalizes it.
    inv_placeholder = {
        "run_id": run_id,
        "case_id": case.id,
        "axes": {
            "runner": axes.runner.value,
            "mode": axes.mode.value,
            "install_channel": axes.install_channel.value,
            "install_version": axes.install_version,
            "model": axes.model,
            "thinking": axes.thinking,
        },
        "qpb_version": qpb_version,
        "target_sha": target_sha,
        "cli_command": spawn.cli_command,
        "cwd": spawn.cwd,
        "env_snapshot": spawn.env_snapshot,
        "started_at": spawn.started_at,
        "ended_at": None,
        "exit_code": None,
        "terminal_state": None,
        "scrubbed_docs_manifest": None,
        "leakage_gate": None,
        "local_artifact": local_artifact_info,
    }
    (run_dir / "invocation.json").write_text(
        json.dumps(inv_placeholder, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "index": plan_run.index,
        # BUG-003 fix: mark the spawned run RUNNING so a relaunch over a
        # PENDING manifest entry (the _retry_pending_runs_once merge)
        # transitions it out of PENDING instead of leaving a live run
        # tagged PENDING in the manifest + status surfaces.
        "state": "RUNNING",
        "description": plan_run.description,
        "repo": plan_run.repo,
        "runner": plan_run.runner.value,
        "model": plan_run.model,
        "channel": plan_run.channel.value,
        "mode": plan_run.mode.value,
        "target_dir": str(prep_target_dir),
        "run_dir": str(run_dir),
        "run_id": run_id,
        "pid": spawn.pid,
        "started_at": spawn.started_at,
        "stream_path": str(spawn.stream_path),
        "status_path": str(run_dir / "status.json"),
        "max_duration_s": effective_max_duration_s,
        # The plan_run expect map is what the grader needs.
        "expect": plan_run.expect,
        # Per-run prompt for receipt completeness.
        "prompt": (plan_run.prompt
                    if plan_run.prompt else launch_prompt),
        # v1.5.7 123: per-run pristine Mode B worktree
        # (created at launch above; removed at collect-time
        # in `_collect_one_run_detached`). Manifest carries
        # the path so the collector can find + remove it.
        # None for Mode A runs.
        "pristine_root": (str(pristine_root)
                          if pristine_root is not None else None),
    }


def _relpath_for_manifest(path_value: str,
                            harness_run_dir: Path) -> str:
    """v1.5.7 118: convert an absolute path to its relative
    form under ``harness_run_dir`` for manifest writes, so a
    copied/moved harness-run folder reads correctly on any
    machine. If the path isn't under ``harness_run_dir`` (e.g.
    a target_dir on a different mount), leave it absolute.

    Used at manifest-write time; the read side resolves via
    ``status._resolve_manifest_path``, which knows about both
    relative (new) and absolute (legacy) forms."""
    if not path_value:
        return path_value
    p = Path(path_value)
    if not p.is_absolute():
        return path_value
    try:
        return str(p.relative_to(harness_run_dir))
    except ValueError:
        return path_value


def _relativize_manifest_entry(entry: dict,
                                  harness_run_dir: Path) -> dict:
    """v1.5.7 118: convert path-bearing fields in a manifest
    entry to be relative to ``harness_run_dir``. Returns a NEW
    dict; the caller's entry is unchanged."""
    if entry is None:
        return entry
    out = dict(entry)
    for field in ("run_dir", "stream_path", "status_path",
                    "target_dir"):
        if field in out:
            out[field] = _relpath_for_manifest(
                out[field], harness_run_dir)
    return out


def _resolve_entry_path(entry_value: str,
                          harness_run_dir: Path) -> Path:
    """v1.5.7 118: collector-side resolver. Same semantics as
    ``status._resolve_manifest_path`` — kept local so
    plan_runner doesn't need to import from status.py
    (avoid a circular import at module load)."""
    if not entry_value:
        return harness_run_dir
    p = Path(entry_value)
    if not p.is_absolute():
        return harness_run_dir / p
    if p.exists():
        return p
    hr_name = harness_run_dir.name
    parts = list(p.parts)
    if hr_name in parts:
        idx = parts.index(hr_name)
        tail = parts[idx + 1:]
        if tail:
            return harness_run_dir.joinpath(*tail)
        return harness_run_dir
    return harness_run_dir / p.name


def _collect_one_run_detached(
        entry: dict, harness_run_dir: Path,
        log: "Optional[_ProgressLog]" = None,
) -> RunOutcome:
    """v1.5.7 108: collect ONE manifest entry. Idempotent:
    if ``grading.json`` already exists, returns the existing
    outcome without re-running facts/grade. Otherwise polls
    the AI-CLI PID until termination (or ``max_duration_s``
    elapses), then runs facts + grade and writes the final
    receipts.

    Orphan-polling: the AI-CLIs are children of the now-
    exited run_plan; the collector polls liveness via
    ``_pid_is_alive`` (``os.kill(pid, 0)``). Exit code can't
    be recovered for orphans; terminal_state is inferred from
    artifacts (gate-report-latest.json present ⇒ COMPLETED;
    absent + process gone ⇒ FAILED). Max-duration enforced
    via ``runner._kill_process_tree``.
    """
    from bin.harness import facts as _facts_mod
    from bin.harness import runner as _runner_mod
    from bin.harness import inflight_registry as _inflight
    from bin.harness.schema import (
        Runner, Mode as _Mode, InstallChannel,
        run_facts_to_json,
    )

    # v1.5.7 118: resolve manifest path entries against the
    # harness-run dir so a copied/moved harness-run folder is
    # collectable from any machine. Back-compat: legacy
    # absolute paths still work when the folder hasn't moved.
    run_dir = _resolve_entry_path(
        entry.get("run_dir", ""), harness_run_dir)
    target_dir = _resolve_entry_path(
        entry.get("target_dir", ""), harness_run_dir)
    grading_path = run_dir / "grading.json"

    # v1.5.7 125: release the lifetime-slot from the global
    # registry once the run reaches a terminal state. Called
    # at every return path (idempotent — release_run_slot is
    # a no-op if no matching entry).
    _run_index = entry["index"]

    def _release_slot() -> None:
        _inflight.release_run_slot(
            harness_run_dir=harness_run_dir,
            run_index=_run_index,
        )

    # Re-hydrate a minimal PlanRun for grading + axes for
    # facts extraction. The manifest carries enough to re-
    # build the axes; the plan_run is reconstructed for
    # grade_expect.
    plan_run = PlanRun(
        index=entry["index"],
        description=entry["description"],
        repo=entry["repo"],
        ref="",  # unused at collect time
        runner=Runner(entry["runner"]),
        model=entry["model"],
        channel=InstallChannel(entry["channel"]),
        expect=entry.get("expect", {}),
        mode=_Mode(entry.get("mode", "A")),
    )
    axes = RunAxes(
        runner=plan_run.runner,
        mode=plan_run.mode,
        install_channel=plan_run.channel,
        model=plan_run.model,
    )

    tag = _run_tag(plan_run)

    def _log(msg: str) -> None:
        if log is not None:
            log.log(msg, run_dir=run_dir, tag=tag)

    # ----- IDEMPOTENCY: already collected → return existing -----
    if grading_path.is_file():
        try:
            grading_dict = json.loads(
                grading_path.read_text(encoding="utf-8"))
            facts_path = run_dir / "facts.json"
            facts_dict = (
                json.loads(facts_path.read_text(encoding="utf-8"))
                if facts_path.is_file() else None
            )
            # Reconstruct outcome from receipts.
            gate_verdict_str = "N/A"
            terminal_str = entry.get(
                "terminal_state",
                TerminalState.COMPLETED.value,
            )
            if facts_dict and "gate" in facts_dict:
                gate_verdict_str = {
                    "PASS": "PASSED", "CLEANUP": "CLEANUP",
                    "FAIL": "FAILED",
                }.get(facts_dict["gate"].get("gate_result"),
                       "?")
            _release_slot()
            return RunOutcome(
                index=plan_run.index,
                description=plan_run.description,
                repo=plan_run.repo,
                runner=plan_run.runner.value,
                model=plan_run.model,
                phase_yn={f"P{i}": "-" for i in range(7)},
                gate_verdict=gate_verdict_str,
                result=grading_dict.get("verdict", "N/A"),
                terminal_state=terminal_str,
                grading=grading_dict,
                facts=facts_dict,
            )
        except (json.JSONDecodeError, KeyError):
            # Corrupt receipt — fall through to re-collect.
            pass

    # ----- ABORTED_PREP from launch → grade as N/A immediately -----
    if entry.get("terminal_state") == TerminalState.ABORTED_PREP.value:
        outcome = RunOutcome(
            index=plan_run.index,
            description=plan_run.description,
            repo=plan_run.repo,
            runner=plan_run.runner.value,
            model=plan_run.model,
            phase_yn={f"P{i}": "-" for i in range(7)},
            gate_verdict="N/A",
            result="N/A",
            terminal_state=TerminalState.ABORTED_PREP.value,
            grading={"prep_error": entry.get("prep_error",
                                                "unknown")},
        )
        # Write a grading.json marker so a re-sweep skips.
        (run_dir / "grading.json").write_text(
            json.dumps({"verdict": "N/A",
                        "prep_error": entry.get(
                            "prep_error", "unknown")},
                        indent=2) + "\n",
            encoding="utf-8",
        )
        _log("DONE: gate=N/A result=N/A (ABORTED_PREP)")
        _release_slot()
        return outcome

    # ----- BUG-001 fix: a still-PENDING entry with no pid has not launched
    # yet (starved, awaiting a slot via _retry_pending_runs_once). It is NOT
    # a crashed run — do not grade it terminal. Leaving it ungraded lets the
    # next collector pass retry it (or mark it ABANDONED_STARVED past the
    # deadline). Without this guard the pid-is-None branch below grades it
    # FAILED on the first sweep, defeating the ABANDONED_STARVED deadline. -----
    if (entry.get("state") == "PENDING" and entry.get("pid") is None
            and not grading_path.is_file()):
        return RunOutcome(
            index=plan_run.index,
            description=plan_run.description,
            repo=plan_run.repo,
            runner=plan_run.runner.value,
            model=plan_run.model,
            phase_yn={f"P{i}": "-" for i in range(7)},
            gate_verdict="N/A",
            result="PENDING",
            terminal_state="PENDING",
        )

    # ----- ORPHAN POLLING: wait for the AI-CLI to terminate -----
    pid = entry.get("pid")
    started_at = entry.get("started_at", "")
    max_duration_s = float(
        entry.get("max_duration_s", _DEFAULT_MAX_DURATION_S)
    )
    deadline = (time.monotonic()
                + max(0.0, max_duration_s))
    # v1.5.7 118: resolve through the manifest helper so a
    # moved/copied harness-run folder still finds its stream.
    stream_path_for_classify = (
        _resolve_entry_path(
            entry.get("stream_path", ""),
            harness_run_dir)
        if entry.get("stream_path")
        else run_dir / "stream.ndjson"
    )
    terminal: TerminalState
    terminal_reason = ""
    while True:
        # v1.5.7 120: PROACTIVE REAP on terminal result event.
        # Claude --print emits exactly one terminal `result`
        # envelope at the end of its turn; once it appears,
        # the run is done semantically. Kill any exit-hang
        # process and classify from the stream — instead of
        # burning the full max_duration on the exit-hang.
        # The AUP-experiment's Mode A gson runs hit this:
        # GATE PASSED, is_error:false, but the claude --print
        # process hung at exit; pre-120 they burned the full
        # 2h max_duration and were recorded TIMED_OUT despite
        # the clean completion.
        stream_state, stream_reason = (
            _runner_mod._classify_stream_terminal(
                stream_path_for_classify, target_dir=target_dir)
        )
        if stream_state is not None:
            # Reap the exit-hang if still alive.
            if pid is not None and _pid_is_alive(pid):
                _runner_mod._kill_process_tree(pid)
            terminal = stream_state
            terminal_reason = stream_reason
            break
        if pid is None or not _pid_is_alive(pid):
            # Process terminated WITHOUT a terminal result
            # event — Mode B path (run_playbook doesn't emit
            # a Claude `result` envelope) or a Claude run
            # that died before emitting its result. Use the
            # artifact heuristic: gate-report-latest.json
            # present ⇒ COMPLETED; otherwise FAILED.
            #
            # The 113 stream-classifier check is folded into
            # the proactive-reap branch above; this branch is
            # only reached when the classifier returned None
            # (no terminal result event).
            gate_report = (
                target_dir / "quality" / "results"
                / "gate-report-latest.json"
            )
            quality_dir = target_dir / "quality"
            if gate_report.is_file():
                terminal = TerminalState.COMPLETED
            elif quality_dir.is_dir() and any(quality_dir.iterdir()):
                # Partial work — treat as FAILED.
                terminal = TerminalState.FAILED
            else:
                terminal = TerminalState.FAILED
            break
        if time.monotonic() >= deadline:
            # Max-duration kill. v1.5.7 120: race-safe
            # re-check the stream after the kill — the
            # result event may have appeared between the
            # last poll iteration and the deadline. Stream
            # wins (the kill was reaping the exit-hang, not
            # interrupting work). If still no result event,
            # this is a GENUINE TIMED_OUT (no completion
            # signal).
            _runner_mod._kill_process_tree(pid)
            stream_state, stream_reason = (
                _runner_mod._classify_stream_terminal(
                    stream_path_for_classify, target_dir=target_dir)
            )
            if stream_state is not None:
                terminal = stream_state
                terminal_reason = stream_reason
            else:
                terminal = TerminalState.TIMED_OUT
            break
        time.sleep(0.25)

    ended_at = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    # Write terminal status.json (carries 112's
    # terminal_reason when BLOCKED).
    _write_terminal_status(run_dir, pid, started_at,
                            ended_at, terminal,
                            terminal_reason=terminal_reason)

    # ----- FACTS + GRADE -----
    facts = None
    grading = None
    result_label = "N/A"
    transcript = ""
    stream_path = (
        _resolve_entry_path(
            entry.get("stream_path", ""), harness_run_dir)
        if entry.get("stream_path")
        else run_dir / "stream.ndjson"
    )
    if stream_path.is_file():
        try:
            transcript = stream_path.read_text(
                encoding="utf-8", errors="ignore"
            )
        except OSError:
            transcript = ""
    if terminal == TerminalState.COMPLETED:
        _log("facts (re-run installed gate)")
        try:
            facts = _facts_mod.extract_facts(
                target_dir=target_dir,
                axes=axes,
                transcript=transcript,
                exit_code=0,
                raw_receipt=stream_path.name,
            )
            (run_dir / "facts.json").write_text(
                json.dumps(run_facts_to_json(facts),
                           indent=2) + "\n",
                encoding="utf-8",
            )
            _log("grade")
            grading = grade_expect(plan_run, facts, axes)
            (run_dir / "grading.json").write_text(
                json.dumps(grading.to_json(), indent=2)
                + "\n", encoding="utf-8",
            )
            result_label = grading.verdict
        except _facts_mod.FactsError as exc:
            _log(f"facts error: {exc}")
            grading = {"facts_error": str(exc)}
            result_label = "N/A"
            (run_dir / "grading.json").write_text(
                json.dumps(grading, indent=2) + "\n",
                encoding="utf-8",
            )
    else:
        # Non-COMPLETED: write a grading.json sentinel so a
        # re-sweep doesn't re-poll a long-gone process.
        (run_dir / "grading.json").write_text(
            json.dumps({
                "verdict": "N/A",
                "terminal_state": terminal.value,
            }, indent=2) + "\n",
            encoding="utf-8",
        )

    phase_yn = capture_phase_yn(transcript,
                                  target_dir / "quality")
    if terminal != TerminalState.COMPLETED:
        for p in ("P3", "P4", "P5", "P6"):
            if phase_yn.get(p) == "N":
                phase_yn[p] = "-"
    gate_verdict = _gate_verdict_str(terminal, facts)
    # v1.5.7 123: tear down the per-run pristine Mode B
    # worktree (if any). Created at launch in
    # `_launch_one_run_detached`; removed here so a
    # long-lived harness session doesn't leak worktrees.
    # Best-effort — a failed teardown is logged but doesn't
    # block the grade result.
    pristine = entry.get("pristine_root")
    if pristine:
        try:
            _runner_mod._remove_pristine_qpb_tree(
                Path(pristine))
            _log(f"123: removed pristine worktree {pristine}")
        except Exception as exc:  # pragma: no cover
            _log(f"123: pristine worktree cleanup "
                 f"failed (best-effort): {exc}")
    _log(f"DONE: gate={gate_verdict} result={result_label}")
    _release_slot()
    return RunOutcome(
        index=plan_run.index,
        description=plan_run.description,
        repo=plan_run.repo,
        runner=plan_run.runner.value,
        model=plan_run.model,
        phase_yn=phase_yn,
        gate_verdict=gate_verdict,
        result=result_label,
        terminal_state=terminal.value,
        grading=(grading.to_json() if hasattr(grading, "to_json")
                  else grading),
        facts=(run_facts_to_json(facts) if facts else None),
    )


def _write_terminal_status(run_dir: Path, pid: "Optional[int]",
                            started_at: str, ended_at: str,
                            terminal: TerminalState,
                            *,
                            terminal_reason: str = "") -> None:
    """v1.5.7 108: collector's terminal status.json write
    (the orphan-polling path can't recover exit_code, so it
    records -1 + the inferred terminal_state).

    v1.5.7 112: ``terminal_reason`` carries the AUP / API-error
    body when ``terminal == BLOCKED``. Empty for other states.

    v1.5.7 166 (closes 164's production gap): when the on-disk
    status.json ALREADY carries a ``terminal_state``, DO NOT
    overwrite. The supervisor's 164 abort writer beat us here and
    its authoritative values (real ``exit_code``, populated
    ``terminal_reason``, ``phase_aborted``) are richer than the
    collector's inference. The 2026-05-30 19:42 retest's run-02
    (chi codex Mode B, Phase 2 abort on ChatGPT quota) is the
    empirical: supervisor wrote ABORTED_PHASE + exit_code=1 +
    phase_aborted=2; this function then overwrote it with FAILED
    + exit_code=-1 + terminal_reason="". 166 makes the collector
    respect the supervisor's write — the 164 plumbing reaches
    production correctly."""
    status_path = run_dir / "status.json"
    # 166: respect an existing terminal_state (supervisor or
    # prior collector pass wrote it). Best-effort read; any error
    # falls through to the existing inference write.
    if status_path.is_file():
        try:
            existing = json.loads(
                status_path.read_text(encoding="utf-8"))
            if (isinstance(existing, dict)
                    and existing.get("terminal_state")):
                return  # supervisor's write wins
        except (OSError, ValueError):
            pass
    tmp = status_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({
        "state": "DONE",
        "pid": pid,
        "started_at": started_at,
        "heartbeat": ended_at,
        "ended_at": ended_at,
        "exit_code": -1,
        "terminal_state": terminal.value,
        "terminal_reason": terminal_reason,
    }, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, status_path)


# v1.5.7 165: collector retry + ABANDONED_STARVED deadline. Builds
# on 161 Task A (which writes PENDING manifest entries on
# starvation). Per the 161-A halt ruling, the artifact_map is
# resolved from ``<harness-run>/artifacts/manifest.json`` on disk
# (the canonical artifact-bundle manifest that `_build_artifacts`
# writes at run startup; verified shape via 152's evidence
# directory).
_PENDING_DEADLINE_DEFAULT_S = 3600.0


def _pending_deadline_s() -> float:
    """v1.5.7 165: PENDING-deadline threshold (seconds). After this
    long without a slot, a starved entry becomes
    ``ABANDONED_STARVED``. Default 3600s; env-tunable via
    ``QPB_HARNESS_PENDING_DEADLINE_S``."""
    raw = os.environ.get("QPB_HARNESS_PENDING_DEADLINE_S")
    if raw is None:
        return _PENDING_DEADLINE_DEFAULT_S
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return _PENDING_DEADLINE_DEFAULT_S
    return v if v > 0 else _PENDING_DEADLINE_DEFAULT_S


def _resolve_artifact_map_from_disk(
        harness_run_dir: Path,
        ) -> "dict[str, dict]":
    """v1.5.7 165: read ``<harness-run>/artifacts/manifest.json``
    and return the artifact_map dict keyed by channel name (the
    same shape ``_build_artifacts`` writes in memory + persists to
    disk). Empty dict when the manifest is absent / unparseable
    (the collector still tries to retry; ``_launch_one_run_detached``
    will fail clearly if the artifact it needs is missing — caught
    by the retry's broader exception handler)."""
    manifest_path = harness_run_dir / "artifacts" / "manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        return json.loads(
            manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _manifest_lock_path(harness_run_dir: Path) -> Path:
    """v1.5.7 174: the ``.manifest.lock`` file used to serialize
    manifest mutations across orchestrator launch threads,
    collector retry, and watchdog state updates. Separate from
    ``.collect.lock`` (which serializes collector body) so
    cross-acquisition doesn't deadlock (FINDING-1 lesson — locks
    on different files don't cross-block in the same process).
    """
    return harness_run_dir / ".manifest.lock"


@contextlib.contextmanager
def _with_manifest_lock(harness_run_dir: Path):
    """v1.5.7 174: blocking LOCK_EX on ``.manifest.lock`` for the
    duration of the context. Use for any manifest mutation: the
    orchestrator launch loop's count-then-mark step, the
    collector retry path's PENDING→RUNNING transition, the
    watchdog's state updates. Holding briefly per-mutation (NOT
    across slow operations like subprocess spawn or collect)
    avoids the same-process recursion risk from 172 FINDING-1.
    """
    import fcntl as _fcntl
    lock_path = _manifest_lock_path(harness_run_dir)
    fp = open(lock_path, "w", encoding="utf-8")
    try:
        _fcntl.flock(fp.fileno(), _fcntl.LOCK_EX)
        try:
            yield
        finally:
            try:
                _fcntl.flock(fp.fileno(), _fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        fp.close()


def _runner_in_flight_count(
        manifest: dict, runner: str) -> int:
    """v1.5.7 174: count manifest entries currently in-flight for
    this runner — replaces inflight_registry's per-provider
    tracking with per-plan manifest-state counting.

    "In-flight" includes both ACQUIRING (slot reserved, spawn in
    progress) and RUNNING (spawn completed, AI-CLI live). Both
    consume a pool slot.
    """
    count = 0
    for e in manifest.get("runs", []) or []:
        if e.get("runner") != runner:
            continue
        st = e.get("state")
        if st in ("ACQUIRING", "RUNNING"):
            count += 1
    return count


def _try_acquire_pool_slot(
        manifest_path: Path,
        runner: str,
        pool_size: int,
        run_index: int,
        started_at: str) -> bool:
    """v1.5.7 174: pool-only slot acquisition under
    ``.manifest.lock``. Atomically:

    1. Re-read manifest.
    2. Count RUNNING + ACQUIRING entries for ``runner``.
    3. If ``< pool_size``: mark the entry ``state="ACQUIRING"``
       + ``started_at`` (no pid yet — caller spawns next).
       Return True.
    4. Else: leave the entry as-is. Return False.

    Caller MUST follow up True with either:
      - ``_finalize_pool_slot_running(manifest_path, run_index,
        pid)`` after successful spawn, OR
      - ``_finalize_pool_slot_failed(manifest_path, run_index,
        reason)`` if spawn fails.

    Race-free pool-cap enforcement via the lock + the ACQUIRING
    sentinel: any concurrent launcher counts this entry as
    in-flight even before its pid is recorded.
    """
    harness_run_dir = manifest_path.parent
    with _with_manifest_lock(harness_run_dir):
        try:
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        in_flight = _runner_in_flight_count(manifest, runner)
        if in_flight >= pool_size:
            return False
        runs = manifest.get("runs", [])
        for i, e in enumerate(runs):
            if e.get("index") == run_index:
                runs[i] = {
                    **e,
                    "state": "ACQUIRING",
                    "started_at": started_at,
                }
                break
        manifest["runs"] = runs
        try:
            tmp = manifest_path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8")
            os.replace(tmp, manifest_path)
        except OSError:
            return False
        return True


def _finalize_pool_slot_running(
        manifest_path: Path, run_index: int,
        pid: int, extra: "Optional[dict]" = None) -> None:
    """v1.5.7 174: confirm ACQUIRING→RUNNING after a successful
    spawn. Records pid + any extra entry fields (target_dir,
    stream_path, etc.) the spawn produced. Under
    ``.manifest.lock``."""
    update = {"state": "RUNNING", "pid": int(pid)}
    if extra:
        update.update(extra)
    harness_run_dir = manifest_path.parent
    with _with_manifest_lock(harness_run_dir):
        _update_manifest_entry_no_lock(
            manifest_path, run_index, update)


def _finalize_pool_slot_failed(
        manifest_path: Path, run_index: int,
        reason: str) -> None:
    """v1.5.7 174: ACQUIRING→DONE+FAILED when spawn raises. Under
    ``.manifest.lock``."""
    update = {
        "state": "DONE",
        "terminal_state": "FAILED",
        "terminal_reason": reason,
        "ended_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
    }
    harness_run_dir = manifest_path.parent
    with _with_manifest_lock(harness_run_dir):
        _update_manifest_entry_no_lock(
            manifest_path, run_index, update)


def _update_manifest_entry_no_lock(
        manifest_path: Path, run_index: int,
        update: "dict") -> None:
    """v1.5.7 174: the locked body of
    ``_update_manifest_entry_atomic``. CALLER MUST HOLD
    ``.manifest.lock``. Used by helpers that already hold the
    lock for an atomic read-modify-write sequence."""
    try:
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8"))
        runs = manifest.get("runs", [])
        for i, e in enumerate(runs):
            if e.get("index") == run_index:
                runs[i] = {**e, **update}
                break
        manifest["runs"] = runs
        tmp = manifest_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8")
        os.replace(tmp, manifest_path)
    except OSError:
        pass


def _make_pending_manifest_entry(
        plan_run: "PlanRun",
        harness_run_dir: Path) -> dict:
    """v1.5.7 174: build a canonical PENDING manifest entry for
    one PlanRun. The pre-write step calls this for each entry
    BEFORE the launch loop; the launch loop later updates the
    entry in place (PENDING → ACQUIRING → RUNNING + pid → DONE
    + terminal_state).

    Carries all fields needed for the retry path's
    ``_entry_to_plan_run`` reconstruction (177 BUG-010 hardened
    the required-fields contract; this writer must include
    ref / runner / model / channel / mode AND the per-run path
    fields the collector/watchdog need)."""
    run_dir = harness_run_dir / f"run-{plan_run.index:02d}"
    target_dir = run_dir / "target"
    return {
        "index": plan_run.index,
        "description": plan_run.description,
        "repo": plan_run.repo,
        "ref": plan_run.ref,
        "runner": plan_run.runner.value,
        "model": plan_run.model,
        "channel": plan_run.channel.value,
        "mode": plan_run.mode.value,
        "target_dir": str(target_dir),
        "run_dir": str(run_dir),
        "run_id": f"r{plan_run.index}",
        "pid": None,
        "started_at": "",
        "stream_path": str(run_dir / "stream.ndjson"),
        "status_path": str(run_dir / "status.json"),
        "max_duration_s": float(
            plan_run.max_duration_s or 0.0),
        "expect": plan_run.expect,
        "state": "PENDING",
    }


def _prewrite_manifest_pending(
        plan: "Plan", harness_run_dir: Path) -> Path:
    """v1.5.7 174: write ``manifest.json`` BEFORE the orchestrator
    launch loop, with EVERY entry in state="PENDING". The launch
    loop then uses ``.manifest.lock`` + ``_try_acquire_pool_slot``
    to atomically count + transition entries to ACQUIRING (then
    spawn outside the lock + RUNNING under lock again).

    Single atomic write — no lock needed because nothing else is
    reading yet (the collector + watchdog are spawned AFTER the
    launch loop completes per the 174 ruling).

    Returns the manifest path."""
    manifest_path = harness_run_dir / "manifest.json"
    entries = [
        _make_pending_manifest_entry(pr, harness_run_dir)
        for pr in plan.runs
    ]
    relative_entries = [
        _relativize_manifest_entry(e, harness_run_dir)
        for e in entries
    ]
    manifest = {
        "harness_run_dir": str(harness_run_dir),
        "plan": {
            "pools": plan.pools,
        },
        "runs": relative_entries,
    }
    tmp = manifest_path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, manifest_path)
    return manifest_path


def _update_manifest_entry_atomic(
        manifest_path: Path, run_index: int,
        update: "dict") -> None:
    """v1.5.7 165: update a single manifest entry by index.

    v1.5.7 174: now acquires ``.manifest.lock`` around the
    read-modify-write so concurrent launch / retry / watchdog
    paths don't clobber each other. Best-effort on filesystem
    errors (the retry retries next cycle)."""
    harness_run_dir = manifest_path.parent
    try:
        with _with_manifest_lock(harness_run_dir):
            _update_manifest_entry_no_lock(
                manifest_path, run_index, update)
    except OSError:
        pass


def _entry_to_plan_run(entry: dict) -> "PlanRun":
    """v1.5.7 165: reconstruct a ``PlanRun`` from a PENDING
    manifest entry (the orchestrator's 161-A writer populates all
    the required fields). Used by the collector's retry loop to
    call ``_launch_one_run_detached``.

    v1.5.7 177 (BUG-010): the required fields are now ENFORCED at
    read time. Pre-177 every missing field silently defaulted
    (ref → "main", runner → "claude", model → "opus", channel →
    "clone", mode → "A"). The 161-A writer is responsible for
    setting all of them; a missing field is a data-integrity bug
    that must surface immediately rather than masquerade as the
    default and cause confusing downstream failures (e.g.
    `git switch main` against an `express/master` repo).

    Methodology: same shape as 170's `_assert_parseable_started_at`
    — enforce invariant at write site (161-A includes the field)
    + raise loudly at read site (no silent default). After 177 the
    "missing field" branch is unreachable for legitimate state.
    """
    from bin.harness.schema import (
        InstallChannel, Mode, Runner)
    required_fields = (
        "ref", "runner", "model", "channel", "mode",
    )
    missing = [f for f in required_fields if f not in entry]
    if missing:
        raise ValueError(
            f"manifest entry index={entry.get('index')} missing "
            f"required field(s) {missing}; the 161-A PENDING "
            f"writer must preserve them for the retry path. "
            f"Entry keys present: {sorted(entry.keys())}"
        )
    return PlanRun(
        index=int(entry.get("index", 0)),
        description=str(entry.get("description", "")),
        repo=str(entry.get("repo", "")),
        ref=str(entry["ref"]),
        runner=Runner(entry["runner"]),
        model=str(entry["model"]),
        channel=InstallChannel(entry["channel"]),
        mode=Mode(entry["mode"]),
        expect=dict(entry.get("expect", {}) or {}),
    )


def _retry_pending_runs_once(
        harness_run_dir: Path,
        log: "Optional[_ProgressLog]" = None,
        ) -> int:
    """v1.5.7 165 Tasks A+B: ONE pass of the collector's PENDING-
    retry loop. For each PENDING entry:

    1. Check the deadline: if ``starved_since`` is older than
       ``_pending_deadline_s()`` → mark ``ABANDONED_STARVED`` and
       move on.
    2. Otherwise try ``acquire_run_slot(max_wait_s=5.0)``. On
       success, call ``_launch_one_run_detached`` and update the
       manifest entry IN PLACE with the spawned run's fields.
       On TimeoutError, mark ``starved_since`` if not already
       set and continue. On launch failure, mark the entry
       terminal as ``FAILED`` (don't retry forever on broken
       artifacts).

    Returns the number of state transitions (spawned + abandoned +
    failed) in this pass — caller uses it as a "made progress"
    signal for the multi-pass collector loop. The collector's
    existing parallel-collect path then handles the newly-RUNNING
    entries on its next sweep."""
    manifest_path = harness_run_dir / "manifest.json"
    if not manifest_path.is_file():
        return 0
    try:
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    pending_entries = [
        e for e in manifest.get("runs", [])
        if e.get("state") == "PENDING"
        and e.get("pid") is None
    ]
    if not pending_entries:
        return 0
    plan_pools = manifest.get("plan", {}).get("pools", {}) or {}
    # Per-provider cap: re-derive at retry time. None → use the
    # registry's default behavior (matches the orchestrator's
    # behavior when --max-per-provider isn't passed).
    max_per_provider = manifest.get(
        "plan", {}).get("max_per_provider") or {}
    artifact_map = _resolve_artifact_map_from_disk(
        harness_run_dir)
    deadline_s = _pending_deadline_s()
    now = datetime.now(timezone.utc)
    transitions = 0
    for pending in pending_entries:
        pr = _entry_to_plan_run(pending)
        plan_pool_cap = plan_pools.get(pr.runner.value)
        run_dir = harness_run_dir / Path(
            pending.get("run_dir", "")).name
        target_dir = run_dir / "target"
        # 165 Task B: deadline check.
        starved_since = pending.get("starved_since")
        if starved_since:
            try:
                ts = datetime.fromisoformat(
                    starved_since.replace("Z", "+00:00"))
            except ValueError:
                ts = None
            if (ts is not None
                    and (now - ts).total_seconds() > deadline_s):
                _update_manifest_entry_atomic(
                    manifest_path, pr.index, {
                        "state": "DONE",
                        "terminal_state": "ABANDONED_STARVED",
                        "terminal_reason":
                            f"PENDING for "
                            f"{(now - ts).total_seconds():.0f}s "
                            f"(deadline {deadline_s:.0f}s) — "
                            f"abandoned",
                        "ended_at": now.strftime(
                            "%Y-%m-%dT%H:%M:%SZ"),
                    })
                if log is not None:
                    log.log(
                        f"abandoned starved run: "
                        f"run-{pr.index:02d}")
                transitions += 1
                continue
        # 165 Task A: try to acquire a slot.
        try:
            from bin.harness import inflight_registry as _inflight
            _inflight.acquire_run_slot(
                runner=pr.runner.value,
                harness_run_dir=harness_run_dir,
                run_index=pr.index,
                started_at=now.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"),
                max_per_provider=max_per_provider,
                plan_pool_cap=plan_pool_cap,
                max_wait_s=5.0,
            )
        except TimeoutError:
            # Still starved; set starved_since on first observation.
            if pending.get("starved_since") is None:
                _update_manifest_entry_atomic(
                    manifest_path, pr.index, {
                        "starved_since": now.strftime(
                            "%Y-%m-%dT%H:%M:%SZ"),
                    })
            continue
        # Slot acquired — spawn the worker.
        try:
            entry = _launch_one_run_detached(
                pr, harness_run_dir, run_dir, target_dir,
                artifact_map=artifact_map,
                local_artifact_info=artifact_map.get(
                    pr.channel.value),
                log=log,
                tag=None,
            )
            _update_manifest_entry_atomic(
                manifest_path, pr.index, entry)
            # BUG-002 fix: record the real PID so the pid=0 reservation made
            # by acquire_run_slot above is converted before it ages out at
            # _PID_ZERO_MAX_AGE_S (300s). Without this the slot frees while
            # the retry-spawned run is still alive and the per-provider cap
            # is exceeded — matching the orchestrator launch path (3078).
            _retry_pid = entry.get("pid")
            if _retry_pid is not None:
                _inflight.update_pid(
                    harness_run_dir=harness_run_dir,
                    run_index=pr.index, pid=int(_retry_pid))
            if log is not None:
                log.log(
                    f"retried starved run: "
                    f"run-{pr.index:02d} ⇒ spawned "
                    f"pid={entry.get('pid')}")
            transitions += 1
        except BaseException as exc:
            # Launch failed — terminal FAILED, release the slot
            # so it doesn't leak.
            _update_manifest_entry_atomic(
                manifest_path, pr.index, {
                    "state": "DONE",
                    "terminal_state": "FAILED",
                    "terminal_reason":
                        f"relaunch failed: {exc!r}",
                    "ended_at": now.strftime(
                        "%Y-%m-%dT%H:%M:%SZ"),
                })
            try:
                from bin.harness import inflight_registry as _ir
                _ir.release_run_slot(
                    harness_run_dir=harness_run_dir,
                    run_index=pr.index)
            except Exception:
                pass
            transitions += 1
    return transitions


def collect_harness_run(harness_run_dir: Path,
                          log: "Optional[_ProgressLog]" = None,
                          ) -> "list[RunOutcome]":
    """v1.5.7 108: the detached collector entry point. Reads
    ``<harness-run>/manifest.json``, iterates every entry,
    collects each non-finished run (polling its PID +
    grading), rewrites ``SUMMARY.md`` incrementally, and
    returns the final list of outcomes.

    Idempotent: re-running over a harness-run with all runs
    already collected is a no-op for each (the per-run helper
    short-circuits when ``grading.json`` is present). Invoked
    by ``qpb_harness collect <dir>`` and auto-spawned by
    ``run_plan`` in production mode.
    """
    manifest_path = harness_run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"collect_harness_run: no manifest.json at "
            f"{manifest_path}"
        )
    # v1.5.7 172: acquire <harness-run>/.collect.lock so the 172
    # watchdog and the original collector can't race on manifest /
    # SUMMARY writes. Lock is fcntl.flock-based (POSIX) and held for
    # the function's lifetime; release via FD close on return. The
    # watchdog acquires LOCK_EX|LOCK_NB and skips a tick if held;
    # the collector takes blocking LOCK_EX since it's the primary
    # writer. If the collector dies, the OS releases the lock (FD
    # close) and the watchdog's next tick can recovery-collect.
    import fcntl as _fcntl  # local: keep top-of-file imports POSIX-agnostic
    _collect_lock_path = harness_run_dir / ".collect.lock"
    _collect_lock_fp = open(_collect_lock_path, "w",
                              encoding="utf-8")
    try:
        _fcntl.flock(_collect_lock_fp.fileno(), _fcntl.LOCK_EX)
    except OSError:
        _collect_lock_fp.close()
        raise
    try:
        return _collect_harness_run_locked(
            harness_run_dir, manifest_path, log)
    finally:
        try:
            _fcntl.flock(_collect_lock_fp.fileno(),
                          _fcntl.LOCK_UN)
        except OSError:
            pass
        _collect_lock_fp.close()


def _collect_harness_run_locked(
        harness_run_dir: Path,
        manifest_path: Path,
        log: "Optional[_ProgressLog]" = None,
        ) -> "list[RunOutcome]":
    """Body of :func:`collect_harness_run`. Runs INSIDE the v1.5.7
    172 collect lock — never call this directly; go through
    :func:`collect_harness_run`."""
    # v1.5.7 165 + 171: retry PENDING entries before the parallel
    # collect AND after each RUNNING future returns terminal (171
    # fix for BUG-008). 161-A wrote PENDING manifest entries for
    # starved runs; this gives them a chance to spawn into RUNNING
    # (or be marked ABANDONED_STARVED if past deadline) before the
    # collector grades them. 171 closes the gap where a slot freed
    # mid-collection (e.g., a fast claude/haiku run terminating
    # while a slow claude/opus run was still alive) left starved
    # PENDING entries orphaned because the retry only fired once
    # at entry. Now the retry fires on every RUNNING terminate
    # and newly-RUNNING entries are dynamically added to the
    # in-flight collect set.
    _retry_pending_runs_once(harness_run_dir, log)
    # Re-read manifest after the retry pass — newly-spawned
    # entries have RUNNING state + a pid we need.
    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8"))
    outcomes: list[RunOutcome] = []
    collected_indices: "set[int]" = set()
    pool_total = max(1, len(manifest.get("runs", [])))
    with ThreadPoolExecutor(max_workers=pool_total) as ex:
        futures: "dict[Future, int]" = {
            ex.submit(_collect_one_run_detached, entry,
                       harness_run_dir, log): entry["index"]
            for entry in manifest.get("runs", [])
        }
        while futures:
            done, _pending = wait(
                list(futures.keys()),
                return_when=FIRST_COMPLETED,
            )
            for f in done:
                idx = futures.pop(f)
                outcome = f.result()
                outcomes.append(outcome)
                # v1.5.7 172 (BUG-009 fix): only mark this index
                # 'collected' if the future returned a TERMINAL
                # outcome. BUG-001's PENDING shortcircuit (at
                # _collect_one_run_detached:2101-2111) returns
                # RunOutcome(terminal_state="PENDING"), which is
                # the collector's way of saying "still in flight;
                # defer judgment." Marking it collected here lets
                # the 171 dynamic-submit block skip a retry-spawned
                # future for the same index (`if idx in
                # collected_indices: continue`), so the run
                # completes silently without grading. Only true
                # terminal states count.
                if outcome.terminal_state != "PENDING":
                    collected_indices.add(idx)
            # v1.5.7 171 BUG-008 fix: a future just returned
            # terminal — a slot may have freed. Retry PENDING
            # entries; submit any newly-RUNNING ones for collection
            # on this same sweep so we don't lose them to the
            # operator-must-re-invoke trap that 165 fell into.
            transitions = _retry_pending_runs_once(
                harness_run_dir, log)
            if transitions:
                manifest = json.loads(
                    manifest_path.read_text(encoding="utf-8"))
                in_flight = set(futures.values())
                for entry in manifest.get("runs", []):
                    idx = entry.get("index")
                    if (idx in collected_indices
                            or idx in in_flight):
                        continue
                    # 171: a retry-spawned entry now has state
                    # RUNNING (165 launch path) or DONE (e.g.,
                    # ABANDONED_STARVED via deadline). Either way
                    # submit it so it gets graded on this sweep.
                    if entry.get("state") in ("RUNNING", "DONE"):
                        fut = ex.submit(
                            _collect_one_run_detached, entry,
                            harness_run_dir, log)
                        futures[fut] = idx
    # Final SUMMARY rewrite (idempotent — same outcomes
    # produce same SUMMARY).
    plan_for_summary = manifest.get("plan", {})
    if plan_for_summary:
        try:
            from bin.harness.schema import Mode as _Mode
            # Re-build a minimal Plan-like object just for the
            # summary table header.
            class _PoolStub:
                def __init__(self, pools: dict) -> None:
                    self.pools = pools
                    self.runs = []
            stub = _PoolStub(
                plan_for_summary.get("pools", {}))
            (harness_run_dir / "SUMMARY.md").write_text(
                render_summary(stub, outcomes),  # type: ignore[arg-type]
                encoding="utf-8",
            )
        except Exception:
            # Best-effort; the per-run receipts are the
            # authoritative artifacts.
            pass
    return outcomes


def _spawn_collector(harness_run_dir: Path,
                       log: "Optional[_ProgressLog]" = None,
                       ) -> int:
    """v1.5.7 108: spawn the detached collector subprocess.
    Anti-SIGTTIN: ``start_new_session=True`` + stdin from
    ``/dev/null`` + stdout/stderr to
    ``<harness-run>/collector.log``. Returns the collector's
    PID so run_plan can print it for the operator.
    """
    collector_log = harness_run_dir / "collector.log"
    cmd = [
        sys.executable, "-m", "bin.qpb_harness",
        "collect", str(harness_run_dir),
    ]
    log_fp = open(collector_log, "ab")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(_repo_root_for_collector()),
            stdout=log_fp,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    finally:
        log_fp.close()
    if log is not None:
        log.log(
            f"collector spawned (pid={proc.pid}); "
            f"log={collector_log}"
        )
    return proc.pid


def _spawn_watchdog(harness_run_dir: Path,
                      log: "Optional[_ProgressLog]" = None,
                      ) -> int:
    """v1.5.7 172: spawn the detached watchdog subprocess.
    Mirrors :func:`_spawn_collector` exactly — same anti-SIGTTIN
    pattern (start_new_session + stdin=/dev/null + stdout/stderr
    to ``<harness-run>/watchdog.log``). Returns the watchdog's PID
    so the launch banner can display it alongside the collector's.
    """
    watchdog_log = harness_run_dir / "watchdog.log"
    cmd = [
        sys.executable, "-m", "bin.qpb_harness",
        "watchdog", str(harness_run_dir),
    ]
    log_fp = open(watchdog_log, "ab")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(_repo_root_for_collector()),
            stdout=log_fp,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    finally:
        log_fp.close()
    if log is not None:
        log.log(
            f"watchdog spawned (pid={proc.pid}); "
            f"log={watchdog_log}"
        )
    return proc.pid


def _repo_root_for_collector() -> Path:
    """v1.5.7 108: the QPB clone root — the cwd the collector
    must run from so ``python -m bin.qpb_harness`` resolves."""
    # plan_runner.py lives at <root>/bin/harness/plan_runner.py.
    return Path(__file__).resolve().parents[2]


# v1.5.7 159: acquire_run_slot defensive timeout — read once per
# spawn so an operator can tune via env var without a re-import.
# Default 300s (5 min) matches the instruction's recommendation;
# operators who deliberately want long waits can bump it up, and
# tests can drop it to a fraction of a second.
_ACQUIRE_RUN_SLOT_TIMEOUT_DEFAULT_S = 300.0


def _acquire_run_slot_timeout_s() -> float:
    """v1.5.7 159: defensive timeout for ``acquire_run_slot``.
    Default 300s; operator-tunable via ``QPB_HARNESS_ACQUIRE_TIMEOUT_S``.
    A non-numeric / non-positive value falls back to the default."""
    raw = os.environ.get("QPB_HARNESS_ACQUIRE_TIMEOUT_S")
    if raw is None:
        return _ACQUIRE_RUN_SLOT_TIMEOUT_DEFAULT_S
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return _ACQUIRE_RUN_SLOT_TIMEOUT_DEFAULT_S
    return v if v > 0 else _ACQUIRE_RUN_SLOT_TIMEOUT_DEFAULT_S


def _install_orchestrator_signal_handlers() -> None:
    """v1.5.7 155: ignore SIGHUP so the orchestrator survives the
    operator's launching shell closing (session-leader exit
    propagates SIGHUP to processes in the session — the orchestrator
    inherits that signal otherwise). Idempotent: calling multiple
    times is safe.

    The original 155 instruction proposed also calling ``os.setsid()``
    early as defense in depth. Deferred per the ruling's "worker's
    call; SIGHUP-IGN alone is sufficient" — adding setsid here would
    detach the process from the controlling terminal AT IMPORT TIME
    if a test imports plan_runner, breaking pytest output capture.
    Operators who want full session detachment should use the
    documented bridge: ``nohup python3 -m bin.qpb_harness <plan.json>
    > /tmp/log 2>&1 & disown``.

    See ``reviews/155-orchestrator-sighup-resilience-HALT-RULING.md``
    for the 5-zombie-wave diagnosis (start_new_session already in
    place at every Popen site; stdio already file-redirected; the
    SIGPIPE-via-inherited-TTY hypothesis ruled out by code reading)."""
    try:
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
    except (ValueError, OSError):
        # SIGHUP not available on this platform (Windows) or we're
        # in a thread without signal-handling privilege. Either way
        # the call is best-effort; no-op gracefully.
        pass


def run_plan(plan: Plan, harness_runs_root: Path,
              hooks: "Optional[PlanRunnerHooks]" = None,
              *,
              builder: "Optional[BuilderHooks]" = None,
              wheel_override: "Optional[Path]" = None,
              tgz_override: "Optional[Path]" = None,
              detach: bool = True,
              max_per_provider: "Optional[dict[str, int]]" = None,
              ) -> "list[RunOutcome]":
    """Execute a parsed Plan end-to-end. Returns the list of
    RunOutcomes in plan-array order.

    Creates a timestamped harness-run subdir under
    ``harness_runs_root``, builds the local artifacts the plan
    needs into ``<harness-run>/artifacts/``, copies ``plan.json``
    in, launches the runs in parallel gated by ``pools``, writes
    per-run receipts + the root ``SUMMARY.md``.

    v1.5.7 101 build step:
      * Runs ONCE per harness run, BEFORE any per-run launches.
      * ``builder`` injects test mocks for wheel/tgz build
        callables (production omits → default_build_* would
        raise NotImplementedError for live runs, matching the
        099 halt-condition pattern).
      * ``wheel_override`` / ``tgz_override`` copy a pre-built
        artifact into the harness-run folder instead of
        building. Default (overrides absent) is build-fresh.
      * On BuildError, the exception propagates — NO per-run
        folders are created, NO SUMMARY.md is written. The empty
        ``<harness-run>/artifacts/`` is the forensic trail of
        what was attempted.
    """
    # v1.5.7 155 Task A: ignore SIGHUP so closing the launching
    # shell doesn't take the orchestrator with it. Children are
    # already spawned with start_new_session=True at every Popen
    # site (runner.py:925, plan_runner.py:2378) and their stdio
    # is file-redirected (not inherited from the parent's TTY),
    # so SIGHUP-IGN on the orchestrator alone closes the
    # walk-away-able gap.
    _install_orchestrator_signal_handlers()

    hooks = hooks or PlanRunnerHooks()
    harness_runs_root.mkdir(parents=True, exist_ok=True)
    # v1.5.7 158 (revised): when the auto-detach parent process set
    # QPB_HARNESS_FORCED_RUN_ID, use that timestamp so the parent's
    # banner (printed BEFORE the fork) names the same harness-run
    # dir the child creates. Otherwise generate fresh.
    forced_id = os.environ.get("QPB_HARNESS_FORCED_RUN_ID")
    harness_run_dir = (harness_runs_root / forced_id if forced_id
                       else harness_runs_root / _utc_now_run_id())
    harness_run_dir.mkdir(parents=True, exist_ok=False)

    # v1.5.7 104: progress logger — stderr + harness.log
    # (per-run log added when each run-NN dir is created).
    log = _ProgressLog(harness_run_dir)
    log.log(f"harness-run dir = {harness_run_dir}")
    log.log(f"plan: {len(plan.runs)} runs, "
            f"pools={plan.pools}")

    # v1.5.7 101: build the local artifacts BEFORE any runs
    # launch. BuildError propagates — no run-dirs, no SUMMARY.md;
    # the empty `<harness-run>/artifacts/` (or no artifacts/ at
    # all when the plan needs no local builds) is the forensic
    # trail of what was attempted.
    needed_channels = _required_local_channels(plan)
    if needed_channels:
        log.log(
            f"build artifacts "
            f"({sorted(c.value for c in needed_channels)})"
        )
    artifact_map = build_artifacts(
        harness_run_dir, plan,
        builder=builder,
        wheel_override=wheel_override,
        tgz_override=tgz_override,
    )
    if needed_channels:
        log.log("build artifacts complete")

    # Copy plan.
    (harness_run_dir / "plan.json").write_text(
        json.dumps({
            "pools": plan.pools,
            "runs": [{
                "description": r.description,
                "repo": r.repo, "ref": r.ref,
                "runner": r.runner.value, "model": r.model,
                "channel": (
                    f"{r.channel.value}@{r.install_version}"
                    if r.install_version else r.channel.value
                ),
                "prep": r.prep, "docs": r.docs,
                "expect": r.expect,
                # v1.5.7 100: persist parameters when present so
                # the run is reproducible; omit when empty to
                # keep round-trips of pre-100 plans byte-stable.
                **({"parameters": r.parameters}
                   if r.parameters else {}),
                # v1.5.7 106: persist mode + max_duration_s only
                # when non-default; absent fields keep pre-106
                # plan files round-trip byte-stable.
                **({"mode": r.mode.value}
                   if r.mode != Mode.A else {}),
                **({"max_duration_s": r.max_duration_s}
                   if r.max_duration_s is not None else {}),
                # v1.5.7 107: persist workspace_root only when
                # set; absent keeps pre-107 plans byte-stable.
                **({"workspace_root": r.workspace_root}
                   if r.workspace_root is not None else {}),
                # v1.5.7 106 (fix): persist per-run prompt
                # override only when set; absent keeps pre-106
                # plans byte-stable.
                **({"prompt": r.prompt}
                   if r.prompt is not None else {}),
                # v1.5.7 138: persist prep_timeout_s only when
                # set; absent keeps pre-138 plans byte-stable.
                **({"prep_timeout_s": r.prep_timeout_s}
                   if r.prep_timeout_s is not None else {}),
            } for r in plan.runs],
        }, indent=2) + "\n",
        encoding="utf-8",
    )

    gate = _PoolGate(plan.pools)
    pool_total = max(1, sum(plan.pools.values())) if plan.pools else len(plan.runs)
    pool_total = min(pool_total, len(plan.runs)) or 1

    # v1.5.7 108: branch on hooks.fake_run AND the explicit
    # `detach` parameter.
    #   * fake_run set OR detach=False: synchronous flow —
    #     launches + grades inline. Used by tests + the
    #     existing direct-call paths. ``detach=False`` is the
    #     opt-out used by tests that exercise the live
    #     composition end-to-end without spawning a real
    #     collector subprocess.
    #   * fake_run None AND detach=True (production default):
    #     detached flow — launches all AI-CLIs without waiting,
    #     writes manifest.json, spawns the detached collector
    #     subprocess (anti-SIGTTIN per 108), and returns
    #     RUNNING placeholder outcomes. The collector runs
    #     facts + grade + SUMMARY out of the blocking path.
    # v1.5.7 125: resolve the global per-provider cap from
    # the operator's spec (CLI/env), merged with the
    # conservative defaults in inflight_registry. Threaded
    # through to the detached path so the registry's
    # acquire_run_slot enforces both per-plan pool caps AND
    # the global per-provider cap under one lock.
    from bin.harness import inflight_registry as _inflight
    effective_max_per_provider = (
        max_per_provider
        if max_per_provider is not None
        else _inflight.parse_max_per_provider_spec(
            os.environ.get(
                "QPB_HARNESS_MAX_PER_PROVIDER"))
    )

    if hooks.fake_run is not None or not detach:
        return _run_plan_synchronous(
            plan, harness_run_dir, hooks, artifact_map,
            gate, pool_total, log,
        )
    return _run_plan_detached(
        plan, harness_run_dir, artifact_map, gate, pool_total,
        log, effective_max_per_provider,
    )


def _run_plan_synchronous(
        plan: Plan, harness_run_dir: Path,
        hooks: PlanRunnerHooks,
        artifact_map: "dict[InstallChannel, dict]",
        gate: "_PoolGate", pool_total: int,
        log: "_ProgressLog",
) -> "list[RunOutcome]":
    """The pre-108 synchronous flow — launch + grade each run
    inline via ``_execute_one_run``. Used when ``hooks.fake_run``
    is set (the test fast-path) so existing 099-107 tests keep
    working unchanged.
    """
    outcomes: list[Optional[RunOutcome]] = [None] * len(plan.runs)

    def _wrapped(idx: int) -> None:
        pr = plan.runs[idx]
        gate.acquire(pr.runner.value)
        try:
            outcomes[idx] = _execute_one_run(
                pr, harness_run_dir, hooks,
                artifact_map=artifact_map,
                log=log,
            )
        finally:
            gate.release(pr.runner.value)

    with ThreadPoolExecutor(max_workers=pool_total) as ex:
        futures = [ex.submit(_wrapped, i)
                   for i in range(len(plan.runs))]
        for f in futures:
            f.result()
    result: list[RunOutcome] = [o for o in outcomes if o is not None]
    (harness_run_dir / "SUMMARY.md").write_text(
        render_summary(plan, result), encoding="utf-8",
    )
    met = sum(1 for o in result if o.result == "MET")
    log.log(
        f"all runs complete: {met}/{len(result)} MET — "
        f"SUMMARY={harness_run_dir / 'SUMMARY.md'}"
    )
    return result


def _run_plan_detached(
        plan: Plan, harness_run_dir: Path,
        artifact_map: "dict[InstallChannel, dict]",
        gate: "_PoolGate", pool_total: int,
        log: "_ProgressLog",
        max_per_provider: "Optional[dict[str, int]]" = None,
) -> "list[RunOutcome]":
    """v1.5.7 108: the new detached/collector flow. Launches
    every run via ``_launch_one_run_detached`` (parallel,
    gated by ``pools``), writes ``manifest.json`` at the
    harness-run root with each run's PID, auto-spawns the
    fully-detached collector subprocess, and returns RUNNING
    placeholder outcomes. The collector runs facts + grade +
    SUMMARY out of the blocking path.

    v1.5.7 174: replaces the pre-174 file-backed
    ``inflight_registry`` with manifest-based per-plan pool
    tracking. Pre-writes manifest.json with all entries in
    state="PENDING" BEFORE the launch loop; each launch thread
    then uses ``_try_acquire_pool_slot`` (which takes
    ``.manifest.lock``) to atomically count + transition to
    ACQUIRING + spawn + finalize RUNNING. Starved entries are
    left as PENDING; the 165 retry path picks them up when
    slots free. ``max_per_provider`` is accepted for back-
    compat with pre-174 callers but is now IGNORED — per-plan
    pools are the only concurrency knob.
    """
    # v1.5.7 174: pre-write manifest.json with all entries in
    # PENDING state. The launch loop atomically transitions
    # each entry through PENDING → ACQUIRING → RUNNING.
    manifest_path = _prewrite_manifest_pending(
        plan, harness_run_dir)

    def _wrapped(idx: int) -> None:
        pr = plan.runs[idx]
        run_dir = harness_run_dir / f"run-{pr.index:02d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        target_dir = run_dir / "target"
        local_artifact_info = artifact_map.get(pr.channel)
        # v1.5.7 101: per-run artifact_used.json (mirrors the
        # synchronous path so the receipt set is uniform
        # regardless of which flow ran).
        if local_artifact_info is not None:
            (run_dir / "artifact_used.json").write_text(
                json.dumps({
                    "channel": pr.channel.value,
                    **local_artifact_info,
                }, indent=2) + "\n", encoding="utf-8",
            )
        # v1.5.7 174: per-plan pool size is the ONLY concurrency
        # knob. Missing runner ⇒ default pool=1 (safe-by-default).
        plan_pool_size = (plan.pools.get(pr.runner.value, 1)
                            if plan.pools else 1)
        started_at_iso = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        # v1.5.7 174: pool-only acquisition. Fast non-blocking
        # check under .manifest.lock — if at capacity, leave the
        # entry as PENDING for the 165 retry path to pick up
        # when slots free. No 300s waits. The launch loop
        # completes in seconds; orchestrator detaches
        # immediately. Obsoletes 159's defensive timeout.
        acquired = _try_acquire_pool_slot(
            manifest_path,
            runner=pr.runner.value,
            pool_size=plan_pool_size,
            run_index=pr.index,
            started_at=started_at_iso,
        )
        if not acquired:
            log.log(
                f"pool full: run-{pr.index:02d} "
                f"({pr.runner.value}) — pool_size="
                f"{plan_pool_size}; left PENDING for retry"
            )
            # v1.5.7 174: entry stays PENDING in the pre-written
            # manifest. The 165 retry path inside the collector
            # picks it up when a slot frees (or marks
            # ABANDONED_STARVED past the deadline).
            return
        # v1.5.7 174: ACQUIRING was set by _try_acquire_pool_slot
        # under .manifest.lock. Now spawn the run OUTSIDE the
        # lock (slow operation), then finalize the entry to
        # RUNNING+pid (or DONE+FAILED on failure) under the
        # lock again.
        try:
            entry = _launch_one_run_detached(
                pr, harness_run_dir, run_dir, target_dir,
                artifact_map=artifact_map,
                local_artifact_info=local_artifact_info,
                log=log,
                tag=_run_tag(pr),
            )
            if entry is not None:
                pid_val = entry.get("pid")
                # Relativize the spawn-time entry fields so the
                # manifest stays portable per 118.
                rel_entry = _relativize_manifest_entry(
                    entry, harness_run_dir)
                # Strip the fields we don't want to overwrite
                # (state + started_at were set by the launch
                # helper; we want our own RUNNING + the
                # ACQUIRING-time started_at).
                extra = {
                    k: v for k, v in rel_entry.items()
                    if k not in (
                        "index", "state", "pid",
                        "started_at")
                }
                if pid_val is not None:
                    _finalize_pool_slot_running(
                        manifest_path, pr.index,
                        int(pid_val), extra=extra)
                else:
                    # No pid returned (ABORTED_PREP path) —
                    # mark terminal so the collector grades.
                    extra["terminal_state"] = (
                        rel_entry.get("terminal_state")
                        or "ABORTED_PREP")
                    extra["state"] = "DONE"
                    _update_manifest_entry_atomic(
                        manifest_path, pr.index, extra)
        except BaseException as exc:
            # Spawn raised — finalize as DONE+FAILED so the
            # entry doesn't sit ACQUIRING forever (which would
            # consume a pool slot from the retry path's count).
            _finalize_pool_slot_failed(
                manifest_path, pr.index,
                f"launch raised: {exc!r}")
            raise

    with ThreadPoolExecutor(max_workers=pool_total) as ex:
        futures = [ex.submit(_wrapped, i)
                   for i in range(len(plan.runs))]
        for f in futures:
            f.result()
    # v1.5.7 174: manifest.json was pre-written by
    # _prewrite_manifest_pending and updated incrementally
    # under .manifest.lock by each launch thread. No final
    # write needed.
    log.log(
        f"launch loop complete; manifest at "
        f"{harness_run_dir / 'manifest.json'}"
    )

    # Spawn the detached collector (108 anti-SIGTTIN:
    # start_new_session + stdin=/dev/null + stdout/stderr to
    # collector.log). The collector is a separate Python
    # subprocess that runs `qpb_harness collect <dir>`.
    collector_pid = _spawn_collector(harness_run_dir, log)
    # v1.5.7 172: spawn the watchdog daemon alongside the
    # collector. Safety net for collector-side accounting bugs
    # (165/171/etc.). Same anti-SIGTTIN pattern; runs
    # `qpb_harness watchdog <dir>` and exits cleanly when all
    # runs reach terminal state.
    watchdog_pid = _spawn_watchdog(harness_run_dir, log)

    # Return RUNNING placeholders so the CLI can print a
    # rollup (or so a future programmatic caller can see
    # which runs were launched).
    # v1.5.7 174: re-read the (now pre-written + incrementally
    # updated) manifest to build the placeholders. Skip entries
    # that ended up DONE+FAILED at launch (the collector grades
    # them N/A from the manifest).
    placeholders: list[RunOutcome] = []
    try:
        on_disk = json.loads(
            manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        on_disk = {"runs": []}
    for entry in on_disk.get("runs", []):
        placeholders.append(RunOutcome(
            index=entry["index"],
            description=entry.get("description", ""),
            repo=entry.get("repo", ""),
            runner=entry.get("runner", ""),
            model=entry.get("model", ""),
            phase_yn={f"P{i}": "-" for i in range(7)},
            gate_verdict="(running)",
            result="(running)",
            terminal_state=entry.get(
                "terminal_state", entry.get("state", "RUNNING")
            ),
        ))
    # Surface the collector PID to the caller via a module-
    # level attribute (the CLI reads this). Cleaner than
    # adding a return-tuple that would break existing
    # callers.
    log.log(
        f"detached: returning {len(placeholders)} RUNNING "
        f"placeholders; collector pid={collector_pid} "
        f"watchdog pid={watchdog_pid}"
    )
    _LAST_COLLECTOR_PID["pid"] = collector_pid
    _LAST_WATCHDOG_PID["pid"] = watchdog_pid
    return placeholders


# v1.5.7 108: the CLI reads this after run_plan in detached
# mode to print "collector pid <N>" for the operator. Module-
# level so it survives the return + doesn't pollute the
# RunOutcome dataclass shape.
_LAST_COLLECTOR_PID: "dict[str, int]" = {}
# v1.5.7 172: companion to _LAST_COLLECTOR_PID — CLI banner reads
# this to display the watchdog's pid alongside the collector's.
_LAST_WATCHDOG_PID: "dict[str, int]" = {}


# ---------------------------------------------------------------------------
# SUMMARY.md rendering
# ---------------------------------------------------------------------------


def render_summary(plan: Plan,
                    outcomes: "list[RunOutcome]") -> str:
    """Render the run_playbook-style table per the design's
    SIMPLIFIED RUNNER MODEL section.

    Columns: # · description · repo · runner · model · P0..P6 Y/N ·
    gate · result. Rollup line: ``=> N/M MET — acceptance
    PASSED|FAILED``.
    """
    lines: list[str] = []
    lines.append("# Harness Run Summary")
    lines.append("")
    # Header row.
    header = (
        f"{'#':<3} {'description':<40} {'repo':<10} "
        f"{'runner':<8} {'model':<10} "
        f"{'P0':<3}{'P1':<3}{'P2':<3}{'P3':<3}"
        f"{'P4':<3}{'P5':<3}{'P6':<3} "
        f"{'gate':<10} {'result':<8}"
    )
    lines.append("```")
    lines.append(header)
    for o in outcomes:
        desc = (o.description[:37] + "...") if len(o.description) > 40 else o.description
        repo = (o.repo[:7] + "...") if len(o.repo) > 10 else o.repo
        model = (o.model[:7] + "...") if len(o.model) > 10 else o.model
        marker = {"MET": "✓ MET", "NOT-MET": "✗ NOT",
                   "N/A": "N/A"}.get(o.result, o.result)
        row = (
            f"{o.index:<3} {desc:<40} {repo:<10} "
            f"{o.runner:<8} {model:<10} "
            + "".join(f"{o.phase_yn.get(f'P{i}', '-'):<3}"
                      for i in range(7))
            + f" {o.gate_verdict:<10} {marker:<8}"
        )
        lines.append(row)
    lines.append("```")
    lines.append("")
    met = sum(1 for o in outcomes if o.result == "MET")
    total = len(outcomes)
    acceptance = ("PASSED" if met == total and total > 0
                  else "FAILED")
    lines.append(
        f"=> {met}/{total} MET — acceptance {acceptance}"
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "PlanError",
    "BuildError",
    "PlanRun",
    "Plan",
    "RunOutcome",
    "PlanRunnerHooks",
    "BuilderHooks",
    "parse_plan",
    "load_plan",
    "grade_expect",
    "capture_phase_yn",
    "run_plan",
    "render_summary",
    "build_artifacts",
    "_PoolGate",
    "_ProgressLog",
    "_execute_one_run",
    "_execute_one_run_production",
    "_is_workspace_prepared",
    "_required_local_channels",
    "_resolve_workspace_sha",
    "_run_tag",
    # v1.5.7 108 — detach + collector
    "_LAST_COLLECTOR_PID",
    "_collect_one_run_detached",
    "_launch_one_run_detached",
    "_pid_is_alive",
    "_spawn_collector",
    "collect_harness_run",
]
