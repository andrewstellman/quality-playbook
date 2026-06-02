# Casbin API Contract — Enforce, Policy Mutations, RBAC, Cache

## Sources

- Enforcer source: https://raw.githubusercontent.com/casbin/casbin/master/enforcer.go
- Management API: https://raw.githubusercontent.com/casbin/casbin/master/management_api.go
- RBAC API: https://raw.githubusercontent.com/casbin/casbin/master/rbac_api.go
- CachedEnforcer source: https://raw.githubusercontent.com/casbin/casbin/master/enforcer_cached.go
- SyncedCachedEnforcer source: https://raw.githubusercontent.com/casbin/casbin/master/enforcer_cached_synced.go
- SyncedEnforcer source: https://raw.githubusercontent.com/casbin/casbin/master/enforcer_synced.go
- Management API docs: https://casbin.org/docs/management-api
- RBAC API docs: https://casbin.org/docs/rbac-api

## Context

This document is the contract surface that QPB needs to detect access-control invariants against. The Go API is fanned out across three layers: the **core Enforcer** (`Enforce`, low-level `addPolicy`/`removePolicy`), the **Management API** (`AddPolicy`/`RemovePolicy`/`AddGroupingPolicy`/`RemoveGroupingPolicy`, plus named/filtered variants), and the **RBAC API** (`AddRoleForUser`/`DeleteRoleForUser`/etc., which are thin convenience wrappers around the grouping-policy management calls). The cache-wrapping enforcers (`CachedEnforcer`, `SyncedCachedEnforcer`) override only a subset of these mutators with cache-invalidation logic — and the subset is the heart of the bug class this audit targets.

## Enforce

```go
func (e *Enforcer) Enforce(rvals ...interface{}) (bool, error)
func (e *Enforcer) EnforceWithMatcher(matcher string, rvals ...interface{}) (bool, error)
func (e *Enforcer) EnforceEx(rvals ...interface{}) (bool, []string, error)
func (e *Enforcer) EnforceExWithMatcher(matcher string, rvals ...interface{}) (bool, []string, error)
func (e *Enforcer) BatchEnforce(requests [][]interface{}) ([]bool, error)
```

- `Enforce` is the standard call. Returns `(true, nil)` only when the effect expression evaluates to Allow.
- `EnforceWithMatcher` allows passing a custom matcher string at call time, overriding the model's `[matchers]`. This is useful for ad-hoc queries but bypasses any caching that depends on the matcher being stable.
- `EnforceEx` additionally returns the matched rule (the "explain"), enabling audit logs.
- `BatchEnforce` iterates `Enforce` calls; it is NOT atomic (other goroutines can mutate policy between requests).
- `Enforce(...)` is read-only with respect to the policy and role data structures BUT it writes to `e.matcherMap` (compiled-expression cache) and the `gFunctionCache`. Concurrent calls on a base `Enforcer` are safe only because `matcherMap` is a `sync.Map`; concurrent `Enforce` + policy mutation on a base `Enforcer` is **not** safe.

## Adding policy rules

```go
func (e *Enforcer) AddPolicy(params ...interface{}) (bool, error)
func (e *Enforcer) AddPolicies(rules [][]string) (bool, error)
func (e *Enforcer) AddNamedPolicy(ptype string, params ...interface{}) (bool, error)
func (e *Enforcer) AddPermissionForUser(user string, permission ...string) (bool, error)  // RBAC convenience
```

- Returns `(false, nil)` if the rule already exists (not an error — just "not affected"). Returns `(true, nil)` on a successful add.
- If `autoSave == true` (default), the change is persisted through the adapter immediately.
- If `autoNotifyWatcher == true` and a watcher is set, the watcher is notified.
- **CachedEnforcer does NOT override `AddPolicy`.** New permissions are visible to the next `Enforce` call (because the enforcer reads `model["p"][...].Policy` fresh on every call), but a previously cached `false` for the now-newly-permitted request will continue to be returned until TTL expiry. This is a smaller-impact variant of the cache-staleness bug.
- **SyncedCachedEnforcer DOES override `AddPolicy`**, calling `checkOneAndRemoveCache(params...)` first. The override deletes the key `key(params...) = "alice$$data1$$read$$"` (computed from the policy rule itself, treating its elements as request parameters). This is symmetric with `RemovePolicy` but is also a fragile assumption — see below.

## Removing policy rules

```go
func (e *Enforcer) RemovePolicy(params ...interface{}) (bool, error)
func (e *Enforcer) RemovePolicies(rules [][]string) (bool, error)
func (e *Enforcer) RemoveNamedPolicy(ptype string, params ...interface{}) (bool, error)
func (e *Enforcer) RemoveFilteredPolicy(fieldIndex int, fieldValues ...string) (bool, error)
func (e *Enforcer) DeletePermissionForUser(user string, permission ...string) (bool, error)
```

- `RemovePolicy("alice", "data1", "read")` removes the matching `p` rule. Returns `(false, nil)` if no such rule exists.
- **CachedEnforcer overrides RemovePolicy and RemovePolicies** with key-based cache deletion. Critical detail: the cache key derived from the policy rule is identical to the cache key derived from the request — both use `GetCacheKey("alice", "data1", "read") = "alice$$data1$$read$$"`. This identity is what makes the key-based invalidation work for direct ACL rules. **It does NOT work when the cached decision was reached through an RBAC indirection** — the cache key `"alice$$data1$$read$$"` was set by an Enforce call, but the policy mutation that broke the decision was `RemoveGroupingPolicy("alice", "admin")` whose key is `"alice$$admin$$"` — a key the cache never had.
- `RemoveFilteredPolicy(0, "alice")` removes ALL rules where field 0 equals "alice". **CachedEnforcer does NOT override RemoveFilteredPolicy.** Filtered removals leave stale cache entries.

## RBAC: roles and grouping policy

```go
// RBAC API (thin wrappers around grouping policy)
func (e *Enforcer) AddRoleForUser(user string, role string, domain ...string) (bool, error)
func (e *Enforcer) DeleteRoleForUser(user string, role string, domain ...string) (bool, error)
func (e *Enforcer) DeleteRolesForUser(user string, domain ...string) (bool, error)
func (e *Enforcer) DeleteUser(user string) (bool, error)
func (e *Enforcer) DeleteRole(role string) (bool, error)

// Grouping policy (lower-level)
func (e *Enforcer) AddGroupingPolicy(params ...interface{}) (bool, error)
func (e *Enforcer) RemoveGroupingPolicy(params ...interface{}) (bool, error)
func (e *Enforcer) RemoveFilteredGroupingPolicy(fieldIndex int, fieldValues ...string) (bool, error)
```

Concrete relationships (from `rbac_api.go`):

```go
func (e *Enforcer) AddRoleForUser(user, role string, domain ...string) (bool, error) {
    args := []string{user, role}
    args = append(args, domain...)
    return e.AddGroupingPolicy(args)
}
func (e *Enforcer) DeleteRoleForUser(user, role string, domain ...string) (bool, error) {
    args := []string{user, role}
    args = append(args, domain...)
    return e.RemoveGroupingPolicy(args)
}
func (e *Enforcer) DeleteRolesForUser(user string, domain ...string) (bool, error) {
    return e.RemoveFilteredGroupingPolicy(0, user)
}
func (e *Enforcer) DeleteUser(user string) (bool, error) {
    e.RemoveFilteredGroupingPolicy(0, user)
    e.RemoveFilteredPolicy(subIndex, user)
}
func (e *Enforcer) DeleteRole(role string) (bool, error) {
    e.RemoveFilteredGroupingPolicy(0, role)
    e.RemoveFilteredGroupingPolicy(1, role)
    e.RemoveFilteredPolicy(subIndex, role)
}
```

- **Neither CachedEnforcer nor SyncedCachedEnforcer override AddGroupingPolicy, RemoveGroupingPolicy, RemoveFilteredGroupingPolicy, or RemoveFilteredPolicy.** This is the CASBIN-7 root cause: the wrapper class adds key-based cache invalidation only for `p`-style mutations (which share the request keyspace), and silently does nothing for `g`-style mutations (which don't).
- After `DeleteRoleForUser("alice", "admin")`, the in-memory role-link graph IS updated — a fresh `Enforce("alice", "data1", "read")` going through the base enforcer would return `false`. But on a CachedEnforcer with a cached `true` for `"alice$$data1$$read$$"` set during alice's admin tenure, the cache hit returns `true` until the entry expires.

## LoadPolicy and cache lifecycle

```go
func (e *Enforcer) LoadPolicy() error
func (e *CachedEnforcer) LoadPolicy() error            // clears cache, then loads
func (e *CachedEnforcer) InvalidateCache() error       // clears cache only
func (e *CachedEnforcer) ClearPolicy()                 // clears cache + clears policy
func (e *CachedEnforcer) EnableCache(enableCache bool) // toggles cache use
func (e *CachedEnforcer) SetExpireTime(expireTime time.Duration)
func (e *CachedEnforcer) SetCache(c cache.Cache)
```

- `LoadPolicy` on the base enforcer reloads from the adapter, replacing the in-memory policy and rebuilding role links. It is the canonical "I changed things externally, please refresh" hook.
- **CachedEnforcer.LoadPolicy clears the entire cache before loading.** This is the only universally-correct invalidation path: any application that calls `LoadPolicy` after any mutation gets a clean cache. Applications that DON'T call `LoadPolicy` (because the mutation went through the in-process API) rely on the per-mutator overrides to handle invalidation — and those overrides only cover the `p`-style cases.
- `InvalidateCache` is the explicit escape hatch: callers that know they made a mutation Casbin can't invalidate (e.g., a `DeleteRoleForUser`) can call `e.InvalidateCache()` themselves. This is the documented workaround for the bug class — but it requires the caller to know about it.
- Cache TTL: if `e.expireTime > 0`, entries expire after that duration. If `expireTime == 0` (the default — never explicitly set), `time.Duration(-1)` is passed to `Set`, and `DefaultCache.Get` checks `if res.ttl > 0` — so entries with `ttl <= 0` never expire. **A CachedEnforcer that has not been configured with SetExpireTime will hold stale entries indefinitely** until `InvalidateCache`, `LoadPolicy`, `ClearPolicy`, or a key-based delete clears them.

## Watcher and Dispatcher (cross-process consistency)

```go
func (e *Enforcer) SetWatcher(watcher persist.Watcher) error
```

- A Watcher is meant for cross-process coordination: when node A modifies the policy, it notifies the Watcher, and on node B the Watcher fires a callback that calls `e.LoadPolicy()`.
- **On CachedEnforcer with a Watcher attached, the watcher callback calls Enforcer.LoadPolicy (the embedded base), NOT CachedEnforcer.LoadPolicy.** The default `SetWatcher` callback is `func(string) { _ = e.LoadPolicy() }` and `e` here is the base Enforcer pointer captured during `SetWatcher`. This means the cache is NOT cleared on cross-process policy changes via Watcher unless the application supplies a custom `SetUpdateCallback` that calls the cached wrapper. (This is a separate cache-staleness path from CASBIN-7, but in the same class.)

## API Contract Invariants

- A successful `RemovePolicy(sub, obj, act)` MUST cause subsequent `Enforce(sub, obj, act)` to return `false` (assuming no other rule grants the same permission).
- A successful `DeleteRoleForUser(user, role)` MUST cause subsequent `Enforce(user, X, Y)` calls — for any permission X/Y that the user only had through `role` — to return `false`.
- A successful `AddPolicy(sub, obj, act)` MUST cause subsequent `Enforce(sub, obj, act)` to return `true` (assuming the matcher accepts the rule, the effect doesn't deny, and the enforcer is enabled).
- A successful `AddRoleForUser(user, role)` MUST cause subsequent `Enforce(user, X, Y)` calls — for any permission X/Y that `role` carries — to return `true`.
- `LoadPolicy` MUST replace the entire in-memory policy with the adapter's current contents. Stale role links MUST be cleared and rebuilt.
- `InvalidateCache` MUST remove all cached decisions, so the next `Enforce` for any tuple re-evaluates against the live policy.
- `EnableEnforce(false)` MUST cause all subsequent `Enforce` calls to return `true` (kill-switch / monitor mode). When toggled back to `true`, the closed-by-default semantics resume.
