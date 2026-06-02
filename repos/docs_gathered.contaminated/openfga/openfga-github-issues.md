# OpenFGA GitHub Issues Bearing on Correctness and Security

Sources:
- https://github.com/openfga/openfga/issues
- https://github.com/openfga/openfga/issues/3099
- https://github.com/openfga/openfga/issues/3094
- https://github.com/openfga/openfga/issues/3088
- https://github.com/openfga/openfga/issues/3076
- https://github.com/openfga/openfga/issues/3063
- https://github.com/openfga/openfga/issues/1511
- https://github.com/openfga/openfga/issues/1961
- https://github.com/openfga/openfga/commit/e5960d4eba92b723de8ff3a5346a07f50c1379ca

These are open and notable issues that bear on authorization correctness, ListObjects behavior, conditions/ABAC evaluation, consistency/caching, and key rotation. Status reflects the openfga/openfga issue tracker as gathered (open issues showed `is:issue state:open`). Several published advisories (see `openfga-security-advisories.md`) originated as bug reports of exactly these kinds.

---

## Issue #3099: OIDC JWKS cache misses key-rotation events (RefreshUnknownKID not enabled)

**Number**: #3099
**Status**: Open (opened Apr 30, 2026)
**Impact**: Authentication failures / potential acceptance of tokens signed by stale keys when the IdP rotates signing keys
**Category**: Server authentication (OIDC/JWT validation)

### Problem
The JWKS (JSON Web Key Set) cache used to validate OIDC bearer tokens does not enable `RefreshUnknownKID`. When the identity provider rotates its signing keys, a token signed with a new key ID (`kid`) the cache hasn't seen will not trigger a refresh, so OpenFGA cannot validate it (and, depending on cache behavior, may keep trusting stale key material). Because OIDC is one of OpenFGA's server-auth modes, correct JWKS rotation handling is part of the server's authentication trust boundary.

---

## Issue #3094: Tuple-reader fan-out under dual-direction recursive inheritance

**Number**: #3094
**Status**: Open, labeled **bug** (opened Apr 28, 2026)
**Impact**: Performance blow-up (and potential incorrect/incomplete results under deadline) for recursive models
**Category**: Tuple-to-userset (`from`) evaluation / ListObjects correctness

### Problem
With **dual-direction recursive inheritance** — e.g. a relation defined as `X from parent` *and* `X from child` on the same type — the tuple reader fans out excessively. This is the tuple-to-userset traversal interacting with bidirectional recursion. Beyond performance, fan-out that hits a deadline can yield partial results (see #1961), and recursive `from` traversal is the same machinery implicated in several `from`-related advisories.

---

## Issue #3088: Conditions using attributes from relationships

**Number**: #3088
**Status**: Open, labeled **enhancement** (opened Apr 27, 2026)
**Impact**: Feature gap in ABAC expressiveness (not a bug, but defines a boundary of what conditions can safely reference)
**Category**: Conditions / ABAC

### Problem
Request to let CEL conditions reference attributes drawn from *relationships* (stored tuple data) rather than only from request context and tuple-bound parameters. Relevant to auditors because it clarifies the current invariant: conditions are evaluated over request context + tuple-bound context only, and broadening that surface would expand the attack surface for condition evaluation.

---

## Issue #3076: Multi-Type ListObjects / "list all accessible objects for a user"

**Number**: #3076
**Status**: Open, labeled **enhancement** (opened Apr 20, 2026)
**Impact**: Callers hand-roll multi-type enumeration, increasing the chance of incomplete authorization views
**Category**: ListObjects API surface

### Problem
ListObjects is single-type (you ask for objects of one type). There is no built-in "list every object of every type this user can access." Applications that need this compose multiple ListObjects calls, which is error-prone and interacts with the partial-result/deadline behavior of ListObjects (#1961).

---

## Issue #3063: `mergePropertiesToContext` — request-context fields shadow subject/resource/action properties

**Number**: #3063
**Status**: Open, labeled **bug** (opened Apr 13, 2026)
**Impact**: Condition (ABAC) evaluation against a corrupted context -> potentially incorrect authorization decisions
**Category**: Conditions / context merging

### Problem
When building the CEL evaluation context, `mergePropertiesToContext` lets **request-context fields incorrectly shadow subject/resource/action properties**. Because conditions gate relationships based on this merged context, a request that supplies a context field with a colliding name can override an intended subject/resource/action property and change how a condition evaluates. This is a live example of the "conditions can only restrict, never be subverted by attacker-influenced context" invariant being threatened by context-merge precedence.

### Expected / Actual
- **Expected**: subject/resource/action properties are authoritative and cannot be overridden by free-form request context.
- **Actual**: request-context fields can shadow them, so a crafted context could alter condition outcomes.

---

## Issue #1511: ListObjects should ignore conditional-tuple evaluation errors once a result is already determined

**Number**: #1511
**Status**: Notable (closed/addressed) — fix landed to avoid erroring out
**Impact**: Spurious errors (or inconsistent results) from ListObjects when a conditional tuple errors even though the object's membership was already decided
**Category**: ListObjects + conditions evaluation

### Problem
In ListObjects, if a Conditional Relationship Tuple raised an evaluation error, the call could fail (or skew results) even when a **determinate result for that object had already been determined** by another path. The fix avoids returning an error in ListObjects for conditional-tuple evaluation errors when the object's result is already settled. The security-relevant nuance: error handling in condition evaluation must "fail closed" for the *gate* but must not let an unrelated erroring condition either grant access or mask a correct denial.

---

## Issue #1961: ListObjects / ListUsers should inform the user when the deadline is hit

**Number**: #1961
**Status**: Notable
**Impact**: Callers cannot distinguish a **complete** result from a **truncated** one, leading to wrong allow/deny conclusions
**Category**: ListObjects / ListUsers completeness

### Problem
When ListObjects or ListUsers hits the request deadline, it returns a **partial** result without clearly signaling truncation. A caller that treats "object absent from the list" as "user is denied" will wrongly deny access (or, when the list is used to build an allow-set, expose/hide the wrong objects) whenever the truncation — not a real denial — is the cause. Per-object security decisions should use Check rather than inferring denial from ListObjects absence.

### Expected / Actual
- **Expected**: a truncated ListObjects/ListUsers result is clearly distinguishable from a complete one.
- **Actual**: the deadline-truncated result looks like a complete result.

---

## Cross-Cutting Notes for Auditors

- **ListObjects is best-effort under deadline pressure** (#1961, #3076, #3094): never infer a denial from an object's absence in a ListObjects response; use Check for authoritative per-object decisions.
- **Condition/context handling is an active correctness surface** (#3063, #3088, #1511): context merging, error handling, and what conditions may reference all affect whether the ABAC gate behaves as intended. #3063 in particular is a path by which attacker-influenced request context could alter a decision.
- **`from` (tuple-to-userset) recursion drives both performance and correctness risk** (#3094), echoing the `from`-related advisories CVE-2024-42473 and CVE-2022-39341.
- **OIDC key rotation** (#3099) is part of the server-auth trust boundary; stale JWKS handling can break (or weaken) token validation.
- Many published advisories began as bug reports of this exact character — the issue tracker is the leading indicator for the next evaluation-edge-case advisory.
