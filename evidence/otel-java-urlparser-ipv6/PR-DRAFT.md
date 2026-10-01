<!-- DRAFT for Andrew to review and submit. Not submitted. -->
<!-- Provenance: found by a Quality Playbook run (QPB v1.5.8, 2026-06-23, code-only review).
     Reproduction, fix and tests were done by Claude (Opus 5.5), reviewed by Andrew Stellman.
     Tests ran in a standalone javac + JUnit harness, not Gradle — run
     `./gradlew :instrumentation-api-incubator:test :instrumentation:reactor:reactor-netty:reactor-netty-1.0:javaagent-unit-tests:test`
     (and spotless) locally before opening. -->

**Title:** Handle bracketed IPv6 hosts in UrlParser

`UrlParser.getHostEndIndexExclusive` (in `instrumentation-api-incubator` and its copy in
`reactor-netty-1.0`) ends the host at the first `:`, which for an IPv6 authority is inside the brackets:

```
UrlParser.getHost("http://[::1]:8080/")              -> "["
UrlParser.getHost("https://[2001:db8::1]:8443/path") -> "[2001"
UrlParser.getPort(...)                               -> null
```

Visible effects:
- reactor-netty HTTP client spans get `server.address = "["` and `server.port` falls back to the scheme default (80/443).
- a `service_peer_mapping` entry like `[::1]:8080` is indexed under host `"["`, so it never matches.

This PR makes the host end at the closing `]` (RFC 3986 §3.2.2) and has `getHost` return the address
without brackets, the same as `HostAddressAndPortExtractor` (#19540) and the DB target parsing.
An unterminated `[` is treated as having no host.

Tests: `testGetHostAndPortWithIpv6` in both `UrlParserTest`s, plus an IPv6 row in `ServicePeerResolverTest`.

The finding came from a [Quality Playbook](https://github.com/andrewstellman/quality-playbook) run; the
reproduction, fix and tests were written with Claude (Opus 5.5) and reviewed by me.
