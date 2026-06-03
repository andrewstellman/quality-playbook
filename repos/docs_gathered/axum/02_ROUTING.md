# Axum Routing System

**Source:** https://docs.rs/axum/latest/axum/routing/
**Version:** 0.8.8+
**Accessed:** April 2026

## Overview

The routing system in Axum is built on the Router struct, which implements Tower's Service trait. Routes map HTTP requests to handlers based on:

1. Request method (GET, POST, PUT, DELETE, etc.)
2. Request path with optional path parameter extraction
3. Fallback behavior for unmatched routes

Routes are declarative and macro-free, using builder pattern composition.

## Router Struct

The Router is the primary building block for HTTP dispatch. It:

- Implements `tower::Service<Request<Body>>`
- Owns registered routes and their handlers
- Stores optional application state
- Manages middleware layers at router and route levels
- Is itself a handler that can be nested

### Creating Routers

```rust
// Empty router
let router = Router::new();

// Router with initial route
let router = Router::new()
    .route("/", get(handler))
    .route("/users/:id", get(user_handler));

// Router with state
let state = AppState { db: Arc::new(db) };
let router = Router::new()
    .route("/", get(index))
    .with_state(state);
```

## Route Registration

Routes are registered using `.route(path, handler)` where the handler can be:

- A single method handler: `get(handler)`, `post(handler)`, `put(handler)`, etc.
- A MethodRouter from method combinators: `get(h1).post(h2).put(h3)`
- A nested Router
- Any Tower Service

### Path Syntax

Paths use a simple syntax for parameters:

- `/` - Root path
- `/users` - Literal path segment
- `/users/:id` - Path parameter (captured as `Path<IdParam>`)
- `/files/:path` - Greedy path parameter (captures remaining segments)
- `/` and `/foo` are different (trailing slash matters)

Path parameters are extracted via the `Path<T>` extractor with serde deserialization.

### Method Routing Functions

The module provides functions for common HTTP methods:

```
get(handler)      → GET requests only
post(handler)     → POST requests only
put(handler)      → PUT requests only
delete(handler)   → DELETE requests only
patch(handler)    → PATCH requests only
head(handler)     → HEAD requests only
options(handler)  → OPTIONS requests only
connect(handler)  → CONNECT requests only
trace(handler)    → TRACE requests only
```

These return a MethodRouter that can be:
- Chained with other method handlers
- Used as a route handler
- Layered with middleware

### Method Router Composition

```rust
let user_routes = get(get_user)
    .post(create_user)
    .put(update_user)
    .delete(delete_user);

let router = Router::new()
    .route("/users/:id", user_routes);
```

## Nesting and Route Organization

Nested routers enable hierarchical organization and middleware scoping:

```rust
let user_router = Router::new()
    .route("/:id", get(get_user))
    .route("/:id/posts", get(user_posts))
    .layer(middleware::axum_authn);  // Only for /users routes

let router = Router::new()
    .nest("/users", user_router)
    .nest("/posts", post_router)
    .route("/", get(index));
```

### Nesting Behavior

When a router is nested at a prefix:

1. The nested router receives requests matching the prefix
2. The prefix is stripped from the path before routing inside the nested router
3. Middleware on nested routers only applies to routes within that router
4. Middleware on parent routers applies to all nested routes
5. If nested router finds no match, parent router's fallback is used

Important: Nesting differs from mounting at a prefix route—nested routers participate in routing, while routes with `:path` parameters capture remaining path segments.

## Fallback Handling

The `.fallback(handler)` method specifies behavior for unmatched routes:

```rust
let router = Router::new()
    .route("/", get(index))
    .route("/users/:id", get(user))
    .fallback(not_found_handler);
```

### Fallback Behavioral Contracts

1. Fallback only executes if no route matches the path exactly
2. Fallback receives the full unmatched request
3. Router without fallback returns a built-in 404 response
4. Fallback takes the request as-is (path not modified)
5. Method not allowed (405) is a route match, not a fallback trigger
6. Fallback can return any `IntoResponse` type

Contrast with `MethodRouter::fallback()` which handles method mismatches:

```rust
let handler = get(handler1)
    .post(handler2)
    .fallback(method_not_allowed);  // For unhandled methods
```

## Middleware Application

Middleware can be applied at multiple scopes:

### Router-Level Middleware

`.layer()` applies middleware to all routes in the router:

```rust
let router = Router::new()
    .route("/", get(index))
    .layer(middleware::cors)
    .layer(middleware::logging);
```

### Route-Level Middleware

`.route_layer()` applies middleware to specific routes only:

```rust
let router = Router::new()
    .route("/public", get(public_handler))
    .route("/admin", get(admin_handler))
    .route_layer(middleware::admin_auth);  // Only on /admin
```

### Handler-Level Middleware

Individual handlers can layer middleware using the Handler trait:

```rust
async fn protected_handler() -> String {
    "admin content".into()
}

let handler = protected_handler
    .layer(middleware::auth_check);

let router = Router::new()
    .route("/admin", handler);
```

### Middleware Ordering Rules

With multiple layers:

```rust
router
    .layer(cors_layer)          // Applied 4th (outermost)
    .layer(compression_layer)   // Applied 3rd
    .route_layer(auth_layer)    // Applied 2nd
    .layer(logging_layer)       // Applied 1st (innermost)
```

Requests flow: logging → auth (route-specific) → compression → cors → handler → (reverse)

## State Management with Router

State is provided at the time a router is finalized:

```rust
let state = AppState { db: pool };

let router = Router::new()
    .route("/", get(index))
    .route("/users/:id", get(get_user))
    .with_state(state);
```

### State Access in Routes

Once state is set via `.with_state()`, handlers can access it:

```rust
async fn get_user(
    State(state): State<AppState>,
    Path(id): Path<u32>,
) -> Json<User> {
    // state is available and type-safe
}
```

### Multiple Router Instances

Different routers can have different state:

```rust
let api_router = Router::new()
    .route("/data", get(api_handler))
    .with_state(api_state);

let admin_router = Router::new()
    .route("/users", get(admin_handler))
    .with_state(admin_state);

// Combine via service composition
```

## Route Matching and Conflict Resolution

### Matching Order

1. Literal path segments are matched exactly
2. Path parameters (`:param`) match single segments
3. Greedy path parameters (`:path`) match multiple segments
4. Longest matching prefix wins in case of conflicts

### Conflicts Resolution

Axum uses a priority system:

- `/users/special` beats `/users/:id` for exact match
- `/users/:id/posts/:post_id` beats `/users/:id/:path` for the common prefix
- Routes registered later can override earlier routes (behavior may vary by version)

### 404 vs 405

- **404 Not Found** - No route matches the path
- **405 Method Not Allowed** - Path matches but method doesn't

A MethodRouter with no handler for the request method returns 405.

## Router as Service

Router implements Tower's Service trait:

```rust
impl Service<Request<Body>> for Router {
    type Response = Response<Body>;
    type Error = Infallible;
    type Future = /* ... */;
}
```

This enables:
- Routing incoming HTTP requests
- Composing routers with other services
- Using router in custom service layers
- Running router on custom HTTP servers

## Path Parameter Extraction

Path parameters are automatically extracted and deserialized:

```rust
#[derive(Deserialize)]
struct Params {
    id: u32,
}

async fn handler(Path(Params { id }): Path<Params>) -> String {
    format!("ID: {}", id)
}

let router = Router::new()
    .route("/users/:id", get(handler));
```

Type mismatch in path parameters causes extraction failure, returning 400.

## Critical Behaviors to Verify

1. **Path matching is exact** - `/users` and `/users/` are different
2. **Parameter capturing** - `/:id` captures to end of segment only, `:path` captures multiple
3. **Nesting strips prefix** - Nested router receives path without prefix
4. **Fallback is last resort** - Only called if no route matches
5. **Router is composable** - Can be used as a handler in another router
6. **Method routing is separate** - Path matching independent of method
7. **Middleware order matters** - Last `.layer()` is outermost (processes requests last)
8. **State is required** - Routes using `State<T>` require `.with_state()` to be called

## Known Issues and Edge Cases

1. **Trailing slashes** - No automatic redirect; `/users` ≠ `/users/`
2. **Path parameter greedy matching** - `:path` captures all remaining segments
3. **Conflicting routes** - Order of registration may affect resolution
4. **Nested router state** - Parent and nested routers have separate state contexts
5. **Method not allowed** - Requires matching MethodRouter to return 405

## Sources

- https://docs.rs/axum/latest/axum/routing/
- https://docs.rs/axum/latest/axum/struct.Router.html
- https://docs.rs/axum/latest/axum/routing/struct.MethodRouter.html
- https://github.com/tokio-rs/axum/tree/main/axum
