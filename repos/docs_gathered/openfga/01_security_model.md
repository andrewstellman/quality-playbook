# OpenFGA Security Model: Allow vs Deny, Consistency Guarantees, and Non-Guarantees

## Sources

- https://openfga.dev/docs/concepts
- https://openfga.dev/docs/configuration-language
- https://openfga.dev/docs/modeling/building-blocks/usersets
- https://openfga.dev/docs/modeling/parent-child
- https://openfga.dev/docs/modeling/conditions
- https://openfga.dev/docs/interacting/contextual-tuples
- https://openfga.dev/docs/interacting/consistency
- https://openfga.dev/blog/query-consistency-options-announcement
- https://research.google/pubs/pub48190/
- https://deepwiki.com/openfga/language/1.1-core-concepts

## Context

OpenFGA's security model is the set semantics defined by an **authorization model** evaluated over a store of **relationship tuples** plus any **contextual tuples** provided at query time. A Check is `allowed=true` iff the requested user is in the set the requested relation denotes for the requested object, computed under the model's rewrite rules. There is no separate "deny" rule list — denials are simply the absence of membership. This matters: revocation is "delete the granting tuple," not "add a deny tuple." A bug that fails to honor a deletion (e.g., a stale cache) re-grants access by inaction.

## Allow vs Deny semantics

- **Allow = set membership under the rewrite.** `Check(store, model, U, R, O)` returns `true` iff, evaluating the rewrite for relation `R` on object `O` over the union of stored and contextual tuples, `U` is in the resulting set.
- **Deny = absence of membership.** There is no explicit deny primitive. The negative side of `but not` (exclusion) is the only construct that *subtracts* users from a set; it is not a deny rule in the RBAC sense, it is set difference.
- **Conditions can only restrict.** A CEL condition gates an already-granted relationship — it can remove access the rewrite would have granted, but it can never grant access the rewrite did not already grant. A failing/erroring condition must fail closed for that gate.
- **Type restrictions gate every contributing tuple.** A relation's `directly_related_user_types` constrains which tuple shapes count toward membership. A tuple of a disallowed shape — *including a contextual tuple* — must not contribute to a positive decision.

## Rewrite operators and their set meanings

| Operator | Notation | Set meaning |
| --- | --- | --- |
| Direct | `[user]` / `this` | Membership via a stored or contextual tuple of an allowed shape. |
| Computed userset | `define viewer: editor` | Alias on the same object: every editor is a viewer. |
| Union | `or` | Set union. Adding a child path can only grant. |
| Intersection | `and` | Set intersection. All children must hold. |
| Exclusion | `but not` | Set difference. Right-hand side subtracts. |
| Tuple-to-userset | `viewer from parent` | Two-hop join: `U has (R from T) on O` iff exists `O'` with `O#T@O'` and `U has R on O'`. |

Intersection and exclusion combined with tuple-to-userset have been the engine's hardest correctness bugs (CVE-2024-31452 cyclic `and`/`but not`; CVE-2024-42473 `but not` + `from` + userset).

## Consistency modes (the explicit security knob)

OpenFGA descends from Zanzibar but exposes a simpler two-value `consistency` parameter on `Check`, `ListObjects`, and `ListUsers`:

| Mode | Behavior | Tradeoff |
| --- | --- | --- |
| `MINIMIZE_LATENCY` (default) | Use cached results when available; may read from a database **replica/secondary**. | Lowest latency; decision may reflect **stale** data. |
| `HIGHER_CONSISTENCY` | **Bypass the cache** and read from the **primary** database. | Strong consistency at higher latency / primary load. |

Rules:

- When **caching is disabled**, all queries are strongly consistent regardless of mode requested.
- When **caching is enabled**, `MINIMIZE_LATENCY` may serve a cached decision; `HIGHER_CONSISTENCY` always recomputes.
- For replica deployments: `HIGHER_CONSISTENCY` hits the primary; `MINIMIZE_LATENCY` may hit a secondary.

Intended use: `HIGHER_CONSISTENCY` for read-after-write moments (e.g., immediately after granting access) and revocation-sensitive checks; `MINIMIZE_LATENCY` for high-volume steady state where slight staleness is acceptable.

## Explicit guarantees

- **Model immutability + versioning.** A `WriteAuthorizationModel` returns a new `authorization_model_id`. Old versions remain queryable; queries pinned to an old id evaluate under that old policy.
- **Store-scoped isolation.** Every data-plane and data-management call (except store-management itself) carries a `store_id`. The storage adapter includes `store` in primary keys / predicates.
- **Strong consistency on demand.** `HIGHER_CONSISTENCY` reads the primary and bypasses the check cache, guaranteeing the decision reflects every committed write at the moment of the call.
- **Type restrictions on relations are enforced.** Stored tuples are validated against the model's `directly_related_user_types` at Write time. The engine must also honor this at evaluation time (especially for contextual tuples).
- **Conditions are gates, not grants.** A condition can only remove access the relationship graph already granted.

## Explicit non-guarantees (the staleness window)

These are documented limitations, not bugs. A reviewer must not flag them as bugs but must verify the engine never *exceeds* them:

- **`MINIMIZE_LATENCY` may return stale decisions.** A just-revoked grant may still appear granted until the cache TTL expires or the CacheController's changelog poll invalidates it. The user is expected to choose `HIGHER_CONSISTENCY` for revocation-sensitive checks.
- **Cache TTL is the upper bound on staleness, not an SLA.** `OPENFGA_CHECK_QUERY_CACHE_TTL` plus the CacheController's poll interval together bound how long a stale `allowed=true` can survive. Within that window, staleness is accepted.
- **Replica lag is not bounded by OpenFGA.** When a secondary is used under `MINIMIZE_LATENCY`, replication delay is a property of the database, not the authorization engine.
- **ListObjects results are best-effort under deadline pressure.** A deadline-truncated list looks like a complete list to the caller. Per-object security decisions should use Check (see issue #1961).
- **OpenFGA does not authenticate end users.** It answers "does `U` relate to `O` via `R`" — it trusts the caller's claim about who `U` is. Application authentication is out of scope.

## Application-side invariants OpenFGA depends on

These are part of the security model in the sense that OpenFGA's correctness assumes them:

- The application authenticates the end user before naming them in a Check.
- The application enforces the returned `allowed` decision.
- The application pins `authorization_model_id` for decisions that must be reproducible against a specific policy.
- The application uses `HIGHER_CONSISTENCY` (or disables caching) for revocation-sensitive checks.

## Threat-model anchors

| Threat | Mechanism | Mitigation in the engine |
| --- | --- | --- |
| Authorization bypass via rewrite mis-evaluation | Engine returns `allowed=true` when the set semantics deny | Faithful rewrite traversal; assertion-test coverage |
| Authorization bypass via contextual-tuple injection | Caller supplies a tuple of disallowed shape and the engine honors it | Type-restriction filter on every tuple, including contextual |
| Stale-cache over-grant after revocation | Cache returns `allowed=true` after the granting tuple was deleted | `HIGHER_CONSISTENCY`, CacheController invalidation, TTL |
| Cross-tenant leak | A query in store A reads tuples from store B | `store_id` in every query and primary key |
| Unauthenticated server access | A network caller hits a data endpoint without credentials | Preshared key / OIDC enforced on every endpoint |

## Security-relevant invariants

- **Check decision = ground-truth graph reachability under the named model.** Any divergence is a bypass (false `true` = over-grant; false `false` = over-deny).
- **`HIGHER_CONSISTENCY` must bypass the cache and read the primary.** A code path that consults the cache under `HIGHER_CONSISTENCY` violates the documented contract.
- **Cache TTL bounds staleness; the engine must not exceed it.** Cached entries older than TTL must not be served; invalidation polling intervals are part of the bound.
- **Type restrictions apply to contextual tuples.** A contextual tuple whose user shape is not in the relation's `directly_related_user_types` must not influence the decision.
- **Conditions can only restrict.** A failing condition removes access; an erroring condition fails closed for that gate; a contextual override of subject/resource/action context must not flip a decision.
- **Model immutability is load-bearing.** A decision computed under a pinned `authorization_model_id` must use exactly that model version.
