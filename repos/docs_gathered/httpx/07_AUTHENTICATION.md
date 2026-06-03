# HTTPX Authentication Mechanisms

**Source:** https://www.python-httpx.org/advanced/authentication/
**Accessed:** April 2026

## Built-in Authentication Types

### 1. Basic Authentication
**Description:** "HTTP basic authentication is an unencrypted authentication scheme that uses a simple encoding of the username and password" in the Authorization header.

**Usage:**
```python
httpx.Client(auth=(username, password))
```

**Security Note:** Best used over HTTPS due to weak encoding.

**Behavioral specification:**
- Credentials are base64-encoded
- Sent in every request to the authenticated server
- Less secure than other methods

### 2. Digest Authentication
**Description:** A challenge-response mechanism providing encryption capability for unencrypted connections.

**Implementation:**
```python
httpx.Client(auth=httpx.DigestAuth(username=username, password=password))
```

**Behavioral requirements:**
- Requires an additional round-trip to negotiate credentials
- Server sends authentication challenge
- Client responds with digested credentials
- More secure than Basic auth over unencrypted connections

### 3. NetRC Authentication
**Description:** Leverages `.netrc` configuration files to associate "authentication credentials to specified hosts."

**Behavior:**
- When requests target matching hosts, HTTP basic authentication applies automatically
- Reads from `~/.netrc` file
- Uses file permissions for security
- Automatic authentication without explicitly passing credentials

### 4. Custom Authentication Schemes
Developers can implement custom flows by:

#### Two-Tuple Approach (Basic Auth Shorthand)
```python
auth=(username, password)
```

#### Built-in Auth Classes
```python
auth=httpx.BasicAuth(username, password)
auth=httpx.DigestAuth(username, password)
```

#### Callable Functions
```python
def custom_auth(request):
    request.headers['Authorization'] = 'Bearer token'
    return request

auth=custom_auth
```

#### Subclassing httpx.Auth
For advanced flows, subclass `httpx.Auth` with `auth_flow()` methods:

```python
class CustomAuth(httpx.Auth):
    def auth_flow(self, request):
        # Modify request
        response = yield request
        # Handle response if needed
        return response
```

## Implementation Flexibility

### Access to Request Body
Custom schemes support:
```python
class SigningAuth(httpx.Auth):
    requires_request_body = True

    def auth_flow(self, request):
        # Can access request.content for signing
        request.headers['X-Signature'] = sign(request.content)
        yield request
```

### Access to Response Body
For token refresh patterns:
```python
class TokenRefreshAuth(httpx.Auth):
    requires_response_body = True

    def auth_flow(self, request):
        response = yield request
        if response.status_code == 401:
            # Refresh token and retry
            self.token = refresh_token()
            request.headers['Authorization'] = f'Bearer {self.token}'
            yield request
```

### Sync/Async Support
Override distinct methods for different client types:
- `.sync_auth_flow()` - For synchronous `Client`
- `.async_auth_flow()` - For asynchronous `AsyncClient`

```python
class DualAuth(httpx.Auth):
    def sync_auth_flow(self, request):
        # Sync-specific implementation
        yield request

    async def async_auth_flow(self, request):
        # Async-specific implementation
        yield request
```

## Authentication Scope

Authentication can be applied:

### Per-Request
```python
response = client.get(url, auth=(username, password))
```

### Client-Wide
```python
client = httpx.Client(auth=(username, password))
# All requests use this auth
```

**Behavioral note:** Client-wide authentication standardizes credential handling across all outgoing requests.

## Important Behavioral Notes

### Redirect Behavior with Authentication
When `follow_redirects=True`:
- **Same-domain redirects:** Authorization headers are preserved
- **Cross-domain redirects:** Authentication headers are automatically **stripped** to prevent credential leakage

This is a critical security feature to prevent exposing credentials to third-party sites.

### Custom Auth Flow Control
The `yield` statement in custom auth flows allows for:
1. **Request modification** before sending
2. **Response handling** after receiving
3. **Request retry** with modified credentials

### Bearer Token Pattern
While httpx doesn't have a dedicated Bearer token class, it's easily implemented:

```python
client = httpx.Client(
    headers={"Authorization": "Bearer your_token"}
)
```

Or dynamically:
```python
class BearerAuth(httpx.Auth):
    def __init__(self, token):
        self.token = token

    def auth_flow(self, request):
        request.headers['Authorization'] = f'Bearer {self.token}'
        yield request
```

## Security Considerations

1. **Basic Auth:** Never use over unencrypted connections
2. **Custom tokens:** Store securely, never in version control
3. **Cross-domain redirects:** HTTPX automatically strips auth headers
4. **Token refresh:** Implement proper token refresh mechanisms for long-lived sessions
