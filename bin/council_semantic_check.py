"""council_semantic_check.py — Phase 6 Layer-2 hallucination mitigation.

Assembles the Council-of-Three semantic review output into
`quality/citation_semantic_check.json` per schemas.md §9.

Layer 1 (Phase 5d) re-runs the deterministic excerpt extraction at gate
time to catch fabricated excerpts — a purely mechanical check.

Layer 2 (Phase 6) asks three independent AI reviewers whether each Tier
1/2 REQ's `citation_excerpt` actually supports the requirement as
stated, or whether the requirement overreaches what the excerpt says.
Three values per REQ:

    supports     — excerpt clearly supports the requirement.
    overreaches  — citation exists but requirement claims more than
                   the excerpt says.
    unclear      — reviewer cannot tell.

Gate rule (schemas.md §10 invariant #17): ≥2 of 3 `overreaches` for the
same REQ fails the gate; isolated `overreaches` / `unclear` surface as
warnings. See `.github/skills/quality_gate/quality_gate.py` for the
mechanical check implementation.

This module is deliberately structured as pure functions with the
module-level boundary at "assemble the reviews array" — actually
invoking the LLMs lives in the orchestrator (Phase 4 Council machinery).
That separation keeps the module testable without an LLM round-trip.

Public surface:

    collect_tier_12_reqs(quality_dir) -> list[ReqRecord]
        Extract the Tier 1/2 REQs that need semantic review.

    build_prompts_for_member(member_id, reqs, *, batch_size=5, threshold=15)
        Return the list of prompt strings the member should see. One
        prompt for ≤15 REQs; batches of up to `batch_size` for >15.

    parse_member_response(member_id, response_text, expected_req_ids)
        Validate and coerce a JSON response into review entries.

    assemble_reviews(responses_by_member) -> list[ReviewEntry]
        Flatten per-member review lists into one reviews[] array.

    write_semantic_check(repo_dir, reviews, *, schema_version=..., now=None)
        Emit quality/citation_semantic_check.json per §9 wrapper shape.

CLI (for operator re-assembly from captured per-member JSON files):

    python -m bin.council_semantic_check <repo_dir> \
        --member claude-opus-4.7   --response path/to/opus.json \
        --member gpt-5.5           --response path/to/gpt.json \
        --member claude-sonnet-4.6 --response path/to/sonnet.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from . import archive_lib
    from . import benchmark_lib as lib
    from .council_config import council_members, DEFAULT_COUNCIL_MEMBERS
except ImportError:  # running as a script from the repo root
    import archive_lib
    import benchmark_lib as lib
    from council_config import council_members, DEFAULT_COUNCIL_MEMBERS


VALID_VERDICTS = ("supports", "overreaches", "unclear")


class SemanticCheckError(Exception):
    """Raised on unrecoverable assembly failures."""


@dataclass(frozen=True)
class ReqRecord:
    """Minimal subset of a REQ needed for semantic review."""

    req_id: str
    tier: int
    description: str
    citation_excerpt: str
    citation_document: str
    citation_locator: str  # rendered "section=X line=Y" string


@dataclass(frozen=True)
class ReviewEntry:
    """One row of the citation_semantic_check.json reviews[] array."""

    req_id: str
    reviewer: str
    verdict: str
    notes: str


# ---------------------------------------------------------------------------
# REQ extraction
# ---------------------------------------------------------------------------


def collect_tier_12_reqs(quality_dir: Path) -> List[ReqRecord]:
    """Load Tier 1/2 REQs from quality/requirements_manifest.json.

    REQs without a well-formed citation are skipped silently — Layer-1
    (Phase 5d) already flags them. This function's job is to assemble
    the Layer-2 review set, not to re-validate citation shape.
    """
    path = quality_dir / "requirements_manifest.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    records = data.get("records")
    if not isinstance(records, list):
        return []
    result: List[ReqRecord] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        tier = rec.get("tier")
        if tier not in (1, 2):
            continue
        req_id = rec.get("id")
        if not isinstance(req_id, str) or not req_id:
            continue
        citation = rec.get("citation")
        if not isinstance(citation, dict):
            continue
        excerpt = citation.get("citation_excerpt")
        if not isinstance(excerpt, str) or not excerpt:
            continue
        document = citation.get("document")
        if not isinstance(document, str):
            document = ""
        section = citation.get("section")
        line = citation.get("line")
        locator_bits: List[str] = []
        if isinstance(section, str) and section:
            locator_bits.append(f"section={section}")
        if isinstance(line, int) and not isinstance(line, bool):
            locator_bits.append(f"line={line}")
        description = rec.get("description") or rec.get("title") or ""
        if not isinstance(description, str):
            description = str(description)
        result.append(
            ReqRecord(
                req_id=req_id,
                tier=int(tier),
                description=description,
                citation_excerpt=excerpt,
                citation_document=document,
                citation_locator=" ".join(locator_bits) or "(no locator)",
            )
        )
    return result


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


_PROMPT_HEADER = (
    "You are {member} reviewing citation support for {count} Tier 1/2 "
    "requirements extracted from a target repo. For each requirement below, "
    "read the citation_excerpt and decide whether the excerpt supports the "
    "requirement as stated or whether the requirement overreaches what the "
    "excerpt says.\n"
    "\n"
    "Respond with a single JSON array. One object per requirement, in the "
    "same order as given. Each object MUST have exactly these keys:\n"
    '  "req_id": string matching the input\n'
    '  "verdict": "supports" | "overreaches" | "unclear"\n'
    '  "reasoning": brief explanation (may be empty string)\n'
    "\n"
    "Do not include any prose outside the JSON array. Do not add extra keys."
    "\n\n"
    "--- Requirements ---\n"
)


def _render_req_block(req: ReqRecord) -> str:
    return (
        f"req_id: {req.req_id}\n"
        f"tier: {req.tier}\n"
        f"description: {req.description.strip()}\n"
        f"citation_document: {req.citation_document}\n"
        f"citation_locator: {req.citation_locator}\n"
        f"citation_excerpt: |\n  "
        + req.citation_excerpt.replace("\n", "\n  ")
        + "\n"
    )


def build_prompts_for_member(
    member_id: str,
    reqs: Sequence[ReqRecord],
    *,
    batch_size: int = 5,
    threshold: int = 15,
) -> List[str]:
    """Return one or more prompt strings for a Council member.

    - If `len(reqs) <= threshold`: one prompt containing every REQ.
    - Else: batches of up to `batch_size` REQs, in `req_id`-stable order
      so multiple reviewers see the same partition across their batch
      sequences.

    Empty reqs returns an empty list (no prompts to send — Spec Gap
    run; semantic check file will have `reviews: []`).
    """
    reqs_list = list(reqs)
    if not reqs_list:
        return []
    if len(reqs_list) <= threshold:
        return [_render_single_prompt(member_id, reqs_list)]
    # Stable partitioning: sort by req_id so each reviewer sees the same
    # batch boundaries.
    ordered = sorted(reqs_list, key=lambda r: r.req_id)
    prompts: List[str] = []
    for start in range(0, len(ordered), batch_size):
        batch = ordered[start : start + batch_size]
        prompts.append(_render_single_prompt(member_id, batch))
    return prompts


def _render_single_prompt(member_id: str, reqs: Sequence[ReqRecord]) -> str:
    header = _PROMPT_HEADER.format(member=member_id, count=len(reqs))
    body = "\n".join(_render_req_block(r) for r in reqs)
    return header + body


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def parse_member_response(
    member_id: str,
    response_text: str,
    expected_req_ids: Iterable[str],
) -> List[ReviewEntry]:
    """Parse a Council member's JSON-array response into review entries.

    Validation:
      - Response is (or contains) a JSON array.
      - Each element is a dict with `req_id`, `verdict`, `reasoning`.
      - `verdict` is in the `VALID_VERDICTS` enum.
      - Every `expected_req_ids` member appears in the response.

    Missing / invalid entries raise SemanticCheckError with a specific
    message naming the offending REQ id.
    """
    payload = _extract_first_json_array(response_text)
    if payload is None:
        raise SemanticCheckError(
            f"{member_id}: response does not contain a JSON array"
        )
    if not isinstance(payload, list):
        raise SemanticCheckError(
            f"{member_id}: top-level JSON is {type(payload).__name__}, expected array"
        )
    seen: Dict[str, ReviewEntry] = {}
    expected = list(expected_req_ids)
    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            raise SemanticCheckError(
                f"{member_id}: response[#{idx}] is {type(item).__name__}, expected object"
            )
        req_id = item.get("req_id")
        if not isinstance(req_id, str) or not req_id:
            raise SemanticCheckError(
                f"{member_id}: response[#{idx}] missing or non-string req_id"
            )
        verdict = item.get("verdict")
        if verdict not in VALID_VERDICTS:
            raise SemanticCheckError(
                f"{member_id}: response[#{idx}] (req_id={req_id}) invalid "
                f"verdict {verdict!r}; expected one of {VALID_VERDICTS}"
            )
        reasoning = item.get("reasoning", "")
        if reasoning is None:
            reasoning = ""
        if not isinstance(reasoning, str):
            raise SemanticCheckError(
                f"{member_id}: response[#{idx}] (req_id={req_id}) reasoning is "
                f"{type(reasoning).__name__}, expected string"
            )
        if req_id in seen:
            raise SemanticCheckError(
                f"{member_id}: duplicate review for req_id={req_id!r}"
            )
        seen[req_id] = ReviewEntry(
            req_id=req_id, reviewer=member_id, verdict=verdict, notes=reasoning
        )
    missing = [rid for rid in expected if rid not in seen]
    if missing:
        raise SemanticCheckError(
            f"{member_id}: response missing review(s) for {missing}"
        )
    # Preserve the expected order so downstream assembly is stable.
    return [seen[rid] for rid in expected]


_JSON_ARRAY_PATTERN = re.compile(r"\[[\s\S]*\]")


def _extract_first_json_array(text: str):
    """Return the first JSON array in `text`, or None.

    Models sometimes wrap responses in markdown code fences or brief
    prose. Tolerate that by scanning for the first `[...]` balanced
    block.
    """
    # Fast path: whole payload is a JSON array.
    stripped = text.strip()
    if stripped.startswith("["):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    # Fallback (BUG-006 fix): find the FIRST balanced `[...]` substring that
    # parses as JSON. The previous greedy regex `\[[\s\S]*\]` matched from
    # the first `[` to the LAST `]`, so a valid array followed by trailing
    # prose containing any `]` (e.g. "see item [2]") failed to parse and the
    # whole reviewer response was dropped — contradicting this function's
    # "first balanced block / outermost that parses" docstring.
    start = text.find("[")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("[", start + 1)
    return None


# ---------------------------------------------------------------------------
# Assembly + emission
# ---------------------------------------------------------------------------


def assemble_reviews(
    responses_by_member: Dict[str, List[ReviewEntry]],
) -> List[ReviewEntry]:
    """Flatten {member_id: [ReviewEntry, ...], ...} into one reviews[] array.

    Order: iterate members in insertion order (typically the council
    roster order), emitting each member's entries in the order parsed
    (stable by req_id per `parse_member_response`). This produces
    deterministic output suitable for diffing across runs.
    """
    flat: List[ReviewEntry] = []
    for member_id, entries in responses_by_member.items():
        for entry in entries:
            if entry.reviewer != member_id:
                raise SemanticCheckError(
                    f"assemble_reviews: entry reviewer={entry.reviewer!r} does "
                    f"not match outer member_id={member_id!r}"
                )
            flat.append(entry)
    return flat


def _schema_version(qpb_root: Optional[Path] = None) -> str:
    version = lib.detect_skill_version(qpb_root)
    return version or "unknown"


def write_semantic_check(
    repo_dir: Path,
    reviews: List[ReviewEntry],
    *,
    schema_version: Optional[str] = None,
    now: Optional[datetime] = None,
    qpb_root: Optional[Path] = None,
) -> Path:
    """Emit quality/citation_semantic_check.json per schemas.md §9 wrapper.

    Returns the written path. Overwrites an existing file (one emission
    per run).
    """
    quality_dir = Path(repo_dir) / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": schema_version or _schema_version(qpb_root),
        "generated_at": archive_lib.utc_extended_timestamp(now),
        "reviews": [
            {
                "req_id": e.req_id,
                "reviewer": e.reviewer,
                "verdict": e.verdict,
                "notes": e.notes,
            }
            for e in reviews
        ],
    }
    path = quality_dir / "citation_semantic_check.json"
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Plan mode — emit per-member prompt files for operator dispatch
# ---------------------------------------------------------------------------


PROMPTS_SUBDIR = "council_semantic_check_prompts"
RESPONSES_SUBDIR = "council_semantic_check_responses"


def plan_prompts(
    repo_dir: Path,
    *,
    members: Optional[Sequence[str]] = None,
) -> Tuple[List[Path], Path]:
    """Emit per-member prompt files for the semantic check.

    Writes one file per Council member under
    `quality/council_semantic_check_prompts/<member>.txt` when the run
    has Tier 1/2 REQs. If a member's prompt set has been batched (>15
    REQs), per-batch files are written as
    `<member>-batch<N>.txt`.

    When no Tier 1/2 REQs are present (Spec Gap), no prompt files are
    written and an empty `quality/citation_semantic_check.json` is
    emitted directly — the operator has nothing to send to the Council.

    Returns (prompt_paths, semantic_check_path). The second value is
    the path to citation_semantic_check.json when Spec Gap wrote it
    directly; otherwise None-equivalent as an empty Path.
    """
    repo = Path(repo_dir).resolve()
    quality_dir = repo / "quality"
    roster = list(members) if members is not None else list(council_members())

    reqs = collect_tier_12_reqs(quality_dir)
    prompts_dir = quality_dir / PROMPTS_SUBDIR

    if not reqs:
        # Spec Gap: no prompts to send; write the empty §9 wrapper directly.
        # If a prior non-Spec-Gap run left prompt files behind, clear them so
        # the operator isn't tempted to dispatch stale prompts.
        _clear_prompt_files(prompts_dir)
        path = write_semantic_check(repo, [])
        return ([], path)

    # Clear any `.txt` left from a prior plan call before writing fresh
    # prompts. A rerun that transitions from a 20-REQ batch layout (12
    # files) to a 1-REQ unbatched layout (3 files) would otherwise leave
    # nine stale `-batchN.txt` files that the operator might dispatch by
    # mistake. Non-`.txt` files in the folder (e.g. operator-placed
    # notes.md) are preserved.
    _clear_prompt_files(prompts_dir)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for member in roster:
        prompts = build_prompts_for_member(member, reqs)
        if len(prompts) == 1:
            filename = f"{member}.txt"
            target = prompts_dir / filename
            target.write_text(prompts[0], encoding="utf-8")
            written.append(target)
        else:
            for idx, prompt_text in enumerate(prompts, start=1):
                target = prompts_dir / f"{member}-batch{idx}.txt"
                target.write_text(prompt_text, encoding="utf-8")
                written.append(target)
    return (written, Path())


def _clear_prompt_files(prompts_dir: Path) -> None:
    """Remove stale `.txt` prompts from a prior plan call (Phase 7 r7)."""
    if not prompts_dir.exists():
        return
    for existing in prompts_dir.iterdir():
        if existing.is_file() and existing.suffix == ".txt":
            existing.unlink()


# ---------------------------------------------------------------------------
# CLI — plan | assemble modes (legacy --member/--response form still works)
# ---------------------------------------------------------------------------


def _parse_member_response_file(
    member_id: str, response_path: Path, expected_req_ids: Sequence[str]
) -> List[ReviewEntry]:
    try:
        text = response_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SemanticCheckError(
            f"{member_id}: could not read {response_path}: {exc}"
        )
    return parse_member_response(member_id, text, expected_req_ids)


def _plan_main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="semantic-check plan",
        description=(
            "Generate per-Council-member prompt files for the Layer-2 semantic "
            "citation check. Operator dispatches each prompt to its Council "
            "member and captures the JSON response to "
            "quality/council_semantic_check_responses/<member>.json, then runs "
            "`semantic-check assemble` (or the legacy --member/--response CLI)."
        ),
    )
    parser.add_argument("repo", help="Target repository root.")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"{repo}: target repository does not exist", file=sys.stderr)
        return 2
    try:
        prompts, spec_gap_file = plan_prompts(repo)
    except SemanticCheckError as exc:
        print(f"semantic_check plan: {exc}", file=sys.stderr)
        return 1

    if not prompts:
        # Spec Gap path: plan_prompts already wrote the empty reviews[].
        print(
            f"No Tier 1/2 REQs — wrote empty {spec_gap_file} (Spec Gap run). "
            "Skip dispatch."
        )
        return 0

    print(f"Wrote {len(prompts)} prompt file(s) to "
          f"{(repo / 'quality' / PROMPTS_SUBDIR).relative_to(repo)}:")
    for p in prompts:
        print(f"  {p.relative_to(repo)}")
    print(
        "Next: feed each prompt to its Council member, capture the JSON-array "
        "response to quality/council_semantic_check_responses/<member>.json, "
        "and run `quality_playbook semantic-check assemble <repo> --member ... "
        "--response ...`."
    )
    return 0


def _assemble_main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="semantic-check assemble",
        description=(
            "Assemble citation_semantic_check.json from captured Council "
            "member JSON responses. Each --member/--response pair must be "
            "adjacent; order matches the Council roster."
        ),
    )
    parser.add_argument("repo", help="Target repository root.")
    parser.add_argument(
        "--member",
        action="append",
        default=[],
        help="Council member identifier (repeatable; one per --response).",
    )
    parser.add_argument(
        "--response",
        action="append",
        default=[],
        help="Path to the member's JSON response file (repeatable).",
    )
    args = parser.parse_args(argv)

    if len(args.member) != len(args.response):
        print(
            "--member and --response must appear in equal count",
            file=sys.stderr,
        )
        return 2
    if not args.member:
        print("no Council members supplied; nothing to assemble", file=sys.stderr)
        return 2

    # Phase 7 r8: typo-and-drift protection. The gate's invariant #17 groups
    # reviews by `reviewer` — an unrecognized identifier (`claude-opus-4.6`,
    # trailing whitespace, etc.) silently becomes a phantom fourth reviewer
    # and breaks the 2-of-3 vote. Validate against the canonical roster at
    # CLI entry so the operator sees the typo before it reaches the gate.
    roster = set(council_members())
    unknown = [m for m in args.member if m not in roster]
    if unknown:
        expected = ", ".join(sorted(roster))
        print(
            f"unknown Council member identifier(s): {unknown}; "
            f"expected one of: {expected}",
            file=sys.stderr,
        )
        return 2
    if len(set(args.member)) != len(args.member):
        dupes = sorted({m for m in args.member if args.member.count(m) > 1})
        print(
            f"duplicate Council member identifier(s): {dupes}; "
            "each member must appear exactly once",
            file=sys.stderr,
        )
        return 2

    repo = Path(args.repo).resolve()
    quality_dir = repo / "quality"
    reqs = collect_tier_12_reqs(quality_dir)
    expected_ids = [r.req_id for r in reqs]

    responses_by_member: Dict[str, List[ReviewEntry]] = {}
    try:
        for member_id, response_path in zip(args.member, args.response):
            entries = _parse_member_response_file(
                member_id, Path(response_path), expected_ids
            )
            responses_by_member[member_id] = entries
    except SemanticCheckError as exc:
        print(f"semantic_check: {exc}", file=sys.stderr)
        return 1

    reviews = assemble_reviews(responses_by_member)
    path = write_semantic_check(repo, reviews)
    print(f"Wrote {path} with {len(reviews)} review entries")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
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
            name='council_semantic_check',
            summary=(
            "Council-style semantic cross-check runner — assembles N "
            "reviewer responses for a single REQ/UC and compares "
            "them. "
            ),
            role=(
            "Called by Phase 4 semantic-check (via "
            "quality_playbook.py) to fan out one Council-of-Three "
            "pass per cross-check item. "
            ),
            usage_hint='python3 -m bin.council_semantic_check --help',
        )
        return 0

    if argv is None:
        argv = sys.argv[1:]
    # v1.5.7 090a: full attribution banner at top of --help.
    _print_help_banner(argv)
    if argv and argv[0] == "plan":
        return _plan_main(argv[1:])
    if argv and argv[0] == "assemble":
        return _assemble_main(argv[1:])
    # Legacy form: fall through to assemble when --member flags are present.
    return _assemble_main(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
