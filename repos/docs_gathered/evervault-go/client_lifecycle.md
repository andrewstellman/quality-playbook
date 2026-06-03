# Client lifecycle and initialization

The entry point to the SDK is the `evervault.Client` type. Callers obtain one through either of two constructors:

```go
func MakeClient(appUUID, apiKey string) (*Client, error)
func MakeCustomClient(appUUID, apiKey string, config Config) (*Client, error)
```

`MakeClient` is a convenience wrapper that calls `MakeConfig()` (see the configuration doc) and forwards to `MakeCustomClient`. Both constructors require a non-empty `apiKey` and `appUUID`; if either is empty the constructor returns `ErrAppCredentialsRequired` and a nil client.

The `Client` struct itself is small and intentionally not user-constructable in a meaningful way:

```go
type Client struct {
    Config                    Config
    appUUID                   string
    apiKey                    string
    p256PublicKeyUncompressed []byte
    p256PublicKeyCompressed   []byte
}
```

Only `Config` is exported. Credentials and the cached app public keys are private fields populated during initialization.

After field assignment, the constructor invokes `client.initClient()`, which performs a single HTTP `GET` against `Config.EvAPIURL + "/cages/key"`. The response is parsed into a `KeysResponse`:

```go
type KeysResponse struct {
    TeamUUID                string `json:"teamUuid"`
    Key                     string `json:"key"`
    EcdhKey                 string `json:"ecdhKey"`
    EcdhP256Key             string `json:"ecdhP256Key"`
    EcdhP256KeyUncompressed string `json:"ecdhP256KeyUncompressed"`
}
```

The `EcdhP256Key` and `EcdhP256KeyUncompressed` fields are base64-decoded and stored on the client for the lifetime of the instance. Both are used by the encryption path: the compressed form is embedded in the encrypted output (so server-side decryption knows which app public key was used), and the uncompressed form is imported into a `crypto/ecdh.P256()` curve to derive a shared secret with a freshly generated ephemeral key on every encrypt call.

Once `initClient` returns successfully, the client is reusable across goroutines for encryption (no further mutation occurs to the cached keys). Token creation, decryption, and function invocation are all stateless from the client's perspective — each call builds its own HTTP request.

The auxiliary types exported from `client.go` that callers may see in return values:

```go
type TokenResponse struct {
    Token  string `json:"token"`
    Expiry int64  `json:"expiry"`
}
```

`TokenResponse` is returned by `CreateClientSideDecryptToken` and by the function-token path. If the initial public-key fetch fails — non-`200` status, JSON parse error, or a credentials/decoding error — the constructor returns a wrapped error and a nil client; the caller should treat that as fatal for the session.

Word count: ~380
