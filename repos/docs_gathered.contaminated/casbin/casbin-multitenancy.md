# Casbin Multi-Tenancy / Domain RBAC

Sources:
- https://casbin.apache.org/docs/rbac-with-domains
- https://casbin.apache.org/docs/rbac
- https://casbin.apache.org/docs/syntax-for-models

## Overview

Casbin supports multi-tenant authorization through domain-based RBAC, where the same user can have different roles in different domains (tenants). This is designed for cloud systems where users operate across multiple tenants.

## Model Configuration

### Role Definition

Domain-scoped roles require a THREE-element role definition (compared to standard RBAC's two-element definition):

```ini
[role_definition]
g = _, _, _
```

The three elements are: user, role, domain.

### Request Definition

The request must include a domain parameter:

```ini
[request_definition]
r = sub, dom, obj, act
```

### Policy Definition

Policies are scoped to domains:

```ini
[policy_definition]
p = sub, dom, obj, act
```

### Matcher

The matcher MUST validate the domain and use the three-argument form of g():

```ini
[matchers]
m = g(r.sub, p.sub, r.dom) && r.dom == p.dom && r.obj == p.obj && r.act == p.act
```

**Critical detail**: The matcher must include `r.dom == p.dom` to ensure domain isolation. Without this check, a user's role in domain A could grant access to resources in domain B.

## Example

### Policies
```csv
p, admin, tenant1, data1, read
p, admin, tenant2, data2, read
```

### Role Assignments
```csv
g, alice, admin, tenant1
g, alice, user, tenant2
```

### Behavior
- Alice has the `admin` role in `tenant1` and the `user` role in `tenant2`
- Alice CAN read `data1` in `tenant1` (she is admin there)
- Alice CANNOT read `data2` in `tenant2` (she is only a user, not admin, in tenant2)
- Roles are completely isolated between domains

## Custom Domain Token Names

Instead of using `dom`, you can use alternative names for the domain field:

```ini
[request_definition]
r = sub, tenant, obj, act

[policy_definition]
p = sub, tenant, obj, act
```

For pattern matching scenarios, Casbin infers the domain token when positioned at index 1 in both request and policy definitions.

For non-standard domain placements, use `e.SetFieldIndex("p", constant.DomainIndex, index)` to ensure domain-specific APIs function correctly.

## Security-Relevant Considerations

### Domain Isolation
The domain check in the matcher (`r.dom == p.dom`) is the primary mechanism for tenant isolation. If this check is missing or incorrect:
- A user with `admin` role in `tenant1` could potentially access resources in `tenant2`
- Cross-tenant authorization bypass becomes possible

### Role Resolution Scope
The `g(r.sub, p.sub, r.dom)` call resolves roles WITHIN the specified domain. A role assignment in one domain does not propagate to another domain. This is enforced by the role manager, not the matcher itself.

### Domain-Specific API Methods
Casbin provides domain-aware API methods:
- `GetRolesForUserInDomain(user, domain)`
- `GetPermissionsForUserInDomain(user, domain)`
- `GetUsersForRoleInDomain(role, domain)`

These methods depend on correct `DomainIndex` configuration. If `SetFieldIndex` is not called correctly for non-standard domain positions, these APIs may return incorrect results.

### Pattern Matching in Domains
When using pattern matching (e.g., wildcards) in domain fields, there is a risk of matching across domains. For example, if domain patterns use `*`, a policy for `domain:*` could match any domain.

### Empty or Missing Domain
If a request is submitted without a domain value, or with an empty string, the behavior depends on the matcher expression. There is no built-in validation that the domain field is non-empty. An empty domain in a request could potentially match policies with empty domain fields.

### Inheritance Across Domains
Role hierarchy inheritance is scoped to individual domains. If alice has role1 in domain1, and role1 has role2 in domain1, then alice inherits role2 in domain1. This inheritance does NOT cross domain boundaries.
