"""sections.py — SKILL.md / reference-file section enumeration for Phase 3.

Pass A iterates over the section tree rather than over the file
verbatim; this module produces the deterministic enumeration that
defines the iteration unit set. Decisions are encoded here once so
all four passes agree on what counts as a "section" and what counts
as a meta section.

Rules implemented (per the Phase 3 brief "Section enumeration spec"):

  1. Fenced-block-aware. Headings inside ``` fenced blocks are
     template fragments, NOT document structure -- skipped.
  2. Top-level iteration unit is `##`. `###` and below are
     sub-sections within their parent `##`. The split rule (>300
     lines per top-level section) splits at the next heading level
     down (`###`).
  3. Duplicate-heading-tolerant. Sections are indexed by an
     auto-assigned monotonic `section_idx`; heading text is
     informational only.
  4. Meta-section allowlist (META_SECTION_ALLOWLIST). Headings on
     the allowlist are emitted with `skip_reason: "meta-allowlist"`
     and Pass A produces no draft REQs for them. Pass D treats them
     as intentional skips for completeness accounting.

Stdlib-only.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator, List, Optional


# Sections whose presence does not imply requirement coverage. Tuned
# against QPB's own SKILL.md; adjust per Phase 3 brief F.2 if the
# orphan-flagged set diverges from human judgment.
META_SECTION_ALLOWLIST = frozenset({
    "Why This Exists",
    "Overview",
    "Acknowledgments",
    "Quick Start",
    "Glossary",
    "Changelog",
    "What This Skill Produces",  # describes outputs but not testable claims
    "Terminology",
    "Principles",
    "Reference Files",  # index of references; the references themselves carry the claims
    # Phase 3c live-run additions: surfaced as flagged completeness
    # gaps that on inspection are descriptive/structural, not
    # testable. "Purpose" sections describe what a reference file is
    # for (rationale, not behavior). "Template" and "Generated file
    # template" sections are fenced template snippets showing the
    # shape of an output artifact, not rules an implementation
    # follows.
    "Purpose",
    "Template",
    "Generated file template",
})

# All-caps screaming-section pattern (template-output markers like
# `## RUN_METADATA` should be skipped if they ever escape a fenced
# block). Conservative: only fires on plain UPPER_SNAKE.
_ALL_CAPS_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Phase 3b A.1: keywords that mark a section as describing an
# execution mode (Pass A produces UC drafts in addition to REQ
# drafts for these sections). Verified against QPB's actual SKILL.md
# `##` headings; tune by adding/removing entries before the live
# Pass A run and verifying that 8-12 sections fire (target = Haiku's
# 10 use cases ± 20%).
EXECUTION_MODE_KEYWORDS = frozenset({
    "how to use",
    "phase 0",
    "phase 1", "phase 2", "phase 3", "phase 4",
    "phase 5", "phase 6", "phase 7",
    "recheck",
    "bootstrap",
    "iteration",
    "convergence",
    "interactive",
    "non-interactive",
    # Phase 3d additions per Round 6 Council Finding 4: surface
    # UC-09 (Benchmark Operator) and UC-10 (Bootstrap Self-Audit)
    # which the original keyword set missed.
    # - "self-check" matches SKILL.md "Gate Self-Check" (the
    #   bootstrap-style self-audit execution mode) AND
    #   references/verification.md "Self-Check Benchmarks" (the
    #   benchmark execution mode).
    # - "benchmark" matches "Self-Check Benchmarks" directly and
    #   any future SKILL.md/reference heading using the term.
    "self-check",
    "benchmark",
})

# Top-level section split threshold (lines). A `##` section longer
# than this is split at the next `###` heading down so each
# subsection becomes its own iteration unit -- keeps per-call prompt
# size bounded.
SECTION_SPLIT_LINE_THRESHOLD = 300


@dataclass
class Section:
    section_idx: int
    document: str  # repo-relative path
    heading: str   # raw heading text without the leading hashes
    heading_level: int  # 2 for ##, 3 for ###, etc.
    line_start: int  # 1-based line number of the heading line
    line_end: int    # 1-based, INCLUSIVE; the last line that belongs to this section
    skip_reason: Optional[str]  # "meta-allowlist" / "screaming" / None when not skipped
    # Phase 3b A.1/A.2: section_kind drives Pass A's prompt selection.
    # "operational" = REQ-only; "execution-mode" = REQ + UC; "meta" =
    # skipped (no LLM call). Computed at enumeration time so all
    # downstream passes agree on the kind.
    section_kind: str = "operational"


# Phase 3b A.3: regex for detecting cross-references to reference
# files inside section body text. Matches both "references/foo.md"
# (path-form) and "foo.md" (bare filename when paired with a hint
# like "see foo.md"). The regex captures the filename component;
# resolution to a repo-relative path is the caller's job.
_CROSS_REF_PATTERN_PATHED = re.compile(r"references/([a-zA-Z0-9_\-]+\.md)")
_CROSS_REF_PATTERN_BARE = re.compile(
    r"\b(?:see|cf\.?|per|in|from)\s+`?([a-zA-Z0-9_\-]+\.md)`?",
    re.IGNORECASE,
)


def detect_cross_references(
    section_text: str, *, references_basenames: frozenset[str]
) -> list[str]:
    """Return repo-relative paths to reference files cited in the
    section text.

    references_basenames is the set of valid reference-file basenames
    (e.g., {"exploration_patterns.md", "verification.md"}); only
    matches in this set are returned. This avoids false positives on
    casual mentions of unrelated .md files.

    Returns deduplicated list of "references/<filename>" strings,
    sorted for determinism.
    """
    found: set[str] = set()
    for match in _CROSS_REF_PATTERN_PATHED.findall(section_text):
        if match in references_basenames:
            found.add(f"references/{match}")
    for match in _CROSS_REF_PATTERN_BARE.findall(section_text):
        if match in references_basenames:
            found.add(f"references/{match}")
    return sorted(found)


def collect_reference_basenames(references_dir: Optional[Path]) -> frozenset[str]:
    """Return the set of .md basenames in references_dir, or empty
    frozenset if the directory is absent. Used by detect_cross_references
    to avoid false positives on unrelated .md mentions."""
    if references_dir is None or not references_dir.is_dir():
        return frozenset()
    return frozenset(p.name for p in references_dir.glob("*.md"))


def is_meta_heading(heading: str) -> Optional[str]:
    """Return a skip_reason string if the heading is meta, else None."""
    stripped = heading.strip()
    if stripped in META_SECTION_ALLOWLIST:
        return "meta-allowlist"
    if _ALL_CAPS_RE.match(stripped):
        return "screaming"
    return None


def is_execution_mode_heading(heading: str) -> bool:
    """Return True iff the heading matches an EXECUTION_MODE_KEYWORDS entry.

    Case-insensitive substring match per the brief A.1 matching rules:
    `.lower()` both sides, match the keyword anywhere in the heading
    text. Heading-only -- callers must NOT pass section body text.
    """
    lowered = heading.lower()
    for keyword in EXECUTION_MODE_KEYWORDS:
        if keyword in lowered:
            return True
    return False


def classify_section_kind(heading: str, skip_reason: Optional[str]) -> str:
    """Three-way classification: meta / execution-mode / operational.

    Order matters: meta wins over execution-mode. A section in the
    META_SECTION_ALLOWLIST is never an execution-mode section even if
    its heading happens to contain an execution-mode keyword.
    """
    if skip_reason is not None:
        return "meta"
    if is_execution_mode_heading(heading):
        return "execution-mode"
    return "operational"


def _iter_top_level_headings(text: str) -> Iterator[tuple]:
    """Yield (line_idx_0based, heading_level, heading_text) for top-level
    `##` and `###` headings, skipping anything inside a fenced code block.

    line_idx is 0-based for internal slicing convenience; callers
    convert to 1-based when populating the Section dataclass.
    """
    in_fence = False
    fence_marker: Optional[str] = None
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        # Fence open/close detection. Both ``` and ~~~ are markdown
        # fences; we only see ``` in QPB's corpus, but supporting both
        # is correct.
        if stripped.startswith("```") or stripped.startswith("~~~"):
            marker = "```" if stripped.startswith("```") else "~~~"
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif fence_marker == marker:
                in_fence = False
                fence_marker = None
            continue
        if in_fence:
            continue
        if line.startswith("## ") and not line.startswith("### "):
            yield (idx, 2, line[3:].rstrip())
        elif line.startswith("### "):
            yield (idx, 3, line[4:].rstrip())


def enumerate_sections(
    document_path: Path,
    repo_root: Optional[Path] = None,
    *,
    starting_idx: int = 0,
) -> List[Section]:
    """Parse `document_path` and return its Section list.

    Top-level iteration unit is `##`. `##` sections that exceed
    SECTION_SPLIT_LINE_THRESHOLD lines are split at their first child
    `###` heading, producing one Section per `###` subsection (the
    parent `##` becomes a "header-only" section spanning the lines
    from the `##` to the first `###`).

    `starting_idx` lets callers chain enumeration across multiple
    documents while keeping `section_idx` globally monotonic.
    """
    if repo_root is None:
        repo_root = document_path.parent
    rel_doc = str(document_path.resolve().relative_to(repo_root.resolve())) \
        if document_path.resolve().is_relative_to(repo_root.resolve()) \
        else str(document_path)

    text = document_path.read_text(encoding="utf-8")
    total_lines = len(text.splitlines())

    headings = list(_iter_top_level_headings(text))
    if not headings:
        return []

    sections: List[Section] = []
    next_idx = starting_idx

    # Pre-compute the END line (0-based exclusive) for each heading by
    # looking at the next-or-equal-level heading boundary.
    for hi, (line_idx_0, level, heading) in enumerate(headings):
        # The "next-heading-of-any-level" boundary -- used when this
        # section is small enough that subsections aren't emitted
        # separately, so its line span runs to the next heading.
        if hi + 1 < len(headings):
            next_line_idx_0 = headings[hi + 1][0]
        else:
            next_line_idx_0 = total_lines
        # The "next-heading-of-same-or-higher-level" boundary -- used
        # for the split-rule line-count check, so a level-2 section's
        # length includes all of its level-3+ child content.
        next_same_or_higher_idx_0 = total_lines
        for h_idx_0, h_level, _ in headings:
            if h_idx_0 > line_idx_0 and h_level <= level:
                next_same_or_higher_idx_0 = h_idx_0
                break
        section_lines = next_same_or_higher_idx_0 - line_idx_0
        line_start_1 = line_idx_0 + 1
        line_end_1 = next_line_idx_0  # next heading regardless of level
        if level == 2:
            # Top-level section. Decide split.
            should_split = section_lines > SECTION_SPLIT_LINE_THRESHOLD and any(
                inner_level == 3
                and line_idx_0 < inner_idx_0 < next_same_or_higher_idx_0
                for inner_idx_0, inner_level, _ in headings
            )
            if not should_split:
                skip_reason = is_meta_heading(heading)
                sections.append(
                    Section(
                        section_idx=next_idx,
                        document=rel_doc,
                        heading=heading,
                        heading_level=2,
                        line_start=line_start_1,
                        line_end=line_end_1,
                        skip_reason=skip_reason,
                        section_kind=classify_section_kind(heading, skip_reason),
                    )
                )
                next_idx += 1
            # When splitting, the `##` itself is not emitted as its
            # own section -- the contained `###` subsections are. The
            # `###` headings are picked up by the level-3 branch
            # below as we iterate.
        elif level == 3:
            # Only emit a level-3 section if its parent level-2
            # exceeded the split threshold. Find the parent.
            parent_line_idx_0 = -1
            parent_section_lines = 0
            for parent_idx_0, parent_level, _ in headings:
                if parent_level == 2 and parent_idx_0 < line_idx_0:
                    parent_line_idx_0 = parent_idx_0
            if parent_line_idx_0 < 0:
                continue
            # Compute parent's line span (next heading at same-or-higher level).
            parent_end_idx_0 = total_lines
            for h_idx_0, h_level, _ in headings:
                if h_idx_0 > parent_line_idx_0 and h_level <= 2:
                    parent_end_idx_0 = h_idx_0
                    break
            parent_section_lines = parent_end_idx_0 - parent_line_idx_0
            if parent_section_lines <= SECTION_SPLIT_LINE_THRESHOLD:
                continue  # parent fits in one unit; subsection isn't enumerated
            skip_reason = is_meta_heading(heading)
            sections.append(
                Section(
                    section_idx=next_idx,
                    document=rel_doc,
                    heading=heading,
                    heading_level=3,
                    line_start=line_start_1,
                    line_end=line_end_1,
                    skip_reason=skip_reason,
                    section_kind=classify_section_kind(heading, skip_reason),
                )
            )
            next_idx += 1
    return sections


def enumerate_skill_and_references(
    skill_md_path: Path,
    references_dir: Optional[Path],
    repo_root: Path,
    *,
    role_map_files: Optional[List[Path]] = None,
) -> List[Section]:
    """Phase 3b A.2: enumerate SKILL.md AND every references/*.md file.

    Iteration units are chained with monotonic `section_idx` across
    all documents. Pass A reads the chained list and runs the LLM
    once per non-skipped section.

    v1.5.4 Phase 2.1 (Round 4 Council finding C1): when ``role_map_files``
    is provided, enumeration walks exactly that list (the absolute paths
    of every file the Phase-1 role map tagged ``skill-prose`` or
    ``skill-reference``). Order is the role-map order, with SKILL.md
    pulled to the front when present so Pass A's contract — SKILL.md
    sections enumerated first — is preserved. This is what lets a
    target like pdf-1.5.3 (whose skill-prose surface is SKILL.md +
    FORMS.md + REFERENCE.md, not the conventional `references/*.md`
    layout) be enumerated correctly.

    ``role_map_files`` routing (v1.5.4 Phase 3 Stage 3, finding B1-F6):

      - **``None``** — backward-compat path. The role map is absent or
        unparsable. Enumeration falls back to the v1.5.3 behaviour:
        SKILL.md plus ``references_dir/*.md`` in sorted-by-name order.
        Pre-Phase-1 / pre-iteration targets land here.
      - **``[]``** (empty list) — role-map path with zero matches. The
        role map exists, was parsed cleanly, and reported zero files
        tagged ``skill-prose`` or ``skill-reference``. Enumeration
        returns an empty section list; the v1.5.3 fallback does NOT
        fire. The activation predicate ``has_skill_prose`` normally
        gates this case before Pass A is invoked, but the asymmetry
        is intentional so direct callers that bypass the predicate
        get a deterministic empty result rather than a fallback walk.
      - **non-empty list** — role-map walk over the supplied files,
        SKILL.md first, in role-map order otherwise.

    Reference files are markdown by convention; non-markdown files
    are skipped. Pass C uses the `document` field on each draft to
    set source_type correctly (skill-section for SKILL.md;
    reference-file for everything else).
    """
    if role_map_files is not None:
        return _enumerate_role_map_files(
            role_map_files, skill_md_path, repo_root
        )
    out: List[Section] = []
    if skill_md_path.is_file():
        out.extend(
            enumerate_sections(skill_md_path, repo_root=repo_root, starting_idx=0)
        )
    if references_dir is not None and references_dir.is_dir():
        next_idx = len(out)
        for ref in sorted(references_dir.glob("*.md")):
            ref_secs = enumerate_sections(
                ref, repo_root=repo_root, starting_idx=next_idx
            )
            out.extend(ref_secs)
            next_idx += len(ref_secs)
    return out


def _enumerate_role_map_files(
    role_map_files: List[Path],
    skill_md_path: Path,
    repo_root: Path,
) -> List[Section]:
    """Walk a role-map-supplied file list. SKILL.md is enumerated first
    (its sections must occupy section_idx 0..N so Pass C's source_type
    routing keeps working); the rest follow in role-map order. Files
    that don't exist on disk or aren't markdown are skipped silently —
    the role map is the spec, but enumeration still requires bytes.

    v1.5.4 Phase 3 Stage 3 (Round 5 finding B1-F6): when
    ``role_map_files`` is the empty list, this function returns an
    empty section list — SKILL.md is NOT auto-enumerated. The empty
    list means "the role map exists and reports zero skill-prose /
    skill-reference files," and per the v1.5.4 architecture the role
    map IS the spec. SKILL.md present on disk but not tagged
    skill-prose is by definition not a skill input. The activation
    predicate ``has_skill_prose`` normally guards this case before
    Pass A reaches here, but the deterministic empty result protects
    direct callers."""
    if not role_map_files:
        return []

    out: List[Section] = []
    seen: set = set()
    skill_resolved = skill_md_path.resolve() if skill_md_path.is_file() else None

    def _enum(path: Path, starting_idx: int) -> int:
        nonlocal out
        secs = enumerate_sections(
            path, repo_root=repo_root, starting_idx=starting_idx
        )
        out.extend(secs)
        return starting_idx + len(secs)

    next_idx = 0
    if skill_resolved is not None and skill_resolved in {
        p.resolve() for p in role_map_files if p.is_file()
    }:
        next_idx = _enum(skill_md_path, next_idx)
        seen.add(skill_resolved)

    for entry in role_map_files:
        try:
            resolved = entry.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        if not resolved.is_file():
            continue
        if resolved.suffix.lower() != ".md":
            continue
        next_idx = _enum(resolved, next_idx)
        seen.add(resolved)

    return out


def write_sections_json(sections: List[Section], out_path: Path) -> None:
    """Emit pass_a_sections.json (the deterministic enumeration artifact).

    schema_version bumped 1.0 -> 1.1 in Phase 3b: the Section
    dataclass gained a `section_kind` field. Purely additive (existing
    consumers reading the prior 1.0 keys still work; new consumers
    reading section_kind get the classification).
    """
    payload = {
        "schema_version": "1.1",
        "sections": [asdict(s) for s in sections],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    import os
    os.replace(tmp, out_path)
