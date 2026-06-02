# JetStream API Contract — Consumer Create/Update/Delete and the `addConsumerWithAction` Path

## Sources:
- https://docs.nats.io/nats-concepts/jetstream
- https://docs.nats.io/nats-concepts/jetstream/consumers
- https://docs.nats.io/reference/reference-protocols/nats_api_reference
- https://github.com/nats-io/nats-server/blob/main/server/jetstream_api.go
- https://github.com/nats-io/nats-server/blob/main/server/consumer.go
- https://github.com/nats-io/nats-server/issues/4225
- https://github.com/nats-io/nats-server/issues/6180
- https://github.com/nats-io/nats-server/issues/3202

## Context

JetStream is operated as request/reply on the `$JS.API.*` namespace. Streams are created with `$JS.API.STREAM.CREATE.<stream>`; consumers with `$JS.API.CONSUMER.CREATE.<stream>.<consumer>` (base) or `$JS.API.CONSUMER.CREATE.<stream>.<consumer>.<filter>` (extended, single-filter only). The handler routes the consumer-create request into `addConsumerWithAction` inside the server, which validates the `ConsumerConfig`, enforces stream limits and JetStream-internal invariants, and instantiates the consumer. Crucially, the permission checks applied at this stage cover the **API subject** (the user must be allowed to publish on `$JS.API.CONSUMER.CREATE.*`) — not the user's `subscribe` ACL over the original message subjects the consumer will end up delivering. This is the structural shape of the NATS-1 finding.

## Stream and consumer in one paragraph

A **stream** is a persisted, ordered log capturing messages published on a configured set of subjects (`subjects: ["orders.*"]`). A **consumer** tracks a single reader's position and acknowledgments against a stream and may carry a filter narrowing which stream subjects it sees. Two consumer delivery modes:

- **Pull consumer** — the client requests batches via `$JS.API.CONSUMER.MSG.NEXT.<stream>.<consumer>`.
- **Push consumer** — the server delivers to a `DeliverSubject` the client subscribes to. The `DeliverSubject` is the subject on which the user's subscribe ACL is evaluated for push consumers.

A consumer's filter can be set in two ways, both inside `ConsumerConfig`:
- `FilterSubject` (singular, `string`) — at most one subject pattern.
- `FilterSubjects` (plural, `[]string`) — multiple subject patterns (added later, after the extended-subject mitigation was already in place).

## The relevant API subjects

```
# Consumer lifecycle
$JS.API.CONSUMER.CREATE.<stream>.<consumer>                   # base (durable name supplied in body)
$JS.API.CONSUMER.CREATE.<stream>.<consumer>.<filter>           # extended (single-filter only; filter token = FilterSubject)
$JS.API.CONSUMER.DURABLE.CREATE.<stream>.<consumer>            # legacy durable-create form
$JS.API.CONSUMER.DELETE.<stream>.<consumer>
$JS.API.CONSUMER.INFO.<stream>.<consumer>
$JS.API.CONSUMER.LIST.<stream>
$JS.API.CONSUMER.NAMES.<stream>

# Consumer use
$JS.API.CONSUMER.MSG.NEXT.<stream>.<consumer>                  # pull fetch
$JS.ACK.<stream>.<consumer>.<delivery>.<...>                   # acknowledgments
$JS.FC.<stream>.<consumer>.<id>                                # flow control

# Stream lifecycle (related, same shape)
$JS.API.STREAM.CREATE.<stream>
$JS.API.STREAM.UPDATE.<stream>
$JS.API.STREAM.DELETE.<stream>
$JS.API.STREAM.PURGE.<stream>
```

The base/extended distinction exists for one reason: to give operators a way to lock the consumer create subject down to a specific filter. With the extended form, the filter subject is part of the API request subject, so a publish-permission allow on `$JS.API.CONSUMER.CREATE.TEST.DEREK.foo.*` (or a deny on the base) confines the consumer to exactly that filter. This works **only** when `FilterSubject` (singular) is used; `FilterSubjects` (plural) does not surface in the subject string. Issue #6180 is the explicit request to extend the same lockability to `filter_subjects`.

## `addConsumerWithAction` — what is and is not checked

The request is decoded into a `jsConsumerCreateRequest` and forwarded into `addConsumerWithAction(stream *stream, cfg *ConsumerConfig, action ConsumerAction, …)`. The checks performed at this layer are JetStream-internal correctness checks and account-level resource limits:

What IS checked (paraphrased from current source / docs):

- **Account-scoped resource limits** — `MaxConsumers`, max streams, max storage, replica count, MaxAckPending, etc.
- **Stream membership** — the target stream exists in the caller's account.
- **Consumer configuration validity** — durable name, deliver subject vs deliver group, ack policy compatibility, replay policy, OptStartSeq/Time consistency, deliver-subject syntax, pull vs push exclusivity.
- **Filter validity vs stream subjects** — `FilterSubject` and each element of `FilterSubjects` must be a valid subject pattern that overlaps the stream's captured `Subjects`.
- **Singular/plural exclusivity** — `FilterSubject` and `FilterSubjects` are mutually exclusive within a single ConsumerConfig.
- **Republishing / mirror / source constraints** — JetStream-internal correctness rules.
- **API-subject publish permission** — implicitly, by virtue of the request having reached `addConsumerWithAction` at all; the client had to be allowed to publish to `$JS.API.CONSUMER.CREATE.<stream>.<consumer>[.<filter>]`. For the extended form, this incidentally limits the *singular* filter via the core publish-permission machinery (see `03_authorization_boundaries.md`).

What is NOT checked (the NATS-1 surface):

- **The caller's `subscribe` permission against `FilterSubject` / `FilterSubjects` / the stream's captured subjects.** A user able to publish `$JS.API.CONSUMER.CREATE.*` (or even `$JS.API.>`) can create a consumer whose `FilterSubject` or `FilterSubjects` covers subjects the user would be denied from subscribing to directly. This is the explicit content of issue #4225 and of community write-up "NATS Weekly #31" (which became issue #3202).
- **The caller's `subscribe` permission against subjects delivered through the consumer at MSG.NEXT time.** Consumed messages are delivered on the consumer's delivery/inbox subject, not their original subject, so per-subject subscribe ACLs are never re-applied to the delivered message. The user effectively reads original-subject messages through a renamed delivery channel.
- **The caller's `publish` permission against the stream's captured subjects when creating a stream.** Symmetric to consumer-create on the read side: a `$JS.API.STREAM.CREATE.*` allow lets a user create a stream capturing `no.>` even with no pub/sub on `no.>` (shaunco's example in #4225).

The maintainer's own description of the design (`derekcollison` in #4225):

> "We are aware of the discrepancy between security models etc. We have been working on some ideas to help normalize. Under the covers it still will result in the low level understanding of consumers and the subjects they use to interact etc."

> "FYI for single subject filtered consumers you can lock that down already. The client will use an extended version of consumer create that appends the filter subject to the end of the create subject itself. For instance if I want to create a consumer named DEREK on a stream called TEST, that has a filtered subject of `foo.*`, the subject the clients will use is `$JS.API.CONSUMER.CREATE.TEST.DEREK.foo.*`. This can be used for user publish permissions at the core level. Some users/customers who want to be pedantic also put in a deny perm on `$JS.API.CONSUMER.CREATE.TEST.DEREK`."

The mitigation is **operator-side configuration**, not a server-side ACL check inside `addConsumerWithAction`. There is no equivalent mitigation for `FilterSubjects` (plural); issue #6180 documents that residual gap explicitly.

## FilterSubject vs FilterSubjects semantics

| Property | `FilterSubject` (singular) | `FilterSubjects` (plural) |
| --- | --- | --- |
| Type in `ConsumerConfig` | `string` | `[]string` |
| Number of patterns | At most one | Any number |
| Appears in API request subject | Yes — appended as the final token(s) of `$JS.API.CONSUMER.CREATE.<stream>.<consumer>.<filter>` | **No** — only present in the JSON request body |
| Lockable via core publish permission | **Yes** — operator can scope `$JS.API.CONSUMER.CREATE.<stream>.<consumer>.<filter>` and deny the base form | **No** — there is no subject-level handle on the body's plural filter list |
| Validated against stream subjects | Yes (`FilterSubject` must overlap stream Subjects) | Yes (each element must overlap) |
| Re-checked against caller's subscribe ACL | **No** | **No** |
| Mutually exclusive | Yes — a `ConsumerConfig` may set one OR the other, never both | Same |

Issue #6180's "Current Behavior" summary on this asymmetry:
- Permissions such as `$JS.API.CONSUMER.CREATE.my_stream.*.my_stream.123.>` work effectively for `filter_subject`.
- The equivalent does not apply to `filter_subjects`, leaving users unable to block or enforce restrictions when multiple subjects are provided.

## Push consumer delivery and the `DeliverSubject` evaluation point

A push consumer has a `DeliverSubject` — the subject the server publishes consumed messages to. The client then subscribes to that subject to receive them. The subscribe ACL **is** evaluated against `DeliverSubject` at subscribe time (because it is an ordinary subscription), but the user's subscribe ACL on the *stream's captured subjects* is irrelevant — once a message lands on the `DeliverSubject`, only the ACL on `DeliverSubject` matters. Issue #6016 documents wildcard matching problems between `DeliverSubject` and a wildcarded subscription. The same asymmetry as pull consumers applies: subscribe permissions on original subjects are not re-checked.

## Update and delete

- **`$JS.API.CONSUMER.DELETE.<stream>.<consumer>`** — like create, gated by the publish permission on the API subject, not by the user's pub/sub on the consumer's filter subjects.
- **Update path** — consumer-create with the same name updates an existing consumer; the action variant (`ConsumerActionUpdate` / `ConsumerActionCreateOrUpdate`) is selected inside `addConsumerWithAction`. Mutations of `FilterSubject` / `FilterSubjects` on update flow through the same code path as create and inherit the same missing subscribe-ACL check.

## Where in the source

These docs point a reviewer at where to verify the gap:

- `server/jetstream_api.go` — `jsConsumerCreateRequest`, the request decoder, the routing into `addConsumerWithAction`. Look for any call that resolves the caller's user/account-level subscribe permission against `cfg.FilterSubject` / `cfg.FilterSubjects` / the target stream's `Subjects`. The current code does the API-subject publish check (the request had to reach this handler) but does not perform that subscribe-ACL cross-check.
- `server/consumer.go` — `addConsumerWithAction`, `validateConsumerConfig`, and the consumer's run loop. The validation chain enforces JetStream-internal correctness and stream-overlap, but does not consult the client's `subscribe` allow/deny.
- `server/client.go` — `canSubscribe` and the pub/sub permission machinery. These are the functions a future fix would have to call from the consumer-create path.

## Security-Relevant Considerations

- **The API-subject publish permission is the only subject-level ACL that `addConsumerWithAction` indirectly relies on.** Everything else it checks (config validity, stream overlap, limits) is JetStream correctness, not user authorization over message contents.
- **The extended consumer-create subject (`$JS.API.CONSUMER.CREATE.<stream>.<consumer>.<filter>`) is the only mechanism for operator-side restriction of `FilterSubject`** — and it requires both (a) clients that consistently use the extended form (modern client libraries do) and (b) a matching deny on the bare `$JS.API.CONSUMER.CREATE.<stream>.<consumer>` to prevent the base form from being used to escape the scoping.
- **`FilterSubjects` (plural) has no subject-level handle and cannot be locked down with the same technique.** Until the server enforces `FilterSubjects` against the caller's subscribe ACL, operators have no way to restrict multi-filter consumers (issue #6180).
- **A consumer's actual data exfiltration path is `$JS.API.CONSUMER.MSG.NEXT.<stream>.<consumer>` or the push `DeliverSubject`** — neither carries the original message subject in a way that triggers re-checking the user's subscribe ACL against those original subjects.
- **Stream-create and consumer-create are symmetric on the write side and read side of the gap.** A `$JS.API.STREAM.CREATE.*` grant lets a user define what subjects a stream captures; a `$JS.API.CONSUMER.CREATE.*` grant lets the user define what subjects a consumer filters. Neither is re-checked against the user's underlying pub/sub permissions on those subjects.
