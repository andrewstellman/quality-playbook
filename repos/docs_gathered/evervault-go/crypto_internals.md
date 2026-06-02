# Encryption primitives (internal/crypto)

The `internal/crypto` package implements the per-call cryptographic work that backs the public `Encrypt*` methods. It is not exported, but its shape is part of the SDK's contract with the Evervault server side: the wire format must round-trip with whatever the Evervault API decrypts.

## Key derivation

```go
func DeriveKDFAESKey(publicKey, sharedECDHSecret []byte) ([]byte, error)
```

Given the ephemeral public key (uncompressed) and the raw ECDH shared secret produced from the app public key + ephemeral private key, this derives a symmetric AES key. The derivation hashes (SHA-256) the byte sequence `sharedECDHSecret || 0x00000001 || (p256 ANS1 prefix || hex(publicKey))`. The ANS1 prefix is a hard-coded SubjectPublicKeyInfo header for P-256 declared as a package constant; concatenating it with the hex-encoded raw key produces a standards-shaped DER blob without depending on `crypto/x509` marshalling at this site.

## Public-key compression

```go
func CompressPublicKey(keyToCompress []byte) []byte
```

Takes an uncompressed SEC1-encoded P-256 public key (65 bytes: `0x04` prefix + X + Y) and returns the 33-byte compressed form: a `0x02` or `0x03` prefix (chosen by the parity of the Y coordinate's last byte) followed by the X coordinate.

## Additional authenticated data

```go
func CreateV2Aad(datatype datatypes.Datatype, ephemeralPublicKey, appPublicKey []byte) (bytes.Buffer, error)
```

Builds the AAD passed to AES-GCM. The first byte is a packed `(datatype << 4) | version`, where version is 1 and datatype is 0 (string), 1 (number), or 2 (boolean). The ephemeral public key and the app public key follow as raw bytes.

## Encryption entry point

```go
func EncryptValue(aesKey, ephemeralPublicKey, appPublicKey []byte,
    value, role string, datatype datatypes.Datatype) (string, error)
```

Creates an AES cipher and GCM mode, generates a 12-byte nonce via `crypto/rand`, builds the metadata block (`buildEncodedMetadata`), prepends a two-byte little-endian length prefix, appends the plaintext value bytes, and seals the result under the V2 AAD. The output is then formatted by `evFormat`.

## Metadata block

`buildEncodedMetadata` writes a MessagePack-style fixed-map header (2 entries when there is no role, 3 entries with a role). Each entry is a 2-byte key (`"eo"`, `"et"`, `"dr"`) followed by a typed value: an unsigned int for the encryption origin (`9`, the Go SDK identifier), a 4-byte big-endian unsigned int for the encryption timestamp (`time.Now().Unix()`), and a fixed-length string for the data role when present.

## Wire format

```go
func evFormat(cipherText, iv, publicKey []byte, datatype datatypes.Datatype) string
```

Produces strings of the form `ev:QkTC:[number:|boolean:]<b64(iv)>:<b64(publicKey)>:<b64(cipherText)>:$`. Base64 padding is stripped via `base64EncodeStripped`. String values omit the datatype tag; number and boolean values include `number:` or `boolean:` between the version marker and the IV.

Word count: ~410
