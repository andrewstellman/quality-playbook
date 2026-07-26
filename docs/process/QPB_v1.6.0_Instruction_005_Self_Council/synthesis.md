# Instruction 005 self-Council — synthesis

**Scope:** bump the skill version 1.5.10 → 1.6.0, activating the Feature C render
contract (version-gated to v1.6.0+).
**Panel:** a single focused panelist per the instruction ("a focused single-panel
self-Council suffices"), worktree-isolated. Charter: item 3 — did any test flip behavior
silently, and is any fixture passing only because the contract was inert?

## Verdict: SHIP (single panel), one advisory closed

The panelist reviewed the version-bump commit `11dd2d5` and returned **SHIP**:

- **No silent flips.** The render-contract tests pin `skill_version` explicitly (module
  constant `SKILL_VERSION = "1.6.0"`), so they always exercised the active path — the bump
  does not change their behavior. The gate-integration trees (`minimal_zero_bug_tree`,
  default `1.4.4`) write their own in-fixture `SKILL.md` + `PROGRESS.md` and run via
  subprocess against their own tree, so they are immune to the real-repo bump; the render
  contract still correctly skips for them.
- **Fixtures not vacuous.** The clean-document fixture passes all checks with the real,
  unmutated contract code, and ~10 `test_c*_fires` / `test_mp*_fires` tests assert `fails
  >= 1` on deliberately broken fixtures — the contract genuinely FAILs bad input and
  PASSes clean input, not "inert on everything."
- **004 fail-closed still fires at 1.6.0.** Mutation bite: neutering the `if product_reqs:`
  FAIL turned the bold-marker tests RED with the version gate live; restored via
  `shutil.copy2`, `__pycache__` purged, clean.
- **Version consistency.** `test_version_single_source_057` passes — all derived surfaces
  (README, package.json, pyproject.toml, plugin.json, `cli.__version__`,
  `benchmark_lib.RELEASE_VERSION`, the staged `_bundle/SKILL.md`) equal the 1.6.0
  frontmatter.
- **Independently verified the real production activation path** (ambient SKILL.md →
  `detect_skill_version` → `check_render_contract`, with no `skill_version` override): the
  contract fired and FAILed correctly on a bold-marker document. This is the path the
  instruction exists to turn on, and it works.

## The advisory the panelist named — closed in `264d250`

The panelist's one substantive observation: *no automated test* pins the real
ambient-SKILL.md → activation path; every render-contract test pins `skill_version`
explicitly, so a future regression stamping the shipped SKILL.md below the v1.6.0 floor
(silently turning Feature C off on every run — the exact state this instruction ends)
would pass the whole suite. The panelist verified the path manually but called out the
missing regression guard. Closed by adding `RenderContractShippedVersionActivatesTests`,
which reads the real repo-root SKILL.md and asserts the shipped version clears the
render-contract floor (robust to future bumps; fails on a below-floor regression).

## Findings surfaced (out of the worker's fix scope)

1. **`quality_playbook_cli.__version__` is bundle-first, not purely runtime-derived.** It
   reads the gitignored staged `_bundle/SKILL.md` before the repo-root SKILL.md, so a
   stale bundle can transiently shadow the canonical version (the CLI reported 1.5.10
   until the suite regenerated the bundle). The 057 guard catches drift in CI, but the
   lookup order is a real risk. Recommend reordering the candidates or hard-erroring on a
   bundle-vs-source mismatch. (The panelist independently reached the same observation.)
2. **A build/stage test mutates tracked repo files and the bundle as a side effect** during
   the suite run — correct end state, but a test-hygiene smell.

Both are pre-existing and orthogonal to the version-literal bump; flagged for the
orchestrator.

## State at filing

Full suite **2593 tests, 0 failures (14 skipped)**, Python 3.14.6. Mutation bite restored
via `shutil.copy2`, `__pycache__` purged, worktree clean. Cleared to file.
