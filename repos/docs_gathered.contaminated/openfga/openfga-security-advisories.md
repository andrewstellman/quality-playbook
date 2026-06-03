# OpenFGA Published Security Advisories (GHSA / CVE)

Sources:
- https://github.com/openfga/openfga/security/advisories
- https://github.com/advisories?query=openfga
- https://github.com/openfga/openfga/security/advisories/GHSA-95x7-mh78-7w2r
- https://github.com/advisories/GHSA-vj4m-83m8-xpw5
- https://github.com/openfga/openfga/security/advisories/GHSA-8cph-m685-6v6r
- https://github.com/advisories/GHSA-3f6g-m4hr-59h8
- https://github.com/openfga/openfga/security/advisories/GHSA-32q6-rr98-cjqv
- https://github.com/advisories/GHSA-g4v5-6f5p-m38j
- https://github.com/advisories/GHSA-c72g-53hw-82q7
- https://github.com/openfga/openfga/security/advisories/GHSA-mgh9-4mwp-fg55
- https://github.com/openfga/openfga/security/advisories/GHSA-jq9f-gm9w-rwm9

## Summary

Unlike many libraries, the OpenFGA core engine has a **substantial published advisory history** — nine GitHub Security Advisories (each with a CVE), almost all categorized as **authorization bypass** or **improper policy enforcement** (CWE-285 / CWE-863). The pattern is consistent and instructive: the bugs are not in the storage or transport layer but in the **graph-evaluation engine**, specifically in how it evaluates particular *combinations* of rewrite operators (exclusion `but not`, intersection `and`, tuple-to-userset `from`), usersets, type-bound public access (`*`), conditions, and contextual tuples. The one exception (CVE-2022-39340) is an unauthenticated-endpoint information disclosure.

All nine are listed below, every ID verified against a live GitHub advisory URL.

---

## CVE-2022-39340 (GHSA-95x7-mh78-7w2r): Information Disclosure on `streamed-list-objects`

**Status**: Fixed in v0.2.4
**Impact**: Disclosure of objects in a store to unauthenticated callers
**Category**: Missing authentication on an endpoint (information disclosure)
**Affected**: `<= 0.2.3` | **Fixed**: `0.2.4` | **Severity**: Moderate

### Problem
During an internal security assessment, the `streamed-list-objects` endpoint was found to **not validate the authorization header**, resulting in disclosure of objects in the store. Affects deployments exposing the OpenFGA service to the internet.

### Expected / Actual
- **Expected**: every data-returning endpoint enforces the configured server auth (preshared key / OIDC).
- **Actual**: `streamed-list-objects` answered without checking the auth header, so an unauthenticated network caller could enumerate objects.

---

## CVE-2022-39341 (GHSA-vj4m-83m8-xpw5): Authorization Bypass via Tupleset Wildcard

**Status**: Fixed in v0.2.4
**Impact**: Authorization bypass
**Category**: Rewrite-evaluation correctness — wildcard on a tupleset relation
**Affected**: `<= 0.2.3` | **Fixed**: `0.2.4` | **Severity**: Moderate (CVSS 5.9) | CWE-285, CWE-863

### Problem
A tuple with a **wildcard (`*`) assigned to a tupleset relation** (the right-hand side of a `from` statement) caused an authorization bypass. The fix forbids wildcards on tupleset relations, so the update is **not backward compatible** with any model that used a wildcard on a tupleset relation.

### Root cause / Reproduction
- Model uses `X from Y` where `Y` (the tupleset) has a tuple with `*` as the user.
- The wildcard on the tupleset side was treated as matching, expanding the intermediate-object set incorrectly and granting access that the model did not intend.
- Fix commit: `b466769`.

---

## CVE-2024-31452 (GHSA-8cph-m685-6v6r): Authorization Bypass with Intersection/Exclusion + Cyclical Relationships

**Status**: Fixed in v1.5.3
**Impact**: Authorization bypass on Check and ListObjects
**Category**: Rewrite-evaluation correctness — `and` / `but not` over cyclic relationships
**Affected**: `> 1.5.0, < 1.5.3` | **Fixed**: `1.5.3` | **Severity**: High

### Problem
End users are "very likely affected if your model involves exclusion (e.g. `a but not b`) or intersection (e.g. `a and b`) and you have any cyclical relationships." Under those conditions, Check/ListObjects could return an incorrect decision (authorization bypass). Backward compatible fix.

### Expected / Actual
- **Expected**: intersection/exclusion evaluate to correct set-math results even when relationships form cycles.
- **Actual**: certain cyclic models with `and`/`but not` produced wrong (over-permissive) results.

---

## CVE-2024-42473 (GHSA-3f6g-m4hr-59h8): Authorization Bypass with `but not` + `from` + Userset

**Status**: Fixed in v1.5.9 (Helm 0.2.12)
**Impact**: Authorization bypass on Check
**Category**: Rewrite-evaluation correctness — exclusion combined with tuple-to-userset and a userset
**Affected**: `>= 1.5.7, < 1.5.9` (i.e. v1.5.7, v1.5.8) | **Fixed**: `1.5.9` | **Severity**: High (CVSS 8.2) | CWE-285, CWE-863

### Problem
OpenFGA v1.5.7 and v1.5.8 are vulnerable to authorization bypass when calling Check with a model that uses **`but not` and `from` expressions and a userset**. CVSS vector shows **Integrity: High** (the engine returns an incorrect "allowed" where it should deny). Backward compatible fix; upgrade urged "as soon as possible."

---

## CVE-2024-56323 (GHSA-32q6-rr98-cjqv): Authorization Bypass with Conditions + Caching + Contextual Tuples

**Status**: Fixed in v1.8.3 (Helm 0.2.19)
**Impact**: Authorization bypass on Check and ListObjects
**Category**: Caching / contextual-tuple + condition evaluation
**Affected**: `>= 1.3.8, < 1.8.3` | **Fixed**: `1.8.3` | **Severity**: Moderate (CVSS 5.8)

### Problem (all three preconditions required)
1. Calling Check or ListObjects with a model that uses **conditions**, **and**
2. OpenFGA configured with **caching enabled** (`OPENFGA_CHECK_QUERY_CACHE_ENABLED`), **and**
3. The Check/ListObjects call contains **contextual tuples that include conditions**.

Under these conditions the engine could return an incorrect (over-permissive) decision. This is the canonical "cache key did not properly account for contextual tuples carrying conditions" failure. Backward compatible fix.

---

## CVE-2025-25196 (GHSA-g4v5-6f5p-m38j): Authorization Bypass — Public Access + Userset of Same Type

**Status**: Fixed in v1.8.5 (Helm 0.2.22)
**Impact**: Authorization bypass on Check and ListObjects
**Category**: Rewrite-evaluation correctness — type-bound public access vs userset, same type
**Affected**: `<= 1.8.4` | **Fixed**: `1.8.5` | **Severity**: Moderate (CVSS 5.8) | CWE-285

### Problem (all preconditions required)
- A relation **directly assignable to both type-bound public access (`type:*`) AND a userset of the same type**, and
- A type-bound public access tuple is assigned to an object, and
- A userset tuple is **not** assigned to the same object, and
- The Check request's `user` field is a **userset** that has the same type as the public-access tuple's user type.

Under this exact shape the engine wrongly resolved the userset request against the public-access tuple, returning `allowed=true` incorrectly. Fix commit: `0aee4f4`. Backward compatible.

---

## CVE-2025-48371 (GHSA-c72g-53hw-82q7): Authorization Bypass — Public Access + Userset with Contextual Tuples

**Status**: Fixed in v1.8.13 (Helm 0.2.31)
**Impact**: Authorization bypass on Check and ListObjects
**Category**: Contextual-tuple type filtering vs public-access/userset
**Affected**: `>= 1.8.0, < 1.8.13` | **Fixed**: `1.8.13` | **Severity**: Moderate (CVSS 5.8) | CWE-285 (Improper Authorization)

### Problem (all preconditions required)
- Model has a relation **directly assignable by both type-bound public access AND a userset** with the same type, and
- Check/ListObjects queries carry **contextual tuples** for that relation, and
- Those contextual tuples' `user` field is a **userset**, and
- Type-bound public-access tuples are **not** assigned to the relation.

### Root cause
The `CombinedTupleReader`'s `ReadUsersetTuples` did not filter contextual tuples by `allowedUserTypeRestrictions`, so **unrelated contextual tuples leaked into the userset evaluation** and produced incorrect (over-permissive) results. Fix: filter context tuples by type restrictions for `ReadUsersetTuples`. Fix commit: `e5960d4`. Reported by @udyvish. Go vuln: GO-2025-3707. Backward compatible.

### Why it matters
This is the clearest illustration of the **type-restrictions-gate-contextual-tuples** invariant: a caller-supplied contextual tuple of the wrong shape was allowed to influence the decision.

---

## CVE-2025-55213 (GHSA-mgh9-4mwp-fg55): Improper Policy Enforcement — >1 Directly-Assignable Userset of Same Type

**Status**: Fixed in v1.9.5 (Helm 0.2.42)
**Impact**: Improper policy enforcement on Check and ListObjects
**Category**: Rewrite-evaluation correctness — "weight 2 optimization" with multiple usersets
**Affected**: `>= 1.9.3, < 1.9.5` (v1.9.3, v1.9.4) | **Fixed**: `1.9.5` | **Severity**: Moderate (CVSS 5.8)

### Problem (all preconditions required)
- Model has a relation **directly assignable by more than one userset of the same type**, and
- Check/ListObjects queries rely on that relation, and
- Userset tuples are assigned to that relation.

### Root cause / Fix
A check optimization ("weight 2 optimization") misbehaved when more than one directly-assignable userset of the same type existed. v1.9.5 **does not run the weight-2 optimization** for cases with more than one directly-assignable userset. **Workaround**: downgrade to v1.9.2 with `enable-check-optimizations` removed from `OPENFGA_EXPERIMENTALS`. Reported by Dominic Harries (@domharries) and rrozza-apolitical. Backward compatible.

---

## CVE-2026-24851 (GHSA-jq9f-gm9w-rwm9): Improper Policy Enforcement — Public + Non-Public Tuples and Lexicographic Object Ordering

**Status**: Fixed in v1.11.3 (Helm 0.2.52)
**Impact**: Improper policy enforcement on Check
**Category**: Rewrite-evaluation correctness — public-access + non-public-access tuples, object-ID ordering
**Affected**: `>= 1.8.5, <= 1.11.2` | **Fixed**: `1.11.3` | **Severity**: Moderate (CVSS 5.8)

### Problem (all preconditions required)
- Model has a relation **directly assignable by type-bound public access AND by type-bound non-public access**, and
- A tuple assigned for the relation that is type-bound public access, and
- A tuple for the **same object + relation** that is **not** public access, and
- A tuple for a **different object whose object ID is lexicographically larger**, with the same user and relation, that is not public access.

Under this configuration the engine mis-enforced the policy (incorrect decision). **No workaround**; upgrade to v1.11.3. Backward compatible. Published Feb 5, 2026.

---

## Cross-Cutting Pattern (for auditors)

- **8 of 9 are authorization-bypass / improper-policy-enforcement in the graph-evaluation engine.** The recurring trigger is a *combination* of features: tuple-to-userset (`from`), usersets, type-bound public access (`*`), exclusion (`but not`), intersection (`and`), conditions, and contextual tuples. Edge-case interactions between these — especially around **type restrictions on usersets/contextual tuples** and **optimizations that short-circuit evaluation** — are where the bugs live.
- **Type-restriction filtering of usersets and contextual tuples** is implicated in CVE-2025-48371, CVE-2025-25196, and CVE-2026-24851.
- **Performance optimizations are a recurring source of correctness bugs** (CVE-2025-55213 was the "weight 2 optimization"; the fix disables it for the problematic case). An optimization that prunes the search must never prune a path that would have changed the answer.
- **Caching + contextual tuples + conditions** produced CVE-2024-56323 — reinforcing the consistency/cache invariants in `openfga-check-listobjects-consistency.md`.
- **Severity skews Moderate (CVSS 5.8)** because most require a specific model shape and specific tuple/contextual-tuple assignments, but the subsequent-system impact is consistently rated High on confidentiality/integrity (it is, after all, an authorization decision being subverted).
