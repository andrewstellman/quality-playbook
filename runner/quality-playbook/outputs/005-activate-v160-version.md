# Output for 005-activate-v160-version.md
**Status:** completed

## Files created / changed
| Path | Note |
|------|------|
| `SKILL.md` | Item 1: frontmatter `version: 1.5.10 → 1.6.0` — THE single canonical source. |
| `plugins/quality-playbook/skills/quality-playbook/scripts/benchmark_lib.py` | Item 2: defensive fallback literal `1.5.10 → 1.6.0` (reached only in a broken clone). |
| `CHANGELOG.md` | Item 4: in-progress `[1.6.0]` entry (Features C/D/F), no ship date, no benchmark numbers. |
| `README.md` | Derived surface (build-stamped **Version:** badge) → 1.6.0. |
| `package.json` | Derived surface (build-stamped) → 1.6.0. |
| `pyproject.toml` | Derived surface (build-stamped) → 1.6.0. |
| `plugins/quality-playbook/.claude-plugin/plugin.json` | Derived surface (build-stamped) → 1.6.0. |
| `bin/tests/test_render_contract_v160.py` | Council follow-up: `RenderContractShippedVersionActivatesTests` — pins that the shipped SKILL.md version activates the render contract (closes the panelist's named gap). |

`quality_playbook_cli/_bundle/SKILL.md` (the staged bundle) is **gitignored** and regenerated at build/stage time; it was refreshed to 1.6.0 during the suite run but is not part of the commit.

## Commits made
- `11dd2d5` — v1.6.0 [instr 005]: bump skill version to 1.6.0 — activates Feature C.
- `264d250` — v1.6.0 [instr 005]: pin the shipped-version-activates-the-contract invariant (closes the Council panelist's named gap).
- `3298366` — v1.6.0 [instr 005]: tracked self-Council synthesis.
- `<this commit>` — runner: output for instruction 005.

## Acceptance criteria — pass/fail per item
| Criterion | Result |
|-----------|--------|
| SKILL.md the single source; banner/CLI report 1.6.0 | **PASS (with a caveat)** — `_purpose.get_version()`, `benchmark_lib.RELEASE_VERSION`, and the run-start banner all report **v1.6.0**. `quality_playbook_cli.__version__` reports 1.6.0 too — *but* it reads the staged `_bundle/SKILL.md` first, so it reported 1.5.10 until the suite regenerated the bundle; see Findings. |
| benchmark_lib fallback updated | **PASS** — `RELEASE_VERSION = "1.6.0"`. |
| Full suite green at 1.6.0 | **PASS** — `python3 -m unittest discover bin/tests` → **2592 tests, 0 failures, 14 skipped** at the bump; **2593** after the added activation guard, Python 3.14.6. |
| No version-gated test flipped silently | **PASS** — see Notable observations; the render-contract tests pin `skill_version` explicitly (test constant `SKILL_VERSION="1.6.0"`), and the gate-integration trees stamp their own versions, so nothing changed which branch it exercises. |
| Render contract now activates, not skips | **PASS** — `_render_run_predates_contract(q, "1.6.0")` → `False` (active); at `1.5.10` → `True` (skip). The fixtures already drive the active path. |
| 004 fail-closed still fires at 1.6.0 | **PASS** — mutation bite: neutering the `if product_reqs:` FAIL turns the bold-marker tests RED with the version gate live; restored via `shutil.copy2`, `__pycache__` purged, clean. |
| Version single-source guard | **PASS** — `test_version_single_source_057` green: all derived surfaces (README, package.json, pyproject.toml, plugin.json, `cli.__version__`, `RELEASE_VERSION`, staged `_bundle/SKILL.md`) equal the 1.6.0 frontmatter. |

## Council (if required)
**Verdict: SHIP** (single focused panel, per the instruction). Worktree-isolated. Charter:
item 3 — did any test flip behavior silently, and is any fixture passing only because the
contract was inert?

The panelist reviewed `11dd2d5` and returned SHIP: **no silent flips** (render-contract
tests pin `skill_version` explicitly; gate-integration trees write their own in-fixture
SKILL.md/PROGRESS and run isolated via subprocess), **fixtures not vacuous** (clean doc
passes all checks, ~10 `test_c*_fires` tests FAIL broken input with real code), **004
fail-closed still fires** (mutation-bitten RED, restored), and **version consistency**
holds (057 guard green). It independently verified the real production activation path
(ambient SKILL.md → `detect_skill_version` → `check_render_contract`) fires and FAILs
correctly on a bold-marker document.

**One advisory, closed in `264d250`:** the panelist noted that no *automated* test pins
the real ambient-SKILL.md → activation path — every render-contract test pins
`skill_version`, so a regression stamping SKILL.md below the v1.6.0 floor (turning Feature
C off on every run) would pass the whole suite. Closed by
`RenderContractShippedVersionActivatesTests`, which reads the real repo-root SKILL.md and
asserts the shipped version clears the render-contract floor (robust to future bumps;
fails on a below-floor regression).

Artifacts: `RUNNER_ROOT/reviews/005_self_council/synthesis.md` (gitignored) and the tracked
mirror `docs/process/QPB_v1.6.0_Instruction_005_Self_Council/synthesis.md`.

## Notable observations

### The activation is real
Before the bump, a real run stamped 1.5.10 and the render contract skipped ("v1.6.0+ obligation, skipped"). After: `_render_run_predates_contract` returns `False` at ambient 1.6.0, so `check_render_contract` runs its checks. The instruction's own evidence (a 27-heading conformant document that was NOT checked at 1.5.10, then passed 12 checks once forced to 1.6.0) is now the default path.

### No silent flips; fixtures are not vacuous
- The render-contract fixture tests (`test_render_contract_v160.py`) pass `skill_version` explicitly, with the module constant `SKILL_VERSION = "1.6.0"`. They have therefore always exercised the **active** contract path regardless of what SKILL.md stamped — the bump does not change their behavior, and none was passing only because the contract was inert.
- The version-gating tests (`RenderContractVersionGatingTests`) deliberately stamp 1.5.10 / 1.6.0 / 1.7.2 via PROGRESS.md to assert the skip-vs-active boundary; those are *about* the gate and are unaffected by the ambient bump.
- Gate-integration trees (`minimal_zero_bug_tree`, default version `1.4.4`) carry their own PROGRESS version, so the render contract still correctly skips for them — the bump changes the default for *new* runs, not the recorded version of a synthetic old tree.

### Anything underspecified or wrong

1. **`quality_playbook_cli.__version__` is not purely "runtime-derived from SKILL.md" — it is bundle-first.** The instruction says the CLI version "derives from it at runtime via `_purpose.get_version()`." It does not: `quality_playbook_cli._detect_version()` reads candidate 1 `quality_playbook_cli/_bundle/SKILL.md` (a **gitignored staged build artifact**) *before* candidate 2 the repo-root SKILL.md. So a **stale staged bundle silently shadows the canonical version at runtime.** Concretely: immediately after bumping SKILL.md, the CLI still reported **1.5.10**, because a leftover `_bundle/SKILL.md` from a prior stage still said 1.5.10; only when the suite's build/stage step regenerated the bundle did the CLI report 1.6.0. In a fresh clone (no bundle) or a freshly-built wheel (bundle staged from the 1.6.0 source) the CLI reports 1.6.0 correctly — but a source tree that has ever staged a bundle carries this shadowing risk. **Recommend the orchestrator either (a) reorder `_detect_version` candidates so the live repo-root SKILL.md wins over a staged bundle in a source checkout, or (b) treat a bundle-vs-source version mismatch as a hard error rather than silently preferring the bundle.** The `test_version_single_source_057` guard does catch a stale bundle (it asserts `_bundle/SKILL.md == frontmatter`), so drift is *guarded in CI* — but the guard only passes here because the suite regenerates the bundle as a side effect (next point).

2. **A build/stage test mutates tracked repo files and the gitignored bundle as a side effect.** The four tracked derived surfaces (README, package.json, pyproject.toml, plugin.json) and `_bundle/` went 1.5.10 → 1.6.0 during the suite run, not from any edit of mine — a stage/build test runs against the real repo root and stamps versions there. It produces the correct end state (and the stamped tracked files are the intended derived surfaces of the bump, committed here), but a test with real-working-tree side effects is a hygiene smell: run in a different order, or on a tree where SKILL.md and the stamped files disagreed for a different reason, it could mask or manufacture a diff. Flagged for the orchestrator; out of this instruction's scope.

3. **Scope held:** version-string bump + verification only. No retag, no publish, no release-automation edits. The `_bundle/` refresh happened as a test side effect, not a deliberate publish step, and is gitignored either way.

## Next action expected from orchestrator
Land the instruction-005 commit on `1.6.0` (worker never pushes/merges). Consider the two findings above (CLI bundle-first lookup; the stage test's real-repo side effects). Publishing remains deferred per `QPB_Carry_Forward_To_1.6.0.md`.
