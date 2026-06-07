# Panelist C — Regression test sufficiency + mutation verification

Instruction 203 self-Council Protocol 1. Repo HEAD `36d53ed` on branch `1.5.8`.

## 1. Charter recap

Audit `NpmPackRoundTripStdoutTests.test_npm_pack_dry_run_stdout_is_pure_json` for real-round-trip coverage of the prepack stdout-pollution contract, independently verify the mutation bite, and decide whether the "JSON-pure stdout for consumers" defect class warrants an AUDIT-table invariant sweep.

## 2. Test-design audit

File: `bin/tests/test_publish_npm.py:346-392` (class `NpmPackRoundTripStdoutTests`).

**Real round-trip — confirmed.** The test:

- Resolves `npm` and `python3` via `shutil.which` (lines 355-358) and skips if either is absent. This is the correct CI-safe skip pattern — no need to fail on a runner without npm.
- Computes `repo_root = Path(__file__).resolve().parents[2]` and skips if `package.json` isn't at that root (lines 359-361) — guards against running the test from a vendored/installed copy where the on-disk package.json doesn't exist.
- Invokes `subprocess.run([npm, "pack", "--dry-run", "--json"], cwd=repo_root, ...)` — this is the genuine npm binary against the on-disk `package.json` + the on-disk `bin/build_channel_package.py` prepack hook (`package.json:33`: `"prepack": "python3 bin/build_channel_package.py --stage"`). Not a mock, not a stub. Full round trip.
- Passes `encoding="utf-8", errors="replace", timeout=120` — matches the v1.5.7 instruction 190 subprocess-encoding contract and bounds runtime.

**Assertions pin the right contract.** Three layers, in escalating strictness:
1. `returncode == 0` — npm itself succeeded.
2. `r.stdout.lstrip().startswith("[")` — the load-bearing assertion. This is exactly the contract the 202 bug violated: the JSON array must be the first non-whitespace content on stdout. The failure message embeds `repr(r.stdout[:200])` for actionable diagnosis.
3. `json.loads(r.stdout)` returns a `list`, length > 0, first entry has `files`, and `name == "quality-playbook"` — pins both the structure and the package identity (prevents a future drift where stdout happens to be valid JSON but for a different package).

**Local imports inside the test method** (`shutil`, `subprocess` rebound as `_shutil`, `_sub`) are deliberate — keeps the module's top-level imports unmocked-friendly for the subprocess-mocking tests in the same file. Reasonable.

**Skip logic — confirmed CI-safe.** Three independent skip conditions: missing `npm`, missing `python3`, missing `package.json`. None of these raise; each calls `self.skipTest(...)` cleanly. A CI box without npm gets a `skip`, not a `fail` — exactly right.

**Independent live run on current HEAD:** test passes in 0.948s. Full `test_publish_npm` suite: 34 tests, all pass.

## 3. Mutation verification

**Build agent's reported result — confirmed.** I performed an independent mutation bite distinct from the build agent's:

1. Snapshotted current `bin/build_channel_package.py` to `/tmp/qpb_203_panelist_c_snapshot.py`. Verified byte-equal with the build agent's snapshot at `/tmp/qpb_203_bcp_snapshot.py` (`diff -q` clean).
2. Used `Edit` to remove `file=sys.stderr,` from the staged-files print (lines 564-568 of `bin/build_channel_package.py`), restoring the v1.5.7 stdout-polluting behavior.
3. Purged `bin/__pycache__` and re-ran `python3 -m unittest test_publish_npm.NpmPackRoundTripStdoutTests.test_npm_pack_dry_run_stdout_is_pure_json` → FAIL with:
   ```
   AssertionError: False is not true : npm pack stdout is NOT pure JSON — prepack stdout pollution detected. First 200 chars of stdout:
   'build_channel_package: staged 59 files into /Users/andrewstellman/Documents/QPB/quality_playbook_cli/_bundle\n[\n  {\n    "id": "quality-playbook@1.5.8",\n    "name": "quality-playbook",\n    "version": "1'
   ```
   This is the exact diagnostic the build agent reported (modulo timestamp differences). The polluted prefix is reproduced exactly.
4. Restored via `python3 -c "shutil.copy2(...)"` from my snapshot (per `[[feedback_mutation_bite_pycache]]` — NOT `git checkout`).
5. Re-purged `bin/__pycache__`; re-ran test → PASS. `git status` clean; `git diff bin/build_channel_package.py` empty.

The test bites. The mutation-revert→fail→restore→pass loop holds independently.

**Per DEVELOPMENT_PROCESS.md § Mutation-test discipline** (lines 122-131), the discipline requires "Revert → confirm fail → restore → confirm pass" with the result cited in the commit message. The commit message at `36d53ed` does cite it ("Mutation verification (per ai_context/DEVELOPMENT_PROCESS.md § Mutation-test discipline)") and the result is now independently reproduced. Discipline satisfied.

## 4. AUDIT-pattern evaluation

**Quoting the canonical:**

`ai_context/DEVELOPMENT_PROCESS.md:97-118`:

> ### AUDIT-table invariant test pattern (v1.5.7 184+)
>
> When a defect class shape is observed across multiple sites in the codebase, the fix is incomplete unless it includes an exhaustive-sweep invariant test that scans the entire relevant tree and asserts the contract holds at every site. Has shipped across 184 (`_pid_alive` divergence), 189 (log-read encoding fallback), 190 (subprocess stdin encoding) — **three confirmed reuses graduate it from "pattern" to "standard mechanism."**
> ...
> **When to file an AUDIT sweep test:**
> - The defect class fired **a third time across QPB**. (Two instances may be coincidence; three is a pattern.)
> - The shape is identifiable via mechanical scan (regex, AST, identity-`is` check).
> - A reasonable future PR could re-introduce the same defect at a new site without anyone noticing.

**The defect class shape:** "Scripts whose stdout is consumed by a JSON parser (npm prepack, pip publish hook, future channel scripts) must keep stdout JSON-pure — all progress/diagnostic prints go to `sys.stderr`, with `--version` (or other consumer-facing data) as the only documented exception."

**Counting QPB occurrences of this defect class:**

This is the **first known firing** in QPB. I grepped for `file=sys.stderr` and `file=sys.stdout` discipline sites across `bin/build_channel_package.py`, `bin/install_skill.py`, `bin/publish_npm.py`, `bin/publish_pip.py` — only `build_channel_package.py` currently has this pattern. The 202 publish bug was the first reported instance of a script-consumed-as-JSON contract being violated.

**Verdict on AUDIT-pattern elevation:** **Not yet.** The doc's own criterion is explicit: "three confirmed reuses graduate it from 'pattern' to 'standard mechanism.'" The instruction's prompt itself acknowledges this: "pattern requires three to graduate." We have one. The other v1.5.7 worked examples (184, 189, 190) each cite three or more prior instances at filing time. Filing an AUDIT sweep on a one-fire class would be premature and would create a maintenance burden (every new `print()` in `bin/` would need to be triaged against the allow-list).

**However, the instruction-203 commit DID do the right defense-in-depth.** Two complementary fixes:
1. Root-cause fix at `bin/build_channel_package.py:557, 567` (stderr discipline) — closes the bug at its specific site.
2. Defense-in-depth at `bin/publish_npm.py:308-322` — even if a future change re-introduces prepack stdout pollution, the publish script still parses correctly by finding `[` and slicing from there.

The module-top audit comment at `bin/build_channel_package.py:544-548` documents the stdout discipline ("All progress/diagnostic messages go to `sys.stderr` so consumers ... can parse our stdout cleanly. `--version` is the only exception"). This is the right doc-level annotation for a first-fire defect — it pins the contract at the file that just violated it, without yet promoting it to a tree-wide invariant.

**Recommendation (advisory, not blocking):** if a second consumer-of-stdout-JSON script ships in v1.5.x (e.g., a publish_pip prebuild hook that's parsed by some tooling), file the AUDIT sweep at that point. The shape would be: enumerate all `print(` calls in any `bin/*.py` that's referenced from a `prepack`/`prepublishOnly`/equivalent hook, assert each one passes `file=sys.stderr` unless on a documented allow-list. AST-walkable, low-noise. But not now. Premature AUDIT tables are themselves a maintenance hazard.

## 5. Per-finding narrative

None. No CONCERN or FIX-REQUIRED items.

## 6. Optional NITs

- **NIT (low):** the test's `repo_root` skip guard (`if not (repo_root / "package.json").is_file(): self.skipTest(...)`) is defensive against a test layout I can't easily construct in practice (tests are co-located with the package.json'd repo). Keep it — it's cheap and honest about the assumption. No change needed.
- **NIT (low):** the `test_log_captures_full_unmodified_stdout` test (lines 328-343) uses `"PREPACK NOISE"` as the polluted prefix; the round-trip diagnostic uses the actual `build_channel_package:` prefix. The mocked test would more faithfully simulate the live failure if its polluted prefix matched the real prepack message. Stylistic only — both pass and pin the contract. No change needed.
- **NIT (low):** `bin/publish_npm.py:308-322` uses `stdout.find("[")` which would also match a `[` inside an early stderr-mirroring progress line if such a line ever contained square brackets. In practice prepack progress is `build_channel_package: staged N files into <path>` which has no `[`, but a future change to that progress message could break the defensive parse. Consider a more specific anchor (e.g., regex match for the JSON array start at column 0 of a line) if the defense-in-depth ever needs to be hardened further. Not a blocker — current behavior is correct given the current prepack output.

## 7. Verdict

```
VERDICT: SHIP
```

Test design is correct and tight; skip logic is CI-safe; mutation bite is independently reproduced and passes the revert→fail→restore→pass discipline; defense-in-depth at the publish-script level is in place. The AUDIT-table question is correctly answered "not yet" by the doc's own three-fire criterion — the first-fire response (site fix + module-level audit comment + companion mocked tests + real round-trip test) is the right shape of fix for a single-instance defect class.
