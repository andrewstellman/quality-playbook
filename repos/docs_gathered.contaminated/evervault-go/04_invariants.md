# Cross-cutting Invariants

## Sources

This file consolidates invariants extracted from:
- `00_README.md`, `01_cryptographic_contract.md`, `02_api_contract.md`, `03_attestation_and_trust.md`
- `internal/crypto/crypto.go`, `internal/attestation/*`, `attest.go`, `attestation/pcrs.go`, `evervault.go`
- Evervault Encryption docs: https://docs.evervault.com/developers/evervault-encryption
- [REDACTED] advisory: https://github.com/evervault/evervault-go/security/advisories/[REDACTED]

## Context

This is the **must-hold-always** list — invariants that a code review or static analysis would be checking to detect classes of bugs including the target CVE. Each invariant is named (for cross-referencing), declared as a "MUST" / "MUST NOT" / "MUST ALWAYS" statement, and tagged with where it should be enforced.

The [REDACTED] issue is encoded directly as `[REDACTED]` below — the SDK pre-1.3.2 violated this invariant.

## Hard invariants

### Encryption — AES-GCM mechanics

- **FRESH-EPHEMERAL-PER-CALL** — Every encryption call MUST generate a NEW ephemeral P-256 keypair from `crypto/rand`. Reuse across calls is forbidden.  
  *Enforcement site:* `evervault.go : getAesKeyAndCompressedEphemeralPublicKey` (called from every `Encrypt*` path).
  
- **FRESH-NONCE-PER-CALL** — Every encryption call MUST generate 12 NEW random bytes from `crypto/rand` for the GCM nonce.  
  *Enforcement site:* `internal/crypto/crypto.go : EncryptValue` (`io.ReadFull(rand.Reader, nonce)`).
  
- **NONCE-LENGTH-12** — The GCM nonce length MUST be exactly 12 bytes.  
  *Enforcement site:* `nonceSize = 12` constant in `internal/crypto/crypto.go`.
  
- **AES-KEY-LENGTH-32** — The AES key derived from the KDF MUST be 32 bytes. `aes.NewCipher` will reject anything else.  
  *Enforcement site:* implicit in `DeriveKDFAESKey` returning `sha256.Sum(...)` (32 bytes).
  
- **AAD-BINDS-EPHEMERAL-AND-APP-PUBKEY** — The AAD passed to `aesgcm.Seal` MUST contain both the ephemeral public key bytes AND the app's compressed public key bytes, prefixed by the version/datatype byte.  
  *Enforcement site:* `internal/crypto/crypto.go : CreateV2Aad`.

- **AAD-NEVER-EMPTY** — `aesgcm.Seal(..., aad)` MUST NOT be called with empty AAD.  
  *Enforcement site:* `EncryptValue` — `v2Aad` is built via `CreateV2Aad` which always emits at least 1 + 65 + 33 = 99 bytes (version-byte + uncompressed ephemeral + compressed app pubkey).
  
- **NO-NONCE-IN-CALLER-CONTROL** — No callable API path allows the caller to supply a nonce.  
  *Enforcement site:* whole-API audit — only `EncryptValue` allocates nonces and it is internal.

- **NO-AESKEY-IN-CALLER-CONTROL** — No callable API path allows the caller to supply an AES key.

### Encryption — Key derivation

- **KDF-IS-SHA256-CONCAT** — The KDF MUST be SHA-256 over `sharedECDHSecret || 0x00000001 || ANS1EncodedEphemeralPublicKey`, exactly as in `DeriveKDFAESKey`. Changing the order, omitting the counter, or substituting a different hash is a wire-incompatible change AND a security regression.
  
- **KDF-USES-EPHEMERAL-NOT-APP-PUBKEY** — The "OtherInfo" portion of the concat KDF input MUST be the ephemeral pubkey ANS1-encoded, NOT the app pubkey. (Per `DeriveKDFAESKey` and the NIST SP 800-56A "concatenation KDF" convention used by Evervault.)
  
- **ECDH-USES-APP-UNCOMPRESSED-PUBKEY** — `ephemeralECDHKey.ECDH(appPubKey)` MUST receive the App's uncompressed P-256 public key. The compressed form goes into the AAD instead.
  
- **ECDH-CURVE-IS-P256** — Both the ephemeral and the app pubkey MUST be on P-256. The SDK hard-codes `ecdh.P256()` in both places.

### Encryption — Metadata

- **METADATA-IS-IN-PLAINTEXT-NOT-AAD** — The metadata (origin, timestamp, role) is part of the AES-GCM **plaintext**, prefixed by a 2-byte little-endian length. It is encrypted AND authenticated as part of the ciphertext, but the SDK does NOT include it as AAD.  
  *Enforcement site:* `EncryptValue` — `valueWithMetadata := metadataOffset || metadata || value` is passed as the plaintext to `Seal`.

- **METADATA-ORIGIN-IS-9-FOR-GO** — Every encrypted payload from this SDK MUST contain `eo: 0x09` in its metadata. (Constant `encryptionOrigin = 0x09`.)
  
- **METADATA-TIMESTAMP-PRESENT** — Every encrypted payload MUST contain an `et` field with the current Unix-epoch seconds.

### Encryption — Wire format

- **EV-FORMAT-VERSION-IS-QkTC** — Every ciphertext MUST start with `ev:QkTC:` (the Go SDK is on Evervault Encryption Scheme v2).
  
- **EV-FORMAT-FIELDS-IN-ORDER** — `[datatype:]Base64(IV):Base64(EphemeralPubKey):Base64(Ciphertext):$`. Re-ordering breaks every downstream decoder.

- **BASE64-STRIPPED-PADDING** — `=` padding MUST be removed from each base64 segment. (`base64EncodeStripped`.)

### Decryption

- **NO-LOCAL-DECRYPT** — The SDK MUST NOT implement an AES-GCM decryption path. All `Decrypt*` calls go to Evervault's API.  
  *Enforcement site:* `evervault.go : decrypt` — POSTs to `EvAPIURL/decrypt` (private helper).

- **TYPE-CHECK-AFTER-DECRYPT** — `DecryptInt`, `DecryptBool`, `DecryptString`, etc., MUST verify the returned value's Go type matches the requested type and MUST return `ErrInvalidDataType` otherwise.

### Attestation — Document validation

- **VERIFY-BEFORE-CACHE** — A `nitrite.Document` MUST NOT be stored in the attestation cache unless `nitrite.Verify` succeeded AND `validatedDoc.SignatureOK` is `true` AND PCR0/PCR1/PCR2 are present.  
  *Enforcement site:* `internal/attestation/attestation_cache.go : [REDACTED]` (since v1.3.2). Pre-v1.3.2 the cache stored raw bytes without this [REDACTED], which is the proximate cause of [REDACTED].

- **[REDACTED]** *(THE CVE INVARIANT)* — Before comparing expected vs received PCRs, the SDK MUST confirm that the **received** attestation document has PCR0, PCR1, AND PCR2 present and non-empty. PCR8 may be absent (for unsigned EIFs).  
  *Enforcement site:* `attest.go : mapAttestationPCRs` AND `attestation/pcrs.go : (PCRs).[REDACTED]` AND `attestation/pcrs.go : (PCRs).[REDACTED]` (since v1.3.2).  
  
  **Pre-v1.3.2 violation:** `[REDACTED](p1, p2) = p1 != "" && p2 != "" && p1 != p2` returned `false` (i.e., "equal") whenever either side was empty. An attestation document that the operator served with an [REDACTED] map would silently satisfy any expected PCRs struct, because every expected vs received comparison hit the `p2 == ""` short-circuit and returned "equal". The advisory's POC sets `actualDocument.PCRs = map[uint][]byte{10: make([]byte, 32)}` — a document with NO PCR0/1/2/8 set — and shows `verifyPCRs(expectedPCRs, actualDocument) == true` on the vulnerable version.

### Attestation — Comparison semantics

- **EXPECTED-EMPTY-IS-DONTCARE** — An empty field in an expected PCRs struct MUST be treated as "any received value is acceptable for this field". But this freedom only applies to the **expected** side; on the **received** side, PCR0/1/2 emptiness is a hard fail (see [REDACTED]).

- **EXPECTED-NONEMPTY-MUST-MATCH** — A non-empty expected PCR value MUST bytewise (hex-string-wise) equal the received value.

- **OR-ACROSS-EXPECTED-SET** — Multiple PCR sets in the `[]PCRs` slice are OR'd: any one `[REDACTED]` passes.

- **REJECT-NO-EXPECTATIONS** — A `[]PCRs` slice with no non-[REDACTED] MUST be rejected with `ErrNoPCRs` at client construction.

### Attestation — Channel binding

- **PUBKEY-IN-USERDATA** — `attestCert` MUST verify `bytes.Equal(MarshalPKIX(cert.PubKey), doc.UserData)`. Without this binding, an attacker proxying a valid Nitro attestation could pair it with a different TLS certificate.

- **FAIL-CLOSED-ON-ATTEST-FAILURE** — Every failure mode in `createDial` MUST return an error and a nil `net.Conn`. There is no "warn and proceed" path.

- **NO-KEEPALIVE-ON-ENCLAVE** — The HTTP transport for enclave clients MUST set `DisableKeepAlives: true` so each request re-attests at the TLS layer.

- **TLS12-MIN-EVERYWHERE** — `tls.Config.MinVersion = tls.VersionTLS12` for relay, cages, and enclave clients.

- **TLS-VERIFY-ALWAYS-ON** — `tls.Config.InsecureSkipVerify = false` for relay, cages, and enclave clients.

- **TLS-SERVERNAME-SET** — `tls.Config.ServerName` MUST be set to the enclave hostname; otherwise SNI may leak and the cert chain validation may behave unexpectedly.

### Key handling

- **APP-PRIVKEY-NEVER-LOCAL** — The SDK MUST never receive, store, or operate on the App's ECDH **private** key. (Audit: `KeysResponse` has no private field; the public-key fetch returns only public material.)

- **EPHEMERAL-PRIVKEY-NOT-PERSISTED** — The ephemeral private key MUST go out of scope by the end of the `Encrypt*` call.

- **NO-EXPLICIT-ZEROING (KNOWN-GAP)** — The SDK does NOT explicitly zero sensitive material before GC. This is consistent with Go ecosystem practice but is a documented gap if the threat model includes process-memory dumps.

### Trust roots

- **API-KEY-FETCH-PKI-TRUST** — The public-key fetch from `EvAPIURL/cages/key` uses standard WebPKI. The SDK MUST set `tls.Config.MinVersion = TLS 1.2` (currently implicit via Go default) and MUST NOT disable verification.

- **NO-KEY-PINNING (KNOWN-GAP)** — The SDK does not pin the certificate for `api.evervault.com`. A compromise of WebPKI for that hostname compromises the trust path to the App public key.

## Sanity invariants on test surfaces (informational)

- The test suite is gated on env vars (`EV_APP_UUID`, `EV_API_KEY`, `EV_ENCLAVE_API_KEY`, `EV_SYNTHETIC_ENDPOINT_URL`, etc.) so a fresh-checkout `go test -short ./...` runs unit tests only.
- `pcrs_test.go` gained +86 lines in [REDACTED] to specifically cover the missing-PCR case the CVE exploited.

## Invariants that QPB should derive from the docs (without source)

The following list is what a QPB run with **docs only** (no source access) should be able to assemble from the cryptographic contract above:

1. SDK encrypts with **AES-256-GCM** under a **per-payload ephemeral ECDH-P256 key**.
2. **Nonce is 12 bytes, random per call** — therefore (nonce, key) pairs are unique by construction.
3. **AAD binds the ephemeral pubkey, the app pubkey, the datatype, and the version** — therefore the SDK guarantees tamper-evidence on type confusion and on cross-app replay attempts.
4. **Decryption is out-of-process** — the SDK has no AES-GCM open routine.
5. **Enclave / Cage trust requires BOTH signature verification AND PCR comparison AND cert-pubkey-in-attestation-UserData** — three checks, all must pass, all fail closed.
6. **PCRs must be present** on the received document for the comparison to be meaningful — the CVE class is "the SDK accepted a document that didn't actually attest to anything".
7. **InsecureSkipVerify is always false; MinTLS = 1.2; ServerName is set; keep-alives are disabled on enclave clients.**

Anything in the source that contradicts one of these is a candidate finding.
