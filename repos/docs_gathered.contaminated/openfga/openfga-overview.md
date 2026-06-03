# OpenFGA Overview: Zanzibar-Style Fine-Grained Authorization

Sources:
- https://openfga.dev/docs/fga
- https://openfga.dev/docs/concepts
- https://openfga.dev/docs/authorization-concepts
- https://github.com/openfga/openfga
- https://auth0.com/blog/auth0s-openfga-open-source-fine-grained-authorization-system/
- https://research.google/pubs/pub48190/ (Zanzibar: Google's Consistent, Global Authorization System)
- https://github.com/cncf/tag-security/issues/902

## What OpenFGA Is

OpenFGA (Fine-Grained Authorization) is an open-source, high-performance authorization/permission engine inspired by Google's **Zanzibar** paper. It was created by Auth0/Okta, donated to the **Cloud Native Computing Foundation (CNCF)** in September 2022, and is currently a CNCF **Incubation** project. The hosted commercial variant is "Okta FGA" / "Auth0 FGA" (formerly Auth0 Fine-Grained Authorization at `docs.fga.dev`), built on the same engine.

OpenFGA implements **Relationship-Based Access Control (ReBAC)** as its primary paradigm and can also express **RBAC** and **ABAC** use-cases. The central idea from Zanzibar: authorization is modeled as a graph of **relationship tuples** ("user U has relation R on object O"), and an authorization decision is a graph-reachability query over those tuples constrained by a declarative **authorization model**.

The core decision answered by OpenFGA is: *"Does user `U` have relation `R` to object `O`?"* — returned by the `Check` API as a boolean `allowed`.

## Zanzibar Lineage

OpenFGA adopts the key Zanzibar concepts:

- **Relationship tuples** — the unit of stored authorization data, written `object#relation@user` (e.g. `document:roadmap#viewer@user:anne`).
- **Usersets** — a set of users defined indirectly, written `object#relation` (e.g. `group:eng#member` denotes "all members of group:eng"). Used as the `user` field of a tuple to grant a relation to an entire set.
- **Namespace / type configuration** — Zanzibar's namespace config becomes OpenFGA's **authorization model**, declaring object types and the rewrite rules for each relation.
- **Userset rewrites** — union, intersection, exclusion, `this` (direct), computed userset, and **tuple-to-userset** (the `X from Y` traversal). These are the semantic core.
- **Consistency tokens (zookies)** — Zanzibar's snapshot tokens become OpenFGA's **consistency modes** (`MINIMIZE_LATENCY` vs `HIGHER_CONSISTENCY`), trading staleness for latency.

OpenFGA does *not* implement Zanzibar's full Spanner-backed external-consistency / zookie-per-write machinery; it offers a simpler two-mode consistency knob layered over a relational store (Postgres, MySQL, SQLite) or in-memory store.

## Core Components and APIs

### Data-plane (query) APIs

| API | Question answered | Returns |
| --- | --- | --- |
| **Check** | Does user `U` have relation `R` on object `O`? | `{ allowed: bool }` |
| **Expand** | What is the full userset tree for `object#relation`? | tree of usersets (debugging / introspection) |
| **ListObjects** | Which objects of type `T` does user `U` have relation `R` to? | list of object IDs |
| **StreamedListObjects** | Streaming variant of ListObjects | stream of object IDs |
| **ListUsers** | Which users have relation `R` on object `O`? | list of users/usersets |

### Data-management APIs

| API | Purpose |
| --- | --- |
| **Write** | Add or delete relationship tuples (writes and deletes in one transaction) |
| **Read** | Query stored tuples matching a filter |
| **ReadChanges** | Read the changelog (tuple write/delete history) — used by cache invalidation |
| **WriteAuthorizationModel** | Create a new immutable authorization-model version in a store |
| **ReadAuthorizationModel(s)** | Fetch a model version (or the latest) |
| **CreateStore / GetStore / ListStores / DeleteStore** | Manage stores (the tenant/isolation boundary) |
| **WriteAssertions / ReadAssertions** | Store test assertions against a model |

### Key data structures

- **Store** — the top-level isolation container. Holds tuples, authorization-model versions, assertions, and a changelog. Every data-plane and data-management call is scoped to a `store_id`. (See `openfga-stores-and-multitenancy.md`.)
- **Authorization model** — an immutable, versioned declaration of types and relations. Each `WriteAuthorizationModel` produces a new `authorization_model_id` within the store; older versions remain queryable. (See `openfga-authorization-model.md`.)
- **Relationship tuple** — `(store_id, object, relation, user, condition?)`. The `user` field may be a concrete user (`user:anne`), a wildcard (`user:*`, "type-bound public access"), or a userset (`group:eng#member`).
- **Contextual tuples** — tuples supplied *at query time* in a Check/ListObjects request, not persisted. Used for ABAC / request-context data. (See `openfga-check-listobjects-consistency.md`.)
- **Conditions** — named CEL (Common Expression Language) expressions attached to relations/tuples, evaluated against request context to gate a relationship (ABAC).

## High-Level Architecture

```
+----------------------------------------------------------+
|                     Application                           |
|  (asks: can user U do R on object O?  -> Check(...))      |
+---------------------------+------------------------------+
                            |  gRPC / HTTP (+ store_id, model_id)
                +-----------v------------+
                |      OpenFGA server     |
                |  +-------------------+  |
                |  |  API layer        |  |  validates store_id, model,
                |  |  (Check/List/...) |  |  request shape, auth (preshared
                |  +---------+---------+  |  key / OIDC)
                |  +---------v---------+  |
                |  |  Query resolver / |  |  graph traversal of rewrite
                |  |  graph engine     |  |  rules; condition (CEL) eval
                |  +---------+---------+  |
                |  +---------v---------+  |
                |  |  Check-query cache|  |  optional; invalidated via
                |  |  (+ cache ctrl)   |  |  changelog polling
                |  +---------+---------+  |
                |  +---------v---------+  |
                |  |  Storage adapter  |  |  Postgres / MySQL / SQLite /
                |  |                   |  |  memory; primary + replicas
                |  +-------------------+  |
                +-------------------------+
```

## Trust Boundaries

1. **Caller -> OpenFGA API.** OpenFGA is the policy decision point (PDP). The application is trusted to (a) authenticate the end user itself, (b) pass the correct `user`, `object`, `relation`, and `store_id`, and (c) enforce the returned decision. OpenFGA does *not* authenticate the end user; it answers a relationship question about whoever the app names.

2. **API -> store.** The `store_id` is the tenant boundary. Every query and write must be scoped to a store; the engine must never read tuples from a different store than the one named.

3. **API authentication.** The OpenFGA server itself can be protected by **no auth**, **preshared key**, or **OIDC/JWT**. A misconfigured or unauthenticated server exposes all stores to any network caller. (Historically, the `streamed-list-objects` endpoint failed to validate the auth header — see CVE-2022-39340 in `openfga-security-advisories.md`.)

4. **Model -> tuples.** The authorization model constrains which tuples are *meaningful*. A relation's `directly related user types` restrict which user shapes may be assigned. The engine must enforce these type restrictions during evaluation; failing to do so has been the root cause of several authorization-bypass advisories.

## Security-Relevant Considerations

The intended invariants that must always hold for OpenFGA to be a sound authorization system:

- **The Check decision must equal the ground-truth graph reachability.** `Check(store, model, U, R, O)` must return `true` if and only if, under the named model version, the stored tuples (plus any contextual tuples) make `U` reach `R` on `O` via the model's rewrite rules. Any divergence is an authorization bypass (false `true` -> over-grant; false `false` -> over-deny / DoS-on-authorization). Most OpenFGA GHSA advisories are exactly this: an evaluation path returns `true` when the correct answer is `false` (or vice versa) for specific rewrite combinations.

- **`store_id` scopes every operation.** Without correct store scoping, a Check in store A could read tuples from store B -> cross-tenant authorization leak. The store is the isolation boundary; see `openfga-stores-and-multitenancy.md`.

- **The authorization model version used must be the one intended.** Models are immutable and versioned. If a query silently resolves against a different (e.g. newer, looser) model version than the caller intended, the decision is computed under the wrong policy. Callers should pin `authorization_model_id`.

- **Type restrictions on relations are load-bearing.** The set of "directly related user types" on a relation is a security constraint, not just validation sugar. If the engine evaluates a tuple (especially a *contextual* tuple, or a wildcard/userset tuple) without honoring these restrictions, an attacker-supplied contextual tuple of the wrong type can flip a decision — the mechanism behind CVE-2025-48371 and CVE-2025-25196.

- **The server must authenticate before answering.** Any endpoint that returns authorization data (Check, ListObjects, StreamedListObjects, Read) must enforce the configured auth scheme. An endpoint that skips the auth check is an information-disclosure / bypass vector (CVE-2022-39340 on `streamed-list-objects`).

- **The application remains responsible for authentication and enforcement.** OpenFGA answers "does U relate to O via R" — it trusts the caller's claim about who U is. If the app passes an attacker-controlled `user` without authenticating that identity, OpenFGA's correct answer is still an application-level bypass. This boundary must be respected by integrators.
