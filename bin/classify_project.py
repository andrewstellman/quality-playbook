"""classify_project.py — DEBUG UTILITY ONLY (v1.5.4 status).

**v1.5.4 Part 1 status: this module is no longer part of the playbook
run path.** QPB v1.5.4 replaced the mechanical Code/Skill/Hybrid
classifier with AI-driven file-by-file role tagging during Phase 1
exploration; the run path now reads `quality/exploration_role_map.json`
(produced by the Phase 1 LLM agent) and consumers (pass_c, quality_gate)
derive any legacy "project type" label they need from the role map's
breakdown via `bin.role_map.derive_legacy_project_type`. See
`docs/design/QPB_v1.5.4_Design.md` Part 1 for the rationale (the v1.5.3
LOC-based heuristic was both never wired into run_playbook AND silently
polluted by QPB infrastructure shipped into benchmark targets).

The module is retained as a debug utility:
  - `python3 -m bin.classify_project --target <repo>` prints what the
    v1.5.3 mechanical heuristic WOULD say about a target. Useful when
    triaging whether a target's surface looks code-shaped vs
    skill-shaped before manually inspecting the role map.
  - The `--override` / `--override-rationale` flags can still be used
    for ad-hoc manual classification during Council review.

Nothing in the v1.5.4 run path reads `quality/project_type.json` any
longer; calling `--write` only produces a debugging artifact that other
tooling ignores.

Original v1.5.3 docstring preserved below for historical context.

QPB v1.5.3 introduced a Phase 0 step that classifies a target repository
as Code, Skill, or Hybrid before the playbook's exploration phase begins.
Code projects kept the v1.5.0 divergence pipeline; Skill and Hybrid
projects got the skill-specific four-pass derivation pipeline added in
later v1.5.3 phases (Phases 2-7). The classifier emitted
`<target>/quality/project_type.json`; pass_c and quality_gate read it.
Both consumers were rewired to the role map in v1.5.4.

Heuristic (per QPB_v1.5.3_Design.md "Classification Mechanism"):

  - SKILL.md exists at repo root AND prose word count in SKILL.md
    substantially exceeds code line count across the repo => Skill
  - SKILL.md exists at repo root AND substantial code exists alongside it
    => Hybrid
  - No SKILL.md at repo root => Code

The "substantially exceeds" threshold lands at the 2x ratio called out in
QPB_v1.5.3_Implementation_Plan.md Open Question 1; this is calibrated so
that QPB itself classifies as Hybrid (its SKILL.md prose is comparable to
its code LOC, not dominant over it).

Override hook: callers may pass an explicit `override` (with rationale) to
bypass the heuristic. v1.5.3 Phase 4's Council uses this hook to re-verify
classifications and override them with rationale; the heuristic's evidence
is preserved in the output even when an override applies.

CLI override (Phase 4 DQ-4-1):

    python3 -m bin.classify_project --target <repo> \\
        --override <code|skill|hybrid> \\
        --override-rationale "<text>" \\
        --write

The full Phase 4 Council Override Workflow (when to invoke, what
downstream phases need re-running, expected post-override
project_type.json shape) lives at
`docs/design/QPB_v1.5.3_Phase4_Council_Override_Workflow.md`.

Note on the empty-SKILL.md edge case: an empty SKILL.md (zero words) at
the repo root classifies as Hybrid with low confidence, NOT Code. This
is intentional -- the file's presence is treated as a signal of
skill-shaped intent, distinct from a target where SKILL.md is genuinely
absent -- but a maintainer who creates an empty SKILL.md as a template
stub may be surprised. To classify as Code, ensure SKILL.md is absent
(not just empty); to keep the Hybrid classification, populate SKILL.md
with prose. The `confidence_reason` field on the JSON output reports
`"empty-skill-md"` for this case so downstream consumers can detect and
flag the stub state explicitly.

Public API:
    classify_project(target_dir, *, override=None, override_rationale=None)
        -> classification record dict
    write_classification(target_dir, record) -> path written

Module is stdlib-only and side-effect-free except for write_classification
and the optional `git ls-files` subprocess invocation used to respect
.gitignore when counting code LOC.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

# v1.5.7 instruction 077 (addendum §5.2 W3 entry-point audit): uniform
# entry-point bootstrap. classify_project.py is stdlib-only and imports
# no sibling bin.* module today, so this is a defensive no-op that
# keeps script-form invocation (`python <clone>/bin/classify_project.py
# …` from any cwd) robust if a future sibling import is added (the
# module docstring already discusses the bin.role_map replacement path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CLASSIFIER_VERSION = "1.0"
# Bumped from "1.0" to "1.1" in v1.5.3 Phase 2 to signal the additive
# `evidence.confidence_reason` field (C.5 polish). Purely additive change;
# no existing field's shape or semantics is altered. The classifier's
# JSON schema is internal to bin/classify_project.py and is not consumed
# by quality_gate.py / schemas.md, so this bump is independent of the
# per-manifest `schema_version`-MUST-equal-`metadata.version` invariant.
SCHEMA_VERSION = "1.1"

# C.5 polish (v1.5.3 Phase 2): allowed values for the `confidence_reason`
# field on the JSON evidence block. Decision-tree order is enforced in
# _apply_heuristic; the first match wins.
#
# DQ-2 (v1.5.3 Phase 3 / Round 2 Council): side-aware variants
# (`near-band-edge-skill-side` / `near-band-edge-hybrid-side`) are a
# future-extension candidate if downstream consumers need to apply
# different derivation strategies for "almost Hybrid" Skill projects vs
# "deep Skill" projects. Phase 3's four-pass pipeline branches on
# classification (Skill vs Hybrid vs Code) only, so the bare
# `near-band-edge` value is sufficient today.
VALID_CONFIDENCE_REASONS = (
    "empty-skill-md",
    "empty-target",
    "small-project",
    "near-band-edge",
    "unambiguous",
)


@dataclass(frozen=True)
class ProjectClassification:
    """Structured result of the heuristic decision tree (DQ-1).

    Replaces the prior 4-tuple `(classification, rationale, confidence,
    confidence_reason)` so that Phase 3 callers (and any future
    consumer) can reference fields by name rather than positional index.
    Frozen so the value is hashable and immutable -- consistent with
    _apply_heuristic's pure-function contract.
    """

    classification: str
    rationale: str
    confidence: str
    confidence_reason: str

# Proportional band around each ratio threshold within which the
# heuristic reports `near-band-edge`. 10% on each side: ratio in
# [1.8, 2.2] flags the 2.0x boundary; ratio in [4.5, 5.5] flags the
# 5.0x boundary.
_NEAR_BAND_EDGE_PROPORTION = 0.10

VALID_CLASSIFICATIONS = ("Code", "Skill", "Hybrid")
VALID_CONFIDENCES = ("high", "medium", "low")

# Words-to-LOC ratio thresholds. Calibrated so QPB itself (SKILL.md prose
# comparable to but not dominant over bin/ code) classifies as Hybrid; per
# QPB_v1.5.3_Implementation_Plan.md Open Question 1.
#
# Why these specific values: prose words and code lines are not directly
# comparable units, so the boundaries are picked empirically against real
# targets, not derived from first principles. QPB itself sits at ~1.7
# words-per-LOC, so the SKILL_DOMINANCE_RATIO (Skill vs Hybrid boundary)
# at 2.0 leaves QPB comfortably on the Hybrid side -- a 1× boundary would
# misclassify QPB as Skill, a 5× boundary would miss obvious skill-shaped
# targets that still carry some helper code.
SKILL_DOMINANCE_RATIO = 2.0
# Anything 5× or more is unambiguously skill-dominant regardless of
# absolute code size: even a real engineering codebase tucked under
# extensive skill prose still falls below 5× when its code carries weight,
# so a project crossing this threshold is reliably Skill, not Hybrid. The
# 5× choice (vs 3× or 10×) keeps the medium-confidence Skill band wide
# enough to catch borderline projects and gives QPB at its current ratio
# (~1.10× as of v1.5.3 release-readiness; verify with
# `python3 -m bin.classify_project --benchmark`) a comfortable margin
# from any transition. Phase 5 calibration anchor refresh: the ratio
# slid from 1.67× (v1.5.2) to 1.10× (v1.5.3) as code outpaced prose
# during Phases 1-4. Re-check before each release; QPB sits well within
# the [1.0×, 2.0×) Hybrid band either way.
SKILL_HIGH_CONFIDENCE_RATIO = 5.0
# Symmetric to SKILL_DOMINANCE_RATIO but on the code-dominant side: a
# project where code outsizes SKILL.md prose by 2× or more is reliably
# Hybrid with high confidence. Picked at 2.0 (not e.g. 3.0) so that the
# medium-confidence Hybrid band stays narrow -- a code-dominant project
# should surface as high-confidence Hybrid quickly, leaving the medium
# band for genuinely balanced cases like QPB.
HYBRID_HIGH_CONFIDENCE_RATIO = 2.0

# Threshold below which a no-SKILL project is "Code with low confidence"
# rather than "Code with high confidence" -- a near-empty directory is not
# a confident Code classification.
SMALL_PROJECT_LOC_THRESHOLD = 50

EXTENSION_LANGUAGE = {
    ".py": "Python",
    ".go": "Go",
    ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin", ".kts": "Kotlin",
    ".scala": "Scala",
    ".c": "C", ".h": "C",
    ".cpp": "C++", ".hpp": "C++", ".cc": "C++", ".cxx": "C++", ".hxx": "C++",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".m": "Objective-C", ".mm": "Objective-C",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".cs": "C#",
    ".fs": "F#",
    ".vb": "Visual Basic",
}
CODE_EXTENSIONS = frozenset(EXTENSION_LANGUAGE.keys())

# Conventional ignore directories for filesystem walk (used when target_dir
# is not a git repo). git ls-files takes precedence when available because
# it already respects .gitignore.
# v1.5.7 instruction 054 (A-10): the trailing block (.claude … .aider)
# are the 8 adopter install marker dirs. QPB installs its own skill
# tree (incl. post-050 Python closure modules) under one of these
# markers; classify_project's walker would otherwise descend and
# miscount QPB's own files when classifying Code/Skill/Hybrid.
# Canonical source is bin/install_skill.AI_TOOL_MAP.values();
# intentionally DUPLICATED (Option B, additive — instruction-053
# precedent) for parity with the two quality_gate.py walkers, which
# cannot import install_skill (standalone-deployed gate).
#
# DELIBERATE DEVIATION FROM THE INSTRUCTION (verify-before-claim):
# the instruction directs adding ``"bin"`` to ALL THREE sites, but
# ``"bin"`` is NOT added HERE. classify_project's purpose is to
# *count adopter source* to classify Code/Skill/Hybrid; adopter
# projects legitimately keep source in a top-level ``bin/`` —
# excluding it misclassifies them (proven: the in-tree
# ``hybrid_fixture`` keeps its Python in ``bin/`` and a blanket
# ``"bin"`` exclusion regressed it Hybrid → Skill). The two
# quality_gate.py walkers DO exclude ``"bin"`` because the gson A-10
# ship-blocker is specifically language *detection* (a first-match
# heuristic) returning "py" from QPB's flat-layout ``target/bin/*.py``
# — a different role with a different trade-off. The 8 markers fully
# cover the dominant install_skill.py layout AND the flat
# ``.github/skills/`` tree; the only residual is the flat-layout
# root-level ``target/bin/*.py`` (setup_repos), an accepted minor
# under-exclusion here vs. breaking every ``bin/``-using adopter.
# TODO(v1.5.7.x): consolidate the exclusion-set copies behind a
# single gate-standalone-safe shared constant.
DEFAULT_IGNORE_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "target", "build", "dist", ".idea", ".vscode", ".pytest_cache",
    ".mypy_cache", ".tox", ".eggs", "vendor",
    ".claude", ".cursor", ".github", ".continue",
    ".codex", ".windsurf", ".cline", ".aider",
})


def classify_project(
    target_dir: Path,
    *,
    override: Optional[str] = None,
    override_rationale: Optional[str] = None,
) -> dict:
    """Classify a target directory as Code, Skill, or Hybrid.

    target_dir: repository root to classify.
    override: optional explicit classification ("Code" / "Skill" / "Hybrid")
        that supersedes the heuristic. The heuristic is still computed so
        its evidence is recorded in the output.
    override_rationale: free-text reason for the override. Required when
        override is non-None.

    Returns a dict matching the JSON schema documented in this module's
    header. Does not write to disk; callers pass the dict to
    write_classification() to persist.
    """
    if override is not None:
        if override not in VALID_CLASSIFICATIONS:
            raise ValueError(
                f"override must be one of {VALID_CLASSIFICATIONS}; got {override!r}"
            )
        if not override_rationale:
            raise ValueError("override_rationale is required when override is set")

    target_dir = Path(target_dir).resolve()
    skill_md_path = target_dir / "SKILL.md"
    skill_md_present = skill_md_path.is_file()
    skill_md_word_count = _count_words(skill_md_path) if skill_md_present else None

    total_code_loc, code_languages = _count_code_loc(target_dir)

    heuristic = _apply_heuristic(
        skill_md_present=skill_md_present,
        skill_md_word_count=skill_md_word_count,
        total_code_loc=total_code_loc,
    )
    heuristic_class = heuristic.classification
    heuristic_rationale = heuristic.rationale
    heuristic_confidence = heuristic.confidence
    confidence_reason = heuristic.confidence_reason

    if override is not None:
        final_classification = override
        final_rationale = (
            f"Override applied: {override_rationale} "
            f"(heuristic suggested {heuristic_class}: {heuristic_rationale})"
        )
        # Explicit override is treated as authoritative; confidence reflects
        # the human/Council judgment, not the underlying signal.
        final_confidence = "high"
    else:
        final_classification = heuristic_class
        final_rationale = heuristic_rationale
        final_confidence = heuristic_confidence

    return {
        "schema_version": SCHEMA_VERSION,
        "classification": final_classification,
        "rationale": final_rationale,
        "confidence": final_confidence,
        "evidence": {
            "skill_md_present": skill_md_present,
            # Repo-relative POSIX-style path -- never absolute -- so the
            # JSON record stays portable across machines and CI environments
            # (C.2 polish). The classifier only ever looks for SKILL.md at
            # target_dir / "SKILL.md", so the relative path is fixed when
            # SKILL.md is present.
            "skill_md_path": "SKILL.md" if skill_md_present else None,
            "skill_md_word_count": skill_md_word_count,
            "total_code_loc": total_code_loc,
            "code_languages": sorted(code_languages),
            # C.5 polish (v1.5.3 Phase 2): which decision-tree branch fired
            # in _apply_heuristic. Internal to bin/classify_project.py;
            # not validated by quality_gate.py.
            "confidence_reason": confidence_reason,
        },
        "classified_at": _utc_now_iso(),
        "classifier_version": CLASSIFIER_VERSION,
        "override_applied": override is not None,
        "override_rationale": override_rationale if override is not None else None,
    }


def write_classification(target_dir: Path, record: dict) -> Path:
    """Write a classification record to <target>/quality/project_type.json.

    Creates the quality/ directory if it doesn't exist. Atomic write
    (tmp + rename) so a crash mid-write doesn't leave a half-written JSON
    file on disk. Returns the path written.
    """
    target_dir = Path(target_dir).resolve()
    quality_dir = target_dir / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    out_path = quality_dir / "project_type.json"

    payload = json.dumps(record, indent=2, sort_keys=False) + "\n"
    tmp_path = out_path.with_name(out_path.name + ".tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    os.replace(tmp_path, out_path)
    return out_path


# ---------------------------------------------------------------------------
# Internals (private; signatures fixed in skeleton, bodies in next commit)
# ---------------------------------------------------------------------------


def _count_words(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    return len(text.split())


def _count_code_loc(target_dir: Path) -> "tuple[int, set[str]]":
    """Count non-blank lines in code files; identify languages present.

    Defers file enumeration to _iter_code_files (which prefers `git ls-files`
    over a filesystem walk so .gitignore is respected). Counts only
    non-blank lines so generated whitespace doesn't dominate the comparison
    against SKILL.md word count.
    """
    languages: set[str] = set()
    total_loc = 0
    for f in _iter_code_files(target_dir):
        ext = f.suffix.lower()
        lang = EXTENSION_LANGUAGE.get(ext)
        if lang is not None:
            languages.add(lang)
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if line.strip():
                total_loc += 1
    return total_loc, languages


def _iter_code_files(target_dir: Path) -> Iterable[Path]:
    """Yield code file paths under target_dir.

    Uses `git ls-files` when target_dir is a git repo so .gitignore is
    respected (this matters for projects like QPB where vendored benchmark
    targets live under repos/ but are gitignored). Falls back to an
    os.walk that prunes DEFAULT_IGNORE_DIRS.
    """
    git_files = _git_tracked_files(target_dir)
    if git_files is not None:
        for rel in git_files:
            p = target_dir / rel
            if p.suffix.lower() in CODE_EXTENSIONS and p.is_file():
                yield p
        return

    for root, dirs, names in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in DEFAULT_IGNORE_DIRS]
        for name in names:
            p = Path(root) / name
            if p.suffix.lower() in CODE_EXTENSIONS:
                yield p


def _git_tracked_files(target_dir: Path) -> "Optional[list[str]]":
    """Return tracked relative paths via `git ls-files`, or None if not a repo."""
    git_dir = target_dir / ".git"
    if not git_dir.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return [line for line in result.stdout.splitlines() if line]


def _apply_heuristic(
    *,
    skill_md_present: bool,
    skill_md_word_count: Optional[int],
    total_code_loc: int,
) -> ProjectClassification:
    """Apply the classification heuristic.

    Returns a ProjectClassification with `.classification`, `.rationale`,
    `.confidence`, `.confidence_reason` fields. See module header for the
    heuristic statement; ratio thresholds are module-level constants. The
    `confidence_reason` field enumerates which branch of the decision
    tree fired -- C.5 polish to make the classifier's confidence
    calibration auditable.

    Decision-tree precedence (top-down, first match wins):
      1. empty-skill-md  -- SKILL.md present but 0 words
      2. empty-target    -- no SKILL.md and no code
      3. small-project   -- no SKILL.md, code below SMALL_PROJECT_LOC_THRESHOLD
      4. near-band-edge  -- ratio within 10% of 2.0x or 5.0x
      5. unambiguous     -- everything else (default catch-all)

    Return-type history: pre-Phase-3 this returned a 4-tuple; DQ-1
    promoted the tuple to a frozen dataclass so Phase 3 callers and
    future consumers can use named accessors instead of positional
    unpacking.
    """
    word_count = skill_md_word_count or 0

    # Branch 1: empty-skill-md (SKILL.md exists but contributes no prose).
    # The file's presence signals skill-shaped intent but there's no prose
    # to be the program; classify as Hybrid/low so a maintainer notices.
    if skill_md_present and word_count == 0:
        return ProjectClassification(
            classification="Hybrid",
            rationale=(
                f"SKILL.md exists at repo root but is empty (0 words); "
                f"{total_code_loc} non-blank code lines observed."
            ),
            confidence="low",
            confidence_reason="empty-skill-md",
        )

    # Branch 2: empty-target (no SKILL.md AND no code -- empty repo).
    if not skill_md_present and total_code_loc == 0:
        return ProjectClassification(
            classification="Code",
            rationale=(
                "No SKILL.md at repo root; no code lines observed (empty or "
                "near-empty target)."
            ),
            confidence="low",
            confidence_reason="empty-target",
        )

    # Branch 3: small-project (no SKILL.md, code below confidence floor).
    if not skill_md_present and total_code_loc < SMALL_PROJECT_LOC_THRESHOLD:
        return ProjectClassification(
            classification="Code",
            rationale=(
                f"No SKILL.md at repo root; only {total_code_loc} non-blank "
                f"code lines observed (small project below the "
                f"{SMALL_PROJECT_LOC_THRESHOLD}-line confidence threshold)."
            ),
            confidence="medium",
            confidence_reason="small-project",
        )

    # Beyond branches 1-3 we always have *some* code OR a populated SKILL.md.
    # Compute the classification + confidence first, then disambiguate
    # near-band-edge vs unambiguous from the ratio (branches 4 / 5).

    if not skill_md_present:
        # Confident Code branch (substantial code, no SKILL.md).
        return ProjectClassification(
            classification="Code",
            rationale=(
                f"No SKILL.md at repo root; {total_code_loc} non-blank code "
                f"lines observed across the repo."
            ),
            confidence="high",
            confidence_reason="unambiguous",
        )

    # SKILL.md with prose but no code at all: unambiguously Skill.
    if total_code_loc == 0:
        return ProjectClassification(
            classification="Skill",
            rationale=(
                f"SKILL.md exists at repo root with {word_count} prose words "
                f"and no code lines observed."
            ),
            confidence="high",
            confidence_reason="unambiguous",
        )

    ratio_words_to_code = word_count / total_code_loc
    confidence_reason = _confidence_reason_from_ratio(ratio_words_to_code)

    if ratio_words_to_code > SKILL_HIGH_CONFIDENCE_RATIO:
        return ProjectClassification(
            classification="Skill",
            rationale=(
                f"SKILL.md prose word count ({word_count}) substantially "
                f"exceeds code line count ({total_code_loc}); "
                f"ratio {ratio_words_to_code:.1f}x."
            ),
            confidence="high",
            confidence_reason=confidence_reason,
        )
    if ratio_words_to_code > SKILL_DOMINANCE_RATIO:
        return ProjectClassification(
            classification="Skill",
            rationale=(
                f"SKILL.md prose word count ({word_count}) exceeds code line "
                f"count ({total_code_loc}) by more than "
                f"{SKILL_DOMINANCE_RATIO:g}x (actual {ratio_words_to_code:.1f}x)."
            ),
            confidence="medium",
            confidence_reason=confidence_reason,
        )

    ratio_code_to_words = total_code_loc / word_count
    if ratio_code_to_words > HYBRID_HIGH_CONFIDENCE_RATIO:
        return ProjectClassification(
            classification="Hybrid",
            rationale=(
                f"SKILL.md exists at repo root ({word_count} prose words) but "
                f"code dominates ({total_code_loc} non-blank lines; "
                f"ratio {ratio_code_to_words:.1f}x)."
            ),
            confidence="high",
            confidence_reason=confidence_reason,
        )
    return ProjectClassification(
        classification="Hybrid",
        rationale=(
            f"SKILL.md exists at repo root ({word_count} prose words) "
            f"alongside substantial code ({total_code_loc} non-blank lines); "
            f"ratio {ratio_words_to_code:.2f} words/LOC sits within the "
            f"Hybrid band [1/{HYBRID_HIGH_CONFIDENCE_RATIO:g}x, "
            f"{SKILL_DOMINANCE_RATIO:g}x]."
        ),
        confidence="medium",
        confidence_reason=confidence_reason,
    )


def _confidence_reason_from_ratio(ratio: float) -> str:
    """Pick `near-band-edge` vs `unambiguous` from a words/LOC ratio.

    Returns `near-band-edge` when the ratio sits within
    _NEAR_BAND_EDGE_PROPORTION (10%) of either SKILL_DOMINANCE_RATIO or
    SKILL_HIGH_CONFIDENCE_RATIO; otherwise returns `unambiguous`. Used
    only for inputs that have both prose and code (branches 4/5 of the
    decision tree).
    """
    delta = _NEAR_BAND_EDGE_PROPORTION
    near_dominance = (
        SKILL_DOMINANCE_RATIO * (1.0 - delta)
        <= ratio
        <= SKILL_DOMINANCE_RATIO * (1.0 + delta)
    )
    near_high = (
        SKILL_HIGH_CONFIDENCE_RATIO * (1.0 - delta)
        <= ratio
        <= SKILL_HIGH_CONFIDENCE_RATIO * (1.0 + delta)
    )
    if near_dominance or near_high:
        return "near-band-edge"
    return "unambiguous"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# CLI / benchmark verification entry point
# ---------------------------------------------------------------------------
#
# Usage:
#   python3 -m bin.classify_project --target <path> [--write]
#   python3 -m bin.classify_project --benchmark
#
# --benchmark classifies the v1.5.3 Phase 1 acceptance set: the five code
# benchmark repos plus QPB itself, and writes results to each target's
# quality/project_type.json (skipping QPB's own write so the classifier
# does not introduce a tracked file under quality/ on the QPB repo).


# The acceptance set is fixed; the brief calls these out by name. Paths
# are resolved relative to the QPB repo root (this file's grandparent).
_QPB_ROOT = Path(__file__).resolve().parents[1]

# Maintenance discipline (Phase 5 DQ-5-3 / Stage 3C): the cobra path
# is pinned per release rather than auto-resolved. To bump the
# pinned snapshot for a future v1.5.x release:
#   1. Verify the new cobra/ snapshot exists under repos/.
#   2. Update the path tuple below.
#   3. Re-run `python3 -m bin.classify_project --benchmark`; commit
#      the updated benchmark log along with the pin bump.
# Auto-resolving (e.g. globbing "repos/cobra-*") would silently
# follow whatever snapshot happens to be on disk and break
# reproducibility across releases. Explicit pinning keeps the
# benchmark surface stable.
_BENCHMARK_TARGETS: list[tuple[str, Path, str, bool]] = [
    # (label, path-relative-to-QPB-root, expected_classification, write_to_disk)
    ("chi-1.5.1", Path("repos/chi-1.5.1"), "Code", True),
    ("virtio-1.5.1", Path("repos/virtio-1.5.1"), "Code", True),
    ("express-1.5.1", Path("repos/express-1.5.1"), "Code", True),
    ("cobra-1.3.46", Path("repos/cobra-1.3.46"), "Code", True),
    ("casbin-1.5.1", Path("repos/archive/casbin-1.5.1"), "Code", True),
    # QPB itself: classify but do NOT write -- QPB's quality/ subtree is
    # tracked, and the v1.5.3 Phase 1 brief explicitly forbids modifying
    # files outside the Phase 1 surface. The verification log captures the
    # JSON content for the audit trail.
    ("QPB-self", Path("."), "Hybrid", False),
]


def _run_benchmark_verification(
    qpb_root: Path,
    log_path: Optional[Path],
) -> int:
    """Run the classifier against the v1.5.3 Phase 1 acceptance set.

    Returns 0 if every target produced its expected classification, 1 if any
    classification mismatched. Writes a verification log if log_path is set.
    """
    lines: list[str] = []
    lines.append("# QPB v1.5.3 Phase 1 -- Project type classifier verification")
    lines.append("")
    lines.append(f"Classifier version: {CLASSIFIER_VERSION}")
    lines.append(f"Schema version:     {SCHEMA_VERSION}")
    lines.append(f"Run timestamp:      {_utc_now_iso()}")
    lines.append("")
    lines.append("## Per-target results")
    lines.append("")

    overall_ok = True
    for label, rel_path, expected, write_to_disk in _BENCHMARK_TARGETS:
        target = (qpb_root / rel_path).resolve()
        lines.append(f"### {label}")
        lines.append("")
        lines.append(f"- target: `{target}`")
        if not target.exists():
            lines.append("- result: SKIPPED (target path does not exist)")
            lines.append("")
            overall_ok = False
            continue

        record = classify_project(target)
        actual = record["classification"]
        match = "OK" if actual == expected else "FAIL"
        if actual != expected:
            overall_ok = False

        lines.append(f"- expected: `{expected}`")
        lines.append(f"- actual:   `{actual}`  ({record['confidence']})")
        lines.append(f"- result:   {match}")
        lines.append(f"- evidence: {json.dumps(record['evidence'], sort_keys=True)}")

        if write_to_disk:
            out_path = write_classification(target, record)
            lines.append(f"- wrote:    `{out_path}`")
        else:
            lines.append("- wrote:    (skipped; capturing JSON in log)")

        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(record, indent=2))
        lines.append("```")
        lines.append("")

    summary = "PASS" if overall_ok else "FAIL"
    lines.append(f"## Overall: {summary}")
    lines.append("")

    rendered = "\n".join(lines)
    print(rendered)

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(rendered, encoding="utf-8")

    return 0 if overall_ok else 1


def _parse_args(argv: Optional[list[str]] = None) -> "argparse.Namespace":
    import argparse

    parser = argparse.ArgumentParser(
        prog="classify_project",
        description=(
            "v1.5.3 Phase 1 project-type classifier. "
            "Classifies a target as Code, Skill, or Hybrid."
        ),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--target",
        type=Path,
        help="classify a single target directory",
    )
    mode.add_argument(
        "--benchmark",
        action="store_true",
        help=(
            "run the v1.5.3 Phase 1 acceptance set (5 code benchmarks + QPB) "
            "and emit a verification log"
        ),
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "with --target: also write <target>/quality/project_type.json "
            "(default: print only)"
        ),
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="with --benchmark: path to write the verification log",
    )
    # Phase 4 DQ-4-1 (Council override workflow): Round 1 carry-
    # forward. The classify_project() function has had override /
    # override_rationale parameters since v1.5.3 Phase 1, but they
    # weren't exposed at the CLI surface. Phase 4 adds them so a
    # Council reviewer who believes the heuristic classification is
    # wrong can re-run with explicit override + rationale. See
    # docs/design/QPB_v1.5.3_Phase4_Council_Override_Workflow.md.
    parser.add_argument(
        "--override",
        choices=["code", "skill", "hybrid"],
        default=None,
        help=(
            "override the heuristic classification with this value "
            "(case-insensitive); requires --override-rationale"
        ),
    )
    parser.add_argument(
        "--override-rationale",
        type=str,
        default=None,
        help="required when --override is used; recorded in project_type.json",
    )
    args = parser.parse_args(argv)
    if args.override and not args.override_rationale:
        parser.error("--override requires --override-rationale")
    if args.override_rationale and not args.override:
        parser.error("--override-rationale only meaningful with --override")
    return args


def _main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)

    if args.benchmark:
        return _run_benchmark_verification(_QPB_ROOT, args.log)

    # The classify_project() function expects capitalized values
    # ("Code"/"Skill"/"Hybrid") in VALID_CLASSIFICATIONS; the CLI
    # accepts lowercase per the Phase 4 brief. Normalize here.
    override = args.override.capitalize() if args.override else None
    record = classify_project(
        args.target,
        override=override,
        override_rationale=args.override_rationale,
    )
    print(json.dumps(record, indent=2))
    if args.write:
        out_path = write_classification(args.target, record)
        print(f"\nwrote: {out_path}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_main())
