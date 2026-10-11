# addressable: `route_from` returns an empty route when only the base URI has a query

Status: **open for review, [sporkmonger/addressable#623](https://github.com/sporkmonger/addressable/pull/623).** Submitted as a draft on 2026-10-05 and marked ready by Andrew the same day. See the submission record at the end.

## The project

[sporkmonger/addressable](https://github.com/sporkmonger/addressable) is a Ruby URI library, an alternative to the URI implementation in Ruby's standard library. It parses, normalizes and joins URIs and supports IRIs and URI templates.

`route_from` answers "what relative reference gets me from this base URI to this target?". It is the opposite of `join`: joining the base with the route should give back the target.

## The bug

- **Expected:** joining the base with the route returns the target. Two sources:
  - RFC 3986 section 5.2.2 (checked today in the RFC text, lines 1754 to 1759): `if (R.path == "") then T.path = Base.path; if defined(R.query) then T.query = R.query; else T.query = Base.query;`. So an empty reference keeps the base's query.
  - The maintainer, in issue #126, as quoted in the PR text below. The earlier review panel checked that quotation against the issue page. I could not load the comment today, so I have not re-checked it.
- **Actual** (run today on upstream `main`, `d298c9f`):
  ```ruby
  uri = Addressable::URI.parse("http://example.com/file.txt")
  uri.route_from("http://example.com/file.txt?x=1").to_s   # => ""
  # joining the base with "" gives http://example.com/file.txt?x=1, not the target
  ```
- **Cause:** when the two paths are equal, `route_from` (`lib/addressable/uri.rb`, around line 2105) drops the path, and clears the query only when both queries match. A target with no query, routed from a base that has one, ends up as an empty reference.
- **Why it went unnoticed:** it needs equal paths and a query on the base only. The existing specs cover equal queries and different paths.

## The fix

When the paths are equal and only the base has a query, return the target's last path segment instead of an empty path. The segment gets a `./` prefix when it is empty or contains `:` (RFC 3986 section 4.2, lines 1445 to 1449: a first segment with a colon "would be mistaken for a scheme name" and "must be preceded by a dot-segment").

```diff
           if normalized_self.path == uri.path
-            components[:path] = nil
             if normalized_self.query == uri.query
+              components[:path] = nil
               components[:query] = nil
+            elsif normalized_self.query == nil
+              # An empty path would inherit the base's query (RFC 3986 5.2.2);
+              # "./" stands in for an empty segment and keeps one with ":"
+              # from reading as a scheme (RFC 3986 4.2)
+              segment = normalized_self.path.rpartition(SLASH).last
+              if segment.empty? || segment.include?(":")
+                segment = "./" + segment
+              end
+              components[:path] = segment
+            else
+              components[:path] = nil
             end
```

Three specs are added to the existing `route_from` examples in `spec/addressable/uri_spec.rb`: `file.txt`, a directory path (route `./`), and a segment with a colon (route `./a:b`).

Total: `lib/addressable/uri.rb` +12/-1, `spec/addressable/uri_spec.rb` +26.

## Regression test

Re-run on 2026-10-04 in a cloud sandbox (Ruby 3.3.6, rspec 3.13.2) on upstream `main` at `d298c9f`:

- **Unpatched upstream, full suite:** `1433 examples, 0 failures, 5 pending`
- **Green (fix applied), full suite:** `1436 examples, 0 failures, 5 pending`
- **Revert (fix removed, specs kept), `uri_spec.rb`:** `1071 examples, 3 failures, 5 pending`. The three failures are the three new specs: `expected: "./"  got: ""`, `expected: URI:file.txt  got: URI:`, `expected: "./a:b"  got: ""`.
- Two things about the environment, neither caused by the patch: I ran with `IDNA_MODE=pure` (the native `idn-ruby` gem needs libidn, which the sandbox lacks), and with a UTF-8 locale (without one, 9 unrelated `tld` specs fail on both trees because the public_suffix gem reads its list as US-ASCII).
- Older logs from 2026-10-01 (`red.log`, `green.log`, `green-full.log`, `revert.log` in this folder) show the same counts.

## Knock-on effects (run 2026-10-04)

- **Callers:** `route_to` (`uri.rb:2161-2162`) calls `route_from`. Nothing else in `lib/` does.
- **Before and after on ordinary inputs** (`knock_on.rb` in this folder: 240 URIs, every target against every base, 57,600 pairs, each checked for whether joining the base with the route gives back the target):
  - 576 pairs change, and every one goes from not round-tripping to round-tripping.
  - 56,040 pairs round-trip on both trees with the same route.
  - 408 pairs fail the round trip on both trees with the same route (other defects, see below).
  - 576 pairs raise `InvalidURIError` on both trees (a target path `/a:b` routed from a base with a different path).

| Target path | Base | Route before | Route after |
|---|---|---|---|
| `/file.txt` | `/file.txt?x=1` | `""` (joins to the base) | `"file.txt"` |
| `/a/b/` | `/a/b/?x=1` | `""` (joins to the base) | `"./"` |
| `/a:b` | `/a:b?x=1` | `""` (joins to the base) | `"./a:b"` |
| `/file.txt#f` | `/file.txt?x=1` | `"#f"` (joins to the base plus `#f`) | `"file.txt#f"` |
| (no path) | `?x=1` | `""` (joins to the base) | `"./"` |
| `/file.txt?x=1` | `/file.txt?x=1` | `"#"` | `"#"` |
| `/file.txt?y=2` | `/file.txt?x=1` | `"?y=2"` | `"?y=2"` |
| `/file.txt?x=1` | `/file.txt` | `"?x=1"` | `"?x=1"` |
| `/a/b` | `/file.txt?x=1` | `"a/b"` | `"a/b"` |
| `/file.txt` | `/file.txt` | `"#"` | `"#"` |

- **Behaviour change for existing users:** one. Code that treats an empty route as "same document" will now see a non-empty route when the base has a query and the target does not. The old empty route pointed at a different URI than the target, so the review panel judged the change acceptable (S5, focused re-review).
- **Performance:** the first version of the fix used a regex that was quadratic on long paths; the panel caught it and it was replaced by `rpartition`. Re-timed today on a 30,000-character path: 0.0145 s unpatched, 0.0145 s fixed.
- **Not fixed by this change, same before and after:** a target whose last segment contains `:` routed from a base with a different path raises `InvalidURIError`; the 408 pairs above; `URI#==` treats `./` and an empty path as equal, which is why the `./` spec compares strings.

## Review history

- **Found by** a Quality Playbook run on addressable (BUG-011 of that run).
- **Confirmed** by an independent confirmer: `evidence/review-2026-09-30-wave2/packets/addr-011/CONFIRMATION.md`.
- **Full panel** (2 executors and 13 reviewers), 2026-10-01: `evidence/review-2026-09-30-wave2/SYNTHESIS.md`. 2 SHIP, 13 FIX-REQUIRED. Three changes were required and made (`CHANGES-AFTER-PANEL.md`): the colon case raised `InvalidURIError` (now `./a:b`, with a spec); the quadratic regex (now `rpartition`); wording of the commit message and of the #126 quotation.
- **Focused re-review** of the revised code (2 executors and 7 reviewers): all nine SHIP.
- **Upstream check (2026-10-04):** `main` is at `d298c9f551fa9748d16dbfb6273b70f60b3d61bc` (2026-05-17), the commit the panel tested. The patch applies cleanly with `git am`.
- **Duplicate check (2026-10-04):** I fetched all 330 pull-request heads and searched each diff for changes to the `route_from` lines. None touches them.

## Things to know before submitting

- **Related open work:** PR #622 (not ours, 2026-09-25, "Fix colon disambiguation after path normalization") changes how a relative path with a colon is normalized. This patch applies on top of it and `uri_spec.rb` passes there (`1077 examples, 0 failures`). I did not confirm whether #622 is still open; it is not merged.
- **Maintainer activity:** the last commits by the maintainer (Bob Aman) are from 2026-04-05. Since then `main` has only dependency bumps, and five pull requests from other people opened between late August and late September are not merged. A review may take a while.
- **Process:** the repo has no CONTRIBUTING file, no PR template, no AI policy file and no CLA that I could find. The patch does not touch `CHANGELOG.md`; the changelog looks like it is written at release time, so I left it alone.
- **The #126 quotation** is in the PR text under your name. The earlier panel checked it against the issue page; I could not load the comment today. It is worth opening https://github.com/sporkmonger/addressable/issues/126 and reading it yourself.
- **Likely pushback:** "an empty route for equal paths is intended". The answer is the maintainer's own round-trip statement and RFC 3986 section 5.2.2. A maintainer may also ask why the colon case is handled only in this branch; the other branch's `InvalidURIError` is a separate, existing defect.
- **The submit script's local check may fail on your Mac.** It runs `bundle install`, and the project's Gemfile builds the native `idn-ruby` gem, which needs libidn. If that fails, the script stops after creating the branch and a second run will refuse because the branch exists. The tests were run today on this exact upstream commit, so the command below skips the local check.

## The PR as it will be submitted

**Title:** Fix route_from when only the base URI has a query

> ```ruby
> uri = Addressable::URI.parse("http://example.com/file.txt")
> uri.route_from("http://example.com/file.txt?x=1").to_s
> # actual:   ""          (joins back to "http://example.com/file.txt?x=1")
> # expected: "file.txt"  (joins back to "http://example.com/file.txt")
> ```
>
> When the paths are equal, `route_from` (lib/addressable/uri.rb) drops the path and only clears the query if both queries match. So a target without a query, routed from a base with one, gets an empty reference, which resolves back to the base. It now returns the target's last path segment, prefixed with `./` when that segment is empty or contains `:` (RFC 3986 §4.2). Three specs added to the existing `route_from` examples.
>
> In #126 sporkmonger wrote: "IIRC, `Addressable::URI.join(a, Addressable::URI.route_from(a, b)).should == b` for all sane values of `a` and `b`. ... If it does not, that is a bug."
>
> RFC 3986 §5.2.2 (Transform References): `if (R.path == "") then T.path = Base.path; if defined(R.query) then T.query = R.query; else T.query = Base.query;`
>
> Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.

## To submit

```zsh
SKIP_TESTS=1 zsh ~/Documents/QPB/evidence/SUBMIT/submit-addressable-route-from-base-query.sh
```

The script checks that `gh` is logged in as `andrewstellman`, forks the repo if needed, clones the fork to `~/src/pr-work/addressable`, applies the patch on a new branch `route-from-base-query`, pushes it to your fork and opens a **draft** PR. It does not mark the PR ready.

## Submission record

- **Submitted:** 2026-10-05 (10:47 -04:00) by Andrew, using `submit-addressable-route-from-base-query.sh`. He pasted the script's output: number 623, `isDraft: true`, the title as above.
- **PR:** [sporkmonger/addressable#623](https://github.com/sporkmonger/addressable/pull/623), opened as a **draft** from `andrewstellman:route-from-base-query` into `sporkmonger:main`; 1 commit, `50338c0`.
- **Verified by git (2026-10-05):** I fetched `refs/pull/623/head`. It is one commit on `d298c9f`, and its tree (`4497af4`) is identical to the tree made by applying this folder's patch to `d298c9f`. Blob hashes match the patch: `lib/addressable/uri.rb` `07c9aeb..de78be7`, `spec/addressable/uri_spec.rb` `0cb76fc..c7abe7e`. Author Andrew Stellman <andrew@stellman.com>; no trailers. The commit hash differs from the local one only because `git am` re-creates the commit.
- **Title and body:** a fetch of the PR page shows the title above and the body text above. That reading is a tool summary, not a byte-for-byte check.
- **Bots and CI:** none shown on the page. CI status not checked.
- **2026-10-05 (10:54 -04:00):** Andrew reports marking the PR ready for review in the browser. Not re-checked from the sandbox (its page reader has misreported draft state before); `gh pr view 623 --repo sporkmonger/addressable --json isDraft` is the exact check.
- **Still to do on Andrew's side:** nothing until a maintainer responds.
- **Maintainer responses:** none yet.
