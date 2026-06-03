# Axum Documentation Index

**Last Updated:** April 2026  
**Framework Version:** 0.8.8+  
**Total Documents:** 9

## Document Overview

### 01_OVERVIEW_AND_ARCHITECTURE.md (320 lines)
**Focus:** Framework structure, design principles, core components

**Key Topics:**
- Tower-based design philosophy
- Handler-first architecture
- Core components: Router, Extractors, Responses, State
- Module organization
- Performance characteristics
- Behavioral contracts overview

**Critical Behaviors:**
- Router path matching is longest-match-first
- State is shared via Arc<T> across all requests
- Extractors run left-to-right in parameter order
- Body consumed once (enforced at compile time)
- Middleware ordering is last-added-first-executed

**Use for:** Understanding overall architecture and design decisions

---

### 02_ROUTING.md (320 lines)
**Focus:** Router implementation, path matching, routing rules, nesting

**Key Topics:**
- Router struct and creation
- Route registration (.route, .nest, .fallback)
- Path syntax (literals, parameters, greedy matching)
- Method routing (get, post, put, delete, etc.)
- Nesting and hierarchical organization
- Middleware application levels
- State management with Router
- Route matching and conflict resolution
- Router as Tower Service

**Critical Behaviors:**
- Path matching is longest-first (most specific wins)
- Fallback only triggers on path miss (not method miss)
- Nesting strips prefix before routing in nested router
- Trailing slashes are significant (/users ≠ /users/)
- Method not allowed (405) is route match, not fallback
- Nested routers can have different middleware scopes

**Spec Auditor Focus:**
- Verify path matching priority
- Check nesting prefix stripping
- Test 404 vs 405 distinction
- Verify fallback scope
- Check middleware ordering across nested routers

**Use for:** Understanding routing mechanics, path matching rules, nesting behavior

---

### 03_EXTRACTORS.md (280 lines)
**Focus:** Extractor system, types, ordering rules, rejections, custom extractors

**Key Topics:**
- FromRequestParts vs FromRequest traits
- Standard extractors (Path, Query, Json, State, Headers, etc.)
- Extractor ordering rules (parts before body, single body extractor)
- Optional extractors
- Custom extractor implementation
- Rejection handling and error propagation
- Body consumption and size limits
- Fallible extractors and Result handling

**Critical Behaviors:**
- Parts-before-body ordering enforced at compile time
- Single body-consuming extractor per handler (compile time)
- Extractors run left-to-right in parameter order
- Body can only be consumed once (type system enforces)
- Rejection prevents handler execution (short-circuit)
- Extension missing results in 500 (indicates middleware bug)
- Body is async stream, consumed at most once

**Spec Auditor Focus:**
- Verify extractor ordering enforcement
- Check body consumption limits
- Verify rejection status codes
- Test single body extractor constraint
- Check Option<T> behavior for optional extraction
- Verify rejection prevents handler execution

**Known Issues:**
- Extension missing → 500 (indicates middleware problem)
- Serde errors leak details (security issue)
- Large body uploads cause 413 on limit
- Charset issues on String extractor (non-UTF-8 → 400)

**Use for:** Understanding extractor types, ordering rules, rejection handling

---

### 04_RESPONSE_TYPES.md (300 lines)
**Focus:** Response building, IntoResponse trait, response composition, content-type handling

**Key Topics:**
- IntoResponse trait and implementation
- Built-in response types (StatusCode, String, Json, Html, Bytes)
- Composite responses via tuples
- Custom response types
- Response builder pattern
- Content-type negotiation (lack thereof)
- Special response types (NoContent, Redirect)
- Response extension propagation

**Critical Behaviors:**
- IntoResponse is required for handler return types
- Tuples enable composition (status, headers, body)
- First tuple element is status code
- Content-Type determined by response type (no negotiation)
- Headers can be added/modified on Response
- Extensions propagate downstream to middleware

**Spec Auditor Focus:**
- Verify IntoResponse trait coverage
- Check tuple ordering and composition
- Verify content-type assignment per type
- Test custom response implementation
- Check header modification after creation
- Verify extension propagation

**Use for:** Understanding response composition, content-type handling, IntoResponse implementation

---

### 05_MIDDLEWARE.md (350 lines)
**Focus:** Middleware system, Tower integration, layer composition, state access

**Key Topics:**
- Tower Service abstraction
- Middleware application levels (router, route, handler)
- Layer stacking order and request flow
- from_fn for simple middleware
- from_fn_with_state for state access
- Custom Tower Service middleware
- Built-in middleware patterns
- Middleware composition
- Error handling in middleware
- Tower middleware compatibility
- Best practices and patterns

**Critical Behaviors:**
- Last .layer() is outermost (processes requests first)
- ServiceBuilder reverses order (top-to-bottom)
- Next execution must call next.run() to proceed
- State in middleware must be Arc<T> or Clone
- Error handling is middleware responsibility
- Route-level middleware scoped to specific routes only
- Backpressure-sensitive Tower middleware incompatible

**Spec Auditor Focus:**
- Verify layer ordering (last added outermost)
- Check request flow direction
- Verify ServiceBuilder order reversal
- Test route-level middleware scope
- Check state sharing across middleware
- Test error handling patterns
- Verify backpressure compatibility

**Known Issues:**
- Backpressure incompatibility with some Tower middleware
- Request body consumption in middleware unavailable to handler
- Nested routers and middleware scope confusion
- State type mismatches (caught at compile time)
- from_fn type inference issues

**Use for:** Understanding middleware patterns, layer ordering, state access in middleware

---

### 06_ERROR_HANDLING.md (310 lines)
**Focus:** Error types, rejection patterns, custom errors, error propagation

**Key Topics:**
- Extractor rejections and handling
- Common rejection patterns (Path, Query, Json, etc.)
- Handling rejections in handlers (Result wrapping)
- Optional extraction (Option<T>)
- Custom error types
- JSON error responses
- Error propagation flow
- Fallible extractors
- Error details leakage
- Panic handling
- Result type in handlers
- Multiple error types
- Middleware error handling

**Critical Behaviors:**
- Extractor rejections are immediate (short-circuit handler)
- Rejections are IntoResponse (auto-converted)
- Handler errors propagate via Result
- Error type must implement IntoResponse
- Extension missing → 500 (middleware bug)
- Panics → 500 (graceful degradation)
- Default rejections expose error details (security)

**Spec Auditor Focus:**
- Verify rejection status codes per extractor
- Check rejection short-circuit behavior
- Test error propagation
- Verify IntoResponse implementation
- Check details leakage
- Test panic handling
- Verify multiple error type handling

**Known Issues:**
- Detailed error leakage (default rejections)
- Error type inference complexity
- Body already consumed (second extractor fails)
- Serde error messages expose schema

**Use for:** Understanding error handling patterns, custom error types, rejection behavior

---

### 07_WEBSOCKET_SUPPORT.md (280 lines)
**Focus:** WebSocket handling, upgrade patterns, message handling, concurrent operations

**Key Topics:**
- WebSocketUpgrade extractor
- Basic WebSocket handler pattern
- WebSocket type and Message types
- Concurrent message handling
- Protocol negotiation
- Error handling in WebSocket
- State integration
- Middleware in WebSocket handlers
- Connection lifecycle
- Broadcasting to multiple clients
- Performance considerations
- Router configuration

**Critical Behaviors:**
- Upgrade is background task (handler returns immediately)
- 101 Switching Protocols sent automatically
- Single connection per upgrade
- split() enables concurrent send/receive
- Message order preserved within stream
- Closure owns WebSocket (lives until connection closes)
- State sharing via Arc<T>
- Error indicates connection closed

**Spec Auditor Focus:**
- Verify upgrade returns 101
- Check background task execution
- Test concurrent message handling
- Verify split() sender/receiver independence
- Check state integration
- Test protocol negotiation
- Verify error handling patterns

**Known Issues:**
- Slow message processing causes backlog
- Memory leaks possible with forgotten handlers
- Protocol violations cause connection loss
- Ping/Pong handling (typically automatic)
- Graceful shutdown complexity

**Use for:** Understanding WebSocket patterns, upgrade mechanics, concurrent handling

---

### 08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md (420 lines)
**Focus:** Precise behavioral rules, type system enforcement, edge cases, gotchas

**Key Topics:**
- Extractor ordering and type system enforcement
- Request body consumption rules
- Routing and path matching contracts
- State management contracts
- Middleware ordering and composition
- Error propagation and rejection
- Body type and content-type contracts
- Important behavioral contract summary
- Known behavioral gotchas

**Critical Contracts:**
- **Compile-time:** Extractor ordering, single body extractor, state type, response type
- **Runtime:** Extractor order execution, rejection short-circuit, body consumed once, state sharing
- **Routing:** Longest match first, nesting prefix stripping, fallback scope, trailing slashes
- **Middleware:** Layer ordering, body consumption, extension propagation, state sharing

**Edge Cases:**
- State extractor placement (allowed before body)
- Multiple State<T> extractors (allowed for different types)
- Nested router fallback behavior
- Path parameter conflicts
- Trailing slash normalization (doesn't happen)
- Body size limits per extractor
- Content-Type defaults
- Serde error exposure

**Spec Auditor Focus - Must Verify:**
1. Router path matching priority
2. State is Arc<T> shared across requests
3. Extractor ordering enforcement (parts before body)
4. Single body extractor rule
5. Body consumed once
6. Middleware layer ordering (last added outermost)
7. Rejection short-circuits handler
8. State type match at compile time

**Use for:** Comprehensive behavioral reference, edge case handling, specification verification

---

## Cross-Document Navigation

### For Learning Path
1. Start: 01_OVERVIEW_AND_ARCHITECTURE.md
2. Routing: 02_ROUTING.md
3. Extractors: 03_EXTRACTORS.md
4. Responses: 04_RESPONSE_TYPES.md
5. Middleware: 05_MIDDLEWARE.md
6. Error Handling: 06_ERROR_HANDLING.md
7. WebSockets: 07_WEBSOCKET_SUPPORT.md
8. Deep Dive: 08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md

### By Topic

**Request Handling:**
- 03_EXTRACTORS.md (extraction)
- 04_RESPONSE_TYPES.md (responses)
- 06_ERROR_HANDLING.md (errors)

**Framework Architecture:**
- 01_OVERVIEW_AND_ARCHITECTURE.md
- 02_ROUTING.md
- 05_MIDDLEWARE.md

**Advanced Topics:**
- 07_WEBSOCKET_SUPPORT.md
- 08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md

**Specification Auditing:**
- 08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md (primary)
- Feature documents for specific areas
- "Critical Behaviors to Verify" sections

### By Behavior Category

**Type System (Compile-Time):**
- 03_EXTRACTORS.md - Ordering, single body
- 04_RESPONSE_TYPES.md - IntoResponse
- 01_OVERVIEW_AND_ARCHITECTURE.md - Overview
- 08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md - Details

**Routing:**
- 02_ROUTING.md - Complete reference
- 08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md - Contracts

**Middleware:**
- 05_MIDDLEWARE.md - Complete reference
- 08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md - Contracts

**Error Handling:**
- 06_ERROR_HANDLING.md - Complete reference
- 03_EXTRACTORS.md - Rejection patterns
- 08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md - Propagation rules

## Quick Reference - Key Contracts

| Contract | Location | Type |
|----------|----------|------|
| Extractor ordering (parts before body) | 03_EXTRACTORS.md | Compile-time |
| Single body extractor | 03_EXTRACTORS.md | Compile-time |
| Path matching (longest first) | 02_ROUTING.md | Runtime |
| Nesting prefix stripping | 02_ROUTING.md | Runtime |
| Layer ordering (last added outermost) | 05_MIDDLEWARE.md | Runtime |
| State is Arc<T> shared | 01_OVERVIEW_AND_ARCHITECTURE.md | Runtime |
| Rejection short-circuits handler | 06_ERROR_HANDLING.md | Runtime |
| Body consumed once | 03_EXTRACTORS.md | Compile-time |
| Content-Type determined by response type | 04_RESPONSE_TYPES.md | Runtime |
| Extension missing → 500 | 06_ERROR_HANDLING.md | Runtime |

## Coverage Matrix

| Feature | Document | Depth |
|---------|----------|-------|
| Router | 02_ROUTING.md | Comprehensive |
| Extractors | 03_EXTRACTORS.md | Comprehensive |
| Responses | 04_RESPONSE_TYPES.md | Comprehensive |
| Middleware | 05_MIDDLEWARE.md | Comprehensive |
| Error Handling | 06_ERROR_HANDLING.md | Comprehensive |
| WebSockets | 07_WEBSOCKET_SUPPORT.md | Comprehensive |
| Behavioral Contracts | 08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md | Deep |
| Architecture | 01_OVERVIEW_AND_ARCHITECTURE.md | Overview |

## Sources Used

- https://docs.rs/axum/latest/axum/
- https://docs.rs/axum/latest/axum/extract/
- https://docs.rs/axum/latest/axum/response/
- https://docs.rs/axum/latest/axum/routing/
- https://docs.rs/axum/latest/axum/middleware/
- https://github.com/tokio-rs/axum
- https://docs.rs/tower/latest/tower/

## Tips for Different Users

### For Code Quality Tools
- Prioritize: 08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md
- Reference: Individual feature documents for details
- Focus: Type system enforcement and runtime contracts

### For Bug Hunters
- Start: Identify feature area
- Read: Corresponding feature document
- Check: "Known Issues" and edge cases
- Reference: 08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md

### For Framework Contributors
- Read: All documents in order
- Deep study: 08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md
- Focus: Type system and edge cases

### For Learning
- Follow: Learning path above
- Skip: 08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md initially
- Reference: Individual feature documents

---

**Total Documentation:** ~2,500 lines across 9 files
**Format:** Markdown with code examples
**Focus:** Behavioral contracts and specification verification
**Currency:** April 2026, Axum 0.8.8+
