"""role_map.py — QPB v1.5.4 Phase 1 file-role-tagging schema and helpers.

QPB v1.5.4 Part 1 replaces the v1.5.3 mechanical Code/Skill/Hybrid project
classifier with AI-driven file-by-file role tagging produced during Phase 1
exploration. The Phase 1 LLM agent reads SKILL.md (if present) and each
file in the target tree, then emits ``quality/exploration_role_map.json``
with one record per file plus an aggregate ``breakdown``. This module is
the canonical schema definition + reader/validator that all consumers
(INDEX rendering in archive_lib, the four-pass derivation pipeline in
skill_derivation/pass_c, and the skill-side checks in quality_gate.py)
share.

See ``docs/design/QPB_v1.5.4_Design.md`` Part 1 for the rationale that
motivated the redesign and ``docs/design/QPB_v1.5.4_Implementation_Plan.md``
Phase 1 for the work-item breakdown.

Role taxonomy (the fixed surface; new roles must be added here AND in
the Phase 1 prompt's role-taxonomy section in run_playbook.phase1_prompt):

  - ``skill-prose``     SKILL.md / agents/* / declarative skill content.
  - ``skill-reference`` Additional reference docs the skill names
                        (e.g. ``references/exploration_patterns.md``).
  - ``skill-tool``      A script the skill prose explicitly references
                        AND tells the agent to invoke. Distinguished
                        from ``code`` by being subordinate to skill
                        prose; the SKILL.md is the contract, the script
                        is the implementation.
  - ``code``            Independent orchestrator/library code that
                        carries its own behavior contract (e.g. QPB's
                        ``bin/run_playbook.py``).
  - ``test``            Test files and harnesses.
  - ``docs``            README, CHANGELOG, design docs, anything in
                        ``docs/``.
  - ``config``          ``.gitignore``, ``pyproject.toml``, settings.
  - ``fixture``         Test fixtures or example data used by tests.
  - ``formal-spec``     RFCs, external specifications, citable sources.
  - ``playbook-output`` Files inside a target's ``quality/`` subtree
                        from a prior playbook run. Tagging these
                        explicitly prevents the v1.5.3 LOC-pollution
                        bug: prior-run artifacts are no longer counted
                        as the target's own surface.

Schema (``quality/exploration_role_map.json``)::

  {
    "schema_version": "1.0",
    "timestamp_start": "<ISO 8601 UTC>",
    "files": [
      {
        "path": "SKILL.md",
        "role": "skill-prose",
        "size_bytes": 12345,
        "rationale": "..."
        // "skill_prose_reference": "SKILL.md:47"  — required when role is
        //   skill-tool (validate_role_map enforces); optional otherwise.
        //   Anchors the SKILL.md / reference-file location naming this script.
      },
      ...
    ],
    "breakdown": {
      "files_by_role": {"skill-prose": 5, ...},
      "size_by_role":  {"skill-prose": 12345, ...},
      "percentages":   {"skill_share": 0.18, "code_share": 0.65,
                        "tool_share": 0.04, "other_share": 0.13}
    }
  }

Public API:
    SCHEMA_VERSION                       canonical schema version string
    VALID_ROLES                          frozenset of legal role values
    DEFAULT_FILENAME                     "exploration_role_map.json"
    default_path(repo_dir)               -> Path to quality/<DEFAULT_FILENAME>
    load_role_map(path)                  -> dict | None (None if absent)
    validate_role_map(data)              -> list[str] of validation errors
    compute_breakdown(files)             -> breakdown dict from file entries
    has_skill_prose(role_map)            -> bool   (activation: four-pass pipeline)
    has_code(role_map)                   -> bool   (activation: code-side review)
    has_skill_tools(role_map)            -> bool   (activation: prose-to-code divergence)
    derive_legacy_project_type(role_map) -> "Code" | "Skill" | "Hybrid"

The legacy-project-type derivation exists ONLY to feed the v1.5.3 6-row
disposition table inside pass_c (Branch 5 vs Branch 6 hinges on whether
a behavioral claim can be demoted to a code-derived Tier 5, which in turn
hinges on whether the project has any code surface). It is not a return
of the Code/Skill/Hybrid trichotomy as an input field; it is an internal
mapping used by exactly one consumer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional


SCHEMA_VERSION = "1.0"
DEFAULT_FILENAME = "exploration_role_map.json"

# v1.5.4 Round 2 Council finding C1 + Panel A polish (Step 5):
# the canonical INDEX.md schema_version that bin-side emitters
# (archive_lib.build_index_payload, run_playbook.write_live_index_stub)
# stamp on every fresh INDEX. The gate ships into target repos as a
# stdlib-only script and cannot import this module, so it carries its
# own ``SCHEMA_VERSION_CURRENT`` constant (in
# .github/skills/quality_gate/quality_gate.py) — but the cross-check
# in bin/tests/test_legacy_project_type_consistency.py pins them
# equal so a v1.5.5+ schema bump cannot land on one side without
# the other. This is distinct from ``SCHEMA_VERSION`` above, which
# is the role-map JSON schema version, not the INDEX schema version.
INDEX_SCHEMA_VERSION_CURRENT = "2.0"

# Roles that count toward the skill's declarative surface (numerator of
# skill_share in the breakdown percentages).
SKILL_PROSE_ROLES = frozenset({"skill-prose", "skill-reference"})
SKILL_TOOL_ROLES = frozenset({"skill-tool"})
CODE_ROLES = frozenset({"code"})

# ROLE_DESCRIPTIONS is the single source of truth for the role taxonomy.
# Both VALID_ROLES (the gate-side enum check) and the Phase 1 prompt's
# role-taxonomy section (constructed in run_playbook.phase1_prompt) read
# from this dict. Adding a new role here automatically updates both.
# v1.5.4 Round 1 Council finding C3-1.
ROLE_DESCRIPTIONS: dict = {
    "skill-prose": (
        "SKILL.md / agents/* / declarative skill content."
    ),
    "skill-reference": (
        "Additional reference docs the skill names "
        "(e.g., references/exploration_patterns.md)."
    ),
    "skill-tool": (
        "A script the skill prose explicitly references AND tells the "
        "agent to invoke. The distinguishing test: does SKILL.md (or a "
        "referenced doc) contain prose that names this script and tells "
        "the agent to call it for a specific subtask? If yes, "
        "skill-tool. If the script is independent code with its own "
        "behavior contract that the SKILL.md doesn't reference, it's "
        "code. (Worked example: QPB's bin/run_playbook.py is code, NOT "
        "skill-tool — SKILL.md does not direct agents to invoke it; it "
        "has its own contract.)"
    ),
    "code": (
        "Independent orchestrator/library code (carries its own behavior "
        "contract; not subordinate to SKILL.md prose)."
    ),
    "test": "Test files and test harnesses.",
    "docs": "README, CHANGELOG, design docs, anything in docs/.",
    "config": ".gitignore, pyproject.toml, settings.",
    "fixture": "Test fixtures or example data used by tests.",
    "formal-spec": "RFCs, external specifications, citable sources.",
    "playbook-output": (
        "Files inside the target's quality/ subtree, or QPB-managed "
        "installations like quality_gate.py (next to SKILL.md, "
        "regardless of which AI-tool install layout was used), that "
        "came from a prior playbook run rather than the target's "
        "intrinsic surface."
    ),
}

VALID_ROLES = frozenset(ROLE_DESCRIPTIONS.keys())

# v1.5.4 Phase 3.6.1 Section A.1 (codex-prevention): path prefixes that
# MUST NOT appear in the role map. These are .gitignored content
# (git internals) or vendored dependencies that should never be tagged
# as part of the target's intrinsic surface. Codex's 2026-04-29
# self-audit attempt walked .git/ and .venv/, inflating the role map
# to 5287 entries and almost certainly stalling Phase 2 on context.
DISALLOWED_PATH_PREFIXES = frozenset({
    ".git/",
    ".venv/",
    "venv/",
    "node_modules/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".tox/",
})

# Path components (matched against Path(path).parts) whose suffix
# indicates generated content. ``str.startswith`` can't match
# wildcards like ``*.egg-info/``, so we check each path segment for
# the suffix instead.
DISALLOWED_PATH_SUFFIXES = frozenset({
    ".egg-info",
    ".dist-info",
})

# Hard ceiling on role-map entry count. A role map exceeding this
# almost certainly indicates Phase 1 walked .gitignored content. Tune
# via Phase 1 rerun in v1.5.5+ if real-world targets need more
# headroom; the operator override --max-role-map-entries N covers the
# legitimate-but-large case.
MAX_ROLE_MAP_ENTRIES = 2000

# v1.5.4 Phase 3.6.1 Section A.1.b: provenance values record HOW the
# Phase 1 file enumeration was produced. ``git-ls-files`` is the
# preferred path (respects .gitignore automatically); the
# filesystem-walk fallback is only acceptable when the target isn't a
# git repo. ``unknown`` is the migration value for role maps written
# before this field was required.
VALID_PROVENANCE = frozenset({
    "git-ls-files",
    "filesystem-walk-with-skips",
    "unknown",
})

# Required top-level keys in a role map document. ``provenance`` and
# ``summary`` were added in v1.5.4 Phase 3.6.1; older role maps that
# omit them get explicit migration errors from validate_role_map.
_REQUIRED_TOP_KEYS = ("schema_version", "files", "breakdown", "provenance", "summary")
_REQUIRED_BREAKDOWN_KEYS = ("files_by_role", "size_by_role", "percentages")
_REQUIRED_PERCENTAGE_KEYS = (
    "skill_share",
    "code_share",
    "tool_share",
    "other_share",
)
_REQUIRED_FILE_ENTRY_KEYS = ("path", "role", "size_bytes", "rationale")


def default_path(repo_dir: Path) -> Path:
    """Return the canonical role-map path for a target repo."""
    return Path(repo_dir) / "quality" / DEFAULT_FILENAME


def load_role_map(path: Path) -> Optional[dict]:
    """Load and JSON-parse a role-map file. Returns ``None`` if the file
    is absent or cannot be parsed as a JSON object. Does NOT validate
    the schema; call :func:`validate_role_map` for that.
    """
    p = Path(path)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def validate_role_map(
    data: dict,
    *,
    allowed_disallowed_prefixes: Optional[frozenset] = None,
    max_role_map_entries: Optional[int] = None,
) -> list[str]:
    """Return a list of validation errors for ``data``. Empty list ==
    well-formed. Validation covers required keys, role enum, file entry
    shape, breakdown internal consistency (percentages sum to ~1.0
    when total size > 0), provenance, and v1.5.4 Phase 3.6.1
    codex-prevention constraints (disallowed paths + entry-count
    ceiling).

    Operator overrides:
      ``allowed_disallowed_prefixes`` — paths starting with any of
      these prefixes will NOT trigger the disallowed-path validation
      error. Use case: a target that legitimately commits ``dist/``
      content. Suppresses errors for the named prefixes only.

      ``max_role_map_entries`` — overrides ``MAX_ROLE_MAP_ENTRIES`` for
      unusually large legitimate targets.
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["role map is not a JSON object"]

    allowed_prefixes = allowed_disallowed_prefixes or frozenset()
    effective_max = (
        max_role_map_entries
        if max_role_map_entries is not None
        else MAX_ROLE_MAP_ENTRIES
    )

    for key in _REQUIRED_TOP_KEYS:
        if key not in data:
            errors.append(f"missing required key: {key!r}")
    if errors:
        return errors

    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"schema_version {data.get('schema_version')!r} does not match "
            f"expected {SCHEMA_VERSION!r}"
        )

    # Provenance: v1.5.4 Phase 3.6.1 Section A.1.b. Required, must be
    # one of the documented values.
    provenance = data.get("provenance")
    if not isinstance(provenance, str) or provenance not in VALID_PROVENANCE:
        errors.append(
            f"provenance {provenance!r} must be one of "
            f"{sorted(VALID_PROVENANCE)!r}"
        )

    files = data.get("files")
    if not isinstance(files, list):
        errors.append("'files' must be a list")
        return errors

    # Entry-count ceiling check. Counts every entry whether it ends up
    # being well-formed or not — the operator needs the signal that
    # Phase 1 walked too much, regardless of per-entry validity.
    if len(files) > effective_max:
        errors.append(
            f"role map has {len(files)} entries (limit {effective_max}); "
            "likely walked .gitignored content. Re-run Phase 1 with "
            "`git ls-files`-respecting enumeration. Use "
            "--max-role-map-entries N to override the ceiling for "
            "unusually large legitimate targets."
        )

    seen_paths: set[str] = set()
    for idx, entry in enumerate(files):
        if not isinstance(entry, dict):
            errors.append(f"files[{idx}] is not an object")
            continue
        for k in _REQUIRED_FILE_ENTRY_KEYS:
            if k not in entry:
                errors.append(f"files[{idx}] missing required key {k!r}")
        path = entry.get("path")
        if isinstance(path, str):
            if path in seen_paths:
                errors.append(f"files[{idx}] duplicate path {path!r}")
            seen_paths.add(path)
            # v1.5.4 Phase 3.6.1 Section A.1.a: disallowed-path check.
            # Prefix match catches .git/, .venv/, etc. Suffix-on-parts
            # catches *.egg-info/, *.dist-info/ regardless of where in
            # the path they sit.
            for prefix in DISALLOWED_PATH_PREFIXES:
                if path.startswith(prefix) and prefix not in allowed_prefixes:
                    errors.append(
                        f"files[{idx}] path {path!r} starts with "
                        f"disallowed prefix {prefix!r} — "
                        ".gitignored content / vendored deps must not "
                        "appear in the role map. Re-run Phase 1 with "
                        "`git ls-files`-respecting enumeration. Use "
                        "--allow-disallowed-prefix PREFIX to override "
                        "for legitimately-tracked content."
                    )
                    break
            for component in Path(path).parts:
                for suffix in DISALLOWED_PATH_SUFFIXES:
                    if component.endswith(suffix):
                        errors.append(
                            f"files[{idx}] path {path!r} contains "
                            f"component {component!r} ending with "
                            f"disallowed suffix {suffix!r} — generated "
                            "content (egg-info / dist-info) must not "
                            "appear in the role map."
                        )
                        break
        role = entry.get("role")
        if role not in VALID_ROLES:
            errors.append(
                f"files[{idx}] role {role!r} is not in VALID_ROLES "
                f"({sorted(VALID_ROLES)})"
            )
        size = entry.get("size_bytes")
        if not isinstance(size, int) or size < 0:
            errors.append(
                f"files[{idx}] size_bytes must be a non-negative int "
                f"(got {size!r})"
            )
        # v1.5.4 Round 1 Council finding A2/B2/C1: skill_prose_reference
        # is REQUIRED on every skill-tool entry, not merely validated when
        # present. Without it, the Phase 4 prose-to-code divergence check
        # has no anchor to look up — the cited prose location is the
        # entire point of distinguishing skill-tool from code.
        if role == "skill-tool":
            ref = entry.get("skill_prose_reference")
            if ref is None or not isinstance(ref, str) or not ref.strip():
                errors.append(
                    f"file {entry.get('path')!r} has role='skill-tool' but "
                    "missing or empty 'skill_prose_reference'; required for "
                    "Phase 4 prose-to-code divergence checks"
                )

    breakdown = data.get("breakdown")
    if not isinstance(breakdown, dict):
        errors.append("'breakdown' must be an object")
        return errors
    for k in _REQUIRED_BREAKDOWN_KEYS:
        if k not in breakdown:
            errors.append(f"breakdown missing required key {k!r}")

    percentages = breakdown.get("percentages")
    if isinstance(percentages, dict):
        for k in _REQUIRED_PERCENTAGE_KEYS:
            if k not in percentages:
                errors.append(f"breakdown.percentages missing key {k!r}")
            else:
                v = percentages[k]
                if not isinstance(v, (int, float)) or v < 0 or v > 1.0001:
                    errors.append(
                        f"breakdown.percentages[{k!r}] must be in [0, 1] "
                        f"(got {v!r})"
                    )
        total_size = sum(
            int(e.get("size_bytes", 0))
            for e in files
            if isinstance(e, dict) and isinstance(e.get("size_bytes"), int)
        )
        if total_size > 0:
            psum = sum(
                float(percentages.get(k, 0))
                for k in _REQUIRED_PERCENTAGE_KEYS
                if isinstance(percentages.get(k), (int, float))
            )
            if abs(psum - 1.0) > 0.01:
                errors.append(
                    f"breakdown.percentages do not sum to 1.0 (sum={psum:.4f})"
                )

    # v1.5.4 Phase 3.7 Fix 5 (Round 8 HIGH): summary self-consistency.
    # The codex hallucination class (narrative cites X files / JSON
    # holds Y) was structurally addressed in Section A.1.c by routing
    # both artifacts through summarize_role_map(). This validator
    # check closes the gap: a hand-fabricated role map with
    # {"file_count": 9999, "files": [<2 entries>]} would otherwise
    # pass. The stored summary MUST match what summarize_role_map()
    # would produce from the actual files[] list.
    stored_summary = data.get("summary")
    if stored_summary is not None:
        expected_summary = summarize_role_map(data)
        if stored_summary != expected_summary:
            errors.append(
                f"role map summary {stored_summary!r} does not match "
                f"summary derived from files[]: {expected_summary!r}. "
                "The summary must be produced by summarize_role_map() "
                "from the actual files[] entries."
            )

    return errors


def compute_breakdown(files: Iterable[dict]) -> dict:
    """Aggregate ``files`` into the canonical ``breakdown`` dict.

    Percentages are computed against total size_bytes; when total size is
    zero (e.g. an empty target) all four shares default to 0.0. Roles
    contribute to ``skill_share`` (skill-prose + skill-reference),
    ``code_share`` (code), ``tool_share`` (skill-tool), and
    ``other_share`` (everything else). ``playbook-output`` is bucketed
    into ``other_share`` so prior-run artifacts can't inflate the
    target's apparent skill or code surface.
    """
    files_by_role: dict[str, int] = {}
    size_by_role: dict[str, int] = {}
    total_size = 0
    for entry in files:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        if role not in VALID_ROLES:
            continue
        size = entry.get("size_bytes", 0)
        if not isinstance(size, int) or size < 0:
            size = 0
        files_by_role[role] = files_by_role.get(role, 0) + 1
        size_by_role[role] = size_by_role.get(role, 0) + size
        total_size += size

    def _share(role_set: frozenset[str]) -> float:
        if total_size == 0:
            return 0.0
        return sum(size_by_role.get(r, 0) for r in role_set) / total_size

    skill = _share(SKILL_PROSE_ROLES)
    tool = _share(SKILL_TOOL_ROLES)
    code = _share(CODE_ROLES)
    other = max(0.0, 1.0 - skill - tool - code) if total_size > 0 else 0.0

    return {
        "files_by_role": files_by_role,
        "size_by_role": size_by_role,
        "percentages": {
            "skill_share": skill,
            "code_share": code,
            "tool_share": tool,
            "other_share": other,
        },
    }


def summarize_role_map(role_map: dict) -> dict:
    """Single-source-of-truth summary for cross-artifact agreement.

    v1.5.4 Phase 3.6.1 Section A.1.c (codex-prevention M3): codex's
    2026-04-29 self-audit attempt produced an EXPLORATION.md narrative
    that cited a sane file count (~293) while the JSON role map held
    5287 entries. The LLM hallucinated agreement between the two
    artifacts. Both the role map's top-level ``summary`` field AND
    EXPLORATION.md's "File inventory" section MUST render from this
    helper so the agreement is mechanical, not aspirational.

    Returns a dict with:
      - ``file_count`` (int) — total entries in role_map["files"]
      - ``role_breakdown`` (dict[str, int]) — per-role counts
      - ``percentages`` (dict[str, float]) — the four shares
      - ``provenance`` (str) — passed through from the role map

    The ``role_breakdown`` is taken from
    ``role_map["breakdown"]["files_by_role"]`` so the count is
    consistent with what was previously computed; ``file_count`` is
    the raw length of the files list (catches the "breakdown was
    computed but new files were appended without recomputing"
    failure mode).
    """
    files = role_map.get("files") or []
    breakdown = role_map.get("breakdown") or {}
    return {
        "file_count": len(files) if isinstance(files, list) else 0,
        "role_breakdown": dict(breakdown.get("files_by_role") or {}),
        "percentages": dict(breakdown.get("percentages") or {}),
        "provenance": role_map.get("provenance", "unknown"),
    }


def render_role_map_narrative(role_map: dict) -> str:
    """Render the EXPLORATION.md "File inventory" section from the
    role map summary. The Phase 1 prompt instructs the LLM to copy
    this exact rendering into EXPLORATION.md, ensuring the narrative
    cannot disagree with the JSON. v1.5.4 Phase 3.6.1 Section A.1.c."""
    s = summarize_role_map(role_map)
    pcts = s["percentages"]
    lines = [
        "## File inventory (rendered from quality/exploration_role_map.json)",
        "",
        f"- **Total files:** {s['file_count']}",
        f"- **Provenance:** `{s['provenance']}`",
        "- **Role breakdown:**",
    ]
    for role in sorted(s["role_breakdown"].keys()):
        lines.append(f"  - `{role}`: {s['role_breakdown'][role]}")
    lines.extend([
        "- **Surface shares:**",
        f"  - skill: {pcts.get('skill_share', 0.0):.1%}",
        f"  - code: {pcts.get('code_share', 0.0):.1%}",
        f"  - tool: {pcts.get('tool_share', 0.0):.1%}",
        f"  - other: {pcts.get('other_share', 0.0):.1%}",
        "",
        "_If this section disagrees with `quality/exploration_role_map.json`, "
        "the role map is authoritative. Re-render this section from "
        "`bin.role_map.render_role_map_narrative()`._",
    ])
    return "\n".join(lines)


def has_skill_prose(role_map: Optional[dict]) -> bool:
    """True iff the role map contains at least one file tagged
    ``skill-prose`` or ``skill-reference``. This is the activation
    condition for the v1.5.3 four-pass derivation pipeline (replacing
    the prior ``project_type in ('Skill', 'Hybrid')`` gate).
    """
    return _any_role(role_map, SKILL_PROSE_ROLES)


def has_code(role_map: Optional[dict]) -> bool:
    """True iff the role map contains at least one file tagged ``code``.
    Activation for the existing code-review pipeline."""
    return _any_role(role_map, CODE_ROLES)


def has_skill_tools(role_map: Optional[dict]) -> bool:
    """True iff the role map contains at least one ``skill-tool`` file.
    Activation for prose-to-code divergence checks."""
    return _any_role(role_map, SKILL_TOOL_ROLES)


def _any_role(role_map: Optional[dict], roles: frozenset[str]) -> bool:
    if not isinstance(role_map, dict):
        return False
    files = role_map.get("files") or []
    if not isinstance(files, list):
        return False
    for entry in files:
        if isinstance(entry, dict) and entry.get("role") in roles:
            return True
    return False


def derive_legacy_project_type(role_map: Optional[dict]) -> str:
    """Return the v1.5.3-equivalent project type string. Used ONLY by
    pass_c's 6-row disposition table (Branch 5 demotes behavioral claims
    to Tier 5 ``code-derived`` when the project has code authority;
    Branch 6 routes to council-review when it does not).

    Mapping:
      - has skill-prose AND has code  -> "Hybrid"
      - has skill-prose, no code      -> "Skill"
      - no skill-prose                -> "Code"
    """
    skill = has_skill_prose(role_map)
    code = has_code(role_map)
    if skill and code:
        return "Hybrid"
    if skill:
        return "Skill"
    return "Code"


def role_breakdown_for_index(role_map: Optional[dict]) -> Optional[dict]:
    """Return the value to write into the INDEX.md ``target_role_breakdown``
    field. ``None`` when the role map is absent (Phase 1 not yet run);
    otherwise a compact summary containing the breakdown subtree.

    The shape exposed in INDEX is intentionally small (the per-file
    rationale set lives only in exploration_role_map.json itself).
    """
    if not isinstance(role_map, dict):
        return None
    breakdown = role_map.get("breakdown")
    if not isinstance(breakdown, dict):
        return None
    return {
        "files_by_role": breakdown.get("files_by_role", {}),
        "size_by_role": breakdown.get("size_by_role", {}),
        "percentages": breakdown.get("percentages", {}),
    }
