<!-- DRAFT for Andrew to review and submit. Not submitted. -->
<!-- Provenance (keep or trim, but keep the AI disclosure per OTel's GenAI policy):
     Found by a Quality Playbook run (QPB v1.5.8, 2026-06-23, code-only review).
     Reproduction, fix and tests were done by Claude (Opus 5.5) and reviewed by Andrew Stellman.
     Tests were run with a standalone javac + JUnit harness, not Gradle — run
     `./gradlew :instrumentation-api:check` locally before opening. -->

**Title:** Handle bracketed IPv6 hosts in ForwardedHostAddressAndPortExtractor

Follow-up to #15158 / #19540.

#19540 taught `HostAddressAndPortExtractor` to parse a bracketed IPv6 authority, but the sibling
`ForwardedHostAddressAndPortExtractor` still splits at the first `:`. That is the extractor
`HttpServerAttributesExtractor` uses for `server.address` / `server.port` from the `Forwarded` `host=`
parameter, `X-Forwarded-Host`, `:authority` and `Host`, so a server request with
`Host: [2001:db8::1]:8080` currently gets `server.address = "[2001"` and no `server.port`
(`Host: [::1]:8080` gives `"["`).

This adds the same `[`…`]` branch used in `HostAddressAndPortExtractor` and in the `for=` parsing of
`HttpServerAddressAndPortExtractor`: the address is the text inside the brackets and the port is parsed
after `]:`. An unterminated `[` is treated as malformed, like an unterminated quote.

Tests:
- new rows in `ForwardedHostAddressAndPortExtractorTest` for `Host` / `X-Forwarded-Host` / `:authority`
  and quoted `Forwarded: host="[...]"` (RFC 7239 requires IPv6 values to be quoted)
- `HttpServerAttributesExtractorTest.shouldExtractIpv6ServerAddressAndPortFromHostHeader` (attribute-level)

Before the fix the new cases fail with e.g. `expected: "2001:db8::1" but was: "[2001"`.

The finding came from a [Quality Playbook](https://github.com/andrewstellman/quality-playbook) run; the
reproduction, fix and tests were written with Claude (Opus 5.5) and reviewed by me.
