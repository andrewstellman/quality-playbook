# HTTPX Environment Variables and Logging

**Source:** https://www.python-httpx.org/environment_variables/ and https://www.python-httpx.org/logging/
**Accessed:** April 2026

## ENVIRONMENT VARIABLES

### Overview
HTTPX recognizes several environment variables for configuration. To disable environment variable support, set `trust_env=False` when creating a client or making requests.

**Default behavior:** Environment variables are trusted and processed automatically

## Proxy Configuration Variables

### HTTP_PROXY
- **Purpose:** "set the proxy to be used for `http` requests"
- **Format:** URL pointing to the proxy server
- **Example:** `HTTP_PROXY=http://my-external-proxy.com:1234`
- **When applied:** HTTP requests only

### HTTPS_PROXY
- **Purpose:** "set the proxy to be used for `https` requests"
- **Format:** URL pointing to the proxy server
- **Example:** `HTTPS_PROXY=http://my-external-proxy.com:1234`
- **When applied:** HTTPS requests only
- **Important note:** Even for HTTPS proxying, use `http://` URL scheme (not `https://`)

### ALL_PROXY
- **Purpose:** "set the proxy to be used for all requests" (http, https, and other schemes)
- **Format:** URL pointing to the proxy server
- **Priority:** Lower priority than HTTP_PROXY and HTTPS_PROXY
- **Use case:** Default proxy when scheme-specific proxies not set

### NO_PROXY
- **Purpose:** Bypasses proxy for specified hosts
- **Format:** "a comma-separated list of hostnames/urls"
- **Example:** `NO_PROXY=http://127.0.0.1,python-httpx.org`
- **Behavior:** These hosts will connect directly, not through proxy
- **Typical usage:** Local development servers, internal hosts

## SSL/TLS Configuration Variables

### SSL_CERT_FILE
- **Purpose:** File containing CA certificates
- **Value:** File path
- **Behavior:** "HTTPX will load CA certificate from the specified file instead of the default location"
- **Example:** `SSL_CERT_FILE=/path/to/ca-certs/ca-bundle.crt`
- **Impact:** Overrides default certifi CA bundle

### SSL_CERT_DIR
- **Purpose:** Directory containing CA certificates
- **Value:** Directory path
- **Requirement:** Directory must follow "OpenSSL specific layout"
- **Example:** `SSL_CERT_DIR=/path/to/ca-certs/`
- **Setup:** Typically requires running `c_rehash` on the directory
- **Impact:** Loads CA certificates from directory instead of default

## Managing Environment Variable Trust

### Enable Environment Variables (Default)
```python
# trust_env=True is the default
client = httpx.Client()  # Uses HTTP_PROXY, SSL_CERT_FILE, etc.
response = httpx.get(url)  # Also uses environment variables
```

### Disable Environment Variables
```python
client = httpx.Client(trust_env=False)  # Ignores all environment variables
response = httpx.get(url, trust_env=False)  # Per-request disable
```

**Use case:** Testing, sandboxed environments, security-conscious deployments

## Standard Convention Compliance

These environment variables follow conventions established by:
- **cURL**
- **The requests library**
- **Other major HTTP clients**

This ensures consistency across the Python HTTP ecosystem.

---

## LOGGING DOCUMENTATION

**Source:** https://www.python-httpx.org/logging/

### Overview

HTTPX provides logging capabilities through Python's standard logging module to inspect internal network behavior.

## Basic Setup

To enable logging, configure Python's logging with a basic setup:

```python
import logging
import httpx

logging.basicConfig(
    format="%(levelname)s [%(asctime)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG
)

httpx.get("https://www.example.com")
```

## Output Information

The logging system provides details from two sources:

### High-Level httpx Logger
- Application-level HTTP request/response information
- What the application code is doing
- Request methods, URLs, response status codes

### Network-Level httpcore Logger
- Lower-level connection and protocol details
- TCP connections establishment
- TLS handshake information
- HTTP/1.1 frames transmission
- Data transmission details

### Example Log Output Includes
- Connection establishment
- TLS handshake progress
- Request header transmission
- Response reception stages
- Body transmission/reception

## Advanced Configuration

For more sophisticated setups, use dictionary-style logging configuration:

```python
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "http",
        }
    },
    "formatters": {
        "http": {
            "format": "%(levelname)s [%(asctime)s] %(name)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "loggers": {
        "httpx": {
            "handlers": ["default"],
            "level": "DEBUG",
        },
        "httpcore": {
            "handlers": ["default"],
            "level": "DEBUG",
        }
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
```

This allows independent configuration of both `httpx` and `httpcore` loggers.

### Selective Logging

Log only specific components:

```python
# Only log HTTPX, not HTTPCore
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Only log HTTPCore, not HTTPX
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.DEBUG)
```

## Important Considerations

### Debug Log Format May Change
"Debug logging format may change across different versions, so pin dependencies to fixed versions if relying on specific output formatting."

**Impact:**
- Don't parse debug logs in production code
- Debug logs are for human inspection
- Format stability not guaranteed across releases

### Performance Impact
Debug logging adds overhead. Use in development/troubleshooting, not production.

## Common Debugging Scenarios

### Debugging Connection Issues
```python
logging.getLogger("httpcore").setLevel(logging.DEBUG)
# Look for TCP connection and TLS errors
```

### Debugging Request/Response Mismatches
```python
logging.getLogger("httpx").setLevel(logging.DEBUG)
# See what headers/body are being sent/received
```

### Debugging Protocol Errors
```python
logging.getLogger("httpcore").setLevel(logging.DEBUG)
# See low-level protocol details and frame information
```

### Debugging Timeout Issues
```python
logging.basicConfig(level=logging.DEBUG)
# Look for timeout messages in connection/read operations
```

## Log Filtering

Filter logs to specific modules:

```python
import logging

# Only show HTTPX logs, not other libraries
logger = logging.getLogger("httpx")
logger.setLevel(logging.DEBUG)

# Don't pollute with other library logs
logging.getLogger().setLevel(logging.INFO)
```

## Integration with Application Logging

HTTPX uses Python's standard logging module, so it integrates cleanly with application logging:

```python
# Your application logging
app_logger = logging.getLogger("myapp")

# HTTPX logs are captured by the same configuration
import httpx
response = httpx.get(url)
```

Both appear in the same logs with appropriate logger names and levels.
