model: gpt-6-sol
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:13:53 UTC; finished 2026-09-28 23:15:59 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# calibre server review (7691f4f1)

## Findings

1. **Medium — stale rendered books are never removed, and cleanup can remove an unrelated directory.** `src/calibre/srv/books.py:116` calls `safe_remove(x)` where `x` is only a name from `os.listdir(fdir)`. The preceding code reads the manifest at `os.path.join(fdir, x, ...)`, and the comment says to delete that stale book. `safe_remove` resolves the relative name against the process working directory, so the actual cache directory remains. If the working directory contains a same-named directory, that directory is recursively deleted instead. Pass `os.path.join(fdir, x)` to `safe_remove`.

2. **Medium — Digest authentication accepts a request whose query differs from the signed URI.** `src/calibre/srv/auth.py:202` parses the `uri` from the Authorization header but compares only its path to `data.path` at line 203. The parser separately returns the query (`src/calibre/srv/http_request.py:81-96`), and the request retains its original URI (`src/calibre/srv/http_response.py:280`). Thus a valid Digest header for `/ajax/search?query=one` also authenticates `/ajax/search?query=two` when the same path and method are used, despite `H_A2` signing the first complete URI (`auth.py:173-177`). This defeats the URI binding that the Digest code and its mismatched-URI check intend. Compare the complete request target, including the query, to the signed `uri` after appropriate normalization.

3. **Low — a malformed byte-range header raises an unhandled exception.** `src/calibre/srv/http_response.py:138` unpacks `brange.split('-', 1)` without handling ranges that contain no hyphen. For example `Range: bytes=garbage` (or `Range: bytes=0-1,garbage`) raises `ValueError` while finalizing the response, producing a server error. The function's own docstring says an empty list indicates no valid range was found. Ignore invalid components or return an empty list so the server returns the intended range error rather than a 500.

## Files read

- `src/calibre/srv/auth.py`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py`
- `src/calibre/srv/routes.py`
- `src/calibre/srv/books.py`
- `src/calibre/srv/content.py`
- `src/calibre/srv/code.py`
- `src/calibre/srv/tests/auth.py`
- `src/calibre/srv/tests/routes.py`
