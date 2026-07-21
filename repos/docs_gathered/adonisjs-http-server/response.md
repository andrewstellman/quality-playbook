# Response

`HttpResponse` wraps Node.js `ServerResponse` and provides a fluent, feature-rich API for constructing HTTP responses. It is exported from the package root and accessible as `ctx.response` in handlers and middleware.

## Package location

`src/response.ts` — extends `@poppinss/macroable` (`Macroable`).

## Constructor

```ts
new HttpResponse(
  request: IncomingMessage,
  response: ServerResponse,
  encryption: Encryption,
  config: ResponseConfig,
  router: Router,
  qsParser: Qs
)
```

The native `ServerResponse` is accessible as `response.response`. The `Router` reference is used only for URL generation in redirects.

## Response body methods

```ts
response.send(body)             // auto-detect type and serialize
response.json(body)             // serialize as JSON
response.jsonp(body)            // JSONP response
response.stream(stream, errorCallback?)
response.download(filePath, generateEtag?)
response.attachment(filePath, name?, disposition?, generateEtag?)
```

`send` inspects the type of `body` and selects the appropriate serialization:
- `string` → `text/html; charset=utf-8` (unless another content-type is already set)
- `Buffer` → `application/octet-stream; charset=utf-8`
- `object`, `number`, `boolean`, `bigint` → `application/json; charset=utf-8` via `config.serializeJSON`
- `null` / `undefined` → empty body with the existing status

`stream` pipes a `Readable` or `ReadableStream` to the underlying socket and handles cleanup on request abort.

`download` and `attachment` send a file from the filesystem, setting `Content-Disposition`, `Content-Length`, `Last-Modified`, and optionally an `ETag`. They both check `fresh()` to support conditional GET / HEAD caching.

## Status code

```ts
response.status(200)          // set explicit status
response.safeStatus(200)      // set status only if not already set
response.getStatus()          // read current status
response.hasExplicitStatus   // boolean
```

## Headers

```ts
response.header(key, value)       // overwrite
response.append(key, value)       // append to existing
response.removeHeader(key)        // remove
response.getHeader(key)           // read
response.vary(field)              // append to Vary
response.type(mimeOrExtension)    // set Content-Type
response.location(url)            // set Location
response.etag(body, encoding?)    // compute and set ETag
```

## Cookies

Cookie serialization is handled through `CookieSerializer`, which in turn delegates to `CookieClient`.

```ts
response.cookie(key, value, options?)           // plain (base64-encoded)
response.encryptedCookie(key, value, options?)  // encrypted
response.signedCookie(key, value, options?)     // signed
response.clearCookie(key, options?)             // clear cookie
```

Default cookie options come from `config.cookie`:

| Option | Default |
|---|---|
| `maxAge` | `'2h'` (normalised to seconds) |
| `path` | `'/'` |
| `httpOnly` | `true` |
| `secure` | `true` |
| `sameSite` | `'lax'` |

Per-call options are merged on top of defaults. `maxAge` may be expressed as a human-readable string (e.g. `'7d'`) — the framework normalises it to seconds using `@poppinss/utils/string`.

## Redirects

```ts
response.redirect('/login')                        // immediate redirect
response.redirect().toPath('/login')              // fluent form
response.redirect().toRoute('auth.login')         // redirect to named route
response.redirect().back('/fallback')             // redirect to Referer
response.redirect().status(301).toPath('/new')    // with custom status
response.redirect().withQs({ page: 1 }).toPath('/') // append query string
```

`redirect()` with no arguments returns a `Redirect` instance. `redirect(url)` is a shorthand for `.redirect().toPath(url)`.

## Abort helpers

```ts
response.abort(body, status?)      // throw E_HTTP_REQUEST_ABORTED
response.abortIf(condition, body, status?)
response.abortUnless(condition, body, status?)
```

`abort` throws `E_HTTP_REQUEST_ABORTED`, which self-handles by sending `status` and `body` without reaching the exception handler's rendering logic.

## Response writing lifecycle

`HttpResponse` does not write to the socket immediately. All body, header, and cookie calls accumulate into internal state. The `writeResponse` factory (`src/server/factories/write_response.ts`) flushes this state after the middleware pipeline settles. This deferred approach allows middleware to modify the response after a route handler returns.

Return values from route handlers are intercepted by `useReturnValue` (`src/router/factories/use_return_value.ts`): if the handler returns a non-`undefined` value and the response body has not yet been committed, `response.send(returnValue)` is called automatically.

## JSONP

```ts
response.jsonp({ hello: 'world' })
```

Wraps the JSON body in a call to the `jsonpCallbackName` query parameter (default `callback`).

## ETag and caching

When `config.etag` is `true`, `send` automatically computes and sets an `ETag` header for string and buffer bodies. The `download` method always computes the `ETag` unless the second parameter is `false`.

## Response configuration

Key fields of `ResponseConfig`:

| Field | Type | Default | Description |
|---|---|---|---|
| `etag` | `boolean` | `false` | Auto-generate ETag on `send` |
| `jsonpCallbackName` | `string` | `'callback'` | Query param name for JSONP |
| `serializeJSON` | `(payload) => string` | `safeStringify` | Custom JSON serializer |
| `cookie` | `Partial<CookieOptions>` | see above | Default cookie attributes |
| `redirect.allowedHosts` | `string[]` | `[]` | Hosts allowed as redirect referrers |
| `redirect.forwardQueryString` | `boolean` | `false` | Forward query string on redirects |

## Macroable extension

Like `HttpRequest`, `HttpResponse` extends `Macroable`:

```ts
HttpResponse.macro('flash', function (this: HttpResponse, messages) {
  this.cookie('_flash', messages)
})
```
