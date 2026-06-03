# Casbin Security Model — Authorization Evaluation Semantics

## Sources

- README (PERM metamodel description): https://raw.githubusercontent.com/casbin/casbin/master/README.md
- Enforcer source (`enforce` function): https://raw.githubusercontent.com/casbin/casbin/master/enforcer.go
- ACL model example: https://github.com/casbin/casbin/blob/master/examples/basic_model.conf
- RBAC model example: https://raw.githubusercontent.com/casbin/casbin/master/examples/rbac_model.conf
- RBAC with deny model: https://raw.githubusercontent.com/casbin/casbin/master/examples/rbac_with_deny_model.conf
- ABAC model example: https://github.com/casbin/casbin/blob/master/examples/abac_model.conf
- Docs index for model syntax: https://casbin.org/docs/syntax-for-models
- Effector: https://github.com/casbin/casbin/tree/master/effector

## Context

Casbin evaluates an authorization request as a two-step process. First, each policy rule is independently scored against the request through the **matcher** expression (a govaluate-evaluated boolean/numeric formula referencing `r.*` and `p.*` tokens). Second, the per-rule scores and the per-rule `p_eft` (allow/deny) are combined by the **effect** expression to produce a single Allow / Deny / Indeterminate verdict. **Only Allow becomes `Enforce` → `true`; both Deny and Indeterminate produce `false`.** This means the default answer for any request that fails to match any allow rule is "deny" — Casbin is closed-by-default.

## Model File Structure

A Casbin model has up to five sections:

```ini
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = r.sub == p.sub && r.obj == p.obj && r.act == p.act
```

- `[request_definition]` — names the tokens of an incoming request. Default ACL/RBAC uses `r = sub, obj, act`. RBAC-with-domains adds `dom`: `r = sub, dom, obj, act`. Custom shapes are allowed.
- `[policy_definition]` — names the tokens of each policy rule. If a `p` definition includes `eft`, then each rule carries an explicit `allow`/`deny` tag; otherwise every rule is implicitly `allow`.
- `[role_definition]` — names role-link tables. `g = _, _` is the simplest: a user/role pair. `g = _, _, _` adds a domain. `g2 = _, _` defines a second role-link (e.g., for resource roles).
- `[policy_effect]` — how matched rules combine. Common forms:
  - `e = some(where (p.eft == allow))` — at least one allow match → Allow (no explicit deny).
  - `e = !some(where (p.eft == deny))` — no deny match → Allow (no allow rules needed).
  - `e = some(where (p.eft == allow)) && !some(where (p.eft == deny))` — allow if any allow matches AND no deny matches. **Deny-override semantics.**
  - `e = priority(p_eft) || deny` — first-match wins by rule order; explicit deny if no match.
- `[matchers]` — boolean expression returning whether a given (request, rule) pair matches. May call built-in functions: `keyMatch`, `keyMatch2`, `keyMatch3`, `regexMatch`, `ipMatch`, `globMatch`, `g(...)` (role-link query).

## Evaluation Semantics — Step by Step

From `enforcer.go` `enforce(...)`:

1. If `e.enabled == false`, `Enforce` returns `(true, nil)` immediately — every request is allowed. (See `EnableEnforce(false)`.) This is a kill-switch, not a default state.
2. Build the function map: standard functions (`keyMatch`, etc.) plus a `g`-family function per `g` role definition, generated from the live role manager. **The `g` functions close over the role manager's current state** — they reflect grouping policy mutations immediately for any single `Enforce` call.
3. If `e.acceptJsonRequest == true`, attempt to parse each string-typed request argument that begins with `{` or `[` as JSON into `map[string]interface{}`.
4. Verify the number of request tokens matches `len(rvals)`; error otherwise.
5. For each policy rule `p_i` in `e.model["p"][pType].Policy`:
   - Set `parameters.pVals = p_i`.
   - Evaluate the matcher expression. Result must be bool, float64, or int. Convert to `matcherResults[i] ∈ {0, 1}` (boolean true or non-zero numeric counts as match).
   - Determine `policyEffects[i]` from `p_i`'s `eft` token: `"allow"` → Allow, `"deny"` → Deny, anything else → Indeterminate. If the policy definition has no `eft` token, all rules count as Allow.
   - Call `e.eft.MergeEffects(effectExpr, policyEffects, matcherResults, i, totalLen)`. This is the effector applying the `[policy_effect]` rule incrementally. If the merger returns a definite Allow or Deny before all rules are scanned, the loop breaks early.
6. Final boolean: `result = (effect == Allow)`. So both `Deny` and `Indeterminate` produce `false`.
7. `EnforceEx` additionally records the index of the explaining rule in `explains[]` — useful for auditing why a request was allowed.

## RBAC Semantics

When the model contains `[role_definition]` and the matcher uses `g(r.sub, p.sub)`, that function call is resolved at evaluation time against the role manager:

- `g(alice, admin)` returns true if `alice == admin`, or if the grouping policy contains a path `alice → ... → admin` through `g` rules.
- A `g` definition with 3 args supports domains: `g(alice, admin, tenant1)` checks role inheritance scoped to tenant1.
- The role manager has a `maxHierarchyLevel` (default 10) limiting transitive lookup depth. Cycles in `g` are not formally rejected at insert time, but lookups terminate at `maxHierarchyLevel` hops.
- `g(...)` results are cached in the `gFunctionCache` (per-enforcer) when `e.gFunctionCache == true`. This is a **separate** cache from `CachedEnforcer`'s decision cache. The `gFunctionCache` is invalidated by `e.invalidateMatcherMap()` and `EnableGFunctionCache(...)`. It is intended to be disabled for high-cardinality inputs (UUIDs, dynamic paths) to prevent unbounded memory growth.

## ABAC Semantics

ABAC requests pass non-string objects (Go structs or maps) as `sub` and `obj`. The matcher accesses fields directly:

```ini
m = r.obj.Owner == r.sub && r.act == "read"
```

ABAC has no `[policy_definition]` if the policy is fully expressed in the matcher; otherwise it can be combined with `p` rules. **CachedEnforcer skips the cache for non-string inputs** (`GetCacheKey` returns `(_, false)` for non-string, non-`CacheableParam` arguments), so ABAC requests with struct subjects never hit the cache — `CachedEnforcer.Enforce` falls through to `Enforcer.Enforce` for them.

## Closed-by-default invariants

- A request that matches no policy rule receives `Indeterminate` from the effector → `false` from `Enforce`. There is no implicit-allow path.
- A model with no policy rules (`len(e.model["p"][pType].Policy) == 0`) skips the per-rule loop. The effector is called once with a single Indeterminate effect → `false`.
- The only way to make a request return `true` without a matching allow rule is `EnableEnforce(false)`, which puts the enforcer into a "permissive monitor" state. There is no documented use of this in production paths.

## Invariants

- `Enforce(sub, obj, act)` returning `true` MUST imply at least one policy rule matched the request AND the effect expression evaluated to Allow (modulo `EnableEnforce(false)`).
- Closed-by-default: a request with no matching allow rule MUST return `false`.
- Deny rules (in models with deny-override effect) MUST override allow rules: if any rule with `p_eft == deny` matches, the final result MUST be `false` regardless of how many allow rules also match.
- Role inheritance MUST be transitive through `g`-rule chains up to `maxHierarchyLevel` hops. A user with `g, alice, admin` and `g, admin, root` MUST be treated as having role `root` in matchers that use `g(r.sub, "root")`.
- Removing a grouping policy (`g, alice, admin`) MUST cause subsequent `Enforce(alice, X, Y)` calls — where the permission to X depends on alice having role admin — to return `false`. (This is the invariant CachedEnforcer violates in the CASBIN-7 finding: the role-manager state changes correctly but the decision cache still returns the stale `true`.)
- `EnforceEx` MUST return the index of the rule that produced the Allow verdict (or empty when the verdict was Deny/Indeterminate). This is the auditable "why was this allowed" path; if it disagrees with `Enforce`, the enforcer is in an inconsistent state.
- ABAC requests with struct subjects/objects MUST evaluate against the live struct field values on every call — `CachedEnforcer` enforces this by deliberately skipping the cache for non-string inputs.
