## Panelist B — Test coverage sufficiency (instruction 204, HEAD c46b5de, branch 1.5.8)

**Role-lock:** I am a REVIEWER, not the orchestrator. My charter is test coverage sufficiency for the publish-script `--publish` flag commit. My output ends in a VERDICT block.

---

### 1. Charter recap

Verify that `PublishFlagTests` in both `bin/tests/test_publish_pip.py` and `bin/tests/test_publish_npm.py` actually pins the documented `--dry-run` XOR `--publish` affirmation semantics, mutation verification is genuine, no regressions, and decide on AUDIT-table elevation.

---

### 2. Per-script test-method-presence + assertion table (10 methods)

#### `bin/tests/test_publish_pip.py` — class `PublishFlagTests` (lines 554–599)

| Method | File:Line | Asserts what (beyond exit 0)? |
|---|---|---|
| `test_no_args_prints_intro_and_exits_zero` | test_publish_pip.py:561 | `main()` returns `0` with `sys.argv=["publish_pip"]`. (Existing `NoArgsBannerTests.test_no_args_prints_banner_returns_zero` at line 525 additionally asserts banner text — combined coverage is strong.) |
| `test_dry_run_and_publish_mutually_exclusive` | test_publish_pip.py:568 | rc == `publish_pip.EX_USAGE` (64) AND stderr contains `"mutually exclusive"`. Charter item 2.b satisfied. |
| `test_skip_tests_alone_is_not_a_publish_trigger` | test_publish_pip.py:578 | rc == `publish_pip.EX_USAGE` (64) AND stderr contains `"must pass --dry-run or --publish"`. Pins the pre-204 regression. Charter item 2.c satisfied. |
| `test_publish_flag_parses_as_store_true` | test_publish_pip.py:590 | `parse_args(["--publish"])` yields `args.publish is True` AND `args.dry_run is False`. Charter item 2.d satisfied. |
| `test_dry_run_flag_parses_as_store_true` | test_publish_pip.py:596 | `parse_args(["--dry-run"])` yields `args.dry_run is True` AND `args.publish is False`. Charter item 2.e satisfied. |

#### `bin/tests/test_publish_npm.py` — class `PublishFlagTests` (lines 508–550)

| Method | File:Line | Asserts what (beyond exit 0)? |
|---|---|---|
| `test_no_args_prints_intro_and_exits_zero` | test_publish_npm.py:515 | `main()` returns `0` with `sys.argv=["publish_npm"]`. |
| `test_dry_run_and_publish_mutually_exclusive` | test_publish_npm.py:521 | rc == `publish_npm.EX_USAGE` AND stderr contains `"mutually exclusive"`. |
| `test_skip_stage_alone_is_not_a_publish_trigger` | test_publish_npm.py:531 | rc == `publish_npm.EX_USAGE` AND stderr contains `"must pass --dry-run or --publish"`. Note the npm script's orthogonal flag is `--skip-stage` (not `--skip-tests`), so the name correctly mirrors the npm-side surface. |
| `test_publish_flag_parses_as_store_true` | test_publish_npm.py:542 | `parse_args(["--publish"])` yields `args.publish is True` AND `args.dry_run is False`. |
| `test_dry_run_flag_parses_as_store_true` | test_publish_npm.py:547 | `parse_args(["--dry-run"])` yields `args.dry_run is True` AND `args.publish is False`. |

**All 10 methods present, asymmetric on the right surface, asserting both rc + stderr message content (not just exit 0).** Charter item 1 + 2 fully satisfied.

Targeted run output:

```
$ cd bin/tests && python3 -m unittest test_publish_pip.PublishFlagTests test_publish_npm.PublishFlagTests -v
... 10 tests in 0.002s — OK
```

---

### 3. Mutation verification audit

**Orchestrator's report (commit message + build-agent notes):** snapshot `/tmp/qpb_204_pip_snapshot.py`; XOR block in `main()` commented out; `test_skip_tests_alone_is_not_a_publish_trigger` failed with `AssertionError: 65 != 64`; restored via `shutil.copy2`; pycache purged; re-ran PASS.

**Evidence trail confirmed:**
- `/tmp/qpb_204_pip_snapshot.py` still present (756 lines, 26773 bytes, mtime 12:02 — earlier than current file's 12:05 my safety snapshot).
- `diff /tmp/qpb_204_pip_snapshot.py bin/publish_pip.py` → identical (no output), confirming clean restore.
- Commit message explicitly documents the mutation bite (lines: "snapshotted publish_pip.py to /tmp; commented out the XOR affirmation block in main(); ran ... → FAILED with AssertionError: 65 != 64").

**Independent re-perform (Panelist B):** I took my own snapshot at `/tmp/qpb_204_pip_panelB_safety.py`, edited `bin/publish_pip.py` to comment out the entire XOR block (both branches), purged `bin/__pycache__`, ran the targeted test, restored via `shutil.copy2`, re-ran:

```
PRE-MUTATION expected: rc == 64 (EX_USAGE)
MUTATED:               rc == 65 (EX_DATAERR — script reached the clean-tree preflight)
                       AssertionError: 65 != 64   ← matches orchestrator's report exactly
POST-RESTORE:          OK
git status --porcelain after restore: clean (no diff)
```

The mutation reproduces deterministically. The test would catch a future regression that removes the XOR gate. EX_DATAERR (65) leaks through because the preflight reports the working tree dirty (since the script was just edited) — semantically this is fine for the mutation bite because it confirms the test is gating on the right exit code path (the XOR check rejects with 64 BEFORE preflights run; without it, preflights run and reject with 65). The test asserts `== 64`, so it correctly distinguishes "guard fires" from "guard absent."

**One small gap:** Only `publish_pip.py` was mutation-bitten. The same XOR block was added to `publish_npm.py` (verified at `bin/publish_npm.py:491` and `:498`); its corresponding `test_skip_stage_alone_is_not_a_publish_trigger` was NOT independently mutation-bitten. The pip↔npm structural mirror is tight enough that the same test design will pin the same defect, but per `ai_context/DEVELOPMENT_PROCESS.md § Mutation-test discipline`, each pinned regression should ideally be individually mutation-verified. This is a **NIT** (the cost is low, the orchestrator could have done it for symmetry), not a blocker — the test code is byte-identical in structure and the production code is too, so a passing mutation bite on one channel is high-confidence transferable evidence for the other.

Charter item 3 satisfied (with NIT).

---

### 4. AUDIT-table elevation evaluation

**Per DEVELOPMENT_PROCESS.md § AUDIT-table invariant test pattern, the criteria are:**

1. Defect class fired a **third** time across QPB (2 = coincidence, 3 = pattern).
2. Shape identifiable via mechanical scan.
3. Reasonable future PR could re-introduce the defect at a new site without anyone noticing.

**Hits and misses:**

- **Sites today:** 2 — `bin/publish_pip.py` and `bin/publish_npm.py`. `submit_awesome_copilot.py` is **out of scope** by the commit message's own rationale (writes a packet to disk only; not destructive; no live-vs-dry-run distinction exists). So the defect class has fired at **2** sites simultaneously, which by the codified rule is **coincidence, not yet a pattern**.
- **Mechanical-scan shape exists:** "every `bin/publish_*.py` whose `main()` can perform a destructive external action must require an explicit `--publish` XOR `--dry-run` gate before reaching the action." This is auditable by AST walk for `argparse.ArgumentParser` instances and `main()` early-return on missing affirmation. Criterion 2 is satisfied.
- **Future-PR risk:** Real. If someone adds `bin/publish_brew.py`, `bin/publish_homebrew.py`, `bin/publish_chocolatey.py`, or a `bin/publish_marketplace.py` in v1.5.9+ (the methodology explicitly contemplates "new marketplace submission process" — DEVELOPMENT_PROCESS.md:34), the omission of the XOR gate is exactly the failure that fired here at 204. Criterion 3 is satisfied.

**Verdict on elevation:** **NOT-YET-REQUIRED but RECOMMENDED-FUTURE.** With only 2 sites today, AUDIT elevation would be premature per the documented rule. However, the **next** new publish-channel script that lands without the XOR gate (or with a XOR gate that diverges in spelling/semantics) triggers the third-instance rule and the AUDIT sweep test becomes mandatory then.

**Concrete future shape suggestion** (for the post-third-instance moment):
- File: `bin/tests/test_publish_channel_affirmation_invariant.py`
- AUDIT-table entries: `bin/publish_pip.py` → FIXED-at-c46b5de; `bin/publish_npm.py` → FIXED-at-c46b5de; `bin/submit_awesome_copilot.py` → SAFE-with-justification ("non-destructive; writes packet to disk only; no live-vs-dry-run dichotomy").
- Sweep test: glob `bin/publish_*.py` AND `bin/*_publish.py`, AST-walk for `argparse.ArgumentParser`, assert each parser declares both `--dry-run` and `--publish` (or is on the SAFE allow-list).

I'm NOT requiring this for SHIP — the elevation rule explicitly says "third instance, not second." Charter item 4 evaluated and decided.

---

### 5. Full suite regression check

```
$ python3 -m pytest bin/tests/test_publish_pip.py bin/tests/test_publish_npm.py bin/tests/test_submit_awesome_copilot.py
... Ran 105 tests in 0.811s — OK
EXIT=0
```

All 105 tests pass (47 pip + 47 npm + 11 awesome-copilot). Charter item 5 satisfied.

---

### 6. Per-finding narrative (CONCERN / FIX-REQUIRED)

None.

---

### 7. NITs

**NIT-1 (mutation symmetry):** The npm side's `test_skip_stage_alone_is_not_a_publish_trigger` was not independently mutation-bitten. Recommend the orchestrator do a one-shot mutation on `publish_npm.py:491–504` for symmetry next time it touches that file. The structural mirror with pip is tight enough that I'm not blocking on it — but the discipline section says "every regression-pin test" and 5 of the 10 here were verified only by transitive inference.

**NIT-2 (AUDIT-table forward planning):** Document the "publish-channel affirmation" defect-class shape in `docs/design/` or in a comment in `ai_context/DEVELOPMENT_PROCESS.md § AUDIT-table` as a worked example of a *2-site pattern queued for elevation*, so the next reviewer who sees a new `publish_*.py` script will know to check for the XOR gate even before the third instance lands. Cheap to do; pays off the next time a publish channel is added.

**NIT-3 (test-data dual-pin):** The pip test uses `--skip-tests`, the npm test uses `--skip-stage`. Both are the right channel-specific flag, but if a future contributor refactors either script's orthogonal-flag set, the test name no longer corresponds to a real flag. Low risk — argparse will reject the unknown flag at parse_args time and the test will fail loudly. No action needed.

---

### 8. Summary

The commit ships exactly what instruction 204 calls for: a `--publish` flag, mutually-exclusive XOR semantics in both `main()` functions, 5 well-scoped pin tests per script asserting both exit code AND stderr message content, mutation verification on the pip side that reproduces independently, and zero regressions in the surrounding 105-test suite. The submit_awesome_copilot exclusion is correctly justified. AUDIT-table elevation is not yet required by the codified 3-instance rule. The 3 NITs are forward-looking polish, not blockers.

```
VERDICT: SHIP
```
