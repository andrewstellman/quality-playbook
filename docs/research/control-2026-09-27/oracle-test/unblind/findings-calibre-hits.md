# Hits: calibre

| ID | Reports that include it as a finding | Reports that mention it but do not report it |
|---|---|---|
| calibre-01 | opus-run01 | — |
| calibre-02 | opus-run03, opus-run05, opus-run06 | — |
| calibre-03 | opus-run07 | — |
| calibre-04 | opus-run03, opus-run05, opus-run06, opus-run08 | — |
| calibre-05 | opus-run01, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run09, opus-run10 | — |
| calibre-06 | opus-run01, opus-run02, opus-run03, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, sonnet-run10 | — |
| calibre-07 | opus-run04 | — |
| calibre-08 | opus-run08 | — |
| calibre-09 | opus-run06, opus-run07, opus-run09 | — |
| calibre-10 | sonnet-run01, sonnet-run02, sonnet-run05, sonnet-run07, sonnet-run09, sonnet-run10 | — |
| calibre-11 | opus-run05 | — |
| calibre-12 | opus-run08 | — |
| calibre-13 | opus-run05, opus-run06, opus-run07 | — |
| calibre-14 | opus-run01, opus-run02, opus-run04, opus-run05, opus-run06, opus-run08, opus-run09, opus-run10, sonnet-run01, sonnet-run03, sonnet-run06 | — |
| calibre-15 | opus-run09 | — |
| calibre-16 | opus-run01, opus-run02, opus-run03, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10 | — |
| calibre-17 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10 | sonnet-run02 |
| calibre-18 | sonnet-run01, sonnet-run02, sonnet-run05, sonnet-run07, sonnet-run09, sonnet-run10 | — |
| calibre-19 | opus-run08 | — |
| calibre-20 | opus-run04, opus-run09 | opus-run02 |
| calibre-21 | opus-run04, opus-run07 | — |
| calibre-22 | opus-run01, opus-run02, opus-run03, opus-run06, opus-run08, opus-run10 | — |
| calibre-23 | sonnet-run01, sonnet-run02, sonnet-run05, sonnet-run07, sonnet-run09, sonnet-run10 | — |
| calibre-24 | opus-run01, opus-run02, opus-run05, opus-run07, opus-run08 | — |
| calibre-25 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10, sonnet-run04, sonnet-run08, sonnet-run10 | — |
| calibre-26 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10, sonnet-run02, sonnet-run07, sonnet-run10 | — |
| calibre-27 | opus-run01, opus-run02, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08 | — |
| calibre-28 | opus-run01, opus-run05, opus-run06, opus-run08, sonnet-run10 | — |
| calibre-29 | opus-run08 | — |
| calibre-30 | opus-run03, opus-run05, opus-run07, opus-run09, opus-run10 | — |
| calibre-31 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10, sonnet-run03, sonnet-run05 | — |
| calibre-32 | opus-run07, opus-run09 | — |
| calibre-33 | sonnet-run10 | — |
| calibre-34 | opus-run08 | — |
| calibre-35 | opus-run03 | — |
| calibre-36 | opus-run08 | — |
| calibre-37 | opus-run04 | — |
| calibre-38 | opus-run05, opus-run06, opus-run07 | — |
| calibre-39 | opus-run02, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10 | — |
| calibre-40 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run08, opus-run09, opus-run10 | — |
| calibre-41 | opus-run01, opus-run02, opus-run04, opus-run06, opus-run08, opus-run09, opus-run10 | — |
| calibre-42 | opus-run07 | — |
| calibre-43 | opus-run08 | — |
| calibre-44 | opus-run04 | — |
| calibre-45 | opus-run01 | — |
| calibre-46 | opus-run08 | — |
| calibre-47 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run06, opus-run08, opus-run10 | — |
| calibre-48 | opus-run05, opus-run08 | — |
| calibre-49 | opus-run01 | opus-run05 |
| calibre-50 | opus-run03, opus-run07, opus-run09, opus-run10 | — |
| calibre-51 | opus-run10 | — |
| calibre-52 | opus-run02, opus-run03, opus-run05, opus-run06, opus-run10 | — |
| calibre-53 | opus-run01, opus-run02, opus-run05, opus-run06 | — |
| calibre-54 | opus-run03, opus-run05, opus-run06, opus-run09 | sonnet-run10 |
| calibre-55 | opus-run08 | — |
| calibre-56 | opus-run08 | — |
| calibre-57 | opus-run08 | — |
| calibre-58 | opus-run08 | — |
| calibre-59 | opus-run01, opus-run05 | — |
| calibre-60 | sonnet-run10 | opus-run02 |
| calibre-61 | opus-run05, opus-run06, opus-run08, sonnet-run10 | — |
| calibre-62 | opus-run08, sonnet-run10 | — |

## Deduplication judgement calls

- Negative chunk sizes (calibre-14) and acceptance of `0x`/`+`/`_` forms (calibre-41) are split: rejecting `chunk_size < 0` fixes the first but not the second. Reports that only mention `+`/`-` in passing while describing the negative case (sonnet-run03, sonnet-run06) are counted for calibre-14 only.
- Chunk-extension rejection (calibre-54) and trailer rejection (calibre-35) are split from each other and from the chunk-size findings. opus-run01's fix text mentions extensions but reports no extension behaviour, so it is not counted for calibre-54. opus-run09 lists extensions as a "related, minor" note inside its finding and is counted as including it. sonnet-run10 lists it under "not reported", so it is a mention.
- BanList: never pruning entries (calibre-31) and reusing a stale per-key fail count (calibre-16) are split, because iterating oldest-first prunes other keys' entries but does not reset the current key's own count (its old entry is popped and re-inserted before the pruning loop runs). Reports that describe only memory growth (opus-run04, sonnet-run03, sonnet-run05) are counted for calibre-31 only.
- get_ranges is split into four: no `-` gives 500 (calibre-26); `bytes=-0` (calibre-17); suffix range on an empty resource (calibre-47); `bytes=--5` giving a negative size (calibre-53). The fixes differ (guard the unpack; skip `stop == 0`; skip `content_length == 0`; digit-only parsing).
- sonnet-run02 puts `bytes=-0` in a "Lower-confidence / minor observation (not filed as a separate ... defect)" section. It is recorded as a mention for calibre-17, not an inclusion.
- The HTTP/1.0 `is_http1` finding (calibre-25) includes its `Accept-Ranges`/206 consequences. The case where a `GeneratedOutput` of unknown length is still chunked to HTTP/1.0 (calibre-52) is split out, because fixing the `is_http1` argument does not change line 793. Counted for opus-run03, opus-run05 and opus-run06, which note it explicitly as a separate remaining issue, and for opus-run02 and opus-run10, which list unknown-length output being chunked among the HTTP/1.0 effects.
- `Accept-Ranges` advertised for non-range outputs (calibre-40) is kept separate from the Range+gzip chunked/Content-Length conflict (calibre-39); different lines, different fixes.
- `q=0` accepted (calibre-05) and `; q=` whitespace not parsed (calibre-30) are split.
- Data files: remove accepting non-data relpaths (calibre-24) and upload accepting `../` names (calibre-29, opus-run08 only) are split; opus-run08 bundled them.
- `/cdb/add-book` shared temp path is split into the same-name collision (calibre-38) and the upload never being deleted (calibre-13).
- OPDS: `max_opds_ungrouped_items = 0` (calibre-45), `sort=None` crash (calibre-49) and `sort=''` counted in no group (calibre-01) are split from opus-run01's bundle. opus-run05's "considered and not reported" entry on `Tag.sort is None` counts as a mention of calibre-49.
- WebSocket: codes >= 5000 (calibre-50) and mid-UTF-8 reason truncation (calibre-42) are split from opus-run07's bundle. opus-run02's "not reported" note on codes 1012-1014 describes a different behaviour and is not counted for calibre-50.
- Header parsing: obs-fold CRLF kept (calibre-21), no-colon line accepted (calibre-07) and whitespace before colon accepted (calibre-44) are split.
- parse_smil_time is split three ways (calibre-34, calibre-08, calibre-56): `ms` ordering, bare number, and the 59 clamp. Each needs a different fix.
- `output_fmt` path traversal: opus-run08 and sonnet-run10 describe the same code path and are merged into calibre-62.
- The three `except A, B:` sites (calibre-18, calibre-23, calibre-10) are kept as three findings, one per file, as every reporting run listed them.
- Status line hard-coded to HTTP/1.1 (calibre-60): sonnet-run10 reports it. opus-run02 lists it under "considered and not reported", so it is a mention.
- `GeneratedOutput` `None >= int` TypeError (calibre-20): opus-run02 lists it under "considered and not reported", so it is a mention.
- Generic "checked, no defect found" statements that name a function or area but do not describe the specific behaviour are not counted as mentions. Examples: sonnet-run05/07/08 on get_ranges, header continuation and chunk accounting; opus-run04 on "close-code validation"; opus-run08 on "WebSocket close handling" and "the HTTP header parser"; sonnet-run03's remark that `is_banned` still applies the interval.
- Items raised by reports only as non-defects, with no report listing them as a finding, have no row. These include non-constant-time password comparison, `routes.py` PEP 695 syntax, unused `MESSAGE_TOO_BIG`, `Offsets` with total 0, `parse_http_list` with bytes, 408 during WAIT, and `ThreadPool.stop` on `Full`.
- Line numbers were checked against the checkout. opus-run05 cites legacy.py:117 and loop.py:612-613 for calibre-48 and calibre-06; the code is at legacy.py:122 and loop.py:615-616.
