# Chi Router - Testing Chi Applications

## Basic Testing with httptest

Chi works seamlessly with Go's standard `testing` package and `net/http/httptest`:

```go
package main

import (
    "net/http"
    "net/http/httptest"
    "testing"
    "github.com/go-chi/chi/v5"
)

func TestGetUser(t *testing.T) {
    // Create router
    r := chi.NewRouter()
    r.Get("/users/{id}", getUser)

    // Create request
    req := httptest.NewRequest("GET", "/users/123", nil)
    w := httptest.NewRecorder()

    // Serve request
    r.ServeHTTP(w, req)

    // Check response
    if w.Code != http.StatusOK {
        t.Errorf("Expected 200, got %d", w.Code)
    }

    expected := `{"id":"123","name":"John"}`
    if w.Body.String() != expected {
        t.Errorf("Expected %s, got %s", expected, w.Body.String())
    }
}

func getUser(w http.ResponseWriter, r *http.Request) {
    id := chi.URLParam(r, "id")
    w.Header().Set("Content-Type", "application/json")
    w.Write([]byte(`{"id":"` + id + `","name":"John"}`))
}
```

## Table-Driven Tests

Test multiple scenarios efficiently:

```go
func TestUserAPI(t *testing.T) {
    tests := []struct {
        name       string
        method     string
        path       string
        wantStatus int
        wantBody   string
    }{
        {
            name:       "get existing user",
            method:     "GET",
            path:       "/users/1",
            wantStatus: http.StatusOK,
            wantBody:   `{"id":"1","name":"Alice"}`,
        },
        {
            name:       "get non-existent user",
            method:     "GET",
            path:       "/users/999",
            wantStatus: http.StatusNotFound,
            wantBody:   `{"error":"user not found"}`,
        },
        {
            name:       "invalid user id",
            method:     "GET",
            path:       "/users/abc",
            wantStatus: http.StatusBadRequest,
            wantBody:   `{"error":"invalid user id"}`,
        },
    }

    r := createRouter()

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            req := httptest.NewRequest(tt.method, tt.path, nil)
            w := httptest.NewRecorder()

            r.ServeHTTP(w, req)

            if w.Code != tt.wantStatus {
                t.Errorf("status: got %d, want %d", w.Code, tt.wantStatus)
            }

            if w.Body.String() != tt.wantBody {
                t.Errorf("body: got %q, want %q", w.Body.String(), tt.wantBody)
            }
        })
    }
}

func createRouter() chi.Router {
    r := chi.NewRouter()
    r.Get("/users/{id}", func(w http.ResponseWriter, r *http.Request) {
        id := chi.URLParam(r, "id")
        // Validation and handler logic
        w.Write([]byte(`{"id":"` + id + `","name":"Alice"}`))
    })
    return r
}
```

## Testing with Context Values

When handlers use context values set by middleware:

```go
func TestProtectedRoute(t *testing.T) {
    r := chi.NewRouter()

    // Add middleware that sets context value
    r.Use(func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            // Manually set context for testing
            ctx := context.WithValue(r.Context(), "userID", "test-user-123")
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    })

    r.Get("/profile", profileHandler)

    req := httptest.NewRequest("GET", "/profile", nil)
    w := httptest.NewRecorder()

    r.ServeHTTP(w, req)

    if w.Code != http.StatusOK {
        t.Errorf("Expected 200, got %d", w.Code)
    }
}

func profileHandler(w http.ResponseWriter, r *http.Request) {
    userID := r.Context().Value("userID").(string)
    w.Write([]byte("User: " + userID))
}
```

## Testing URL Parameters

Injecting chi's route context for parameter testing:

```go
func TestUserWithContext(t *testing.T) {
    handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        id := chi.URLParam(r, "id")
        w.Write([]byte("ID: " + id))
    })

    r := chi.NewRouter()
    r.Get("/users/{id}", handler)

    req := httptest.NewRequest("GET", "/users/42", nil)
    w := httptest.NewRecorder()

    r.ServeHTTP(w, req)

    if w.Body.String() != "ID: 42" {
        t.Errorf("Expected 'ID: 42', got %q", w.Body.String())
    }
}
```

## Testing Error Cases

```go
func TestErrorHandling(t *testing.T) {
    r := chi.NewRouter()

    r.Get("/panic", func(w http.ResponseWriter, r *http.Request) {
        panic("intentional panic")
    })

    r.Use(middleware.Recoverer)

    req := httptest.NewRequest("GET", "/panic", nil)
    w := httptest.NewRecorder()

    // Should not crash
    r.ServeHTTP(w, req)

    if w.Code != http.StatusInternalServerError {
        t.Errorf("Expected 500, got %d", w.Code)
    }
}

func TestNotFound(t *testing.T) {
    r := chi.NewRouter()

    r.NotFound(func(w http.ResponseWriter, r *http.Request) {
        w.WriteHeader(http.StatusNotFound)
        w.Write([]byte("Custom 404"))
    })

    req := httptest.NewRequest("GET", "/nonexistent", nil)
    w := httptest.NewRecorder()

    r.ServeHTTP(w, req)

    if w.Code != http.StatusNotFound {
        t.Errorf("Expected 404, got %d", w.Code)
    }
    if w.Body.String() != "Custom 404" {
        t.Errorf("Expected 'Custom 404', got %q", w.Body.String())
    }
}
```

## Integration Tests with Database

For testing with a real database:

```go
func TestUserAPIWithDB(t *testing.T) {
    // Setup test database (e.g., Docker container or test instance)
    db := setupTestDB()
    defer db.Close()

    // Seed test data
    seedUsers(db)

    // Create router with database
    r := createRouterWithDB(db)

    tests := []struct {
        name     string
        method   string
        path     string
        wantUser string
    }{
        {"get user 1", "GET", "/users/1", "Alice"},
        {"get user 2", "GET", "/users/2", "Bob"},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            req := httptest.NewRequest(tt.method, tt.path, nil)
            w := httptest.NewRecorder()

            r.ServeHTTP(w, req)

            var result map[string]interface{}
            json.NewDecoder(w.Body).Decode(&result)

            if result["name"] != tt.wantUser {
                t.Errorf("Expected %s, got %s", tt.wantUser, result["name"])
            }
        })
    }
}
```

## Testing Middleware

```go
func TestAuthMiddleware(t *testing.T) {
    r := chi.NewRouter()

    // Add auth middleware
    r.Use(func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            token := r.Header.Get("Authorization")
            if token == "" {
                http.Error(w, "Missing token", http.StatusUnauthorized)
                return
            }
            next.ServeHTTP(w, r)
        })
    })

    r.Get("/protected", func(w http.ResponseWriter, r *http.Request) {
        w.Write([]byte("Access granted"))
    })

    tests := []struct {
        name       string
        token      string
        wantStatus int
        wantBody   string
    }{
        {"with token", "valid-token", http.StatusOK, "Access granted"},
        {"no token", "", http.StatusUnauthorized, "Missing token"},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            req := httptest.NewRequest("GET", "/protected", nil)
            if tt.token != "" {
                req.Header.Set("Authorization", tt.token)
            }

            w := httptest.NewRecorder()
            r.ServeHTTP(w, req)

            if w.Code != tt.wantStatus {
                t.Errorf("status: got %d, want %d", w.Code, tt.wantStatus)
            }
        })
    }
}
```

## Best Practices

1. **Use httptest.NewRequest**: Create realistic HTTP requests for testing
2. **Use httptest.NewRecorder**: Capture response without network I/O
3. **Test in isolation**: Keep tests focused on single behaviors
4. **Use table-driven tests**: Efficiently test multiple scenarios
5. **Mock dependencies**: Use test doubles for databases, external services
6. **Test context values**: Inject required context for middleware-dependent handlers
7. **Test error paths**: Ensure error handlers work correctly
