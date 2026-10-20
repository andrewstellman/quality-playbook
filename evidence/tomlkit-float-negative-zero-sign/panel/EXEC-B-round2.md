# EXEC-B round 2: SHIP (high)

Commit d59cfe9 (amended), base 0518af2. Own copies: /work/t2/scratch/panel2-tomlkit-float-negative-zero-sign-EXEC-B/{fixed,base}. The packet patch applies to the clean base with `git am`, and the resulting tree hash equals HEAD's tree hash in fix-<SLUG> (TREES-EQUAL). `git format-patch -1` on the fixed clone is byte-identical to the packet's `0001-*.patch`.

Round-1 findings in my charter: none (EXEC-B had no required changes). SYNTHESIS.md says the test's first input and the comments changed; I checked this by diffing `rev0/0001-*.patch` against the new patch. The source line is identical. The only test changes are: first input `+0.0` times `-1` became `-1.5` times `0`, the history comment was removed, and `# Integer true division also goes through Float._new.` was added.

## Sequence on d59cfe9
- RED (test file only, base source): `tests/test_items.py:1457 assert doc.as_string() == "a = -0.0"`, `AssertionError: assert 'a = +-0.0' == 'a = -0.0'`. It fails for the claimed reason.
- GREEN (source added): `1 passed`; `tests/test_items.py` `101 passed`.
- REVERT (test kept, source reverted): `1 failed, 100 passed` in test_items.py; full suite `1 failed, 1068 passed`.
- SUITE fixed: `1069 passed`. SUITE base: `1068 passed`.
- Lint on fixed: `ruff check` "All checks passed!", `ruff format --check` "28 files already formatted".
- Note: a fresh `git clone` lacks the tests/toml-test submodule (collection error in test_toml_tests.py). I used `cp -a` of the fixed clone as the brief says.

## PR.md behavioural claims, run on base and fixed
- Repro (`x = -1.5`, `doc["x"] *= 0`): base `x = +-0.0` and `InvalidNumberError Invalid number at line 1 col 9` on re-parse (text matches exactly); fixed `x = -0.0`, parse ok.
- `n = +0`, `doc["n"] /= -1`: base `n = +-0.0`, fixed `n = -0.0`. The Integer true-division claim holds.
- "items.py:879 adds + when self._sign and result >= 0": true on base (line 879).
- Confirmer's repro (copied to my dir): base `7 case(s) wrote a doubled sign`, exit 1; fixed `0 case(s) wrote a doubled sign`, exit 0. Output otherwise matches CONFIRMATION.md.

## Edge inputs (base | fixed), re-parsed with tomllib
| input / op | base | fixed |
|---|---|---|
| `+1e-200`, `-v * 1e-200` (underflow) | `+-0.0` tomllib FAIL | `-0.0` ok signbit=True |
| `+5.0`, `v % -5` | `+-0.0` FAIL | `-0.0` ok signbit=True |
| `+0.0`, `round(v,1) * -1` | `+-0.0` FAIL | `-0.0` ok signbit=True |
| `+inf`, `v - v` (nan) | `nan` | `nan` (unchanged) |
| `+nan` passthrough | `+nan` | `+nan` (unchanged) |
| `-0.0`, `abs(v)` | `+0.0` | `+0.0` (unchanged) |
| `+0`, `v * -1.0` | `-0.0` | `-0.0` (unchanged) |
| `+2`, `v ** -1` | `+0.5` | `+0.5` (unchanged) |
Also run: `+1_0.5` times `-0.0` fixed to `-0.0`. Every changed output was `+-0.0` before and is a valid `-0.0` now; no other output changed.

## Review of the revision
1. No problems found in the amended test. The second step (`-0.0 * -1` renders `+0.0`) passes on fixed and also on base, and it guards against over-fixing the sign.
2. PR.md: every sentence I could run is true. "Negative zero is the only value that is >= 0 and prints with a leading -": the edge runs (nan, inf, ordinary values) agree. Not checked: the references to #345/#341 (not in my charter).
3. Side-effect rule: the only output that changes was unparseable text (`+-0.0`) before; I found nobody who is hurt. Known out-of-scope case: `Integer.__pow__` negative exponent (SYNTHESIS.md) was not exercised here beyond `+2 ** -1`, which gives `+0.5` on both trees.

| red | green | revert | suite | repro | patch=tree | PASS/FAIL |
|---|---|---|---|---|---|---|
| fail (`+-0.0` vs `-0.0`) | pass | fail | 1069 / 1068 base | 7 bad base, 0 fixed | identical | PASS |
