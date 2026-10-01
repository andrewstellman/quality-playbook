# Changes from v1

Panel: 15-reviewer synthesis, `SYNTHESIS.md` section "calibre-opds" (and detail in
`O1-maintainer.md`, `O4-not-a-bug.md`, `O5-slop.md`).

1. **Base patch swapped.** v1 shipped `0001-*.patch` (navcatalog only) as primary and
   `alt/0001-*.patch` (all three handlers) as a labeled alternative. v2 starts from the
   `alt/` version and is the only patch: `opds_navcatalog`, `opds_category`, and
   `opds_categorygroup` all get the `try`/`except ValueError` around their
   `from_hex_unicode` calls [O1, O2, O3, O4, O5, S3, S4, exec-A].

2. **Dropped the `if not which: raise HTTPNotFound('Not found')` line** that both v1
   patches added to `opds_navcatalog`. `parse_uri` (`http_request.py`) drops empty path
   segments before routing, so `/opds/navcatalog/` and `/opds/navcatalog//` both collapse
   to the 2-component path `('opds', 'navcatalog')`, which never matches this handler's
   3-component route -- an empty `which` cannot arrive over HTTP, only via a direct
   function call. [O1, O4, O5]. Verified again in green.log's reachability table
   (`opds_navcatalog`'s own route), and, separately (see the Appendix below for the raw
   output), `parse_uri` drops empty segments the same way for the 4-component
   `/opds/category/{category}/{which}` and `/opds/categorygroup/{category}/{which}`
   routes -- an empty `which` or `category` there is equally unreachable over HTTP, for
   the same reason. Per the scope of this change, the pre-existing
   `if not which or not category: raise HTTPNotFound('Not found')` checks already in
   upstream `opds_category` and `opds_categorygroup` are untouched -- they were not part
   of the finding and this patch does not remove any check that was already there.

3. **PR body rewritten.** Cut to three sentences: the bug, the fix, then one disclosure
   sentence plus how it was verified. Removed the bracketed
   "[If sending the alternative patch, add:]" editorial placeholder [O1, O4, O5, S2, S3],
   removed the meta-commentary about "sending the alternative patch" (there's only one
   patch now), and removed anything addressed to Andrew -- the draft is meant to be pasted
   as-is. No security framing, per the panel's and O4's read that this is a 500-vs-404
   correctness/log-noise issue, not a vulnerability.

4. **Commit message unchanged** (still the single-line subject from the `alt/` patch:
   "Content server: return 404 instead of 500 for malformed hex ids in OPDS feeds"). It
   was already short and did not need editing for this round.

5. **Verification re-run for v2 specifically**, not just copied from v1: `red.log` and
   `green.log` in this folder are fresh runs of the validator's `harness.py` against (a)
   the pinned unpatched commit and (b) the v2 patch applied via `git apply` on a clean
   checkout of that same commit, using a Python 3.14.7 interpreter (`uv`-installed) and
   `ruff` 0.16.9 (the repo's `pyproject.toml` needs >=0.16 to parse). See `green.log` for
   why the harness's own exit code/RESULT line still shows one `[FAIL]` (the unreachable
   empty-id case, explained there) rather than a clean `RESULT: GREEN`.


## Appendix: reachability check for the 4-component routes

Same `parse_uri` extraction as `harness.py`, run against `opds_category`'s and
`opds_categorygroup`'s routes (`/opds/category/{category}/{which}`,
`/opds/categorygroup/{category}/{which}`) to confirm the pre-existing `if not which or
not category` guards in those two handlers also guard a case `parse_uri` already makes
unreachable over HTTP -- not part of this patch, included here only so the claim in
item 2 above is checkable:

```
b'/opds/category//zz'          -> ('opds', 'category', 'zz')
b'/opds/category/x/'           -> ('opds', 'category', 'x')
b'/opds/category//'            -> ('opds', 'category')
b'/opds/category/x/zz'         -> ('opds', 'category', 'x', 'zz')
b'/opds/categorygroup//zz'     -> ('opds', 'categorygroup', 'zz')
b'/opds/categorygroup/x/'      -> ('opds', 'categorygroup', 'x')
```

None of the empty-segment cases produce the 4-component tuple the route needs, matching
the same mechanism already documented for `opds_navcatalog` in `red.log`/`green.log`.
