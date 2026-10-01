# chi: `Recoverer` only recognises `Connection: Upgrade` as an exact string

**Verdict: ALREADY REPORTED.** Reproduced and fixed locally, but covered by three **open** PRs:
- **#1077, opened by `andrewstellman` on 2026-04-04** ("Fix Recoverer upgrade detection for case-insensitive tokenized Connection header"). Same fix, same test cases.
- #1170 (2026-09-01) and #1172 (2026-09-07), both titled "make Connection upgrade check token-aware and case-insensitive".
**Do not open a new PR.**
QPB source: chi-1.6.0 BUG-008.

## Pinned upstream
`3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc` (2026-09-18), go1.25.1 linux/arm64.

## Defect
`middleware/recoverer.go:39`: `if r.Header.Get("Connection") != "Upgrade" { w.WriteHeader(500) }`. The check was added by PR #795 to fix #661, where writing a 500 to a hijacked/upgraded (WebSocket) connection misbehaved. The exact-string compare misses `upgrade` (lowercase) and `keep-alive, Upgrade`. Firefox sends the latter for WebSocket handshakes.

## Expected behaviour
- RFC 9110 §7.6.1: `Connection = #connection-option`, and "Connection options are case-insensitive."
- The intent is stated in #661 and #795: "skip write header when connection has been upgrade".

## Red / green / impact
- `red.log`: 3 of 4 cases get a 500 written (`upgrade`, `keep-alive, Upgrade`, `Upgrade, keep-alive`).
- `green.log`: all pass with token-list matching.
- `hijack-demo.log`: scratch test, not in the patch. A real server, a handler that hijacks and then panics. On master, `keep-alive, Upgrade` makes net/http log `http: response.WriteHeader on hijacked connection from ...Recoverer.func1.1 (recoverer.go:40)`. With the fix, nothing is logged. With current Go, the practical impact is that spurious log line: net/http refuses the write, so no bytes reach the client. Low severity, and no security impact found.
- `suite-before.log` / `suite-after.log`: both pass (after run at `49ca853`).

## Disclosure search
`repo:go-chi/chi Recoverer Upgrade`: #1077, #1170, #1172 (all open), #795 (merged, origin), #911 (unrelated).

## Open question for Andrew
You already have #1077 open for this. Options: leave it, or refresh/ping it with this reproduction. This session posted nothing.
