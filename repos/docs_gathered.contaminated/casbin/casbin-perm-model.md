# Casbin PERM Metamodel

Sources:
- https://casbin.apache.org/docs/how-it-works
- https://casbin.apache.org/docs/syntax-for-models
- https://casbin.apache.org/docs/supported-models

## Overview

Casbin's authorization system is built on the PERM metamodel: **Policy, Effect, Request, Matchers**. Access control models are expressed as CONF files based on this metamodel. The PERM abstraction decouples the authorization decision logic from storage and enforcement, allowing the same engine to implement ACL, RBAC, ABAC, and other models by changing only the configuration.

## The Four Components

### 1. Request Definition

The request definition specifies the parameters submitted for access evaluation. A basic request is a tuple object: subject (who is requesting), object (the resource), and action (the operation).

```ini
[request_definition]
r = sub, obj, act
```

Requests can be customized:
- `r = sub, act` (no resource, e.g., for feature flags)
- `r = sub, sub2, obj, act` (multiple subjects)
- `r = sub, dom, obj, act` (domain/tenant-scoped)

The request tuple maps directly to the arguments of the `Enforce()` call. Each element becomes accessible in the matcher as `r.sub`, `r.obj`, `r.act`, etc.

### 2. Policy Definition

The policy definition describes the shape of access rules: field names and order. Policies are stored externally (files, databases) and loaded into the enforcer.

```ini
[policy_definition]
p = sub, obj, act
p2 = sub, act
```

Sample policy file:
```csv
p, alice, data1, read
p, bob, data2, write
p2, charlie, write-all-objects
```

**Critical detail: Policy rule elements are always treated as strings.** This means that `1` and `01` are different values, and there is no type coercion. When using ABAC with eval(), policy expressions are stored as strings and evaluated at enforcement time.

The optional `eft` field specifies the policy effect (allow or deny). When omitted, the default effect is "allow":
```ini
p = sub, obj, act, eft
```

Multiple policy types (p, p2, p3) can coexist in the same model, each with different shapes.

### 3. Matchers

The matcher defines how a request is evaluated against policies. It is a boolean expression that references both request and policy fields.

```ini
[matchers]
m = r.sub == p.sub && r.obj == p.obj && r.act == p.act
```

Matchers support:
- Equality/inequality operators
- Logical operators (&&, ||, !)
- Arithmetic operators
- Built-in functions (keyMatch, regexMatch, ipMatch, etc.)
- The `in` operator for array membership
- The `g()` function for RBAC role resolution
- The `eval()` function for dynamic expression evaluation from policy fields

**Performance-critical note:** Place computationally cheaper conditions first in the matcher. A documented test case showed reordering to evaluate object matching before role lookups reduced execution time from 6+ seconds to ~7 milliseconds.

Matchers are evaluated using language-specific expression engines:
- Go: govaluate
- Java: AviatorScript
- Node.js: expression-eval
- Python: simpleeval

### 4. Policy Effect

The effect section combines the effects of all matched policies with a logical expression. This is where the final authorization decision is made.

```ini
[policy_effect]
e = some(where (p.eft == allow))
```

Supported effect expressions:

| Expression | Meaning | Behavior |
|---|---|---|
| `some(where (p.eft == allow))` | Allow-override | Allow if ANY matched policy allows |
| `!some(where (p.eft == deny))` | Deny-override | Allow only if NO matched policy denies |
| `some(where (p.eft == allow)) && !some(where (p.eft == deny))` | Allow-and-deny | Requires at least one allow AND zero denies |
| `priority(p.eft) \|\| deny` | Priority | First matched policy by priority order wins; default deny |
| `subjectPriority(p.eft)` | Subject hierarchy priority | Leaf roles (end users) have higher priority than inner roles |

## Authorization Decision Flow

When `Enforce(sub, obj, act)` is called:

1. The request parameters populate the defined request tuple structure
2. The matcher expression is evaluated against EACH stored policy rule
3. For each policy where the matcher evaluates to true, the policy's effect (allow/deny) is collected
4. The effect expression combines all collected effects into a single boolean authorization decision
5. The boolean result is returned

## Multiple Section Types

Models can define alternate sets of request/policy/effect/matcher using numeric suffixes:

```ini
[request_definition]
r = sub, obj, act
r2 = sub, obj

[policy_definition]
p = sub, obj, act
p2 = sub, obj

[matchers]
m = r.sub == p.sub && r.obj == p.obj && r.act == p.act
m2 = r2.sub == p2.sub && r2.obj == p2.obj

[policy_effect]
e = some(where (p.eft == allow))
e2 = some(where (p.eft == allow))
```

These grouped sections (r2, p2, e2, m2) can be invoked via `EnforceContext`, enabling simultaneous support for different policy schemas within a single enforcer.

## Role Definition (RBAC Extension)

RBAC models add a `[role_definition]` section:

```ini
[role_definition]
g = _, _
```

This defines a role inheritance graph. `g = _, _` means user-to-role mapping. `g2 = _, _` can define resource-to-role mapping. For domain RBAC, `g = _, _, _` adds a domain dimension.

Role relationships are stored as policies:
```csv
g, alice, admin
g, bob, user
```

The `g()` function in matchers resolves role membership:
```ini
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act
```

Role hierarchy is transitive: if alice has role1 and role1 has role2, then alice effectively has role2 and all its permissions. Default maximum hierarchy depth is 10 levels.

## Constraint Definition (RBAC Extension)

Optional constraints enforce invariants on role assignments:

```ini
[constraint_definition]
c = sod("finance_requester", "finance_approver")          # Separation of Duties
c2 = sodMax(["payroll_view", "payroll_edit", "payroll_approve"], 1)  # Max concurrent roles
c3 = roleMax("superadmin", 2)                              # Role cardinality cap
c4 = rolePre("db_admin", "security_trained")               # Prerequisite role
```

Constraints are checked when grouping policies change and validated during model loading.

## Security-Relevant Design Properties

1. **Default-deny**: If no policy matches, access is denied (unless the effect expression explicitly defaults to allow)
2. **String-only policies**: All policy elements are strings; no type system means no type-safety guarantees
3. **Expression evaluation**: Matchers use runtime expression evaluation, which introduces the risk of injection if user input flows into matcher expressions
4. **Evaluation order matters**: For priority models, the order of policy rules determines authorization outcome
5. **No built-in policy validation**: Casbin does not validate that policies make semantic sense; contradictory or redundant policies are silently accepted
