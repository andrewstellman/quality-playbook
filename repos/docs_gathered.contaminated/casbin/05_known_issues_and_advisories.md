# Casbin Known Issues and Advisories

## Sources

- GitHub security advisories (Casbin org): https://github.com/casbin/casbin/security/advisories
- GitHub security advisories (Apache org, current canonical home after donation): https://github.com/apache/casbin/security/advisories
- GitHub security policy: https://github.com/casbin/casbin/security/policy
- Issue #832 (cache invalidation discussion): https://github.com/casbin/casbin/issues/832
- Issue #1202 (RBAC cache discussion): https://github.com/casbin/casbin/issues/1202
- CachedEnforcer source (the maintainer-acknowledged invalidation scope): https://raw.githubusercontent.com/casbin/casbin/master/enforcer_cached.go
- CachedEnforcer test (the maintainer-acknowledged test coverage scope): https://raw.githubusercontent.com/casbin/casbin/master/enforcer_cached_test.go

## Context

Casbin has had no published GHSA / CVE security advisories on its GitHub Security tab as of the date of this collection (the page returns "There aren't any published security advisories" on both the `casbin/casbin` and `apache/casbin` URLs). The interesting class of "known limitations" therefore lives in the issue tracker, in source-code structure (the absence of overrides on the cache wrappers), and in the test-suite shape (the absence of tests for grouping-policy invalidation on cached enforcers). This document inventories those signals.

## Published security advisories

- **None on GitHub.** As of collection, both https://github.com/casbin/casbin/security/advisories and https://github.com/apache/casbin/security/advisories report "There aren't any published security advisories."
- The Casbin project moved to the Apache Software Foundation (the GitHub URL `github.com/casbin/casbin` now redirects to `github.com/apache/casbin`). Casbin has not historically issued CVEs for its own bugs; the issues that come closest (matcher-injection, custom-function panics) have been handled as regular bug fixes rather than GHSAs.
- The Casbin Security Policy (https://github.com/casbin/casbin/security/policy) directs reporters to email `admin@casbin.org`.

## Maintainer-acknowledged limitations from code structure

These are not separately announced; they are visible from reading the relevant files.

### CachedEnforcer cache invalidation is partial by design

The class only overrides `LoadPolicy`, `RemovePolicy`, `RemovePolicies`, `ClearPolicy`, and `InvalidateCache`. It does NOT override `AddPolicy`, `AddPolicies`, `AddGroupingPolicy`, `RemoveGroupingPolicy`, `RemoveFilteredPolicy`, `RemoveFilteredGroupingPolicy`, `UpdatePolicy`, `UpdateGroupingPolicy`, or any of the RBAC convenience wrappers (`AddRoleForUser`, `DeleteRoleForUser`, `DeleteUser`, `DeleteRole`). Each of these is a documented "you must call `InvalidateCache` yourself" path — except the documentation does not actually mention that requirement.

### SyncedCachedEnforcer has wider but still incomplete coverage

It additionally overrides `AddPolicy` and `AddPolicies`. It still does NOT override any grouping-policy method or any filtered-policy method. The asymmetry between `CachedEnforcer` and `SyncedCachedEnforcer` on `AddPolicy` is itself a clue that the cache-invalidation coverage was extended piecemeal rather than designed up front.

### Default TTL is infinite

`NewCachedEnforcer` does not call `SetExpireTime`. `e.expireTime` remains the zero value (`time.Duration(0)`). `DefaultCache.Set` stores entries with `ttl = 0`, and `DefaultCache.Get` only treats entries as expired when `ttl > 0`. The combination means a default `CachedEnforcer` caches indefinitely. There is no warning in the README or documentation; the only signal is reading `default-cache.go` carefully.

### The test suite tests the happy paths only

`enforcer_cached_test.go` is the entire test file for `CachedEnforcer`. It exercises:

1. ACL with `RemovePolicy` — cached entry correctly invalidated.
2. RBAC with `RemovePolicies` of permission rules (`p` prefix) — cached entries correctly invalidated.
3. RBAC with `ClearPolicy` — entire cache wiped.

There is **no test for RBAC with `RemoveGroupingPolicy`** or `DeleteRoleForUser` followed by a hit on a cached decision that depended on the removed role link. The absence of this test is the structural reason CASBIN-7 exists in the released code: nobody wrote the test that would have caught it.

## Issue tracker — relevant threads

(Issue body and comments could not be programmatically scraped during this collection; the GitHub HTML pages return empty bodies through the available web fetch path. The references below are based on issue numbers called out in the audit brief and on the maintainer-acknowledged scope visible in source-code comments.)

### Issue #832 — referenced in the audit brief

The brief identifies #832 as part of the cache-invalidation discussion thread. Without being able to fetch the issue body, the most defensible read is that this issue is part of the documented history where users reported stale-cache behavior on policy mutations and the maintainers responded by extending the per-mutator invalidation set rather than by switching to a coarse-invalidate-everything-on-any-mutation approach. The current state of `enforcer_cached.go` and `enforcer_cached_synced.go` reflects that incremental approach.

**Source URL:** https://github.com/casbin/casbin/issues/832

### Issue #1202 — referenced in the audit brief

The brief identifies #1202 as also part of the cache-invalidation discussion thread. The structure of the wrapper code suggests #1202 is part of the same family of reports: users encountering specific mutation paths that leave cache stale, and the resolution being either a new per-method override or a documentation note recommending `InvalidateCache`.

**Source URL:** https://github.com/casbin/casbin/issues/1202

## Related concern: matcher expression and govaluate

- The matcher is a `govaluate` expression evaluated against the request and policy parameters. Custom matchers passed to `EnforceWithMatcher` are user-supplied strings; they are NOT a code-injection vector against the Go runtime (govaluate is a sandboxed expression evaluator), but a misconstructed matcher can produce surprising authorization results. The Enforcer's matcher cache (`matcherMap`) caches compiled expressions by string identity; a malicious caller who passes a long stream of distinct `EnforceWithMatcher` strings can grow the matcher cache without bound. No size limit on `matcherMap` is enforced.
- The `eval(...)` matcher function (`util.HasEval`) lets a matcher dynamically eval a sub-expression from a policy field. This effectively lets policy authors embed expression fragments in CSV. It is documented as a feature; its risk surface is governance of who can author policy.

## Adapter-side concerns

- File adapter: `LoadPolicy` and `SavePolicy` rewrite the entire policy file. No atomic-rename safety; a crash mid-write produces a partial file.
- DB adapters: external modules, out of scope here. The `Watcher` mechanism is the canonical cross-node coordination path. The default `SetWatcher` callback wraps `Enforcer.LoadPolicy`, not the cache wrapper's `LoadPolicy` — see the `CachedEnforcer` + Watcher invariant violation noted in `04_invariants.md`.

## What QPB should re-derive

The CASBIN-7 finding the Windows replay run aims to reproduce is structurally:

1. From `enforcer_cached.go`: enumerate which mutation methods are overridden (`LoadPolicy`, `RemovePolicy`, `RemovePolicies`, `ClearPolicy`, `InvalidateCache`).
2. From `management_api.go` and `rbac_api.go`: enumerate which mutation methods change the state that `Enforce` reads. Notably: `AddPolicy`, `AddGroupingPolicy`, `RemoveGroupingPolicy`, `RemoveFilteredPolicy`, `RemoveFilteredGroupingPolicy`, `UpdatePolicy`, `UpdateGroupingPolicy`, and the RBAC wrappers.
3. Subtract: any method in (2) but not in (1) is a cache-staleness candidate. `RemoveGroupingPolicy` / `DeleteRoleForUser` is the most operationally important entry on that list because it implements permission revocation.
4. Construct a unit test or trace where: build CachedEnforcer with RBAC, Enforce a request that resolves via a role-link to true (cache `true`), `DeleteRoleForUser`, Enforce again, observe stale `true`. Within the TTL window (or indefinitely if TTL not set), the cached `true` is returned.

This re-derivation does not require reading #832 or #1202 — it can be done purely from the source-code structure of `enforcer_cached.go`, `rbac_api.go`, and the test file. The issue tracker provides corroborating context that this has been raised before but does not change the technical analysis.
