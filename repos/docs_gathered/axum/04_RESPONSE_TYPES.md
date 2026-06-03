# Axum Response Types

**Source:** https://docs.rs/axum/latest/axum/response/
**Version:** 0.8.8+
**Accessed:** April 2026

## Overview

Responses in Axum are built on the `IntoResponse` trait, which allows any type implementing it to be returned from a handler. This design enables flexible, composable response building with automatic content-type handling and serialization.

## The IntoResponse Trait

The core trait that enables response flexibility:

```rust
pub trait IntoResponse {
    fn into_response(self) -> Response<BoxBody>;
}
```

Any type implementing `IntoResponse` can be returned from a handler. Axum provides implementations for many common types and enables powerful composition through tuples.

## Built-In Response Types

### StatusCode

Returns HTTP status codes without body:

```rust
use axum::http::StatusCode;

async fn created() -> StatusCode {
    StatusCode::CREATED  // 201
}

async fn not_found() -> StatusCode {
    StatusCode::NOT_FOUND  // 404
}

async fn server_error() -> StatusCode {
    StatusCode::INTERNAL_SERVER_ERROR  // 500
}
```

Behavioral contract:
- Response body is empty
- Only status code is sent
- No Content-Type header
- Useful for minimal responses

### String

Returns text with content-type `text/plain; charset=utf-8`:

```rust
async fn hello() -> String {
    "Hello, world!".into()
}

async fn user_info(Path(id): Path<u32>) -> String {
    format!("User ID: {}", id)
}
```

Behavioral contract:
- Automatically sets `Content-Type: text/plain; charset=utf-8`
- Body is UTF-8 encoded
- No length limit at response level

### Bytes and Vec<u8>

Returns binary data with content-type `application/octet-stream`:

```rust
async fn download() -> Bytes {
    Bytes::from_static(b"binary data")
}

async fn stream_file() -> Vec<u8> {
    vec![1, 2, 3, 4, 5]
}
```

Behavioral contract:
- Content-Type is `application/octet-stream`
- Body can contain any byte sequence
- No encoding assumptions

### Json<T>

Serializes type as JSON with content-type `application/json`:

```rust
use serde::Serialize;

#[derive(Serialize)]
struct User {
    id: u32,
    name: String,
}

async fn get_user() -> Json<User> {
    Json(User {
        id: 1,
        name: "Alice".into(),
    })
}

async fn get_users() -> Json<Vec<User>> {
    Json(vec![/* ... */])
}
```

Behavioral contract:
- Serializes using serde_json
- Content-Type is `application/json`
- Rejects with 500 if serialization fails
- Supports any serde-serializable type

### Html<T>

Returns HTML with content-type `text/html; charset=utf-8`:

```rust
async fn index() -> Html<&'static str> {
    Html("<h1>Hello</h1>")
}

async fn template() -> Html<String> {
    Html(format!("<h1>Title</h1>"))
}
```

Behavioral contract:
- Content-Type is `text/html; charset=utf-8`
- No HTML sanitization or escaping performed
- Caller responsible for safe output
- Body must be valid UTF-8

### () - Unit Type

Returns empty response:

```rust
async fn no_content() -> () {
    // Empty response with 200 OK
}
```

Behavioral contract:
- HTTP 200 OK with empty body
- No Content-Type header
- Useful for operations that don't return data

## Composite Responses (Tuples)

Axum enables powerful response composition through tuple types. A tuple combines status, headers, and body:

### (StatusCode, impl IntoResponse)

Combine status with response:

```rust
async fn created_user() -> (StatusCode, Json<User>) {
    let user = User { id: 1, name: "Alice".into() };
    (StatusCode::CREATED, Json(user))
}

async fn accepted() -> (StatusCode, String) {
    (StatusCode::ACCEPTED, "Processing...".into())
}
```

Behavioral contract:
- First element sets HTTP status code
- Second element provides response body
- Status overrides default from response type

### (StatusCode, HeaderMap, impl IntoResponse)

Combine status, headers, and body:

```rust
async fn with_headers() -> (StatusCode, HeaderMap, String) {
    let mut headers = HeaderMap::new();
    headers.insert(
        "X-Custom",
        "value".parse().unwrap(),
    );
    (StatusCode::OK, headers, "Done".into())
}
```

Behavioral contract:
- First element is status code
- Second element is header map
- Third element is response body
- Headers are merged with default headers

### (StatusCode, Vec<(HeaderName, HeaderValue)>, impl IntoResponse)

Alternative header specification:

```rust
async fn with_vec_headers() -> (StatusCode, Vec<(HeaderName, HeaderValue)>, String) {
    let headers = vec![
        (header::CONTENT_TYPE, "text/plain".parse().unwrap()),
    ];
    (StatusCode::OK, headers, "Response".into())
}
```

### (StatusCode, HeaderMap, Extension<T>, impl IntoResponse)

Include response extensions:

```rust
async fn with_extension() -> (
    StatusCode,
    HeaderMap,
    Extension<ResponseMetadata>,
    Json<Data>,
) {
    (
        StatusCode::OK,
        HeaderMap::new(),
        Extension(ResponseMetadata { traced: true }),
        Json(data),
    )
}
```

Behavioral contract:
- Extensions are response-level metadata
- Available to downstream middleware
- Order in tuple matters
- Extensions are last element

## Redirect Response

Redirect responses:

```rust
use axum::response::Redirect;

async fn redirect_home() -> Redirect {
    Redirect::permanent("/home")
}

async fn redirect_temp() -> Redirect {
    Redirect::temporary("/new-location")
}
```

Behavioral contract:
- Permanent (301) or temporary (307) redirects
- Location header automatically set
- Body is empty
- No validation of target URL

## Error Responses

Error types implementing `IntoResponse`:

```rust
use axum::response::ErrorResponse;

async fn error() -> Result<String, StatusCode> {
    Err(StatusCode::NOT_FOUND)
}
```

Any error type implementing `IntoResponse` can be returned from handlers using Result.

## Custom Response Types

Implement `IntoResponse` for custom types:

```rust
struct CustomResponse {
    status: StatusCode,
    body: String,
}

impl IntoResponse for CustomResponse {
    fn into_response(self) -> Response {
        (self.status, self.body).into_response()
    }
}

async fn handler() -> CustomResponse {
    CustomResponse {
        status: StatusCode::OK,
        body: "Custom".into(),
    }
}
```

## Response Builder Pattern

For complex responses, use response builders:

```rust
use axum::response::Response;
use axum::http::HeaderValue;

async fn complex() -> Response {
    let mut response = String::from("Hello").into_response();
    response.headers_mut().insert(
        "X-Custom",
        HeaderValue::from_static("value"),
    );
    response
}
```

Behavioral contract:
- Responses are mutable after creation
- Headers can be added or modified
- Body is already committed
- Extensions can be added

## Content-Type Negotiation

Axum does not perform automatic content-type negotiation. Response types determine content-type:

- **String** → `text/plain; charset=utf-8`
- **Json<T>** → `application/json`
- **Html<T>** → `text/html; charset=utf-8`
- **Bytes/Vec<u8>** → `application/octet-stream`
- **Custom types** → Whatever you set

To support multiple formats, return different response types conditionally:

```rust
enum Response {
    Json(Json<Data>),
    Html(Html<String>),
}

impl IntoResponse for Response {
    fn into_response(self) -> axum::response::Response {
        match self {
            Response::Json(json) => json.into_response(),
            Response::Html(html) => html.into_response(),
        }
    }
}
```

## Special Response Types

### NoContent

Empty response with 204 status:

```rust
use axum::response::NoContent;

async fn delete_user() -> NoContent {
    // 204 No Content
}
```

### IntoResponseParts

Trait for types that can be used in tuple responses but aren't full responses:

```rust
impl IntoResponseParts for HeaderMap {
    // Allows using HeaderMap in tuple responses
}
```

## Response Extension Propagation

Extensions added to responses:

```rust
let mut response = "body".into_response();
response.extensions_mut().insert(metadata);
```

Available in downstream middleware but not sent to client.

## Behavioral Contracts - Critical

1. **IntoResponse is required** - Only types implementing it can be returned from handlers
2. **Tuples enable composition** - Status, headers, body can be combined
3. **First tuple element is status** - StatusCode always first if present
4. **Content-Type is determined by type** - No negotiation, type-based
5. **Body consumed on into_response** - Can't modify body after creation
6. **Headers are settable** - Can be added or modified on Response
7. **Extensions propagate downstream** - Available to middleware after handler

## Known Issues and Edge Cases

1. **Generic impl IntoResponse complexity** - Complex tuple combinations may have inference issues
2. **Content-Type override** - Manual override required, no negotiation
3. **Streaming bodies** - Standard responses buffer entire body
4. **Custom status codes** - StatusCode supports full range but some are rarely used
5. **Header parsing** - HeaderValue parsing may fail (parse().unwrap() anti-pattern)
6. **Trait object responses** - Box<dyn IntoResponse> requires additional wrapping

## Serialization Errors

When Json<T> serialization fails:

```rust
async fn serialize_error() -> Json<UnserializableType> {
    // If serde_json fails: 500 Internal Server Error
    // Serialization error becomes handler error
}
```

## Response Size Considerations

For large responses:

1. **String/Bytes responses** - Buffered in memory entirely
2. **Json responses** - Serialized to memory before sending
3. **Streaming needed** - Use Body type or custom response wrapper
4. **Backpressure** - Not handled by standard response types

## Sources

- https://docs.rs/axum/latest/axum/response/
- https://docs.rs/axum/latest/axum/response/trait.IntoResponse.html
- https://docs.rs/axum/latest/axum/response/struct.Response.html
- https://docs.rs/axum/latest/axum/response/struct.Redirect.html
- https://github.com/tokio-rs/axum/tree/main/axum
