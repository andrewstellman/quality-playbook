# OpenFGA Consistency, Caching, and Cache Invalidation

## Sources

- https://openfga.dev/docs/interacting/consistency
- https://openfga.dev/blog/query-consistency-options-announcement
- https://openfga.dev/docs/getting-started/setup-openfga/configure-openfga
- https://openfga.dev/docs/best-practices/running-in-production
- https://github.com/openfga/openfga/blob/main/internal/cachecontroller/cache_controller.go
- https://github.com/openfga/openfga/blob/main/internal/graph/cached_resolver.go
- https://github.com/openfga/openfga/blob/main/pkg/server/commands/list_objects.go
- https://github.com/openfga/openfga/pull/2779
- https://github.com/openfga/openfga/pull/2791
- https://github.com/openfga/openfga/security/advisories/GHSA-32q6-rr98-cjqv (CVE-2024-56323)
- https://deepwiki.com/openfga/openfga/2.3-performance-optimizations

## Context

OpenFGA's check-query cache exists to keep latency low on the hot path: rather than re-traversing the rewrite graph for every Check, the engine caches `{cacheKey -> (allowed, lastModified)}` and serves repeat queries from memory until the entry expires or is invalidated. The cache is **disabled by default** and is only meaningful when explicitly enabled. When it is enabled, two facts dominate this audit:

1. The cache must not outlive the data it was computed from beyond an accepted, documented staleness window.
2. The `CacheController` is the engine's mechanism for closing that window — by polling the store's changelog for new writes and invalidating affected entries.

PR #2779 (merged 2025-11-06, reverted 2025-11-06 by PR #2791) is the textbook case of how this invariant breaks in practice: the fix tried to plug a hole where `LastInvalidationTime.IsZero()` made *every* cached entry look valid, but the fix assumed a CacheController is always running. When that assumption fails (Noop controller, controller not configured), the fix would disable the cache entirely — so it was reverted, leaving the staleness window unmanaged for the ListObjects fan-out path.

## The configuration knobs

- `OPENFGA_CHECK_QUERY_CACHE_ENABLED` — turn the check cache on/off. **Default: disabled.**
- `OPENFGA_CHECK_QUERY_CACHE_TTL` — how long a cached entry remains valid. The upper bound on staleness if no invalidation event arrives.
- `OPENFGA_CHECK_QUERY_CACHE_LIMIT` — max entries.
- `OPENFGA_CACHE_CONTROLLER_ENABLED` — turn the CacheController polling on/off.
- `OPENFGA_CACHE_CONTROLLER_TTL` — how often the controller polls the changelog for new writes.

When caching is disabled, every Check evaluates from storage: strong consistency, regardless of mode requested.

## Consistency modes (recap)

| Mode | Behavior | Cache use | DB target |
| --- | --- | --- | --- |
| `MINIMIZE_LATENCY` (default) | Use cached results when available; may read from a secondary. | Yes | Secondary if configured, primary otherwise |
| `HIGHER_CONSISTENCY` | Bypass the cache; read directly from primary. | No | Primary |

The mode is a request-level parameter on Check, ListObjects, ListUsers, and BatchCheck. The engine must honor it both at the top level and in any internal fan-out (the key observation behind the ListObjects fan-out cache discussion).

## How the cache key is constructed

The cache key for a Check is a function of `(store_id, model_id, user, relation, object, contextual_tuples, context)`. Contextual tuples and request context *must* participate in the key — if they don't, two requests differing only in contextual data collide. This is exactly what CVE-2024-56323 was: caching + contextual tuples carrying conditions → cache key collision → wrong (over-permissive) decision returned. The fix (in v1.8.3) included contextual-tuple condition data in the key.

## CachedCheckResolver: the validity check

The hot-path cache check lives in `internal/graph/cached_resolver.go`, function `CachedCheckResolver.ResolveCheck`. The relevant logic at the time of PR #2779:

```go
// Pseudocode reflecting the actual code paths in question.
tryCache := req.Consistency != openfgav1.ConsistencyPreference_HIGHER_CONSISTENCY
if tryCache {
    if cachedResp := c.cache.Get(cacheKey); cachedResp != nil {
        res := cachedResp.(*CheckResponseCacheEntry)
        isValid := res.LastModified.After(LastInvalidationTime)
        if isValid {
            return res.CheckResponse, nil
        }
    }
}
// fall through to full evaluation
```

`LastInvalidationTime` comes from the CacheController. If the controller has never seen a changelog entry for this store, it returns `time.Time{}` (the Go zero value). The pre-PR-2779 code path then computed `res.LastModified.After(time.Time{})`, which is `true` for **any** non-zero `LastModified` — i.e., **every cached entry is considered valid**, even if it's been around forever. This is the latent over-grant: a revoked grant whose cached `allowed=true` would be served indefinitely until something else evicted the entry.

## CacheController: how invalidation is supposed to work

The CacheController polls the **changelog** table for each store at a configured interval. When it sees new writes for a store, it advances the `LastInvalidationTime` for that store. Cached check entries with `LastModified` older than this time are then considered invalid and the next request triggers re-evaluation.

```
Tuple write or delete in store X
       |
       v
ChangelogTable[X] += { id, timestamp, ... }
       |
       v  (CacheController poll, interval = OPENFGA_CACHE_CONTROLLER_TTL)
       |
       v
LastInvalidationTime[X] = latest changelog timestamp
       |
       v
Subsequent CachedCheckResolver consults this; entries with LastModified <
LastInvalidationTime are bypassed and recomputed.
```

The staleness floor is therefore bounded by `OPENFGA_CACHE_CONTROLLER_TTL` + the time to issue and observe the changelog write. Cached entries older than `OPENFGA_CHECK_QUERY_CACHE_TTL` are also evicted regardless of invalidation events; that TTL is the absolute upper bound.

## NoopCacheController: what happens when invalidation is off

`NoopCacheController` (in `internal/cachecontroller/cache_controller.go`) is the no-invalidation implementation. Pre-PR-2779 it always returned `time.Time{}` from `DetermineInvalidationTime`, which combined with the validity check above to make every cached entry valid forever (modulo TTL). Post-PR-2779 it had an optional `InvalidationTime` field for tests; the revert (PR #2791) removed it again — back to returning the zero time always.

## PR #2779: "if LastInvalidationTime.IsZero(), ignore cache"

**Author**: `justincoh`. **Merged**: 2025-11-06 15:50 UTC. **Reverted**: 2025-11-06 16:34 UTC by PR #2791 (same author).

### The fix the PR shipped

1. **`internal/graph/cached_resolver.go`** — changed the cache-consult gate from `if tryCache` to `if tryCache && !req.LastCacheInvalidationTime.IsZero()`. Effect: if no invalidation time is established for the store, do not trust the cache.
2. **`internal/cachecontroller/cache_controller.go`** — extended `NoopCacheController` with an `InvalidationTime` field (test-only) so tests can simulate a controller that has an invalidation time.
3. **`pkg/server/commands/list_objects.go`** — added `WithCheckCommandCache(q.sharedDatastoreResources, q.cacheSettings)` to the `NewCheckCommand` invocation inside `ListObjectsQuery.evaluate`. **This is the line that makes ListObjects' fan-out Checks participate in the same cache and invalidation pipeline as top-level Checks.**

PR description (verbatim excerpt):

> When the CacheController is running, the first thing it does is call `DetermineInvalidationTime`. This func attempts to read from the changelog cache to find what a store's most recent write was. In cases where there is nothing in that cache, or that cached entry is older than the cache controller's defined TTL, we fallback to `time.Time{}`.
>
> The cached check resolver is currently directly using the zero time when retrieving cached check results:
>
> `isValid := res.LastModified.After(LastInvalidationTime)`
>
> If the LastInvalidationTime above is `time.Time{}`, then **any** cached check response will be considered valid. This is incorrect. Just because a changelog cache entry was not found, or was older than the cache controller's TTL, does not necessarily mean we can just trust the check cache.

### Files touched

```
CHANGELOG.md                                      +3   -0
internal/cachecontroller/cache_controller.go      +4   -2
internal/graph/cached_resolver.go                 +1   -1
internal/graph/cached_resolver_test.go            +8   -3
pkg/server/commands/list_objects.go               +1   -0   <-- WithCheckCommandCache added
pkg/server/commands/list_objects_test.go         +21   -2
pkg/server/server_test.go                       +156  -38
```

## PR #2791: revert

**Author**: `justincoh`. **Merged**: 2025-11-06 16:34 UTC (44 minutes after #2779 merged).

PR description:

> Reverts openfga/openfga#2779
>
> That PR has an implicit assumption that the CacheController will always be used, which is incorrect, and could lead to an entirely unused check cache.

### What the revert means in practice

The fix correctly identified that `LastInvalidationTime.IsZero()` makes every cached entry look valid — that's a real correctness gap. But the fix's implementation made the cache **unused** in deployments that don't run a CacheController (e.g., NoopCacheController, or no controller configured). Since the cache is the whole point of the optimization, the team chose to revert to the pre-#2779 behavior (every cached entry treated as valid when invalidation time is zero) rather than ship a fix that effectively disables the cache for many users.

Critically, **the revert also removed the `WithCheckCommandCache` wiring in `pkg/server/commands/list_objects.go`**. So as of mid-November 2025, the documented issue persists in two compounding forms:

1. **The zero-time cache-validity gap.** When the CacheController hasn't published an invalidation time, every cached check entry is treated as valid. A revoked grant can survive in the cache until TTL expires.
2. **ListObjects fan-out Check does not consult the same cache pipeline as top-level Check.** Even after both issues are independently understood, the residual code state in `list_objects.go` (no `WithCheckCommandCache`) means ListObjects' internal Checks behave differently from a direct Check for the same question.

This is the "OPENFGA-2 / GHSA-related" finding QPB is replaying.

## Why this matters for an audit (the security framing)

- **Revocation correctness depends on cache invalidation.** A deleted `viewer` tuple must invalidate any cached `allowed=true` for that user/relation/object — within an accepted staleness window (cache TTL + controller poll interval). The pre-PR-2779 behavior makes that window *unbounded* in deployments without a working CacheController, because the zero-time check makes every cached entry valid.
- **`HIGHER_CONSISTENCY` is the documented escape hatch.** A revocation-sensitive caller must use `HIGHER_CONSISTENCY` to bypass the cache. But callers don't always know they need to, and ListObjects callers in particular may not realize their per-object decisions are running through fan-out Checks with different cache wiring.
- **The fan-out path is a distinct invariant.** A Check called directly and a Check issued as a ListObjects fan-out leg must produce the same answer for the same `(user, relation, object)` under the same consistency mode. If their cache hookups differ, they don't.
- **Caching + contextual tuples is historically dangerous.** CVE-2024-56323 was the same family of bug — cache key didn't capture contextual condition data, so two requests collided. The fix (v1.8.3) was structurally similar to PR #2779: tighten what the cache may serve. This pattern recurs.

## Security-relevant invariants (cache + consistency)

- **`HIGHER_CONSISTENCY` must bypass the cache on every Check call path, including internal fan-out Checks from ListObjects, ListUsers, and BatchCheck.** A path that honors the mode at the outer command but consults a cache deeper down is a contract violation.
- **A cached decision must not outlive the data it was computed from beyond the accepted staleness window.** That window is bounded by `OPENFGA_CHECK_QUERY_CACHE_TTL` (absolute) and by `OPENFGA_CACHE_CONTROLLER_TTL` (when invalidation is running). When invalidation is not running, the engine must either disable the cache or expose the unbounded-staleness risk explicitly — the PR #2779/#2791 episode is exactly the project working through this trade-off.
- **`LastInvalidationTime == zero` is not equivalent to "no invalidations have occurred."** It is equivalent to "no information." Treating "no information" as "all cached entries valid" is a latent over-grant. The pre-#2779 code does this; #2779 attempted to fix it; #2791 reverted because the fix had a different failure mode (cache effectively unused).
- **Fan-out Checks inside ListObjects must use the same cache pipeline as top-level Checks.** Specifically, `NewCheckCommand` inside `ListObjectsQuery.evaluate` must be constructed with `WithCheckCommandCache` so the fan-out participates in invalidation. The post-revert state of `pkg/server/commands/list_objects.go` lacks this option; that is the residual issue surface.
- **Cache key must include contextual tuples and condition context.** Two requests differing only in those must not collide in the cache (CVE-2024-56323 lesson).
- **The cache must never serve an entry across stores.** `store_id` is part of the cache key; cross-store cache contamination would be a tenant-isolation breach.
- **Changelog writes are the ground truth for invalidation.** A tuple write or delete that does not produce a changelog entry leaves the CacheController unable to advance `LastInvalidationTime`, and stale entries persist. The Write path must always emit changelog entries.

## What to look for in code review

When auditing the cache pipeline:

1. **`internal/graph/cached_resolver.go`** — does the `tryCache` gate check `LastCacheInvalidationTime.IsZero()`? Post-revert: no. Decide whether that's acceptable for the deployment posture.
2. **`internal/cachecontroller/cache_controller.go`** — what does `NoopCacheController.DetermineInvalidationTime` return? Post-revert: always zero time. Combined with #1, every cached entry is valid until TTL.
3. **`pkg/server/commands/list_objects.go`** (`ListObjectsQuery.evaluate`) — is `WithCheckCommandCache` passed to `NewCheckCommand`? Post-revert: no. The fan-out Checks therefore do not participate in the same cache pipeline as top-level Checks.
4. **`pkg/server/commands/check.go`** — top-level Check does wire cache via `WithCheckCommandCache`. Compare with ListObjects fan-out to confirm the divergence.
5. **Test files (`pkg/server/server_test.go`, `list_objects_test.go`, `cached_resolver_test.go`)** — the PR #2791 revert removed nested subtests covering cache invalidation scenarios under ListObjects. Whatever coverage existed for ListObjects + cache invalidation no longer exists.
