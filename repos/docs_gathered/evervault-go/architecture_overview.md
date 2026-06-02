# Architecture overview

The `evervault-go` module is a Go SDK for the Evervault platform. At this version it targets Go 1.20 and ships as a single Go module rooted at `github.com/evervault/evervault-go`. The repository is laid out as one public package (`evervault`) at the module root with a small number of supporting packages:

- `evervault` (root) — the public API. Constructors, the `Client` type, all `Encrypt*` / `Decrypt*` methods, function invocation, enclave / cage client construction, outbound relay client construction, configuration, and exported error values all live here.
- `attestation` — public types used by callers when supplying expected enclave measurements. Notably the `PCRs` struct (PCR0, PCR1, PCR2, PCR8) and the `BuildStaticPcrProvider` helper.
- `internal/crypto` — non-exported encryption primitives. Holds the AES-GCM encryption routine, the KDF that derives an AES key from an ECDH shared secret, public-key compression, the Evervault wire-format encoder, and the metadata encoder.
- `internal/datatypes` — an enum of supported plaintext kinds (`String`, `Number`, `Boolean`, `Bytes`).
- `internal/attestation` — the polling PCR manager and the attestation-document cache used by enclave and cage clients.
- `internal/testhelper` — small helpers used by the test suite (e.g., loading required env vars).
- `e2e/` — black-box integration tests that exercise the SDK against live Evervault infrastructure.

Design philosophy at this version is "one fluent client, many transports." Callers construct a single `*evervault.Client`, then ask that client to mint whatever they need next: encrypted strings, function invocations, a `*http.Client` that proxies through Outbound Relay, or a `*http.Client` whose TLS dialer attests a connection to an enclave or cage. Concurrency-sensitive state (the attestation document cache, the polling PCR provider) lives behind the `internal/attestation` package and is guarded with `sync.RWMutex`.

External dependencies are deliberately small: `github.com/hf/nitrite` for AWS Nitro attestation-document verification, and `github.com/stretchr/testify` for tests. Indirect-only dependencies pull in `fxamacker/cbor/v2` (via nitrite) and `jarcoal/httpmock` (test-only).

The SDK is consumed via `go get github.com/evervault/evervault-go` and documented online through `pkg.go.dev` and the official Evervault docs site under `/sdks/go`. The README points new users at those two references rather than duplicating the surface in-tree.

Word count: ~360
