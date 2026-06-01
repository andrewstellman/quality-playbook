# HTTPX Timeout Documentation

**Source:** https://www.python-httpx.org/advanced/timeouts/
**Accessed:** April 2026

## Overview
HTTPX enforces timeouts by default to prevent indefinite network hangs. The default behavior raises a `TimeoutException` after 5 seconds of network inactivity.

**IMPORTANT BEHAVIORAL SPECIFICATION:** HTTPX has mandatory default timeouts, unlike the Requests library which has none by default.

## Basic Usage

### Per-Request Timeout
```python
httpx.get('http://example.com/api/v1/example', timeout=10.0)
```

### Disabling Timeouts for a Request
```python
httpx.get('http://example.com/api/v1/example', timeout=None)
```

## Client-Level Configuration

Set default timeouts when creating a client instance:

```python
# Uses default 5-second timeout
httpx.Client()

# Uses 10-second default
httpx.Client(timeout=10.0)

# Disables all timeouts
httpx.Client(timeout=None)
```

## Granular Timeout Types

HTTPX supports four specific timeout categories, any of which can be individually configured:

### 1. Connect Timeout
- **Purpose:** Maximum wait time for establishing a socket connection
- **Exception:** Raises `ConnectTimeout` if exceeded
- **Use case:** Catching slow server connections

### 2. Read Timeout
- **Purpose:** Maximum duration to receive data chunks
- **Exception:** Raises `ReadTimeout` if exceeded
- **Use case:** Catching slow responses or incomplete data transmission

### 3. Write Timeout
- **Purpose:** Maximum duration to send data chunks
- **Exception:** Raises `WriteTimeout` if exceeded
- **Use case:** Catching slow uploads or unresponsive servers

### 4. Pool Timeout
- **Purpose:** Maximum wait time acquiring a connection from the pool
- **Exception:** Raises `PoolTimeout` if exceeded
- **Use case:** Detecting connection pool exhaustion
- **Related to:** The `limits` argument for maximum pool connections

## Fine-Tuned Configuration

### Example: Mixed Timeout Configuration
```python
timeout = httpx.Timeout(10.0, connect=60.0)
client = httpx.Client(timeout=timeout)
```

This creates:
- 60-second connect timeout
- 10-second default for read/write/pool operations

### Using httpx.Timeout Class
The `httpx.Timeout` class allows granular control:
- Pass a single float value as the default for all timeout types
- Override individual timeout types (connect, read, write, pool)
- Pass `None` to disable specific timeout types

## Behavioral Specifications

### Default Behavior
- **Default timeout value:** 5 seconds
- **Applied to:** All network operations
- **Exception type:** `TimeoutException` (base class for specific timeout exceptions)

### Request-Level Override
Request-level timeout parameters override client-level defaults:
```python
client = httpx.Client(timeout=5.0)
response = client.get(url, timeout=10.0)  # Uses 10 seconds, not 5
```

### Disabling Timeouts
While possible, disabling timeouts is discouraged and can lead to indefinite hangs:
```python
client = httpx.Client(timeout=None)  # Not recommended
```

## Important Notes

- **Default timeout enforcement is stricter than Requests:** HTTPX enforces timeouts by default (5 seconds), whereas Requests has no default timeout
- **Timeout is per-operation:** Each operation (connect, read, write) can timeout independently
- **Pool timeout relates to connection limits:** PoolTimeout occurs when the connection pool is exhausted and a new connection cannot be acquired within the configured time
