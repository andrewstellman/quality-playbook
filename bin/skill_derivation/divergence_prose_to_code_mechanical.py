"""divergence_prose_to_code_mechanical.py — Phase 4 Part A.2:
mechanical (Tier 1) prose-to-code divergence detection.

For each REQ in pass_c_formal.jsonl whose acceptance_criteria contains
a countable claim about code (e.g., "the gate runs 45 checks"), this
module:

  1. Identifies the named code artifact via heuristic
     (skill_section context + explicit filename mentions).
  2. Mechanically counts the relevant entity in the artifact
     ("checks" -> regex `^def check_*`, "phases" -> regex
     `^### Phase \\d+`, "tests" -> regex `^def test_*`, etc.).
  3. Compares claimed count vs actual count. Mismatches emit a
     divergence record.

Per the Phase 4 brief Part A.2, this module:
- Skips REQs associated with un-anchored UCs (the un_anchored_uc_ids
  set returned by Part A.1).
- Targets Hybrid projects only when the artifact is code (the
  artifact-locator returns None on Skill projects with no code
  references).
- Is pure-mechanical and idempotent. Re-run by deleting the output
  file.

Output: quality/phase3/pass_e_prose_to_code_divergences.jsonl. The
LLM-driven Tier 2 (Part A.3) appends to the same file.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


# Re-use the countable-noun regex + Phase 5 Stage 1 precision filters
# from divergence_internal so the two modules see the same set of
# countable claims AND the same hedge / parenthetical / ordinal
# context filters.
from bin.skill_derivation.divergence_internal import (
    _COUNTABLE_RE,
    _normalize_token,
    _filtered_countable_matches,
)


# Mapping: (normalized_noun) -> (default_artifact_path_relative_to_repo,
#                                code_count_pattern_regex_string,
#                                regex_flags).
#
# Phase 5 Stage 1E (Round 8 DN-3 + Phase 4 G.2 audit-back): every
# pattern uses `^\s*` (rather than the bare `^`) so indented
# declarations are counted. Phase 4's QPB G.1 silently miscounted
# `def test_*` methods as 0 because tests live inside
# unittest.TestCase classes (indented). The same shape of bug could
# surface on another corpus where:
#   * `def check_*` lives inside a class (currently top-level in
#     quality_gate.py — verified 34 top-level, 0 indented at HEAD
#     `43ddaee`);
#   * `def run_pass_*` is moved into a Pass*Driver class (currently
#     top-level in pass_a.py..pass_d.py — verified 4 top-level,
#     0 indented);
#   * `## Phase N` is nested under another heading (currently
#     top-level in SKILL.md — verified 9 top-level, 0 indented).
# Switching to `^\s*` is a no-op against the current QPB corpus and
# defensive against future structural moves.
_CODE_PATTERNS: dict[str, tuple[str, str, int]] = {
    "check": (
        ".github/skills/quality_gate/quality_gate.py",
        r"^\s*def check_",
        re.MULTILINE,
    ),
    "phase": (
        "SKILL.md",
        r"^\s*##\s+Phase\s+\d+",
        re.MULTILINE,
    ),
    "test": (
        "bin/tests/",  # directory; resolver counts def test_ across all .py
        # Tests are methods inside unittest.TestCase classes (indented);
        # the leading \s* matches both top-level and indented forms.
        r"^\s*def test_",
        re.MULTILINE,
    ),
    "pass": (
        "bin/skill_derivation/",  # pass_a/b/c/d.py — counts run_pass_ across all .py
        r"^\s*def run_pass_",
        re.MULTILINE,
    ),
}


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _count_in_artifact(
    repo_root: Path, artifact_rel: str, pattern: str, flags: int
) -> Optional[tuple[int, str]]:
    """Return (count, artifact_path) or None if the artifact doesn't
    exist. For directory artifacts, recurse into .py / .md files."""
    artifact_path = repo_root / artifact_rel
    if artifact_path.is_file():
        text = artifact_path.read_text(encoding="utf-8", errors="replace")
        return (len(re.findall(pattern, text, flags)), str(artifact_rel))
    if artifact_path.is_dir():
        total = 0
        for py in sorted(artifact_path.rglob("*.py")):
            text = py.read_text(encoding="utf-8", errors="replace")
            total += len(re.findall(pattern, text, flags))
        return (total, str(artifact_rel))
    return None


@dataclass
class ProseToCodeMechanicalConfig:
    formal_path: Path  # input: pass_c_formal.jsonl
    output_path: Path  # output: pass_e_prose_to_code_divergences.jsonl
    repo_root: Path  # repo root for resolving artifact paths
    sections_path: Path  # for section_heading lookup
    skipped_uc_ids: tuple = ()  # un-anchored UCs (Part A.1) to skip
    starting_div_idx: int = 1


def run_divergence_prose_to_code_mechanical(
    config: ProseToCodeMechanicalConfig,
) -> dict:
    """Drive Part A.2 end-to-end. Returns summary dict.

    Output schema (per the Phase 4 brief):
        {divergence_id, divergence_type="prose-to-code",
         subtype="mechanical-countable", req_id, source_document,
         section_idx, section_heading, excerpt, claimed_count,
         code_artifact, code_count_pattern, actual_count,
         provisional_disposition ("spec-fix" | "code-fix"),
         rationale, triage_batch_key}
    """
    reqs = _read_jsonl(config.formal_path)
    skipped_uc_ids = set(config.skipped_uc_ids or ())

    # If this run accumulates onto a prior file (e.g., Tier 2 appending
    # later), the brief specifies we re-run by deleting the output;
    # so we always start fresh here.
    output_lines: list[str] = []
    div_idx = config.starting_div_idx
    examined = 0
    matched_artifacts = 0

    for req in reqs:
        # Skip REQs derived from un-anchored UCs. The Phase 3 schema
        # doesn't link REQs to UCs directly; the practical proxy is
        # to skip REQs whose `req_id` (or any UC ID embedded in their
        # rationale) appears in skipped_uc_ids. UCs and REQs are
        # distinct artifacts in Phase 3, so in practice this filter
        # rarely fires; it's the documented hook from the brief.
        if req.get("id") in skipped_uc_ids:
            continue

        excerpt = (
            req.get("citation_excerpt")
            or req.get("acceptance_criteria", "")
            or ""
        )
        # Phase 5 Stage 1 (DQ-5-4): use filtered matches. Drops
        # ordinal-context numbers ("Tier 2 REQ"), hedge words
        # ("typically 50 tests"), and parenthetical conditions
        # ("(5-15 source files)"). Each entry is (num: int, noun: str,
        # match_start: int, artifacts: set).
        matches = _filtered_countable_matches(excerpt)
        if not matches:
            continue
        examined += 1

        for num_int, noun, _match_start, _artifacts in matches:
            num_str = str(num_int)
            token = _normalize_token(noun)
            artifact_spec = _CODE_PATTERNS.get(token)
            if artifact_spec is None:
                continue
            artifact_rel, pattern, flags = artifact_spec
            counted = _count_in_artifact(
                config.repo_root, artifact_rel, pattern, flags
            )
            if counted is None:
                continue
            actual_count, artifact_path_str = counted
            matched_artifacts += 1
            claimed_count = int(num_str)
            if claimed_count == actual_count:
                continue

            # Mismatch — emit divergence. Provisional disposition:
            # if the prose looks under-counted (claimed < actual), the
            # spec is stale (spec-fix); if claimed > actual, the code
            # is incomplete (code-fix). This is the mechanical default;
            # Council can override.
            disp = "spec-fix" if claimed_count > actual_count else "spec-fix"
            # ^ actually keep the rule simple: prose is the side that
            # diverges from the verifiable code; default to spec-fix.
            # Use code-fix only when claimed > actual (the prose
            # promises more than the code delivers).
            disp = "code-fix" if claimed_count > actual_count else "spec-fix"

            source_document = req.get("source_document") or "SKILL.md"
            section_idx = req.get("section_idx")
            rec = {
                "divergence_id": f"DIV-P2C-{div_idx:03d}",
                "divergence_type": "prose-to-code",
                "subtype": "mechanical-countable",
                "req_id": req.get("id"),
                "source_document": source_document,
                "section_idx": section_idx,
                "section_heading": _section_heading(
                    config.sections_path, source_document, section_idx,
                ),
                "excerpt": excerpt,
                "claimed_count": claimed_count,
                "code_artifact": artifact_path_str,
                "code_count_pattern": pattern,
                "actual_count": actual_count,
                "provisional_disposition": disp,
                "rationale": (
                    f"Prose claims {claimed_count} {noun} (REQ "
                    f"{req.get('id')}), code matches "
                    f"{actual_count} via {pattern!r} in "
                    f"{artifact_path_str}."
                ),
                "triage_batch_key": (
                    f"{source_document}::{section_idx}"
                    if section_idx is not None
                    else f"{source_document}::unknown"
                ),
            }
            output_lines.append(json.dumps(rec, sort_keys=False))
            div_idx += 1

    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.output_path.with_name(config.output_path.name + ".tmp")
    tmp.write_text(
        ("\n".join(output_lines) + "\n") if output_lines else "",
        encoding="utf-8",
    )
    os.replace(tmp, config.output_path)

    return {
        "divergences_emitted": len(output_lines),
        "reqs_with_countable_claim": examined,
        "reqs_with_resolvable_artifact": matched_artifacts,
    }


def _section_heading(sections_path: Path, document: str, section_idx) -> str:
    if section_idx is None or not sections_path.is_file():
        return ""
    payload = json.loads(sections_path.read_text(encoding="utf-8"))
    for s in payload.get("sections", []):
        if s.get("section_idx") == section_idx and s.get("document") == document:
            return s.get("heading", "") or ""
    return ""


# v1.5.7 089x: every bin/*.py is safe + self-describing on no-args.
if __name__ == "__main__":
    try:
        from bin._purpose import print_purpose as _print_purpose
    except ImportError:
        from _purpose import print_purpose as _print_purpose  # type: ignore[no-redef]
    _print_purpose(
        name='skill_derivation.divergence_prose_to_code_mechanical',
        summary=(
            "Prose-to-code divergence detector (mechanical lane) — "
            "string/AST analysis variant that runs without an LLM call. "
        ),
        role=(
            "Imported by skill_derivation pass C as the cross-check pair "
            "for the LLM detector. "
        ),
        kind="library",
    )
    import sys as _sys
    _sys.exit(0)
