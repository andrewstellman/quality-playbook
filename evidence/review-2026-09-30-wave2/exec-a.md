# EXEC-A report (executor). Scratch deleted. Disk at finish: 342 MB free (below the 400 MB build floor; not caused by me, my scratch is gone).

Method: scratch clone of each worktree, checkout HEAD~1; test hunk of fix.patch only (red); then source hunk (green); then source reverted (revert); then touched file/class on the fixed tree; then confirmer or PR-text repro. Command output below is verbatim excerpts.

## Substitutions and gaps (read first)
- pyd-006 and pyd-033: NO Rust build (free disk 554 MB at decision time, a debug pydantic-core target would take it under 400; fixer's target dir no longer exists). Used the prebuilt base wheel .so at /tmp/pydv/.venv/.../_pydantic_core...so as "base", and the fixer's already-built .so left in /tmp/w2fix/pyd-006/pydantic-core/python/pydantic_core/ as "fixed" (pyd-006 only). pyd-006 "revert" = the base .so, not a source revert. pyd-033: no fixed .so exists anywhere on disk, so green/revert/file-suite NOT RUN by me. Fixer's claim (27 pre-existing suite failures, same with/without fix) is unverified by me.
- javalin: the background-run script died twice (process killed between calls); reran in foreground under the jav lock, `mvn -q` rc captured. Test classes only (TestStaticFilesPrecompressor, TestStaticFiles*, TestRedirectToLowercasePathPlugin), not the module suite.
- express-issue: no node_modules in the pinned tree and no network in bash, so I did not run a live express server. I ran the exact `res.cookie` arithmetic (response.js:764-770) through the `cookie` package (v1.1.1 found at /tmp/adonw/node_modules; express pins ^0.7.1, same output format). Docs page fetched via web_fetch.

## Per-item results
### cobra-016
Red (test only): `completions_test.go:2058: expected: "--string\n:0\n..." got: ":0\n..."` and `:2074 expected "arg\n--string..." got "arg\n:0..."` FAIL. Green: ok. Revert: FAIL at :2074 (first assert at 2058 also in red). `go test ./...` ok (cobra, cobra/doc); `go vet ./...` and `gofmt -l .` empty. Repro /tmp/cobrav/BUG-016 against base: `ValidArgsFunction args ... = ["pos1"]` / `= []`, "BUG PRESENT"; against fixed: `["pos1" "--output"]` / `["--output"]`, "no bug". (First attempt of mine reused a clobbered tree and showed BUG PRESENT on "fixed"; that was my harness error, redone with its own clone.)
### cobra-030
Red: `cobra_test.go:122: Expected ld: 1 Got: 2` (subtest Non-ASCII_characters). Green ok. Revert: Got 2 FAIL. Full ok, vet/gofmt clean. Repro BUG-030: base "BUG PRESENT: non-ASCII name ... not suggested"; fixed "no bug".
### st-024
Red: `test_include_recursive_glob` AssertionError, extra item 'app/static/app.css', log `warning: no files found matching '**/*.css'`. Green: test_manifest.py 70 passed. Revert: 1 failed, 69 passed. test_egg_info+test_sdist+test_manifest: 179 passed, 1 xfailed. ruff check + ruff format --check clean. Repro (data/a.txt, x/b.txt, x/y/c.txt, `include data/**/*.txt`): base SOURCES.txt has only data/x/b.txt; fixed has all three.
### st-004
Red: `AttributeError: 'NoneType' object has no attribute 'get'` (_apply_pyprojecttoml.py:187) for readme case; revert run shows both cases fail (the python_requires one: `TypeError: 'NoneType' object is not iterable`). Green: 64 passed, 1 xfailed. tests/config: 183 passed, 1 xfailed. ruff check + format clean. Repro: base crashes with both errors; fixed builds, egg-info PKG-INFO has no Description/Requires-Python (values ignored). I did not assert the _MissingDynamic warning text in my repro (the unit test covers it).
### addr-032
Red: `{+pct}` expected "%20a%2Fb" got "%2520a%252Fb"; `{#pct}` expected "#%20a%2Fb" got "#%2520a%252Fb"; 328 examples, 2 failures. Green 0 failures. Revert: same 2 failures. Full rspec on fixed: 1435 examples, 0 failures, 5 pending. Repro: fixed gives "%20a%2Fb", "#%20a%2Fb", and `{+half}` "50%25" (matches PR text).
### addr-011
Red: 2 failures (uri_spec.rb:3363 './' from '...resource/?query=x'; :3575 'file.txt' got empty URI). Green: 1070 examples, 0 failures, 5 pending. Revert: same 2 failures. Full rspec fixed: 1435, 0 failures. Repro (PR snippet): fixed route_from => "file.txt", join with base => "http://example.com/file.txt"; base => "" and join gives "...file.txt?x=1".
### pyd-006
Red (base .so, test hunk): 6 failed (3 inputs x py/json), `Failed: DID NOT RAISE ValidationError` (test_float.py:161), 182 passed. Green (fixer .so): test_float.py 328 passed. Revert = base .so (substitution): same 6 fail. tests/validators + tests/serializers on fixed .so: 5347 passed, 123 skipped, 8 xfailed, 1 failed (`test_allow_partial.py::test_set_frozenset[set_schema]`, inline_snapshot ast.Set); that test also fails on the base .so, so pre-existing/environmental. Behaviour on fixed: inf, -inf, nan, JSON Infinity, JSON NaN rejected with `multiple_of`; 1.0 and 1.5 accepted; 0.3 rejected.
### pyd-033
Red (base .so + test hunk): `assert b'{"b":"hi"}' == b'{"b":"aGk="}'` FAIL, i.e. for the claimed reason (own ser_json_bytes ignored); other 49 tests in test_types_typeddict.py pass, 31 skipped. Green / revert / file suite: NOT RUN (no fixed build). Source read: patch makes the TypedDict's own `config` replace (not merge with) the parent config in the serializer; matches the validator pattern and the fixer's note, but the new test only covers the own-config-has-the-key and no-own-config cases.
### jav-011
Red: `expected: 1 but was: 0` (TestStaticFilesPrecompressor, `precompressMaxSize of zero precompresses files of any size`), 11 run, 1 error. Green: mvn rc=0. Revert: same error, 11 run 1 error. TestStaticFiles* on fixed: rc=0.
### jav-025
Red: `expected: "/blog/users/John" but was: "/users/John"` (9 run, 1 error). Green: rc=0. Revert: same failure. File: whole TestRedirectToLowercasePathPlugin rc=0 on fixed.
### express-issue (text only)
Verified: response.js:764-770 does `opts.expires = new Date(Date.now() + maxAge)` and `opts.maxAge = Math.floor(maxAge / 1000)`; package.json version 5.2.1; pinned HEAD 9a34acf0 matches; cookie.serialize output for maxAge 500 is `a=b; Max-Age=0; Path=/; Expires=<+0.5s>` (matches the issue's block exactly); 999 -> Max-Age=0; 1000 -> Max-Age=1. Docs: express 5.x res.cookie page says "The `maxAge` option is a convenience option for setting “expires” relative to the current time in milliseconds." Issue quotes it without the quotation marks around expires (harmless, but not strictly verbatim).
WRONG CLAIM: "`maxAge: 0` and negative values would still send `Max-Age=0`". Measured: maxAge -5 sends `Max-Age=-1` (floor(-0.005)); -5000 would send -5. Only 0 sends Max-Age=0. Reword to "values of 0 or below are unchanged".
Unverified by me: "`npm test` passes" and the patch itself (not in this packet's scope). RFC 6265 4.1.2.2 (Max-Age precedence) and 5.2.2 (delta-seconds <= 0 means expire now) are cited from my knowledge, not fetched. Docs fetch also showed the OpenJS Foundation publishes an "AI Coding Assistants Policy" (https://ai-coding-assistants-policy.openjsf.org/, footer link of expressjs.com); my fetch of it returned empty, so its content is unread. The panel's maintainer-context note says express has no stated policy; someone should read that page before the issue goes out and check the disclosure line against it.

## Table
| ID | red | green | revert | file suite | repro | PASS/FAIL |
|---|---|---|---|---|---|---|
| cobra-016 | fail (2 asserts) | pass | fail | pass, vet, gofmt | pass (base BUG, fixed no bug) | PASS |
| cobra-030 | fail (got 2 want 1) | pass | fail | pass, vet, gofmt | pass | PASS |
| st-024 | fail | pass | fail | 179 pass | pass | PASS |
| st-004 | fail (both cases) | pass | fail (both) | 183 pass, ruff clean | pass | PASS |
| addr-032 | fail (2) | pass | fail (2) | 1435/0 fail | pass | PASS |
| addr-011 | fail (2) | pass | fail (2) | 1435/0 fail | pass | PASS |
| pyd-006 | fail (6, base .so) | pass (fixer .so) | fail (base .so, substitution) | 5347 pass, 1 pre-existing env fail | pass (python+JSON) | PASS (with substitution) |
| pyd-033 | fail (base .so, right reason) | NOT RUN | NOT RUN | NOT RUN | NOT RUN | INCOMPLETE (no build) |
| jav-011 | fail | pass | fail | class + TestStaticFiles* pass | n/a (confirmer's cache probe not rerun) | PASS |
| jav-025 | fail | pass | fail | class pass | covered by the test (/blog/Users/John) | PASS |
| express-issue | n/a | n/a | n/a | n/a | arithmetic repro pass, no live server | FAIL on one claim (negatives), otherwise accurate |

## Verdicts (executor view; behaviour only, not maintainer/slop/process)
cobra-016: SHIP. Confidence high (behaviour). 
cobra-030: SHIP. Confidence high.
st-024: SHIP. Confidence high.
st-004: SHIP. Confidence high.
addr-032: SHIP. Confidence high.
addr-011: SHIP. Confidence high.
pyd-006: SHIP on behaviour; medium (green used a prebuilt .so, not a build I made).
pyd-033: FIX-REQUIRED until someone with disk runs green + revert + test_types_typeddict.py on a real build; red is confirmed. Confidence low.
jav-011: SHIP. Confidence high.
jav-025: SHIP. Confidence high.
express-issue: FIX-REQUIRED: correct the negative-maxAge sentence; read the OpenJS AI policy page. Confidence high on the factual error.

Summary: eight code items reproduce red/green/revert cleanly with their file suites passing; pyd-006 passes with a disclosed prebuilt-.so substitution.
pyd-033 only has red (no fixed build exists and the disk was under the build floor); it must not be called verified.
express-issue has one factually wrong sentence (negative maxAge sends Max-Age=-1 or lower, not 0) and an unread AI-policy link.
