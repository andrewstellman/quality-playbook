# Axum Middleware System

**Source:** https://docs.rs/axum/latest/axum/middleware/
**Source:** https://github.com/tokio-rs/axum/blob/main/axum/src/docs/middleware.md
**Version:** 0.8.8+
**Accessed:** April 2026

## Overview

Axum does not implement its own middleware system. Instead, it integrates fully with **Tower**, the Rust ecosystem's standard service abstraction. This design provides several benefits:

1. Access to all Tower and tower-http middleware
2. Middleware written for Hyper or Tonic works with Axum
3. Composability with other Tower-based services
4. Mature, battle-tested implementations

The tradeoff is that middleware must respect Tower's abstractions and service patterns.

## Tower Service Abstraction

Middleware in Axum is built on Tower's Service trait:

```rust
pub trait Service<Request> {
    type Response;
    type Error;
    type Future: Future<Output = Result<Self::Response, Self::Error>>;
    
    fn call(&mut self, req: Request) -> Self::Future;
}
```

Each middleware layer is a Service that wraps an inner service. Requests flow through outer layers first, then the handler, then responses flow back outward.

## Middleware Application Levels

Middleware can be applied at multiple scope levels:

### Router-Level Middleware

`.layer()` applies middleware to all routes in a router:

```rust
let router = Router::new()
    .route("/", get(index))
    .route("/users", get(users))
    .layer(middleware::cors)
    .layer(middleware::logging);
```

All routes receive middleware in **reverse registration order**:
1. logging layer processes request first
2. cors layer processes request second
3. Handler executes
4. cors layer processes response
5. logging layer processes response

### Route-Level Middleware

`.route_layer()` applies middleware to specific routes only:

```rust
let protected = get(admin_handler)
    .route_layer(middleware::auth);

let public = get(public_handler);

let router = Router::new()
    .route("/admin", protected)
    .route("/public", public);
```

Route-level middleware only wraps the specific route's handler.

### Handler-Level Middleware

Individual handlers can layer middleware using the Handler trait:

```rust
async fn admin_handler() -> String {
    "admin".into()
}

let router = Router::new()
    .route("/admin",
        admin_handler
            .layer(middleware::auth)
    );
```

Handler-level middleware wraps only that handler.

## Middleware Ordering

### Layer Stacking Order

When middleware is stacked with multiple `.layer()` calls:

```rust
router
    .layer(logging_layer)      // Applied 1st (innermost)
    .layer(auth_layer)         // Applied 2nd
    .layer(cors_layer)         // Applied 3rd (outermost)
```

**Request flow:**
1. CORS middleware processes request
2. Auth middleware processes request
3. Logging middleware processes request
4. Handler executes
5. Logging middleware processes response
6. Auth middleware processes response
7. CORS middleware processes response

**Last registered layer is outermost** - receives requests first.

### ServiceBuilder Reversal

Tower's ServiceBuilder reverses the stacking order:

```rust
use tower::ServiceBuilder;

let middleware_stack = ServiceBuilder::new()
    .layer(cors_layer)         // Applied 3rd
    .layer(auth_layer)         // Applied 2nd
    .layer(logging_layer)      // Applied 1st (innermost)
    .into_inner();

router.layer(middleware_stack)
```

ServiceBuilder executes **top-to-bottom**, which many find more intuitive. The middleware closest to the handler is listed first.

## Writing Middleware with from_fn

The simplest approach for axum-specific middleware:

```rust
use axum::middleware::Next;

async fn logging_middleware(
    req: Request,
    next: Next,
) -> Response {
    println!("Request: {}", req.uri());
    let response = next.run(req).await;
    println!("Response: {}", response.status());
    response
}

let router = Router::new()
    .route("/", get(index))
    .layer(middleware::from_fn(logging_middleware));
```

Behavioral contract:
- Handler signature is `async fn(Request, Next) -> Response`
- Middleware must call `next.run(req).await` to proceed
- Can modify request before calling next
- Can modify response after calling next
- Only works with axum, not publishable as generic middleware

## Middleware with State

Access application state in middleware:

```rust
struct State {
    db: Arc<Database>,
}

async fn auth_middleware(
    State(state): State<Arc<State>>,
    mut req: Request,
    next: Next,
) -> Response {
    // Access state.db
    if !is_authed(&state, &req) {
        return StatusCode::UNAUTHORIZED.into_response();
    }
    next.run(req).await
}

let state = Arc::new(State { db });
let router = Router::new()
    .route("/", get(index))
    .layer(middleware::from_fn_with_state(state, auth_middleware));
```

Behavioral contract:
- First parameter must be `State(state)` extractor
- State must be Arc<T> or implement Clone
- State is passed to all middleware instances
- Same state available in handlers via State extractor

## Custom Tower Middleware

For publishable middleware or maximum control:

```rust
use tower::Layer;
use tower::Service;

#[derive(Clone)]
struct TimingLayer;

impl<S> Layer<S> for TimingLayer {
    type Service = TimingMiddleware<S>;
    
    fn layer(&self, inner: S) -> Self::Service {
        TimingMiddleware { inner }
    }
}

#[derive(Clone)]
struct TimingMiddleware<S> {
    inner: S,
}

impl<S> Service<Request<Body>> for TimingMiddleware<S>
where
    S: Service<Request<Body>, Response = Response> + Send + 'static,
    S::Future: Send + 'static,
{
    type Response = Response;
    type Error = S::Error;
    type Future = BoxFuture<'static, Result<Self::Response, Self::Error>>;
    
    fn poll_ready(&mut self, cx: &mut Context) -> Poll<Result<(), Self::Error>> {
        self.inner.poll_ready(cx)
    }
    
    fn call(&mut self, req: Request<Body>) -> Self::Future {
        let start = Instant::now();
        let future = self.inner.call(req);
        
        Box::pin(async move {
            let response = future.await?;
            let elapsed = start.elapsed();
            println!("Request took: {:?}", elapsed);
            Ok(response)
        })
    }
}

let router = Router::new()
    .route("/", get(index))
    .layer(TimingLayer);
```

Behavioral contract:
- Requires implementing both Layer and Service traits
- More boilerplate but enables maximum control
- Can be published as reusable crate
- Requires Pin and Future handling

## Built-in Middleware Functions

Axum provides utility functions for common patterns:

### from_fn

Simple async/await middleware (shown above).

### from_extractor

When middleware type also serves as extractor:

```rust
struct MyMiddleware {
    user_id: u32,
}

#[async_trait]
impl<S> FromRequestParts<S> for MyMiddleware
where
    S: Send + Sync,
{
    // Extractor impl
}

let router = Router::new()
    .route("/", get(index))
    .layer(middleware::from_extractor::<MyMiddleware>());
```

## Middleware Composition Patterns

### Before and After Processing

```rust
async fn timing(
    req: Request,
    next: Next,
) -> Response {
    let start = Instant::now();
    let response = next.run(req).await;  // Call inner service
    let elapsed = start.elapsed();
    // Can log, track metrics, etc.
    response
}
```

### Request Modification

```rust
async fn add_request_id(
    mut req: Request,
    next: Next,
) -> Response {
    let request_id = uuid::Uuid::new_v4();
    req.extensions_mut().insert(request_id);
    next.run(req).await
}
```

### Conditional Handling

```rust
async fn auth_check(
    req: Request,
    next: Next,
) -> Response {
    if req.uri().path().starts_with("/admin") {
        if !is_authenticated(&req) {
            return StatusCode::UNAUTHORIZED.into_response();
        }
    }
    next.run(req).await
}
```

### Error Handling

```rust
async fn handle_errors(
    req: Request,
    next: Next,
) -> Response {
    let response = next.run(req).await;
    
    if response.status().is_server_error() {
        eprintln!("Server error: {}", response.status());
    }
    
    response
}
```

## Important Behavioral Contracts

### Layer Ordering

1. Last `.layer()` call is outermost (processes requests last)
2. First `.layer()` call is innermost (closest to handler)
3. Requests flow outer → inner → handler → inner → outer
4. ServiceBuilder reverses this (top-to-bottom = outer-to-inner)

### Next Execution

1. Calling `next.run(req)` proceeds to next middleware/handler
2. Not calling `next` (short-circuits) is valid for auth failures
3. Multiple `next.run()` calls duplicate the inner service execution
4. Response from next can be modified before returning

### State Access

1. State in middleware must be Arc<T> or Clone
2. State must be provided via `.layer()` or `with_state()`
3. Same state instance shared with handlers
4. State changes in one handler don't affect others (Arc clones)

### Error Handling

1. Middleware must handle errors from inner service gracefully
2. Panic in middleware becomes 500 error
3. Some Tower middleware expects backpressure (Axum doesn't support—can cause issues)
4. Custom errors must implement IntoResponse or be converted

## Tower Middleware Compatibility

### Compatible Middleware

Tower middleware that work with Axum:

- `tower::ServiceBuilder` - Composition utility
- `tower_http::cors::CorsLayer` - CORS handling
- `tower_http::trace::TraceLayer` - Request/response tracing
- `tower_http::compression::CompressionLayer` - Response compression
- Custom Tower Services (with caveats)

### Incompatible Patterns

Some Tower middleware won't work with Axum:

- Backpressure-sensitive middleware (Axum ignores backpressure)
- Middleware expecting specific body types (Axum uses BoxBody)
- Streaming middleware with complex buffering

## Best Practices

1. **Order middleware thoughtfully** - Auth before business logic, logging outermost
2. **Use from_fn for simple cases** - Less boilerplate for axum-only middleware
3. **Implement custom Service for publishable middleware** - Enables reuse
4. **Handle errors gracefully** - Short-circuit on auth failures, log errors
5. **Avoid blocking in middleware** - Use async I/O for DB calls, etc.
6. **Keep middleware focused** - Single responsibility principle
7. **Use State for shared data** - Don't rely on thread-local storage

## Critical Behaviors to Verify

1. **Layer ordering** - Last added is outermost, processes requests first
2. **Next execution** - Must call `next.run()` to proceed
3. **State sharing** - State is shared as Arc<T> across all requests
4. **Error handling** - Errors must be converted to Response
5. **Middleware ordering effect on auth** - Auth layers must be before business logic
6. **Extension propagation** - Extensions set in middleware visible to handlers
7. **Panic handling** - Panics in middleware become 500 errors

## Known Issues and Edge Cases

1. **Backpressure incompatibility** - Some Tower middleware fail with Axum
2. **Request body consumption** - Body consumed by middleware unavailable to handler
3. **Nested routers and middleware** - Scope and application order can be confusing
4. **State type mismatches** - Wrong state type causes runtime errors
5. **from_fn type inference** - Complex generic scenarios may have inference issues
6. **ServiceBuilder clarity** - Ordering intuition differs from `.layer()` stacking

## Sources

- https://docs.rs/axum/latest/axum/middleware/
- https://github.com/tokio-rs/axum/blob/main/axum/src/docs/middleware.md
- https://docs.rs/tower/latest/tower/
- https://github.com/tokio-rs/axum/blob/main/examples/
