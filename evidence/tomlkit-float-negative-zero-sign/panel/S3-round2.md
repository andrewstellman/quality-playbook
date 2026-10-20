# S3 round 2: SHIP (high)

Scope: slop (B). Fresh copy at /work/t2/scratch/panel2-tomlkit-float-negative-zero-sign-S3 (HEAD d59cfe9, base 0518af2). Did not read panel/ files.

Round-1 findings in my charter, checked by reading and running:
1. Summary length: fixed. Now three short paragraphs plus a 5-line repro. The "results render as before" list, pass count and spec paragraph are gone. The cause and fix are no longer split into separate headings.
2. Contrived repro: fixed. PR.md uses `x = -1.5` then `doc["x"] *= 0`. Run on base: `'x = +-0.0'`, then `InvalidNumberError Invalid number at line 1 col 9`. Run on fixed: `'x = -0.0'`, parses back.
3. Notes line: fixed. One sentence pair, no URL, no repeated tool name.
4. Model line: shortened to three names. I cannot verify the names from the packet (unchanged from round 1, left to the operator).
5. Test narration: the "used to render" comment is gone. The test now starts from `a = -1.5` times 0, matching the PR. The only comments are the one on the Integer block and the one on the source line.

Behavioural claims in the new PR.md and commit message, each run:
- "`Float._new` (`tomlkit/items.py:879`) adds `+` when `self._sign and result >= 0`": true on base, where line 879 is the `if` line. After the fix the `if` moves to line 880 because of the new comment. That is fine for a PR text describing the base.
- "-0.0 >= 0 is True, str(-0.0) is '-0.0'": true.
- "the line #345 changed for #341": `git show bf01a25` is "fix: don't add sign if the float is negative (#345)" with body "Fix #341", and it introduced `if self._sign and result >= 0:`. True.
- "A signed integer reaches the same line through true division (`n = +0`, then `doc["n"] /= -1`)": base gives `'n = +-0.0'` and the same InvalidNumberError, fixed gives `'n = -0.0'`. True.
- "Negative zero is the only value that is >= 0 and prints with a leading '-'": checked 0.0, -0.0, 1.5, inf, -inf, nan, -nan, 1e-320. Only -0.0 matches. (nan >= 0 is False.) True for floats.
- Commit message: "'a = -1.5' times 0 was written as 'a = +-0.0'": true on base.

Slop findings on the revision (all optional, none blocks):
1. The Summary's first sentence and the commit body both say the output is unparseable; the comment above the source line says the same a third time in different words. Acceptable at this size. If the operator wants one cut, cut nothing from the PR and leave the commit body as is.
2. The disclosure sentence "Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change." appears in the commit and again in the PR Notes. This is intentional per the operator's rule (no trailers) and is not padding.
3. Test: three asserts after the first (`*= -1` back to `+0.0`, and the Integer block). S4 and S2 already judged more cases padding; I agree this is the right size.

Text is proportionate to a one-line fix: the PR is about 150 words plus the repro, no restated diff, no pass-count, no spec paragraph, no unrelated changes. I found no claim beyond the evidence.

Side-effect rule: the only output that changes was `+-0.0`, which the library could not read back. Nobody relying on old behaviour is hurt.

Not checked: full suite and lint (executors' charter); the model names in the Model line.
