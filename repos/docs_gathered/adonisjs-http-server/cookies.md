# Cookies

Cookie handling is split across four classes (`CookieClient`, `CookieParser`, `CookieSerializer`, and three driver modules) that together support three distinct cookie flavours: plain, signed, and encrypted.

## Package locations

| File | Role |
|---|---|
| `src/cookies/client.ts` | `CookieClient` — low-level encode/decode |
| `src/cookies/parser.ts` | `CookieParser` — lazy inbound cookie parsing |
| `src/cookies/serializer.ts` | `CookieSerializer` — outbound cookie serialization |
| `src/cookies/drivers/plain.ts` | Plain (base64 JSON) driver |
| `src/cookies/drivers/signed.ts` | HMAC-signed driver |
| `src/cookies/drivers/encrypted.ts` | AES-encrypted driver |

All three classes are exported from the package root.

## Cookie flavours

### Plain cookies

The value is serialised with `JSON.stringify` and then base64-encoded. No integrity protection is applied. The `stringify` option (boolean) controls whether JSON serialization is performed; setting it to `false` stores the raw string.

### Signed cookies

The value is serialised as JSON, then an HMAC signature is appended. On reading, the signature is verified before the value is returned. If verification fails, `null` is returned. Signing uses the `@boringnode/encryption` service.

### Encrypted cookies

The value is serialised and then fully encrypted (not just signed) using the `@boringnode/encryption` service. The raw cookie header reveals only opaque ciphertext. Decryption failure returns `null`.

## CookieClient

`CookieClient` is the lowest-level abstraction. It is not used directly by application code; instead `CookieParser` and `CookieSerializer` compose it.

```ts
class CookieClient {
  constructor(encryption: Encryption)

  // Outbound
  encrypt(key: string, value: any): string | null
  sign(key: string, value: any): string | null
  encode(key: string, value: any, stringify?: boolean): string | null

  // Inbound
  decrypt(key: string, value: string): any | null
  unsign(key: string, value: string): any | null
  decode(key: string, value: string, stringified?: boolean): any | null

  // Test helper
  parse(key: string, cookieValue: string): any | null
}
```

`parse` auto-detects the cookie flavour by inspecting the value prefix, making it useful in test harnesses where the exact flavour is not known ahead of time.

## CookieParser

`CookieParser` processes the inbound `Cookie` header. It is created lazily inside `HttpRequest` on the first cookie access.

```ts
class CookieParser {
  constructor(cookieHeader: string, encryption: Encryption)

  decode(key: string, stringified?: boolean): any | null    // plain
  unsign(key: string): any | null                           // signed
  decrypt(key: string): any | null                          // encrypted
  list(): Record<string, any>                               // raw key-value
}
```

**Lazy decoding per key**: Parsing all cookies on every request would waste CPU when only one or two are actually needed. Instead, each key's value is decoded on first access and cached in a per-parser cache object split by flavour (`plainCookies`, `signedCookies`, `encryptedCookies`). Subsequent reads for the same key return the cached value.

The raw cookie header is parsed once at construction time by `cookie-es`'s `parse` function. The per-key caching layer (`#getCachedOrParse`) is a generic private helper shared across all three flavours.

## CookieSerializer

`CookieSerializer` constructs the `Set-Cookie` header value for outbound responses. It is created once per response inside `HttpResponse`.

```ts
class CookieSerializer {
  constructor(encryption: Encryption)

  encode(key, value, options?): string | null   // plain
  sign(key, value, options?): string | null      // signed
  encrypt(key, value, options?): string | null   // encrypted
}
```

Each method calls the corresponding `CookieClient` method to produce the packed value, then passes it through `serializeCookie` (which wraps `cookie-es`'s `serialize`) to add attributes like `Path`, `HttpOnly`, `Secure`, `SameSite`, `MaxAge`, and `Domain`.

The `options` parameter is typed as `Partial<CookieOptions>`:

```ts
type CookieOptions = {
  domain: string
  expires: Date | (() => Date)
  httpOnly: boolean
  maxAge: number | string
  path: string
  sameSite: boolean | 'lax' | 'none' | 'strict'
  secure: boolean
  partitioned?: boolean
  priority?: 'low' | 'medium' | 'high'
}
```

Options are merged with the global cookie defaults from `ServerConfig.cookie` at the response level (in `HttpResponse`).

## Application-level API

Application code interacts with cookies via `HttpRequest` and `HttpResponse`, not directly with `CookieParser` or `CookieSerializer`:

```ts
// Reading cookies (HttpRequest)
ctx.request.cookie('prefs')               // plain
ctx.request.signedCookie('session')       // signed
ctx.request.encryptedCookie('userId')     // encrypted
ctx.request.plainCookie('raw')            // raw string
ctx.request.cookiesList()                 // all raw cookies

// Writing cookies (HttpResponse)
ctx.response.cookie('prefs', { theme: 'dark' })
ctx.response.signedCookie('session', token)
ctx.response.encryptedCookie('userId', id, { maxAge: '30d' })
ctx.response.clearCookie('session')
```

`clearCookie` sets the expiry to the Unix epoch and clears `maxAge`, causing the browser to discard the cookie.

## Test helper: CookieClient

For integration tests that need to simulate a browser sending server-issued cookies, the `CookieClient` class is exported from `./factories` via `HttpContextFactory` and related factory classes. Tests can directly call `client.encrypt`, `client.sign`, or `client.encode` to produce cookie header values, and `client.parse` to decode values received in `Set-Cookie` response headers.
