# Instruction 028 — acceptance-run fixes: self-Council synthesis

**Terminal verdict: unanimous SHIP** across all three charters, zero FIX-REQUIRED.

Three real acceptance runs of the hardened v1.6.0 pipeline (virtio via Claude Code;
chi + express via sonnet sub-agents) validated the core fixes and surfaced four
defects, all confirmed on disk. This instruction fixed all four; none is a
security-floor change. Because fix 1 touches the Phase-0 gate and fixes 2–4 the
persona apply path, a full 3-charter self-Council ran (each panelist in its own
worktree reset to `7a1b20b`, each running the code and mutation-biting).

## The four fixes
1. **Validator flat-layout false-flag** (recurring, adopter-facing). `qpb_validate`
   hard-coded the NESTED install path (`.github/skills/quality-playbook/`), but
   `setup_repos.sh` / the instruction-020 `.github` form install FLAT
   (`.github/skills/SKILL.md`, `bin/` at the target root), so a flat install was
   reported `install_absent` (remediable in `installed`, escalating to blocked in
   `clone`). Fix: `_resolve_install_layout` accepts both layouts (prefers whichever's
   SKILL.md exists; defaults nested so a missing skill still `install_absent`s), and
   `check_closure` resolves `bin/*` under a separate `bin_root`.
2. **Grounded add had no `tier`.** `classify_move` stamps the cited FORMAL_DOC's tier
   (from the doc the tier-guard already resolved) onto the grounded move;
   `_apply_move` backfills it onto the synthesized REQ.
3. **REQUIREMENTS.md lagged the manifest after the persona pass.**
4. **Confirm-move IDs in the review summary were pre-renumber.** `build_review_summary`
   applies the existing renumber remap to every summary entry's `req_id`.

## The fix-3 operator decision
The instruction said fix 3 should "re-render REQUIREMENTS.md ... reuse the existing
render path." Investigation showed there is **no Python markdown renderer** —
REQUIREMENTS.md is AI-authored (the "Feature C renderer" is the agent,
requirements_interview.md § Write-back); `requirements_render.py` only does
renumber/remap/order. Since the instruction's premise was factually contradicted by
the code and the resolution changed the implementation shape, the worker asked the
operator once. **The operator chose "Persist manifest + prose re-render":**
`run_feature_h` now writes the updated `quality/requirements_manifest.json` (the
source of truth), and `requirements_pipeline.md` E.9 instructs the agent to re-render
REQUIREMENTS.md from it after the pass (mirroring the human-interview write-back). No
Python renderer was added.

## Charters + verdicts

- **A — The validator recognizes flat + nested and still fails a truly-missing
  skill: SHIP.** Flat + nested validate clean; a genuinely-missing skill (no SKILL.md
  / bare `.github` / empty target) still `install_absent`s; partial installs (missing
  `bin/`, `references/`) still `install_partial` — the fix relaxes *where* to look,
  not closure completeness (all 54 INSTALL_CLOSURE entries still iterated). The
  default-to-nested guard is mutation-confirmed load-bearing (forcing it to the flat
  root lets a missing skill pass).

- **B — The tier-backfill + re-render are correct and reuse existing paths: SHIP.**
  The tier comes from the SAME `doc` the tier-guard resolved (Tier 1 and 2 verified),
  the guard runs before the stamp, and a tier-less/Tier-4 cite is a candidate (no
  grounded low-tier add). The manifest persist reuses json + the quality/ dir;
  write/no-write/off-switch all correct; **no Python renderer was added** and the
  re-render prose accurately instructs the agent. Both mutations load-bearing.

- **C — The confirm-id remap uses the existing renumber remap + no scope creep:
  SHIP.** `build_review_summary` uses the same `merge_result.remap` the BUG
  cross-refs use — shifted→remapped, unshifted→identity, across confirm/correct/drop
  + conflict target/moves; None/unknown pass through; the remap is idempotent (no
  double-apply) and mutates no state (copies conflict moves). Only 7 files touched;
  no regression. Mutation-confirmed load-bearing.

## Verification
Full suite **2787 / 0 / 14**, Python 3.14.6. Reviewed commit `7a1b20b`.
(Also: a recurring stale zero-byte `.git/index.lock` was cleared at the start of the
tick per the authorized pattern — no live git process.)

**Terminal verdict: SHIP.** The flat `.github` layout validates clean while a
missing skill still blocks; grounded adds are tier-complete; the persona pass
persists the manifest and instructs the re-render; and the review summary references
post-renumber ids.
