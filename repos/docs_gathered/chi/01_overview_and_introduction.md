# Chi Router - Overview and Introduction

## What is Chi?

Chi is a **lightweight, idiomatic, and composable HTTP router** for building Go services. It's specifically designed to help you write large REST API services that remain maintainable as your project grows.

## Key Characteristics

- **Lightweight**: Core router is approximately 1,000 lines of code
- **100% Standard Library Compatible**: Built on Go's standard `net/http` package
- **No External Dependencies**: Relies only on Go's standard library
- **Built on Context Package**: Leverages Go 1.7+ `context` package for request-scoped values, cancellation, and timeouts
- **Production-Ready**: Used in production by Pressly, Cloudflare, Heroku, and 99Designs

## Design Philosophy

Chi emphasizes several core principles:

1. **Project Structure** - Organize APIs into logical, maintainable components
2. **Maintainability** - Keep code clean and understandable as it scales
3. **Standard HTTP Handlers** - Use stdlib-only patterns, no framework-specific abstractions
4. **Developer Productivity** - Make it easy and efficient to build APIs
5. **Modularity** - Deconstruct large systems into many small, composable parts

## Installation

```bash
go get -u github.com/go-chi/chi/v5
```

## Quick Start Example

```go
package main

import (
    "net/http"
    "github.com/go-chi/chi/v5"
    "github.com/go-chi/chi/v5/middleware"
)

func main() {
    r := chi.NewRouter()

    // Add middleware
    r.Use(middleware.Logger)
    r.Use(middleware.Recoverer)

    // Define routes
    r.Get("/", func(w http.ResponseWriter, r *http.Request) {
        w.Write([]byte("Hello World"))
    })

    // Start server
    http.ListenAndServe(":3000", r)
}
```

## Why Choose Chi?

Chi is ideal for:
- Building RESTful APIs with clean structure
- Microservices that need lightweight routing
- Projects where maintainability and code organization matter
- Teams familiar with Go's standard library patterns
- Applications needing middleware composition
- Cases where performance is important but not the primary concern

## Versions

- **v5.x** (Current) - Module-based versioning with `github.com/go-chi/chi/v5`
- **v4.x** - Previous stable version
- **v3.x** - Earlier version with flexible routing patterns
- Supports the 4 most recent major versions of Go
