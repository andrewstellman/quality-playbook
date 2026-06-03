# Chi Router - Core API Reference

## Mux Type

The main router type implementing both `http.Handler` and the `Router` interface.

```go
type Mux struct {
    // Unexported fields
}
```

### Constructor

```go
func NewRouter() *Mux
func NewMux() *Mux
```

Both functions create and return a new `*Mux` instance. They are equivalent.

## Router Interface

Main interface for configuring and using the router.

```go
type Router interface {
    http.Handler
    Routes

    // Middleware
    Use(middlewares ...func(http.Handler) http.Handler) Router
    With(middlewares ...func(http.Handler) http.Handler) Router

    // Route grouping
    Group(fn func(r Router)) Router
    Route(pattern string, fn func(r Router)) Router
    Mount(pattern string, h http.Handler)

    // Route registration
    Handle(pattern string, h http.Handler)
    HandleFunc(pattern string, h http.HandlerFunc)
    Method(method, pattern string, h http.Handler)
    MethodFunc(method, pattern string, h http.HandlerFunc)

    // HTTP method shortcuts
    Connect(pattern string, h http.HandlerFunc)
    Delete(pattern string, h http.HandlerFunc)
    Get(pattern string, h http.HandlerFunc)
    Head(pattern string, h http.HandlerFunc)
    Options(pattern string, h http.HandlerFunc)
    Patch(pattern string, h http.HandlerFunc)
    Post(pattern string, h http.HandlerFunc)
    Put(pattern string, h http.HandlerFunc)
    Trace(pattern string, h http.HandlerFunc)

    // Error handling
    NotFound(h http.HandlerFunc)
    MethodNotAllowed(h http.HandlerFunc)
}
```

### Middleware Methods

#### `Use(middlewares ...func(http.Handler) http.Handler) Router`

Appends middlewares to the current router's middleware stack. These middlewares apply to all routes defined on this router and its subrouters.

```go
r := chi.NewRouter()
r.Use(middleware.Logger)
r.Use(middleware.Recoverer)
```

#### `With(middlewares ...func(http.Handler) http.Handler) Router`

Returns a new router with additional middlewares applied only to the next route(s) defined in the chain.

```go
r.With(paginate).Get("/items", listItems)  // Only listItems gets paginate middleware
```

### Route Grouping Methods

#### `Route(pattern string, fn func(r Router)) Router`

Mounts a sub-router at the given pattern with isolated middleware.

```go
r.Route("/api", func(r chi.Router) {
    r.Get("/users", listUsers)
    r.Post("/users", createUser)
})
```

#### `Group(fn func(r Router)) Router`

Creates an inline router with fresh middleware stack.

```go
r.Group(func(r chi.Router) {
    r.Use(authMiddleware)
    r.Get("/admin", adminPanel)
})
```

#### `Mount(pattern string, h http.Handler)`

Attaches any `http.Handler` or chi `Router` as a subrouter.

```go
r.Mount("/static", http.FileServer(http.Dir("static")))
r.Mount("/api", apiRouter)
```

### Route Registration Methods

#### `Handle(pattern string, h http.Handler)`

Register an http.Handler for all HTTP methods on the pattern.

```go
r.Handle("/users", userHandler)
```

#### `HandleFunc(pattern string, h http.HandlerFunc)`

Register an http.HandlerFunc for all HTTP methods on the pattern.

```go
r.HandleFunc("/users", userHandlerFunc)
```

#### `Method(method, pattern string, h http.Handler)`

Register an http.Handler for a specific HTTP method.

```go
r.Method("GET", "/users", getHandler)
r.Method("POST", "/users", postHandler)
```

#### `MethodFunc(method, pattern string, h http.HandlerFunc)`

Register an http.HandlerFunc for a specific HTTP method.

```go
r.MethodFunc("GET", "/users", getHandler)
```

### HTTP Method Shortcuts

All accept `pattern` and `h http.HandlerFunc` parameters.

```go
r.Get(pattern, h)
r.Post(pattern, h)
r.Put(pattern, h)
r.Delete(pattern, h)
r.Patch(pattern, h)
r.Head(pattern, h)
r.Options(pattern, h)
r.Connect(pattern, h)
r.Trace(pattern, h)
```

### Error Handler Methods

#### `NotFound(h http.HandlerFunc)`

Sets the handler for routes that don't match any pattern (404).

```go
r.NotFound(func(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusNotFound)
    w.Write([]byte("Not found"))
})
```

#### `MethodNotAllowed(h http.HandlerFunc)`

Sets the handler for routes that match but with wrong HTTP method (405).

```go
r.MethodNotAllowed(func(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusMethodNotAllowed)
    w.Write([]byte("Method not allowed"))
})
```

## Routes Interface

Provides read-only access to routing information.

```go
type Routes interface {
    Routes() []Route
    Middlewares() Middlewares
    Match(rctx *Context, method, path string) bool
    Find(rctx *Context, method, path string) string
}
```

### Methods

#### `Routes() []Route`

Returns a slice of all registered routes.

```go
routes := router.Routes()
for _, route := range routes {
    fmt.Println(route.Pattern)
}
```

#### `Middlewares() Middlewares`

Returns the middleware stack for this router.

#### `Match(rctx *Context, method, path string) bool`

Tests if a route matches the given method and path.

```go
matched := router.Routes().Match(rctx, "GET", "/users/123")
```

#### `Find(rctx *Context, method, path string) string`

Returns the matching route pattern or empty string if no match.

```go
pattern := router.Routes().Find(rctx, "GET", "/users/123")
// Returns "/users/{id}"
```

## Context Type

Request-scoped routing context attached by chi.

```go
type Context struct {
    Routes       Routes
    RoutePath    string
    RouteMethod  string
    URLParams    RouteParams
    RoutePatterns []string
}
```

### Methods

#### `NewRouteContext() *Context`

Creates a new route context (rarely used directly).

```go
rctx := chi.NewRouteContext()
```

#### `RouteContext(ctx context.Context) *Context`

Extracts the chi route context from a standard context.

```go
rctx := chi.RouteContext(r.Context())
```

#### `Reset()`

Resets the route context to initial state.

#### `RoutePattern() string`

Returns the matched route pattern.

```go
pattern := rctx.RoutePattern()  // "/users/{id}"
```

#### `URLParam(key string) string`

Returns the value of a URL parameter.

```go
id := rctx.URLParam("id")
```

## URL Parameters

### `URLParam(r *http.Request, key string) string`

Extracts a URL parameter value from the request.

```go
func handler(w http.ResponseWriter, r *http.Request) {
    id := chi.URLParam(r, "id")
    fmt.Fprintf(w, "ID: %s", id)
}
```

### `URLParamFromCtx(ctx context.Context, key string) string`

Extracts URL parameter from a context (advanced).

```go
id := chi.URLParamFromCtx(r.Context(), "id")
```

### RouteParams Type

```go
type RouteParams struct {
    Keys, Values []string
}

func (s *RouteParams) Add(key, value string)
```

Access all parameters:

```go
rctx := chi.RouteContext(r.Context())
for i, key := range rctx.URLParams.Keys {
    value := rctx.URLParams.Values[i]
    fmt.Printf("%s=%s\n", key, value)
}
```

## Middlewares Type

```go
type Middlewares []func(http.Handler) http.Handler

func Chain(middlewares ...func(http.Handler) http.Handler) Middlewares
func (mws Middlewares) Handler(h http.Handler) http.Handler
func (mws Middlewares) HandlerFunc(h http.HandlerFunc) http.Handler
```

### Chain Function

Creates a middleware chain.

```go
mws := chi.Chain(
    middleware.Logger,
    middleware.Recoverer,
)
```

### Handler and HandlerFunc Methods

Applies the middleware stack to a handler.

```go
mws := chi.Chain(middleware.Logger, middleware.Recoverer)
handler := mws.Handler(myHandler)
```

## Route Type

Represents a registered route in the router.

```go
type Route struct {
    Pattern string
    Handler http.Handler
}
```

## Utility Functions

### `Walk(r Routes, fn WalkFunc) error`

Walks all routes and calls fn for each.

```go
chi.Walk(router, func(method string, route string, handler http.Handler, middlewares ...func(http.Handler) http.Handler) error {
    fmt.Printf("[%s] %s\n", method, route)
    return nil
})
```

### `RegisterMethod(method string)`

Registers a custom HTTP method.

```go
chi.RegisterMethod("CUSTOM")
r.Method("CUSTOM", "/resource", handler)
```
