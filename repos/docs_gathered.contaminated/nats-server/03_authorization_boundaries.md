# Authorization Boundaries — Where the Subscribe ACL Stops and Why

## Sources:
- https://github.com/nats-io/nats-server/issues/4225
- https://github.com/nats-io/nats-server/issues/6180
- https://github.com/nats-io/nats-server/issues/3202
- https://www.byronruth.com/nats-weekly-31/#do-user-subscribe-permissions-affect-consumption-of-a-stream
- https://github.com/nats-io/nats-server/discussions/4860
- https://docs.nats.io/running-a-nats-service/configuration/securing_nats/authorization
- https://github.com/nats-io/nats-server/security/advisories/GHSA-fhg8-qxh5-7q3w

## Context

NATS's authorization story is clean for live pub/sub: every publish and every delivery passes a per-user subject ACL. JetStream introduces a second authorization surface — the `$JS.API.*` subject space — that controls who may create streams and consumers and who may fetch from them. These two surfaces have **different units of authorization**. Core ACLs are per *message subject*; JetStream API ACLs are per *API subject*. They overlap imperfectly: a `$JS.API.>` grant says nothing about which original message subjects the user is allowed to read, and a per-subject subscribe ACL says nothing about whether the user may operate on a JetStream consumer that captures those subjects. The gap is explicit, longstanding, maintainer-acknowledged, and unfixed in the general case.

## The two surfaces side by side

| Surface | Unit of authorization | Where evaluated | What it controls |
| --- | --- | --- | --- |
| **Core NATS subject ACL** | message subject pattern (with `*` / `>`) | every publish (PUB) and every delivery (MSG) | live pub/sub; the `$JS.API.*` subjects themselves when the user is the API caller |
| **JetStream API ACL** | the `$JS.API.*` request subject (which encodes stream/consumer/sometimes-filter names) | publish to the API request subject | who may invoke a given JetStream operation |

The JetStream API surface is governed by the **core** ACL — so there is no separate JetStream-permissions language; you grant `publish: ["$JS.API.CONSUMER.CREATE.>"]` to a user the same way you grant `publish: ["orders.>"]`. The asymmetry that produces the gap is on the *read* side: the user reads via `$JS.API.CONSUMER.MSG.NEXT.<stream>.<consumer>` (or via a push `DeliverSubject`), and the messages it receives back are not re-evaluated against its subscribe ACL on the *original* subjects those messages were published on.

## The known gap (NATS-1 territory)

**Maintainer-acknowledged**, issue #4225, derekcollison:

> "We are aware of the discrepancy between security models etc. We have been working on some ideas to help normalize."

**Community articulation**, issue #3202 (originating in NATS Weekly #31):

A user `sue` with `subscribe = ["users.sue", "_INBOX.>"]` cannot directly subscribe to `users.joe` or `users.pam`. But if `sue` can also publish to `$JS.API.CONSUMER.INFO.*.*` and `$JS.API.CONSUMER.MSG.NEXT.*.*` against a stream capturing `users.*`, `sue` can fetch and read `users.joe` and `users.pam` messages because:

1. Consumed messages are delivered on the consumer's delivery/inbox subject, not on `users.joe` / `users.pam`.
2. The per-subject subscribe ACL is never applied to the delivered message.
3. `addConsumerWithAction` does not re-check `cfg.FilterSubject` / `cfg.FilterSubjects` / the stream's `Subjects` against `sue`'s subscribe permissions before creating the consumer.

**Symmetric write-side gap**, issue #4225, shaunco:

A user `bar` with publish/subscribe limited to `yes.>` plus `$JS.API.>` (and `$JS.ACK.>`, `$JS.FC.>`, `$JSC.>`) can create a stream and a consumer for the subject `no.>` despite having no pub/sub on `no.>`. Stream-create and consumer-create both gate on the API subject; neither cross-checks against the user's underlying pub/sub permissions on the message subjects involved.

## Scoping tighter via extended subject patterns (the documented mitigation)

The current mitigation is **operator-side configuration**, using the fact that for a single-filter consumer the client appends the filter to the create subject. Concrete pattern (derekcollison's example, #4225):

```
# Goal: user may only create the DEREK consumer on stream TEST, filtered to foo.*

publish: {
  allow: [
    "$JS.API.CONSUMER.CREATE.TEST.DEREK.foo.*"
  ]
  deny:  [
    "$JS.API.CONSUMER.CREATE.TEST.DEREK"     # block the base (no-filter) form
  ]
}
```

The deny on the base form is required because without it, a client could still hit `$JS.API.CONSUMER.CREATE.TEST.DEREK` with a JSON body containing `FilterSubject: ">"` and bypass the scoping. The allow on the extended form lets only filters under `foo.*` reach the handler. derekcollison explicitly calls out the deny as the "pedantic" hardening some users adopt.

For a consumer with no filter at all, you can scope the bare API subject:

```
publish: { allow: ["$JS.API.CONSUMER.CREATE.TEST.READER"] }
```

For multi-filter consumers using `FilterSubjects` (plural), **there is no equivalent.** The plural list lives in the JSON request body, not in the API subject string. Operators have no subject-level handle to allow some filter sets and deny others. This is the substance of issue #6180.

## Issue #6180 — the residual gap (filter_subject vs filter_subjects asymmetry)

Verbatim from issue #6180:

> The current ACL system for NATS JetStream lacks the ability to enforce granular restrictions on filter_subjects in consumer configurations. While filter_subject can be controlled via specific permission patterns, there is no equivalent mechanism for filter_subjects. This limitation exposes a potential security gap for users attempting to enforce strict subject-level access controls.
>
> **Current Behavior**
> - Permissions such as `$JS.API.CONSUMER.CREATE.my_stream.*.my_stream.123.>` work effectively for filter_subject.
> - The equivalent does not apply to filter_subjects, leaving users unable to block or enforce restrictions when multiple subjects are provided.
>
> **Expected Behavior**
> - Deny specific filter_subjects patterns in JetStream consumer creation permissions.
> - Allow granular ACLs to restrict or allow filter_subjects configurations similar to filter_subject.

The issue is open as a feature request. There is no maintainer-acknowledged plan to surface plural filters into the API subject; the consensus across #4225 and #6180 is that the correct long-term fix is server-side ACL enforcement inside `addConsumerWithAction` (and any other consume-time check point) rather than a subject-string workaround.

## Related authorization-boundary surfaces

These are not NATS-1 but they show how the boundary cracks in adjacent ways:

- **CVE-2025-30215** — four JetStream admin APIs (`$JS.API.ACCOUNT.PURGE.*`, `$JS.API.SERVER.REMOVE`, `$JS.API.ACCOUNT.STREAM.MOVE.*.*`, cancel-move) lacked the system-account check. Any user with `$JS.>` publish (commonly granted to per-account admins) could execute them across account boundaries — destroying data in unrelated accounts. The reference pattern that *did* check correctly was `$JS.API.META.LEADER.STEPDOWN`. Lesson: a broad `$JS.>` publish grant is necessary but **not sufficient** for system-scoped admin APIs.
- **CVE-2026-33222** — JetStream stream restore was authorized by API-subject ACL only; it did not verify that the target stream name was within the caller's authorized scope, so a user with restore permission for one stream could restore-over another stream. Same shape as the consumer gap: the API ACL is per-API-subject, not per-affected-data.
- **CVE-2026-33217** — MQTT subject ACLs not applied in the `$MQTT.>` namespace; an entire interface escaped ACL evaluation.
- **CVE-2022-29946** — deny on a specific subject combined with allow on a wildcard was honored for direct subscription but leaked through wildcard queue subscriptions. The intended invariant — "deny filters every delivery path" — is the same invariant being violated by JetStream consumer reads, just at the JetStream layer instead of the queue-group layer.
- **Discussion #4860** — publish vs subscribe permission semantics; recurring source of misconfiguration where reply traffic on `_INBOX.>` is silently denied.

## Why the gap exists by design (the abstraction story)

JetStream was added as a higher-level capability on top of core NATS. Its model is: messages are captured into a stream by their original subjects, but they are *delivered to a consumer* on a different subject (the delivery/inbox subject or `DeliverSubject`). That decoupling is what enables replay, redelivery, exactly-once-window semantics — but it also means the original-subject ACL is structurally invisible at delivery time, because the delivery is not "a publish on the original subject" anymore.

The fix is not impossible — it requires `addConsumerWithAction` (and any path that mutates a consumer's filters or accepts a pull/push read) to consult the user's stored subscribe ACL against the filter subjects and to refuse / prune / filter accordingly. This is exactly what #4225 requests:

> "evaluate privs vs consumer filters (most similar to the limitation in what you can subscribe on in nats), or hide msgs with subjects not permitted to subscribe to when the consumer actually filters the messages available through the consumer"

The maintainer's posture is that the discrepancy is known and that some normalization is being designed, but the design is not yet landed.

## Security-Relevant Considerations

- **The boundary between core ACLs and JetStream API ACLs is per-subject vs per-API-subject; they are not interchangeable.** A `$JS.API.>` (or `$JS.>`) grant says nothing about which original message subjects the user may read or write — verifying one is not verifying the other.
- **The extended consumer-create subject is operator-side mitigation, not a server-side guarantee.** It works only for `FilterSubject` (singular), only when the client uses the extended form, and only when the operator also denies the bare API subject so the JSON body can't bypass it.
- **There is no server-side check that `cfg.FilterSubject` / `cfg.FilterSubjects` is within the caller's subscribe ACL.** This is the structural feature that makes NATS-1 a real finding rather than a misconfiguration: an operator cannot, by configuration alone, cause `addConsumerWithAction` to reject a consumer whose filter exceeds the caller's subscribe permission.
- **Issue #6180's residual gap (no API-subject handle for `filter_subjects`) means even the operator-side mitigation is unavailable for multi-filter consumers.** Until the server enforces the cross-check directly, plural-filter consumers cannot be locked down at the ACL layer at all.
- **Symmetric admin APIs have failed in the same shape before** (CVE-2025-30215, CVE-2026-33222): "the request reached the handler, so we acted" is not a sufficient authorization gate when the affected scope (account, stream, filter, original subject) is broader than the API subject expresses.
