# Exception Handling

Error handling in `@adonisjs/http-server` follows a structured, two-phase pattern: **report** (logging / external notification) and **handle** (convert the error into an HTTP response). The base class `ExceptionHandler` and the built-in error types in `src/errors.ts` together define the full error-handling surface.

## Package locations

| File | Role |
|---|---|
| `src/exception_handler.ts` | `ExceptionHandler` base class |
| `src/errors.ts` | Built-in HTTP error constructors |
| `src/server/main.ts` | Wires the error handler into the pipeline |

Both `ExceptionHandler` and the `errors` namespace are exported from the package root.

## Built-in error types

### E_ROUTE_NOT_FOUND

Thrown by `routeFinder` when no registered route matches the incoming method and URL. Produces a `404` HTTP status.

```ts
export const E_ROUTE_NOT_FOUND = createError<[method: string, url: string]>(
  'Cannot %s:%s',
  'E_ROUTE_NOT_FOUND',
  404
)
```

### E_CANNOT_LOOKUP_ROUTE

Thrown by the URL builder when a route identifier cannot be resolved in the route registry. Produces a `500` status.

```ts
export const E_CANNOT_LOOKUP_ROUTE = createError<[routeIdentifier: string]>(
  'Cannot lookup route "%s"',
  'E_CANNOT_LOOKUP_ROUTE',
  500
)
```

### E_HTTP_EXCEPTION

A general-purpose HTTP exception for converting arbitrary values into structured HTTP responses:

```ts
// Static factory
E_HTTP_EXCEPTION.invoke(body: any, status: number, code?: string): HttpException
```

`invoke` normalises `body`:
- `null` / `undefined` → body becomes `'Internal server error'`
- `object` → `error.body = body`, `error.message = body.message || 'HTTP Exception'`
- other → `error.body = body`, `error.message = body`

### E_HTTP_REQUEST_ABORTED

Extends `E_HTTP_EXCEPTION` and adds a self-handling `handle` method that writes the body and status directly to the response. This is the error thrown by `response.abort(...)`.

```ts
class AbortException extends E_HTTP_EXCEPTION {
  handle(error: AbortException, ctx: HttpContext) {
    ctx.response.status(error.status).send(error.body)
  }
}
```

## ExceptionHandler base class

Extend `ExceptionHandler` to create the application's central error handler:

```ts
export default class HttpExceptionHandler extends ExceptionHandler {
  protected debug = app.inDev
  protected renderStatusPages = app.inProduction

  protected statusPages: Record<StatusPageRange, StatusPageRenderer> = {
    '404': (error, ctx) => ctx.view.render('errors/not_found'),
    '500..599': (error, ctx) => ctx.view.render('errors/server_error'),
  }

  protected ignoreExceptions = [...super.ignoreExceptions, MyCustomError]
}
```

The class extends `Macroable`, enabling further extension via macros.

### Configuration properties

| Property | Type | Default | Description |
|---|---|---|---|
| `debug` | `boolean` | `true` in non-production | Include stack traces in error responses |
| `renderStatusPages` | `boolean` | `true` in production | Use custom status page renderers |
| `statusPages` | `Record<StatusPageRange, StatusPageRenderer>` | `{}` | Page renderers by status code range |
| `reportErrors` | `boolean` | `true` | Whether to log / report errors |
| `ignoreExceptions` | `any[]` | `[E_HTTP_EXCEPTION, E_ROUTE_NOT_FOUND, E_CANNOT_LOOKUP_ROUTE, E_HTTP_REQUEST_ABORTED]` | Skip reporting for these exception types |
| `ignoreStatuses` | `number[]` | `[400, 422, 401]` | Skip reporting for these status codes |
| `ignoreCodes` | `string[]` | `[]` | Skip reporting for these error codes |

`StatusPageRange` is expressed as:
- A single status code: `'404'` or `404`
- A range using `..`: `'400..499'`

Ranges are expanded into a per-code lookup map at first use.

### Report phase

```ts
async report(error: unknown, ctx: HttpContext): Promise<void>
```

1. Normalises the error with `toHttpError`.
2. Calls `shouldReport(error)` — returns `false` if the error matches any ignore list.
3. If the error has its own `report` method, delegates to it.
4. Otherwise logs via `ctx.logger` at an appropriate level:
   - `status >= 500` → `'error'`
   - `status >= 400` → `'warn'`
   - otherwise → `'info'`

### Handle phase

```ts
async handle(error: unknown, ctx: HttpContext): Promise<void>
```

1. Normalises with `toHttpError`.
2. If the error has its own `handle` method, delegates to it (self-handling exceptions).
3. If `error.code === 'E_VALIDATION_ERROR'` and `error.messages` exists, delegates to `renderValidationError`.
4. Otherwise delegates to `renderError`.

### Content-negotiated rendering

`renderError` inspects `request.accepts(['html', 'application/vnd.api+json', 'json'])`:

| Accept header | Method called |
|---|---|
| `html` (default) | `renderErrorAsHTML` |
| `application/vnd.api+json` | `renderErrorAsJSONAPI` |
| `json` | `renderErrorAsJSON` |

Validation errors follow the same content negotiation via `renderValidationError`.

In `debug` mode, HTML and JSON responses include full stack trace output from the `youch` package (an optional peer dependency). In production mode, HTML errors check `statusPages` first; if a renderer is configured for the status code, it is invoked.

### Error normalization

```ts
protected toHttpError(error: unknown): HttpError
```

Ensures any thrown value (including non-`Error` objects and strings) is converted to a `HttpError` object with at minimum `message` and `status` fields.

```ts
type HttpError = {
  message: string
  status: number
  code?: string
  stack?: string
  cause?: any
  messages?: any   // validation messages
  errors?: any     // structured field errors
  handle?: (...args: any[]) => any
  report?: (...args: any[]) => any
}
```

## Pipeline integration

The server registers `#requestErrorResponder` as the error handler on the `@poppinss/middleware` runner:

```ts
runner.errorHandler((error) => this.#requestErrorResponder(error, ctx))
```

`#requestErrorResponder` calls `resolvedErrorHandler.report(error, ctx)` then `resolvedErrorHandler.handle(error, ctx)`, wrapped in the `adonisjs.http.exception.handler` tracing channel. If the error handler itself throws, the built-in default handler catches it with a `fatal` log and sends a plain 500 response.
