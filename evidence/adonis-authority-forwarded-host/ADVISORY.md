Title: authority() consults X-Forwarded-Host, which lets a forwarded host defeat the same-origin check in redirect().back()

Ecosystem: npm
Package: @adonisjs/http-server
Affected versions: >= 9.0.0, <= 9.3.1 (authority() was added in 1278253 before v9.0.0; confirmed on 9.3.1 and main at 0801ec2)
Patched versions: none yet
Severity: Moderate (CVSS 3.1 suggestion: 4.7, AV:N/AC:H/PR:N/UI:R/S:C/C:N/I:L/A:N)
CWE: CWE-601 URL Redirection to Untrusted Site (Open Redirect), CWE-348 Use of Less Trusted Source
Credit: Andrew Stellman

Description

`Request.authority()` (src/request.ts:591) is documented as not consulting `X-Forwarded-Host` and as unaffected by `trustProxy`, because it exists to give a trustworthy value for validating redirect targets against the current origin. The implementation returns `this.header(':authority') || this.host() || null`, and `host()` does consult `X-Forwarded-Host` when the peer is a trusted proxy.

`getPreviousUrl()` (src/helpers.ts:114) uses `authority()` as the same-origin reference when `redirect().back()` validates the `Referer` header. So when a trusted proxy forwards a client-supplied `X-Forwarded-Host`, a request with `X-Forwarded-Host: evil.example.test` and `Referer: https://evil.example.test/...` passes the check, and `back()` redirects to the attacker's host. That is the redirect the helper exists to prevent.

Preconditions: the request's peer must be trusted by `trustProxy`. The default is `proxyAddr.compile('loopback')`, so the common shape is a reverse proxy on the same host that passes `X-Forwarded-Host` through from the client rather than overwriting it from the validated `Host`. An app that does not trust its proxy, or a proxy that sets the header itself, is not exposed.

Reproduction (against unmodified main, 2026-10-20)

A route returning `{ authority: request.authority(), host: request.header('host') }`, requested over loopback with `X-Forwarded-Host: evil.example.test`:

    AssertionError: expected 'evil.example.test' to equal 'localhost:41119'

Fix

Fall back to the raw `Host` header instead of `host()`, which is what the JSDoc already describes:

    authority(): string | null {
      return this.header(':authority') || this.header('host') || null
    }

The patch below makes that change and adds a regression test next to the existing forwarded-host test in tests/request.spec.ts. With it: 669/669 tests pass, typecheck, eslint and prettier are clean. I am happy to open it as a PR whenever you prefer.

Found with the Quality Playbook (an AI code-review and test-generation skill I maintain); I reproduced it and reviewed the fix myself.
