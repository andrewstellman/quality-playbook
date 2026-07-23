# Output for 028-acceptance-run-fixes.md
**Status:** completed

## What this instruction was
Fix four defects surfaced by three real acceptance runs of the hardened v1.6.0
pipeline (virtio via Claude Code; chi + express via sonnet sub-agents). The runs
validated the core fixes (authoritative docs classify citable, advisories floor on
hard signals only, 75–90% Tier 1/2, Feature C/H run correctly) and surfaced four
defects, all confirmed on disk. None is a security-floor change.

## Terminal verdict: unanimous SHIP (0 FIX-REQUIRED)
| Charter | Verdict |
|---------|---------|
| A — Validator recognizes flat + nested, still fails a truly-missing skill | **SHIP** |
| B — Tier-backfill + re-render correct, reuse existing paths | **SHIP** |
| C — Confirm-id remap uses the existing remap, no scope creep | **SHIP** |

Each panelist ran the code against the reviewed commit and mutation-bit the fix.

## Fix 1 — validator flat-layout false-flag (highest priority, adopter-facing)
**Before:** `qpb_validate` resolved `install_root = target / MARKER_TO_INSTALL_REL[marker]`
(the NESTED `.github/skills/quality-playbook/`). But `setup_repos.sh` / the
instruction-020 `.github` form install **flat** (`.github/skills/SKILL.md`, with
`bin/` at the **target root**). So a flat install → `install_root` absent →
`install_absent` (remediable in `installed`, escalating to **blocked** in `clone`)
— a Phase-0 stopper for a real adopter (reproduced in `repos/virtio-1.6.0`).
**After:** `_resolve_install_layout(target, marker) -> (skill_root, bin_root)`
accepts BOTH layouts — prefers whichever's SKILL.md exists, **defaults nested** so a
genuinely-missing skill still `install_absent`s. `check_closure(install_root,
bin_root)` resolves `bin/*` entries under `bin_root` (the target root for flat).
- **Flat validates clean** (no install_absent, no install_partial); the nested layout
  still validates; a missing skill (no SKILL.md / bare `.github` / empty target)
  still fails; a partial install (missing bin/ or references/) still `install_partial`
  — the fix relaxes *where* to look, not *what* must be there (Panelist A, mutation-
  confirmed the default-to-nested guard).

## Fix 2 — grounded persona add had no `tier`
`persona_grounding.classify_move` stamps the cited FORMAL_DOC's tier — from the SAME
`doc` the Tier-1/2 guard already resolved — onto the grounded move; `persona_merge.
_apply_move` backfills `"tier"` onto the synthesized REQ. An `agent-validation` add
is now tier-complete like a derivation REQ (Tier 1 **and** 2 verified). The guard runs
before the stamp, so a Tier-4/tier-less cite is a candidate, never a grounded low-tier
add (Panelist B).

## Fix 3 — REQUIREMENTS.md lagged the manifest (operator-directed resolution)
**Investigation:** the instruction said "re-render REQUIREMENTS.md ... reuse the
existing render path," but there is **no Python markdown renderer** — REQUIREMENTS.md
is AI-authored (the "Feature C renderer" is the agent; `requirements_render.py` only
does renumber/remap/order). The premise was factually contradicted by the code, so I
**asked the operator once**. **The operator chose "Persist manifest + prose
re-render":**
- `run_feature_h` now writes the updated `quality/requirements_manifest.json` (the
  source of truth — the pass applied moves + the terminal renumber). With
  `write=False` it doesn't write it; the off-switch writes neither.
- `references/requirements_pipeline.md` E.9 instructs the agent to **re-render
  REQUIREMENTS.md from the updated manifest** after the persona pass, exactly as the
  human-interview write-back does.
- **No Python renderer was added** (Panelist B confirmed via grep). The Python half is
  the manifest persistence; the re-render is the same AI step the human interview uses.

## Fix 4 — confirm-move IDs in the review summary were pre-renumber
The terminal renumber remaps REQ ids and already updated BUG cross-refs (instr 017),
but the moves recorded in `persona_review_summary.json` still carried pre-renumber
`req_id`s. `build_review_summary` now applies the **same `merge_result.remap`** to
every summary entry's `req_id` (confirm/correct/drop) + the conflict target/moves.
Shifted→remapped, unshifted→identity, None/unknown pass through, idempotent, no state
mutation (Panelist C, mutation-confirmed).

## Acceptance oracle — pass/fail
| # | Item | Result |
|---|------|--------|
| 1 | Flat validates clean (both contexts); nested still validates; missing still fails | **PASS** — `FlatGithubLayout028Tests`; Panelist A (the `install_absent` layout false-flag is context-independent — removed regardless) |
| 2 | Tier backfilled = cited FORMAL_DOC's tier | **PASS** — `test_fix2_grounded_add_backfills_the_cited_docs_tier` |
| 3 | Re-rendered — persisted manifest contains the add | **PASS** — `test_fix3_persists_the_updated_requirements_manifest` (operator-directed persist+prose form) |
| 4 | Confirm IDs remapped post-renumber | **PASS** — `test_fix4_confirm_req_id_is_post_renumber_in_the_review_summary` |
| 5 | Full suite green | **PASS** — 2787 / 0 / 14, Python 3.14.6 |

## Files changed
| File | Fix |
|------|-----|
| `plugins/.../scripts/qpb_validate.py` | 1 — `_resolve_install_layout` + `_skill_installed` + `check_closure(bin_root)` |
| `plugins/.../scripts/persona_grounding.py` | 2 — stamp the cited doc's tier on the grounded move |
| `plugins/.../scripts/persona_merge.py` | 2 — backfill `tier` on the add record |
| `plugins/.../scripts/persona_apply.py` | 3 — persist `requirements_manifest.json`; 4 — remap review-summary `req_id`s |
| `references/requirements_pipeline.md` | 3 — E.9 re-render prose (+ tier/post-renumber notes) |
| `bin/tests/test_qpb_validate.py` | 1 — `FlatGithubLayout028Tests` |
| `bin/tests/test_persona_pipeline_v160.py` | 2/3/4 — `AcceptanceRunFixes028Tests` |

## Commits made (branch `1.6.0`, local only — never pushed)
- `7a1b20b` — the four fixes (code + prose + tests).
- `3ce9975` — tracked self-Council synthesis.

## Notes
- A recurring stale zero-byte `.git/index.lock` (no live git process) was cleared at
  the start of the tick per the authorized pattern.
- The 2 residual `install_partial` findings on the REAL virtio flat install
  (`skill-template.gitignore`, `ai_context/TOOLKIT.md`) are genuine closure gaps in
  setup_repos.sh's benchmark install (it deliberately omits ai_context per 089n) —
  NOT the validator layout false-flag, which is fixed. Whether setup_repos.sh should
  ship those two in the flat layout is a separate completeness matter for the
  orchestrator.

## Remaining release items (unchanged — for the orchestrator)
Broader 1.6.0 acceptance + Phase 8 tag/merge; OD-9 live FP bound from instr 019;
Feature-G non-plaintext-contract → FORMAL_DOC wiring; chi/express/virtio Slice-1
coherence-fixture regeneration (a real run); OD-11 drop/selective-revert BUG-ref
re-point hardening; design-doc refresh (Design.md still mentions the removed
fabrication-tell).

## Artifacts
- Gitignored: `runner/quality-playbook/reviews/028_self_council/` (three panelist verdicts).
- Tracked: `docs/process/QPB_v1.6.0_Instruction_028_Self_Council/synthesis.md`.
