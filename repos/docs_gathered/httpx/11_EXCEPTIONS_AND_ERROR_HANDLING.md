# HTTPX Exception Types and Error Handling

**Source:** https://www.python-httpx.org/exceptions/
**Accessed:** April 2026

## Exception Hierarchy Overview

HTTPX organizes exceptions into a structured hierarchy for precise error handling.

### Base Exception

**HTTPError** - "Base class for `RequestError` and `HTTPStatusError`"

This is the root exception for all HTTP-related errors in HTTPX.

## Request-Related Errors

### RequestError
Covers all exceptions during `.request()` operations. This is the parent class for errors that occur while making HTTP requests.

### TransportError
Occurs at the Transport API level, representing low-level network failures.

## Timeout Exceptions

HTTPX provides granular timeout exceptions for different timeout scenarios:

### TimeoutException (Base)
Parent class for all timeout-related errors.

### ConnectTimeout
- **Scenario:** "Timed out while connecting to the host"
- **Cause:** Socket connection establishment exceeded timeout
- **Typical timeouts:** Network unreachability, unresponsive servers

### ReadTimeout
- **Scenario:** "Timed out while receiving data from the host"
- **Cause:** Server is not sending data within timeout window
- **Typical causes:** Slow server responses, network latency

### WriteTimeout
- **Scenario:** "Timed out while sending data to the host"
- **Cause:** Cannot send request data within timeout window
- **Typical causes:** Slow network connections, large uploads

### PoolTimeout
- **Scenario:** "Timed out waiting to acquire a connection from the pool"
- **Cause:** Connection pool exhausted, unable to get available connection
- **Related to:** `limits` argument for maximum pool connections
- **Occurrence:** Under high concurrency when max_connections is reached

## Network Errors

### NetworkError (Base)
Parent class for low-level network failures.

### ConnectError
Connection failure at the socket level.

### ReadError
Error while reading data from the network.

### WriteError
Error while writing data to the network.

### CloseError
Error closing the connection.

## Protocol & Connection Issues

### ProtocolError
Generic protocol-level error.

### LocalProtocolError
Protocol error caused by local (client) code.

### RemoteProtocolError
Protocol error caused by remote (server) code.

**Common scenario:** "Server disconnected without sending a response" - typically a RemoteProtocolError

### ProxyError
Error related to proxy connection or configuration.

### UnsupportedProtocol
Unsupported protocol version requested (e.g., trying HTTP/3 without support).

## Response & Stream Errors

### HTTPStatusError
Raised by `response.raise_for_status()` on non-2xx responses.

**IMPORTANT BEHAVIORAL SPECIFICATION:**
Unlike the requests library, HTTPX raises exceptions for **all non-2xx responses**, including:
- 1xx (Informational)
- 3xx (Redirects) - **Especially important**
- 4xx (Client errors)
- 5xx (Server errors)

**Exception properties:**
- `.request` - The original request
- `.response` - The HTTP response with status code and headers

### DecodingError
Error decoding response body (e.g., invalid UTF-8).

### TooManyRedirects
Too many redirect responses exceeded the `max_redirects` limit.

**Default max_redirects:** 20

**Configuration:**
```python
client = httpx.Client(max_redirects=10)  # Custom limit
```

### StreamError (Base)
Parent class for stream-related errors.

### StreamConsumed
Stream body has already been read/consumed and cannot be read again.

**Behavioral note:** Some streaming methods raise this, others return empty. Refer to documentation for specific methods.

### StreamClosed
Stream has been closed and cannot be read.

### ResponseNotRead
Attempting to access response body before it has been read.

**Example scenario:**
```python
response = client.get(url)
# Without calling .read() or iterating:
print(response.content)  # May raise if not yet read
```

### RequestNotRead
Attempting to access request body before it has been read.

## Other Exceptions

### InvalidURL
Invalid URL format or structure.

**Causes:**
- Malformed URL syntax
- Missing required components
- Invalid characters

### CookieConflict
Cookie configuration or usage conflict.

**Causes:**
- Conflicting cookie domain/path settings
- Duplicate cookie names with incompatible attributes

## Error Handling Pattern

The recommended approach combines request execution with status validation:

```python
try:
    response = client.get(url)
    response.raise_for_status()  # Raises HTTPStatusError for non-2xx
except httpx.HTTPStatusError as exc:
    print(f"HTTP Error: {exc.response.status_code}")
except httpx.TimeoutException as exc:
    print(f"Timeout: {exc}")
except httpx.RequestError as exc:
    print(f"Request failed: {exc}")
```

## Timeout Exception Handling

```python
try:
    response = client.get(url, timeout=5.0)
except httpx.ConnectTimeout:
    print("Connection timeout - server unreachable")
except httpx.ReadTimeout:
    print("Read timeout - server too slow")
except httpx.WriteTimeout:
    print("Write timeout - network too slow")
except httpx.PoolTimeout:
    print("Pool exhausted - too many concurrent requests")
except httpx.TimeoutException:
    print("Generic timeout")
```

## Stream Error Handling

```python
try:
    with client.stream("GET", url) as response:
        for line in response.iter_lines():
            process(line)
except httpx.StreamConsumed:
    print("Stream already consumed")
except httpx.StreamError:
    print("Stream error")
```

## Important Behavioral Notes

### raise_for_status() Behavior
HTTPX's `raise_for_status()` raises exceptions for **any non-2xx status code**, not just 4xx/5xx like Requests.

This includes:
- 1xx: Informational responses
- 3xx: Redirect responses
- 4xx: Client error responses
- 5xx: Server error responses

### Max Redirects Default
Default `max_redirects=20`. After 20 redirects, `TooManyRedirects` is raised.

### Stream Consumption
Once a stream is consumed (read), it cannot be read again without explicit re-reading. Different streaming methods have different behavior:
- Some raise `StreamConsumed`
- Some return empty content

### Exception Access to Request/Response
Most exceptions provide access to the underlying request and response:

```python
except httpx.HTTPStatusError as exc:
    print(exc.request)   # Original request
    print(exc.response)  # HTTP response with status/headers
```

This allows detailed error handling and debugging.
