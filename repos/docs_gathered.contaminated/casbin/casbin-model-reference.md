# Casbin Model Reference

Sources:
- https://casbin.apache.org/docs/supported-models
- https://casbin.apache.org/docs/syntax-for-models
- https://casbin.apache.org/docs/rbac
- https://casbin.apache.org/docs/abac
- https://casbin.apache.org/docs/priority-model

## Supported Model Types

Casbin supports 18 distinct access control models. Each model is defined by a CONF file specifying request, policy, effect, and matcher sections.

### ACL (Access Control List)

Directly assigns permissions to users for specific resources.

```ini
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = r.sub == p.sub && r.obj == p.obj && r.act == p.act
```

Variants:
- **ACL with superuser**: Adds a superuser check (`r.sub == "root" || (...)`) that bypasses all policy checks
- **ACL without users**: Omits the subject field for scenarios without authentication
- **ACL without resources**: Permissions apply to resource categories rather than individual instances

### RBAC (Role-Based Access Control)

Uses role inheritance to simplify permission management.

```ini
[role_definition]
g = _, _

[matchers]
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act
```

The `g()` function resolves role membership transitively. If alice has role1 and role1 has role2, then `g(alice, role2)` returns true.

**Role hierarchy**: RBAC1-style, transitive, max default depth of 10 levels.

**Critical limitation**: Users and roles are both strings. The same name can represent both a user and a role. Casbin recommends naming conventions (e.g., prefix `role::`) to distinguish them. Never reuse names between users and roles.

**Implicit vs. Direct permissions**:
- `GetRolesForUser()` / `GetPermissionsForUser()` return only direct assignments
- `GetImplicitRolesForUser()` / `GetImplicitPermissionsForUser()` include inherited permissions through role hierarchy

Variants:
- **RBAC with resource roles**: Both users and resources have role memberships (`g2 = _, _`)
- **RBAC with domains/tenants**: See casbin-multitenancy.md

### ABAC (Attribute-Based Access Control)

Evaluates access based on attributes of subjects, objects, and actions rather than identity alone.

```ini
[matchers]
m = r.sub.Age > 18 && r.sub.Department == r.obj.Department
```

Casbin accesses struct/object fields via reflection. You pass actual objects (not strings) to `Enforce()`.

**ABAC attribute access works only for request elements** (`r.sub`, `r.obj`, `r.act`). Policy elements like `p.sub` cannot use ABAC attribute access because policies cannot store struct or class definitions.

**JSON parameter support**: When enabled via `EnableAcceptJsonRequest(true)`, parameters beginning with `{` or `[` are automatically parsed as JSON. Invalid JSON produces a clear error; other strings are left as-is. Performance overhead: approximately 1.1x to 1.5x.

**eval() for dynamic rules**: Policies can contain expressions evaluated at enforcement time:
```ini
[matchers]
m = eval(p.sub_rule) && r.obj == p.obj && r.act == p.act
```
Policy:
```csv
p, r.sub.Age > 18, /data1, read
p, r.sub.Age < 60, /data2, write
```

**Security note**: eval() executes arbitrary expressions from policy strings. If policies are user-controlled or loaded from untrusted sources, this is a potential injection vector.

### RESTful

Supports URL path patterns and HTTP methods.

```ini
[matchers]
m = r.sub == p.sub && keyMatch(r.obj, p.obj) && r.act == p.act
```

Uses keyMatch functions (keyMatch, keyMatch2, etc.) for URL path matching. See casbin-matchers.md for details on each function.

### Deny-Override

Both allow and deny policies operate simultaneously, with denials taking precedence.

```ini
[policy_definition]
p = sub, obj, act, eft

[policy_effect]
e = some(where (p.eft == allow)) && !some(where (p.eft == deny))
```

**Security-critical behavior**: This effect expression requires at least one allow AND zero denies. If ANY matched policy has `eft=deny`, the entire request is denied regardless of how many allow policies match.

### Priority Model

Policy rules follow ordered evaluation. The first matching rule determines the outcome (like firewall rules).

```ini
[policy_effect]
e = priority(p.eft) || deny
```

Three priority approaches:

1. **Implicit priority (policy order)**: First policy listed has highest priority. Simple but fragile -- reordering policies changes authorization behavior.

2. **Explicit priority (numeric field)**: Lower number = higher priority. Non-numeric values get lowest priority.
   ```ini
   [policy_definition]
   p = priority, sub, obj, act, eft
   ```
   **Critical limitation**: Only `AddPolicy` and `AddPolicies` respect explicit priority. Do not change the priority field via `UpdatePolicy`.

3. **Subject hierarchy priority**: Uses `subjectPriority(p.eft)`. Leaf roles (end users) have higher priority than inner roles. Hierarchies must form trees, not graphs. Multi-role users must exist at identical depths. Same-level ties resolve by policy order.

### Formal Security Models

- **BLP (Bell-LaPadula)**: Mathematical framework for security labels (confidentiality)
- **Biba**: Integrity constraints model
- **LBAC**: Lattice-based access control combining confidentiality and integrity

### Other Models

- **PBAC (Policy-Based)**: Dynamic, context-aware authorization decisions
- **OrBAC**: Extends RBAC with abstraction layers for multi-organization policies
- **UCON (Usage Control)**: Ongoing authorization with mutable attributes, obligations, and conditions
- **IP Match**: Network-level access control via IP/CIDR matching

## Model Syntax Rules

1. Lines beginning with `#` are comments
2. Every model MUST have: `[request_definition]`, `[policy_definition]`, `[policy_effect]`, `[matchers]`
3. RBAC models add `[role_definition]`; RBAC with constraints adds `[constraint_definition]`
4. Policy definitions support multiple instances (p, p2, p3) with different shapes
5. Multiple matcher/effect/request sets can be defined with numeric suffixes (m2, e2, r2)
6. Policy rule elements are always treated as strings
7. When `eft` is omitted from policy definition, matching policies default to "allow"
8. Expression evaluators are language-specific (govaluate for Go, AviatorScript for Java, etc.)
