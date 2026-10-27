# marshmallow: URL validator rejects a relative URL that has "://" in its path, query or fragment

Status: **open and ready for review (marked ready by Andrew on 2026-10-05), [marshmallow-code/marshmallow#3067](https://github.com/marshmallow-code/marshmallow/pull/3067).** Submitted by Andrew on 2026-10-05; see the submission record at the end. Before that: On 2026-10-05 at 17:43 -04:00 Andrew answered the AI-policy question: "i read and understand the code, it's simple".

Who wrote what: this file, the fix, the test and the PR text were written by an unattended workflow of Claude Sonnet sessions (QPB 1.6.1). The section "Checks by the orchestrating session" was added afterwards by the Claude Opus session that ran the workflow. Nothing has been pushed or posted.

## The project
marshmallow (https://github.com/marshmallow-code/marshmallow) is a Python library that turns objects into plain data and back, and checks the incoming data. `marshmallow.validate.URL` is one of its checks: it decides whether a string looks like a URL. With `relative=True` it also accepts URLs without a host, such as `/foo/bar`, `?bar` or `#frag`.

## The bug
`URL(relative=True)("/redirect?to=http://example.com")` raises `ValidationError: Not a valid URL.` The same happens for `/a#http://x.y`. These are relative URLs whose query or fragment happens to contain a full URL, for example a "next page" or redirect parameter.

The cause is a pre-check at `src/marshmallow/validate.py:225-228` (before the fix). It looks for `://` anywhere in the string and treats all text before the first one as the scheme. For `/redirect?to=http://example.com` that text is `/redirect?to=http`, which is not in `schemes`, so the value is rejected before the regex runs. The URL regex itself accepts these values.

What "expected" rests on: the only documentation is `:param relative: Whether to allow relative URLs.` (`src/marshmallow/validate.py:91`). It does not mention `://`. The case for the fix is that the regex already accepts these values, and that the scheme check was written for absolute URLs (the check dates from 2015, per CONFIRMATION.md). That is a judgement call a maintainer may see differently. It went unnoticed because no existing test has `://` after a path, query or fragment start (`tests/test_validate.py` relative-valid cases before the change: `/foo/bar`, `/foo?bar`, `?bar`, `/foo?bar#baz`, `#frag` and similar).

## The fix
The text before the first `://` is treated as a scheme only if it contains none of `/`, `?` or `#`. Otherwise the scheme check is skipped and the regex decides. The change in `validate.py` is 3 lines added and 2 removed, plus 2 test cases and a changelog bullet.

```diff
diff --git a/CHANGELOG.rst b/CHANGELOG.rst
index 802ce0d3..89112742 100644
--- a/CHANGELOG.rst
+++ b/CHANGELOG.rst
@@ -14,6 +14,9 @@ Bug fixes:
   (not `ValueError`) for NaN in `TimeDelta <marshmallow.fields.TimeDelta>`
   (:pr:`3004`).
   Thanks :user:`vidigoat` for the PR.
+- Fix `URL <marshmallow.validate.URL>` with ``relative=True`` rejecting a relative URL
+  that contains ``://`` in its path, query or fragment,
+  e.g. ``/redirect?to=http://example.com`` (:pr:`NNNN`).
 
 4.3.1 (2026-08-08)
 ------------------
diff --git a/src/marshmallow/validate.py b/src/marshmallow/validate.py
index 35c0e8bc..9542e95a 100644
--- a/src/marshmallow/validate.py
+++ b/src/marshmallow/validate.py
@@ -222,8 +222,9 @@ class URL(Validator):
 
         # Check first if the scheme is valid
         scheme = None
-        if "://" in value:
-            scheme = value.split("://", maxsplit=1)[0].lower()
+        candidate, separator, _ = value.partition("://")
+        if separator and not any(char in candidate for char in "/?#"):
+            scheme = candidate.lower()
             if scheme not in self.schemes:
                 raise ValidationError(message)
 
diff --git a/tests/test_validate.py b/tests/test_validate.py
index 752e544e..0c779b63 100644
--- a/tests/test_validate.py
+++ b/tests/test_validate.py
@@ -91,6 +91,8 @@ def test_url_absolute_invalid(invalid_url):
         "/foo?bar",
         "/foo?bar#baz",
         "#frag",
+        "/redirect?to=http://example.com",
+        "/a#http://x.y",
     ],
 )
 def test_url_relative_valid(valid_url):
```

## Regression test
Two cases were added to the existing `test_url_relative_valid` parametrize list.
- Red: `E               marshmallow.exceptions.ValidationError: Not a valid URL.` at `src/marshmallow/validate.py:228`; `2 failed in 0.19s` (red.log)
- Green: `223 passed in 0.20s` for the touched file (green.log); full suite `1192 passed in 1.20s` (suite.log)
- Revert: same error at `src/marshmallow/validate.py:228`; `2 failed, 221 passed in 0.28s` (revert.log)
- Logs: red.log, green.log, revert.log, suite.log

## Knock-on effects (run 2026-10-05)
- Callers of the changed code: `URL.__call__` (`src/marshmallow/validate.py:218`) is called by `marshmallow.fields.Url`, which builds a `validate.URL` at `src/marshmallow/fields.py:1778` and inserts it into its validators. Nothing else in `src/` constructs `validate.URL`.
- Before/after: `knock_on.py` ran 18 inputs through `validate.URL` in four configurations and through `fields.Url(relative=True).deserialize`. Base is `1c63bdaf` (`HEAD~1`), fixed is the patched clone. Outputs: `knock_on.base.txt`, `knock_on.fixed.txt`. `diff` of the two files shows changes only in `relative=True` sections, 6 inputs in each of 4 sections (three `validate.URL` configurations with `relative=True`, and the field). The table shows `relative=False` and `relative=True`; the other `relative=True` sections and the field change in the same 6 rows.

| input | relative=False, base | relative=False, fixed | relative=True, base | relative=True, fixed |
|---|---|---|---|---|
| `'http://example.com'` | ok | ok | ok | ok |
| `'http://example.com/a?u=http://b.c'` | ok | ok | ok | ok |
| `'ftp://example.com'` | ok | ok | ok | ok |
| `'ws://test.test'` | ERR | ERR | ERR | ERR |
| `'foo://example.org'` | ERR | ERR | ERR | ERR |
| `'/foo/bar'` | ERR | ERR | ok | ok |
| `'/foo?bar#baz'` | ERR | ERR | ok | ok |
| `'//host/x'` | ERR | ERR | ok | ok |
| `'/redirect?to=http://example.com'` | ERR | ERR | ERR | ok |
| `'/a#http://x.y'` | ERR | ERR | ERR | ok |
| `'/p?u=ws://q'` | ERR | ERR | ERR | ok |
| `'/a/b://c'` | ERR | ERR | ERR | ok |
| `'?next=https://example.com/'` | ERR | ERR | ERR | ok |
| `'#http://x.y'` | ERR | ERR | ERR | ok |
| `'a://b'` | ERR | ERR | ERR | ERR |
| `'file:///tmp/x'` | ERR | ERR | ERR | ERR |
| `''` | ERR | ERR | ERR | ERR |
| `'://x'` | ERR | ERR | ERR | ERR |

- Behaviour changes for existing users:
  1. With `relative=True`, strings with `://` after the first `/`, `?` or `#` (and no `/?#` before it) were rejected and are now accepted. `schemes` is not consulted for them. Affected: users who relied on the rejection as a rough guard on redirect-style fields. Likelihood low: `//host/x` and the percent-encoded form (`/redirect?to=http%3A%2F%2Fexample.com`, CONFIRMATION.md) were already accepted. Judgement: acceptable under the side-effect rule, and stated in the PR text.
  2. `relative=False` (the default): no change in any of the 18 inputs.
  3. Absolute URLs and `a://b`, `ws://test.test` (not in default schemes), `file:///tmp/x`, `""`, `://x`: same result before and after.

## Review history
- Confirmed: CONFIRMATION.md (verdict CONFIRMED)
- Panel: SYNTHESIS.md (roster: full, fifteen Sonnet reviewers)
- Re-review: round 2 by both executors and the nine reviewers who flagged items; all SHIP. Text and test fixes applied after round 1: new test folded into `test_url_relative_valid`; behaviour change stated in PR text; docs paragraph reworded; PR text trimmed; suite count rerun; CHANGELOG wording; AUTHORS hunk and "Thanks" line removed.
- Upstream check (2026-10-05): dev at 1c63bdaf7fba217b8736e6eca8a1fcf377e41161 (2026-10-01, "Update astral-sh/setup-uv action to v10.2.0 (#3061)"); `git am` applies cleanly: yes (new commit fdec84a1). Suite on that tip with the patch: `1192 passed in 2.12s`.
- Local check on a fresh venv (Python and `pip install pytest simplejson` only): `1192 passed in 1.25s`.

## Things to know before submitting
- The issue tracker and open pull requests were not searched: GitHub was not reachable. Duplicates are unchecked. Run `bash quality/upstream/dup-search.sh` first and read `dup-search.out`.
- Pull-request heads in the local clone that touch `src/marshmallow/validate.py` and the URL code: pr/2324 (changes the same `"://" in value` lines, "Improve error messages for URL validation"), pr/2928 (IDN support in the URL regex, `_regex_generator`), pr/3063 (changes `_UNICODE_LETTERS`, a different line). Git cannot say if any is open. None changes the `://` behaviour described here. pr/2324 could conflict with the changed lines if it is open.
- The panel was fifteen Sonnet reviewers (EXEC-A, EXEC-B, O1 to O5, S1 to S8), then a second round.
- Findings raised and not adopted: extra test cases for `relative=False`, `absolute=False`, custom schemes and `foo/bar://x` (minimal-change rule; behaviour was checked by runs instead); a comment above the changed `if` and renaming `candidate`; switching the example to `/search?q=...`; a regex or `isalnum` speed-up (about 1 to 3 microseconds per call); the percent-encoding workaround and "strict check is a safety feature" objection (a maintainer judgement); non-string input raising `AttributeError` (it was already not a `ValidationError`).
- Optional nits left: the title says "path or query" while the changelog also says fragment.
- Maintainer may reply that percent-encoding the query already works, or that the strict rejection is useful for redirect targets. The PR states the behaviour change plainly so they can decide.
- Policy (POLICY.md): no CLA or DCO. No `Co-authored-by` for an AI (AI_POLICY.md:14). Disclosure line is the last line of the PR. Target branch `dev`.
- The patch's CHANGELOG.rst line carries the placeholder `NNNN`, because the PR number does not exist until the PR is open. `submit-draft-pr.sh` (added by the orchestrating session) runs `submit.sh`, then puts the real number in, amends the single commit and force-pushes. So the final commit differs from the reviewed patch in that one number. For a few seconds the draft PR shows `NNNN`.
- Optional: add yourself to `AUTHORS.rst` and add a "Thanks :user:`handle` for the PR." line. Both were removed because the GitHub handle could not be checked here. `expected_login` in `scripts.json` is `andrewstellman`; check that this is your login.
- POLICY.md says to run `uv run tox -e lint`. This session did not run it for this step.

## Checks by the orchestrating session (Claude Opus, 2026-10-05, after the Sonnet workflow finished)

- **AI policy, answered by Andrew on 2026-10-05 ("i read and understand the code, it's simple").** marshmallow's organisation-level `AI_POLICY.md` says: "Absolutely **no** unsupervised agentic tools like OpenClaw." and "If you cannot explain and defend the changes you submit, do not submit them and open a high-quality bug report/feature request instead." The change and this text were machine-drafted by an unattended pipeline. Submitting is in line with the policy only if Andrew has read the change and can defend it himself. Filing a bug report instead is the alternative the policy names.
- **Upstream re-check (21:44 UTC):** `dev` is still `1c63bdaf`, 1423 pull-request heads, the patch applies to the same tree and the suite gives `1192 passed`.
- **Upstream (20:41 UTC):** `dev` is still `1c63bdaf`. The patch applies with `git am`. Blobs: `validate.py` `35c0e8bc..9542e95a`, `tests/test_validate.py` `752e544e..0c779b63`, `CHANGELOG.rst` `802ce0d3..89112742`. Tree `d0d705acf66386d5a0994d5044de96ae89c3d062`. Author `Andrew Stellman <andrew@stellman.com>`, no trailers.
- **Tests rerun by me:** touched file `223 passed`; full suite `1192 passed`; unpatched suite `1190 passed`; with only the source change reverted, `2 failed, 221 passed`, both new cases, each with `ValidationError: Not a valid URL.`
- **Lint:** `ruff check` gave `All checks passed!` and `ruff format --check` gave `2 files already formatted` on the two Python files (ruff 0.16.10; the project pins v0.16.6). `uv run tox -e lint` was not run.
- **Every behavioural claim in the PR text** was run on the unpatched and the fixed code. All hold.
- **Differential fuzz (mine):** 740,973 strings containing `://`, built from 20 tokens, up to 5 tokens long, through 6 validator configurations.
  - `relative=False` (two configurations): no string changed result.
  - `relative=True` (four configurations): 102,256 strings newly accepted, none newly rejected. Every newly accepted string starts with `/`, `?` or `#`. None starts with a scheme. I found no way for an absolute URL with a disallowed scheme to get through.
- **Security angle.** The fix makes a validator accept more. I looked for a bypass and found none (the fuzz above), and `//host/x`, which points at another host, was already accepted before. Reviewer O2 said SHIP. Whether that clears the correctness-only rule is Andrew's call.
- **Duplicates.** 1423 pull-request heads fetched. The ones that touch `validate.py`: #2324 (2024-10-18, error messages; edits the same two lines), #3063 (2026-10-02, internationalised domain names; same file, other lines), #2928 and older. None changes this behaviour. The issue tracker has NOT been searched: GitHub's search pages are closed to my fetch tool. One web search found no matching issue; the closest title, #1114, is about hosts without a top-level domain. `../dup-search.sh` runs the tracker search with your `gh`.
- **The strongest plain argument is not in the PR text:** `http://example.com/a?u=http://b.c` is accepted, while `/a?u=http://b.c` is rejected with `relative=True`. The same query string is fine on an absolute URL and refused on a relative one.
- **My assessment:** a real inconsistency, low severity. The documentation does not promise the behaviour, so the maintainers may reasonably decline it. They merged a comparable outside fix to this validator in August (#3016, commit 902f99c4).
- **Other bugs from this run are already being fixed upstream by other people** (seen as pull-request heads): BUG-004 matches #2989 (2026-06-29), BUG-002 matches #3056 and #3058, BUG-003 and BUG-007 overlap #3054. The shortlist step caught three of those four from the git history.

## The PR as it will be submitted
**Title:** Fix URL validator rejecting "://" in a relative URL's path or query

> ```python
> from marshmallow import validate
> v = validate.URL(relative=True)
> v("/redirect?to=http://example.com")  # actual: ValidationError "Not a valid URL."; expected: returns the value
> v("/a#http://x.y")                    # same
> ```
>
> The scheme check split on the first "://" even when the text before it contained "/", "?" or "#". Here that text was `/redirect?to=http`, which is not in `schemes`.
>
> The `relative` parameter is documented only as "Whether to allow relative URLs." (`src/marshmallow/validate.py:91`). That does not mention "://". I am relying on the URL regex, which already accepts these values once the scheme check is skipped.
>
> Behaviour change: with `relative=True`, values with "://" after the first "/", "?" or "#" were rejected and are now accepted, and `schemes` is not consulted for them. `//host/x` was already accepted before this change. With the default `relative=False`, the two examples above, `//host/x`, `/p?u=ws://q`, `/a/b://c` and `ws://test.test` are rejected both before and after. `ws://test.test` is also still rejected with `relative=True`.
>
> Adds two cases to `test_url_relative_valid`. Full suite passes (1192 tests).
>
> Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.

## To submit
    bash ~/Documents/QPB/harness_runs/cloud-pilot-marshmallow-2026-10-05/upstream/marshmallow-url-relative-scheme/submit-draft-pr.sh

To skip the local test run, put `SKIP_TESTS=1` in front of the command. The local test run needs a `python3` that is 3.10 or newer, because marshmallow requires it; the tests were run here on the same upstream commit.

What it does: checks `gh` is logged in as `andrewstellman`, forks and clones if needed, branches from upstream `dev`, applies the patch with `git am`, runs the tests in a temporary virtual environment, pushes to the fork and opens a **draft** PR with `PR.body.md`. Then it replaces `NNNN` in CHANGELOG.rst with the PR number, amends and force-pushes. It does not mark the PR ready, comment, or merge. `verify.sh <URL>` afterwards saves the PR title, body and diff for comparison. Neither script was run here; the changelog-number step was tested on a local clone.

## Submission record

- **Submitted:** 2026-10-05 by Andrew, after reading the change, using `submit-draft-pr.sh`. His paste of the script output: `"isDraft": true`, `"number": 3067`, `"title": "Fix URL validator rejecting \"://\" in a relative URL's path or query"`.
- **PR:** [marshmallow-code/marshmallow#3067](https://github.com/marshmallow-code/marshmallow/pull/3067), opened as a **draft** from `andrewstellman:fix-url-relative-scheme-in-query` into `marshmallow-code:dev`; 1 commit, `0544e52a73197941a25c586db0454149cb69cd2e`.
- **Verified by git (2026-10-05 21:49 UTC, `git fetch` of `refs/pull/3067/head`):**
  - One commit on top of `1c63bdaf`, which is still the tip of `dev`.
  - `git diff` between the reviewed commit and the PR head shows exactly one changed line: the changelog entry's `(:pr:\`NNNN\`)` is now `(:pr:\`3067\`)`. No `NNNN` remains. So the hand-written number step worked.
  - Blobs: `validate.py` `35c0e8bc..9542e95a` and `tests/test_validate.py` `752e544e..0c779b63`, the same as the reviewed patch; `CHANGELOG.rst` `802ce0d3..e9fd8d33` (the reviewed patch had `89112742`, with the placeholder).
  - The commit message matches the patch. No trailers.
  - Author: `Andrew Stellman <andrew@stellman.com>`. Committer: `andrewstellman <astellman@stellman-greene.com>`, 2026-10-05 17:45:52 -0400 (the amend in the script).
  - GitHub's merge ref for the PR exists, so there is no conflict with `dev`.
- **Title and description:** the title in Andrew's paste matches. The fetch tool's reading of the PR page gave the description word for word as above, base `marshmallow-code:dev`, 1 commit, status Draft, and no comments. That tool is a summary, so treat the description check as likely, not proven. The exact check is `bash verify.sh https://github.com/marshmallow-code/marshmallow/pull/3067`.
- **Not checked:** CI results; the issue tracker for a duplicate report.
- **Still to do on Andrew's side:** nothing until a maintainer responds.
- **2026-10-05 17:53 -04:00:** Andrew ran `gh pr view --json number,isDraft,state,url` for this PR. Output: `draft=false  OPEN`. He had marked it ready in the web UI. It is open and ready for review.
- **Maintainer responses:** none seen.
