# NATS Server: Overview, Core Concepts, Topology, and Trust Boundaries

Sources:
- https://github.com/nats-io/nats-server
- https://github.com/nats-io/nats.docs/blob/master/nats-concepts/subjects.md
- https://docs.nats.io/nats-concepts/subjects
- https://docs.nats.io/nats-concepts/core-nats/reqreply
- https://docs.nats.io/using-nats/developer/receiving/wildcards
- https://github.com/nats-io/nats.docs/blob/master/running-a-nats-service/configuration/securing_nats/accounts.md
- https://github.com/nats-io/nats-general/blob/main/SECURITY-SELF-ASSESSMENT.md

> Note: `docs.nats.io` is client-rendered (GitBook); canonical content was read from the `nats-io/nats.docs` GitHub markdown sources, which render server-side, plus search summaries of the docs.nats.io pages.

## What NATS Server is

NATS Server (`nats-server`) is a high-performance, open-source publish/subscribe distributed messaging system written in Go, maintained by Synadia and a CNCF project. It is a connective technology for cloud, on-premise, IoT, and edge: clients connect over TCP (also WebSockets and MQTT) and exchange messages addressed by **subject**. NATS is fundamentally an **interest-based** system — the server routes a message only to subscribers who have expressed interest in its subject, and a message with no interested subscriber in core NATS is simply discarded (persistence is provided by the optional JetStream layer).

## Core messaging concepts

### Subjects
A **subject** is a dot-delimited string (e.g. `time.us.east.atlanta`) that names a communication channel. Subjects form a hierarchy via `.`. A publisher always publishes to a *fully specified* subject (no wildcards). Subjects are the unit of addressability and, crucially, **the unit on which security (authorization) and account isolation are enforced**.

- Allowed characters: any Unicode except `null`, space, `.`, `*`, `>`. Recommended: alphanumerics, `-`, `_`. Names are case-sensitive.
- By convention, subjects beginning with `$` are reserved for system use: `$SYS` (system events), `$JS` (JetStream API), `$KV`, `$OBJ`, `$MQTT`, `$G` (the implicit global account). Inboxes use the `_INBOX.` prefix.

### Wildcards (subscription-side only)
NATS provides two wildcards, usable only by subscribers (and in permission/import/export rules), never by publishers:

```
*   matches exactly one token         time.*.east   -> time.us.east, time.eu.east   (NOT time.us.east.atlanta)
>   matches one or more trailing tokens; only at the end   time.us.>   -> time.us.east, time.us.east.atlanta
```

`*` cannot match a partial token (`time.New*.east` is not partial matching). `*` may appear multiple times; the two can be mixed (`*.*.east.>`). A bare `>` subscription is a full "wire tap" receiving every message the subscriber is permitted to see.

### Publish / Subscribe, Queue Groups, Request/Reply
- **Pub/Sub**: a publisher sends to a subject; every interested subscriber receives a copy (fan-out).
- **Queue groups**: subscribers that register the same *queue name* on a subject form a queue group; each message to that subject is delivered to exactly one (randomly chosen) member — load balancing. Queue-group membership can itself be permission-constrained.
- **Request/Reply**: a requester publishes to a subject with a `reply` subject (typically an `_INBOX.<generated>` subject). A responder subscribes to the request subject and publishes its answer to the reply subject. Inbox reply subjects are dynamically routed back to the requester regardless of location. Response permissions (`allow_responses`) exist to grant a responder temporary publish rights to the reply subject.

## Deployment topology and trust boundaries

NATS scales from a single server to a global mesh; each connection type is a distinct trust boundary.

- **Clients** connect to a server on the client port (default 4222), authenticate, and are bound to exactly one **account**. A client never selects its own account — the account is determined by its credentials. WebSocket and MQTT are additional client interfaces with their own ports.
- **Cluster**: a set of full-mesh `nats-server` instances that route messages among themselves to form one logical server. Routes are a *trusted* interconnect; account and subject scoping are preserved across routes. The **system account `$SYS` is shared across the whole cluster/supercluster** and is privileged.
- **Gateways / Superclusters**: clusters connected by gateway links into a supercluster spanning regions. Subject interest and account scoping propagate across gateways; the system account spans the supercluster.
- **Leaf nodes**: a `nats-server` (often at the edge, or embedded) connects *outbound* to a hub cluster as a leaf. A leaf node extends a single account into the leaf by default and is **not fully trusted unless the system account is explicitly bridged**. Identity claims and headers crossing a leaf boundary must be validated by the hub — unchecked propagation is a known vulnerability class (CVE-2026-33246).
- **MQTT / WebSocket bridges**: alternate client protocols mapped onto NATS subjects (MQTT under `$MQTT.>`). These must enforce the same subject ACLs as core NATS (a failure here was CVE-2026-33217).

## Security model (high level)

NATS layers three mechanisms:
1. **Authentication** — proving who a client is (token, user/password, TLS/mTLS, NKEYS, decentralized JWT, or auth callout). See `nats-authentication.md`.
2. **Account** — the multi-tenancy isolation boundary. Each account is an independent subject namespace; messages in one account are invisible to others unless explicitly shared via exports/imports. See `nats-accounts-and-multitenancy.md`.
3. **Authorization** — per-user subject permissions (publish/subscribe allow/deny lists, queue-group constraints, response permissions, allowed connection types) evaluated on every publish and subscribe. See `nats-authorization-permissions.md`.

The **system account `$SYS`** is the privileged administrative boundary (server management, account purge, events). JetStream persistence adds the `$JS.API.*` subject space, which is also subject to account scoping and authorization. See `nats-jetstream.md`.

## Security-Relevant Considerations

What must hold for NATS to be secure, and what goes wrong otherwise:

- **The subject is the authorization unit, so subject-permission evaluation and account scoping must be correct for every message on every path.** If subject matching or scoping is wrong, a client receives or sends messages outside its intended reach. Because wildcards (`*`, `>`) can over-match, an allow rule that is broader than intended (or a missing deny) silently widens access.
- **A client's account is assigned by its credentials and is immutable for the life of the connection; the server must never let a client choose or switch accounts.** Violating this is a total multi-tenancy breach (CVE-2022-24450).
- **Each connection type is a trust boundary with a different trust level.** Clients are least trusted; routes within a cluster are trusted; leaf nodes are partially trusted (not for the system account unless bridged). Server-asserted identity must be (re)established at each boundary and not blindly propagated from a less-trusted side (CVE-2026-33246, CVE-2026-33223).
- **The system account `$SYS` is the superuser boundary and spans the entire cluster/supercluster.** Anyone who can publish to `$SYS` (or who is wrongly placed there) can administer the deployment and move laterally; `$SYS` access must be tightly restricted and the process sandboxed.
- **Core NATS discards messages with no interested subscriber; persistence (and replay) is only via JetStream**, which therefore introduces additional access-control surface (the `$JS.API.*` space and stored data) that must be scoped per account just like live subjects.
- **Alternate interfaces (MQTT, WebSocket, leaf) must enforce the identical authorization model as core NATS**; any interface that bypasses subject ACLs is an authorization bypass (CVE-2026-33217).
