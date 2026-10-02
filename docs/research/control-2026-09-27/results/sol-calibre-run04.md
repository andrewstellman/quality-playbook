model: gpt-6-sol
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:07:38 UTC; finished 2026-09-28 23:09:15 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; traced code and existing tests; direct runtime check unavailable
interruptions or errors: calibre import requires sys.extensions_location
network access attempted (yes/no, and what): no attempt reported

# Review of `src/calibre/srv/`

## Findings

1. **Medium — URL prefix is optional during route matching** (`src/calibre/srv/routes.py:323–325`). When `url_prefix='/calibre'`, `find_route(('calibre', 'probe'))` strips the prefix, but `find_route(('probe',))` proceeds to match the same `/probe` endpoint because a missing prefix is never rejected. The `url_prefix` option is documented in `src/calibre/srv/opts.py` as “A prefix to prepend to all URLs,” and `Router.url_for()` prepends it to generated URLs. Thus endpoints remain reachable at unprefixed paths even when the server is configured to live under a prefix. Reject paths that do not begin with `self.strip_path` before trying any route; only strip when it matches.

2. **Medium — digest authentication accepts a header signed for a different query string** (`src/calibre/srv/auth.py:202–207`). `parse_uri(...)[1]` returns only the path tuple; `parse_uri()` discards the query string from that value (`src/calibre/srv/http_request.py:78–96`). A valid Digest `Authorization` header with `uri="/endpoint?x=1"` can therefore authenticate a request to `/endpoint?x=2`: `request_digest()` hashes the header's `self.uri`, while `validate_request()` compares only path components. The error message here explicitly says the Request-Line URI and Authorization URI must match, and the Digest A2 calculation above binds authentication to `digest-uri-value`. A captured header can be replayed against a different query operation for the nonce lifetime. Compare the complete digest URI request target, including its query string, against `data.request_original_uri` (handling absolute-form request targets as appropriate) before accepting the digest.

## Verification

The route and digest paths were traced against the request parser, handler construction, option description, and existing tests. I attempted a direct Python import, but this checkout requires calibre's runtime-provided `sys.extensions_location`; the local interpreter cannot import it. No checkout files were modified.

## Files read

- `src/calibre/srv/auth.py`
- `src/calibre/srv/routes.py`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/handler.py`
- `src/calibre/srv/opts.py`
- `src/calibre/srv/code.py`
- `src/calibre/srv/last_read.py`
- `src/calibre/srv/changes.py`
- `src/calibre/srv/fts.py`
- `src/calibre/srv/http_response.py` (search matches only)
- `src/calibre/srv/tests/routes.py`
- `src/calibre/srv/tests/auth.py`
- `src/calibre/srv/tests/http.py` (search matches only)
- `src/calibre/srv/tests/base.py`
