# EXEC-A: SHIP (high)

Scope: executor charter only (red/green/revert/suite/repro). Worked in `/work/t2/scratch/panel-tomlkit-float-negative-zero-sign-EXEC-A`, copied from the fixed clone and checked out at `HEAD~1` (0518af2). I read `CONFIRMATION.md` first, as the charter allows. I did not review the PR text, policy or maintainer fit, and I ran no edge inputs of my own (that is EXEC-B's job).

## Steps and results

1. Test part only (`git apply --include=tests/test_items.py`): the new test fails. The assertion at `tests/test_items.py:1458`:
```
>       assert doc.as_string() == "a = -0.0"
E       AssertionError: assert 'a = +-0.0' == 'a = -0.0'
1 failed, 100 deselected in 0.19s
```
   The failure is for the claimed reason: `+0.0 * -1` renders `+-0.0`.
2. Source part applied (`tomlkit/items.py`): `1 passed, 100 deselected in 0.04s`.
3. Source part reverted, test kept: fails again at the same line, same message (`1 failed, 100 deselected in 0.19s`).
4. Source restored, then:
   - touched file `tests/test_items.py`: `101 passed in 0.26s`
   - full suite: `1069 passed in 1.49s` (base 1068, plus the new test)
5. Confirmer's repro: copied to my directory and run with `PYTHONPATH` set to my copy (verified `tomlkit.__file__` resolves to my copy). Result: all 10 lines `ok`, the 7 former bug cases write `x = -0.0`, `0 case(s) wrote a doubled sign`, exit 0. tomllib re-parse is `ok -0.0 signbit=True` for each. The unaffected cases are unchanged (`+0.0 + 0.0` gives `+0.0`, `-1.5 * -1` gives `+1.5`).
6. Lint:
   - On the two touched files, `ruff check` gives `All checks passed!` and `ruff format --check` gives `2 files already formatted`.
   - Repo-wide, `ruff check` reports 8 errors and `ruff format --check` reports 1 file, all in `tests/toml-test/gen.py`. The patch does not touch that file, so the findings predate it.

## Test reading
The test covers the Float path (`+0.0 *= -1`), the round trip back to `+0.0`, and the Integer true-division path (`+0` `/= -1`). All three are tied to the claimed bug. The comment in the test matches the failure.

## Findings
None blocking. Nothing needs to change on execution grounds.
Minor and not required: the round-trip `*= -1` back to `+0.0` passes only because `raw` for positive zero is `"0.0"` and the sign is then added. That is correct behaviour and it is asserted.

## Table

| red | green | revert | suite | repro | verdict |
|---|---|---|---|---|---|
| FAIL as expected (`+-0.0` vs `-0.0`, test_items.py:1458) | pass (1 passed) | FAIL as expected (same assertion) | 1069 passed; touched file 101 passed | exit 0, 0 doubled signs, all 10 ok | PASS |
