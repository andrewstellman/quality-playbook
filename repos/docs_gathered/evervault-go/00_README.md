# evervault-go — Project Overview

## Sources

- Repository: https://github.com/evervault/evervault-go
- Package: `github.com/evervault/evervault-go` (Go module)
- Package docs: https://pkg.go.dev/github.com/evervault/evervault-go
- Official docs (Go SDK): https://docs.evervault.com/sdks/go
- Encryption scheme docs: https://docs.evervault.com/developers/evervault-encryption
- Enclaves product docs: https://docs.evervault.com/enclaves
- README: https://github.com/evervault/evervault-go/blob/main/README.md
- CHANGELOG: https://github.com/evervault/evervault-go/blob/main/CHANGELOG.md
- License: MIT
- GitHub metadata (description, created_at, language): GitHub API `repos/evervault/evervault-go` (created 2023-05-25, last pushed 2025-09-15)

## Context

evervault-go is the **official server-side Go SDK** for the Evervault privacy-preserving compute platform. The SDK is deliberately thin: nearly every cryptographic operation is paired with the **Evervault Encryption Engine (E3)**, an AWS Nitro Enclave service that holds the App's private key. The SDK encrypts values **locally** using the App's published ECDH public key (in cooperation with E3) and decrypts by calling the Evervault API, which routes the decrypt through E3.

The SDK additionally provides:
- Outbound Relay proxy clients (TLS proxy that decrypts on egress)
- Cages clients (deprecated → Enclaves) and Enclaves clients — both for AWS Nitro Enclave-hosted user workloads, both authenticated by **attestation** rather than by classical PKI alone
- Function invocation (`RunFunction`) and run-token issuance for Evervault Functions
- Client-side decrypt-token issuance for short-lived, scoped decrypt grants

### Domain primitives

| Term | Meaning |
| --- | --- |
| **App** | An Evervault tenant. Each App has its own ECDH P-256 keypair, where the private half is held only inside E3. |
| **App Master Key (AMK)** | An AES-256 key per App, never seen in plaintext outside E3. Used to AES-encrypt the App's ECDH private key at rest. Split via Shamir's Secret Sharing (3-of-3) across two databases + E3. |
| **E3 (Evervault Encryption Engine)** | The AWS Nitro Enclave service holding key material and performing decryption. All Evervault hosted products (Functions, Enclaves, Relay, UI Components) talk to E3. |
| **Cage / Enclave** | A user-supplied workload running inside an AWS Nitro Enclave with measured PCRs. "Cages" is the deprecated name; the product was renamed to **Enclaves** as of evervault-go v1.1.0 (CHANGELOG). |
| **PCR** | Platform Configuration Register — Nitro attestation values 0/1/2/8 that measure (0) enclave image, (1) kernel + bootstrap, (2) application, (8) image signing cert. PCR8 is only populated when the image is signed at build time. |
| **Attestation document** | A CBOR-signed COSE_Sign1 object returned by the Nitro hypervisor. The SDK fetches it from `https://<enclave-domain>/.well-known/attestation`. Verified via `github.com/hf/nitrite`. |
| **Relay** | An outbound proxy that intercepts traffic and decrypts Evervault-encrypted tokens on the way out. |
| **Function** | Evervault-hosted server-side function invoked via the SDK by name. |
| **Data Role** | A label embedded in the ciphertext metadata (AAD) that the Evervault dashboard can use to police who is allowed to decrypt. |
| **Evervault Encryption Format ("ev format")** | The string serialization of a ciphertext: `ev:Base64(Version):[datatype:]Base64(KeyIV):Base64(ECDHPublicKey):Base64(AESEncryptedData):$`. The Go SDK emits version tag `QkTC`. |

### Language and runtime

- **Language:** Go (`go.mod` declares the module path `github.com/evervault/evervault-go`). All cryptographic primitives are pulled from Go's `crypto/` standard library (`crypto/aes`, `crypto/cipher`, `crypto/ecdh`, `crypto/rand`, `crypto/sha256`, `crypto/tls`, `crypto/x509`).
- **External crypto dep:** `github.com/hf/nitrite` for AWS Nitro attestation document parsing and verification.
- **No CGO crypto.** Pure-Go implementations.

### Repository layout (relevant files)

```
evervault-go/
├── attest.go                       — TLS dial + attestation glue (mapAttestationPCRs, verifyPCRs, attestCert, createDial)
├── cage.go                         — Deprecated Cages HTTP client
├── enclave.go                      — Enclaves HTTP client (replacement for Cages)
├── client.go                       — Client struct + public-key fetch from Evervault API
├── config.go                       — Environment-variable-driven configuration
├── error.go                        — Sentinel errors (ErrAttestionFailure, ErrMissingPCR, ErrUnVerifiedSignature, ...)
├── evervault.go                    — Top-level Encrypt/Decrypt entry points
├── function.go                     — RunFunction + CreateFunctionRunToken
├── relay.go                        — OutboundRelayClient (TLS proxy)
├── attestation/
│   └── pcrs.go                     — Public PCRs struct, Equal, SatisfiedBy, IsEmpty
├── internal/
│   ├── attestation/
│   │   ├── attestation_cache.go    — Background-polled cache of verified attestation docs
│   │   └── pcr_manager.go          — Static / polling expected-PCR provider
│   ├── crypto/
│   │   └── crypto.go               — DeriveKDFAESKey, CompressPublicKey, CreateV2Aad, EncryptValue, ev format
│   └── datatypes/                  — String / Number / Boolean datatype enum
```

### Versioning at the time of the target CVE

- **Vulnerable range:** `< 1.3.2`
- **Patched version:** `1.3.2` (released 2025-09-15, PR #48 merged the same day)
- **Patch PR:** https://github.com/evervault/evervault-go/pull/48 — title "Improve correctness of PCR check in enclaves Go SDK"
- **Patch commit:** `7c824d289bba11ec0bea46a338023f5b128bbb28`

### What the SDK does NOT do (out of scope for this audit but worth noting)

- It does not implement the Nitro attestation parser itself — that work is delegated to `hf/nitrite`.
- It does not perform decryption in-process. `Decrypt*` calls Evervault's API; E3 does the AES-GCM open.
- It does not currently support post-quantum primitives.

## Invariants implied by overview

- INV-OV-1: All cryptographic operations the SDK performs locally are **encryption**, never decryption. Decryption is delegated to E3 over the wire.
- INV-OV-2: The SDK's threat model assumes the App ECDH **public** key fetched from `EvAPIURL/cages/key` is authentic. The trust root for that fetch is standard TLS PKI to `api.evervault.com`.
- INV-OV-3: For any Cage / Enclave connection, the SDK MUST not return a usable HTTP client unless both (a) the TLS peer certificate's public key is bound to a fresh, signed Nitro attestation document, and (b) the document's PCRs satisfy a caller-supplied expectation set.
- INV-OV-4: For Outbound Relay, TLS verification is standard PKI (custom Evervault CA cert appended to the system pool); attestation is not performed at this layer.
