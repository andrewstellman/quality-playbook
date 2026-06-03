# OpenFGA Authorization Model: Types, Relations, Rewrites, and Conditions

Sources:
- https://openfga.dev/docs/configuration-language
- https://openfga.dev/docs/concepts
- https://openfga.dev/docs/modeling/building-blocks/usersets
- https://openfga.dev/docs/modeling/building-blocks/direct-relationships
- https://openfga.dev/docs/modeling/parent-child
- https://openfga.dev/docs/modeling/conditions
- https://openfga.dev/docs/modeling/contextual-time-based-authorization
- https://openfga.dev/docs/interacting/contextual-tuples
- https://deepwiki.com/openfga/language/1.1-core-concepts

## The Authorization Model

The authorization model is the **formal policy specification**. It declares the object **types** in a store and, for each type, the **relations** users can have and the **rewrite rules** that define when a relation holds. Models are written in either:

- the **DSL** (`.fga`, a.k.a. the "configuration language") — human-friendly, compiles to JSON before being sent to the API; or
- the **JSON** API representation — what the server actually stores and evaluates.

Each `WriteAuthorizationModel` call creates a **new immutable version** identified by an `authorization_model_id`. Older versions remain queryable so a model change cannot retroactively rewrite past decisions. There is a schema version header; current models use `schema 1.1` (which introduced explicit type restrictions on relations and conditions).

### Minimal DSL example

```dsl
model
  schema 1.1

type user

type document
  relations
    define owner: [user]
    define editor: [user] or owner
    define viewer: [user] or editor
```

The same model in JSON (abbreviated) attaches a `userset` rewrite to each relation:

```json
{
  "schema_version": "1.1",
  "type_definitions": [
    { "type": "user" },
    {
      "type": "document",
      "relations": {
        "owner":  { "this": {} },
        "editor": { "union": { "child": [ { "this": {} }, { "computedUserset": { "relation": "owner" } } ] } },
        "viewer": { "union": { "child": [ { "this": {} }, { "computedUserset": { "relation": "editor" } } ] } }
      },
      "metadata": {
        "relations": {
          "owner":  { "directly_related_user_types": [ { "type": "user" } ] },
          "editor": { "directly_related_user_types": [ { "type": "user" } ] },
          "viewer": { "directly_related_user_types": [ { "type": "user" } ] }
        }
      }
    }
  ]
}
```

## Type Restrictions (`directly_related_user_types`)

The `[user]` in `define owner: [user]` is the **type restriction**: the set of user shapes that may be *directly assigned* to that relation. Allowed shapes:

- A concrete type: `[user]`
- A userset of a type+relation: `[group#member]`
- Type-bound public access (wildcard): `[user:*]`
- Conditioned types (schema 1.1 conditions): `[user with non_expired_grant]`

This list is a **security constraint**: the engine must reject (and must not evaluate as matching) a tuple — *including a contextual tuple supplied at query time* — whose user shape is not in the relation's allowed list. Several bypass advisories arose from this constraint being skipped for contextual/wildcard/userset tuples.

## Relation Rewrites (the semantic core)

A relation's rewrite defines the *set of users* who have that relation on an object. The engine answers Check by evaluating these rules as a graph traversal.

### 1. Direct (`this` / `[type]`)

```dsl
define viewer: [user, group#member]
```
A user has `viewer` if there is a stored (or contextual) tuple `document:X#viewer@user:U` (or `@group:G#member` matching the userset shape). Semantics: membership comes directly from a tuple of an allowed type.

### 2. Computed userset (relation reference)

```dsl
define editor: [user]
define viewer: editor
```
`viewer` rewrites to "whoever is `editor` on the same object." Semantics: alias/inheritance on the *same* object — every editor is a viewer. No tuple of relation `viewer` is needed.

### 3. Union (`or`)

```dsl
define viewer: [user] or editor or owner
```
Holds if the user is in **any** child set. Semantics: set union. Adding a path can only *grant*, never revoke.

### 4. Intersection (`and`)

```dsl
define can_view: viewer and member
```
Holds only if the user is in **all** child sets. Semantics: set intersection. Used to require two conditions simultaneously (e.g. "is a viewer AND is an active org member").

### 5. Exclusion (`but not`)

```dsl
define viewer: [user] but not blocked
```
Holds if the user is in the left set **and not** in the right set. Semantics: set difference. The right-hand side is a *negative* / revocation path — a `blocked` tuple must subtract the user from `viewer`.

> Intersection and exclusion are the rewrites most prone to evaluation bugs, because they require the engine to correctly compute "is NOT in set" and to terminate correctly on cyclic relationships. CVE-2024-31452 (cyclical relationships with `and`/`but not`) and CVE-2024-42473 (`but not` + `from` + userset) are exactly these.

### 6. Tuple-to-userset (`X from Y`) — the most important rewrite

```dsl
type folder
  relations
    define viewer: [user]

type document
  relations
    define parent: [folder]
    define viewer: [user] or viewer from parent
```

`viewer from parent` means: *"to find the viewers of this document, first find the objects related to it by `parent` (the **tupleset**), then take the `viewer` userset of each of those objects."* Concretely, a user has `viewer` on `document:D` if there exists `document:D#parent@folder:F` **and** the user has `viewer` on `folder:F`. This is how hierarchical / inherited permissions ("inherit access from the containing folder") are modeled.

Terminology:
- The relation after `from` (`parent`) is the **tupleset** — the right-hand side that produces the set of intermediate objects.
- The relation before `from` (`viewer`) is the **computed relation** evaluated on each intermediate object.

Semantics, precisely: `U has (R from Tupleset) on O` iff there exists an object `O'` such that `O#Tupleset@O'` is a tuple **and** `U has R on O'`.

> The tupleset side has a historical security footgun: a **wildcard (`*`) on a tupleset relation** was mishandled (CVE-2022-39341), allowing authorization bypass. Wildcards on tupleset relations are no longer permitted.

## Conditions and Contextual Tuples (ABAC)

OpenFGA layers attribute-based access control on top of ReBAC via **conditions** — named CEL (Common Expression Language) expressions that gate a relationship based on runtime context.

### Defining a condition

```dsl
model
  schema 1.1

type user

type document
  relations
    define viewer: [user with non_expired_grant]

condition non_expired_grant(current_time: timestamp, grant_time: timestamp, grant_duration: duration) {
  current_time < grant_time + grant_duration
}
```

A tuple assigned to a conditioned relation carries the condition and any tuple-bound parameters:

```json
{
  "user": "user:anne",
  "relation": "viewer",
  "object": "document:roadmap",
  "condition": {
    "name": "non_expired_grant",
    "context": { "grant_time": "2025-01-01T00:00:00Z", "grant_duration": "10m" }
  }
}
```

At Check time the caller supplies the remaining context:

```json
{
  "tuple_key": { "user": "user:anne", "relation": "viewer", "object": "document:roadmap" },
  "context": { "current_time": "2025-01-01T00:05:00Z" }
}
```

The relationship holds only if the tuple's stored relation path holds **and** the condition evaluates to `true` against the merged context. Semantics: a condition is a *gate* multiplied onto the relationship — it can only remove access that the relationship graph already grants, never add it.

### Contextual tuples

Contextual tuples are tuples passed in the Check/ListObjects request body that are **not persisted**. They are evaluated as if they existed in the store, but only for that one request. Used for request-scoped facts (e.g. "the user is currently in this IP range," "this user is acting in org X"). They are subject to the same type restrictions as stored tuples — and *must* be, or an attacker who can influence the request context can inject a tuple that flips the decision (the contextual-tuple-with-conditions bypass, CVE-2024-56323, and the contextual-tuple userset bypass, CVE-2025-48371).

## Security-Relevant Considerations

The model is the *intended* policy; the engine's evaluation must match it exactly. Invariants:

- **Rewrite evaluation must be faithful to set semantics.** `or` = union, `and` = intersection, `but not` = set difference, `from` = the two-hop tupleset→computed-relation join. A Check returns `allowed=true` iff the user is in the set the rewrite denotes. An engine that, e.g., treats `and` as `or`, drops a `but not` exclusion, or mis-joins a tuple-to-userset, produces an authorization bypass. This is the **rewrite-evaluation correctness invariant** and is the single largest class of OpenFGA advisories.

- **Exclusion (`but not`) must actually subtract.** If the negative branch is not evaluated (or short-circuits the wrong way), a `blocked`/revoked user retains access. Combined with `from` traversal and usersets this has produced real bypasses (CVE-2024-42473).

- **Cyclic relationships must terminate with the correct answer.** Models that allow cycles through `and`/`but not` must not loop, and must not return `true` from an incompletely-explored cycle (CVE-2024-31452).

- **Type restrictions gate every tuple, including contextual ones.** A tuple whose user shape is not in the relation's `directly_related_user_types` must not contribute to a positive decision. Skipping this check for contextual tuples or for the userset/public-access combination lets a caller inject an unauthorized grant (CVE-2025-48371, CVE-2025-25196).

- **Wildcards (`*`) are restricted by position.** Type-bound public access (`user:*`) is valid on ordinary relations but was never intended on a **tupleset** relation; allowing it there bypassed authorization (CVE-2022-39341). Wildcard handling must respect the model's type metadata.

- **Conditions can only restrict, never grant.** A condition gates an already-granted relationship. A bug that treats a failing/erroring condition as "pass," or that lets condition context override the relationship graph, is a bypass. Field-shadowing in context merging (open issue #3063) is a live example of how condition context can be corrupted.

- **The model version is part of the decision.** Because models are immutable and versioned, the decision is only meaningful relative to a specific `authorization_model_id`. Evaluating tuples under the wrong model version computes the wrong policy.
