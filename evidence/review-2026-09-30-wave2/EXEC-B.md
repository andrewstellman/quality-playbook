# EXEC-B report (executor, independent). All red/green/revert runs done; scratch deleted; locks pyd/jav released.
Substitutions disclosed: pydantic built with CARGO_PROFILE_DEV_DEBUG=0 + CARGO_INCREMENTAL=0 (disk), one shared target dir, venv .pth temporarily repointed then restored to /tmp/w2fix/pyd-006. For jav-011/jav-025 "revert" = base src + new test (same state as the red run). I read CONFIRMATION.md while pulling patches (executor, no blind-verdict duty).

## Results table
| ID | red | green | revert | file suite | repro | PASS/FAIL |
|---|---|---|---|---|---|---|
| cobra-016 | FAIL 2 asserts (got ":0", want "--string"/"arg\n--string") | ok | FAIL same | go test ./... ok, vet+gofmt clean | BUG-016: base "BUG PRESENT", fixed "no bug" | PASS |
| cobra-030 | FAIL "Expected ld: 1 Got: 2" | ok | FAIL same | go test ./... ok | BUG-030 base "BUG PRESENT", fixed "no bug" | PASS |
| pyd-033 | FAIL b'{"b":"hi"}' != b'{"b":"aGk="}' | ok | FAIL same (006 reverted too = base) | test_types_typeddict 50 pass/31 skip; serializers+validators typed_dict 291 pass; test_config+test_serialize 178 pass | own edge script (below) | PASS |
| pyd-006 | FAIL 6x DID NOT RAISE ValidationError | test_float 328 pass | 6 failed/322 pass | 328 pass | own edge script | PASS |
| st-024 | FAIL "Extra items in the left set: 'app/static/app.css'" | ok | FAIL | test_manifest.py 70 pass | direct FileList run | PASS |
| st-004 | FAIL AttributeError 'NoneType'.get + TypeError 'NoneType' not iterable (both params) | 2 pass | FAIL both | test_apply_pyprojecttoml 64 pass, 1 xfail | build_meta on tmp project: base crashes, fixed warns+ignores | PASS |
| addr-032 | FAIL 2: got "%2520a%252Fb" / "#%2520a%252Fb" | 328 ex 0 fail | 2 fail | template_spec 328/0 | edge script | PASS |
| addr-011 | FAIL 2: got "" (want "./", "file.txt") | 1070 ex 0 fail, 5 pending | 2 fail | uri_spec 1070/0 | edge script | PASS |
| jav-011 | ERROR "[file should be precompressed and cached] expected: 1" | class 15 tests 0 fail (11 orig + 4 of mine) | = red state | TestStaticFilesPrecompressor green | edge tests | PASS |
| jav-025 | ERROR expected "/blog/users/John" but was "/users/John" | class 13 tests 0 fail (9 + 4 of mine) | = red state | TestRedirectToLowercasePathPlugin green | edge tests | PASS |
| express-issue | n/a | n/a | n/a | n/a | repro run on pinned express 9a34acf0 (5.2.1, node 22.23.2, cookie 0.7.2): Max-Age=0 confirmed for 500 | see below |

## Own edge inputs (3+ per fix; B = base, F = fixed)
- cobra-016: `child -- --string=x` toComplete B "x" -> F "--string=x"; `child -- -s ""` args B [] -> F ["-s"]; `child --sl a -- --sl ""` args B [] -> F ["--sl"] but the StringSlice value seen by ValidArgsFunction goes ["a","a"] -> ["a","a","a"] (3rd ParseFlags; slice already duplicated in base, Run sees ["a"]). Not-interspersed variants all correct.
- cobra-030: ld("\xff","\xfe") 1 -> 0 (distinct invalid UTF-8 bytes both become U+FFFD; harmless); ld("日本語","日本") 3 -> 1; end-to-end `app ubr` suggests "über" only after fix. NFD "café" vs NFC "café" = 1 edit (no normalisation; fine).
- pyd-006: inf/-inf/nan/JSON Infinity/NaN all now multiple_of error (also with ge=0, strict, float|None, explicit allow_inf_nan=True); finite 1.5 ok, 1.3 err, 1e300 ok, -0.0 ok; allow_inf_nan=False still finite_number; int field unchanged. multiple_of=0/inf rejected at schema build (unaffected).
- pyd-033: E1 parent ser_json_bytes=hex, TD with own config of only str_to_upper: B hex "6869" -> F "hi" (parent ser_json_* silently dropped; own config REPLACES parent). E5c hand-written core schema with literal `config: None`: B ok -> F SchemaError (validator already raises the same; pydantic never emits None). serialize_by_alias in TD own config now honoured (B {"a":1} -> F {"A":1}). Nested no-config TD under an own-config TD now inherits that TD's config.
- st-024: `data/**/*.txt` 1 -> 3 files; `**/*.txt` 2 -> 7 (now includes `.hid/z/h.txt`, hidden dirs, root.txt); `data/**` 1 -> 4; `data/**.txt` unchanged (1) so "** crosses slash" per docs is still false for `**` not a whole path component; symlink loop `data/x/loop -> ..`: B 1 file -> F 123 entries (`data/x/loop/x/loop/...`) until ELOOP (same as existing recursive-include).
- st-004: case static pyproject w/o readme + setup.py long_description / python_requires / both+content_type: B crashes, F builds, METADATA has no Requires-Python/Description/Content-Type, _MissingDynamic warnings printed for both. `dynamic=[readme,requires-python]` unchanged (values kept). Unrelated pre-existing: static requires-python ">=3.9" + setup.py python_requires ">=3.8" -> METADATA ">=3.8" (setup.py wins), same B and F.
- addr-032: `{+v}` "50%25" B "50%2525" -> F "50%25"; "%zz%2 %a" unchanged (lone % still %25); list/hash explode values keep triplets; `{+v:3}` "%20abc" B "%2520" -> F "%20"; `{v}` simple unchanged. extract round trip: B "a%20b/c" -> "a%2520b" -> "a%20b/c"; F -> "a%20b/c" -> "a b/c" (value no longer round-trips).
- addr-011: `http://a/x:y` from `http://a/x:y?x=1`: B "" (wrong) -> F raises InvalidURIError "Cannot assemble URI string with ambiguous path" (also `/d/x:y`). `http://a` from `http://a?x=1` -> "./" (joins to `http://a/`, normalisation only). Fragment/;params/%20 segments/dir/root all round-trip after fix; `?` empty-query base still gives "#" (pre-existing).
- jav-011: size -2 stays disabled (cache +0); size 0 with 1 MB swagger bundle: B gzip on the fly, no Content-Length, cache +0 -> F Content-Length 336091, cache +1; size 0 identity/missing/gzip: B cache +0 -> F cache +2 (identity and gzip entries), 404 unaffected; size 300 on 279-byte file cached (unchanged).
- jav-025: root ctx "/" -> "/users/John" (no "//"); ctx "/blog" + query `?x=1&y=Z` kept; trailing slash input redirects to no-slash form (pre-existing); ctx "a//b/" and "blog" (unnormalised) -> "/a/b/users/John", "/blog/users/John"; already-lowercase `/blog/users/john` -> 418 (no redirect).

## Verdicts
### cobra-016
Verdict: SHIP
Confidence: medium
Findings:
1. Verified red/green/revert and confirmer repro; doc quote present at cite/site_content_completions__index.md:238.
2. Optional: restore branch runs ParseFlags a third time; slice flags seen by ValidArgsFunction gain one more duplicate (["a","a","a"]) - pre-existing duplication, but a maintainer may ask. No change required.
### cobra-030
Verdict: FIX-REQUIRED
Confidence: high
Findings:
1. PR-DRAFT: "Likewise `cafx` does not suggest `café`" is FALSE. Base already suggests it (ld bytes = 2, min distance 2). Verified end-to-end on base: `Did you mean this? café`. Delete that sentence (or use a case that really fails, e.g. `ubr`/`über` only).
2. Everything else checks: `ld("cafe","café")`=2 and `ld("ubr","über")`=3 on bytes, 1 and 2 on runes; user_guide.md:791 quote verified.
### pyd-033
Verdict: FIX-REQUIRED
Confidence: medium
Findings:
1. Undisclosed behaviour change: own config REPLACES the parent, so a TypedDict with any own config (even `str_to_upper` only) stops inheriting the parent's ser_json_* (E1: hex -> utf8). Docs (docs_concepts_config.md:232-233) support it; say so in one sentence.
2. Commit message "as the validator does" is loose: validator never falls back to the parent (validators/typed_dict.rs:57); the fix falls back when `config` is absent. Reword: "use the schema's own config when present".
3. Test builds only the inherit and own-with-same-key cases; no case for own config that omits the key. Optional.
4. Hand-written core schema with `config: None` now raises SchemaError in the serializer (matches validator). Low risk.
### pyd-006
Verdict: SHIP
Confidence: medium
Findings:
1. Verified; native behaviour now matches the Python fallback (_validators.py:300-306) and JSON-Schema text (cite json-schema-spec_jsonschema-validation.md:177).
2. Compat unstated: with explicit `allow_inf_nan=True` + `multiple_of`, inf/nan used to pass and now fail. Add half a sentence.
### st-024
Verdict: FIX-REQUIRED
Confidence: medium
Findings:
1. PR omits the consequence: `include **/*.x` now walks the whole tree, including dot-directories and, through directory symlinks, loops (123 bogus entries until ELOOP in my test). recursive-include already behaves this way, so it is consistent, but the sdist can grow. State it in the PR (the confirmer predicted this pushback).
2. Scope claim: docs say `**` matches "zero or more characters including forward slash" (miscellaneous.rst:113-114 verified). `include data/**.txt` is still not recursive, so title/summary should say "`**` as a whole path component".
3. Test is minimal and idiomatic; newsfragment orphan name `+...bugfix.rst` matches repo precedent (`+ghsa-...`).
### st-004
Verdict: SHIP
Confidence: medium
Findings:
1. Verified crash->warning for both fields, content-type also cleared, METADATA clean. Both new params fail for the right reasons.
2. Not verified by me: the #4183 characterisation (confirmer says the maintainer endorses warn-and-ignore while #4183 itself asks for an error). Reword to "the warn-and-ignore behaviour #4183 describes" or drop the reference.
### addr-032
Verdict: SHIP
Confidence: medium
Findings:
1. Verified; RFC 6570 3.2.1 quote correct (cite lines 1083-1088).
2. Compat sentence worth adding: a caller passing a literal "100%25 off"/"a%20b" that was meant to be encoded now gets it passed through, and expand->extract no longer round-trips ("a%20b/c" -> "a b/c"). This is RFC-mandated but visible.
3. `{+v:N}` can still cut mid-triplet ("%2" -> "%252"); pre-existing, out of scope.
### addr-011
Verdict: FIX-REQUIRED
Confidence: high
Findings:
1. New exception: when the last segment contains ":" (`http://a/x:y` routed from `http://a/x:y?x=1`) route_from now raises InvalidURIError ("ambiguous path") where base returned "" (wrong but non-raising). Confirmer knew (BUG-012 "same as other branch"); PR-DRAFT does not say so. Either emit "./x:y" for that case or disclose it.
2. Rest verified (RFC 3986 5.2.2 quote at cite rfc3986-uri.txt:1753-1759; round trip holds for file/dir/root/fragment/%20/;params).
### jav-011
Verdict: FIX-REQUIRED
Confidence: medium
Findings:
1. PR says the file "is gzipped on the fly (chunked, no Content-Length)". True for a large compressible file (1 MB webjar: cl null -> 336091), not for small ones (confirmer saw a Content-Length at 216 KB; the 279-byte test file is not gzipped on base). Say "recompressed on every request, nothing cached" or name the large-file case.
2. Test is titled "any size" but uses a 279-byte file; it does cover both guard changes (base fails). Acceptable; consider a comment.
3. StaticFileConfig.kt:52 comment ("-1 means disabled, otherwise set the max size") not updated; maintainer may prefer a docs fix (cite javalin.io_docs.md:1566 verified).
### jav-025
Verdict: SHIP
Confidence: high
Findings:
1. Verified red/green; root, "/blog", unnormalised and slash-less context paths all produce the right Location; no "//" at root. Docs lines 1508/1762 verified; PR is honest that they do not explicitly promise the combination.
### express-issue
Verdict: FIX-REQUIRED
Confidence: high
Findings:
1. FALSE claim: "`maxAge: 0` and negative values would still send `Max-Age=0`". Run on pinned express (before and after the patch): `maxAge: -5` sends `Max-Age=-1`; only 0 sends 0. Fix: "`maxAge: 0` and negative values are unchanged".
2. Quoted doc sentence ("a convenience option for setting expires relative to the current time in milliseconds") is unverified: I could not retrieve the expressjs.com text (JS-rendered; no cite copy). The code comment at lib/response.js:728 reads "max-age in milliseconds, converted to `expires`". Verify the exact wording or paraphrase without quotes.
3. "same result as `res.clearCookie`": same effect, different wire form (clearCookie sends `Expires=1970`, no Max-Age; response.js:714-721). Say "same effect".
4. Repro verified exactly (`a=b; Max-Age=0; Path=/; Expires=...`); also 0.5 and '500' give 0. `Max-Age=1` after the patch for all of 500/0.5/'500'. Floor and RFC section cites (4.1.2.2 precedence, 5.2.2 <=0 expires) match my reading of RFC 6265; I did not open a cite copy. "master (9a34acf...)" is the pinned control checkout, not re-checked against current master. "npm test passes": evidence suite-after.log 1263 passing.

## Summary
- Ready: cobra-016, pyd-006, st-004, addr-032, jav-025 (SHIP; only optional sentences).
- Text/code fixes first: cobra-030 (false `cafx` claim), addr-011 (new InvalidURIError undisclosed), express-issue (false negative-maxAge claim, unverified doc quote), pyd-033 (replace-not-merge semantics), st-024 (symlink/hidden/scope), jav-011 ("chunked" overgeneral).
- No REJECT; all 10 patches go red->green->red on the claimed reason.
