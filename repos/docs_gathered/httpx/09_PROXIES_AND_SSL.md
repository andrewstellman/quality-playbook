# HTTPX Proxies and SSL/TLS Configuration

**Source:** https://www.python-httpx.org/advanced/proxies/ and https://www.python-httpx.org/advanced/ssl/
**Accessed:** April 2026

## PROXY CONFIGURATION

### Basic HTTP Proxy Setup

To route traffic through an HTTP proxy, pass the proxy URL during client initialization:

```python
with httpx.Client(proxy="http://localhost:8030") as client:
    ...
```

### Advanced Configuration with Multiple Proxies

For routing HTTP and HTTPS requests to different proxies, use a mounts dictionary:

```python
proxy_mounts = {
    "http://": httpx.HTTPTransport(proxy="http://localhost:8030"),
    "https://": httpx.HTTPTransport(proxy="http://localhost:8031"),
}
with httpx.Client(mounts=proxy_mounts) as client:
    ...
```

**Important behavioral note:** "the proxy URL for the `https://` key _should_ use the `http://` scheme" because most proxies only support HTTP connections for initial setup.

### Authentication

Credentials are embedded in the proxy URL as userinfo:

```python
with httpx.Client(proxy="http://username:password@localhost:8030") as client:
    ...
```

## Proxy Mechanisms

### Forwarding
The proxy makes the request and returns the response directly.

**Usage:** Simple HTTP proxies
**Behavior:** Request is sent through the proxy without additional setup

### Tunnelling (CONNECT)
The proxy establishes a TCP connection to the target server, allowing the client to "upgrade" connections to HTTPS through TLS handshakes over the tunnel.

**Usage:** HTTPS requests through HTTP proxies
**Behavior:** Initial CONNECT request establishes tunnel, then TLS happens through tunnel
**Important:** This is why HTTPS proxy URLs should use `http://` scheme - they only support HTTP for the initial tunnel

## SOCKS Protocol Support

HTTPX supports SOCKS proxies via an optional dependency:

```bash
pip install httpx[socks]
```

Configuration:

```python
httpx.Client(proxy='socks5://user:pass@host:port')
```

**Supported versions:**
- SOCKS5 (primary)
- SOCKS4 (with credential support)

## Environment Variable Integration

Proxies can be configured through environment variables:

```bash
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
export NO_PROXY=localhost,127.0.0.1
```

To use environment variables:

```python
# trust_env=True is default
client = httpx.Client()  # Uses environment proxy settings
```

To disable environment variable support:

```python
client = httpx.Client(trust_env=False)
```

## SSL/TLS VERIFICATION DOCUMENTATION

### Default Behavior
HTTPX verifies HTTPS connections by default using the "certifi CA bundle delivered by a trusted certificate authority."

**Important:** Invalid SSL certificates trigger a `ConnectError`.

### Disabling Verification
You can bypass SSL verification using the `verify=False` parameter:

```python
client = httpx.Client(verify=False)
response = client.get(url)
```

**Security warning:** This permits insecure requests to proceed without validation. Use only in testing environments.

## Custom SSL Configuration Options

### SSL Context Approach
Configure verification via SSL context instances passed during client instantiation:

```python
import ssl
import certifi

context = ssl.create_default_context(cafile=certifi.where())
client = httpx.Client(verify=context)
```

### Using truststore Package
For system certificate stores:

```python
import ssl
import truststore

client = httpx.Client(verify=truststore.SSLContext())
```

### Custom Certificate Bundles
Via `cafile` or `capath` parameters:

```python
context = ssl.create_default_context(cafile="/path/to/ca-bundle.crt")
client = httpx.Client(verify=context)
```

### Explicit Path Configuration
```python
context = ssl.create_default_context(capath="/path/to/ca-certs/")
client = httpx.Client(verify=context)
```

## Client-Side Certificates

Servers can authenticate clients using certificates loaded via the `.load_cert_chain()` API:

```python
import ssl

context = ssl.create_default_context()
context.load_cert_chain(
    certfile="/path/to/client-cert.pem",
    keyfile="/path/to/client-key.pem"
)
client = httpx.Client(verify=context)
```

**Common usage:** Organizational environments requiring mutual TLS (mTLS).

## Environment Variables for SSL/TLS

HTTPX respects standard environment variables:

### SSL_CERT_FILE
```bash
export SSL_CERT_FILE=/path/to/ca-bundle.crt
```

Designates a file containing CA certificates. When set, HTTPX loads certificates from this path instead of the default location.

### SSL_CERT_DIR
```bash
export SSL_CERT_DIR=/path/to/ca-certs/
```

Points to a directory with CA certificates in OpenSSL-specific layout. The directory must follow "OpenSSL specific layout" (typically after running `c_rehash`).

**Behavioral note:** These variables follow conventions established by tools like cURL and the requests library.

## Local Development with HTTPS

For HTTPS testing against localhost:

1. Generate custom certificates using the `trustme` package
2. Configure HTTPX to trust them through a custom SSL context
3. Point to your client certificate file

```python
import ssl
import trustme

ca = trustme.CA()
server_cert = ca.issue_cert("localhost")

context = ssl.create_default_context()
# Configure context to trust the custom CA
client = httpx.Client(verify=context)
```

## Certificate Validation Behavior

### Default Validation
- Verifies hostname matches certificate CN or SAN
- Validates certificate chain
- Checks certificate expiration
- Validates certificate signatures

### Verification=False Behavior
Disables all validation:
- Accepts expired certificates
- Accepts self-signed certificates
- Accepts hostname mismatches
- Accepts revoked certificates

**Important:** Only use for testing/development.

## Important Security Notes

1. **Never use verify=False in production**
2. **Custom CA certificates should be carefully validated**
3. **Mutual TLS requires both client and server certificates**
4. **Environment variables are trusted by default** - Set `trust_env=False` to ignore them
5. **Certificate verification is essential for security**
