BUG-004: redirect Location gets a second '?' when the target already has a query string. CONFIRMED.
Claim: response.redirect().withQs('b','2').toPath('/foo?a=1') (or withQs() forwarding GET /?b=2) emits Location: /foo?a=1?b=2; expected /foo?a=1&b=2.
Mechanism: src/redirect.ts:132 `url = stringified ? `${url}?${stringified}` : url` with no check for an existing '?'. back() already splits the referrer into pathname+query and merges. The package has appendQueryString helper (src/helpers.ts:321) documented to do exactly this merge, but nothing in src calls it.
Doc: v6-docs_basics_response.md:246 "You can use the withQs method to append a query string to the redirect URL."
Tests: tests/redirect.spec.ts has no toPath target containing '?'. No duplicate (closest #127, PR #142 about forwardQueryString flag).
Pushback: merge precedence when keys collide (appendQueryString uses Object.assign; added wins). Keep the target's original query text rather than re-encoding it if possible.
