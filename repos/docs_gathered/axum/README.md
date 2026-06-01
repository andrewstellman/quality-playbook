# Axum Documentation Collection

This directory contains comprehensive documentation for the Axum web framework, gathered from official sources, GitHub repositories, and technical specifications.

## Purpose

This documentation collection is designed to support **specification auditing** and **bug detection**—comparing actual code behavior against documented intent and behavioral contracts. It provides:

1. **Official behavioral specifications** from Axum documentation
2. **Architectural design** explaining framework components
3. **Behavioral contracts** specifying exact expected behavior
4. **Known issues and edge cases** documented by users and maintainers
5. **Type system rules** enforced at compile and runtime
6. **Integration patterns** for common use cases

## Quick Navigation

### Start Here
- **INDEX.md** - Comprehensive index with all document summaries
- **README.md** - This file

### Core Axum Features (in recommended reading order)
1. **01_OVERVIEW_AND_ARCHITECTURE.md** - Framework structure, core components
2. **02_ROUTING.md** - Router, routing rules, path matching, nesting
3. **03_EXTRACTORS.md** - Request data extraction, ordering rules, rejections
4. **04_RESPONSE_TYPES.md** - Response building, IntoResponse, tuples
5. **05_MIDDLEWARE.md** - Tower integration, middleware ordering, layer composition
6. **06_ERROR_HANDLING.md** - Error types, rejection patterns, custom errors
7. **07_WEBSOCKET_SUPPORT.md** - WebSocket handling, upgrade patterns
8. **08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md** - Precise rules and gotchas

## Key Concepts

### Handler Functions
Handlers are async functions that accept extractors and return response types:

```rust
async fn handler(
    Path(id): Path<u32>,
    Json(body): Json<Data>,
) -> impl IntoResponse {
    // ...
}
```

### Extractors
Extractors pull data from HTTP requests. The type system ensures:
- Only valid extractor combinations compile
- Body can only be consumed once
- FromRequestParts extractors come before FromRequest extractors

### Responses
Any type implementing `IntoResponse` can be returned. Tuples enable composition:

```rust
(StatusCode, Json(data))           // Status + JSON body
(StatusCode, HeaderMap, String)    // Status + headers + text
```

### Tower Integration
Axum uses Tower's Service abstraction for middleware, gaining access to a rich ecosystem of middleware from Hyper, Tonic, and community crates.

### Routing
Path matching is longest-first; nesting preserves hierarchy and can scope middleware.

## Using This Documentation

### For Finding Bugs
1. Identify the feature area (routing, extractors, middleware, etc.)
2. Read the comprehensive feature document from the list above
3. Check "Critical Behaviors to Verify" sections
4. Look at "Known Issues and Edge Cases" for similar problems
5. Review the behavioral contracts document for detailed rules

### For Understanding Architecture
Read in order:
1. 01_OVERVIEW_AND_ARCHITECTURE.md
2. 03_EXTRACTORS.md
3. 05_MIDDLEWARE.md
4. 08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md

### For Auditing Specific Features
1. Find the relevant document from the feature list
2. Read the "Behavioral Contracts" section
3. Check "Critical Behaviors to Verify" for what to test
4. Reference "Known Issues" for edge cases
5. Cross-reference the behavioral contracts document

### For Implementing New Code
1. Review the relevant feature document
2. Study the "Behavioral Contracts" carefully
3. Check examples for recommended patterns
4. Verify edge cases from "Known Issues"

## Critical Behavioral Rules (Must Verify)

### Type System - Enforced at Compile Time

1. **Extractor Ordering** - FromRequestParts before FromRequest
2. **Single Body Extractor** - Only one body-consuming extractor per handler
3. **State Type Match** - State<T> type must match what's provided via with_state()
4. **Response Type** - Handler return type must implement IntoResponse

### Extractor Behavior - Enforced at Runtime

1. **Extraction Order** - Extractors run left-to-right in parameter order
2. **Rejection Short-Circuits** - If extractor fails, handler doesn't execute
3. **Body Consumed Once** - Only one extractor can access the request body
4. **Extraction Failures Produce 4xx/5xx** - Not panic or silent failure

### Routing Behavior

1. **Longest Match First** - Most specific path wins in conflicts
2. **Nesting Strips Prefix** - Nested router doesn't see prefix in path
3. **Fallback Only on Path Miss** - Not triggered for method mismatches (405)
4. **Trailing Slashes Matter** - `/users` ≠ `/users/`, no auto-redirect

### Middleware Behavior

1. **Last Added is Outermost** - Most recently added layer processes requests first
2. **Body Consumption in Middleware** - Unavailable to handler afterward
3. **Extension Propagation** - Extensions set in middleware visible to handlers
4. **State Sharing** - Same Arc<T> across all middleware and handlers

## State Management Patterns

**Recommended:** Use `State<Arc<T>>` for application data:

```rust
struct AppState {
    db: Arc<Database>,
}

async fn handler(State(state): State<Arc<AppState>>) -> Response { }

let state = Arc::new(AppState { db: pool });
let router = Router::new()
    .route("/", get(handler))
    .with_state(state);
```

**Alternative:** Use Extensions for request-scoped data (from middleware):

```rust
async fn auth_middleware(mut req: Request, next: Next) -> Response {
    let user = extract_user(&req);
    req.extensions_mut().insert(user);
    next.run(req).await
}

async fn handler(Extension(user): Extension<User>) -> Response { }
```

## Common Pitfalls

1. **Calling multiple `.with_state()`** - Only last one is used
2. **Forgetting state in Router** - Handlers using State fail at runtime
3. **Middleware ordering confusion** - Last added is outermost/first to run
4. **Body extraction in middleware** - Unavailable to handlers afterward
5. **Extension not provided** - Results in 500 (indicates middleware bug)
6. **Wrong State type** - Compile-time error, good for early detection
7. **Serde error details leakage** - Default rejections expose schema
8. **Service backpressure** - Some Tower middleware won't work with Axum

## Document Statistics

- **Total files:** 9 markdown documents
- **Total coverage areas:** 8 major feature areas + comprehensive edge cases
- **Focus:** Behavioral contracts and specification details (not tutorials)
- **Target audience:** Code quality tools, specification auditors, bug hunters

## Key Features of This Documentation

### Specificity
Each document includes:
- **Behavioral Contracts** - Exact required behavior
- **Critical Behaviors to Verify** - What to test/audit
- **Known Issues** - Edge cases and gotchas
- **Verification examples** - Code showing correct vs incorrect behavior

### Completeness
Covers:
- All major framework components
- Type system enforcement rules
- Runtime behavioral contracts
- Integration patterns
- Error cases
- WebSocket support
- Middleware system
- State management

### Auditability
Documentation is designed for:
- Finding bugs in implementations
- Verifying specifications
- Understanding why behaviors matter
- Detecting edge case violations

## Sources

This documentation was gathered from:

1. **Official Axum Documentation**
   - https://docs.rs/axum/latest/axum/
   - https://docs.rs/axum/latest/axum/extract/
   - https://docs.rs/axum/latest/axum/response/
   - https://docs.rs/axum/latest/axum/routing/
   - https://docs.rs/axum/latest/axum/middleware/

2. **GitHub Repository**
   - https://github.com/tokio-rs/axum
   - Main branch examples and documentation
   - Discussion and issue resolution patterns

3. **Related Documentation**
   - Tower: https://docs.rs/tower/latest/tower/
   - Hyper: https://docs.rs/hyper/latest/hyper/
   - Tokio: https://docs.rs/tokio/latest/tokio/

## Using for Different Roles

### Code Quality Auditor
1. Start with 08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md
2. Read specific feature documents
3. Check "Critical Behaviors to Verify" sections
4. Look for contract violations in code

### Bug Investigator
1. Identify feature area
2. Read comprehensive feature document
3. Check "Known Issues" section
4. Review behavioral contracts
5. Look for similar reported issues

### Framework Developer
1. Read 01_OVERVIEW_AND_ARCHITECTURE.md
2. Deep dive into relevant feature documents
3. Study behavioral contracts carefully
4. Review all edge cases
5. Understand type system enforcement

### New Developer
1. Start with 01_OVERVIEW_AND_ARCHITECTURE.md
2. Read 02_ROUTING.md and 03_EXTRACTORS.md
3. Understand 05_MIDDLEWARE.md
4. Study examples in feature documents
5. Reference 08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md when unsure

## Last Updated

April 2026

---

For detailed behavioral specifications, see INDEX.md and the individual feature documents.
