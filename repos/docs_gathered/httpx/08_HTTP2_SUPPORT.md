# HTTPX HTTP/2 Support Documentation

**Source:** https://www.python-httpx.org/http2/
**Accessed:** April 2026

## Overview
HTTP/2 is presented as "a major new iteration of the HTTP protocol, that provides a far more efficient transport, with potential performance benefits."

**Key Difference from HTTP/1.1:**
- HTTP/1.1: Text-based protocol
- HTTP/2: Binary format enabling request/response multiplexing and header compression

## Key Advantages of HTTP/2

### Connection Multiplexing
Unlike HTTP/1.1's requirement for separate connections per request, HTTP/2 allows a **single TCP connection to manage multiple concurrent requests**.

**Behavioral impact:**
- Significant performance improvement for multiple simultaneous requests
- Reduced latency from connection setup overhead
- Better resource utilization

### Additional Benefits
- Response prioritization
- Server push capabilities
- Header compression (HPACK)

## Implementation in HTTPX

### Installation
To enable HTTP/2 support, users must install optional dependencies:

```bash
pip install httpx[http2]
```

This installs the `h2` library required for HTTP/2 protocol support.

### Activation
Both `Client` and `AsyncClient` support HTTP/2 through an `http2=True` parameter:

```python
client = httpx.AsyncClient(http2=True)
# or
client = httpx.Client(http2=True)
```

**Important Note:** "HTTP/2 is disabled by default because HTTP/1.1 is a mature, battle-hardened transport layer."

### Default Behavior
- HTTP/2 is opt-in, not automatic
- HTTP/1.1 remains the default protocol
- HTTP/2 adoption depends on server support
- Automatic fallback occurs if server doesn't support HTTP/2

## Checking Protocol Version

Users can inspect which HTTP version was used via the response's `.http_version` property:

```python
response = client.get(url)
print(response.http_version)  # Returns "HTTP/1.0", "HTTP/1.1", or "HTTP/2"
```

**Behavioral specification:**
- Each response reports the actual protocol version used for that request
- Useful for debugging and monitoring protocol usage
- Allows detection of HTTP/2 connection failures/fallbacks

## HTTP/2 Connection Behavior

### Single Connection per Origin
The HTTP/2 specification mandates opening **a single connection to an origin** and using stream multiplexing for multiple concurrent requests rather than using multiple connections.

**HTTPX carefully follows this specification.**

### Implication for Connection Pooling
When using HTTP/2 with HTTPX:
- Multiple concurrent requests to the same origin will share a single TCP connection
- Connection pool behavior differs from HTTP/1.1
- Stream IDs are used instead of separate connections
- Flow control credits manage request ordering and concurrency

### Multi-Request Patterns
For multiple concurrent requests with HTTP/2:

```python
async with httpx.AsyncClient(http2=True) as client:
    tasks = [
        client.get(url1),
        client.get(url2),
        client.get(url3),
    ]
    responses = await asyncio.gather(*tasks)
```

All requests will use the same underlying connection through HTTP/2 multiplexing.

## Known Issues and Behavioral Notes

### Connection Pool Issues with HTTP/2
Users have reported issues with HTTP/2 connection pools:

**Issue:** When httpx connects to an HTTP/2 server and the server disconnects, httpx may attempt to reuse the connection. This occurs particularly when `keepalive_expiry` is larger than the server's `keep_alive_timeout`, causing connection mismatches.

**Mitigation:**
- Monitor server keep-alive settings
- Consider adjusting `keepalive_expiry` to match server expectations
- Disable HTTP/2 if connection issues persist

### Migration from HTTP/1.1
When switching from HTTP/1.1 to HTTP/2:

1. **Connection behavior changes** - Single connection instead of multiple
2. **Error handling may differ** - Some error scenarios behave differently
3. **Performance characteristics change** - Multiplexing provides benefits but may introduce new bottlenecks
4. **Testing requirements** - Thoroughly test with actual HTTP/2 servers

## Performance Considerations

### When HTTP/2 is Beneficial
- Multiple concurrent requests to the same server
- Latency-sensitive applications
- High-frequency API calls

### When HTTP/2 May Not Help
- Single requests per connection
- Low concurrency scenarios
- Older server support requirements

## Compatibility Notes

**Server Support:** Not all servers support HTTP/2. HTTPX handles unsupported servers by:
1. Attempting HTTP/2 connection
2. Falling back to HTTP/1.1 if negotiation fails
3. Using appropriate protocol transparently

This fallback mechanism ensures broad compatibility while allowing HTTP/2 optimization where available.
