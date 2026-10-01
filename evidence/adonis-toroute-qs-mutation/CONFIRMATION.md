BUG-008: brisk route redirect loses its query string after the first request. CONFIRMED.
Claim: router.on('/old').redirect('new', {}, { qs: { a: 1 } }): first GET /old -> /new?a=1, every later request -> /new.
Mechanism: src/redirect.ts:309-312 toRoute does `this.withQs(options.qs); options.qs = undefined`, mutating the caller's options object; BriskRoute.redirect (src/router/brisk.ts:120-131) captures that same object in a closure and passes it on every request.
Doc: v6-docs_basics_routing.md:559 "The query string for the redirect URL can be defined within the options object." (note the doc example passes qs as 2nd arg; 9.x signature takes options as 3rd).
Tests: tests/router/brisk.spec.ts only checks toJSON; tests/redirect.spec.ts:345 single call. No duplicate (#127/#142 different).
Fix direction: don't mutate the caller's options (copy), e.g. read qs without assigning back.
