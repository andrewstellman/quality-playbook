# NATS JetStream: Persistence, Account Isolation, and the `$JS.API.*` Surface

Sources:
- https://docs.nats.io/nats-concepts/jetstream
- https://docs.nats.io/nats-concepts/jetstream/consumers
- https://docs.nats.io/nats-concepts/jetstream/key-value-store
- https://docs.nats.io/reference/reference-protocols/nats_api_reference
- https://docs.nats.io/running-a-nats-service/configuration/leafnodes/jetstream_leafnodes
- https://github.com/nats-io/nats-server/issues/3202
- https://github.com/nats-io/nats-server/issues/4225
- https://github.com/nats-io/nats-server/issues/3108
- https://github.com/nats-io/nats-server/security/advisories/GHSA-fhg8-qxh5-7q3w
- https://advisories.nats.io/CVE/secnote-2026-12.txt
- https://advisories.nats.io/CVE/CVE-2022-26652.txt

> `docs.nats.io` is GitBook-rendered; conceptual content from the docs pages' search summaries plus the JetStream-related GitHub issues and advisories, which render fully.

## What JetStream is

JetStream is the built-in persistence engine. Where core NATS discards a message with no interested subscriber, JetStream **captures messages into streams** and replays them to **consumers** on demand, with acknowledgment and at-least-once / exactly-once-window semantics. Storage (a Stream) is configured separately from consumption (Consumers).

- **Stream**: a named, persisted, ordered log that captures messages matching one or more subjects (`subjects: ["orders.*"]`). Backed by file or memory storage, with retention (limits / interest / workqueue), replication (`num_replicas` via RAFT), and limits (max msgs/bytes/age).
- **Consumer**: tracks delivery position and acknowledgments for a client reading a stream. **Pull** consumers fetch batches on demand; **push** consumers deliver to a `deliver_subject`. A consumer may have a `filter_subject` narrowing which stream subjects it sees.
- **KV store**: an eventually-/immediately-consistent key-value map, materialized as a stream named `KV_<bucket>`; keys map to subjects under that stream.
- **Object store**: large-blob storage, materialized as a stream named `OBJ_<bucket>`.

## The `$JS.API.*` subject space

JetStream is operated entirely via request/reply on reserved subjects in the `$JS` namespace. Management of JetStream assets happens with messages in the `$JS.` namespace in the system account, **partially exposed into regular accounts** so account holders can manage their own assets. Representative subjects:

```
$JS.API.STREAM.CREATE.<stream>
$JS.API.STREAM.INFO.<stream>
$JS.API.STREAM.DELETE.<stream>
$JS.API.CONSUMER.CREATE.<stream>.<consumer>[.<filter>]   # filter appended for single-filter consumers
$JS.API.CONSUMER.INFO.<stream>.<consumer>
$JS.API.CONSUMER.MSG.NEXT.<stream>.<consumer>            # pull fetch
$JS.ACK.>                                                # acknowledgments
$JS.FC.>                                                 # flow control
$JS.API.ACCOUNT.PURGE.<account>                          # SYSTEM-account admin (must be restricted)
$JS.API.SERVER.REMOVE                                    # SYSTEM-account admin
$JS.API.ACCOUNT.STREAM.MOVE.<...>                        # SYSTEM-account admin
$JS.API.META.LEADER.STEPDOWN                             # correctly restricted to system account
```

Because these are ordinary subjects, JetStream access is granted with ordinary publish/subscribe permissions (see `nats-authorization-permissions.md`). A consumer created with a single filter subject appends the filter to the create subject (`$JS.API.CONSUMER.CREATE.TEST.DEREK.foo.*`), which lets the filter itself be constrained by core publish permissions.

## JetStream domains

A **domain** is an independent JetStream name space, used with leaf nodes / hub-and-spoke edge topologies. To address a remote JetStream you prefix its API with the domain: `$JS.<domain>.API.>`. Within the same account, the same stream name may exist in different domains without collision. Domains let an edge leaf node run its own JetStream isolated from (or mirrored to) the hub's.

## Storage and account isolation

- **All JetStream operations are account-scoped.** A stream and its consumers belong to exactly one account; on disk they live under `<store_dir>/jetstream/<ACCOUNT>/streams/<stream>/...` (per the server logs in issue #3108). JetStream must be explicitly enabled per account (`jetstream: enabled` or via account limits).
- **KV/Object stores inherit the stream's account scoping.** Cross-account KV/object access requires explicit API-prefix configuration (i.e. an export/import or domain prefix), the same controlled-sharing model as core streams.
- **Cross-account stream sharing** is best done via **mirror/source** (a stream in account B mirrors/sources one in A) rather than letting B's clients directly drive A's stream — a more locked-down model. Direct cross-account use requires exports/imports.

## Known access-control gaps (documented, see issues file)

JetStream's authorization model diverges from core NATS in ways that have generated long-running discussion and real CVEs:

1. **Consumption can escape application-level subject permissions.** A user whose `subscribe` permission is `users.sue` can still receive `users.joe`/`users.pam` messages by creating/consuming a stream consumer, because consumed messages are *not delivered on their original subject* and the consumer-create/fetch APIs do not re-check the user's subscribe permissions against each message's subject (issue #3202; feature request #4225). Maintainers acknowledge the discrepancy; the proposed-but-not-implemented invariant is to prune messages whose subjects the user cannot subscribe to.
2. **Stream/consumer creation can exceed pub/sub permissions.** A user with `$JS.API.>` can create a stream/consumer for subjects (`no.>`) it has no direct pub/sub permission for (issue #4225 comment).
3. **Admin APIs were not restricted to the system account** — account purge / server remove / stream move (CVE-2025-30215) and stream restore to arbitrary names (CVE-2026-33222).
4. **Restore archive path traversal** — CVE-2022-26652 (Zip Slip in stream restore).

## Security-Relevant Considerations

Isolation and access-control invariants for persisted data and the API surface:

- **A stream/consumer/KV/object store belongs to exactly one account, and its data and `$JS.API.*` operations are confined to that account.** A regular-account user must never read, create, move, purge, or restore another account's JetStream assets. Cross-account JetStream sharing must go through explicit exports/imports or mirror/source, never implicit reach.
- **System-scoped JetStream admin APIs must require system-account authority — a `$JS.>` (or `>`) publish grant is necessary but NOT sufficient.** Account purge, server remove, stream move/cancel-move, and stream restore must check the caller's account/role, mirroring `$JS.API.META.LEADER.STEPDOWN`. (CVE-2025-30215, CVE-2026-33222.)
- **Restore must be scoped to the caller's authorized stream name(s); restore targets must be validated.** Restoring to an arbitrary stream name (CVE-2026-33222) or writing archive entries outside the storage directory (CVE-2022-26652) are both authorization/path-integrity failures. Untrusted archive filenames must be sanitized against path traversal.
- **Reading via a JetStream consumer should not grant access beyond what the user could subscribe to live.** The current divergence (issue #3202/#4225) is a recognized risk: where strong guarantees are required, a consumer's filter and delivered subjects must be constrained by the user's subscribe permissions, and messages on denied subjects must be filtered out server-side — relying on clients to hide the `$JS.>` API is not an access-control boundary.
- **Stream subject capture must respect account boundaries on ingest.** A stream in account A capturing `orders.*` must only capture messages legitimately within A (or legitimately imported), not messages from another tenant that happen to share the subject (the concern raised in issue #3108).
- **JetStream domains are independent namespaces; addressing a remote domain (`$JS.<domain>.API.>`) must not bypass the account/permission checks of the target.** Leaf-node JetStream setups must preserve account scoping and not let a partially-trusted leaf reach hub assets it doesn't own.
