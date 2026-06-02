# Known Issues and Security Advisories

## Sources

- [REDACTED] ([REDACTED]) advisory page: https://github.com/evervault/evervault-go/security/advisories/[REDACTED]
- GitHub Advisory Database entry: https://github.com/advisories/[REDACTED]
- NVD entry: https://nvd.nist.gov/vuln/detail/[REDACTED]
- Patch [REDACTED] (merged 2025-09-15): https://github.com/evervault/evervault-go[REDACTED]
- Patch commit: https://github.com/evervault/evervault-go/commit/[REDACTED]
- CHANGELOG entry for 1.3.2: https://github.com/evervault/evervault-go/blob/main/CHANGELOG.md
- GitHub Advisories portal query: https://github.com/advisories?query=evervault
- Evervault security disclosure: typical SECURITY.md / Evervault docs (no public SECURITY.md in repo as of fetch date — reporters can email security@evervault.com per advisory metadata)

## Context

evervault-go has **one public security advisory** at the time of writing:

### [REDACTED] / [REDACTED]

| Field | Value |
| --- | --- |
| Identifier | [REDACTED] (Github) / [REDACTED] (CVE) |
| Title | Evervault Go SDK: Incomplete PCR Validation in Enclave Attestation for non-Evervault hosted Enclaves |
| Severity | High |
| CVSS v3.1 | 8.7 — `AV:N/AC:L/PR:H/UI:N/S:C/C:H/I:H/A:N` |
| CWE | [REDACTED] — Improper Verification of Cryptographic Signature |
| Reporter | JoranHonig |
| Publisher | John-Hetherton (Evervault) |
| Published | 2025-11-11 (advisory) / 2025-11-12 (NVD) |
| Vulnerable | `< 1.3.2` |
| Patched | `1.3.2` |
| Patch | [REDACTED] commit `[REDACTED]` |
| EPSS percentile | 9.68% (~0.00032) — low exploitation likelihood metric |

### Summary (verbatim from advisory)

> A vulnerability was identified in the `evervault-go` SDK's attestation verification logic that may allow incomplete documents to pass validation. This may cause the client to trust an enclave operator that does not meet expected integrity guarantees.
>
> The exploitability of this issue is limited in Evervault-hosted environments as an attacker would require the pre-requisite ability to serve requests from specific evervault domain names, following from our ACME challenge based TLS certificate acquisition pipeline.
>
> The vulnerability primarily affects applications which only check PCR8. Though the efficacy is also reduced for applications that check all PCR values, the impact is largely remediated by checking PCR 0, 1 and 2.

### Root cause

The pre-1.3.2 PCR equality check, `[REDACTED]`, returned `false` ("considered equal") whenever **either** side of the comparison was the empty string:

```go
func [REDACTED](p1, p2 string) bool {
    return p1 != "" && p2 != "" && p1 != p2
}
```

`Equal` used `[REDACTED]` four times, once per PCR field. Combined with the cache storing raw bytes (not verified-and-PCR-checked documents), an attacker who controlled the attestation endpoint could serve a document with no PCR0/1/2/8 entries; every `[REDACTED]` comparison short-circuited on the receiver's empty value, every field reported "equal", and the document was deemed to attest to whatever PCRs the caller expected.

The advisory's POC sets `actualDocument.PCRs = map[uint][]byte{10: make([]byte, 32)}` — a single PCR10 entry, none of the load-bearing PCR0/1/2/8 — and shows that `verifyPCRs(expectedPCRs, actualDocument)` returns `true` on the vulnerable version.

### Patch (v1.3.2)

Three coordinated changes:

1. **Cache stores verified documents only** (`internal/attestation/attestation_cache.go : [REDACTED]`):
   - Calls `nitrite.Verify`.
   - Asserts `validatedDoc.SignatureOK`.
   - Asserts PCR0, PCR1, PCR2 are present in the document's `PCRs` map (using the comma-ok idiom).
   - Returns an error otherwise; bad documents never enter the cache.

2. **`mapAttestationPCRs` enforces PCR0/1/2 presence at comparison time** (`attest.go`):
   ```go
   PCR0, ok := attestationPCRs.PCRs[0]
   if !ok { return ..., ErrMissingPCR }
   // same for 1, 2
   ```
   PCR8 is read with the comma-ok idiom but absence is allowed (so unsigned EIFs are still acceptable).

3. **New `[REDACTED]` method on `PCRs`** (`attestation/pcrs.go`):
   - Short-circuits on `!receivedPCRs.[REDACTED]()` (i.e., received PCR0/1/2 all non-empty) — this is the load-bearing check that closes the CVE.
   - For each PCR field, only enforces equality if the **expected** value is non-empty; an empty expected value is treated as "don't care".
   - Replaces the unsound `Equal` call in `verifyPCRs`.

### Workarounds (per advisory, for users who cannot upgrade to 1.3.2)

> 1. Modify your application logic to fail verification if PCR8 is not explicitly present and non-empty.
> 2. Add custom pre-validation to reject documents that omit any required PCRs.

### Disclosure timeline (reconstructed)

- 2025-09-15: [REDACTED] merged; v1.3.2 cut the same day.
- 2025-11-11: GitHub advisory published (`updated_at` 11:47 UTC).
- 2025-11-12: NVD entry published (21:15 UTC).

### Why this matters cryptographically

The vulnerability is in the **trust-establishment** layer, not in the AEAD itself. AES-GCM continued to work correctly. ECDH continued to work correctly. The bug is that the SDK accepted as a "trusted enclave" a peer that had **no signed measurement of the workload running there**. Once the connection was considered attested, any application-layer secret the caller sent over that channel — including ciphertexts they had encrypted with the App public key and were forwarding to a Cage / Enclave for processing — was sent to an attacker-controlled endpoint with all the integrity guarantees of "this is the right enclave" silently downgraded to "this is any host serving a valid TLS cert for the expected domain".

### Why it primarily affects PCR8-only callers

A caller checking only PCR8 in their expected `PCRs` struct (PCR0/1/2 all empty strings) was completely unprotected: even before the CVE, PCR8 is the only field they were comparing, and `[REDACTED]("expected", "")` returned `false` → "equal". For callers who set PCR0/1/2 to non-empty values, the bug still triggered if **any one** of those received PCRs was missing — the empty-string short-circuit hit on the comma-ok-defaulted received side.

### CWE classification

[REDACTED] ("Improper Verification of Cryptographic Signature") is the assigned CWE. Arguably the root cause is closer to CWE-1025 ("Comparison Using Wrong Factors") or CWE-754 ("Improper Check for Unusual or Exceptional Conditions") — the SDK was checking equality without first checking that the operands were valid — but the operational impact is signature-bypass-shaped, which the GitHub Reviewed labeling captured as [REDACTED].

## Other security-relevant CHANGELOG items

From the CHANGELOG (not separate CVEs, but security-flavored):

- **1.3.1** — "Remove log line from Attestation Document caching" — a noisy log was leaking attestation cache state to stdout. Information disclosure adjacent; no CVE.
- **1.3.0** — "Patch Decrypt calls and Enclave Attestation Document fetching" — described in PR #37 as a polling/decrypt fix. Not a CVE but touched the same subsystem.
- **1.1.0** — Deprecated `CagesClient` in favor of `EnclaveClient`. Migration retained the same attestation logic, so the v1.3.2 fix is required on both code paths.
- **1.0.0** — Migrated Function run requests to a new API. Not security-related.

## Disclosure policy

The repo does not ship a `SECURITY.md`. The advisory shows the `Evervault security team` (publisher: John-Hetherton@Evervault) handles reports; standard GitHub private vulnerability reporting is enabled on the repo (`has_issues: true`, security tab present). Evervault's public security contact is documented on the main Evervault site (https://evervault.com/security typically) — the SDK relies on Evervault's company-wide disclosure process rather than maintaining its own.

## Invariants implied by the advisory

- INV-ADV-1: Any future PCR comparison code MUST replicate `[REDACTED]`'s `![REDACTED]()` short-circuit. Replacing it with a "loop over fields and compare" idiom risks reintroducing the CVE.
- INV-ADV-2: Any future caching of attestation documents MUST validate before insert (signature + PCR0/1/2 presence). Caching unvalidated bytes is the prior failure mode.
- INV-ADV-3: New attestation-related code paths (e.g., a hypothetical TDX/SGX equivalent) MUST inherit the same "validate-and-then-compare" discipline. An additive helper that bypasses these gates would re-open the CVE class.
- INV-ADV-4: The legacy `Equal` method (which still ships on the `PCRs` struct as of v1.3.2) MUST NOT be called from the attestation hot path. It's preserved for backward compatibility but is unsafe.
