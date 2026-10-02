# Hits: aiohttp

| ID | Reports that include it as a finding | Reports that mention it but do not report it |
|---|---|---|
| aiohttp-01 | sonnet-run08, sonnet-run09, sonnet-run10 | sonnet-run03 |
| aiohttp-02 | opus-run02, opus-run04, opus-run05, opus-run07, opus-run09, opus-run10 | — |
| aiohttp-03 | opus-run05 | — |
| aiohttp-04 | opus-run04, sonnet-run09 | — |
| aiohttp-05 | opus-run08, sonnet-run03, sonnet-run09 | — |
| aiohttp-06 | opus-run01, opus-run02, opus-run04, opus-run05, opus-run07 | — |
| aiohttp-07 | opus-run02, opus-run04, opus-run05, opus-run07 | opus-run09 |
| aiohttp-08 | opus-run02, opus-run04, opus-run05, opus-run07, opus-run09, opus-run10, sonnet-run01 | — |
| aiohttp-09 | sonnet-run01, sonnet-run04 | — |
| aiohttp-10 | opus-run04, opus-run05, opus-run07, opus-run09, sonnet-run09 | opus-run10 |
| aiohttp-11 | sonnet-run01 | — |
| aiohttp-12 | sonnet-run05 | — |
| aiohttp-13 | opus-run08, sonnet-run09, sonnet-run10 | — |
| aiohttp-14 | sonnet-run01 | — |
| aiohttp-15 | opus-run04 | — |
| aiohttp-16 | opus-run09, opus-run10 | — |
| aiohttp-17 | opus-run01, opus-run02, opus-run09, opus-run10 | — |
| aiohttp-18 | sonnet-run05 | — |
| aiohttp-19 | opus-run04 | — |
| aiohttp-20 | sonnet-run05 | sonnet-run09 |
| aiohttp-21 | sonnet-run03 | — |
| aiohttp-22 | opus-run04, opus-run07, sonnet-run04 | — |
| aiohttp-23 | sonnet-run10 | — |
| aiohttp-24 | opus-run01, opus-run02, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10, sonnet-run01, sonnet-run10 | sonnet-run04 |
| aiohttp-25 | opus-run01, opus-run02, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10 | — |
| aiohttp-26 | sonnet-run01, sonnet-run03, sonnet-run09 | — |
| aiohttp-27 | sonnet-run04 | — |
| aiohttp-28 | sonnet-run04 | — |
| aiohttp-29 | opus-run04 | — |
| aiohttp-30 | opus-run02, opus-run04, opus-run05, opus-run07, opus-run09, opus-run10 | — |
| aiohttp-31 | opus-run01, opus-run02 | — |
| aiohttp-32 | sonnet-run01 | — |
| aiohttp-33 | opus-run01, opus-run02, opus-run05 | — |
| aiohttp-34 | sonnet-run08 | — |
| aiohttp-35 | sonnet-run03 | — |
| aiohttp-36 | sonnet-run09 | — |
| aiohttp-37 | opus-run06 | — |
| aiohttp-38 | sonnet-run05 | sonnet-run02 |
| aiohttp-39 | opus-run01, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08 | — |
| aiohttp-40 | opus-run04, opus-run10 | — |
| aiohttp-41 | sonnet-run04 | — |
| aiohttp-42 | sonnet-run07 | — |
| aiohttp-43 | opus-run08, opus-run10, sonnet-run01 | — |
| aiohttp-44 | opus-run04 | — |
| aiohttp-45 | opus-run06, opus-run07 | — |
| aiohttp-46 | opus-run04 | — |
| aiohttp-47 | opus-run10 | — |
| aiohttp-48 | sonnet-run01, sonnet-run06 | — |
| aiohttp-49 | opus-run03, opus-run06, opus-run08, opus-run10, sonnet-run04, sonnet-run08 | — |
| aiohttp-50 | opus-run02, opus-run05, opus-run07 | — |
| aiohttp-51 | sonnet-run04, sonnet-run09 | — |
| aiohttp-52 | sonnet-run03 | — |
| aiohttp-53 | opus-run05, opus-run07 | — |
| aiohttp-54 | opus-run09 | — |
| aiohttp-55 | sonnet-run05 | — |
| aiohttp-56 | sonnet-run03 | sonnet-run08 |
| aiohttp-57 | opus-run02, opus-run06, opus-run07, opus-run08, opus-run09, sonnet-run06, sonnet-run08, sonnet-run09 | opus-run10 |
| aiohttp-58 | sonnet-run06 | — |
| aiohttp-59 | opus-run02, opus-run03, opus-run04, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10 | — |
| aiohttp-60 | opus-run05, opus-run09 | opus-run08, opus-run10 |
| aiohttp-61 | opus-run08, sonnet-run04 | — |

## Deduplication judgement calls

- **Column rules.** A report counts under "include" only when the item appears in its numbered or headed defect list. Items that a report puts in a "considered and not reported", "lower-confidence, not filed", "not included as headline defects" or "investigated and disproven" section count as "mention". This includes opus-run07's #13 (`max_redirects`), which is numbered but labelled lower confidence; it counts as include. Generic "area checked, no defect" lines that do not name the specific behaviour count in neither column. Examples: "CookieJar domain/path matching", "suffix-range handling", "max-age/expires precedence".
- **aiohttp-17 / aiohttp-16.** `_charset_` handling is split into two findings: the unconsumed delimiter, and the `read_chunk(32)` assertion on long boundaries. The fix for one does not fix the other. opus-run09 and opus-run10 each bundle both.
- **aiohttp-25 / aiohttp-43.** The stale expiry after replacement by a session cookie is aiohttp-25. opus-run05 and opus-run06 also note that an unparseable Max-Age leaves the old expiry in place; that is folded into aiohttp-25. The unparseable Max-Age that suppresses Expires is aiohttp-43. opus-run10 bundles aiohttp-43 under its aiohttp-25 heading.
- **aiohttp-06 / aiohttp-23.** Both concern `HeadersDictProxy.getall` comma splitting, but they are kept separate. aiohttp-06 is commas inside `<...>` in Link. aiohttp-23 is Date and Set-Cookie values being split at all. The fixes differ.
- **aiohttp-33 / aiohttp-29.** `HeadersDictProxy` iteration/len and `__eq__` are separate findings.
- **aiohttp-50 / aiohttp-53 / aiohttp-02.** The fresh decompressor per chunk in `BodyPartReaderPayload.write` is aiohttp-50. Quoted-printable decoded per chunk is aiohttp-53. The sync `decode()` truncation is aiohttp-02. opus-run05 reports aiohttp-53 via `request.post()`. opus-run07 states within its aiohttp-50 finding that quoted-printable is "affected the same way", and this counts as include for aiohttp-53.
- **aiohttp-59 / aiohttp-54.** opus-run09 reports that `MultipartWriter.decode()` ignores `encoding`/`errors` for part bodies (aiohttp-54). opus-run10 only adds "pass `encoding, errors`" to its fix text for aiohttp-59 and does not list the behaviour. It is counted in neither column for aiohttp-54.
- **aiohttp-08 / aiohttp-30.** Accept-Encoding `q=0` is split into `StreamResponse` compression (aiohttp-08) and `FileResponse` sibling selection (aiohttp-30). Reports that bundle both are credited with both. sonnet-run01 covers only aiohttp-08.
- **aiohttp-49 / aiohttp-47.** `chunked=False` still enabling chunking (aiohttp-49) is separate from a user-supplied `Transfer-Encoding: chunked` header producing TE+CL with an unchunked body (aiohttp-47). opus-run08's `data=None` variant is folded into aiohttp-49.
- **aiohttp-46 / aiohttp-15.** opus-run04 #12 is split into two findings: `EmptyStreamReader.readuntil` and `total_raw_bytes`.
- **aiohttp-61 / aiohttp-05 / aiohttp-13.** Access-log format problems are split three ways: `%%` (aiohttp-61), `%{FOO}e` (aiohttp-05) and `%O` (aiohttp-13). opus-run08 reports all three. sonnet-run03 reports only `e`. sonnet-run09 reports `e` and `O`. sonnet-run10 reports only `O`.
- **aiohttp-35 / aiohttp-52.** sonnet-run03 #5 is split into the chunk-size-line branch and the trailer-line branch.
- **aiohttp-10 / aiohttp-36 / aiohttp-01.** sonnet-run09 #6 is the multi-byte separator in `readuntil` (aiohttp-10). Its #7 bundles `readuntil` `max_size=0` (aiohttp-36) with payload `remaining_content_len or DEFAULT_CHUNK_SIZE` (aiohttp-01), so #7 is split.
- **aiohttp-01 mention.** sonnet-run03 says a "zero-length read in `IOBasePayload.write_with_length`" was investigated with reproduction scripts and ruled out. This is treated as a mention of aiohttp-01.
- **aiohttp-38 mention.** sonnet-run02 describes the "fewer than 4 base64 chars in a non-final chunk, no carry" case as a documented, accepted tradeoff. This is treated as a mention.
- **aiohttp-24 mention.** sonnet-run04 lists `bytes=-0` under "Lower-confidence observations (not filed as confirmed defects)", so it counts as a mention. sonnet-run08 (aiohttp-56), sonnet-run09 (aiohttp-20) and opus-run10 (aiohttp-60, aiohttp-57, aiohttp-10) are handled the same way.
- **aiohttp-39.** opus-run08 also notes that the quoted alternative accepts control characters. This is folded into aiohttp-39 because it has the same regex and the same fix.
- **aiohttp-31.** The retry and same-origin-redirect variants of the popped `Host` header are one finding.
- **aiohttp-32 / aiohttp-27.** sonnet-run01 (no unescaping) and sonnet-run04 (comma-separated elements) describe the `forwarded` pair loop in isolation. These are phrased at the level of the cited code in the property, because values reach it via `HeadersDictProxy.getall`.
- **aiohttp-16.** Reports disagree on the exact boundary length that triggers the assertion: "longer than 30 characters" versus "29 characters or more". The observed behaviour uses the WebKit-style example both reports give.
- **Items mentioned but reported by no one, so not in the list.** These were:
  - sonnet-run04: `web_ws.receive(timeout=0)` using `or`
  - sonnet-run04: `client_ws.receive()` setting `close_code` on timeout
  - sonnet-run04: `connector._close_immediately` not clearing `_acquired_per_host`
  - sonnet-run09: `EmptyStreamReader.begin_http_chunk_receiving` / `end_http_chunk_receiving`
  - sonnet-run09: `make_mocked_request` exact `Connection: upgrade` compare
  - sonnet-run10: timer ceil threshold `>=` vs `>`
  - sonnet-run10: `AsyncResolver` link-local port not reassigned
  - opus-run09: digest `unescape_quotes` ordering
  - sonnet-run01: base64 multipart "Reading after EOF" (disproven)
  - sonnet-run03: concatenated gzip under a length cap (ruled out)
  - sonnet-run06: `StaticResource.resolve` non-normalized path, and duplicate Content-Length (ruled out)
- **sonnet-run02** reports no defects.
