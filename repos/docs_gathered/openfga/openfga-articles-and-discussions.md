# OpenFGA: Articles, Talks, and Community Discussions

Sources:
- https://auth0.com/blog/auth0s-openfga-open-source-fine-grained-authorization-system/
- https://auth0.com/blog/supercharge-your-authorization-system-with-openfga/
- https://auth0.com/blog/using-api-gateway-fine-grained-authorization/
- https://openfga.dev/blog
- https://openfga.dev/blog/query-consistency-options-announcement
- https://openfga.dev/blog/fine-grained-news-2025-09
- https://research.google/pubs/pub48190/ (Zanzibar paper)
- https://github.com/cncf/tag-security/issues/902
- https://www.intel.com/content/www/us/en/developer/articles/community/fine-grained-authorization-with-openfga.html
- https://deepwiki.com/openfga/openfga/1.1-high-level-architecture
- https://deepwiki.com/openfga/language/1.1-core-concepts

These go beyond the official reference docs: vendor blog posts, the foundational paper, CNCF/conference material, and third-party analyses. They are useful for understanding *how OpenFGA is meant to be used* and *where practitioners get it wrong*.

## Foundational: the Zanzibar paper

**"Zanzibar: Google's Consistent, Global Authorization System"** (Google, USENIX ATC 2019; `research.google/pubs/pub48190`). The blueprint OpenFGA implements. Key ideas OpenFGA inherits: relationship tuples as the unit of authorization, userset rewrites (union/intersection/exclusion/tuple-to-userset), namespace configs (= authorization models), and snapshot tokens ("zookies") for consistency. Reading the paper clarifies *why* OpenFGA's evaluation is a graph-reachability problem and *why* consistency is a first-class, tunable concern. OpenFGA deliberately simplifies Zanzibar's Spanner-backed external-consistency machinery into the two-mode `consistency` knob.

## Official announcement and positioning (Auth0/Okta)

**"Announcing OpenFGA — Auth0's Open Source Fine Grained Authorization System"** (auth0.com/blog). Establishes provenance: built by Auth0/Okta, donated to the CNCF (sandbox in Sept 2022, later Incubation). Frames OpenFGA as taking Zanzibar's ReBAC ideas while also serving RBAC and ABAC. Positions OpenFGA as the open engine under the hosted "Auth0 FGA"/"Okta FGA" product.

**"Supercharge Your Authorization System with FGA"** and **"Using an API Gateway with Fine-Grained Authorization"** (auth0.com/blog). Usage-pattern posts. The API-gateway post is notable for the integration trust boundary: the gateway authenticates the end user and calls Check; OpenFGA only answers the relationship question. The recurring lesson: **OpenFGA does not authenticate your users — your app/gateway does**, and passing an unauthenticated/attacker-controlled `user` to Check produces a correct-but-useless answer (an application-level bypass).

## OpenFGA project blog (openfga.dev/blog)

- **"Query Consistency Options"** (announcement post). Introduces `MINIMIZE_LATENCY` vs `HIGHER_CONSISTENCY` and the cache/replica tradeoffs detailed in `openfga-check-listobjects-consistency.md`. The practitioner takeaway emphasized in the post: use `HIGHER_CONSISTENCY` for read-after-write and revocation-sensitive checks; accept staleness only where it's safe.
- **"Fine-Grained News"** monthly digests (e.g. 2025-09). Track releases, advisories, and modeling guidance — a useful changelog of when correctness fixes shipped.

## CNCF / conference material

- **CNCF TAG-Security presentation** (`cncf/tag-security` issue #902): the security-review/presentation track for OpenFGA as a CNCF project. Relevant for the project's stated threat model and security posture.
- **KubeCon NA — "Design Patterns for Consistent Centralized Authorization"** (Jose Padilla, Okta). Centralized-PDP patterns; reinforces that the application enforces decisions and OpenFGA is the decision point.
- **All Things Open — ReBAC / Zanzibar paradigm shift** (Sam Bellen). Conceptual framing of relationship-based access control vs RBAC/ABAC.

## Third-party analyses and architecture write-ups

- **Intel Developer Zone — "Fine-Grained Authorization with OpenFGA"**: a vendor-neutral walkthrough of modeling and integration.
- **DeepWiki — OpenFGA high-level architecture and performance optimizations** (`deepwiki.com/openfga/openfga`): community-generated architecture notes covering the query resolver, the check-query cache, the CacheController changelog-polling invalidation, and the storage adapters (Postgres/MySQL/SQLite). The performance-optimizations page is directly relevant to the advisory pattern where an optimization (e.g. the "weight 2 optimization" behind CVE-2025-55213) introduced a correctness bug.
- **DeepWiki — OpenFGA language core concepts** (`deepwiki.com/openfga/language`): explains the DSL-to-JSON compilation and the rewrite operators, useful when reasoning about what a model *means* vs how the engine evaluates it.

## Where People Get It Wrong (recurring pitfalls from the discussion corpus)

These themes recur across blog comments, GitHub discussions/issues, and the advisory history:

1. **Treating ListObjects absence as denial.** ListObjects can truncate under a deadline (issue #1961). Inferring "denied" from "not in the list" is a correctness/security mistake; use Check for per-object decisions.
2. **Assuming MINIMIZE_LATENCY is fine for revocation.** The default mode can serve a stale cached `allowed=true` after a grant is deleted, until cache invalidation catches up. Revocation-sensitive checks need `HIGHER_CONSISTENCY` (or caching disabled).
3. **Under-restricting relations in a shared-store multi-tenant model.** When tenants share one store, isolation lives entirely in the rewrite rules. A relation that doesn't traverse the org/tenant link leaks across tenants — the store boundary won't save you. Prefer store-per-tenant for untrusting tenants.
4. **Trusting contextual tuples.** Contextual tuples are caller-supplied. They must be constrained by the model's type restrictions; the advisories CVE-2024-56323 and CVE-2025-48371 show what happens when contextual-tuple handling diverges from the type model.
5. **Forgetting OpenFGA doesn't authenticate end users.** The most common application-level bypass: passing a `user` the app never authenticated. OpenFGA answers about whoever you name.
6. **Leaning on `and`/`but not` in complex/cyclic models without testing.** Intersection and exclusion are where the engine's hardest evaluation bugs have lived (CVE-2024-31452, CVE-2024-42473). Use the `WriteAssertions`/test tooling to lock down expected decisions.

## Security-Relevant Considerations

What the informal corpus tells QPB about OpenFGA's intended invariants:

- **The application owns authentication and enforcement; OpenFGA owns the relationship decision.** Every integration post restates this boundary. A reviewer should confirm the caller authenticates the `user` and enforces the `allowed` result — OpenFGA returning the right answer about the wrong (unauthenticated) user is still a breach.
- **Consistency mode is a security choice, not just a performance knob.** The Query Consistency post makes explicit that `MINIMIZE_LATENCY` trades freshness for speed. Revocation correctness depends on choosing `HIGHER_CONSISTENCY` (or disabling caching) for security-critical reads, because a stale cache can keep a revoked user authorized until invalidation.
- **Performance optimizations must preserve decision correctness.** The architecture/performance write-ups plus CVE-2025-55213 show that an evaluation optimization which prunes the search space can change the answer. Any optimization in the engine must be proven not to alter the set the rewrite denotes.
- **Type restrictions and contextual tuples are the soft underbelly.** The community and advisory record agree: the engine's correctness hinges on faithfully honoring `directly_related_user_types` for usersets, wildcards, and caller-supplied contextual tuples. Divergence here is the most repeated authorization-bypass mechanism in OpenFGA's history.
- **Cross-tenant isolation is only as strong as the chosen topology.** Store-per-tenant gives a hard boundary; shared-store relies on model discipline. The pitfall corpus repeatedly flags shared-store under-restriction as the cross-tenant leak surface.
