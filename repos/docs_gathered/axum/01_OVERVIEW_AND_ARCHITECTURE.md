# Axum Overview and Architecture

**Source:** https://docs.rs/axum/latest/axum/
**Version:** 0.8.8+
**Accessed:** April 2026

## What is Axum?

Axum is a modular web application framework for Rust that emphasizes ergonomics and composability. It is built on the Tokio runtime and Hyper HTTP transport, providing a high-performance foundation for building production HTTP services.

The framework's core philosophy is to leverage existing, battle-tested components (Tower, Hyper, Tokio) rather than reinventing middleware or service abstractions.

## Architectural Principles

### Tower-Based Design

Axum's most distinctive architectural choice is **full integration with Tower** rather than implementing proprietary middleware or service traits. This design decision has profound implications:

- Axum gets timeout handling, tracing, compression, authorization, and other cross-cutting concerns "for free" from the Tower ecosystem
- Middleware and services written for Hyper and Tonic work directly with Axum
- The entire Tower ServiceBuilder ecosystem is available for composition
- Custom Tower layers can be applied at router, route, or handler levels

### Handler-First Architecture

Handlers are the primary building blocks. A handler is an async function that:

1. Accepts zero or more extractors as parameters
2. Returns a type implementing `IntoResponse`
3. Is completely decoupled from HTTP details via extractors and response traits

This design enables compile-time safety—the type system prevents many classes of errors that would be runtime failures in dynamic frameworks.

### Extractor-Based Request Deconstruction

Rather than passing raw `Request` objects to handlers, Axum uses extractors—types implementing `FromRequest` or `FromRequestParts` that automatically deserialize request components:

```
Handler Parameters:
  Path<Params>    → URL path parameters
  Query<Params>   → Query string
  Json<T>         → JSON body
  HeaderMap       → Request headers
  State<T>        → Application state
  String          → Raw body bytes (text mode)
  Bytes           → Raw body bytes (binary mode)
```

The type system enforces strict rules about extractor usage and ordering (documented separately).

## Core Components

### Router

The Router struct composes handlers and services into an HTTP request dispatcher. It:

- Provides declarative route definitions without macros
- Supports nesting for hierarchical route organization
- Enables method-based routing (GET, POST, etc.)
- Supports fallbacks for unmatched routes
- Manages path parameter extraction
- Is itself a Tower Service

Key operations:
- `Router::new()` - Create empty router
- `.route(path, handler)` - Register single handler
- `.nest(prefix, sub_router)` - Mount sub-router at prefix
- `.fallback(handler)` - Handle unmatched routes
- `.layer(layer)` - Add middleware to entire router
- `.route_layer(layer)` - Add middleware to specific routes
- `.with_state(state)` - Attach application state

### Extractors

Extractors are the primary mechanism for pulling data from HTTP requests. They implement either:

- **FromRequestParts<S>** - Non-body extractors (headers, path params, query strings)
- **FromRequest<S, B>** - Body-consuming extractors (only one per handler, must be last)

Common extractors include:
- `Path<T>` - URL path parameters with serde deserialization
- `Query<T>` - Query string deserialization
- `Json<T>` - JSON body parsing
- `HeaderMap` - Access all request headers
- `Header<T>` - Typed header extraction
- `State<T>` - Application state access
- `Extension<T>` - Request-scoped data injection
- `String` / `Bytes` - Raw body content
- `Form<T>` - Form data parsing

Extractors automatically handle rejection with configurable error responses.

### Responses

Any type implementing `IntoResponse` can be returned from a handler. Axum provides implementations for:

- **StatusCode** - HTTP status only
- **String** - Text with `text/plain; charset=utf-8`
- **Bytes** / **Vec<u8>** - Binary data as `application/octet-stream`
- **Json<T>** - JSON serialization with `application/json`
- **Html<T>** - HTML with `text/html; charset=utf-8`
- **()** - Empty response
- **Tuples** - Composite responses combining status, headers, body, extensions

Tuple responses enable powerful composition:
```
(StatusCode, String) → Status + text body
(StatusCode, HeaderMap, Json<T>) → Status + headers + JSON
(StatusCode, Vec<(HeaderName, HeaderValue)>, Html<T>) → Status + headers + HTML
```

### State Management

Application state is made available to handlers via the `State<T>` extractor. Key behavioral rules:

- State is stored as `Arc<T>` for thread-safe sharing across all requests
- State must be provided at server startup via `.with_state(state)`
- State is accessible in handlers as `State<T>` extractor
- Same state is available in middleware via `from_fn_with_state`
- Multiple state types can be combined using tuples

## Module Organization

The framework organizes functionality into logical modules:

- **axum::routing** - Router, routing traits, method routing combinators
- **axum::extract** - Extractors, rejection types, extractor traits
- **axum::response** - Response types, IntoResponse trait, status codes
- **axum::middleware** - Middleware utilities (from_fn, from_extractor)
- **axum::http** - Re-exports from http crate (StatusCode, HeaderMap, Uri, Method)
- **axum::body** - Body type and utilities
- **axum::json** - JSON serialization (re-export of serde_json)
- **axum::extract::ws** - WebSocket support (feature-gated)

## Performance Characteristics

Axum is designed for high performance through:

1. **Zero-cost abstractions** - Tower layers compile to direct service composition
2. **Async/await throughout** - Full async I/O with Tokio
3. **No unnecessary allocations** - Router uses efficient path matching
4. **Connection reuse** - Built on Hyper's persistent connections
5. **Middleware ordering** - Strategic layer placement for minimal overhead

## Behavioral Contracts

Several important behavioral contracts define Axum's operation:

### Request Processing Flow

1. Incoming request arrives at router
2. Router matches against registered routes (returns 404 if no match, unless fallback exists)
3. Middleware layers wrap the matched handler
4. Middleware layers execute in reverse registration order (last added receives request first)
5. Extractors run left-to-right in handler signature
6. Handler executes
7. Response flows back through middleware in reverse
8. Final response sent to client

### Extractor Ordering Rules

1. All `FromRequestParts` extractors run before any `FromRequest` extractors
2. `FromRequestParts` extractors can run in any order relative to each other
3. Only one `FromRequest` extractor per handler (the body-consuming one)
4. `FromRequest` extractors must be last in the parameter list
5. Body can only be consumed once—verified at compile time

### Error Propagation

1. Extractor rejections return HTTP 400 or 422 by default (configurable)
2. Handler errors that implement `IntoResponse` are converted to responses
3. Panics in handlers become HTTP 500 responses (in release builds)
4. Middleware can intercept errors and convert them

## Dependencies and Feature Flags

Core dependencies:
- **tokio** - Async runtime
- **hyper** - HTTP transport
- **tower** - Service abstraction
- **tower-service** - Service trait
- **tower-layer** - Layer trait

Optional features:
- **ws** - WebSocket support via tokio-tungstenite
- **macros** - Procedural macros for handlers (rarely needed)

## Important Notes

- Axum is runtime-agnostic but optimized for Tokio
- All handlers must be async functions
- Type safety is paramount—errors caught at compile time rather than runtime
- State management is explicit and type-safe
- Error handling uses standard Rust Result type

## Critical Behaviors to Verify

1. Router path matching is longest-match-first (most specific routes win)
2. State is shared via Arc<T>, not cloned per request
3. Extractors run in parameter order, not by type
4. Body can only be consumed once (enforced at compile time)
5. Middleware ordering is last-added-first-executed (for requests)
6. Fallbacks only match completely unmatched paths
7. Nested routers inherit middleware from parent routers

## Sources

- https://docs.rs/axum/latest/axum/
- https://docs.rs/axum/latest/axum/extract/
- https://docs.rs/axum/latest/axum/response/
- https://docs.rs/axum/latest/axum/routing/
- https://github.com/tokio-rs/axum
