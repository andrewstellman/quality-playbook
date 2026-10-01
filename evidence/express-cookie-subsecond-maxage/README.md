# express: `res.cookie` sends `Max-Age=0` for a positive sub-second `maxAge`

**Verdict: CONFIRMED (low severity).** Reproduces on master. The defect is in express itself (`lib/response.js`), not in the `cookie` dependency, which just serializes the integer express hands it.
QPB source: `repos/express-1.5.8/quality/BUGS.md` BUG-002 (v1.5.8 run, 2026-06-19, source-only review).

## Pinned upstream
`9a34acf03cb818ff3f8bc40e44176e277a25cbb9` (2026-09-15, "fix(res.send): preserve ETag generation with Transfer-Encoding (#7459)"), express 5.2.1, Node v22.23.2, npm 10.9.8, cookie 0.7.2.

## Defect
`lib/response.js:764-771` at the pinned SHA:

```js
  if (opts.maxAge != null) {
    var maxAge = opts.maxAge - 0

    if (!isNaN(maxAge)) {
      opts.expires = new Date(Date.now() + maxAge)
      opts.maxAge = Math.floor(maxAge / 1000)
    }
  }
```

For `0 < maxAge < 1000`, `Expires` is set to a time in the future but `Math.floor` makes `Max-Age` 0. The response header contradicts itself, and the attribute that wins says "delete now":

```
res.cookie('a', 'b', { maxAge: 500 })
-> a=b; Max-Age=0; Path=/; Expires=Sun, 27 Sep 2026 20:11:42 GMT
```
(verbatim from `../express-triage-2026-09-27-probe.log`)

## Expected behaviour, with sources
- expressjs.com 5.x API, `res.cookie()` options: `maxAge` is a "Convenient option for setting the expiry time relative to the current time in milliseconds." The same page says the `maxAge` option is "a convenience option for setting “expires” relative to the current time".
- RFC 6265 §4.1.2.2: "If a cookie has both the Max-Age and the Expires attribute, the Max-Age attribute has precedence and controls the expiration date of the cookie."
- RFC 6265 §5.2.2: "If delta-seconds is less than or equal to zero (0), let expiry-time be the earliest representable date and time."

So a positive `maxAge` produces a cookie that a compliant UA expires immediately, the same result `res.clearCookie` gives. `maxAge: 0` (and negative values) still mean "expire now", and the patch keeps that.

## Fix
Keep the `Math.floor` (it has been there since 58553394, 2019, and the "Max-Age never a floating point number" rule comes from cookie@0.3.1). Only when a positive `maxAge` floors to 0, send `Max-Age=1`. Values of 1000 ms and above, 0, and negative values are unchanged.

Tests added to `test/res.cookie.js` under `maxAge`:
- `should not set Max-Age=0 for a positive sub-second maxAge`: `maxAge: 500` expects `Max-Age=1`. Fails on master, passes with the fix.
- `should set Max-Age=0 for a maxAge of 0`: guards the existing "expire now" behaviour. Passes before and after.

## Red / green
- `red.log`: `mocha test/res.cookie.js` on master plus the new tests: 20 passing, 1 failing. The failure reads `expected "Set-Cookie" matching /name=tobi; Max-Age=1; Path=\/; Expires=/, got "name=tobi; Max-Age=0; Path=/; Expires=Sun, 27 Sep 2026 20:10:54 GMT"`.
- `green.log`: the same file with the fix: 21 passing.
- `suite-before.log`: `npm test` on unpatched master: 1261 passing, exit 0.
- `suite-after.log`: `npm test` with the patch: 1263 passing, exit 0.
- `npm run lint` on the patched branch: exit 0 (not captured to a file).

## Patch
`0001-Fix-res.cookie-sending-Max-Age-0-for-a-sub-second-ma.patch`: `git format-patch` against `9a34acf`. Author: Andrew Stellman <andrew@stellman.com>. No Signed-off-by.

## Disclosure search (GitHub search API via web_fetch, 2026-09-27)
| query | hits | relevant |
|---|---|---|
| `repo:expressjs/express maxAge Max-Age` | 19 | none about sub-second. Related but different: #5150 / PR #5151 (Max-Age without Expires), PR #6875 (null maxAge; keeps `Math.floor`), PR #7287 (Infinity/NaN; closed), #3935 (undefined maxAge), #5234 (seconds vs ms) |
| `repo:expressjs/express "Max-Age=0"` | 23 | none about sub-second |
| `repo:expressjs/express cookie maxAge floor` | 1 | PR #7287 (Infinity/NaN), not this |
| `repo:expressjs/express cookie maxAge "less than" second` | 1 | #2727, unrelated |
| `repo:jshttp/cookie maxAge floor` | 0 | none |

Not already reported as far as these searches show.

## Open questions
1. **Is the use case worth the maintainers' time?** Sub-second cookie lifetimes are unusual, and `Expires` has only one-second resolution too. A maintainer could fairly reply "cookie lifetimes are whole seconds; round your value." The PR is small and self-contained, but its value is modest.
2. **Clamp to 1, or `Math.ceil` throughout?** `Math.ceil` is arguably more principled (never shorter than asked), but it changes `Max-Age` for every non-whole-second value (for example, 1500 ms goes from 1 to 2). The clamp only changes the case that is currently self-contradictory. The patch uses the clamp.
3. The CONTRIBUTING guide says to "Create an issue for the bug you want to fix" before the PR. There is no issue yet.
4. The expressjs.com footer links an OpenJS "AI Coding Assistants Policy" (https://ai-coding-assistants-policy.openjsf.org/). Fetching it returned an empty body, so it has not been read. Read it before submitting.
