# Panelist C — Awesome-copilot submission correctness (QPB instruction 202)

Reviewer: Panelist C (Opus 4.7)
Repo: `/Users/andrewstellman/Documents/QPB/` @ branch `1.5.8`, HEAD `d2fd31f` (unpushed)
Files under review:
- `/Users/andrewstellman/Documents/QPB/bin/submit_awesome_copilot.py`
- `/Users/andrewstellman/Documents/QPB/ai_context/DEVELOPMENT_PROCESS.md` (new "Publish scripts" section, lines 220-245)
- `/Users/andrewstellman/Documents/QPB/bin/tests/test_submit_awesome_copilot.py`
- Generated packet at `/tmp/qpb_packet/` (after running `python3 bin/submit_awesome_copilot.py --dest /tmp/qpb_packet`)

## 1. Charter recap

Verify the QPB awesome-copilot submission workflow — the script that generates a submission packet (trimmed `SKILL.md` + `PR_BODY.md` + `MANUAL_STEPS.md`) and the operator-side fork-and-PR instructions — is actually correct against the real `github/awesome-copilot` registry's submission conventions.

## 2. Registry verification (independent gh queries)

The build's claim ("`github/awesome-copilot`, 34k stars, official GitHub org, accepts community skills under `skills/<skill-name>/SKILL.md`") is **VERIFIED**.

### Commands run

```bash
gh search repos awesome-copilot --json fullName,description,stargazersCount --limit 5
```

Top result:

```json
{
  "fullName": "github/awesome-copilot",
  "description": "Community-contributed instructions, agents, skills, and configurations to help you make the most of GitHub Copilot.",
  "stargazersCount": 34556
}
```

```bash
gh repo view github/awesome-copilot --json description,stargazerCount,defaultBranchRef,pullRequestTemplates,licenseInfo
```

- Default branch: `main`
- License: MIT
- Star count: 34,556 (matches script's `34k stars` claim)
- Description explicitly mentions "skills" as a supported contribution type

```bash
gh api repos/github/awesome-copilot/contents
```

Confirmed top-level directories: `agents/`, `cookbook/`, `extensions/`, `hooks/`, `instructions/`, `plugins/`, `skills/`, `workflows/`. The `skills/` directory exists and is the right home.

```bash
gh api repos/github/awesome-copilot/contents/skills | jq '.[].name' | wc -l
```

Skills directory has ~30+ entries (e.g., `architecture-blueprint-generator`, `ai-prompt-engineering-safety-review`, `acquire-codebase-knowledge`, etc.) — submitting a new `quality-playbook` folder fits the existing pattern.

```bash
gh api repos/github/awesome-copilot/contents/CONTRIBUTING.md --jq '.content' | base64 -d > /tmp/awesome_contributing.md
```

CONTRIBUTING.md decoded (23,866 bytes, 443 lines). Key submission rules below.

```bash
gh api repos/github/awesome-copilot/contents/eng/validate-skills.mjs
gh api repos/github/awesome-copilot/contents/eng/constants.mjs
gh api repos/github/awesome-copilot/contents/eng/yaml-parser.mjs
gh api repos/github/awesome-copilot/contents/package.json
```

Validator pulled. Required SKILL.md frontmatter fields are **only**:
- `name` — string, regex `/^[a-z0-9-]+$/`, length 1-64, MUST equal folder name
- `description` — string, length 10-1024

Extra YAML keys (`license`, `compatibility`, `metadata`) are silently tolerated by `vfile-matter`; the validator only enforces the two fields above plus a 5MB per-asset cap.

`package.json` scripts confirm:
- `npm start` = `npm run build`
- `npm run build` = `node ./eng/update-readme.mjs && node ./eng/generate-marketplace.mjs`
- `npm run skill:validate` = `node ./eng/validate-skills.mjs`

### Sample skill SKILL.md (for comparison)

`skills/architecture-blueprint-generator/SKILL.md`:

```yaml
---
name: architecture-blueprint-generator
description: 'Comprehensive project architecture blueprint generator that analyzes codebases...'
---
```

`skills/ai-prompt-engineering-safety-review/SKILL.md`:

```yaml
---
name: ai-prompt-engineering-safety-review
description: 'Comprehensive AI prompt engineering safety review...'
---
```

**Existing skills use only `name` + `description` in frontmatter.** No `license`, `compatibility`, or `metadata` blocks.

## 3. Submission-format match: side-by-side

| Aspect | Registry expects | Script generates | Verdict |
|--------|------------------|------------------|---------|
| Folder location | `skills/<skill-name>/SKILL.md` | `skills/quality-playbook/SKILL.md` | OK |
| `name` field | lowercase a-z0-9-, ≤64 chars, == folder name | `quality-playbook` | OK |
| `description` field | 10-1024 chars | 530 chars | OK |
| Extra YAML keys | tolerated (not validated) | `license`, `compatibility`, `metadata.{version,author,upstream}` | Tolerated; non-standard (no existing skill uses them) |
| Bundled assets | ≤5MB each | None bundled | OK |
| PR target branch | **`staged` (REQUIRED, repeated 3x in CONTRIBUTING.md with explicit warning)** | **`upstream/main`** in MANUAL_STEPS.md Step 2 | **MISMATCH** |
| Pre-submit script | `npm start` (updates README.md AND marketplace.json) | `npm run skill:validate && npm run build` | Partial — works but non-canonical |
| Files to commit | `skills/<name>/SKILL.md` + any README updates from `npm start` | `skills/quality-playbook/ docs/README.skills.md` | **`docs/README.skills.md` does not exist in the registry** |
| PR title fast-track | If submitting as AI agent: append `🤖🤖🤖` to PR title for fast-track merge (per CONTRIBUTING) | Not mentioned in MANUAL_STEPS.md | Minor — operator may want to know |
| PR body | Pull request template has its own checklist (`I am targeting the staged branch`, `I have run npm start`, etc.) | Custom checklist that does not match template | **MISMATCH** |

CONTRIBUTING.md says (verbatim):

> **Create a new branch** for your contribution from the `staged` branch. **This is critical** — ensure that a branch is created from `staged`, not `main`. Branches created from `main` will cause merge conflicts and delays in processing your contribution, **or they may be outright rejected.**

The PR template (fetched via `gh repo view ... --json pullRequestTemplates`) ends with:

> - [ ] I am targeting the `staged` branch for this pull request.

This is the load-bearing failure mode: an operator who follows MANUAL_STEPS.md literally branches off `upstream/main`, opens a PR against `main`, and the PR may be **outright rejected**.

## 4. PR_BODY.md generator review

`bin/submit_awesome_copilot.py` lines 249-303 (`generate_pr_body`).

**Strengths:**
- Mentions version, package name, pip/npm install commands — all factually correct.
- Links back to canonical QPB repo (line 273-274 of the script).
- Verification block (line 281-285) is concrete — `pip install quality-playbook==<version>; qpb install --into ./test-target-repo`.

**Weaknesses:**
- The checklist (line 289-296 of the script) is **completely different from the registry's PR template**. The registry's checklist (fetched from `pullRequestTemplates`) is:
  - "I have read and followed the CONTRIBUTING.md guidelines"
  - "I have read and followed the Guidance for submissions involving paid services"
  - "My contribution adds a new instruction, prompt, agent, skill, or workflow file"
  - "The file follows the required naming convention"
  - "I have tested my instructions, prompt, agent, skill, or workflow with GitHub Copilot"
  - **"I have run `npm start` and verified that `README.md` is up to date"**
  - **"I am targeting the `staged` branch for this pull request"**
  - Type-of-contribution checkboxes including "New skill file"

  When an operator uses `--body-file PR_BODY.md`, the template is **replaced**, not merged — so the maintainer will not see the registry's required checklist confirmations.

- Line 295-296 of the script says `[ ] npm run skill:validate run by maintainer...` — but `skill:validate` is meant to be run by the **submitter** before opening the PR, not the maintainer. CONTRIBUTING.md (line 138) says "Validate and update docs: Run `npm run skill:validate` and then `npm run build`".

- No mention that the submitter is an AI agent (the `🤖🤖🤖` fast-track marker per CONTRIBUTING.md line 408) — this is optional, but the build agent is producing the PR body, so the title should probably contain the marker.

## 5. MANUAL_STEPS.md operator workflow review

`bin/submit_awesome_copilot.py` lines 306-389 (`generate_manual_steps`).

**Step-by-step audit against CONTRIBUTING.md:**

| Script step | What CONTRIBUTING.md says | Verdict |
|-------------|---------------------------|---------|
| Step 1: `gh repo fork github/awesome-copilot --clone=true; npm install` | "Fork this repository" | OK |
| Step 2: `git fetch upstream main; git checkout -b add-quality-playbook-1.5.8 upstream/main` | **"Create a new branch from the `staged` branch... NOT `main`. Branches created from `main`... may be outright rejected"** | **WRONG** — must be `upstream/staged` |
| Step 3: `mkdir -p skills/quality-playbook; cp <packet>/skills/quality-playbook/SKILL.md ...` | "Add your skill in `skills/<name>/SKILL.md`" | OK |
| Step 4: `npm run skill:validate; npm run build` | Submission step 4: "**Run the update script: `npm start`** ... A GitHub Actions workflow will verify that this step was performed correctly" | Partial. `npm start` runs `npm run build` so the README update will happen, but the canonical command is `npm start`. CI explicitly checks that README.md is up to date — the operator's command should match. |
| Step 5: `git add skills/quality-playbook/ docs/README.skills.md` | `npm start` modifies `README.md` (top-level), not `docs/README.skills.md` | **WRONG path** — `docs/README.skills.md` does not exist in the registry. The actual modified file is `README.md`. Operator running this `git add` literally will get `fatal: pathspec 'docs/README.skills.md' did not match any files` and may also silently miss the real README.md change. |
| Step 5: `git commit -m "Add quality-playbook skill v1.5.8"` | No commit-message convention enforced | OK |
| Step 5: `git push -u origin add-quality-playbook-1.5.8` | OK | OK |
| Step 6: `gh pr create --repo github/awesome-copilot --title "Add quality-playbook skill v1.5.8" --body-file <packet>/PR_BODY.md` | Targets default branch (`main`) unless `--base staged` is specified | **WRONG** — `gh pr create --repo github/awesome-copilot` will default to `main`. Operator MUST add `--base staged`. |

**Would a fresh operator be able to follow MANUAL_STEPS.md?** Yes — and that's the problem. The instructions are clear and confident but produce a PR against the wrong branch with a missing/wrong file pointer in the `git add`. The "wait for review" outcome at Step 7 may be "your PR was closed; please target `staged`."

## 6. Generated packet inspection

Ran `python3 bin/submit_awesome_copilot.py --dest /tmp/qpb_packet`. All files generated:

```
/tmp/qpb_packet/
├── MANUAL_STEPS.md           (2533 B)
├── PR_BODY.md                (2305 B)
├── submission.json           (391 B)
└── skills/
    └── quality-playbook/
        └── SKILL.md          (3500 B)
```

**SKILL.md content check:**
- Frontmatter: `name: quality-playbook` ✓, `description` ~530 chars ✓ (under 1024 cap), folder name matches `name` field ✓.
- Body: well-structured (Installation, What it does, License, Canonical source).
- License declared as `Apache-2.0` in frontmatter and body. **Note:** the awesome-copilot registry itself is MIT and the PR template says "I confirm that my contribution... will be licensed under the MIT License." Since QPB ships Apache-2.0, there is potential friction here — the body explicitly says "Apache 2.0", which conflicts with the registry's MIT-only assumption. This may surface as a maintainer question. Minor, not blocking.

**submission.json:** OK — machine-readable, generated_at timestamp, correct version (1.5.8).

**Pre-flight version-parity check:** correctly halts on mismatch (verified by test `test_main_halts_on_version_mismatch`). Output shows `Version parity OK at 1.5.8.`

**Snapshot tests:**
```bash
python3 -m pytest bin/tests/test_submit_awesome_copilot.py --no-header
```
Result: `Ran 19 tests in 0.017s — OK`. All 19 tests pass.

## 7. Per-finding narrative

### FIX-REQUIRED-1: Branch target is `staged`, not `main`

`MANUAL_STEPS.md` Step 2 says `git checkout -b add-quality-playbook-1.5.8 upstream/main`. CONTRIBUTING.md (line 393) says this is "critical" — branches from `main` "may be outright rejected." Step 6's `gh pr create` does not pass `--base staged` either, so the PR will target the fork's default base. Both must change:

- Step 2: `git fetch upstream staged && git checkout -b add-quality-playbook-1.5.8 upstream/staged`
- Step 6: `gh pr create --repo github/awesome-copilot --base staged --title ... --body-file ...`

This is the dominant correctness issue — the script can't be SHIP without it.

### FIX-REQUIRED-2: `docs/README.skills.md` does not exist

`MANUAL_STEPS.md` Step 5 says `git add skills/quality-playbook/ docs/README.skills.md`. The registry's `npm run build` (via `update-readme.mjs`) updates the top-level `README.md`, not `docs/README.skills.md`. An operator running this literally gets a `pathspec did not match` error and may then commit without the README update — failing the CI workflow check.

Fix: replace with `git add skills/quality-playbook/ README.md` (or simply `git add -A` after `npm start`).

### FIX-REQUIRED-3: PR_BODY.md checklist does not match registry template

The registry's PR template (verified via `gh repo view ... --json pullRequestTemplates`) has specific checkboxes including:
- "I have read and followed the CONTRIBUTING.md guidelines"
- "I have run `npm start` and verified that `README.md` is up to date"
- "I am targeting the `staged` branch for this pull request"

The script's `generate_pr_body` (lines 289-296) emits a different, smaller checklist that omits all of these. When the operator passes `--body-file PR_BODY.md` to `gh pr create`, the template is replaced — so the maintainer will not see these load-bearing confirmations checked.

Fix: regenerate the PR_BODY.md to include the registry's exact checklist (or at least the load-bearing items: CONTRIBUTING.md read, npm start run, staged branch targeted, content type = skill).

### CONCERN-1: Canonical pre-submit command is `npm start`, not `npm run build`

CONTRIBUTING.md submission step 4 says "Run the update script: `npm start`". A GitHub Actions workflow verifies it was run. The script's MANUAL_STEPS.md uses `npm run skill:validate && npm run build` instead. `npm start` ≡ `npm run build` (per the registry's `package.json`), so this is functionally equivalent — but the CI check is looking for the README to be up to date, which `npm run build` does accomplish. The substantive risk is documentation drift: if the registry adds steps to `npm start` later (e.g., schema validation), QPB's instructions go stale. Recommend matching the canonical command exactly.

### CONCERN-2: Apache-2.0 license declaration conflicts with registry's MIT licensing assumption

The PR template ends with "I confirm that my contribution... will be licensed under the MIT License." The trimmed SKILL.md frontmatter and body both declare `Apache-2.0`. Existing skills in the registry do not appear to declare a license in their frontmatter at all — they implicitly inherit the registry's MIT. This is a meaningful licensing question; recommend either (a) explicitly contributing the SKILL.md under MIT (separate from QPB's Apache 2.0 toolkit) so the registry can accept it cleanly, (b) removing the `license:` frontmatter line and letting the registry's umbrella MIT apply to just the SKILL.md, or (c) coordinating with awesome-copilot maintainers about Apache-licensed skill submissions. **This is a meta-decision the operator needs to make explicit, not a bug in the script — but the script should flag the question to the operator rather than silently emitting Apache-2.0.**

## 8. NITs

- NIT-1: SKILL.md body line "Cross-platform. Requires Python 3.8+ and git" — pyproject.toml's `requires-python` may be different from 3.8; verify the published package's actual minimum Python. (Not blocking, just consistency.)
- NIT-2: PR_BODY.md says `npx quality-playbook` — confirm the npm package actually has a `bin` entry making this work end-to-end. (Out of scope for this charter, but mentioned in the PR_BODY.)
- NIT-3: The `metadata` block in the trimmed SKILL.md frontmatter (`version`, `author`, `upstream`) is harmless (validator ignores it) but non-standard among existing skills. Could be simplified to just `name` + `description` + an optional `tags` (which `update-readme.mjs` might pick up for the README table).
- NIT-4: MANUAL_STEPS.md does not mention the `🤖🤖🤖` AI-agent fast-track marker (CONTRIBUTING.md line 407-408). Optional, but the AI is generating the PR, so it qualifies.
- NIT-5: `MANUAL_STEPS.md` step 4 says "Do NOT edit any of the generated README tables by hand" — true, but the file actually is the top-level `README.md`, not the `docs/README.skills.md` referenced in Step 5. Internal inconsistency.

## 9. Final verdict

The script's overall architecture — generate a packet, defer the actual fork/validate/PR to a documented operator workflow, version-parity-check before generating, snapshot-test the generators — is sound. The 19 tests pass. The packet content is well-structured. The registry target (`github/awesome-copilot`) is correctly identified and the skill folder layout matches the registry's expected `skills/<name>/SKILL.md` convention.

However, the operator-side workflow generated by the script has **three concrete correctness failures** that would cause a fresh operator (or the build agent's own future self) to open a PR that gets rejected or auto-failed by CI:

1. PR is branched from `main` instead of the required `staged` branch (CONTRIBUTING.md explicitly says PRs from `main` "may be outright rejected").
2. `git add docs/README.skills.md` references a non-existent file — the actual file modified by `npm run build` is the top-level `README.md`.
3. PR_BODY.md ships a custom checklist that omits the registry's required confirmations (read CONTRIBUTING, ran `npm start`, targeting `staged`).

These are not abstract concerns — I verified each against the live registry contents (`gh api repos/github/awesome-copilot/...`) and the PR template (`gh repo view ... --json pullRequestTemplates`). The script's commit message claims "researched, not assumed," but the `staged`-branch convention is the load-bearing detail and was missed. Net: the registry was correctly identified but the submission ritual was not fully extracted from CONTRIBUTING.md.

Recommend fixing all three FIX-REQUIRED items, addressing CONCERN-1 (`npm start`) for forward-compatibility, and at least flagging CONCERN-2 (Apache vs MIT) to the operator. After those, the packet should ship clean against the real registry.

```
VERDICT: FIX-REQUIRED
```
