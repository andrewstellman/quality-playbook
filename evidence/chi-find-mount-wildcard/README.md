# chi: `Mux.Find`/`Match` does not reset the mount wildcard URLParam the way live routing does

**Verdict: NEEDS-MAINTAINER-INPUT.** The behaviour difference reproduces on master. But chi does not document that `Find`/`Match` must leave the context in the same state as a live request, and the doc comment warns that the context is mutated. The fix patch here is a candidate. **Not recommended as an unsolicited PR.**
QPB source: chi-1.6.0 BUG-001.

## Pinned upstream
`3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc` (2026-09-18), go1.25.1 linux/arm64.

## Behaviour
- Live routing: `Mount`'s handler (`mux.go:323-336`) shifts `RoutePath` and then clears the trailing `*` URLParam: "reset the wildcard URLParam which connects the subrouter" (`mux.go:329-333`).
- `Find` (`mux.go:382-408`) shifts `RoutePath` the same way (`mux.go:397`) but does not clear the `*` param.
- Result: after `root.Find(rctx, "GET", "/admin/ping")` on a mounted `/admin` router with a static `/ping` route, `rctx.URLParam("*")` is `"ping"`. A live request sees `""`.

## What the docs say
`Match` and `Find` doc comments (`mux.go:371-372`, `mux.go:380-381`):

> "Note: the *Context state is updated during execution, so manage the state carefully or make a NewRouteContext()."

That warns that the context changes. It does not promise the changes match live routing. `Find`'s job is returning the pattern, and the pattern is correct. So calling this a bug depends on reading an implied contract.

## Red / green
- `red.log`: `Find left URLParam("*") = "ping", live request saw ""`.
- `green.log`: passes with the candidate fix, which copies the same 4-line reset into `Find`.
- `suite-before.log` / `suite-after.log`: both pass (after run at `b494ad0`).

## Disclosure search
- `repo:go-chi/chi Find Match wildcard URLParam`: 0 results.
- `repo:go-chi/chi "Mux.Find" OR "Mux.Match" OR "rctx.URLParams"`: #954 (merged 2024, Find with nested routes, a different problem), #507, #127. None match.
- Related but separate: #939 / PR #940 (SupressNotFound runs `Match` on the live context; already covered by the earlier triage).

## Open question
Should `Find`/`Match` produce the same context state as live routing? If the maintainers say yes, the patch is ready. If no, drop this. Asking in an issue first is cheaper than a PR.
