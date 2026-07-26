# Pass 2 — Requirement Verification (Express v5.2.1)

> Quality Playbook v1.5.8 · 2026-06-19. Behavioral REQ-001..008 (layout REQ-009..016 are gate-verified, not code-reviewed). Each REQ gets its own verdict with ≥1 file:line.

#### REQ-001: `req.protocol` non-empty/correct for every trusted `X-Forwarded-Proto`
**Status: VIOLATED.**
**Evidence:** `lib/request.js:309-314` — `var header = this.get('X-Forwarded-Proto') || proto; var index = header.indexOf(','); return index !== -1 ? header.substring(0, index).trim() : header.trim()`.
**Analysis:** For trusted `", https"` the first element is empty → returns `''`; for `","` → `''`. CoS requires `protocol ∈ {http, https}` for those inputs. No non-empty-token selection. `req.secure` (`:326-328`) then reads false for a secure request. → BUG-001. **Severity: HIGH** (security downgrade of a genuinely-secure request).

#### REQ-002: `res.cookie` must not emit `Max-Age` contradicting a future `Expires`
**Status: VIOLATED.**
**Evidence:** `lib/response.js:763-764` — `opts.expires = new Date(Date.now() + maxAge); opts.maxAge = Math.floor(maxAge / 1000)`.
**Analysis:** `maxAge=500` → `Max-Age=0` (immediate delete) with a future `Expires`. CoS forbids a sub-second `maxAge` serializing `Max-Age=0` alongside a future expiry. → BUG-002. **Severity: HIGH** (silently-dropped cookie on Max-Age-preferring UAs).

#### REQ-003: `res.redirect` well-formed body for any accepted status
**Status: VIOLATED.**
**Evidence:** `lib/response.js:841` — `body = statuses.message[status] + '. Redirecting to ' + address`; `:846-847` builds `<title>` and `<p>` from the same expression.
**Analysis:** `statuses.message` is keyed only by assigned codes. The status guard (`res.status`, `:70`) admits any integer 100–999, so an unassigned 3xx (e.g. 310) makes `statuses.message[310]` `undefined`; string concat yields `"undefined. Redirecting to …"` and `<title>undefined</title>`. CoS forbids the literal `undefined`. No fallback. → BUG-003. **Severity: MEDIUM.**

#### REQ-004: `res.jsonp` callback names restricted to a safe grammar
**Status: SATISFIED (with QUESTION).**
**Evidence:** `lib/response.js:286` filter `/[^\[\]\w$.]/g`; `:282` `nosniff`; `:300` `/**/ typeof CB === 'function' && CB(BODY);`.
**Analysis:** Member-access chains (`a.constructor`) survive the filter, but the filter strips every statement-breaking character (`( ) ' ; space /`), so the survivor can only appear inside the fixed `typeof`-guarded template; no statement injection is reachable, and `nosniff` blocks content-type sniffing escalation. The CoS ("member-access chains either are rejected or are proven safe by the guard") is met by the guard. Recorded as a QUESTION (stricter bare-identifier grammar would be defense-in-depth) but **not a confirmed bug.**

#### REQ-005: `acceptParams` parses media-type params per RFC 7231 §3.1.1.1
**Status: VIOLATED.**
**Evidence:** `lib/utils.js:96-116` — boundary scan via `str.indexOf('=' / ';', …)` with no quoted-string handling; `:111` `ret.quality = parseFloat(value)` (unclamped).
**Analysis:** `text/html;x="a;b";q=0.5` splits at the `;` inside the quotes, truncating the value mid-string; `q=5` is accepted unclamped. CoS requires quoted `;` not split and `q` clamped to `[0,1]`. → BUG-005. **Severity: MEDIUM.**

#### REQ-006: Charset consistent across `res.send` body types and `res.set`/`res.type`
**Status: VIOLATED.** (Pattern: parity — grid in `compensation_grid.json`.)
**Evidence:** `lib/response.js:140` (string → `setCharset(type,'utf-8')`) vs `:150-153` (ArrayBuffer view → only default `bin` when no type, otherwise charset preserved); `:676` (`res.set` → `mime.contentType(value)`).
**Analysis:** Identical handler advertises `charset=utf-8` for a string body but preserves `charset=iso-8859-1` for a Buffer body (UC-06.a vs UC-06.b divergence, undocumented). `History.md:15` records the v5 perf change that introduced the string-only `setCharset` rewrite, with no statement that the Buffer path should diverge. → BUG-004. **Severity: MEDIUM.**

#### REQ-007: `req.host`/`hostname`/`subdomains` resolve for all trusted XFH shapes
**Status: VIOLATED.** (Pattern: parity — grid in `compensation_grid.json`.)
**Evidence:** `lib/request.js:424-427` — trusted-branch `val.substring(0, val.indexOf(',')).trimRight()`; `:430` `return val || undefined`. `hostname` `:447` `if (!host) return;`. `subdomains` `:386` `if (!hostname) return [];`.
**Analysis:** Trusted `",a.com"` → leading element is empty → `host` `undefined` → `hostname` `undefined` → `subdomains` `[]` for a syntactically present authority, violating the CoS "never `undefined` for a present host." → BUG-006. **Severity: MEDIUM.**

#### REQ-008: Settings compilation fails fast on invalid configuration
**Status: SATISFIED.**
**Evidence:** `lib/utils.js:147-148, 179-180, 211-213` — each `compile*` has `default: throw new TypeError(...)`; `lib/application.js:371-379` compiles at `app.set` time.
**Analysis:** Invalid `etag`/`query parser`/`trust proxy` values throw a `TypeError` synchronously at `app.set`, not at request time. CoS met. No bug.

## Pass 2 summary

| REQ | Status | Bug |
|-----|--------|-----|
| REQ-001 | VIOLATED | BUG-001 |
| REQ-002 | VIOLATED | BUG-002 |
| REQ-003 | VIOLATED | BUG-003 |
| REQ-004 | SATISFIED (QUESTION) | — |
| REQ-005 | VIOLATED | BUG-005 |
| REQ-006 | VIOLATED | BUG-004 |
| REQ-007 | VIOLATED | BUG-006 |
| REQ-008 | SATISFIED | — |
