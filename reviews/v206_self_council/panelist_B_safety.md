# Panelist B — Destructive-action safety + idempotency audit (instruction 206)

## 1. Charter recap

Audit the `--submit` path of `bin/submit_awesome_copilot.py` so every
destructive git/gh action is gated by a y/N prompt that presents the right
context, refusal halts with a clear statement of the operator's resulting
state, and re-running after a partial failure resumes cleanly.

## 2. Destructive-action audit table

| # | Destructive op | Code site | y/N gate present? | Context shown before gate | Halt-on-N message clear? |
|---|---------------|-----------|-------------------|---------------------------|--------------------------|
| 1 | `git push -u origin <branch>` | step6 L845 | YES — gate at L817 (`_confirm("Commit and push this submission to your fork?")`) | `git diff --stat` printed L811-813 | YES (L819-823) — "SKILL.md was copied and npm start ran but nothing was committed. Re-run --submit to retry, or commit manually." But see CONCERN #1 about diff-stat completeness. |
| 2 | `gh pr create` | step7 L892 | YES — gate at L882 (`_confirm("Open this PR against ... staged?")`) | PR title + base + first 20 lines of PR_BODY.md (L873-879) | YES (L885-891) — "The branch was pushed to your fork but no PR was opened. You can open it later with `gh pr create --repo {AWESOME_COPILOT_REPO} --base staged --title {title!r} --body-file {pr_body_path}`." Gold-standard halt message. |
| 3 | `git remote set-url upstream <new>` | step2 L643-646 | YES — gate at L633 (`_confirm("upstream points at ..., not github/awesome-copilot. Reset upstream to ...?")`) only fires when current URL is NOT github/awesome-copilot | Current upstream URL and target URL both shown | PARTIAL — L640-642 "upstream points elsewhere ({current!r}) and operator declined to reset. Halt." Says what was refused but not what state the fork is in (.git/+origin set, upstream still wrong, no upstream fetch done). See NIT #1. |
| 4 | `git reset --hard upstream/staged` | step3 L724-727 | YES — gate at L711 (`_confirm("Branch ... exists and diverges from upstream/staged. Reset to upstream/staged?")`) only fires on divergence | Branch name + divergence statement; NO sha or commit-count shown | PARTIAL — L716-719 "branch {branch} diverges and operator declined reset. Operator must resolve manually." Doesn't state that the working tree is still on whatever branch it was on at script start (no `checkout` ran on the N path). See NIT #2. |
| 5 | `npm install` when fork pre-existing but no node_modules | step1 L563 | NOT gated (file copy / npm install treated as non-destructive) | n/a | n/a — install failure returns a non-zero halt message with stderr tail. Acceptable: npm install is idempotent and reversible (delete node_modules and retry). |

(Bonus: implicit "git remote add upstream" at step2 L655-658 is not gated because adding a missing remote cannot clobber anything; explicit `git add` + `git commit` after the step-6 gate are part of the same gated atomic operation per the prompt copy "Commit and push".)

## 3. Idempotency audit table

| State | Detection | Resume behavior | Verdict |
|-------|-----------|-----------------|---------|
| Packet already generated | `dest.mkdir(parents=True, exist_ok=True)` + plain `write_packet` overwrite | Re-writes packet files unconditionally | OK — packet writes are deterministic, idempotent by overwrite |
| Fork already cloned | `fork_path.is_dir() and (fork_path/".git").exists()` (step1 L553) | Skip gh fork, skip npm install if node_modules present | OK — pinned by `test_submit_skips_fork_when_path_exists` (the test fails the responder if gh fork or gh auth is called) |
| `node_modules` present | `node_modules.is_dir()` check (step1 L560-561) | Skip `npm install`; if absent, run it | OK |
| `upstream` remote already correct | `git remote get-url upstream` ⇒ checks for `github/awesome-copilot` (step2 L630-632) | No-op, no prompt, no set-url call | OK |
| Branch exists at upstream/staged HEAD | rev-parse compare branch ↔ upstream/staged sha (step3 L702-704) | Reuse: `git checkout {branch}`, no reset prompt | OK — exactly the charter requirement |
| Branch exists but divergent | Same rev-parse compare | Prompt y/N; on Y reset --hard, on N halt | OK (charter req 4) |
| SKILL.md already copied | `shutil.copy2` is unconditional, then SHA256 parity check (step4) | Overwrites; sha verifies; safe | OK by construction |
| `nothing to commit` after re-run | `combined.lower()` substring check (step6 L838) | Treated as already-committed; log + continue to push | OK — covers the partial-push retry case |
| PR already opened | NOT detected | `gh pr create` re-run will exit non-zero ("duplicate PR" error from gh), step7 returns EX_SOFTWARE with stderr tail | Acceptable trade-off — author's notes explicitly call this out as "operator-side concern (duplicate-PR error from gh surfaces as EX_SOFTWARE)". Operator will see "already exists" in stderr. Not a FIX-REQUIRED because state is unambiguous (PR exists on github) and the error message names the cause. |

## 4. State-clarity-on-N audit (one-path trace)

Trace path: operator runs `--submit`, packet generates OK, fork pre-existing, upstream correct, no branch yet → step3 creates branch from upstream/staged, step4 copies SKILL.md, step5 npm start succeeds, step6 shows diff --stat, operator types `N`.

**What gets printed** (from `_log`, which writes to stdout + log file via `_log_subprocess` and direct prints in step6):

1. `--- git diff --stat in fork ---` … diff text … `--- end diff ---`  (L811-813)
2. Prompt: `Commit and push this submission to your fork? [y/N] `  (L817)
3. Operator types `N` → `_confirm` returns False.
4. step6 returns `(False, "Step 6: operator declined commit+push. SKILL.md was copied and `npm start` ran but nothing was committed. Re-run --submit to retry, or commit manually.")`
5. `run_submission` loop: `_log(log_fh, msg)` ⇒ that message prints; then `_log(log_fh, "Step 6: HALT.")`; returns `EX_SOFTWARE` (70).

**Verdict on clarity**: the operator clearly knows
- SKILL.md is in the fork's working tree (not committed)
- `npm start` already ran (so README.md is also modified, untracked + tracked)
- Nothing was committed → no push happened
- Re-running --submit is safe (idempotent path will copy SKILL.md again and prompt afresh)

This is the GOLD STANDARD halt message and meets the charter unambiguously.

Same trace at step7 (push gate Y, PR gate N): operator gets a literal `gh pr create --repo ... --title ... --body-file ...` rescue command. Excellent.

Trace at step3-reset N: operator gets "branch diverges and operator declined reset. Operator must resolve manually." This is technically correct — no `git checkout` ran before the prompt (L720-723 is AFTER the `if not ok: return`), so the working tree state is unchanged from script start — but the message doesn't TELL the operator that. See NIT #2.

Trace at step2-upstream N: "upstream points elsewhere ({current!r}) and operator declined to reset. Halt." Operator knows the URL is wrong but doesn't get told that the fork was successfully cloned (or pre-existed) and is otherwise intact. See NIT #1.

## 5. Per-finding narrative

### CONCERN #1 — `git diff --stat` does NOT include the new SKILL.md file shown to the operator before the push gate

step6 L809 runs `git diff --stat` (no ref). Git semantics: this shows **unstaged tracked-file modifications only**, omitting both staged content and untracked files.

The submission packet's headline file is `skills/quality-playbook/SKILL.md`, which is **brand-new** — `step4_copy_skill_md` writes it via `shutil.copy2` into a directory just created by `dst_dir.mkdir(parents=True, exist_ok=True)`. It is **untracked** when step6 runs the diff.

I verified this with a sandbox repro at /tmp/diff-test: `git diff --stat` shows only modifications to already-tracked files; an untracked `b.txt` (and a fortiori a brand-new file in a brand-new subdirectory) does NOT appear.

Net effect: the operator sees the README.md row in the diff-stat (1 line changed, generated by `npm start`) and confirms the push — but the new SKILL.md (the **entire** content of this submission) is invisible at the gate. The push will include it (via `git add skills/{SKILL_NAME}/`), but the gate did not show it.

Per charter req 1 this is a defect — the y/N gate is present, but the context shown before the gate is incomplete in a way that defeats the purpose of "show before push." The fix is one of:
- `git status --porcelain` AND `git diff --stat upstream/staged...HEAD` (after `git add`), or
- run `git add` BEFORE the diff and use `git diff --stat --cached`, or
- run `git status --short` alongside the diff-stat.

I'm flagging this as CONCERN rather than FIX-REQUIRED because (a) the gate IS present, (b) the operator can ALWAYS abort by typing N and inspect the working tree manually, and (c) the eventual PR_BODY.md preview at step7 names the package + version explicitly. But this is a meaningful gap and should be fixed in a follow-up.

### Sanity confirmations (no findings)

- Re-running `--submit` after a step-6 N is genuinely safe (verified by reading step1/step3 idempotency paths and pinned by `test_submit_skips_fork_when_path_exists`).
- All four destructive-op gates fire only when needed (step2 only on URL mismatch, step3 only on divergence) — no spurious gates that train operators to mash Y.
- The `_confirm` helper (L522-528) returns False on EOFError (e.g., `--submit < /dev/null`), preventing accidental Y in headless contexts.
- `EX_SOFTWARE` (70) on any halt — operator can detect failure via `$?` in automation.

## 6. NITs (non-blocking)

- **NIT #1** — step2 L640-642 halt message: add "(fork is intact at {fork_path}; no upstream fetch was performed)" so operator knows nothing was clobbered.
- **NIT #2** — step3 L716-719 halt message: add "(working tree unchanged from script start; branch `{branch}` still at its divergent SHA)" so operator knows the on-disk state.
- **NIT #3** — step3 divergence prompt L711 does not show the branch's current SHA or how many commits diverge. A `git log --oneline upstream/staged..{branch}` preview would let the operator make an informed choice about discarding work.
- **NIT #4** — step7 duplicate-PR detection is left to gh's stderr. A pre-flight `gh pr list --head <user>:<branch> --base staged --repo github/awesome-copilot --json url` check could detect the existing PR and surface its URL instead of failing through gh's "already exists" error. Nice-to-have, not required.
- **NIT #5** — step6 L838 substring match `"nothing to commit" in combined.lower()` is locale-dependent on git's error text. Most git installs are English, but a stricter check would be `r_commit.returncode == 1 and "nothing to commit" in (r_commit.stdout + r_commit.stderr).lower()` and/or also accept `"clean working tree"`. Edge case.

## 7. Verdict

The destructive-action gating model is sound: all four charter-mandated destructive ops (push, PR-create, set-url, reset --hard) are gated with y/N prompts that fire only when needed, and three of the four refusal paths leave clean state with informative messages. Idempotency strategy is correct across all six dimensions the charter calls out (packet, fork, upstream, branch, file copy, commit-state). All 29 unit tests pass including the 10 SubmitFlagTests pinning the gates and the affirmation XOR.

The one substantive gap is CONCERN #1: the diff-stat preview shown before the push gate omits the brand-new SKILL.md because `git diff --stat` (sans ref) doesn't include untracked files. The gate is technically present and the operator can always decline, but the context shown is incomplete in a way that partially defeats the gate's purpose. This is a meaningful but recoverable defect — operator can N out and inspect — so it's a CONCERN, not a FIX-REQUIRED. It should be addressed in a follow-up instruction.

```
VERDICT: CONCERN
```
