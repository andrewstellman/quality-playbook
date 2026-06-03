# Chi Router - Common Patterns and Examples

## Complete REST API Example

```go
package main

import (
    "encoding/json"
    "net/http"
    "github.com/go-chi/chi/v5"
    "github.com/go-chi/chi/v5/middleware"
)

type Article struct {
    ID    string `json:"id"`
    Title string `json:"title"`
    Body  string `json:"body"`
}

var articles = map[string]Article{
    "1": {ID: "1", Title: "First", Body: "Content here"},
    "2": {ID: "2", Title: "Second", Body: "More content"},
}

func main() {
    r := chi.NewRouter()

    // Middleware
    r.Use(middleware.RequestID)
    r.Use(middleware.RealIP)
    r.Use(middleware.Logger)
    r.Use(middleware.Recoverer)

    // Routes
    r.Get("/", func(w http.ResponseWriter, r *http.Request) {
        w.Write([]byte("Welcome"))
    })

    r.Route("/articles", func(r chi.Router) {
        r.Get("/", listArticles)
        r.Post("/", createArticle)
        r.Route("/{id}", func(r chi.Router) {
            r.Get("/", getArticle)
            r.Put("/", updateArticle)
            r.Delete("/", deleteArticle)
        })
    })

    http.ListenAndServe(":8080", r)
}

func listArticles(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(articles)
}

func createArticle(w http.ResponseWriter, r *http.Request) {
    var a Article
    json.NewDecoder(r.Body).Decode(&a)
    articles[a.ID] = a
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(http.StatusCreated)
    json.NewEncoder(w).Encode(a)
}

func getArticle(w http.ResponseWriter, r *http.Request) {
    id := chi.URLParam(r, "id")
    article, exists := articles[id]
    if !exists {
        http.Error(w, "Not found", http.StatusNotFound)
        return
    }
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(article)
}

func updateArticle(w http.ResponseWriter, r *http.Request) {
    id := chi.URLParam(r, "id")
    var a Article
    json.NewDecoder(r.Body).Decode(&a)
    a.ID = id
    articles[id] = a
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(a)
}

func deleteArticle(w http.ResponseWriter, r *http.Request) {
    id := chi.URLParam(r, "id")
    delete(articles, id)
    w.WriteHeader(http.StatusNoContent)
}
```

## Pagination Middleware

```go
import "strconv"

type Paginated struct {
    Page  int
    Limit int
}

func Paginate(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        pageStr := r.URL.Query().Get("page")
        limitStr := r.URL.Query().Get("limit")

        page := 1
        limit := 10

        if p, err := strconv.Atoi(pageStr); err == nil && p > 0 {
            page = p
        }
        if l, err := strconv.Atoi(limitStr); err == nil && l > 0 && l <= 100 {
            limit = l
        }

        ctx := context.WithValue(r.Context(), "pagination", Paginated{page, limit})
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}

// Usage
r.With(Paginate).Get("/articles", func(w http.ResponseWriter, r *http.Request) {
    p := r.Context().Value("pagination").(Paginated)
    // Use p.Page and p.Limit
})
```

## CORS Middleware Example

```go
func CORS(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Access-Control-Allow-Origin", "*")
        w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

        if r.Method == http.MethodOptions {
            w.WriteHeader(http.StatusOK)
            return
        }

        next.ServeHTTP(w, r)
    })
}

r.Use(CORS)
```

## Request Logging with Custom Format

```go
import "log"
import "time"

func CustomLogger(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        start := time.Now()

        // Wrap response to capture status
        wrapped := &statusRecorder{ResponseWriter: w, statusCode: 200}

        next.ServeHTTP(wrapped, r)

        duration := time.Since(start)
        log.Printf(
            "[%s] %s %s %d %dms",
            time.Now().Format("2006-01-02 15:04:05"),
            r.Method,
            r.RequestURI,
            wrapped.statusCode,
            duration.Milliseconds(),
        )
    })
}

type statusRecorder struct {
    http.ResponseWriter
    statusCode int
}

func (sr *statusRecorder) WriteHeader(code int) {
    sr.statusCode = code
    sr.ResponseWriter.WriteHeader(code)
}

r.Use(CustomLogger)
```

## API Versioning

```go
func main() {
    r := chi.NewRouter()

    // V1 API
    r.Route("/api/v1", func(r chi.Router) {
        r.Get("/users", listUsersV1)
        r.Get("/posts", listPostsV1)
    })

    // V2 API (different handlers)
    r.Route("/api/v2", func(r chi.Router) {
        r.Get("/users", listUsersV2)
        r.Get("/posts", listPostsV2)
    })

    http.ListenAndServe(":8080", r)
}

func listUsersV1(w http.ResponseWriter, r *http.Request) {
    // V1 format
}

func listUsersV2(w http.ResponseWriter, r *http.Request) {
    // V2 format with enhanced features
}
```

## Health Check Endpoint

```go
func HealthCheck(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        if r.URL.Path == "/health" {
            w.Header().Set("Content-Type", "application/json")
            json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
            return
        }
        next.ServeHTTP(w, r)
    })
}

// Or simpler
r.Get("/health", func(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
})
```

## Admin Routes with Authentication

```go
func AdminAuth(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        token := r.Header.Get("X-Admin-Token")

        if !validateAdminToken(token) {
            http.Error(w, "Forbidden", http.StatusForbidden)
            return
        }

        next.ServeHTTP(w, r)
    })
}

func main() {
    r := chi.NewRouter()

    r.Route("/admin", func(r chi.Router) {
        r.Use(AdminAuth)
        r.Get("/users", adminListUsers)
        r.Post("/settings", adminUpdateSettings)
    })
}
```

## File Upload Handler

```go
func uploadFile(w http.ResponseWriter, r *http.Request) {
    // Parse multipart form with 10MB max size
    if err := r.ParseMultipartForm(10 << 20); err != nil {
        http.Error(w, "File too large", http.StatusBadRequest)
        return
    }

    file, handler, err := r.FormFile("file")
    if err != nil {
        http.Error(w, "Missing file", http.StatusBadRequest)
        return
    }
    defer file.Close()

    // Validate file size
    if handler.Size > 5<<20 { // 5MB
        http.Error(w, "File too large", http.StatusBadRequest)
        return
    }

    // Save file
    dst, err := os.Create("./uploads/" + handler.Filename)
    if err != nil {
        http.Error(w, "Save failed", http.StatusInternalServerError)
        return
    }
    defer dst.Close()

    io.Copy(dst, file)

    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(map[string]string{
        "filename": handler.Filename,
        "size":     fmt.Sprintf("%d", handler.Size),
    })
}

r.Post("/upload", uploadFile)
```

## Request Body Binding with Validation

```go
type CreateUserRequest struct {
    Name  string `json:"name" validate:"required,min=2,max=100"`
    Email string `json:"email" validate:"required,email"`
}

func createUser(w http.ResponseWriter, r *http.Request) {
    var req CreateUserRequest

    // Decode JSON
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        http.Error(w, "Invalid JSON", http.StatusBadRequest)
        return
    }

    // Validate (using a validation library)
    if req.Name == "" || req.Email == "" {
        http.Error(w, "Name and Email required", http.StatusBadRequest)
        return
    }

    // Process
    user := User{
        ID:    generateID(),
        Name:  req.Name,
        Email: req.Email,
    }

    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(http.StatusCreated)
    json.NewEncoder(w).Encode(user)
}
```

## Graceful Shutdown

```go
import "context"
import "os/signal"
import "syscall"

func main() {
    r := chi.NewRouter()
    r.Get("/", func(w http.ResponseWriter, r *http.Request) {
        w.Write([]byte("Hello"))
    })

    srv := &http.Server{
        Addr:    ":8080",
        Handler: r,
    }

    // Run in goroutine
    go func() {
        if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            panic(err)
        }
    }()

    // Wait for interrupt signal
    quit := make(chan os.Signal, 1)
    signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
    <-quit

    // Graceful shutdown with timeout
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()

    if err := srv.Shutdown(ctx); err != nil {
        log.Fatalf("Server forced to shutdown: %v", err)
    }
}
```
