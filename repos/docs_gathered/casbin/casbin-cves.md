# Casbin CVEs and Security Advisories

Sources:
- https://github.com/casbin/casbin/security/advisories
- https://github.com/advisories?query=casbin
- https://www.cvedetails.com/vendor/26391/Casbin.html
- https://security.snyk.io/package/npm/casbin
- https://pkg.go.dev/vuln/ (searched for "casbin")
- https://www.cyera.com/blog/cyera-research-discovers-docker-authorization-bypass-that-silently-disables-security-policies

## Summary

As of the date this document was gathered, **no published CVEs exist specifically for the Casbin core authorization library** (Go, Java, Node.js, etc.). The GitHub Security Advisories page for casbin/casbin states "There aren't any published security advisories." The GitHub Advisory Database returns zero results for "casbin." Snyk reports no direct vulnerabilities for the casbin npm package. The Go Vulnerability Database has no entries for casbin.

This does NOT mean Casbin is vulnerability-free. It means:
1. No vulnerabilities have been formally reported through CVE/advisory channels
2. Bugs with security implications have been reported and fixed through regular GitHub issues (see casbin-github-issues.md)
3. The absence of CVEs for an authorization library used in production systems is itself notable -- it may indicate under-reporting rather than absence of bugs

## Related: CVE-2026-34040 (Docker Authorization Plugin Bypass)

A critical vulnerability (CVSS 8.8) was disclosed in Docker Engine that bypasses ALL Docker authorization plugins, including Casbin's docker-casbin-plugin. This is not a Casbin bug per se, but affects Casbin when used as a Docker AuthZ plugin.

- **CVE**: CVE-2026-34040
- **Root cause**: Incomplete fix for CVE-2024-41110. Docker did not properly handle oversized HTTP request bodies (>1MB), allowing a single padded HTTP request to create a privileged container with host filesystem access.
- **Impact**: Any Docker AuthZ plugin (OPA, Prisma Cloud, Casbin, custom) is bypassed entirely.
- **Fix**: Docker Engine 29.3.1
- **Security relevance for Casbin auditors**: This demonstrates that Casbin's authorization decisions can be entirely bypassed at the transport layer. The authorization logic in Casbin itself is never invoked when this attack is used.

## Casbin Products on CVEDetails

CVEDetails lists the Casbin vendor (ID 26391) with the following products:
- **Casdoor** (Product ID 108565): Casbin's authentication/SSO portal. This is a separate product from the core authorization library and has its own vulnerability history.

The core Casbin authorization library does not appear as a separate product in CVEDetails.

## Known Security-Relevant Bugs (Not Formally CVEs)

The following bugs were reported through GitHub issues and have security implications for authorization bypass. They are documented in detail in casbin-github-issues.md:

1. **ABAC rules fail when any deny row exists in policy** (Issue #917) - Authorization incorrectly denied for legitimate requests when unrelated deny rules exist. Fixed in PR #918.

2. **RBAC deny-override blocks too broadly** (Issue #290) - Deny rules applied to "public" role blocked access for all users including administrators.

3. **keyMatch() matches unwanted policies** (node-casbin Issue #66) - keyMatch with non-terminal wildcards matches policies it shouldn't, potentially granting unintended access.

4. **Case sensitivity causes authorization inconsistency** (Issue #694) - "alice" and "ALICE" are treated as different subjects, which can lead to bypass if application normalizes case inconsistently.

5. **Base Enforcer is not thread-safe** - Using the standard Enforcer in concurrent environments without SyncedEnforcer can cause race conditions in policy evaluation, potentially leading to incorrect authorization decisions.

## Implications for Security Auditing

The absence of formal CVEs combined with the presence of security-relevant GitHub issues suggests:

1. **Matcher edge cases** are the primary attack surface -- functions like keyMatch, regexMatch, and globMatch have documented surprising behavior
2. **Effect combination logic** has had bugs where deny rules affect unrelated subjects (Issue #917)
3. **Concurrency** is an explicit concern -- the existence of SyncedEnforcer, SyncedCachedEnforcer, and DistributedEnforcer implies the base Enforcer has known thread-safety limitations
4. **Policy loading and caching** introduces staleness risks -- stale cache = stale authorization decisions
5. **eval() in ABAC policies** allows arbitrary expression evaluation from policy strings, which is a potential injection vector if policies are user-controlled
