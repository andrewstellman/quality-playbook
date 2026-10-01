**Title:** Handle bracketed IPv6 hosts in UrlParser

`UrlParser.getHostEndIndexExclusive` (in `instrumentation-api-incubator` and its copy in
`reactor-netty-1.0`) ends the host at the first `:`, which for an IPv6 authority is inside the
brackets:

```
UrlParser.getHost("http://[::1]:8080/")              -> "["
UrlParser.getHost("https://[2001:db8::1]:8443/path") -> "[2001"
UrlParser.getPort("http://[::1]:8080/")              -> null
```

Callers affected:
- `ReactorNettyHttpClientAttributesGetter` reports `server.address` `"["`, and because `getPort`
  returns null it falls back to port 80/443.
- `ServicePeerResolver` indexes a `service_peer_mapping` entry like `[::1]:8080` under host `"["`,
  so it never matches.
- `ClickHouseClientV2Singletons` (`CurrentServerInfo`) calls `getHost`/`getPort` on a single
  configured endpoint, so an IPv6 endpoint gets the same wrong address and no port.

This PR ends the host at the closing `]` (RFC 3986 §3.2.2) and has `getHost` return the address
without brackets, the same as `HostAddressAndPortExtractor` (#19540). `getPort` now returns the port
(8080 above) instead of null. A `[` with no closing `]` before the first `/`, `?` or `#` is treated
as having no host, so `getHost("http://[x/p?token=abc]")` returns null and path or query text
can't end up in the host.

The pulsar instrumentation has its own `UrlParser` with the same first-`:` split; I left it for a
follow-up to keep this PR to the shared parser and its reactor-netty copy.

Tests: `testGetHostAndPortWithIpv6` in both `UrlParserTest`s, plus IPv6 rows in
`ServicePeerResolverTest`.

Found and fixed with help from Claude (Opus 5.5); I reviewed the change and the tests.
