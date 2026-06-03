# HTTP/1.1 Specifications - RFC 7230-7235

**Source:** RFC 7230-7235 Series (IETF) - Updated by RFC 9110
**References:**
- RFC 7230: HTTP/1.1 Message Syntax and Routing
- RFC 7231: HTTP/1.1 Semantics and Content
- RFC 7232: HTTP/1.1 Conditional Requests
- RFC 7233: HTTP/1.1 Range Requests
- RFC 7234: HTTP/1.1 Caching
- RFC 7235: HTTP/1.1 Authentication

**Note:** RFC 9110 (2022) obsoletes RFCs 7231, 7232, 7233, 7235 and portions of 7230, but RFC 7230-7235 remain important reference documents.

**Accessed:** April 2026

## HTTP/1.1 Message Syntax and Routing (RFC 7230)

### Message Structure

**Specification:** "All HTTP/1.1 messages consist of a start-line followed by a sequence of octets in a format similar to the Internet Message Format."

Message structure includes:
1. Start-line (request-line or status-line)
2. Header fields with field names and values
3. An empty line marking the header section's end
4. An optional message body

### Request Formatting
- Method, request target, and HTTP version
- CRLF line endings (Carriage Return Line Feed: `\r\n`)

### Response Formatting
- Protocol version, numeric status code, and descriptive phrase
- CRLF line endings

### Grammar Compliance
**Specification:** "A sender MUST NOT generate protocol elements that do not match the grammar defined by the corresponding ABNF rules."

**Implication for httpx:** Strict header and message format validation required.

## Content-Length and Transfer-Encoding (Critical for httpx)

### Content-Length Header

**Specification:** "Content-Length indicates the payload size in octets for requests and responses without transfer encoding applied."

**Key rule:** "A sender MUST NOT send a Content-Length header field in any message that contains a Transfer-Encoding header field."

### Transfer-Encoding and Content-Length Conflict

**Critical specification:** "When both Content-Length and Transfer-Encoding appear together, Transfer-Encoding takes precedence."

**Additional specification:** "such a message might indicate an attempt to perform request smuggling or response splitting and ought to be handled as an error."

**Security implication:** This is a known attack vector. Servers must detect and reject messages with both headers.

### Chunked Transfer Encoding

Used when message size is unknown at transmission time:
- `Transfer-Encoding: chunked`
- Messages divided into chunks with size prefix
- Last chunk has size 0
- Optional trailer headers follow

## HTTP Message Properties

### Persistent Connections

**Specification:** HTTP/1.1 supports persistent connections by default.

**Behavioral requirements:**
- Connections can be reused unless explicitly closed
- "Connection: close" header terminates connection
- "Connection: keep-alive" explicitly maintains connection
- Default (no header): Connection is persistent

**Implication for httpx:** Connection pooling relies on persistent connections.

### Connection Management

Key requirements:
- Proper closure handling
- Timeout management for idle connections
- Support for chunked transfer coding

## HTTP Methods (RFC 7231)

### Safe Methods
- GET, HEAD, OPTIONS, TRACE
- MUST NOT modify server state
- Can be called multiple times safely

### Idempotent Methods
- GET, HEAD, PUT, DELETE, OPTIONS, TRACE
- Multiple identical requests have same effect as single request
- Exceptions: PATCH is not idempotent by default

### Methods with Optional Body
- POST: May have body
- PUT: May have body
- PATCH: May have body
- GET, HEAD, DELETE, OPTIONS: Per spec, should not have body

**HTTP semantic rule:** "A payload within a GET request message has no defined semantics; sending a payload body on a GET request might cause some existing implementations to reject the request."

**HTTPX enforcement:** Enforces no-body constraint on GET, HEAD, DELETE, OPTIONS to prevent issues.

## Status Codes (RFC 7231)

### 1xx Informational
- 100 Continue: Client should continue sending body
- 101 Switching Protocols

### 2xx Success
- 200 OK
- 201 Created
- 204 No Content
- 206 Partial Content

### 3xx Redirection
- 300 Multiple Choices
- 301 Moved Permanently
- 302 Found
- 303 See Other
- 304 Not Modified
- 307 Temporary Redirect
- 308 Permanent Redirect

**Important:** Clients SHOULD follow redirects (3xx responses), but some may choose not to.

### 4xx Client Error
- 400 Bad Request
- 401 Unauthorized
- 403 Forbidden
- 404 Not Found
- etc.

### 5xx Server Error
- 500 Internal Server Error
- 501 Not Implemented
- 502 Bad Gateway
- 503 Service Unavailable
- etc.

## Header Field Specifications

### Header Field Format
- Name: value format
- Case-insensitive names
- Whitespace handling (optional around colon)

### Common Headers

**Content-Type:**
- Media type and charset
- Example: `Content-Type: text/html; charset=utf-8`

**Content-Length:**
- Decimal number of octets
- MUST match actual payload size

**Transfer-Encoding:**
- Specifies message encoding transformation
- Common: `chunked`

**Host:**
- Authority (domain and optional port)
- REQUIRED in HTTP/1.1 requests

**Connection:**
- Connection control options
- `keep-alive`: Maintain persistent connection
- `close`: Close connection after response

## Conditional Requests (RFC 7232)

### If-Match
- Precondition: ETag must match
- Used for safe updates

### If-None-Match
- Precondition: ETag must not match
- Used for GET (cache validation)

### If-Modified-Since
- Precondition: Resource modified after date
- Used for cache validation

### If-Unmodified-Since
- Precondition: Resource not modified after date
- Used for safe updates

## Range Requests (RFC 7233)

### Range Header
- Requests specific byte ranges
- Format: `Range: bytes=0-1023`
- Allows resuming partial downloads

### Content-Range Response
- Indicates which part of resource is being sent
- Format: `Content-Range: bytes 0-1023/10000`

## Caching (RFC 7234)

### Cache-Control Header
Controls caching behavior:
- `public`: Cacheable by any cache
- `private`: For single user only
- `max-age=3600`: Cache valid for 3600 seconds
- `no-cache`: Must revalidate before use
- `no-store`: Don't cache at all

### ETag Header
- Entity tag for cache validation
- Allows detection of resource changes
- Example: `ETag: "33a64df551"`

## Authentication (RFC 7235)

### Authorization Header
- Client credentials sent to server
- Format: `Authorization: Basic <credentials>`
- Also used for Bearer tokens, etc.

### WWW-Authenticate Header
- Server indicates required authentication
- Sent with 401 responses
- Specifies authentication scheme

## Behavioral Specifications for httpx Implementation

### Content Validation
HTTPX must validate:
- Content-Length matches actual payload
- Transfer-Encoding and Content-Length are mutually exclusive
- Headers follow ABNF grammar

### Connection Handling
HTTPX must:
- Respect persistent connection defaults
- Handle `Connection: close` properly
- Manage connection timeouts
- Implement keep-alive mechanisms

### Request Method Semantics
HTTPX enforces:
- Safe methods don't modify state
- Idempotent methods can be retried
- GET, HEAD, DELETE, OPTIONS don't have bodies

### Status Code Handling
HTTPX must:
- Support all status codes
- Allow 3xx redirects with proper header handling
- Raise exceptions or allow inspection of 4xx/5xx codes
