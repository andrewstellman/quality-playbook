# Wave 2 panel synthesis (2026-10-01)

Panel: 2 executors (Sonnet) + O1-O5 (Opus) + S1-S8 (Sonnet), brief in PANEL.md, raw outputs alongside. Packets (patch, PR text, confirmation) in packets/.

## Verdict matrix (S = SHIP, F = FIX-REQUIRED, R = REJECT)

| Item | A | B | O1 | O2 | O3 | O4 | O5 | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cobra-016 | S | S | S | S | S | F | F | F | S | S | S | F | S | S | S |
| cobra-030 | S | F | F | S | F | F | F | S | S | F | S | S | S | F | S |
| pyd-033 | F* | F | F | S | S | S | F | F | S | S | F | F | S | F | F |
| pyd-006 | S | S | F | S | S | S | S | S | S | F | S | F | S | S | F |
| st-024 | S | F | S | F | S | F | F | S | S | F | F | F | S | F | S |
| st-004 | S | S | S | S | S | F | F | F | F | F | F | S | S | S | S |
| addr-032 | S | S | S | F | S | F | S | F | F | S | F | F | S | S | S |
| addr-011 | S | F | F | F | F | F | F | F | F | F | F | F | F | F | S |
| jav-011 | S | F | R | F | F | R | F | F | S | F | F | F | S | S | S |
| jav-025 | S | S | S | S | S | S | S | S | S | S | F | S | S | S | S |
| express-issue | F | F | F | S | F | R | F | S | – | F | F | F | S | F | S |

\* EXEC-A could not build pydantic (disk); red only. EXEC-B built it: red/green/revert PASS for both pydantic items.

All ten fixes passed red/green/revert with both executors where run (EXEC-B: 10/10). No fix is wrong about the bug.

## Per item

- **jav-025: ready.** 14 SHIP. S4's optional suggestion (follow the redirect in the test) not required.
- **cobra-016: code revision.** (1) The extra flag re-parse adds one more duplicate to slice flags (`[a a]` → `[a a a]`; O3, O4 measured; the duplication pre-exists). (2) After `--`, a `--out=x` word now reaches ValidArgsFunction as `toComplete` instead of `x`; unstated (S5). (3) Fold the new block into the one above; duplicated error return (S1). (4) Open PR #2259 touches the same `--` probe lines (O4): mention it. (5) Doc quote joins two sentences (O5).
- **cobra-030: text + route.** Code correct. PR claims "`cafx` does not suggest `café`": false, base already suggests it (B, O3, O5, S3, S7 all ran it). Open PR #2478 rewrites the same `ld` and its new test pins `café`/`cafe` = 2, the byte behaviour (O1, O4). Options: PR mentioning #2478, or a comment on #2478.
- **pyd-033: text + rebase.** Commit message/comment "as the validator does" is wrong (validator ignores the parent config; this falls back to it: S1, S7, O5). State the behaviour change: a TypedDict with any own config stops inheriting the parent's ser_json_* (B, O1, O3, S5). Restore the PR template checklist (O1, S8). Rebase past #13891 merged 2026-09-29 in the same area (O4).
- **pyd-006: text.** Restore checklist; cite closed PR #13473 ("probably belongs in pydantic-core"); say inf/nan are now rejected even with allow_inf_nan=True (B, S5).
- **pydantic policy (S8):** AI policy requires contributors to "certify that they fully understand the code" and names mass-submission across repos as grounds for closing/banning. "I reviewed the change" is weaker. Andrew must be able to say he understands both Rust changes.
- **st-024: text.** Newsfragment and PR must say `include` lines with `**` may now add deeper files, including hidden dirs, venv/, node_modules/ (O2, S5 measured 2 → 6 files); symlink loops produce many paths (same as recursive-include). Say `setuptools.glob`, not stdlib glob; `**` only as a whole path component (`data/a**.txt` still not recursive). Example in PR should match the test.
- **st-004: small code revision.** Drop the untested long_description_content_type reset (YAGNI) or test it (S2, S4). Update the `val` annotations that now receive None (S1, O5). Comment the `vars(dist.metadata).pop` line (O1, S1). Point at abravalheri's comment in #4183, not #4183 itself (#4183 asks for an error; O4, O5).
- **addr-032: small code revision.** Hoist the regexp to a constant, use the file's `[a-fA-F0-9]` spelling (S1). Add specs: non-hex `%zz`, mid-string `%2`, lowercase hex, a list/explode case (S2, S4). PR line: pre-encoded values now pass through, and expand-then-extract of `%20a%2Fb` now returns `" a/b"` (O2, O4, S5). Not framed as security.
- **addr-011: code revision (blocking).** (1) Last segment containing `:` now raises InvalidURIError where base returned "" (12 reviewers): prefix `./` (RFC 3986 §4.2) plus a spec; O2 tested the one-liner (uri_spec 1070/0). (2) **New quadratic regex** `path[/[^\/]*\z/]` (S6 measured: 10k-char segment 0.004 s → 0.295 s, 30k → 2.7 s) in a library that parses untrusted URLs: use `path.rpartition("/").last`. (3) Commit message: "whenever only the base had a query" (S7); #126 is the maintainer's stated invariant, quote it as such.
- **jav-011: do not send as a code change (O1, O4 REJECT; O2, O3, S5, S6 flag).** Upstream #2616 (2026-07-31): a user copied `precompressMaxSize = 0` from the docs, served 3.6 GB files, hit OOM; tipsy fixed it in #2618 by streaming. This patch would make 0 read every file fully into an unbounded, never-evicted in-memory cache. The in-repo KDoc ("-1 means disabled, otherwise set the max size") suggests the website line is what's wrong. Options: docs PR to javalin.io, or a short issue asking which tipsy wants. The "chunked, no Content-Length" claim only holds for large files (B).
- **express-issue: text fixes, and O4 argues not to file.** Wrong: negative maxAge sends `Max-Age=-1`, not 0 (A, B, O3, S4, S5). Wrong: "Expires half a second in the future" — Expires has 1 s resolution (O4 measured 308-314 ms in the past). Docs quote drops the quotation marks around "expires" (S7). "Same result as res.clearCookie" → "same effect". "(npm test passes)" unverified from here. Needs a title and one line of real-world motivation (O1). Use the standard disclosure line (O1, O5, S8). O4: a sub-second lifetime is below both attributes' resolution and `Max-Age=1` doubles it; #7287 was an Infinity/NaN PR (the brief misdescribed it), and the maintainer's reply was "open an issue first ... more sense in the cookie package". O5: answer that by noting the rounding is in lib/response.js:769, not in cookie. OpenJS AI Coding Assistants Policy not yet read (A, O5).

## Andrew's decisions (2026-10-01)
- jav-011: dropped. Rule: no fixes with bad side effects; not worth it.
- express-issue: dropped (O4's argument accepted). v2 text kept in revised/ for the record only.
- pyd-033, pyd-006: held this round.
- cobra-016, st-004, addr-011, addr-032 (code revised): focused re-review. st-024 added to it for the side-effect rule only (its `include **` change can pull hidden dirs, venv/, node_modules/ into existing sdists).

## Focused re-review (PANEL-2.md, outputs in panel2/)

| Item | EXEC-A | EXEC-B | O2 | O3 | O4 | S1 | S2 | S4 | S5 |
|---|---|---|---|---|---|---|---|---|---|
| cobra-016 | S | S | S | S | S | S | S | S | S |
| st-004 | S | S | S | S | S | S | S | S | S |
| addr-011 | S | S | S | S | S | S | S | S | S |
| addr-032 | D | D | S | S | D | S | S | S | S |
| st-024 | – | – | D | D | D | D | S* | D | D |

D = drop under Andrew's side-effect rule. S* = S2 leans ship, says drop if zero surprise is wanted.
- All three revisions verified: cobra-016 slice-flag duplicate gone (`[a a]` as on base); addr-011 colon case returns `./a:b`, timing back to base (30k chars: 0.0101 s base, 0.0099 s fixed); st-004 content-type reset dropped, metadata pop confirmed load-bearing by mutation.
- st-024: measured on realistic layouts, `include **/*.py` went 13 → 264 (O3), 12 → 184 (O4), 13 → 3073 (O2, real venv); node_modules, venv/, env/, hidden dirs, in one case a nested service-account.json. setuptools only prunes .venv/.tox/.nox at the root. Silent, and a PyPI upload can't be undone. **Dropped.**
- addr-032: split 6-3. Literal `%XX` meant as text now changes the target URL silently (`docs/a%20b.md` now points at `a b.md`); an app that filters `..` but not `%2e%2e` loses the old double-encoding protection. RFC 6570 requires the new behaviour. Andrew to decide.
- Upstream heads checked 2026-10-01: cobra main, setuptools main, addressable main, javalin master are all still at the pinned commits; all five ready patches `git apply --check` cleanly.

Submit kit (evidence/SUBMIT/): cobra-complete-after-dashdash, cobra-suggest-runes, setuptools-missing-dynamic-crash, addressable-route-from-base-query, javalin-lowercase-redirect-contextpath.
