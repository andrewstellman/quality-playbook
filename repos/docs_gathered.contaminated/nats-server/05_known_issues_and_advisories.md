# Known Issues and Security Advisories

## Sources:
- https://advisories.nats.io/
- https://github.com/nats-io/nats-server/security/advisories
- https://github.com/advisories?query=nats-server
- https://github.com/nats-io/nats-server/issues/4225
- https://github.com/nats-io/nats-server/issues/6180
- https://github.com/nats-io/nats-server/issues/3202
- https://github.com/nats-io/nats-server/issues/3108
- https://github.com/nats-io/nats-server/security/advisories/GHSA-fhg8-qxh5-7q3w
- https://github.com/nats-io/nats-server/security/advisories/GHSA-g6w6-r76c-28j7
- https://github.com/nats-io/nats-server/security/advisories/GHSA-fr2g-9hjm-wr23
- https://github.com/nats-io/nats-server/security/advisories/GHSA-6h3m-36w8-hv68
- https://github.com/nats-io/nats-server/security/advisories/GHSA-8m2x-3m6q-6w8j
- https://github.com/nats-io/nats-server/security/advisories/GHSA-8r68-gvr4-jh7j
- https://advisories.nats.io/CVE/secnote-2026-12.txt
- https://advisories.nats.io/CVE/secnote-2026-09.txt
- https://advisories.nats.io/CVE/secnote-2026-08.txt
- https://advisories.nats.io/CVE/secnote-2026-07.txt
- https://advisories.nats.io/CVE/secnote-2026-13.txt
- https://advisories.nats.io/CVE/CVE-2021-3127.txt
- https://advisories.nats.io/CVE/CVE-2022-29946.txt
- https://advisories.nats.io/CVE/CVE-2022-28357.txt
- https://advisories.nats.io/CVE/CVE-2020-26892.txt

## Context

The NATS project publishes advisories canonically at `advisories.nats.io` and mirrors them as GitHub Security Advisories on `nats-io/nats-server` (plus `nats-io/jwt` and `nats-io/nkeys`). The history clusters into a small number of recurring failure modes that map directly onto the security invariants in `04_invariants.md`. The two open GitHub issues most relevant to the NATS-1 finding — `#4225` (the feature request to enforce subscribe ACLs against consumer filters) and `#6180` (the residual `filter_subjects` lockability gap) — are not CVEs; the maintainers have acknowledged the discrepancy but not classified it as a security advisory. This file enumerates the relevant advisories, the two key issue threads, and the project's security-reporting policy.

## The two key open issues

### Issue #4225 — Support privileges-enforcement for JetStream similar/identical to normal NATS

- **URL**: https://github.com/nats-io/nats-server/issues/4225
- **Status**: Open feature request, maintainer-acknowledged
- **Category**: JetStream authorization model parity
- **Reporter ask**: Validate that any subject used to access a stream (via a consumer's filter, or via direct fetch) would be allowed as a direct subscription. Creating a consumer with a filter wider than the user's subscribe permission should fail. Alternatively, hide messages whose subjects are denied for the user before applying the consumer filter.
- **shaunco's elaboration**: The asymmetry extends to writes — a user with `$JS.API.>` can create a stream and consumer for `no.>` despite having no pub/sub on `no.>`. The relevant config (verbatim from the thread):
  ```yaml
  accounts {
    FOO: {
      users: [
        {
          user: "bar"
          password: "bar"
          permissions: {
            publish: [ "yes.>", "$JS.API.>", "$JS.ACK.>", "$JS.FC.>", "$JSC.>" ]
            subscribe: [ "yes.>", "$JS.API.>", "$JS.ACK.>", "$JS.FC.>", "$JSC.>" ]
          }
        }
      ]
    }
  }
  ```
  With this config `bar` has no `no.>` permission, but can still create a stream and a consumer for `no.>`.
- **derekcollison's response** (verbatim):
  > "We are aware of the discrepancy between security models etc. We have been working on some ideas to help normalize. Under the covers it still will result in the low level understanding of consumers and the subjects they use to interact etc."
  >
  > "FYI for single subject filtered consumers you can lock that down already. The client will use an extended version of consumer create that appends the filter subject to the end of the create subject itself. For instance if I want to create a consumer named DEREK on a stream called TEST, that has a filtered subject of `foo.*`, the subject the clients will use is `$JS.API.CONSUMER.CREATE.TEST.DEREK.foo.*`. This can be used for user publish permissions at the core level. Some users/customers who want to be pedantic also put in a deny perm on `$JS.API.CONSUMER.CREATE.TEST.DEREK`."
- **State of the fix**: No server-side ACL cross-check has been landed; the documented mitigation is operator-side configuration via the extended consumer-create subject (single-filter only). `tpihl` follow-up in the thread: "Any progress with acl for consumers?"

### Issue #6180 — Enhance ACL Flexibility for JetStream filter_subjects Permissions

- **URL**: https://github.com/nats-io/nats-server/issues/6180
- **Status**: Open feature request
- **Category**: Residual gap from the #4225 mitigation — extended subject pattern doesn't cover `filter_subjects` (plural)
- **Verbatim "Current Behavior"**:
  > - Permissions such as `$JS.API.CONSUMER.CREATE.my_stream.*.my_stream.123.>` work effectively for filter_subject.
  > - The equivalent does not apply to filter_subjects, leaving users unable to block or enforce restrictions when multiple subjects are provided.
- **Verbatim "Expected Behavior"**:
  > - Deny specific filter_subjects patterns in JetStream consumer creation permissions.
  > - Allow granular ACLs to restrict or allow filter_subjects configurations similar to filter_subject.
- **Use case (verbatim)**:
  > "This feature is critical for setups where external clients should be restricted to subscribing only to specific subjects based on their ID or other identifying patterns, ensuring unauthorized access to other subjects is fully blocked. This enhancement would greatly benefit users relying on precise access controls in multi-tenant environments."

### Issue #3202 — Subscribe user permission not enforced for consumer

- **URL**: https://github.com/nats-io/nats-server/issues/3202
- **Status**: Open / discussion ("works as designed" per maintainer, contested as a security gap by community)
- **Category**: JetStream authorization vs. core subject permissions (leaky abstraction)
- **The scenario**: User `sue` with `subscribe = ["users.sue", "_INBOX.>"]` and publish permissions including `$JS.API.CONSUMER.INFO.*.*` / `$JS.API.CONSUMER.MSG.NEXT.*.*` can fetch from a consumer on a stream that captured `users.*` and receive `users.joe` and `users.pam` messages. The subscribe permission on `users.sue` is bypassed because JetStream delivers consumed messages on the consumer's delivery/inbox subject, not the original subject.
- **derekcollison's framing**: messages from JetStream "are not delivered on their original subject, by design"; pull consumers could in principle bind client permission context but currently do not.
- **Community framing** (simon-connektica, abalmos, tpihl): a "major security issue" / "security leak" that blocks audit/certification in regulated environments.

## NATS security advisories — authorization/account-isolation cluster

### CVE-2022-24450 — Unconstrained account assumption

- **GHSA**: GHSA-g6w6-r76c-28j7 | **Fixed**: nats-server 2.7.2, nats-streaming-server 0.24.1 | **Severity**: Critical | **CWE**: 863 (Incorrect Authorization)
- **Affected**: nats-server `2.0.0 <= V <= 2.7.1`; nats-streaming-server `0.15.0 <= V <= 0.24.0`
- **Root cause**: A coding error in an undocumented experimental "sandbox accounts" feature let a client crafting the initial protocol-level handshake specify a target account and switch into it — including any other tenant and including `$SYS`. Even deployments not using multi-tenancy were vulnerable. The fix removed the feature entirely.
- **Why it matters here**: It establishes the "account-is-fixed-by-credentials" invariant as a hard requirement.

### CVE-2025-30215 — Failure to authorize certain JetStream admin APIs

- **GHSA**: GHSA-fhg8-qxh5-7q3w (NATS-advisory-ID 2025-01) | **Fixed**: 2.10.27, 2.11.1 | **Severity**: Critical (CVSS 9.6) | **CWE**: 285 (Improper Authorization)
- **Affected**: `<= 2.11.0` (from v2.2.0 onward)
- **Root cause**: Four admin-level JetStream APIs lacked authorization checks restricting them to system-account users — `$JS.API.ACCOUNT.PURGE.*`, `$JS.API.SERVER.REMOVE`, `$JS.API.ACCOUNT.STREAM.MOVE.*.*`, and cancel-move. Any user with `$JS.>` publish (commonly granted to per-account admins) could execute them across accounts. PoC: a user in account `TEST2` published `$JS.API.ACCOUNT.PURGE.TEST` and destroyed all JetStream data in the unrelated account `TEST`.
- **Why it matters here**: Same structural failure as the NATS-1 consumer gap — "the API subject was reachable, so the operation was performed" without a deeper check on the affected scope. The reference pattern (`$JS.API.META.LEADER.STEPDOWN`) correctly restricted to system-account users.

### CVE-2026-33222 — JetStream stream-restore endpoint auth bypass

- **GHSA**: GHSA-9983-vrx2-fg9c (NATS-advisory-ID 2026-12) | **Fixed**: 2.11.15, 2.12.6 | **Severity**: Moderate | **CWE**: 285
- **Root cause**: Users authorized to restore a stream were not constrained to the stream name(s) their restore permission targeted; the endpoint did not verify the target name was within the caller's authorized scope. Workaround: temporarily remove limited JetStream-restore permissions.
- **Why it matters here**: A second instance of "the API subject was reachable, so the operation was performed" — same shape as both #4225 and CVE-2025-30215.

### CVE-2021-3127 — Import token permissions checking not enforced

- **GHSA**: GHSA-j756-f273-xhp4 (jwt: GHSA-62mh-w5cv-p88c) (NATS-advisory-ID 2021-02) | **Fixed**: jwt 2.0.1, nats-server 2.2.0 | **Severity**: High
- **Affected**: jwt `< 2.0.1`; nats-server `2.0.0`–`2.1.9`
- **Root cause**: The `nats-io/jwt` library *warned* on mismatches in import-token bindings instead of *rejecting* the token. Any account could replay another's import token to import any subject from the exporting account.
- **Why it matters here**: Establishes "binding mismatch must reject, not warn" as a hard invariant. The advisory shipped a `jwt-audit.py` script that flags "token grants X but used to access Y" abuse.

### CVE-2022-29946 — Negative user permissions not enforced in queue subscription

- **NATS-advisory-ID 2022-04** | **Fixed**: nats-server 2.8.2, nats-streaming-server 0.24.6
- **Affected**: nats-server `2.0.0`–`2.8.1`
- **Root cause**: A deny on a specific subject combined with an allow on a wildcard subscribe was honored for *direct* subscription but leaked through a *wildcard queue subscription*; the implicit delivery via the wildcard queue subscription did not receive the deny filter.
- **Why it matters here**: Same invariant shape as NATS-1 — "deny must filter every delivery path." The queue-group escape and the JetStream-consumer escape are both violations of this invariant, at different layers.

### CVE-2026-33217 — MQTT ACLs ineffective

- **GHSA**: GHSA-jxxm-27vp-c3m5 (NATS-advisory-ID 2026-07) | **Fixed**: 2.11.15, 2.12.6
- **Root cause**: Subject ACLs were not applied in the `$MQTT.>` namespace; MQTT clients bypassed ACL checks for MQTT subjects.
- **Why it matters here**: An entire interface escaping ACL evaluation — same family as a consumer-create path escaping subscribe-ACL evaluation.

### CVE-2026-33223 — Internal identity header `Nats-Request-Info` spoofable

- **GHSA**: GHSA-pwx7-fx9r-hr4h (NATS-advisory-ID 2026-09) | **Fixed**: 2.11.15, 2.12.6
- **Root cause**: Stripping `Nats-Request-Info:` from inbound client messages was not fully effective. Related: **CVE-2026-33246 (GHSA-55h8-8g96-x4hj)** — leafnodes could propagate `Nats-Request-Info` identity claims unchecked.

### CVE-2026-33248 — mTLS DN-based identity auth bypass for some DN patterns

- **GHSA**: GHSA-3f24-pcvm-5jqc (NATS-advisory-ID 2026-13) | **Fixed**: 2.11.15, 2.12.6
- **Root cause**: With `verify_and_map` mTLS, certain RDN patterns in the client cert's Subject DN were not correctly enforced when mapping to a NATS identity.

### CVE-2023-47090 — Adding accounts for just the system account adds auth bypass

- **GHSA**: GHSA-fr2g-9hjm-wr23 (NATS-advisory-ID 2023-01; GO-2023-2133) | **Fixed**: 2.10.2, 2.9.23 | **Severity**: High | **CWE**: 305
- **Root cause**: When the only account added was `$SYS`, the server created an implicit user in the global account `$G` and set it as `no_auth_user` — re-enabling anonymous connection. Administrators using a legacy `authorization` block would silently get unauthenticated access while believing auth was enabled.

### CVE-2022-26652 — JetStream arbitrary file write (Zip Slip)

- **GHSA**: GHSA-6h3m-36w8-hv68 | **Fixed**: 2.7.4 | **Severity**: High | **CWE**: 26
- **Affected**: nats-server `2.2.0`–`2.7.3`
- **Root cause**: JetStream stream backup/restore used a tar archive; inadequate sanitization of filenames inside the archive permitted Zip Slip path-traversal writes outside the JetStream storage directory.

### CVE-2022-28357 — Arbitrary file write from the privileged system account

- **NATS-advisory-ID 2022-03** | **Fixed**: 2.8.0 | **Severity**: High
- **Root cause**: Inadequate filename check in account-synchronization filename construction (performed in `$SYS`). NATS treats `$SYS` as privileged so this "does not cross a privilege boundary" by its own model, but `$SYS` is shared cluster-wide so this enables lateral movement.

### CVE-2023-46129 — nkeys xkeys Seal encryption used an all-zeros key

- **GHSA**: GHSA-mr45-rx8q-wcm9 (NATS-advisory-ID 2023-02) | **Fixed**: nkeys 0.4.6, nats-server 2.10.4
- **Affected**: nkeys `0.4.0`–`0.4.5`; nats-server `2.10.0`–`2.10.3`
- **Root cause**: The nkeys "xkeys" encryption path passed a buffer by value into an internal function that mutated it to populate the encryption key; all encryption used an all-zeros key. Affects auth-callout request payloads (which carry the user password).

### CVE-2020-26892 — Incorrect handling of credential expiry

- **GHSA**: GHSA-4w5x-x539-ppf5 (jwt) / GHSA-2c64-vj8g-vwrq (nats-server) (NATS-advisory-ID 2020-02) | **Fixed**: jwt 1.1.0, nats-server 2.1.9
- **Root cause**: `nats-io/jwt`'s `IsRevoked()` misused its own API and expiration was not enforced. A corrected `IsClaimRevoked()` was introduced; the old `IsRevoked()` now always returns true.

## Denial-of-service advisories (pre-auth and import-loop)

Availability-class rather than authorization-class, included because they share the project's advisory stream:

- **CVE-2026-27571** (GHSA-qrvq-68c2-7grw) — WebSockets pre-auth memory DoS via compression bomb. Fixed 2.11.12 / 2.12.3. CVSS 5.9.
- **CVE-2026-33219** (GHSA-8r68-gvr4-jh7j) — WebSockets pre-auth unbounded memory DoS (non-compression variant). Fixed 2.12.6 / 2.11.15. CVSS 5.3.
- **CVE-2026-33249** (GHSA-8m2x-3m6q-6w8j) — Message tracing can be redirected to an arbitrary subject the client has no publish permission for. Fixed 2.12.6 / 2.11.15. CVSS 4.3. Permission-bypass-adjacent.
- **CVE-2026-29785** (GHSA-52jh-2xxh-pwh6) and **CVE-2026-27889** (GHSA-pq2q-rcw4-3hr6) — leafnode / WebSockets pre-auth panic/crash.
- **CVE-2020-28466 / CVE-2022-42709** — account service-import loops causing server DoS.
- **CVE-2022-42708** — server panic from inappropriate JetStream replica count.

## Additional advisories (listed in the index, not individually fetched here)

- **CVE-2026-33216** (GHSA-v722-jcv5-w7mc) — MQTT plaintext password disclosure.
- **CVE-2026-33215** (GHSA-fcjp-h8cc-6879) — MQTT hijacking via Client ID.
- **CVE-2026-33247** (GHSA-x6g4-f6q3-fqvv) — credentials via command-line argv exposed to monitoring.
- **CVE-2026-33218** (GHSA-vprv-35vv-q339) — pre-auth panic in leafnode handling.
- **CVE-2021-32026** — TLS ciphersuite settings missing with CLI flags.
- **CVE-2020-26521** — nil-deref panic in JWT library.
- **CVE-2020-26149** — info disclosure in JS client libraries.

## NATS security-reporting policy

- **Canonical advisory index**: https://advisories.nats.io/
- **Reporting channel**: per `SECURITY.md` in `nats-io/nats-server`, security issues should be reported to the `security@nats.io` address, not via public GitHub issues.
- **Fix delivery**: paired releases on the latest two supported minor lines (currently `2.11.x` and `2.12.x`); advisories are published with the fixed-in versions and a workaround paragraph.
- **Sandbox guidance**: the project ships `util/nats-server-hardened.service` with `ProtectSystem=strict`, `PrivateTmp=true`, and narrow `ReadWritePaths` as a recommended baseline.

## Security-Relevant Considerations

The advisory and issue history defines the system's intended invariants by showing what breaks when they are violated:

- **Issues #4225, #6180, and #3202 — together — frame NATS-1 as a recognized, maintainer-acknowledged structural gap, not a misconfiguration.** Maintainer description: "We are aware of the discrepancy between security models." Documented mitigation works only for `FilterSubject` (singular); `FilterSubjects` (plural) has no mitigation.
- **CVE-2025-30215 and CVE-2026-33222 are the closest prior-art for NATS-1.** Both are "the API request subject was reachable, so the operation was performed" — without a deeper check on whether the affected scope (account, stream, filter) was within the caller's authority. Both were ultimately fixed by adding the missing scope check; neither was fixable by configuration alone.
- **CVE-2022-29946 is the closest prior-art for the read-side gap.** It violated the same "deny must filter every delivery path" invariant that NATS-1 violates — just at the queue-group layer instead of the JetStream-consumer layer.
- **The advisory pattern matters for QPB detection**: the project consistently treats "API subject reachable ≠ operation authorized" as a security issue requiring server-side enforcement, not configuration guidance.
