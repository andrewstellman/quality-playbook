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
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

try:  # canonical package form (run from QPB root or PYTHONPATH set)
    from bin import role_map
except ModuleNotFoundError:  # flat/bundled layout: bin/ itself on sys.path
    import role_map  # type: ignore[no-redef]


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
_INDEX_VALID_VERDICTS = ("pass", "partial", "fail")

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


def _validate_phase2(quality: Path) -> tuple[list[str], list[str]]:
    passes: list[str] = []
    fails: list[str] = []
    seen_any = False
    for name in _RECORD_SHAPED_MANIFESTS:
        if (quality / name).is_file():
            seen_any = True
        p, f = _validate_manifest_wrapper(
            quality, name, array_key="records", other_key="reviews"
        )
        passes += p
        fails += f
    if (quality / _SEMANTIC_CHECK_MANIFEST).is_file():
        seen_any = True
        p, f = _validate_manifest_wrapper(
            quality, _SEMANTIC_CHECK_MANIFEST,
            array_key="reviews", other_key="records",
        )
        passes += p
        fails += f
    if not seen_any:
        fails.append(
            "FAIL: no Phase 2 manifests found in quality/ "
            "(expected at least one of "
            f"{list(_RECORD_SHAPED_MANIFESTS)}) — Phase 2 produced "
            "nothing to validate"
        )
    return passes, fails


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


def _validate_index(quality: Path, check_verdict_value: bool
                    ) -> tuple[list[str], list[str]]:
    passes: list[str] = []
    fails: list[str] = []
    payload, err = _load_index_payload(quality)
    if err is not None:
        fails.append(f"FAIL: {err}")
        return passes, fails

    # A current run's Phase 5/6 INDEX MUST be the v1.5.4 contract
    # (schemas.md §11: "New runs MUST emit schema_version: '2.0'").
    # The gate is lenient for *archived* INDEX files; this validator
    # runs against the live run, so 2.0 is required, not optional.
    sv = payload.get("schema_version")
    if sv != "2.0":
        fails.append(
            f"FAIL: quality/INDEX.md schema_version={sv!r} — a current "
            "run MUST emit '2.0' (schemas.md §11; '1.0'/absent is the "
            "archived-legacy read path only)"
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

    if not fails:
        passes.append("PASS: quality/INDEX.md present with all §11 "
                      "required fields"
                      + (" + valid gate_verdict" if check_verdict_value
                         else ""))
    return passes, fails


_PHASE_DISPATCH = {
    1: lambda q: _validate_phase1(q),
    2: lambda q: _validate_phase2(q),
    5: lambda q: _validate_index(q, check_verdict_value=False),
    6: lambda q: _validate_index(q, check_verdict_value=True),
}


def validate(target: Path, phase: int) -> tuple[list[str], list[str]]:
    quality = target / "quality"
    return _PHASE_DISPATCH[phase](quality)


def main(argv: list[str] | None = None) -> int:
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
        return 2
    if not (target / "quality").is_dir():
        print(f"USAGE ERROR: {args.target!r} has no quality/ directory "
              "(run from the target repo root, after the phase ran)",
              file=sys.stderr)
        return 2

    passes, fails = validate(target, args.phase)
    for line in passes:
        print(line)
    for line in fails:
        print(line)
    print(f"--- phase {args.phase}: {len(passes)} PASS, "
          f"{len(fails)} FAIL ---")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
