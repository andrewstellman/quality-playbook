# Casbin Policy Effect Evaluation

Sources:
- https://casbin.apache.org/docs/syntax-for-models (effect section)
- https://casbin.apache.org/docs/supported-models
- https://casbin.apache.org/docs/priority-model
- https://github.com/casbin/casbin/issues/917 (ABAC deny bug)
- https://github.com/casbin/casbin/issues/290 (RBAC deny-override issues)
- https://github.com/apache/casbin/issues/727 (evaluation short-circuiting)
- https://github.com/casbin/casbin/issues/550 (priority support)

## Overview

The policy effect section defines how the effects of all matched policies are combined into a final authorization decision. This is the last step in Casbin's PERM evaluation: after the matcher identifies which policies match a request, the effect expression aggregates their effects (allow/deny) into a single boolean result.

## Effect Expressions

### 1. Allow-Override (Default)

```ini
e = some(where (p.eft == allow))
```

**Semantics**: The result is ALLOW if ANY matched policy has effect "allow". If no policies match, the result is DENY (default-deny).

**Behavior**:
- Iterates through all matched policies
- If any matched policy has eft=allow, returns true
- Short-circuits: stops evaluation after finding the first allow match
- Policies without an explicit `eft` field default to "allow"
- If zero policies match, result is deny

### 2. Deny-Override

```ini
e = !some(where (p.eft == deny))
```

**Semantics**: The result is ALLOW only if NO matched policy has effect "deny".

**Behavior**:
- If ANY matched policy has eft=deny, returns false
- If no policies match the request, result is ALLOW (because there are no denies)
- **Security warning**: This means requests that match NO policies are ALLOWED. This is the opposite of default-deny. Use with caution.

### 3. Allow-and-Deny (Combined)

```ini
e = some(where (p.eft == allow)) && !some(where (p.eft == deny))
```

**Semantics**: The result is ALLOW only if there is at least one matched allow policy AND zero matched deny policies.

**Behavior**:
- Requires at least one allow match
- Any deny match vetoes the entire request
- If no policies match, result is DENY (because there is no allow match)
- This is the recommended effect for deny-override models that should also be default-deny

**Known bug (fixed)**: Issue #917 documented a critical bug where ABAC matchers failed incorrectly when the policy file contained ANY deny rule, even if that deny rule didn't apply to the current request. For example, with matcher `m = r.sub.Superuser || r.sub.User == r.obj.Owner` and an unrelated deny policy `p, foobar, /blah, read, deny`, a superuser request would be incorrectly denied. Fixed in PR #918. The root cause was that the ABAC evaluation was processing deny effects from policies that the ABAC matcher never actually matched against.

### 4. Priority (Policy Order)

```ini
e = priority(p.eft) || deny
```

**Semantics**: The first matched policy by priority order determines the result. If no policy matches, the result is DENY.

**Three priority modes**:

#### Implicit Priority (Document Order)
- The first policy listed in the policy file has highest priority
- Simple but fragile: reordering policies changes authorization behavior
- No explicit priority field needed

#### Explicit Priority (Numeric Field)
```ini
[policy_definition]
p = priority, sub, obj, act, eft
```
- Lower number = higher priority
- Non-numeric values receive the lowest ranking
- **Critical limitation**: Only `AddPolicy` and `AddPolicies` respect explicit priority. Do NOT change the priority field via `UpdatePolicy` -- the priority ordering will not be updated.

#### Subject Hierarchy Priority
```ini
e = subjectPriority(p.eft)
```
- Leaf roles (end users) have higher priority than inner roles (e.g., admin, root)
- Hierarchies must form tree structures, not graphs
- Multi-role users must exist at identical depths in the hierarchy
- Same-level ties resolve by policy order

## The `eft` Field

The optional `eft` (effect) field in policy definitions specifies whether a policy rule allows or denies access.

- When `eft` is omitted from the policy definition, all matching policies default to "allow"
- When `eft` is included, valid values are "allow" and "deny"
- Policy: `p, alice, data1, read, deny` explicitly denies alice read access to data1

## Security-Relevant Edge Cases

### 1. ABAC with Deny Effects (Issue #917)
When using ABAC matchers (which evaluate attributes, not policy strings), the deny effect evaluation must be properly scoped. The bug in #917 showed that deny effects from policy rules that were never actually matched by the ABAC condition were still being counted in the effect aggregation. This is because the ABAC matcher evaluates to a boolean independent of specific policy rows, but the effect system still iterates all policies.

### 2. Deny-Override Scope (Issue #290)
With `some(where (p.eft == allow)) && !some(where (p.eft == deny))`, deny rules apply globally across all matched policies. A deny for "public" on "/admin" blocks ALL users, not just public users. The deny effect does not check whether the deny policy's subject matches the request's subject -- it only checks whether the deny policy was matched by the matcher.

**Implication**: If the matcher uses `p.sub == "public"` in combination with `|| p.sub == r.sub`, a deny for "public" on "/admin" will match when the request's subject is "public" (via the second clause) OR when the subject is in the public role, and that deny will block the request regardless of other allow policies.

### 3. Short-Circuit Evaluation (Issue #727)
With `some(where (p.eft == allow))` and only allow rules, the engine stops after finding the first match. The Casbin team confirmed this is existing behavior. However, with deny-involved effects, ALL policies must be evaluated to check for deny matches.

### 4. No-Match Default
- `some(where (p.eft == allow))`: No match -> DENY
- `!some(where (p.eft == deny))`: No match -> ALLOW (dangerous!)
- `some(where...) && !some(where...)`: No match -> DENY
- `priority(p.eft) || deny`: No match -> DENY

### 5. Priority Conflicts
When using explicit priority, policies with the same priority value have undefined ordering behavior. The first matched at that priority level wins, but the iteration order is implementation-dependent.

### 6. Effect Expression is Not Extensible
Casbin supports only the predefined effect expressions listed above. Custom effect logic cannot be defined. If the predefined expressions don't match the desired authorization semantics, the model must be restructured (e.g., using multiple policy types or custom matchers).

## Interaction with Matchers

The effect evaluation operates on the SET of policies where the matcher returned true. The matcher determines WHICH policies are relevant; the effect determines HOW to combine them.

A policy with `eft=deny` that does NOT match the request (matcher returns false for that policy) is ignored by the effect evaluation. The bug in Issue #917 was specifically about ABAC matchers incorrectly evaluating policies, not about the effect logic itself.
