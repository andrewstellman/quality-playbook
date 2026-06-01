# Javalin CORS and Error Handling

## CORS (Cross-Origin Resource Sharing)

### Overview

CORS is a browser security mechanism that controls cross-origin HTTP requests. The CORS plugin in Javalin manages CORS headers based on configuration for allowed hosts.

### CORS Basics

**What is CORS?**
- Browser security feature preventing requests from one origin to another
- Requires server to explicitly allow cross-origin access
- Works with HTTP headers, not cookies or authentication

**When is CORS needed?**
- Frontend on different domain than API (e.g., app.example.com calling api.example.com)
- Frontend on different port (e.g., localhost:3000 calling localhost:8080)
- Different protocol (http vs https)

### CORS Plugin Configuration

Enable the CORS plugin:

```java
var app = Javalin.create(config -> {
    config.bundledPlugins.enableCors(cors -> {
        cors.add(c -> c
            .allowHost("example.com")
            .allowHost("www.example.com")
            .allowCredentials = false
        );
    });
}).start();
```

### CORS Configuration Options

**Basic Configuration**:
```java
config.bundledPlugins.enableCors(cors -> {
    cors.add(c -> c
        .allowHost("example.com", "javalin.io")  // Specific hosts
        .allowCredentials = false                  // Allow credentials
    );
});
```

**Specific Hosts**:
```java
cors.add(c -> c
    .allowHost("example.com")
    .allowHost("api.example.com")
);
```

**Subdomain Wildcards**:
```java
cors.add(c -> c
    .allowHost("*.example.com")  // Allows subdomain.example.com
);
```

**Any Host (Insecure)**:
```java
cors.add(c -> c
    .anyHost()  // Allows all origins - use only for public APIs
    .allowCredentials = false  // Cannot be true with anyHost()
);
```

**Custom Scheme**:
```java
cors.add(c -> c
    .allowHost("example.com")
    .scheme("http")  // Default is "https"
);
```

**Client Origin Reflection**:
```java
cors.add(c -> c
    .reflectClientOrigin = true  // Echo back the requesting origin
);
```

**Additional Headers**:
```java
cors.add(c -> {
    c.allowCredentials = true;
    c.exposeHeader("X-Custom-Header");
    c.exposeHeader("X-Total-Count");
});
```

**Path-Based Configuration**:
```java
// Different CORS rules for different paths
cors.add("/api/*", c -> c
    .allowHost("example.com")
);

cors.add("/public/*", c -> c
    .anyHost()
);

cors.add("/images/*", c -> c
    .allowHost("cdn.example.com")
);
```

### CORS Important Constraint

**Critical Security Rule**:
```
You CANNOT use anyHost() together with allowCredentials = true
```

This is a browser security requirement. Browsers explicitly forbid this combination.

```java
// WRONG - Will cause error
cors.add(c -> c
    .anyHost()
    .allowCredentials = true  // NOT ALLOWED
);

// CORRECT - Use specific hosts with credentials
cors.add(c -> c
    .allowHost("example.com")
    .allowCredentials = true
);

// CORRECT - Use anyHost without credentials
cors.add(c -> c
    .anyHost()
    .allowCredentials = false
);
```

### Frontend CORS Configuration

**JavaScript Fetch**:
```javascript
// Without credentials
fetch('http://api.example.com/users')
    .then(response => response.json())
    .then(data => console.log(data));

// With credentials (cookies)
fetch('http://api.example.com/users', {
    credentials: 'include'  // Important for allowCredentials = true
})
    .then(response => response.json())
    .then(data => console.log(data));
```

**Axios**:
```javascript
// Without credentials
axios.get('http://api.example.com/users')
    .then(response => console.log(response.data));

// With credentials
axios.get('http://api.example.com/users', {
    withCredentials: true  // Important for allowCredentials = true
})
    .then(response => console.log(response.data));
```

### CORS Headers Generated

When configured, Javalin sets these response headers:

```
Access-Control-Allow-Origin: example.com
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Max-Age: 3600
Access-Control-Expose-Headers: X-Custom-Header
```

### Preflight Requests

For complex requests (POST, PUT, DELETE with custom headers), browsers send an OPTIONS preflight request:

```
OPTIONS /api/users
Origin: http://example.com
Access-Control-Request-Method: POST
Access-Control-Request-Headers: Content-Type
```

Javalin automatically handles preflight with configured headers.

## Error Handling in Javalin

### Exception Handlers

Exception handlers catch exceptions thrown in route handlers and convert them to HTTP responses.

**Configuration**:
```java
var app = Javalin.create(config -> {
    config.routes.exception(CustomException.class, (e, ctx) -> {
        ctx.status(400)
           .json(Map.of(
               "error", e.getMessage(),
               "type", "CustomException"
           ));
    });

    config.routes.exception(NotFoundException.class, (e, ctx) -> {
        ctx.status(404)
           .json(Map.of("error", "Resource not found"));
    });

    config.routes.exception(Exception.class, (e, ctx) -> {
        ctx.status(500)
           .json(Map.of("error", "Internal server error"));
    });
}).start();
```

**Important Rules**:
- More specific exception mappers take precedence over general ones
- Exception handlers are configured in the config block (Javalin 7)
- Can be registered for specific exception types

**Example - Custom Exception**:
```java
class ValidationException extends Exception {
    public ValidationException(String message) {
        super(message);
    }
}

// Endpoint throwing exception
post("/users", ctx -> {
    String email = ctx.bodyAsClass(User.class).email;
    if (!isValidEmail(email)) {
        throw new ValidationException("Invalid email format");
    }
    ctx.json(createUser(email));
});

// Exception handler
config.routes.exception(ValidationException.class, (e, ctx) -> {
    ctx.status(400)
       .json(Map.of(
           "error", e.getMessage(),
           "code", "VALIDATION_ERROR"
       ));
});
```

### Error Handlers

Error handlers catch HTTP errors (404, 401, 500, etc.) that aren't caught by exception handlers.

**Configuration**:
```java
config.routes.error(404, ctx -> {
    ctx.status(404)
       .json(Map.of(
           "error", "Endpoint not found",
           "path", ctx.path()
       ));
});

config.routes.error(500, ctx -> {
    ctx.status(500)
       .json(Map.of(
           "error", "Internal server error"
       ));
});
```

**Common HTTP Errors**:
- **400**: Bad Request (invalid input)
- **401**: Unauthorized (auth required)
- **403**: Forbidden (auth succeeded but not allowed)
- **404**: Not Found
- **405**: Method Not Allowed
- **409**: Conflict
- **500**: Internal Server Error
- **503**: Service Unavailable

### Default HTTP Response Classes

Javalin provides default responses for common errors:

```java
// In endpoint handler
if (userNotFound) {
    throw new NotFoundException("User not found");
}

if (userUnauthorized) {
    ctx.status(401);  // Or use UnauthorizedException
}

if (forbidden) {
    ctx.status(403);
}
```

### Exception Handler with Content Type

```java
config.routes.exception(ValidationException.class, (e, ctx) -> {
    if (ctx.header("Accept")?.contains("application/json")) {
        ctx.contentType("application/json")
           .status(400)
           .json(Map.of("error", e.getMessage()));
    } else {
        ctx.contentType("text/html")
           .status(400)
           .html("<h1>Error: " + e.getMessage() + "</h1>");
    }
});
```

### WebSocket Exception Handlers

```java
config.routes.wsException(WebSocketException.class, (e, ctx) -> {
    ctx.error(e);
});
```

## Complete Error Handling Example

```java
public class ErrorHandlingExample {

    // Custom exceptions
    static class ValidationException extends Exception {
        ValidationException(String msg) { super(msg); }
    }

    static class AuthenticationException extends Exception {
        AuthenticationException(String msg) { super(msg); }
    }

    static class ResourceNotFoundException extends Exception {
        ResourceNotFoundException(String msg) { super(msg); }
    }

    public static void main(String[] args) {
        var app = Javalin.create(config -> {
            // CORS Configuration
            config.bundledPlugins.enableCors(cors -> {
                cors.add(c -> c
                    .allowHost("example.com")
                    .allowCredentials = true
                );
            });

            config.routes(() -> {
                // Exception handlers
                exception(ValidationException.class, (e, ctx) -> {
                    ctx.status(400)
                       .json(Map.of(
                           "error", e.getMessage(),
                           "code", "VALIDATION_ERROR"
                       ));
                });

                exception(AuthenticationException.class, (e, ctx) -> {
                    ctx.status(401)
                       .json(Map.of(
                           "error", e.getMessage(),
                           "code", "AUTH_ERROR"
                       ));
                });

                exception(ResourceNotFoundException.class, (e, ctx) -> {
                    ctx.status(404)
                       .json(Map.of(
                           "error", e.getMessage(),
                           "code", "NOT_FOUND"
                       ));
                });

                exception(Exception.class, (e, ctx) -> {
                    ctx.status(500)
                       .json(Map.of(
                           "error", "Internal server error",
                           "code", "INTERNAL_ERROR"
                       ));
                });

                // Error handlers for 404, etc.
                error(404, ctx -> {
                    ctx.json(Map.of(
                        "error", "Endpoint not found",
                        "path", ctx.path()
                    ));
                });

                error(405, ctx -> {
                    ctx.json(Map.of(
                        "error", "Method not allowed",
                        "method", ctx.method(),
                        "path", ctx.path()
                    ));
                });

                // Routes
                post("/users", ctx -> {
                    User user = ctx.bodyAsClass(User.class);

                    if (user.email == null || !user.email.contains("@")) {
                        throw new ValidationException("Invalid email");
                    }

                    if (!isAuthenticated(ctx)) {
                        throw new AuthenticationException("Login required");
                    }

                    User created = createUser(user);
                    ctx.status(201).json(created);
                });

                get("/users/{id}", ctx -> {
                    int id = ctx.pathParamAsClass("id", Integer.class).get();
                    User user = getUserById(id);

                    if (user == null) {
                        throw new ResourceNotFoundException(
                            "User with id " + id + " not found"
                        );
                    }

                    ctx.json(user);
                });
            });
        }).start();
    }

    static boolean isAuthenticated(Context ctx) {
        return ctx.header("Authorization") != null;
    }

    static User createUser(User user) {
        // Implementation
        return user;
    }

    static User getUserById(int id) {
        // Implementation
        return null;
    }

    static class User {
        public String email;
    }
}
```

## Testing CORS and Error Handling

```java
@Test
public void testCORSHeaders() {
    given()
        .header("Origin", "example.com")
    .when()
        .get("http://localhost:8080/api/users")
    .then()
        .header("Access-Control-Allow-Origin", "example.com")
        .header("Access-Control-Allow-Credentials", "true");
}

@Test
public void testValidationError() {
    given()
        .body(Map.of("email", "invalid-email"))
    .when()
        .post("http://localhost:8080/users")
    .then()
        .statusCode(400)
        .body("code", equalTo("VALIDATION_ERROR"));
}

@Test
public void testNotFound() {
    given()
    .when()
        .get("http://localhost:8080/users/9999")
    .then()
        .statusCode(404)
        .body("code", equalTo("NOT_FOUND"));
}

@Test
public void testUnauthorized() {
    given()
    .when()
        .get("http://localhost:8080/protected")
    .then()
        .statusCode(401)
        .body("code", equalTo("AUTH_ERROR"));
}
```

## CORS Troubleshooting

### Issue: CORS errors in browser console

**Symptoms**:
```
Access to XMLHttpRequest at 'http://api.example.com' from origin 'http://app.example.com'
has been blocked by CORS policy
```

**Solutions**:
1. Check that frontend origin is in allowHost()
2. Verify allowCredentials setting matches frontend
3. Check that frontend is using correct credentials option
4. Ensure OPTIONS preflight is handled

### Issue: Credentials not working

**Symptoms**:
- Cookies not sent with cross-origin requests
- Session data lost

**Solutions**:
1. Set `allowCredentials = true` on server
2. Set `credentials: 'include'` in fetch or `withCredentials: true` in axios
3. Cannot use `anyHost()` with credentials
4. Cookies must have SameSite=None; Secure in Secure context

### Issue: Too restrictive CORS

**Symptoms**:
- Legitimate requests blocked
- Development blocked while testing

**Solutions**:
1. Add specific domains to allowHost()
2. Use wildcard for subdomains: `*.example.com`
3. Development: use localhost if needed
4. Never use `anyHost()` in production for sensitive APIs

## Best Practices

**CORS**:
1. Be explicit about allowed origins
2. Never use `anyHost()` with sensitive operations
3. Require `allowCredentials = true` if using cookies/auth
4. Test CORS setup before production
5. Document CORS requirements for API consumers

**Error Handling**:
1. Use specific exception types
2. Provide clear error messages
3. Include error codes for client handling
4. Log full exceptions server-side
5. Don't leak sensitive info in error messages
6. Use appropriate HTTP status codes
7. Test error paths in unit/integration tests

## References

- CORS Plugin Documentation: https://javalin.io/plugins/cors
- Official CORS Examples: https://javalin.io/
- MDN CORS Guide: https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
- HTTP Status Codes: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status
