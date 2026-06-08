# Quality Playbook v1.5.8 — Release Close-Out Checklist

*Created 2026-06-08 after the 208 repo restructure surfaced that the release close-out checklist should explicitly track post-restructure verification of all install channels and documentation, not just rely on the generic close-out sequence in `ai_context/DEVELOPMENT_PROCESS.md`.*

*Authored under explicit operator carve-out from the default "QPB source files are propose-don't-edit" rule.*

---

## Why this checklist exists

v1.5.8 close-out has been longer and more complex than typical:

- 10 instructions filed during close-out (191, 192, 197-209), each landing real source changes after the v1.5.8 tag was placed
- Instruction 208 restructured the repo to a plugin-native layout (`skills/quality-playbook/` instead of root-level SKILL.md + supporting files), and instruction 209 completed the restructure to the **standard self-hosted marketplace layout** (`.claude-plugin/marketplace.json` at root + plugin content under `plugins/quality-playbook/`). The 208 hybrid empirically failed Claude Code's `--plugin-dir` load test; 209 fixes the layout so both `--plugin-dir` and `/plugin marketplace add` work.
- Three install channels (pip, npm, Claude Code plugin marketplace) all depend on the file layout being correct
- Three sets of documentation (adopter-facing README, AI-assistant TOOLKIT, maintainer DEVELOPMENT_CONTEXT) all reference file paths that changed

The generic close-out sequence in `DEVELOPMENT_PROCESS.md` § Release close-out covers the **shape** of the work (push branch → publishes → docs → merge) but doesn't enforce the **verification** that each affected channel and document is consistent with the post-restructure state. This checklist fills that gap for v1.5.8 specifically.

---

## Status legend

- ✅ Done and verified
- 🔄 In progress
- ⏳ Pending
- ❌ Blocked / needs decision

---

## A. Source restructure verification (post-instructions 208 + 209)

Instruction 208 moved skill-bundled files from the repo root into `skills/quality-playbook/`; instruction 209 then moved them again into `plugins/quality-playbook/skills/quality-playbook/` (standard self-hosted marketplace layout). Each install path that consumes those files needs explicit verification:

| # | Item | Status | Notes |
|---|------|--------|-------|
| A.1 | Review instruction 208 worker output (panelist files + diff) | ✅ | Reviewed 2026-06-08. Panel: A FIX-REQUIRED (5 test files hardcoded old `quality_gate` path) → RESOLVED; B SHIP unconditional; C CONCERN (10 broken README links) → RESOLVED; C orientation-doc bare-prose drift (~40 mentions) DEFERRED to TOOLKIT_TEST_PROTOCOL per the orientation-doc release-gate rule. Synthesis recommends SHIP. |
| A.2 | Verify `bin/install_skill.py::_bundle_files()` enumerates the same files as before, reading from new source paths | ✅ | Empirical: `_bundle_files()` resolves all 57 source paths under `skills/quality-playbook/...`. Install into temp target produces exactly 57 files. |
| A.3 | `bin/build_channel_package.py` source paths updated to read from `skills/quality-playbook/<...>` | ✅ | Empirical: pip dry-run's build step succeeds; staged bundle has the flat `_bundle/SKILL.md`, `_bundle/bin/...` layout pre-208 had. |
| A.4 | `bin/submit_awesome_copilot.py` source path for SKILL.md frontmatter read updated | ✅ | Per Panelist A's audit; verify empirically in F.2 below |
| A.5 | Other `bin/*.py` defensive sweep for hardcoded root paths | ✅ | Per Panelist A's audit. 5 test files were the only hits; all updated. |
| A.6 | `bin/tests/test_plugin_layout_208.py` exists and passes | ✅ | 15 tests, all pass. Mutation verified twice (worker + Panelist C independent). |
| A.7 | `bin/install_skill.py` shim at the historical path delegates correctly | ✅ | Empirical: `python3 -m bin.install_skill --into <target> --ai-tool claude --no-smoke` produces 57 files at target. Shim docstring explains the hyphen-in-module-name workaround. |

## B. pip channel verification

| # | Item | Status | Notes |
|---|------|--------|-------|
| B.1 | `python3 bin/publish_pip.py --dry-run` passes all 8 preflights | ✅ | Verified 2026-06-08 in sandbox: all 8 preflights pass; build produces wheel + sdist; forbidden-contents scan clean. |
| B.2 | Bundle contains expected files at expected internal paths | ✅ | Per Panelist B's audit: wheel `_bundle/SKILL.md` + `_bundle/bin/citation_verifier.py` at flat (pre-208) paths. |
| B.3 | Bundle file count matches pre-208 baseline | ✅ | 59 staged files (build_channel_package output); 57 installed into adopter targets (verified empirically). Matches pre-208. |
| B.4 | Clean venv install + entry-point smoke test | ⏳ | Sandbox can't fully exercise pip-from-wheel; operator should verify on their machine: `python3 -m venv /tmp/qpb-pip-test && source /tmp/qpb-pip-test/bin/activate && pip install dist/quality_playbook-1.5.8-py3-none-any.whl && quality-playbook --version` |
| B.5 | Clean venv install + skill install into target | ⏳ | Above + `quality-playbook install --into . --ai-tool claude --no-smoke` produces 57 files at `.claude/skills/quality-playbook/` |
| B.6 | Multi-target install test (all 8 AI tools) | ⏳ | Loop install across `claude`, `cursor`, `copilot`, `continue`, `codex`, `windsurf`, `cline`, `aider`; all 8 produce 57 files at correct path |

## C. npm channel verification

| # | Item | Status | Notes |
|---|------|--------|-------|
| C.1 | `python3 bin/publish_npm.py --dry-run` passes all 7 preflights | ⏳ | Including `npm pack --dry-run --json` JSON parse (fix from instruction 203) |
| C.2 | Tarball contents inspection — expected files at expected paths | ⏳ | `npm pack --dry-run --json \| grep _bundle/` checks |
| C.3 | Tarball file count matches pre-208 baseline | ⏳ | Expected: 64 files in tarball |
| C.4 | Fresh-directory npm install + npx smoke test | ⏳ | `mkdir /tmp/qpb-208-npm-test && cd /tmp/qpb-208-npm-test && npm install <local tarball> && npx quality-playbook --version` |
| C.5 | Fresh-directory + skill install into target | ⏳ | Above + `npx quality-playbook install --into . --ai-tool claude --no-smoke` produces 57 files |
| C.6 | Multi-target install test (all 8 AI tools) | ⏳ | Same loop as B.6 but via npx |

## D. Clone-based install verification

| # | Item | Status | Notes |
|---|------|--------|-------|
| D.1 | `git clone` of post-restructure repo + `python3 -m bin.install_skill --into <target> --ai-tool claude` | ⏳ | Verify clone-based install path still works after restructure |
| D.2 | Resulting target install matches pip/npm install (same file count, same paths) | ⏳ | The three install channels should produce identical adopter-side layouts |

## E. Claude Code plugin marketplace verification

| # | Item | Status | Notes |
|---|------|--------|-------|
| E.1 | `.claude-plugin/marketplace.json` is structurally valid (drops the invalid `skills` inline array + `strict: false`) | ⏳ | Per the plugin schema research from this session |
| E.2 | `.claude-plugin/plugin.json` exists and uses the 65/35 framing for the plugin description | ⏳ | |
| E.3 | `claude --plugin-dir ~/Documents/QPB` loads QPB as a plugin without errors | ⏳ | Local verification before marketplace publish |
| E.4 | `/plugin marketplace add github.com/andrewstellman/quality-playbook` adds the marketplace successfully | ⏳ | After push lands on origin/main (so the public URL resolves) |
| E.5 | `/plugin install quality-playbook` succeeds | ⏳ | |
| E.6 | Installed plugin's skill is discoverable in a test project | ⏳ | Ask Claude Code to run QPB on a small project; confirm activation |

## F. awesome-copilot channel verification

| # | Item | Status | Notes |
|---|------|--------|-------|
| F.1 | Close old anthropics/skills#659 PR (cleanup) | ⏳ | `gh pr close 659 --repo anthropics/skills --comment "..."` |
| F.2 | `bin/submit_awesome_copilot.py --dry-run` regenerates packet with correct content (post-207 trim template fixes) | ⏳ | Verify Python 3.10+, `quality-playbook install` (not `qpb install`), Phase 5 (Reconcile), Phase 6 (Verify), 5 support directories |
| F.3 | `bin/submit_awesome_copilot.py --submit` succeeds end-to-end (or operator runs MANUAL_STEPS.md flow) | ⏳ | The 206 automation handles fork + branch + push + PR |
| F.4 | PR opens at github/awesome-copilot targeting `staged` branch | ⏳ | |

## G. Documentation reference updates (post-208 restructure)

Every doc that references file paths needs to reflect the new layout. Inventory of files that may contain stale references:

| # | File | Status | Notes |
|---|------|--------|-------|
| G.1 | `README.md` — install path examples, repository structure section, "see SKILL.md" references | ⏳ | SKILL.md is now at `skills/quality-playbook/SKILL.md`; the `quality-playbook install --into . --ai-tool <tool>` invocations are unchanged but discoverability references shift |
| G.2 | `ai_context/TOOLKIT.md` — wait, this file MOVED into the skill per 208 (now at `skills/quality-playbook/ai_context/TOOLKIT.md`) | ⏳ | The repo-root copy was REMOVED. README's link to TOOLKIT.md needs to point at the new location |
| G.3 | `ai_context/DEVELOPMENT_CONTEXT.md` — Project structure section near the top diagrams the repo layout | ⏳ | Rewrite to reflect skills/quality-playbook/ structure |
| G.4 | `ai_context/DEVELOPMENT_PROCESS.md` — any path references inside | ⏳ | Likely small number of references; defensive sweep + update each |
| G.5 | `AGENTS.md` — entry-point doc for AI coding agents; if it references SKILL.md or bundled files | ⏳ | |
| G.6 | `CHANGELOG.md` — should note the structural change in the v1.5.8 entry | ⏳ | |
| G.7 | `docs/design/QPB_v1.5.9_Design.md` — references "current SKILL.md is 1256 lines" etc. — verify still accurate post-restructure | ⏳ | Source SKILL.md count shouldn't change with the file move (just location), but verify |
| G.8 | `docs/design/QPB_v1.5.9_Harness_Skill_Design.md` — references paths like `skills/quality-playbook-harness/` which now coexists naturally with `skills/quality-playbook/` | ⏳ | Should already be correctly aligned with the new layout (the v1.5.9 design assumed plugin-native already) |
| G.9 | Other `docs/design/QPB_v1.5.10_*.md` files — any path references | ⏳ | Small number; defensive sweep |
| G.10 | `ai_context/VERSION_HISTORY.md` — should note v1.5.8 includes the plugin-native restructure | ⏳ | If/when v1.5.8 ships fully |

## H. Methodology / process updates

| # | Item | Status | Notes |
|---|------|--------|-------|
| H.1 | Update `DEVELOPMENT_PROCESS.md` § Release close-out sequence to note that releases involving structural changes (file moves, new package layouts) require explicit verification of all install channels and a defensive sweep of all docs referencing affected paths | ⏳ | Lesson learned from v1.5.8 — the generic close-out sequence didn't enforce this and we caught it late |
| H.2 | Run TOOLKIT_TEST_PROTOCOL on orientation docs to address the ~40 bare-prose path references deferred from 208 Panelist C | ⏳ | Affected files: `AGENTS.md` + `ai_context/IMPROVEMENT_LOOP.md` + `ai_context/DEVELOPMENT_CONTEXT.md` + `ai_context/TOOLKIT.md` + `ai_context/DEVELOPMENT_PROCESS.md` + potentially `ai_context/CALIBRATION_PROTOCOL.md` + `ai_context/TOOLKIT_TEST_PROTOCOL.md` + README.md. Per the workspace CLAUDE.md release-gate rule: orientation docs are TOOLKIT_TEST_PROTOCOL-gated, NOT Council-gated. |
| H.3 | Move v1.5.8 tag to current HEAD if all of A-G + H.1 + H.2 pass | ⏳ | Tag is at `794ba1e`; should be at the post-208 + post-close-out HEAD before merging |

## I. Final close-out steps (after A-H complete)

| # | Item | Status | Notes |
|---|------|--------|-------|
| I.1 | Push all local commits to `origin/1.5.8` | ⏳ | `git push origin 1.5.8` |
| I.2 | Verify push landed | ⏳ | `git ls-remote origin refs/heads/1.5.8` matches local SHA |
| I.3 | Tag move + force-push (if decided in H.2) | ⏳ | `git tag -f v1.5.8 <sha> && git push --force origin refs/tags/v1.5.8` |
| I.4 | Merge `1.5.8` → `main` | ⏳ | `git checkout main && git pull && git merge --no-ff 1.5.8 -m "Merge 1.5.8 into main"` |
| I.5 | Push `main` to origin + verify | ⏳ | `git push origin main && git ls-remote origin refs/heads/main` |
| I.6 | Mark v1.5.8 closed; v1.5.9 work can begin (branch off main when ready) | ⏳ | |

---

## Open methodology question

Looking at v1.5.8's actual scope creep (191-208 = 17 instructions filed during close-out, many of which were responses to issues surfaced AFTER the original tag), there's a meta-question: when does close-out end and the next release begin? The methodology doc treats the release branch as open through close-out (correct), but doesn't define WHEN close-out is done if every new issue creates another instruction. Likely needs a "close-out scope freeze" rule — at some point you declare "no more instructions this release; remaining issues file as instructions for v1.5.9." v1.5.8 has informally hit that point already (208 is the last in-scope instruction); explicit codification could go into `DEVELOPMENT_PROCESS.md`.

*End of v1.5.8 close-out checklist. Track progress by updating status markers as items complete.*
