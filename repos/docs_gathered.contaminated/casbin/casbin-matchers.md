# Casbin Matcher Functions and Built-ins

Sources:
- https://casbin.apache.org/docs/function
- https://github.com/casbin/casbin/issues/909 (KeyMatch5 for query params)
- https://github.com/casbin/node-casbin/issues/66 (keyMatch matching unwanted policies)
- https://github.com/casbin/casbin/issues/694 (case sensitivity)

## Overview

Casbin matchers use expression evaluation to compare request parameters against policy rules. The matcher is a boolean expression that can use equality operators, logical operators, arithmetic, built-in functions, and custom functions. Matchers are evaluated using language-specific expression engines (govaluate for Go, AviatorScript for Java, expression-eval for Node.js, simpleeval for Python).

## Built-in Key-Matching Functions

All key-matching functions have the signature:
```
bool function_name(string url, string pattern)
```

### keyMatch

Matches URL paths where `*` is a wildcard that matches everything.

- `/alice_data/resource1` matches `/alice_data/*` -> true
- **CRITICAL LIMITATION**: keyMatch assumes `*` is the LAST character of the pattern string. It is NOT designed to handle patterns like `alice:*:B` where the wildcard is in the middle. When `*` appears mid-pattern, keyMatch will match more broadly than expected.
- This was confirmed as a design limitation in GitHub Issue #66: keyMatch with non-terminal wildcards matches policies it shouldn't.

### keyMatch2

Matches URL paths using colon notation for named parameters.

- `/alice_data/resource1` matches `/alice_data/:resource` -> true
- The `:param` captures a single path segment (does not cross `/` boundaries)

### keyMatch3

Matches URL paths using curly brace notation.

- `/alice_data/resource1` matches `/alice_data/{resource}` -> true
- Similar to keyMatch2 but uses `{param}` syntax instead of `:param`

### keyMatch4

Handles repeated named parameters in paths.

- `/alice_data/123/book/123` matches `/alice_data/{id}/book/{id}` -> true (same id must match)
- `/alice_data/123/book/456` matches `/alice_data/{id}/book/{id}` -> false (different ids)
- Enforces consistency: the same parameter name must have the same value in all positions

### keyMatch5

Supports both `{}` parameters and `*` wildcards, with **query string handling**.

- Ignores everything after `?` in URLs for matching purposes
- Designed for RESTful APIs where query parameters vary but the resource path is consistent
- Added in response to Issue #909 where existing matchers couldn't handle URLs like `/path/?status=1&type=2`

### regexMatch

Matches using standard regular expressions.

- `regexMatch("/alice_data/resource1", "/alice_data/.*")` -> true
- Uses the host language's regex engine
- Full regex syntax supported

### ipMatch

Matches IP addresses against CIDR notation or specific IPs.

- `ipMatch("192.168.2.123", "192.168.2.0/24")` -> true
- `ipMatch("192.168.2.123", "192.168.2.123")` -> true (exact match)
- Supports IPv4 CIDR notation

### globMatch

Matches paths using glob patterns.

- `globMatch("/alice_data/resource1", "/alice_data/*")` -> true
- Uses glob syntax (not regex) -- `*` matches within a single path segment, `**` matches across segments
- Added in response to Issue #396

## Key-Extraction Functions

These functions extract named values from URL patterns:

```
string KeyGet(string url, string pattern)
string KeyGet2(string url, string pattern, string key_name)
string KeyGet3(string url, string pattern, string key_name)
```

Examples:
- `KeyGet("/resource1/action", "/*")` returns `"resource1/action"`
- `KeyGet2("/resource1/action", "/:res/action", "res")` returns `"resource1"`
- `KeyGet3("/resource1_admin/action", "/{res}_admin/*", "res")` returns `"resource1"`

These are used internally for role pattern matching and can be used in custom matchers.

## The `in` Operator

Checks array membership in matchers:

```ini
[matchers]
m = r.sub.Name in (r.obj.Admins)
```

This checks if the subject's Name field exists in the object's Admins array.

## The `g()` Function (RBAC)

Resolves role membership:

```ini
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act
```

`g(user, role)` returns true if the user has the specified role (directly or through hierarchy). For domain RBAC: `g(user, role, domain)`.

## The `eval()` Function (ABAC)

Evaluates expressions stored in policy fields:

```ini
m = eval(p.sub_rule) && r.obj == p.obj && r.act == p.act
```

**Security concern**: eval() executes arbitrary expressions from policy strings. If policies are loaded from untrusted sources, this is a code injection vector.

## Custom Function Registration

Users can define custom matcher functions:

1. Create a function with required arguments returning `bool`
2. Wrap it as `func(...interface{}) (interface{}, error)` (Go)
3. Register via `e.AddFunction("my_func", MyFuncWrapper)`
4. Use in matchers: `m = r.sub == p.sub && my_func(r.obj, p.obj) && r.act == p.act`

## Security-Relevant Edge Cases

### Case Sensitivity
All string comparisons in matchers are case-sensitive by default. `alice` and `ALICE` are different subjects. This can lead to authorization bypass if:
- The application normalizes case at some points but not others
- Users can register with different casings of the same name
- Workaround: Use custom functions like `toLower()` in matchers, or pre-process all Enforce() arguments to a canonical form

### Wildcard Position in keyMatch
keyMatch only works correctly when `*` is the terminal character. Mid-pattern wildcards cause over-matching, potentially granting unintended access.

### Query Parameter Handling
Before keyMatch5, none of the built-in matchers handled query parameters. URLs like `/path?admin=true` and `/path?user=normal` would need to be handled carefully to avoid authorization bypass through query parameter manipulation.

### Expression Evaluator Differences
Different language implementations use different expression engines. Behavior may differ across Go, Java, Node.js, and Python implementations of Casbin for the same model definition, especially for edge cases in expression evaluation.

### Matcher Short-Circuiting
When using `some(where (p.eft == allow))` with only allow rules, the engine stops evaluation upon finding the first match. This is a performance optimization but means the order of policy rules can affect which policy "wins" in priority models.

### Performance and Evaluation Order
Place computationally cheaper conditions first in matchers. The documented test case showed that reordering to evaluate object matching before role lookups (g() calls) reduced execution time from 6+ seconds to ~7 milliseconds. This suggests g() calls can be expensive and may involve database lookups in some configurations.
