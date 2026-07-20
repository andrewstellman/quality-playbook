"""v1.5.7 instruction 065 (A-14 + A-15 + A-16) — phase-boundary
artifact-contract validator.

Three artifact-shape ship-blockers surfaced in BOTH the virtio and
the 2026-05-16 express opus-4.6 Mode-A runs. In every case the
documented contract was already correct (schemas.md / phase prompts
/ reference guides) — opus simply ignored it, then reported PASS
against a gate that had actually FAILED. Prompt-level guidance alone
did not work; this is the structural fix: a CLI the agent MUST
invoke at phase boundaries that exit-codes on shape violations, so
non-compliance is mechanically detectable (mirrors the A-13
gate-verdict-witness pattern, but per-phase and earlier).

Defect classes (and ONLY these — this tool is a fast-fail SUBSET of
quality_gate.py's own §10 invariants, never a re-implementation of
the full gate; see instruction-065 halt-condition #1):

  A-14  Phase 2 manifest wrappers violate schemas.md §1.6: array
        key `bugs`/`requirements`/`use_cases` instead of canonical
        `records`; `generated_at` null/missing instead of an
        ISO-8601 timestamp. (citation_semantic_check.json is the
        documented §9.1 exception — it uses `reviews`.)
  A-15  quality/INDEX.md not emitted / missing §11 required fields
        (schemas.md §10 invariant #10 + §11).
  A-16  quality/exploration_role_map.json `breakdown` written as
        null instead of the canonical object (schemas.md §11.1 /
        bin/role_map.py `_REQUIRED_BREAKDOWN_KEYS`). The Mode-B
        runner auto-normalizes this between Phase 1 and Phase 2 via
        role_map.normalize_role_map_for_gate(); Mode A never calls
        it — that gap IS the A-16 root cause.

Consistency with quality_gate.py (deliberate, documented):
  - The breakdown-shape check reuses
    role_map._REQUIRED_BREAKDOWN_KEYS so it can never drift from the
    gate's check_role_map_consistency / role_map.validate_role_map.
  - The INDEX.md §11 required-field list mirrors
    quality_gate.py::_V150_INDEX_COMMON_FIELDS + target_role_breakdown
    (schemas.md §11 is the canonical contract; test coherence pins
    the mirror so it cannot silently drift).
  - `generated_at` is checked STRICTER here than the gate: the gate
    (check_v1_5_0_manifest_wrappers) only requires a non-empty
    string; this validator additionally requires it parse as ISO
    8601 with an explicit timezone (schemas.md §1.5 mandates
    "ISO 8601 with explicit timezone. Prefer Z"). This is
    intentionally stricter and NON-divergent: validator-PASS is a
    strict subset of gate-PASS for this field, so the validator can
    only fail-faster, never pass something the gate would fail.

Usage:

    python3 -m bin.validate_phase_artifacts <target> --phase {1|2|5|6}

Exit codes:
    0  all validations passed for the requested phase
    1  at least one violation (each FAIL line written to stdout)
    2  invalid usage / missing target

Final verdict line (instruction 067 F2): the LAST stdout line on
every exit path is a self-authenticating verdict mirroring
quality_gate.py's A-13 `RESULT: GATE PASSED|FAILED` shape —
`RESULT: VALIDATION PASSED (phase N)` (exit 0),
`RESULT: VALIDATION FAILED (phase N — X FAIL, Y PASS)` (exit 1), or
`RESULT: VALIDATION ERROR (phase N — usage; exit 2)` (exit 2). The
phase prompts mandate quoting this line verbatim so a static
reviewer can verify the validator actually ran and its verdict.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# v1.5.7 instruction 077 (addendum §5.2 W3 entry-point audit): put the
# QPB clone root on sys.path so script-form invocation
# (`python <clone>/bin/validate_phase_artifacts.py …` from any cwd)
# resolves the canonical `from bin import role_map` (and role_map's
# own sibling imports). No-op under `python -m
# bin.validate_phase_artifacts` (root already on sys.path). The
# try/except below remains as the flat/bundled-layout fallback.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# v1.5.7 090c: foreign-bin-proof import. 3-step ladder:
# (1) canonical package form, (2) flat-layout import, (3)
# path-load from THIS file's directory (anchored on __file__).
try:  # canonical package form (run from QPB root or PYTHONPATH set)
    from bin import role_map
except ModuleNotFoundError:
    try:  # flat/bundled layout: bin/ itself on sys.path
        import role_map  # type: ignore[no-redef]
    except ModuleNotFoundError:
        import importlib.util as _ilu
        _rm_path = Path(__file__).resolve().parent / "role_map.py"
        _rm_spec = _ilu.spec_from_file_location(
            "_qpb_role_map_via_validate_phase_artifacts", _rm_path,
        )
        if _rm_spec is None or _rm_spec.loader is None:
            raise ImportError(
                f"validate_phase_artifacts: cannot resolve "
                f"role_map — path-load fallback target "
                f"{_rm_path} is missing."
            )
        role_map = _ilu.module_from_spec(_rm_spec)  # type: ignore[no-redef]
        # v1.5.7 090c: register in sys.modules BEFORE exec_module
        # so dataclass/typing machinery resolves.
        sys.modules[_rm_spec.name] = role_map
        _rm_spec.loader.exec_module(role_map)


# v1.5.10 058 (D2 lockstep): import the gate's testable-language detector +
# disclosure-threshold helper so the validator's conditional disclosure
# check CANNOT drift from quality_gate.py. Same foreign-bin-proof ladder as
# role_map above. Degrades gracefully: if the gate module can't be located
# (unexpected), _gate_lang_helpers is None and the conditional is skipped
# (the gate's own check_v1_5_0_index_md remains the primary enforcement).
_gate_lang_helpers = None
try:  # path-load quality_gate.py next to this file (the bundled layout)
    import importlib.util as _ilu2
    _qg_path = Path(__file__).resolve().parent / "quality_gate.py"
    if _qg_path.is_file():
        _qg_spec = _ilu2.spec_from_file_location(
            "_qpb_quality_gate_via_validate_phase_artifacts", _qg_path,
        )
        if _qg_spec is not None and _qg_spec.loader is not None:
            _qg_mod = _ilu2.module_from_spec(_qg_spec)
            sys.modules[_qg_spec.name] = _qg_mod
            _qg_spec.loader.exec_module(_qg_mod)
            _gate_lang_helpers = (
                _qg_mod.detect_project_languages,
                _qg_mod.languages_over_disclosure_threshold,
            )
except Exception:  # noqa: BLE001 — never let an import break the validator
    _gate_lang_helpers = None


# Mirror of quality_gate.py::_V150_INDEX_COMMON_FIELDS +
# _V154_INDEX_CURRENT_FIELDS. schemas.md §11 is the canonical
# contract; test_validate_phase_artifacts pins this mirror so a
# schemas.md / gate change that this list misses is caught.
_INDEX_REQUIRED_FIELDS = (
    "run_timestamp_start",
    "run_timestamp_end",
    "duration_seconds",
    "qpb_version",
    "target_repo_path",
    "target_repo_git_sha",
    "phases_executed",
    "summary",
    "artifacts",
    "target_role_breakdown",
)
_INDEX_REQUIRED_SUMMARY_KEYS = ("requirements", "bugs", "gate_verdict")
# v1.5.7 089d (F17): "pass-with-cleanup" added — the INDEX gate_verdict
# value for the 089c three-state gate's `RESULT: GATE PASSED WITH
# CLEANUP NEEDED` line (review completed, bug findings stand, only
# audit record-keeping is incomplete; non-blocking, exit 0). Mirrors
# schemas.md §11 + SKILL.md + references/run_state_schema.md +
# references/phase6_verify_guide.md.
_INDEX_VALID_VERDICTS = ("pass", "pass-with-cleanup", "partial", "fail")

_RECORD_SHAPED_MANIFESTS = (
    "formal_docs_manifest.json",
    "requirements_manifest.json",
    "use_cases_manifest.json",
    "bugs_manifest.json",
)
_SEMANTIC_CHECK_MANIFEST = "citation_semantic_check.json"


def _load_json(path: Path):
    """Return (obj, error_message). error_message is None on success."""
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"{path.name}: file does not exist"
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, f"{path.name}: not valid JSON ({exc})"


def _is_iso8601_with_tz(value: str) -> bool:
    """True iff `value` parses as ISO 8601 with an explicit timezone
    (schemas.md §1.5: 'ISO 8601 with explicit timezone. Prefer Z')."""
    if not isinstance(value, str) or not value:
        return False
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _validate_phase1(quality: Path) -> tuple[list[str], list[str]]:
    passes: list[str] = []
    fails: list[str] = []

    rm_path = quality / "exploration_role_map.json"
    obj, err = _load_json(rm_path)
    if err is not None:
        fails.append(f"FAIL: {err} (A-16 — Phase 1 must emit a valid "
                     "exploration_role_map.json)")
    elif not isinstance(obj, dict):
        fails.append("FAIL: exploration_role_map.json top-level is not a "
                     "JSON object (A-16)")
    else:
        breakdown = obj.get("breakdown")
        if not isinstance(breakdown, dict):
            fails.append(
                "FAIL: exploration_role_map.json 'breakdown' is "
                f"{type(breakdown).__name__}, must be an object "
                "(A-16 — the express defect was `\"breakdown\": null`; "
                "populate via role_map.normalize_role_map_for_gate())"
            )
        else:
            missing = [k for k in role_map._REQUIRED_BREAKDOWN_KEYS
                       if k not in breakdown]
            if missing:
                fails.append(
                    "FAIL: exploration_role_map.json breakdown missing "
                    f"required key(s) {missing} (A-16; expected "
                    f"{list(role_map._REQUIRED_BREAKDOWN_KEYS)})"
                )
            else:
                passes.append("PASS: exploration_role_map.json breakdown "
                              "is a canonical object (§11.1)")

    expl = quality / "EXPLORATION.md"
    if not expl.is_file():
        fails.append("FAIL: quality/EXPLORATION.md does not exist "
                     "(Phase 1 foundation artifact)")
    elif len(expl.read_text(encoding="utf-8", errors="ignore").strip()) < 200:
        fails.append("FAIL: quality/EXPLORATION.md is trivially small "
                     "(< 200 chars) — Phase 1 produced no real content")
    else:
        passes.append("PASS: quality/EXPLORATION.md present and non-trivial")

    return passes, fails


def _validate_manifest_wrapper(
    quality: Path, name: str, array_key: str, other_key: str
) -> tuple[list[str], list[str]]:
    """Shared §1.6 / §9.1 wrapper check. `array_key` is the record
    array this manifest must carry (`records` for the four
    record-shaped manifests; `reviews` for citation_semantic_check.json
    per §9.1). `other_key` is the array key it must NOT carry."""
    passes: list[str] = []
    fails: list[str] = []
    path = quality / name
    if not path.is_file():
        return passes, fails  # absent manifest: not this validator's defect
    obj, err = _load_json(path)
    if err is not None:
        fails.append(f"FAIL: {err} (A-14 — schemas.md §1.6)")
        return passes, fails
    if not isinstance(obj, dict):
        fails.append(f"FAIL: {name} top-level is not a JSON object "
                     "(schemas.md §1.6)")
        return passes, fails

    sv = obj.get("schema_version")
    if not isinstance(sv, str) or not sv:
        fails.append(f"FAIL: {name} missing/empty top-level "
                     "'schema_version' (schemas.md §1.6)")

    ga = obj.get("generated_at")
    if not isinstance(ga, str) or not ga:
        fails.append(
            f"FAIL: {name} 'generated_at' is "
            f"{ga!r} — must be an ISO 8601 timestamp with explicit "
            "timezone, not null/empty (schemas.md §1.6; the express "
            "defect was `\"generated_at\": null`)"
        )
    elif not _is_iso8601_with_tz(ga):
        fails.append(
            f"FAIL: {name} 'generated_at'={ga!r} is not ISO 8601 with "
            "an explicit timezone (schemas.md §1.5 — prefer "
            "'2026-05-16T22:30:00Z')"
        )

    if not isinstance(obj.get(array_key), list):
        fails.append(
            f"FAIL: {name} missing top-level {array_key!r} array "
            f"(schemas.md §1.6{'/§9.1' if array_key == 'reviews' else ''}"
            f"). Found keys: {sorted(obj.keys())}"
        )
    if other_key in obj:
        fails.append(
            f"FAIL: {name} has reserved key {other_key!r} — this "
            f"manifest must use {array_key!r} "
            f"(schemas.md §9.1 / §10 invariant #13)"
        )

    if not fails:
        passes.append(f"PASS: {name} wrapper §1.6 valid "
                      f"(uses {array_key!r})")
    return passes, fails


def _has_tier12_reqs(quality: Path) -> bool:
    """True iff requirements_manifest.json exists and carries at least
    one record with ``tier`` in (1, 2) — the schemas.md §9.1 condition
    under which citation_semantic_check.json becomes required.
    Defensive: any load/shape problem → False (the absent-manifest
    FAIL for requirements_manifest.json itself covers that case)."""
    obj, err = _load_json(quality / "requirements_manifest.json")
    if err is not None or not isinstance(obj, dict):
        return False
    recs = obj.get("records")
    if not isinstance(recs, list):
        return False
    for r in recs:
        if isinstance(r, dict):
            t = r.get("tier")
            if t in (1, 2) and not isinstance(t, bool):
                return True
    return False


def _validate_phase2(quality: Path) -> tuple[list[str], list[str]]:
    passes: list[str] = []
    fails: list[str] = []
    # A-19 (instruction 072/073): every record-shaped manifest is
    # UNCONDITIONALLY required for Phase 2. File ABSENCE is a defect in
    # its own right — the 2026-05-17 httpx run skipped manifest
    # generation entirely (not merely wrong-shape per A-14), reached
    # Phase 6, and self-reported pass. Absent → explicit FAIL; present
    # → the existing schemas.md §1.6 shape check.
    for name in _RECORD_SHAPED_MANIFESTS:
        if not (quality / name).is_file():
            fails.append(
                f"FAIL: required Phase 2 manifest absent: quality/{name} "
                "(schemas.md §1.6 requires this manifest to be present; "
                "the 2026-05-17 httpx run skipped manifest generation "
                "entirely — write it per schemas.md §6/§7/§8)"
            )
            continue
        p, f = _validate_manifest_wrapper(
            quality, name, array_key="records", other_key="reviews"
        )
        passes += p
        fails += f
    # citation_semantic_check.json is CONDITIONALLY required per
    # schemas.md §9.1 — only when requirements_manifest.json carries a
    # Tier 1/2 REQ. When present it must use the `reviews` array.
    if (quality / _SEMANTIC_CHECK_MANIFEST).is_file():
        p, f = _validate_manifest_wrapper(
            quality, _SEMANTIC_CHECK_MANIFEST,
            array_key="reviews", other_key="records",
        )
        passes += p
        fails += f
    elif _has_tier12_reqs(quality):
        fails.append(
            "FAIL: required Phase 2 manifest absent: "
            f"quality/{_SEMANTIC_CHECK_MANIFEST} (schemas.md §9.1 "
            "requires it when requirements_manifest.json has Tier 1/2 "
            "REQs)"
        )
    else:
        passes.append(
            f"PASS: {_SEMANTIC_CHECK_MANIFEST} not required — no Tier "
            "1/2 REQs (schemas.md §9.1 vacuous case)"
        )
    # v1.6.0 Feature C: RUN_CONTRACT.md is CONDITIONALLY required — only
    # when requirements_manifest.json carries at least one tool-contract
    # REQ (references[] pointing exclusively into quality/). Same
    # conditional shape as citation_semantic_check.json above, and for the
    # same reason this module exists at all: phase boundaries should reject
    # an incomplete artifact set AT the boundary rather than deferring to
    # the Phase 6 gate. Deliberately NOT added to the unconditional
    # required_fixed list in run_state_lib.py, which would retroactively
    # fail every archived pre-v1.6.0 Phase-2 tree.
    tool_contract_ids = _tool_contract_req_ids(quality)
    if not tool_contract_ids:
        passes.append(
            "PASS: RUN_CONTRACT.md not required — no tool-contract REQs "
            "in requirements_manifest.json (v1.6.0 Design §5.1 vacuous case)"
        )
    elif (quality / "RUN_CONTRACT.md").is_file():
        passes.append(
            f"PASS: RUN_CONTRACT.md present for {len(tool_contract_ids)} "
            "tool-contract REQ(s)"
        )
    else:
        fails.append(
            "FAIL: required Phase 2 artifact absent: quality/RUN_CONTRACT.md "
            f"({len(tool_contract_ids)} tool-contract REQ(s) in "
            "requirements_manifest.json render there, not into "
            "REQUIREMENTS.md — v1.6.0 Design §5.1; see "
            "references/phase2_generation_guide.md § 'Split the product "
            "spec from the tool contract')"
        )
    return passes, fails


def _tool_contract_req_ids(quality: Path) -> list[str]:
    """REQ ids whose references[] point exclusively into quality/.

    These are QPB's own run-layout invariants, not requirements of the
    audited system. Returns [] when the manifest is absent or unreadable —
    an absent manifest is already a FAIL above, and this helper must not
    manufacture a second, confusing failure for the same cause.
    """
    path = quality / "requirements_manifest.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    records = data.get("records")
    if not isinstance(records, list):
        return []
    ids = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        refs = rec.get("references")
        if not isinstance(refs, list) or not refs:
            continue
        if all(str(r).startswith("quality/") for r in refs):
            rid = rec.get("id")
            if rid:
                ids.append(str(rid))
    return ids


def _load_index_payload(quality: Path) -> tuple[dict | None, str | None]:
    path = quality / "INDEX.md"
    if not path.is_file():
        return None, ("quality/INDEX.md does not exist (required on "
                      "every run per schemas.md §10 invariant #10 / "
                      "§11) — A-15")
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)
    if not m:
        return None, "quality/INDEX.md: no fenced ```json block (schemas.md §11)"
    try:
        payload = json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        return None, f"quality/INDEX.md: fenced JSON invalid ({exc})"
    if not isinstance(payload, dict):
        return None, "quality/INDEX.md: fenced JSON block is not an object"
    return payload, None


def _validate_index(quality: Path, phase: int, check_verdict_value: bool
                    ) -> tuple[list[str], list[str]]:
    passes: list[str] = []
    fails: list[str] = []
    payload, err = _load_index_payload(quality)
    if err is not None:
        fails.append(f"FAIL: {err}")
        return passes, fails

    # v1.5.7 089e (BUG-014, Option A — phase-aware schema_version
    # enforcement). The gate's `check_v1_5_0_index_md` case-4 is
    # deliberately lenient on missing `schema_version` so a Phase 1
    # stub-INDEX (written before the field has been set) doesn't
    # FAIL — that tolerance is a design point per the schema-routing
    # block at .github/skills/quality_gate/quality_gate.py:2820. The
    # validator now matches that intent:
    #
    #   phase >= 5  → Phase 5/6 final INDEX MUST have
    #                 schema_version == "2.0" (strict — schemas.md
    #                 §11: "New runs MUST emit schema_version:
    #                 '2.0'"). Wrong value still FAILs.
    #   phase  < 5  → Phase 1/2 stub-INDEX MAY omit schema_version
    #                 (matches gate case-4). If present, must be
    #                 "2.0" (wrong value still FAILs at stub stage).
    #
    # The divergence-with-gate at Phase 5/6 (gate lenient via case-4,
    # validator strict) is intentional and documented: the validator
    # is the canonical Phase 5/6 enforcement surface; gate case-4 is
    # best-effort archive-tolerance.
    sv = payload.get("schema_version")
    if phase >= 5:
        if sv != "2.0":
            fails.append(
                f"FAIL: quality/INDEX.md schema_version={sv!r} — a "
                f"Phase {phase} final INDEX MUST emit '2.0' "
                "(schemas.md §11; '1.0'/absent is the archived-legacy "
                "read path only)"
            )
    else:
        # Phase 1/2 stub-INDEX: missing is OK (gate case-4 territory).
        # If present, must be the current value.
        if sv is not None and sv != "2.0":
            fails.append(
                f"FAIL: quality/INDEX.md schema_version={sv!r} — if "
                f"present at Phase {phase}, must be '2.0' (missing is "
                "permitted on stub-INDEX per BUG-014 / 089e)"
            )

    for key in _INDEX_REQUIRED_FIELDS:
        if key not in payload:
            fails.append(f"FAIL: quality/INDEX.md missing required field "
                         f"{key!r} (schemas.md §11) — A-15")
        elif isinstance(payload[key], str) and not payload[key]:
            fails.append(f"FAIL: quality/INDEX.md field {key!r} is an "
                         "empty string (schemas.md §11)")

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        fails.append("FAIL: quality/INDEX.md 'summary' is not an object "
                     "(schemas.md §11)")
    else:
        for sub in _INDEX_REQUIRED_SUMMARY_KEYS:
            if sub not in summary:
                fails.append(f"FAIL: quality/INDEX.md summary missing "
                             f"{sub!r} sub-key (schemas.md §11)")
        if check_verdict_value and "gate_verdict" in summary:
            gv = summary.get("gate_verdict")
            if gv not in _INDEX_VALID_VERDICTS:
                fails.append(
                    f"FAIL: quality/INDEX.md summary.gate_verdict={gv!r} "
                    f"must be one of {list(_INDEX_VALID_VERDICTS)} "
                    "(schemas.md §11)"
                )
        # v1.5.10 058 (D2 lockstep): conditional multi-language disclosure
        # fields. Mirrors quality_gate.py::check_v1_5_0_index_md — when >=2
        # testable languages clear the disclosure threshold (computed on
        # quality.parent via the gate's own detector, so it can't drift),
        # languages_detected / ran_on / untested_testable_languages MUST be
        # present and non-empty. Legacy archives (schema_version "1.0") are
        # exempt, matching the gate's is_legacy exemption. Skipped if the
        # gate helpers couldn't be imported.
        if _gate_lang_helpers is not None and sv != "1.0":
            _detect, _over = _gate_lang_helpers
            try:
                fires = len(_over(_detect(quality.parent))) >= 2
            except Exception:  # noqa: BLE001 — detection must not crash
                fires = False
            if fires:
                for sub in (
                    "languages_detected", "ran_on",
                    "untested_testable_languages",
                ):
                    if sub not in summary:
                        fails.append(
                            f"FAIL: quality/INDEX.md summary missing {sub!r} "
                            "sub-key — required because >=2 testable "
                            "languages clear the disclosure threshold "
                            "(schemas.md §11; v1.5.10 058)"
                        )
                    elif summary[sub] in (None, "", []):
                        fails.append(
                            f"FAIL: quality/INDEX.md summary {sub!r} is empty "
                            "— multi-language disclosure requires a value "
                            "(schemas.md §11; v1.5.10 058)"
                        )

    if not fails:
        passes.append("PASS: quality/INDEX.md present with all §11 "
                      "required fields"
                      + (" + valid gate_verdict" if check_verdict_value
                         else ""))
    return passes, fails


_PHASE_DISPATCH = {
    1: lambda q: _validate_phase1(q),
    2: lambda q: _validate_phase2(q),
    # v1.5.7 089e (BUG-014): _validate_index now takes phase to
    # support phase-aware schema_version enforcement (Phase 1/2 stub
    # accepts missing; Phase 5/6 final requires '2.0').
    5: lambda q: _validate_index(q, 5, check_verdict_value=False),
    6: lambda q: _validate_index(q, 6, check_verdict_value=True),
}


def validate(target: Path, phase: int) -> tuple[list[str], list[str]]:
    quality = target / "quality"
    return _PHASE_DISPATCH[phase](quality)


def main(argv: list[str] | None = None) -> int:
    # v1.5.7 089x: no-args is purpose-banner-safe.
    _argv_list_089x = list(sys.argv[1:] if argv is None else argv)
    try:
        from bin._purpose import print_command_intro as _print_command_intro
        from bin._purpose import print_help_banner as _print_help_banner
    except ImportError:
        from _purpose import print_command_intro as _print_command_intro  # type: ignore[no-redef]
        from _purpose import print_help_banner as _print_help_banner  # type: ignore[no-redef]
    if not _argv_list_089x:
        _print_command_intro(
            name='validate_phase_artifacts',
            summary=(
            "Per-phase artifact validator — checks that the phase's "
            "expected output files exist, are non-empty, and conform "
            "to the schema. "
            ),
            role=(
            "Called between phases (and by the Phase 6 gate) to "
            "catch structural drift early — a "
            "missing/empty/malformed phase artifact aborts the run "
            "before the next phase reads it. "
            ),
            usage_hint='python3 -m bin.validate_phase_artifacts <target> --phase 2',
        )
        return 0

    # v1.5.7 090a: full attribution banner at top of --help.
    _print_help_banner(_argv_list_089x)

    parser = argparse.ArgumentParser(
        prog="python3 -m bin.validate_phase_artifacts",
        description="Phase-boundary artifact-contract validator "
                    "(A-14/A-15/A-16). Fast-fail subset of "
                    "quality_gate.py — run at phase boundaries.",
    )
    parser.add_argument("target", help="Path to the target repo "
                        "(the dir containing quality/).")
    parser.add_argument("--phase", type=int, required=True,
                        choices=(1, 2, 5, 6),
                        help="Which phase boundary to validate.")
    args = parser.parse_args(argv)

    target = Path(args.target)
    if not target.is_dir():
        print(f"USAGE ERROR: target {args.target!r} is not a directory",
              file=sys.stderr)
        print(f"RESULT: VALIDATION ERROR (phase {args.phase} — usage; "
              "exit 2)")
        return 2
    if not (target / "quality").is_dir():
        print(f"USAGE ERROR: {args.target!r} has no quality/ directory "
              "(run from the target repo root, after the phase ran)",
              file=sys.stderr)
        print(f"RESULT: VALIDATION ERROR (phase {args.phase} — usage; "
              "exit 2)")
        return 2

    passes, fails = validate(target, args.phase)
    for line in passes:
        print(line)
    for line in fails:
        print(line)
    print(f"--- phase {args.phase}: {len(passes)} PASS, "
          f"{len(fails)} FAIL ---")
    # Self-authenticating final verdict line (A-13-shaped — mirrors
    # quality_gate.py's `RESULT: GATE PASSED|FAILED` so the agent has
    # a familiar, quoteable, statically-verifiable witness; instruction
    # 067 F2 closing the 065 codex HALT). ALWAYS the last stdout line,
    # on every exit path (0/1/2), so a static reviewer reading the
    # agent's chat can verify the validator actually ran + its verdict.
    if fails:
        print(f"RESULT: VALIDATION FAILED (phase {args.phase} — "
              f"{len(fails)} FAIL, {len(passes)} PASS)")
        return 1
    print(f"RESULT: VALIDATION PASSED (phase {args.phase})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
