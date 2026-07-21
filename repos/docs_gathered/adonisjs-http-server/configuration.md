# Configuration

All server configuration is centralised in the `defineConfig` function and the `ServerConfig` type. `defineConfig` merges user-provided options with built-in defaults and normalises certain values (cookie `maxAge`, trust-proxy function).

## Package location

`src/define_config.ts` — exported from the package root as `defineConfig`.

## Usage

```ts
import { defineConfig } from '@adonisjs/http-server'

const config = defineConfig({
  trustProxy: true,
  useAsyncLocalStorage: false,
  cookie: { maxAge: '7d', secure: false },
  etag: true,
  qs: {
    parse: { depth: 5, arrayLimit: 20 },
    stringify: { skipNulls: false },
  },
})
```

The result is a fully-resolved `ServerConfig` object passed to the `Server` constructor.

## ServerConfig reference

`ServerConfig` is the intersection of `RequestConfig`, `ResponseConfig`, and several server-level fields.

### Server-level fields

| Field | Type | Default | Description |
|---|---|---|---|
| `useAsyncLocalStorage` | `boolean` | `false` | Enable Node.js `AsyncLocalStorage` for context propagation |
| `keepAliveTimeout` | `number` (ms) | Node.js default (5000) | Socket keep-alive timeout |
| `headersTimeout` | `number` (ms) | Node.js default (60000) | Time to receive complete HTTP headers |
| `requestTimeout` | `number` (ms) | Node.js default (300000) | Time to receive the full request body |
| `timeout` | `number` (ms) | Node.js default (0) | Socket inactivity timeout |
| `onBadUrl` | `(req, res) => void` | 400 plain-text response | Handler invoked when the request URI contains malformed percent-encoding |
| `qs` | `QSParserConfig` | see below | Query string parser configuration |

### RequestConfig fields

| Field | Type | Default | Description |
|---|---|---|---|
| `subdomainOffset` | `number` | `2` | Number of URL segments to ignore when extracting subdomains |
| `generateRequestId` | `boolean` | `false` | Auto-generate `x-request-id` if the header is absent |
| `createRequestId` | `() => string` | `crypto.randomUUID` | Factory for request IDs |
| `allowMethodSpoofing` | `boolean` | `false` | Allow `_method` query param to override HTTP method on POST requests |
| `trustProxy` | `(address, distance) => boolean` | loopback only | Determine which proxy IPs are trusted |
| `getIp` | `(request, originalFn) => string` | `undefined` | Custom IP address resolver |

### ResponseConfig fields

| Field | Type | Default | Description |
|---|---|---|---|
| `etag` | `boolean` | `false` | Auto-generate `ETag` headers on `response.send()` |
| `jsonpCallbackName` | `string` | `'callback'` | Query parameter name for JSONP callback |
| `serializeJSON` | `(payload) => string` | `safeStringify` from `@poppinss/utils` | Custom JSON serializer for response bodies |
| `cookie` | `Partial<CookieOptions>` | see below | Default cookie attributes |
| `redirect.allowedHosts` | `string[]` | `[]` | Hosts permitted as redirect referrers (empty = own host only) |
| `redirect.forwardQueryString` | `boolean` | `false` | Forward current request's query string on all redirects by default |

### Cookie defaults

| Option | Default |
|---|---|
| `maxAge` | `'2h'` → normalised to seconds |
| `path` | `'/'` |
| `httpOnly` | `true` |
| `secure` | `true` |
| `sameSite` | `'lax'` |

`maxAge` accepts a human-readable string (e.g. `'2h'`, `'7d'`, `'30m'`) or a number in seconds. `defineConfig` normalises string values to seconds using `@poppinss/utils/string`.

### QSParserConfig

```ts
type QSParserConfig = {
  parse: {
    depth?: number              // default: 5
    parameterLimit?: number     // default: 1000
    allowSparse?: boolean       // default: false
    arrayLimit?: number         // default: 20
    comma?: boolean             // default: true
  }
  stringify: {
    encode?: boolean            // default: true
    encodeValuesOnly?: boolean  // default: false
    arrayFormat?: 'indices' | 'brackets' | 'repeat' | 'comma'  // default: 'indices'
    skipNulls?: boolean         // default: false
  }
}
```

These options are forwarded to `@poppinss/qs` (a wrapper around the `qs` package). `depth` controls how deeply nested objects are parsed. `parameterLimit` caps the number of top-level parameters. `arrayLimit` caps the array index that is treated as an array (higher indices are treated as object keys).

## Trust proxy normalisation

The `trustProxy` option can be provided in three forms and is normalised to a function:

| Input form | Result |
|---|---|
| `boolean` | `(_, __) => value` |
| `string` | `proxy-addr.compile(value)` (e.g. `'loopback'`, `'10.0.0.1'`) |
| `(address, distance) => boolean` | Used as-is |

The compiled function is used by `HttpRequest` to determine the client IP (via `proxy-addr`) and whether the `X-Forwarded-Proto` header should be trusted for `request.protocol()`.

## Configuration in the AdonisJS application

In a standard AdonisJS application, `defineConfig` is called in `config/app.ts` or a dedicated `config/http.ts` file and the resulting object is injected into the `Server` at boot time by the AdonisJS framework provider. The `Server` itself does not impose an opinionated file structure — `defineConfig` is a standalone utility that can be used in any Node.js project.
