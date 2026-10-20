# tomlkit: arithmetic on a signed float can write `+-0.0`, which tomlkit cannot read back

Status: **submitted as a draft PR by the operator: https://github.com/python-poetry/tomlkit/pull/629** (updated 2026-10-03)

## The project

tomlkit (https://github.com/python-poetry/tomlkit) is a Python TOML library that keeps a file's layout and comments when a program edits it. Poetry and other tools use it to rewrite `pyproject.toml`.

## The bug

- **Expected:** a float has at most one sign. TOML 1.1.0, section "Float": "Float values `-0.0` and `+0.0` are valid and should map according to IEEE 754." (`reference_docs/cite/toml-spec-1.1.0__toml.md:517`). The grammar allows one optional sign: `dec-int = [ minus / plus ] unsigned-dec-int` (`toml-spec-1.1.0__toml.abnf.txt:134`).
- **Actual:** when a value was written with an explicit sign and arithmetic on it gives negative zero, tomlkit writes `+-0.0`. Run on master 0518af2:
  ```python
  doc = tomlkit.parse("x = -1.5")
  doc["x"] *= 0
  doc.as_string()                 # 'x = +-0.0'
  tomlkit.parse(doc.as_string())  # InvalidNumberError: Invalid number at line 1 col 9
  ```
  Python's `tomllib` rejects the output too (`TOMLDecodeError`).
- **Cause:** `Float._new` (`tomlkit/items.py:879`) adds `+` when `self._sign and result >= 0`. `-0.0 >= 0` is `True`, and `str(-0.0)` already starts with `-`.
- **Why it went unnoticed:** the maintainer fixed doubled signs on this same line in 2024 (commit bf01a25, PR #345, "Fix #341") and added `test_no_extra_minus_sign` the next day (c2611c5). That test uses `-1` and `-1.5`. No test builds a negative zero from a signed value.
- **How often:** the source value needs an explicit `+` or `-` (every negative number has one) and the result must be negative zero. Examples that reach it: `-1.5 * 0`, `round(-0.4)`, `-0.0 * 2`, `+0.0 * -1`, signed integer `+0 / -1`. Severity LOW.

## The fix

One condition in `Float._new`: add the `+` only when the text does not already start with `-`. `result >= 0` stays, because without it a NaN result on a signed value would change from `nan` to `+nan` (two reviewers ran that alternative).

```diff
diff --git a/tests/test_items.py b/tests/test_items.py
index cf6134a..e814b5f 100644
--- a/tests/test_items.py
+++ b/tests/test_items.py
@@ -1451,6 +1451,19 @@ def test_no_extra_minus_sign() -> None:
     assert doc.as_string() == "a = -1.5"
 
 
+def test_no_extra_plus_sign_on_negative_zero() -> None:
+    doc = parse("a = -1.5")
+    doc["a"] *= 0
+    assert doc.as_string() == "a = -0.0"
+    doc["a"] *= -1
+    assert doc.as_string() == "a = +0.0"
+
+    # Integer true division also goes through Float._new.
+    doc = parse("a = +0")
+    doc["a"] /= -1
+    assert doc.as_string() == "a = -0.0"
+
+
 def test_serialize_table_with_dotted_key() -> None:
     child = api.table()
     child.add(api.key(("b", "c")), 1)
diff --git a/tomlkit/items.py b/tomlkit/items.py
index 8589df9..db151f7 100644
--- a/tomlkit/items.py
+++ b/tomlkit/items.py
@@ -876,7 +876,8 @@ class Float(Item, _CustomFloat):
     def _new(self, result: float) -> Float:
         raw = str(result)
 
-        if self._sign and result >= 0:
+        # -0.0 >= 0 is True, but str(-0.0) already carries its sign.
+        if self._sign and result >= 0 and not raw.startswith("-"):
             raw = f"+{raw}"
 
         return Float(result, self._trivia, raw)
```

## Regression test

`tests/test_items.py::test_no_extra_plus_sign_on_negative_zero`, placed right after the maintainer's `test_no_extra_minus_sign`.

- Red (test added, source as on master): `AssertionError: assert 'a = +-0.0' == 'a = -0.0'`, `1 failed, 100 deselected`
- Green: `tests/test_items.py` gives `101 passed`; full suite `1069 passed` (1068 on master plus the new test)
- Revert (source change removed, test kept): `1 failed, 100 passed`, same assertion
- Lint: `ruff check` gives `All checks passed!`; `ruff format --check` gives `2 files already formatted` (ruff 0.16.9, the version the project pins)
- Logs: `red.log`, `green.log`, `revert.log`, `suite.log`, `lint.log` (re-run by the orchestrating session on the final commit; both panel executors repeated the sequence independently)

## Knock-on effects (run 2026-10-02)

- **Callers of the changed code:** every arithmetic method of `Float` (`tomlkit/items.py:890-988`: abs, add, sub, mul, truediv, floordiv, mod, pow, neg, pos, round and their reflected forms) and `Integer.__truediv__` / `__rtruediv__` (`items.py:830`, `836`). Parsing and `as_string()` do not call it.
- **Before and after on ordinary inputs** (run by the orchestrating session on master and on the fix; each output re-read with tomlkit and tomllib):

  | Operation | master | with the fix |
  |---|---|---|
  | `x = -1.5`, `* 0` | `x = +-0.0` (both parsers reject) | `x = -0.0` |
  | `x = +0.0`, `* -1` | `x = +-0.0` (both reject) | `x = -0.0` |
  | `x = -0.0`, `* 2` | `x = +-0.0` (both reject) | `x = -0.0` |
  | `x = -0.4`, `round()` | `x = +-0.0` (both reject) | `x = -0.0` |
  | `x = +0`, `/ -1` (integer) | `x = +-0.0` (both reject) | `x = -0.0` |
  | `x = +1.0`, `* nan` | `x = nan` | `x = nan` |
  | `x = +1.0`, `* inf` | `x = +inf` | `x = +inf` |
  | `x = -1.5`, `* -1` | `x = +1.5` | `x = +1.5` |
  | `x = +0.0`, `+ 0.0` | `x = +0.0` | `x = +0.0` |
  | `x = 0.0` (unsigned), `* -1` | `x = -0.0` | `x = -0.0` |

- **Wider sweeps by reviewers:** 7,540 operation cases (369 differ), 3,960 (148 differ) and 7,175 (270 differ). In all three, every differing case is `+-0.0` becoming `-0.0`, and the set of cases that raise is identical.
- **Behaviour changes for existing users:** one. Output that was `+-0.0` is now `-0.0`. The old output could not be read by tomlkit or tomllib, so no working program depends on it. Judged acceptable under the side-effect rule by every reviewer who looked (O1 to O5, S5); no DROP.
- **Not fixed by this change, on purpose:** `Integer.__pow__` with a negative exponent that underflows (for example `n = -10`, `**= -401`) still writes `+-0.0` through `Integer._new`. It is a different defect (an Integer item holding a float) and the PR text makes no claim about it. If the maintainer asks, that is the answer.

## Review history

- Found by: Quality Playbook 1.6.1 run on tomlkit 0518af2, Council of Three spec audit (the Fable council member), BUG-022. Challenge gate: two rounds, both CONFIRMED at LOW.
- Confirmed: `CONFIRMATION.md` (fresh Opus confirmer; 7 of 10 cases wrote `+-0.0`).
- Duplicate search: the operator ran `dup-search.sh` on 2026-10-02T22:19Z (0 failed queries, no hit about a float's sign). The orchestrating session scanned all 364 pull-request heads: only #345, the original #341 fix, touches this condition (`../pr-ref-scan.md`). An open issue with no PR is still possible; one reviewer noted the search query `float sign invalid number` did not return #341 itself, so an empty search is weak evidence.
- Panel: `SYNTHESIS.md` (roster: full, 15 reviewers). Round 1: 11 SHIP, 4 FIX-REQUIRED, all four about the PR text or test comments. No REJECT, no DROP.
- Re-review after the revision: executors A and B, O5, S2, S3, S7. All SHIP.
- Text fixes applied: summary cut from 239 to about 150 words; repro changed to `-1.5 * 0`; spec paragraph, pass count and "renders as before" list removed; Notes line shortened; "on master" added to the line reference.
- Code revision (re-reviewed): test now starts from `a = -1.5` times `0`; history comment removed; comment added on the integer block; commit message example updated. Final commit d59cfe9.
- Upstream check (2026-10-02): `master` at 0518af253901e57872c03835db6fe9bacab40ee7; patch applies cleanly with `git am`: yes (resulting tree 860e0eb, identical to the reviewed tree).

## Things to know before submitting

1. **Rewrite the Summary in your own words first.** In issue #574 the maintainer wrote (as quoted by the fetch tool, not checked byte for byte): "the summary and reply must come from a human." The Summary in `PR.md` was drafted by the agent, and the Notes line says so. The facts in it are checked; the sentences should be yours. Edit `PR.md` in this folder; `submit.sh` sends that file as the PR body.
2. **Then change the Notes line so it is still true.** Suggested: `- Notes: Found by Quality Playbook, an AI code-review tool, with Claude. The agent drafted the test and the fix. I reviewed the change and wrote this summary.`
3. **"I reviewed the change" is your statement.** It is in the commit message and in the Notes line. Read the diff above before you run the script.
4. **Model line.** The names are the model aliases this session was configured with (the Council member that found the bug ran as `claude-fable-5-1`, the confirmer, fixer and O-reviewers as `claude-opus-5-5`, phase workers and S-reviewers as `claude-sonnet-5-5`). The session cannot prove which model served each call. Shorten the line if you prefer.
5. **Related upstream items:** #341 / #345 (the earlier doubled-sign fix on this line; the PR text mentions them without "Fixes"). #346 (doubled minus on integers, fixed in 990e325). No open PR touches `Float._new`. PR #628 adds an unrelated parser test that contains `-0.0`.
6. **No CLA, no DCO, no changelog line.** The four fixes merged since 0.15.1 each changed one source file and one test file.
7. **Not run here:** Python 3.9 to 3.12 and 3.14, macOS and Windows (the project's CI covers them; this sandbox has 3.13 on Linux). The change uses only `str.startswith`.
8. **Likely pushback:** "too niche" (answer: same class as #341 and #346, which were fixed, and the output is unreadable); "why keep `result >= 0`" (answer: it keeps a NaN result as `nan`).
9. **Maintainer load.** He has said most incoming PRs are AI-authored and review is the bottleneck. This PR is two files and 15 added lines.

## The PR as it will be submitted

**Title:** Do not add a plus sign to a negative zero float result

> ## Summary
>
> Arithmetic on a float written with an explicit sign renders `+-0.0` when the result is negative zero, and tomlkit cannot parse that output.
>
> ```python
> import tomlkit
>
> doc = tomlkit.parse("x = -1.5")
> doc["x"] *= 0
> print(doc.as_string())          # actual: x = +-0.0    expected: x = -0.0
> tomlkit.parse(doc.as_string())  # InvalidNumberError: Invalid number at line 1 col 9
> ```
>
> `Float._new` (`tomlkit/items.py:879` on master) adds `+` when `self._sign and result >= 0`. `-0.0 >= 0` is `True`, and `str(-0.0)` is already `"-0.0"`. This is the line #345 changed for #341, and negative zero is the case that change left open. A signed integer reaches the same line through true division (`n = +0`, then `doc["n"] /= -1`).
>
> The fix adds the `+` only when `str(result)` does not already start with `-`. Negative zero is the only value that is `>= 0` and prints with a leading `-`, so no other result renders differently.
>
> ## Agent Drafting Metadata
>
> - Agent: Quality Playbook, run with Claude Code
> - Model: Claude Fable 5.1, Claude Opus 5.5 and Claude Sonnet 5.5
> - Notes: Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change. The agent also drafted the test, the fix and this text.

(The body is `PR.md` as it stands now. If you rewrite it, what you submit is your version.)

## To submit

    bash ~/Documents/QPB/harness_runs/cloud-tomlkit-2026-10-02/upstream/tomlkit-float-negative-zero-sign/submit.sh

What the script does: checks `gh` is logged in as `andrewstellman` (it stops if the login differs); forks python-poetry/tomlkit if you have no fork; clones your fork to `~/src/pr-work/tomlkit` if it is not there; fetches upstream `master`; creates branch `fix-float-negative-zero-sign` (it refuses if the branch exists); applies the patch with `git am`; pushes the branch to your fork; opens a **draft** pull request with the title above and `PR.md` as the body; prints the URL.

What it does not do: it does not run the tests locally (no test command is set; they were run here, and the project's CI runs on the PR), it does not mark the PR ready, and it does not comment or merge. Marking it ready is yours to do in the web UI.

## Submission record

- **Submitted:** 2026-10-02 20:36 -04:00 by the operator, with `submit.sh`. He replied "reviewed" before pasting the script output.
- **PR:** https://github.com/python-poetry/tomlkit/pull/629 (number 629), draft, title "Do not add a plus sign to a negative zero float result", base `python-poetry:master`, head `andrewstellman:fix-float-negative-zero-sign`.
- **Head commit:** a62fe9194df6dc87b101c83e321b484b4af25faa, one commit on 0518af2. Author Andrew Stellman <andrew@stellman.com>; committer andrewstellman <astellman@stellman-greene.com> (`git am` on his machine). No trailers.
- **Diff verified (2026-10-03T00:37Z, by the orchestrating session, without gh):** fetched `refs/pull/629/head` with git. Its tree is 860e0ebf6c179cb48ce0bb8c64de4da6dca9f193, identical to the reviewed tree. `upstream_scripts.py --compare-diff` on the patch and `git diff master pr/629`: `MATCH: every file's blob hashes in the forge diff equal the patch's.`
- **Title and body verified (2026-10-03T00:43Z):** the operator ran `verify.sh 629`. `verify.pr.json`: title equal to the reviewed title; body equal to `PR.md` character for character (1,221 characters, no CR); `isDraft` true, state OPEN, head `fix-float-negative-zero-sign` at a62fe9194df6dc87b101c83e321b484b4af25faa. `upstream_scripts.py --compare-diff` on the patch and `verify.pr.diff`: `MATCH: every file's blob hashes in the forge diff equal the patch's.`
- **Summary authorship:** the Summary went up as drafted by the agent, and the Notes line says so ("The agent also drafted the test, the fix and this text."). The disclosure is accurate. The maintainer's stated preference (#574) is a summary written by a human; the description can still be edited while the PR is a draft.
- **Bot actions and CI:** none seen on the page by the fetch tool; CI status not checked.
- **Remaining on the operator's side:** decide whether to rewrite the Summary before marking the PR ready; mark it ready in the web UI; answer the maintainer himself.
- **Marked ready for review:** the operator reports doing this in the GitHub web UI on 2026-10-02 (about 21:50 -04:00). Not confirmed from the sandbox: a fetch of the PR page at 2026-10-03T01:58Z still showed "Draft", which may be a stale copy. `gh pr view 629 --repo python-poetry/tomlkit --json isDraft` is the exact check.
- **Ready for review confirmed (2026-10-04):** the operator ran `gh pr view 629 --repo python-poetry/tomlkit --json isDraft`; it printed `"isDraft": false`. The fetch-tool readings of "Draft" recorded above were wrong.
- **Maintainer responses:** none as of 2026-10-04; not merged (PR head not on master, checked by git).
