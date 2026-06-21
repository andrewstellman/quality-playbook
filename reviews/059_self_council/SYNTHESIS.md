# 059 self-Council — SYNTHESIS — SHIP

Focused single-panel adversarial self-Council on instruction 059
(print the skill version in the attribution banner), branch `1.5.10`.
A focused panel is sufficient for a change this small (per the
instruction). Reviewer was an independent Agent subagent with a
role-lock preamble, grounding against the git-tracked source.

| Panel | Charter | Verdict |
|-------|---------|---------|
| focused | correctness + spec/design-choice + regression + tests/honesty | **SHIP** (2 NITs) |

## Confirmed
- **Version reaches all print paths.** `attribution_banner_text()`
  renders `v{get_version()}` at call time; `print_attribution_banner()`
  writes it; the install-end banner delegates through it
  (`install_skill.py:734`), and run_playbook start/end + CLI paths
  all route through `print_attribution_banner`. Width 48 ≤ 80; stays
  on **stderr** (089k clean-stdout rule preserved).
- **Runtime-derived design is the right read** (not a gap). The
  version is single-sourced from SKILL.md frontmatter (057): it
  appears as a literal **exactly once** (frontmatter); everywhere it
  is printed it is derived from `get_version()`. A stale install thus
  renders **its own** version — the stale-install tripwire the
  instruction wants. Keeping the SKILL.md fenced block + `BANNER_TEXT`
  as the **versionless skeleton** (with the MANDATORY FIRST ACTION
  **prose** directing the agent to render `vX.Y.Z` from frontmatter)
  preserves the 089j (AGENTS.md) and 090k (SKILL.md) byte-for-byte
  pins and avoids the build-stamp + 057-guard-rewrite blast radius a
  hardcoded literal would have caused.
- **090k pin updated correctly** (version-aware, instruction step 3):
  the stale `"... or add a version number"` clause is gone; the new
  clause + "include the running skill version" directive are pinned.
- **New `test_banner_version_059.py` genuinely bites** — the reviewer
  independently reverted the title line, saw `FAILED (failures=3)`
  (`'v1.5.10' not found`), restored, re-ran green. The pin is dynamic
  (expected derived from `get_version()`, not hardcoded) → a future
  version bump never breaks it.
- Suite **2443 → 2447 (+4), 3× stable, Python 3.14.6** — only the 5
  known baseline failures (3 genuinely pre-existing + the 2
  README-reflow regressions tracked as `QPB_v1.5.10_Implementation_Plan.md`
  item 21; not mislabeled as pre-existing).

## NITs (non-blocking)
1. `attribution_banner_text()` inlines the banner skeleton rather than
   composing from `BANNER_TEXT` — a tiny duplication of the static
   lines (kept readable; the title line is the only difference).
2. Minor SKILL.md prose redundancy between the MANDATORY FIRST ACTION
   sentence and the post-fence clarifying note.

VERDICT: SHIP
