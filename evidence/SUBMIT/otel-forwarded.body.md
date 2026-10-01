Follow-up to #15158 / #19540.

#19540 taught `HostAddressAndPortExtractor` to parse a bracketed IPv6 authority, but the sibling
`ForwardedHostAddressAndPortExtractor` still splits at the first `:`. That is the extractor
`HttpServerAttributesExtractor` uses for `server.address` / `server.port` from the `Forwarded` `host=`
parameter, `X-Forwarded-Host`, `:authority` and `Host`, so a server request with
`Host: [2001:db8::1]:8080` currently gets `server.address = "[2001"` and no `server.port`
(`Host: [::1]:8080` gives `"["`).

This adds the same `[`…`]` branch used in `HostAddressAndPortExtractor` and in the `for=` parsing of
`HttpServerAddressAndPortExtractor`: the address is the text inside the brackets and the port is parsed
after `]:`.

One behavior change for malformed values: an unterminated `[` (for example `Host: [::1`) is now
treated as malformed, like an unterminated quote, so the extractor falls through to the next header
source instead of recording `server.address = "["`.

Tests:
- new rows in `ForwardedHostAddressAndPortExtractorTest` for `Host` / `X-Forwarded-Host` / `:authority`
  and quoted `Forwarded: host="[...]"` (RFC 7239 requires IPv6 values to be quoted)
- `HttpServerAttributesExtractorTest.shouldExtractIpv6ServerAddressAndPortFromHostHeader` (attribute-level)

Before the fix the new cases fail with e.g. `expected: "2001:db8::1" but was: "[2001"`.

Found by Quality Playbook, an AI code-review tool, and fixed with Claude (Opus 5.5); I reviewed the change and the tests.
