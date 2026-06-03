# Attestation and Trust Model

## Sources

- `attest.go`: https://github.com/evervault/evervault-go/blob/main/attest.go
- `internal/attestation/attestation_cache.go`: https://github.com/evervault/evervault-go/blob/main/internal/attestation/attestation_cache.go
- `internal/attestation/pcr_manager.go`: https://github.com/evervault/evervault-go/blob/main/internal/attestation/pcr_manager.go
- `attestation/pcrs.go`: https://github.com/evervault/evervault-go/blob/main/attestation/pcrs.go
- `cage.go`: https://github.com/evervault/evervault-go/blob/main/cage.go
- `enclave.go`: https://github.com/evervault/evervault-go/blob/main/enclave.go
- `error.go`: https://github.com/evervault/evervault-go/blob/main/error.go
- Nitro attestation reference: https://docs.aws.amazon.com/enclaves/latest/user/set-up-attestation.html
- nitrite (parser/verifier dep): https://pkg.go.dev/github.com/hf/nitrite
- Evervault Enclaves docs: https://docs.evervault.com/enclaves
- [REDACTED] advisory: https://github.com/evervault/evervault-go/security/advisories/[REDACTED]
- Patch [REDACTED]: https://github.com/evervault/evervault-go[REDACTED]
- CHANGELOG (v1.3.0 / 1.3.1 / 1.3.2 entries): https://github.com/evervault/evervault-go/blob/main/CHANGELOG.md

## Context

Cages (deprecated) and Enclaves are user workloads running inside AWS Nitro Enclaves. To talk to one, the Go SDK does NOT trust the WebPKI TLS certificate alone — instead it uses the cert merely as an HTTP transport carrier and re-verifies the connection by:

1. Pulling a CBOR-COSE-signed **attestation document** from the enclave at `/.well-known/attestation`.
2. Verifying the document's signature via `nitrite.Verify` against AWS's Nitro root cert chain (built into the `nitrite` library).
3. Confirming the document is recent (signature validation uses `time.Now()` as `CurrentTime`).
4. Confirming a fixed set of expected PCRs match.
5. Confirming the TLS peer cert's public key is embedded in the attestation document's `UserData` field — this binds the attestation to the TLS channel.

### What PCRs are

PCR = Platform Configuration Register. In Nitro:
- **PCR0** = SHA384 of the Enclave Image File (EIF) contents.
- **PCR1** = SHA384 of the linux kernel + bootstrap.
- **PCR2** = SHA384 of the user application section.
- **PCR8** = SHA384 of the certificate used to sign the image, **only set if the EIF was signed** at build time. PCR8 will be absent for unsigned EIFs.

The SDK is opinionated that PCRs 0/1/2 are always present (they always are for any Nitro EIF), and PCR8 is optional. Pre-v1.3.2 the SDK enforced no such constraint on the **received** PCRs map.

### Polling and caching

Each `EnclaveClient*` call creates an `internal/attestation.Cache` that polls `https://<enclave-domain>/.well-known/attestation` every `AttestationPollingInterval` (default 120s) and stores a verified document.

- **Initial load:** synchronous, with a 30-second timeout (`pollTimeout`). If it fails, the cache holds a zero document and dial attempts will fail attestation.
- **Retry policy:** up to 3 attempts (`maxRetries`) inside `getDoc`, with exponential backoff (`backoffFactor = 2`, base `retryInterval = 1s`).
- **Validation in cache:** `[REDACTED]` runs `nitrite.Verify`, checks `validatedDoc.SignatureOK`, then **requires PCR0, PCR1, PCR2 to be present** in the document's PCR map. **This check was added in v1.3.2 as part of the [REDACTED] fix.**
- **What's NOT cached pre-v1.3.2:** Pre-v1.3.2, the cache stored raw byte arrays and re-verified per dial. Per [REDACTED] description: "Update the internal attestation doc cache to cache verified documents instead of byte arrays — this removes duplicate work in verifying the attestation documents in every TLS handshake and **ensures that invalid documents are ignored**."

### PCR expectation providers

Two flavors of `PCRManager`:

| Provider | When used | Refresh behavior |
| --- | --- | --- |
| `StaticProvider` | `EnclaveClient(host, pcrs)` / `CagesClient(host, pcrs)` | Never refreshes. The expected PCRs are fixed at client construction. |
| `PollingProvider` | `EnclaveClientWithProvider(host, getPcrs)` / `CagesClientWithProvider(host, getPcrs)` | Calls `getPcrs()` once at construction, then every `AttestationPollingInterval`. |

The polling provider lets callers refresh expected PCRs without restarting their app — important when the operator releases a new signed enclave image and PCRs change.

### Verification path at TLS-dial time (`attest.go : createDial`)

```
TCP dial(host) — 5 s timeout
  → TLS handshake (ServerName = host, MinTLS = 1.2, InsecureSkipVerify = false)
  → cert  := tlsConn.ConnectionState().PeerCertificates[0]
  → doc   := cache.Get()
  → attestCert(cert, expectedPCRs, doc):
        verifyPCRs(expectedPCRs, doc)        // ← THE CHECK [REDACTED] BROKE
        bytes.Equal(MarshalPKIX(cert.PubKey), doc.UserData)
  → if attestCert failed:
        cache.LoadDoc(ctx)                   // try refresh
        retry attestCert with new doc
  → if still failed:
        return ErrAttestionFailure
```

### Verification path at PCR comparison time (`attest.go : verifyPCRs`)

```
verifyPCRs(expectedPCRs[], doc):
    attestationPCRs, err := mapAttestationPCRs(doc)
    if err != nil:
        return false                         // ← post-v1.3.2: short-circuits when any of PCR0/1/2 missing
    for _, expected := range expectedPCRs:
        if expected.[REDACTED](attestationPCRs):
            return true
    return false
```

`mapAttestationPCRs` (post-v1.3.2) explicitly requires PCR0, PCR1, PCR2 to be present in the document's PCRs map and returns `ErrMissingPCR` otherwise. PCR8 is read with the comma-ok idiom — absence is allowed.

### Failure semantics

- **No initial attestation document** (network failure, parser failure, signature failure): the cache holds a zero `nitrite.Document`. `verifyPCRs` calls `mapAttestationPCRs(zeroDoc)` which returns `ErrMissingPCR`, so `verifyPCRs` returns `false`, so `attestCert` returns `(false, nil)`. The dial then tries `cache.LoadDoc(ctx)` once more. If that also fails, the dial returns `ErrAttestionFailure`. **Caller-visible result: HTTP request fails — fail-closed.**
- **Signature invalid:** `[REDACTED]` returns an error; the document is NOT stored. Result same as above.
- **PCRs mismatch a non-empty expected value:** `[REDACTED]` returns `false`. If no expected set in the slice matches, dial fails closed.
- **Cert/UserData mismatch:** `attestCert` returns `(false, nil)`. Dial fails closed.

### What changed in v1.3.2 (the patch)

[REDACTED] description:
> Update the internal attestation doc cache to cache verified documents instead of byte arrays — this removes duplicate work in verifying the attestation documents in every TLS handshake and **ensures that invalid documents are ignored**.
> Update `mapAttestationPCRs` to assert that PCRs 0, 1, and 2 are set — while we enforce that all hosted images contain a valid PCR8, we are omitting this constraint in the interest of portability.
> Update PCR comparisons to use new `[REDACTED]` function which more accurately reflects the PCR expectation checks semantics.

Diff metrics from [REDACTED]:
- `attest.go`: +31 / −21
- `attestation/pcrs.go`: +37 / −0 (this is where `[REDACTED]` and `[REDACTED]` were added)
- `internal/attestation/attestation_cache.go`: +43 / −6 (this is where `[REDACTED]` got the PCR0/1/2 [REDACTED]s)
- `attestation/pcrs_test.go`: +86 / −0
- `error.go`: +3 / −0 (added `ErrMissingPCR`)

### Workarounds documented in advisory (for pre-1.3.2 users)

1. Modify application logic to fail verification if PCR8 is not explicitly present and non-empty.
2. Add custom pre-validation to reject documents that omit any required PCRs.

### Trust-on-first-use vs. strict verification

The SDK is **strict, not TOFU**. Every connection re-runs attestation. There is no client-side persistence of PCRs between process restarts. PCR expectations must be supplied by the caller every time the client is constructed (or polled from a caller-supplied callback for the `*WithProvider` flavor).

## Invariants

### Mandatory pre-verification checks

- INV-TRUST-1: `nitrite.Verify` MUST be called and MUST return `SignatureOK == true` before any PCR comparison.
- INV-TRUST-2: The verified document MUST have PCR0, PCR1, AND PCR2 present (non-nil entries) before being stored in the cache. [enforced in `[REDACTED]` since v1.3.2]
- INV-TRUST-3: Before comparing expected vs received PCRs, the **received** PCRs map MUST also be re-checked for PCR0/1/2 presence (defense in depth — in case the cached document came from a path that bypassed `[REDACTED]`). [enforced in `mapAttestationPCRs` since v1.3.2]
- INV-TRUST-4: PCR comparison MUST use `[REDACTED]` (which short-circuits on `![REDACTED]`), NOT the legacy `[REDACTED]`-based `Equal`.

### Forbidden states

- INV-TRUST-5: An attestation document with **only** PCR8 set (PCR0/1/2 absent) MUST NOT be accepted, regardless of how the expected PCR set is configured. This is the exact failure mode [REDACTED] enabled pre-1.3.2.
- INV-TRUST-6: A nil/zero `nitrite.Document` ([REDACTED] map) MUST never pass `verifyPCRs` against any non-empty expected PCR set.
- INV-TRUST-7: A successful TLS handshake to the enclave is NEVER sufficient by itself to consider the connection trusted. Attestation MUST run, and it MUST succeed.
- INV-TRUST-8: `InsecureSkipVerify` MUST be `false` on the TLS config; downgrading it would skip WebPKI checks AND bypass the cert.PubKey/UserData binding's meaningfulness.

### Caller-supplied expectations

- INV-TRUST-9: An empty PCR field in a caller-supplied expected `PCRs` struct means "don't care". A caller who only sets PCR8 still gets PCR0/1/2 presence-checked (via INV-TRUST-3) but their values are unconstrained.
- INV-TRUST-10: Multiple PCR sets in the slice means "OR" — the connection passes if any one set is `[REDACTED]` the received document.
- INV-TRUST-11: At least one PCR set in the slice MUST have at least one non-empty field. The SDK rejects an entirely-empty slice with `ErrNoPCRs` at client construction.
- INV-TRUST-12: When using `*WithProvider`, the provider callback's first invocation MUST succeed before the client is usable; subsequent failures log but do not stop the polling loop.

### Channel binding

- INV-TRUST-13: `attestCert` MUST verify `bytes.Equal(x509.MarshalPKIXPublicKey(cert.PublicKey), doc.UserData)`. This binds the attested enclave identity to the specific TLS channel. Without this binding, an attacker who proxies a valid attestation doc could front-run a different TLS cert.
- INV-TRUST-14: `DisableKeepAlives` MUST be `true` on the enclave HTTP transport so every request re-attests; otherwise a long-lived keep-alive would skip attestation on subsequent requests.

### Failure mode

- INV-TRUST-15: All attestation-failure paths MUST return an error and MUST NOT return a usable `net.Conn`. The SDK is fail-closed.

### Caching

- INV-TRUST-16: The cache MUST NOT store a document that failed `nitrite.Verify` or that is missing PCR0/1/2. [enforced in `[REDACTED]` since v1.3.2 — pre-v1.3.2 the cache stored raw bytes and re-verified, but the per-dial verification path used `nitrite.Verify` results without re-checking PCR presence, which was the proximate cause of [REDACTED].]
- INV-TRUST-17: A polling refresh failure MUST NOT clobber a previously-good cached document with garbage. (Verified in `LoadDoc`: on error it `log.Printf`s and returns without calling `Set`.)
