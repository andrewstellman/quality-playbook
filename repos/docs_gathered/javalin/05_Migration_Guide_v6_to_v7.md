# Javalin Migration Guide: v6 to v7

## Overview

Javalin 7 represents a significant shift toward upfront configuration. Many breaking changes require code refactoring, but the migration improves application structure and ensures all routes are registered before the server starts.

**Release Date**: 2024+
**Key Requirement**: Java 17+ (previously Java 11)

## Breaking Changes Summary

### 1. Routes and Handlers Configuration (CRITICAL)

**What Changed**:
Routes, handlers, and lifecycle events must now be configured within the `Javalin.create()` config block rather than after instantiation.

**Javalin 6 (Old Way)**:
```java
var app = Javalin.create().start();
app.get("/hello", ctx -> ctx.result("Hello World"));
app.post("/users", ctx -> createUser(ctx));
```

**Javalin 7 (New Way)**:
```java
var app = Javalin.create(config -> {
    config.routes(() -> {
        get("/hello", ctx -> ctx.result("Hello World"));
        post("/users", ctx -> createUser(ctx));
        put("/users/{id}", ctx -> updateUser(ctx));
        delete("/users/{id}", ctx -> deleteUser(ctx));
    });
}).start();
```

**Impact**:
- Routes cannot be added after `.start()` is called
- Ensures all routes are registered before server starts
- Makes application configuration explicit and verifiable
- Requires using ApiBuilder methods within `config.routes()`

### 2. Validation API Updates

**What Changed**:
Validator methods now return `Validator<T?>` by default (nullable). To get non-nullable validators, call `.required()` explicitly.

**Javalin 6 (Old Way)**:
```java
Integer age = ctx.queryParamAsClass("age", Integer.class).get();
```

**Javalin 7 (New Way)**:
```java
Integer age = ctx.queryParamAsClass("age", Integer.class).required().get();
```

**Rules**:
- `.required()` must be called before `.get()` for non-nullable types
- Without `.required()`, result is nullable
- Improves null safety and explicit intent

### 3. Configuration Property Changes

| Old (v6) | New (v7) | Notes |
|----------|----------|-------|
| `config.jetty.defaultHost` | `config.jetty.host` | Default host for server |
| `config.jetty.defaultPort` | `config.jetty.port` | Default port for server |
| `ctx.matchedPath()` | `ctx.endpoint().path()` | Get the route path |
| `app.createAndStart()` | `app.create().start()` | Constructor/startup pattern |
| `app.unsafeConfig()` | `app.unsafe` | Returns `JavalinState` instead |

**Context Updates**:
```java
// Javalin 6
String path = ctx.matchedPath();

// Javalin 7
String path = ctx.endpoint().path();
```

### 4. Exception and Error Handlers

**What Changed**:
Exception and error handlers must be configured in the config block.

**Javalin 6 (Old Way)**:
```java
app.error(404, ctx -> ctx.json(Map.of("error", "Not found")));
app.exception(Exception.class, (e, ctx) -> ctx.status(500));
```

**Javalin 7 (New Way)**:
```java
Javalin.create(config -> {
    config.routes.error(404, ctx -> {
        ctx.json(Map.of("error", "Not found"));
    });
    config.routes.exception(Exception.class, (e, ctx) -> {
        ctx.status(500);
    });
}).start();
```

### 5. Module Reorganization

**RateLimitUtil → RateLimitPlugin**:
```java
// Javalin 6
config.requestLogger((ctx, executionMs) -> {
    // logging
});

// Javalin 7
config.registerPlugin(new RateLimitPlugin(rateLimit -> {
    rateLimit.requestsPerMinute = 100;
}));
```

**JavalinVue → Plugin Architecture**:
- Previously: Built-in Vue support
- Now: Use JavalinVue plugin or rendering plugins

### 6. Template Rendering Split

**What Changed**:
Template rendering was split into separate modules per engine.

**Javalin 6**:
```xml
<dependency>
    <groupId>io.javalin</groupId>
    <artifactId>javalin</artifactId>
    <version>6.x.x</version>
</dependency>
```

**Javalin 7** (Choose one engine):
```xml
<!-- For JTE -->
<dependency>
    <groupId>io.javalin</groupId>
    <artifactId>javalin-rendering-jte</artifactId>
    <version>7.x.x</version>
</dependency>

<!-- For Mustache -->
<dependency>
    <groupId>io.javalin</groupId>
    <artifactId>javalin-rendering-mustache</artifactId>
    <version>7.x.x</version>
</dependency>

<!-- For Velocity -->
<dependency>
    <groupId>io.javalin</groupId>
    <artifactId>javalin-rendering-velocity</artifactId>
    <version>7.x.x</version>
</dependency>

<!-- For Pebble -->
<dependency>
    <groupId>io.javalin</groupId>
    <artifactId>javalin-rendering-pebble</artifactId>
    <version>7.x.x</version>
</dependency>
```

### 7. Multipart Configuration

**What Changed**:
Multipart configuration is now part of Jetty config instead of global singleton.

**Javalin 6**:
```java
MultipartUtil.preUploadFunction = (exchange) -> {
    // validate before upload
};
```

**Javalin 7**:
```java
config.jetty.multipartConfig = new MultipartConfigElement(
    location,
    maxFileSize,
    maxRequestSize,
    fileSizeThreshold
);
```

### 8. Servlet API Package Changes

**What Changed**:
Package migration from `javax.servlet.*` to `jakarta.servlet.*`

**Javalin 6**:
```java
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
```

**Javalin 7**:
```java
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
```

**Note**: This aligns with Jetty 12 upgrade to Jakarta EE 10

### 9. Jetty Version Upgrade

**What Changed**:
Requires Jetty 12+ (previously 11 or earlier)

**Impact**:
- Jetty 12 = Jakarta EE 10
- All javax.* packages renamed to jakarta.*
- Better HTTP/2 support
- Improved async handling

### 10. Java Version Requirement

**Javalin 6**: Java 11+
**Javalin 7**: Java 17+

**Impact**:
- Text blocks available (triple quotes)
- Records and sealed classes supported
- Pattern matching improvements
- Updated minimum language features

## Migration Checklist

### Phase 1: Dependencies & Java Version

- [ ] Upgrade Java version to 17+
- [ ] Update Javalin to 7.x.x
- [ ] Update Jetty dependency (should auto-update with Javalin)
- [ ] Update servlet API imports if used directly

### Phase 2: Route Configuration

- [ ] Move all route definitions into `config.routes()` block
- [ ] Remove any `app.get()`, `app.post()`, etc. calls after `.start()`
- [ ] Use ApiBuilder pattern for path grouping
- [ ] Update route registration to happen before `.start()`

### Phase 3: Validation Updates

- [ ] Find all validator chains
- [ ] Add `.required()` for non-nullable validations
- [ ] Test null handling for optional validators
- [ ] Update unit tests for validation logic

### Phase 4: Handler and Error Configuration

- [ ] Move exception handlers to config block
- [ ] Move error handlers to config block
- [ ] Move before/after handlers to config.routes()
- [ ] Test error handling paths

### Phase 5: API Changes

- [ ] Replace `ctx.matchedPath()` with `ctx.endpoint().path()`
- [ ] Update `app.unsafeConfig()` to `app.unsafe`
- [ ] Remove `createAndStart()` calls, use `create().start()`

### Phase 6: Template Rendering

- [ ] Remove generic javalin dependency for templates
- [ ] Add specific rendering engine module
- [ ] Register rendering plugin if needed
- [ ] Update template path references

### Phase 7: Multipart Handling

- [ ] Find MultipartUtil usage
- [ ] Move to Jetty multipartConfig in config block
- [ ] Test file upload functionality

### Phase 8: Testing

- [ ] Run full test suite
- [ ] Test all endpoints
- [ ] Test error handling
- [ ] Test async operations
- [ ] Verify validation behavior

## Complete Example: Before and After

**Javalin 6**:
```java
public class App {
    public static void main(String[] args) {
        var app = Javalin.create()
            .start(8080);

        app.get("/", ctx -> ctx.result("Hello"));
        app.get("/users/{id}", ctx -> getUser(ctx));
        app.post("/users", ctx -> createUser(ctx));
        app.error(404, ctx -> ctx.json(Map.of("error", "Not found")));

        app.exception(Exception.class, (e, ctx) -> {
            ctx.status(500).json(Map.of("error", e.getMessage()));
        });
    }
}
```

**Javalin 7**:
```java
public class App {
    public static void main(String[] args) {
        var app = Javalin.create(config -> {
            config.routes(() -> {
                get("/", ctx -> ctx.result("Hello"));
                get("/users/{id}", ctx -> getUser(ctx));
                post("/users", ctx -> createUser(ctx));

                error(404, ctx -> ctx.json(Map.of("error", "Not found")));
                exception(Exception.class, (e, ctx) -> {
                    ctx.status(500).json(Map.of("error", e.getMessage()));
                });
            });
        }).start(8080);
    }
}
```

## Common Migration Issues

### Issue 1: Routes Not Working After Start
**Problem**: Routes added after `.start()` are ignored
**Solution**: Move all routes into config block before `.start()`

### Issue 2: Nullable Validators
**Problem**: Getting null from validators unexpectedly
**Solution**: Add `.required()` before `.get()` for non-null results

### Issue 3: Package Import Errors
**Problem**: `javax.servlet` imports fail
**Solution**: Update to `jakarta.servlet` packages

### Issue 4: Context API Changes
**Problem**: `ctx.matchedPath()` not found
**Solution**: Use `ctx.endpoint().path()` instead

## Performance Considerations

- Upfront route configuration eliminates runtime route registration overhead
- No performance impact on route matching (same algorithm)
- May see slight startup time increase due to full configuration requirements
- Overall application performance unchanged

## Rollback Strategy

If issues arise during migration:
1. Keep v6 branch stable
2. Test v7 in separate branch
3. Deploy to staging before production
4. Gradual rollout if possible
5. Have v6 fallback ready

## Getting Help

- Official migration guide: https://javalin.io/migration-guide-javalin-6-to-7
- GitHub issues: https://github.com/javalin/javalin/issues
- Discord community: Connect with other developers
- Javalin news: Check release notes for detailed updates
