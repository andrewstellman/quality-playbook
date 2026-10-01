# chi: `RegisterMethod` races with requests being served

**Verdict: NEEDS-MAINTAINER-INPUT, leaning "working as designed".** The data race reproduces under `-race`, but the maintainer designed `RegisterMethod` for `init()`-time use. A code fix (a lock on the per-request hot path) is not recommended. At most, a one-line doc-comment clarification.
QPB source: chi-1.6.0 BUG-009.

## Pinned upstream
`3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc` (2026-09-18), go1.25.1 linux/arm64.

## Behaviour
`RegisterMethod` (`tree.go:68-86`) writes the package-level `methodMap`, `reverseMethodMap` and `mALL` with no synchronisation. `routeHTTP` reads `methodMap` on every request (`mux.go:476` in the race report). Calling `RegisterMethod` while a router is serving is a data race.

## Evidence
- `red.log`: `go test -race` gives `WARNING: DATA RACE`, read at `mux.go:476` (`routeHTTP`), previous write at `tree.go:83` (`RegisterMethod`), `race detected during execution of test`.
- `without-race-detector.log`: the same test without `-race`, `-count=20`, passes. No crash was observed. Note that the method is only newly registered in the first iteration.
- `suite-before.log`, `suite-before-race.log`: master passes both normally and under `-race`.
- No fix written.

## Why "working as designed"
- The doc comment (`tree.go:68-69`) says only: "RegisterMethod adds support for custom HTTP method handlers, available via Router#Method and Router#MethodFunc". It does not state when it may be called.
- PR #271 (maintainer pkieltyka, 2017), which added it: "Please use chi.RegisterMethod("LINK") and chi.RegisterMethod("UNLINK") in an init function instead."
- `_examples/custom-method/main.go:10-14` calls it from `func init()`.
- A route for a custom method must be registered after `RegisterMethod` (otherwise `Mux.Method` panics). chi's route tree is not synchronised for adding routes while serving either, so registering methods at runtime is already outside the supported pattern.

## Disclosure search
`repo:go-chi/chi RegisterMethod race OR concurrent OR mutex`: 9 results (#686 per-router registration request, #1021/#1022 reverseMethodMap fix, #573, #602, #253, #271, #479, #1122). None report a race.

## Open question
Whether a doc tweak ("must be called before serving, e.g. from init()") is worth a PR. It is low value, and it's Andrew's call.
