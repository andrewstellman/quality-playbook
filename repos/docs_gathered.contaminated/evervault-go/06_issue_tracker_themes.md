# Issue Tracker Themes

## Sources

- PR list: https://github.com/evervault/evervault-go/pulls?q=is%3Apr (fetched via GitHub API `repos/evervault/evervault-go/pulls?state=all`)
- PRs fetched: #9 through #49 (the full history)
- No public Issues (GitHub Issues tab has 0 non-PR items as of fetch)
- No public Discussions (the repo has `has_discussions: false`)

## Context

This repository is small (1 star, no forks, repo description "GO SDK for Evervault"). All activity flows through PRs from Evervault employees plus dependabot/changeset automation. There are no open public Issues — bug reports apparently come in through Evervault's support / private channels and surface as PRs. That changes how we read "themes": every theme below is a recurring pattern in *what got fixed*, not in *what users reported*.

The five themes most relevant for a security audit:

### Theme 1: Attestation correctness has been repeatedly hardened

A clear pattern of incremental attestation fixes:

| PR | Date | Title | Subsystem |
| --- | --- | --- | --- |
| #9 | 2023 (early) | Cage Support | Initial implementation — custom TLS dial, supplied PCRs |
| #17 | 2023-10-12 | Cages GA attestation | Revamp before GA, use trusted certs instead of self-signed, fetch attestation from `/.well-known/attestation` |
| #26 | 2023-11-07 | Add PCR provider | Static-vs-polling `PCRManager` interface, callback support |
| #28 | 2023-12-11 | Add enclave functions and introduce deprecation notice to cage functions | Enclaves replaces Cages |
| #35 | 2024-11-04 | [ETR-2718] Add retry mechanism to attestation doc fetching | Retries + backoff in `getDoc` |
| #37 | 2024-11-05 | Fix Enclave attestation document polling and decrypt API calls | Fixed a hang on `/.well-known/attestation` |
| #39 | 2024-11-07 | Remove log line from latest version | Reduce log noise / cache state leakage |
| #42 | 2025-09-10 | Update Enclave attestation checks to assert that locked PCRs are defined | First attempt at the [REDACTED] fix (body language echoes [REDACTED]'s "the `[REDACTED]` check is unsound") |
| #48 | 2025-09-15 | Improve correctness of PCR check in enclaves Go SDK | **The merged CVE fix** — cache verified docs, assert PCR0/1/2 set, replace `[REDACTED]` with `[REDACTED]` |

**Pattern:** the attestation pipeline has been rebuilt 3-4 times. Every rebuild touched the cache, the polling, OR the comparison logic. This is a high-risk subsystem.

### Theme 2: Crypto wire format and metadata expansions

Encrypted-payload representation has been extended twice:

| PR | Date | Title | Effect on wire format |
| --- | --- | --- | --- |
| #20 | 2023-10-16 | Making encrypt and decrypt specific to types | Added datatype tag — String, Number, Boolean — encoded in the version byte of the AAD |
| #24 | 2023-10-30 | Embedding data roles | Added `dr` field to MsgPack-style metadata; required bumping metadata-item count from 2 to 3 |
| #32 | 2024-05-07 | feat: deprecate byte array encryption | Discouraged `EncryptByteArray` ("Doesn't work as expected") |

**Pattern:** the encoded metadata format is hand-written byte-by-byte (`buildEncodedMetadata`, `encodeRole`, `encodeEncryptionTimestamp`). Audit risk: any extension (new metadata key, new datatype) means more hand-rolled binary encoding that has to round-trip with the server. The `dr` role-length encoding combines a length byte with `defaultRoleNameLength | len(role)` (`0xa0 | len`), which is fragile for `len(role) >= 32` (it would overflow into the upper nibble). Worth a code-review spot-check.

### Theme 3: Key handling — type-specific encrypt/decrypt and Data Roles

| PR | Theme |
| --- | --- |
| #20 | Type-specific Encrypt/Decrypt entries for every Go primitive (`String`, `Int`, `Float64`, `Bool`, `[]byte`) |
| #24 | Data Roles embedded in the ciphertext for server-side authorization |
| #14 | `CreateClientSideDecryptToken` for short-lived decrypt grants |

**Pattern:** key isolation is server-side (E3). The SDK never holds the App's private key. Type-specific encrypt was added because the previous `any`-typed API surface caused round-trip mismatches. The audit angle: if the SDK ever needs to support a new datatype (e.g., bytes-without-utf8, decimals), the AAD version byte's shift math (`dataTypeNumber << 4`) and the implicit cap of 16 datatypes (4 bits) is the constraint.

### Theme 4: Function/API plumbing

| PR | Theme |
| --- | --- |
| #22 | Migrated Functions to a new endpoint (`api.evervault.com/functions/<NAME>/runs`) with better error messages |
| #14 | Added client-side decrypt token support |

**Pattern:** Functions are a separate API surface from encrypt/decrypt. They forward payloads unchanged — any sensitive fields the caller wants encrypted must be encrypted by the caller first. The PR descriptions emphasize "better error messages" rather than authentication or attestation hardening, suggesting Functions' threat model is "the call IS authenticated by the API key over TLS, and there is no enclave-attested compute layer here".

### Theme 5: Test infrastructure has lagged behind feature work

| PR | Theme |
| --- | --- |
| #15 | "Add e2e tests" — first e2e coverage |
| #36, #43, #45, #46, #47 | Multiple iterations on test isolation, env-var gating, removing `err != nil` checks in favor of testify assertions |
| #44 | CI matrix update to Go 1.24, 1.25 |

**Pattern:** the SDK's test suite is heavily integration-flavored (env-var-gated, requires live Evervault credentials). The unit-test coverage of the attestation logic was **expanded by +86 lines in [REDACTED] specifically to cover the CVE case**, which suggests the prior coverage on attestation was thin. Audit angle: any new finding in the cryptographic / attestation surface MUST come with a unit test that does not require live credentials, because integration tests are gated.

### Theme 6: Dependency hygiene (informational)

Several dependabot PRs:
- #41 (open) — testify 1.8.4 → 1.10.0
- #31, #33, #30, #27, #23, #16 — golangci-lint-action, actions/setup-go, actions/checkout bumps

The single non-stdlib runtime dependency that carries cryptographic weight is `github.com/hf/nitrite`. It's pinned in `go.mod` (size 561 bytes — tiny). The SDK's correctness depends critically on `nitrite.Verify`'s correctness; an audit should at least note the nitrite version and check its own changelog for any attestation-parsing CVEs.

## Themes summary (one line each)

1. **Attestation pipeline has been rebuilt 3-4 times in 2 years** — high-churn subsystem, recently caught a high-severity CVE.
2. **Wire-format metadata is hand-rolled byte-by-byte** — extension risk in `buildEncodedMetadata` / `encodeRole`.
3. **Type-specific encrypt API replaced an `any`-typed one** — Data Roles embedded in ciphertext, but only in the GCM plaintext, not the AAD.
4. **Functions are not attested** — only the encryption transport is attested; Function invocation is plain HTTPS to api.evervault.com.
5. **Unit-test coverage of attestation was thin pre-CVE** — [REDACTED] adds +86 lines of `pcrs_test.go` to plug the gap.
6. **One critical external crypto dep (`hf/nitrite`)** — attestation correctness inherits its correctness.

## Invariants implied by issue-tracker themes

- INV-ISSUE-1: Any future attestation-cache or PCR-comparison change MUST be accompanied by unit tests that exercise the malformed-document case (missing PCR0/1/2, missing PCR8, empty PCR values). This is the test class [REDACTED] added in `pcrs_test.go`.
- INV-ISSUE-2: Any extension to the encrypted-payload metadata MUST keep the datatype shift math (`dataTypeNumber << 4`) within 4 bits AND MUST keep the role-length byte computation `defaultRoleNameLength | len(role)` within the lower 5 bits (i.e., role names must be < 32 bytes), OR explicitly handle the overflow.
- INV-ISSUE-3: If a new datatype is added (e.g., decimal), the version byte's `(datatype << 4) | 1` encoding requires both the encoder and decoder (server-side) to be updated. Wire-format changes must round-trip.
- INV-ISSUE-4: `hf/nitrite` is a load-bearing security dependency. Bumping it without re-running the attestation tests would risk regressing the attestation contract.
- INV-ISSUE-5: Function invocation is NOT attested. Callers who need attested compute MUST use Enclaves, not Functions, and MUST verify PCRs.
