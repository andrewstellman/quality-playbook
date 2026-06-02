# NATS: Articles, Talks, and Public Discussions (security model in practice)

Sources:
- https://github.com/nats-io/nats-general/blob/main/SECURITY-SELF-ASSESSMENT.md
- https://www.synadia.com/blog/decentralized-security-webinar
- https://www.synadia.com/blog/onboarding-distributed-nats-clients-nkeys-jwts
- https://www.synadia.com/blog/why-nats
- https://www.synadia.com/blog/nats-http-monitoring-endpoints
- https://github.com/nats-io/nats-architecture-and-design/blob/main/adr/ADR-26.md
- https://natsbyexample.com/examples/auth/callout/cli/
- https://natsbyexample.com/examples/auth/callout-decentralized/cli
- https://www.byronruth.com/nats-weekly-31/#do-user-subscribe-permissions-affect-consumption-of-a-stream
- https://github.com/nats-io/nats-server/discussions/5788
- https://github.com/nats-io/nats-server/discussions/4860
- https://github.com/nats-io/nats-server/discussions/5468
- https://docs.nats.io/running-a-nats-service/configuration/securing_nats/accounts

> These go beyond the reference docs to capture how the NATS security model is described, used, and misunderstood. Several pages are surfaced via search; where a page was not fully fetched it is summarized from the search result and the canonical URL is cited.

## CNCF Security Self-Assessment (`nats-io/nats-general/SECURITY-SELF-ASSESSMENT.md`)

The project's own security self-assessment is the most authoritative statement of the intended threat model. Key points relevant to invariants:
- **Accounts are the multi-tenancy isolation boundary.** Messages published in one account cannot be accessed by clients in another unless explicitly exported and imported. Compromise of the account-isolation boundary breaks tenant-isolation guarantees.
- **Authorization-engine bypass or misconfiguration** is called out as a primary risk: it "could lead to unauthorized message access or injection."
- **Monitoring endpoints (the HTTP `/varz`, `/connz`, etc.) do not support HTTP-level authentication** and must be protected with TLS and network isolation. (This is the design backdrop for CVE-2026-33247, credentials in argv exposed to monitoring, and the MQTT password-disclosure advisory.)
- Clients authenticate via tokens, user/password, TLS certs, NKEYS, or JWTs and are isolated by account boundaries and subject-based permissions.

## Synadia: Decentralized security (webinar/blog)

`synadia.com/blog/decentralized-security-webinar` and the NKeys/JWT onboarding post describe the **operator → account → user JWT chain** as the recommended large-scale model: an operator issues account JWTs to teams, and each team independently issues user JWTs for its own account without the operator holding team private keys. This is the "fully decentralized authorization" story. The onboarding post (`onboarding-distributed-nats-clients-nkeys-jwts`) walks through generating NKeys, issuing user JWTs, and distributing `.creds` files — and emphasizes keeping operator/account *identity* keys offline and using **signing keys** for issuance so a leaked signing key can be revoked without rotating the root identity.

## Synadia: HTTP monitoring endpoints

`synadia.com/blog/nats-http-monitoring-endpoints` documents the monitoring surface (`/varz`, `/connz`, `/subsz`, `/accountz`, `/jsz`, etc.) and reiterates that these endpoints are **unauthenticated** — they must be bound to localhost or protected by network controls and TLS. This is a recurring real-world misconfiguration: exposing the monitoring port can leak connection metadata, account names, and (historically) credentials passed via argv.

## ADR-26: Authorization Callouts (`nats-architecture-and-design`)

The architecture decision record for **Auth Callout** specifies delegating client auth/authz to a NATS service backed by an external IAM. Security-relevant design points: the callout request carries the connecting client's presented credentials (including passwords), so the ADR recommends **encrypting the request payload with an xkey** and using a dedicated account for callouts. (The nkeys xkeys encryption defect CVE-2023-46129 directly undermined this recommendation until 2.10.4.)

## NATS by Example: Auth Callout (centralized & decentralized CLI walkthroughs)

`natsbyexample.com/examples/auth/callout/...` provides runnable examples of both centralized and decentralized auth-callout configurations, showing the designated callout user, the issuer NKey that signs the returned user JWT, and the encrypted request/response flow. Useful as the concrete shape of a correct callout deployment.

## NATS Weekly #31 (byronruth): "Do user subscribe permissions affect consumption of a stream?"

This community write-up is the origin of GitHub issue #3202. It explains, with examples, that **a user's `subscribe` permissions do NOT constrain what it can read via a JetStream consumer**, because consumed messages are delivered on the consumer's inbox/delivery subject, not their original subject. It frames the "knowledge gap": operators reason about permissions at the application (subject) level, which is correct for core NATS, but JetStream's intermediate `$JS.*` API breaks that symmetry. This is the single most-cited place where people "get the security model wrong."

## GitHub Discussions

- **#5788 — Sharing many distributed account streams with a server-side account**: practitioners working through cross-account JetStream stream sharing, reinforcing that direct cross-account stream use is discouraged in favor of mirror/source and explicit export/import.
- **#4860 — NATS publish vs subscribe permissions**: clarifies the asymmetry between publish and subscribe permission lists and how request/reply inbox subjects (`_INBOX.>`) must be permitted — a common source of misconfiguration where reply traffic is silently denied.
- **#5468 — JetStream KV/ObjectStore as a database?**: discussion of using KV/object stores as durable stores, relevant because it stresses that these are streams (`KV_*`, `OBJ_*`) under the account and inherit account scoping and the same `$JS.*` permission surface.

## Where people get the security model wrong (synthesis)

Recurring misunderstandings, drawn from the above:
1. **Assuming subscribe permissions protect persisted data.** They don't constrain consumer reads (issue #3202 / NATS Weekly #31). Operators who rely on subscribe ACLs to keep tenants out of stored messages are mistaken unless they also constrain the `$JS.*` API and consumer filters.
2. **Granting `$JS.>` or `>` to per-account admins.** This silently includes system-account JetStream admin subjects, which is how CVE-2025-30215 (cross-account purge) was reachable in real configs.
3. **Treating exports as private by default.** An export with no `accounts:` list is PUBLIC — any account can import it.
4. **Trusting leaf nodes / server-asserted headers.** Leaf nodes are partially trusted; identity headers from a leaf or a client must be validated, not propagated (CVE-2026-33246, CVE-2026-33223).
5. **Exposing the unauthenticated monitoring port.** It leaks account/connection metadata and historically credentials.
6. **Relying on `deny` over a broad `allow` and assuming it filters every path.** Historically a wildcard queue subscription leaked denied subjects (CVE-2022-29946).

## Security-Relevant Considerations

The intended invariants these sources reinforce:

- **Account isolation is the load-bearing tenancy guarantee; an authorization-engine bypass or a misconfigured export/import directly breaks it** (per the project's own security self-assessment). A reviewer should treat any path that delivers a message across an account boundary without a matching export+import as a critical defect.
- **Subscribe permissions are NOT a sufficient control over persisted (JetStream) data; consumer access must be independently constrained**, because consumed messages are delivered off-subject. Configurations that assume subject ACLs protect stored data are insecure (issue #3202 / NATS Weekly #31).
- **Decentralized JWT security depends on keeping operator/account identity keys offline and using revocable signing keys**; the trust chain operator→account→user must verify at every link, and revocation must propagate via the resolver.
- **Auth-callout requests carry credentials and must be encrypted (xkey) and isolated to a dedicated account** (ADR-26); a degraded encryption path (CVE-2023-46129) exposes them.
- **Monitoring/management endpoints are unauthenticated by design and must be protected by network isolation + TLS**; never expose them to untrusted networks.
- **Exports default to public; private sharing requires an explicit `accounts:` allow-list (static) or a correctly-bound activation token (JWT).** Misreading this default leaks data to every tenant.
