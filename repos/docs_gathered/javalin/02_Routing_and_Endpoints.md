# Javalin Routing and Endpoints Documentation

## HTTP Handler Types

Javalin provides three main handler types:

### 1. Before-Handlers (Middleware/Filters)
- Run before endpoint handlers or all requests
- Configured with: `config.routes.before()`
- Used for cross-cutting concerns
- Known as filters, interceptors, or middleware in other frameworks

### 2. Endpoint-Handlers
- Execute the actual route logic
- HTTP Verbs supported:
  - `get`, `post`, `put`, `patch`, `delete`
  - `head`, `options`, `trace`, `connect`
  - Custom methods (e.g., `PROPFIND` for WebDAV)

### 3. After-Handlers
- Run after endpoint handlers
- Configured with: `config.routes.after()`
- Used for post-processing and logging

### 4. Wrapper-Handlers
- Run "around" endpoint handlers
- `HandlerWrapper` functional interface receives an Endpoint and returns a new Handler
- Wraps the original handler for custom behavior

### 5. Exception-Handlers & Error-Handlers
- Configured in the config block
- Handle exceptions and error conditions

## Basic Route Definition

### Javalin 7 (Current)
Routes must now be defined in the config block during application creation:

```
var app = Javalin.create(config -> {
    config.routes(() -> {
        get("/hello", ctx -> ctx.result("Hello World"));
        post("/users", ctx -> ctx.json(createUser(ctx)));
        put("/users/{id}", ctx -> updateUser(ctx));
        delete("/users/{id}", ctx -> deleteUser(ctx));
    });
}).start();
```

**Critical Constraint**: Routes cannot be added after calling `.start()`.

## Path Parameters

Path variables are denoted with `{id}` syntax:

```
get("/users/{id}", ctx -> {
    String userId = ctx.pathParam("id");
    // handle request
});
```

**Accessing Parameters**:
- `ctx.pathParam("id")` - Get path parameter by name
- `ctx.pathParam(Integer.class)` - Get single path parameter as specific type

## Routing Organization

### API Builder Pattern
Group endpoints using `apiBuilder()` and `path()` methods:

```
config.routes(() -> {
    path("/api", () -> {
        path("/users", () -> {
            get(ctx -> {...});  // GET /api/users
            post(ctx -> {...}); // POST /api/users
        });
    });
});
```

This pattern:
- Avoids repeating path prefixes
- Improves code readability
- Enables modular endpoint organization
- Uses temporary static instance of Javalin

## Request Context

The `Context` object provides access to all request/response data:

### Request Data
- `ctx.pathParam()` - Path parameters
- `ctx.queryParam()` - Query string parameters
- `ctx.header()` - HTTP headers
- `ctx.body()` - Request body
- `ctx.method()` - HTTP method
- `ctx.path()` - Request path
- `ctx.matchedPath()` - Javalin route path (deprecated in v7, use `ctx.endpoint().path()`)

### Response Methods
- `ctx.result()` - Set response body
- `ctx.json()` - Send JSON response
- `ctx.html()` - Set HTML content
- `ctx.contentType()` - Set content type
- `ctx.status()` - Set HTTP status
- `ctx.header()` - Set response header
- `ctx.redirect()` - HTTP redirect

### Request Handling
- `ctx.future()` - Set CompletableFuture for async processing
- `ctx.future(CompletableFuture)` - For async request handling

## Handler Concurrency Model

### Message Ordering
- WebSocket operates over TCP
- Messages arrive in the order sent by client
- Javalin handles messages from a given WebSocket connection sequentially
- Order messages are handled matches order client sent them

### Parallel Processing
- Different connections handled in parallel on multiple threads
- WebSocket event handlers must be thread-safe
- Different HTTP requests run on different threads

## Input Validation

Javalin provides built-in validator API:

### Query Parameters
```
ctx.queryParamAsClass("age", Integer.class).required().get()
```

### Form Data
```
ctx.formParamAsClass("email", String.class).required().get()
```

### Request Body
```
ctx.bodyAsClass(User.class)
```

### Validator Updates (Javalin 7)
- Validator methods now return `Validator<T?>` by default (nullable)
- Must call `.required()` before `.get()` to get non-nullable validator
- Example: `ctx.queryParamAsClass("age", Integer.class).required().get()`

## Default HTTP Response Classes

Javalin provides standard responses:
- 404 - Not Found
- 401 - Unauthorized
- 403 - Forbidden
- And other standard HTTP status codes

## Error and Exception Handling

### Exception Handlers
```
config.routes.exception(CustomException.class, (e, ctx) -> {
    ctx.status(400).json(Map.of("error", e.getMessage()));
});
```

### Error Handlers
```
config.routes.error(404, ctx -> {
    ctx.json(Map.of("error", "Resource not found"));
});
```

**Exception Precedence**: More specific exception mappers take precedence over general ones.

## HTTP Compression and ETags

Configuration available for:
- **ETags**: Automatic generation and validation
- **Compression**: Gzip compression settings
- **Timeouts**: Request and response timeouts

## Custom HTTP Methods

Support for non-standard HTTP methods:
- WebDAV methods (e.g., `PROPFIND`)
- Custom protocol implementations

## Static Files and SPA Routing

### Static File Configuration
```
config.staticFiles.add(staticFiles -> {
    staticFiles.hostedPath = "/assets";           // Change host path
    staticFiles.directory = "/public";            // File directory
    staticFiles.location = Location.CLASSPATH;    // Jar or external
    staticFiles.precompress = true;               // Cache compressed
    staticFiles.aliasCheck = true;                // Enable symlinks
    staticFiles.headers = Map.of(...);            // Custom headers
});
```

### Single Page Application (SPA) Mode
```
config.spaRoot.addFile("/root", "/path/to/index.html");
config.spaRoot.addFile("/root", "/path/to/index.html", Location.EXTERNAL);
```

Features:
- Runs after endpoint matching
- Runs after static file handling
- Acts as fancy 404 mapper
- Converts 404s into specified page
- Allows client-side routing to take over
- Can define multiple SPA handlers with different root paths

## Access Management

Javalin provides role-based access control:
- Configure via `config.accessManager()`
- Specify user roles and permission levels
- Restrict endpoints to specific roles

## Context API Changes (v6 to v7)

- `ctx.matchedPath()` → `ctx.endpoint().path()`
- `ctx.unsafeConfig()` → `app.unsafe` returns `JavalinState`

## Event Lifecycle

Handlers execute in order:
1. Before-handlers (all matching)
2. Endpoint-handler
3. After-handlers (all matching)

Exception handlers can interrupt this flow if exceptions occur.
