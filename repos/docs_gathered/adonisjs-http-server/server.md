# Server

The `Server` class is the top-level entry point of `@adonisjs/http-server`. It ties together routing, middleware, error handling, request/response construction, and Node.js HTTP integration into a single coherent lifecycle.

## Package location

`src/server/main.ts` — exported from the package root as `Server`.

## Constructor signature

```ts
new Server(
  app: Application<any>,
  encryption: Encryption,
  emitter: EmitterLike<HttpServerEvents>,
  logger: Logger,
  config: ServerConfig
)
```

The constructor receives five peer-injected dependencies:

- `app` — the AdonisJS IoC container host; used to resolve middleware and error-handler classes and to create per-request container resolvers.
- `encryption` — a `@boringnode/encryption` instance; forwarded to `HttpRequest`, `HttpResponse`, and the `Router` for signed-URL and cookie operations.
- `emitter` — an `@adonisjs/events` emitter; used to emit `http:request_completed` events when listeners are registered.
- `logger` — a `@adonisjs/logger` instance; a child logger tagged with `request_id` is attached to every `HttpContext`.
- `config` — a fully-resolved `ServerConfig` produced by `defineConfig`.

During construction the server creates a `Qs` parser, a `Router`, and optionally initialises Node.js `AsyncLocalStorage` for request-context propagation.

## Boot sequence

`Server.boot()` must be called before the server handles any requests. It is idempotent — subsequent calls are no-ops. Boot performs three ordered steps:

1. **Compile middleware** — freezes the accumulated global middleware list into an immutable `@poppinss/middleware` stack.
2. **Commit routes** — calls `router.commit()`, locking route definitions into the `RoutesStore`.
3. **Resolve error handler** — if a custom error handler was registered via `server.errorHandler(...)`, its module is dynamically imported and instantiated through the IoC container.

## Request lifecycle

The public method `server.handle(req, res)` is the Node.js `http.RequestListener` compatible entry point. For each request it:

1. Constructs an `HttpRequest` (which parses the URL and query string); a malformed URI causes `config.onBadUrl` to be invoked and `handle` returns immediately.
2. Creates a per-request IoC `ContainerResolver`.
3. Constructs an `HttpResponse` and an `HttpContext` (with a child logger).
4. Optionally registers an `on-finished` hook to emit `http:request_completed` when the response closes.
5. Runs `#handleRequest(ctx, resolver)`, wrapping it in `AsyncLocalStorage.run` when that feature is enabled.
6. `#handleRequest` runs the frozen global middleware stack via `@poppinss/middleware`. The `routeFinder` factory is set as the **final handler** — it performs route matching and executes the matched route. All errors propagate to `#requestErrorResponder`, which delegates to the resolved error handler.
7. After the pipeline resolves or rejects, `writeResponse` is invoked in `.finally()` to flush the response to the socket.

## Middleware registration

```ts
server.use([
  () => import('./middleware/cors.ts'),
  () => import('./middleware/body_parser.ts'),
])
```

`use` accepts an array of lazy-import thunks returning middleware classes. Middleware is appended to an internal list until `boot()` is called; after boot the list is frozen and further calls have no effect.

## Error handler registration

```ts
server.errorHandler(() => import('./exception_handler.ts'))
```

The lazy import is resolved during `boot()`. The resolved class must implement `{ handle(error, ctx), report(error, ctx) }`. If no custom handler is registered, a built-in fallback responds with `500 Internal server error`.

## Node.js server configuration

```ts
server.setNodeServer(httpServer)
```

Applies `config.timeout`, `config.keepAliveTimeout`, `config.headersTimeout`, and `config.requestTimeout` to the native Node.js `http.Server` or `https.Server` instance.

## Testing pipeline

```ts
const pipeline = server.pipeline([AuthMiddleware, ThrottleMiddleware])
await pipeline.finalHandler(handler).run(ctx)
```

`pipeline` creates an isolated middleware stack without touching the server's production stack. Useful for unit-testing individual middleware chains.

## Inspection accessors

| Method | Return type | Description |
|---|---|---|
| `booted` | `boolean` | Whether `boot()` has completed |
| `usingAsyncLocalStorage` | `boolean` | Whether ALS is enabled |
| `getRouter()` | `Router` | The internal router instance |
| `getNodeServer()` | `HttpServer | HttpsServer | undefined` | The native server |
| `getMiddlewareList()` | `ParsedGlobalMiddleware[]` | Current middleware list |
| `createRequest(req, res)` | `HttpRequest` | Construct a request manually |
| `createResponse(req, res)` | `HttpResponse` | Construct a response manually |
| `createHttpContext(req, res, resolver)` | `HttpContext` | Construct context manually |

## Diagnostic tracing

Every request and its exception handling are instrumented via Node.js `diagnostics_channel` tracing channels (`adonisjs.http.request` and `adonisjs.http.exception.handler`). External APM tools can subscribe to these channels without modifying application code.

## Events

`Server` emits one event when listeners are registered:

```ts
type HttpServerEvents = {
  'http:request_completed': { ctx: HttpContext; duration: [number, number] }
}
```

The `duration` field is a `process.hrtime()` tuple.
