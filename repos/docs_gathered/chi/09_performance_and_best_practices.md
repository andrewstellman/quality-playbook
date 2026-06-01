# Chi Router - Performance and Best Practices

## Performance Characteristics

### Architecture

Chi uses a **Patricia Radix Trie** (also called a radix tree) for URL pattern matching. This provides:

- **Fast Lookups**: O(k) where k is the length of the route pattern string
- **Memory Efficient**: Optimal space complexity for routing trees
- **No Regular Expression Overhead**: Most routing doesn't require regex evaluation

### Performance vs Other Routers

Chi consistently ranks among the fastest HTTP routers in Go:

- Comparable to specialized high-performance routers like HttpRouter
- Significantly faster than regex-based routing
- More maintainable than hand-written optimizations

**Important Note**: Router performance should rarely be your primary selection criterion. All major routers are fast enough for nearly all applications.

## Performance Best Practices

### 1. Middleware Ordering

Place middleware in the correct order for efficiency:

```go
r := chi.NewRouter()

// Logging before recovery - catches panic details
r.Use(middleware.Logger)
r.Use(middleware.Recoverer)

// Authentication early - prevent unnecessary processing
r.Use(authMiddleware)

// Compression late - after handler produces output
r.Use(middleware.Compress)
```

### 2. Route Organization

Use subrouters to reduce matching cost:

```go
// Good: Subrouters narrow the search space
r.Route("/api", func(r chi.Router) {
    r.Route("/v1", func(r chi.Router) {
        r.Get("/users", handler)
    })
})

// Less efficient: Long regex patterns
r.Get("/api/v1/users/{id:[0-9]+}", handler)
```

### 3. Limit Route Specificity

Avoid overly specific regex patterns that require evaluation:

```go
// Good: Simple pattern
r.Get("/posts/{id}", getPost)

// Avoids: Complex regex when simple works
r.Get("/posts/{id:[0-9]+}", getPost)  // Only if you really need to validate
```

### 4. Context Value Caching

Cache computed values in context rather than recomputing:

```go
// Bad: Recompute on every handler call
func handler(w http.ResponseWriter, r *http.Request) {
    user := fetchUserFromDB(chi.URLParam(r, "userID"))
    // ...
}

// Good: Compute once in middleware
func userMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        userID := chi.URLParam(r, "userID")
        user := fetchUserFromDB(userID)
        ctx := context.WithValue(r.Context(), "user", user)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}
```

### 5. Connection Pooling

For database access, use connection pooling efficiently:

```go
type Config struct {
    MaxOpenConns    int
    MaxIdleConns    int
    ConnMaxLifetime time.Duration
}

// Configure database connection pool
db, _ := sql.Open("postgres", dsn)
db.SetMaxOpenConns(25)
db.SetMaxIdleConns(5)
db.SetConnMaxLifetime(5 * time.Minute)

// Pass to handlers via middleware
r.Use(func(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        ctx := context.WithValue(r.Context(), "db", db)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
})
```

## Best Practices

### 1. Use Standard Library Patterns

```go
// Good: Standard http.Handler and http.HandlerFunc
r.Get("/users", handler)

// Where handler is stdlib compatible
func handler(w http.ResponseWriter, r *http.Request) {
    // ...
}
```

### 2. Organize by Domain

```go
// users/router.go
package users

func Router() chi.Router {
    r := chi.NewRouter()
    r.Use(loadUserMiddleware)
    r.Get("/", list)
    r.Get("/{id}", get)
    return r
}

// posts/router.go
package posts

func Router() chi.Router {
    r := chi.NewRouter()
    r.Post("/", create)
    return r
}

// main.go
func main() {
    r := chi.NewRouter()
    r.Mount("/users", users.Router())
    r.Mount("/posts", posts.Router())
}
```

### 3. Document URL Parameters

```go
// Good: Clear documentation
// GET /users/{userID}
// Returns a user by ID
// Parameters:
//   - userID: numeric user ID
func getUser(w http.ResponseWriter, r *http.Request) {
    userID := chi.URLParam(r, "userID")
    // ...
}
```

### 4. Validate Early

```go
func getUser(w http.ResponseWriter, r *http.Request) {
    userID := chi.URLParam(r, "userID")

    // Validate immediately
    if userID == "" {
        http.Error(w, "Missing userID", http.StatusBadRequest)
        return
    }

    // Continue with valid data
    user, err := fetchUser(userID)
    if err != nil {
        http.Error(w, "User not found", http.StatusNotFound)
        return
    }

    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(user)
}
```

### 5. Use Type-Safe Context Keys

```go
// Good: Custom type prevents collisions
type ctxKey string
const userKey ctxKey = "user"

ctx := context.WithValue(r.Context(), userKey, user)
user := r.Context().Value(userKey).(User)

// Avoid: String keys cause collisions
ctx := context.WithValue(r.Context(), "user", user)  // Could conflict with other packages
```

### 6. Handle Panics Gracefully

```go
r.Use(middleware.Recoverer)  // Always include
```

### 7. Clean Resource Lifecycle

```go
func main() {
    db, _ := sql.Open("postgres", dsn)
    defer db.Close()

    r := chi.NewRouter()
    // ... routes ...

    server := &http.Server{
        Addr:    ":8080",
        Handler: r,
    }

    go server.ListenAndServe()

    // Graceful shutdown
    sigChan := make(chan os.Signal)
    signal.Notify(sigChan, os.Interrupt)
    <-sigChan

    ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()
    server.Shutdown(ctx)
}
```

## Common Pitfalls

### 1. Wildcard Routing Blocking 404

**Problem**: Wildcard routes match too broadly
```go
// Wrong: Catches everything, custom NotFound never called
r.Get("/*", http.FileServer(http.Dir("static")))
r.NotFound(custom404)
```

**Solution**: Order routes carefully
```go
r.Get("/api/*", apiHandler)      // Specific routes first
r.Mount("/static", fileServer)   // Wildcard later
```

### 2. Middleware Order Matters

**Problem**: Wrong middleware order causes issues
```go
// Wrong: Logger catches panic stack
r.Use(middleware.Recoverer)
r.Use(middleware.Logger)
```

**Solution**: Logger before Recoverer
```go
r.Use(middleware.Logger)
r.Use(middleware.Recoverer)
```

### 3. Context Value Collisions

**Problem**: String keys cause conflicts
```go
// Two packages both use context.WithValue(ctx, "user", ...)
// They overwrite each other!
```

**Solution**: Use type-safe keys
```go
type key string
const myKey key = "myuser"
```

### 4. Large Objects in Context

**Problem**: Storing large data in context
```go
// Bad: Context is not for caching large objects
ctx = context.WithValue(ctx, "largeCache", bigMap)
```

**Solution**: Store only request-scoped, lightweight data
```go
// Good: Simple, lightweight values
ctx = context.WithValue(ctx, "userID", "123")
```

## Monitoring and Debugging

### Print Routes

```go
func printRoutes(r chi.Router) {
    walkFunc := func(method string, route string, handler http.Handler, middlewares ...func(http.Handler) http.Handler) error {
        fmt.Printf("[%s] %s\n", method, route)
        return nil
    }

    chi.Walk(r, walkFunc)
}
```

### Request ID Tracking

```go
r.Use(middleware.RequestID)

// In handlers
func handler(w http.ResponseWriter, r *http.Request) {
    requestID := middleware.GetReqID(r.Context())
    log.Printf("Request %s: processing", requestID)
}
```

### Custom Metrics

```go
func MetricsMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        start := time.Now()
        wrapped := &statusRecorder{ResponseWriter: w}

        next.ServeHTTP(wrapped, r)

        duration := time.Since(start)
        recordMetric(r.Method, r.URL.Path, wrapped.statusCode, duration)
    })
}
```
