# Axum Extractors

**Source:** https://docs.rs/axum/latest/axum/extract/
**Version:** 0.8.8+
**Accessed:** April 2026

## Overview

Extractors are the primary mechanism for declaratively pulling data from HTTP requests into handler function parameters. They implement `FromRequest` or `FromRequestParts` traits and enable type-safe, compile-time verified request handling.

## Core Concept

Rather than passing raw Request objects to handlers, handlers declare their dependencies as parameters. The type system ensures:

1. Only valid combinations of extractors are allowed
2. Body-consuming extractors are last
3. Only one body-consuming extractor per handler
4. Extractors run in parameter order

## Extractor Traits

### FromRequestParts<S>

For extractors that don't consume the request body (headers, path params, query strings):

```rust
pub trait FromRequestParts<S>: Sized {
    type Rejection: IntoResponse;
    
    async fn from_request_parts(
        parts: &mut Parts,
        state: &S,
    ) -> Result<Self, Self::Rejection>;
}
```

Multiple FromRequestParts extractors can be used in any order.

### FromRequest<S, B>

For extractors that consume or access the request body:

```rust
pub trait FromRequest<S, B>: Sized {
    type Rejection: IntoResponse;
    
    async fn from_request(
        req: Request<B>,
        state: &S,
    ) -> Result<Self, Self::Rejection>;
}
```

Only one FromRequest extractor per handler, and it must be the last parameter.

## Standard Extractors

### Path - URL Parameters

Extracts and deserializes URL path parameters:

```rust
// Route: /users/:id/posts/:post_id

async fn handler(
    Path((id, post_id)): Path<(u32, u64)>,
) -> String {
    format!("User {}, Post {}", id, post_id)
}

// Or with struct:
#[derive(Deserialize)]
struct Params {
    id: u32,
    post_id: u64,
}

async fn handler(Path(params): Path<Params>) -> String {
    format!("User {}, Post {}", params.id, params.post_id)
}
```

Behavioral contract:
- Rejects with 400 Bad Request if deserialization fails
- Captures URL-encoded values (% decoding applied)
- Multiple params can use tuple or struct deserialization

### Query - Query String Parameters

Extracts and deserializes query string parameters:

```rust
// GET /search?q=rust&limit=10

#[derive(Deserialize)]
struct SearchQuery {
    q: String,
    #[serde(default)]
    limit: u32,
}

async fn search(Query(params): Query<SearchQuery>) -> String {
    format!("Search: {}, limit: {}", params.q, params.limit)
}
```

Behavioral contract:
- Rejects with 400 Bad Request if deserialization fails
- Supports serde field attributes (#[serde(default)], #[serde(rename)])
- Missing optional fields use serde defaults
- URL-encoded decoding applied

### Json - JSON Body

Parses and deserializes JSON request body:

```rust
#[derive(Deserialize)]
struct CreateUser {
    name: String,
    email: String,
}

async fn create_user(Json(payload): Json<CreateUser>) -> StatusCode {
    // Process payload
    StatusCode::CREATED
}
```

Behavioral contract:
- **Body-consuming extractor** - Must be last parameter
- Rejects with 400 Bad Request if JSON is invalid
- Rejects with 413 Payload Too Large if body exceeds limits
- Content-Type application/json required (or missing, defaults to JSON)
- Deserializes using serde

### String and Bytes - Raw Body

Raw access to request body:

```rust
async fn echo(body: String) -> String {
    body  // Echo the request body as text
}

async fn binary(body: Bytes) -> Bytes {
    body  // Echo as binary
}
```

Behavioral contract:
- **Body-consuming extractors** - Must be last
- String assumes UTF-8 encoding, rejects with 400 if not valid UTF-8
- Bytes accepts any data
- No size limits enforced at extractor level

### HeaderMap - All Headers

Access all request headers:

```rust
async fn handler(headers: HeaderMap) -> String {
    match headers.get("x-custom") {
        Some(value) => {
            format!("Custom: {:?}", value)
        }
        None => "No custom header".into(),
    }
}
```

Behavioral contract:
- Non-body extractor - Can appear anywhere in parameters
- Returns all headers including standard ones
- Header values are bytes, not strings (may contain non-UTF-8)

### Header<T> - Typed Headers

Extracts specific headers with type conversion:

```rust
use axum::http::header::USER_AGENT;

async fn handler(
    TypedHeader(user_agent): TypedHeader<UserAgent>,
) -> String {
    format!("Agent: {}", user_agent)
}
```

Behavioral contract:
- Non-body extractor
- Requires headers crate integration
- Rejects with 400 if header is missing or invalid
- Type-safe header parsing

### State - Application State

Accesses application state:

```rust
struct AppState {
    db: Arc<Database>,
}

async fn handler(State(state): State<AppState>) -> String {
    // Access state.db
}
```

Behavioral contract:
- Non-body extractor - Can appear early
- State must be provided via Router::with_state()
- Returns Arc<T> internally, shared across all requests
- State is thread-safe (Arc<T>)

### Extension<T> - Request Extensions

Request-scoped data injection (typically by middleware):

```rust
// Middleware inserts:
extensions.insert(CurrentUser { id: 42 });

// Handler extracts:
async fn handler(Extension(user): Extension<CurrentUser>) -> String {
    format!("User: {}", user.id)
}
```

Behavioral contract:
- Non-body extractor
- Typically populated by middleware before handler
- Rejects with 500 if extension not present
- Value is cloned (ensure Clone is reasonable)

### Form - Form Data

Parses application/x-www-form-urlencoded or multipart/form-data:

```rust
#[derive(Deserialize)]
struct FormData {
    username: String,
    password: String,
}

async fn login(Form(data): Form<FormData>) -> StatusCode {
    // Validate credentials
    StatusCode::OK
}
```

Behavioral contract:
- **Body-consuming extractor** - Must be last
- Content-Type application/x-www-form-urlencoded required
- Rejects with 400 if form is invalid
- URL-encoded decoding applied

### ConnectInfo - Connection Information

Information about the TCP connection:

```rust
use axum::extract::ConnectInfo;

async fn handler(
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
) -> String {
    format!("Client: {}", addr)
}
```

Behavioral contract:
- Non-body extractor
- Requires ConnectInfo layer or middleware to populate
- Address depends on server configuration (may be proxy address)
- Type parameter is typically SocketAddr or custom type

## Extractor Ordering Rules

Axum enforces strict rules about parameter ordering:

### Rule 1: Parts Before Body

All `FromRequestParts` extractors must come before any `FromRequest` (body-consuming) extractors:

```rust
// CORRECT:
async fn handler(
    Path(id): Path<u32>,           // FromRequestParts
    headers: HeaderMap,            // FromRequestParts
    State(state): State<AppState>, // FromRequestParts
    Json(body): Json<T>,           // FromRequest - LAST
) { }

// INCORRECT:
async fn handler(
    Json(body): Json<T>,           // FromRequest
    Path(id): Path<u32>,           // FromRequestParts - ERROR!
) { }
```

### Rule 2: Single Body Extractor

Only one body-consuming extractor per handler:

```rust
// INCORRECT:
async fn handler(
    Json(body): Json<T>,
    String(raw): String,  // ERROR: Two body consumers
) { }

// CORRECT: Choose one
async fn handler(Json(body): Json<T>) { }
```

### Rule 3: Body Extractor is Last

Any body-consuming extractor must be the final parameter:

```rust
// INCORRECT:
async fn handler(
    Json(body): Json<T>,     // FromRequest
    Path(id): Path<u32>,     // ERROR: Parts after body
) { }

// CORRECT:
async fn handler(
    Path(id): Path<u32>,
    Json(body): Json<T>,     // Last
) { }
```

### Rule 4: Execution Order

Extractors run left-to-right in parameter order, not by type.

## Optional Extractors

Some extractors support optional extraction via Result or Option:

```rust
async fn handler(
    Path(id): Path<u32>,
    Query(params): Query<SearchQuery>,  // Rejections become 400
    Json(body): Result<Json<T>, JsonRejection>,  // Can fail gracefully
) {
    // Handle rejection in handler
}
```

Some extractors implement OptionalFromRequestParts:

```rust
async fn handler(
    maybe_header: Option<TypedHeader<UserAgent>>,
) {
    // Extraction succeeds even if header is missing
}
```

## Custom Extractors

Implement FromRequestParts for non-body extractors:

```rust
struct UserId(u32);

#[async_trait]
impl<S> FromRequestParts<S> for UserId
where
    S: Send + Sync,
{
    type Rejection = StatusCode;
    
    async fn from_request_parts(
        parts: &mut Parts,
        _state: &S,
    ) -> Result<Self, Self::Rejection> {
        parts
            .headers
            .get("x-user-id")
            .and_then(|h| h.to_str().ok())
            .and_then(|s| s.parse::<u32>().ok())
            .map(UserId)
            .ok_or(StatusCode::UNAUTHORIZED)
    }
}
```

Implement FromRequest for body-consuming extractors (less common).

## Rejection Handling

Extractors reject requests when validation fails. Default rejections:

- **Path extraction fails** - 400 Bad Request
- **Query deserialization fails** - 400 Bad Request
- **Json parsing fails** - 400 Bad Request (also 413 if too large)
- **Missing required header** - 400 Bad Request
- **Invalid header value** - 400 Bad Request
- **Missing extension** - 500 Internal Server Error (indicates middleware bug)

Custom rejections can be implemented by creating custom extractors.

## Behavioral Contracts - Critical

1. **Extractors are type-safe** - Invalid combinations cause compile errors
2. **Body consumed only once** - Enforced at type level
3. **Extraction order is parameter order** - Left to right in function signature
4. **Rejections are IntoResponse** - Become HTTP responses automatically
5. **State must be provided** - Router::with_state() required to use State<T>
6. **Parts-only extractors are reusable** - Can appear in any order, multiple times
7. **Body extractors are singular** - Only one per handler, must be last

## Known Issues and Edge Cases

1. **Extension not found** - Results in 500, indicating middleware misconfiguration
2. **State mismatch** - Wrong state type causes compile error
3. **Nested deser fails** - serde errors may not be descriptive
4. **Large body uploads** - Json limits can cause 413 rejection
5. **Charset issues** - String extractor assumes UTF-8, rejects invalid UTF-8
6. **Query param encoding** - URL percent-encoding must be valid
7. **Form multipart** - Requires specific Content-Type header

## Sources

- https://docs.rs/axum/latest/axum/extract/
- https://docs.rs/axum/latest/axum/extract/struct.Path.html
- https://docs.rs/axum/latest/axum/extract/struct.Query.html
- https://docs.rs/axum/latest/axum/extract/struct.Json.html
- https://docs.rs/axum/latest/axum/extract/struct.State.html
- https://github.com/tokio-rs/axum/tree/main/axum
