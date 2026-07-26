# Middleware

The middleware subsystem defines how cross-cutting concerns (authentication, CORS, body parsing, rate limiting, etc.) are layered around route handlers. It is built on top of `@poppinss/middleware` and comprises two distinct middleware scopes: global (server-level) and route-level (named or inline).

## Package locations

- `src/types/middleware.ts` — type definitions
- `src/define_middleware.ts` — `defineNamedMiddleware` helper
- `src/server/main.ts` — `Server.use()` for global middleware
- `src/server/factories/middleware_handler.ts` — execution adapter
- `src/router/executor.ts` — route-level middleware execution

## Middleware contract

Every class-based middleware must implement:

```ts
class ExampleMiddleware {
  async handle(ctx: HttpContext, next: NextFn, args?: any): Promise<void> {
    // pre-handler logic
    await next()
    // post-handler logic
  }
}
```

The `args` parameter carries the per-invocation arguments for named middleware. The `NextFn` type is re-exported from `@poppinss/middleware/types`.

## Global middleware

Global middleware runs on every incoming HTTP request, before route matching:

```ts
server.use([
  () => import('./middleware/cors.ts'),
  () => import('./middleware/body_parser.ts'),
  () => import('./middleware/auth.ts'),
])
```

`server.use` accepts an array of **lazy-import thunks**. Each thunk is a zero-argument function that returns a dynamic `import()` promise resolving to a module with a `default` export of the middleware class. Using lazy imports defers module loading until `server.boot()`.

During `boot()`, each thunk is processed by `moduleImporter(...).toHandleMethod()` from `@adonisjs/fold`, producing a `ParsedGlobalMiddleware` record:

```ts
type ParsedGlobalMiddleware = {
  name?: string
  reference: LazyImport<MiddlewareAsClass> | MiddlewareAsClass
  handle: (resolver: ContainerResolver<any>, ctx: HttpContext, next: NextFn, params?: any) => any
}
```

The `handle` field is the IoC-aware execution function — it resolves the middleware class from the container, instantiates it, and calls `instance.handle(ctx, next, params)`.

## Named middleware

Named middleware enables selective application to individual routes or groups with optional per-invocation arguments:

```ts
// Definition
const middleware = router.named({
  auth: () => import('./middleware/auth.ts'),
  throttle: () => import('./middleware/throttle.ts'),
})

// Usage on routes
router.get('/dashboard', handler).middleware([middleware.auth()])
router.get('/api', handler).middleware([middleware.throttle({ max: 100 })])
```

`router.named(collection)` delegates to `defineNamedMiddleware`, which converts each middleware entry into a factory function. When called (e.g. `middleware.auth()`), the factory returns a `ParsedNamedMiddleware` record containing the `args` value.

```ts
type ParsedNamedMiddleware = {
  name: string
  reference: LazyImport<MiddlewareAsClass> | MiddlewareAsClass
  handle: ParsedGlobalMiddleware['handle']
  args: any
}
```

TypeScript preserves the argument types from the middleware's `handle` method signature, so `middleware.auth(wrongArg)` is a compile-time error.

## Route-level inline middleware

Routes also accept inline function middleware without named registration:

```ts
router.get('/admin', handler).middleware([
  async (ctx, next) => {
    if (!ctx.request.header('x-admin-token')) {
      ctx.response.abort('Forbidden', 403)
    }
    await next()
  },
])
```

Inline functions are stored as `MiddlewareFn` (`(ctx, next) => any`) and are distinguishable from named middleware in the `StoreRouteMiddleware` union.

## Middleware execution order

For a given request the order is:

1. **Global middleware** — in registration order (applied by `Server.#handleRequest`)
2. **Route middleware** — in registration order (applied by `route.execute()`)
3. **Route handler** — the final handler set on the `@poppinss/middleware` runner

Within each scope, `await next()` chains the pipeline. Post-`next()` code runs in reverse registration order (innermost-first) as the call stack unwinds.

## Error propagation

Each middleware pipeline is configured with an `errorHandler`:

```ts
runner.errorHandler((error) => errorResponder(error, ctx))
```

Any uncaught error in a middleware or the route handler propagates to this handler, which invokes `ExceptionHandler.report` then `ExceptionHandler.handle`. Errors thrown in the error handler itself are caught by a `.catch` at the top of `#handleRequest` and handled by the built-in default error handler.

## Route executor middleware pipeline

The route-level pipeline is implemented in `src/router/executor.ts`. It mirrors the global pipeline structure but operates on `route.middleware` (a per-route `@poppinss/middleware` instance frozen at commit time). Named middleware `args` are passed as the third argument to `handle`. Inline function middleware receive only `(ctx, next)`.

## Testing middleware pipelines

```ts
const pipeline = server.pipeline([AuthMiddleware, CorsMiddleware])
await pipeline
  .finalHandler(() => ctx.response.send('ok'))
  .run(ctx)
```

`Server.pipeline` creates an isolated, non-production middleware stack for unit testing specific middleware combinations without running the full server.

## Middleware type metadata

For observability, `MiddlewareHandlerInfo` describes the kind of middleware at runtime:

```ts
type MiddlewareHandlerInfo =
  | { type: 'closure'; name: string }
  | { type: 'named'; name: string; args: any; method: string; moduleNameOrPath: string }
  | { type: 'global'; name?: string; method: string; moduleNameOrPath: string }
```

This metadata is attached to tracing channel events (`adonisjs.http.middleware`) and is available to APM subscribers.
