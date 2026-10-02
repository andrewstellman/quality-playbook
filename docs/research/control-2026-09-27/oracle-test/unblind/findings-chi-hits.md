# Hits: chi

| ID | Reports that include it as a finding | Reports that mention it but do not report it |
|---|---|---|
| chi-01 | sonnet-run09 | sonnet-run01, sonnet-run04 |
| chi-02 | opus-run10 | opus-run07, opus-run08 |
| chi-03 | opus-run10 | opus-run07 |
| chi-04 | opus-run01, opus-run03, opus-run10 | opus-run06, opus-run08, opus-run09 |
| chi-05 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run10 | |
| chi-06 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10, sonnet-run01, sonnet-run03, sonnet-run06, sonnet-run07, sonnet-run08 | sonnet-run02 |
| chi-07 | opus-run01, opus-run03, opus-run07, opus-run08, opus-run09, opus-run10 | |
| chi-08 | opus-run04, opus-run07 | |
| chi-09 | opus-run07 | sonnet-run05 |
| chi-10 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10, sonnet-run03, sonnet-run04 | |
| chi-11 | opus-run02, opus-run04, opus-run05 | |
| chi-12 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10 | |
| chi-13 | opus-run01, opus-run05, opus-run10, sonnet-run08 | |
| chi-14 | opus-run01, opus-run04, opus-run07 | |
| chi-15 | opus-run10 | |
| chi-16 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10, sonnet-run06, sonnet-run07 | sonnet-run04 |
| chi-17 | opus-run02, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10 | |
| chi-18 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run07, opus-run08, opus-run09 | |
| chi-19 | opus-run07, sonnet-run03 | |
| chi-20 | opus-run02, opus-run03, opus-run07, opus-run08, opus-run09 | opus-run06 |
| chi-21 | opus-run01, opus-run02, opus-run03, opus-run10 | opus-run08 |
| chi-22 | opus-run05, opus-run06 | opus-run09 |
| chi-23 | opus-run10 | |
| chi-24 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10, sonnet-run02, sonnet-run10 | |
| chi-25 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10 | |
| chi-26 | sonnet-run08 | |
| chi-27 | opus-run06, opus-run10 | opus-run07 |
| chi-28 | opus-run10 | |
| chi-29 | opus-run04 | |
| chi-30 | opus-run09 | opus-run01, opus-run03, opus-run04, opus-run06, opus-run07, opus-run08, opus-run10, sonnet-run01 |
| chi-31 | opus-run07, opus-run09, opus-run10 | |
| chi-32 | opus-run03, opus-run05, opus-run08, opus-run09 | |
| chi-33 | opus-run01, opus-run02, opus-run03, opus-run06, opus-run07, opus-run08, opus-run10, sonnet-run01, sonnet-run03, sonnet-run06, sonnet-run08, sonnet-run10 | sonnet-run09 |
| chi-34 | opus-run05 | opus-run06 |
| chi-35 | opus-run06, opus-run07 | |

## Deduplication judgement calls

- **chi-06 / chi-16 (q=0 vs substring match).** Nearly every report bundles these. Split because parsing q-values does not by itself remove substring matching. A report counts for chi-16 only if it describes a token merely *containing* the name matching. sonnet-run01/03/08 only prescribe "exact match" in their fix, so not counted for chi-16. sonnet-run02 describes "a known imprecision around q=0" in its rejected section: a mention for chi-06.
- **chi-10 / chi-29 / chi-07 (SupressNotFound).** chi-10 is the shared-context mutation (mounted 404, root handler serving mounted path, duplicated params): one fix. chi-29 (404 instead of 405) is separate because a fresh context still returns false on method mismatch. chi-07 (look-ahead uses `r.URL.Path`) is separate; counted only where the report explicitly calls that choice deficient (opus-run01, 03, 07, 08, 09, 10). opus-run04/05/06 only prescribe "compute path the way GetHead does" in the fix: neither column.
- **chi-09 / chi-19.** opus-run07 D6 bundles case and whitespace; `ToLower` and `TrimSpace` are independent fixes.
- **chi-08 / chi-18 / chi-20 (ContentCharset).** Three separate fixes. opus-run08 carries chi-20 as a "side issue" inside its finding, counted as included.
- **chi-12 / chi-35 (RedirectSlashes).** Mount prefix vs. re-escaping. opus-run06 and opus-run07 report both.
- **chi-22 / chi-03 / chi-02 (RawPath).** chi-22: StripSlashes with route context and empty RoutePath. chi-03: no-context branch; opus-run10 raises it inside its PathRewrite finding (chi-02). opus-run09's rejected note on StripSlashes/URLFormat deriving the path from `r.URL.Path` is a mention of chi-22; the URLFormat half has no row.
- **chi-11 / chi-27 (URLFormat).** Dotfile-as-extension vs. panic with no `/`. opus-run03's and sonnet-run03's vague notes: neither column.
- **chi-14 / chi-15 (Sunset).** Format vs. non-UTC time. opus-run10 extends chi-15 to Deprecation.
- **chi-13 / chi-25 / chi-33 (RouteHeaders).** Host lookup, pattern case, map order. opus-run10 bundles Host and case and adds map order as "Related": counted for all three.
- **chi-30 (Timeout).** opus-run03's "small race" and sonnet-run01's detailed decline are mentions. sonnet-run05's note is about `DeadlineExceeded` vs `Canceled`: not counted.
- **chi-01 (BasicAuth).** sonnet-run01 and sonnet-run04 count as mentions.
- **Not made into rows** (never reported as a defect): `rctx` nil parenthetical (sonnet-run03/04); the test-file `Header.Set` loop (sonnet-run02); rejected-only items: Logger status 0, NoCache deleting conditional headers, Throttle zero BacklogTimeout / Retry-After truncation, missing `Vary`, `http2FancyWriter` ReadFrom, CleanPath not cleaning an already-set RoutePath, RealIP spoofing, `SetEncoder` mutate-while-ranging.
