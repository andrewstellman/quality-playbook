# OpenFGA Query Evaluation, Consistency Modes, and Caching

Sources:
- https://openfga.dev/docs/interacting/consistency
- https://openfga.dev/blog/query-consistency-options-announcement
- https://openfga.dev/docs/interacting/contextual-tuples
- https://openfga.dev/docs/getting-started/setup-openfga/configure-openfga
- https://openfga.dev/docs/best-practices/running-in-production
- https://deepwiki.com/openfga/openfga/2.3-performance-optimizations
- https://docs.fga.dev/writing-data/consistency-modes

## The Query APIs and Their Evaluation Semantics

### Check
`Check(store, model, user, relation, object, context?, contextual_tuples?)` returns `{ allowed: bool }`. The engine evaluates the relation's rewrite as a graph traversal: direct tuples, computed usersets, unions/intersections/exclusions, and tuple-to-userset (`from`) hops, gating on any CEL conditions. The decision is `true` iff the user is in the set the rewrite denotes (see `openfga-authorization-model.md`).

### Expand
`Expand(store, model, relation, object)` returns the full **userset tree** for `object#relation` without resolving it to a yes/no for a specific user. It is an introspection/debugging tool — it shows *why* a relation resolves the way it does.

### ListObjects / StreamedListObjects
`ListObjects(store, model, user, relation, type, context?, contextual_tuples?)` returns the object IDs of the given type to which the user has the relation. Internally it is a fan-out of Checks / reverse-graph traversal; it is more expensive than Check and is the API most prone to latency and correctness edge cases (it can hit a deadline and return a partial list — see open issue #1961, and the ListObjects pipeline deadlock/short-circuit fixes).

### ListUsers
`ListUsers(store, model, object, relation, user_filters)` returns the users (and usersets) that have the relation on the object — the inverse direction of ListObjects.

### Contextual tuples (all query APIs)
Contextual tuples are tuples supplied in the request and evaluated as if present in the store, **for that request only**. They power request-scoped ABAC. They are subject to the model's type restrictions exactly like stored tuples; failing to filter them by type restriction caused authorization bypasses (CVE-2025-48371). Their interaction with conditions caused another (CVE-2024-56323).

## Consistency Modes (the zookie tradeoff)

OpenFGA descends from Zanzibar, whose **zookie** snapshot tokens let a caller demand "evaluate against data at least as fresh as this write." OpenFGA exposes a simpler two-value `consistency` parameter on Check and ListObjects:

| Mode | Behavior | Tradeoff |
| --- | --- | --- |
| `MINIMIZE_LATENCY` (default) | Use cached results when available; may read from a database **replica/secondary**. | Lowest latency, but a decision may reflect slightly **stale** data (a just-written grant may not yet be visible; a just-deleted grant may still appear granted). |
| `HIGHER_CONSISTENCY` | **Bypass the cache** and read directly from the **primary** database. | Strong, up-to-date decision at higher latency / load. |

Key rules:
- When **caching is disabled**, all queries have strong consistency regardless of the mode requested (there is no stale cache to read).
- When **caching is enabled**, `MINIMIZE_LATENCY` may serve a cached decision; `HIGHER_CONSISTENCY` always recomputes from the primary.
- For replica deployments: `HIGHER_CONSISTENCY` always hits the **primary**; `MINIMIZE_LATENCY` may hit a **secondary** (falling back to primary if none).

The intended use: call `HIGHER_CONSISTENCY` for the read-after-write moment (e.g. immediately after granting access and then checking it), and `MINIMIZE_LATENCY` for the high-volume steady state where slight staleness is acceptable.

## Caching

OpenFGA has an optional **check-query cache** (and partial ListObjects caching), **disabled by default**, enabled with `OPENFGA_CHECK_QUERY_CACHE_ENABLED`. Relevant configuration:

- `OPENFGA_CHECK_QUERY_CACHE_ENABLED` — turn the cache on.
- `OPENFGA_CHECK_QUERY_CACHE_TTL` — how long a cached decision lives.
- Cache controller / `CacheControllerTTL` — controls cache invalidation polling.

### Cache invalidation
Invalidation is driven by a **CacheController** that polls the store's **changelog table** at a configured interval and detects writes by looking for new changelog entries. When it sees new writes for a store, it invalidates affected cached results. This means invalidation is **eventually consistent**: between a tuple write/delete and the next changelog poll, a previously cached decision can still be served under `MINIMIZE_LATENCY`.

The cache is keyed per store and per (sub)problem; contextual tuples and request context participate in the key (the historical bug CVE-2024-56323 involved caching interacting incorrectly with contextual tuples that carried conditions).

## Security-Relevant Considerations

The consistency/caching staleness risk and the evaluation invariants:

- **A cached decision must not outlive the data it was computed from — beyond the explicitly accepted staleness window.** The core risk: a user's access is **revoked** (a `viewer` tuple is deleted), but a Check under `MINIMIZE_LATENCY` returns a **stale cached `allowed=true`** until the cache TTL expires or the CacheController's changelog poll invalidates it. For the duration of that window, a de-authorized user still passes Check -> **revocation does not take effect immediately**. Any security-critical revocation (offboarding, breach response, blocking a compromised account) must use `HIGHER_CONSISTENCY` or disable caching, otherwise the deletion is not enforced until invalidation catches up.

- **The inverse staleness also exists but is usually benign:** a newly *granted* access may not be visible under `MINIMIZE_LATENCY` until the cache/replica catches up (read-after-write). This is an availability/correctness issue, not a security one — but it drives callers to use `HIGHER_CONSISTENCY` after a grant, and getting the mode wrong on the *revoke* side is the dangerous direction.

- **Cache invalidation must be tied to writes for the correct store.** Because invalidation polls the changelog, the changelog must capture every tuple write/delete and the controller must scope invalidation per store. A write that fails to produce a changelog entry, or an invalidation that targets the wrong store, leaves stale (over-permissive) decisions cached. Cross-store invalidation confusion would also be a tenant-isolation concern.

- **Contextual tuples and conditions must be part of the cache key.** If two requests differ only in their contextual tuples or condition context but share a cache entry, one request can receive a decision computed for a different context -> wrong (possibly over-permissive) answer. CVE-2024-56323 was exactly this class: caching enabled + contextual tuples carrying conditions -> authorization bypass; fixed in v1.8.3.

- **ListObjects partial/deadline results must not be mistaken for complete denials or grants.** ListObjects can hit a timeout and return a truncated set (open issue #1961). A caller that treats "object not in the returned list" as "user is denied" can wrongly deny (or, if used to filter an allow-list, wrongly include/exclude) when the list was merely truncated. ListObjects results are best-effort under deadline pressure; security decisions on individual objects should use Check.

- **`HIGHER_CONSISTENCY` is the safe default for correctness-critical decisions.** It bypasses the cache and reads the primary, so it always reflects committed writes. The cost is latency and primary load; the benefit is that the decision matches ground truth at the instant of the call.
