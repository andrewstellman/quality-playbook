# Casbin Issue Tracker — Recurring Themes

## Sources

- Issue list: https://github.com/casbin/casbin/issues (current home: https://github.com/apache/casbin/issues — 46 open at collection time)
- Referenced issues from the audit brief: https://github.com/casbin/casbin/issues/832 and https://github.com/casbin/casbin/issues/1202
- Source files relevant to recurring themes (`enforcer_cached.go`, `rbac_api.go`, `management_api.go`, `enforcer.go`)
- Pull requests page: https://github.com/casbin/casbin/pulls (27 open at collection time)
- Discussions: https://github.com/casbin/casbin/discussions

## Context

The full GitHub issue bodies and comment threads could not be programmatically extracted during this collection — GitHub's HTML pages render JS-side and the available web-fetch path returns empty bodies. The themes below are derived from (a) the audit brief's explicit pointer to #832 and #1202 as cache-invalidation discussion threads, (b) the structure of the source code (which mutator methods are overridden in the cache wrappers and which are not), (c) the structure of the test suite (which paths are tested and which are not), and (d) the inherent surface area of Casbin (policy mutation × cache × role inheritance × cross-process consistency). The themes are presented as the kinds of issues that recur on this tracker; each is grounded in code that QPB can read independently.

## Theme 1 — Cache staleness after RBAC mutations (CASBIN-7 family)

**Symptom users report:** "I called `DeleteRoleForUser(alice, admin)` but `Enforce(alice, data1, read)` still returns true."

**Root cause:** `CachedEnforcer` does not override `RemoveGroupingPolicy`, `DeleteRoleForUser`, or any of the filtered-policy methods. Cached decisions that resolved through a role link remain hot until TTL or explicit `InvalidateCache`. See `03_caching_behavior.md` for the full enumeration.

**Workarounds maintainers typically recommend:**

- Call `e.InvalidateCache()` after any grouping-policy mutation.
- Set `e.SetExpireTime(short_ttl)` to bound the staleness window.
- Use `LoadPolicy()` after mutations (clears the cache).
- Don't use `CachedEnforcer` with RBAC if you need immediate revocation.

**Related issues called out in the brief:** #832 and #1202.

## Theme 2 — RBAC consistency: role inheritance, max-hierarchy-level, cycles

**Symptom users report:** "Why doesn't `g, alice, admin; g, admin, root` give alice root permissions?" or "Why does adding `g, alice, manager; g, manager, alice` not error?"

**Root cause:** The default role manager has `maxHierarchyLevel = 10`. Lookups beyond 10 hops return `false`. Cycles are not validated at insert time; lookups terminate at the depth limit. Multi-domain RBAC (`g, alice, admin, tenant1`) requires the role manager to be a domain-aware variant; mixing domain-aware and non-domain-aware `g` lookups produces silent mismatches.

**Workarounds:**

- Use `NewRoleManager(20)` (or higher) for deeper hierarchies.
- Run `e.RunDetections()` to catch role-link anomalies (Casbin has a `detector` package for this).
- Be explicit about whether your model uses `g = _, _` or `g = _, _, _`.

## Theme 3 — Performance / matcher cost on large policies

**Symptom users report:** "Enforce is O(N) over policy size, my policy has 100K rules, it's too slow." or "Memory grows unbounded after many Enforce calls."

**Root causes:**

- `Enforce` is a linear scan over `e.model["p"]["p"].Policy`. There is no index. For 100K rules this is 100K matcher evaluations per `Enforce`.
- `e.matcherMap` caches compiled expressions by string identity. Custom matchers via `EnforceWithMatcher` with high-cardinality input strings grow the map without bound.
- `gFunctionCache` (per-Enforce-evaluation memoization of `g(...)`) grows with the number of distinct (user, role) pairs queried within a single matcher expression. When inputs are high-cardinality (UUIDs, dynamic paths), the comment in `enforcer.go` explicitly recommends `EnableGFunctionCache(false)` to prevent unbounded memory growth.

**Workarounds:**

- Use `BatchEnforce` for amortization.
- Use a database adapter with `LoadFilteredPolicy` to load only relevant rules.
- Use the priority model with rule ordering so early matches short-circuit.

## Theme 4 — Watcher and cross-node consistency

**Symptom users report:** "I updated policy on node A, node B still uses old policy" or "After a watcher reload, my CachedEnforcer returns stale results."

**Root causes:**

- The Watcher callback default is `func(string) { _ = e.LoadPolicy() }` where `e` is the base Enforcer pointer captured at `SetWatcher` time. On a `CachedEnforcer`, this calls the embedded base's `LoadPolicy`, which reloads the policy but does NOT clear the wrapper's decision cache. So node B's RBAC mutations from node A propagate the policy correctly, but cached decisions from before the propagation remain in node B's cache.
- Watchers are eventually-consistent. Users sometimes expect "after my mutation returns, every node sees it" — this is not how Watchers work; the receiving node only reloads on the next watcher event.

**Workarounds:**

- Replace the default callback with one that calls the cache-aware `LoadPolicy` of the wrapping enforcer.
- Use `DistributedEnforcer` (with a Dispatcher) for synchronous distributed consensus, at the cost of latency.

## Theme 5 — Adapter semantics and persistence ordering

**Symptom users report:** "AddPolicy returned true but my database doesn't have the row" or "My adapter's LoadPolicy is called multiple times during startup."

**Root causes:**

- `autoSave = true` by default; mutations are persisted through the adapter inline with the in-memory mutation. If the adapter errors mid-write, the in-memory state may already reflect the change. Recovery requires the application to call `LoadPolicy` to resync.
- `InitWithModelAndAdapter` calls `LoadPolicy` at construction (unless the adapter is a `FilteredAdapter` already filtered). This means a fresh `NewEnforcer` does one full load; if the adapter is slow, construction is slow.

**Workarounds:**

- Wrap mutations in a transaction at the application level.
- Use `EnableAutoSave(false)` and call `SavePolicy()` explicitly for batched writes.
- Use `LoadFilteredPolicy` for large policies where only a subset is needed per process.

## Theme 6 — Model authoring and matcher debugging

**Symptom users report:** "My matcher returns false for inputs I expected to match" or "I get `No parameter 'r_sub'` errors."

**Root causes:**

- Matcher token names are derived from `[request_definition]` and `[policy_definition]` — `r = sub, obj, act` makes `r.sub`, `r.obj`, `r.act` available, while `r = user, resource, action` would make `r.user`, etc. Mismatches between the request_definition and the matcher token names produce parse-time errors.
- The matcher is `govaluate` syntax, which is C-like but not Go. Things like `==`, `&&`, `||` work; `:=`, `func` do not.
- ABAC requires the request arguments to be structs or maps. Passing strings for ABAC requests with field access produces runtime errors.
- The `eval(...)` function lets policy rules embed sub-expressions; misformatted sub-expressions panic during `Enforce` (caught by the recover()).

**Workarounds:**

- Use `casbin.org/editor/` to validate models.
- Use `EnforceEx` to see which rule was matched (or that none was).
- Enable logging via `SetLogger(...)` to trace evaluation.

## What QPB can extract from these themes

The themes most relevant to the security audit are Themes 1 and 4. Theme 1 is the direct CASBIN-7 finding. Theme 4 is a structurally identical bug pattern (cache not invalidated on a state-change signal) in a different code path. Both are detectable from source-code structure alone:

- Theme 1: "the wrapper does not override mutation method X that affects the state Y the cache depends on."
- Theme 4: "the watcher callback captures the wrong receiver pointer, so cache invalidation does not happen on cross-node reload."

Themes 2, 3, 5, 6 are operational / performance / usability concerns that QPB's authorization-invariant analysis is unlikely to surface as security findings — they are correctness concerns at a different level.
