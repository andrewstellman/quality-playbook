# Panel synthesis: marshmallow-url-relative-scheme (BUG-005)

Full panel of 15 ran, all on Sonnet. All 15 files exist in `panel/` and carry a verdict. No REJECT, no DROP.

| Item | A | B | O1 | O2 | O3 | O4 | O5 | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| marshmallow-url-relative-scheme | S | S | F | S | S | F | F | F | F | F | F | F | S | S | F |

S = SHIP, F = FIX-REQUIRED, R = REJECT, D = DROP, – = not run.

Both executors reproduced red (fails at `validate.py:228`), green (222 in the file), revert (fails again), suite (1191 passed) and the confirmer's repro. Differential runs by EXEC-B, O2, O3 and S4 found no `relative=False` change and no accepted-to-rejected change. Nobody found a code defect. The findings are about the test, the text and two operator checks.

## Findings that must change

1. **Test is off-style and partly redundant** (O5, S1, S2, S3, S4; EXEC-A and EXEC-B called it optional). The `for` loop hides which URL failed, `..._in_query` is wrong for the fragment case, and the `ws://test.test` assertion repeats `test_url_relative_and_custom_schemes` (tests/test_validate.py:262-270). Change: drop the new function and add `"/redirect?to=http://example.com"` and `"/a#http://x.y"` to the `test_url_relative_valid` parametrize list (S1, S3, S4). Then re-run red, green, revert and the suite, and refresh the logs and counts.
2. **PR.md does not state the behaviour change** (O1, O4, S2, S3, S5, S8; O2, EXEC-A, EXEC-B, S6, S7 noted it as undisclosed). With `relative=True`, values with `://` after the first `/`, `?` or `#` were rejected and are now accepted, and `schemes` is no longer consulted for them. `relative=False` is unchanged (run by six reviewers). Affected: users of `URL(relative=True)` who relied on the rejection as a rough guard on redirect-style fields. Likelihood low: `//host/x` and the percent-encoded form were already accepted. Add one or two plain sentences, only with claims that were run (EXEC-A ran `//host/x` on base). Keep it a correctness text, no security framing.
3. **"Documentation relied on" paragraph overstates** (O1, O4, O5, S3, S7; S8 optional). The docstring "Whether to allow relative URLs." (`validate.py:91`) says nothing about `://`. Replace with a sentence saying so and that the argument rests on the regex already accepting these values. Drop "shown on the API reference page" (not checked, S3, S7).
4. **PR.md and commit body restate the diff** (O5, S3). Drop "around line 225" and "The fix treats ...". Commit body: one cause sentence, for example `With relative=True, "/redirect?to=http://example.com" was rejected because "/redirect?to=http" was checked as a scheme.`
5. **Suite count in PR.md** (S1, S3). Re-run after finding 1 and paste the real number, not 1191.
6. **CHANGELOG wording** (O1, O5, S1, S3, S5). Use the "Fix ... rejecting ..." shape of neighbouring bullets and the `Name <marshmallow.x>` cross-reference form (O1). Keep "path, query or fragment" (S3).
7. **Operator checks before submitting** (O1, O4, O5, S1, S4, S7, S8, EXEC-A, EXEC-B and others). Replace the `NNNN` placeholder after the PR is opened. Confirm `andrewstellman` is the real GitHub handle in `AUTHORS.rst` and the changelog, or drop the AUTHORS hunk and the "Thanks" line (S8). Move the placeholder note out of the PR body into the operator checklist (O5).

## Not adopted

- Add `relative=False`, `relative=True, absolute=False`, custom-schemes and `foo/bar://x` cases (S2, S4, S5, O4, O1): minimal-change rule. Behaviour was checked by runs in this panel; the one-test limit stands.
- Add a comment above the changed `if`, rename `candidate` (S1): O5, S3 and O1 judged the code fine as written, and the project's code has sparse comments. Skip.
- Switch the example to `/search?q=...` (O2): optional, and the changed examples would need new red/green logs for no gain beyond finding 1's rerun. Left to the operator.
- Regex or `isalnum` micro-optimisation (S6): about 1 to 3 microseconds per call, not worth the churn.
- Percent-encoding workaround and "strict check is a safety feature" pushback (O4, O1, EXEC-B, O3): a maintainer judgement, not a defect. No upstream PR or commit declining it was found in the local clone. The issue tracker was not searched (unreachable), so duplicates are unchecked. O4 said to DROP only if the operator is not comfortable with the disclosure sentence in finding 2; that is the operator's call, not a panel DROP.
- Non-str input raising AttributeError instead of TypeError (O3): both were non-ValidationError crashes before, no practical change.

## Outcome

REVISE: text and test changes only, then a focused re-review by both executors and the reviewers who flagged items.

## Round 2

Round 1 is kept in `rev0/`. Code revision by one fresh Sonnet fixer (commit amended to 9903cb71, still one commit, author Andrew Stellman, no trailers). Patch regenerated; `git am` on a clean clone of 1c63bdaf gives tree d0d705ac, the same as HEAD of the fixed clone (checked by me, EXEC-A and EXEC-B). Logs rewritten: red `2 failed` (validate.py:228), green `223 passed`, revert `2 failed, 221 passed`, suite `1192 passed`.

What changed, by finding:
1. Test: standalone function deleted; `"/redirect?to=http://example.com"` and `"/a#http://x.y"` added to `test_url_relative_valid`.
2. Behaviour change: PR.md now says that with `relative=True` such values were rejected and are accepted, `schemes` is not consulted for them, `//host/x` was already accepted, and `relative=False` is unchanged. Each claim was run on base and fix by me (`/work/pilot/scratch/rev2-marshmallow-url-relative-scheme-parent/t.py`) and by the executors. No security framing.
3. Docs paragraph: now quotes `validate.py:91`, says it does not mention "://", and says the argument rests on the regex. "API reference page" removed.
4. PR.md "line 225" and "The fix treats ..." removed. Commit body is the one cause sentence suggested.
5. Suite count: 1192, from a real run.
6. CHANGELOG: "Fix `URL <marshmallow.validate.URL>` ... rejecting ..." shape, "path, query or fragment" kept.
7. AUTHORS.rst hunk and "Thanks :user:" line dropped: the GitHub handle cannot be verified from here, and the maintainer usually adds names afterwards (POLICY.md). The placeholder note left PR.md and is on the checklist below.

Not adopted, same reasons as round 1: extra reject, `relative=False`, `absolute=False` and custom-schemes test cases; a comment above the `if`; renaming `candidate`; `/search?q=` example; micro-optimisation. S1 and S4 accepted these omissions in round 2. Optional nits left alone: the title says "path or query" while the CHANGELOG also names fragment; "Adds two cases" in PR.md names the test change. One late text edit after the re-review: "the six inputs I tried" in PR.md was replaced by the named inputs (run by me, all rejected before and after with `relative=False`).

Re-review row (round 2):

| Item | EXEC-A | EXEC-B | O1 | O4 | O5 | S1 | S2 | S3 | S4 | S5 | S8 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| marshmallow-url-relative-scheme | S | S | S | S | S | S | S | S | S | S | S |

S7 gave SHIP in round 1 and was not re-run; its two text findings (docs paragraph, "API reference page") are fixed.

Operator checklist before submitting:
- Open the PR, then replace `NNNN` in `CHANGELOG.rst` with the real number and amend the commit. Do not push with `NNNN`.
- If wanted, add yourself to `AUTHORS.rst` with your real GitHub handle and add a "Thanks :user:`handle` for the PR." line. Both were removed.
- Issue tracker and duplicates were not searched (unreachable). A maintainer may prefer to keep the old strict rejection; percent-encoding already works as a workaround.

## Outcome (round 2)

SHIP
