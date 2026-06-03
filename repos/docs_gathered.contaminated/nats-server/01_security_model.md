# NATS Security Model — Subject ACLs, the `$JS.API.*` Layer, Account Isolation

## Sources:
- https://docs.nats.io/running-a-nats-service/configuration/securing_nats/authorization
- https://github.com/nats-io/nats.docs/blob/master/running-a-nats-service/configuration/securing_nats/authorization.md
- https://docs.nats.io/running-a-nats-service/configuration/securing_nats/accounts
- https://github.com/nats-io/nats.docs/blob/master/running-a-nats-service/configuration/securing_nats/accounts.md
- https://docs.nats.io/nats-concepts/jetstream
- https://github.com/nats-io/nats-general/blob/main/SECURITY-SELF-ASSESSMENT.md
- https://github.com/nats-io/nats-server/issues/4225
- https://advisories.nats.io/CVE/CVE-2022-24450.txt
- https://advisories.nats.io/CVE/CVE-2025-30215.txt

## Context

NATS layers three orthogonal mechanisms — **authentication** (who you are), **account** (which tenant you're in), and **authorization** (which subjects you may publish to or subscribe to). Authorization is enforced **per subject, per user**, on every publish and subscribe. The unit of authorization is the subject string; allow/deny lists may include wildcards. The same subject-permission machinery governs JetStream because JetStream's control plane is itself a set of NATS subjects under `$JS.API.*`. Account isolation is the load-bearing multi-tenancy boundary: messages in account A are not visible in account B unless A explicitly **exports** and B explicitly **imports**. The system account `$SYS` is privileged and spans the entire cluster/supercluster.

## Subject-based publish/subscribe ACLs

Each user may carry `publish` and `subscribe` permission lists. Either may be a plain subject list or a permission map with explicit `allow` and `deny` lists. Subjects use the same wildcards as subscriptions (`*` matches one token; `>` matches one or more trailing tokens).

```hocon
authorization {
  default_permissions = {
    publish   = "SANDBOX.*"
    subscribe = ["PUBLIC.>", "_INBOX.>"]
  }
  ADMIN     = { publish = ">",            subscribe = ">" }
  REQUESTOR = { publish = ["req.a","req.b"], subscribe = "_INBOX.>" }
  RESPONDER = { subscribe = ["req.a","req.b"], publish = "_INBOX.>" }
  users = [
    {user: admin,   password: $ADMIN_PASS,   permissions: $ADMIN}
    {user: client,  password: $CLIENT_PASS,  permissions: $REQUESTOR}
    {user: service, password: $SERVICE_PASS, permissions: $RESPONDER}
    {user: other,   password: $OTHER_PASS}                       # inherits default_permissions
  ]
}
```

### Allow / deny precedence

When both `allow` and `deny` are provided, **`deny` has priority over `allow`** in case of overlap. This is the single most important authorization rule: a deny on a specific subject must override a broader allow (including a wildcard `>`) that would otherwise match. The deny must filter every delivery path — direct subscriptions, wildcard subscriptions, and queue-group delivery. CVE-2022-29946 was a historical violation: a deny was honored for direct subscription but leaked through a wildcard queue subscription.

### Permission failure semantics

If an unauthorized client publishes or subscribes to a non-allow-listed subject, the action **fails closed**: it is logged at the server, and the client receives a `Permissions Violation` / `Authorization Violation` error. Failing open or silently dropping is never acceptable.

### Queue-group permissions

The `subscribe` permission can constrain queue-group membership with `<subject> <queue>` syntax. A deny on a queue subject must prevent a user from joining that queue, because queue membership changes who receives which messages.

### Response permissions

`allow_responses` is a deliberately scoped temporary widening for request/reply responders. It grants the responder permission to publish to the requester's reply subject without listing every dynamic inbox, bounded by `max` and `expires`. Important caveat: when `allow_responses` is enabled, the reply subject is **not** constrained to the `publish` allow/deny list — strict control over reply targets requires explicit `publish` allow lists instead.

### `allowed_connection_types`

A user may be restricted to specific interfaces (`STANDARD`, `WEBSOCKET`, `LEAFNODE`, `MQTT`, `IN_PROCESS`). Failing to enforce ACLs on a particular interface is an authorization bypass (CVE-2026-33217: MQTT subject ACLs not applied in `$MQTT.>`).

## The `$JS.API.*` layer

JetStream's entire control plane is request/reply on reserved subjects in the `$JS` namespace. Because these are ordinary subjects, JetStream access is granted with ordinary publish/subscribe permissions. Representative subjects:

```
$JS.API.STREAM.CREATE.<stream>
$JS.API.STREAM.INFO.<stream>
$JS.API.STREAM.DELETE.<stream>
$JS.API.CONSUMER.CREATE.<stream>.<consumer>                  # base form
$JS.API.CONSUMER.CREATE.<stream>.<consumer>.<filter>          # extended form (single filter only)
$JS.API.CONSUMER.INFO.<stream>.<consumer>
$JS.API.CONSUMER.MSG.NEXT.<stream>.<consumer>                 # pull fetch
$JS.ACK.>                                                     # acknowledgments
$JS.FC.>                                                      # flow control
$JS.API.ACCOUNT.PURGE.<account>                               # SYSTEM-account admin (must be restricted)
$JS.API.SERVER.REMOVE                                         # SYSTEM-account admin
$JS.API.ACCOUNT.STREAM.MOVE.<...>                             # SYSTEM-account admin
$JS.API.META.LEADER.STEPDOWN                                  # correctly restricted to system account
```

The mismatch between core-NATS subject ACLs and JetStream consumer reads is the entire substance of issue #4225: a user with `$JS.API.>` publish can create a consumer for subjects it has no direct subscribe permission on, and messages delivered by the consumer escape the per-subject subscribe ACL because they are delivered on the consumer's delivery/inbox subject, not their original subject. This is the surface area in which the NATS-1 finding sits.

## Account isolation: the multi-tenancy boundary

```hocon
accounts: {
    A: { users: [ {user: a, password: a} ] },
    B: { users: [ {user: b, password: b} ] },
}
```

Accounts `A` and `B` are fully isolated. A message published by `a` on subject `orders.new` cannot reach `b`, even though both accounts independently use the subject `orders.new`. A client's account is **fixed by its credentials and immutable** — the server must never let a client choose or switch accounts. CVE-2022-24450 was a total isolation breach: an undocumented experimental "sandbox accounts" feature let any authenticated client name a target account at handshake time, including `$SYS`.

### Cross-account exports / imports

The only sanctioned cross-account path is:

- **Stream export** (one-directional, exporter → importer; a stream of core-NATS messages, distinct from a JetStream stream).
- **Service export** (request/reply endpoint the importer may request).

```hocon
A: {
  exports: [
    {stream: puba.>}                       # PUBLIC stream — any account may import
    {service: pubq.>}                       # PUBLIC service — any account may request
    {stream: b.>,  accounts: [B]}           # PRIVATE stream — only B may import
    {service: q.b, accounts: [B]}           # PRIVATE service — only B may request
  ]
}
B: {
  imports: [
    {stream:  {account: A, subject: b.>}}
    {service: {account: A, subject: q.b}}
  ]
}
```

| Field | Meaning |
| --- | --- |
| `stream` / `service` | the exported subject (mutually exclusive). |
| `accounts` | allow-list of importing accounts. **If omitted, the export is PUBLIC** — any account may import. |
| `prefix` (stream import) / `to` (service import) | local subject remapping; must not widen the exported subject set. |

Activation tokens (decentralized JWT mode) bind (exporter = issuer, importer, exact subject); any mismatch must reject (CVE-2021-3127 was the warning-instead-of-reject violation).

### The system account `$SYS`

`$SYS` is the privileged administrative account, shared cluster-wide and supercluster-wide. By NATS's own security model, a `$SYS`-account client performing an unexpected action "does not cross a privilege boundary" — but it enables lateral movement across the whole deployment. Regular-account users must never reach `$SYS`-only operations. CVE-2025-30215 was the canonical violation: four JetStream admin APIs (account purge, server remove, account stream move, cancel-move) lacked the system-account check, and any user with `$JS.>` publish could destroy data in unrelated accounts.

## Intra-account vs cross-account scope

| Scope | Authorization mechanism |
| --- | --- |
| Intra-account live pub/sub | per-user `publish`/`subscribe` allow/deny lists on subjects (with wildcards). |
| Intra-account JetStream control | publish permissions on the `$JS.API.*` subjects the user invokes. |
| Intra-account JetStream consumption | currently the consumer-create subject + delivery subject; **NOT** re-checked against the user's `subscribe` list per original message subject (the NATS-1 gap; #4225). |
| Cross-account live pub/sub | exporter `exports` (with optional `accounts:` allow-list) + importer `imports`; activation token in JWT mode. |
| Cross-account JetStream | preferred pattern is **mirror/source** (B's stream mirrors A's); direct cross-account use requires exports/imports. |
| System-scoped admin | `$SYS` account membership, **not** a `$JS.>` publish grant. Mistaking the latter for the former was CVE-2025-30215. |

## Security-Relevant Considerations

The intended invariants of the security model:

- **Authorization is per subject, per user, per direction, evaluated on every publish and subscribe** — deny precedes allow on every delivery path (including wildcard queue-group delivery), the failure mode is "refuse and log," and no interface (MQTT, WebSockets, leafnode, JetStream API) may escape ACL evaluation.
- **An account is a hard subject-namespace boundary.** A message published in A on subject `S` is deliverable only to subscribers in A unless A explicitly exports `S` and the receiving account explicitly imports it. A client's account is determined solely by its credentials and is never client-selectable.
- **A public export (no `accounts:` list) is importable by every account.** Treating a private export as public, or omitting the allowed-accounts check, exposes the export to all tenants. Activation tokens must be cryptographically bound to (exporter, importer, exact subject); any mismatch rejects.
- **System-scoped operations must require system-account authority — a broad `$JS.>` publish grant is necessary but NOT sufficient.** `$JS.API.META.LEADER.STEPDOWN` is the correct reference pattern; admin APIs that omit the system-account check (CVE-2025-30215) cross account boundaries.
- **The `$JS.API.*` subject space is ordinary in shape but extraordinary in consequence**: control over persisted streams sits behind these subjects, and the user's subscribe permissions on *original message subjects* are not currently re-applied when the user reads messages via a consumer (the NATS-1 finding; see `04_invariants.md`).
