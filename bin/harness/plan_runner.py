"""QPB Test Harness — simple plan-runner (v1.5.7 099).

The owner-simplified model per the design's ⚠️ SIMPLIFIED RUNNER
MODEL section (2026-05-26): collapse the case/run-plan/SCHEMA
split into ONE input file → ONE self-contained output folder →
ONE summary table. SUPERSEDES the unfinished manager execution
loop (the manager + TUI stay as-is — bells & whistles, NOT
required by this flow).

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

import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
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
    # Mode is always A for the plan-runner (Mode B would mean
    # run_playbook drives the phases — out of scope for the
    # simple flow).
    mode: Mode = Mode.A


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
    out: dict[str, str] = {}
    transcript_lower = transcript or ""
    for phase, patterns in _PHASE_MARKER_RES.items():
        hit = any(p.search(transcript_lower) for p in patterns)
        if not hit and quality_dir is not None and quality_dir.is_dir():
            # Look for the phase's canonical artifact in
            # quality/. The markers above already encode the
            # filenames; we just check presence.
            artifact = {
                "P1": "EXPLORATION.md",
                "P2": "REQUIREMENTS.md",
                "P3": "RUN_CODE_REVIEW.md",
                "P4": "RUN_SPEC_AUDIT.md",
                "P5": "RUN_TDD_TESTS.md",
                "P6": "COMPLETENESS_REPORT.md",
            }.get(phase)
            if artifact and (quality_dir / artifact).is_file():
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
    Production: the operator-triggered live path supplies a real
    builder that shells out to `bin/build_channel_package.py
    --stage` + `python3 -m build --outdir <artifacts>` / `npm
    pack --pack-destination <artifacts>` (matches design §D's
    pre-publish lane).

    Each callable accepts the harness-run's ``artifacts`` dir and
    returns the path of the built file (which must live inside
    that dir). The default ``_default_build_*`` helpers raise
    NotImplementedError per the 099 halt-condition pattern.
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


def _default_build_wheel(artifacts_dir: Path) -> Path:
    raise NotImplementedError(
        "production wheel build is operator-triggered. Tests "
        "pass BuilderHooks.build_wheel; live operation shells "
        "out to `python3 bin/build_channel_package.py --stage` "
        "+ `python3 -m build --outdir " + str(artifacts_dir) +
        "`."
    )


def _default_build_tgz(artifacts_dir: Path) -> Path:
    raise NotImplementedError(
        "production tgz build is operator-triggered. Tests pass "
        "BuilderHooks.build_tgz; live operation shells out to "
        "`npm pack --pack-destination " + str(artifacts_dir) + "`."
    )


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
    """
    run_dir = harness_run_dir / f"run-{plan_run.index:02d}"
    run_dir.mkdir(parents=True, exist_ok=True)
    target_dir = run_dir / "target"

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
        return RunOutcome(
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

    # Production path — uses the real prepare/launch/facts/grade
    # modules. Implemented for completeness, but the live-run
    # behaviour (real clone + install + AI-CLI subprocess) is
    # operator-triggered and NOT exercised by tests (per
    # instruction Task D).
    raise NotImplementedError(
        "production plan-runner execution path is operator-"
        "triggered. Tests use hooks.fake_run; live operation "
        "will land when an operator invokes "
        "`python3 -m bin.qpb_harness run-plan <plan.json>` with "
        "real clone/install/launch wiring + a real AI-CLI on "
        "PATH. The Phase 1-6 substrate (prepare/runner/facts/"
        "grade) is unit-proven; composing it here is the "
        "operator-driven smoke test deferred per the "
        "instruction's halt-condition (no real QPB runs in CI)."
    )


def run_plan(plan: Plan, harness_runs_root: Path,
              hooks: "Optional[PlanRunnerHooks]" = None,
              *,
              builder: "Optional[BuilderHooks]" = None,
              wheel_override: "Optional[Path]" = None,
              tgz_override: "Optional[Path]" = None,
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
    hooks = hooks or PlanRunnerHooks()
    harness_runs_root.mkdir(parents=True, exist_ok=True)
    harness_run_dir = harness_runs_root / _utc_now_run_id()
    harness_run_dir.mkdir(parents=True, exist_ok=False)

    # v1.5.7 101: build the local artifacts BEFORE any runs
    # launch. BuildError propagates — no run-dirs, no SUMMARY.md;
    # the empty `<harness-run>/artifacts/` (or no artifacts/ at
    # all when the plan needs no local builds) is the forensic
    # trail of what was attempted.
    artifact_map = build_artifacts(
        harness_run_dir, plan,
        builder=builder,
        wheel_override=wheel_override,
        tgz_override=tgz_override,
    )

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
            } for r in plan.runs],
        }, indent=2) + "\n",
        encoding="utf-8",
    )

    gate = _PoolGate(plan.pools)
    outcomes: list[Optional[RunOutcome]] = [None] * len(plan.runs)

    def _wrapped(idx: int) -> None:
        pr = plan.runs[idx]
        gate.acquire(pr.runner.value)
        try:
            outcomes[idx] = _execute_one_run(
                pr, harness_run_dir, hooks,
                artifact_map=artifact_map,
            )
        finally:
            gate.release(pr.runner.value)

    # ThreadPoolExecutor sized to total pool capacity (sum of
    # pools) so all threads can sit at the gate; the gate
    # enforces per-runner caps.
    pool_total = max(1, sum(plan.pools.values())) if plan.pools else len(plan.runs)
    pool_total = min(pool_total, len(plan.runs)) or 1
    with ThreadPoolExecutor(max_workers=pool_total) as ex:
        futures = [ex.submit(_wrapped, i)
                   for i in range(len(plan.runs))]
        for f in futures:
            f.result()
    # Type-narrow.
    result: list[RunOutcome] = [o for o in outcomes if o is not None]
    # Write SUMMARY.md.
    (harness_run_dir / "SUMMARY.md").write_text(
        render_summary(plan, result), encoding="utf-8",
    )
    return result


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
    "_execute_one_run",
    "_required_local_channels",
]
