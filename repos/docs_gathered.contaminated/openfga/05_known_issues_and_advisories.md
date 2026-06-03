# OpenFGA Known Issues: Security Advisories and PR History

## Sources

- https://github.com/openfga/openfga/security/advisories
- https://github.com/advisories?query=openfga
- https://github.com/openfga/openfga/security/advisories/GHSA-95x7-mh78-7w2r
- https://github.com/advisories/GHSA-vj4m-83m8-xpw5
- https://github.com/openfga/openfga/security/advisories/GHSA-8cph-m685-6v6r
- https://github.com/advisories/GHSA-3f6g-m4hr-59h8
- https://github.com/openfga/openfga/security/advisories/GHSA-32q6-rr98-cjqv
- https://github.com/advisories/GHSA-g4v5-6f5p-m38j
- https://github.com/advisories/GHSA-c72g-53hw-82q7
- https://github.com/openfga/openfga/security/advisories/GHSA-mgh9-4mwp-fg55
- https://github.com/openfga/openfga/security/advisories/GHSA-jq9f-gm9w-rwm9
- https://github.com/openfga/openfga/pull/2779
- https://github.com/openfga/openfga/pull/2791

## Context

OpenFGA has a substantial published advisory history — nine GitHub Security Advisories, each with a CVE. Almost all are categorized as **authorization bypass** or **improper policy enforcement** (CWE-285 / CWE-863). The recurring pattern is not in transport, storage, or auth plumbing, but in the **graph-evaluation engine**: specific *combinations* of rewrite operators (exclusion `but not`, intersection `and`, tuple-to-userset `from`), usersets, type-bound public access (`*`), conditions, and contextual tuples produce incorrect decisions. The single exception (CVE-2022-39340) is a missing-auth endpoint. This pattern is what makes OpenFGA an interesting QPB target: the bugs require composing features the way real models do, and the smallest input shape that triggers a bug is usually non-obvious.

Below are the nine published advisories plus the recent PR #2779 / PR #2791 episode that is the central concern of this audit.

---

## CVE-2022-39340 (GHSA-95x7-mh78-7w2r): Information Disclosure on `streamed-list-objects`

- **Status**: Fixed in v0.2.4 | **Affected**: `<= 0.2.3` | **Severity**: Moderate
- **Impact**: Unauthenticated callers could enumerate objects in a store.
- **Category**: Missing authentication on a streaming endpoint.

**Problem.** During an internal security assessment, `streamed-list-objects` was found not to validate the authorization header. An unauthenticated network caller could call the endpoint and stream object IDs from any store.

**Invariant violated.** Every data-returning endpoint must enforce server auth uniformly, including streaming variants.

---

## CVE-2022-39341 (GHSA-vj4m-83m8-xpw5): Authorization Bypass via Tupleset Wildcard

- **Status**: Fixed in v0.2.4 | **Affected**: `<= 0.2.3` | **Severity**: Moderate (CVSS 5.9) | CWE-285, CWE-863
- **Impact**: Authorization bypass.
- **Category**: Rewrite-evaluation correctness — wildcard on a tupleset relation.

**Problem.** A tuple with a wildcard (`*`) user assigned to a tupleset relation (the right side of `X from Y`) caused an authorization bypass. The fix forbids wildcards on tupleset relations and is not backward-compatible with models that used a wildcard there. Fix commit: `b466769`.

**Invariant violated.** Wildcards on tupleset relations are forbidden by the model semantics.

---

## CVE-2024-31452 (GHSA-8cph-m685-6v6r): Authorization Bypass with Intersection/Exclusion + Cyclical Relationships

- **Status**: Fixed in v1.5.3 | **Affected**: `> 1.5.0, < 1.5.3` | **Severity**: High
- **Impact**: Incorrect Check / ListObjects decision when the model combined `and` or `but not` with cyclical relationships.
- **Category**: Rewrite-evaluation correctness — set operations over cycles.

**Problem.** Models that combine intersection or exclusion with cyclical relationships could return wrong (over-permissive) decisions. Backward-compatible fix.

**Invariant violated.** Cyclic relationships must terminate with the correct answer; intersection/exclusion must implement their set semantics under cycles.

---

## CVE-2024-42473 (GHSA-3f6g-m4hr-59h8): Authorization Bypass with `but not` + `from` + Userset

- **Status**: Fixed in v1.5.9 | **Affected**: v1.5.7, v1.5.8 | **Severity**: High (CVSS 8.2) | CWE-285, CWE-863
- **Impact**: Check returned `allowed=true` when set semantics required `false`.
- **Category**: Rewrite-evaluation correctness — exclusion composed with tuple-to-userset and a userset.

**Problem.** Calling Check against a model that uses `but not` and `from` expressions together with a userset returned an incorrect "allowed." CVSS Integrity:High; backward-compatible fix.

**Invariant violated.** Exclusion must actually subtract; tuple-to-userset must compute the correct join; combinations must compose correctly.

---

## CVE-2024-56323 (GHSA-32q6-rr98-cjqv): Authorization Bypass with Conditions + Caching + Contextual Tuples

- **Status**: Fixed in v1.8.3 | **Affected**: `>= 1.3.8, < 1.8.3` | **Severity**: Moderate (CVSS 5.8)
- **Impact**: Over-permissive Check / ListObjects decision.
- **Category**: Cache-key correctness — contextual tuples carrying conditions did not participate in the cache key.

**Problem (all three preconditions required):**
1. Model uses conditions.
2. Server has `OPENFGA_CHECK_QUERY_CACHE_ENABLED`.
3. The Check/ListObjects call carries contextual tuples that include conditions.

Under those conditions the cache could return a decision computed for different condition context. Backward-compatible fix.

**Invariant violated.** Cache key must include contextual tuples and condition context.

**Relevance to this audit.** This is the prior cache+contextual-tuple bypass; it sets the precedent that the cache layer is a recurring correctness surface and motivates why PR #2779 was filed.

---

## CVE-2025-25196 (GHSA-g4v5-6f5p-m38j): Authorization Bypass — Public Access + Userset of Same Type

- **Status**: Fixed in v1.8.5 | **Affected**: `<= 1.8.4` | **Severity**: Moderate (CVSS 5.8) | CWE-285
- **Impact**: Userset Check resolved against a type-bound public-access tuple incorrectly.
- **Category**: Rewrite-evaluation correctness — type-bound public access vs userset of same type.

**Problem (all preconditions required):**
- Relation directly assignable to both `type:*` and a userset of the same type.
- A `type:*` tuple is assigned; a matching userset tuple is not.
- The Check request's `user` is a userset of the same type as the public-access tuple.

The engine wrongly resolved the userset request against the public-access tuple. Fix commit: `0aee4f4`. Backward-compatible.

**Invariant violated.** Type-bound public access and direct usersets of the same type must not collide in evaluation.

---

## CVE-2025-48371 (GHSA-c72g-53hw-82q7): Authorization Bypass — Contextual Tuples Bypassing Type Restrictions

- **Status**: Fixed in v1.8.13 | **Affected**: `>= 1.8.0, < 1.8.13` | **Severity**: Moderate (CVSS 5.8) | CWE-285
- **Impact**: Over-permissive Check / ListObjects decision.
- **Category**: Contextual-tuple type filtering vs userset evaluation.

**Problem (all preconditions required):**
- Relation directly assignable by both type-bound public access and a userset of the same type.
- Check/ListObjects carries contextual tuples for that relation.
- Those contextual tuples' `user` is a userset.
- No type-bound public-access tuples are assigned to the relation.

**Root cause.** `CombinedTupleReader.ReadUsersetTuples` did not filter contextual tuples by `allowedUserTypeRestrictions`, so unrelated contextual tuples leaked into the userset evaluation. Fix: filter contextual tuples by type restrictions for `ReadUsersetTuples`. Fix commit: `e5960d4`. Reported by `@udyvish`. Go vuln: GO-2025-3707. Backward-compatible.

**Invariant violated.** Contextual tuples must be filtered by type restrictions on every read path, including internal usersets.

---

## CVE-2025-55213 (GHSA-mgh9-4mwp-fg55): Improper Policy Enforcement — >1 Directly-Assignable Userset of Same Type

- **Status**: Fixed in v1.9.5 | **Affected**: v1.9.3, v1.9.4 | **Severity**: Moderate (CVSS 5.8)
- **Impact**: Incorrect Check / ListObjects decision.
- **Category**: Rewrite-evaluation correctness — a Check optimization ("weight 2 optimization") misbehaved.

**Problem (all preconditions required):**
- Relation directly assignable by more than one userset of the same type.
- Userset tuples assigned to that relation.

**Root cause.** The "weight 2 optimization" assumed a single userset of a given type was directly assignable; when more than one was, it short-circuited incorrectly. v1.9.5 disables the weight-2 optimization for this case. Workaround: downgrade to v1.9.2 with `enable-check-optimizations` removed from `OPENFGA_EXPERIMENTALS`. Reported by Dominic Harries and `rrozza-apolitical`. Backward-compatible.

**Invariant violated.** Performance optimizations must not change the set the rewrite denotes.

---

## CVE-2026-24851 (GHSA-jq9f-gm9w-rwm9): Improper Policy Enforcement — Public + Non-Public Tuples and Object Ordering

- **Status**: Fixed in v1.11.3 | **Affected**: `>= 1.8.5, <= 1.11.2` | **Severity**: Moderate (CVSS 5.8)
- **Impact**: Incorrect Check decision under a specific tuple shape.
- **Category**: Rewrite-evaluation correctness — interaction of public-access tuples, non-public tuples, and lexicographic object-ID ordering.

**Problem (all preconditions required):**
- Relation directly assignable by both type-bound public access and type-bound non-public access.
- A public-access tuple is assigned for the relation.
- A non-public-access tuple exists for the same object + relation.
- A non-public-access tuple exists for a different object whose object ID is lexicographically larger, with the same user and relation.

No workaround; upgrade to v1.11.3. Published February 2026. Backward-compatible.

**Invariant violated.** Public + non-public tuples on the same relation must be evaluated correctly regardless of object-ID lex order.

---

## PR #2779 / PR #2791: ListObjects Fan-out Cache Invalidation (the OPENFGA-2 finding QPB is replaying)

### PR #2779: "fix: if LastInvalidationTime.IsZero(), ignore cache"

- **Author**: `justincoh`. **Merged**: 2025-11-06 15:50 UTC. **Commits**: 11. **Files**: 7. **Diff**: +194 / -46.
- **Files changed**:
  - `internal/cachecontroller/cache_controller.go` — `NoopCacheController` gained an optional `InvalidationTime` field (test-only).
  - `internal/graph/cached_resolver.go` — cache gate became `if tryCache && !req.LastCacheInvalidationTime.IsZero()`.
  - `pkg/server/commands/list_objects.go` — `WithCheckCommandCache(q.sharedDatastoreResources, q.cacheSettings)` added to the `NewCheckCommand` call inside `ListObjectsQuery.evaluate`. **This is the line that makes ListObjects' fan-out Checks participate in the cache pipeline.**
  - Plus three test files updated.

The PR description (excerpt): "When the CacheController is running, the first thing it does is call `DetermineInvalidationTime`. ... In cases where there is nothing in that cache, or that cached entry is older than the cache controller's defined TTL, we fallback to `time.Time{}`. ... If the LastInvalidationTime above is `time.Time{}`, then **any** cached check response will be considered valid. This is incorrect."

### PR #2791: "Revert 'fix: if LastInvalidationTime.IsZero(), ignore cache'"

- **Author**: `justincoh`. **Merged**: 2025-11-06 16:34 UTC (44 minutes later). **Commits**: 1. **Files**: 7. **Diff**: +46 / -194.
- Revert reason (from the PR description): "That PR has an implicit assumption that the CacheController will always be used, which is incorrect, and could lead to an entirely unused check cache."

**Net post-revert state of `pkg/server/commands/list_objects.go`.** No `WithCheckCommandCache` option in the `ListObjectsQuery.evaluate` fan-out. ListObjects' internal Checks therefore do not participate in the same cache pipeline as top-level Checks — even when the top-level Check command is wired with `WithCheckCommandCache` and the CacheController is running.

**Residual issue surface.** A stale cached `allowed=true` set by a top-level Check at time T1 can survive past a tuple deletion at T2 if the deletion's changelog entry has not yet been polled or if no controller is configured. Under `MINIMIZE_LATENCY` (default), a subsequent ListObjects whose fan-out hits the same cache key returns the stale allow. The documented mitigation is `HIGHER_CONSISTENCY`, but callers don't always know to use it for revocation-sensitive ListObjects calls.

**Invariants relevant.** "Fan-out Checks inside ListObjects must use the same cache pipeline as top-level Checks." "`LastInvalidationTime == zero` must not mean 'all cached entries valid.'" (See `04_invariants.md`.)

---

## Cross-cutting pattern

- **8 of 9 advisories are authorization-bypass / improper-policy-enforcement in the graph-evaluation engine.** The trigger is a *combination* of features: tuple-to-userset (`from`), usersets, type-bound public access (`*`), exclusion (`but not`), intersection (`and`), conditions, contextual tuples.
- **Type-restriction filtering of usersets and contextual tuples is implicated in three advisories** (CVE-2025-48371, CVE-2025-25196, CVE-2026-24851). This is the engine's softest underbelly.
- **Performance optimizations are a recurring source of correctness bugs** (CVE-2025-55213 weight-2 optimization). The PR #2779 reasoning explicitly tries to *tighten* the cache-validity check; the revert backed off because it would have effectively disabled the cache — illustrating the same tension.
- **Caching + contextual tuples / conditions / fan-out is the cache-layer pattern.** CVE-2024-56323 is the contextual-tuple-in-cache-key form; PR #2779/#2791 is the LastInvalidationTime-zero + fan-out form. Both belong to the same family: the cache must capture every dimension of the query that can change the answer, and it must invalidate when the underlying data does.
- **Severity skews Moderate (CVSS 5.8)** because most require a specific model shape and specific tuple/contextual-tuple assignments, but the subsystem impact (authorization decisions being subverted) is consistently rated High on confidentiality and integrity.

## Maintainer-acknowledged limitations (non-CVE)

- **ListObjects can truncate under deadline** (issue #1961). The result does not clearly signal incompleteness.
- **Conditions cannot reference attributes from relationships** (issue #3088). This is by design; the proposed enhancement would expand the attack surface for condition evaluation.
- **The CacheController is optional.** When not running, cache invalidation does not advance, and the `LastInvalidationTime == zero` path (post-PR #2791 revert) treats all cached entries as valid until TTL — the trade-off documented in the revert reasoning.
- **OpenFGA does not authenticate end users.** Application owns authentication; OpenFGA answers about whoever the app names.
