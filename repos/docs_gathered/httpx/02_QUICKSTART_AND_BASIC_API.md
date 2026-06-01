# HTTPX QuickStart Guide and Basic API

**Source:** https://www.python-httpx.org/quickstart/ and https://www.python-httpx.org/api/
**Accessed:** April 2026

## Basic Usage Overview

HTTPX is a Python HTTP client library. Start by importing it:

```python
import httpx
```

## Core HTTP Methods

The library supports standard HTTP verbs with consistent syntax:

- **GET**: `httpx.get('https://httpbin.org/get')`
- **POST**: `httpx.post('https://httpbin.org/post', data={'key': 'value'})`
- **PUT/DELETE/HEAD/OPTIONS**: Follow the same pattern

## Key Features

### URL Parameters
Pass query parameters using the `params` argument with dictionaries or lists.

### Response Content
- Access response data as text via `.text`
- Access bytes via `.content`
- Parse JSON using `.json()`

### Custom Headers
Include headers through the `headers` parameter.

### Form Data
- Send form-encoded data using the `data=` parameter
- Multipart uploads use `files=`

### JSON Requests
Use `json=` for JSON-encoded request bodies.

### Status Codes
- Check `.status_code`
- Use `raise_for_status()` to raise exceptions for non-2xx responses

### Response Headers
Access headers as a case-insensitive dictionary through `.headers`.

### Streaming
Use `httpx.stream()` for large downloads with methods like:
- `iter_bytes()`
- `iter_text()`
- `iter_lines()`

### Cookies
- Handle cookies via `.cookies` on responses
- Pass them in requests

### Redirects
- Control redirect behavior with `follow_redirects=True`
- Inspect redirect history via `.history`

### Authentication
- Support for Basic auth (2-tuple)
- Digest authentication via `DigestAuth` class

### Timeouts
- Default 5-second timeout
- Customize or disable as needed

### Error Handling
- Catch `RequestError` for connection issues
- Catch `HTTPStatusError` for bad status codes

## Module-Level Helper Functions

HTTPX provides module-level functions for making individual HTTP requests:

- **`httpx.request()`** - Sends an HTTP request with support for all HTTP methods
- **`httpx.get()`, `httpx.post()`, `httpx.put()`, `httpx.patch()`, `httpx.delete()`, `httpx.options()`, `httpx.head()`** - Method-specific convenience functions
- **`httpx.stream()`** - Streams response body instead of loading entirely into memory

**Note:** "Only use these functions if you're testing HTTPX in a console or making a small number of requests."

## Client Classes

### `Client`
Synchronous HTTP client with:
- Connection pooling
- HTTP/2
- Redirects
- Cookie persistence
- etc.

Can be shared between threads.

### `AsyncClient`
Asynchronous variant for use with `async`/`await`. "It can be shared between tasks."

**Common parameters for both:**
- `auth`
- `params`
- `headers`
- `cookies`
- `verify`
- `cert`
- `http2`
- `proxy`
- `timeout`
- `limits`
- `max_redirects`
- `base_url`
- `transport`
- `trust_env`
- `default_encoding`

**Key methods:**
- `request()`
- `get()`
- `post()`
- `put()`
- `patch()`
- `delete()`
- `options()`
- `head()`
- `stream()`
- `build_request()`
- `send()`
- `close()`/`aclose()`

## Core Classes

### Response
Contains:
- Status code
- Headers
- Content
- URL
- Cookies
- History
- Elapsed time

Methods:
- `.json()`
- `.text`
- `.raise_for_status()`

### Request
"Can be constructed explicitly for more control over exactly what gets sent over the wire"

### URL
"A normalized, IDNA supporting URL" with properties for:
- scheme
- host
- port
- path
- query

### Headers
Case-insensitive multi-dict for HTTP headers

### Cookies
Dict-like cookie store supporting domain and path management

### Proxy
Proxy server configuration with:
- URL
- Auth
- Headers
- SSL context

## Important Notes

**Important:** "Only use these functions if you're testing HTTPX in a console or making a small number of requests." For long-lived connections, use Client instances to benefit from connection pooling.
