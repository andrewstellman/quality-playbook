# OpenFGA Query API Contract: Check, ListObjects, ListUsers, BatchCheck

## Sources

- https://openfga.dev/api/service
- https://openfga.dev/docs/interacting/relationship-queries
- https://openfga.dev/docs/interacting/consistency
- https://openfga.dev/docs/interacting/contextual-tuples
- https://github.com/openfga/api (proto definitions)
- https://github.com/openfga/openfga/blob/main/pkg/server/commands/check.go
- https://github.com/openfga/openfga/blob/main/pkg/server/commands/list_objects.go
- https://github.com/openfga/openfga/blob/main/pkg/server/commands/list_users.go
- https://github.com/openfga/openfga/blob/main/pkg/server/commands/batch_check.go

## Context

The query APIs are the engine's contract with applications: they take a `store_id`, an optional `authorization_model_id`, a relationship question, optional `contextual_tuples` and `context`, and an optional `consistency` mode, and they return a relationship decision (or the set of decisions, for List/Batch variants). Each API has documented guarantees around when its result is authoritative and when it is best-effort, and each has a defined response shape. This document captures the contract precisely so that QPB can derive intended behavior — the cache-staleness bug at the center of this audit is exactly a divergence between the implemented Check fan-out inside ListObjects and the documented Check guarantees.

## Check

**Endpoint**: `POST /stores/{store_id}/check`

### Request shape (key fields)

```
{
  "tuple_key": { "user": "user:anne", "relation": "viewer", "object": "document:roadmap" },
  "context": { /* JSON object passed to CEL conditions */ },
  "contextual_tuples": { "tuple_keys": [ /* tuples evaluated for this request only */ ] },
  "authorization_model_id": "01H...",   // optional; defaults to latest in store
  "consistency": "MINIMIZE_LATENCY" | "HIGHER_CONSISTENCY"  // default MINIMIZE_LATENCY
}
```

### Response shape

```
{
  "allowed": true | false,
  "resolution": "..."   // optional; debug info about the resolution path
}
```

### Guarantees

- **Truth condition.** `allowed=true` iff the user is in the set the relation denotes for the object, under the named (or latest) authorization-model version, over the union of stored and contextual tuples.
- **Consistency.** Under `HIGHER_CONSISTENCY`, the engine bypasses the check cache and reads the primary. Under `MINIMIZE_LATENCY`, the engine may serve a cached decision and may read from a secondary.
- **Type restrictions.** Contextual tuples must be filtered by the relation's `directly_related_user_types`.
- **Conditions.** A relation gated by a condition holds only if the relationship path holds *and* the condition evaluates to `true` against the merged context.
- **Authoritative for per-object decisions.** Check is the canonical per-object decision and must be used (not ListObjects-absence) for security-critical reads.

## ListObjects (and StreamedListObjects)

**Endpoint**: `POST /stores/{store_id}/list-objects` (and `/streamed-list-objects`)

### Request shape (key fields)

```
{
  "type": "document",
  "relation": "viewer",
  "user": "user:anne",
  "context": { ... },
  "contextual_tuples": { ... },
  "authorization_model_id": "...",
  "consistency": "MINIMIZE_LATENCY" | "HIGHER_CONSISTENCY"
}
```

### Response shape

```
{ "objects": [ "document:roadmap", "document:budget", ... ] }
```

### Implementation outline

Internally, `ListObjectsQuery.evaluate` (`pkg/server/commands/list_objects.go`) does a reverse-graph traversal and fans out to internal **Checks** for candidate objects. Each fan-out Check is constructed via `NewCheckCommand(...)` with options like `WithCheckCommandLogger`, `WithCheckCommandMaxConcurrentReads`, `WithCheckDatastoreThrottler`, and — when wired correctly — `WithCheckCommandCache(q.sharedDatastoreResources, q.cacheSettings)`. The `WithCheckCommandCache` option is what makes the fan-out Checks participate in cache invalidation. Its presence/absence is the load-bearing detail behind the bug at the center of this audit (PR #2779 added it; PR #2791 reverted it).

### Guarantees and non-guarantees

- **Each returned object must satisfy Check.** An object in the result set must be one for which `Check(user, relation, object)` would return `allowed=true` under the same model and consistency mode.
- **Best-effort under deadline.** The result can be **truncated** when the request deadline is hit. The truncated set looks like a complete set to a naive caller — there is no canonical "incomplete" flag (open issue #1961).
- **Consistency mode applies.** `HIGHER_CONSISTENCY` recomputes from the primary for every fan-out Check; `MINIMIZE_LATENCY` may consult caches.
- **Per-object security decisions should use Check.** Inferring "denied" from "absent from list" is unsafe when the list was truncated.

### Why this matters for the audit

The cache-staleness bug arises specifically because the fan-out Checks inside `ListObjects.evaluate` were not wired into the cache-controller pipeline. As a result, even after a `WithCheckCommandCache` was added at the top-level Check command, ListObjects' internal Checks bypassed the same invariant — so a stale `allowed=true` cached at the per-Check layer could be served via a ListObjects path that lacked the matching invalidation hookup. PR #2779 added the missing option; PR #2791 reverted it because the cache-controller assumption it relied on was deemed too strong; that revert is the residual bug surface.

## ListUsers

**Endpoint**: `POST /stores/{store_id}/list-users`

### Request shape (key fields)

```
{
  "object": { "type": "document", "id": "roadmap" },
  "relation": "viewer",
  "user_filters": [ { "type": "user" } ],
  "context": { ... },
  "contextual_tuples": { ... },
  "authorization_model_id": "...",
  "consistency": "MINIMIZE_LATENCY" | "HIGHER_CONSISTENCY"
}
```

### Response shape

```
{
  "users": [
    { "object": { "type": "user", "id": "anne" } },
    { "userset": { "type": "group", "id": "eng", "relation": "member" } },
    { "wildcard": { "type": "user" } }
  ],
  "excluded_users": [ ... ]    // users excluded by `but not`
}
```

### Guarantees and non-guarantees

- **Inverse of ListObjects.** Returns the users (and usersets/wildcards) that have the relation on the object.
- **Same best-effort-under-deadline caveat as ListObjects.** See issue #1961.
- **`excluded_users`** materializes the `but not` subtraction: users who would have been in the set but are excluded by an exclusion branch.

## BatchCheck

**Endpoint**: `POST /stores/{store_id}/batch-check`

### Request shape (key fields)

```
{
  "checks": [
    {
      "tuple_key": { "user": "...", "relation": "...", "object": "..." },
      "context": { ... },
      "contextual_tuples": { ... },
      "correlation_id": "abc-123"
    },
    ...
  ],
  "authorization_model_id": "...",
  "consistency": "MINIMIZE_LATENCY" | "HIGHER_CONSISTENCY"
}
```

### Response shape

```
{
  "result": {
    "abc-123": { "allowed": true, "error": null },
    "def-456": { "allowed": false, "error": null },
    "ghi-789": { "allowed": false, "error": { "code": "...", "message": "..." } }
  }
}
```

### Guarantees and non-guarantees

- **Each entry is independent.** A batched Check is semantically identical to issuing the same Check on its own — including consistency-mode handling.
- **Per-item error isolation.** A failure in one Check does not cause others to fail; the failing entry returns an error in its result map.
- **Same cache invariants apply.** Because BatchCheck is multiple Checks, the same cache/invalidation rules govern each — a stale-cache bug in Check affects BatchCheck identically.

## Expand

**Endpoint**: `POST /stores/{store_id}/expand`

Returns the userset *tree* for `object#relation` without evaluating membership for a specific user. Used for introspection and debugging; not used for per-user authorization decisions in production code paths.

## Response shape invariants (across all query APIs)

- `allowed` is a strict boolean. Absence/null is not a valid response state; an internal error returns an explicit error response.
- `consistency` mode in the request governs the path the engine takes; the response does not echo back whether a cache hit occurred (it is a transparent optimization within the stated consistency mode).
- The `authorization_model_id` actually used in evaluation is the one supplied in the request, or the latest in the store if omitted.

## Security-relevant invariants

- **Check is authoritative per object.** Other APIs (ListObjects, ListUsers) are best-effort under deadline; security decisions on individual objects must use Check.
- **Consistency mode is part of the request contract.** `HIGHER_CONSISTENCY` must bypass the cache and read the primary, *both* at the top-level Check and for any internal fan-out Check (ListObjects, BatchCheck). A code path that honors the mode at the outer call but ignores it inside fan-out is a bug.
- **ListObjects fan-out Checks must respect the same cache invalidation as direct Checks.** A cache-invalidation hookup that exists for top-level Check but not for the fan-out is a divergence from the contract: a caller using ListObjects gets weaker freshness than a caller using Check for the same question. (This is the PR #2779 / PR #2791 history.)
- **Contextual tuples and condition context participate in the cache key.** Two requests differing only in contextual tuples or condition context must not collide in the cache (CVE-2024-56323).
- **Type restrictions filter contextual tuples on every path.** Including the internal `ReadUsersetTuples` used in fan-out (CVE-2025-48371).
- **A ListObjects truncation is not a denial.** Callers and the engine itself must not treat "object not in the list" as "Check would deny."
