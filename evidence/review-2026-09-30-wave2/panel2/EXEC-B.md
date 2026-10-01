# EXEC-B results (cobra-016, st-004, addr-011, addr-032; st-024 not in my roster)

| Item | red (base src + new tests) | green | full suite | edge inputs (base vs fixed) |
|---|---|---|---|---|
| cobra-016 | FAIL: expected "--string\n:0..." got ":0..." ; expected "arg\n--string\n:0..." got "arg\n:0..." | pass | `go test ./...` ok (cobra, doc) | 8 cases x interspersed on/off; only post-`--` / non-interspersed cases differ |
| st-004 | 2 fail: `TypeError: 'NoneType' object is not iterable` (python_requires), readme AttributeError | 18 pass | apply_pyprojecttoml + test_manifest: 133 passed, 1 xfailed | 3 end-to-end egg_info projects |
| addr-011 | 3 fail: "./" got ""; "file.txt" got ""; "./a:b" got "" | 1071 pass | full rspec 1436 ex, 0 fail | 12 pairs, join round-trip |
| addr-032 | 4 fail (pct, lowercase-hex, list, #pct); %zz/%2 are regression guards | 330 pass | full rspec 1437 ex, 0 fail | 16 values incl. extract round-trip |

### cobra-016
Verdict: SHIP
Side effects:
- ValidArgsFunction now receives a flag-looking word after `--` (or after the first arg when non-interspersed) as an arg. Affects authors whose ValidArgsFunction ran after `--`; they now see the same args as Run. Likelihood low, change is the bug fix. Acceptable.
- toComplete for `child -- --string=x` was "x" on base, now "--string=x" (also `child arg --string=x`, non-interspersed). Base value was wrong (positional treated as flag value). Acceptable, disclosed.
- Flag-value completion otherwise unchanged: `--string v ''`, `--string=''`, `--bool --string ''` produce byte-identical output base vs fixed.
Findings:
1. `--tags a -- --tags ''`: tags=[a a] on both base and fixed (no extra duplicate vs base; claim verified). ARGS now ["--tags"] (was []).
2. `-- --string v --string ''`: ARGS now ["--string" "v" "--string"] (base dropped last). Correct.
3. No regression in any of 8 cases outside post-`--` ones.

### st-004
Verdict: SHIP
Side effects:
- A setup.py giving long_description / python_requires while pyproject omits readme / requires-python: base crashes (AttributeError / TypeError), fixed warns and drops the value. Only crash -> warning; nobody depended on the crash. Acceptable.
- Dropped values are not applied (same policy as other fields). Users who "worked" before? None: base crashed. Acceptable.
Findings:
1. E1 (setup.py sets python_requires, long_description, long_description_content_type; pyproject has neither): fixed egg_info succeeds, warning printed, PKG-INFO has no Requires-Python/Description but still has `Description-Content-Type: text/x-rst` + `Dynamic: description-content-type` (content type reset was dropped per panel). Cosmetic leftover, harmless.
2. Paths where the fields ARE in dynamic or statically set (E2, E3): PKG-INFO byte-identical base vs fixed.
3. E3 (static pyproject values + conflicting setup.py) shows `Requires-Python: >=3.8` (setup.py's) on both base and fixed: pre-existing, not touched by this patch.

### addr-011
Verdict: SHIP
Side effects:
- Equal paths, base has query, target has none: route_from returned "" (which joins back with the base's query, i.e. wrong URI); now returns last segment ("b", "./" for empty, "./a:b" for colon). Affects callers that call route_from on query-bearing bases and treated "" specially (e.g. `.empty?`). Likelihood low; "" was incorrect. Acceptable.
- Same-query and different-query cases unchanged (`?x=1` vs `?x=2` -> "?x=1").
Findings:
1. All 10 changed pairs round-trip via base.join(route) == target (e.g. http://e.com vs http://e.com?x=1 -> "./" -> http://e.com/). Base: roundtrip=false for the same 10.
2. Fragment preserved: `/a/b#frag` vs `/a/b?x=1` -> "b#frag".
3. Pre-existing, unchanged: target `/a/b` vs base `/a/b?` -> "#" (joins to `?#`); not caused by this patch. Relative target/base still raises ArgumentError on both.
4. Percent-encoded colon `%3Ab` normalizes to ":" so "./b:c" is produced; correct.

### addr-032
Verdict: DROP (side effect)   (code is correct per RFC 6570 3.2.1 and tests/mutations are good; the behaviour change is the problem)
Side effects:
- BAD: `{+var}` / `{#var}` previously encoded every "%", so a user value was always recoverable verbatim. Now any value containing a literal `%XX` is emitted raw and decodes to something else. Measured, base vs fixed:
  - `{+v}` v="50%25" -> base "50%2525" extract "50%25"; fixed "50%25" extract "50%".
  - v="%41" -> base "%2541"; fixed "%41" (extract "A").
  - v="%%20" -> base "%25%2520"; fixed "%25%20" (extract "% ").
  - hash/list values likewise (`{+k}` a=%20 -> "a,%20,b,%25", extract "a, ,b,%").
- Who: anyone feeding user/file/search text into `{+x}` or `{#x}` (redirect URLs, paths, "continue=" style values, filenames like "50%20off.txt"). Silent data change, no error, no deprecation. Also security-relevant for untrusted input: `%2e%2e%2f`, `%00`, `%0d%0a` in a value now pass through and become traversal / NUL / CRLF after the receiver decodes, where base neutralised them. Likelihood: moderate for a widely used gem (reserved expansion is the common choice for URL-valued vars); impact: silent, hard to find. Not acceptable under Andrew's rule, even though it matches the RFC and the "expand-then-extract" asymmetry is disclosed in the PR line.
- Acceptable parts: bare "%", "100%", mid-string "%2", non-hex "%zz" encode identically to base.
Findings:
1. Mutation/regression guards in the spec are good (reviser's claims about lookahead/{2}/hex case verified by red output: lowercase-hex and list cases fail on base).
2. If it is to be pursued, it needs to be opt-in or a major-version change; not as a default.

### st-024
Not in EXEC roster for my id; no work done.
