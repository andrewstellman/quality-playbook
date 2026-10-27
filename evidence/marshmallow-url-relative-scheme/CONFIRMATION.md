# BUG-005: validate.URL(relative=True) rejects relative references containing "://" after the path/query/fragment start

Claim: `validate.URL(relative=True)("/redirect?to=http://example.com")` raises ValidationError ("Not a valid URL."); the report expects it to be accepted, based on the docstring `:param relative: Whether to allow relative URLs.` and RFC 3986 section 4.2 (general knowledge, not a gathered doc).

Verdict: CONFIRMED (low severity; narrow, with one maintainer judgement call, see pushback)

## Repro
/work/pilot/scratch/confirm-marshmallow-url-relative-scheme-confirmer/repro.py (run at dev 1c63bdaf, PYTHONPATH=<clone>/src). Output verbatim:

    '/redirect?to=http://example.com' rejected: ['Not a valid URL.']
    '/a#http://x.y' rejected: ['Not a valid URL.']
    '/a/b://c' rejected: ['Not a valid URL.']
    '/foo?bar' accepted
    '/redirect?to=http%3A%2F%2Fexample.com' accepted
    exit=1

Cause: src/marshmallow/validate.py:225-228, `if "://" in value: scheme = value.split("://", maxsplit=1)[0].lower()`; the text before `://` ("/redirect?to=http") is checked against `self.schemes`. The regex (relative_part `[/?#]\S+`) would accept these values, so only the scheme pre-check rejects them.

## Expectation check
- Docstring, cite/src_validate.py:91: "Whether to allow relative URLs." Only says relative URLs are allowed. It does not mention `://` in a query. The "expected" for this case rests on RFC 3986 4.2 and inference, not on a quoted marshmallow doc.
- Tests: tests/test_validate.py:110-135 (relative valid: /foo/bar, /foo?bar, ?bar, /foo?bar#baz, #frag). No test has `://` after a path/query/fragment start; nothing makes the rejection intentional. Rejections of `foo://example.org` and `ws://` stay under the proposed fix.
- CHANGELOG.rst and docs/: grep found no mention of this behaviour (only "Add ``relative`` parameter" at CHANGELOG.rst:2702 in the cited copy).
- History: the `"://" in value` check dates to bad7e56c (2015, Steven Loria); git log -S shows 94cc7809 (reformat) only. Last touches: 76bc28ae (#2800 file handling), 7324d8f3 (pre-commit). The scheme check was written for absolute URLs; relative=True was not considered. No sign it was a deliberate choice.
- Proposed fix (quality/patches/BUG-005-fix.patch) partitions on "://" and only treats it as a scheme when the prefix has no `/?#`. Not re-run by me; the report says suite 1190 passed.

## Duplicate search (local git only; forge not reachable)
PR heads touching the `"://"` lines: pr/2324 "Improve error messages for URL validation", pr/2800 "Add more tests cases; update changelog" (file handling), pr/2914 "Allow lambda in Nested" (maxsplit tweak). None changes the behaviour. Closest match: none found. Issue tracker not searched. None of the 8 numbers in known_open_bugs.md describes this.
dup queries:
- "URL relative query string contains ://"
- "validate.URL relative=True redirect url http://"
- "URL validator scheme check relative path"
- "Not a valid URL relative next=http://"
- "validate.URL :// in query rejected"

## Security
No. Over-rejection of valid input, not a bypass. (An open-redirect-style value is being accepted as a relative URL, but the validator only checks syntax.)

## Likely maintainer pushback
- Relative-with-absolute-URL-in-query is rare; a user can percent-encode the query (`%3A%2F%2F` is accepted, shown above).
- "Whether to allow relative URLs" is thin documentation; maintainers may ask for a docs note or say the strict check is a safety feature for redirect targets.
- Not checked: browser/urllib behaviour for edge inputs like "a://b" (no leading slash) which stays treated as a scheme under the fix.

## Parent re-run

Exit code: 1

```
'/redirect?to=http://example.com' rejected: ['Not a valid URL.']
'/a#http://x.y' rejected: ['Not a valid URL.']
'/a/b://c' rejected: ['Not a valid URL.']
'/foo?bar' accepted
'/redirect?to=http%3A%2F%2Fexample.com' accepted
```
