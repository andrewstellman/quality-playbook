# OpenFGA: Project Overview

## Sources

- https://github.com/openfga/openfga
- https://openfga.dev/docs/fga
- https://openfga.dev/docs/concepts
- https://openfga.dev/docs/authorization-concepts
- https://auth0.com/blog/auth0s-openfga-open-source-fine-grained-authorization-system/
- https://research.google/pubs/pub48190/ (Zanzibar: Google's Consistent, Global Authorization System)
- https://github.com/cncf/tag-security/issues/902

## Context

OpenFGA ("Fine-Grained Authorization") is an open-source, high-performance authorization/permission engine inspired by Google's **Zanzibar** paper. It was created by Auth0/Okta, donated to the **CNCF** in September 2022, and is now a CNCF **Incubation** project. The hosted commercial variant is "Okta FGA" / "Auth0 FGA" (formerly Auth0 Fine-Grained Authorization), built on the same engine.

OpenFGA implements **Relationship-Based Access Control (ReBAC)** as its primary paradigm and can also express **RBAC** and **ABAC** use-cases. The central idea from Zanzibar: authorization is modeled as a graph of **relationship tuples** ("user U has relation R on object O"), and an authorization decision is a graph-reachability query over those tuples constrained by a declarative **authorization model**.

The core decision answered by OpenFGA is: *"Does user `U` have relation `R` to object `O`?"* — returned by the `Check` API as a boolean `allowed`.

- **Language**: Go (the server, which is the code under audit) plus per-language SDKs (JS/TS, Go, Python, Java, .NET).
- **Storage adapters**: Postgres, MySQL, SQLite, in-memory.
- **APIs**: gRPC + HTTP/JSON gateway.
- **Domain**: centralized policy-decision-point for ReBAC/RBAC/ABAC.

## Key Terminology

| Term | Meaning |
| --- | --- |
| **Store** | Top-level container. Holds tuples, authorization-model versions, assertions, and a changelog. The isolation boundary — every data-plane and data-management call carries a `store_id`. Two stores are as isolated as two separate databases. |
| **Authorization model** | Immutable, versioned declaration of types and relations. Each `WriteAuthorizationModel` creates a new `authorization_model_id`; older versions remain queryable. Schema version `1.1` introduced explicit type restrictions and conditions. |
| **Tuple** (relationship tuple) | The unit of stored authorization data: `(store_id, object, relation, user, condition?)`. Written `object#relation@user` (e.g., `document:roadmap#viewer@user:anne`). |
| **Relation** | A named edge type on an object type. Each relation has a **rewrite** (the set definition) and a set of **directly related user types** (type restrictions). |
| **Type** | An object type declared in the model (e.g., `user`, `document`, `folder`, `organization`). |
| **Userset** | A set of users defined indirectly by an `object#relation` pair (e.g., `group:eng#member` = "all members of group:eng"). Used as the `user` field of a tuple to grant a relation to an entire set. |
| **Type-bound public access (wildcard)** | The token `type:*` (e.g., `user:*`) representing "every user of this type." Allowed on ordinary relations; forbidden on tupleset relations since CVE-2022-39341. |
| **Contextual tuple** | A tuple supplied at query time (Check/ListObjects) that is *not* persisted and applies only to that one request. Used for request-scoped ABAC. Must be filtered by the model's type restrictions like any stored tuple. |
| **Condition** | A named CEL (Common Expression Language) expression attached to a relation/tuple, evaluated against request context to gate a relationship (ABAC). Can only restrict access, never grant it. |
| **Changelog** | Per-store log of tuple writes/deletes. Drives `ReadChanges` and cache invalidation (the `CacheController` polls the changelog). |
| **Rewrite** | The declarative definition of a relation: `this` (direct), computed userset (alias), union (`or`), intersection (`and`), exclusion (`but not`), or tuple-to-userset (`X from Y`). |
| **Tupleset** | In `X from Y`, the relation `Y` whose tuples produce the intermediate objects. The wildcard footgun lived here (CVE-2022-39341). |

## Query and Management APIs

### Query APIs

| API | Question | Returns |
| --- | --- | --- |
| **Check** | Does user `U` have relation `R` on object `O`? | `{ allowed: bool, resolution? }` |
| **BatchCheck** | Multiple Check questions in one request. | `{ result: map<correlation_id, CheckResult> }` |
| **Expand** | Full userset tree for `object#relation`. | tree (introspection/debugging) |
| **ListObjects** / **StreamedListObjects** | Which objects of type `T` does user `U` have relation `R` to? | list of object IDs (best-effort under deadline) |
| **ListUsers** | Which users have relation `R` on object `O`? | list of users/usersets |

### Management APIs

| API | Purpose |
| --- | --- |
| **Write** | Add or delete relationship tuples (writes and deletes in one transaction). |
| **Read** | Query stored tuples matching a filter. |
| **ReadChanges** | Read the changelog of tuple writes/deletes. |
| **WriteAuthorizationModel** | Create a new immutable model version. |
| **ReadAuthorizationModel(s)** | Fetch a model version (or the latest). |
| **CreateStore / GetStore / ListStores / DeleteStore** | Store management. |
| **WriteAssertions / ReadAssertions** | Persist test assertions. |

## Architecture (engine internals relevant to this audit)

```
+----------------------------------------------------------+
|                     Application                           |
|  (asks: can user U do R on object O?  -> Check(...))      |
+---------------------------+------------------------------+
                            |  gRPC / HTTP (+ store_id, model_id)
                +-----------v------------+
                |      OpenFGA server     |
                |  +-------------------+  |
                |  |  API layer        |  |  auth (preshared key / OIDC)
                |  +---------+---------+  |
                |  +---------v---------+  |
                |  |  Command layer    |  |  Check / ListObjects / ListUsers
                |  |  (pkg/server/...) |  |  ListObjects fan-out -> Check
                |  +---------+---------+  |
                |  +---------v---------+  |
                |  |  Graph engine /   |  |  Rewrite traversal, CEL eval
                |  |  CachedCheckRslvr |  |  consults check-query cache
                |  +---------+---------+  |
                |  +---------v---------+  |
                |  |  CacheController  |  |  polls changelog,
                |  |  + check cache    |  |  determines invalidation time
                |  +---------+---------+  |
                |  +---------v---------+  |
                |  |  Storage adapter  |  |  Postgres / MySQL / SQLite /
                |  |                   |  |  memory; primary + replicas
                |  +-------------------+  |
                +-------------------------+
```

Key engine source locations (Go):

- `internal/graph/cached_resolver.go` — `CachedCheckResolver.ResolveCheck`, the consult-the-cache hot path.
- `internal/cachecontroller/cache_controller.go` — `CacheController` and `NoopCacheController`, owners of `DetermineInvalidationTime`.
- `pkg/server/commands/list_objects.go` — `ListObjectsQuery.evaluate`, the fan-out that issues internal Checks.
- `pkg/server/commands/check.go` — top-level Check command with `WithCheckCommandCache` wiring.

## Trust Boundaries (for the auditor)

1. **Caller -> OpenFGA API.** OpenFGA is the policy decision point. The application is trusted to (a) authenticate the end user, (b) pass the correct `user`, `object`, `relation`, `store_id`, and (c) enforce the returned decision. OpenFGA does not authenticate the end user.
2. **API -> store.** `store_id` is the tenant boundary. Every query and tuple read must be scoped to the named store; the storage adapter must include `store` in its predicates.
3. **API authentication.** Server modes: **no auth**, **preshared key**, or **OIDC/JWT**. A misconfigured server exposes every store.
4. **Model -> tuples.** The model's `directly_related_user_types` is a security constraint on which tuples (including contextual tuples) may contribute to a positive decision.

## Project Status (as of mid-2026)

- CNCF Incubation; active development; multi-year history of published advisories (see `05_known_issues_and_advisories.md`).
- Stable engine; most recent published advisory class targets *combinations* of rewrite operators rather than individual primitives.
- Active correctness surfaces in 2025-2026: cache invalidation correctness (this audit's focus), condition/context merging, ListObjects under deadline, performance optimizations that prune evaluation.
