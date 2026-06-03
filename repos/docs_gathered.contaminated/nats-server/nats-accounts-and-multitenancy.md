# NATS Accounts and Multi-Tenancy (the isolation boundary)

Sources:
- https://github.com/nats-io/nats.docs/blob/master/running-a-nats-service/configuration/securing_nats/accounts.md
- https://docs.nats.io/running-a-nats-service/configuration/securing_nats/accounts
- https://advisories.nats.io/CVE/CVE-2021-3127.txt
- https://github.com/nats-io/nats-server/issues/3108
- https://advisories.nats.io/CVE/CVE-2022-28357.txt
- https://docs.nats.io/using-nats/nats-tools/nsc/streams
- https://docs.nats.io/using-nats/nats-tools/nsc/services

## Accounts as the isolation boundary

An **account** is a securely isolated communication context. Accounts group clients and isolate them from clients in other accounts, providing multi-tenancy. With accounts, **the subject space is not globally shared** — each account has its own private subject namespace, so two accounts can both use `orders.>` without any overlap or leakage. Messages published by users in account `A` are not visible to users in account `B` unless `A` explicitly exports and `B` explicitly imports.

```
accounts: {
    A: { users: [ {user: a, password: a} ] },
    B: { users: [ {user: b, password: b} ] },
}
```
> Accounts `A` and `B` are fully isolated. A message published by `a` on subject `orders.new` cannot reach `b`, even though both accounts are free to use the subject `orders.new` independently.

Each account entry may contain `users`, `exports`, and `imports`. A user's account is fixed by its credentials; **a client cannot select or switch its account** (the experimental account-assumption bug that allowed this was CVE-2022-24450 — a total isolation breach).

### The `$G` global account and `no_auth_user`
Legacy `authorization {}` blocks place users in the implicit global account `$G`. `no_auth_user` maps unauthenticated connections to a named user/account:

```
accounts: { A: { users: [{user: a, password: a}] }, B: { users: [{user: b, password: b}] } }
no_auth_user: a
```
`no_auth_user` does **not** work with nkeys or bcrypted passwords. A misconfiguration interaction here (a `$SYS`-only `accounts` block implicitly creating a `$G` `no_auth_user`) produced an auth-bypass: CVE-2023-47090.

## The system account `$SYS`

`$SYS` is the special **privileged** account used for server management and System Events. It is **shared across an entire cluster/supercluster**. NATS treats `$SYS` as a "superuser" trust boundary by design — by its own security model, a system-account client performing an unexpected action (e.g. CVE-2022-28357 arbitrary file write) "does not cross a privilege boundary," but it does enable **lateral movement across the whole deployment**. Regular-account users must never be able to reach `$SYS`-only operations; certain JetStream admin APIs failing to enforce this was CVE-2025-30215.

## Cross-account exports and imports

The only sanctioned way to move messages between accounts is **exporting** a stream or service from one account and **importing** it into another. Each account controls what it exports and imports. Two kinds:

- **Stream** = messages your application *publishes* that importers may *consume* (one-directional, exporter → importer). (Note: this "stream" is a *stream of core-NATS messages*, NOT a JetStream stream — an unfortunate terminology collision.)
- **Service** = a request/reply endpoint your application *subscribes to and answers*; importers may *make requests* to it.

### Export configuration map
```
accounts: {
  A: {
    users: [ {user: a, password: a} ]
    exports: [
      {stream: puba.>}                       # PUBLIC stream — any account may import
      {service: pubq.>}                       # PUBLIC service — any account may request
      {stream: b.>,  accounts: [B]}           # PRIVATE stream — only account B may import
      {service: q.b, accounts: [B]}           # PRIVATE service — only account B may request
    ]
  }
}
```
| Property | Meaning |
| --- | --- |
| `stream` | subject (may have wildcards) the account publishes (exclusive of `service`) |
| `service` | subject (may have wildcards) the account subscribes to (exclusive of `stream`) |
| `accounts` | list of account names allowed to import. **If omitted, the export is PUBLIC and any account can import it.** |
| `response_type` | `single` or `stream` — shape of a service reply |

### Import configuration map
```
accounts: {
  B: {
    users: [ {user: b, password: b} ]
    imports: [
      {stream:  {account: A, subject: b.>}}      # consume A's private stream b.>
      {service: {account: A, subject: q.b}}      # may request A's private service q.b
    ]
  }
  C: {
    users: [ {user: c, password: c} ]
    imports: [
      {stream:  {account: A, subject: puba.>}, prefix: from_a}  # remap into from_a.puba.>
      {service: {account: A, subject: pubq.C}, to: Q}           # publish locally to Q -> A's pubq.C
    ]
  }
}
```
- Every import requires a corresponding export on the exporting account. **Accounts cannot self-import.**
- `prefix` (streams) and `to` (services) remap the subject locally so the importer doesn't depend on the exporter's naming. Service imports cannot use wildcards (hence remapping); stream imports may.
- The `source configuration map` (`{account, subject}`) names the remote export being imported.

### Activation tokens (private exports under decentralized JWT)
For private exports in JWT-based (operator) mode, the exporter issues an **activation token**: a JWT signed by the exporting account authorizing a *specific* importing account to import a *specific* subject. The token may subset the exported subject. **The token is bound to (exporting account = issuer, importing account, subject).** All three bindings must be enforced — failing to reject a mismatch was CVE-2021-3127, which let any account replay another's token to import arbitrary subjects.

## Account propagation across leaf nodes / gateways / clusters

- Subject interest and account scoping propagate across **routes** (cluster) and **gateways** (supercluster); the same isolation holds globally.
- A **leaf node** extends one account into the leaf and is **not fully trusted** unless the system account is bridged. Identity/headers from a leaf must be validated by the hub, not propagated blindly (CVE-2026-33246).
- JetStream streams can be shared across accounts, but the recommended pattern is **mirror/source** (a stream in account B mirrors/sources a stream in account A) rather than letting B's clients directly use A's stream — a more "locked-down" sharing model.

## Security-Relevant Considerations

Invariants that must hold for one account never to see another's subjects/messages:

- **An account is a hard subject-namespace boundary.** For any subject `S`, a message published in account `A` on `S` must be deliverable only to subscribers in `A` — unless `A` has an `export` of `S` (or a wildcard covering `S`) AND the receiving account `B` has a matching `import`. If subject matching for delivery ignores the account, tenants leak into each other.
- **A client's account is determined solely by its credentials and is immutable.** No protocol field, header, or handshake option may let a client change accounts. (CVE-2022-24450.)
- **A public export (no `accounts:` list) is importable by every account; a private export is importable only by the named accounts.** Code must not treat a private export as public, or omit the allowed-accounts check — doing so exposes the export to all tenants.
- **Activation/import tokens must be rejected (not merely warned about) on any binding mismatch.** The token binds exporter (issuer), importer, and exact subject; a client importing on a subject broader than the token grants, or an importer that isn't the token's named account, must be rejected. (CVE-2021-3127.)
- **Subject remapping (`prefix`/`to`) must not widen the imported subject set beyond the export grant.** Remapping is cosmetic/local; it must never let an importer reach subjects the export didn't authorize.
- **The system account `$SYS` is shared cluster-wide and privileged; regular-account users must never reach `$SYS`-scoped operations** (server management, account purge/move). Confusing a `$JS.>` publish grant with system-account authorization is an isolation breach (CVE-2025-30215).
- **Account isolation must hold in the JetStream layer too.** A persisted stream/consumer belongs to exactly one account; its `$JS.API.*` operations and stored data are account-scoped. (See `nats-jetstream.md`; community concern about JetStream consumption escaping subject permissions is documented in `nats-github-issues.md`, e.g. issue #3108 and #3202.)
- **Leaf nodes and gateways must preserve, not erode, account scoping and server-asserted identity.** A partially-trusted leaf must not be allowed to assert membership in or inject messages destined for an account it doesn't legitimately represent, nor propagate identity headers unchecked.
