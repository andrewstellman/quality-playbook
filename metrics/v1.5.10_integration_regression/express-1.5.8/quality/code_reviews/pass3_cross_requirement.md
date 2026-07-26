# Pass 3 — Cross-Requirement Consistency (Express v5.2.1)

> Quality Playbook v1.5.8 · 2026-06-19. Compare REQ pairs sharing a concept; verify mutual consistency against the actual code.

## Shared Concept: `X-Forwarded-*` list parsing (REQ-001 ↔ REQ-007)

**What REQ-001 claims:** `req.protocol` always comma-splits and trims `X-Forwarded-Proto`.
**What REQ-007 claims:** `req.host` comma-splits `X-Forwarded-Host` only in the trusted branch, using `.trimRight()`.
**Consistency: INCONSISTENT.**
**Code evidence:**
- `req.protocol` (`request.js:310-314`): `index = header.indexOf(','); … header.substring(0,index).trim()` — always splits (even when trust already passed), uses `.trim()` (both ends).
- `req.host` (`request.js:424-427`): splits only inside `else if (val.indexOf(',') !== -1)`, uses `.trimRight()` (right only).
**Analysis:** Two getters parsing the "same shape" (comma list with possible leading/trailing comma) disagree on (a) where splitting happens and (b) which sides are trimmed. **Both share the identical leading-empty-element defect**: `substring(0, 0)` returns `''` when the list begins with a comma. The asymmetry is the documented cross-implementation drift; the shared empty-leading-element bug is captured as BUG-001 (protocol) and BUG-006 (host) — same root pattern, two getters, two distinct observable failures (secure-downgrade vs undefined-hostname). **Impact:** an operator who normalizes one header shape cannot assume the other getter handles it the same way.

## Shared Concept: charset injection path (REQ-006 internal)

**What the string-`send` path claims:** force `charset=utf-8` via `setCharset` (`response.js:140`, `utils.js:225-238`).
**What the `res.set`/Buffer path claims:** inject charset via `mime.contentType` (`response.js:676`); Buffer `send` preserves the pre-set charset (`:150-153`).
**Consistency: INCONSISTENT.**
**Code evidence:** `setCharset` uses `content-type` parse/format to *overwrite* the charset parameter to utf-8; `mime.contentType` *adds* a default charset only when none is present, never overwriting. For an input `text/plain; charset=iso-8859-1`: string `send` → `text/plain; charset=utf-8`; Buffer `send` / `res.set` → `text/plain; charset=iso-8859-1`.
**Analysis:** The two injection mechanisms reach different final headers for the same input. `History.md:15` documents only the string-`send` perf change; the divergence is unspecified. **Impact:** a single route advertises a different charset depending on body type and on which surface set the type. Captured as BUG-004 (parity REQ-006).

## Shared Concept: status-code range guard (REQ-003)

**What `res.status` claims:** accepts integers 100–999 (`response.js:70`; `History.md` "status code must be greater than 99 and less than 1000").
**What `res.redirect` body logic claims:** builds the body from `statuses.message[status]` for whatever status it is handed (`response.js:841,846-847`), then calls `this.status(status)` (`:856`).
**Consistency: INCONSISTENT.**
**Code evidence:** `res.status` admits 310 (a valid integer in range) but `statuses.message[310]` is `undefined`. The redirect body builder has no fallback for codes the message map omits.
**Analysis:** The range guard admits a strictly larger set than `statuses.message` covers; the redirect body logic does not reconcile the gap, so an in-range-but-unassigned code yields `undefined` in the body/title. **Impact:** any in-range 3xx code absent from `statuses.message` produces a malformed body. Captured as BUG-003.

## Pass 3 summary

| Shared concept | REQ pair | Consistency | Bug |
|----------------|----------|-------------|-----|
| XFP vs XFH list parsing | REQ-001 ↔ REQ-007 | INCONSISTENT | BUG-001, BUG-006 |
| charset injection paths | REQ-006 internal | INCONSISTENT | BUG-004 |
| status range vs message map | REQ-003 | INCONSISTENT | BUG-003 |
