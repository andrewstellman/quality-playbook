# Chi Router - Built-in Middleware Reference

## Overview

Chi provides optional middleware in the `github.com/go-chi/chi/v5/middleware` package. All are standard `net/http` middleware.

```go
import "github.com/go-chi/chi/v5/middleware"
```

## Request/Response Middleware

### Logger

Logs HTTP requests to stdout with method, path, status, and duration.

```go
r.Use(middleware.Logger)
```

Output example:
```
2024/03/15 10:30:45 "GET /users HTTP/1.1" from 127.0.0.1 - 200 2.123ms
```

### Recoverer

Recovers from panics and logs panic details without crashing.

```go
r.Use(middleware.Recoverer)
```

Should be placed early in the middleware stack, before other logging.

### RequestID

Injects a unique request ID into the context under the `RequestIDKey`.

```go
r.Use(middleware.RequestID)

// In handler
func handler(w http.ResponseWriter, r *http.Request) {
    requestID := middleware.GetReqID(r.Context())
    log.Printf("Request %s: processing", requestID)
}
```

### RealIP

Extracts the client's real IP from proxy headers like X-Forwarded-For.

```go
r.Use(middleware.RealIP)

// In handler
func handler(w http.ResponseWriter, r *http.Request) {
    clientIP := r.RemoteAddr
}
```

## Compression Middleware

### Compress

Compresses response body with gzip if client supports it.

```go
r.Use(middleware.Compress)
```

Automatically detects Accept-Encoding header and compresses accordingly.

## Timeout Middleware

### Timeout

Sets a deadline on the request context.

```go
r.Use(middleware.Timeout(30 * time.Second))

// In handler
func handler(w http.ResponseWriter, r *http.Request) {
    select {
    case <-r.Context().Done():
        // Timeout exceeded
        http.Error(w, "Request timeout", http.StatusRequestTimeout)
        return
    case result := <-doLongWork(r.Context()):
        w.Write(result)
    }
}
```

## Authentication Middleware

### BasicAuth

HTTP basic authentication helper.

```go
// Define credentials
users := map[string]string{
    "user1": "pass1",
    "user2": "pass2",
}

// Middleware factory
func BasicAuthMiddleware(users map[string]string) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            username, password, ok := r.BasicAuth()

            if !ok || users[username] != password {
                w.Header().Set("WWW-Authenticate", `Basic realm="restricted"`)
                http.Error(w, "Unauthorized", http.StatusUnauthorized)
                return
            }

            next.ServeHTTP(w, r)
        })
    }
}

r.Use(BasicAuthMiddleware(users))
```

## Content Negotiation Middleware

### AllowContentType

Whitelist accepted Content-Type headers.

```go
r.Use(middleware.AllowContentType("application/json"))

// Only JSON requests allowed; others get 415 Unsupported Media Type
```

### AllowContentEncoding

Whitelist accepted Content-Encoding headers.

```go
r.Use(middleware.AllowContentEncoding("gzip", "deflate"))
```

## Response Header Middleware

### NoCache

Adds headers to prevent client caching.

```go
r.Use(middleware.NoCache)
```

Adds headers:
- `Cache-Control: no-cache, no-store, must-revalidate`
- `Pragma: no-cache`
- `Expires: 0`

### SetHeader

Adds a header to all responses.

```go
r.Use(middleware.SetHeader("X-Custom-Header", "value"))
```

### Header

Middleware to set custom headers.

```go
r.Use(func(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("X-Custom", "value")
        next.ServeHTTP(w, r)
    })
})
```

## Path Middleware

### CleanPath

Cleans up request paths by removing double slashes.

```go
r.Use(middleware.CleanPath)

// /users//123 → /users/123
```

### StripSlashes

Removes trailing slashes from paths. Not built-in; implement with:

```go
func StripSlashes(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        path := r.URL.Path
        if len(path) > 1 && strings.HasSuffix(path, "/") {
            http.Redirect(w, r, path[:len(path)-1], http.StatusMovedPermanently)
            return
        }
        next.ServeHTTP(w, r)
    })
}

r.Use(StripSlashes)
```

## Health Check Middleware

### Heartbeat

Simple health check endpoint.

```go
r.Use(middleware.Heartbeat("/ping"))

// GET /ping → "." (single dot)
```

Useful for load balancers and monitoring.

## Request Limiting Middleware

### Throttle

Limits concurrent requests.

```go
r.Use(middleware.Throttle(100))  // Max 100 concurrent requests

// Excess requests get 503 Service Unavailable
```

## URL Format Middleware

### URLFormat

Extracts format parameter from URL path.

```go
r.Use(middleware.URLFormat)

// /users.json → format=json in context
// /users.xml → format=xml in context
```

Access in handler:

```go
func handler(w http.ResponseWriter, r *http.Request) {
    format := r.URL.Query().Get("format")
}
```

## Multiple Middleware Stacks

### Route-Specific Stack

```go
// Strict stack for admin routes
adminMW := chi.Chain(
    middleware.Logger,
    middleware.Recoverer,
    adminAuthMiddleware,
)

r.Route("/admin", func(r chi.Router) {
    // Apply stack to this group
    r.Use(adminMW...)
    r.Get("/dashboard", adminDashboard)
})
```

### Grouped Stack

```go
r.Group(func(r chi.Router) {
    r.Use(middleware.BasicAuth)
    r.Use(middleware.Timeout(5 * time.Second))

    r.Get("/protected", handler1)
    r.Post("/protected", handler2)
})
```

## Middleware Ordering Best Practices

```go
r := chi.NewRouter()

// 1. Logging (first - captures all requests)
r.Use(middleware.Logger)

// 2. Request ID (for tracking)
r.Use(middleware.RequestID)

// 3. Real IP (for accurate client tracking)
r.Use(middleware.RealIP)

// 4. Recovery (before others that might panic)
r.Use(middleware.Recoverer)

// 5. Compression (after handlers, before response sent)
r.Use(middleware.Compress)

// 6. Rate limiting
r.Use(middleware.Throttle(100))

// 7. Authentication/Authorization
r.Use(authMiddleware)

// 8. Business logic middleware
r.Use(loadContextMiddleware)
```

## Custom Middleware Pattern

When built-in middleware doesn't suffice:

```go
func CustomMiddleware(config Config) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            // Pre-processing
            start := time.Now()

            // Call next
            next.ServeHTTP(w, r)

            // Post-processing
            duration := time.Since(start)
            log.Printf("Processed in %dms", duration.Milliseconds())
        })
    }
}

r.Use(CustomMiddleware(config))
```

## Middleware Context Helpers

### GetReqID

Retrieves request ID from context:

```go
import "github.com/go-chi/chi/v5/middleware"

requestID := middleware.GetReqID(r.Context())
```

### Other Context Values

Access other middleware-set values through standard context API:

```go
// Logger sets no context values
// Recoverer sets no context values
// RequestID sets RequestIDKey
// RealIP modifies r.RemoteAddr
```
