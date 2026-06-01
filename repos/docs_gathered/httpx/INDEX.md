# HTTPX Documentation Index - Comprehensive Behavioral Specification

**Generated:** April 2026
**Purpose:** Complete documentation for HTTPX library behavioral specifications, HTTP standards compliance, and design decisions
**Target Use:** Specification auditing to identify divergences between documented intent and code implementation

---

## Document Overview

This documentation collection provides a complete reference for understanding HTTPX's intended behavior, HTTP standards compliance requirements, and design decisions. The documents are organized by topic and include:

1. **Official Documentation** - HTTPX project documentation
2. **HTTP Standards** - RFC specifications that HTTPX must implement
3. **Design Specifications** - Architectural decisions and behavioral specifications
4. **Technical Deep Dives** - Detailed implementations and known issues

---

## Document List

### 1. 01_OFFICIAL_DOCS_OVERVIEW.md
**Content:** HTTPX project overview and basic information
**Key Topics:**
- What HTTPX is and key features
- Installation and requirements
- Project statistics and community
- Core dependencies
- Official documentation resources

**Spec Auditor Focus:** Foundation for understanding HTTPX's scope and claimed features

---

### 2. 02_QUICKSTART_AND_BASIC_API.md
**Content:** HTTPX basic usage and API reference
**Key Topics:**
- Basic HTTP method usage (GET, POST, PUT, DELETE, HEAD, OPTIONS)
- Response content access (.text, .content, .json())
- Common parameters (params, headers, data, files, json)
- Module-level helper functions
- Client and AsyncClient classes
- Core response classes (Response, Request, URL, Headers, Cookies, Proxy)

**Spec Auditor Focus:**
- Verify HTTP method implementations
- Check parameter validation and handling
- Validate response property access
- Confirm class interface contracts

---

### 3. 03_ASYNC_SUPPORT.md
**Content:** Asynchronous programming with HTTPX
**Key Topics:**
- AsyncClient usage and configuration
- Async request methods (all require await)
- Streaming operations (aiter_bytes, aiter_text, aiter_lines)
- Async backend support (AsyncIO, Trio, AnyIO)
- Best practices for connection pooling
- Performance characteristics

**Behavioral Specifications:**
- All async methods must be awaited
- Async streaming methods must be iterated with async for
- Single AsyncClient instance should be reused, not created per-request
- Connection pooling applies equally to async

**Spec Auditor Focus:**
- Verify all async methods properly await
- Check streaming implementation completeness
- Validate backend detection and fallback
- Confirm connection pooling works in async context

---

### 4. 04_TIMEOUTS.md
**Content:** HTTPX timeout configuration and behavior
**Key Topics:**
- Default 5-second timeout (CRITICAL DIFFERENCE from Requests)
- Per-request and client-level timeout configuration
- Four timeout types: connect, read, write, pool
- Timeout exceptions and handling
- Timeout override and disabling

**Behavioral Specifications:**
- HTTPX enforces 5-second timeout by default (Requests has no default)
- Four distinct timeout exceptions can be raised
- Each timeout type can be configured independently
- Request-level timeouts override client-level defaults
- Pool timeout occurs when connection pool exhausted

**Spec Auditor Focus:**
- Verify 5-second default is enforced
- Check timeout exception types are correctly raised
- Validate timeout configuration applies correctly
- Confirm timeout is applied to all operations

**CRITICAL BEHAVIORS:**
- Timeout=None disables timeouts entirely (allows indefinite hangs)
- Different timeout exceptions must be raised for different scenarios
- Pool timeout must respect max_connections limit

---

### 5. 05_CONNECTION_POOLING_AND_CLIENTS.md
**Content:** Connection pooling configuration and client lifecycle
**Key Topics:**
- Connection pooling mechanics and benefits
- Client configuration approaches (context manager, sharing)
- Configuration merging rules (headers/params/cookies combined, others override)
- httpx.Limits class (max_keepalive_connections, max_connections, keepalive_expiry)
- Connection reuse requirements
- HTTPCore pool architecture

**Behavioral Specifications:**
- Client instance reuses TCP connections to same host
- Default limits: max_keepalive_connections=20, max_connections=100, keepalive_expiry=5
- Headers/params/cookies are merged from client and request levels
- Other parameters use request-level override (not merge)
- Single client instance should be reused, not created per-request
- Multiple client instances lose pooling benefits

**CRITICAL BEHAVIORS:**
- Connection pooling is transparent (automatic reuse)
- Pool timeout occurs when max_connections reached
- Idle connections closed after keepalive_expiry seconds
- HTTP/2 mandates single connection per origin

**Known Issues:**
- O(n²) performance with many queued requests
- Server disconnection scenarios with HTTP/2
- Possible connection not closed on async cancellation

**Spec Auditor Focus:**
- Verify connections are reused for same-host requests
- Check limits are applied correctly
- Validate configuration merging behavior
- Confirm pool timeout exception is raised appropriately

---

### 6. 06_TRANSPORT_API.md
**Content:** Transport API for customizing HTTP transmission
**Key Topics:**
- HTTP, WSGI, ASGI built-in transports
- Custom transport implementation (BaseTransport, AsyncBaseTransport)
- Mount-based request routing (scheme, domain, port patterns)
- Transport responsibilities and limitations
- Interface separation (Client vs Transport)

**Behavioral Specifications:**
- Transport handles only low-level send/receive
- Transport does NOT handle redirects, auth, cookies
- Custom transport must implement handle_request method
- Mounts dictionary routes requests to different transports
- More specific mount patterns override general ones
- Mount=None bypasses transport for pattern

**Spec Auditor Focus:**
- Verify transport API is invoked correctly
- Check mount routing logic (specificity ordering)
- Validate WSGI/ASGI transport compatibility
- Confirm transport method signature and return type

---

### 7. 07_AUTHENTICATION.md
**Content:** HTTP authentication mechanisms
**Key Topics:**
- Basic authentication
- Digest authentication (challenge-response)
- NetRC authentication (from .netrc file)
- Custom authentication (callables, subclassing httpx.Auth)
- Auth flow control (requires_request_body, requires_response_body)
- Sync and async auth implementations
- Per-request and client-wide authentication

**Behavioral Specifications:**
- Basic auth uses base64 encoding (weak, use HTTPS)
- Digest auth uses challenge-response mechanism
- NetRC authentication is automatic for matching hosts
- Custom auth can modify request before sending
- Custom auth can handle response and retry
- Cross-domain redirects strip Authorization header automatically
- Authentication can be applied per-request or client-wide

**CRITICAL SECURITY BEHAVIOR:**
- Authorization header is automatically stripped on cross-domain redirects (prevents credential leakage)
- Bearer tokens can be used via custom headers

**Spec Auditor Focus:**
- Verify auth header modifications
- Check cross-domain redirect header stripping
- Validate auth flow mechanism (request modification, response handling)
- Confirm NetRC parsing and application

---

### 8. 08_HTTP2_SUPPORT.md
**Content:** HTTP/2 protocol support
**Key Topics:**
- HTTP/2 advantages (multiplexing, compression, prioritization)
- Installation requirements (pip install httpx[http2])
- Enabling HTTP/2 (http2=True parameter)
- Single connection per origin requirement
- Protocol version detection (response.http_version)
- Known HTTP/2 issues

**Behavioral Specifications:**
- HTTP/2 disabled by default (HTTP/1.1 is default)
- http2=True parameter enables HTTP/2
- Single TCP connection multiplexed for concurrent requests
- Response.http_version indicates protocol used
- Automatic fallback if server doesn't support HTTP/2
- Server disconnection handled differently than HTTP/1.1

**CRITICAL BEHAVIORS:**
- HTTP/2 specification requires single connection per origin (enforced by httpx)
- Multiple concurrent requests use stream multiplexing, not separate connections
- keepalive_expiry larger than server keep-alive can cause connection reuse issues

**Known Issues:**
- "Server disconnected" errors with HTTP/2 and large keepalive_expiry
- Stream allocation may create separate connections under high concurrency

**Spec Auditor Focus:**
- Verify single connection per origin for HTTP/2
- Check protocol version reporting
- Validate connection fallback behavior
- Confirm keepalive_expiry handling for HTTP/2

---

### 9. 09_PROXIES_AND_SSL.md
**Content:** Proxy configuration and SSL/TLS verification
**Key Topics:**
- HTTP proxy configuration
- Multiple proxy setup (mounts dictionary)
- Proxy authentication
- CONNECT tunneling for HTTPS proxies
- SOCKS proxy support
- SSL verification (default, custom context, disable)
- Client certificates (mTLS)
- Environment variables (HTTP_PROXY, HTTPS_PROXY, NO_PROXY, SSL_CERT_FILE, SSL_CERT_DIR)

**Behavioral Specifications:**
- Proxy URL format: "http://[user:pass@]host:port"
- HTTPS proxies should use "http://" scheme (tunneling requirement)
- Credentials embedded in proxy URL
- SSL verification enabled by default (certifi CA bundle)
- verify=False disables all SSL checking
- Custom SSL context via ssl.SSLContext object
- Environment variables trust by default (trust_env=True)

**CRITICAL BEHAVIORS:**
- Invalid SSL certificate raises ConnectError
- HTTPS proxy URLs use "http://" not "https://"
- Cross-proxy settings via mounts dictionary
- NO_PROXY bypasses proxy for specified hosts

**Known Issues:**
- HTTPS proxy support limited (HTTPS proxies not fully supported)
- Connection errors with HTTPS proxies

**Spec Auditor Focus:**
- Verify proxy URL parsing and authentication
- Check SSL verification enforcement
- Validate custom SSL context handling
- Confirm environment variable processing

---

### 10. 10_REQUESTS_COMPATIBILITY.md
**Content:** Differences between HTTPX and Requests library
**Key Topics:**
- Redirect following (not default in HTTPX, default in Requests)
- Response URL type (URL object vs string)
- File upload requirements (binary mode only)
- Character encoding differences (UTF-8 vs Latin-1)
- Cookie management (client-wide only, not per-request)
- Timeout behavior (5-second default vs no default)
- HTTP method body restrictions (GET/DELETE/HEAD/OPTIONS)
- Success status checking (is_success vs is_ok)

**CRITICAL BREAKING CHANGES:**
1. **Redirect following:** Must enable explicitly with follow_redirects=True
2. **File uploads:** Must open in binary mode (strict enforcement)
3. **GET/DELETE/HEAD/OPTIONS bodies:** Not supported via convenience methods
4. **Default timeout:** 5 seconds (Requests has no default)
5. **Character encoding:** UTF-8 default (Requests uses Latin-1)
6. **Cookie setting:** Client-wide only (not per-request)
7. **Status raising:** All non-2xx codes raise (Requests only 4xx/5xx)

**Migration Strategy:**
- Update imports
- Session() → Client()
- Add follow_redirects=True if needed
- Ensure files opened in binary mode
- Add explicit timeouts
- Use .request() for non-standard bodies

**Spec Auditor Focus:**
- Verify all breaking changes are enforced
- Check migration guide accuracy
- Validate incompatibility errors are helpful

---

### 11. 11_EXCEPTIONS_AND_ERROR_HANDLING.md
**Content:** Exception types and error handling patterns
**Key Topics:**
- Exception hierarchy (HTTPError base class)
- RequestError, TransportError
- Timeout exceptions (ConnectTimeout, ReadTimeout, WriteTimeout, PoolTimeout)
- Network errors (ConnectError, ReadError, WriteError, CloseError)
- Protocol errors (ProtocolError, RemoteProtocolError, ProxyError)
- Response errors (HTTPStatusError, DecodingError, TooManyRedirects)
- Stream errors (StreamConsumed, StreamClosed, ResponseNotRead)
- Other exceptions (InvalidURL, CookieConflict)

**Behavioral Specifications:**
- HTTPStatusError raised for ALL non-2xx responses (1xx, 3xx, 4xx, 5xx)
- Different timeout exceptions for different timeout types
- TooManyRedirects after exceeding max_redirects (default 20)
- StreamConsumed raised when attempting to read consumed stream
- HTTPStatusError has .request and .response properties

**CRITICAL BEHAVIORS:**
- raise_for_status() raises for ALL non-2xx codes (unlike Requests)
- Specific timeout exceptions allow precise error handling
- Max redirects default is 20

**Spec Auditor Focus:**
- Verify correct exception types are raised
- Check HTTPStatusError for all non-2xx codes
- Validate exception properties (request, response)
- Confirm max_redirects enforcement

---

### 12. 12_ENVIRONMENT_VARIABLES_AND_LOGGING.md
**Content:** Environment variable configuration and logging
**Key Topics:**
- Environment variable trust (trust_env parameter)
- Proxy variables (HTTP_PROXY, HTTPS_PROXY, ALL_PROXY, NO_PROXY)
- SSL variables (SSL_CERT_FILE, SSL_CERT_DIR)
- Standard logging setup
- httpx and httpcore loggers
- Advanced logging configuration
- Log filtering and debugging

**Behavioral Specifications:**
- Environment variables trusted by default (trust_env=True)
- HTTP_PROXY, HTTPS_PROXY, ALL_PROXY for proxy configuration
- NO_PROXY for proxy bypass (comma-separated hosts)
- SSL_CERT_FILE for CA bundle path
- SSL_CERT_DIR for CA directory (requires OpenSSL layout)
- httpx logger for high-level events
- httpcore logger for low-level network details
- Debug log format not guaranteed across versions

**Spec Auditor Focus:**
- Verify environment variable reading
- Check proxy variable precedence (HTTPS_PROXY > HTTP_PROXY > ALL_PROXY)
- Validate logging configuration
- Confirm trust_env=False disables environment variables

---

### 13. 13_HTTP_SPECIFICATIONS_RFC7230_7235.md
**Content:** HTTP/1.1 protocol specifications (RFC 7230-7235)
**Key Topics:**
- Message syntax and structure (start-line, headers, body)
- Request and response formatting
- Content-Length header
- Transfer-Encoding and chunked encoding
- Content-Length and Transfer-Encoding conflict (security issue)
- Persistent connections
- HTTP methods (safe, idempotent, with/without body)
- Status codes (1xx, 2xx, 3xx, 4xx, 5xx)
- Header fields (Content-Type, Host, Connection, etc.)
- Conditional requests (If-Match, If-None-Match, If-Modified-Since)
- Range requests
- Caching (Cache-Control, ETag)
- Authentication (Authorization, WWW-Authenticate)

**CRITICAL SPECIFICATIONS:**
- Content-Length MUST NOT appear with Transfer-Encoding header
- Both headers appearing indicates request smuggling/response splitting attack
- GET, HEAD, DELETE, OPTIONS SHOULD NOT have body (HTTPX enforces)
- HTTP/1.1 default is persistent connections
- Chunked encoding used when size unknown

**Behavioral Requirements for HTTPX:**
- Validate Content-Length/Transfer-Encoding mutual exclusivity
- Enforce no-body constraint on safe methods
- Support persistent connections by default
- Implement chunked encoding support
- Follow ABNF grammar for message format

**Spec Auditor Focus:**
- Verify RFC compliance in message construction
- Check Content-Length/Transfer-Encoding validation
- Validate HTTP method semantics enforcement
- Confirm persistent connection handling

---

### 14. 14_HTTP2_SPECIFICATIONS_RFC9113.md
**Content:** HTTP/2 protocol specifications (RFC 9113)
**Key Topics:**
- Connection preface (24-octet client sequence + SETTINGS)
- Frame format (9-octet header + payload)
- Frame types (HEADERS, DATA, SETTINGS, RST_STREAM, WINDOW_UPDATE, GOAWAY, PING, etc.)
- Stream lifecycle (idle → open → half-closed → closed)
- Stream state transitions
- Flow control (window-based)
- Multiplexing benefits
- Connection errors vs stream errors
- Settings negotiation and acknowledgment

**CRITICAL SPECIFICATIONS:**
- Connection preface MUST be sent correctly
- SETTINGS frames MUST be acknowledged
- Stream order is significant (HEADERS before DATA)
- Single connection per origin for HTTP/2
- Flow control window management required
- Stream IDs: client uses odd, server uses even

**Behavioral Requirements for HTTPX:**
- Proper connection preface implementation
- SETTINGS frame negotiation and acknowledgment
- Stream state machine implementation
- Flow control window tracking
- Single connection per origin enforcement
- GOAWAY frame handling

**Known Issues:**
- HTTP/2 disconnection handling with keepalive_expiry
- Stream allocation under high concurrency

**Spec Auditor Focus:**
- Verify connection preface is correct
- Check SETTINGS acknowledgment
- Validate stream state transitions
- Confirm flow control implementation
- Verify single connection per origin

---

### 15. 15_COOKIES_RFC6265.md
**Content:** HTTP Cookies specifications (RFC 6265)
**Key Topics:**
- Cookie mechanism (Set-Cookie response, Cookie request)
- Cookie attributes (Domain, Path, Secure, HttpOnly, Max-Age, Expires, SameSite)
- Domain matching (exact, suffix with period requirement, no IP matching)
- Path matching (exact, suffix with /, directory separator)
- Cookie scope and security
- Cookie storage and transmission rules
- Expiration handling (Max-Age vs Expires)

**CRITICAL SPECIFICATIONS:**
- Domain suffix match requires period before domain
- Path suffix must be "/" or followed by "/"
- Domain=example.com matches example.com and *.example.com, not IP addresses
- Secure flag restricts to HTTPS only
- HttpOnly flag restricts JavaScript access
- SameSite prevents cross-site cookie transmission
- Max-Age takes precedence over Expires

**Behavioral Requirements for HTTPX:**
- Implement domain-matching algorithm exactly per RFC
- Implement path-matching algorithm with three conditions
- Track Max-Age and Expires for expiration
- Respect Secure flag (HTTPS only)
- Strip cookies from cross-domain redirects (or send appropriately based on domain)
- Default path computation from request URL

**Spec Auditor Focus:**
- Verify domain-matching algorithm
- Check path-matching algorithm with three conditions
- Validate cookie expiration handling
- Confirm cookie transmission rules (domain, path, secure)
- Check cross-domain redirect behavior

---

### 16. 16_GITHUB_DESIGN_DECISIONS.md
**Content:** HTTPX design decisions from GitHub discussions
**Key Topics:**
- Redirect behavior (not followed by default)
- Request body restrictions (GET/DELETE/HEAD/OPTIONS)
- Transport API separation (high-level vs low-level)
- Response reading (content cached after read)
- Path handling (normalization)
- Cross-domain redirect header stripping
- Connection pooling and long-running requests
- Known behavioral edge cases

**Behavioral Specifications from Discussions:**
- Redirects not followed by default (explicit opt-in)
- GET, DELETE, HEAD, OPTIONS methods cannot have bodies (enforced)
- Authorization header stripped on cross-domain redirects
- Response body can be read multiple times (cached)
- Connection pool issues with keepalive_expiry
- High concurrency connection allocation issues
- Stream consumption behavior differences

**Important Design Rationale:**
- "Break with requests compatibility to reduce incorrect usage"
- "Keep things clear and concise"
- Explicit over implicit
- HTTP semantic compliance

**Spec Auditor Focus:**
- Verify design decisions are implemented as discussed
- Check redirect behavior is explicit opt-in
- Validate request body restrictions
- Confirm header stripping on cross-domain redirects
- Verify response body caching

---

### 17. 17_TECHNICAL_ARTICLES_AND_DESIGN.md
**Content:** Technical articles and design insights
**Key Topics:**
- HTTPX vs Requests vs AIOHTTP comparison
- Design philosophy (explicitness, safety, HTTP compliance)
- Dual-mode operation (sync and async)
- Modern HTTP client features
- HTTPCore architecture
- Performance characteristics
- Use case implications
- Known limitations

**Design Philosophy:**
- **Explicitness over implicit:** Redirects explicit, no default redirect following
- **HTTP semantic compliance:** GET/DELETE/HEAD/OPTIONS no bodies
- **Safety first:** Default timeouts, SSL verification, credential stripping
- **Clear separation:** Client vs Transport responsibilities

**Spec Auditor Focus:**
- Verify design philosophy is implemented
- Check performance characteristics match claims
- Validate use case appropriateness
- Confirm known limitations are understood

---

## Summary: Key Behavioral Specifications for Spec Auditing

### CRITICAL BEHAVIORS TO AUDIT

1. **Default Timeout:** 5 seconds (not None like Requests)
2. **Redirect Following:** Not by default (requires follow_redirects=True)
3. **Exception Handling:** HTTPStatusError for ALL non-2xx (not just 4xx/5xx)
4. **Request Bodies:** GET, DELETE, HEAD, OPTIONS cannot have bodies
5. **Cross-Domain Redirects:** Authorization header automatically stripped
6. **Connection Pooling:** Single instance reuse required for benefits
7. **HTTP/2:** Single connection per origin (RFC 9113 requirement)
8. **File Uploads:** Binary mode required
9. **SSL Verification:** Enabled by default
10. **Environment Variables:** Trusted by default (trust_env=True)

### SPECIFICATION COMPLIANCE AREAS

1. **RFC 7230-7235:** HTTP/1.1 message format, methods, headers
2. **RFC 9113:** HTTP/2 framing, connection preface, settings
3. **RFC 6265:** Cookie domain/path matching, expiration
4. **Transport API:** Low-level send/receive only
5. **Error Handling:** Specific exception types for different scenarios

### COMMON AUDIT QUESTIONS

- Does HTTPX enforce the default 5-second timeout?
- Are HTTP methods enforced for no-body requirement?
- Is Authorization header stripped on cross-domain redirects?
- Are all non-2xx responses raising HTTPStatusError?
- Is HTTP/2 using single connection per origin?
- Are cookies matched correctly by domain and path?
- Is connection pooling transparent and automatic?
- Are environment variables being read correctly?

---

## Using This Documentation

### For Code Review
1. Read the behavioral specification document for the feature
2. Check RFC specifications for protocol requirements
3. Verify design decision rationale from GitHub discussions
4. Compare code implementation against expected behavior

### For Bug Investigation
1. Identify the feature area (timeouts, redirects, cookies, etc.)
2. Read the comprehensive document for that feature
3. Check the "CRITICAL BEHAVIORS" section
4. Review "Known Issues" section
5. Check RFC specifications for protocol requirements

### For Feature Implementation
1. Read the behavioral specification
2. Understand design decisions from GitHub discussions
3. Check RFC specifications for requirements
4. Review existing implementation patterns
5. Ensure HTTP/2 and HTTP/1.1 both supported if applicable

---

## Documentation Maintenance

This documentation was gathered from:
- Official HTTPX documentation (python-httpx.org)
- HTTP RFCs (7230-7235, 9113, 6265, 9110)
- GitHub encode/httpx discussions and issues
- Technical articles and design comparisons
- HTTPCore documentation

**Last Updated:** April 2026

---

## Files Included

1. 01_OFFICIAL_DOCS_OVERVIEW.md
2. 02_QUICKSTART_AND_BASIC_API.md
3. 03_ASYNC_SUPPORT.md
4. 04_TIMEOUTS.md
5. 05_CONNECTION_POOLING_AND_CLIENTS.md
6. 06_TRANSPORT_API.md
7. 07_AUTHENTICATION.md
8. 08_HTTP2_SUPPORT.md
9. 09_PROXIES_AND_SSL.md
10. 10_REQUESTS_COMPATIBILITY.md
11. 11_EXCEPTIONS_AND_ERROR_HANDLING.md
12. 12_ENVIRONMENT_VARIABLES_AND_LOGGING.md
13. 13_HTTP_SPECIFICATIONS_RFC7230_7235.md
14. 14_HTTP2_SPECIFICATIONS_RFC9113.md
15. 15_COOKIES_RFC6265.md
16. 16_GITHUB_DESIGN_DECISIONS.md
17. 17_TECHNICAL_ARTICLES_AND_DESIGN.md
18. INDEX.md (this file)

Total: 18 comprehensive documentation files covering HTTPX behavioral specifications, HTTP standards, and design decisions.
