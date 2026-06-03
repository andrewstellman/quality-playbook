# HTTPX Async Support Documentation

**Source:** https://www.python-httpx.org/async/
**Accessed:** April 2026

## Overview
HTTPX provides asynchronous HTTP client functionality alongside its standard synchronous API. The documentation emphasizes that "Async is a concurrency model that is far more efficient than multi-threading" and is particularly valuable when working with async web frameworks.

## Key Components

### AsyncClient Usage
The primary async interface uses `AsyncClient`:

```python
async with httpx.AsyncClient() as client:
    ...
```

All request methods require the `await` keyword.

### Request Methods
All HTTP methods are async and must be awaited:
- `get()`
- `post()`
- `put()`
- `patch()`
- `delete()`
- `head()`
- `options()`
- `request()`

Usage pattern:
```python
response = await client.get(url)
```

### Streaming Operations

#### Response Streaming
- `aiter_bytes()` - Async iteration over response bytes
- `aiter_text()` - Async iteration over text lines
- `aiter_lines()` - Async iteration over lines
- `aiter_raw()` - Async iteration over raw response

#### Request Streaming
Use async generators for request bodies instead of standard byte generators

#### Stream Context Manager
The `stream()` method operates as an async context block:

```python
async with client.stream("GET", url) as response:
    ...
```

## Supported Async Backends

HTTPX supports three async backends with automatic detection:

1. **AsyncIO** - Python's built-in async library
2. **Trio** - Structured concurrency alternative (requires separate installation)
3. **AnyIO** - Cross-compatible wrapper supporting both backends

## Best Practices

The documentation warns against instantiating multiple client instances in "hot loops" to maximize connection pooling benefits. Developers should maintain either:
- A single scoped client that's passed throughout wherever it's needed
- A single global client instance throughout their application

### Important Connection Pooling Note
"In order to get the most benefit from connection pooling, make sure you're not instantiating multiple client instances." This applies equally to both `Client` and `AsyncClient`.

## Async Patterns

### Context Manager Pattern (Recommended)
```python
async with httpx.AsyncClient() as client:
    response = await client.get(url)
```

### Task Coordination
Use `asyncio.gather(*tasks)` for parallel execution:
```python
tasks = [client.get(url1), client.get(url2), client.get(url3)]
responses = await asyncio.gather(*tasks)
```

## Performance Considerations

**Concurrency Efficiency:**
"Async is a concurrency model that is far more efficient than multi-threading," and can provide significant performance benefits and enable the use of long-lived network connections such as WebSockets.

**Connection Reuse:**
Unlike instantiating a new client per request, maintaining a single `AsyncClient` instance allows the underlying connection pool to be shared across all requests, significantly reducing overhead.
