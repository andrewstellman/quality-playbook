# HTTPX and Requests Library Compatibility Guide

**Source:** https://www.python-httpx.org/compatibility/
**Accessed:** April 2026

## Key Migration Differences

### 1. Redirect Handling - CRITICAL DIFFERENCE

**HTTPX behavior:** "HTTPX does **not follow redirects by default**."

**Requests behavior:** Follows redirects by default for POST/PUT/DELETE (not for GET which already follows).

**Migration requirement:**
- Enable automatic redirects explicitly: `follow_redirects=True`
- Per-request: `client.get(url, follow_redirects=True)`
- Client-wide: `httpx.Client(follow_redirects=True)`

**Behavioral impact:** All code migrating from Requests must explicitly enable redirect following or handle redirects manually.

### 2. Client Sessions

**Requests:** `requests.Session()`
**HTTPX:** `httpx.Client()`

The `httpx.Client()` class replaces `requests.Session()` for managing persistent connections and settings across multiple requests.

### 3. Response URL Format

**Requests:** Response URLs return as strings
**HTTPX:** Response URLs return as `URL` objects

**Migration:** Convert using `str(response.url)` if needed

```python
url = response.url          # httpx.URL object
url_str = str(response.url) # Convert to string if needed
```

### 4. Redirect Request Access

**Requests:** `response.next`
**HTTPX:** `response.next_request`

**Migration example:**
```python
# Requests
next_req = response.next

# HTTPX
next_req = response.next_request
```

### 5. Content Upload Distinction - CRITICAL DIFFERENCE

HTTPX enforces clear separation:
- **Raw content:** Use `content=` parameter
- **Form data:** Use `data=` parameter

**Behavioral difference from Requests:**
Requests accepts both `data=` for form encoding and raw content. HTTPX requires explicit parameter choice, preventing confusion between different data types.

```python
# Form data
client.post(url, data={"key": "value"})

# Raw content
client.post(url, content=b"raw bytes")
```

### 6. File Upload Requirements - STRICT REQUIREMENT

"HTTPX strictly enforces that upload files must be opened in binary mode" to prevent encoding issues.

**Correct:**
```python
with open("file.bin", "rb") as f:  # Binary mode
    client.post(url, files={"file": f})
```

**Incorrect:**
```python
with open("file.txt", "r") as f:  # Text mode - will fail
    client.post(url, files={"file": f})
```

### 7. Character Encoding - IMPORTANT DIFFERENCE

**HTTPX:** Defaults to UTF-8 for request bodies
**Requests:** Uses Latin-1

**Impact:** Non-ASCII characters in request bodies will be encoded differently.

```python
# HTTPX encodes to UTF-8
client.post(url, content="café")  # UTF-8 encoded

# Requests would encode to Latin-1
```

### 8. Cookie Management - BEHAVIORAL DIFFERENCE

**Requests:** Cookies can be set per-request
**HTTPX:** Cookies must be set during client instantiation

**Correct HTTPX approach:**
```python
client = httpx.Client(cookies={"name": "value"})
# All requests now include these cookies
```

**Not possible in HTTPX:**
```python
# This doesn't work in HTTPX
client.get(url, cookies={"name": "value"})  # Error
```

### 9. Timeout Behavior - CRITICAL DIFFERENCE

**Requests:** No default timeout - can hang indefinitely
**HTTPX:** 5-second default timeout

**Behavioral implication:**
- HTTPX is safer by default (won't hang indefinitely)
- Requests code without explicit timeouts must be updated
- HTTPX code may need explicit `timeout=None` to disable

```python
# HTTPX: 5-second default timeout
response = client.get(url)

# Explicitly disable
response = client.get(url, timeout=None)
```

### 10. HTTP Method Request Bodies - STRICT REQUIREMENT

**Behavioral specification in HTTPX:**
GET, DELETE, HEAD, and OPTIONS methods don't support request bodies.

**Requests:** Allows bodies on any method

**Migration:**
```python
# To send a body with GET/DELETE/HEAD/OPTIONS, use .request():
response = client.request(method="GET", url=url, content=b"body")
```

**Rationale:** HTTPX enforces HTTP semantics - these methods shouldn't have bodies per RFC specifications.

### 11. Success Status Checking

**Requests:** `response.is_ok` (ambiguous)
**HTTPX:** `response.is_success` (explicit for 2xx)

```python
# HTTPX
if response.is_success:
    process_response()
```

### 12. Underlying Networking Technology

**Requests:** Uses urllib3
**HTTPX:** Uses HTTPCore

**Impact:** Different connection management, error handling, and performance characteristics.

## Request Body Restrictions Summary

The HTTP specification defines several HTTP methods that should not have a request body:
- GET
- HEAD
- DELETE
- OPTIONS
- TRACE

**HTTPX enforces this:** Attempting to send a body with these methods through the convenience methods (.get(), .delete(), etc.) will raise an error.

**Workaround:** Use `.request()` method if you truly need to send a body:

```python
# Allowed, but non-standard
response = client.request("DELETE", url, content=b"body")
```

## Migration Strategy

When migrating from Requests to HTTPX:

1. **Update imports:** `requests` → `httpx`
2. **Session → Client:** `Session()` → `Client()`
3. **Enable redirects:** Add `follow_redirects=True` if needed
4. **Update file modes:** Ensure files opened in binary mode
5. **Update timeout handling:** Add explicit timeouts if needed
6. **Update method bodies:** Use `.request()` for non-standard bodies
7. **Test thoroughly:** Different behavior in edge cases

## Intentional Breaking Changes

HTTPX makes several intentional breaking changes from Requests:

- **No default redirect following:** More explicit, prevents hidden multiple requests
- **No GET/DELETE/HEAD/OPTIONS bodies:** Enforces HTTP semantics
- **Default timeouts:** Safer, prevents indefinite hangs
- **Binary file requirement:** Prevents encoding confusion
- **URL type:** Provides more functionality than strings

These changes improve correctness and safety at the cost of some compatibility.
