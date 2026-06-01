# NATS Server Authentication

Sources:
- https://docs.nats.io/running-a-nats-service/configuration/securing_nats/auth_intro
- https://docs.nats.io/running-a-nats-service/configuration/securing_nats/auth_intro/jwt
- https://docs.nats.io/running-a-nats-service/nats_admin/security/jwt
- https://github.com/nats-io/jwt
- https://docs.nats.io/using-nats/nats-tools/nsc/signing_keys
- https://docs.nats.io/running-a-nats-service/configuration/securing_nats/auth_callout
- https://github.com/nats-io/nats.docs/blob/master/running-a-nats-service/configuration/securing_nats/auth_callout.md
- https://github.com/nats-io/nats-architecture-and-design/blob/main/adr/ADR-26.md
- https://advisories.nats.io/CVE/secnote-2023-02.txt
- https://advisories.nats.io/CVE/CVE-2020-26892.txt
- https://advisories.nats.io/CVE/secnote-2026-13.txt
- https://www.synadia.com/blog/onboarding-distributed-nats-clients-nkeys-jwts

> `docs.nats.io` is GitBook-rendered; canonical content drawn from `nats-io/nats.docs` markdown sources, the `nats-io/jwt` repo, and search summaries of the docs pages.

## Authentication methods

NATS authenticates a connecting client to establish its identity and the **account** it belongs to. Several mechanisms are supported, configured either in the server config file (centralized) or carried in JWTs (decentralized).

### Token authentication
A single shared bearer token for the server or a connection:
```
authorization { token: "s3cr3t" }
```
Weakest method (one shared secret); the token grants whatever permissions are configured.

### User/password (with bcrypt)
```
authorization {
  users: [ { user: alice, password: "$2a$11$...bcrypt-hash..." } ]
}
```
Passwords may be plaintext (discouraged; the server logs `Plaintext passwords detected, use nkeys or bcrypt`) or **bcrypt** hashes (`mkpasswd`/`nats server passwd`). `no_auth_user` does not work with bcrypt.

### TLS / mTLS certificate authentication
TLS provides transport encryption; **mTLS** (client certificates) additionally authenticates the client. With `verify_and_map`, the NATS user identity is derived from the client certificate's Subject DN (or SAN). The DN-to-identity mapping must be exact — a mapping bug for certain RDN patterns was CVE-2026-33248 (auth bypass).

### NKEYS
NKEYS are NATS's Ed25519-based public-key identities (a seed = private key, a public key prefixed by role letter, e.g. `U` user, `A` account, `O` operator). The client proves possession of the seed by signing a server-issued nonce; the server only stores the public key.
```
authorization { users: [ { nkey: "UDXU4RCSJNZOIQHZNWXHXORDPRTGNJAHAHFRGZNEEJCPQTT2M7NW3J5P" } ] }
```
The server never holds the private seed, so credential theft from the server is not possible.

### Decentralized JWT authentication (operator → account → user)
The richest model: account, export/import, user, and permission configuration is moved out of the server into signed **JWTs**, organized as a hierarchical chain of trust between three NKEY roles:

```
Operator (O...)   signs ->   Account JWTs (A...)   signs ->   User JWTs (U...)
```
- **Operator**: root of trust for an authentication domain; its public key is configured into every server (`operator: <jwt or path>`). The operator JWT may name the **account resolver** and the **system account**.
- **Account**: an account JWT (signed by the operator or an operator signing key) defines the account's limits, exports/imports, and the account's identity. The account's key (or its signing keys) signs user JWTs.
- **User**: a user JWT (signed by the account or an account signing key) carries the user's permissions, limits, and expiry. The user presents this JWT plus a signature over the server nonce (proving it holds the user seed).

All NATS JWTs are **always and only signed with Ed25519** (no `alg:none`, no RS256 confusion). Managed with the `nsc` tool.

```
# user credentials file (.creds) bundles the user JWT + user seed
-----BEGIN NATS USER JWT-----
eyJ0eXAiOiJKV1QiLCJhbGciOiJlZDI1NTE5LW5rZXkifQ...
------END NATS USER JWT------
-----BEGIN USER NKEY SEED-----
SUAEXAMPLESEED...
------END USER NKEY SEED------
```

#### Signing keys
An account (or operator) can authorize separate **signing keys** to sign child JWTs, keeping the root identity key offline. A user JWT is valid if signed by the account's identity key *or* any of its authorized signing keys. Revoking a signing key invalidates everything it signed going forward; this scopes the blast radius of a compromised key (compromise of one signing key does not require rotating the root account key, but does require revoking that key and reissuing).

#### Account resolver
The server obtains account JWTs via a resolver: `MEMORY` (static, preloaded), `URL`/`nats-account-server` (HTTP), or the built-in `NATS`-based resolver (`full`/`cache`) that distributes account JWTs over the system account. The resolver is how an updated account JWT (e.g. a new export, or a revocation list) reaches running servers.

#### Expiry and revocation
- User and account JWTs may carry an **expiry (`exp`)**. An expired JWT must be rejected (mishandling expiry was CVE-2020-26892).
- An account JWT can carry a **revocation list** (`revocations`) keyed by user public key + timestamp; a revoked user must be rejected. Updating the revocation requires pushing the new account JWT through the resolver.

### Auth callout (delegated authentication)
**Auth Callout** delegates authentication/authorization to an application-defined NATS service, so an external IAM (LDAP, SAML, OAuth, a DB, a file) can be the source of truth. Configured under `authorization.auth_callout` (centralized) or in operator mode (decentralized):
```
authorization {
  auth_callout {
    issuer: "ABC...NKEY"          # public key that signs the authorization response (user JWT)
    auth_users: [ auth ]          # the designated callout user(s)/nkey(s)
    account: AUTH                 # account the callout service connects in
    xkey: "XABC..."               # optional x25519 public key to ENCRYPT request payloads
  }
}
```
The server sends an authorization *request* (the connecting client's presented credentials, including any password) to the callout service, which validates against its backend and returns a signed user JWT (or a rejection). The `xkey` enables encrypting the request payload — recommended because the request carries the user's password. The nkeys "xkeys" encryption bug (CVE-2023-46129) silently encrypted these to an all-zeros key, risking credential exposure when callout shares an account with untrusted users or runs without TLS.

## Identity / trust invariants and key scope

- **Operator key compromise = total compromise of the authentication domain** (can mint any account). Keep operator keys offline; use signing keys for day-to-day issuance.
- **Account key compromise = compromise of that account** (can mint any user, alter exports/imports). Signing keys limit exposure: a leaked signing key can be revoked without rotating the account identity.
- **User seed compromise = impersonation of that one user** until the user JWT is revoked or expires.

## Security-Relevant Considerations

What must always be true for authentication to be sound:

- **Every connection's identity and account are established by verified credentials before any messaging is allowed; an unauthenticated connection (absent an explicit `no_auth_user`) must be refused.** The `$SYS`-only-accounts auth-bypass (CVE-2023-47090) shows the danger of an implicit `no_auth_user` silently re-enabling anonymous access.
- **A user/account JWT must be cryptographically verified up its chain to the configured operator, using Ed25519 only.** A user JWT is valid only if signed by its account's identity key or an authorized signing key; an account JWT only if signed by the operator or an operator signing key. Accepting an unsigned/wrongly-signed JWT, or a different algorithm, breaks the entire trust model.
- **Expired or revoked JWTs must be rejected on every connection and re-checked, not cached past expiry.** Time-based expiry must actually be enforced (CVE-2020-26892). A revocation pushed via the resolver must take effect for new connections.
- **Credential proof must be possession-based and the server must not hold private key material.** NKEYS/JWT prove possession of a seed by signing a server nonce; the server stores only public keys. (mTLS proves possession of the cert key.)
- **External-identity mapping (mTLS DN, auth callout) must be exact and unforgeable.** An ambiguous DN mapping (CVE-2026-33248) or a callout response that isn't validated against the configured issuer NKEY is an authentication bypass.
- **Auth-callout request payloads carry secrets (passwords) and must be genuinely encrypted (xkey) and/or transported over TLS.** A degraded/zeroed encryption key (CVE-2023-46129) exposes credentials to anyone able to observe the callout subject.
- **Signing keys scope blast radius; a compromised signing key must be revocable independently of the root identity, and revocation must propagate.** This is the intended containment property of the operator/account/signing-key hierarchy.
