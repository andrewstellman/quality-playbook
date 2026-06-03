# Chi Router - Error Handling and Custom Handlers

## Default Error Handling

By default, chi provides standard HTTP error responses:

- **404 Not Found**: When route doesn't match
- **405 Method Not Allowed**: When route exists but HTTP method doesn't match

## Custom NotFound Handler

Override the default 404 response:

```go
r := chi.NewRouter()

r.NotFound(func(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusNotFound)
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(map[string]string{
        "error": "Resource not found",
        "path":  r.RequestURI,
    })
})
```

## Custom MethodNotAllowed Handler

Handle cases where route exists but wrong HTTP method is used:

```go
r.MethodNotAllowed(func(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusMethodNotAllowed)
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(map[string]string{
        "error":  "Method not allowed",
        "method": r.Method,
        "path":   r.RequestURI,
    })
})
```

## Panic Recovery Middleware

Use the built-in `Recoverer` middleware to catch and handle panics:

```go
r := chi.NewRouter()
r.Use(middleware.Recoverer)  // Recovers from panics

r.Get("/panic", func(w http.ResponseWriter, r *http.Request) {
    panic("Something went wrong!")  // Caught by Recoverer
})
```

The Recoverer middleware logs panic details and returns a 500 error without crashing the server.

## Custom Error Handling Middleware

Create middleware to handle errors consistently:

```go
func ErrorHandler(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        defer func() {
            if err := recover(); err != nil {
                w.Header().Set("Content-Type", "application/json")
                w.WriteHeader(http.StatusInternalServerError)
                json.NewEncoder(w).Encode(map[string]interface{}{
                    "error": fmt.Sprintf("%v", err),
                })
            }
        }()
        next.ServeHTTP(w, r)
    })
}

r.Use(ErrorHandler)
```

## Custom Handler Types

Chi supports standard `http.Handler`, but you can also implement custom handler types that return errors:

```go
// Custom handler type that returns an error
type ErrorHandler func(w http.ResponseWriter, r *http.Request) error

// Wrapper to make it compatible with http.Handler
func (h ErrorHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    if err := h(w, r); err != nil {
        w.WriteHeader(http.StatusInternalServerError)
        w.Write([]byte(err.Error()))
    }
}

// Usage
r.Get("/users/{id}", ErrorHandler(func(w http.ResponseWriter, r *http.Request) error {
    id := chi.URLParam(r, "id")
    user, err := loadUser(id)
    if err != nil {
        return err  // Automatically converted to 500
    }
    return json.NewEncoder(w).Encode(user)
}))
```

## Validation and Error Responses

Pattern for validation with proper error responses:

```go
type ValidationError struct {
    Field   string
    Message string
}

func createUser(w http.ResponseWriter, r *http.Request) {
    var user User
    if err := json.NewDecoder(r.Body).Decode(&user); err != nil {
        w.WriteHeader(http.StatusBadRequest)
        json.NewEncoder(w).Encode(map[string]string{
            "error": "Invalid JSON",
        })
        return
    }

    // Validate
    var validationErrors []ValidationError
    if user.Email == "" {
        validationErrors = append(validationErrors, ValidationError{
            Field:   "email",
            Message: "Email is required",
        })
    }
    if len(user.Name) < 2 {
        validationErrors = append(validationErrors, ValidationError{
            Field:   "name",
            Message: "Name must be at least 2 characters",
        })
    }

    if len(validationErrors) > 0 {
        w.WriteHeader(http.StatusUnprocessableEntity)
        json.NewEncoder(w).Encode(map[string]interface{}{
            "error":      "Validation failed",
            "validation": validationErrors,
        })
        return
    }

    // Create user...
    w.WriteHeader(http.StatusCreated)
    json.NewEncoder(w).Encode(user)
}
```

## Common Issue: Custom NotFound Handler Not Invoked

**Problem**: When using wildcard routes with `http.FileServer`, custom NotFound handler doesn't trigger.

**Cause**: The wildcard route matches everything, preventing NotFound from being called.

**Solution**: Order routes carefully or use separate mounting:

```go
// Correct: Specific routes first, then wildcard
r.Get("/api/users", getUsers)
r.Mount("/static", http.FileServer(http.Dir("static")))

// Less ideal: Wildcard intercepts all 404s
r.Get("/", handler)
r.Mount("/", http.FileServer(http.Dir("static")))  // Matches everything!
```

## Error Handling in Middleware

Handle errors within middleware chains:

```go
func LoggingWithErrors(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        start := time.Now()

        // Wrap response writer to capture status
        wrapped := &responseWriter{ResponseWriter: w, statusCode: 200}

        next.ServeHTTP(wrapped, r)

        duration := time.Since(start)
        if wrapped.statusCode >= 400 {
            log.Printf("[ERROR] %s %s %d (%dms)",
                r.Method, r.RequestURI, wrapped.statusCode, duration.Milliseconds())
        } else {
            log.Printf("[OK] %s %s %d (%dms)",
                r.Method, r.RequestURI, wrapped.statusCode, duration.Milliseconds())
        }
    })
}

type responseWriter struct {
    http.ResponseWriter
    statusCode int
}

func (w *responseWriter) WriteHeader(code int) {
    w.statusCode = code
    w.ResponseWriter.WriteHeader(code)
}
```
