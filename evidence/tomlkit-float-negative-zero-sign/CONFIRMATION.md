# BUG-022: Arithmetic on a signed Float renders `+-0.0` when the result is negative zero

**Claim.** Input: a Float (or Integer, via true division) parsed with an explicit sign (`+0.0`, `-0.0`, `+5.0`, `+0`) on which arithmetic yields IEEE negative zero. Actual: `Float._new` (tomlkit/items.py:876-882) writes `+-0.0`. Expected: `-0.0`. Source of expected: TOML 1.1.0 allows one optional sign (abnf:134) and says `-0.0` is valid (toml.md:517); tomlkit's own parser rejects `+-0.0`.

**Verdict: CONFIRMED** on python-poetry/tomlkit @ 0518af2 (0.15.1), Python 3.13.15. tomlkit writes text that tomlkit and tomllib both refuse to parse.

**Repro** (`/work/t2/scratch/confirm-022/repro.py`, abridged: the full file adds a tomllib re-parse and 4 more cases). Run: `cd /work/t2/scratch/confirm-022 && PYTHONPATH=$PWD /work/t2/venv/bin/python repro.py`
```python
import tomlkit
CASES = [("x = +0.0", lambda v: -v), ("x = +5.0", lambda v: v * -0.0), ("x = -0.0", lambda v: v * 1),
         ("x = +0", lambda v: v / -1), ("x = 0.0", lambda v: -v), ("x = -1.5", lambda v: v * -1)]
bad = 0
for src, op in CASES:
    doc = tomlkit.parse(src); doc["x"] = op(doc["x"]); out = doc.as_string()
    bad += "+-" in out; print(repr(src), "->", repr(out))   # then tomlkit.parse(out), tomllib.loads(out)
raise SystemExit(1 if bad else 0)
```

**Output (verbatim, unpatched).**
```
BUG 'x = +0.0'       -x                         -> 'x = +-0.0'      | tomlkit: InvalidNumberError: Invalid number at line 1 col 9 | tomllib: TOMLDecodeError: Invalid value (at line 1, column 5)
BUG 'x = +5.0'       x * -0.0                   -> 'x = +-0.0'      | tomlkit: InvalidNumberError: Invalid number at line 1 col 9 | tomllib: TOMLDecodeError: Invalid value (at line 1, column 5)
BUG 'x = +5.0'       x / -inf                   -> 'x = +-0.0'      | tomlkit: InvalidNumberError: Invalid number at line 1 col 9 | tomllib: TOMLDecodeError: Invalid value (at line 1, column 5)
BUG 'x = -0.0'       x * 1                      -> 'x = +-0.0'      | tomlkit: InvalidNumberError: Invalid number at line 1 col 9 | tomllib: TOMLDecodeError: Invalid value (at line 1, column 5)
BUG 'x = -0.0'       +x                         -> 'x = +-0.0'      | tomlkit: InvalidNumberError: Invalid number at line 1 col 9 | tomllib: TOMLDecodeError: Invalid value (at line 1, column 5)
BUG 'x = -1e-200'    x * 1e-200                 -> 'x = +-0.0'      | tomlkit: InvalidNumberError: Invalid number at line 1 col 9 | tomllib: TOMLDecodeError: Invalid value (at line 1, column 5)
BUG 'x = +0'         x / -1 (Integer)           -> 'x = +-0.0'      | tomlkit: InvalidNumberError: Invalid number at line 1 col 9 | tomllib: TOMLDecodeError: Invalid value (at line 1, column 5)
ok  'x = 0.0'        -x (unsigned source)       -> 'x = -0.0'       | tomlkit: ok -0.0 signbit=True | tomllib: ok -0.0 signbit=True
ok  'x = +0.0'       x + 0.0 (positive zero)    -> 'x = +0.0'       | tomlkit: ok 0.0 signbit=False | tomllib: ok 0.0 signbit=False
ok  'x = -1.5'       x * -1                     -> 'x = +1.5'       | tomlkit: ok 1.5 signbit=False | tomllib: ok 1.5 signbit=False
tomlkit 0.15.1; 7 case(s) wrote a doubled sign
exit code: 1
```
With `quality/patches/BUG-022-fix.patch` applied in the scratch clone: all 10 lines `ok`, the 7 bug cases write `x = -0.0`, exit code 0, suite `1068 passed in 1.26s` (baseline `1068 passed in 1.32s`). Patch reverted afterwards; the clone holds only the untracked `repro.py`.

**Expectation check.**
- `grep -n "IEEE 754" cite/toml-spec-1.1.0__toml.md` gives `517:Float values `-0.0` and `+0.0` are valid and should map according to IEEE 754.`
- `grep -n "^dec-int\|^float-int-part" cite/toml-spec-1.1.0__toml.abnf.txt` gives `134:dec-int = [ minus / plus ] unsigned-dec-int` and `146:float-int-part = dec-int`. One optional sign, so `+-0.0` is not TOML.
- Cause: items.py:879 `if self._sign and result >= 0:`; `-0.0 >= 0` is True while `str(-0.0)` is `"-0.0"`. `git blame -L 876,881` puts lines 879-880 in bf01a25e (Frost Ming, 2024-05-07, "fix: don't add sign if the float is negative (#345)", "Fix #341"). That commit replaced `sign = "+" if result >= 0 else "-"; raw = sign + raw`, so the stated intent is one sign and negative zero is the case it missed.
- Not intentional: `grep -rn "\-0\.0\|negative zero\|copysign" tests/*.py` returns nothing. `test_no_extra_minus_sign` (tests/test_items.py:1438) pins `-1.5 * -1 -> +1.5` only; tests/test_items.py:742-745 pins `+34.12 + 1 -> +35.12` only. Both still pass with the fix.
- Correction to BUGS.md: the changelog line for #341 is CHANGELOG.md:116, not :114 (`grep -n "extra minus sign" CHANGELOG.md`).
- Upstream master: a WebFetch of raw `tomlkit/items.py` on master returned the same `if self._sign and result >= 0:` body, and the master CHANGELOG has no Unreleased entry on this. WebFetch output is a model summary, not raw text.

**Duplicate search.** None found for negative zero. Closest: issue #341 "Sign change when doing math gives invalid number" (`-3.1415 * -1` twice gave `--3.1415`; fixed in 0.12.5 by bf01a25 / PR #345; the page summary did not state open/closed, closed is inferred from the "Fix #341" commit and changelog). Also #346 (negative Integer cycling `+3`, `--3` when multiplied by -1; title not returned by the fetch; fixed by 990e325 "Fix #346"). Neither page mentions `-0.0`, zero, or `+-`. Same family, different input, so this is a follow-up to #341 and should cite it. Queries: WebSearch `tomlkit "+-0.0" float negative zero sign issue`; `site:github.com/python-poetry/tomlkit float sign "negative zero" OR "-0.0" OR "extra sign" OR "double sign"`; `site:github.com/python-poetry/tomlkit "InvalidNumberError" float sign after arithmetic`; `github python-poetry tomlkit pull Float "_new" sign zero "+-"`. WebFetch: issues #341, #346. Not checked: issue and PR listing pages, the open PR list (no query surfaced an open PR on this; that is not proof there is none), Discussions.

**dup queries**
- `negative zero float`
- `"+-0.0"`
- `float sign invalid number`
- `extra sign float arithmetic`
- `Float _new sign`
- `signed zero InvalidNumberError`

**Security angle:** no. Malformed output only from the caller's own arithmetic on an item; no injection, bypass, DoS or exposure.

**Likely maintainer pushback.**
- "Too niche": needs an explicitly signed source value and a negative-zero result. Fair, and LOW is right. The counter is that #341 and #346 were the same class and were fixed, and the result is unparseable output with no error at write time.
- Fix shape: they may prefer `if self._sign and not raw.startswith("-")` or `math.copysign(1.0, result) > 0` to the patch's three-clause condition. Note the first alternative also changes a NaN result on a signed source from `nan` to `+nan` (valid TOML, but a behaviour change); the shipped patch does not. I did not run either alternative.
- Whether `-0.0 * 1` on a parsed `-0.0` should keep `-0.0`: yes under toml.md:517, and the patch does.

---
**Addendum by the parent, 2026-10-02 (tracker search).** The operator ran `dup-search.sh` at 2026-10-02T22:19:21Z; `dup-search.out` has 24 query blocks, 0 `FAILED`. The parent also scanned all 364 pull-request heads (`pr-ref-scan.md`).
Hits for this bug: five of six queries returned nothing; the `"+-0.0"` query returned 30 issues and 30 PRs matched on loose tokens, none about a float's sign by title. The ref scan finds no pull request other than #345 (the original #341 fix) that touches the sign condition, and none that mentions negative zero for `Float._new`. Issue #341's open/closed state is not confirmed (one fetch summary says open; commit bf01a25 says "Fix #341" and CHANGELOG.md:116 lists it as fixed). No duplicate found. **Final verdict: CONFIRMED.**
