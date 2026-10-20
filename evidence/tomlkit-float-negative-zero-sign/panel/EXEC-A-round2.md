# EXEC-A round 2: SHIP (high)

Amended commit d59cfe9 (base 0518af2). Work dir: /work/t2/scratch/panel2-tomlkit-float-negative-zero-sign-EXEC-A (plus -base and -clean siblings). Did not read panel/ files.

Round-1 finding in my charter: none required a source change. Executor sequence redone from scratch on the amended commit.

1. Round-2 diff vs rev0 patch (test only, source line unchanged): first input now `a = -1.5` times `0` (was `+0.0` times `-1`); first comment removed; comment `# Integer true division also goes through Float._new.` added. Matches SYNTHESIS.md.
2. RED (test hunk only at HEAD~1): `assert doc.as_string() == "a = -0.0"` fails with `AssertionError: assert 'a = +-0.0' == 'a = -0.0'`. Right reason, first assertion.
3. GREEN (source applied): `1 passed, 100 deselected`.
4. REVERT (source only reverted): `1 failed` on the same test.
5. Touched file: `101 passed`. Suite: `1069 passed in 1.29s` (base 1068 + 1).
6. Lint: `ruff check tomlkit tests/test_items.py` passes; `ruff format --check` on the same: `13 files already formatted`. A bare repo-wide `ruff check` reports 8 errors, all in tests/toml-test/gen.py (untouched, pre-existing).
7. Patch application: `git am` of `0001-*.patch` onto a clean clone at 0518af2 succeeds; tree 860e0ebf6c179cb48ce0bb8c64de4da6dca9f193 equals the tree at HEAD of fix-tomlkit-float-negative-zero-sign (identical hash). Diffstat 2 files, 15 insertions, 1 deletion.
8. PR.md behavioural claims run on base and fixed (own repro, round-trips through tomlkit and tomllib):
   - `x = -1.5` times `0`: base `x = +-0.0` (InvalidNumberError), fixed `x = -0.0` (ok). This is the PR snippet; the comments in it are accurate.
   - `x = +0` then `/= -1`: base `+-0.0`, fixed `-0.0`.
   - Also base-bad and fixed-ok: `+0.0` negated, `+5.0 * -0.0`, `-0.0 * 1`.
   - Unchanged on both: `x = 0.0` negated gives `-0.0`; `x = -1.5 * -1` gives `+1.5`.
   - Base items.py:879 is `if self._sign and result >= 0:` (line number in PR text correct).
   Not checked by me: the #345/#341 history and the PR's "Negative zero is the only value that is >= 0 and prints with a leading -" beyond the cases above (NaN has no leading `-` in str; not run).

| red | green | revert | suite | repro | verdict |
|---|---|---|---|---|---|
| fail (`+-0.0` vs `-0.0`) | pass | fail | 1069 passed | base: 5 of 7 bad; fixed: 0 bad | PASS |

New problems in the revision: none found.
Side-effect rule: only outputs that were unparseable `+-0.0` change; nobody is hurt.
