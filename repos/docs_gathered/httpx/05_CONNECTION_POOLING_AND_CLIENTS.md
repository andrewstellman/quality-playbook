# HTTPX Connection Pooling and Client Configuration

**Source:** https://www.python-httpx.org/advanced/clients/ and https://www.encode.io/httpcore/connection-pools/
**Accessed:** April 2026

## HTTPX Client Connection Pooling

### Key Benefits

**Connection Pooling Efficiency**
The documentation emphasizes that "a `Client` instance uses HTTP connection pooling," which means connections are reused across multiple requests to the same host rather than creating new ones each time. This approach delivers meaningful performance gains including:
- Reduced latency (subsequent requests ~0.1s vs initial ~0.5s)
- Lower CPU usage
- Decreased network congestion

### Behavioral Specification
When you make several requests to the same host, the Client will **reuse the underlying TCP connection** instead of recreating one for every single request.

## Client Configuration Approaches

### Context Manager Usage (Recommended)
The recommended pattern involves wrapping client operations:

```python
with httpx.Client() as client:
    response = client.get(url)
```

This ensures proper cleanup of connection resources when exiting the block.

### Sharing Configuration
Developers can apply settings across all requests by passing parameters to the constructor:

```python
client = httpx.Client(
    headers={"User-Agent": "My App"},
    base_url="https://api.example.com"
)
```

Settings such as custom headers or base URLs apply automatically to all requests made through the client.

### Configuration Merging Rules

The library implements smart merging when both client-level and request-level options exist:
- **Headers, query parameters, and cookies:** Combined together
- **Other parameters:** Request-level values override client-level defaults

## Connection Pool Configuration

### Resource Limits Configuration

HTTPX allows developers to manage connection pools through the `httpx.Limits` class, which offers three configurable parameters:

#### 1. max_keepalive_connections
- **Default:** 20
- **Purpose:** Controls the number of persistent connections allowed
- **Configuration:** Set to `None` for unlimited connections
- **Behavioral impact:** Limits how many idle connections are maintained

#### 2. max_connections
- **Default:** 100
- **Purpose:** Establishes an upper bound on total concurrent connections
- **Configuration:** Set to `None` to disable restrictions
- **Behavioral impact:** Prevents connection pool exhaustion

#### 3. keepalive_expiry
- **Default:** 5 seconds
- **Purpose:** Specifies how long idle persistent connections remain open
- **Configuration:** Set to `None` for no expiration
- **Behavioral impact:** Determines connection lifetime after use

### Implementation Example

```python
limits = httpx.Limits(
    max_keepalive_connections=5,
    max_connections=10
)
client = httpx.Client(limits=limits)
```

This approach enables fine-tuned control over resource consumption, making it useful for managing:
- Bandwidth
- Server load
- Memory usage

In different deployment scenarios.

## Advanced Request Control

### Explicit Request Building
The documentation describes using explicit Request instances through `.build_request()` and `.send()` for scenarios requiring "maximum control on what gets sent over the wire."

```python
request = client.build_request("GET", url)
response = client.send(request)
```

## Progress Monitoring

Both upload and download progress can be tracked through:
- Response properties
- Content generators (using libraries like `tqdm` and `rich`)

## Important Behavioral Notes

### Connection Reuse Requirement
"In order to get the most benefit from connection pooling, make sure you're not instantiating multiple client instances."

This can be achieved either by:
1. Having a single scoped client that's passed throughout wherever it's needed
2. Having a single global client instance

### Pool Timeout
When the connection pool reaches its maximum concurrent connections (`max_connections`), subsequent requests will wait to acquire a connection. If this wait exceeds the pool timeout (part of the `timeout` configuration), a `PoolTimeout` exception is raised.

## HTTPCore Connection Pool Architecture

### Design Principles
Connection pools in HTTPCore enable reuse of established connections across multiple requests, significantly improving performance by eliminating redundant connection overhead.

### Thread and Task Safety
"Connection pools are designed to be thread-safe. Similarly, when using `httpcore` in an async context connection pools are task-safe."

This allows sharing a single pool instance across:
- Multiple threads (in sync context)
- Multiple tasks (in async context)

### Request Queuing and Assignment
The implementation queues incoming requests and intelligently assigns them to available connections, creating or closing connections as needed while respecting configured limits.

### Resource Management Patterns

Pools support three lifecycle patterns:
1. **Automatic cleanup:** Via garbage collection
2. **Context manager:** For explicit scoping
3. **Manual control:** `.close()` calls for explicit lifecycle management

## Known Issues and Limitations

### HTTP/2 Connection Behavior
The HTTP/2 specification mandates opening a **single connection to an origin** and using stream multiplexing for multiple concurrent requests rather than using multiple connections. HTTPX carefully follows this specification, which can be a source of confusion for developers familiar with HTTP/1.1 behavior.

### Performance Concerns (HTTPCore Level)
The original connection pooling design had documented issues including critical bugs when maxing out concurrent connections. Users should be aware that under high concurrency loads with many queued requests, performance can degrade.

### Server Disconnection Issues
Users have reported intermittent "Server disconnected without sending a response" errors. When this occurs, disabling connection pooling can reduce error frequency, though this comes at a significant performance cost.
