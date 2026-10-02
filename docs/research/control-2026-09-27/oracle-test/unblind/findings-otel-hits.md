# Hits: otel

| ID | Reports that include it as a finding | Reports that mention it but do not report it |
|---|---|---|
| otel-01 | opus-run01, sonnet-run01 | — |
| otel-02 | opus-run01 | — |
| otel-03 | opus-run01 | — |
| otel-04 | opus-run01, sonnet-run01 | — |
| otel-05 | opus-run01 | — |
| otel-06 | opus-run01 | — |
| otel-07 | opus-run01 | — |
| otel-08 | opus-run01, sonnet-run01 | — |
| otel-09 | opus-run01 | — |
| otel-10 | opus-run01 | — |
| otel-11 | opus-run01 | — |
| otel-12 | opus-run01 | — |

## Deduplication judgement calls

- opus-run01 finding 2 bundled IPv6 and userinfo handling across two separate `UrlParser` copies (incubator and reactor-netty). Split into four rows (otel-05, otel-10, otel-06, otel-11): IPv6 and userinfo need separate fixes, and the two copies are separate code, so fixing one file does not fix the other. The reactor-netty rows include the fallback to the scheme-default port, since that is the observed consequence of the parse failure there.
- opus-run01 finding 3 bundled IPv6 and comma-list handling in `ForwardedHostAddressAndPortExtractor`; split into otel-02 and otel-07. The `Forwarded` comma case and the `X-Forwarded-Host` comma case were kept as one row (otel-07) because both values reach `extractHost`, where treating `,` as a terminator fixes both.
- Both reports bundled the `length() - 1` check across three files; split into otel-04, otel-01, otel-08 because each is a separate method with its own fix. opus-run01 cites HttpServerAddressAndPortExtractor.java line 53; the check is at line 51 in the checkout.
- opus-run01 cites incubator `getPath` at lines 74-77; the `indexOf('/', ...)` call is at line 73 in the checkout.
- sonnet-run01's "Areas reviewed but found correct" says both `UrlParser` copies' host/port/path scanning was traced by hand and matches documented behaviour, and lists `ResponseReceiverInstrumentation` as reviewed with no logic errors. These are general statements that do not discuss the specific inputs in otel-03, otel-05, otel-10, otel-06, otel-11 or otel-09, so under the strict rule they were not counted as mentions. A looser reading would put sonnet-run01 in the mention column for those rows.
- sonnet-run01's notes on `X-Forwarded-For` port never being set and on the `InstrumentationContexts` queue are considered-and-rejected items that no report lists as a finding, so they have no row.
