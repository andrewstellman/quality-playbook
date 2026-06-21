# Instruction 059 — Focused Adversarial Self-Council Review

Reviewer role: single FOCUSED adversarial code reviewer (not implementer, not orchestrator).
Branch: 1.5.10. Python 3.14.6. Change: 4 files (`_purpose.py`, `SKILL.md`,
`test_qpb_validate_in_closure_090k.py`, new `test_banner_version_059.py`) plus a
`.gitignore` hygiene line (5 files in `git diff --stat`; the spec named the 4 substantive ones).

## 1. CORRECTNESS — PASS

- **Version carried everywhere the banner is printed.** `print_attribution_banner()`
  (`_purpose.py:406`) now writes `attribution_banner_text()` instead of the static
  `BANNER_TEXT`. All three print paths funnel through `print_attribution_banner`:
  - run_playbook start/end and CLI no-args (`print_command_intro` → `print_attribution_banner`,
    `_purpose.py:319`) and `--help` (`print_help_banner`, `_purpose.py:350`);
  - install-end: `install_skill._print_banner` (`install_skill.py:725-734`) is a thin
    delegator to `_PURPOSE.print_attribution_banner`. Verified the canonical
    `install_skill.py` still routes the printed banner through `_purpose`, so install-end
    now carries the version too. (`install_skill._BANNER_TEXT` at :722 is the versionless
    skeleton, used only by structural pins — see §3.)
- **Read at call time, not frozen.** `attribution_banner_text()` (`_purpose.py:360`) calls
  `get_version()` (`:166`, the canonical SKILL.md-frontmatter reader) on every invocation;
  no module-level capture. A stale install therefore renders ITS OWN version — exactly the
  tripwire instruction 059 wants.
- **Width ≤ 80.** Title line `  Quality Playbook v1.5.10 -- by Andrew Stellman` = 48 chars.
  Box rules unchanged at 80.
- **stderr (089k) preserved.** Default `stream=sys.stderr` unchanged at `:404-405`; the
  rendering change is purely in the text builder. `test_print_attribution_banner_emits_version_on_stderr`
  pins the version on the default stderr stream.
- Graceful stream-error try/except unchanged.

## 2. SPEC COMPLIANCE / DESIGN-CHOICE JUDGMENT — ACCEPTABLE (no FIX-REQUIRED)

The key judgment call is runtime-derivation with a versionless fenced block + prose that
directs version insertion. I scrutinized whether keeping the FENCED block versionless
(against instruction step 2's "reproduce byte-for-byte … output now carries the version")
is a real gap. Verdict: acceptable, and in fact the correct read.

- Instruction step 1 explicitly authorizes runtime rendering from `get_version()` and says
  "do NOT hardcode the version." A literal `v1.5.10` in the fenced block would BE a second
  hardcoded literal — directly contrary to step 1 and to 057 single-source. It would also
  force build-stamping the SKILL.md block and rewriting the 057 "appears exactly once" guard,
  the 089j AGENTS.md byte-for-byte pin, and the 090k fence pin. The implementer correctly
  avoided that blast radius.
- Step 2's "byte-for-byte" requirement is satisfied by keeping the fenced block the canonical
  versionless skeleton and adding **explicit prose** that the agent renders `vX.Y.Z` onto the
  title line "exactly as `print_attribution_banner()` emits it." The SKILL.md change removes
  "or add a version number," keeps the anti-condensation guard, adds the title-line directive,
  AND adds a parenthetical reminder right under the fence (`SKILL.md:58`). The agent does NOT
  lack a copyable reference: it has the full 8-line block plus an unambiguous one-line edit
  instruction. The omission-risk is low and is the same shape as every other "render X from
  frontmatter" directive already in the skill.
- Step 3 wanted version-aware pins "derived from get_version(), not hardcoded." The new
  `test_banner_version_059.py` does exactly this (`test_pin_is_dynamic_not_static`,
  `test_banner_contains_version` both compose the expected string from `get_version()`).
  The skeleton pins (089j AGENTS.md, 090k fence) stay versionless — which is consistent,
  because they pin the versionless skeleton (`BANNER_TEXT` / the SKILL.md fenced block),
  not the rendered output. The implementer's `test_skeleton_banner_text_stays_versionless`
  explicitly documents and guards this split. Internally coherent.

Note on instruction step 3's named files: it listed `test_full_banner_on_clis_090a.py` and
`test_scripts_self_describing_089x.py` as candidates to make version-aware. I verified those
do NOT byte-for-byte pin the *rendered* banner against the versionless skeleton — 090a uses
substring/`assertIn` checks and 089j's printed-banner checks are substring-based — so they did
NOT need changes and did NOT regress. The only pin that needed updating was the SKILL.md-prose
pin in 090k, which the diff updates correctly. Not touching 090a/089x is correct, not a miss.

## 3. REGRESSION / SCOPE — PASS

- **057 single-source preserved.** Literal `1.5.10` appears in SKILL.md exactly once, in
  frontmatter (`SKILL.md:6`). The new prose uses `vX.Y.Z` placeholders (2 occurrences),
  not literals. `test_version_single_source_057` passes.
- **090k pin update correct.** Old clause `"do NOT condense, abbreviate, summarize, reformat,
  or add a version number"` is gone; new assertions present: positive `"do NOT condense,
  abbreviate, summarize, or reformat"`, negative `assertNotIn("or add a version number")`,
  and positive `assertIn("include the running skill version")`. Matches the actual SKILL.md
  text. The existing fenced-block extraction pin (`:225`) still expects the VERSIONLESS
  author line `Quality Playbook -- by Andrew Stellman`, which is correct because the fenced
  block stays versionless.
- **089j AGENTS.md byte-for-byte pin holds** (`test_install_skill_banner_089j.py:540-541`):
  it compares AGENTS.md against `install_skill._BANNER_TEXT` (versionless skeleton). Because
  `BANNER_TEXT` is deliberately left versionless, this pin does not break. Confirmed green.
- **SKILL.md token ceiling not breached.** `test_skill_md_size` (3 tests) OK.
- No unrelated drift; `.gitignore` change is a hygiene line for integration-regression run
  artifacts (out of strict scope but harmless and self-documented).

## 4. TEST SUFFICIENCY / HONESTY — PASS (mutation independently verified)

- **Suite of 5 modules green.** `test_qpb_validate_in_closure_090k`,
  `test_full_banner_on_clis_090a`, `test_install_skill_banner_089j`,
  `test_version_single_source_057`, `test_banner_version_059` → `Ran 31 tests … OK`.
- **Mutation bite independently reproduced.** I reverted the title line in
  `attribution_banner_text()` to `f"  {BANNER_NAME} -- by {BANNER_AUTHOR}\n"` (via Edit, not
  git checkout), purged `__pycache__`, and ran `test_banner_version_059`:
  `FAILED (failures=3)` — `test_banner_contains_version`, `test_pin_is_dynamic_not_static`,
  and `test_print_attribution_banner_emits_version_on_stderr` all FAILED with
  `'v1.5.10' not found in …`. The test genuinely bites the load-bearing behavior.
- **Restored exactly** via Edit, purged `__pycache__`, re-ran all 5 modules → 31 tests OK.
  `git diff --stat` matches the original 4-substantive-file change (57 insertions, 4 deletions).
  Tree is restored.
- Implementer's claim (suite green, only the 5 known README/doc-drift baseline failures) is
  plausible and consistent with the focused modules I ran.

## NITs (non-blocking)

- `attribution_banner_text()` duplicates the BANNER skeleton structure inline rather than
  deriving from `BANNER_TEXT` (e.g. a single title-line substitution). The two skeletons
  (`BANNER_TEXT` at :92 and the builder at :380) could drift if a future taglineor license
  edit touches only one. A guard test asserting the two agree modulo the version would be
  belt-and-suspenders. Not blocking — `test_skeleton_banner_text_stays_versionless` partially
  covers this, and any structural drift would fail the 089j/090k pins.
- The SKILL.md parenthetical at `:58` slightly overlaps the title-line directive at `:44`;
  mild redundancy, arguably good for an agent reader.

## Conclusion

Correct, spec-compliant under the right reading of the runtime-derived design choice, no
regression, version-single-sourced (057), pins consistent, and the new test mutation-bites
(independently verified) with a clean restore.

VERDICT: SHIP
