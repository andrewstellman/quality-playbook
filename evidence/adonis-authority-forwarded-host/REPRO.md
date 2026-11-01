# adonisjs/http-server BUG-011 reproduction (security triage, reproduce-only)

Date (UTC): run on 2026-10-20. Repo https://github.com/adonisjs/http-server
Note: Andrew has an open PR #145 with this maintainer carrying pushback on this issue; it was not touched.

## Clone and head
- Cloned current main into `/tmp/claude-0/sec/adonis/src` with `--depth 50`, `GIT_LFS_SKIP_SMUDGE=1`.
- HEAD: `0801ec2d7480a9610bd4063da24a82633fc2674a`
- HEAD date: `2026-10-16T13:01:49+05:30`
- HEAD subject: `perf(server): skip tracing channels without subscribers (#147)`
- Campaign ran at `3bf3cde` (9.3.1), which is present in the shallow clone.

## Install
- Node v22.22.0, npm 10.9.4. The project uses npm (package-lock.json).
- Plain `npm install` fails with an npm 10 arborist peer-resolution crash (`Cannot read properties of null (reading 'edgesOut')`). `npm install --legacy-peer-deps` works. A transitive peer, `@adonisjs/config`, was then missing (`@adonisjs/application` needs it) and was installed with `npm install --no-save --legacy-peer-deps @adonisjs/config@^6.0.0`.
- Disk note: the container was at 94% (~3 GB free); one early install run hit `ENOSPC`. Cleared the npm cache and the install then completed.

## Fix-since-run check
`git log 3bf3cde..HEAD -- src/request.ts` returns nothing: `src/request.ts` has not changed since the campaign commit. The bug code is still on current main:
- `authority()` (src/request.ts:591-593): `return this.header(':authority') || this.host() || null`
- `host()` (src/request.ts:565-568): when `trustProxy(remoteAddress, config.trustProxy)` is true it returns the first `X-Forwarded-Host`.
- The JSDoc for `authority()` (src/request.ts:585) still says "Unlike [[host]], this method does not consult `X-Forwarded-Host`". Not fixed.

## Trusted-proxy gating (checked, as requested)
`host()` consults `X-Forwarded-Host` only when `trustProxy(this.request.socket.remoteAddress, this.#config.trustProxy)` is true. The default trustProxy is `proxyAddr.compile('loopback')` (src/define_config.ts:53), so by default only a peer on loopback (127.0.0.1/::1) is trusted. So yes, X-Forwarded-Host handling here is gated by a trusted-proxy setting, and the default trusts loopback. In the reproduction the supertest client connects over loopback, so the default config trusts it and the forwarded host is honoured; the same happens in the common production shape of a reverse proxy running on the same host.

## Reproduction (regression test)
Applied the record's patch `tests/quality_regression/BUG-011.spec.ts`, which boots a real server, defines `GET /` returning `{ authority: request.authority(), host: request.header('host') }`, and sends `X-Forwarded-Host: evil.com`. Run on unmodified main (verbatim assertion):
```
- Expected  - 1
- localhost:3000
+ evil.com
ℹ AssertionError: expected 'evil.com' to equal 'localhost:3000'
 ❯ 41 ┃      assert.equal(res.body.authority, res.body.host)
 FAILED
Tests  1 failed (1)
```
`authority()` returns `evil.com` (the client-supplied X-Forwarded-Host) while the real Host header is `localhost:3000`. RED on unmodified main.

Red test name: `Quality Playbook regression tests › BUG-011: authority() ignores X-Forwarded-Host` (tests/quality_regression/BUG-011.spec.ts).

## Full suite baseline (unmodified main)
```
Tests  668 passed (668)
```
(Run with the BUG-011 spec removed. Clean baseline, no failures.)

## No fix written
The record ships a fix patch (fall back to the `host` header instead of `host()`), but I did not apply or write it. The fix is small, but it is the subject of an open, contested PR (#145) with this maintainer, so by the "do not touch that" instruction and the reproduce-only scope I left the code unmodified and recorded red only.

## Impact assessment
- Input controller: a client sending the `X-Forwarded-Host` header, but only when the request's peer is a trusted proxy. By default that is loopback, i.e. a reverse proxy co-located on the same host that forwards the header without overwriting it.
- What the attacker gains: `authority()` is the same-origin reference in `getPreviousUrl` (src/helpers.ts:114), which `redirect().back()` uses to validate the Referer before redirecting to it. By controlling `X-Forwarded-Host`, an attacker can make a Referer on an attacker-chosen host pass the same-origin check, turning `back()` into an open redirect to that host. That is exactly the attack the helper exists to prevent.
- Vulnerability or ordinary bug: a real security bug (open-redirect enabler) and a documented contradiction (the code violates its own JSDoc). Its practical severity is bounded by the trusted-proxy gate: it bites only when a trusted (by default loopback) proxy forwards a client-controlled X-Forwarded-Host without sanitizing it. A correctly configured proxy that sets X-Forwarded-Host from the validated Host, or an app that does not trust the proxy, is not exposed. The campaign rated it MEDIUM; I agree it is a genuine vulnerability of moderate severity, conditional on deployment, rather than a trivially remote one.

## Paths written
- `/tmp/claude-0/sec/adonis/REPRO.md` (this file)
- `/tmp/claude-0/sec/adonis/out/0001-BUG-011-regression-test-authority-must-ignore-X-Forw.patch`
