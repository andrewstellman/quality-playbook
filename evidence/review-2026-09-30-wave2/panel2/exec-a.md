# EXEC-A (wave 2, panel 2)
All runs in clones under /tmp/w2review2/scratch/exec-a (deleted). Worktrees untouched.

| ID | Red (test on base) | Green | Revert source | Touched file + full suite |
|---|---|---|---|---|
| cobra-016 | FAIL, 2 new asserts (completions_test.go:2058 got ":0..." want "--string\n:0..."; :2074 got "arg\n:0..." want "arg\n--string\n:0...") | ok | FAIL at :2074 | `go test ./...` ok (cobra 0.203s, doc ok) |
| st-004 | FAIL 2: long_description (AttributeError 'NoneType' has no 'get'), python_requires (TypeError 'NoneType' not iterable) | pass | same 2 FAIL | test_apply_pyprojecttoml.py + test_manifest.py: 133 passed, 1 xfailed |
| addr-011 | FAIL 3: "./" got ""; "file.txt" spec; "./a:b" spec | 1071/0 | 3 FAIL | full rspec 1436 ex, 0 fail, 5 pending |
| addr-032 | FAIL 4: {+pct} got %2520a%252Fb; {+badpct} got %25zz%252/%252f; {+pctlist*} got %2520a,b%252F; {#pct} | 330/0 | 4 FAIL | full rspec 1437 ex, 0 fail, 5 pending |

addr-011 re-time (http://example.com/ + n a's + "/", routed from same + ?q=1): base n=10000 0.0153s, n=30000 0.0101s; fixed 0.0151s / 0.0099s. Linear; no regression (the first-round regex was 0.30s / 2.6s per the reviser).

### cobra-016
Verdict: SHIP
Side effects:
- A ValidArgsFunction now receives flag-looking words after `--` (or after the first arg with interspersed off) in `args`, and `toComplete` for `-- --string=x` is now "--string=x", was "x". Affects only completion authors whose function sees such input; base behaviour was the bug (Run gets the same words). Rare. Acceptable.
- Flag-value completion before `--` is unchanged. I ran 13 inputs x interspersed on/off (child -s "", --string=, --bool --string "", ...): every base-vs-fixed diff was a word after `--`/after an arg with interspersed off. Acceptable.
Findings:
1. `--tags a -- --tags ''` args=["--tags"], no duplicate slice value (reviser's claim holds).
2. `--out=x`-after-`--` toComplete change is untested (reviser says so); disclosed in PR. Fine.

### st-004
Verdict: SHIP
Side effects:
- Builds that crashed on base (setup.py sets long_description/python_requires, pyproject [project] lacks readme/requires-python and dynamic) now complete with the existing _MissingDynamic warning, and the setup.py value is dropped. Nobody whose build worked is changed. Risk: a project could now publish with no Requires-Python/description, but only after a loud warning, same as every other field. Acceptable.
- Checked end to end (egg_info on a toy project): fixed builds with the warning; base AttributeError at _apply_pyprojecttoml.py:187. PKG-INFO keeps `Description-Content-Type: text/markdown` from setup.py (content-type reset dropped, as the panel asked) with no description; harmless.
Findings: 1. None blocking. 2. Remaining oddity: PKG-INFO also shows `Dynamic: description-content-type`; not caused by this patch (not checked on base because base crashes).

### addr-011
Verdict: SHIP
Side effects:
- route_from with same path, base has a query, target has none: was "" (wrongly inherits the base query), now last segment or "./". Affects callers that test `.to_s.empty?` as "same URL" or store/compare the result, and route_to (calls route_from). Needs same path + base-only query; moderate-low likelihood. Result is RFC 3986 5.2.2 correct and the old value joined back to the wrong URL (join-back false in all 9 cases tried on base, true in 7 of 9 fixed). Acceptable.
- Cases tried (fixed vs base): `/a:b` -> "./a:b" (no InvalidURIError, the first-round blocker), `/a/b/` -> "./", `/a/b` -> "b", `#f` target "b#f" (base "#f", lost the query-clearing), `%2F` kept, `//` kept. Timing as above.
Findings:
1. Residual: `http://example.com` (empty path) -> "./"; joined back gives `http://example.com/`, not byte-identical to the target (equivalent for HTTP). Target with empty query (`.../b?`) -> "b"; join drops the "?". Trivial.

### addr-032
Verdict: DROP (side effect) -- lean, confidence moderate; code and tests are fine, the behaviour is the issue.
Side effects (measured, template "https://api.example.com/files/{+name}"):
- Fixed: "%2e%2e%2fsecret" -> .../%2e%2e%2fsecret (base %252e%252e%252fsecret); "%0d%0aX-Injected:1" -> unchanged (base %250d...). Any app that passes untrusted text through {+x}/{#x} used to get every "%" neutralised; now encoded traversal/CRLF/`%3F`/`%23` reach the server decoded. Same trust boundary already leaks raw "/", "?", "#" for `+`, but filters that strip "/" or ".." before expanding are now bypassed by the encoded forms. Likelihood: moderate (the `+` operator is how API clients splice user paths).
- Values that literally contain %XX (file "report%2520v2.txt", "100%25 sure", user-typed "50%20off") now resolve to a different resource silently; before they round-tripped. Likelihood: low, but silent data change.
- expand then extract no longer round-trips for pre-encoded values (`%20a%2Fb` -> extract " a/b"; base returned the original). Anyone relying on the round trip for pre-encoded input breaks. PR text discloses this one but not the two above.
- Why not acceptable: nobody would expect an upgrade to change what leaves the library for the same input, and a user who gets it wrong is hurt with no warning. The RFC 3.2.1 text supports the change, so a defensible alternative is shipping it as an issue/opt-in, not a default change.
Findings:
1. Code: constant ALLOW_RESERVED_ENCODE_MAP, template.rb +45; mutation checks in CHANGES-AFTER-PANEL hold (red/green/revert 4 fail / 0 / 4 fail).
2. Prefix modifier: `{+v:2}` on "%20abc" -> "%252" (cut triplet, unchanged from base); `{+v:3}` now "%20".
3. Perf fine: 600 KB of "%20" 0.056s fixed, 0.112s base; 600k "%" 0.22s both.

### st-024
Not assessed by EXEC-A (not in the EXEC roster; side-effect check is for the O/S reviewers).
