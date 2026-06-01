# HTTP Cookies Specifications - RFC 6265

**Source:** RFC 6265 - HTTP State Management Mechanism
**References:**
- RFC 6265 official specification: https://datatracker.ietf.org/doc/html/rfc6265

**Accessed:** April 2026

## Overview

RFC 6265 defines the HTTP Cookie and Set-Cookie header fields. These header fields enable HTTP servers to store state (called cookies) at HTTP user agents, "letting the servers maintain a stateful session over the mostly stateless HTTP protocol."

**Key purpose:** Enable state persistence across multiple HTTP requests to build sessions and remember user preferences.

## Cookie Mechanism

### Basic Flow

1. **Server sends:** Set-Cookie header in HTTP response
   - Contains cookie name, value, and attributes

2. **User agent receives:** Stores the cookie according to attributes
   - Domain
   - Path
   - Expiration
   - Security flags

3. **User agent returns:** Cookie header in subsequent requests
   - Only when domain and path match
   - Only when not expired
   - Only when security conditions met (HTTPS if Secure flag)

### Example

**Server send:**
```
Set-Cookie: SessionID=31d4d96e407aad42
```

**User agent return (subsequent requests):**
```
Cookie: SessionID=31d4d96e407aad42
```

## Cookie Attributes

### Name and Value
- **Format:** `name=value`
- **Restrictions:** Cannot contain semicolon, comma, or whitespace (in standard format)
- **Encoding:** URL encoding used for special characters

### Domain Attribute
**Syntax:** `Domain=example.com`

**Purpose:** Specifies which hosts receive the cookie

**Matching rules:**
1. **Exact match:** Domain string and request host are identical
2. **Suffix match:** Domain is suffix of request host with conditions:
   - The last character not in domain is a period (".")
   - Request host is a host name (not IP address)

**Important security constraint:** "the user agent rejects cookies unless the Domain attribute specifies a scope for the cookie that would include the origin server."

### Path Attribute
**Syntax:** `Path=/directory/`

**Purpose:** Restricts cookie to specific paths on the domain

**Matching rules:**
A "request-path path-matches a given cookie-path if at least one of the following conditions holds":

1. **Identical paths:** Cookie-path and request-path are identical
   - Example: `Path=/api` matches only `/api`

2. **Trailing slash match:** Cookie-path is prefix of request-path, and last character of cookie-path is "/" ("/")
   - Example: `Path=/api/` matches `/api/users`, `/api/posts`

3. **Directory separator match:** Cookie-path is prefix of request-path, and first character of request-path not in cookie-path is "/"
   - Example: `Path=/api` matches `/api/users` (because `/` follows `/api`)
   - Example: `Path=/api` does NOT match `/api-v2`

**Default path:** Computed from request URI, typically the directory containing the requested resource
- Request to `/path/to/resource.html` → Default path: `/path/to/`

### Secure Attribute
**Syntax:** `Secure`

**Purpose:** Restricts cookie transmission to secure (HTTPS) connections

**Behavioral requirement:**
- If Secure flag set: Cookie MUST only be sent over HTTPS
- If not set: Cookie sent over both HTTP and HTTPS

**Security implication:** Prevents cookie leakage over unencrypted connections

### HttpOnly Attribute
**Syntax:** `HttpOnly`

**Purpose:** Restricts cookie access to HTTP requests only

**Behavioral requirement:**
- If HttpOnly flag set: Cookie NOT accessible via JavaScript (document.cookie)
- If not set: Cookie accessible to JavaScript

**Security implication:** Protects against XSS attacks stealing cookies via JavaScript

### Max-Age Attribute
**Syntax:** `Max-Age=3600`

**Purpose:** Cookie lifetime in seconds

**Behavioral rules:**
- If Max-Age=0: Cookie deleted immediately
- If positive: Cookie expires after N seconds from request time
- If not set: Cookie is session cookie (expires when browser closes)

**Precedence:** Max-Age takes precedence over Expires if both present

### Expires Attribute
**Syntax:** `Expires=Thu, 01-Jan-2026 00:00:01 GMT`

**Purpose:** Cookie expiration date (legacy, superseded by Max-Age)

**Format:** HTTP-date format (RFC 2822 compatible)

**Behavioral rules:**
- If date in past: Cookie deleted
- If date in future: Cookie expires at that time
- Max-Age takes precedence if both set

### SameSite Attribute
**Syntax:** `SameSite=Strict` or `SameSite=Lax` or `SameSite=None`

**Purpose:** Control cookie transmission in cross-site requests

**Values:**
- **Strict:** Cookie only sent if request originated from same site
- **Lax:** Cookie sent for same-site requests and top-level navigations
- **None:** Cookie sent in all requests (requires Secure flag)

**Security note:** Prevents CSRF attacks by limiting cross-site cookie transmission

## Cookie Scope

### Domain Matching (RFC 6265 Section 5.1.3)

**Domain-matching algorithm:**

"A string domain-matches a given domain string if at least one of the following conditions hold":

1. **Exact match:** The domain string and the string are identical

2. **Subdomain match:** All three conditions hold:
   - The domain string is a suffix of the string
   - The last character of the string that is not included in the domain string is a period (".") character
   - The string is a host name (i.e., not an IP address)

**Examples:**
- `Domain=example.com` matches:
  - `example.com` (exact match)
  - `www.example.com` (suffix match)
  - `api.v2.example.com` (suffix match)
  - But NOT: `notexample.com` (no period before domain)
  - But NOT: `127.0.0.1` (IP address)

### Path Matching (RFC 6265 Section 5.1.4)

Already defined above with examples.

## Behavioral Specifications for httpx

### Cookie Storage
HTTPX must:
- Parse Set-Cookie headers from responses
- Store cookies with all attributes
- Apply domain and path matching
- Check expiration before sending

### Cookie Transmission
HTTPX must:
- Include Cookie header in subsequent requests
- Only when domain matches
- Only when path matches
- Only when not expired
- Only when security requirements met (Secure flag, HTTPS)

### Domain Validation
HTTPX must:
- Implement domain-matching algorithm correctly
- Prevent cookies without explicit domain from matching unrelated hosts
- Handle IP addresses correctly (no domain matching for IPs)

### Path Matching
HTTPX must:
- Implement path-matching algorithm with three conditions
- Handle trailing slashes correctly
- Support default path computation

### Expiration Handling
HTTPX must:
- Track Max-Age and Expires
- Delete expired cookies
- Treat Max-Age as authoritative when both present
- Handle session cookies (no expiration date)

### Security Attributes
HTTPX must:
- Respect Secure flag (HTTPS only)
- Respect HttpOnly flag (don't expose to JavaScript)
- Handle SameSite attribute (cross-site restrictions)

## Cookie Jar Implementation

HTTPX provides cookie persistence through its cookie jar:

```python
cookies = httpx.Cookies()
cookies.set("name", "value", domain="example.com", path="/")

# Cookie jar in client
client = httpx.Client(cookies=cookies)
```

**Requirements:**
- Persist cookies across requests
- Maintain cookie attributes
- Apply domain/path matching
- Handle expiration

## Known Cookie Issues

### Cross-Domain Redirect Behavior
When following redirects across domains, httpx automatically strips authentication-related headers (Authorization, Proxy-Authorization).

**Cookie behavior:** Cookies with Domain attribute matching the new host WILL be sent (subject to domain/path matching rules).

### Cookie Domain Validation
Servers cannot set cookies for unrelated domains. HTTPX must validate:
- Cookie domain is a suffix of or equal to request domain
- Rejects overly broad domain cookies (e.g., `.co.uk`)

## Important RFC 6265 Notes

### Implementation Considerations
- RFC 6265 is complex with many edge cases
- Regular expression patterns in Domain/Path validation must be precise
- Cookie storage and retrieval must be deterministic
- Multiple cookies with same name but different attributes are allowed

### Strict vs Loose Parsing
- Some implementations are lenient with cookie parsing
- HTTPX should be strict about cookie validation
- Malformed cookies should be rejected rather than guessed

### Security Implications
- Cookies enable session management but are security-sensitive
- Domain/path restrictions prevent cookies from being sent to unintended hosts
- Secure flag prevents eavesdropping
- HttpOnly prevents JavaScript-based theft
- SameSite prevents CSRF attacks
