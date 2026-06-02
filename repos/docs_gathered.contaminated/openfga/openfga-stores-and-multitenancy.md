# OpenFGA Stores and Multi-Tenant Isolation

Sources:
- https://openfga.dev/docs/concepts
- https://openfga.dev/docs/getting-started/create-store
- https://openfga.dev/docs/getting-started/setup-openfga/configure-openfga
- https://openfga.dev/docs/modeling/migrating/migrating-models
- https://openfga.dev/api/service
- https://github.com/openfga/openfga

## What a Store Is

A **store** is OpenFGA's top-level container and **isolation boundary**. A store holds:

- all **relationship tuples** for one logical application/tenant,
- the store's **authorization-model versions** (immutable, versioned policy),
- **assertions** (test cases) for those models,
- a **changelog** of tuple writes/deletes (used for cache invalidation and `ReadChanges`).

Every store has a `store_id`. Stores are independent: there is no cross-store relation, no cross-store inheritance, and no API that joins tuples across stores. Two stores are as isolated as two separate databases.

## `store_id` Scopes Every Operation

Essentially all data-plane and data-management calls require a `store_id` path parameter:

```
POST /stores/{store_id}/check
POST /stores/{store_id}/list-objects
POST /stores/{store_id}/list-users
POST /stores/{store_id}/expand
POST /stores/{store_id}/read
POST /stores/{store_id}/write
POST /stores/{store_id}/authorization-models
GET  /stores/{store_id}/authorization-models/{id}
GET  /stores/{store_id}/changes
```

The only store-unscoped endpoints are store *management* itself (`CreateStore`, `ListStores`, `GetStore`, `DeleteStore`). Every query and every tuple write is therefore namespaced by store at the API layer and must be namespaced by store in the storage layer (the `store` column is part of the tuple's primary key in the relational adapters).

## Authorization-Model Versioning Per Store

- Each `WriteAuthorizationModel` creates a **new immutable model version** within that store, returning a fresh `authorization_model_id`.
- Models are never edited in place; "changing" a model means writing a new version.
- Queries may pin a specific `authorization_model_id`. If omitted, OpenFGA uses the **latest** model in that store.
- Because old versions persist, a Check issued against an old model id evaluates under that old policy even after newer versions exist. This is intentional: it lets applications migrate models without a flag-day, and it means a decision is reproducible against the exact model that produced it.

### Multi-tenant patterns

Two common topologies:

1. **One store per tenant.** Strongest isolation — tenant A's tuples physically cannot be read by a query scoped to tenant B's store. The `store_id` *is* the tenant key.
2. **One shared store, tenant encoded in object/relation.** A single store with a `tenant`/`organization` type and tuples that scope every resource to its org (e.g. `document:doc1#org@organization:acme`, plus model rules that require org membership). Isolation here is enforced by the **model**, not by the store boundary — a modeling mistake (a relation that doesn't require the org link) leaks across tenants.

Pattern 1 leans on the store boundary; pattern 2 leans on the rewrite-evaluation-correctness invariant. Most production guidance prefers a store per tenant for hard isolation when tenants are mutually untrusting.

## Server-Level Access Control

The store boundary only matters if the *server* is access-controlled. OpenFGA supports:

- **No authentication** (default for local dev) — every store is reachable by any caller.
- **Preshared key** — a static API token in the `Authorization` header.
- **OIDC / JWT** — tokens validated against an issuer.

A single OpenFGA deployment commonly hosts many stores. If the server has no auth (or an endpoint skips the auth check), a network caller can enumerate `ListStores` and read tuples from *every* tenant's store. (This is precisely the class of CVE-2022-39340, where `streamed-list-objects` did not validate the auth header.)

## Security-Relevant Considerations

The multi-tenant isolation invariant and its failure modes:

- **`store_id` must scope every query and every tuple read at the storage layer — not just the API layer.** If the storage adapter ever builds a query that omits the `store` predicate (or uses the wrong store), a Check in store A could read tuples from store B -> **cross-tenant authorization leak**: tenant A's user is granted access based on tenant B's grants, or tenant B's private resource list is disclosed to tenant A. The store column being part of the tuple primary key is what enforces this; any query path that drops it is a tenant-isolation breach.

- **`ListStores` and store-management endpoints must be authenticated.** These are the enumeration surface. An unauthenticated `ListStores` reveals every tenant's `store_id`, which is the key to every other store-scoped call. Server auth (preshared key / OIDC) is the only thing standing between an anonymous caller and all tenants' data.

- **Every data-returning endpoint must enforce server auth uniformly.** A single endpoint that forgets the auth check (the CVE-2022-39340 pattern on `streamed-list-objects`) bypasses the entire tenant model, because it can be called against any `store_id` without credentials -> information disclosure of objects across stores.

- **In a shared-store multi-tenant model, isolation depends entirely on the rewrite rules.** When tenants share one store and are distinguished by an `organization`/`tenant` link, the model must require that link on every resource relation. A relation that grants access without traversing the org link (e.g. a stray `define viewer: [user]` instead of `define viewer: member from org`) is a cross-tenant leak that the store boundary will not catch. Prefer store-per-tenant when tenants are mutually untrusting.

- **Model version is part of the security context.** Because a store keeps all historical model versions and unpinned queries use the latest, a deploy that writes a new, looser model version silently changes the policy for every unpinned query in that store. Pin `authorization_model_id` for decisions that must be reproducible, and treat "write a new model version" as a policy change requiring the same review as a code change.

- **`DeleteStore` is a destructive, store-wide operation.** Because it removes all tuples and models for a tenant, it must be tightly authorized; an attacker with store-management access can erase a tenant's entire authorization state.
