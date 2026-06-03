# Axum Behavioral Contracts and Edge Cases

**Source:** https://docs.rs/axum/latest/axum/
**Version:** 0.8.8+
**Accessed:** April 2026

## Overview

This document specifies the exact behavioral contracts that define Axum's operation. These are the precise rules that must be enforced for correct behavior, especially important for bug detection and specification auditing.

## Extractor Ordering and Type System Enforcement

### Contract: Parts-Before-Body Ordering

**Rule:** All FromRequestParts extractors must appear before any FromRequest (body-consuming) extractors in handler parameter lists.

**Mechanism:** Compile-time enforcement via trait system:
- FromRequest<S, ViaParts> is automatically implemented for FromRequestParts<S>
- This allows parts extractors to be used as FromRequest extractors
- But only when placed before actual body-consuming extractors
- Generic implementations prevent invalid combinations

**Verification:**

```rust
// VALID: Parts before body
async fn handler(
    Path(id): Path<u32>,           // FromRequestParts
    headers: HeaderMap,            // FromRequestParts
    State(state): State<T>,        // FromRequestParts (even though State is global)
    Json(body): Json<Data>,        // FromRequest - MUST be last
) { }

// INVALID: Would fail to compile
async fn handler(
    Json(body): Json<Data>,        // FromRequest
    Path(id): Path<u32>,           // ERROR: Parts after body
) { }
```

**Edge Case:** State extractor placement
- State<T> is technically a FromRequestParts extractor
- Can appear before body-consuming extractors
- Must be Arc<T> or implement Clone
- Multiple State<T> extractors allowed (for different types)

### Contract: Single Body Extractor Per Handler

**Rule:** Only one FromRequest (body-consuming) extractor allowed per handler.

**Mechanism:** Type system prevents multiple body consumers
- Attempting two Json<T> extractors fails to compile
- Attempting Json<T> and String together fails
- Attempting Json<T> and Bytes together fails

**Verification:**

```rust
// VALID: Single body extractor
async fn handler(Json(body): Json<Data>) -> Response { }

// INVALID: Multiple body extractors
async fn handler(
    Json(body): Json<Data>,
    String(raw): String,  // COMPILE ERROR
) { }
```

**Edge Case:** Body extraction in extractors vs handlers
- Custom extractors can consume body (implement FromRequest)
- Wrapping one body extractor in another causes double-consumption error

### Contract: Extractor Execution Order

**Rule:** Extractors run in parameter order (left-to-right), not by type or phase.

**Mechanism:** Code generation from handler signature
- Extractors are awaited sequentially in parameter order
- Order visible in expanded macro or trait implementation
- Not grouped by type (parts first) at runtime—that's compile-time

**Verification:**

```rust
async fn handler(
    a: Extractor1,  // Runs first
    b: Extractor2,  // Runs second
    c: Extractor3,  // Runs third (body extractor)
) { }

// Execution: a.from_request_parts(...).await
//           b.from_request_parts(...).await
//           c.from_request(...).await
```

**Edge Case:** Extractor side effects
- If extractors have side effects (logging, metrics), order matters
- Database queries in extractors execute in order
- Failed extractor stops subsequent execution

## Request Body Consumption Rules

### Contract: Body Consumed Once

**Rule:** The HTTP request body is an async stream that can only be consumed once. Only one extractor can access it.

**Mechanism:** Rust's type system ownership
- Body is moved out of Request
- Only one extractor can own it
- Compile-time prevention of double-consumption
- Type-level enforcement via SplitBody trait

**Verification:**

```rust
// CORRECT: Body consumed once
async fn handler(Json(body): Json<Data>) -> Response { }

// INVALID: Would fail to compile
async fn handler(
    body1: String,
    body2: Bytes,  // Can't consume body twice
) { }

// INVALID: Custom extractor double-consuming
struct BothBodies {
    text: String,
    bytes: Bytes,
}
// Implementing FromRequest would fail—can't consume body twice
```

**Edge Case:** Body extractor ordering
- Even if syntax allowed, body extraction must be last
- Path/Query don't consume body, can appear before
- Mixed usage: String for text body, Bytes for binary—choose one

### Contract: Body Limits and Size

**Rule:** Request body size limits are enforced at extractor level, not globally.

**Mechanism:** Extractor-specific limits
- Json<T> has default 100MB limit (configurable)
- String/Bytes have no built-in limit
- Query/Path have no body (no limit)
- CustomJsonRejection includes payload too large error

**Verification:**

```rust
// Rejects if body > 100MB (default for Json)
async fn handler(Json(data): Json<Data>) -> Response { }

// Rejects if body > 1MB (configured)
async fn handler(
    Json(data): Json<Data>,  // Would need config to change limit
) -> Response { }

// No limit
async fn handler(String(body): String) -> Response { }
```

**Edge Case:** Body size across multiple requests
- Each request can have full limit
- Previous request consumption doesn't affect next
- Per-request isolation guaranteed

## Routing and Path Matching Contracts

### Contract: Longest-Match-First Route Resolution

**Rule:** When multiple routes could match a path, the most specific (longest) match wins.

**Mechanism:** Trie-based router with specificity scoring
- `/users/special` beats `/users/:id` for path `/users/special`
- `/posts/:id/comments/:comment_id` beats `/posts/:id/:path`
- Exact literals > path parameters > greedy parameters

**Verification:**

```rust
let router = Router::new()
    .route("/users", get(all_users))          // Matches /users only
    .route("/users/:id", get(get_user))       // Matches /users/123
    .route("/users/special", get(special))    // Matches /users/special (wins vs :id)
    .fallback(not_found);

// GET /users/special → special handler
// GET /users/123 → get_user handler
// GET /users → all_users handler
// GET /users/123/posts → not_found (if no other routes)
```

**Edge Case:** Path parameter conflicts
- `/files/:id` and `/files/:path` both could match `/files/a/b`
- Longest matching segment wins (`:path` is greedy, comes last)
- Exact registration order might matter for equivalent specificity

### Contract: Nesting Preserves Path Hierarchy

**Rule:** Nested routers receive paths with prefix stripped; parent routing is not re-evaluated.

**Mechanism:** Path stripping at nesting point
- Parent router strips `/api` before forwarding to nested router
- Nested router sees path without prefix
- No re-matching against parent routes

**Verification:**

```rust
let api_router = Router::new()
    .route("/users", get(users_handler))
    .route("/:id", get(detail_handler));

let router = Router::new()
    .nest("/api", api_router)
    .route("/status", get(status_handler));

// GET /api/users → users_handler (nested router)
// GET /api/123 → detail_handler (nested router, :id = "123")
// GET /status → status_handler (parent router)
// GET /api/status → 404 (api router has no /status route)
```

**Edge Case:** Fallback in nested router
- If nested router has fallback, it handles unmatched paths
- If nested router has no fallback, parent router's fallback is used
- Fallback doesn't see the original path—sees path without prefix

### Contract: 404 vs 405 Distinction

**Rule:** 404 Not Found means path doesn't match any route. 405 Method Not Allowed means path matches but method doesn't.

**Mechanism:** Router distinguishes path and method matching
- Path matching checks route definitions
- Method matching checks MethodRouter handlers
- Path miss → 404 (unless fallback)
- Path hit but method miss → 405 (unless MethodRouter::fallback)

**Verification:**

```rust
let router = Router::new()
    .route("/users", get(list_users).post(create_user))
    .fallback(not_found);

// GET /users → 200 OK (matches route and method)
// POST /users → 200 OK (matches route and method)
// PUT /users → 405 Method Not Allowed (matches route, not method)
// GET /posts → 404 Not Found (route doesn't exist, fallback triggered)
```

**Edge Case:** Nested router method routing
- MethodRouter in nested router still returns 405 if method not found
- Fallback in nested router catches path misses, not method misses

### Contract: Trailing Slashes Are Significant

**Rule:** `/users` and `/users/` are different paths; no automatic redirect.

**Mechanism:** Exact path matching
- Routes are matched exactly as registered
- No normalization or redirect
- `/users` doesn't match `/users/` route

**Verification:**

```rust
let router = Router::new()
    .route("/users", get(handler1))
    .route("/users/", get(handler2));

// GET /users → handler1
// GET /users/ → handler2
// If only /users registered:
//   GET /users → 200
//   GET /users/ → 404 (no matching route)
```

**Edge Case:** Path parameter with trailing slash
- `/users/:id/` is different from `/users/:id`
- Explicit routes needed for each variant

## State Management Contracts

### Contract: State is Shared Across All Requests

**Rule:** State provided via `.with_state(T)` is wrapped in Arc<T> and shared by all handlers.

**Mechanism:** Arc<T> wrapped by framework
- State is cloned per request (cheaply, as Arc clone)
- Same state instance across all requests
- Modifications to Arc<T> contents are visible to all handlers
- State must be Send + Sync for thread safety

**Verification:**

```rust
struct AppState {
    counter: Arc<AtomicU32>,
}

async fn handler(State(state): State<AppState>) -> String {
    let count = state.counter.fetch_add(1, Ordering::SeqCst);
    format!("Count: {}", count)
}

let state = AppState {
    counter: Arc::new(AtomicU32::new(0)),
};

let router = Router::new()
    .route("/inc", get(handler))
    .with_state(state);

// Each request increments same counter
// All handlers see updated value
```

**Edge Case:** State type variations
- State<T> requires Router::with_state() to be called
- Missing with_state() causes compile error
- Wrong state type also causes compile error (caught at compile time)

### Contract: State Extraction Cannot Fail

**Rule:** If State<T> is declared, T must be provided via with_state(). Extraction never produces rejection.

**Mechanism:** Type system enforcement
- State type mismatch detected at compile time
- Missing state also detected at compile time
- Cannot wrap State<T> in Result—not a fallible extractor

**Verification:**

```rust
async fn handler(State(state): State<AppState>) -> Response { }

// Compile error: AppState not in scope if not provided
let router = Router::new()
    .route("/", get(handler));
    // Missing .with_state() causes error

// Correct:
let router = Router::new()
    .route("/", get(handler))
    .with_state(AppState { /* ... */ });
```

## Middleware Ordering and Composition Contracts

### Contract: Layer Ordering - Last Added is Outermost

**Rule:** Middleware added via `.layer()` last executes first for requests (outermost position).

**Mechanism:** Nested Layer application
- Each layer wraps the previous service
- Last added wraps all previous
- Requests flow outer → inner → handler → inner → outer

**Verification:**

```rust
let router = Router::new()
    .route("/", get(handler))
    .layer(logging_layer)      // Applied 1st (innermost - closest to handler)
    .layer(auth_layer)         // Applied 2nd
    .layer(cors_layer)         // Applied 3rd (outermost - processes request first)
    .layer(metrics_layer);     // Applied 4th (outermost - processes request last)

// Request flow: metrics → cors → auth → logging → handler
// Response flow: logging → auth → cors → metrics
```

**Edge Case:** ServiceBuilder reversal
- ServiceBuilder applies layers top-to-bottom
- Results in opposite order compared to stacked `.layer()` calls
- Most intuitive when middleware is "around" the handler

### Contract: Route-Level Middleware Scope

**Rule:** `.route_layer()` applies middleware only to specific routes, not to other routes or nested routers.

**Mechanism:** Middleware applied at route registration
- Separate from router-level layers
- Each route can have different route-level middleware
- Route-level runs after router-level

**Verification:**

```rust
let admin = get(admin_handler).route_layer(auth_layer);
let public = get(public_handler);

let router = Router::new()
    .route("/admin", admin)     // Only /admin gets auth_layer
    .route("/public", public)   // /public doesn't get auth_layer
    .layer(logging_layer);      // Both get logging_layer

// GET /admin: logging → auth → handler
// GET /public: logging → handler (no auth)
```

## Error Propagation and Rejection Contracts

### Contract: Extractor Rejection Short-Circuits Handler

**Rule:** If any extractor rejects, the handler doesn't execute; rejection is converted to HTTP response.

**Mechanism:** Early return on rejection
- Extractor rejection returns immediately
- Subsequent extractors don't run
- Handler code never executes

**Verification:**

```rust
async fn handler(
    Path(id): Path<u32>,           // If rejects (invalid int), stops here
    Query(q): Query<Params>,       // Skipped if Path rejected
    Json(body): Json<Data>,        // Skipped if previous rejected
) -> Response { }

// GET /invalid/path?foo=bar
// Path extraction fails → 400 Bad Request
// Query and Json extractors never run
// Handler never executes
```

**Edge Case:** Multiple rejections
- Only first rejection matters
- Subsequent extractors not evaluated after first failure

### Contract: Rejection Type Determines Status Code

**Rule:** Each extractor type has a specific rejection that maps to an HTTP status code.

**Mechanism:** IntoResponse implementation for rejection types
- Json<T> rejection → 400 Bad Request (or 413 Payload Too Large)
- Path<T> rejection → 400 Bad Request
- Query<T> rejection → 400 Bad Request
- Extension<T> rejection → 500 Internal Server Error
- Custom extractors define their own rejection

**Verification:**

```rust
// Json parsing fails
POST /api/users
Content-Type: application/json
invalid json

// Response: 400 Bad Request
// Body: serde error details

// Missing extension (middleware bug)
async fn handler(Extension(user): Extension<User>) -> Response { }
// Response: 500 Internal Server Error (indicates middleware not working)
```

## Body Type and Content-Type Contracts

### Contract: Content-Type Determines Extractor

**Rule:** The Content-Type header in the request determines how the body is interpreted by extractors.

**Mechanism:** Extractor-specific Content-Type checking
- Json<T> expects application/json (or no Content-Type defaults to JSON)
- Form<T> expects application/x-www-form-urlencoded
- String assumes UTF-8 encoded text body
- No negotiation—Content-Type must be correct

**Verification:**

```rust
async fn handler(Json(data): Json<Data>) -> Response { }

// POST with Content-Type: application/json → parsed as JSON
// POST with Content-Type: application/octet-stream → fails (not JSON)
// POST with no Content-Type → defaults to JSON (may parse successfully)
// POST with Content-Type: text/plain → might fail depending on content
```

**Edge Case:** Missing Content-Type
- Json<T> defaults to treating body as JSON
- Form<T> requires explicit Content-Type
- Risky default for Json—relies on client following protocol

### Contract: Response IntoResponse Sets Content-Type

**Rule:** The response type determines the Content-Type of the response body.

**Mechanism:** IntoResponse implementation
- String → text/plain; charset=utf-8
- Json<T> → application/json
- Html<T> → text/html; charset=utf-8
- Bytes/Vec<u8> → application/octet-stream
- StatusCode → no Content-Type (no body)

**Verification:**

```rust
async fn handler() -> String {
    "hello".into()
}
// Response: 200 OK
// Content-Type: text/plain; charset=utf-8

async fn handler() -> Json<Data> {
    Json(Data { /* ... */ })
}
// Response: 200 OK
// Content-Type: application/json
```

## Important Behavioral Contracts Summary

### Compile-Time Safety

1. **Extractor ordering** - Parts before body, enforced at compile time
2. **Single body extractor** - Only one FromRequest per handler, enforced at compile time
3. **State type** - Must match what's provided, enforced at compile time
4. **Response type** - Must implement IntoResponse, enforced at compile time

### Runtime Behavior

1. **Extractor execution** - Left-to-right in parameter order
2. **Body consumption** - Happens once, remainder unavailable
3. **Rejection propagation** - Stops handler execution immediately
4. **State sharing** - Arc<T> across all requests
5. **Middleware ordering** - Last added is outermost (processes requests first)

### Routing Behavior

1. **Path matching** - Longest match first, exact then params then greedy
2. **Nesting** - Prefix stripped, path hierarchy maintained
3. **Fallback** - Only on path miss, not method miss
4. **Trailing slashes** - Significant, no auto-redirect

## Known Behavioral Gotchas

1. **State type mismatch** - Compile error, not runtime rejection
2. **Missing extension** - 500 error (middleware bug indicator)
3. **Body already consumed** - Second extractor gets empty body
4. **Query parameter encoding** - Must be valid URL encoding
5. **Json size limit** - 100MB default, exceeding → 413 Payload Too Large
6. **Serde error details** - Exposed in rejection (security consideration)
7. **Panic in handler** - Becomes 500 error
8. **Middleware out of scope** - Route-level doesn't apply to other routes

## Sources

- https://docs.rs/axum/latest/axum/
- https://docs.rs/axum/latest/axum/extract/
- https://docs.rs/axum/latest/axum/routing/
- https://github.com/tokio-rs/axum
