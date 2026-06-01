# Chi Router - Advanced Topics

## Route Matching Internals

### Patricia Radix Trie

Chi's routing is built on a Patricia Radix Trie, a space-optimized trie variant that:

- **Compresses paths**: Consecutive single-child nodes merge
- **Fast lookup**: O(k) where k is key length
- **Memory efficient**: Far better than naive trie
- **Deterministic**: Same match order always

### Route Precedence

Routes are matched by specificity:

```go
// More specific routes matched first
r.Get("/users/me", currentUser)         // Matches /users/me (highest priority)
r.Get("/users/{id:[0-9]+}", userByID)   // Matches /users/123
r.Get("/users/{id}", userByName)        // Matches /users/john (lowest priority)
```

### Empty Routes and Wildcards

Wildcard matching has special behavior:

```go
// Wildcard must be last element
r.Get("/files/*", serveFiles)      // Matches /files/anything/here

// Special case: root wildcard
r.Get("/*", catchAll)              // Matches any path not caught above
```

## Custom HTTP Methods

Register and handle custom HTTP methods beyond standard RFC verbs:

```go
func main() {
    r := chi.NewRouter()

    // Register custom method
    r.RegisterMethod("CUSTOM")

    // Use custom method
    r.Method("CUSTOM", "/resource", customHandler)

    // Or create a shortcut
    r.HandleFunc("GET /users", listUsers)  // Go 1.22+
}
```

## Route Context Deep Dive

### Accessing Route Information During Request

```go
func handler(w http.ResponseWriter, r *http.Request) {
    // Get chi's route context
    rctx := chi.RouteContext(r.Context())

    // Route pattern that matched
    pattern := rctx.RoutePattern()  // "/users/{id}"

    // HTTP method
    method := rctx.RouteMethod      // "GET"

    // All matched patterns up to this point
    patterns := rctx.RoutePatterns  // ["/", "/api", "/users/{id}"]

    // URL parameters
    keys := rctx.URLParams.Keys     // ["id"]
    vals := rctx.URLParams.Values   // ["123"]

    // Access nested router info
    rctx.Routes                     // The current Routes interface
}
```

### Testing Route Matching

```go
func TestRouteMatching(t *testing.T) {
    r := chi.NewRouter()
    r.Get("/users/{id}", handler)

    // Test if route matches
    rctx := &chi.Context{}
    matches := r.Routes().Match(rctx, "GET", "/users/123")

    if !matches {
        t.Error("Route should match")
    }

    // Find pattern for a request
    pattern := r.Routes().Find(rctx, "GET", "/users/123")
    if pattern != "/users/{id}" {
        t.Errorf("Expected /users/{id}, got %s", pattern)
    }
}
```

## Nested Route Parameter Access

### Parameter Extraction in Nested Contexts

```go
r.Route("/teams/{teamID}", func(r chi.Router) {
    r.Route("/projects/{projectID}", func(r chi.Router) {
        r.Get("/tasks/{taskID}", func(w http.ResponseWriter, r *http.Request) {
            // Access all parameters
            teamID := chi.URLParam(r, "teamID")
            projectID := chi.URLParam(r, "projectID")
            taskID := chi.URLParam(r, "taskID")

            // Access through route context for debugging
            rctx := chi.RouteContext(r.Context())
            allParams := rctx.URLParams
        })
    })
})
```

## Middleware Wrapping and Composition

### Creating Meta-Middleware (Middleware Factories)

```go
// Factory creates middleware with configuration
func RateLimitByUserID(limiter *Limiter) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            userID := r.Context().Value("userID").(string)

            if !limiter.Allow(userID) {
                http.Error(w, "Rate limit exceeded", http.StatusTooManyRequests)
                return
            }

            next.ServeHTTP(w, r)
        })
    }
}

// Usage
r.Use(RateLimitByUserID(limiter))
```

### Middleware Chaining with Conditions

```go
func ConditionalMiddleware(condition func(r *http.Request) bool, mw func(http.Handler) http.Handler) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            if condition(r) {
                mw(next).ServeHTTP(w, r)
            } else {
                next.ServeHTTP(w, r)
            }
        })
    }
}

// Usage: Apply auth only to API routes
r.Use(ConditionalMiddleware(
    func(r *http.Request) bool {
        return strings.HasPrefix(r.URL.Path, "/api/")
    },
    authMiddleware,
))
```

## Response Wrapper Pattern

### Capturing Response Metadata

```go
type ResponseWriter struct {
    http.ResponseWriter
    statusCode int
    body       []byte
    written    bool
}

func (rw *ResponseWriter) Write(b []byte) (int, error) {
    if !rw.written {
        rw.written = true
    }
    rw.body = append(rw.body, b...)
    return rw.ResponseWriter.Write(b)
}

func (rw *ResponseWriter) WriteHeader(code int) {
    rw.statusCode = code
    rw.ResponseWriter.WriteHeader(code)
}

// Middleware using response wrapper
func ResponseLogging(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        wrapped := &ResponseWriter{
            ResponseWriter: w,
            statusCode:     200,
        }

        next.ServeHTTP(wrapped, r)

        log.Printf("Status: %d, Body size: %d", wrapped.statusCode, len(wrapped.body))
    })
}
```

## Request-to-Handler Communication

### Signal Patterns

Using context for communication between middleware and handlers:

```go
// Define signal types
type signal string

const (
    signalSkipLogging signal = "skip-logging"
    signalCached      signal = "cached"
)

// Middleware sets signal
func CacheMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        if cached, ok := cache[r.URL.Path]; ok {
            w.Write(cached)
            ctx := context.WithValue(r.Context(), signalCached, true)
            r = r.WithContext(ctx)
            return
        }
        next.ServeHTTP(w, r)
    })
}

// Handler checks signal
func handler(w http.ResponseWriter, r *http.Request) {
    if cached, _ := r.Context().Value(signalCached).(bool); cached {
        // Handle cache hit
    }
}
```

## Dynamic Route Registration

### Runtime Route Addition

```go
type DynamicRouter struct {
    mux     *chi.Mux
    mu      sync.RWMutex
}

func (dr *DynamicRouter) AddRoute(method, pattern string, handler http.HandlerFunc) {
    dr.mu.Lock()
    defer dr.mu.Unlock()
    dr.mux.Method(method, pattern, handler)
}

func (dr *DynamicRouter) Handler() http.Handler {
    return dr.mux
}

// Usage
dr := &DynamicRouter{mux: chi.NewRouter()}
dr.AddRoute("GET", "/users", listUsers)
dr.AddRoute("POST", "/users", createUser)
```

## Performance Profiling

### Identifying Bottlenecks

```go
import (
    "log"
    "runtime"
    "time"
)

func ProfilingMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        var m runtime.MemStats
        runtime.ReadMemStats(&m)
        startMem := m.Alloc

        start := time.Now()
        next.ServeHTTP(w, r)
        duration := time.Since(start)

        runtime.ReadMemStats(&m)
        memAllocated := m.Alloc - startMem

        log.Printf(
            "[PROFILE] %s %s: %dms, %d bytes allocated",
            r.Method,
            r.URL.Path,
            duration.Milliseconds(),
            memAllocated,
        )
    })
}

r.Use(ProfilingMiddleware)
```

## Instrumentation and Observability

### Structured Logging Integration

```go
import "log/slog"

func StructuredLogging(logger *slog.Logger) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            start := time.Now()
            wrapped := &statusRecorder{ResponseWriter: w, statusCode: 200}

            next.ServeHTTP(wrapped, r)

            logger.LogAttrs(context.Background(),
                slog.LevelInfo,
                "request",
                slog.String("method", r.Method),
                slog.String("path", r.URL.Path),
                slog.Int("status", wrapped.statusCode),
                slog.Duration("duration", time.Since(start)),
            )
        })
    }
}
```

### Metrics Collection

```go
import "expvar"

var (
    requestsTotal   = expvar.NewInt("requests.total")
    requestsByCode  = expvar.NewMap("requests.by.code")
    requestDuration = expvar.NewInt("request.duration.ms")
)

func MetricsMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        requestsTotal.Add(1)
        start := time.Now()

        wrapped := &statusRecorder{ResponseWriter: w, statusCode: 200}
        next.ServeHTTP(wrapped, r)

        requestsByCode.AddInt(fmt.Sprintf("%d", wrapped.statusCode), 1)
        requestDuration.Set(int64(time.Since(start).Milliseconds()))
    })
}
```
