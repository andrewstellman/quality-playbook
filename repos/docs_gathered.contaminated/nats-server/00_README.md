# NATS Server — Project Overview and Documentation Index

## Sources:
- https://github.com/nats-io/nats-server
- https://docs.nats.io
- https://docs.nats.io/nats-concepts/subjects
- https://docs.nats.io/nats-concepts/core-nats/reqreply
- https://docs.nats.io/nats-concepts/jetstream
- https://github.com/nats-io/nats-general/blob/main/SECURITY-SELF-ASSESSMENT.md
- https://github.com/nats-io/nats.docs/blob/master/nats-concepts/subjects.md

## Context

NATS Server (`nats-server`) is a high-performance, open-source messaging system written in Go, maintained by Synadia and graduated under the Cloud Native Computing Foundation. It provides three messaging modalities — publish/subscribe, request/reply (with dynamic reply-inbox routing), and JetStream (a persistent streaming layer with at-least-once / exactly-once-window semantics). Clients connect over TCP (default port 4222), WebSockets, or MQTT, and exchange messages addressed by dot-delimited **subjects**. NATS is fundamentally an **interest-based** system: the server routes a message only to subscribers that have expressed interest in its subject, and a message with no interested subscriber in core NATS is simply discarded. Persistence is provided by the optional JetStream layer.

This documentation package is structured to feed a Quality Playbook (QPB) security audit focused on JetStream's authorization-scoping invariants. The single verified real finding in scope is **NATS-1**: JetStream consumer creation does not enforce subscribe ACLs on `FilterSubject`/stream subjects. The `jsConsumerCreateRequest` → `addConsumerWithAction` path in `server/jetstream_api.go` has no subscribe-ACL check; maintainer `derekcollison` acknowledged the discrepancy in issue #4225 ("We are aware of the discrepancy between security models"). The recommended mitigation is to scope the extended create subject `$JS.API.CONSUMER.CREATE.<stream>.<consumer>.<filter>` and add deny perms. Issue #6180 documents the residual gap: `filter_subject` (singular) is lockable, `filter_subjects` (plural) is not.

## Language and domain

- **Language**: Go (Go 1.21+ in current branches).
- **Domain**: distributed messaging — pub/sub, request/reply, persistent streaming (JetStream), KV store, object store, MQTT bridge, WebSockets.
- **Topology**: single-server, cluster (full-mesh routes), supercluster (gateways between clusters), leaf nodes (edge / hub-and-spoke).
- **Deployment role**: connective tissue for microservices, IoT/edge fleets, and event-driven systems.

## Key terminology

| Term | Meaning |
| --- | --- |
| **Subject** | A dot-delimited string (`time.us.east.atlanta`) naming a message channel. The unit of addressability AND the unit on which authorization and account isolation are enforced. Reserved prefixes: `$SYS`, `$JS`, `$KV`, `$OBJ`, `$MQTT`, `$G`, `_INBOX`. |
| **Wildcards** | `*` matches exactly one token; `>` matches one or more trailing tokens (only at end). Subscription-side only — publishers must use fully specified subjects. |
| **Account** | The multi-tenancy isolation boundary. Each account has its own private subject namespace; two accounts may both use `orders.>` with no overlap. A client's account is fixed by its credentials and is **immutable** for the connection's life. |
| **User** | An authenticated identity within an account. Carries subject-level publish/subscribe permissions (allow/deny lists), queue-group constraints, response permissions, and allowed connection types. |
| **System account `$SYS`** | The privileged administrative account, shared across the entire cluster/supercluster. Hosts server management, account purge, system events. Treated as a "superuser" trust boundary. |
| **Stream (JetStream)** | A named, persisted, ordered log capturing messages matching one or more subjects (e.g. `subjects: ["orders.*"]`), with retention/replication/limits. Distinct from "stream export" (a cross-account share of core-NATS messages). |
| **Consumer** | Tracks delivery position and acknowledgments for a client reading a stream. **Pull** consumers fetch batches; **push** consumers deliver to a `deliver_subject`. May have a `filter_subject` (singular) or `filter_subjects` (plural) narrowing visible stream subjects. |
| **`$JS.API.*`** | The request/reply API surface that drives JetStream. Examples: `$JS.API.STREAM.CREATE.<stream>`, `$JS.API.CONSUMER.CREATE.<stream>.<consumer>[.<filter>]`, `$JS.API.CONSUMER.MSG.NEXT.<stream>.<consumer>`, `$JS.API.ACCOUNT.PURGE.<account>` (system-only). |
| **Export / Import** | The only sanctioned mechanism to move messages between accounts. Exports may be **public** (no `accounts:` list) or **private** (named accounts only). Stream exports are one-directional (exporter → importer); service exports are request/reply endpoints. |
| **Activation token** | A JWT signed by an exporting account authorizing a *specific* importing account to import a *specific* subject. Bound to (exporter, importer, subject); any mismatch must reject. |
| **Operator / Account / User keys** | The decentralized JWT trust chain: operator NKEY → account NKEY → user NKEY. All NATS JWTs are signed Ed25519 only. |
| **Domain (JetStream)** | An independent JetStream namespace, addressed as `$JS.<domain>.API.>`. Used in hub-and-spoke edge topologies. |

## File index

| File | Purpose |
| --- | --- |
| `00_README.md` | This file — project overview, language, domain, terminology. |
| `01_security_model.md` | Permissions model: subject-based publish/subscribe ACLs, the `$JS.API.*` layer, account isolation, intra-account vs cross-account scopes. |
| `02_jetstream_api_contract.md` | JetStream consumer create/update/delete; the `addConsumerWithAction` path; what permissions are checked; `FilterSubject` vs `FilterSubjects` semantics. |
| `03_authorization_boundaries.md` | The known gap between `$JS.API.*` permissions and live subscribe ACLs; tighter scoping via extended subject patterns; the `filter_subject` vs `filter_subjects` asymmetry. |
| `04_invariants.md` | "Subscribe ACL must always be checked when…" / "Cross-account access must never…" invariants derived from docs and maintainer discussion (#4225, #6180). |
| `05_known_issues_and_advisories.md` | GHSAs, CVEs, the #4225 thread, #6180 thread, NATS security policy. |
| `06_issue_tracker_themes.md` | 4–6 themes drawn from GitHub issues (security, authz, JetStream, permissions). |
| `MANIFEST.txt` | One line per file with title + 1-sentence summary. |

## Repository pointers (where to look for the audit target)

- `server/jetstream_api.go` — the JetStream API surface; contains `jsConsumerCreateRequest` and routing into `addConsumerWithAction`. This is the file where the NATS-1 finding lives.
- `server/consumer.go` — `addConsumerWithAction`, consumer configuration validation, FilterSubject/FilterSubjects handling.
- `server/client.go` — subject permission checks (`canSubscribe`, `pubAllowed`, etc.). The functions that JetStream consumer-create currently does **not** consult.
- `server/accounts.go` — account isolation, export/import enforcement.
- `server/auth.go` — user permission resolution.

## Cross-reference convention

Throughout these files, "NATS-1" refers to the audit finding: missing subscribe-ACL enforcement in `addConsumerWithAction`. Issue references (`#4225`, `#6180`, `#3202`) point to `github.com/nats-io/nats-server/issues/<n>`. Advisory IDs (`CVE-…`, `GHSA-…`) resolve at `advisories.nats.io` and `github.com/nats-io/nats-server/security/advisories`.
