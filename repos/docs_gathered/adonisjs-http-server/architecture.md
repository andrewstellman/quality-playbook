# Architecture and Design Philosophy

`@adonisjs/http-server` is the HTTP request-handling layer of the AdonisJS framework. It provides a complete, standalone implementation of routing, middleware pipelines, request/response abstractions, cookie handling, URL generation, and error handling. The package is designed to be integrated via the AdonisJS IoC container (`@adonisjs/fold`) and application host (`@adonisjs/application`), but its core classes can also be composed independently in any Node.js project.

## Design philosophy

### Explicit boot sequence

The `Server` follows a two-phase lifecycle: **registration** (configuration, route definition, middleware registration) and **serving** (triggered by `server.boot()`). After boot, the middleware stack and route tree are frozen and immutable. This prevents accidental mutation during request handling and enables a single code path — there is no "first-request" lazy initialisation.

### Dependency injection via IoC container

All cross-cutting services (encryption, logging, events, application) are injected into the `Server` constructor. Middleware and error-handler classes are resolved through the AdonisJS IoC container (`@adonisjs/fold`) at boot time using lazy imports. This separation keeps the server testable, mockable, and free of global state.

### Macroable extension points

`HttpRequest`, `HttpResponse`, `HttpContext`, `Redirect`, `RouteGroup`, `RouteResource`, and `ExceptionHandler` all extend `@poppinss/macroable`. This allows the AdonisJS ecosystem (auth, sessions, views, bouncer) to add typed properties and methods to these objects at the application level without subclassing or monkey-patching. The extension mechanism is process-level, meaning macros defined once are available for every request.

### Lazy initialisation within requests

Repeated per-request operations that may not always be needed are initialised on first access:
- Cookie parsing (`CookieParser` is created when the first cookie method is called)
- Content negotiation (`accepts` instance is created when negotiation is first invoked)
- Route type lookup in URL builder (routes map is loaded once on first URL generation call)

### Tracing without coupling

All observable operations (requests, middleware, route handlers, error handlers, response serialization) are instrumented via Node.js `diagnostics_channel.tracingChannel`. Subscribers receive rich contextual data but cannot affect control flow. The overhead is near zero when no subscribers are registered, because `tracePromise` checks `hasSubscribers` before publishing.

## Package structure

```
src/
  server/          — Server class + request-handling factories
  router/          — Router, Route, RouteGroup, RouteResource, BriskRoute, RoutesStore, matchers
  http_context/    — HttpContext class + AsyncLocalStorage singleton
  cookies/         — CookieClient, CookieParser, CookieSerializer + three driver modules
  client/          — URL builder factory (also usable in edge/template contexts)
  types/           — TypeScript type definitions for all subsystems
  request.ts       — HttpRequest
  response.ts      — HttpResponse
  redirect.ts      — Redirect
  qs.ts            — Qs (query string parser wrapper)
  errors.ts        — Built-in HTTP error types
  exception_handler.ts — ExceptionHandler base class
  define_config.ts — defineConfig utility
  define_middleware.ts — defineNamedMiddleware helper
  tracing_channels.ts  — diagnostics_channel exports
  helpers.ts       — URL encoding, cookie serialization, signed URL helpers
  utils.ts         — safeDecodeURI, trustProxy, parseRange
  debug.ts         — debug logger namespace ('adonisjs:http')
factories/         — Test factory classes
tests/             — Japa test files mirroring src layout
benchmarks/        — Autocannon benchmarks comparing against Fastify
```

## Public API surface

The package exports from five sub-paths:

| Sub-path | Contents |
|---|---|
| `.` (root) | `Server`, `Router`, `Route`, `RouteGroup`, `RouteResource`, `BriskRoute`, `HttpRequest`, `HttpResponse`, `HttpContext`, `CookieClient`, `CookieParser`, `CookieSerializer`, `Redirect`, `ResponseStatus`, `ExceptionHandler`, `Qs`, `defineConfig`, `errors`, `tracingChannels` |
| `./helpers` | `getPreviousUrl`, `encodeUrl`, cookie/URL helper functions |
| `./types` | All TypeScript type exports |
| `./client/url_builder` | `createUrlBuilder`, `createURL`, `findRoute`, client URL types |
| `./factories` | Test factory classes |

## Data and control flow for a request

```
Node.js http.Server
  │
  └─► Server.handle(req, res)
        │
        ├─ create HttpRequest (parse URL + query string)
        ├─ create ContainerResolver (per-request IoC scope)
        ├─ create HttpResponse
        ├─ create HttpContext (child logger, circular refs)
        │
        └─► [AsyncLocalStorage.run if ALS enabled]
              │
              └─► Server.#handleRequest(ctx, resolver)
                    │
                    ├─► GlobalMiddlewareStack.runner()
                    │     ├─ middleware 1 (pre → next → post)
                    │     ├─ middleware 2 (pre → next → post)
                    │     └─ [final handler: routeFinder]
                    │           │
                    │           ├─ router.match(url, method, hostname)
                    │           ├─ populate ctx.params, ctx.route, ctx.routeKey
                    │           └─► route.execute()
                    │                 ├─► RouteMiddlewareStack.runner()
                    │                 │     ├─ named/inline middleware
                    │                 │     └─ [final: route handler]
                    │                 │           └─ useReturnValue → response.send
                    │                 └─ [errors → errorResponder]
                    │
                    ├─ [errors → ExceptionHandler.report + handle]
                    └─ [finally: writeResponse flushes to socket]
```

## Peer dependency model

The package does not bundle its framework peers; they are declared as `peerDependencies`:

- `@adonisjs/application` — IoC container host
- `@adonisjs/fold` — IoC container and module importer
- `@adonisjs/events` — event emitter for `http:request_completed`
- `@adonisjs/logger` — structured logging
- `@boringnode/encryption` — cookie signing and encryption, signed URL signing
- `youch` (optional) — rich HTML/JSON error formatting in debug mode

Runtime dependencies that are bundled include `cookie-es`, `etag`, `mime-types`, `on-finished`, `proxy-addr`, `vary`, `fresh`, `content-disposition`, and `@poppinss/macroable`, `@poppinss/middleware`, `@poppinss/matchit`, `@poppinss/qs`, `@poppinss/utils`.

## Build and packaging

The package is built with `tsdown` (an ESM bundler based on Rollup) and `tsc --emitDeclarationOnly`:

```json
{
  "tsdown": {
    "entry": ["./index.ts", "./src/helpers.ts", "./src/types/main.ts",
               "./src/client/url_builder.ts", "./factories/main.ts"],
    "format": "esm",
    "outDir": "./build",
    "target": "esnext"
  }
}
```

The package is published as pure ESM (`"type": "module"`). The `engines` field requires Node.js 24+, which ensures native `crypto.randomUUID`, `AsyncLocalStorage`, and `diagnostics_channel.tracingChannel` are available without polyfills.

Only the `build` directory (minus `build/bin` and `build/tests`) is published to npm. Declaration files (`.d.ts`) are emitted by a separate `tsc --emitDeclarationOnly` pass so that type consumers get accurate IDE integration.
