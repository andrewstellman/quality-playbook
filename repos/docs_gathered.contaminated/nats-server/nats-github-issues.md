# NATS Server GitHub Issues (authorization, account isolation, permission/wildcard, JWT, JetStream access control)

Sources:
- https://github.com/nats-io/nats-server/issues
- https://github.com/nats-io/nats-server/issues/3202
- https://github.com/nats-io/nats-server/issues/4225
- https://github.com/nats-io/nats-server/issues/3108
- https://github.com/nats-io/nats-server/issues/4832
- https://github.com/nats-io/nats-server/issues/6293
- https://github.com/nats-io/nats-server/issues/6016
- https://github.com/nats-io/nats-server/issues/3819
- https://github.com/nats-io/nats-server/discussions/4860

## Summary

The most security-relevant open/long-running issues in `nats-server` concern the **mismatch between core-NATS subject permissions and JetStream access control**. The recurring theme, articulated across issues #3202 and #4225 (and acknowledged by maintainer `derekcollison`), is that core NATS has a clean per-subject allow/deny model, but JetStream introduces an "intermediate API" (`$JS.*`) whose permission semantics are different and surprising: a user's *subscribe* permissions do not automatically limit what it can *read via a consumer*, and creating a stream/consumer can exceed the user's direct pub/sub rights. A second cluster of issues concerns **wildcard evaluation in leaf-node and JetStream permission contexts** behaving more restrictively (or differently) than fixed tokens. Issue numbers below were verified against live GitHub URLs; status is recorded as observed.

---

## Issue #3202 — Subscribe user permission not enforced for consumer

- **Status**: Open / discussion (documented behavior, treated by maintainers as "works as designed" but widely contested as a security gap)
- **Impact**: Data exfiltration — a user can read messages on subjects it is NOT permitted to subscribe to, via a JetStream consumer
- **Category**: JetStream authorization vs. core subject permissions (leaky abstraction)
- **Problem**: With a user `sue` whose `subscribe` is limited to `users.sue` and `_INBOX.>`, but who can publish `$JS.API.CONSUMER.INFO.*.*` / `$JS.API.CONSUMER.MSG.NEXT.*.*`, fetching from a consumer on a stream that captured `users.*` returns `users.joe` and `users.pam` messages too. The subscribe permission on `users.sue` is bypassed because JetStream delivers consumed messages on the consumer's delivery/inbox subject, not the original subject, so the per-subject subscribe ACL is never applied to them.
- **Expected / Actual**: Expected — a user can only read (via any mechanism, including a consumer) subjects it is permitted to subscribe to. Actual — consumption escapes the subscribe ACL. Maintainer `derekcollison`: messages from JetStream "are not delivered on their original subject, by design"; pull consumers could in principle bind client permission context but currently do not. Multiple commenters (`simon-connektica`, `abalmos`, `tpihl`) consider this a "major security issue" / "security leak" and argue it blocks audit/certification.

## Issue #4225 — Support privileges-enforcement for JetStream similar/identical to normal NATS

- **Status**: Open feature request
- **Impact**: Cannot restrict what a user reads from a stream; cannot prevent creating streams/consumers for subjects the user lacks pub/sub rights to
- **Category**: JetStream authorization model parity
- **Problem**: Core NATS lets you precisely limit which subjects a user may publish/subscribe; there is no equivalent for limiting which messages a user may *read via a consumer*. A consumer with a filter wider than the user's permission should fail, and/or messages on non-permitted subjects should be hidden server-side before applying the consumer filter. Comment (`shaunco`): a user `bar` with only `$JS.API.>` can create a stream/consumer for `no.>` despite having no pub/sub on `no.>`; stream/consumer/bucket names disallow dots and mid-token wildcards, making tight lockdown require very long permission maps; some `$JSC.>` / `$JS.FC.>` subjects use hashes/random strings that are hard to constrain.
- **Expected / Actual**: Expected — JetStream pub/sub/consume governed by the same subject-permission model as core NATS, dynamically evaluated at consume time against current permissions. Actual — consumer access governed by the lower-level `$JS.*` API permissions, decoupled from message-subject permissions.

## Issue #3108 — Account isolation: JetStream receives messages it shouldn't

- **Status**: Closed (reporter's reproduction could not be confirmed by maintainer `kozlovic`; the attached log actually showed correct per-account delivery — `test3` reached only CLIENT, not CLIENT2)
- **Impact** (as alleged): a JetStream stream in one account capturing a wildcard subject (`orders.*.stream.entry`) might capture imported messages intended only for another account
- **Category**: Account isolation in JetStream ingest vs. cross-account stream imports
- **Problem (as reported)**: Two accounts CLIENT and CLIENT2 each import a different private stream subject from a PUBLIC account (`orders.client.stream.>` and `orders.client2.stream.>` respectively) and each create a JetStream stream on `orders.*.stream.entry`. The reporter claimed both accounts' streams ended up with the same message; the concern is that a malicious tenant could create a wildcard-subject stream to capture another tenant's imported messages.
- **Expected / Actual**: Expected — a stream in CLIENT only captures subjects CLIENT legitimately imports; CLIENT2's import must not reach CLIENT's stream. Actual (per maintainer analysis of the logs) — delivery was correctly account-scoped; the issue was closed as not reproduced. Retained here because it captures the *intended* invariant (a JetStream stream's wildcard subject must not let one tenant capture another tenant's imported subjects) that any review should confirm holds.

## Issue #4832 — Wildcard in leaf node permissions is more restrictive than a fixed token

- **Status**: Open (per search index)
- **Impact**: Permission-evaluation inconsistency at the leaf-node boundary; a wildcard permission does not grant what an equivalent set of fixed-token permissions would
- **Category**: Wildcard matching correctness in leaf-node permission context
- **Problem**: Using a wildcard (e.g. `*`) in leaf-node permissions behaves more restrictively than naming the equivalent fixed token (e.g. `CREATE`); the expectation is that a wildcard covers at least what the specific tokens do. (Details from the search index; full thread not fetched.)

## Issue #6293 — JetStream Permissions Issue with Leaf Node Setup

- **Status**: Open (per search index)
- **Impact**: JetStream operations fail or behave unexpectedly across leaf-node domain mappings; access restrictions interact badly with domain prefixes
- **Category**: JetStream + leaf-node domain permission interaction
- **Problem**: Permission/domain-mapping interactions in a leaf-node JetStream setup produce access issues. (Details from the search index; full thread not fetched.)

## Issue #6016 — Push consumer deliver_subject does not match wildcarded subscription

- **Status**: Open (per search index)
- **Impact**: A push consumer's `deliver_subject` and the client's wildcard subscription must align; mismatches with wildcards cause delivery problems
- **Category**: Consumer delivery-subject vs. subscription/permission matching
- **Problem**: A push consumer requires the client to subscribe to the `deliver_subject` first; when wildcards are involved the matching does not behave as expected. Relevant because the `deliver_subject` is the subject on which permission is actually evaluated for push consumers. (Details from the search index; full thread not fetched.)

## Issue #3819 — JetStream JWT authentication problem

- **Status**: Open (per search index)
- **Impact**: JetStream interaction with decentralized JWT auth produces authentication/authorization problems
- **Category**: JWT auth + JetStream
- **Problem**: Reported difficulties getting JetStream to work correctly under JWT-based (operator) security. (Details from the search index; full thread not fetched.)

## Discussion #4860 — NATS publish vs subscribe permissions

- **Status**: Discussion
- **Impact**: Clarifies the intended semantics of publish vs subscribe permissions (community confusion is itself a misconfiguration risk)
- **Category**: Permission-model documentation/semantics
- **Problem**: Users seeking clarity on how publish and subscribe permission lists interact, the asymmetry, and how request/reply inboxes must be permitted. (Details from the search index; full thread not fetched.)

## Security-Relevant Considerations

Invariants these issues bear on (and that a code review should verify):

- **Reading a message via a JetStream consumer must not grant access that a direct subscription would deny.** Issues #3202 and #4225 document that today it can; the intended invariant is that consume-time access is governed by the user's current subject-subscribe permissions, with non-permitted subjects filtered server-side. Treating the `$JS.>` API as the only gate (and relying on clients to hide it) is not an access-control boundary.
- **Creating or operating a stream/consumer must not exceed the user's pub/sub rights on the underlying subjects.** A user able to publish `$JS.API.>` must not thereby capture or read subjects (`no.>`) it cannot pub/sub directly (#4225).
- **Account isolation must hold for JetStream ingest:** a wildcard-subject stream in one tenant must capture only that tenant's (and legitimately imported) subjects, never another tenant's imported messages (#3108 — the intended invariant, even though that specific report was not reproduced).
- **Wildcard permissions must be at least as permissive as the equivalent enumerated fixed tokens and must evaluate consistently across boundaries** (client, leaf node, JetStream). Inconsistent wildcard evaluation (#4832) is both a usability and a security hazard, since operators may grant a wildcard believing it covers cases it silently doesn't (or over-grant compensating for it).
- **Push-consumer delivery subjects are the actual permission-evaluation point; subscription/permission matching for `deliver_subject` (including wildcards) must be correct** (#6016).
- **JetStream under JWT auth must enforce the same account/permission guarantees as static config** (#3819).
