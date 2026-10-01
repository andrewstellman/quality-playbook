# Disclosure search: aiohttp readuntil split separator

Date: 2026-09-27. All requests used the `mcp__workspace__web_fetch` tool (no curl, wget or Python requests). Rows 1, 2, 2b, 6 and 11 were fetched by the main agent. Rows 1 and 3-14 were run by a delegated subagent with the same tool; its results are recorded as it reported them. The main agent's own fetches of rows 1, 6 and 11 matched the subagent's counts.

GitHub search is lexical and does not cover every comment, external tracker or private report, so "nothing found" does not prove the defect is unreported.

## Queries and results

| # | Query / URL | total_count | Results and relevance |
|---|---|---|---|
| 1 | `https://api.github.com/search/issues?q=repo:aio-libs/aiohttp+readuntil&per_page=100` (main agent) and `per_page=50` (subagent) | 23 | Items seen in the response: #13686, #13807, #13806 (docs signature fix and backports), #13825 (open draft, docs signatures), #1800, #12393 (LineTooLong message), #13467, #12208, #12262, #3881, #4397, #8643, #6810, #6701, #7079, #4054, #4734, #5196. The saved response contained 18 items although total_count was 23 (incomplete_results false); the missing 5 were not identified. None describes a separator split across chunks. |
| 2 | `repo:aio-libs/aiohttp readuntil separator` (main agent) | 10 | #13686, #13807, #13806, #12393, #3881, #8643, #6701, #6810, #7079, #4734. No match. |
| 2b | `repo:aio-libs/aiohttp readuntil chunk` (main agent) | 7 | #13807, #13825, #12393, #3881, #8643, #4397, #579. No match. |
| 3 | `repo:aio-libs/aiohttp "chunk boundary"` | 30 | #13348 (C parser pause/EOF race, ContentLengthError), #8643, old multipart PRs #757, #1900, #454. No match. |
| 4 | `repo:aio-libs/aiohttp separator split` | 16 | #12996/#13003 (content-disposition whitespace), #11355, #12119/#12121/#12122 (chunked size mismatch hang), #10141. No match. |
| 5 | `repo:aio-libs/aiohttp delimiter split` | 2 | #13058 (parse_mimetype), #1476 (CI bot). No match. |
| 6 | `repo:aio-libs/aiohttp "split delimiter"` (main agent verified) | 0 | none |
| 7 | `repo:aio-libs/aiohttp readline split chunk` | 5 | #13348, #8643, #757, #1900, #454. No match. |
| 8 | `repo:aio-libs/aiohttp readline separator` | 4 | #12228, #8643, #6701, #4734. No match. |
| 9 | `repo:aio-libs/aiohttp readuntil in:comments` | 12 | #13807, #13686, #13806, #1800, #13467, #12208, #12262, #4397, #1689, #681, #579, #1151 (original readuntil feature request, 2016). No match. |
| 10 | `repo:aio-libs/aiohttp StreamReader separator` | 9 | Same cluster as above. No match. |
| 11 | `repo:aio-libs/aiohttp readuntil is:open` (main agent verified) | 1 | #13825, open draft "Correct API reference signatures that drifted from the code". Docs only. |
| 12 | `https://github.com/aio-libs/aiohttp/issues?q=readuntil` | n/a | HTTP 200, but the page is client-rendered; no issue list was extractable. |
| 13 | `https://github.com/aio-libs/aiohttp/pulls?q=readuntil` | n/a | Same: no extractable list. |
| 14 | `https://github.com/aio-libs/aiohttp/security/advisories` | n/a | Page 1 of 5 listed 10 advisories; none mentions readuntil, readline or separator handling. Nearest by theme (subagent-read): GHSA-63hw-fmq6-xxg2 "C HTTP Parser Bypasses max_line_size for Fragmented Lines" (CVE-2026-54277, fixed 3.14.1), a length-limit bypass in the C HTTP parser, different code path and defect class. Pages 2-5 were not read. |

## Near misses read in full

- #6701 / PR #6810 (backport #7079), 2022: readuntil with a multi-byte separator computed the wrong read length when the buffer offset was non-zero. That fix produced the current `ichar - offset + seplen - 1` expression. It is a single-chunk bug, not the cross-chunk one.
- #8643, 2024, closed: multipart body boundary split across chunks, in `BodyPartReader`'s own boundary scan (it reads with `read(n)`), not `StreamReader.readuntil`. Same symptom family, different code.
- #13686 (merged 2026-09-24) and #13825 (open draft): documentation of the readuntil signature only.

## Conclusion

No existing issue, PR or advisory reporting or fixing this defect was found. Prior triage (`docs/research/triage-2026-09-27/nonlinux/evidence/extra-disclosure-search.json`) reached the same result at commit 25f3057.
