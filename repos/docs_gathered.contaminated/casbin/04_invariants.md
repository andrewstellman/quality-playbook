# Casbin — Consolidated Invariants

## Sources

- Enforcer source: https://raw.githubusercontent.com/casbin/casbin/master/enforcer.go
- CachedEnforcer source: https://raw.githubusercontent.com/casbin/casbin/master/enforcer_cached.go
- SyncedCachedEnforcer source: https://raw.githubusercontent.com/casbin/casbin/master/enforcer_cached_synced.go
- DefaultCache: https://raw.githubusercontent.com/casbin/casbin/master/persist/cache/default-cache.go
- Management API: https://raw.githubusercontent.com/casbin/casbin/master/management_api.go
- RBAC API: https://raw.githubusercontent.com/casbin/casbin/master/rbac_api.go
- Issue tracker (referenced for cache-staleness discussion threads): https://github.com/casbin/casbin/issues/832 and https://github.com/casbin/casbin/issues/1202

## Context

This document distills the contracts from the prior files into a flat checklist of "X MUST always..." and "X MUST never..." statements. These are the invariants that a static analyzer or a re-derivation pass (such as QPB's targeted analysis) should expect every released version of Casbin to uphold. Some of the invariants below are upheld; some are violated by the current implementation. Each invariant is annotated with the affected types and an UPHELD / VIOLATED tag for the v3 codebase examined.

## Core enforcement invariants

- **MUST.** `Enforce(...)` MUST return `(true, nil)` if and only if (a) `e.enabled == true`, AND (b) the effect expression evaluates to Allow over the per-rule matcher results. — UPHELD by `enforcer.go`.
- **MUST.** Closed-by-default: a request with no matching allow rule MUST yield `false`. — UPHELD: an empty `policyEffects` set produces `Indeterminate`, which maps to `false`.
- **MUST.** Deny rules in deny-override models MUST overrule allow rules. — UPHELD by the effector when `[policy_effect]` is `e = some(where (p.eft == allow)) && !some(where (p.eft == deny))`.
- **MUST.** `EnforceEx` MUST agree with `Enforce` on the boolean verdict for the same request. — UPHELD: both call `e.enforce(...)` and only `EnforceEx` additionally fills the explain slot.
- **MUST.** `EnableEnforce(false)` MUST make every subsequent `Enforce` call return `true` until re-enabled. — UPHELD: short-circuit at the top of `enforce(...)`.
- **MUST NEVER.** `Enforce` MUST NOT panic on unexpected input. — UPHELD via `defer recover()` in `enforce(...)`, which converts panics to errors. (See `enforcer.go` lines containing `defer func() { if r := recover() ... }`.)

## Policy mutation visibility (base Enforcer)

- **MUST.** After a successful `AddPolicy(sub, obj, act)`, a subsequent `Enforce(sub, obj, act)` MUST return `true` (assuming no overriding deny rule and `enabled == true`). — UPHELD by base `Enforcer`. VIOLATED by `CachedEnforcer` when a previous cached `false` is still hot (smaller-impact cache-staleness variant).
- **MUST.** After a successful `RemovePolicy(sub, obj, act)`, a subsequent `Enforce(sub, obj, act)` MUST return `false` (assuming no other allow rule grants the same permission). — UPHELD by base `Enforcer` AND by `CachedEnforcer` (which deletes the matching key). UPHELD by `SyncedCachedEnforcer`.
- **MUST.** After a successful `AddRoleForUser(user, role)`, `Enforce(user, X, Y)` for any permission X/Y that `role` carries MUST return `true`. — UPHELD by base `Enforcer` (role manager is updated synchronously). VIOLATED by `CachedEnforcer` and `SyncedCachedEnforcer` if a previous cached `false` is still hot — neither wrapper invalidates the cache on grouping-policy adds.
- **MUST.** After a successful `DeleteRoleForUser(user, role)`, `Enforce(user, X, Y)` for any permission X/Y that the user only had through `role` MUST return `false`. — UPHELD by base `Enforcer`. **VIOLATED by `CachedEnforcer` and `SyncedCachedEnforcer`.** This is the CASBIN-7 finding. The wrappers do not override `RemoveGroupingPolicy`; cached `true` decisions persist until TTL or explicit `InvalidateCache`.
- **MUST.** After `DeleteUser(user)`, all `Enforce(user, ...)` calls MUST return `false`. — UPHELD by base `Enforcer`. **VIOLATED by `CachedEnforcer` / `SyncedCachedEnforcer`**: `DeleteUser` calls `RemoveFilteredGroupingPolicy(0, user)` and `RemoveFilteredPolicy(subIndex, user)`, neither of which is overridden in either cache wrapper.
- **MUST.** After `DeleteRole(role)`, all `Enforce(user, X, Y)` calls where the user-→permission chain went through `role` MUST return `false`. — UPHELD by base `Enforcer`. **VIOLATED by both cache wrappers** for the same reason.

## Cache consistency invariants

- **MUST.** For any cached decision `CachedEnforcer.Enforce(req) → v`, `v` MUST equal what a freshly-evaluated `Enforcer.Enforce(req)` on the same underlying state would return. — VIOLATED in the cases enumerated above. This is the single overarching invariant the bug class breaks.
- **MUST.** `LoadPolicy` on a cached enforcer MUST clear the cache before reloading. — UPHELD by `CachedEnforcer.LoadPolicy` and `SyncedCachedEnforcer.LoadPolicy`.
- **MUST.** `InvalidateCache` MUST delete every cached entry such that the next `Enforce` for any tuple re-runs the matcher. — UPHELD.
- **MUST.** `ClearPolicy` on a cached enforcer MUST clear both the policy and the cache. — UPHELD.
- **MUST.** The default TTL behavior MUST be either (a) clearly documented as "never expires" or (b) a sensible non-zero default. — VIOLATED: the default is `expireTime == 0`, which `DefaultCache` interprets as "never expires," and the README/docs do not warn that a default-configured `CachedEnforcer` will hold stale entries indefinitely after an un-invalidated mutation.
- **MUST.** If `EnableCache(false)` is called, subsequent `Enforce` calls MUST bypass the cache (not just skip stores). — UPHELD: the `Enforce` method's first branch is `if enableCache == 0 { return Enforcer.Enforce(...) }`.
- **MUST NEVER.** A `CachedEnforcer` configured with `EnableCache(true)` and `expireTime == 0` and used with grouping-policy mutations through any code path other than `LoadPolicy` / `ClearPolicy` / `InvalidateCache` MUST NOT return a stale `true` decision after a revocation. — **VIOLATED.** This is the operational form of CASBIN-7.
- **MUST.** Watcher callbacks on `CachedEnforcer` MUST clear the wrapper's cache, not just reload the base enforcer's policy. — VIOLATED by the default `SetWatcher` callback: it captures the base `Enforcer` pointer and calls its `LoadPolicy`, leaving the wrapper's cache untouched on cross-process notifications.

## Threading and consistency invariants

- **MUST.** `SyncedEnforcer` MUST serialize concurrent writes against reads. — UPHELD via `sync.RWMutex` taken in every wrapper method.
- **MUST.** Concurrent `Enforce` calls on a base `Enforcer` MUST be safe iff no concurrent mutation runs. — UPHELD because `Enforce`'s only writes are to `e.matcherMap` (`sync.Map`) and the policy-rule slice is only read.
- **MUST NEVER.** A `SyncedEnforcer` mutation MUST NOT leave the role-link graph in a partial state visible to a concurrent reader. — UPHELD via write-lock around mutator wrappers.
- **MUST.** The `gFunctionCache` (per-enforcer `g(...)` memoization) MUST be invalidated when grouping policies change. — Behavior depends on adapter path: `SetRoleManager` calls `invalidateMatcherMap`, and `BuildRoleLinks` / `BuildIncrementalRoleLinks` invalidate the matcher map. But the `gFunctionCache` itself is regenerated on every `Enforce` call via `util.GenerateGFunction`, so the cache is per-evaluation, not persistent. — UPHELD.

## API contract invariants

- **MUST.** `AddPolicy(...)` returning `(false, nil)` MUST indicate the rule already existed (idempotent no-op). It MUST NOT be confused with an error. — UPHELD.
- **MUST.** `RemovePolicy(...)` returning `(false, nil)` MUST indicate the rule did not exist. It MUST NOT cause a side effect. — UPHELD.
- **MUST.** Auto-notify-watcher MUST fire exactly once per successful mutation when `e.autoNotifyWatcher == true` and a watcher is attached. — UPHELD via the internal `addPolicy` / `removePolicy` paths.
- **MUST.** `BatchEnforce` MUST process requests in order and MUST NOT lock across the batch. — UPHELD: the method is a simple loop over `Enforce` calls; concurrent mutations between requests are allowed (and visible).

## Defaults and configuration invariants

- **MUST.** `NewEnforcer` MUST initialize `autoSave = true`, `autoBuildRoleLinks = true`, `autoNotifyWatcher = true`, `enabled = true`. — UPHELD in `initialize()`.
- **MUST.** `NewCachedEnforcer` MUST initialize `enableCache = 1`. — UPHELD.
- **MUST NEVER.** A newly-created `CachedEnforcer` with no explicit `SetExpireTime` call MUST NOT silently default to infinite TTL without surfacing this as a documented gotcha. — VIOLATED in documentation. (Code behavior is documented inline but not in the README or `casbin.org/docs`.)
- **MUST NEVER.** A non-string request argument MUST NOT be cached (would produce a non-deterministic key). — UPHELD: `GetCacheKey` returns `("", false)` for non-string args, and `Enforce` falls through to the uncached path.

## Documentation invariants

- **MUST.** Any caching wrapper's public docs MUST enumerate which mutations invalidate the cache and which do not. — VIOLATED: the README and `casbin.org/docs/cached-enforcer` describe `CachedEnforcer` as caching `Enforce` calls and mention that `RemovePolicy` invalidates "the corresponding cache item," but do not warn that `DeleteRoleForUser` / `RemoveGroupingPolicy` do NOT invalidate.
- **MUST.** Any caching wrapper's public docs MUST surface the default TTL behavior. — VIOLATED: no explicit warning that the default `expireTime == 0` means "never expires."
