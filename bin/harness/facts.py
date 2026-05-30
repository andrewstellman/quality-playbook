"""QPB Test Harness — two-sourced fact extraction.

Per ``QPB_Test_Harness_1.5.7_Design.md`` §C / design §C/§5:

  * **Gate-derived facts** come from RE-RUNNING **the run's own
    installed ``quality_gate.py``** (NOT the dev clone's gate)
    over the run's final ``quality/`` artifacts, with the run's
    vendor env var set so the gate's runner detection is correct
    (see ``_RUNNER_ENV_MARKERS`` in ``quality_gate.py``).
  * **Live-behavior facts** are NOT in the artifacts; they come
    from the transcript / stream (``phase0_first_probe``,
    ``banner_rendered``, ``gitignore_remediation_followed``,
    ``blocked`` / ``stop_reason``).

Using the clone's gate would mis-grade a
``pip-registry@1.5.6`` comparison run with 1.5.7's verdict logic,
and could diverge from the verdict the run actually produced.
Pinning "installed gate" here is the load-bearing robustness
decision.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from bin.harness.schema import (
    Attribution,
    GateFacts,
    GateResult,
    InstallSurfaceFacts,
    Phase0Facts,
    ProvenanceFacts,
    RunAxes,
    RunFacts,
    RunMetaFacts,
    Runner,
    VerdictFacts,
    VerdictState,
    gate_result_from_raw,
)


class FactsError(RuntimeError):
    """Fact extraction failed in a way the harness can't recover
    from (e.g. the installed ``quality_gate.py`` is missing from
    the target). Distinct from "fact unknown" — that case sets the
    field to a defensive default and the grader treats it like
    any missing assertion target."""


# ---------------------------------------------------------------------------
# Locate the run's OWN installed quality_gate.py
# ---------------------------------------------------------------------------


# Same install-marker list QPB's installer uses (per
# ``bin/install_skill.py``). The harness searches these in order.
_INSTALL_MARKERS = (
    ".claude",
    ".github",
    ".cursor",
    ".codex",
)


def find_installed_gate(target_dir: Path) -> Path:
    """Locate the run's own installed ``quality_gate.py`` inside
    ``target_dir``. Searches the canonical install layouts:

      * ``<target>/<marker>/skills/quality-playbook/quality_gate.py``
        (install_skill.py-style)
      * ``<target>/.github/skills/quality_gate.py``
        (setup_repos.sh flat layout)
      * ``<target>/quality_gate.py`` (legacy top-level)

    Returns the first match. Raises ``FactsError`` if none exists —
    re-running an absent gate over the run's artifacts is the kind
    of silent miscalibration this layer was designed to prevent.
    """
    candidates: list[Path] = []
    for marker in _INSTALL_MARKERS:
        candidates.append(
            target_dir / marker / "skills" / "quality-playbook"
            / "quality_gate.py"
        )
    candidates.extend([
        target_dir / ".github" / "skills" / "quality_gate.py",
        target_dir / "quality_gate.py",
    ])
    for c in candidates:
        if c.is_file():
            return c
    raise FactsError(
        f"installed quality_gate.py not found under {target_dir}; "
        f"searched: {[str(c.relative_to(target_dir)) for c in candidates]}"
    )


def _vendor_env_var_for(runner: Runner) -> "tuple[str, str] | None":
    """The single env var the gate's ``_RUNNER_ENV_MARKERS`` keys
    off, per runner. Returned as ``(name, value)`` so the caller
    can stick it into ``env`` directly."""
    if runner == Runner.CLAUDE:
        return ("CLAUDECODE", "1")
    if runner == Runner.CODEX:
        return ("CODEX_THREAD_ID", "harness")
    if runner == Runner.COPILOT:
        return ("COPILOT_AGENT_SESSION_ID", "harness")
    return None


# ---------------------------------------------------------------------------
# Gate-derived facts (re-run the installed gate)
# ---------------------------------------------------------------------------


def rerun_installed_gate(target_dir: Path, *, axes: RunAxes,
                          timeout_s: float = 120.0) -> str:
    """Re-run the run's own installed ``quality_gate.py`` against
    the run's final ``quality/`` artifacts and return the FULL
    stdout. The run's vendor env var is set so the gate's
    ``provenance.detected_runner`` reflects the right runner.

    The harness passes ``target_dir`` as the gate's positional
    argument so it analyzes the run's artifacts in place — exactly
    the invocation the agent itself used.
    """
    gate_path = find_installed_gate(target_dir)
    env = os.environ.copy()
    # Clear any pre-existing vendor markers so the re-run isn't
    # contaminated by the harness's own env (the harness itself
    # may be running under one of these markers).
    for var in ("CLAUDECODE", "CODEX_THREAD_ID",
                 "COPILOT_AGENT_SESSION_ID"):
        env.pop(var, None)
    vendor = _vendor_env_var_for(axes.runner)
    if vendor is not None:
        env[vendor[0]] = vendor[1]
    try:
        result = subprocess.run(
            [sys.executable, str(gate_path), str(target_dir)],
            capture_output=True, text=True, timeout=timeout_s,
            env=env,
        )
    except subprocess.TimeoutExpired:
        raise FactsError(
            f"installed quality_gate.py timed out re-running over "
            f"{target_dir} (timeout={timeout_s}s)"
        )
    # Combined stdout+stderr — the gate prints to stdout but
    # tolerate stderr noise from imports.
    return (result.stdout or "") + (result.stderr or "")


# Regex pinning the canonical 090v/090w/090x verdict-block lines.
# These match the strings emitted by ``_emit_operator_verdict`` +
# ``_format_provenance_lines`` (load-bearing per the gate's
# load-bearing-string discipline).

_RE_TOTAL_PASS = re.compile(
    r"^Total: \d+ FAIL, (?P<warn>\d+) WARN$", re.MULTILINE,
)
_RE_TOTAL_CLEANUP = re.compile(
    r"^Total: (?P<cleanup>\d+) CLEANUP, (?P<warn>\d+) WARN$",
    re.MULTILINE,
)
_RE_TOTAL_FAILED = re.compile(
    r"^Total: \d+ FAIL "
    r"\((?P<sub>\d+) substantive, (?P<rk>\d+) record-keeping\), "
    r"(?P<warn>\d+) WARN$",
    re.MULTILINE,
)
_RE_RESULT_LINE = re.compile(
    r"^RESULT: (?P<rest>GATE PASSED WITH CLEANUP NEEDED.*"
    r"|GATE PASSED|GATE FAILED.*)$",
    re.MULTILINE,
)
_RE_LEAD_SOLID = re.compile(
    r"✅ GATE PASSED — this run looks solid",
)
_RE_LEAD_SHALLOW = re.compile(
    r"⚠️ GATE PASSED — but this run looks shallow",
)
_RE_LEAD_FAILED = re.compile(r"❌ GATE FAILED")
_RE_WEAK_MODEL = re.compile(r"Attribution: weak-model artifact")
_RE_ENV_FAILURE = re.compile(
    r"Attribution: environment / setup problem",
)
_RE_STRONGER_MODEL = re.compile(r"stronger reasoning model")
# 090x curated bugs_unverified narration — the load-bearing
# 'found bug' / 'code-review candidates' tokens.
_RE_BUGS_UNVERIFIED = re.compile(
    r"\[bugs_unverified\]|"
    r"This run found bug\(s\) but didn't verify them",
)
# 090w provenance lines (one per repo).
_RE_PROV_RUNNER = re.compile(
    r"^\s*Runner:\s+(?P<runner>\S+(?:\+\S+)*)\s+\(",
    re.MULTILINE,
)
_RE_PROV_MODEL_SELFREPORT = re.compile(
    r"^\s*Model:\s+(?P<model>.+?)\s+\(self-reported by the agent — not verified\)",
    re.MULTILINE,
)
_RE_PROV_MODEL_NOT_RECORDED = re.compile(
    r"^\s*Model:\s+not recorded$",
    re.MULTILINE,
)
_RE_PROV_BUGS_PLAIN = re.compile(
    r"^\s*Bugs:\s+(?P<gate>\d+) found \(gate-counted\)$",
    re.MULTILINE,
)
_RE_PROV_BUGS_MISMATCH = re.compile(
    r"^\s*Bugs:\s+(?P<gate>\d+) found \(gate-counted\)\s+"
    r"\[run-metadata self-reported: (?P<self>\d+) — mismatch",
    re.MULTILINE,
)


def parse_gate_stdout(stdout: str) -> "tuple[GateFacts, VerdictFacts, ProvenanceFacts]":
    """Extract the three gate-derived fact triples from a captured
    ``quality_gate.py`` stdout. Pins the 090v/090w/090x verdict-
    block strings load-bearingly — a future gate output change
    would surface here as a fact regression.

    Returns a tuple ``(gate, verdict, provenance)`` matching the
    design §C/§5 structure. Defensive: missing optional pieces
    (e.g. provenance not emitted) yield safe defaults rather than
    raising — the assertion grader can then surface
    "fact unknown" rather than the harness crashing.
    """
    # ----- GateFacts -----
    total_line: str = ""
    cleanup_gaps = 0
    # v1.5.7 097: parse the substantive / record-keeping fail
    # counts independently from the gate's `Total:` line — they
    # feed the de-circularized no_false_pass / no_false_fail
    # checks in the grader.
    substantive_fail_count = 0
    record_keeping_fail_count = 0
    m_failed = _RE_TOTAL_FAILED.search(stdout)
    m_cleanup = _RE_TOTAL_CLEANUP.search(stdout)
    m_pass = _RE_TOTAL_PASS.search(stdout)
    if m_failed is not None:
        total_line = m_failed.group(0)
        # ``Total: N FAIL (M substantive, K record-keeping), W
        # WARN`` — the 089c three-state FAIL form.
        substantive_fail_count = int(m_failed.group("sub"))
        record_keeping_fail_count = int(m_failed.group("rk"))
    elif m_cleanup is not None:
        total_line = m_cleanup.group(0)
        cleanup_gaps = int(m_cleanup.group("cleanup"))
        # CLEANUP path: by 089c construction substantive ==
        # 0 (otherwise the gate would have routed to FAIL); the
        # cleanup_gaps count IS the record-keeping count.
        record_keeping_fail_count = cleanup_gaps
    elif m_pass is not None:
        total_line = m_pass.group(0)
        # ``Total: 0 FAIL, W WARN`` — both counts are 0.
    else:
        raise FactsError(
            "could not find canonical Total: line in gate stdout "
            "— ran the wrong gate or stdout is empty"
        )
    result_match = _RE_RESULT_LINE.search(stdout)
    if result_match is None:
        raise FactsError(
            "could not find canonical RESULT: line in gate stdout"
        )
    result_line = result_match.group("rest")
    gate_result = gate_result_from_raw(result_line)
    gate = GateFacts(
        gate_total=total_line,
        gate_result=gate_result,
        cleanup_gaps=cleanup_gaps,
        substantive_fail_count=substantive_fail_count,
        record_keeping_fail_count=record_keeping_fail_count,
    )

    # ----- VerdictFacts (090v / 090x) -----
    if _RE_LEAD_FAILED.search(stdout):
        verdict_state = VerdictState.FAILED
    elif _RE_LEAD_SHALLOW.search(stdout):
        verdict_state = VerdictState.SHALLOW
    elif _RE_LEAD_SOLID.search(stdout):
        verdict_state = VerdictState.SOLID
    else:
        raise FactsError(
            "could not find canonical 090v lead verdict line in "
            "gate stdout (✅ / ⚠️ / ❌)"
        )
    has_weak_model = _RE_WEAK_MODEL.search(stdout) is not None
    has_env_failure = _RE_ENV_FAILURE.search(stdout) is not None
    bugs_unverified = _RE_BUGS_UNVERIFIED.search(stdout) is not None
    if has_weak_model:
        attribution = Attribution.WEAK_MODEL
    elif bugs_unverified:
        attribution = Attribution.INCOMPLETE_VERIFICATION
    elif has_env_failure:
        # The env-failure bucket doesn't map directly to a the design doc
        # §4.1 attribution value (the enum has weak_model /
        # incomplete_verification / none). Conservative direction:
        # treat env-failure-only as ``none`` for the attribution
        # axis (the grader can still observe ``recommends_stronger
        # _model=False`` and the env-failure narration via other
        # facts). This matches the verdict-block emission: env-
        # failure is its own section, not a weak_model variant.
        attribution = Attribution.NONE
    else:
        attribution = Attribution.NONE
    recommends_stronger = _RE_STRONGER_MODEL.search(stdout) is not None
    verdict = VerdictFacts(
        verdict_state=verdict_state,
        attribution=attribution,
        recommends_stronger_model=recommends_stronger,
        bugs_unverified_present=bugs_unverified,
    )

    # ----- ProvenanceFacts (090w) -----
    m_runner = _RE_PROV_RUNNER.search(stdout)
    detected_runner = m_runner.group("runner") if m_runner else "unknown"
    m_model_self = _RE_PROV_MODEL_SELFREPORT.search(stdout)
    if m_model_self is not None:
        selfreport_model_label = m_model_self.group("model").strip()
    else:
        # `Model: not recorded` → None
        selfreport_model_label = None
    m_mismatch = _RE_PROV_BUGS_MISMATCH.search(stdout)
    if m_mismatch is not None:
        gate_bug_count = int(m_mismatch.group("gate"))
        reported_bug_count = int(m_mismatch.group("self"))
        provenance_mismatch = True
    else:
        m_plain = _RE_PROV_BUGS_PLAIN.search(stdout)
        if m_plain is not None:
            gate_bug_count = int(m_plain.group("gate"))
            reported_bug_count = None
            provenance_mismatch = False
        else:
            gate_bug_count = 0
            reported_bug_count = None
            provenance_mismatch = False
    provenance = ProvenanceFacts(
        detected_runner=detected_runner,
        selfreport_model_label=selfreport_model_label,
        gate_bug_count=gate_bug_count,
        reported_bug_count=reported_bug_count,
        provenance_mismatch=provenance_mismatch,
    )
    return gate, verdict, provenance


# ---------------------------------------------------------------------------
# Live-behavior facts (transcript / stream parsing)
# ---------------------------------------------------------------------------


# Heuristic patterns. Phase 1 keeps these minimal; Phase 5 will
# refine per-adapter parsing as the other CLIs land (their stream
# shapes differ from claude's clean stream-json).

# v1.5.7 136: nonce-tolerant. The real validator emits
# ``event=validation_complete nonce=<UUID> status=…`` (the §3.4
# anti-fabrication run-nonce sits between event= and status=);
# the optional ``nonce=\S+`` group matches BOTH the real
# nonce-bearing output AND the bare ``event=validation_complete
# status=…`` form used by AGENTS.md narration / older streams /
# test fixtures. Used by the no-nonce fallback path in
# ``parse_transcript``; the nonce-bearing primary path uses
# ``_RE_PHASE0_PROBE`` below.
_RE_PHASE0_OK = re.compile(
    r"event=validation_complete\s+(?:nonce=\S+\s+)?status=ok",
)
_RE_PHASE0_REMEDIABLE = re.compile(
    r"event=validation_complete\s+(?:nonce=\S+\s+)?status=remediable",
)
_RE_PHASE0_BLOCKED = re.compile(
    r"event=validation_complete\s+(?:nonce=\S+\s+)?status=blocked",
)
# v1.5.7 136: the REAL probe matcher — requires a nonce, so it
# matches only genuine validator emissions, NEVER the AGENTS.md
# instructional quote (which has no nonce). Captures the nonce
# (to dedupe the echo+result double-emission) and the status (to
# build the ordered probe sequence).
_RE_PHASE0_PROBE = re.compile(
    r"event=validation_complete\s+nonce=(?P<nonce>\S+)\s+"
    r"status=(?P<status>\w+)",
)
_RE_PHASE0_BARE_PATH_FAIL = re.compile(
    r"python3 bin/qpb_validate\.py.*FileNotFoundError|"
    r"\[Errno 2\] No such file or directory.*qpb_validate",
)
# 090m/090n canonical banner — the 80-wide ═══ rule is the
# Markdown-inert signal that the agent actually printed the
# banner.
_RE_BANNER_RULE = re.compile(r"═{80}")
# 090u gitignore remediation — the canonical macos/linux form
# the validator emits. ``followed`` if the agent ran exactly
# this command (or shipped equivalent: a `cat` of
# ``skill-template.gitignore`` into ``<target>/.gitignore``).
_RE_GITIGNORE_REMEDIATION = re.compile(
    r"cat\s+\S*skill-template\.gitignore\s+>>\s+\S*\.gitignore",
)
_RE_GITIGNORE_IMPROVISATION = re.compile(
    r"printf\s+['\"]\\nquality/\\n['\"]\s+>>\s+\.gitignore|"
    r"echo\s+['\"]quality/['\"]\s+>>\s+\.gitignore",
)
# v1.5.7 157: outcome-based gitignore remediation detection — the
# minimal intersection of the 3 entries observed in every successful
# 2026-05-29 copilot run (keto bash + chi/express Edit/Write). The
# full skill-template.gitignore has 5 entries (these 3 plus
# `!quality/RUN_INDEX.md` and `quality/logs/`); the empirical chi run
# only appended 3, so the conservative intersection is the right
# threshold to call the remediation "followed". A runner that adds
# more (keto added all 5) trivially passes.
_GITIGNORE_LOAD_BEARING_ENTRIES = (
    "docs_gathered/",
    "**/docs_gathered/",
    "quality/runs/",
)


def _gitignore_outcome_check(
        target_dir: "Path | None") -> bool:
    """v1.5.7 157: detect successful gitignore remediation by reading
    ``target_dir/.gitignore`` directly and checking for the load-
    bearing entries from ``skill-template.gitignore``. Replaces the
    pre-157 stream-regex check, which missed runners that used
    structured editing tools instead of `cat ... >>`. The caller
    combines this with the improvisation regex (improvisation still
    counts as not-followed even if the outcome happens to be correct).
    Conservative: requires ALL load-bearing entries — a partial
    append is still flagged as not-followed."""
    if target_dir is None:
        return False
    gitignore = Path(target_dir) / ".gitignore"
    if not gitignore.is_file():
        return False
    try:
        content = gitignore.read_text(
            encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return all(entry in content
               for entry in _GITIGNORE_LOAD_BEARING_ENTRIES)
# Vendor AUP-stop heuristics — generic; refined per-adapter in
# Phase 5.
_RE_BLOCKED = re.compile(
    r"refus|cannot help|won'?t help|policy|"
    r"unsafe|harmful|inappropriate",
    re.IGNORECASE,
)


def _phase0_probes_from_witnesses(
        target_dir: "Path") -> "tuple[list[str], bool]":
    """v1.5.7 145: reconstruct the ordered, deduped Phase-0 probe
    statuses from the validator's on-disk witnesses under
    ``<target_dir>/quality/.qpb_validation_<ts>_<nonce>.txt``.

    Each witness carries ``nonce=`` always and (145-format)
    ``status=``/``findings=``. Pre-145 witnesses (no ``status=``)
    are silently skipped. Files are processed in filename order
    (the ``<ts>`` prefix is chronological), deduped by nonce —
    matching the stream path's dedup. Returns
    ``(probe_statuses, bare_path_fail)``.
    """
    qdir = Path(target_dir) / "quality"
    if not qdir.is_dir():
        return [], False
    probes: "list[str]" = []
    seen: "set[str]" = set()
    bare_path = False
    try:
        witnesses = sorted(qdir.glob(".qpb_validation_*.txt"))
    except OSError:
        return [], False
    for wf in witnesses:
        try:
            text = wf.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        fields: "dict[str, str]" = {}
        for line in text.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                fields[k] = v
        status = fields.get("status")
        nonce = fields.get("nonce")
        if status is None or nonce is None:
            continue  # pre-145 witness — no status field; skip
        if status == "bare-path-fail":
            bare_path = True
        if nonce not in seen:
            seen.add(nonce)
            probes.append(status)
    return probes, bare_path


def parse_transcript(
        transcript: str,
        target_dir: "Path | None" = None,
) -> "tuple[Phase0Facts, InstallSurfaceFacts, bool, str | None]":
    """Parse the agent's transcript / stream for the live-behavior
    facts the gate-derived path doesn't carry.

    Returns ``(phase0, install_surface, blocked, stop_reason)``.
    ``blocked`` + ``stop_reason`` feed ``RunMetaFacts``; the rest
    is per-named-tuple per design §C/§5.

    v1.5.7 145: ``target_dir`` enables an artifact fallback for the
    Phase-0 facts. Non-Claude runners (copilot / codex / cursor)
    emit boxed-TUI streams that don't capture the validator's
    ``event=validation_complete`` stdout, so the stream yields zero
    probes and the facts would default to ``blocked`` / not-ok. When
    the stream has NO probes AND ``target_dir`` is given, fall back
    to the validator's on-disk witnesses
    (``<target>/quality/.qpb_validation_*.txt``, 145-format with
    ``status=``/``findings=``). None / no post-145 witnesses ⇒
    pre-145 behavior preserved. Stream probes always win when
    present.
    """
    # Phase 0 status / probe_attempts / first_probe_ok.
    #
    # v1.5.7 136: the real validator emits nonce-bearing lines
    # (§3.4 anti-fabrication); AGENTS.md:212 carries a non-nonce
    # instructional QUOTE of ``event=validation_complete status=ok``
    # that pre-136 the regexes matched by accident (making
    # ``status`` resolve "ok" regardless of the real probes). The
    # nonce-bearing PRIMARY path below derives every fact from the
    # ordered, deduped sequence of REAL probes only; the no-nonce
    # FALLBACK preserves pre-136 behavior for older streams / test
    # fixtures using the bare form.
    #
    # Each real validator line appears twice in a stream (the
    # tool_use command echo + the tool_result body), so dedupe by
    # nonce preserving first-seen order to get the true probe
    # sequence (e.g. a fresh target's designed remediation flow:
    # blocked → remediable → ok).
    real_probes: "list[str]" = []
    _seen_nonces: "set[str]" = set()
    for _pm in _RE_PHASE0_PROBE.finditer(transcript):
        _nonce = _pm.group("nonce")
        if _nonce not in _seen_nonces:
            _seen_nonces.add(_nonce)
            real_probes.append(_pm.group("status"))

    bare_path_fail = _RE_PHASE0_BARE_PATH_FAIL.search(transcript) is not None

    # v1.5.7 145: artifact fallback — when the STREAM carried no
    # probes (non-Claude TUI streams), reconstruct the probe sequence
    # from the validator's on-disk witnesses. Stream probes win when
    # present (this only fires on an empty stream-probe list).
    if not real_probes and target_dir is not None:
        _wit_probes, _wit_bare = _phase0_probes_from_witnesses(
            target_dir)
        if _wit_probes:
            real_probes = _wit_probes
            bare_path_fail = bare_path_fail or _wit_bare

    if real_probes:
        # v1.5.7 141: scope to the PHASE-0 prefix. Phase 0 ends the
        # moment the agent reaches a clean probe ("ok") and proceeds
        # to Phase 1 — so the phase-0 sequence is the prefix UP TO
        # AND INCLUDING the first "ok". Probes AFTER the first ok are
        # LATER-PHASE validations (Phase 1/2 artifact validators emit
        # the same ``event=validation_complete nonce=… status=…``
        # shape); 136 v2 wrongly swept them into the phase-0 count.
        # That mis-attribution was the express sonnet false-negative:
        # its real phase-0 flow was blocked → remediable → ok (3
        # probes, identical to gson), but a Phase-1 ``status=ok``
        # validation made it look like a 4-probe sequence whose
        # non-final "ok" failed the all-blocked/remediable check.
        if "ok" in real_probes:
            phase0_probes = real_probes[:real_probes.index("ok") + 1]
        else:
            phase0_probes = real_probes
        last = phase0_probes[-1]
        status = last if last in ("ok", "remediable", "blocked") else "blocked"
        probe_attempts = len(phase0_probes)
        # v1.5.7 136 semantic (preserved): the run reached a clean
        # probe, no bare-path failure occurred, and any probes BEFORE
        # the clean one were legitimate remediation cases (blocked /
        # remediable — the designed 090u flow), NOT bare-path
        # retries. This stops penalizing a fresh-target run for the
        # extra probes its own remediation requires (which the SAME
        # run is rewarded for via ``gitignore_remediation_followed``).
        first_probe_ok = (
            last == "ok"
            and not bare_path_fail
            and all(p in ("blocked", "remediable")
                    for p in phase0_probes[:-1])
        )
    else:
        # No nonce-bearing probes — older stream / test fixture
        # using the bare ``event=validation_complete status=…``
        # form. Pre-136 logic (the nonce-tolerant regexes match
        # the bare form too).
        if _RE_PHASE0_OK.search(transcript):
            status = "ok"
        elif _RE_PHASE0_REMEDIABLE.search(transcript):
            status = "remediable"
        elif _RE_PHASE0_BLOCKED.search(transcript):
            status = "blocked"
        else:
            # Defensive default: no validator-event seen →
            # "blocked" rather than silently "ok".
            status = "blocked"
        probe_attempts = len(re.findall(
            r"event=validation_complete", transcript,
        )) or 1  # min 1 — running the gate is at least one attempt
        first_probe_ok = (
            probe_attempts == 1
            and status == "ok"
            and not bare_path_fail
        )
    phase0 = Phase0Facts(
        status=status,
        probe_attempts=probe_attempts,
        first_probe_ok=first_probe_ok,
    )

    # Install surface
    banner_rendered = _RE_BANNER_RULE.search(transcript) is not None
    # v1.5.7 148: artifact fallback (parallel to 145's phase-0
    # witness fallback). Non-Claude TUI streams (copilot/codex/
    # cursor) don't capture the install subprocess's output, so the
    # ═{80} attribution banner — emitted on stderr at the end of a
    # SUCCESSFUL install and captured by 146's install.log — is
    # invisible in the stream and banner_rendered defaults False
    # even when the install (and banner) clearly succeeded. When the
    # stream has no banner AND target_dir is given, read
    # <run-NN>/install.log (= target_dir.parent/install.log per the
    # 145/146 wiring) and apply the SAME _RE_BANNER_RULE. The stream
    # match always wins (this only fires when the stream had none).
    if not banner_rendered and target_dir is not None:
        install_log = Path(target_dir).parent / "install.log"
        if install_log.is_file():
            try:
                _log_text = install_log.read_text(
                    encoding="utf-8", errors="ignore")
            except OSError:
                _log_text = ""
            if _RE_BANNER_RULE.search(_log_text):
                banner_rendered = True
    # v1.5.7 157: outcome-based detection. We read target/.gitignore
    # directly (when target_dir is provided AND the file exists) and
    # check for the load-bearing entries from skill-template.gitignore.
    # The pre-157 stream-regex check (`cat skill-template.gitignore
    # >> .gitignore`) only matched runners using the canonical bash
    # form; capable runners (notably copilot gpt-5.4 — empirically
    # `harness_runs/20260529T235425Z/run-05` express + `run-06` chi)
    # use their structured editing tools (Edit/Write) that achieve the
    # same outcome without emitting the canonical line. The
    # improvisation regex stays as a stream-side check because the
    # `printf '\nquality/\n' >> .gitignore` shortcut is a quality bug
    # regardless of outcome — it usually means the runner skipped
    # reading the template. Fallback: when target_dir is None or
    # target_dir/.gitignore is missing, fall back to the pre-157
    # stream-regex check so existing tests and call sites that don't
    # pass target_dir keep their behavior.
    saw_improvise = _RE_GITIGNORE_IMPROVISATION.search(transcript) is not None
    if (target_dir is not None
            and (Path(target_dir) / ".gitignore").is_file()):
        gitignore_followed = (
            _gitignore_outcome_check(target_dir)
            and not saw_improvise)
    else:
        saw_canonical = _RE_GITIGNORE_REMEDIATION.search(
            transcript) is not None
        gitignore_followed = saw_canonical and not saw_improvise
    install = InstallSurfaceFacts(
        banner_rendered=banner_rendered,
        gitignore_remediation_followed=gitignore_followed,
    )

    # Blocked / stop_reason
    blocked = False
    stop_reason: "str | None" = None
    block_m = _RE_BLOCKED.search(transcript)
    if block_m:
        blocked = True
        # Capture a short context window for the operator.
        start = max(0, block_m.start() - 60)
        end = min(len(transcript), block_m.end() + 60)
        stop_reason = transcript[start:end].strip()[:200]
    return phase0, install, blocked, stop_reason


# ---------------------------------------------------------------------------
# Combined extractor
# ---------------------------------------------------------------------------


def extract_facts(target_dir: Path, *, axes: RunAxes,
                   transcript: str, exit_code: int,
                   raw_receipt: str = "stream.ndjson",
                   timings: "dict | None" = None,
                   gate_stdout: "str | None" = None) -> RunFacts:
    """Two-sourced extraction per design §C.

    ``gate_stdout``, if provided, is used directly; otherwise the
    function re-runs the installed gate over ``target_dir``. Tests
    inject ``gate_stdout`` to exercise the parse paths without a
    real gate run; production calls use the re-run path.
    """
    if gate_stdout is None:
        gate_stdout = rerun_installed_gate(target_dir, axes=axes)
    gate, verdict, provenance = parse_gate_stdout(gate_stdout)
    phase0, install, blocked, stop_reason = parse_transcript(
        transcript, target_dir=target_dir)
    run_meta = RunMetaFacts(
        blocked=blocked,
        stop_reason=stop_reason,
        exit_code=exit_code,
        timings=timings or {},
        raw_receipt=raw_receipt,
    )
    return RunFacts(
        phase0=phase0,
        verdict=verdict,
        provenance=provenance,
        gate=gate,
        install=install,
        run_meta=run_meta,
    )


__all__ = [
    "FactsError",
    "find_installed_gate",
    "rerun_installed_gate",
    "parse_gate_stdout",
    "parse_transcript",
    "extract_facts",
]
