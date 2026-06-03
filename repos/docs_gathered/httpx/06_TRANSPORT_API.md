# HTTPX Transport API Documentation

**Source:** https://www.python-httpx.org/advanced/transports/
**Accessed:** April 2026

## Overview

HTTPX's `Client` accepts a `transport` argument to customize how requests are sent. The framework provides several built-in transport options and allows custom implementations.

## Core Transport Types

### HTTP Transport
The default mechanism for network requests. Advanced features include:

#### Connection Retry Configuration
- Retries connections for `ConnectError` and `ConnectTimeout` scenarios
- Configurable retry count for failed connections

#### Unix Domain Socket Support
- Available via the `uds` parameter
- Allows communication over Unix sockets instead of TCP

#### Local Address Binding
- Through `local_address` parameter
- Useful for multi-network scenarios

### WSGI Transport
Enables direct invocation of Python web applications following the WSGI protocol.

**Use cases:**
- Testing
- Mocking external services

**Key configuration options:**
- `raise_app_exceptions` - Whether to propagate application exceptions
- `script_name` - WSGI SCRIPT_NAME setting
- `remote_addr` - WSGI REMOTE_ADDR setting

### ASGI Transport
Supports async Python web applications using the ASGI protocol.

**Configurable parameters:**
- `raise_app_exceptions` - Whether to propagate application exceptions
- `root_path` - ASGI root_path setting
- `client` - For IP/port specification

## Custom Transport Implementation

### Base Classes
Developers must subclass either:
- `httpx.BaseTransport` (synchronous)
- `httpx.AsyncBaseTransport` (asynchronous)

### Critical Method: handle_request

The critical method to implement is `handle_request`, which:
- **Accepts:** A `Request` object
- **Returns:** A `Response` object
- **Purpose:** Handles the low-level HTTP request/response cycle

```python
class CustomTransport(httpx.BaseTransport):
    def handle_request(self, request):
        # Process request and return response
        return response
```

### Transport Lifecycle

The Transport API operates at the lowest level, dealing with:
- Sending a single request
- Returning a single response
- No higher-level concerns (redirects, authentication, cookie handling)

## Mount-Based Request Routing

The `mounts` dictionary enables sophisticated request routing based on:

### Routing Criteria
- **Scheme matching:** `http://` vs `https://`
- **Domain patterns:** With wildcard support (`*example.com`, `*.example.com`)
- **Port specifications:** `:8080` etc.
- **Combination approaches:** Multiple criteria combined

### Mount Dictionary Example

```python
mounts = {
    "http://": httpx.HTTPTransport(...),
    "https://": httpx.HTTPTransport(...),
    "https://example.com": httpx.HTTPTransport(...),
}
client = httpx.Client(mounts=mounts)
```

### Null Mounts (Disabling Proxies)

You can assign `None` values to bypass routing for specific patterns:

```python
mounts = {
    "https://": proxy_transport,
    "https://internal.example.com": None,  # Don't use proxy for internal
}
```

This supports:
- No-proxy configurations
- Environment variable integration
- Selective proxy bypassing

## Transport-Level Responsibilities

The Transport API handles:
- **Low-level HTTP mechanics:** Opening sockets, sending bytes, receiving bytes
- **Protocol implementation:** HTTP/1.1 or HTTP/2 frame handling
- **Connection management:** At the transport level

The Transport API **does NOT handle:**
- Redirects
- Authentication
- Cookie handling
- Higher-level HTTP semantics

These are handled at the Client level.

## Important Behavioral Notes

### Interface Separation
There's a clear interface split between:
- **Client (httpx):** Higher-level models, cookie handling, redirects, authentication
- **Transport API (httpcore):** "Just send an HTTP request" low-level operations

This separation makes each easier to understand and reason about in isolation.

### Request Routing Specificity
More specific mount patterns take precedence over general ones. For example:
- `"https://api.example.com"` takes precedence over `"https://"`
- `"*.example.com"` takes precedence over `"https://"`

### Async vs Sync
Async applications must use `AsyncBaseTransport` and implement async methods, while sync applications use `BaseTransport` with synchronous methods.
