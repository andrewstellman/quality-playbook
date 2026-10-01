# calibre: `/opds/navcatalog/<id>` returns 500 for a malformed hex id

Verdict: **CONFIRMED** (harness execution of the unmodified handler, not end-to-end), with a correction to the historical description. Fixed locally, not submitted.

- Repository: https://github.com/kovidgoyal/calibre
- Pinned commit: `7691f4f1a155d799afdfec99e2cdc2716c178402` (master, committed 2026-09-27 11:40:02 +0530; subject line is literally "...")
- Origin: Quality Playbook run, `repos/secbench2/sb2-24-calibre/quality/BUGS.md` BUG-003; triaged in `docs/research/triage-2026-09-27/scout-candidates-wave2.md` rank 3. Reproduction and fix in this folder were done by Claude (Opus 5.5) in a Linux sandbox.

## Defect

`src/calibre/srv/opds.py` at the pinned commit, lines 654-671:

```python
@endpoint('/opds/navcatalog/{which}', postprocess=atom)
def opds_navcatalog(ctx: Context, rd: RequestData, which: str) -> etree.Element:
    try:
        offset = int(rd.query.get('offset', 0))
    except Exception:
        raise HTTPNotFound('Not found')
    rc = RequestContext(ctx, rd)

    page_url = rc.url_for('/opds/navcatalog', which=which)
    up_url = rc.url_for('/opds')
    which = from_hex_unicode(which)
    type_ = which[0]
    ...
```

`from_hex_unicode` (`src/polyglot/binary.py:48-51`) is `unhexlify(x).decode('utf-8')`. For a path component that is not valid hex (`zz`, odd length `4`) it raises `binascii.Error`; for valid hex that is not UTF-8 (`ff`) it raises `UnicodeDecodeError`. Neither is an `HTTPSimpleResponse`, so `http_response.py:546-558` (`job_done`) re-raises it, `loop.py:669-677` logs "Unhandled exception" with a traceback and calls `report_unhandled_exception`, which sends a bare 500 (`http_response.py:710-711`). The client gets 500 with no body detail; the server log gets a traceback per request.

### Correction to the historical finding

The historical report (and the brief) name `IndexError` from `''[0]` on an empty id. That case is **not reachable over HTTP**: `parse_uri` (`http_request.py:94`) drops empty path segments, so `/opds/navcatalog/` and `/opds/navcatalog//` become the 2-component path `('opds', 'navcatalog')`, which does not match the 3-component route and gets the router's own 404. Any non-empty valid hex decodes to a non-empty string. The reachable 500s are the decode errors above.

Consequence: the sibling guard in `opds_category` (`opds.py:681-682`, `if not which or not category: raise HTTPNotFound('Not found')`) guards only the empty case, so copying it alone would **not** fix the reachable bug. `opds_category` and `opds_categorygroup` have the same unguarded decode (lines 687, 739, 745) and also return 500 for `zz` (shown in red.log, informational section).

## Expected behaviour and what it rests on

404 Not Found, which is what this handler already returns for every other bad input (bad `offset`, unknown type prefix after decode) and what the codebase does for bad encoded path arguments elsewhere:

- `src/calibre/srv/ajax.py:352-355` and `:475-478`: `try: decode_name(...)` (the same `from_hex_unicode`) `except Exception: raise HTTPNotFound(...)`.
- `src/calibre/srv/content.py:356-359` (`reader_background`, the endpoint fixed via PR #3101): `except ValueError, UnicodeDecodeError: raise HTTPNotFound(...)`.
- `src/calibre/srv/routes.py:244` (`Route.matches.check`): a path argument of the wrong type becomes `HTTPNotFound('Argument of incorrect type')`.

HTTP semantics: a malformed client-supplied identifier is a client error (4xx); 500 signals a server fault. 400 would also be defensible, but 404 matches calibre's convention. OPDS itself does not specify error codes for malformed catalog URLs; OPDS clients only ever receive ids that the server generated with `as_hex_unicode`, so this only affects hand-typed, truncated or corrupted URLs.

**Plainly: this is a 500-vs-404 correctness/cosmetic issue plus one error-log traceback per bad request.** No data exposure (the 500 body carries no traceback), no traversal, no resource cost beyond a normal request. The endpoint is behind the server's normal auth settings. Not a security issue, and the PR must not frame it as one (see PR #3101, where the maintainer rejected the "security" framing of similar fixes while merging them).

## What was executed

Harness execution, not end-to-end. calibre master requires Python >= 3.14 and compiled `calibre_extensions` (plus Qt/ICU) even to import `calibre`; no build was possible here (`tests-and-lint.log` shows `setup.py test` failing on `calibre_extensions.translator`). A CPython 3.14.7 was installed with `uv` under /tmp for the harness.

`harness.py` (included):
- Real, unmodified code: `opds_navcatalog`, `opds_category`, `opds_categorygroup` bodies extracted from `opds.py` with `ast` and exec'd (only the `@endpoint` decorator dropped); `parse_request_uri`/`parse_uri`/`quoted_slash` from `http_request.py` the same way; real imports of `polyglot.binary`, `polyglot.urllib.unquote`, `calibre.srv.errors` (the top-level `calibre` package replaced by a bare namespace module so `calibre/__init__.py` is not executed).
- Stubbed: `RequestContext` (url_for returns a string, `get_categories()` returns `{}`, `db.field_metadata` is `{}`), `get_all_books`/`get_navcatalog` (return a sentinel), `ctx`/`rd` (rd has only `.query = {}`).
- Not executed: the routing table, the worker pool / job_done / event loop path to the 500. That link is from source reading (line refs above).

## Results

- `red.log` (unpatched 7691f4f, exit 1): `zz` -> `binascii.Error: Non-hexadecimal digit found`; `4` -> `binascii.Error: Odd-length string`; `ff` -> `UnicodeDecodeError`; `''` (direct call only) -> `IndexError`. Controls pass: `Ntags` reaches `get_navcatalog('tags')`, `Otitle` reaches `get_all_books('title')`, unknown prefix `X` -> `HTTPNotFound`.
- `green.log` (primary patch, exit 0): all four malformed cases -> `HTTPNotFound(Not found)`; controls unchanged. Siblings still raise `binascii.Error` (not in scope of the primary patch).
- `green-alt.log` (alternative patch, exit 0): navcatalog as above, and `opds_category` / `opds_categorygroup` malformed ids -> `HTTPNotFound`.
- Existing tests: calibre's srv test suite has no OPDS coverage (`src/calibre/srv/tests/ajax.py:374`: "Not going test legacy and opds as they are too painful") and cannot run without a build, so there are no before/after suite logs. `tests-and-lint.log`: `ruff check` and `ruff format --check` (repo config) pass on both patched files; `py_compile` under 3.14 passes.

## Patches (both `git format-patch` against 7691f4f, author Andrew Stellman, apply cleanly with `git apply --check`)

- `0001-Content-server-return-404-instead-of-500-for-malform.patch` (primary, navcatalog only, +6/-1): adds the sibling's `if not which: raise HTTPNotFound('Not found')` and wraps the decode in `try/except ValueError` (covers `binascii.Error` and `UnicodeDecodeError`, both `ValueError` subclasses) -> `HTTPNotFound('Not found')`.
- `alt/0001-Content-server-return-404-instead-of-500-for-malform.patch` (alternative, +18/-4): the same plus the same `try/except ValueError` around the decodes in `opds_category` and `opds_categorygroup`.

No regression test is included: calibre has no OPDS tests and its maintainer has explicitly declined to write them; a test would need the full server test fixture (library + running server), which could not be built here.

## Decisions for Andrew

1. Primary (navcatalog only, as scoped) vs. alternative (all three OPDS handlers with the same defect). The alternative is the more complete fix of one defect class; the primary is the smaller diff.
2. Keep or drop the `if not which` line in the primary patch. It mirrors the sibling but guards a case that cannot arrive over HTTP; the `try/except` is what fixes the reachable bug. Dropping it gives a +4/-1 diff.
3. Whether it is worth a PR at all: the effect is 500 instead of 404 on URLs no OPDS client generates. PR #3101 shows the maintainer merges small, correct robustness fixes quickly.

## Upstream status

Merged 2026-09-29 by Kovid Goyal as kovidgoyal/calibre#3310: commit `70e61b11e2` (unchanged from the submitted v2 patch), merge commit `1d4904f1a5` on master. Verified from a fresh clone of master.
