# Output for 014-feature-h-persona-orchestration-and-isolation.md
**Status:** completed

## Files created / changed
| Path | Note |
|------|------|
| `plugins/.../scripts/persona_orchestration.py` | **New** stdlib-only module: input staging, tool-restricted spawn config, fabrication-tell, `run_personas` (parallel/blind), target-agnostic provisioning seam. |
| `bin/tests/test_persona_orchestration_v160.py` | **New** — 16 tests: staging correctness, least-privilege *prevention* (mutation), fabrication-tell, independence, diff-set shape, target-agnostic seam. |
| `docs/process/QPB_v1.6.0_Instruction_014_Self_Council/synthesis.md` | Tracked 3-charter security-Council synthesis. |
| `runner/.../reviews/014_self_council/{panelist_A,B,C,synthesis}.md` | Gitignored full Council artifacts. |

## Commits made (branch `1.6.0`, local only — never pushed)
- `8b38a33` — Feature H slice 2: persona orchestration + least-privilege isolation (+ 15 tests).
- `2476984` — self-Council polish: pin the traversal-flatten test (Panelist A), drop unused import (Panelist C).
- `<synthesis commit>` — tracked self-Council synthesis.

## Acceptance oracle — pass/fail per item
| # | Item | Result |
|---|------|--------|
| 1 | Staging dir contains exactly docs+spec+rubric; impl tree/secrets/`operator_confirmations.jsonl` provably absent | **PASS** — `StagingCorrectnessTests` |
| 2 | Least-privilege *enforced, not detected* (persona cannot reach impl/secrets/out-of-run) | **PASS** — `LeastPrivilegePreventionTests` (prevention proven, mutation-bitten) |
| 3 | Fabrication-tell fires on output referencing unstaged source | **PASS** — `FabricationTellTests` |
| 4 | Independence — personas parallel, blind to each other | **PASS** — `IndependenceAndRunTests` |
| 5 | Raw candidate diff-set well-formed; no grounding/merge/apply here | **PASS** — `defer` rejected; move carries req/section/reason/citation |
| 6 | Target-agnostic seam (Feature B can bind) | **PASS** — `TargetAgnosticSeamTests` (B-shaped provision drives it unchanged) |
| 7 | Existing suite unchanged and green | **PASS** — see STATUS |

## The staging layout + absence assertions
`stage_persona_inputs(persona_id, inputs, staging_root)` materializes a fresh `staging_root/<persona_id>/` containing **exactly** the declared inputs (each `StagedInput(name, text)` written as a flat file — the name is flattened via `Path(name).name` so a traversal name like `../../passwd` lands *inside* the dir, never escapes). Prevention by absence: the implementation tree, secrets/credentials, and `operator_confirmations.jsonl` are never copied, so they are absent. Defensive checks: `stage_persona_inputs` refuses to stage a forbidden name (`operator_confirmations.jsonl`); `assert_isolation` raises on any symlink (would escape), subdirectory (could re-introduce the impl tree), forbidden file, or path that resolves outside the staging dir.

## The exact tool restriction applied at spawn
`persona_tool_config(staging_dir)` → `PersonaToolConfig(read_root=<staging dir>, allow_tools=("Read",), allow_bash=False, allow_network=False)`. `denies()` returns True for every shell alias (`Bash`/`shell`/`sh`/`exec`/`run`) and every network alias (`fetch`/`WebFetch`/`network`/`curl`/`http`/`url`), and for any tool not in `allow_tools`; Read is allowed, rooted at the staging dir. This is the config the harness applies when it spawns the fresh-context Task sub-agent — data, so it is testable without a live spawn.

## Isolation-prevention mutation results (each out-of-bounds access proven impossible)
With a run tree containing `src/router.go`, `.env`, and `quality/operator_confirmations.jsonl`:
- **impl tree** — `router.go` is **not** in the staging dir (absent), and the config has **no shell/network** to reach it → cannot be read.
- **secret** — `.env` absent + no shell/network → cannot be read.
- **human ledger** — `operator_confirmations.jsonl` absent; staging *refuses* to stage it; no shell → cannot be read or written.
- **symlink escape** — a symlink from the staging dir into a secret/impl file → `assert_isolation` raises.
- **traversal input** — `../../passwd` → flattened to `passwd` inside the staging dir; the outside path is untouched.
Panelist A mutation-bit the guards (weaken `denies`, drop the forbidden-name guard, no-op `assert_isolation`) — each fails the suite, confirming they are load-bearing, not decorative.

## Fabrication-tell (backstop)
`detect_fabrication(diff_set, staged_texts)` flags any move whose `citation` is not a substring of the staged corpus — content the persona could only have obtained by reading source it was not given. It is the second line behind staging + allowlist (the prevention stands even if the tell never fires), tested independently.

## Independence check
`run_personas` calls `executor(persona, staging_dir, tool_config)` — each executor receives **only** its own persona, staging dir, and config; there is no diff-set/sibling-dir parameter and no shared mutable state, so a persona is structurally blind to the others' moves. Each persona gets a **distinct** staging dir. (Sequential loop; literal parallelism is the slice-7 spawn's job — blindness is order-independent, which is what guard 3 requires.)

## Raw diff-set shape
Each persona emits `{"persona_id", "moves": [{"move": confirm/correct/add/drop, "req_id"/"section", "reason", "citation"}]}`. `_validate_diff_set` rejects a `defer` move (operator-only), an unknown move, and a non-dict. No grounding (slice 3), merge (slice 4), or apply (slice 5) happens here — a move is a raw **candidate** carrying the context those slices need.

## Target-agnostic seam
`run_personas(selected, provision, executor, staging_root)` — **`provision`** is the per-target context-provisioning parameter. The orchestration does not know or care what the inputs are: Feature H's `provision` returns docs+spec+rubric; a Feature-B-shaped `provision` (finding+source+REQ+rubric — the *opposite, more-restrictive* isolation) drives the exact same `run_personas` unchanged (`TargetAgnosticSeamTests`, verified by Panelist C). No H-specific input set is baked into the mechanism.

## Self-Council
**Full 3-charter security Council, unanimous SHIP** (each panelist in its own worktree). (a) isolation-is-prevention, (b) independence + diff-set integrity, (c) substrate fidelity + target-agnostic reuse + scope. Two cheap findings closed post-panel (`2476984`): A's traversal-flatten test-coverage gap, C's unused import. Noted non-defects (sequential loop; sibling isolation rests on the live spawn honoring `read_root`) are correct as designed. Artifacts: gitignored `reviews/014_self_council/` + tracked `docs/process/QPB_v1.6.0_Instruction_014_Self_Council/synthesis.md`.

## §8b isolation/substrate — underspecified / notes
- **Sibling-persona isolation ultimately depends on the live spawn honoring `read_root`.** The `staging_root` is shared (all per-persona dirs sit under one parent), so isolation between siblings rests on the per-persona Read-root allowlist (guard 2), not on filesystem separation. The config is correct; the *enforcement* is the harness spawn's contract — §8b's substrate paragraph pins the allowlist but not the spawn implementation, which is the live-run slice's responsibility.
- **`executor` seam ↔ live spawn.** This slice tests the mechanism (staging + tool restriction + fabrication-tell) deterministically; the live fresh-context sub-agent spawn that honors the tool config is slice 7. The seam is where the harness Task-spawn binds.

## For the orchestrator — bundle when execution lands
`persona_orchestration.py` and `persona_catalog.py` (slice 1) are **not bundled adopter-side yet** (nothing imports them adopter-side until the persona-execution/live-run slice). That slice must add **both** to all five bundle-drift sites (install_skill._bundle_files, qpb_validate INSTALL_CLOSURE + count-pin, run_state_lib._FLAT_LAYOUT_BUNDLED_BIN_FILES, AGENTS.md cp recipes, setup_repos.sh).

## Feature H progress
guard 2 (012) + persona catalog (013) + orchestration/isolation (014) done. Remaining: guard 1 grounding (slice 3), guard 3 merge + conflict surfacing + single renumber (slice 4), guard 4 auto-apply + review summary + revert + off-switch (slice 5), maturity disclosure + target-agnostic harness acceptance (slice 6), and the live gap-finding run (slice 7 — needs a live vessel).

## Next action expected from orchestrator
Sequence slice 3 (guard 1 — grounding + fit-for-this-system + candidate bucket), which consumes this slice's raw candidate diff-sets and grounds each move against the byte-verified `formal_docs_manifest` (candidate-only when grounding rests solely on injection-controlled content).
