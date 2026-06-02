# OpenFGA Issue Tracker Themes: Security, Authz, Consistency, Performance

## Sources

- https://github.com/openfga/openfga/issues
- https://github.com/openfga/openfga/issues/3099
- https://github.com/openfga/openfga/issues/3094
- https://github.com/openfga/openfga/issues/3088
- https://github.com/openfga/openfga/issues/3076
- https://github.com/openfga/openfga/issues/3063
- https://github.com/openfga/openfga/issues/2598
- https://github.com/openfga/openfga/issues/1961
- https://github.com/openfga/openfga/issues/1511
- https://github.com/openfga/openfga/pull/2779
- https://github.com/openfga/openfga/pull/2791

## Context

This document surfaces six themes recurring in the openfga/openfga issue tracker that an auditor should know are *live* concerns — not yet advisories, but active enough that maintainers have engaged with them or labeled them as bugs. Several published advisories began life as exactly these kinds of bug reports; the tracker is the leading indicator for the next evaluation-edge-case advisory. Each theme cites a representative issue, captures the failure shape, and connects it to the broader invariants from `04_invariants.md`.

---

## Theme 1: Cache invalidation correctness and ListObjects fan-out

**Representative work:** PR #2779 (merged & reverted), PR #2791 (revert), prior #2598 (Postgres metric register/close hygiene around cache controller behaviour).

**Shape.** The check-query cache is correct only when the CacheController is actively polling the changelog *and* the cache is keyed and gated on every dimension that can change the answer. When `LastInvalidationTime` defaults to the Go zero value (no controller, or controller hasn't polled yet), the validity check `res.LastModified.After(LastInvalidationTime)` returns `true` for every entry — every cached `allowed` is considered fresh forever (modulo TTL). PR #2779 tightened the gate; PR #2791 reverted because the tightening made the cache effectively unused in deployments without a controller.

**Why it matters.** Revocation-sensitive Checks under `MINIMIZE_LATENCY` can be served a stale `allowed=true` long after the granting tuple was deleted. The ListObjects fan-out is doubly affected because PR #2779's revert also removed the `WithCheckCommandCache` wiring in `list_objects.go` — fan-out Checks now don't even participate in the same cache pipeline as top-level Checks.

**Invariants implicated.** "Fan-out Checks must use the same cache pipeline as top-level Checks." "`LastInvalidationTime == zero` must not mean 'all cached entries valid.'" "`HIGHER_CONSISTENCY` must bypass the cache on every code path."

**Prior advisory in the same family.** CVE-2024-56323 — cache key didn't include contextual-tuple condition data; fix tightened the key.

---

## Theme 2: Type-restriction enforcement on contextual tuples and usersets

**Representative work:** CVE-2025-48371 (now closed; fix commit `e5960d4`), CVE-2025-25196 (closed; fix commit `0aee4f4`), CVE-2026-24851 (closed; fixed v1.11.3), ongoing maintainer attention to userset evaluation paths.

**Shape.** `directly_related_user_types` is the model-declared constraint on which tuple shapes (concrete type, userset, wildcard, conditioned type) may directly satisfy a relation. Multiple advisories arose from this filter being applied at one read path but not another — most pointedly, `CombinedTupleReader.ReadUsersetTuples` did not filter contextual tuples by `allowedUserTypeRestrictions`, so an attacker-supplied contextual tuple of an unallowed shape could flip a decision.

**Why it matters.** Type restrictions are the model's primary mechanism for preventing caller-supplied data (contextual tuples) from injecting unauthorized grants. A code path that skips this filter is the most common shape of OpenFGA's published bypasses.

**Invariants implicated.** "Contextual tuples must be filtered by type restrictions on every read path, including internal usersets." "Type-bound public access and direct usersets of the same type must not collide in evaluation."

**Audit guidance.** Wherever the engine reads tuples — stored or contextual — the read must consult the relation's `directly_related_user_types` and drop tuples that don't match. The audit can grep for all `ReadUsersetTuples`-shaped paths and verify each filters contextual tuples.

---

## Theme 3: Condition / CEL context merging and ABAC integrity

**Representative work:** Issue #3063 (`mergePropertiesToContext` lets request-context fields shadow subject/resource/action properties — labeled `bug`, open as of late April 2026), Issue #1511 (closed; ListObjects should not error out when a conditional-tuple eval error occurs but the result is already determined), Issue #3088 (enhancement: let conditions reference attributes from relationships).

**Shape.** Conditions evaluate over a merged context: request context + tuple-bound parameters + (per #3088 proposal) potentially relationship-derived attributes. When the merge precedence is wrong, request-context fields can shadow authoritative subject/resource/action properties, and a crafted context can change what a condition evaluates to. When error handling is wrong, a conditional-tuple evaluation error can either fail open (incorrect grant) or override a correctly-determined result.

**Why it matters.** Conditions are advertised as "can only restrict, never grant." Any pathway by which condition context is corruptible by caller-influenced data or by which a condition error leads to over-grant violates that contract.

**Invariants implicated.** "Conditions can only restrict, never grant." "Condition context cannot override subject/resource/action properties." "A conditional tuple evaluation error must not falsely grant."

**Audit guidance.** Trace context construction for CEL evaluation; verify subject/resource/action properties are merged with higher precedence than free-form request fields; verify error paths fail closed for the gate.

---

## Theme 4: ListObjects / ListUsers completeness under deadline

**Representative work:** Issue #1961 (notable; "ListObjects/ListUsers should inform the user when the deadline is hit"), Issue #3076 (enhancement: multi-type ListObjects; callers hand-roll the multi-type pattern, increasing the chance of incomplete authorization views), Issue #3094 (`bug`; dual-direction recursive inheritance causes tuple-reader fan-out blow-up — performance, but also a path to deadline truncation).

**Shape.** ListObjects/ListUsers are bounded by request deadline. When the deadline is hit, the result is truncated, but the response shape doesn't distinguish truncated from complete. A caller that treats "object absent from the list" as "denied" makes a security-relevant inference from a performance event.

**Why it matters.** This is a contract / UX problem with security consequences. The engine cannot prevent truncation (it's a real-world deadline), but it can and should communicate truncation. Until it does, integrators must use Check for per-object decisions.

**Invariants implicated.** "A ListObjects truncation is not a denial." "A truncated ListObjects/ListUsers result should be distinguishable from a complete result." "Performance-driven recursion blow-up must not silently corrupt completeness."

**Audit guidance.** Verify the engine never *internally* infers denial from ListObjects absence (e.g., in fan-out logic). External callers' responsibility to use Check is documentation, but internal callers (other engine code) must not make the same mistake.

---

## Theme 5: Server authentication and OIDC key rotation

**Representative work:** Issue #3099 (open; OIDC JWKS cache does not enable `RefreshUnknownKID`). Also the historical CVE-2022-39340 (`streamed-list-objects` skipped auth — closed years ago).

**Shape.** OpenFGA supports OIDC/JWT for server authentication. The JWKS cache used to validate tokens must support identity-provider key rotation. Without `RefreshUnknownKID`, a token signed with a `kid` the cache hasn't seen will not trigger a JWKS refresh — depending on cache behavior, either the token is rejected (availability hit during rotation) or, worse, stale key material is trusted.

**Why it matters.** This is the server's authentication trust boundary. OIDC is one of the supported modes; if rotation handling is broken, deployments using OIDC accept the wrong tokens (or reject the right ones) during rotation windows.

**Invariants implicated.** "Every data-returning endpoint enforces server auth." "OIDC JWKS handling must support key rotation."

**Audit guidance.** Examine the JWKS configuration; verify `RefreshUnknownKID` is enabled and the cache TTL/refresh behavior matches the IdP's rotation cadence.

---

## Theme 6: Performance optimizations that prune evaluation

**Representative work:** CVE-2025-55213 (closed; "weight 2 optimization" misbehaved for >1 directly-assignable userset of same type), DeepWiki performance-optimizations page (community-generated), and the philosophical position implicit in PR #2779/#2791 — every optimization is a place a correctness bug can hide.

**Shape.** The graph engine has multiple optimizations that prune the search space when certain shape conditions hold. Each is a place where "the optimization assumes X about the model, X turns out not always to hold, the optimization changes the answer." The weight-2 optimization is the worked example; the cache validity gate in PR #2779 is the same family of reasoning applied to caching.

**Why it matters.** OpenFGA's correctness bugs cluster around the *interactions* of features and around *optimizations* that didn't anticipate certain feature combinations. An auditor reading the engine should treat every short-circuit, every "if this condition holds, we can skip X" path as a candidate divergence from set semantics.

**Invariants implicated.** "Performance optimizations must not change the set the rewrite denotes." "Decisions must equal ground-truth graph reachability."

**Audit guidance.** Enumerate every `experimentals` flag and every short-circuit path in `internal/graph/`. For each, ask: "What input shape did this assume? What input shape would break that assumption?" CVE-2025-55213 was found by exactly this reasoning.

---

## Cross-cutting takeaways for the audit

- **Issue tracker themes recur in advisories.** Each of the six themes above has at least one published CVE in the same family. The next OpenFGA advisory is likely to come from one of these surfaces.
- **The cache layer (Theme 1) is the central concern for this audit.** PR #2779/#2791 is unresolved-as-of-revert, and the ListObjects fan-out / `LastInvalidationTime.IsZero()` interaction is the named OPENFGA-2 finding.
- **Type-restriction filtering (Theme 2) and condition context (Theme 3) are the most reliable bug-shape predictors.** When an audit reads code that handles contextual tuples or condition context, applying the relevant invariants from `04_invariants.md` is the highest-yield discipline.
- **ListObjects completeness (Theme 4) connects to caching:** a ListObjects under `MINIMIZE_LATENCY` with stale cache entries could return a fan-out result that doesn't match Check for the same `(user, relation, object)` — both because the cache is stale *and* because the result might be truncated. The two failures compound.
