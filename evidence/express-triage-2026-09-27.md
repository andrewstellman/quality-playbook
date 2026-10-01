# express triage, 2026-09-27

Source: `docs/research/triage-2026-09-27/scout-candidates.md` (express rows), historical findings `repos/express-1.5.8/quality/BUGS.md` (v1.5.8 run, 2026-06-19, source-only).
Pinned upstream: expressjs/express `9a34acf03cb818ff3f8bc40e44176e277a25cbb9` (2026-09-15), express 5.2.1, Node v22.23.2. Clean clone in the sandbox. Baseline `npm test`: 1261 passing, exit 0.
Skipped by instruction: BUG-001 (X-Forwarded-Proto), BUG-006 (X-Forwarded-Host). None of the four candidates below has security impact.

Runtime probe of all four on the pinned SHA: `express-triage-2026-09-27-probe.log` (verbatim output of the probe script reproduced at the end of this file).

| candidate | verdict | where the defect lives | evidence |
|---|---|---|---|
| BUG-002 `res.cookie` sub-second `maxAge` -> `Max-Age=0` | **CONFIRMED** (low severity) | express `lib/response.js:769` | `evidence/express-cookie-subsecond-maxage/` |
| BUG-003 `res.redirect` literal `undefined` for unassigned codes | **ALREADY REPORTED** (open PR #7045) | express `lib/response.js:843,848-849` | probe log only |
| BUG-005 `acceptParams` quoted `;` / unclamped `q` | **ALREADY REPORTED** (quoted `;`: open PR #7479). `q` clamp: **NOT REPRODUCED** at any public API | express `lib/utils.js:89-120` (private helper) | probe log only |
| BUG-004 charset asymmetry in `res.send` | **NOT REPRODUCED** as a defect (by design, maintainer-confirmed) | n/a | probe log only |

## BUG-002: CONFIRMED
`res.cookie('a','b',{maxAge:500})` sends `Max-Age=0` together with a future `Expires`. RFC 6265 §4.1.2.2 gives Max-Age precedence, and §5.2.2 treats `Max-Age=0` as expire-now, so the cookie is deleted. The expressjs.com docs describe `maxAge` as "setting the expiry time relative to the current time in milliseconds." The fix clamps a positive `maxAge` that floors to 0 up to `Max-Age=1`; everything else is unchanged. Red: 1 failing. Green: pass. Suite: 1261 -> 1263 passing. Lint: exit 0. Disclosure searches found nothing. Full detail and open questions are in the evidence README.

## BUG-003: ALREADY REPORTED
Reproduces: `res.redirect(310, '/x')` gives the body `"undefined. Redirecting to /x"` and `<title>undefined</title>`. The docs support calling it a bug: `res.sendStatus` says "If an unknown status code is specified, the response body will just be the code number", and `sendStatus` already does `statuses.message[statusCode] || String(statusCode)` (`lib/response.js:326`).
Already covered by **https://github.com/expressjs/express/pull/7045** ("fix: non standard status code will result in undefined", open since 2026-02-20, no maintainer review). Per `GET /repos/expressjs/express/pulls/7045/files`, that PR fixes the text body and the HTML `<p>`, but **it still leaves `<title>` as `statuses.message[status]`** (→ `<title>undefined</title>`), and it adds no test.
Searches: `repo:expressjs/express redirect statuses.message` (3 hits: #7045, #5058, #5167); `repo:expressjs/express redirect undefined status message` (9 hits; #7045 is the only match; #4598 "Check for invalid or unknown http status codes" is closed and older).

## BUG-005: ALREADY REPORTED / NOT REPRODUCED publicly
The internal mis-parse is real: `utils.normalizeType('text/html;x="a;b";q=5')` returns `{"value":"text/html","quality":5,"params":{"x":"\"a"}}`. But `normalizeType`/`acceptParams` are `@api private`, and the only callers (`res.format`, `lib/response.js:587,593`) read `.value` alone, which is the slice before the first `;` and is always correct. `req.accepts*` uses the `accepts` package, and `res.type` uses `mime-types`, so neither goes through this code. The historical finding's claim that it "affects `req.accepts*`/`res.format`/`res.type`" does not hold. A public-API test (`res.format` with that key) passes on master, so there is no observable defect.
The quoted-`;` half is already reported: **https://github.com/expressjs/express/pull/7479** ("fix: acceptParams truncates quoted values containing a semicolon", open; one non-reviewing comment from krzysdz quoting RFC 9110). Search `repo:expressjs/express acceptParams`: 17 hits, mostly refactors and closed PRs (#7292, #6981, #6318, #6320, #7336, ...). No q-clamp PR was found, but a clamp would change nothing observable.

## BUG-004: NOT REPRODUCED as a defect
The asymmetry exists (string body: `charset=utf-8`; Buffer body: the caller's `iso-8859-1` is kept), but it is intentional and correct. For strings, express writes the bytes as UTF-8 (`encoding = 'utf8'`; the probe shows `café` sent as `636166c3a9`), so advertising any other charset would be wrong. For Buffers, express does not know the encoding. A maintainer confirmed this in **https://github.com/expressjs/express/issues/2238** (dougwilson, 2014): "the correct way to send any encoding you want is to encode it into a `Buffer` … We do not touch the charset for a `Buffer`, because we have no idea what it may be." The historical "fix" (make the paths agree) would reintroduce a wrong-charset bug. Search `repo:expressjs/express res.send charset in:title`: 1 hit (#2238).

## Method notes
- All disclosure searches used the GitHub REST search API through `web_fetch`, on 2026-09-27. Result counts are as returned.
- Nothing was pushed, opened, or commented on.
- The OpenJS AI Coding Assistants Policy (linked from the expressjs.com footer) could not be fetched (empty response). It has not been read.

## Probe script (`/tmp/probe.js`)
```js
const express = require('/tmp/express'); const request = require('/tmp/express/node_modules/supertest');
const utils = require('/tmp/express/lib/utils');
(async () => {
  const app = express();
  app.get('/c', (req, res) => { res.cookie('a', 'b', { maxAge: 500 }); res.end(); });
  app.get('/r', (req, res) => res.redirect(310, '/x'));
  app.get('/s', (req, res) => { res.set('Content-Type', 'text/plain; charset=iso-8859-1'); res.send('café'); });
  app.get('/b', (req, res) => { res.set('Content-Type', 'text/plain; charset=iso-8859-1'); res.send(Buffer.from('café','latin1')); });
  app.get('/f', (req, res) => res.format({ 'text/html;x="a;b";q=5': () => res.send('ok') }));
  let r = await request(app).get('/c'); console.log('cookie:', r.headers['set-cookie']);
  r = await request(app).get('/r').set('Accept','text/plain'); console.log('redirect text:', JSON.stringify(r.text), r.status);
  r = await request(app).get('/r').set('Accept','text/html'); console.log('redirect html:', JSON.stringify(r.text));
  r = await request(app).get('/s'); console.log('send str:', r.headers['content-type'], r.body && Buffer.from(r.text||'').toString('hex'));
  r = await request(app).get('/b'); console.log('send buf:', r.headers['content-type']);
  r = await request(app).get('/f').set('Accept','text/html'); console.log('format:', r.status, r.headers['content-type']);
  console.log('acceptParams:', JSON.stringify(utils.normalizeType('text/html;x="a;b";q=5')));
})();
```
