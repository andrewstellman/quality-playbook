# Issue Tracker Themes — Security, Authorization, JetStream, Permissions

## Sources:
- https://github.com/nats-io/nats-server/issues
- https://github.com/nats-io/nats-server/issues/3202
- https://github.com/nats-io/nats-server/issues/4225
- https://github.com/nats-io/nats-server/issues/6180
- https://github.com/nats-io/nats-server/issues/3108
- https://github.com/nats-io/nats-server/issues/4832
- https://github.com/nats-io/nats-server/issues/6293
- https://github.com/nats-io/nats-server/issues/6016
- https://github.com/nats-io/nats-server/issues/3819
- https://github.com/nats-io/nats-server/discussions/4860
- https://github.com/nats-io/nats-server/discussions/5468
- https://github.com/nats-io/nats-server/discussions/5788
- https://www.byronruth.com/nats-weekly-31/#do-user-subscribe-permissions-affect-consumption-of-a-stream

## Context

The `nats-server` issue tracker is large and active; this file extracts recurring themes from issues and discussions concerned with security, authorization, JetStream access control, and permission/wildcard correctness. The dominant theme is the mismatch between core-NATS subject permissions and JetStream's `$JS.API.*` permission model. A secondary theme is wildcard evaluation inconsistencies at boundaries (leaf nodes, JetStream filters). The numbered issues below have been verified against live GitHub URLs; statuses are recorded as observed. Where the full thread was not fetched, the issue is summarized from the search index and the canonical URL is cited.

## Theme 1 — JetStream consumer reads escape subscribe ACLs (the NATS-1 family)

The single most-cited security theme. Recurs across issues, discussions, and community write-ups.

- **#3202 — Subscribe user permission not enforced for consumer.** Open; maintainer position is "works as designed," community framing is "major security issue." User `sue` with `subscribe = ["users.sue"]` can fetch `users.joe`/`users.pam` via a consumer because consumed messages are delivered on the consumer's delivery/inbox subject, not the original subject. Multiple commenters (`simon-connektica`, `abalmos`, `tpihl`) flag this as a blocker for audit/certification environments.
- **#4225 — Support privileges-enforcement for JetStream similar/identical to normal NATS.** Open feature request. Maintainer-acknowledged ("We are aware of the discrepancy between security models"). Documents both the read-side gap (consumer filter wider than subscribe permission should fail) and the write-side gap (`bar` with `$JS.API.>` can create a stream/consumer for `no.>` without pub/sub on `no.>`). Documents the current operator-side mitigation (extended consumer-create subject + deny on base form, single-filter only).
- **#6180 — Enhance ACL Flexibility for JetStream filter_subjects Permissions.** Open feature request. The residual gap from #4225's mitigation: the extended-subject workaround handles `filter_subject` (singular) but not `filter_subjects` (plural), leaving multi-filter consumers unlockable at the ACL layer.
- **NATS Weekly #31 (byronruth.com)** — community write-up that became #3202. "Do user subscribe permissions affect consumption of a stream?" Answer: no. The most-cited place where the NATS security model is misunderstood.
- **Why this is a theme, not a bug**: the gap is structural (consume-time delivery happens off-subject), maintainer-acknowledged as a known discrepancy, has prior unanswered follow-ups (`tpihl`: "Any progress with acl for consumers?"), and the documented mitigation explicitly does not cover all consumer configurations.

## Theme 2 — Wildcard evaluation inconsistency across permission contexts

A second cluster, less severe but recurring. Wildcards in leaf-node and JetStream permission contexts behave differently than wildcards in core-account permission contexts.

- **#4832 — Wildcard in leaf node permissions is more restrictive than a fixed token.** Open. Using a wildcard (`*`) in leaf-node permissions behaves more restrictively than naming the equivalent fixed token (`CREATE`). Expectation: a wildcard covers at least what enumerated tokens do. Why it matters: operators may grant a wildcard believing it covers cases it silently doesn't, then over-grant compensating. Or worse, deny via wildcard and have the deny silently not apply to the equivalent fixed token.
- **#6016 — Push consumer deliver_subject does not match wildcarded subscription.** Open. A push consumer requires the client to subscribe to the `DeliverSubject` first; with wildcards involved the matching does not behave as expected. The `DeliverSubject` is the actual permission-evaluation point for push consumers, so the matching has to be correct or messages are silently undelivered (or worse, over-delivered).
- **CVE-2022-29946** — closed-out advisory in the same theme: a deny on a specific subject + an allow on a wildcard was honored for direct subscriptions but leaked through wildcard queue-group subscriptions. The "wildcards evaluate differently across contexts" pattern recurs.
- **Why this is a theme**: wildcards are the unit of expressiveness in the ACL language, so wildcard-evaluation inconsistencies translate directly into over-grant or silent-deny depending on which side breaks.

## Theme 3 — JetStream / leaf-node / JWT auth interactions

Three things layered on top of the core auth model. Each interaction surface produces its own class of reported issues.

- **#6293 — JetStream Permissions Issue with Leaf Node Setup.** Open. JetStream operations behave unexpectedly across leaf-node domain mappings; access restrictions interact badly with domain prefixes. Real-world JetStream + leaf is the deployment shape most operators run into edge cases on.
- **#3819 — JetStream JWT authentication problem.** Open. JetStream interaction with decentralized JWT (operator → account → user) produces authentication/authorization problems. JWT-based auth must enforce the same account/permission guarantees as static config; reported gaps usually concern how account JWTs propagate updated permissions to live connections.
- **Discussion #5788 — Sharing many distributed account streams with a server-side account.** Practitioners working through cross-account JetStream stream sharing; reinforces that direct cross-account stream use is discouraged in favor of mirror/source patterns and explicit export/import.
- **Why this is a theme**: each layer (leaf node, JWT, JetStream) is well-specified individually, but the intersections produce surprising behavior. Reviewers should treat any cross-layer permission claim as suspect until verified against an end-to-end test.

## Theme 4 — Account isolation in JetStream ingest with wildcard-subject streams

A narrower theme: can a wildcard-subject stream in one tenant capture another tenant's (imported) messages?

- **#3108 — Account isolation: JetStream receives messages it shouldn't.** Closed (reporter's reproduction could not be confirmed by maintainer `kozlovic`; logs actually showed correct per-account delivery). Two accounts CLIENT and CLIENT2 each imported different private stream subjects from a PUBLIC account and each created a JetStream stream on `orders.*.stream.entry`; the reporter claimed both streams ended up with the same message. The issue was closed as not reproduced. **Retained as a theme** because it captures the *intended invariant* a reviewer should confirm holds: a stream's wildcard-subject capture must respect account boundaries on ingest — a stream in CLIENT must only capture subjects CLIENT legitimately holds (own or imported), never another tenant's imported messages with the same shape.
- **Why this is a theme**: it's the "stream-side" complement to the consumer-side gap. The consumer-side gap (#4225) is about *reading* outside your scope; the ingest invariant is about *capturing* outside your scope. Both must hold for JetStream account isolation.

## Theme 5 — Recurring operator misconfigurations (the documentation/UX failure mode)

Issues and discussions where the underlying server behavior is correct but the conceptual model is widely misunderstood.

- **Discussion #4860 — NATS publish vs subscribe permissions.** Clarifies the asymmetry between publish and subscribe permission lists and how request/reply inbox subjects (`_INBOX.>`) must be permitted. Recurring source of misconfiguration where reply traffic is silently denied.
- **Discussion #5468 — JetStream KV/ObjectStore as a database?** Discussion of using KV/object stores as durable stores; stresses that these are streams (`KV_*`, `OBJ_*`) under the account that inherit account scoping and the same `$JS.*` permission surface. The conceptual error: treating KV/object as a separate auth surface from JetStream streams.
- **Recurring patterns in operator misconfiguration** (synthesized from the discussions and from how CVEs were reachable in real configs):
  1. **Assuming subscribe permissions protect persisted data.** They don't — issue #3202, NATS Weekly #31, NATS-1 finding.
  2. **Granting `$JS.>` or `>` to per-account admins.** This silently includes system-account JetStream admin subjects, which is how CVE-2025-30215 (cross-account purge) was reachable.
  3. **Treating exports as private by default.** Without an `accounts:` list, an export is public — every account can import it.
  4. **Trusting leaf nodes or server-asserted headers.** Leaf nodes are partially trusted; identity headers must be validated (CVE-2026-33246, CVE-2026-33223).
  5. **Exposing the unauthenticated monitoring port** (`/varz`, `/connz`, etc.) to untrusted networks.
  6. **Relying on `deny` over a broad `allow` and assuming it filters every path.** Historically wildcard queue subscriptions leaked denied subjects (CVE-2022-29946).
- **Why this is a theme**: NATS's permission model is technically clean but its abstractions (subject = unit of auth, `$JS.>` = JetStream control plane, accounts = isolation) interact in ways that operators consistently get wrong. Many CVEs are not "the server is broken" but "the model the operator believed differed from the model the server enforced."

## Theme 6 — Pre-authentication resource safety

Open and historical pre-auth crash/DoS issues. Not authorization-class but consistently present.

- The advisory stream lists multiple pre-auth issues: leafnode handshake crashes (CVE-2026-29785, CVE-2026-33218), WebSocket compression bombs (CVE-2026-27571), WebSocket pre-auth memory unbounded (CVE-2026-33219), account service-import loops (CVE-2020-28466, CVE-2022-42709), JetStream replica-count panic (CVE-2022-42708).
- The recurring shape: a code path before the auth boundary accepts attacker-controlled input (size, compression ratio, handshake fields, replica count) and either crashes or consumes unbounded memory.
- **Why this is a theme**: pre-auth code paths must bound resource use and never panic. Reviewers should treat any decoder, decompressor, or handshake parser as a candidate.

## Themes summary

| Theme | Primary issues | NATS-1 relevance |
| --- | --- | --- |
| 1. JetStream consumer reads escape subscribe ACLs | #3202, #4225, #6180 | **The audit target.** |
| 2. Wildcard evaluation inconsistency | #4832, #6016, CVE-2022-29946 | Adjacent — wildcards in JetStream filters are exactly the unit at issue. |
| 3. JetStream / leaf / JWT interactions | #6293, #3819, #5788 | Same code paths exposed under more topologies. |
| 4. Account isolation in JetStream ingest | #3108 | Stream-side complement to the consumer-side gap. |
| 5. Operator misconfigurations | #4860, #5468 | The NATS-1 gap is widely misunderstood as "subscribe permissions protect stored data" — they don't. |
| 6. Pre-authentication resource safety | (advisory cluster) | Distinct from NATS-1; included for completeness. |

## Security-Relevant Considerations

- **Theme 1 is structural and maintainer-acknowledged; expect any QPB-detected violation of "subscribe ACL must apply to consumer filter" to map directly to NATS-1.** Issues #4225 and #6180 are unresolved feature requests, not bugs in the bug-tracker sense — the server enforces what it currently enforces correctly, and the gap is between the enforcement and the operator's intuitive model.
- **Theme 2 (wildcards) suggests reviewing every place wildcards are evaluated** for consistency: client subscribe, leaf-node propagation, consumer filter overlap, queue-group membership, deny precedence. The consistent failure mode is wildcards over-restricting at one boundary and under-restricting at another.
- **Theme 4 (ingest isolation) is the symmetric invariant to Theme 1 (consumption isolation).** A complete JetStream audit checks both: that one tenant's wildcard-subject stream doesn't capture another tenant's messages, AND that one tenant's consumer doesn't deliver messages on subjects the caller is denied from subscribing to.
- **Theme 5 (misconfigurations) is why mitigation guidance alone is insufficient.** "Use the extended consumer-create subject + deny the base form" is documented operator advice for the single-filter case. Real-world deployments don't apply it consistently (or can't, for plural filters), and the result is that the gap is exploitable in practice, not just in theory.
