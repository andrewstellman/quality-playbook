# Chi Router - Ecosystem and Extensions

## Official Chi Packages

Chi provides a minimal core with optional packages for specific use cases.

### go-chi/chi (Core)

The minimal router (~1000 LOC):
```go
import "github.com/go-chi/chi/v5"

r := chi.NewRouter()
r.Get("/", handler)
```

### go-chi/chi/middleware

Built-in middleware for common patterns:

```go
import "github.com/go-chi/chi/v5/middleware"

r.Use(middleware.Logger)
r.Use(middleware.Recoverer)
r.Use(middleware.RequestID)
r.Use(middleware.RealIP)
r.Use(middleware.Timeout(30 * time.Second))
```

### go-chi/chi/render

JSON/XML response rendering utilities:

```go
import "github.com/go-chi/chi/v5/render"

func handler(w http.ResponseWriter, r *http.Request) {
    render.JSON(w, r, map[string]string{"status": "ok"})
}
```

### go-chi/chi/docgen

Auto-generate API documentation from route structure:

```go
import "github.com/go-chi/docgen"

// Generate markdown documentation of routes
docgen.PrintRoutes(r)
```

## Community Packages

### CORS Support

**go-chi/cors** - CORS middleware implementation

```bash
go get github.com/go-chi/cors
```

```go
import "github.com/go-chi/cors"

r := chi.NewRouter()
r.Use(cors.Handler(cors.Options{
    AllowedOrigins:   []string{"https://*", "http://localhost:*"},
    AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
    AllowedHeaders:   []string{"Accept", "Authorization", "Content-Type"},
    ExposedHeaders:   []string{"Link"},
    AllowCredentials: false,
    MaxAge:           300,
}))
```

### JWT Authentication

**go-chi/jwtauth** - JWT authentication middleware

```bash
go get github.com/go-chi/jwtauth/v5
```

```go
import (
    "github.com/go-chi/chi/v5"
    "github.com/go-chi/jwtauth/v5"
)

tokenAuth := jwtauth.New("HS256", []byte("secret"), nil)

r := chi.NewRouter()
r.Use(jwtauth.Verifier(tokenAuth))

r.Route("/admin", func(r chi.Router) {
    r.Use(jwtauth.Authenticator)
    r.Get("/dashboard", adminHandler)
})
```

### Rate Limiting

**go-chi/httprate** - Rate limiting middleware

```bash
go get github.com/go-chi/httprate
```

```go
import "github.com/go-chi/httprate"

r := chi.NewRouter()

// 100 requests per minute per IP
r.Use(httprate.LimitByIP(100, 1*time.Minute))

// Or by custom key
r.Use(httprate.LimitByRealIP(100, 1*time.Minute))
```

### Request Logging

**go-chi/httplog** - Structured logging middleware

```bash
go get github.com/go-chi/httplog/v2
```

```go
import "github.com/go-chi/httplog/v2"

logger := httplog.NewLogger("myapp", httplog.Options{
    LogLevel: slog.LevelInfo,
})

r := chi.NewRouter()
r.Use(httplog.RequestLogger(logger))
```

### Request Rendering

**go-chi/render** - Response rendering helpers

```bash
go get github.com/go-chi/render
```

```go
import "github.com/go-chi/render"

type User struct {
    ID   int    `json:"id"`
    Name string `json:"name"`
}

func (u User) Render(w http.ResponseWriter, r *http.Request) error {
    return nil
}

r.Get("/users/{id}", func(w http.ResponseWriter, r *http.Request) {
    user := User{ID: 1, Name: "Alice"}
    render.Render(w, r, user)
})
```

## Integration Examples

### Combining Multiple Extensions

```go
import (
    "github.com/go-chi/chi/v5"
    "github.com/go-chi/chi/v5/middleware"
    "github.com/go-chi/cors"
    "github.com/go-chi/jwtauth/v5"
    "github.com/go-chi/httprate"
)

func main() {
    r := chi.NewRouter()

    // Standard middleware
    r.Use(middleware.Logger)
    r.Use(middleware.Recoverer)
    r.Use(middleware.RequestID)

    // CORS
    r.Use(cors.Handler(cors.Options{
        AllowedOrigins: []string{"https://*"},
    }))

    // Rate limiting
    r.Use(httprate.LimitByIP(1000, 1*time.Minute))

    // Public routes
    r.Get("/health", healthHandler)

    // Protected routes
    r.Route("/api", func(r chi.Router) {
        r.Use(jwtauth.Verifier(tokenAuth))
        r.Use(jwtauth.Authenticator)
        r.Get("/users", getUsers)
    })

    http.ListenAndServe(":8080", r)
}
```

### With Database Integration

```go
import (
    "database/sql"
    "github.com/go-chi/chi/v5"
)

func DBMiddleware(db *sql.DB) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            ctx := context.WithValue(r.Context(), "db", db)
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}

func main() {
    db, _ := sql.Open("postgres", dsn)
    defer db.Close()

    r := chi.NewRouter()
    r.Use(DBMiddleware(db))

    r.Get("/users", func(w http.ResponseWriter, r *http.Request) {
        db := r.Context().Value("db").(*sql.DB)
        // Use db...
    })
}
```

## Alternative/Complementary Packages

### Other Routers for Comparison

While chi excels at composition and maintainability, other routers may suit different needs:

- **HttpRouter** - Highest performance, less flexible
- **Gorilla Mux** - More feature-rich regex matching
- **Echo** - Full-featured framework with integrated middleware
- **Gin** - High performance, opinionated framework
- **Fiber** - Express.js-like API for Go

### Complementary Packages

**Validation Libraries:**
- `github.com/go-playground/validator` - Struct validation
- `github.com/asaskevich/govalidator` - String validation

**JSON Processing:**
- `github.com/json-iterator/go` - Fast JSON parsing
- `github.com/goccy/go-json` - JSON with custom types

**Testing:**
- `github.com/stretchr/testify` - Rich assertion library
- `github.com/golang/mock` - Mock generation

**Documentation:**
- `github.com/swaggo/swag` - Swagger/OpenAPI generation
- `github.com/caarlos0/env` - Environment configuration

## Plugin Architecture

### Creating Reusable Router Packages

Organize complex APIs as composable router packages:

```go
// myapi/router.go
package myapi

import "github.com/go-chi/chi/v5"

type API struct {
    db *sql.DB
}

func (api *API) Router() chi.Router {
    r := chi.NewRouter()
    r.Use(api.dbMiddleware)
    r.Get("/users", api.listUsers)
    r.Post("/users", api.createUser)
    return r
}

func NewAPI(db *sql.DB) *API {
    return &API{db: db}
}

// main.go
func main() {
    db, _ := sql.Open("postgres", dsn)
    r := chi.NewRouter()
    r.Mount("/api", NewAPI(db).Router())
    http.ListenAndServe(":8080", r)
}
```

## Community Resources

### Official Resources
- **GitHub**: https://github.com/go-chi/chi
- **Documentation**: https://go-chi.io/
- **Docs Repository**: https://github.com/go-chi/docs

### Learning Resources
- **Examples**: https://github.com/go-chi/chi/tree/master/_examples
- **Issue Tracker**: Community discussions and solutions
- **Godoc**: https://pkg.go.dev/github.com/go-chi/chi/v5

### Popular Third-Party Packages
- Data validation
- Rate limiting
- Caching
- Logging
- Metrics collection
- OpenAPI/Swagger generation
