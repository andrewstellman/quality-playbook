# HTTPX GitHub Discussions - Design Decisions and Behavioral Specifications

**Source:** GitHub encode/httpx Discussions and Issues
**Accessed:** April 2026

## Redirect Behavior Design Decision

**Discussion:** Version 0.20.0 release discussion
**Key decision:** Redirect responses are no longer automatically followed unless specifically requested

**Behavioral rationale:**
- Prioritizes explicit approach to redirects
- Prevents code that unintentionally issues multiple requests due to misconfigured URLs
- Avoids hidden network requests that developers might not expect

**Configuration:**
- Global client setting: `Client(follow_redirects=True)`
- Per-request: `.get(..., follow_redirects=True)`

**Important implication:** Default behavior changed from requests library for better explicitness.

## Request Body Restrictions Design

**Discussion:** "GET method doesn't support body payload" and related discussions
**Key specification:** "The HTTP GET, DELETE, HEAD, and OPTIONS methods are specified as not supporting a request body."

**HTTPX enforcement:**
- `.get()`, `.delete()`, `.head()`, `.options()` functions do NOT support content, files, data, or json arguments
- Raises error if attempted

**Design rationale:**
- "Several design decisions have been made to break with requests compatibility to reduce incorrect usage"
- "keep things clear and concise"
- HTTP specification: "a payload within a GET request message has no defined semantics"
- "sending a payload body on a GET request might cause some existing implementations to reject the request"

**Workaround for edge cases:**
```python
# Use generic .request() method for non-standard requests
httpx.request(method="DELETE", url=url, content=b'body')
```

## Transport API Architecture

**Key design principle:** Clean interface separation

**Split responsibility:**
- **Client (httpx):** High-level models, cookie handling, redirects, authentication, user-friendly configuration
- **Transport API (httpcore):** "just send an HTTP request" - low-level operations

**Behavioral implication:**
- Transport handles only: sending request, receiving response
- Transport does NOT handle: redirects, auth, cookies, higher-level HTTP semantics
- Clear boundary enables simpler reasoning about each component

## Response Reading Behavior

**Behavioral specification:**
- `.read()` or `.aread()` methods read and return bytewise-content after decompression
- Once read, response body remains available
- Can still call `iter_bytes()` or `aiter_bytes()`, which re-return the content

**Important:** Multiple reads of same response are allowed; content is cached.

## Path Handling in URLs

**Behavioral specification:**
- HTTPX handles path traversal, same as browser behavior and requests library
- Example: `../` sequences are normalized
- Follows standard URL path semantics

## Redirect and Authentication Headers

**Discussion:** "follow_redirects dropping Bearer token header"
**Behavioral specification:**

**Same-domain redirects:** Authorization headers are preserved
**Cross-domain redirects:** Authorization headers are **automatically stripped** to prevent credential leakage

**Implementation requirement:** HTTPX must detect cross-domain redirects and remove:
- Authorization header
- Proxy-Authorization header
- Other credential headers

**Security rationale:** Prevents accidentally sending credentials to third-party sites.

## Connection Pooling and Long-Running Requests

**Issue:** PoolTimeout errors with Kubernetes watches and long-lived connections

**Problem scenario:**
- `PoolTimeout` raised when pool exhausted
- Especially with `keepalive_expiry` larger than server's keep-alive timeout
- HTTP/2 connection reuse issues when servers disconnect unexpectedly

**Known issues:**
- "Server disconnected" errors reduce in frequency if pooling disabled
- Connection pool may not be closed correctly in AsyncClient when cancelling requests
- HTTP/2 streams may end up on separate connections under high concurrency

**Behavioral requirement:** HTTPX must handle connection reuse and pool exhaustion gracefully.

## Params and Headers - None Values

**Discussion:** "Params and headers - None value (and comparison with requests)"
**Behavioral specification:**

**In HTTPX:**
- `None` values in params or headers are explicitly handled
- Different from requests library behavior
- More predictable and explicit

**Implementation note:** None values should not be silently ignored but handled consistently.

## Content-Length Detection

**Issue:** "detect length of file-like object?"
**Behavioral difference:**

**HTTPX:**
- Uses Transfer-Encoding: chunked for file-like objects (BytesIO, etc.)
- Doesn't attempt to detect length

**Requests library:**
- Attempts to detect size
- Falls back to chunked encoding

**Implication:** Streaming uploads with HTTPX use chunked encoding by default.

## Important Design Decisions Summary

### Explicitness Over Implicit Behavior
- Redirects not followed by default
- Exceptions raised for all non-2xx codes
- Request body restrictions enforced
- Headers/params with None handled explicitly

### HTTP Semantic Compliance
- GET, DELETE, HEAD, OPTIONS don't support bodies
- Proper status code handling
- Correct redirect behavior
- Authentication header stripping on cross-domain redirects

### Clear Separation of Concerns
- Client handles high-level operations
- Transport handles low-level network
- Distinct responsibilities prevent bugs

### Security-First Approach
- Default timeouts prevent indefinite hangs
- Credential stripping on cross-domain redirects
- SSL verification by default
- Connection validation

## Known Behavioral Edge Cases

### Stream Consumption
- Some methods raise StreamConsumed when stream already read
- Others return empty content
- Behavior documented per method

### Header Case Sensitivity
- Header names are case-insensitive
- Header values are case-sensitive
- Access via dict-like interface

### URL Normalization
- Handles path traversal correctly
- Follows standard URL semantics
- Browser-compatible behavior

### Connection Pool Sizing
- Connection limit can be exhausted under high concurrency
- PoolTimeout when waiting for available connection
- Configurable via Limits class

## Maintainer Philosophy

Based on design discussions, maintainers prioritize:

1. **Correctness** - Following HTTP specifications
2. **Explicitness** - Clear, unsurprising behavior
3. **Safety** - Secure by default (timeouts, SSL, redirects)
4. **Clarity** - Preventing common mistakes through API design
5. **Performance** - Efficient connection pooling and multiplexing

These principles sometimes conflict with the requests library's approach, leading to intentional breaking changes.
