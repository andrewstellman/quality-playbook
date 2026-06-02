# Casbin GitHub Issues Related to Authorization Bugs

Sources:
- https://github.com/casbin/casbin/issues/917
- https://github.com/casbin/casbin/issues/516
- https://github.com/casbin/casbin/issues/909
- https://github.com/casbin/casbin/issues/694
- https://github.com/casbin/casbin/issues/290
- https://github.com/apache/casbin/issues/727
- https://github.com/casbin/casbin/issues/550
- https://github.com/casbin/node-casbin/issues/66
- https://github.com/casbin/casbin.js/issues/31

## Issue #917: ABAC Rules Fail If Policy Includes Any "deny" Rows

**Status**: Fixed (PR #918)
**Impact**: Authorization incorrectly denied for legitimate ABAC requests
**Category**: Effect evaluation bug

### Problem
When using an ABAC matcher with the deny-override effect (`some(where (p.eft == allow)) && !some(where (p.eft == deny))`), ABAC authorization fails for legitimate requests if ANY unrelated deny rule exists in the policy file.

### Reproduction

Model:
```ini
[policy_effect]
e = some(where (p.eft == allow)) && !some(where (p.eft == deny))

[matchers]
m = r.sub.Superuser || r.sub.User == r.obj.Owner
```

Policy:
```csv
p, foobar, /blah, read, deny
```

Request:
```
{ User: 'alice', Superuser: true }, { Owner: 'bob'}, read
```

**Expected**: Allow (alice is superuser)
**Actual**: Deny (the unrelated deny rule for foobar causes all requests to be denied)

### Root Cause
The ABAC evaluation was not properly scoping deny effects to only those policies that actually matched the ABAC condition. The deny effect from an unrelated policy row was being counted in the effect aggregation even though the ABAC matcher never evaluated against that specific policy row.

### Security Implication
Any ABAC model using deny-override effects could have authorization decisions corrupted by the mere presence of deny rules for other subjects. This is a denial-of-service on authorization: adding a deny rule for one user could block all ABAC-evaluated access for all users.

---

## Issue #290: RBAC Deny-Override Blocks Too Broadly

**Status**: Closed (resolved with priority-based approach)
**Impact**: Deny rules applied to one role block all users
**Category**: Effect scope / model design

### Problem
With deny-override effect (`some(where (p.eft == allow)) && !some(where (p.eft == deny))`), a deny rule for the "public" role on "/admin" blocks access for ALL users, including administrators.

### Reproduction

Model matcher:
```ini
m = (g(r.sub, p.sub) || p.sub == "public") && keyMatch(r.obj, p.obj) && access(r.act, p.act)
```

Policy:
```csv
p, public, /*, read, allow
p, admins, /*, init, allow
p, public, /admin, read, deny
g, grimmy, admins
```

**Expected**: grimmy (an admin) can access /admin
**Actual**: grimmy is denied access because the deny rule for "public" on "/admin" matches (since `p.sub == "public"` is true for that policy row) and the deny vetoes the entire request.

### Root Cause
The deny-override effect is global: it checks if ANY matched policy has eft=deny. The matcher condition `p.sub == "public"` causes the deny policy row to match for ALL requests (since p.sub is always "public" for that row), and the deny effect then vetoes everything.

### Security Implication
This is a model design pitfall rather than a Casbin bug. However, it demonstrates that the interaction between OR conditions in matchers and deny effects can produce unintuitive authorization results. Security auditors should check for matchers that use `||` with `p.sub` conditions in deny-override models.

### Resolution
The recommended approach is to use priority-based effects instead of deny-override when both public and role-specific rules coexist.

---

## Issue #66 (node-casbin): keyMatch() Matches Unwanted Policies

**Status**: Closed (documented as design limitation)
**Impact**: Over-matching grants unintended access
**Category**: Matcher edge case

### Problem
keyMatch() matches more policies than expected when the wildcard `*` is NOT the terminal character in the pattern.

### Reproduction

Policies:
```csv
p, alice:*:*
p, alice:*:A
p, alice:*:B
```

Request: `alice:resource1:A`

**Expected**: Matches first two policies (alice:*:* and alice:*:A)
**Actual**: Matches ALL THREE policies, including alice:*:B

### Root Cause
keyMatch() assumes `*` is the last character of the pattern string. It is not designed to handle mid-pattern wildcards.

### Security Implication
Using keyMatch with non-terminal wildcards can cause policies to match requests they shouldn't, potentially granting access to resources that should be denied. If one of the over-matched policies has different permissions than expected, this is an authorization bypass.

### Resolution
Use regexMatch() or globMatch() for patterns with non-terminal wildcards.

---

## Issue #694: Case-Insensitive Policy Enforcement

**Status**: Closed (documented workarounds)
**Impact**: Authorization bypass through case manipulation
**Category**: String comparison edge case

### Problem
Casbin treats all policy elements as case-sensitive strings. "alice" and "ALICE" are different subjects. If an application normalizes case inconsistently (e.g., login is case-insensitive but Enforce() call uses the raw input), authorization can be bypassed.

### Example
- Policy: `g, alice, data2_admin`
- Request: `ALICE, data2, read`
- Result: false (ALICE != alice)

### Security Implication
If the authentication system treats "alice" and "ALICE" as the same user, but Casbin treats them as different, then:
1. A user who logs in as "ALICE" may bypass policies defined for "alice"
2. Conversely, a user may not receive permissions that were granted to a different casing of their name

### Workarounds
1. Pre-process all Enforce() arguments to lowercase before calling
2. Create custom matcher functions (e.g., toLower()) for case normalization
3. Enforce a canonical form at the application layer

---

## Issue #516: Performance Issue with Sequential Policy Evaluation

**Status**: Fixed (PR #515, parallel evaluation)
**Impact**: Slow authorization decisions under load
**Category**: Performance / availability

### Problem
Casbin evaluates policies sequentially, causing significant slowdowns when:
- There are many policy rules
- Matchers involve external service calls (e.g., database lookups for role resolution)
- Multiple custom functions need to execute

### Security Implication
Slow authorization evaluation can lead to:
1. Timeout-based bypass: If the application has a timeout on authorization checks, slow evaluation may cause the check to be skipped
2. Denial of service: Attackers can craft requests that maximize evaluation time
3. Race conditions: If policy changes occur during long evaluation windows

### Resolution
Parallel evaluation was added as an optional feature (disabled by default) for backward compatibility.

---

## Issue #909: KeyMatch5 for URL Query Parameter Matching

**Status**: Fixed (PR #910)
**Impact**: Authorization bypass through query parameter manipulation
**Category**: Missing matcher functionality

### Problem
Before keyMatch5, none of the built-in matchers could handle URLs with query parameters. URLs like `/path/?status=1&type=2` could not be properly matched.

### Security Implication
Without proper query parameter handling:
1. Requests to `/admin?bypass=true` and `/admin` could be evaluated differently
2. Authorization rules based on path matching could be bypassed by adding query parameters
3. The same resource accessed with different query strings could get different authorization results

### Resolution
keyMatch5 was added to ignore everything after `?` in URLs for matching purposes, supporting both `{}` parameters and `*` wildcards.

---

## Issue #727: Stopping Policy Evaluation After First Allow Match

**Status**: Closed (confirmed as existing behavior)
**Impact**: Understanding of evaluation semantics
**Category**: Evaluation behavior documentation

### Problem
A developer asked whether Casbin stops evaluating after finding the first allow match when using `some(where (p.eft == allow))`.

### Resolution
The Casbin team confirmed that with the `some(where...)` policy effect and only allow rules, the engine already stops evaluation upon finding the first match. This is a short-circuit optimization.

### Security Implication
- With allow-only effects, evaluation order matters: the first matching policy determines the result
- With deny-involved effects, ALL policies must be evaluated (no short-circuit) to check for deny matches
- If custom matchers have side effects (e.g., logging, rate limiting), short-circuit behavior means some policies may never be evaluated

---

## Issue #550: Priority Policy Element Support

**Status**: Fixed (PR #714)
**Impact**: Inability to control which policy wins when multiple match
**Category**: Policy evaluation ordering

### Problem
Without priority support, when multiple rules match a request, the evaluation order depends on the order of policies in the file/database. There was no mechanism to ensure specific rules (e.g., more precise regex patterns) take precedence.

### Security Implication
Without priority:
1. Policy ordering determines authorization outcomes, which is fragile
2. Adding a new policy rule can change the authorization result for existing requests
3. Database adapters may return policies in non-deterministic order, causing inconsistent authorization

### Resolution
Explicit priority numbering was added. Lower number = higher priority.

---

## Issue #31 (casbin.js): CasbinJsGetPermissionForUser Strips Effect Information

**Status**: Documented
**Impact**: Deny permissions become allow permissions
**Category**: API data loss

### Problem
The `CasbinJsGetPermissionForUser` API strips the `.eft` field from policy data. This means any deny permission becomes an allow permission when transmitted to the client side.

### Security Implication
If a JavaScript client uses this API to make client-side authorization decisions, all deny rules are lost. A user who should be denied access will appear to be allowed. This is a complete authorization bypass for client-side checks that rely on this API.

---

## Summary of Bug Patterns

1. **Effect scope bugs**: Deny effects applying more broadly than intended (Issues #917, #290)
2. **Matcher over-matching**: Built-in functions matching more policies than expected (Issue #66)
3. **String handling**: Case sensitivity and type coercion issues (Issue #694)
4. **Missing functionality**: Authorization bypass through unhandled input patterns (Issue #909)
5. **Data loss**: API methods stripping security-relevant fields (Issue #31)
6. **Ordering sensitivity**: Authorization decisions depending on policy order (Issues #550, #727)
7. **Performance**: Sequential evaluation enabling denial-of-service (Issue #516)
