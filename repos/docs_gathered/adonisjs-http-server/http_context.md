# HTTP Context

`HttpContext` is the per-request container that aggregates the request, response, logger, route information, and IoC resolver into a single object that flows through the middleware and handler pipeline. It is exported from the package root and accessible as the `ctx` argument in every middleware and route handler.

## Package locations

- `src/http_context/main.ts` — `HttpContext` class
- `src/http_context/local_storage.ts` — `asyncLocalStorage` singleton

## Class shape

```ts
class HttpContext extends Macroable {
  // Instance properties set by Server and routeFinder
  request: HttpRequest
  response: HttpResponse
  logger: Logger
  containerResolver: ContainerResolver<any>
  route?: RouteJSON
  routeKey?: string
  params: Record<string, any>
  subdomains: Record<string, any>

  // Static methods for ALS access
  static get usingAsyncLocalStorage: boolean
  static get(): HttpContext | null
  static getOrFail(): HttpContext
  static runOutsideContext<T>(callback: (...args: any[]) => T, ...args: any[]): T
}
```

`HttpContext` extends `Macroable`, making it extensible at runtime for application-level additions (e.g., `ctx.auth`, `ctx.bouncer`, `ctx.session`).

## Construction

`Server.createHttpContext(request, response, resolver)` constructs an `HttpContext`. The constructor creates a circular reference: `request.ctx = this` and `response.ctx = this`. This allows request or response macros that need other context properties (such as the logger) to access them via `this.ctx`.

```ts
new HttpContext(
  request: HttpRequest,
  response: HttpResponse,
  logger: Logger,              // child logger tagged with request_id
  containerResolver: ContainerResolver<any>
)
```

## Route information

Until the middleware pipeline reaches the `routeFinder` final handler, `ctx.route` and `ctx.routeKey` are `undefined`. After route matching succeeds, `routeFinder` populates:

```ts
ctx.params      // { id: '42', ... }  — dynamic URL parameters
ctx.subdomains  // { subdomain: 'api' } — domain tokens
ctx.route       // RouteJSON — the matched route descriptor
ctx.routeKey    // string — unique route identifier
```

Global middleware therefore executes before `ctx.route` is available. Route-level middleware and handlers always have access to the full context.

## Async Local Storage (ALS)

When `useAsyncLocalStorage: true` in config, the `HttpContext` is stored in a Node.js `AsyncLocalStorage` instance for the duration of the request. This allows any code running within the request's async context to retrieve the current context without explicit parameter threading.

```ts
// Enable via config
defineConfig({ useAsyncLocalStorage: true })

// Retrieve anywhere within the async call stack
const ctx = HttpContext.get()     // returns null if not in a request
const ctx = HttpContext.getOrFail() // throws RuntimeException if not in a request
```

`HttpContext.get()` and `HttpContext.getOrFail()` both return `null` / throw when called outside a request context or when ALS is disabled.

`HttpContext.runOutsideContext(callback, ...args)` exits the ALS scope before executing `callback`, making `HttpContext.get()` return `null` within that callback. This is useful for background tasks spawned from request handlers that should not inherit the request context.

## ALS implementation

`asyncLocalStorage` in `local_storage.ts` is a module-level singleton object:

```ts
const asyncLocalStorage: {
  isEnabled: boolean
  storage: null | AsyncLocalStorage<HttpContext>
  create(): AsyncLocalStorage<HttpContext>
  destroy(): void
}
```

`Server` calls `asyncLocalStorage.create()` or `asyncLocalStorage.destroy()` during its constructor based on `config.useAsyncLocalStorage`. This is a process-level operation — it does not change between requests.

When ALS is enabled, `Server.handle` wraps `#handleRequest` in `asyncLocalStorage.storage!.run(ctx, ...)`, so every `await` downstream inherits the context.

## Container resolver

`ctx.containerResolver` is a per-request `ContainerResolver<any>` from `@adonisjs/fold`. Middleware and handlers receive it to resolve dependencies:

```ts
const service = await ctx.containerResolver.make(MyService)
```

The resolver is scoped to the request — values resolved within a request live only for that request's lifecycle.

## Macroable extension

Application packages typically add properties to `HttpContext` via macros. The AdonisJS framework itself uses this pattern for auth, sessions, views, and bouncer:

```ts
HttpContext.macro('auth', function (this: HttpContext) {
  return new AuthManager(this)
})

HttpContext.getter('session', function (this: HttpContext) {
  return new Session(this.request, this.response)
}, true /* cached getter */)
```

Macros are defined once at application startup and become available on every `HttpContext` instance.

## Inspect helper

```ts
ctx.inspect()
```

Returns a Node.js `util.inspect` string showing top-level context properties (depth 1), useful for debugging.

## TypeScript declaration merging

Because `HttpContext` is extensible, the package exports its type so application code can augment it:

```ts
// In app/types.ts
declare module '@adonisjs/http-server' {
  interface HttpContext {
    auth: AuthManager
    session: SessionManager
  }
}
```

This pattern keeps IDE autocompletion working for dynamically added properties.
