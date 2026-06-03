# Chi Router - Routing Organization (Groups, Subrouters, Mounting)

## Route Method

The `Route` method mounts a sub-router at a path pattern with its own middleware:

```go
r := chi.NewRouter()

// Mount articles subrouter
r.Route("/articles", func(r chi.Router) {
    r.Get("/", listArticles)           // GET /articles
    r.Post("/", createArticle)         // POST /articles
    r.Get("/{id}", getArticle)         // GET /articles/{id}
    r.Put("/{id}", updateArticle)      // PUT /articles/{id}
    r.Delete("/{id}", deleteArticle)   // DELETE /articles/{id}
})
```

## Group Method

The `Group` method creates an inline router with a fresh middleware stack:

```go
r := chi.NewRouter()
r.Use(middleware.Logger)  // Applied to all routes

r.Group(func(r chi.Router) {
    r.Use(middleware.BasicAuth)  // Only for this group
    r.Get("/admin", adminPanel)
    r.Get("/settings", settings)
})

// This route doesn't have BasicAuth
r.Get("/public", publicHandler)
```

## Mount Method

The `Mount` method attaches any `http.Handler` or chi Router as a subrouter:

```go
// Mount a static file server
r.Mount("/static", http.FileServer(http.Dir("static")))

// Mount another chi router
adminRouter := chi.NewRouter()
adminRouter.Get("/dashboard", dashboard)
adminRouter.Post("/users", createUser)

r.Mount("/admin", adminRouter)
```

## Complete RESTful API Example

A realistic organization pattern:

```go
package main

import (
    "net/http"
    "github.com/go-chi/chi/v5"
    "github.com/go-chi/chi/v5/middleware"
)

func main() {
    r := chi.NewRouter()

    // Global middleware
    r.Use(middleware.Logger)
    r.Use(middleware.Recoverer)
    r.Use(middleware.RequestID)

    // Public routes
    r.Get("/", homepage)
    r.Get("/health", healthCheck)

    // API v1
    r.Route("/api/v1", func(r chi.Router) {
        r.Route("/users", func(r chi.Router) {
            r.Get("/", listUsers)
            r.Post("/", createUser)
            r.Route("/{userID}", func(r chi.Router) {
                r.Use(userCtx)
                r.Get("/", getUser)
                r.Put("/", updateUser)
                r.Delete("/", deleteUser)

                // Nested: user's posts
                r.Route("/posts", func(r chi.Router) {
                    r.Get("/", listUserPosts)
                    r.Post("/", createUserPost)
                })
            })
        })

        r.Route("/posts", func(r chi.Router) {
            r.Get("/", listPosts)
            r.Post("/", createPost)
            r.Route("/{postID}", func(r chi.Router) {
                r.Use(postCtx)
                r.Get("/", getPost)
                r.Put("/", updatePost)
                r.Delete("/", deletePost)
            })
        })
    })

    // Protected admin routes
    r.Route("/admin", func(r chi.Router) {
        r.Use(adminAuth)
        r.Get("/dashboard", adminDashboard)
        r.Get("/users", allUsers)
        r.Post("/settings", updateSettings)
    })

    // Static files
    r.Mount("/static", http.FileServer(http.Dir("static")))

    http.ListenAndServe(":8080", r)
}

// Middleware for loading user context
func userCtx(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        userID := chi.URLParam(r, "userID")
        user := loadUser(userID)

        ctx := r.Context()
        ctx = context.WithValue(ctx, "user", user)

        next.ServeHTTP(w, r.WithContext(ctx))
    })
}

// Middleware for admin authentication
func adminAuth(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        token := r.Header.Get("Authorization")
        if !isValidAdminToken(token) {
            http.Error(w, "Forbidden", http.StatusForbidden)
            return
        }
        next.ServeHTTP(w, r)
    })
}
```

## Composition Strategies

### Separate Router Packages

Organize routers by domain:

```go
// users/routes.go
package users

func Router() chi.Router {
    r := chi.NewRouter()
    r.Get("/", ListUsers)
    r.Post("/", CreateUser)
    return r
}

// posts/routes.go
package posts

func Router() chi.Router {
    r := chi.NewRouter()
    r.Get("/", ListPosts)
    r.Post("/", CreatePost)
    return r
}

// main.go
func main() {
    r := chi.NewRouter()
    r.Mount("/users", users.Router())
    r.Mount("/posts", posts.Router())
    http.ListenAndServe(":8080", r)
}
```

### Middleware per Domain

```go
// posts/routes.go
func Router() chi.Router {
    r := chi.NewRouter()
    r.Use(PostMiddleware)  // Domain-specific middleware
    r.Get("/", ListPosts)
    r.Post("/", CreatePost)
    return r
}
```

## Benefits of Organization

- **Scalability**: Easy to add new routes and features
- **Testability**: Can test subrouters in isolation
- **Maintainability**: Clear structure as project grows
- **Modularity**: Each domain has its own router
- **Reusability**: Routers can be composed into larger applications
