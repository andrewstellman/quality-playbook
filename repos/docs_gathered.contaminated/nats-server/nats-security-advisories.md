# NATS Server Published Security Advisories (GHSA / CVE)

Sources:
- https://advisories.nats.io/
- https://github.com/nats-io/nats-server/security/advisories
- https://github.com/advisories?query=nats-server
- https://github.com/nats-io/nats-server/security/advisories/GHSA-fhg8-qxh5-7q3w
- https://github.com/nats-io/nats-server/security/advisories/GHSA-g6w6-r76c-28j7
- https://github.com/nats-io/nats-server/security/advisories/GHSA-fr2g-9hjm-wr23
- https://github.com/nats-io/nats-server/security/advisories/GHSA-6h3m-36w8-hv68
- https://github.com/nats-io/nats-server/security/advisories/GHSA-8m2x-3m6q-6w8j
- https://github.com/nats-io/nats-server/security/advisories/GHSA-8r68-gvr4-jh7j
- https://github.com/advisories/GHSA-qrvq-68c2-7grw
- https://advisories.nats.io/CVE/secnote-2026-12.txt
- https://advisories.nats.io/CVE/secnote-2026-09.txt
- https://advisories.nats.io/CVE/secnote-2026-08.txt
- https://advisories.nats.io/CVE/secnote-2026-07.txt
- https://advisories.nats.io/CVE/secnote-2026-13.txt
- https://advisories.nats.io/CVE/secnote-2023-02.txt
- https://advisories.nats.io/CVE/CVE-2021-3127.txt
- https://advisories.nats.io/CVE/CVE-2022-29946.txt
- https://advisories.nats.io/CVE/CVE-2022-28357.txt
- https://advisories.nats.io/CVE/CVE-2020-26892.txt

## Summary

NATS Server has a long and instructive published advisory history, maintained canonically at `advisories.nats.io` and mirrored as GitHub Security Advisories on `nats-io/nats-server` (plus `nats-io/jwt` and `nats-io/nkeys` for the supporting libraries). The advisories cluster into a small number of recurring failure modes that map directly onto the system's security-critical invariants:

1. **Account-isolation / authorization bypass** — the most severe class. Bugs where an authenticated client in one account can act in, or destroy data belonging to, another account (CVE-2022-24450, CVE-2025-30215), where import/export grants are not properly bound (CVE-2021-3127), or where a JetStream admin operation is not restricted to the system account (CVE-2025-30215, CVE-2026-33222).
2. **Permission / ACL evaluation correctness** — negative (deny) permissions not honored in a queue-subscription scenario (CVE-2022-29946); MQTT subject ACLs not applied in the `$MQTT.>` namespace (CVE-2026-33217).
3. **Identity / authentication integrity** — spoofable internal identity headers (CVE-2026-33223, CVE-2026-33246), mTLS DN-mapping bypass (CVE-2026-33248), credential-expiry mishandling in the JWT library (CVE-2020-26892), and the nkeys fixed-key encryption flaw affecting auth callout (CVE-2023-46129).
4. **Path traversal / arbitrary file write** — JetStream restore "Zip Slip" (CVE-2022-26652) and system-account account-sync file write (CVE-2022-28357).
5. **Pre-auth denial of service** — WebSocket compression bomb and unbounded memory (CVE-2026-27571, CVE-2026-33219), leafnode pre-auth panics (CVE-2026-29785), account import loops (CVE-2020-28466, CVE-2022-42709).

Every ID below was verified against a live GitHub or `advisories.nats.io` URL. Where an advisory page could not be fetched in full, the canonical `advisories.nats.io` secnote text was used and the limitation is noted. A scheduled security release (nats-server 2.12.7 & 2.11.16) is noted on `advisories.nats.io` for 2026-04-14.

---

## CVE-2022-24450 (GHSA-g6w6-r76c-28j7): Unconstrained account assumption by authenticated clients

**Status**: Fixed in 2.7.2 (nats-streaming-server 0.24.1)
**Impact**: Full account-isolation bypass — any authenticated client can switch into ANY account, including the privileged System account `$SYS`
**Category**: Incorrect Authorization (CWE-863)
**Affected**: nats-server `2.0.0 <= V <= 2.7.1`; nats-streaming-server `0.15.0 <= V <= 0.24.0` | **Fixed**: nats-server `2.7.2`, nats-streaming-server `0.24.1` | **Severity**: Critical

### Root cause
A coding error in a long-extant, undocumented experimental feature (dynamically provisioned "sandbox" accounts). A client crafting the initial protocol-level handshake could, *with valid credentials for any account*, specify a target account and switch into it immediately — including any other tenant and including `$SYS`, which controls core server operations. Even deployments not using multi-tenancy were vulnerable: normal users could elect to be in the System account.

### Expected / Actual
- **Expected**: a client's account is fixed by its credentials; it cannot select or assume a different account.
- **Actual**: the handshake honored a client-supplied target account, granting cross-tenant access and privilege escalation. The fix removed the feature entirely (no client support, never documented).

---

## CVE-2025-30215 (GHSA-fhg8-qxh5-7q3w): Failure to authorize certain JetStream admin APIs

**Status**: Fixed in 2.10.27 and 2.11.1 (NATS-advisory-ID 2025-01; GO-2025-3600)
**Impact**: Cross-account data destruction and administrative action by any authorized user; violates account isolation
**Category**: Improper Authorization (CWE-285)
**Affected**: `<= 2.11.0` (from v2.2.0 onward) | **Fixed**: `2.10.27`, `2.11.1` | **Severity**: Critical (CVSS 9.6, `AV:N/AC:L/PR:L/UI:N/S:C/C:N/I:H/A:H`)

### Root cause
Four admin-level JetStream APIs lacked authorization checks restricting them to system-account users: account purge (`$JS.API.ACCOUNT.PURGE.*`), server remove (`$JS.API.SERVER.REMOVE`), account stream move (`$JS.API.ACCOUNT.STREAM.MOVE.*.*`), and cancel-move. Any user with permission to publish on `$JS.>` (commonly granted to per-account "admin" users, or implied by a `>` grant) could execute them, **including across account boundaries**.

### Expected / Actual
- **Expected**: account-purge / server-remove / stream-move are system-account-only operations, refused for regular-account users; `$JS.API.META.LEADER.STEPDOWN` is the correct pattern (it does restrict to system-account users).
- **Actual**: a user in account `TEST2` could publish `$JS.API.ACCOUNT.PURGE.TEST` and destroy all JetStream data in the unrelated account `TEST` (reproduced in the advisory PoC). Confidentiality was not breached (stream contents not disclosed) but integrity/availability were.

---

## CVE-2026-33222 (GHSA-9983-vrx2-fg9c): JetStream stream-restore endpoint auth bypass

**Status**: Fixed in 2.11.15 and 2.12.6 (NATS-advisory-ID 2026-12)
**Impact**: A user authorized to restore one stream can restore to *other* stream names, overwriting/affecting data they should not reach
**Category**: Improper Authorization (CWE-285)
**Affected**: any version before `2.11.15` or `2.12.6` | **Fixed**: `2.11.15`, `2.12.6` | **Severity**: Moderate

### Root cause
Users with JetStream admin API access to restore a stream were not constrained to the stream name(s) their restore permission targeted; the restore endpoint did not verify that the target stream name was within the caller's authorized scope.

### Expected / Actual
- **Expected**: a restore is scoped to the stream(s) the caller is permitted to manage.
- **Actual**: the caller could restore to arbitrary stream names, impacting protected data. Workaround: temporarily remove limited JetStream-restore permissions until patched.
- **Note**: the GHSA HTML page could not be fetched directly during gathering; details taken from the canonical `secnote-2026-12.txt`.

---

## CVE-2021-3127 (nats-server GHSA-j756-f273-xhp4 / jwt GHSA-62mh-w5cv-p88c): Import token permissions checking not enforced

**Status**: Fixed in jwt 2.0.1; nats-server 2.2.0 (NATS-advisory-ID 2021-02)
**Impact**: Any account can reuse another account's import (activation) token to import ANY subject from an exporting account — cross-account data access
**Category**: Improper enforcement of import-token bindings (account isolation)
**Affected**: jwt `< 2.0.1`; nats-server `2.0.0`–`2.1.9` | **Fixed**: jwt `2.0.1`, nats-server `2.2.0` | **Severity**: High

### Root cause
The `nats-io/jwt` library *warned* on mismatches in the import token's bindings instead of *rejecting* the token. Because the binding to the importing account was not rejected, any account could take an import token used by any other account, re-use it for itself, and import *any* subject from the exporting account — not just the subject named in the token. Account JWTs are treated as semi-public, so an attacker could enumerate accounts and harvest import tokens.

### Expected / Actual
- **Expected**: an activation/import token is cryptographically bound to (a) the issuing/exporting account, (b) the specific importing account, and (c) the specific subject; any mismatch rejects the import.
- **Actual**: mismatches only logged a warning; the token's `account`/`subject` bindings were not enforced, so a private export could be imported by an unauthorized account on an arbitrary subject. An audit script (`jwt-audit.py`) shipped with the advisory flags `token grants X but used to access Y` abuse.

---

## CVE-2022-29946: Negative user permissions not enforced in one scenario

**Status**: Fixed in nats-server 2.8.2; nats-streaming-server 0.24.6 (NATS-advisory-ID 2022-04)
**Impact**: A queue subscriber to a wildcard receives messages on a subject that the user's ACL explicitly denies
**Category**: Permission evaluation correctness — deny not applied to implicit queue-group delivery
**Affected**: nats-server `2.0.0`–`2.8.1` | **Fixed**: nats-server `2.8.2` | **Severity**: (per advisory)

### Root cause
If a user ACL combined a positive (allow) subscribe permission on a wildcard subject with a negative (deny) permission on a specific subject matched by that wildcard, a *queue subscriber* to the wildcard could still receive messages on the denied subject. The direct ability to subscribe to the denied subject was correctly blocked, but the implicit delivery via the wildcard queue subscription did not receive an implicit filter to hide denied subjects.

### Expected / Actual
- **Expected**: a deny on `X` removes `X` from everything delivered to that user, including messages delivered via an allowed wildcard queue subscription that overlaps `X`.
- **Actual**: the deny was honored for explicit subscription but not for the wildcard-queue delivery path. Workaround per advisory: "only add access, never try to deny it" — i.e. don't rely on deny over a broader allow.

---

## CVE-2026-33217 (GHSA-jxxm-27vp-c3m5): MQTT ACLs ineffective

**Status**: Fixed in 2.11.15 and 2.12.6 (NATS-advisory-ID 2026-07)
**Impact**: MQTT clients bypass subject ACL checks
**Category**: Permission/ACL not applied to a namespace
**Affected**: any version before `2.11.15` or `2.12.6` | **Fixed**: `2.11.15`, `2.12.6` | **Severity**: (per advisory)

### Root cause
Subject ACLs were not applied in the `$MQTT.>` namespace, so MQTT clients could bypass ACL checks for MQTT subjects.

### Expected / Actual
- **Expected**: subject permissions apply uniformly across all client interfaces, including the MQTT bridge namespace.
- **Actual**: the MQTT subject namespace escaped ACL evaluation.

---

## CVE-2026-33223 (GHSA-pwx7-fx9r-hr4h): Internal identity header `Nats-Request-Info` spoofable

**Status**: Fixed in 2.11.15 and 2.12.6 (NATS-advisory-ID 2026-09)
**Impact**: An authenticated client can spoof its identity to services that trust the server-provided identity header
**Category**: Identity integrity — incomplete header stripping
**Affected**: any version before `2.11.15` or `2.12.6` | **Fixed**: `2.11.15`, `2.12.6` | **Severity**: (per advisory)

### Root cause
The `Nats-Request-Info:` header is meant to be a server-guaranteed statement of the requester's account/user identity. Stripping this header from *inbound* client messages was not fully effective, so an attacker with valid credentials on any regular client interface could inject/spoof the header and impersonate another identity to downstream services.

### Expected / Actual
- **Expected**: server-asserted identity headers on inbound client messages are always stripped and re-applied by the server; clients cannot set them.
- **Actual**: incomplete stripping let a client supply its own value. Related: **CVE-2026-33246 (GHSA-55h8-8g96-x4hj)** — a leafnode (not fully trusted unless the system account is bridged) could propagate `Nats-Request-Info` identity claims unchecked, allowing the same spoofing across a leafnode boundary.

---

## CVE-2026-33248 (GHSA-3f24-pcvm-5jqc): mTLS DN-based identity auth bypass for some DN patterns

**Status**: Fixed in 2.11.15 and 2.12.6 (NATS-advisory-ID 2026-13)
**Impact**: Authentication bypass when deriving NATS identity from a TLS client-certificate Subject DN
**Category**: Identity-mapping correctness (authentication bypass)
**Affected**: any version before `2.11.15` or `2.12.6` | **Fixed**: `2.11.15`, `2.12.6` | **Severity**: (per advisory; described as unlikely to exploit)

### Root cause
With `verify_and_map` mTLS, certain RDN patterns in the client certificate's Subject DN were not correctly enforced when mapping to a NATS identity, allowing a bypass. Requires a valid certificate from an already-trusted client CA and an unusual DN naming pattern.

### Expected / Actual
- **Expected**: the DN-to-identity mapping is exact and unambiguous; only the intended certificate maps to a given NATS user.
- **Actual**: some DN constructions could be mapped to an unintended identity.

---

## CVE-2023-47090 (GHSA-fr2g-9hjm-wr23): Adding accounts for just the system account adds auth bypass

**Status**: Fixed in 2.10.2 and 2.9.23 (NATS-advisory-ID 2023-01; GO-2023-2133)
**Impact**: Clients can connect *without authentication* when an `authorization` block is used alongside an `accounts` block that only defines `$SYS`
**Category**: Authentication Bypass by Primary Weakness (CWE-305)
**Affected**: `2.2.0 <= V <= 2.9.22` and `2.10.1` | **Fixed**: `2.10.2`, `2.9.23` | **Severity**: High

### Root cause
When the only account added was the system account `$SYS`, the server created an implicit user in the global account `$G` and set it as the `no_auth_user` — re-enabling the "connect without authentication" behavior. Administrators using a legacy `authorization` block (whose users live in `$G`) would silently get unauthenticated access while believing auth was enabled.

### Expected / Actual
- **Expected**: defining users (in `authorization` or `accounts`) means unauthenticated connections are refused.
- **Actual**: a `$SYS`-only `accounts` block implicitly created a `no_auth_user`, allowing anonymous connection. Workaround: define a second (empty) account; fixed versions inhibit the implicit `$G` `no_auth_user`.

```
accounts {
    SYS: { users: [ { user: sysuser, password: ... } ] }
    DUMMY: {}   # workaround before 2.10.2: an empty second account inhibits the implicit no_auth_user
}
system_account: SYS
```

---

## CVE-2022-26652 (GHSA-6h3m-36w8-hv68): Arbitrary file write by JetStream-enabled users (Zip Slip)

**Status**: Fixed in 2.7.4; nats-streaming-server 0.24.3 (canonical CVE-2022-26652.txt)
**Impact**: A JetStream user can cause the server to write arbitrary content to an attacker-controlled filename via stream restore
**Category**: Path Traversal `/dir/../filename` (CWE-26)
**Affected**: nats-server `2.2.0`–`2.7.3` | **Fixed**: `2.7.4` | **Severity**: High

### Root cause
JetStream stream backup/restore uses a tar archive. Inadequate sanitization of filenames inside the archive permitted a "Zip Slip" path-traversal write outside the JetStream storage directory. Mitigation: filesystem sandboxing (the shipped `util/nats-server-hardened.service` with `ProtectSystem=strict`, `PrivateTmp=true`, narrow `ReadWritePaths`).

---

## CVE-2022-28357: Arbitrary file write from the privileged system account

**Status**: Fixed in 2.8.0; nats-streaming-server 0.24.3 (NATS-advisory-ID 2022-03)
**Impact**: Anyone able to publish arbitrary messages to `$SYS` can cause arbitrary file write as the NATS user
**Category**: Path/filename construction in account synchronization (within the privileged system-account trust boundary)
**Affected**: nats-server `2.2.0`–`2.7.4` | **Fixed**: `2.8.0` | **Severity**: High

### Root cause / note on the trust model
An inadequate filename check in account-synchronization filename construction (performed in `$SYS`) allowed arbitrary file write. NATS explicitly treats the **system account as privileged ("superuser")**, so this "does not cross a privilege boundary" by NATS's own security model — but a CVE was requested to draw attention to it. **Critically, `$SYS` is shared across a cluster/supercluster, so this enables lateral movement** within such a deployment. Mitigation: sandbox and run as a dedicated unprivileged user.

---

## CVE-2023-46129 (nkeys GHSA-mr45-rx8q-wcm9): xkeys Seal encryption used a fixed (all-zeros) key

**Status**: Fixed in nkeys 0.4.6; nats-server 2.10.4 (NATS-advisory-ID 2023-02)
**Impact**: Auth-callout request payloads (which include the supplied user password) were effectively encrypted to an all-zeros key — potential credential exposure
**Category**: Cryptographic key-handling defect
**Affected**: nkeys `0.4.0`–`0.4.5`; nats-server `2.10.0`–`2.10.3` | **Fixed**: nkeys `0.4.6`, nats-server `2.10.4` | **Severity**: (per advisory)

### Root cause
The nkeys "xkeys" encryption path passed a buffer **by value** into an internal function that mutated it to populate the encryption key; as a result all encryption used an all-zeros key. Affects encryption only (not signing). Used by the Auth Callout feature (2.10+), whose requests carry the user password — so in callout deployments sharing an account with untrusted users, or without TLS, this can expose credentials.

---

## CVE-2020-26892 (jwt GHSA-4w5x-x539-ppf5 / nats-server GHSA-2c64-vj8g-vwrq): Incorrect handling of credential expiry

**Status**: Fixed in jwt 1.1.0; nats-server 2.1.9 (NATS-advisory-ID 2020-02)
**Impact**: Time-based credential (JWT) expiry did not work — expired credentials kept working
**Category**: Improper access control (credential lifetime)
**Affected**: jwt `< 1.1.0`; nats-server `2.0.0`–`2.1.8` | **Fixed**: jwt `1.1.0`, nats-server `2.1.9` | **Severity**: (per advisory)

### Root cause
The `nats-io/jwt` library's `IsRevoked()` misused its own API and expiration was not enforced; a corrected `IsClaimRevoked()` was introduced and the server updated to use it (the old `IsRevoked()` now always returns true).

---

## Denial-of-service advisories (pre-auth and import-loop)

These do not breach authorization but bear on availability invariants.

- **CVE-2026-27571 (GHSA-qrvq-68c2-7grw)** — WebSockets pre-auth memory DoS via a **compression bomb**. The implementation bounded the final NATS-message size but not the memory consumed decompressing into the stream. Compression is negotiated **before authentication**, so no credentials are required. **Affected**: `< 2.11.12`, and `2.12.0-RC.1 <= V < 2.12.3` | **Fixed**: `2.11.12`, `2.12.3` | CWE-409/CWE-770; CVSS 5.9.
- **CVE-2026-33219 (GHSA-8r68-gvr4-jh7j)** — WebSockets pre-auth DoS (unbounded memory before auth), a milder, non-compression variant of CVE-2026-27571 requiring significant attacker bandwidth. **Affected**: `<= 2.12.5`, `<= 2.11.14` | **Fixed**: `2.12.6`, `2.11.15` | CVSS 5.3. Workaround: disable WebSockets if unused.
- **CVE-2026-33249 (GHSA-8m2x-3m6q-6w8j)** — Message tracing can be redirected to an arbitrary subject. A valid client using message-tracing headers can direct trace messages to any valid subject, *including subjects it has no publish permission for*. The payload is a valid trace message, not attacker-chosen. **Affected**: `>= 2.11.0, <= 2.11.14`, `<= 2.12.5` | **Fixed**: `2.12.6`, `2.11.15` | CVSS 4.3. (Permission-bypass-adjacent: trace delivery escapes the publish ACL.)
- **CVE-2026-29785 (GHSA-52jh-2xxh-pwh6)** and **CVE-2026-27889 (GHSA-pq2q-rcw4-3hr6)** — leafnode / WebSockets pre-auth server panic/crash (2026-03-09). (Verified via `advisories.nats.io` listing; pages not individually fetched.)
- **CVE-2020-28466** and **CVE-2022-42709** — account *service-import loops* causing server DoS; **CVE-2022-42708** — server panic from inappropriate JetStream replica count. (Verified via `advisories.nats.io` listing.)
- Additional listed-but-not-individually-fetched (all from the `advisories.nats.io` index): **CVE-2026-33216 (GHSA-v722-jcv5-w7mc)** MQTT plaintext password disclosure; **CVE-2026-33215 (GHSA-fcjp-h8cc-6879)** MQTT hijacking via Client ID; **CVE-2026-33247 (GHSA-x6g4-f6q3-fqvv)** credentials via command-line argv exposed to monitoring; **CVE-2026-33218 (GHSA-vprv-35vv-q339)** pre-auth panic in leafnode handling; **CVE-2021-32026** TLS ciphersuite settings missing with CLI flags; **CVE-2020-26521** nil-deref panic in JWT library; **CVE-2020-26149** info disclosure in JS client libraries.

---

## Security-Relevant Considerations

The advisory history defines the system's intended security invariants by showing what breaks when they are violated:

- **Account is an absolute isolation boundary; a client's account is fixed by its credentials and is never client-selectable.** CVE-2022-24450 shows the catastrophe when this fails: any authenticated user becomes any account, including `$SYS`. The server must never honor a client-supplied target account at handshake time.
- **System-account-only operations must be enforced as system-account-only, not gated merely by a broad `$JS.>` publish grant.** CVE-2025-30215 (account purge cross-account) and CVE-2026-33222 (restore to arbitrary stream) show that authorization for admin JetStream APIs must check the *caller's account/role*, not just that it can publish on the API subject. `$JS.API.META.LEADER.STEPDOWN` is the correct reference pattern.
- **Cross-account import/export grants must be cryptographically bound to (exporting account, importing account, exact subject) and any mismatch must REJECT, not warn.** CVE-2021-3127 is the canonical violation: a warning-instead-of-rejection let any account replay another's import token to read arbitrary exported subjects.
- **Deny must take precedence over allow on every delivery path, including implicit wildcard/queue-group delivery and JetStream consumption — not just explicit subscriptions.** CVE-2022-29946 shows a deny honored for direct subscription but leaking through a wildcard queue subscription. A subject the user is denied must be filtered out of everything delivered to that user.
- **Subject ACLs must apply uniformly across all client interfaces and namespaces** (core NATS, MQTT `$MQTT.>`, WebSockets, leafnodes). CVE-2026-33217 (MQTT ACLs ineffective) shows a namespace escaping ACL evaluation.
- **Server-asserted identity headers (`Nats-Request-Info`) must be stripped from all inbound client/leafnode messages and only the server may set them.** CVE-2026-33223 and CVE-2026-33246 show identity spoofing when stripping is incomplete or when an untrusted leafnode propagates identity claims unchecked.
- **Credential expiry and revocation must be enforced; an expired or revoked JWT must be rejected.** CVE-2020-26892 shows expiry silently not working.
- **Identity-mapping from external authenticators (mTLS DN) must be exact and unambiguous.** CVE-2026-33248 shows a DN-mapping bypass.
- **The system account `$SYS` is the privileged superuser boundary and is shared across a cluster/supercluster; anyone who can publish to it can perform administrative actions and move laterally across the whole deployment.** CVE-2022-28357 makes this explicit — protect `$SYS` access tightly and sandbox the process.
- **Untrusted input must not control filesystem paths.** CVE-2022-26652 (JetStream restore Zip Slip) and CVE-2022-28357 require path-sanitization plus OS-level sandboxing as defense-in-depth.
- **Pre-authentication code paths (WebSocket compression negotiation, leafnode handshake) must bound resource use and never panic on attacker input.** CVE-2026-27571 / CVE-2026-33219 / CVE-2026-29785 show unauthenticated DoS when these bounds are missing.
- **Cryptographic key material must be handled by reference correctly; auth-callout payloads carry credentials and must be genuinely encrypted.** CVE-2023-46129 (all-zeros xkeys key) shows credential exposure when the encryption silently degrades.
