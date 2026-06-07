# Panelist A — Pre-flight checks completeness + correctness

**Instruction:** 202 (publish scripts for pip + npm + awesome-copilot)
**Repo:** `/Users/andrewstellman/Documents/QPB`, branch `1.5.8`, HEAD `d2fd31f`
**Charter:** For each pre-flight check in `bin/publish_pip.py` (8) and `bin/publish_npm.py` (7): construct the failure-mode scenario the check should catch, verify the test suite covers it, verify the script halts with a clear error, and confirm the check actually prevents the named failure mode.

## 1. Charter recap

Audit the 8 pip + 7 npm pre-flight checks for completeness, correctness, test coverage, and whether each named check actually prevents the named failure mode.

## 2. pip pre-flight table

| # | Check name | Failure mode it should catch | Test fixture | Error-message clarity | Actually prevents the failure mode? |
|---|---|---|---|---|---|
| 1 | Clean working tree | Uncommitted edits / untracked files / stale bundle staging | `CheckCleanTreeTests.test_dirty_tree_fails` (line 110), `test_git_status_failure_halts` (line 121). NO test for the `--ignored` bundle-dir branch on a real gitignored `_bundle/` layout. | Clear for `git status` body; lists file names. | **NO — see FIX-REQUIRED #1.** The `--ignored quality_playbook_cli/_bundle` branch reports `!! quality_playbook_cli/_bundle/` because `_bundle/` is gitignored at the QPB repo (`.gitignore:13`), so the check halts every publish whenever the bundle dir exists on disk (which is always true on `--skip-build` re-runs or after a previous interrupted stage). |
| 2 | Version-string parity | One of pyproject.toml / package.json / `__init__.py` lagged on the bump | `CheckVersionParityTests` covers all four arms (3 mismatch cases + missing manifest). End-to-end `test_dry_run_halts_on_version_mismatch` (line 501). | Excellent — prints all three values + "MISMATCH" sentinel. | **YES.** Regex pinning + 3-way equality. |
| 3 | Tag exists | Operator forgot `git tag v<version>` | `CheckTagExistsTests.test_tag_missing_fails` (line 193). | Clear; includes the `git tag -a ...` fix-up command. | **YES.** Strict equality on `r.stdout.strip() != tag`. Exact `git tag --list <name>` semantics (not a glob) — no prefix-collision risk. |
| 4 | Tag is ancestor of HEAD | Stale tag pointing at an older commit | `CheckTagAncestorTests` covers all four arms (ancestor / yes-confirm / no-confirm / EOF-prompt). | Clear warning text + explicit "Operator declined/confirmed" trail. | **YES.** `git merge-base --is-ancestor`. EOF on input safely fails closed. |
| 5 | Build cleanly | `build_channel_package --stage` or `python -m build` errors out | No direct unit test for `check_build_clean`; only the e2e mocked path. | Captures last 2 KiB of stderr — pragmatic. | **YES.** Wipes `dist/` before re-build so Check 7 only scans fresh artifacts. |
| 6 | 089u parity test passes | Bundle/staging drift between channel install and clone install | `CheckParityTestTests` covers pass/fail/skipped/missing-file. | Clear pass/FAIL with stdout tail. | **YES.** Test file exists at `bin/tests/test_pip_channel_package_parity_089u.py` and pins skill-bundle parity. |
| 7 | No forbidden contents in built sdist/wheel | Cruft (`.git/`, `__pycache__/`, `*.pyc`, `quality/`, `previous_runs/`, `harness_runs/`, `metrics/`, `node_modules/`, `.env`) shipped to PyPI | `CheckForbiddenContentsTests` covers `__pycache__/`, `quality/`, `.env`, missing dist, empty dist. `ScanArchiveTests` covers per-fragment shapes (pycache, .pyc, .env, node_modules). | Lists first 25 hits + count of extras — actionable. | **YES.** Scans both `.whl` (ZipFile) and `.tar.gz` (TarFile). Forbidden-fragment list is a superset of the instruction's list. |
| 8 | Twine auth configured | Operator missing `~/.pypirc` or `TWINE_*` env vars | `CheckTwineAuthTests.test_pypirc_passes`, `test_env_vars_pass`, `test_no_creds_fails`. | Clear; tells the operator to create `.pypirc` or set env vars. | **MOSTLY YES — see NIT #1.** The `env_url and env_pw` branch (line 414) accepts URL+PASSWORD without USERNAME. Twine actually requires USERNAME too (or `__token__`); this branch passes a state that would fail at upload. |

## 3. npm pre-flight table

| # | Check name | Failure mode | Test fixture | Error clarity | Prevents? |
|---|---|---|---|---|---|
| 1 | Clean working tree | Same as pip Check 1 | `CheckCleanTreeTests.test_dirty_tree_fails` (line 62). NO test for the `--ignored` bundle-dir branch. | Clear porcelain dump. | **NO — same FIX-REQUIRED as pip Check 1.** Same code path; same `_bundle/` gitignored false-positive. |
| 2 | Version-string parity | Same as pip Check 2 | `CheckVersionParityTests` covers all three mismatch arms. | Same shape as pip. | **YES.** |
| 3 | Tag exists | Same as pip Check 3 | `CheckTagExistsTests` two arms. | Clear. (npm's message lacks the `git tag -a ...` hint that pip's does — minor inconsistency but not a halt.) | **YES.** |
| 4 | `npm whoami` succeeds | Operator not logged in to npmjs.com | `CheckNpmWhoamiTests` three arms (logged-in / not-logged-in / npm-missing). | Clear; tells operator to `npm login`. Handles `npm` missing on PATH explicitly. | **YES.** `shutil.which("npm")` resolution is clean; dry-run carve-out at line 499-502 lets a fresh checkout exercise the rest of the flow. |
| 5 | `build_channel_package.py --stage` succeeds | Staging script errors | `CheckStageBundleTests` three arms. | Captures stderr tail. | **YES.** |
| 6 | No forbidden contents in staged bundle | Cruft sitting in `_bundle/` before npm pack | `CheckNoForbiddenInBundleTests` five arms (clean / pycache / quality/ / .env / missing bundle). | Lists first 25 hits + count of extras. | **YES.** Walks `_bundle/` via `rglob('*')`. Skips empty directories (only `is_file()`), but that is acceptable because empty dirs aren't packed. |
| 7 | `npm pack --dry-run` succeeds + clean file list | npm's own packaging would error OR pack list contains forbidden contents | `NpmPackDryRunTests` three arms (clean / .pyc / pack-failure). | Lists JSON-parse error and forbidden hits. | **YES.** Defense-in-depth: re-scans the pack file list using the same forbidden lists as Check 6. |

## 4. Cross-cutting observations

- **Test coverage is dense.** 72 tests pass (45 in `test_publish_pip.py`, 27 in `test_publish_npm.py`). Every check has a positive and at least one negative fixture, plus an end-to-end `--dry-run` happy path and an end-to-end version-mismatch halt path.
- **`_purpose.py` no-args banner pinned** in both scripts (NoArgsBannerTests). Honors the 089x discoverability invariant.
- **Logging discipline is sound.** Every check's pass/fail message lands in `~/.qpb/publish_logs/<channel>_<version>_<UTC>.log` via `_log()` with timestamps.
- **No overlapping checks.** Each check has a distinct named failure mode.
- **Missing checks?** None that block ship; the seven (npm) and eight (pip) cover the documented failure modes from the instruction. Two NITs noted below.
- **Forbidden lists differ between pip and npm by design.** pip's `FORBIDDEN_SUFFIXES` includes `.env` (the basename rule already covers it, so this is redundant but harmless); npm's does not. Both correctly cover the instruction's enumerated paths.

## 5. Per-finding narrative

### FIX-REQUIRED #1 — `check_clean_tree` halts every publish on the gitignored `_bundle/` directory (BOTH pip and npm)

**Files / lines:**
- `bin/publish_pip.py:172-186`
- `bin/publish_npm.py:166-178`

**Failure-mode demonstration (real QPB repo at HEAD `d2fd31f`):**

```
$ git status --porcelain --ignored quality_playbook_cli/_bundle
!! quality_playbook_cli/_bundle/
```

…because `.gitignore` line 13 contains `quality_playbook_cli/_bundle/`.

Calling `publish_pip.check_clean_tree(repo_root)` in a clean tree returns:

```
ok: False
msg: build_channel_package may have left state under quality_playbook_cli/_bundle —
     clean it before publishing:
     !! quality_playbook_cli/_bundle/
```

The check's intent (per docstring) is to detect *untracked* files in `_bundle/` left by an interrupted build. But `_bundle/` is gitignored, so `git status --porcelain --ignored quality_playbook_cli/_bundle` emits the ignored-dir sentinel `!!` whenever the directory exists at all — i.e., always, after the first `--stage` run.

This is hit in three common operator scenarios:

1. **`--skip-build` (pip) / `--skip-stage` (npm) re-run** — the flag's whole purpose is "assume the bundle is already staged" → the bundle dir exists → Check 1 halts → the flag is dead-on-arrival.
2. **Re-run after a failure in Check 5–7** — the previous stage left `_bundle/` populated; the next publish attempt halts at Check 1 before even reaching the prior failure point.
3. **Mac/Linux operator who staged the bundle once for inspection before publishing** — same trap.

**Why the test suite missed it:** the tests use a tempdir fake repo (`_make_fake_repo`) that creates `_bundle/` but never runs `git init` + `.gitignore`. The `git status --porcelain --ignored ...` second subprocess call is mocked away with a generic `_run` patch, so the `!!` line never appears in the fixtures.

**Suggested fix (not authoritative):** either drop the `--ignored` branch (the bundle's contents are scanned by Check 7 / Check 6 anyway), or filter the output to only `??` lines (real untracked) before flagging.

**Suggested regression test:** create a tempdir, `git init`, write `.gitignore` containing `quality_playbook_cli/_bundle/`, populate the bundle dir, commit `.gitignore`, then call `check_clean_tree` and assert `ok=True`.

### CONCERN — Tests do not exercise the realistic interaction between `_bundle/` and `.gitignore`

Both `_make_fake_repo` helpers skip `git init`, so the entire `--ignored` code path is mocked at the subprocess boundary. This is the root cause of FIX-REQUIRED #1 escaping detection. Adding a single fixture with `git init` + `.gitignore` would catch it.

## 6. NITs

1. **`check_twine_auth` `env_url and env_pw` branch (publish_pip.py:413-414).** Accepts `TWINE_REPOSITORY_URL + TWINE_PASSWORD` without `TWINE_USERNAME`. Twine's auth requires a username (or `__token__`); URL alone doesn't imply a usable credential. Probably tighten to `env_url and env_user and env_pw` (or document that the operator must use `__token__`).
2. **`check_tag_exists` message asymmetry.** `publish_pip.py:230` shows the `git tag -a <tag> -m "Quality Playbook <ver>"` fix command; `publish_npm.py:207` does not. Cosmetic, not blocking.
3. **`FORBIDDEN_SUFFIXES = (".pyc", ".env")` in pip but `(".pyc",)` in npm.** `.env` is also covered by `FORBIDDEN_BASENAMES = (".env",)` so the pip-side suffix entry is redundant but harmless. Minor — could be removed for symmetry.
4. **`--skip-build` and `--skip-tests` are documented as "NOT for production" in `--skip-tests`'s help, but `--skip-build` is not similarly flagged.** Easy to add the same warning.
5. **`upload_testpypi` / `upload_prod` pass `dist / "*"` literally as a positional arg.** subprocess does not glob-expand strings (no shell=True). On Mac/Linux this fails unless twine itself expands the glob (it does), but it's worth being explicit (`*` is twine's own positional-arg convention) — verify on Windows by enumerating `dist.glob("*")` and passing the file list. Not a regression vs the instruction; just a portability bite to track.

## 7. Verdict

The pre-flight checks are well-structured, named accurately, paired with passing tests, and emit clear error messages with the noted exception. The `check_clean_tree` `--ignored` branch is a real defect that blocks the v1.5.8 publish flow — both pip and npm halt at Check 1 whenever the `_bundle/` directory exists on disk (which is the steady state after the first stage). The fix is small (drop or filter the `--ignored` branch) and the missing regression test is small (one fixture with `git init` + `.gitignore`). NIT #1 (twine URL+PASSWORD without USERNAME) is a secondary correctness issue worth tightening before ship.

```
VERDICT: FIX-REQUIRED
```
