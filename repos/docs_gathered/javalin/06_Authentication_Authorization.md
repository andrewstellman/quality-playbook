# Javalin Authentication and Authorization Guide

## Overview

Javalin provides flexible authentication and authorization mechanisms. Multiple approaches are available, from JWT-based solutions to comprehensive security frameworks like pac4j and Sureness.

## Built-in Access Management

### Role-Based Access Control (RBAC)

Javalin provides `config.accessManager()` for role-based access control:

```java
config.accessManager((handler, ctx, permittedRoles) -> {
    String userRole = ctx.sessionAttribute("role");
    if (permittedRoles.contains(userRole)) {
        handler.handle(ctx);
    } else {
        ctx.status(403).result("Unauthorized");
    }
});
```

### Endpoint-Level Authorization

```java
config.routes(() -> {
    get("/public", ctx -> ctx.result("Public"));
    get("/admin", ctx -> ctx.result("Admin only"), roles(ADMIN));
    get("/user", ctx -> ctx.result("User area"), roles(USER, ADMIN));
});
```

## JWT (JSON Web Token) Authentication

### Overview

JWT is a stateless authentication mechanism where tokens contain encoded user claims. Multiple libraries support JWT in Javalin.

### JWT Token Structure

A JWT has three parts separated by dots:
- **Header**: Token type and hashing algorithm
- **Payload**: Claims (user ID, roles, expiration)
- **Signature**: Cryptographic signature

### Libraries for JWT in Javalin

1. **jjwt** - Pure Java library for working with JWTs
   - Established and well-maintained
   - Full encoding, decoding, verification support
   - Token signing with HMAC or RSA

2. **javalin-jwt** - Javalin-specific extension
   - Convenient wrapper around jjwt
   - Simplified API for common use cases
   - GitHub: https://github.com/kmehrunes/javalin-jwt

3. **javalin-tokens** - Example implementation
   - Reference code for JWT integration
   - GitHub: https://github.com/mednikoviurii/javalin-tokens

### JWT Implementation Pattern

**Token Decoding (Middleware)**:
```java
// Handler that decodes JWT from Authorization header
config.routes.before((ctx) -> {
    String authHeader = ctx.header("Authorization");
    if (authHeader != null && authHeader.startsWith("Bearer ")) {
        String token = authHeader.substring(7);
        try {
            // Decode and validate token
            Claims claims = Jwts.parserBuilder()
                .setSigningKey(SECRET_KEY)
                .build()
                .parseClaimsJws(token)
                .getBody();

            // Add decoded claims to context
            ctx.attribute("userId", claims.getSubject());
            ctx.attribute("roles", claims.get("roles"));
        } catch (JwtException e) {
            ctx.status(401).result("Invalid token");
        }
    }
});
```

**Access Manager with JWT**:
```java
config.accessManager((handler, ctx, roles) -> {
    List<String> userRoles = ctx.attribute("roles");
    boolean hasAccess = roles.isEmpty() ||
        roles.stream().anyMatch(userRoles::contains);

    if (hasAccess) {
        handler.handle(ctx);
    } else {
        ctx.status(403).result("Forbidden");
    }
});
```

**Token Generation**:
```java
post("/login", ctx -> {
    User user = ctx.bodyAsClass(User.class);
    if (validateCredentials(user)) {
        String token = Jwts.builder()
            .setSubject(user.id)
            .claim("roles", user.roles)
            .setExpiration(new Date(System.currentTimeMillis() + 3600000))
            .signWith(SignatureAlgorithm.HS512, SECRET_KEY)
            .compact();

        ctx.json(Map.of("token", token));
    } else {
        ctx.status(401).result("Invalid credentials");
    }
});
```

### JWT Best Practices

1. **Token Storage**:
   - Store in secure httpOnly cookies
   - Never store in localStorage (XSS vulnerability)
   - Use secure + sameSite flags for cookies

2. **Token Expiration**:
   - Set reasonable expiration times (15 min - 1 hour)
   - Implement refresh token mechanism
   - Validate expiration on every request

3. **Signing**:
   - Use HMAC for symmetric key (fast, good for monoliths)
   - Use RSA for asymmetric key (good for microservices)
   - Rotate keys periodically

4. **Claims**:
   - Include minimal necessary data
   - Never include passwords or sensitive data
   - Add `iat` (issued at) and `exp` (expiration) claims

## Sureness Framework Integration

### Overview

Sureness is built on RBAC permission model. It supports:
- Basic authentication
- Digest authentication
- JWT authentication
- Fine-grained access control

### Features

- Out-of-the-box JWT, Basic Auth, Digest Auth support
- Permission-based access control
- Resource and action-based security
- Audit logging capabilities

### Basic Setup

```java
// Configure Sureness
config.registerPlugin(new SurenessPlugin(sureness -> {
    sureness.add(c -> {
        // Configure authentication methods
        // Configure resource permissions
        // Configure audit logging
    });
}));
```

## pac4j Security Library

### Overview

The **javalin-pac4j** project is a comprehensive security library for Javalin:
- OAuth, CAS, SAML, OpenID Connect support
- LDAP integration
- JWT authentication
- Easy integration with Javalin

### Features

- Multiple authentication mechanisms
- Session management
- Profile storage and retrieval
- CORS compatibility

### Example Integration

```java
// Configure pac4j
Config config = new Config();
config.addClients("...");  // Add OAuth, JWT, etc.

config.registerPlugin(new Pac4jPlugin(pac4j -> {
    pac4j.config = config;
}));
```

## Basic Authentication

### Simple Basic Auth

```java
config.routes.before((ctx) -> {
    String authHeader = ctx.header("Authorization");
    if (authHeader != null && authHeader.startsWith("Basic ")) {
        String credentials = new String(
            Base64.getDecoder().decode(authHeader.substring(6))
        );
        String[] parts = credentials.split(":");
        String username = parts[0];
        String password = parts[1];

        if (validatePassword(username, password)) {
            ctx.attribute("username", username);
        } else {
            ctx.status(401).header("WWW-Authenticate", "Basic realm=\"app\"");
        }
    }
});
```

## Session-Based Authentication

### Jetty Session Handling

```java
config.jetty.sessionConfig(sessionHandler -> {
    sessionHandler.setMaxInactiveInterval(1800); // 30 minutes
    sessionHandler.setHttpOnly(true);
    sessionHandler.setSecureRequestOnly(true);
});

// Login endpoint
post("/login", ctx -> {
    User user = validateLogin(ctx);
    if (user != null) {
        ctx.sessionAttribute("userId", user.id);
        ctx.sessionAttribute("roles", user.roles);
        ctx.redirect("/dashboard");
    } else {
        ctx.status(401);
    }
});

// Protected endpoint
get("/dashboard", ctx -> {
    String userId = ctx.sessionAttribute("userId");
    if (userId != null) {
        ctx.result(getDashboard(userId));
    } else {
        ctx.redirect("/login");
    }
});
```

## OAuth 2.0 Integration

### Using pac4j

```java
// Configure OAuth clients
OAuth20Service googleService = new ServiceBuilder()
    .apiKey(CLIENT_ID)
    .apiSecret(CLIENT_SECRET)
    .callback(CALLBACK_URL)
    .build(GoogleApi20.instance());

// OAuth callback handler
get("/oauth/callback", ctx -> {
    String code = ctx.queryParam("code");
    // Exchange code for token
    // Fetch user info
    // Create session
});
```

## LDAP Authentication

### Using pac4j LDAP

```java
LdapProfile profile = ldapAuthenticator.authenticate(
    new LdapCredentials(username, password)
);

if (profile != null) {
    ctx.sessionAttribute("user", profile);
    ctx.status(200);
} else {
    ctx.status(401);
}
```

## Authorization Patterns

### Role-Based Authorization

```java
// Simple role checking
before((ctx) -> {
    String role = ctx.sessionAttribute("role");
    String path = ctx.path();

    if (path.startsWith("/admin") && !"ADMIN".equals(role)) {
        ctx.status(403).result("Forbidden");
    }
});
```

### Permission-Based Authorization

```java
// More granular permission checking
config.accessManager((handler, ctx, requiredPermissions) -> {
    List<String> userPermissions = getUserPermissions(ctx);

    boolean authorized = requiredPermissions.isEmpty() ||
        requiredPermissions.stream()
            .allMatch(userPermissions::contains);

    if (authorized) {
        handler.handle(ctx);
    } else {
        ctx.status(403).result("Insufficient permissions");
    }
});
```

## Security Best Practices

### 1. HTTPS Only
- Always use HTTPS in production
- Set secure and httpOnly flags on cookies
- Implement HSTS headers

### 2. Input Validation
```java
// Validate all inputs
ctx.queryParamAsClass("username", String.class)
    .required()
    .check(u -> u.length() > 0 && u.length() < 50)
    .get();
```

### 3. CORS Configuration
```java
config.bundledPlugins.enableCors(cors -> {
    cors.add(c -> c
        .allowHost("trusted-domain.com")
        .allowCredentials = true
    );
});
```

### 4. Password Hashing
```java
// Never store plain text passwords
String hashedPassword = BCrypt.hashpw(
    plainPassword,
    BCrypt.gensalt()
);

// Verify
if (BCrypt.checkpw(attemptedPassword, storedHash)) {
    // Password valid
}
```

### 5. Error Messages
```java
// Don't leak information
ctx.status(401).result("Invalid credentials");  // Good
ctx.status(401).result("User not found");      // Bad - leaks info
```

### 6. Logging
```java
// Log authentication attempts (not passwords)
logger.info("Authentication attempt for user: {}", username);
logger.warn("Failed authentication attempt from IP: {}", ctx.ip());
```

## Testing Authentication

### Unit Testing with Mocking

```java
@Test
public void testAuthenticatedEndpoint() {
    // Mock authenticated context
    Context ctx = mock(Context.class);
    when(ctx.sessionAttribute("userId")).thenReturn("123");

    // Test handler
    handler.handle(ctx);

    verify(ctx).result("Protected content");
}
```

### Integration Testing

```java
@Test
public void testLoginFlow() {
    // Use javalin-testtools
    String response = given()
        .body(Map.of("username", "user", "password", "pass"))
        .post("/login")
        .getBody();

    // Verify session/token created
    String token = extractToken(response);
    assertNotNull(token);
}
```

## Common Authentication Scenarios

### 1. REST API with JWT
- Send token in Authorization header
- Validate on each request
- Implement token refresh
- Use httpOnly cookies for token storage

### 2. Web Application with Sessions
- Create session on login
- Store session ID in secure cookie
- Validate session on each request
- Clear session on logout

### 3. Microservices
- Use JWT from identity provider
- Validate signature with public key
- Cache public key for performance
- Implement claims validation

### 4. Multi-Tenant Application
- Include tenant ID in token/session
- Validate tenant access per request
- Isolate data by tenant
- Implement tenant-specific permissions

## References

- Official JWT Tutorial: https://javalin.io/2018/09/11/javalin-jwt-example.html
- Sureness Integration: https://javalin.io/2021/04/16/javalin-sureness-example.html
- pac4j Project: https://github.com/pac4j/javalin-pac4j
- Javalin Auth Example: https://javalin.io/tutorials/auth-example
