"""QPB Test Harness — schema dataclasses, enums, and (de)serialization.

Built to match ``bin/harness/SCHEMA.md`` exactly (LOCKED
2026-05-25; v1.5.7 098 moved it from
``repos/security-test-cases/`` to live with the code it
specifies — tracked, bundle-excluded). The §F closed assertion vocabulary, the
three-state ``gate_result`` (PASS|CLEANUP|FAIL), the
``install_channel`` enum, the §5 fact object, and the §6 terminal
states all live here. If SCHEMA.md says something can't be free-
form, the corresponding type here MUST be a closed enum or a
dataclass with documented fields.

Two consumers:

  * Run/case authors (incl. Claude generating acceptance JSON)
    write JSON that ``load_case_json`` / ``load_run_invocation_json``
    parse into these types — bad inputs raise SchemaError with the
    offending field named.
  * The grader reads the normalized fact object (``RunFacts``) and
    the case's ``expected`` list (acceptance) / ``answer_key``
    (security) — both come from the same locked vocabulary here.

Build order: this module is foundational — prepare/runner/facts
all import from it. It has no QPB-internal imports beyond stdlib
(so import-isolation from ``bin.__init__`` is trivial — see
``test_publish_safety_090c.py``).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SchemaError(ValueError):
    """A case/run JSON document violates SCHEMA.md.

    Always carries the offending field path (e.g. ``"cases[2].type"``)
    so the operator can locate the bad entry without re-grepping.
    """


# ---------------------------------------------------------------------------
# §1.1 / §1 — case-level enums
# ---------------------------------------------------------------------------


class CaseType(str, Enum):
    """SCHEMA.md §1: the only two case types."""
    ACCEPTANCE = "acceptance"
    SECURITY_EVAL = "security_eval"


class PrepPolicy(str, Enum):
    """SCHEMA.md §1 ``inputs.prep``. The acceptance/security split
    drives ``prepare.py``: ``acceptance`` keeps docs present;
    ``security`` scrubs ``reference_docs/`` and applies the
    leakage-gate before launching the run."""
    ACCEPTANCE = "acceptance"
    SECURITY = "security"


# ---------------------------------------------------------------------------
# §2 / §3 — run-level enums (the run matrix axes)
# ---------------------------------------------------------------------------


class Runner(str, Enum):
    """SCHEMA.md §2 ``axes.runner`` — the four supported CLIs.
    Phase 1 supports ``CLAUDE`` only; the rest are Phase 5."""
    CLAUDE = "claude"
    COPILOT = "copilot"
    CODEX = "codex"
    CURSOR = "cursor"


class Mode(str, Enum):
    """SCHEMA.md §2 ``axes.mode``. Mode A = agent drives the
    phases inline; Mode B = ``bin/run_playbook.py`` harness drives
    them (Phase 5)."""
    A = "A"
    B = "B"


class InstallChannel(str, Enum):
    """SCHEMA.md §3 ``install_channel`` enum.

    Phase 1 supports ``CLONE`` end-to-end. ``PIP_LOCAL_WHEEL`` /
    ``NPM_LOCAL_TGZ`` (pre-publish acceptance) are wired into the
    enum but full prep-policy support lands with Phase 2. Registry
    channels are Phase 6.

    Note: registry channels carry a ``@<version|latest>`` suffix in
    JSON (e.g. ``"pip-registry@1.5.7"``). The enum value is the
    bare channel name; the version pin is parsed off and stored
    on ``RunAxes.install_version``.
    """
    CLONE = "clone"
    PIP_LOCAL_WHEEL = "pip-local-wheel"
    NPM_LOCAL_TGZ = "npm-local-tgz"
    PIP_REGISTRY = "pip-registry"
    NPM_REGISTRY = "npm-registry"


class TerminalState(str, Enum):
    """SCHEMA.md §6 — run lifecycle terminal states. Grading runs
    only on ``COMPLETED``; all others grade ``N/A (run incomplete)``
    with the reason."""
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    BLOCKED = "BLOCKED"
    KILLED = "KILLED"
    ABORTED_PREP = "ABORTED_PREP"


class RunState(str, Enum):
    """SCHEMA.md §6 — pre-terminal run states (the manager-daemon
    state machine; Phase 1 only exercises QUEUED/PREPARING/RUNNING
    on a single case, but the enum is complete for downstream
    phases)."""
    QUEUED = "QUEUED"
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"


# ---------------------------------------------------------------------------
# §4 — closed assertion vocabulary (THE CONTRACT)
# ---------------------------------------------------------------------------


class AcceptanceAssertion(str, Enum):
    """SCHEMA.md §4.1 — acceptance assertions. The names are
    LOAD-BEARING: graders match on these exact strings."""
    GATE_RESULT = "gate_result"
    VERDICT_STATE = "verdict_state"
    ATTRIBUTION = "attribution"
    RECOMMENDS_STRONGER_MODEL = "recommends_stronger_model"
    PHASE0_STATUS_OK = "phase0_status_ok"
    PHASE0_FIRST_PROBE = "phase0_first_probe"
    BANNER_RENDERED = "banner_rendered"
    GITIGNORE_REMEDIATION_FOLLOWED = "gitignore_remediation_followed"
    PROVENANCE_RUNNER_MATCHES = "provenance_runner_matches"
    PROVENANCE_MODEL_LABELED_SELFREPORT = \
        "provenance_model_labeled_selfreport"
    PROVENANCE_BUGCOUNT_VS_GATE = "provenance_bugcount_vs_gate"
    NO_FALSE_PASS = "no_false_pass"
    NO_FALSE_FAIL = "no_false_fail"
    BUGS_UNVERIFIED_MESSAGE_PRESENT = "bugs_unverified_message_present"


class SecurityAssertion(str, Enum):
    """SCHEMA.md §4.2 — security assertions."""
    ANSWER_KEY_CITED = "answer_key_cited"
    OUTCOME = "outcome"


class Comparator(str, Enum):
    """SCHEMA.md §F-note 3 / §4 ``expected``-entry shape. The
    only legal comparators in an `expected` entry."""
    EQ = "=="
    NE = "!="
    IN = "in"


# Closed-domain enums for assertions whose ``value`` field is
# itself enumerated. Pinned here so a typo in a case's ``expected``
# entry (e.g. ``"value": "Solid"`` vs ``"solid"``) is caught by
# the loader, not silently passed to the grader.
class GateResult(str, Enum):
    """SCHEMA.md §4.1 / §5 — the three-state gate verdict.

    Raw lines map per SCHEMA.md §5: ``GATE PASSED`` → ``PASS``,
    ``GATE PASSED WITH CLEANUP NEEDED`` → ``CLEANUP``,
    ``GATE FAILED`` → ``FAIL``.
    """
    PASS = "PASS"
    CLEANUP = "CLEANUP"
    FAIL = "FAIL"


class VerdictState(str, Enum):
    """SCHEMA.md §4.1 — the 090v operator-verdict lead-line state.

    F-note 1 (LOCKED): ``verdict_state`` ⊥ ``gate_result`` —
    independent axes. A ``CLEANUP`` gate may pair with either a
    ``solid`` or ``shallow`` verdict; ``verdict_state=failed``
    does NOT imply ``gate_result=FAIL``. The grader treats them
    independently.
    """
    SOLID = "solid"
    SHALLOW = "shallow"
    FAILED = "failed"


class Attribution(str, Enum):
    """SCHEMA.md §4.1 — the 090v three-bucket attribution
    (extended by 090x to include the ``incomplete_verification``
    case for ``bugs_unverified`` runs)."""
    WEAK_MODEL = "weak_model"
    INCOMPLETE_VERIFICATION = "incomplete_verification"
    NONE = "none"


class ProvenanceBugcountVsGate(str, Enum):
    """SCHEMA.md §4.1 — the 090w provenance bug-count mismatch
    assertion. ``match`` = self-report agrees with gate;
    ``expect_mismatch`` = the self-report is expected to disagree
    (the NATS run2 fixture shape)."""
    MATCH = "match"
    EXPECT_MISMATCH = "expect_mismatch"


class SecurityOutcome(str, Enum):
    """SCHEMA.md §4.2 — the security grader's verdict.

    F-note 3 (LOCKED): ``BLOCKED`` (AUP/usage-policy stop) is
    graded ``N/A``, NEVER ``MISSED``. F-note 4: ``DETECTED`` /
    ``PARTIAL`` / ``MISSED`` require human review before they
    count (``reviewed:true`` in grading.json).
    """
    DETECTED = "DETECTED"
    PARTIAL = "PARTIAL"
    MISSED = "MISSED"
    BLOCKED = "BLOCKED"


# ---------------------------------------------------------------------------
# §1 — case dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CaseInputs:
    """SCHEMA.md §1 ``inputs`` — the run inputs. Physically
    separated from the answer key / expected assertions so the
    run agent cannot cheat by reading them.

    ``repo_url`` is required for both case types. ``target_ref``
    is required for ACCEPTANCE (pins the version QPB runs against);
    SECURITY_EVAL uses ``vulnerable_parent`` from ``answer_key``
    indirectly via prep (this is intentional — the case-author
    docs make this explicit).

    ``reference_docs_source`` ("path or 'gather'") and ``prep``
    are required.
    """
    repo_url: str
    prep: PrepPolicy
    target_ref: "str | None" = None
    reference_docs_source: "str | None" = None
    # SCHEMA.md §1: security_eval cases also carry doc_sources +
    # scrub_terms + run_prompt at the inputs level (the existing
    # 10 cases). Acceptance cases use reference_docs_source only.
    doc_sources: "list[str] | None" = None
    scrub_terms: "list[str] | None" = None
    run_prompt: "str | None" = None
    # SCHEMA.md §1.1: security cases physically separate the
    # vulnerable_parent SHA into inputs (the harness target_ref)
    # — distinct from answer_key.vulnerable_parent. Kept optional
    # on the dataclass so acceptance cases don't need it.
    vulnerable_parent: "str | None" = None


@dataclass
class ExpectedAssertion:
    """SCHEMA.md §4 ``expected``-entry shape:
    ``{assertion, comparator, value}``. The assertion name is
    drawn from §4.1 / §4.2; the comparator is one of
    ``==`` / ``!=`` / ``in``; the value's legal domain is
    enumerated per assertion in SCHEMA.md (and enforced by the
    closed-domain enums above when applicable)."""
    assertion: str
    comparator: Comparator
    value: Any

    def to_json(self) -> dict:
        return {
            "assertion": self.assertion,
            "comparator": self.comparator.value,
            "value": self.value,
        }


@dataclass
class AnswerKey:
    """SCHEMA.md §1.1 — the SECURITY_EVAL answer key. Carries the
    planted-defect facts the grader matches BUGS.md / writeups
    against. NEVER appears in inputs (the run never reads this).
    """
    cwe: str
    vulnerable_parent: str
    file: str
    symbol: str
    behavior: str
    # SCHEMA.md security cases also carry these extended fields
    # in the existing 10 cases (fix_commit / locus / mechanism /
    # pass_criterion / advisory). Optional on the dataclass.
    fix_commit: "str | None" = None
    files: "list[str] | None" = None
    locus: "str | None" = None
    mechanism: "str | None" = None
    pass_criterion: "str | None" = None
    advisory: "str | None" = None


@dataclass
class Case:
    """SCHEMA.md §1 — a case = identity + prep policy + expected
    outcome. ``expected`` is set on ACCEPTANCE cases (and
    ``answer_key`` is None); ``answer_key`` is set on
    SECURITY_EVAL cases (and ``expected`` is None).

    Acceptance F-note: a case may assert both ``gate_result`` and
    ``verdict_state`` — they are independent axes (F-note 1).
    """
    id: str
    type: CaseType
    title: str
    inputs: CaseInputs
    expected: "list[ExpectedAssertion] | None" = None
    answer_key: "AnswerKey | None" = None
    # SCHEMA.md security_eval existing cases carry these top-level
    # discovery fields; keep them on the dataclass as optional so
    # the existing 10 cases round-trip cleanly.
    category: "str | None" = None
    cwe: "str | None" = None
    project: "str | None" = None
    language: "str | None" = None
    cve: "str | None" = None
    disclosed: "str | None" = None
    recall_risk: "str | None" = None
    qe_catchable: "bool | None" = None


# ---------------------------------------------------------------------------
# §2 — run dataclasses
# ---------------------------------------------------------------------------


@dataclass
class RunAxes:
    """SCHEMA.md §2 ``axes`` — the run matrix point a run binds
    to. ``install_version`` is parsed off the channel suffix for
    registry channels (e.g. ``pip-registry@1.5.7`` →
    ``install_channel=PIP_REGISTRY, install_version="1.5.7"``);
    None for clone/local-wheel/local-tgz."""
    runner: Runner
    mode: Mode
    install_channel: InstallChannel
    model: str
    install_version: "str | None" = None
    thinking: "str | None" = None  # low | medium | high | xhigh | null


@dataclass
class RunInvocation:
    """SCHEMA.md §2 — the full run invocation record written to
    ``runs/<case-id>/<run-id>/invocation.json``."""
    run_id: str        # UTC YYYYMMDDTHHMMSSZ
    case_id: str
    axes: RunAxes
    qpb_version: str
    target_sha: str
    cli_command: str
    cwd: str
    env_snapshot: dict
    started_at: str
    ended_at: str
    exit_code: int
    terminal_state: TerminalState
    # Security-only fields; None for acceptance.
    scrubbed_docs_manifest: "dict | None" = None
    leakage_gate: "str | None" = None  # "clean" | "ABORTED"


# ---------------------------------------------------------------------------
# §5 — normalized run-fact object (the two-sourced extraction)
# ---------------------------------------------------------------------------


@dataclass
class Phase0Facts:
    """Live-behavior — parsed from the transcript/stream."""
    status: str  # "ok" | "remediable" | "blocked"
    probe_attempts: int
    first_probe_ok: bool


@dataclass
class VerdictFacts:
    """Gate-derived — from re-running the installed quality_gate.py
    over the run's final ``quality/`` artifacts."""
    verdict_state: VerdictState
    attribution: Attribution
    recommends_stronger_model: bool
    bugs_unverified_present: bool


@dataclass
class ProvenanceFacts:
    """Gate-derived — from the same re-run, with the vendor env
    var set so ``detected_runner`` reflects the run's actual
    vendor."""
    detected_runner: str  # "claude-code" | "codex" | "copilot" | "..."
    selfreport_model_label: "str | None"
    gate_bug_count: int
    reported_bug_count: "int | None"
    provenance_mismatch: bool


@dataclass
class GateFacts:
    """Gate-derived — the three-state verdict.

    v1.5.7 097: ``substantive_fail_count`` and
    ``record_keeping_fail_count`` are parsed independently from
    the gate's ``Total:`` line (the three-state form carries
    them as ``N FAIL (M substantive, K record-keeping)``). They
    feed the acceptance grader's `no_false_pass` / `no_false_fail`
    checks — which were CIRCULAR pre-097 (they inferred "no
    substantive fails" from the gate's own PASS/CLEANUP routing,
    so a buggy gate that falsely PASSed couldn't be caught). The
    089c three-state verdict logic populates both counts; clean
    PASS lines (``Total: 0 FAIL, M WARN``) set both to 0.
    """
    gate_total: str  # the canonical 'Total: ...' line
    gate_result: GateResult
    cleanup_gaps: int
    substantive_fail_count: int = 0  # v1.5.7 097
    record_keeping_fail_count: int = 0  # v1.5.7 097


@dataclass
class InstallSurfaceFacts:
    """Live-behavior — parsed from the transcript/stream."""
    banner_rendered: bool
    gitignore_remediation_followed: bool


@dataclass
class RunMetaFacts:
    """Run-meta — mostly live, exit_code from the subprocess."""
    blocked: bool
    stop_reason: "str | None"
    exit_code: int
    timings: dict
    raw_receipt: str  # path/filename for stream.ndjson


@dataclass
class RunFacts:
    """SCHEMA.md §5 — the normalized fact object both graders
    consume. Two-sourced: ``phase0`` and ``install`` are live-
    behavior (transcript-derived); ``verdict``, ``provenance``,
    and ``gate`` are gate-derived (re-running the run's OWN
    installed ``quality_gate.py`` over the run's final
    ``quality/`` artifacts, with the run's vendor env var set).
    ``run_meta`` mixes the two.
    """
    phase0: Phase0Facts
    verdict: VerdictFacts
    provenance: ProvenanceFacts
    gate: GateFacts
    install: InstallSurfaceFacts
    run_meta: RunMetaFacts


# ---------------------------------------------------------------------------
# JSON (de)serialization
# ---------------------------------------------------------------------------


# Mapping for the raw "Total: ..." line / "RESULT: ..." line →
# GateResult. SCHEMA.md §5 pins these exactly.
_GATE_RESULT_RAW_MAP = {
    "GATE PASSED WITH CLEANUP NEEDED": GateResult.CLEANUP,
    "GATE PASSED": GateResult.PASS,
    "GATE FAILED": GateResult.FAIL,
}


def gate_result_from_raw(raw_result_line: str) -> GateResult:
    """Map a raw ``RESULT: ...`` line to its ``GateResult`` enum.

    The longer-prefix variant (``GATE PASSED WITH CLEANUP NEEDED``)
    is matched FIRST so it doesn't fall through to ``GATE PASSED``.
    Substring match: the actual gate prints
    ``RESULT: GATE FAILED — N substantive issue(s) must be fixed``
    etc., so we tolerate a suffix.
    """
    raw_result_line = raw_result_line.strip()
    # Longest-match-first ordering is load-bearing.
    for needle, gr in (
        ("GATE PASSED WITH CLEANUP NEEDED", GateResult.CLEANUP),
        ("GATE FAILED", GateResult.FAIL),
        ("GATE PASSED", GateResult.PASS),
    ):
        if needle in raw_result_line:
            return gr
    raise SchemaError(
        f"unrecognized RESULT line: {raw_result_line!r} — "
        f"expected one of "
        f"{list(_GATE_RESULT_RAW_MAP.keys())}"
    )


def _required(d: dict, key: str, where: str) -> Any:
    if key not in d:
        raise SchemaError(f"missing required field {where}.{key!r}")
    return d[key]


def _enum_or_raise(enum_cls, raw: str, where: str):
    try:
        return enum_cls(raw)
    except ValueError:
        legal = ", ".join(repr(e.value) for e in enum_cls)
        raise SchemaError(
            f"{where}: {raw!r} not in {enum_cls.__name__} "
            f"(legal: {legal})"
        )


def _parse_inputs(raw: dict, where: str) -> CaseInputs:
    prep_raw = _required(raw, "prep", where)
    prep = _enum_or_raise(PrepPolicy, prep_raw, f"{where}.prep")
    return CaseInputs(
        repo_url=_required(raw, "repo_url", where),
        prep=prep,
        target_ref=raw.get("target_ref"),
        reference_docs_source=raw.get("reference_docs_source"),
        doc_sources=raw.get("doc_sources"),
        scrub_terms=raw.get("scrub_terms"),
        run_prompt=raw.get("run_prompt"),
        vulnerable_parent=raw.get("vulnerable_parent"),
    )


def _parse_expected(raw_list: list, where: str
                    ) -> "list[ExpectedAssertion]":
    out: list[ExpectedAssertion] = []
    for i, entry in enumerate(raw_list):
        sub = f"{where}[{i}]"
        if not isinstance(entry, dict):
            raise SchemaError(f"{sub}: expected dict, got {type(entry).__name__}")
        assertion = _required(entry, "assertion", sub)
        comparator_raw = _required(entry, "comparator", sub)
        comparator = _enum_or_raise(
            Comparator, comparator_raw, f"{sub}.comparator",
        )
        value = _required(entry, "value", sub)
        out.append(ExpectedAssertion(
            assertion=assertion,
            comparator=comparator,
            value=value,
        ))
    return out


def _parse_answer_key(raw: dict, where: str,
                       case_top_level: "dict | None" = None) -> AnswerKey:
    # SCHEMA.md §1.1: cwe / vulnerable_parent / file / symbol /
    # behavior are required. The legacy 10 cases keep ``cwe`` at the
    # case top level (not inside answer_key) and use richer keys
    # (fix_commit / files / locus / mechanism / pass_criterion /
    # advisory) instead of ``file`` / ``symbol`` / ``behavior``. To
    # accept both the SCHEMA-canonical shape AND the legacy 10, this
    # parser falls back to the case top level for ``cwe`` (when
    # absent from answer_key) and synthesises ``file``/``symbol``/
    # ``behavior`` from the legacy keys.
    file_field = raw.get("file")
    if file_field is None and raw.get("files"):
        file_field = raw["files"][0]
    if file_field is None:
        raise SchemaError(
            f"{where}: answer_key must carry either 'file' or 'files'"
        )
    cwe = raw.get("cwe")
    if cwe is None and case_top_level is not None:
        cwe = case_top_level.get("cwe")
    if cwe is None:
        raise SchemaError(f"missing required field {where}.'cwe'")
    vulnerable_parent = raw.get("vulnerable_parent")
    if vulnerable_parent is None and case_top_level is not None:
        # Legacy 10 cases keep vulnerable_parent in inputs (not
        # answer_key). SCHEMA.md §1.1 puts it under answer_key —
        # accept both, prefer answer_key when present.
        inputs = case_top_level.get("inputs") or {}
        vulnerable_parent = inputs.get("vulnerable_parent")
    if vulnerable_parent is None:
        raise SchemaError(
            f"missing required field {where}.'vulnerable_parent' "
            f"(neither in answer_key nor in inputs)"
        )
    return AnswerKey(
        cwe=cwe,
        vulnerable_parent=vulnerable_parent,
        file=file_field,
        symbol=raw.get("symbol") or raw.get("locus") or "<unspecified>",
        behavior=raw.get("behavior") or raw.get("mechanism")
                 or raw.get("pass_criterion") or "<unspecified>",
        fix_commit=raw.get("fix_commit"),
        files=raw.get("files"),
        locus=raw.get("locus"),
        mechanism=raw.get("mechanism"),
        pass_criterion=raw.get("pass_criterion"),
        advisory=raw.get("advisory"),
    )


def parse_case(raw: dict, where: str = "case") -> Case:
    """Parse one case dict per SCHEMA.md §1 → ``Case``. Raises
    ``SchemaError`` with the offending field path on bad input.

    Enforces §1's "type is mandatory" + the
    acceptance-has-expected / security_eval-has-answer_key split.
    """
    case_id = _required(raw, "id", where)
    where = f"{where}({case_id})"
    case_type_raw = _required(raw, "type", where)
    case_type = _enum_or_raise(CaseType, case_type_raw,
                                f"{where}.type")
    inputs_raw = _required(raw, "inputs", where)
    inputs = _parse_inputs(inputs_raw, f"{where}.inputs")

    expected: "list[ExpectedAssertion] | None" = None
    answer_key: "AnswerKey | None" = None
    if case_type == CaseType.ACCEPTANCE:
        expected_raw = _required(raw, "expected", where)
        if not isinstance(expected_raw, list):
            raise SchemaError(
                f"{where}.expected: must be a list of "
                f"{{assertion, comparator, value}} entries; got "
                f"{type(expected_raw).__name__}"
            )
        expected = _parse_expected(expected_raw, f"{where}.expected")
        if "answer_key" in raw and raw["answer_key"] is not None:
            raise SchemaError(
                f"{where}: acceptance cases MUST NOT carry an "
                f"answer_key (SCHEMA.md §1)"
            )
    else:  # SECURITY_EVAL
        answer_key_raw = _required(raw, "answer_key", where)
        answer_key = _parse_answer_key(
            answer_key_raw, f"{where}.answer_key",
            case_top_level=raw,
        )
        if "expected" in raw and raw["expected"] is not None:
            raise SchemaError(
                f"{where}: security_eval cases MUST NOT carry an "
                f"expected list (SCHEMA.md §1)"
            )

    # title is required for acceptance; legacy security_eval cases
    # use category/cwe as identity, so synthesise a title for them.
    title = raw.get("title")
    if title is None:
        if case_type == CaseType.SECURITY_EVAL:
            title = f"{raw.get('cwe', case_id)} / {raw.get('project', '?')}"
        else:
            raise SchemaError(
                f"{where}: acceptance cases require a 'title'"
            )

    return Case(
        id=case_id,
        type=case_type,
        title=title,
        inputs=inputs,
        expected=expected,
        answer_key=answer_key,
        category=raw.get("category"),
        cwe=raw.get("cwe"),
        project=raw.get("project"),
        language=raw.get("language"),
        cve=raw.get("cve"),
        disclosed=raw.get("disclosed"),
        recall_risk=raw.get("recall_risk"),
        qe_catchable=raw.get("qe_catchable"),
    )


def parse_cases_file(raw_doc: dict) -> "list[Case]":
    """Parse the full ``cases.json`` doc per SCHEMA.md (the existing
    file shape is ``{"schema_version": "1", "note": "...",
    "cases": [...]}``)."""
    if not isinstance(raw_doc, dict):
        raise SchemaError(
            f"cases.json: top-level must be a dict; got "
            f"{type(raw_doc).__name__}"
        )
    cases_list = _required(raw_doc, "cases", "cases.json")
    if not isinstance(cases_list, list):
        raise SchemaError(
            f"cases.json.cases: must be a list; got "
            f"{type(cases_list).__name__}"
        )
    return [parse_case(c, f"cases[{i}]")
            for i, c in enumerate(cases_list)]


def load_cases_file(path: Path) -> "list[Case]":
    """Read + parse a ``cases.json`` file by path."""
    with open(path, "r", encoding="utf-8") as f:
        raw_doc = json.load(f)
    return parse_cases_file(raw_doc)


def _enum_to_str(v):
    """For dataclass serialization: emit enum members as their
    string values."""
    if isinstance(v, Enum):
        return v.value
    return v


def case_to_json(case: Case) -> dict:
    """Serialize a ``Case`` back to the JSON shape SCHEMA.md
    defines. Round-trip: ``parse_case(case_to_json(c)) == c`` for
    all enum-typed fields; optional fields with value ``None`` are
    dropped (cleaner JSON; round-trip is tolerant)."""
    out: dict = {
        "id": case.id,
        "type": case.type.value,
        "title": case.title,
        "inputs": {
            "repo_url": case.inputs.repo_url,
            "prep": case.inputs.prep.value,
        },
    }
    # Optional inputs fields.
    inp = case.inputs
    for k, v in (
        ("target_ref", inp.target_ref),
        ("reference_docs_source", inp.reference_docs_source),
        ("doc_sources", inp.doc_sources),
        ("scrub_terms", inp.scrub_terms),
        ("run_prompt", inp.run_prompt),
        ("vulnerable_parent", inp.vulnerable_parent),
    ):
        if v is not None:
            out["inputs"][k] = v
    if case.expected is not None:
        out["expected"] = [e.to_json() for e in case.expected]
    if case.answer_key is not None:
        ak_dict = {k: v for k, v in asdict(case.answer_key).items()
                   if v is not None}
        out["answer_key"] = ak_dict
    # Top-level optional discovery fields.
    for k, v in (
        ("category", case.category),
        ("cwe", case.cwe),
        ("project", case.project),
        ("language", case.language),
        ("cve", case.cve),
        ("disclosed", case.disclosed),
        ("recall_risk", case.recall_risk),
        ("qe_catchable", case.qe_catchable),
    ):
        if v is not None:
            out[k] = v
    return out


def run_invocation_to_json(inv: RunInvocation) -> dict:
    """Serialize a ``RunInvocation`` per SCHEMA.md §2.

    Note: the registry-channel ``@<version>`` suffix is re-attached
    to ``install_channel`` on serialization, matching the SCHEMA.md
    §3 raw shape: ``"pip-registry@1.5.7"`` etc.
    """
    channel_raw = inv.axes.install_channel.value
    if inv.axes.install_version is not None and inv.axes.install_channel in (
            InstallChannel.PIP_REGISTRY, InstallChannel.NPM_REGISTRY):
        channel_raw = f"{channel_raw}@{inv.axes.install_version}"
    out: dict = {
        "run_id": inv.run_id,
        "case_id": inv.case_id,
        "axes": {
            "runner": inv.axes.runner.value,
            "mode": inv.axes.mode.value,
            "install_channel": channel_raw,
            "install_version": inv.axes.install_version,
            "model": inv.axes.model,
            "thinking": inv.axes.thinking,
        },
        "qpb_version": inv.qpb_version,
        "target_sha": inv.target_sha,
        "cli_command": inv.cli_command,
        "cwd": inv.cwd,
        "env_snapshot": inv.env_snapshot,
        "scrubbed_docs_manifest": inv.scrubbed_docs_manifest,
        "leakage_gate": inv.leakage_gate,
        "started_at": inv.started_at,
        "ended_at": inv.ended_at,
        "exit_code": inv.exit_code,
        "terminal_state": inv.terminal_state.value,
    }
    return out


def parse_run_invocation(raw: dict, where: str = "invocation"
                         ) -> RunInvocation:
    """Parse an ``invocation.json`` document → ``RunInvocation``.

    Handles the SCHEMA.md §3 ``pip-registry@<version>`` channel-
    with-suffix shape: splits the suffix off into
    ``axes.install_version`` and stores the enum on
    ``axes.install_channel``.
    """
    axes_raw = _required(raw, "axes", where)
    awhere = f"{where}.axes"
    runner = _enum_or_raise(Runner, _required(axes_raw, "runner", awhere),
                             f"{awhere}.runner")
    mode = _enum_or_raise(Mode, _required(axes_raw, "mode", awhere),
                           f"{awhere}.mode")
    channel_raw = _required(axes_raw, "install_channel", awhere)
    install_version = axes_raw.get("install_version")
    if "@" in channel_raw:
        bare, _at, suffix = channel_raw.partition("@")
        # If install_version is also explicit, it must agree.
        if install_version is not None and install_version != suffix:
            raise SchemaError(
                f"{awhere}.install_channel: '@' suffix {suffix!r} "
                f"disagrees with axes.install_version "
                f"{install_version!r}"
            )
        install_version = suffix
        channel_enum_str = bare
    else:
        channel_enum_str = channel_raw
    install_channel = _enum_or_raise(
        InstallChannel, channel_enum_str,
        f"{awhere}.install_channel",
    )
    terminal_state = _enum_or_raise(
        TerminalState, _required(raw, "terminal_state", where),
        f"{where}.terminal_state",
    )
    axes = RunAxes(
        runner=runner,
        mode=mode,
        install_channel=install_channel,
        install_version=install_version,
        model=_required(axes_raw, "model", awhere),
        thinking=axes_raw.get("thinking"),
    )
    return RunInvocation(
        run_id=_required(raw, "run_id", where),
        case_id=_required(raw, "case_id", where),
        axes=axes,
        qpb_version=_required(raw, "qpb_version", where),
        target_sha=_required(raw, "target_sha", where),
        cli_command=_required(raw, "cli_command", where),
        cwd=_required(raw, "cwd", where),
        env_snapshot=raw.get("env_snapshot") or {},
        started_at=_required(raw, "started_at", where),
        ended_at=_required(raw, "ended_at", where),
        exit_code=_required(raw, "exit_code", where),
        terminal_state=terminal_state,
        scrubbed_docs_manifest=raw.get("scrubbed_docs_manifest"),
        leakage_gate=raw.get("leakage_gate"),
    )


# ---------------------------------------------------------------------------
# Fact object (de)serialization
# ---------------------------------------------------------------------------


def run_facts_to_json(facts: RunFacts) -> dict:
    """Serialize ``RunFacts`` per SCHEMA.md §5."""
    return {
        "phase0": asdict(facts.phase0),
        "verdict": {
            "verdict_state": facts.verdict.verdict_state.value,
            "attribution": facts.verdict.attribution.value,
            "recommends_stronger_model":
                facts.verdict.recommends_stronger_model,
            "bugs_unverified_present":
                facts.verdict.bugs_unverified_present,
        },
        "provenance": asdict(facts.provenance),
        "gate": {
            "gate_total": facts.gate.gate_total,
            "gate_result": facts.gate.gate_result.value,
            "cleanup_gaps": facts.gate.cleanup_gaps,
            # v1.5.7 097: independent counts (de-circularize
            # no_false_pass / no_false_fail in the grader).
            "substantive_fail_count":
                facts.gate.substantive_fail_count,
            "record_keeping_fail_count":
                facts.gate.record_keeping_fail_count,
        },
        "install": asdict(facts.install),
        "run_meta": asdict(facts.run_meta),
    }


def parse_run_facts(raw: dict, where: str = "facts") -> RunFacts:
    """Parse a ``facts.json`` document → ``RunFacts``. Used by the
    grader test fixtures + (Phase 2) the actual grader."""
    p0 = _required(raw, "phase0", where)
    vd = _required(raw, "verdict", where)
    pr = _required(raw, "provenance", where)
    gt = _required(raw, "gate", where)
    inst = _required(raw, "install", where)
    rm = _required(raw, "run_meta", where)
    return RunFacts(
        phase0=Phase0Facts(
            status=_required(p0, "status", f"{where}.phase0"),
            probe_attempts=_required(p0, "probe_attempts",
                                      f"{where}.phase0"),
            first_probe_ok=_required(p0, "first_probe_ok",
                                      f"{where}.phase0"),
        ),
        verdict=VerdictFacts(
            verdict_state=_enum_or_raise(
                VerdictState,
                _required(vd, "verdict_state", f"{where}.verdict"),
                f"{where}.verdict.verdict_state",
            ),
            attribution=_enum_or_raise(
                Attribution,
                _required(vd, "attribution", f"{where}.verdict"),
                f"{where}.verdict.attribution",
            ),
            recommends_stronger_model=_required(
                vd, "recommends_stronger_model",
                f"{where}.verdict",
            ),
            bugs_unverified_present=_required(
                vd, "bugs_unverified_present",
                f"{where}.verdict",
            ),
        ),
        provenance=ProvenanceFacts(
            detected_runner=_required(pr, "detected_runner",
                                        f"{where}.provenance"),
            selfreport_model_label=pr.get("selfreport_model_label"),
            gate_bug_count=_required(pr, "gate_bug_count",
                                       f"{where}.provenance"),
            reported_bug_count=pr.get("reported_bug_count"),
            provenance_mismatch=_required(
                pr, "provenance_mismatch", f"{where}.provenance",
            ),
        ),
        gate=GateFacts(
            gate_total=_required(gt, "gate_total", f"{where}.gate"),
            gate_result=_enum_or_raise(
                GateResult,
                _required(gt, "gate_result", f"{where}.gate"),
                f"{where}.gate.gate_result",
            ),
            cleanup_gaps=_required(gt, "cleanup_gaps",
                                     f"{where}.gate"),
            # v1.5.7 097 — fall back to 0 on legacy facts.json
            # without these counts (e.g. older receipts).
            substantive_fail_count=gt.get(
                "substantive_fail_count", 0,
            ),
            record_keeping_fail_count=gt.get(
                "record_keeping_fail_count", 0,
            ),
        ),
        install=InstallSurfaceFacts(
            banner_rendered=_required(inst, "banner_rendered",
                                        f"{where}.install"),
            gitignore_remediation_followed=_required(
                inst, "gitignore_remediation_followed",
                f"{where}.install",
            ),
        ),
        run_meta=RunMetaFacts(
            blocked=_required(rm, "blocked", f"{where}.run_meta"),
            stop_reason=rm.get("stop_reason"),
            exit_code=_required(rm, "exit_code",
                                  f"{where}.run_meta"),
            timings=rm.get("timings") or {},
            raw_receipt=_required(rm, "raw_receipt",
                                    f"{where}.run_meta"),
        ),
    )


# Public API: kept minimal. Downstream modules in this Phase 1
# substrate (prepare/runner/facts) reach in for the enums and the
# parser helpers as needed.
__all__ = [
    # Exceptions
    "SchemaError",
    # Case-level
    "CaseType", "PrepPolicy",
    # Run-level
    "Runner", "Mode", "InstallChannel", "TerminalState", "RunState",
    # Assertion vocabulary
    "AcceptanceAssertion", "SecurityAssertion", "Comparator",
    "GateResult", "VerdictState", "Attribution",
    "ProvenanceBugcountVsGate", "SecurityOutcome",
    # Dataclasses
    "CaseInputs", "ExpectedAssertion", "AnswerKey", "Case",
    "RunAxes", "RunInvocation",
    "Phase0Facts", "VerdictFacts", "ProvenanceFacts", "GateFacts",
    "InstallSurfaceFacts", "RunMetaFacts", "RunFacts",
    # Helpers
    "gate_result_from_raw",
    # JSON I/O
    "parse_case", "case_to_json",
    "parse_cases_file", "load_cases_file",
    "parse_run_invocation", "run_invocation_to_json",
    "parse_run_facts", "run_facts_to_json",
]
