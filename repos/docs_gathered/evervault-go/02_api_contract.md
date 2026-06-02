# Public API Contract

## Sources

- `evervault.go`: https://github.com/evervault/evervault-go/blob/main/evervault.go
- `client.go`: https://github.com/evervault/evervault-go/blob/main/client.go
- `enclave.go`: https://github.com/evervault/evervault-go/blob/main/enclave.go
- `cage.go`: https://github.com/evervault/evervault-go/blob/main/cage.go
- `function.go`: https://github.com/evervault/evervault-go/blob/main/function.go
- `relay.go`: https://github.com/evervault/evervault-go/blob/main/relay.go
- `attestation/pcrs.go`: https://github.com/evervault/evervault-go/blob/main/attestation/pcrs.go
- `error.go`: https://github.com/evervault/evervault-go/blob/main/error.go
- `config.go`: https://github.com/evervault/evervault-go/blob/main/config.go
- Public Go docs: https://pkg.go.dev/github.com/evervault/evervault-go
- Evervault docs (Go reference): https://docs.evervault.com/sdks/go

## Context

The exported surface of `package evervault` is small. Everything is reached through a `*Client` obtained from `MakeClient` or `MakeCustomClient`.

### Construction

```go
func MakeClient(appUUID, apiKey string) (*Client, error)
func MakeCustomClient(appUUID, apiKey string, config Config) (*Client, error)
```

Both call `Client.initClient()` which performs a `GET /cages/key` against `Config.EvAPIURL` and stores the App's compressed and uncompressed P-256 public keys on the client. Returns `ErrAppCredentialsRequired` if either argument is empty.

### Configuration

```go
type Config struct {
    EvervaultCaURL             string        // default https://ca.evervault.com
    EvervaultCagesCaURL        string        // default https://cages-ca.evervault.com/cages-ca.crt
    RelayURL                   string        // default https://relay.evervault.com
    EvAPIURL                   string        // default https://api.evervault.com
    CagesPollingInterval       time.Duration // legacy alias of AttestationPollingInterval
    AttestationPollingInterval time.Duration // default 120s, env EV_ATTESTATION_POLLING_INTERVAL
}
```

### Encryption surface

All encrypt methods return a string (the `ev:QkTC:...:$` token) and an error.

```go
func (c *Client) EncryptString(value string) (string, error)
func (c *Client) EncryptStringWithDataRole(value, role string) (string, error)
func (c *Client) EncryptInt(value int) (string, error)
func (c *Client) EncryptIntWithDataRole(value int, role string) (string, error)
func (c *Client) EncryptFloat64(value float64) (string, error)
func (c *Client) EncryptFloat64WithDataRole(value float64, role string) (string, error)
func (c *Client) EncryptBool(value bool) (string, error)
func (c *Client) EncryptBoolWithDataRole(value bool, role string) (string, error)
func (c *Client) EncryptByteArray(value []byte) (string, error)              // Deprecated
func (c *Client) EncryptByteArrayWithDataRole(value []byte, role string) (string, error)  // Deprecated
```

**Guarantees per call:**
- Confidentiality + integrity: AES-256-GCM. See `01_cryptographic_contract.md`.
- Freshness: a new ephemeral P-256 key and a new 12-byte nonce per call.
- Datatype tag in AAD: `String`, `Number`, or `Boolean`. `EncryptInt` and `EncryptFloat64` both encode as `Number`. `EncryptBool` encodes as `Boolean`. `EncryptString` and `EncryptByteArray` both encode as `String`.
- Data role: optional. Appears in encrypted metadata if non-empty. Influences server-side decrypt authorization but is NOT itself authenticated under the AAD — it lives in the AEAD plaintext (so is encrypted AND authenticated as part of the ciphertext, but is invisible to the SDK after `Seal` returns).

**Failure modes:**
- `ErrAppCredentialsRequired` — only at construction.
- `ErrCryptoKeyImportError` — if `ecdh.P256().NewPublicKey(...)` fails on the cached App public key.
- Wrapped `fmt.Errorf` errors for nonce-generation failure, ECDH failure, cipher creation failure, metadata-build failure. There is no sentinel; callers must use `errors.Is/errors.As` against the wrapped strings.

### Decryption surface

```go
func (c *Client) DecryptString(encryptedData string) (string, error)
func (c *Client) DecryptInt(encryptedData string) (int, error)
func (c *Client) DecryptFloat64(encryptedData string) (float64, error)
func (c *Client) DecryptBool(encryptedData string) (bool, error)
func (c *Client) DecryptByteArray(encryptedData string) ([]byte, error)   // Deprecated
```

**Guarantees per call:**
- The SDK does NOT decrypt locally. It POSTs the ciphertext to Evervault's API; E3 inside a Nitro Enclave performs the AES-GCM open.
- Returns `ErrInvalidDataType` if the decrypted JSON value doesn't match the requested Go type (e.g. calling `DecryptInt` on a ciphertext that was an encrypted bool).
- TLS to `api.evervault.com` is standard WebPKI (no pinning).

### Client-side decrypt tokens

```go
func (c *Client) CreateClientSideDecryptToken(payload any, expiry ...time.Time) (TokenResponse, error)

type TokenResponse struct {
    Token  string `json:"token"`
    Expiry int64  `json:"expiry"`
}
```

Issues a short-lived, single-payload token bound to a specific ciphertext that a downstream (e.g. browser) client can use to decrypt. Default expiry 5 minutes, max 10 minutes (enforced server-side).

### Function invocation

```go
func (c *Client) RunFunction(functionName string, payload map[string]any) (FunctionRunResponse, error)
func (c *Client) CreateFunctionRunToken(functionName string, payload any) (RunTokenResponse, error)

type FunctionRunResponse struct {
    Status string         `json:"status"`
    ID     string         `json:"id"`
    Result map[string]any `json:"result"`
}
type RunTokenResponse struct {
    Token string `json:"token"`
}
```

Specific function-related errors: `FunctionNotReadyError`, `FunctionTimeoutError` (in `error.go`).

### Outbound Relay

```go
func (c *Client) OutboundRelayClient() (*http.Client, error)
```

Returns an `http.Client` whose `Transport` is a TLS-12-minimum HTTPS proxy to `RelayURL`, with the Evervault CA cert (fetched at call time from `EvervaultCaURL`) appended to the system pool, and the `Proxy-Authorization` header preset to the client's API key. **No attestation at this layer; relies on PKI.**

### Cages client (deprecated)

```go
func (c *Client) CagesClient(cageHostname string, pcrs []attestation.PCRs) (*http.Client, error)
func (c *Client) CagesClientWithProvider(cageHostname string, pcrsProvider func() ([]attestation.PCRs, error)) (*http.Client, error)
```

Deprecated since v1.1.0. Same behavior as `EnclaveClient*` but wraps under the older naming for backward compatibility. Both create an `http.Client` whose `DialTLSContext` performs the attestation handshake.

### Enclave client (current)

```go
func (c *Client) EnclaveClient(enclaveHostname string, pcrs []attestation.PCRs) (*http.Client, error)
func (c *Client) EnclaveClientWithProvider(enclaveHostname string, pcrsProvider func() ([]attestation.PCRs, error)) (*http.Client, error)
func (c *Client) EnclaveTCPConnectionWithProvider(enclaveHostname string, pcrsProvider func() ([]attestation.PCRs, error)) (...)  // for non-HTTP dial
```

**Guarantees per HTTP request issued through the returned client:**
- Each request opens a fresh TCP+TLS connection (`DisableKeepAlives: true` in `cagesClient` and `enclave.go`).
- For each connection: TLS handshake → fetch (or cache-read) attestation document → verify document signature (in cache validation) → verify PCRs against caller's expected PCR set → verify TLS cert pubkey matches attestation `UserData` field → return TLS conn or `ErrAttestionFailure`.
- TLS config: `InsecureSkipVerify: false`, `MinVersion: TLS 1.2`, `ServerName: <hostname>`.

### PCRs type

```go
type PCRs struct {
    PCR0, PCR1, PCR2, PCR8 string  // hex-encoded
}
func (p *PCRs) Equal(pcrs PCRs) bool       // legacy lenient comparison (used elsewhere)
func (p *PCRs) SatisfiedBy(received PCRs) bool  // post-CVE-2025-64186 strict comparison
func (p *PCRs) IsEmpty() bool
func BuildStaticPcrProvider(pcrs []PCRs) func() ([]PCRs, error)
```

`SatisfiedBy` is the function added in v1.3.2. Its semantics:
- Short-circuit return `false` if the received PCRs are not a "minimal PCR set" (PCR0, PCR1, PCR2 all non-empty).
- Then, for each of PCR0/PCR1/PCR2/PCR8: if the expected value is non-empty AND differs from received, return `false`.
- An empty expected value is "don't care".

The legacy `Equal` is the inverse semantics that was used pre-1.3.2 in `pcrNotEqual`, and is preserved on the type but is no longer used in the attestation path. The `Equal` function still has the **CVE-style flaw**: `pcrNotEqual` returns `false` (i.e. "considered equal") if EITHER side is the empty string. If anything inside the SDK or a caller's code still uses `Equal` against an attestation document with missing fields, the bug recurs.

### Sentinel errors

```go
ErrUnVerifiedSignature      // certificate signature
ErrNoPCRs                   // expected PCR set is empty
ErrInvalidPCRProvider       // unsupported provider type
ErrMissingPCR               // attestation doc missing PCR0/1/2
ErrAttestionFailure         // attestation failed
ErrClientNotInitilization   // [sic] client init failure
ErrAppCredentialsRequired   // missing apiKey or appUUID
ErrCryptoKeyImportError     // ecdh.NewPublicKey rejected app key
ErrCryptoUnableToPerformEncryption
ErrInvalidDataType          // decrypted type mismatch
ErrUnsupportedNetworkType   // non-TCP dial
```

## Invariants on the public API

- INV-API-1: A `*Client` returned by `MakeClient` is the only legitimate carrier of the App public key. Any encrypt call on a `*Client` with a zero `p256PublicKeyUncompressed` must fail with `ErrCryptoKeyImportError`.
- INV-API-2: Every `Encrypt*` MUST end up in `crypto.EncryptValue` with non-empty `aesKey`, non-empty `ephemeralPublicKey`, non-empty `appPublicKey`, and the correct `datatypes.Datatype` literal for the input Go type.
- INV-API-3: `EncryptString` and `EncryptByteArray` MUST produce ciphertexts with the same datatype tag (`String`) so they round-trip through the same `DecryptString`.
- INV-API-4: `EncryptInt` and `EncryptFloat64` MUST produce ciphertexts with the same datatype tag (`Number`). The wire format prefixes both with the `number:` segment.
- INV-API-5: `EnclaveClient` and `CagesClient` MUST produce an `*http.Client` only if the `pcrs` argument contains at least one PCR set with at least one non-empty field. Otherwise return `ErrNoPCRs`.
- INV-API-6: `EnclaveClient` MUST set `tls.Config{InsecureSkipVerify: false, MinVersion: tls.VersionTLS12, ServerName: <hostname>}`. The same applies to `CagesClient`.
- INV-API-7: `OutboundRelayClient` MUST set `tls.Config{InsecureSkipVerify: false, MinVersion: tls.VersionTLS12}` and MUST append the Evervault CA cert before establishing connections.
- INV-API-8: `CreateClientSideDecryptToken` MUST refuse a nil payload (`ErrInvalidDataType`) and MUST forward an expiry of at most "now + 10 minutes" (server side enforces; the SDK does not pre-validate the upper bound — only that "now + 5 minutes" is the default when `expiry` is not supplied).
- INV-API-9: `RunFunction` MUST forward the payload exactly as supplied (no implicit encryption); if the caller wants encrypted fields, they MUST encrypt them themselves before invocation.
- INV-API-10: Sentinel errors are part of the API contract; any internal refactor MUST preserve the error identity returned for the documented failure modes.
- INV-API-11: Deprecated `EncryptByteArray*` MUST remain wire-compatible with `EncryptString` (`datatypes.String`); breaking that would silently break existing decrypts.
