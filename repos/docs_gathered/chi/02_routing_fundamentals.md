# Chi Router - Routing Fundamentals

## Basic Route Definition

Chi provides methods to define routes for each HTTP verb:

```go
r := chi.NewRouter()

r.Get("/users", listUsers)
r.Post("/users", createUser)
r.Put("/users/{id}", updateUser)
r.Delete("/users/{id}", deleteUser)
r.Patch("/users/{id}", patchUser)
```

## HTTP Method Shortcuts

Chi provides convenient shortcuts for all standard HTTP methods:

| Method | HTTP Verb | Usage |
|--------|-----------|-------|
| `Get()` | GET | Retrieve resource |
| `Post()` | POST | Create resource |
| `Put()` | PUT | Replace resource |
| `Patch()` | PATCH | Partial update |
| `Delete()` | DELETE | Remove resource |
| `Head()` | HEAD | Like GET without body |
| `Options()` | OPTIONS | Request options |
| `Connect()` | CONNECT | Establish tunnel |
| `Trace()` | TRACE | Trace path |

## URL Pattern Syntax

### Named Parameters

Named parameters are enclosed in curly braces and match text up to the next slash:

```go
r.Get("/users/{id}", handler)           // matches: /users/123
r.Get("/users/{name}/posts", handler)   // matches: /users/john/posts
r.Get("/posts/{year}/{month}/{day}", handler) // matches: /posts/2024/03/15
```

Access parameters in your handler:

```go
func handler(w http.ResponseWriter, r *http.Request) {
    id := chi.URLParam(r, "id")
    // Use id...
}
```

### Regular Expression Patterns

Use regex patterns within parameter names for validation:

```go
// Only numeric IDs
r.Get("/users/{id:[0-9]+}", handler)

// Slug-like strings (lowercase and hyphens)
r.Get("/articles/{slug:[a-z-]+}", handler)

// Dates in YYYY-MM-DD format
r.Get("/posts/{date:\\d{4}-\\d{2}-\\d{2}}", handler)

// Complex date pattern with separate parts
r.Get("/date/{yyyy:\\d{4}}/{mm:\\d{2}}/{dd:\\d{2}}", handler)

// Anonymous regex pattern (no parameter name)
r.Get("/items/{:\\d+}", handler)
```

### Wildcards

The `*` wildcard matches everything including slashes. It must be the last pattern element:

```go
// Match all files under /static/
r.Get("/static/*", http.FileServer(http.Dir("static")))

// Match any remaining path
r.Get("/admin/*", adminHandler)

// Access the matched portion
func adminHandler(w http.ResponseWriter, r *http.Request) {
    remaining := chi.URLParam(r, "*")
    // Use remaining path...
}
```

## The Method Function

For dynamic HTTP method handling or custom methods:

```go
// Built-in methods
r.Method("GET", "/users", handler)
r.MethodFunc("POST", "/users", handlerFunc)

// Custom HTTP methods
r.RegisterMethod("CUSTOM")
r.Method("CUSTOM", "/data", customHandler)
```

## Route Ordering

Chi uses a Patricia Radix Trie for efficient routing. Routes are matched in order of specificity:

```go
r.Get("/users/me", currentUserHandler)      // More specific - matched first
r.Get("/users/{id}", userByIdHandler)       // Less specific - matched second
```

## Handler Signatures

All handlers must match the `http.Handler` or `http.HandlerFunc` signature:

```go
// http.HandlerFunc style (used with Get, Post, etc.)
func myHandler(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(http.StatusOK)
    w.Write([]byte(`{"status": "ok"}`))
}

// http.Handler style (with ServeHTTP method)
type MyHandler struct{}
func (h MyHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    // Handle request
}
```
