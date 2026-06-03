# NATS Authorization Invariants — What Must Always Hold

## Sources:
- https://github.com/nats-io/nats-server/issues/4225
- https://github.com/nats-io/nats-server/issues/6180
- https://github.com/nats-io/nats-server/issues/3202
- https://github.com/nats-io/nats-server/issues/3108
- https://docs.nats.io/running-a-nats-service/configuration/securing_nats/authorization
- https://docs.nats.io/running-a-nats-service/configuration/securing_nats/accounts
- https://github.com/nats-io/nats-general/blob/main/SECURITY-SELF-ASSESSMENT.md
- https://github.com/nats-io/nats-server/security/advisories
- https://advisories.nats.io/CVE/CVE-2022-24450.txt
- https://advisories.nats.io/CVE/CVE-2025-30215.txt
- https://advisories.nats.io/CVE/CVE-2021-3127.txt
- https://advisories.nats.io/CVE/CVE-2022-29946.txt
- https://advisories.nats.io/CVE/CVE-2026-33222.txt
- https://advisories.nats.io/CVE/CVE-2026-33217.txt

## Context

This file consolidates the security invariants that the rest of this documentation set leans on. They are written in "must always" / "must never" form so a QPB-style invariant detector can pattern-match them against code paths. Each invariant cites the doc passage or maintainer statement (or CVE) that establishes it. The first cluster is the JetStream consumer-authorization invariants — the locus of the NATS-1 finding and the explicit subject of #4225 and #6180. The remaining clusters cover ACL precedence, account isolation, system-account scoping, identity propagation, and pre-auth resource bounds.

## Cluster A — Subscribe ACL coverage for JetStream consumers (NATS-1 / #4225 / #6180)

These are the invariants the audit is primarily verifying. They are violated in the current code; the docs and maintainer statements describe the intended (not currently implemented) behavior.

- **Subscribe ACL must always be checked when a consumer is created or updated with a `FilterSubject` or `FilterSubjects`.** A user creating a consumer whose filter pattern is not within its `subscribe` allow-list (or is within its `deny` list) must be refused at consumer-create time. (Intended invariant per #4225: "Validate that any subject used to access a stream would be allowed as a direct subscription.")
- **Subscribe ACL must always be checked when a consumer with no explicit filter is created.** A consumer with no filter implicitly reads every subject the stream captures; that set must be entirely within the user's subscribe allow-list. ("creating a consumer with a filter wider than allowed in permissions should result in a failure" — #4225.)
- **Subscribe ACL must always be checked when a message is delivered through a consumer.** Either (a) the consumer-create check is strong enough to make delivery-time checking unnecessary, or (b) at delivery time the server filters out messages whose original subject the user is denied from subscribing to. Per #4225: "or hide msgs with subjects not permitted to subscribe to when the consumer actually filters the messages available through the consumer."
- **Subscribe ACL on the consumer's filter must apply identically to `FilterSubject` (singular) and `FilterSubjects` (plural).** The current asymmetry — operator-side scoping works for singular via the extended consumer-create subject, but plural has no API-subject handle — is the explicit content of issue #6180 and must not be a basis for differential enforcement.
- **Publish ACL must always be checked when a stream is created with captured `Subjects`.** A user creating a stream whose `Subjects` list includes patterns it has no publish (and where reads are also a concern, no subscribe) permission on must be refused. (shaunco's example in #4225: user `bar` with no `no.>` permission should not be able to create a stream capturing `no.>`.)
- **Operator-side mitigation via the extended consumer-create subject (`$JS.API.CONSUMER.CREATE.<stream>.<consumer>.<filter>`) is necessary but not sufficient.** The mitigation works only for `FilterSubject` (singular), requires explicit deny on the base form to prevent body-driven escape, and provides no coverage for `FilterSubjects` (plural). It is a configuration-time hardening, not a structural guarantee.
- **The `$JS.API.*` publish permission must never be treated as a substitute for the user's underlying subject permissions on the messages the API operates over.** A `$JS.API.>` grant authorizes "may invoke this JetStream operation"; it does not authorize "may read or write the affected message subjects."

## Cluster B — ACL precedence and uniform enforcement

- **`deny` must take precedence over `allow` on every delivery path.** Direct subscriptions, wildcard subscriptions, queue-group delivery, JetStream consumption — a subject denied for the user must never reach the user. CVE-2022-29946 was the queue-group leak violating this; the JetStream consumer gap is the same invariant violated at a different layer.
- **A wildcard `allow` must never grant access to a more-specifically-denied subject.** A `>` allow includes `$SYS.>`, `$JS.>`, and every other reserved subspace; sensitive subspaces must be explicitly denied (or the allow narrowed). Failing this was central to CVE-2025-30215 reachability in real configurations.
- **Subject ACLs must apply uniformly across every client interface and namespace.** Core NATS, MQTT (`$MQTT.>`), WebSockets, leafnodes, JetStream API, message tracing — each delivery and publish path must consult the same ACL. CVE-2026-33217 (MQTT ACL bypass) and CVE-2026-33249 (message tracing redirect to subjects without publish permission) violated this.
- **An authorization failure must fail closed.** Refuse the action, log it, return a `Permissions Violation` / `Authorization Violation` to the client. Silently allowing or silently dropping masks misconfiguration and is never acceptable.
- **Queue-group membership is itself a permission and must be enforced as such.** A user denied a queue must not join it, because queue membership rewrites who receives which messages.

## Cluster C — Account isolation (cross-account)

- **An account is a hard subject-namespace boundary.** A message published in account A on subject `S` must be deliverable only to subscribers in A unless A explicitly exports `S` and the receiving account B explicitly imports it. Subject-matching that ignores account scope is a multi-tenancy breach.
- **A client's account must be determined solely by its credentials and must be immutable for the connection's lifetime.** No protocol field, header, or handshake option may let a client choose or switch accounts. CVE-2022-24450 was the catastrophic violation.
- **A private export (with an `accounts:` allow-list) must never be importable by an account not on the list.** A public export (no list) is importable by all — the default-public behavior must be obvious to operators.
- **Activation/import tokens must reject on any binding mismatch — not warn.** The token binds (exporting account = issuer, importing account, exact subject); a mismatch on any of the three must reject. CVE-2021-3127 was the warning-instead-of-reject violation that let any account replay another's token.
- **Subject remapping (`prefix` / `to`) on imports must never widen the imported subject set beyond the export grant.** Remapping is cosmetic; it must not authorize subjects the export didn't authorize.
- **Cross-account access must never occur through a JetStream-internal path.** A user in account A must never read, create, move, purge, or restore a JetStream stream/consumer/KV/object in account B (or `$SYS`). CVE-2025-30215 (cross-account purge via `$JS.API.ACCOUNT.PURGE.*`) and CVE-2026-33222 (restore to arbitrary stream name) were violations. The reference pattern (`$JS.API.META.LEADER.STEPDOWN` correctly restricting to system-account users) is the model.
- **A wildcard-subject stream in one tenant must capture only that tenant's (and legitimately imported) subjects.** A stream in account A on `orders.*` must not capture messages from account B that share the subject. (Intended invariant per issue #3108 — the reported case was not reproduced, but the invariant is the one reviewers should verify.)

## Cluster D — System-account scoping

- **The system account `$SYS` is the privileged superuser boundary and spans the entire cluster/supercluster.** Anyone able to publish to `$SYS` can administer the deployment and move laterally. `$SYS` access must be tightly restricted, and the server process must be sandboxed (the shipped `nats-server-hardened.service` shows the intended posture).
- **System-scoped JetStream admin APIs must require system-account authority.** Account purge, server remove, stream move, cancel-move, stream restore: all must check `caller's account == system_account`, not merely "caller may publish on `$JS.>`." CVE-2025-30215 and CVE-2026-33222 were violations of this invariant.
- **A regular-account user must never reach `$SYS`-only operations through any path** — direct publish, account switching, leaf-node propagation, or JetStream admin API.

## Cluster E — Identity integrity and trust propagation

- **Server-asserted identity headers (e.g. `Nats-Request-Info`) must be stripped from all inbound client and leafnode messages and only the server may set them.** CVE-2026-33223 (incomplete client-side stripping) and CVE-2026-33246 (unchecked leafnode propagation) violated this.
- **Identity mapping from external authenticators (mTLS DN, auth callout) must be exact and unforgeable.** Ambiguous DN-to-identity mappings must be rejected (CVE-2026-33248 was a mapping-ambiguity bypass).
- **A user/account JWT must be cryptographically verified up to the configured operator, using Ed25519 only.** No alternate signature algorithms; no acceptance of unsigned tokens.
- **Expired or revoked JWTs must be rejected on every connection.** Expiry must actually be enforced — CVE-2020-26892 was silent expiry-not-working.
- **Server identity must not be hold private key material.** NKEYS/JWT prove possession by signing the server nonce; the server stores only public keys.
- **A leaf node is partially trusted and must not propagate server-asserted identity claims unchecked.** Leaf-node identity must be re-established at the hub.

## Cluster F — Pre-authentication resource bounds

These are availability invariants rather than authorization invariants, but they appear in the same advisory stream and are part of the project's stated threat model.

- **Pre-authentication code paths (WebSocket compression, leafnode handshake) must bound resource use.** Unbounded decompression or buffer growth before auth allows pre-auth memory DoS (CVE-2026-27571, CVE-2026-33219).
- **Pre-authentication code paths must never panic on attacker input.** Leaf-node and WebSocket handshakes that crash the server are unauthenticated DoS (CVE-2026-29785, CVE-2026-27889, CVE-2026-33218).
- **Auth-callout payloads carry credentials and must be genuinely encrypted (xkey) and/or transported over TLS.** A silently-degraded encryption key exposes credentials (CVE-2023-46129 — all-zeros xkey).

## Cluster G — File/path integrity (defensive)

- **Untrusted input must not control filesystem paths.** JetStream stream restore (CVE-2022-26652 — Zip Slip) and system-account account-sync (CVE-2022-28357) were path-traversal failures. Sanitize archive entries against traversal; sandbox the server process with `ProtectSystem=strict` / `PrivateTmp=true` / narrow `ReadWritePaths`.

## Invariant-to-finding map

| Cluster | Most relevant invariants for NATS-1 |
| --- | --- |
| **A (consumer subscribe ACL)** | All of A. This is the substance of the NATS-1 finding. |
| **B (ACL precedence / uniformity)** | "Deny precedes allow on every delivery path" — JetStream consumption is a delivery path; the deny escape via consumer is the same shape as the CVE-2022-29946 queue-group escape. |
| **C (account isolation)** | "Cross-account access must never occur through a JetStream-internal path" — bounds the blast radius of the consumer gap inside the account. |
| **D (system-account scoping)** | Sibling failure mode (CVE-2025-30215) — "API-subject reachable ≠ operation authorized." Same root cause shape. |
