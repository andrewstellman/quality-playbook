# Chi Router - Middleware System

## Middleware Fundamentals

Chi's middleware system is built entirely on Go's standard `net/http` middleware pattern. A middleware is simply a function that:

1. Accepts an `http.Handler` as parameter
2. Returns an `http.Handler`
3. Can execute code before and after calling the wrapped handler

```go
// Standard middleware signature
func MyMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        // Code before handler
        fmt.Println("Before handler")

        // Call the next handler
        next.ServeHTTP(w, r)

        // Code after handler
        fmt.Println("After handler")
    })
}
```

## Applying Middleware

### Global Middleware (Use)

Apply middleware to all routes:

```go
r := chi.NewRouter()
r.Use(middleware.Logger)
r.Use(middleware.Recoverer)
r.Use(middleware.RequestID)

// All routes now have this middleware stack
r.Get("/users", handler)
```

### Route-Specific Middleware (With)

Apply middleware to individual routes:

```go
r.With(middleware.BasicAuth).Get("/admin", adminHandler)
r.With(paginate).Get("/items", listItems)
```

### Group Middleware (Group)

Create a fresh middleware stack for a group of routes:

```go
r.Group(func(r chi.Router) {
    r.Use(middleware.BasicAuth)
    r.Get("/admin", adminPanel)
    r.Get("/settings", settings)
})

// These routes don't have BasicAuth
r.Get("/public", publicHandler)
```

## Built-in Middleware

Chi includes a comprehensive set of standard middleware:

| Middleware | Purpose |
|-----------|---------|
| `Logger` | Request/response logging |
| `Recoverer` | Panic recovery |
| `RequestID` | Inject request ID into context |
| `RealIP` | Extract real IP from proxy headers |
| `Compress` | Gzip response compression |
| `Timeout` | Set request deadline |
| `NoCache` | Prevent client caching |
| `StripSlashes` | Remove trailing slashes |
| `BasicAuth` | HTTP basic authentication |
| `AllowContentType` | Whitelist accepted Content-Types |
| `AllowContentEncoding` | Whitelist Content-Encoding headers |
| `Heartbeat` | Health check endpoint |
| `Throttle` | Concurrent request limits |
| `CleanPath` | Clean up request path |
| `URLFormat` | Format query parameter handling |
| `SetHeader` | Add response headers |

## Middleware Stack Example

A typical middleware stack:

```go
r := chi.NewRouter()

// Logging and monitoring
r.Use(middleware.RequestID)
r.Use(middleware.RealIP)
r.Use(middleware.Logger)

// Safety
r.Use(middleware.Recoverer)

// Performance
r.Use(middleware.Compress)

// Limits
r.Use(middleware.Timeout(60 * time.Second))
r.Use(middleware.Throttle(100))

// Business logic
r.Use(authMiddleware)

r.Get("/users", listUsers)
```

## Custom Middleware with Context Values

Most common use of middleware is to add request-scoped values:

```go
func AuthMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        // Extract token from headers
        token := r.Header.Get("Authorization")

        // Validate token and get user
        user := validateToken(token)

        // Add to context
        ctx := context.WithValue(r.Context(), "user", user)

        // Call next handler with updated context
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}

// In handler
func getUser(w http.ResponseWriter, r *http.Request) {
    user := r.Context().Value("user").(User)
    // Use user...
}
```

## Middleware Composition

Chain multiple middleware for reuse:

```go
// Create middleware combinations
adminMiddleware := chi.Chain(
    middleware.Logger,
    middleware.BasicAuth,
    middleware.Recoverer,
)

// Apply to routes
r.With(adminMiddleware...).Get("/admin", adminHandler)
```

## Important Considerations

1. **Order Matters**: Logger should come before Recoverer if both are used, so errors are logged before recovery
2. **Context Safety**: Use custom types for context keys to avoid collisions
3. **Lightweight Values**: Store only lightweight, request-scoped data in context
4. **Standard Library Compatibility**: Any stdlib-compatible middleware works with chi
