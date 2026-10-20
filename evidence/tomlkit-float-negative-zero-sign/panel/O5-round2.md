# O5 round 2: SHIP (high)

Role: slop (A). Commit reviewed: d59cfe9 on base 0518af2. Copies: `/work/t2/scratch/panel2-tomlkit-float-negative-zero-sign-O5` (fixed) and `...-O5-base` (HEAD~1). I did not read any `panel/` file, including my own round-1 file; the round-1 findings below are taken from SYNTHESIS.md.

## 1. Round-1 findings in my charter: fixed or not

| Round-1 finding | Status | How I checked |
|---|---|---|
| Summary about twice the length of neighbouring merged fixes | Fixed | Counted: Summary is 146 words with the code block, 114 without (rev0: 239 / 207). Merged neighbours fetched today: #612 about 93, #613 about 91, #623 about 54, #591 far longer (several sections). The counts for the neighbours come from the fetch tool's summary, not a byte count. |
| Repro looks contrived (`+0.0` times `-1`) | Fixed | Now `x = -1.5`, `*= 0`. Ran it on base and fixed (output below). |
| Notes line says the same thing twice; tool name and URL repeated | Mostly fixed | URL gone, second sentence no longer repeats "reviewed". "Quality Playbook" and "Claude" still appear in Notes right under the Agent and Model lines that name them. Optional rewrite in finding 1. |
| Model line cannot be checked from the packet | Shortened, still not checkable from the packet | SYNTHESIS.md says "REVIEW.md says where they come from". `find /work/t2 -name 'REVIEW*'` returns nothing. See finding 3. |
| Test comment narrates history ("used to render") | Fixed | `diff rev0/0001-*.patch 0001-*.patch` shows the comment removed and one new comment, `# Integer true division also goes through Float._new.`, which is true (`tomlkit/items.py:836`, `return Float._new(self, result)`). |

## 2. What I ran

PR repro, copied verbatim plus the integer line from the text (`repro_pr.py` in my copy):
```
--- base
x = +-0.0
InvalidNumberError: Invalid number at line 1 col 9
n = +-0.0 Float
--- fixed
x = -0.0
parsed ok
n = -0.0 Float
```
Patch against clean base: `git apply --check` passed, and `git diff --quiet d59cfe9` after applying exited 0 (the applied tree is identical to HEAD of the fixed clone).
Red (test part only on base, whole `tests/test_items.py`): `E       AssertionError: assert 'a = +-0.0' == 'a = -0.0'`, `1 failed, 100 passed in 0.30s`.
Suite on fixed: `1069 passed in 1.41s`. Lint on the two files: `All checks passed!` and `2 files already formatted`.

"Negative zero is the only value that is `>= 0` and prints with a leading `-`, so no other result renders differently": my own sweep (`sweep.py`: 25 source literals, 7 binary operators in both directions against 20 operands, 7 unary operations), base against fixed:
```
7175 cases
differing: 270
Counter({('x = +-0.0', 'x = -0.0'): 270})
base outputs containing '+-': 270
fixed outputs containing '+-': Counter()
```
First sentence of the Summary ("Arithmetic on a float written with an explicit sign renders `+-0.0` when the result is negative zero"): in the sweep, all 263 cases with a signed float source and a `-0.0` result on fixed were `+-0.0` on base. No exception found.
"This is the line #345 changed for #341": `git blame -L 876,881` gives bf01a25e for lines 879-880, subject `fix: don't add sign if the float is negative (#345)`, body `Fix #341`. The old code was `sign = "+" if result >= 0 else "-"; raw = sign + raw`, so negative zero was wrong before #345 too and "left open" is the accurate wording.
`tomlkit/items.py:879` is the right line on base (it is 880 after the fix, which is what a reader of master expects).
Commit message example (`"a = -1.5"` times 0 written as `"a = +-0.0"`): matches the red output above.

## 3. Sentence-by-sentence read of the new PR.md

No sentence makes a claim I could not reproduce. Nothing restates the diff beyond one sentence ("The fix adds the `+` only when ..."), which the next sentence needs. No spec quote, no pass count, no list of unchanged cases, no em dashes, no bold, no bullet padding. Title matches the commit subject and the unprefixed imperative style of #591, #612, #613 and #623. The patch touches two files and nothing unrelated. The test reads like its neighbour `test_no_extra_minus_sign` and has one comment, which is true.

## Findings

1. Optional, not blocking. Notes repeats the tool and the model named on the two lines above it. If the operator keeps the file as drafted, this says the same thing once:
   - Current: `- Notes: Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change. The agent also drafted the test, the fix and this text.`
   - Proposed: `- Notes: Quality Playbook is an AI code-review tool. It found the bug and drafted the test, the fix and this text, and I reviewed the change.`
   If the operator's rule is that the disclosure sentence appears verbatim in the PR body as well as in the commit, keep the current line. It is accurate and short enough.

2. Optional, not blocking. The last line of the commit message is 86 characters and the rest of the body is wrapped at 71 or less. Wrapped form:
   ```
   Found by Quality Playbook, an AI code-review tool, with Claude; I
   reviewed the change.
   ```
   The project squash-merges, so this line is unlikely to survive in history either way.

3. Packet, not PR text. SYNTHESIS.md points twice to `REVIEW.md` (for where the model names come from, and for the instruction that the operator rewrites the Summary and then changes the Notes line). That file does not exist under `/work/t2`. As drafted, Notes says the agent wrote "this text", which is true of the file today and is the same disclosure merged PR #623 carried ("Drafted the patch, regression tests, and PR description."). If the operator rewrites the Summary in his own words, as POLICY.md's reading of the maintainer's comment in #574 asks, the Notes line must change with it or it becomes false. Text for that case:
   `- Notes: Found by Quality Playbook, an AI code-review tool, with Claude. The agent drafted the test and the fix. I reviewed the change and wrote this summary.`
   Use it only if he did write it.

## Side-effect rule

The text now lists one behaviour change: a result that rendered `+-0.0` renders `-0.0`. The old output could not be parsed by tomlkit (ran it) or, per CONFIRMATION.md, by tomllib, so nobody can be relying on it in a file that is read back. My sweep found no other output that differs. Nobody is hurt. Not a DROP.

## Not checked

- The PR bodies of #591, #612, #613 and #623 byte for byte (fetch-tool summaries only).
- The model names on the Model line (no source for them in the packet; the scratch tree has directories named `claude-fable-5-1`, `claude-opus-5-5` and `claude-sonnet-5-5`, which is consistent but is not evidence of who did what).
- Python versions other than the venv's.
- `Integer.__pow__` with a negative exponent still writes `+-0.0` on fixed (`n = -3`, `**= -1001` gives `'n = +-0.0'`, ran it). SYNTHESIS.md lists this as known and left out, and no sentence in PR.md or the commit message claims it is fixed.
