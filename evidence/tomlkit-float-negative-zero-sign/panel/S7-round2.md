# S7 round 2: SHIP (high)

Scope: citations. Every factual claim in the amended commit message (d59cfe9) and the new PR.md, run on base (items.py at HEAD~1) and fixed, in my copy /work/t2/scratch/panel2-tomlkit-float-negative-zero-sign-S7. I did not read panel/ files.

Round-1 findings in my charter: not read (told not to). Re-checked from scratch instead; the claims that changed are the repro, the commit-message example and the dropped paragraphs.

Claims checked (all TRUE unless noted)
1. Repro `doc = parse("x = -1.5"); doc["x"] *= 0`. Base: `'x = +-0.0'`. Fixed: `'x = -0.0'`. Matches the PR comment "actual: x = +-0.0, expected: x = -0.0".
2. `tomlkit.parse(doc.as_string())` on the base output raises `InvalidNumberError Invalid number at line 1 col 9`. Verbatim match with the PR text.
3. "`Float._new` (`tomlkit/items.py:879`) adds `+` when `self._sign and result >= 0`". `git show 0518af2:tomlkit/items.py` puts `if self._sign and result >= 0:` at line 879 (def at 876). True of base. On the fixed tree the same `if` is line 880 because of the new comment, which is fine for a PR against master. The round-0 qualifier "on master 0518af2" was dropped, so the number is now unanchored. Optional: restore "on master". Not required.
4. "`-0.0 >= 0` is `True`, and `str(-0.0)` is already `"-0.0"`". Run: `-0.0 True -0.0`.
5. "This is the line #345 changed for #341". `git show bf01a25` (title "fix: don't add sign if the float is negative (#345)", body "Fix #341") rewrote exactly `if self._sign and result >= 0: raw = f"+{raw}"`. True. "negative zero is the case that change left open" is fair: the pre-#345 code also wrote `+-0.0` (sign "+" because -0.0 >= 0), so #345 did not introduce it and did not cover it.
6. "A signed integer reaches the same line through true division (`n = +0`, then `doc["n"] /= -1`)". Base: `'n = +-0.0'`; fixed: `'n = -0.0'`. Code path: `Integer.__truediv__` calls `Float._new(self, result)` (items.py:835), and Integer sets `_sign` from the leading sign (items.py:631). True.
7. "Negative zero is the only value that is `>= 0` and prints with a leading `-`, so no other result renders differently." Checked: nan is `>= 0` False (so never took the `+` branch), inf prints `inf`, finite non-negative floats print without `-`. Also ran on fixed: `+1.0*-1` -> `-1.0`, `-1.5*-1` -> `+1.5`, `+1.0*nan` -> `nan`, `-0.0*1` -> `-0.0` (unsigned `1.5*0*-1` -> `-0.0`). Only the former `+-0.0` outputs differ. Claim is true; it is an argument by case analysis, and I confirmed the cases above rather than a sweep.
8. Commit message: "'a = -1.5' times 0 was written as 'a = +-0.0', which tomlkit's own parser rejects". True (items 1 and 2). "Add the '+' only when str(result) does not already start with '-'" matches the source line `and not raw.startswith("-")`.
9. Source comment `# -0.0 >= 0 is True, but str(-0.0) already carries its sign.` True (item 4).
10. Test: the new test passes on fixed. Full suite on fixed: `1069 passed in 1.37s`. Test steps match the claims: `-1.5 *0` -> `-0.0`, then `*-1` -> `+0.0`, then `+0 /-1` -> `-0.0`. The comment "Integer true division also goes through Float._new." is true (item 6).
11. Agent Drafting Metadata: Agent / Model / Notes lines are statements about provenance, not code. Not verifiable from the packet or repo (the three model names, "I reviewed the change", "The agent also drafted the test, the fix and this text"). They are the operator's to confirm. Notes line is consistent with the commit message sentence.

Things removed since round 0 that no longer need citations: the spec quote, the ABNF `dec-int` line, the "ran nan/inf/..." list and the pass count. The spec sentence is verbatim in reference_docs (toml-spec-1.1.0__toml.md:517) if anyone wants it back; nothing in the current text depends on it.

New problems in the revision: none. The amended commit differs from rev0 only in the test's first input (`-1.5` times `0`), the removed history comment, the added Integer-block comment, and the commit-message example. No unverifiable or wrong sentence remains.

Not checked: whether the model names or the "I reviewed the change" statement are accurate; whether #341 as an issue page says what the commit title implies (I used the commit message only, no web fetch); the wider fuzz sweep (others did it).

Optional wording (no change required): in the PR second paragraph, "`tomlkit/items.py:879`" could read "`tomlkit/items.py:879` on master".
