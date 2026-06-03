"""divergence_prose_to_code_llm.py — Phase 4 Part A.3: Tier 2
LLM-driven prose-to-code divergence detection (Hybrid only).

For each REQ whose claims are non-countable (i.e., didn't fire the
mechanical regex) AND the code artifact can be located AND the
project classification is Hybrid, this module invokes the same
LLMRunner abstraction as Phase 3 (claude --print --model sonnet) with
a prompt asking: "Given this prose claim from SKILL.md and this code
region, does the code implement the claim? Return JSON
{verdict, rationale}." Non-matching verdicts (`diverges` or
`unclear`) are appended to pass_e_prose_to_code_divergences.jsonl as
subtype="llm-judged".

Resumability per the Phase 4 brief: per-REQ progress in
quality/phase3/pass_e_prose_to_code_progress.json (cursor + status),
atomic tmp-file-then-rename writes, recovery preamble in the LLM
prompt mirroring Phase 3's pattern. Crashed mid-run → restart resumes
from cursor.

For Skill (non-Hybrid) projects: A.3 is a no-op; emits zero LLM
calls and returns immediately.

Tests pass a MockRunner via the runner argument; the production
default is bin.skill_derivation.runners.make_runner("claude").
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from bin.skill_derivation import protocol
from bin.skill_derivation.runners import LLMRunner

# Re-use mechanical module's countable regex / token mapping so we
# can identify "non-countable" REQs as those WITHOUT countable claims.
from bin.skill_derivation.divergence_internal import _COUNTABLE_RE


_PROMPT_TEMPLATE = """\
{recovery_preamble}

---

# Phase 4 Part A.3 — Prose-to-code divergence (one REQ)

You are evaluating whether a prose claim from a skill's SKILL.md is
implemented by a region of code. Return JSON only — no commentary.

## REQ under review

REQ id: `{req_id}`
Source document: `{source_document}`
Section: `{section_heading}`

Claim (prose):
```
{claim}
```

## Code region

File: `{code_artifact}`

```
{code_region}
```

## Output format (strict JSON, single line)

```
{{"verdict": "matches" | "diverges" | "unclear", "rationale": "<one sentence>"}}
```

- `matches`: the code clearly implements the prose claim.
- `diverges`: the code clearly does NOT implement the claim, or
  implements something contradictory.
- `unclear`: cannot determine from this excerpt; needs human review.

Emit exactly one JSON object on one line. Begin below this line.
"""


@dataclass
class ProseToCodeLLMConfig:
    formal_path: Path  # input: pass_c_formal.jsonl
    output_path: Path  # output: pass_e_prose_to_code_divergences.jsonl (append)
    progress_path: Path  # cursor file
    repo_root: Path
    sections_path: Path
    pass_spec_path: Path  # for the recovery preamble
    # v1.5.4 Phase 2 Site 3: the prose-to-code LLM divergence check
    # activates iff the Phase-1 role map reports skill-tool files —
    # scripts the skill prose explicitly invokes, which are the only
    # subjects of the prose-to-code claim. Replaces the v1.5.3
    # project_type=='Hybrid' gate, which keyed on a label that no
    # longer exists in the run path. Defaults to False so an empty
    # config short-circuits to a clean no-op.
    should_run: bool = False
    skipped_uc_ids: tuple = ()
    starting_div_idx: int = 1
    pace_seconds: int = 0


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _is_non_countable(req: dict) -> bool:
    """A REQ is non-countable when its acceptance_criteria does NOT
    match the countable regex. The mechanical Tier 1 (Part A.2)
    handles countable REQs; Tier 2 picks up the rest."""
    text = (
        req.get("citation_excerpt")
        or req.get("acceptance_criteria", "")
        or ""
    )
    return not _COUNTABLE_RE.search(text)


def _resolve_code_region(req: dict, repo_root: Path) -> Optional[tuple[str, str]]:
    """Heuristic: a REQ's code region is the file referenced in
    citation_excerpt / acceptance_criteria via a path-like token. Also
    accepts source_document when it's already a code file under
    .github/skills or bin/. Returns (artifact_relpath, region_text)
    or None.
    """
    text = (
        (req.get("citation_excerpt") or "")
        + "\n"
        + (req.get("acceptance_criteria") or "")
    )
    # Path-like tokens: word/word.py or path/word.py.
    candidates = re.findall(
        r"\b([\w./-]+\.(?:py|md|sh|json))\b", text
    )
    for cand in candidates:
        full = repo_root / cand
        if full.is_file() and (
            cand.startswith("bin/")
            or cand.startswith(".github/")
        ):
            try:
                content = full.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            return (cand, content[:4000])  # cap at 4000 chars to bound prompt
    return None


def _parse_verdict(stdout: str) -> Optional[dict]:
    """Pull the first JSON object out of an LLM response. Returns
    None on parse failure."""
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("```"):
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and "verdict" in rec:
            return rec
    return None


def run_divergence_prose_to_code_llm(
    config: ProseToCodeLLMConfig,
    runner: LLMRunner,
    *,
    resume: bool = True,
) -> dict:
    """Drive Part A.3 end-to-end. Returns summary dict.

    v1.5.4 Phase 2 Site 3: no-op when ``config.should_run`` is False,
    which the caller derives from ``role_map.has_skill_tools(...)``.
    Resumable via per-REQ cursor.

    Backward-compat asymmetry (Phase 2.1 / Round 4 finding A3): Site 3
    (here) and Site 1 (the four-pass pipeline) treat a missing role
    map as "skip" — the dispatcher passes ``should_run=False`` when
    ``has_skill_tools`` returns False on a None / unparsable map.
    Site 2 (run_playbook Phase 3 code review) preserves v1.5.3
    behaviour on missing role maps. See
    ``docs/design/QPB_v1.5.4_Implementation_Plan.md`` Phase 2.
    """
    if not config.should_run:
        return {
            "skipped_reason": (
                "role map reports no skill-tool files; Part A.3 "
                "prose-to-code LLM divergence has no subjects to check"
            ),
            "divergences_emitted": 0,
            "calls_made": 0,
        }

    reqs = _read_jsonl(config.formal_path)
    skipped_uc_ids = set(config.skipped_uc_ids or ())
    candidates: list[dict] = []
    for req in reqs:
        if req.get("id") in skipped_uc_ids:
            continue
        if not _is_non_countable(req):
            continue
        # Only candidates with a resolvable code artifact get LLM time.
        # Skipping cheaply prevents quota waste.
        if _resolve_code_region(req, config.repo_root) is None:
            continue
        candidates.append(req)

    total = len(candidates)
    cursor = (
        protocol.verify_and_resume(
            config.output_path, config.progress_path,
            idx_field="_a3_idx",
        )
        if resume
        else 0
    )
    state = protocol.ProgressState(
        pass_="A3", unit="req", cursor=cursor, total=total,
        status="running", last_updated=_utc_now_iso(),
    )
    protocol.write_progress_atomic(config.progress_path, state)

    div_idx = config.starting_div_idx + _count_existing_a3_divergences(
        config.output_path
    )
    calls = 0
    emitted = 0

    for idx, req in enumerate(candidates):
        if idx < cursor:
            continue
        if calls > 0 and config.pace_seconds > 0:
            import time as _time
            _time.sleep(config.pace_seconds)
        artifact = _resolve_code_region(req, config.repo_root)
        if artifact is None:  # pragma: no cover - filtered above
            cursor = idx + 1
            continue
        artifact_rel, region = artifact
        recovery = protocol.render_recovery_preamble(
            pass_spec_path=config.pass_spec_path,
            progress_file_path=config.progress_path,
        )
        section_heading = _section_heading(
            config.sections_path,
            req.get("source_document") or "SKILL.md",
            req.get("section_idx"),
        )
        prompt = _PROMPT_TEMPLATE.format(
            recovery_preamble=recovery,
            req_id=req.get("id", ""),
            source_document=req.get("source_document") or "SKILL.md",
            section_heading=section_heading,
            claim=(req.get("citation_excerpt")
                   or req.get("acceptance_criteria", "")),
            code_artifact=artifact_rel,
            code_region=region,
        )
        result = runner.run(prompt)
        calls += 1
        verdict = _parse_verdict(result.stdout)
        if verdict is None:
            verdict = {"verdict": "unclear", "rationale": "LLM output unparsable"}
        if verdict.get("verdict") in ("diverges", "unclear"):
            source_document = req.get("source_document") or "SKILL.md"
            section_idx = req.get("section_idx")
            rec = {
                "divergence_id": f"DIV-P2C-{div_idx:03d}",
                "divergence_type": "prose-to-code",
                "subtype": "llm-judged",
                "req_id": req.get("id"),
                "source_document": source_document,
                "section_idx": section_idx,
                "section_heading": section_heading,
                "excerpt": (req.get("citation_excerpt")
                            or req.get("acceptance_criteria", "")),
                "code_artifact": artifact_rel,
                "llm_verdict": verdict.get("verdict"),
                "llm_rationale": verdict.get("rationale", ""),
                "provisional_disposition": (
                    "code-fix" if verdict.get("verdict") == "diverges" else None
                ),
                "rationale": (
                    f"LLM verdict {verdict.get('verdict')!r} for REQ "
                    f"{req.get('id')} against {artifact_rel}: "
                    f"{verdict.get('rationale', '')}"
                ),
                "triage_batch_key": (
                    f"{source_document}::{section_idx}"
                    if section_idx is not None
                    else f"{source_document}::unknown"
                ),
                "_a3_idx": idx,
            }
            protocol.append_jsonl(config.output_path, rec)
            div_idx += 1
            emitted += 1

        cursor = idx + 1
        state = protocol.ProgressState(
            pass_="A3", unit="req", cursor=cursor, total=total,
            status="running", last_updated=_utc_now_iso(),
        )
        protocol.write_progress_atomic(config.progress_path, state)

    state = protocol.ProgressState(
        pass_="A3", unit="req", cursor=total, total=total,
        status="complete", last_updated=_utc_now_iso(),
    )
    protocol.write_progress_atomic(config.progress_path, state)

    return {
        "divergences_emitted": emitted,
        "calls_made": calls,
        "candidates": total,
    }


def _section_heading(sections_path: Path, document: str, section_idx) -> str:
    if section_idx is None or not sections_path.is_file():
        return ""
    payload = json.loads(sections_path.read_text(encoding="utf-8"))
    for s in payload.get("sections", []):
        if s.get("section_idx") == section_idx and s.get("document") == document:
            return s.get("heading", "") or ""
    return ""


def _count_existing_a3_divergences(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(
        1 for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and "_a3_idx" in line
    )


# v1.5.7 089x: every bin/*.py is safe + self-describing on no-args.
if __name__ == "__main__":
    try:
        from bin._purpose import print_purpose as _print_purpose
    except ImportError:
        from _purpose import print_purpose as _print_purpose  # type: ignore[no-redef]
    _print_purpose(
        name='skill_derivation.divergence_prose_to_code_llm',
        summary=(
            "Prose-to-code divergence detector (LLM lane) — uses an LLM "
            "to flag mismatches between prose specs and the code that "
            "should implement them. "
        ),
        role=(
            "Imported by skill_derivation pass C; produces the LLM-side "
            "half of the prose-to-code divergence pair. "
        ),
        kind="library",
    )
    import sys as _sys
    _sys.exit(0)
