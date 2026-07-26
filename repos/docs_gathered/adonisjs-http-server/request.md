# Request

`HttpRequest` is the wrapper over Node.js `IncomingMessage` that provides a uniform API for reading request data. It is exported from the package root and also accessible as `ctx.request` inside handlers and middleware.

## Package location

`src/request.ts` — extends `@poppinss/macroable` (`Macroable`), making the class extensible at runtime via macros and getters.

## Constructor

```ts
new HttpRequest(
  request: IncomingMessage,
  response: ServerResponse,
  encryption: Encryption,
  config: RequestConfig,
  qsParser: Qs
)
```

The native Node.js `IncomingMessage` is stored as the public `request` property. The URL is parsed immediately on construction using `safeDecodeURI`, which produces a `parsedUrl` object with `pathname`, `query`, and `shouldDecodeParam` fields. The query string is also parsed immediately and merged into the internal request data object.

## Request body

The body is **not** parsed by `HttpRequest` itself — that responsibility belongs to an external body-parser middleware. The body-parser calls the following methods to populate body state:

```ts
request.setInitialBody(body: Record<string, any>): void
request.updateBody(body: Record<string, any>): void
request.updateRawBody(rawBody: string): void
request.updateQs(data: Record<string, any>): void
```

`setInitialBody` may be called at most once; a subsequent call throws. It freezes a copy of the merged body+querystring as the "original" snapshot. `updateBody` and `updateQs` can be called any number of times and recompute the merged `#requestData` object.

## Data access methods

```ts
request.all()       // merged body + query string
request.body()      // parsed body only
request.qs()        // query string only
request.original()  // frozen snapshot of initial all()
request.params()    // route params (from ctx.params)
request.raw()       // raw body string or null
```

Specific values can be retrieved with `input(key, defaultValue)`, which reads from `all()`.

## URL and method

```ts
request.url()          // parsed pathname (without query string)
request.originalUrl()  // raw request.url from Node.js
request.method()       // normalised HTTP method string
request.hostname()     // host header (sans port)
request.subdomains()   // array of subdomain segments
request.ip()           // client IP, respecting trustProxy config
request.ips()          // all client IPs
request.protocol()     // 'http' or 'https'
request.secure()       // shorthand for protocol() === 'https'
```

The `method()` implementation respects `allowMethodSpoofing` from config: when enabled, a `_method` query-string parameter (for POST requests) overrides the HTTP method.

## Headers

```ts
request.header(key)              // single header (case-insensitive)
request.header(key, default)     // with fallback
request.headers()                // all headers
request.hasHeader(key)           // boolean check
```

## Content negotiation

`HttpRequest` wraps the `accepts` package for content negotiation. The `accepts` instance is created lazily on first use:

```ts
request.accepts(['json', 'html'])
request.acceptsLanguages(['en', 'fr'])
request.acceptsEncodings(['gzip', 'identity'])
request.acceptsCharsets(['utf-8'])
request.types()          // parsed content-type
request.is('json')       // type-is check
request.fresh()          // conditional-GET freshness check (uses etag / last-modified)
request.stale()          // inverse of fresh()
```

## Cookies

Cookie parsing is lazy: the `CookieParser` is instantiated on the first access.

```ts
request.cookie(key)                // decoded (plain) cookie
request.encryptedCookie(key)       // decrypted cookie
request.signedCookie(key)          // unsigned (verified) cookie
request.plainCookie(key)           // raw string value without decoding
request.cookiesList()              // raw cookie header key-value map
```

## Request ID

```ts
request.id()
```

If the `x-request-id` header is present, its value is returned. Otherwise, if `generateRequestId` is `true` in config, a UUID is generated via `config.createRequestId()`, written back into the headers, and returned. This value is used to tag the per-request child logger.

## Request configuration

Relevant fields of `RequestConfig`:

| Field | Type | Default | Description |
|---|---|---|---|
| `subdomainOffset` | `number` | `2` | How many URL segments to ignore when extracting subdomains |
| `generateRequestId` | `boolean` | `false` | Auto-generate an `x-request-id` if not present |
| `createRequestId` | `() => string` | `crypto.randomUUID` | Factory for request IDs |
| `allowMethodSpoofing` | `boolean` | `false` | Allow `_method` query string to override HTTP method |
| `trustProxy` | `(address, distance) => boolean` | loopback only | Controls which IPs are trusted as proxies |
| `getIp` | `(request, originalFn) => string` | `undefined` | Custom IP resolution override |

## Macroable extension

Because `HttpRequest` extends `Macroable`, application code can add methods and getters without subclassing:

```ts
HttpRequest.macro('currentUser', function (this: HttpRequest) {
  return this.ctx?.auth?.user
})

HttpRequest.getter('geoLocation', function (this: HttpRequest) {
  return parseGeo(this.ip())
}, true /* cached */)
```

Added macros are available on every request instance for the lifetime of the process.
