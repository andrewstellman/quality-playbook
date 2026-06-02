# Casbin Caching Behavior — CachedEnforcer, SyncedCachedEnforcer, Key Generation

## Sources

- CachedEnforcer source: https://raw.githubusercontent.com/casbin/casbin/master/enforcer_cached.go
- SyncedCachedEnforcer source: https://raw.githubusercontent.com/casbin/casbin/master/enforcer_cached_synced.go
- Cache interface: https://raw.githubusercontent.com/casbin/casbin/master/persist/cache/cache.go
- DefaultCache implementation: https://raw.githubusercontent.com/casbin/casbin/master/persist/cache/default-cache.go
- CachedEnforcer tests: https://raw.githubusercontent.com/casbin/casbin/master/enforcer_cached_test.go

## Context

`CachedEnforcer` is a decorator around `Enforcer` that intercepts `Enforce` calls, hashes the string-typed request tuple into a flat string key (e.g. `alice$$data1$$read$$`), and returns a cached boolean if the key is hot. The cache is a `map[string]cacheItem` behind a `sync.RWMutex`, with an optional TTL. The class's central correctness assumption is that **any policy change that affects a cached decision will be matched by a cache key the wrapper knows how to delete**. That assumption holds for direct ACL-style mutations (`AddPolicy`/`RemovePolicy`), where the rule's three fields `(sub, obj, act)` are identical to a request's three fields. It does NOT hold for RBAC-style mutations on the grouping policy, where the rule's fields `(user, role)` don't appear in any request key — yet the decisions that flow from those role-link changes are cached under request keys.

## Cache key generation

From `enforcer_cached.go`:

```go
func GetCacheKey(params ...interface{}) (string, bool) {
    key := strings.Builder{}
    for _, param := range params {
        switch typedParam := param.(type) {
        case string:
            key.WriteString(typedParam)
        case CacheableParam:
            key.WriteString(typedParam.GetCacheKey())
        default:
            return "", false
        }
        key.WriteString("$$")
    }
    return key.String(), true
}
```

- Each param is appended verbatim and followed by the literal separator `$$`.
- `Enforce("alice", "data1", "read")` → `"alice$$data1$$read$$"`.
- A non-string, non-`CacheableParam` argument (e.g., an ABAC struct subject) makes `GetCacheKey` return `("", false)`, and `Enforce` falls through to the uncached path. This is intentional: ABAC requests with object fields can't be safely cached on a flat string key.
- The separator `$$` is not escaped. **`Enforce("alice$$data1", "read", "")` would generate the same key as `Enforce("alice", "data1", "read")` (`"alice$$data1$$read$$"`).** This is a theoretical collision risk only if request strings contain literal `$$` — but the documentation does not warn callers to sanitize their inputs.
- The same function (`GetCacheKey`) is reused to derive the key from a policy rule when invalidating: `getKey(params...)` on `RemovePolicy("alice", "data1", "read")` produces the same `"alice$$data1$$read$$"`. This identity is what makes the key-based invalidation work for ACL mutations.

## CachedEnforcer.Enforce flow

```go
func (e *CachedEnforcer) Enforce(rvals ...interface{}) (bool, error) {
    if atomic.LoadInt32(&e.enableCache) == 0 {
        return e.Enforcer.Enforce(rvals...)         // cache disabled → pass-through
    }
    key, ok := e.getKey(rvals...)
    if !ok {
        return e.Enforcer.Enforce(rvals...)         // non-string args → pass-through
    }
    if res, err := e.getCachedResult(key); err == nil {
        return res, nil                              // cache hit → return cached bool
    } else if err != cache.ErrNoSuchKey {
        return res, err
    }
    res, err := e.Enforcer.Enforce(rvals...)        // cache miss → evaluate
    if err != nil {
        return false, err
    }
    err = e.setCachedResult(key, res, e.expireTime) // store result with TTL
    return res, err
}
```

- `enableCache` is atomic int32; toggling it does not flush the cache. After `EnableCache(false)` followed by mutations followed by `EnableCache(true)`, the previously-cached entries become live again. **Toggling EnableCache is NOT a substitute for InvalidateCache.**
- A cache hit returns the boolean immediately — no policy evaluation, no role-link traversal, no matcher compilation.
- A cache miss runs the full base `Enforce` and stores the result under the request key.
- `getCachedResult` and `setCachedResult` take `e.locker` exclusively (Lock, not RLock) — this serializes ALL cache accesses, so under contention the cache is a bottleneck. (`SyncedCachedEnforcer` does not take this lock around get/set because the underlying SyncCache handles its own concurrency.)

## What invalidates the cache — and what doesn't

From `enforcer_cached.go`:

| Operation | Cache action |
|---|---|
| `Enforce(...)` (miss) | Stores result under request key with TTL |
| `LoadPolicy()` | Clears entire cache, then loads from adapter |
| `RemovePolicy(sub, obj, act)` | Deletes ONE key: `GetCacheKey(sub, obj, act)` |
| `RemovePolicies(rules [][]string)` | Deletes ONE key per rule |
| `ClearPolicy()` | Clears entire cache |
| `InvalidateCache()` | Clears entire cache |
| `EnableCache(false)` | No cache change (just stops using it) |
| `SetCache(c)` | Replaces cache pointer (old entries dropped only because new map is empty) |
| `AddPolicy(...)` | **No cache change.** `CachedEnforcer` does not override this. |
| `AddPolicies(...)` | **No cache change.** |
| `AddGroupingPolicy(...)` (== `AddRoleForUser`) | **No cache change.** |
| `RemoveGroupingPolicy(...)` (== `DeleteRoleForUser`) | **No cache change.** |
| `RemoveFilteredPolicy(...)` | **No cache change.** |
| `RemoveFilteredGroupingPolicy(...)` (== `DeleteRolesForUser`, part of `DeleteUser`, part of `DeleteRole`) | **No cache change.** |
| `UpdatePolicy(old, new)` | **No cache change.** |
| `UpdateGroupingPolicy(old, new)` | **No cache change.** |
| Watcher callback (default `func(string) { _ = e.LoadPolicy() }`) | Calls embedded `Enforcer.LoadPolicy`, NOT the cache-clearing override. **No cache change.** |

The gap between rows that say "Clears entire cache" or "Deletes ONE key" and rows that say "No cache change" is the CASBIN-7 attack surface.

## SyncedCachedEnforcer differences

`SyncedCachedEnforcer` is structurally similar but covers more mutation paths:

| Operation | CachedEnforcer | SyncedCachedEnforcer |
|---|---|---|
| `AddPolicy` | No invalidation | Deletes key by `GetCacheKey(params...)` |
| `AddPolicies` | No invalidation | Deletes one key per rule |
| `RemovePolicy` | Deletes one key | Deletes one key |
| `RemovePolicies` | Deletes one key per rule | Deletes one key per rule |
| `AddGroupingPolicy` / `RemoveGroupingPolicy` | No invalidation | **Still no invalidation** |
| `RemoveFilteredPolicy` / `RemoveFilteredGroupingPolicy` | No invalidation | **Still no invalidation** |
| `LoadPolicy` | Clears entire cache | Clears entire cache |

The `SyncedCachedEnforcer` invalidation logic (`checkOneAndRemoveCache`, `checkManyAndRemoveCache`) computes the key from the policy rule itself and deletes that single key. This works for `p`-prefix rules because rule shape `(sub, obj, act)` matches request shape, but does nothing useful for `g`-prefix rules because rule shape `(user, role)` does not appear in any request key.

## DefaultCache TTL semantics

From `default-cache.go`:

```go
func (c *DefaultCache) Set(key string, value bool, extra ...interface{}) error {
    ttl := time.Duration(-1)
    if len(extra) > 0 {
        ttl = extra[0].(time.Duration)
    }
    (*c)[key] = cacheItem{
        value: value,
        expiresAt: time.Now().Add(ttl),
        ttl: ttl,
    }
    return nil
}

func (c *DefaultCache) Get(key string) (bool, error) {
    if res, ok := (*c)[key]; !ok {
        return false, ErrNoSuchKey
    } else {
        if res.ttl > 0 && time.Now().After(res.expiresAt) {
            delete(*c, key)
            return false, ErrNoSuchKey
        }
        return res.value, nil
    }
}
```

- `expireTime == 0` on CachedEnforcer → `time.Duration(0)` passed as the extra arg → stored `ttl = 0`. **`Get` only checks expiry when `ttl > 0`**, so `ttl == 0` entries never expire. The default-configured CachedEnforcer caches indefinitely.
- This means an application that adopts `CachedEnforcer` for speed without setting `SetExpireTime(5*time.Second)` will, after a `DeleteRoleForUser` for a user with a hot cached `Enforce` decision, return a stale `true` forever (until `InvalidateCache`, `LoadPolicy`, `ClearPolicy`, or process restart).
- A `SetExpireTime(5 * time.Second)` configuration narrows the staleness window to 5 seconds but does not eliminate it. Whether this is acceptable depends on the application's tolerance for a 5-second permission-revocation window — security-sensitive applications generally cannot tolerate any such window.

## The test that didn't catch it

From `enforcer_cached_test.go`, the existing test exercises only:

1. `RemovePolicy` on ACL → cached decision is correctly invalidated.
2. `RemovePolicies` on RBAC, but the removed rules are `p` (permission) rules, not `g` (grouping) rules — the test removes `alice, data1, read` and `bob, data2, write`, both of which are direct permissions.
3. `ClearPolicy` on RBAC → entire cache wiped, all decisions correctly become false.

**The test never executes `DeleteRoleForUser` / `RemoveGroupingPolicy` followed by `Enforce` on a cached entry that depended on the removed role.** That is the missing test, and the existence of the bug class is exactly the gap between "we test RemovePolicy invalidation" and "we don't test RemoveGroupingPolicy invalidation."

## Caching Invariants

- After any successful policy mutation, `CachedEnforcer.Enforce(req)` MUST return the same result as `Enforcer.Enforce(req)` on the underlying base enforcer with no cache. The cache MUST NOT introduce a divergence.
- A cached `Enforce(sub, obj, act) → true` decision that was reached via `g(sub, role)` matching a permission held by `role` MUST be invalidated when:
  - `RemoveGroupingPolicy(sub, role)` succeeds, OR
  - `DeleteRoleForUser(sub, role)` succeeds, OR
  - `RemoveFilteredGroupingPolicy` removes any rule that breaks the chain `sub → ... → role`, OR
  - The role itself loses the permission via `RemovePolicy(role, obj, act)` (this is covered — same request key), OR
  - `DeleteUser(sub)` / `DeleteRole(role)` succeeds.
  Of these, **only the fourth case is actually invalidated by the current code.** The others leave stale `true` entries.
- A cached `Enforce(sub, obj, act) → false` decision MUST be invalidated when `AddPolicy(sub, obj, act)` or `AddRoleForUser(sub, role)` (where `role` has the permission) succeeds.
- The `$$` separator in `GetCacheKey` is structural; cache keys SHOULD treat request values opaquely. Callers MUST NOT rely on key parsing being collision-free if their request values contain `$$`.
- If `e.expireTime <= 0`, cache entries persist indefinitely. The application MUST call `InvalidateCache` or `LoadPolicy` after any mutation the wrapper doesn't invalidate, OR explicitly set a TTL with `SetExpireTime`.
- A Watcher-driven reload (cross-process policy change) MUST clear the cache on the receiving node. The default callback does not do this on CachedEnforcer because it captures the base Enforcer pointer; the application MUST install a custom callback that calls the wrapper's `LoadPolicy`.
