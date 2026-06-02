# OpenFGA Security and Correctness Invariants

## Sources

- https://openfga.dev/docs/concepts
- https://openfga.dev/docs/configuration-language
- https://openfga.dev/docs/interacting/consistency
- https://openfga.dev/docs/interacting/contextual-tuples
- https://github.com/openfga/openfga/security/advisories
- https://github.com/openfga/openfga/pull/2779
- https://github.com/openfga/openfga/pull/2791
- https://github.com/openfga/openfga/issues
- The earlier source-of-truth docs in this folder (`00_README.md`, `01_security_model.md`, `02_api_contract.md`, `03_consistency_and_cache.md`)

## Context

This file gathers the "X must always" / "X must never" statements derived from the OpenFGA documentation, code comments, maintainer issue discussion, and published advisory history. They are written as **invariants** — statements that should hold under all correctly-configured inputs. A violation of any of these is, by definition, a bug; many of them have *been* bugs at some point in OpenFGA's history (each labeled with the CVE/PR/issue that proved it real).

The invariants are grouped by concern. Each one is phrased crisply enough that QPB can mechanically check for code that contradicts it.

---

## Decision correctness invariants

- **`Check(store, model, U, R, O)` must return `true` iff `U` is in the set the rewrite for `R` denotes on `O`.** Under the pinned (or latest) authorization-model version, over the union of stored tuples and contextual tuples. Any divergence is an authorization bypass (over-grant or over-deny). *Class:* the foundational invariant, violated by most published OpenFGA advisories.
- **Rewrite operators must implement their set semantics exactly.** `or` = union, `and` = intersection, `but not` = set difference, `from` = the two-hop tupleset→computed-relation join, computed userset = same-object alias. An operator that mis-evaluates is a bypass. *Class:* general; violated by CVE-2024-31452, CVE-2024-42473, CVE-2025-25196, CVE-2025-55213, CVE-2026-24851.
- **Exclusion (`but not`) must actually subtract.** If the negative branch is skipped or short-circuits to "match," a revoked user retains access. *Class:* CVE-2024-31452 (cyclic), CVE-2024-42473 (`but not` + `from` + userset).
- **Cyclic relationships must terminate with the correct answer.** Models that allow cycles through `and`/`but not` must not loop and must not return `true` from incompletely-explored cycles. *Class:* CVE-2024-31452.
- **Optimizations that prune evaluation must not change the set the rewrite denotes.** A "weight 2 optimization" that short-circuits when more than one userset of the same type is directly assignable is exactly the kind of optimization that has produced bypasses. *Class:* CVE-2025-55213.
- **Decisions are pinned to a model version.** A query bound to `authorization_model_id` X must evaluate under model X — never silently use a newer/different version.

## Type-restriction invariants

- **`directly_related_user_types` is a security constraint, not validation sugar.** A tuple whose user shape is not in the relation's allowed-shapes list must not contribute to a positive decision — *including* a contextual tuple supplied at query time, *including* userset and wildcard tuples. *Class:* CVE-2025-48371, CVE-2025-25196, CVE-2026-24851.
- **Contextual tuples must be filtered by type restrictions on every read path, including internal usersets.** `ReadUsersetTuples` (in `CombinedTupleReader`) must apply `allowedUserTypeRestrictions` to contextual tuples. *Class:* CVE-2025-48371, fix commit `e5960d4`.
- **Wildcards (`*`) on tupleset relations are forbidden.** A type-bound public-access tuple on the right-hand side of a `from` cannot be allowed; the engine must reject it at validation and at evaluation. *Class:* CVE-2022-39341.
- **Type-bound public access and direct usersets of the same type must not collide in evaluation.** Even when both shapes are directly assignable on the same relation, the engine must distinguish which tuples actually exist and not let one shape's presence falsely resolve a query for the other shape. *Class:* CVE-2025-25196, CVE-2026-24851.

## Condition (CEL/ABAC) invariants

- **Conditions can only restrict, never grant.** A failing condition removes access; an erroring condition fails closed for that gate. A bug that lets a condition error grant access is a bypass.
- **Condition context cannot override subject/resource/action properties.** The merge of request context with relation/tuple context must not let a free-form request field shadow an authoritative subject/resource/action property. *Class:* open issue #3063.
- **Conditions evaluate over request context + tuple-bound context only.** Conditions cannot read arbitrary store data (this is the gap discussed in issue #3088 as a feature request, not a bug).
- **A conditional tuple evaluation error must not falsely grant.** ListObjects has tolerated conditional-tuple errors once a determinate result was reached for that object; this must never flip an undecided object to "allowed." *Class:* issue #1511.

## Cache and consistency invariants

- **`HIGHER_CONSISTENCY` must bypass the cache and read the primary, on every call path.** Including internal fan-out Checks from ListObjects, ListUsers, and BatchCheck. A code path that consults a cache when the request asked for `HIGHER_CONSISTENCY` violates the documented contract.
- **A cached decision must not outlive the data it was computed from beyond the accepted staleness window.** The window is bounded by `OPENFGA_CHECK_QUERY_CACHE_TTL` (absolute) and by `OPENFGA_CACHE_CONTROLLER_TTL` (when invalidation is running). Entries older than TTL must be evicted; entries with `LastModified < LastInvalidationTime` must be invalidated. *Class:* PR #2779/#2791 history; CVE-2024-56323 family.
- **`LastInvalidationTime == zero` must not mean "all cached entries valid."** It means "no information about invalidation." Treating "no information" as "all valid" is the latent over-grant PR #2779 identified. The team's chosen trade-off post-#2791 is to accept this under the explicit documentation that callers needing freshness should use `HIGHER_CONSISTENCY`; an audit must flag this as a known-but-accepted risk window. *Class:* PR #2779/#2791.
- **Fan-out Checks inside ListObjects/ListUsers/BatchCheck must use the same cache pipeline as top-level Checks.** Specifically, `NewCheckCommand` inside `ListObjectsQuery.evaluate` must construct with `WithCheckCommandCache(...)` so fan-out participates in invalidation. *Class:* PR #2779 attempted to add this; PR #2791 reverted; the residual state is divergent — this is the OPENFGA-2 finding.
- **Cache key must include contextual tuples and condition context.** Two requests differing only in contextual data or condition input must not collide. *Class:* CVE-2024-56323.
- **The cache must be scoped per store.** `store_id` is part of the cache key; cross-store cache contamination is a tenant-isolation breach.
- **Tuple writes and deletes must always produce a changelog entry.** The CacheController polls the changelog; a Write that skips the changelog leaves the controller unable to invalidate stale entries.
- **Cache invalidation must scope to the correct store.** A controller that invalidates store A's cache on a store B write is a correctness bug; one that fails to invalidate store A on a store A write is an over-grant.

## API-shape and best-effort invariants

- **A ListObjects truncation is not a denial.** Callers (and any internal logic) must not infer "denied" from "object not in the returned list." Per-object security decisions use Check. *Class:* issue #1961.
- **A truncated ListObjects/ListUsers result should be distinguishable from a complete result.** Currently it is not, per the maintainer issue. The audit should flag any consumer code that assumes completeness.
- **A BatchCheck entry's failure must not corrupt other entries' decisions.** Per-item error isolation; one Check's error returns in its result map without affecting others.
- **Streaming variants (StreamedListObjects) carry the same authentication requirement as their non-streaming counterparts.** *Class:* CVE-2022-39340, where `streamed-list-objects` skipped auth.

## Tenant isolation invariants

- **`store_id` scopes every query and every tuple read at the storage layer, not just at the API layer.** A storage query that omits the `store` predicate is a cross-tenant leak.
- **Store-management endpoints (`ListStores`, `CreateStore`, `DeleteStore`) must be authenticated.** These are the enumeration surface; an unauthenticated `ListStores` reveals every tenant's `store_id`.
- **Every data-returning endpoint must enforce the configured server auth uniformly.** A single endpoint that skips auth bypasses the entire tenant model. *Class:* CVE-2022-39340.
- **In shared-store multi-tenant deployments, the model carries isolation.** Every resource relation must traverse the tenant link; a relation that grants access without that traversal is a cross-tenant leak. Audit warning: the engine cannot detect this; it's a modeling concern.
- **`DeleteStore` is destructive and store-wide.** It must be tightly authorized; an attacker with store-management access can erase a tenant's authorization state.

## Authentication and server-boundary invariants

- **Every data-returning and management endpoint enforces server auth (preshared key / OIDC).** Including streaming endpoints. *Class:* CVE-2022-39340 (streamed-list-objects skipped auth).
- **OIDC JWKS handling must support key rotation.** The JWKS cache must enable `RefreshUnknownKID` so tokens signed with a newly-rotated `kid` trigger a refresh rather than silent rejection or stale-key trust. *Class:* issue #3099.
- **OpenFGA does not authenticate end users.** It trusts the caller's claim. The application must authenticate before naming a `user`. *(This is an architectural invariant for integrators, not a code invariant — but it scopes what OpenFGA's "correct" answer means.)*

## Application-side invariants OpenFGA depends on

Stated here so the audit can distinguish "OpenFGA bug" from "integrator bug":

- The application authenticates the end user before passing them in a Check.
- The application enforces the returned `allowed` decision.
- The application uses `HIGHER_CONSISTENCY` (or disables caching) for revocation-sensitive checks.
- The application pins `authorization_model_id` for reproducible decisions.
- The application does not infer denial from ListObjects absence; it uses Check.

## Quick reference: "must always" / "must never" condensation

| Must always | Must never |
| --- | --- |
| Match Check decision to set semantics of rewrite | Skip type restriction on contextual tuples |
| Honor `HIGHER_CONSISTENCY` on every code path including fan-out | Treat `LastInvalidationTime.IsZero()` as "no staleness" |
| Scope `store_id` at the storage layer | Allow `*` on a tupleset relation |
| Filter contextual tuples by `directly_related_user_types` | Return a partial ListObjects as if complete (without caller awareness) |
| Authenticate every data endpoint, including streaming | Treat a condition error as "allowed" |
| Emit a changelog entry for every tuple write/delete | Use a cache entry under `HIGHER_CONSISTENCY` |
| Include `store_id`, contextual tuples, context in cache key | Share a cache entry across stores |
| Evaluate rewrites under the pinned model version | Override subject/resource/action context with request fields |
| Subtract `but not` correctly on every evaluation path | Loop forever in cyclic models with `and`/`but not` |
| Distinguish "no invalidation info" from "all cached entries valid" | Let an optimization prune a path that would have changed the answer |
