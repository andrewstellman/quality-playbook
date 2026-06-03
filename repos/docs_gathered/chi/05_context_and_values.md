# Chi Router - Context and Request-Scoped Values

## Overview

Chi is built on Go's `context` package (introduced in Go 1.7) to handle signaling, cancellation, and request-scoped values across a handler chain. The router leverages context to pass data through middleware and handlers safely.

## Chi's Route Context

Chi automatically attaches a special route context to each request:

```go
// Access chi's route context
type Context struct {
    Routes       Routes
    RoutePath    string
    RouteMethod  string
    URLParams    RouteParams
    RoutePatterns []string
}
```

## URL Parameters with URLParam

Retrieve URL parameters from a request:

```go
func getArticle(w http.ResponseWriter, r *http.Request) {
    // Named parameter
    articleID := chi.URLParam(r, "articleID")

    // Wildcard parameter
    filePath := chi.URLParam(r, "*")

    // Use in logic
    article := loadArticle(articleID)
    respondWithJSON(w, article)
}
```

The `chi.URLParam` function is a convenience wrapper around the context:

```go
// These are equivalent:
id := chi.URLParam(r, "id")
id := chi.URLParamFromCtx(r.Context(), "id")
```

## Adding Request-Scoped Values

The primary use of context in chi applications is passing request-scoped data through middleware:

### Pattern 1: Direct Context Values

```go
func AuthMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        // Extract authentication info
        token := r.Header.Get("Authorization")
        userID := validateToken(token)

        // Add to request context
        ctx := context.WithValue(r.Context(), "userID", userID)

        // Continue with updated context
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}

func protectedHandler(w http.ResponseWriter, r *http.Request) {
    // Retrieve value from context
    userID := r.Context().Value("userID").(string)
    // Use userID...
}
```

### Pattern 2: Custom Type Keys (Recommended)

Using string keys can cause collisions. Use custom types instead:

```go
// Define custom context keys
type ctxKey string

const (
    ctxKeyUser ctxKey = "user"
    ctxKeyAdmin ctxKey = "admin"
    ctxKeyDB ctxKey = "db"
)

// Type-safe context value
type User struct {
    ID    string
    Email string
    Admin bool
}

func AuthMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        user := authenticateRequest(r)

        ctx := context.WithValue(r.Context(), ctxKeyUser, user)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}

func handler(w http.ResponseWriter, r *http.Request) {
    user := r.Context().Value(ctxKeyUser).(User)
    // Now properly typed
    email := user.Email
}
```

### Pattern 3: Struct Holder

For multiple values, use a struct:

```go
type RequestContext struct {
    User      User
    Admin     bool
    RequestID string
    DB        *sql.DB
}

const ctxKey ctxKey = "request"

func LoadContextMiddleware(db *sql.DB) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            user := authenticateRequest(r)
            requestID := r.Header.Get("X-Request-ID")

            ctx := context.WithValue(r.Context(), ctxKey, RequestContext{
                User:      user,
                Admin:     user.Role == "admin",
                RequestID: requestID,
                DB:        db,
            })

            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}

func handler(w http.ResponseWriter, r *http.Request) {
    rc := r.Context().Value(ctxKey).(RequestContext)
    // Access multiple values cleanly
    user := rc.User
    db := rc.DB
}
```

## Chi's Route Context Access

Access chi's own route information:

```go
func handler(w http.ResponseWriter, r *http.Request) {
    // Get chi's route context
    rctx := chi.RouteContext(r.Context())

    // Access route information
    pattern := rctx.RoutePattern()      // "/users/{id}"
    method := rctx.RouteMethod          // "GET"
    params := rctx.URLParams             // RouteParams with Keys and Values

    // Manually access URL parameters
    for i, key := range rctx.URLParams.Keys {
        value := rctx.URLParams.Values[i]
        fmt.Printf("%s=%s\n", key, value)
    }
}
```

## Timeouts with Context

Set request deadlines using context:

```go
r := chi.NewRouter()
r.Use(middleware.Timeout(30 * time.Second))

func handler(w http.ResponseWriter, r *http.Request) {
    // Request context now has a deadline
    select {
    case <-r.Context().Done():
        // Deadline exceeded
        http.Error(w, "Request timeout", http.StatusRequestTimeout)
        return
    case result := <-doWork(r.Context()):
        respondWithJSON(w, result)
    }
}

func doWork(ctx context.Context) <-chan string {
    ch := make(chan string)
    go func() {
        // Check context during long operations
        if err := ctx.Err(); err != nil {
            return
        }
        // Do work...
        ch <- "done"
    }()
    return ch
}
```

## Best Practices

1. **Use Custom Types for Keys**: Avoid string-based keys to prevent collisions
2. **Store Lightweight Data**: Context is for request-scoped data, not large objects
3. **Never Store Connections Directly**: Pass database connections through middleware, not in context
4. **Check Context Cancellation**: In long-running operations, check `ctx.Done()`
5. **Document Context Keys**: Clearly document what values are available in each route
6. **Immutable Values**: Treat context values as immutable once added
