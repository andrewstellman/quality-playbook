# Chi HTTP Router - Complete Documentation Collection

This directory contains comprehensive documentation for the [go-chi/chi](https://github.com/go-chi/chi) HTTP router, a lightweight, idiomatic, and composable router for building Go HTTP services.

## Documentation Contents

### Getting Started

1. **[01_overview_and_introduction.md](01_overview_and_introduction.md)**
   - What is Chi and why use it
   - Key characteristics and design philosophy
   - Installation and quick start example
   - Performance characteristics

2. **[02_routing_fundamentals.md](02_routing_fundamentals.md)**
   - Basic route definition and HTTP methods
   - URL pattern syntax (named parameters, regex, wildcards)
   - Handler signatures and patterns
   - Route ordering and specificity

### Core Functionality

3. **[03_middleware_system.md](03_middleware_system.md)**
   - Middleware fundamentals and patterns
   - Global vs route-specific middleware
   - Built-in middleware overview
   - Custom middleware with context values
   - Middleware composition and ordering

4. **[04_routing_organization.md](04_routing_organization.md)**
   - Route grouping with `Route()` and `Group()`
   - Mounting sub-routers with `Mount()`
   - Complete RESTful API example
   - Domain-based organization strategies
   - Composition patterns for large applications

5. **[05_context_and_values.md](05_context_and_values.md)**
   - Chi's route context and URL parameters
   - Adding request-scoped values
   - Type-safe context keys (best practice)
   - Timeouts with context
   - Context patterns and best practices

### Practical Guidance

6. **[06_error_handling.md](06_error_handling.md)**
   - Default error responses (404, 405)
   - Custom NotFound and MethodNotAllowed handlers
   - Panic recovery middleware
   - Custom error handling middleware
   - Validation and error responses
   - Common issues and solutions

7. **[07_testing_chi_applications.md](07_testing_chi_applications.md)**
   - Basic testing with httptest
   - Table-driven tests
   - Testing with context values
   - Testing URL parameters
   - Testing error cases and middleware
   - Integration tests with databases
   - Testing best practices

8. **[08_examples_and_patterns.md](08_examples_and_patterns.md)**
   - Complete REST API example
   - Pagination middleware
   - CORS middleware example
   - Request logging patterns
   - API versioning
   - Health check endpoint
   - Admin routes with authentication
   - File upload handling
   - Request body binding and validation
   - Graceful shutdown

### Reference and Performance

9. **[09_performance_and_best_practices.md](09_performance_and_best_practices.md)**
   - Performance characteristics (Patricia Radix Trie)
   - Performance best practices
   - Common pitfalls and solutions
   - Monitoring and debugging
   - Request ID tracking

10. **[10_changelog_and_versions.md](10_changelog_and_versions.md)**
    - Major version timeline (v1-v5)
    - Upgrade paths between versions
    - Known issues and resolutions
    - Go version support
    - Version selection recommendations

### Ecosystem and Extensions

11. **[11_ecosystem_and_extensions.md](11_ecosystem_and_extensions.md)**
    - Official chi packages (middleware, render, docgen)
    - Community packages (CORS, JWT, rate limiting, logging)
    - Integration examples
    - Creating reusable router packages
    - Community resources and learning materials

### Advanced Topics

12. **[12_advanced_topics.md](12_advanced_topics.md)**
    - Route matching internals (Patricia Radix Trie)
    - Custom HTTP methods
    - Route context deep dive
    - Nested route parameters
    - Middleware wrapping and composition
    - Response wrapper patterns
    - Dynamic route registration
    - Performance profiling
    - Structured logging and metrics

### API Reference

13. **[13_api_reference.md](13_api_reference.md)**
    - Complete Mux type reference
    - Router interface methods
    - Routes interface and matching
    - Context type and methods
    - URL parameters and RouteParams
    - Middlewares type and composition
    - Route type definition
    - Utility functions

14. **[14_middleware_reference.md](14_middleware_reference.md)**
    - Request/response middleware (Logger, Recoverer, RequestID, RealIP)
    - Compression middleware
    - Timeout middleware
    - Authentication middleware (BasicAuth)
    - Content negotiation
    - Response headers
    - Path middleware
    - Health checks
    - Rate limiting and throttling
    - Middleware ordering best practices

### Resources

15. **[sources.md](sources.md)**
    - Complete list of 56 sources
    - Official chi resources
    - Tutorials and educational materials
    - Advanced topics references
    - Performance and comparison articles
    - GitHub issues and discussions
    - Related utilities and tools

## How to Use This Documentation

### For Beginners

1. Start with **01_overview_and_introduction.md** to understand what chi is
2. Read **02_routing_fundamentals.md** to learn basic routing
3. Follow **03_middleware_system.md** for middleware concepts
4. Study **08_examples_and_patterns.md** for practical patterns
5. Work through **07_testing_chi_applications.md** to test your code

### For Building APIs

1. Review **04_routing_organization.md** for structuring large applications
2. Study **08_examples_and_patterns.md** for REST patterns
3. Reference **06_error_handling.md** for error responses
4. Use **13_api_reference.md** as a quick lookup guide

### For Advanced Users

1. Explore **12_advanced_topics.md** for internal mechanisms
2. Reference **14_middleware_reference.md** for all middleware options
3. Study **11_ecosystem_and_extensions.md** for extending chi
4. Review **09_performance_and_best_practices.md** for optimization

### Quick Lookups

- **API Reference**: See **13_api_reference.md** and **14_middleware_reference.md**
- **Examples**: See **08_examples_and_patterns.md**
- **Common Patterns**: See **03_middleware_system.md** and **04_routing_organization.md**
- **Testing**: See **07_testing_chi_applications.md**
- **Troubleshooting**: See **06_error_handling.md** and **09_performance_and_best_practices.md**

## Key Concepts Summary

### Chi's Design Philosophy

- **Lightweight**: ~1000 lines of core router code
- **Idiomatic**: Uses Go standard library patterns exclusively
- **Composable**: Middleware and routers compose cleanly
- **Production-Ready**: Used by Pressly, Cloudflare, Heroku, and others
- **Stdlib Compatible**: 100% compatible with net/http

### Core Components

- **Mux**: The main router type
- **Router Interface**: Methods for configuring routes and middleware
- **Middleware**: Functions that wrap handlers
- **Context**: Request-scoped values via Go's context package
- **Routes**: Interface for route matching and inspection

### Common Patterns

1. **Route Groups**: Organize routes by domain/feature
2. **Middleware Stack**: Apply cross-cutting concerns
3. **Error Handling**: Custom NotFound and MethodNotAllowed
4. **Context Values**: Pass request-scoped data through middleware
5. **Composable Routers**: Mount smaller routers into larger ones

## Quick Reference

### Basic Setup
```go
r := chi.NewRouter()
r.Use(middleware.Logger)
r.Get("/users", listUsers)
http.ListenAndServe(":8080", r)
```

### Route Organization
```go
r.Route("/api/v1", func(r chi.Router) {
    r.Get("/users", listUsers)
    r.Post("/users", createUser)
})
```

### Middleware
```go
r.Use(middleware.Logger)
r.With(paginate).Get("/items", listItems)
```

### URL Parameters
```go
r.Get("/users/{id}", func(w http.ResponseWriter, r *http.Request) {
    id := chi.URLParam(r, "id")
})
```

### Context Values
```go
func middleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        ctx := context.WithValue(r.Context(), "key", "value")
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}
```

## About Chi

**Project**: go-chi/chi
**Repository**: https://github.com/go-chi/chi
**Documentation**: https://go-chi.io/
**Current Version**: v5.x
**Go Versions Supported**: Four most recent major versions (1.21+)
**License**: MIT

## Documentation Notes

This documentation was compiled from:
- Official chi repository and documentation
- 56+ sources including tutorials, articles, and community resources
- Real-world usage patterns and examples
- GitHub issues and discussions

All code examples are production-ready and follow Go best practices. References to specific issues or versions are current as of April 2026.

## Learning Path

```
Beginner Path:
01 → 02 → 03 → 08 → 07

Intermediate Path:
01 → 02 → 03 → 04 → 05 → 06 → 08

Advanced Path:
11 → 12 → 13 → 14 → 09 → 10

API Developer Path:
01 → 02 → 04 → 13 → 14 → 08

Troubleshooting Path:
06 → 09 → 12 → sources.md
```

---

For the most current information, visit [https://github.com/go-chi/chi](https://github.com/go-chi/chi) and [https://go-chi.io/](https://go-chi.io/).
