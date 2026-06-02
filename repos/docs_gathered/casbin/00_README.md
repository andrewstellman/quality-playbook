# Casbin — Project Overview

## Sources

- Repository (current, mirror at GitHub): https://github.com/casbin/casbin (redirects to https://github.com/apache/casbin — the project was donated to the Apache Software Foundation)
- README: https://raw.githubusercontent.com/casbin/casbin/master/README.md
- Documentation site: https://casbin.org/docs/overview
- Online editor (model + policy playground): https://casbin.org/editor/
- Go package: `github.com/casbin/casbin/v3` (https://pkg.go.dev/github.com/casbin/casbin/v3)

## Context

Casbin is a general-purpose, open-source authorization (access control) library for Go. It separates **policy** (a set of rules, stored in a CSV file, a database, or another backing adapter) from the **model** (a CONF/INI file describing how requests are matched against rules and how multiple matches are combined into a final decision). Around the model and policy sits an **Enforcer**, which evaluates an `Enforce(sub, obj, act)` call into a boolean decision. Casbin is deliberately not an authentication system: it does not verify passwords, manage users, or issue tokens — the calling application is responsible for identifying the subject before asking Casbin whether that subject is permitted to act on a given object. Casbin ships in 8+ language ports; this audit targets the Go reference implementation, which is the canonical one and the one all other ports follow.

## Key Terminology

- **Enforcer** — the central object an application holds; constructed via `NewEnforcer(modelPath, policyPathOrAdapter)`. It loads the model, loads the policy through an adapter, builds role-link data structures, and answers `Enforce(...)` calls. Concrete variants:
  - `Enforcer` — base, single-threaded (not goroutine-safe for concurrent writes).
  - `SyncedEnforcer` — wraps `Enforcer` with a `sync.RWMutex`; safe for concurrent reads + writes.
  - `CachedEnforcer` — wraps `Enforcer` with an in-memory decision cache keyed on the request tuple.
  - `SyncedCachedEnforcer` — wraps `SyncedEnforcer` with the same decision cache.
  - `DistributedEnforcer` — wraps `SyncedEnforcer` for use across multiple nodes via a Dispatcher.
- **Model** — a CONF file with five required sections: `[request_definition]`, `[policy_definition]`, `[policy_effect]`, `[matchers]`, and (for RBAC) `[role_definition]`. Models follow the **PERM metamodel**: Policy, Effect, Request, Matchers.
- **Policy** — a set of rules, conventionally CSV: `p, alice, data1, read` (a permission rule) or `g, alice, admin` (a grouping rule, see below). Stored via an **Adapter** (file, MySQL, MongoDB, Redis, etc.).
- **Request** — the tuple Casbin is asked to decide on, typically `(sub, obj, act)` (subject, object, action), but the model file can define any shape (e.g., add a `dom` for domain/tenant, or use ABAC where `sub`/`obj` are objects with attributes).
- **Matcher** — a `govaluate` expression in the model file that returns true when a request matches a policy rule (e.g., `m = r.sub == p.sub && r.obj == p.obj && r.act == p.act`).
- **Effect** — how multiple matched rules combine to a final allow/deny. ACL uses `e = some(where (p.eft == allow))`. Deny-override uses `e = some(where (p.eft == allow)) && !some(where (p.eft == deny))`.
- **RBAC** — Role-Based Access Control. Casbin expresses roles via **grouping policy** rules with prefix `g`: `g, alice, admin` means alice has role admin. The matcher uses the `g(...)` function: `m = g(r.sub, p.sub) && ...`, which is true when `r.sub` either equals `p.sub` or transitively inherits from it through the grouping policy.
- **Grouping policy / role-link / role manager** — the in-memory graph built from `g` rules. A **RoleManager** answers `HasLink(name1, name2, domain...)` queries. Role inheritance is multi-hop: `g, alice, admin; g, admin, root` means alice transitively has root.
- **ABAC** — Attribute-Based Access Control. Subjects/objects are structs (or maps) and matchers use field syntax like `r.sub.Age > 18 && r.obj.Owner == r.sub.Name`.
- **Adapter** — the persistence boundary: `LoadPolicy(model)`, `SavePolicy(model)`, `AddPolicy`, `RemovePolicy`, `RemoveFilteredPolicy`. The file adapter is built in; database adapters are separate modules.
- **Watcher** — an optional callback object that notifies the enforcer when an external process changes the policy (e.g., another node updates the DB); the enforcer calls `LoadPolicy` in response.
- **Dispatcher** — optional component for distributed consensus on policy changes (used by `DistributedEnforcer`).

## Language and Domain

- **Language:** Go (module path `github.com/casbin/casbin/v3`; older versions used `/v2` and `/v1`).
- **Domain:** Authorization / access control. Casbin is embedded into application code — there is no network protocol, no daemon, no JWT logic. Calls are in-process function calls.
- **Supported models out of the box:** ACL, ACL+superuser, ACL without users, ACL without resources, RBAC, RBAC with resource roles, RBAC with domains/tenants, ABAC, RESTful (with `keyMatch`/regex), deny-override, priority-ordered rules.
- **Threading model:** The base `Enforcer` is **not** safe for concurrent writes — callers that need concurrent `Enforce` plus `AddPolicy`/`RemovePolicy` must use `SyncedEnforcer` or `SyncedCachedEnforcer`. `Enforce` is safe to call from multiple goroutines on a base enforcer only if no mutator runs concurrently.

## Where decisions live

The decision pipeline for `Enforce(sub, obj, act)`:

1. (CachedEnforcer only) Compute a cache key from the string-typed request values (`alice$$data1$$read$$`). If a non-expired entry exists, return it.
2. Build the matcher expression (`m = ...`) from the model, with `g`/`g2`/... role functions bound to the live role managers.
3. For each policy rule `p_i`, evaluate the matcher with `r = request` and `p = p_i`. Collect a vector of matcher results and the per-rule `p_eft` (allow/deny if the policy has an `eft` column, else allow).
4. Apply the effect expression (`e = ...`) to that vector, producing one of `Allow` / `Deny` / `Indeterminate`. Only `Allow` becomes a `true` response — everything else is `false`.
5. (CachedEnforcer only) Store the boolean result in the cache under the request key with the configured TTL.

Step 1 + 5 are the source of the cache-consistency bug class this audit is targeted at: any policy mutation that changes the result of step 3 but is NOT mirrored by a corresponding cache invalidation in step 1's keyspace leaves stale `true` responses for the TTL window.
