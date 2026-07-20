# Pass 1 — Structural Review (Express v5.2.1)

> Quality Playbook v1.5.8 · 2026-06-19 · Scope: `lib/` (response.js, request.js, application.js, utils.js, view.js, express.js). Routing is `router@2.2.0` (out of scope; boundary). Line numbers mandatory; QUESTION when unsure; grep before "missing"; no style notes.

## 1. Input validation and boundary handling

- **`lib/request.js:309-314` (`req.protocol`) — BUG.** `header = X-Forwarded-Proto || proto`; `index = header.indexOf(',')`. For a trusted header whose first comma-separated element is empty (`", https"` → `index===0`), the getter returns `header.substring(0,0).trim() === ''`. Likewise `","` → `''`. There is no guard that re-falls-back to the socket scheme when the leading element is empty. Expected: first **non-empty** trimmed token, else socket scheme, always ∈ {http, https}. Actual: `''`. Why it matters: `req.secure` (`:326-328`) becomes false for a genuinely-secure proxied request → HTTPS-only middleware misfires. → BUG-001.

- **`lib/request.js:424-427` (`req.host`) — BUG.** In the trusted branch, `val.indexOf(',') !== -1` → `val.substring(0, val.indexOf(',')).trimRight()`. For `",a.com"` the first comma is at index 0, so `substring(0,0)` is `''`; `return val || undefined` yields `undefined`. The leading-comma case takes the leading (empty) authority rather than the first present one. → propagates to `hostname` (`:447` `if (!host) return;` → `undefined`) and `subdomains` (`:386` `if (!hostname) return [];`). → BUG-006.

- **`lib/response.js:286` (jsonp callback filter) — QUESTION (not a bug).** `/[^\[\]\w$.]/g` permits `. [ ] $` and word chars, so `a.constructor` survives the filter. Reachability/compensation analysis: the same filter strips `( ) ' ; space` and every other statement-breaking character, so the surviving callback can only ever appear inside the fixed template `/**/ typeof CB === 'function' && CB(BODY);` (`:300`) — the attacker cannot terminate that statement or open a new one. `X-Content-Type-Options: nosniff` is set (`:282`) and the `typeof … === 'function'` guard wraps the call. No statement-injection path is reachable. Flagged QUESTION per "if unsure, file a QUESTION"; demoted, not confirmed. (See Combined Summary, FALSE POSITIVE row.)

- **`lib/utils.js:89-120` (`acceptParams`) — BUG.** The hand-rolled scan finds `=` and `;` boundaries with `str.indexOf` and has no quoted-string awareness. For `text/html;x="a;b";q=0.5`, `endIndex` lands on the `;` *inside* the quotes, so `value = str.slice(splitIndex+1, endIndex).trim()` captures `"a` (truncated mid-value) and the remainder is mis-scanned. Separately, `q` is set via `parseFloat(value)` (`:111`) with **no clamp** to `[0,1]`, so `q=5` flows through as `quality: 5`. → BUG-005.

- **`lib/response.js:818-833`, `:856` (redirect status acceptance) — see area below; the range guard lives in `res.status` (`:70`). Reviewed under REQ-003 / BUG-003.

## 2. Resource lifecycle

Reviewed `res.sendFile`/`sendfile` streaming (`lib/response.js:921-1009`): the `done`/`streaming` flags, the `onaborted`/`onerror`/`onend`/`onfinish` handlers, and the `streaming !== false && !done` guard at `:971`. Every stream path resolves exactly once: `done` is latched at the top of `onaborted`/`onerror`/`onend` and re-checked before `req.next`/callback dispatch. No double-resolve or leaked listener path found. `res.cookie`/`res.redirect`/`res.json`/`res.send` are synchronous and own no streams. **No confirmed lifecycle bug.**

## 3. Concurrency and state management

Express is single-threaded per request; there is no shared mutable state across requests in the reviewed `lib/` paths. The one in-place-mutation site is `req.ips` (`lib/request.js:363`) calling `addrs.reverse().pop()` on the array from `proxyaddr.all`; this is latent only because the dependency returns a fresh array per call (boundary assumption). **No confirmed concurrency bug; documented as latent-only.**

## 4. Unit and encoding correctness

- **`lib/response.js:170-177` (`res.send` Content-Length gate) — reviewed, no bug.** The `chunk.length < 1000` test uses UTF-16 code-unit length to choose the small-chunk branch, while `Buffer.byteLength(chunk, encoding)` supplies the actual byte length. The gate only selects *which* path computes the length; both paths set the byte-accurate value. No incorrect Content-Length results. (A multibyte string of <1000 code units still gets `Buffer.byteLength`.)

- **`lib/response.js:759-766` (`res.cookie` maxAge floor) — BUG.** `opts.maxAge = Math.floor(maxAge / 1000)` while `opts.expires = new Date(Date.now() + maxAge)`. For `maxAge` in (0,1000), `Max-Age` floors to `0` (delete-now) while `Expires` is in the future — contradictory directives. No minimum/round-up guard. → BUG-002.

- **`lib/response.js:137-143` vs `:150-153` (charset injection asymmetry) — BUG.** String bodies rewrite the charset to utf-8 via `setCharset(type,'utf-8')` (`:140`); `ArrayBuffer.isView` (Buffer/typed-array) bodies only set a default `bin` type when Content-Type is absent (`:151-152`) and otherwise **preserve** the caller's charset. The same handler advertises a different charset depending on body JS type. → BUG-004 (parity REQ-006).

## 5. Enumeration and whitelist completeness

**NOT APPLICABLE this run.** Express `lib/` has no `switch`/`case` over a closed set of named C-style constants. The `compile*` switches (`utils.js:130-214`) branch on JS setting-name *strings* with a `default: throw`, not an enum to be exhausted. Status-code and MIME sets are owned by the `statuses`/`accepts`/`mime` dependencies (boundary). The jsonp whitelist is a character-class regex (reviewed in area 1), not a constant enumeration. No `quality/mechanical/*_cases.txt` witness exists for this run by design (PROGRESS.md records this).

## Pass 1 findings

| Site | Verdict | Bug |
|------|---------|-----|
| request.js:309-314 | BUG | BUG-001 |
| response.js:759-766 | BUG | BUG-002 |
| response.js:841,846-847 | BUG (area 1/REQ-003) | BUG-003 |
| response.js:137-143 vs :150-153 | BUG | BUG-004 |
| utils.js:89-120 | BUG | BUG-005 |
| request.js:424-427 | BUG | BUG-006 |
| response.js:286 | QUESTION → FALSE POSITIVE | — |
