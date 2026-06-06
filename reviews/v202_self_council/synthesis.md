# Synthesis — 202 Worker self-Council (3-panelist)

**SHIP recommendation: YES** — after applying both panelists' FIX-REQUIRED items + Panelist B's NIT spot-check pre-push. A's clean-tree check fix lands here; C's awesome-copilot operator-workflow fixes land here.

## Panel summary

| Panelist | Charter | Initial verdict | After remediation |
|----------|---------|----------------|-------------------|
| A | Pre-flight checks completeness + correctness | **FIX-REQUIRED** (clean-tree halts every publish) | **SHIP** (redundant `--ignored` check removed) |
| B | Cross-platform correctness | **SHIP** | (unchanged; 4 non-blocking NITs noted) |
| C | Awesome-copilot submission correctness | **FIX-REQUIRED** (3 workflow errors) | **SHIP** (all 3 fixed; script + DEVELOPMENT_PROCESS.md updated) |

## Panelist A verdict — clean-tree check fix

A independently ran `publish_pip.check_clean_tree(repo_root)` against the real `/Users/andrewstellman/Documents/QPB` and confirmed `ok=False` — exactly the bug. Root cause: `.gitignore:99` lists `quality_playbook_cli/_bundle/` as a directory, so `git status --porcelain --ignored quality_playbook_cli/_bundle` reports `!! quality_playbook_cli/_bundle/` once the dir exists on disk. Files INSIDE the gitignored dir are collapsed under that single `!!` line; the second check could never catch "stale half-built bundle" as intended.

### Resolution

`bin/publish_pip.py:check_clean_tree` and `bin/publish_npm.py:check_clean_tree` simplified to just the first `git status --porcelain` (without `--ignored`). The first check already covers untracked + tracked-modified files. Docstring updated to explain why the bundle-specific check is intentionally absent: pre-flight check 5 (`build_channel_package` + `python -m build`) rebuilds the bundle deterministically — any stale state is overwritten before twine/npm publish sees the artifacts.

Verification: pytest exit=0 on all 91 publish tests; `publish_pip.py --dry-run` on the real QPB repo now correctly halts on the operator's actual uncommitted state (the intended behavior), not on the gitignored bundle.

### Panelist A's NITs (deferred to v0.x backlog)

- A-NIT1: `check_twine_auth` accepts URL+PASSWORD without USERNAME; twine actually requires a username/token. Minor defensive hardening.
- A-NIT2: `check_tag_exists` error message in npm omits the `git tag -a` hint that pip's includes — operator-visible asymmetry.
- A-NIT3: pip's `FORBIDDEN_SUFFIXES` includes `.env` (redundant with `FORBIDDEN_BASENAMES`).
- A-NIT4: `--skip-build` lacks the "NOT for production" warning that `--skip-tests` has.
- A-NIT5: `upload_*` uses literal `*` arg; consider enumerating files for Windows portability.
- A-CONCERN: No fixture combines `git init` + `_bundle/` gitignored — the gap that hid A's FIX-REQUIRED. Now that the offending code is gone, the gap doesn't cause active bugs, but worth a test in v0.x.

## Panelist B verdict — Cross-platform clean

B audited all 3 scripts for cross-platform discipline. All checks pass:

| Concern | Result |
|---|---|
| `shell=True` / `os.fork` / `os.system` | None present |
| POSIX-only modules (`signal`, `pwd`, `grp`, `fcntl`, `termios`) | None |
| Path operations | All `pathlib.Path`; no `os.path.join`; no hardcoded `/usr`, `/etc`, `/home` |
| Subprocess calls | List-form via `_run()` helper with explicit `encoding="utf-8"` |
| Log dir | `Path.home() / ".qpb" / "publish_logs"` with `mkdir(parents=True, exist_ok=True)` — works identically on Win/Mac/Linux |
| `npm` binary resolution | `shutil.which("npm")` — handles `npm.cmd` via PATHEXT on Windows |
| Bundle walker | Normalizes `\` to `/` for the forbidden-fragment scanner |
| `input()` | EOFError-wrapped — graceful CI behavior |
| awesome-copilot script | Zero subprocess calls; pure file generation with explicit UTF-8 |

91/91 publish tests pass on Darwin.

### Panelist B's NITs (deferred)

- B-NIT1: `/tmp/foo` appears as example path in `bin/submit_awesome_copilot.py:45` (docstring) and `:487` (banner `usage_hint`) — confusing on Windows.
- B-NIT2: Em-dash (U+2014) in printed messages could `UnicodeEncodeError` under legacy `PYTHONIOENCODING=cp1252` Windows shell. PEP 528 makes interactive consoles safe; log file is utf-8. (Methodology echo of the 185+189+190 cp1252 hazard triad — same class of bug but lower-risk here because the publish scripts only run during release.)
- B-NIT3: `str(dist / "*")` passed to twine relies on twine's internal `glob.glob`; defensive alternative would be `[str(p) for p in sorted(dist.glob("*"))]`.
- B-NIT4: `.replace("\\", "/")` could be `.as_posix()` (cleaner).

## Panelist C verdict — Awesome-copilot workflow fixed

C independently verified the registry (`github/awesome-copilot`, 34,556 stars) and fetched the live `CONTRIBUTING.md` via `gh api` to compare against MANUAL_STEPS.md + PR_BODY.md. Three load-bearing operator-workflow errors:

### C-FIX-REQUIRED-1 — RESOLVED PRE-PUSH

**Issue**: PRs must target `staged`, not `main`. CONTRIBUTING.md: "PRs targeting `main` may be outright rejected." MANUAL_STEPS.md branched from `upstream/main`; `gh pr create` lacked `--base staged`.

**Resolution**: `bin/submit_awesome_copilot.py` MANUAL_STEPS.md step 2 now branches from `upstream/staged`; step 6 `gh pr create` uses `--base staged`. Same updates mirrored in `ai_context/DEVELOPMENT_PROCESS.md` step 3 + 7.

### C-FIX-REQUIRED-2 — RESOLVED PRE-PUSH

**Issue**: `git add` referenced `docs/README.skills.md` which doesn't exist. The registry's `npm run build` (now `npm start`) updates the top-level `README.md`.

**Resolution**: MANUAL_STEPS.md step 5 `git add` updated to `skills/{SKILL_NAME}/ README.md` (top-level). Same in DEVELOPMENT_PROCESS.md.

### C-FIX-REQUIRED-3 — RESOLVED PRE-PUSH

**Issue**: Generated PR_BODY.md checklist was custom — missing the registry's required confirmations (read CONTRIBUTING, ran pre-submit command, targeting `staged`, contribution type).

**Resolution**: `bin/submit_awesome_copilot.py` `generate_pr_body()` checklist now includes:
- [x] Read CONTRIBUTING.md + followed submission guidelines
- [x] PR targets `staged` (not `main`)
- [x] Contribution type: new skill
- [x] SKILL.md frontmatter has name/description/license
- [x] `name` matches folder name
- [x] description is clear and non-empty
- [x] `npm start` run locally; both SKILL.md and regenerated top-level `README.md` staged
- [x] Canonical repo + license linked

### C-CONCERN-1 — RESOLVED PRE-PUSH

**Issue**: Canonical pre-submit command is `npm start`, not `npm run build`.

**Resolution**: MANUAL_STEPS.md step 4 now uses `npm start` (single command that runs `skill:validate` + regenerates `README.md`). Same in DEVELOPMENT_PROCESS.md step 5.

### C-CONCERN-2 — RESOLVED PRE-PUSH

**Issue**: Apache-2.0 license in QPB's SKILL.md frontmatter vs registry's MIT-only PR-template assertion; script silently emits Apache-2.0.

**Resolution**: PR_BODY.md gained a new "License note for maintainers" section explicitly flagging QPB's Apache-2.0 + asking maintainers to confirm before merging if the registry requires MIT.

## Key panel agreements

1. **Cross-platform discipline holds across all 3 scripts** (B verified).
2. **Pre-flight check architecture sound** post-A's fix (8 in pip, 7 in npm; each has positive + negative fixtures; --dry-run paths cover both happy + version-mismatch flows; defense-in-depth on bundle scanning).
3. **Awesome-copilot registry correctly identified** (`github/awesome-copilot`, 34k stars, official org) — C confirmed independently. The build agent's "researched, not assumed" claim was correct at the registry-identification level; missed the `staged`-branch convention from CONTRIBUTING.md. Now corrected.
4. **License-mismatch operator-visible flag** (Apache-2.0 vs MIT) is the right move — defer the licensing decision to QPB maintainers + awesome-copilot maintainers rather than silently emit a misaligned license string.
5. **91/91 publish tests pass.**

## v0.x polish backlog (deferred NITs)

From this Council:
- A-NIT1: twine USERNAME check defensive hardening
- A-NIT2: npm tag-creation hint asymmetry
- A-NIT3: redundant `.env` in FORBIDDEN_SUFFIXES
- A-NIT4: `--skip-build` "NOT for production" warning
- A-NIT5: literal `*` arg in upload calls
- A-CONCERN: add fixture combining `git init` + gitignored `_bundle/`
- B-NIT1: `/tmp/foo` example path in awesome-copilot docstring/banner
- B-NIT2: em-dash + Windows cp1252 stdout redirection (echoes 185+189+190 hazard triad)
- B-NIT3: `dist.glob("*")` instead of `str(dist / "*")` for twine
- B-NIT4: `.as_posix()` instead of `.replace("\\", "/")`

## Recommendation

**SHIP** — after applying A's clean-tree fix + C's three FIX-REQUIRED + two CONCERN items pre-push.

Push to origin/1.5.8 requires **operator confirmation** per instruction's "Done definition": "No commit pushed to origin without operator approval. Worker commits to the 1.5.8 branch but Andrew confirms before push."

The v1.5.8 ship sequence can now run reproducibly: each of pip / npm / awesome-copilot has a scripted form with pre-flight checks that fail loud and copy-pasteable operator workflows. The methodology generalization is captured in DEVELOPMENT_PROCESS.md: hand-typed publishes are the failure mode this avoids; the operator's job is to review the packet/file-list/confirmation prompt and type `y`, not to remember the command syntax.
