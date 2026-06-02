# Encryption and decryption API

The public encryption surface is per-datatype: there is one method per primitive Go kind the SDK supports, plus a "WithDataRole" variant that lets callers tag the ciphertext with a role name used for downstream access control.

```go
func (c *Client) EncryptString(value string) (string, error)
func (c *Client) EncryptStringWithDataRole(value, role string) (string, error)

func (c *Client) EncryptInt(value int) (string, error)
func (c *Client) EncryptIntWithDataRole(value int, role string) (string, error)

func (c *Client) EncryptFloat64(value float64) (string, error)
func (c *Client) EncryptFloat64WithDataRole(value float64, role string) (string, error)

func (c *Client) EncryptBool(value bool) (string, error)
func (c *Client) EncryptBoolWithDataRole(value bool, role string) (string, error)

func (c *Client) EncryptByteArray(value []byte) (string, error)              // deprecated; use EncryptString
func (c *Client) EncryptByteArrayWithDataRole(value []byte, role string) (string, error)
```

All variants follow the same shape internally: derive a fresh AES key, encode the value as a string, hand `aesKey`, `compressedEphemeralPublicKey`, `appPublicKey`, the string form of the value, the role (or `""`), and a `datatypes.Datatype` to `crypto.EncryptValue`. The numeric kinds encode via `strconv.Itoa` / `strconv.FormatFloat` / `strconv.FormatBool`; the byte-array path simply casts to `string`. The datatype tag chooses between `datatypes.String`, `datatypes.Number`, and `datatypes.Boolean` — the same enum is encoded into the wire format so the decryption side restores the right Go type.

The decryption surface mirrors it:

```go
func (c *Client) DecryptString(encryptedData string) (string, error)
func (c *Client) DecryptInt(encryptedData string) (int, error)
func (c *Client) DecryptFloat64(encryptedData string) (float64, error)
func (c *Client) DecryptBool(encryptedData string) (bool, error)
func (c *Client) DecryptByteArray(encryptedData string) ([]byte, error)      // deprecated
```

Decryption is delegated to the Evervault API: `c.decrypt` JSON-encodes the encrypted string, `POST`s it to `Config.EvAPIURL + "/decrypt"` with basic auth, and parses the response as `any`. Each typed wrapper then type-asserts the result; the integer path narrows a `float64` (since JSON numbers decode that way). A failed assertion returns `ErrInvalidDataType`.

Finally, the SDK can mint a time-bound token a browser can later use to perform a decryption client-side:

```go
func (c *Client) CreateClientSideDecryptToken(payload any, expiry ...time.Time) (TokenResponse, error)
```

A nil payload yields `ErrInvalidDataType`. If `expiry` is omitted the server applies its default (5 minutes); a caller-supplied time is sent as `UnixMilli()` and forwarded to the `/client-side-tokens` endpoint with action `"api:decrypt"`. The returned `TokenResponse` carries the token string and the server-issued expiry.

Word count: ~390
