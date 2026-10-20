# EXEC-B: SHIP (high)

Scope: executor. I ran the patch in my own copy (/work/t2/scratch/panel-tomlkit-float-negative-zero-sign-EXEC-B, checked out at 0518af2, patch split by file with `git apply --include`). I did not review text, style, or policy, and did not run the Windows/macOS or Python 3.9-3.14 CI matrix (only the venv Python).

Findings: none that block. Two observations, neither required:
1. The new test's second block (`+0` then `/= -1`) covers the Integer true-division path. The first `*= -1` pair also checks that the sign comes back to `+0.0`. Both match PR.md claims.
2. My edge cases show no behaviour change other than the negative-zero case (see table).

## Steps (verbatim results)
- Test only applied at base: `FAILED tests/test_items.py::test_no_extra_plus_sign_on_negative_zero` with `E AssertionError: assert 'a = +-0.0' == 'a = -0.0'` at tests/test_items.py:1458. It fails for the claimed reason.
- Source also applied: `1 passed, 100 deselected`.
- Source reverted again (test kept): `1 failed, 100 deselected`, same test.
- tests/test_items.py with fix: `101 passed in 0.14s`.
- Suite with fix: `1069 passed in 1.53s`.
- `ruff check tomlkit tests/test_items.py`: `All checks passed!`; `ruff format --check tomlkit tests/test_items.py`: `13 files already formatted`. (A bare `ruff check` in the clone reports 8 errors and 1 reformat, all in the submodule file tests/toml-test/gen.py, not in the patch.)
- Confirmer's repro (copied to my directory, run against my fixed tree; `tomlkit.__file__` confirmed to be my copy): `tomlkit 0.15.1; 0 case(s) wrote a doubled sign`, exit=0, all 10 lines `ok`, including `x = +0 / -1 (Integer) -> x = -0.0`.

## My own edge inputs (script: <copy>/edge.py), base vs fixed
Round-trip = tomlkit.parse then tomllib.loads on the output.

| input | op | base | fixed |
|---|---|---|---|
| `x = +0.0` | `* -1` | `+-0.0` (both parsers reject) | `-0.0` (both accept, signbit set) |
| `x = -0.0` | `* 1` | `+-0.0` (reject) | `-0.0` (accept) |
| `x = -1e-200` | `* 1e-200` (underflow) | `+-0.0` (reject) | `-0.0` (accept) |
| `x = +0` | `/ -1` (Integer) | `+-0.0` (reject) | `-0.0` (accept) |
| `x = +1.0` | `* nan` | `nan` | `nan` (unchanged) |
| `x = +inf` | `* -1` | `-inf` | `-inf` (unchanged) |
| `x = +0.0` | `* -1 * -1` | `+0.0` | `+0.0` (unchanged) |
| `[t]\nx = +0.0  # c` | `*= -1` | `x = +-0.0  # c` | `x = -0.0  # c` (comment kept) |
| `a = [+0.0, 1]` | `a[0] *= -1` | `[+-0.0, 1]` | `[-0.0, 1]` |

Base and fixed differ only on the rows where base produced unparseable `+-0.0`. NaN, +/-inf and positive results are byte-identical. Note `+1.0 * nan` renders `nan` (no plus), as PR.md says; the PR's claim "Results other than negative zero render as before" held for every non-zero case I ran. I did not run other NaN-sign patterns (e.g. `-nan` from a signed NaN source).

## Result
| red | green | revert | suite | repro | edge cases | verdict |
|---|---|---|---|---|---|---|
| FAIL (as claimed) | PASS | FAIL (as claimed) | 1069 passed | exit 0, 0 doubled signs | 9 run, only the bug rows changed | PASS |

## After reading CONFIRMATION.md
Consistent with my runs. The confirmer's note that `not raw.startswith("-")` alone would also change NaN-on-signed-source from `nan` to `+nan` is accurate in reasoning (NaN >= 0 is False, so the existing `result >= 0` clause is what keeps NaN unchanged); the shipped three-clause condition leaves it as `nan`, which my E2 row confirms. I did not read dup-search.out or pr-ref-scan.md (outside my charter's needs).
