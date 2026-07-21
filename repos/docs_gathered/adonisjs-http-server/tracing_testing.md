# Tracing and Testing

## Tracing channels

`@adonisjs/http-server` instruments its request lifecycle using Node.js `diagnostics_channel` tracing channels. These channels provide a zero-overhead observability hook for APM tools, custom loggers, and performance monitors.

### Package location

`src/tracing_channels.ts` — exported from the package root as `tracingChannels`.

### Available channels

```ts
import { tracingChannels } from '@adonisjs/http-server'

tracingChannels.httpRequest           // adonisjs.http.request
tracingChannels.httpMiddleware        // adonisjs.http.middleware
tracingChannels.httpExceptionHandler  // adonisjs.http.exception.handler
tracingChannels.httpRouteHandler      // adonisjs.http.route.handler
tracingChannels.httpResponseSerializer // adonisjs.http.response.serializer
```

All channels are created using `diagnostics_channel.tracingChannel`, which attaches `start`, `end`, `asyncStart`, `asyncEnd`, and `error` sub-channels to each logical operation.

### Channel payloads

| Channel | Payload type | When fired |
|---|---|---|
| `httpRequest` | `{ ctx: HttpContext }` | Around the entire `#handleRequest` call |
| `httpMiddleware` | `{ middleware: ParsedGlobalMiddleware | ParsedNamedMiddleware | MiddlewareFn }` | Around each middleware `handle` call |
| `httpExceptionHandler` | _(no typed payload)_ | Around `ExceptionHandler.handle` calls |
| `httpRouteHandler` | `{ route: RouteJSON }` | Around the final route handler |
| `httpResponseSerializer` | _(no typed payload)_ | Around non-stream / non-file response serialization in `HttpResponse` |

### Subscribing to channels

```ts
import diagnostics_channel from 'node:diagnostics_channel'

diagnostics_channel.subscribe('adonisjs.http.request:start', ({ ctx }) => {
  console.log('request started', ctx.request.url())
})

diagnostics_channel.subscribe('adonisjs.http.request:end', ({ ctx }) => {
  console.log('request ended', ctx.response.getStatus())
})
```

The channel system is purely passive — subscribers receive data but cannot modify control flow. Tracing overhead is near-zero when there are no subscribers because each `tracePromise` call checks `channel.hasSubscribers` before publishing.

---

## Test factories

The `factories` sub-path (`@adonisjs/http-server/factories`) provides lightweight factory classes for constructing test fixtures without running a full server. These are useful for unit tests that need isolated `HttpRequest`, `HttpResponse`, or `HttpContext` instances.

### Exported factories

```ts
import {
  RequestFactory,        // HttpRequestFactory
  ResponseFactory,       // HttpResponseFactory
  HttpContextFactory,
  RouterFactory,
  ServerFactory,
  QsParserFactory,
} from '@adonisjs/http-server/factories'
```

### HttpContextFactory

```ts
const ctx = new HttpContextFactory().create()
```

Creates an `HttpContext` with stub `IncomingMessage` and `ServerResponse` objects, a minimal encryption instance, and a no-op logger. The factory accepts optional overrides:

```ts
const ctx = new HttpContextFactory()
  .merge({ params: { id: '42' } })
  .create()
```

### RouterFactory

```ts
const router = new RouterFactory().create()
```

Returns a `Router` instance pre-configured with a minimal application stub and encryption.

### ServerFactory

```ts
const server = new ServerFactory().create()
await server.boot()
```

Returns a `Server` configured for testing. `ServerFactory` wires up the router, encryption, emitter, and logger automatically.

### QsParserFactory

```ts
const qs = new QsParserFactory().create()
```

Returns a `Qs` instance with default parse/stringify configuration.

---

## Test conventions

Tests in `@adonisjs/http-server` use the **Japa** test runner (`@japa/runner`). The test entry point is `bin/test.ts`, which registers plugins for assertions, type expectations, snapshot testing, and file-system helpers.

### Test runner setup

```ts
// bin/test.ts
configure({
  files: ['tests/**/*.spec.ts'],
  plugins: [assert(), expectTypeOf(), snapshot(), fileSystem()],
})
```

### Test file naming

Test files mirror the source layout:

| Source | Test |
|---|---|
| `src/request.ts` | `tests/request.spec.ts` |
| `src/router/main.ts` | `tests/router/router.spec.ts` |
| `src/cookies/parser.ts` | `tests/cookies/parser.spec.ts` |
| `src/client/url_builder.ts` | `tests/client/url_builder.spec.ts` |

Integration-level tests that require a live HTTP server are in `tests/server.spec.ts` and use `supertest` to make real HTTP requests against a listening server.

### Integration test pattern

```ts
import supertest from 'supertest'
import http from 'node:http'

const server = new ServerFactory().create()
await server.boot()
const httpServer = http.createServer(server.handle.bind(server))

// within test
await supertest(httpServer).get('/users/1').expect(200)
```

### Type-checking tests

`tests/router/types.spec.ts` and other `types.spec.ts` files use `@japa/expect-type` to make compile-time assertions about the TypeScript types of the public API without executing any runtime logic.

### Snapshot tests

Snapshot tests (using `@japa/snapshot`) capture serialised values for URL generation, route JSON output, and type generation results. Snapshots are stored alongside test files.

### Middleware pipeline testing

The `server.pipeline` API described in the Server documentation is designed specifically for testing middleware in isolation without needing a running server. The `HttpContextFactory` provides a compatible `ctx` instance for `pipeline.run(ctx)`.
