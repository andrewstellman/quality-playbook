# NATS Subject-Based Authorization (Permissions)

Sources:
- https://github.com/nats-io/nats.docs/blob/master/running-a-nats-service/configuration/securing_nats/authorization.md
- https://docs.nats.io/running-a-nats-service/configuration/securing_nats/authorization
- https://github.com/nats-io/nats.docs/blob/master/nats-concepts/subjects.md
- https://advisories.nats.io/CVE/CVE-2022-29946.txt
- https://github.com/nats-io/nats-server/issues/3202
- https://github.com/nats-io/nats-server/issues/4225
- https://advisories.nats.io/CVE/secnote-2026-15.txt

## Overview

NATS authorization is **subject-level, per-user**. Each user may be given `publish` and `subscribe` permission lists naming the subjects (with wildcards) it may publish to or subscribe to. Available with multi-user auth (`users` list) and in user JWTs. A special `default_permissions` entry applies to any user without explicit permissions.

```
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

If an unauthorized client publishes or subscribes to a non-allow-listed subject, the action **fails, is logged at the server, and an error is returned to the client** (`Permissions Violation` / `Authorization Violation`).

## Allow vs deny semantics and precedence

Instead of a plain subject list, `publish`/`subscribe` may be a **permission map** with explicit `allow` and `deny` lists. Both may be provided.

```
permissions: {
  publish:   { deny: ">" }                 # deny all publish
  subscribe: { allow: "client.>" }         # allow subscribe only under client.>
}
```

| Property | Meaning |
| --- | --- |
| `allow` | subjects the client may use |
| `deny`  | subjects the client may NOT use |

**Precedence: in case of overlap, `deny` has priority over `allow`.** This is the single most important authorization rule: a `deny` on a specific subject must override a broader `allow` (including a wildcard allow) that would otherwise match it.

> Known correctness gap (now fixed): CVE-2022-29946 — a `deny` on a specific subject combined with an `allow` on a wildcard *was honored for direct subscription but leaked through a wildcard QUEUE subscription*, so the deny did not filter messages delivered via the queue group. The intended invariant is that deny filters every delivery path.

## Subject wildcard matching and the over-match risk

Permission subjects use the same wildcards as subscriptions:
- `*` matches exactly one token (`time.*.east`).
- `>` matches one or more trailing tokens, only at the end (`time.us.>`); a bare `>` matches everything.

Because wildcards over-match, **an allow that is broader than intended grants more than intended.** `publish = ">"` (the ADMIN example) grants the entire subject space, *including the system and JetStream API namespaces* (`$SYS.>`, `$JS.>`) — which is exactly how the JetStream admin-API bypass (CVE-2025-30215) was reachable: an account "admin" with `$JS.>` (or `>`) could publish to system-account JetStream admin subjects. Permissions should be the narrowest wildcard that satisfies the use case, with explicit denies for sensitive subspaces.

## Queue-group permissions

The `subscribe` permission can constrain queue-group membership using `<subject> <queue>`:
```
users = [
  { user: a, permissions: { sub: { allow: ["foo queue"] } } }      # only as queue 'queue' on foo
  { user: b, permissions: { sub: {
      allow: ["foo", "foo v1", "foo v1.>", "foo *.dev"]            # plain sub + v1/*.dev queue groups
      deny:  ["> *.prod"]                                          # never join *.prod queue groups
  } } }
]
```
This allows constraining *which queue groups* a client may join, independent of plain subscription rights, and denying sensitive queue groups (`*.prod`).

## Response permissions (request/reply)

`allow_responses` grants a service responder *temporary* permission to publish to a request's reply subject without listing every dynamic inbox:
```
users: [
  { user: b, permissions: {subscribe: "q", allow_responses: true } }                       # one reply, no time limit
  { user: c, permissions: {subscribe: "q", allow_responses: { max: 5, expires: "1m" } } }   # <=5 replies, 1 minute
  { user: d, permissions: {subscribe: "q", publish: "x", allow_responses: true } }          # also explicit publish x
]
```
- `true` ≈ `{ max: 1 }`, no time limit. `max` caps the number of responses; `expires` (`1s`/`1m`/`1h`) caps the validity window.
- Enabling `allow_responses` **implicitly denies publish to all other subjects**, but an explicit `publish` allow overrides that implicit deny for the named subject (user `d`).
- **Important caveat (from the docs):** when `allow_responses` is enabled, the reply subject is **not** constrained to the `publish` allow/deny list — a client can hand the responder a reply subject it could not otherwise publish to, and the responder is temporarily allowed. For strict control over reply targets, do not use `allow_responses`; use explicit `publish` allow/deny.

## `allowed_connection_types`

A user may be restricted to specific connection interfaces via `allowed_connection_types`, e.g. `["STANDARD"]`, `["WEBSOCKET"]`, `["LEAFNODE"]`, `["MQTT"]`, `["IN_PROCESS"]`. A user without the relevant type listed is refused on that interface. This is part of the authorization surface: failing to enforce ACLs on a particular interface (e.g. MQTT, CVE-2026-33217) is an authorization bypass.

## JetStream API subjects are authorized like any other subject

JetStream is driven by messages on `$JS.API.*` subjects, so JetStream access is configured with ordinary publish/subscribe permissions on those subjects (e.g. `$JS.API.STREAM.CREATE.*`, `$JS.API.CONSUMER.MSG.NEXT.*.*`, `$JS.ACK.>`, `$JS.FC.>`). This creates a documented mismatch (see `nats-github-issues.md`): a user's *application-level* subject permissions do not automatically constrain what it can read via a JetStream *consumer*, because consumed messages are not delivered on their original subject. The intended-but-not-yet-implemented invariant (feature request #4225) is that a consumer filter wider than the user's subscribe permission should fail.

## Security-Relevant Considerations

The authorization invariants that must always hold:

- **Deny takes precedence over allow, on every delivery and publish path.** A `deny` on subject `X` must override any `allow` (including a wildcard `>` allow) that matches `X`. A wildcard in an allow list must NOT be able to grant access to a more-specifically-denied subject. The deny must filter direct subscriptions, wildcard subscriptions, AND queue-group delivery — the queue-group leak was the bug in CVE-2022-29946.
- **A wildcard must not grant beyond intent.** `*` matches exactly one token and `>` matches one-or-more trailing tokens; matching that is too permissive (e.g. treating `*` as matching multiple tokens, or `>` matching where a deny should win) over-grants. A broad allow like `>` or `$JS.>` silently includes system/JetStream admin subjects, so sensitive subspaces (`$SYS.>`, system-only `$JS.API.*`) must be denied or excluded explicitly.
- **Permissions must be enforced on BOTH publish and subscribe, and on every interface.** A subject the user cannot publish to must not be publishable via any side channel (e.g. message tracing redirect, CVE-2026-33249) or alternate interface (MQTT `$MQTT.>` ACL bypass, CVE-2026-33217). A subject the user cannot subscribe to must not be deliverable to it.
- **Response (`allow_responses`) permission is a deliberately scoped, temporary widening; it must be bounded by `max`/`expires` and must not be confused with a general publish grant.** Because the reply subject escapes the publish allow/deny list under `allow_responses`, code/config relying on strict reply-target control must use explicit publish lists instead.
- **JetStream API subjects (`$JS.API.*`) must be authorized with the same rigor as any subject, and admin/system operations must additionally require system-account authority** — a `$JS.>` publish grant is necessary but must NOT be sufficient for system-scoped admin APIs (account purge, server remove, stream move, restore). This was the root of CVE-2025-30215 and CVE-2026-33222.
- **Queue-group membership is itself a permission**; a client must not join a queue group (e.g. `*.prod`) it is denied, since queue membership changes who receives which messages.
- **An authorization failure must fail closed** — refuse the action, log it, and return an error to the client — never silently allow or silently drop in a way that masks a misconfiguration.
