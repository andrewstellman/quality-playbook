# Panelist A — Automation correctness + step sequence (instruction 206)

STATUS: complete

## 1. Charter recap
Verify the awesome-copilot submission automation in `bin/submit_awesome_copilot.py` runs the right subprocesses in the right order, halts on error, validates `--dry-run` XOR `--submit` before any side-effect, uses valid `gh` flags, and embeds the version in the branch name. (Note: the build-agent notes mention "6 steps"; the driver actually wires 7 — steps 1-6 cover fork → upstream → branch → copy → npm start → commit/push, and step 7 opens the PR. The charter's ordering still maps cleanly: fork→branch→copy→npm start→commit→PR.)

## 2. Per-step audit table

| Step | Subprocess invocation(s) | Halt-on-error check | Line range |
| --- | --- | --- | --- |
| 1 verify/create fork | `gh auth status`; `gh repo fork github/awesome-copilot --clone=true --remote-name origin -- <fork_path>`; `npm install` | `auth.returncode != 0`, `r.returncode != 0`, `r2.returncode != 0` — each returns `(False, msg)` | 544-619 |
| 2 upstream + fetch | `git remote get-url upstream`; `git remote set-url upstream <https>` OR `git remote add upstream <https>`; `git fetch upstream staged` | `r2.returncode != 0`, `r3.returncode != 0`, `rf.returncode != 0` | 622-674 |
| 3 branch | `git rev-parse --verify refs/heads/<branch>`; `git rev-parse upstream/staged`; `git checkout <branch>` (reuse) or `git reset --hard upstream/staged` or `git checkout -b <branch> upstream/staged` (new) | `r_upstream`, `r_co`, `r_reset`, `r_new` returncodes all checked | 677-748 |
| 4 copy SKILL.md | `shutil.copy2` + SHA256 parity (no subprocess) | SHA256 mismatch → `(False, msg)` | 751-772 |
| 5 npm start | `npm start`; `git status --porcelain README.md` | `r.returncode != 0` halt; `r_st.returncode != 0` halt; empty status is WARNING, continues | 775-799 |
| 6 commit + push | `git diff --stat` (preview); `git add skills/<name>/ README.md`; `git commit -m "Add <name> skill v<version>"`; `git push -u origin <branch>` | each returncode checked; "nothing to commit" string is tolerated as idempotent | 802-856 |
| 7 open PR | `gh pr create --repo github/awesome-copilot --base staged --title <T> --body-file <packet>/PR_BODY.md` | `r.returncode != 0` halt with stderr tail | 859-910 |

## 3. Step-ordering verification
`run_submission` (lines 913-943) builds a `steps` list in literal order `[("1", step1), ("2", step2), ("3", step3), ("4", step4), ("5", step5), ("6", step6), ("7", step7)]` and iterates with a `for label, fn in steps:` loop. On any `ok=False` it logs `HALT` and returns `EX_SOFTWARE` (70). Sequence: fork (1) → upstream (2) → branch (3) → copy SKILL.md (4) → npm start (5) → commit/push (6) → PR (7). Matches charter's "fork before branch; branch before copy; copy before npm start; npm start before commit; commit before PR".

## 4. XOR-before-side-effects verification
In `main` (line 1040), argument-parse occurs at 1045; the XOR check is at lines 1049-1064 and returns `EX_USAGE` before any of: `check_version_parity` (1069), `read_skill_frontmatter` (1076), `dest.mkdir` (1085), `write_packet` (1087), and crucially `_open_log` (1104). Log file is NOT created when args are invalid. No subprocess is invoked. Verified.

## 5. gh CLI flag-spelling check
- `gh auth status` — canonical, no flags. OK.
- `gh repo fork github/awesome-copilot --clone=true --remote-name origin -- <fork_path>` — `--clone=true`, `--remote-name`, and the `--` passthrough to underlying `git clone` are all valid in modern gh (>=2.x). OK.
- `gh pr create --repo github/awesome-copilot --base staged --title <T> --body-file <path>` — all four flags valid. `--body-file` (not `--body-from-file`) is the correct spelling. OK.

## 6. Version-in-branch-name check
Driver line 923: `branch = f"add-{SKILL_NAME}-{version}"` where `SKILL_NAME = "quality-playbook"` (constant) and `version` comes from `check_version_parity` (single source of truth across `__init__.py`, `pyproject.toml`, etc.). Test `test_submit_branch_create_uses_versioned_name` (line 455) pins the exact argv `["git", "checkout", "-b", f"add-{sub.SKILL_NAME}-1.5.8", "upstream/staged"]`. Verified.

## 7. Findings narrative
None — no FIX-REQUIRED or CONCERN-level issues found.

## 8. NITs
- NIT (step3, line 702-703): the reuse path runs `r_br = _run(["git", "rev-parse", branch], ...)` and immediately uses `r_br.stdout` without checking `r_br.returncode`. If rev-parse somehow fails after `--verify` succeeded (race / corrupt ref), `branch_sha` would be empty string and would not equal `upstream_sha`, falling into the divergence-confirm path — operator-visible, not silent. Low impact.
- NIT (step5, lines 793-798): empty `git status --porcelain README.md` after `npm start` is a WARNING that continues. If npm start really didn't touch README.md the subsequent `git add README.md` in step6 would still succeed (no-op), and `git commit` would either commit just the skills/ dir or hit the tolerated "nothing to commit" branch. Acceptable but slightly noisy.
- NIT (commit-message tense): commit message is `"Add {SKILL_NAME} skill v{version}"` — fine and matches conventional-commits "imperative add".

VERDICT: SHIP
