# Axum Error Handling

**Source:** https://docs.rs/axum/latest/axum/extract/
**Source:** https://docs.rs/axum/latest/axum/response/
**Version:** 0.8.8+
**Accessed:** April 2026

## Overview

Error handling in Axum is built on the `IntoResponse` trait and Rust's standard `Result` type. Any type implementing `IntoResponse` can be returned from a handler, enabling flexible error responses.

The type system enforces compile-time correctness: extractors and handlers work together to ensure errors are properly converted to HTTP responses.

## Extractor Rejections

Extractors reject requests when validation fails. Rejections are automatically converted to HTTP responses.

### Common Rejection Patterns

**Path Parameter Extraction:**

```rust
// Route: /users/:id

async fn get_user(Path(id): Path<u32>) -> String {
    format!("User {}", id)
}

// Invalid path: /users/not-a-number
// Result: 400 Bad Request with rejection body
```

Behavioral contract:
- Deserialization failure → 400 Bad Request
- serde error details included in response (may expose internals)
- Invalid UTF-8 in path → 400 Bad Request

**Query String Extraction:**

```rust
#[derive(Deserialize)]
struct Params {
    page: u32,
}

async fn search(Query(p): Query<Params>) -> String {
    format!("Page {}", p.page)
}

// Invalid query: ?page=abc
// Result: 400 Bad Request
```

Behavioral contract:
- Missing required fields → 400 Bad Request
- Type mismatch → 400 Bad Request
- Invalid URL encoding → 400 Bad Request

**JSON Body Extraction:**

```rust
#[derive(Deserialize)]
struct CreateUser {
    name: String,
    email: String,
}

async fn create_user(Json(payload): Json<CreateUser>) -> StatusCode {
    StatusCode::CREATED
}

// Invalid JSON in body → 400 Bad Request
// Body too large (>100MB) → 413 Payload Too Large
// Missing Content-Type → assumed JSON, still parsed
```

Behavioral contract:
- Invalid JSON → 400 Bad Request with serde error details
- Body size exceeds limit → 413 Payload Too Large
- Content-Type header optional (defaults to JSON)
- Serde error messages may expose schema details

**Header Extraction:**

```rust
use axum::http::header::USER_AGENT;

async fn handler(
    TypedHeader(agent): TypedHeader<UserAgent>,
) -> String {
    format!("Agent: {:?}", agent)
}

// Missing or invalid header → 400 Bad Request
```

Behavioral contract:
- Missing required header → 400 Bad Request
- Invalid header value → 400 Bad Request
- Case-insensitive header matching

**State Extraction:**

```rust
struct AppState { db: Arc<Db> }

async fn handler(State(state): State<AppState>) -> String {
    // state access
}

// State not provided → Compile error
// Wrong state type → Compile error
```

Behavioral contract:
- State type mismatch detected at compile time
- Missing state causes handler compilation failure
- No runtime rejection

**Extension Extraction:**

```rust
struct UserId(u32);

async fn handler(Extension(user_id): Extension<UserId>) -> String {
    // use user_id
}

// Extension not present → 500 Internal Server Error
```

Behavioral contract:
- Missing extension → 500 Internal Server Error (indicates middleware bug)
- Type mismatch → compile error or runtime panic
- Extension presence depends on middleware setup

## Handling Rejections in Handlers

Wrap extractors in `Result` to handle failures gracefully:

```rust
use axum::extract::rejection::JsonRejection;

async fn create_user(
    Json(payload): Result<Json<User>, JsonRejection>,
) -> Result<StatusCode, CustomError> {
    let user = match payload {
        Ok(user) => user,
        Err(err) => {
            eprintln!("Invalid JSON: {}", err);
            return Err(CustomError::InvalidInput);
        }
    };
    
    // Process user
    Ok(StatusCode::CREATED)
}
```

Behavioral contract:
- Rejection type is available as `<Extractor>Rejection`
- Can be matched and handled in handler
- Custom error responses possible via CustomError
- No automatic conversion to response—must implement IntoResponse

### Optional Extraction

Some extractors support Option for optional fields:

```rust
async fn handler(
    maybe_user_agent: Option<TypedHeader<UserAgent>>,
) -> String {
    match maybe_user_agent {
        Some(agent) => format!("Agent: {}", agent),
        None => "No user agent".into(),
    }
}

// Missing header → Some(default) or None depending on extractor
```

Behavioral contract:
- Not all extractors implement optional extraction
- Option<T> syntax is extractor-specific
- Extraction succeeds with None if optional not available
- Reduces error cases

## Custom Error Types

Implement `IntoResponse` for custom error types:

```rust
use axum::response::IntoResponse;
use axum::http::StatusCode;

#[derive(Debug)]
enum AppError {
    InvalidInput(String),
    Database(String),
    Unauthorized,
    NotFound,
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, msg) = match self {
            AppError::InvalidInput(e) => (StatusCode::BAD_REQUEST, e),
            AppError::Database(e) => {
                eprintln!("DB error: {}", e);
                (StatusCode::INTERNAL_SERVER_ERROR, "Database error".into())
            }
            AppError::Unauthorized => (StatusCode::UNAUTHORIZED, "Unauthorized".into()),
            AppError::NotFound => (StatusCode::NOT_FOUND, "Not found".into()),
        };
        
        (status, msg).into_response()
    }
}

async fn handler() -> Result<String, AppError> {
    Err(AppError::Unauthorized)
}
```

Behavioral contract:
- Must implement IntoResponse
- Can include error logging
- Can vary response format (JSON, plain text, HTML)
- Error information can be hidden from client while logged

### JSON Error Responses

For API applications, return JSON errors:

```rust
use serde::Serialize;

#[derive(Serialize)]
struct ErrorResponse {
    error: String,
    details: Option<String>,
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, msg, details) = match self {
            AppError::InvalidInput(e) => (
                StatusCode::BAD_REQUEST,
                "Invalid input",
                Some(e),
            ),
            // ...
        };
        
        let error_response = ErrorResponse {
            error: msg.into(),
            details,
        };
        
        (status, Json(error_response)).into_response()
    }
}
```

## Error Propagation

Errors flow from extractors → handler → IntoResponse conversion:

```rust
async fn handler(
    Path(id): Path<u32>,              // May reject
    Query(params): Query<Params>,      // May reject
    Json(body): Json<CreateData>,      // May reject
) -> Result<StatusCode, AppError> {
    // If any extractor rejects, handler doesn't execute
    // Rejection converts to HTTP response automatically
    
    // Handler can also return error
    Err(AppError::Processing)?
}
```

Behavioral contract:
- Extractor rejection prevents handler execution
- Handler errors are propagated via Result
- Both become HTTP responses via IntoResponse
- Short-circuit on first error

### Fallible Extractors

Some extractors can fail or succeed optionally:

```rust
use axum::extract::OptionalFromRequestParts;

// If header missing: extraction succeeds with None
async fn handler(
    maybe_user_id: Option<TypedHeader<UserId>>,
) -> String {
    match maybe_user_id {
        Some(id) => format!("User: {}", id),
        None => "No user".into(),
    }
}

// If extraction fails: Still error
async fn handler(
    result: Result<Json<Data>, JsonRejection>,
) -> Result<StatusCode, JsonRejection> {
    let data = result?;
    Ok(StatusCode::OK)
}
```

## Error Details Leakage

Extractors include error details in rejection responses:

```rust
// Rejection response body includes serde error details:
// "invalid value: string \"abc\", expected u32 at line 1 column 10"
```

This can expose API schema and validation logic to clients. To hide details:

```rust
async fn handler(
    result: Result<Json<Data>, JsonRejection>,
) -> Result<StatusCode, AppError> {
    match result {
        Ok(data) => process(data).await,
        Err(_) => {
            eprintln!("Parse error details logged");
            Err(AppError::InvalidInput("Invalid data".into()))
        }
    }
}
```

Behavioral contract:
- Default rejection messages are detailed
- Custom errors should hide internal details
- Security practice: log details, show generic message to client

## Panic Handling

Panics in handlers become HTTP 500 errors (in production):

```rust
async fn handler() -> String {
    panic!("Unhandled error");  // Becomes 500 Internal Server Error
}
```

Behavioral contract:
- Panic is caught by Axum's panic handling
- Results in 500 response
- Panic message logged (depending on configuration)
- Debug builds may propagate panic

## Result Type in Handlers

Handlers return `impl IntoResponse`, which includes Result:

```rust
// Both are valid:
async fn handler1() -> String {
    "success".into()
}

async fn handler2() -> Result<String, AppError> {
    if some_condition {
        Ok("success".into())
    } else {
        Err(AppError::NotFound)
    }
}
```

Behavioral contract:
- Result<T, E> where T and E implement IntoResponse
- Success branch (Ok) is converted to response
- Error branch (Err) is converted to response
- Both must implement IntoResponse

## Multiple Error Types

Handle multiple error types with enum or trait objects:

```rust
#[derive(Debug)]
enum Error {
    Database(db::Error),
    Json(serde_json::Error),
    Custom(String),
}

impl From<db::Error> for Error {
    fn from(err: db::Error) -> Self {
        Error::Database(err)
    }
}

impl From<serde_json::Error> for Error {
    fn from(err: serde_json::Error) -> Self {
        Error::Json(err)
    }
}

impl IntoResponse for Error {
    fn into_response(self) -> Response {
        // match and convert
    }
}

async fn handler() -> Result<String, Error> {
    let data = serde_json::from_str(s)?;  // Converts JsonError → Error
    let db_result = db.query().await?;     // Converts DbError → Error
    Ok(format!("{}", data))
}
```

Behavioral contract:
- Implement From<OtherError> for Error
- Use ? operator for automatic conversion
- Single Result<T, E> return type

## Middleware Error Handling

Middleware can handle errors from handlers:

```rust
async fn error_handler(
    req: Request,
    next: Next,
) -> Response {
    let response = next.run(req).await;
    
    if response.status().is_server_error() {
        eprintln!("Server error: {}", response.status());
        // Could log, send alert, etc.
    }
    
    response
}
```

Behavioral contract:
- Middleware sees final response
- Can't modify handler errors directly
- Can log and react to error responses
- Can create synthetic error responses

## Important Behavioral Contracts

1. **Extractor rejections are immediate** - Handler doesn't execute if extractor fails
2. **Rejections are IntoResponse** - Automatically converted to HTTP responses
3. **Handler errors propagate via Result** - Error type must implement IntoResponse
4. **Status codes in errors are set via IntoResponse** - Full control over response format
5. **Error details are exposed by default** - Consider hiding internal details
6. **Panics become 500 errors** - Graceful degradation
7. **Multiple errors require type conversion** - Implement From traits

## Known Issues and Edge Cases

1. **Detailed error leakage** - Default rejections expose schema
2. **Error type inference** - Complex error types may cause inference issues
3. **Custom rejection types** - Must implement IntoResponse to use in Result
4. **Extension missing** - Results in 500 rather than 400 (middleware bug indicator)
5. **Serde error messages** - Implementation-dependent, may change
6. **Body already consumed** - Second extractor attempting body gets error
7. **State type mismatches** - Compile-time error, not runtime rejection

## Error Handling Best Practices

1. **Use custom error types** - Centralize error logic
2. **Wrap extractor results** - Handle validation failures gracefully
3. **Hide internal details** - Log details, return generic messages
4. **Log errors thoroughly** - Include context and stack traces
5. **Use appropriate status codes** - 400 for client errors, 500 for server
6. **Implement standard traits** - From, Display, Debug for compatibility
7. **Test error paths** - Ensure error responses are correct

## Sources

- https://docs.rs/axum/latest/axum/extract/
- https://docs.rs/axum/latest/axum/response/
- https://docs.rs/axum/latest/axum/http/
- https://github.com/tokio-rs/axum/tree/main/examples
