# Javalin Plugin System Architecture

## Plugin System Overview

Javalin has a plugin system that lets you add functionality by extending the Plugin class. The modern plugin system (Javalin 6+) was reworked to be more opinionated and consistent.

## Plugin API Design

### Modern Plugin System (Javalin 6+)

Plugins are represented by an abstract class `Plugin` with:
- **Required**: Config consumer and default config in constructor
- **Optional**: Hooks for `onInitialize()` and `onStart()`

### Plugin Pattern Example

```
public abstract class Plugin {
    protected final PluginConfig config;

    public Plugin(Consumer<PluginConfig> config) {
        this.config = new PluginConfig();
        config.accept(this.config);
    }

    public void onInitialize(JavalinConfig config) {
        // Hook for initialization
    }

    public void onStart(Javalin javalin) {
        // Hook for startup
    }
}
```

## Key Design Features

**Consumer-Based API**:
- Enforces consistent, opinionated API
- Same pattern used throughout Javalin configuration
- Improves IDE autocompletion and type safety

**Flexible Hooks**:
- `onInitialize()`: Run during Javalin configuration setup
- `onStart()`: Run after server starts
- Can be overridden selectively

## Installing Plugins

Plugins are installed by adding dependency to project and registering:

```
var app = Javalin.create(config -> {
    config.registerPlugin(new MyPlugin(pluginConfig -> {
        pluginConfig.option1 = "value";
        pluginConfig.option2 = true;
    }));
}).start();
```

## Plugin Categories

### Bundled Plugins (Included with Javalin)

1. **JavalinVue**
   - Enables Vue single-file components with server-side routing
   - Ideal for rapid prototyping
   - Built-in SSR support

2. **CORS**
   - Bundles functionality to set CORS headers
   - Configurable for some or all origins
   - Supports subdomain wildcards and credential handling

3. **RouteOverview**
   - Provides HTML/JSON overviews of registered routes
   - Useful for debugging and API documentation
   - Development-only typically

4. **DevLogging**
   - Captures and logs request/response details
   - Development tool for debugging
   - Shows headers, body, timing information

5. **Rate Limiting**
   - Built as `RateLimitPlugin` (Javalin 7)
   - Configurable rate limits per endpoint
   - Previously `RateLimitUtil`

## Third-Party/Community Plugins

1. **OpenAPI Annotation Processor**
   - Reflection-free OpenAPI documentation
   - Schema validation
   - Compile-time processing
   - Swagger UI integration

2. **SSL Helpers**
   - Simple way to configure SSL for Javalin
   - Supports formats: PEM, PKCS12, JKS
   - Automatic certificate handling

3. **Javalin Rendering** (Template Engines)
   - JTE (Java Template Engine)
   - Mustache
   - Velocity
   - Pebble
   - Handlebars
   - Thymeleaf
   - Split into separate modules in Javalin 7

4. **GraphQL**
   - GraphQL specification implementation
   - Query and mutation support
   - Schema definition and execution

5. **JavalinMithril**
   - Mithril.js integration
   - Multi-page application support
   - Lightweight frontend framework integration

6. **Micrometer Plugin**
   - Metrics collection using Micrometer library
   - Prometheus, InfluxDB, and other backends
   - Performance monitoring

7. **javalin-pac4j**
   - OAuth, CAS, SAML, OpenID Connect support
   - LDAP integration
   - JWT authentication
   - Comprehensive security library

8. **Javalin-JWT**
   - JWT-specific extension for Javalin
   - Convenient wrapper around jjwt
   - Token encoding and validation

9. **javalin-jwt (Alternative)**
   - Basic JWT extension implementation
   - GitHub: https://github.com/kmehrunes/javalin-jwt

## Plugin Store

Javalin maintains a plugin store at https://javalin.io/plugins/

Features:
- Browse available plugins
- Filter by category
- Version compatibility information
- Report issues if creators don't address problems
- Maintained as official resource

## Plugin Lifecycle

1. **Construction**: Plugin instance created with config consumer
2. **Registration**: Plugin registered via `config.registerPlugin()`
3. **Initialization**: `onInitialize()` hook called during config setup
4. **Startup**: `onStart()` hook called after server starts
5. **Request Handling**: Plugin may intercept/modify requests via handlers

## Plugin Configuration Pattern

```
config.registerPlugin(new CustomPlugin(cfg -> {
    cfg.enabled = true;
    cfg.path = "/api";
    cfg.requireAuth = true;
}));
```

This pattern ensures:
- Type-safe configuration
- IDE support and autocompletion
- Clear intent in code
- Consistent with rest of Javalin API

## Creating Custom Plugins

Best practices for custom plugin development:

1. **Extend Plugin class**:
```
class MyPlugin extends Plugin {
    public MyPlugin(Consumer<MyPluginConfig> config) {
        super(config);
    }

    @Override
    public void onInitialize(JavalinConfig config) {
        // Register handlers, validators, etc.
    }
}
```

2. **Define Plugin Config**:
```
class MyPluginConfig {
    public boolean enabled = true;
    public String path = "/default";
    // Add options for your plugin
}
```

3. **Hook into Lifecycle**:
   - Use `onInitialize()` for setup requiring config
   - Use `onStart()` for operations needing running server
   - Add cleanup in appropriate places

## Plugin Compatibility

- **Javalin 5.x, 6.x, 7.x**: Modern plugin API
- **Javalin 4 and earlier**: Legacy plugin API (deprecated)
- Check plugin documentation for version compatibility

## Popular Plugin Combinations

**REST API Development**:
- OpenAPI Plugin + SwaggerUI
- CORS Plugin
- Micrometer for monitoring

**Full-Stack Development**:
- JavalinVue (Javalin 5.x) or rendering plugin
- CORS Plugin
- SSL Helpers
- Rate Limiting

**Enterprise Applications**:
- javalin-pac4j for security
- Micrometer for observability
- Database plugins (Hibernate integration)
- Custom plugins for business logic

## Plugin Store Reporting

Plugin creators may not always maintain plugins:
- Report issues if creators don't respond
- Store provides mechanism to flag problematic plugins
- Community-maintained alternatives available

## Template Engine Plugin Reorganization (Javalin 7)

Breaking change: Template rendering now split into separate modules:
- `javalin-rendering-jte`
- `javalin-rendering-mustache`
- `javalin-rendering-velocity`
- `javalin-rendering-pebble`
- `javalin-rendering-handlebars`
- `javalin-rendering-thymeleaf`

Migration path:
1. Remove old template dependency
2. Add specific engine module
3. Register rendering plugin
4. Update template path references

## Example: Full Plugin Setup

```
var app = Javalin.create(config -> {
    // CORS
    config.registerPlugin(new CorsPlugin(cors -> {
        cors.add(c -> c
            .anyHost()
            .allowCredentials = false
        );
    }));

    // OpenAPI Documentation
    config.registerPlugin(new OpenApiPlugin(openApi -> {
        openApi.setDocumentationPath("/swagger-ui");
        openApi.setDefinitionPath("/openapi.json");
    }));

    // Monitoring
    config.registerPlugin(new MicrometerPlugin(micrometer -> {
        micrometer.registry = new MeterRegistry();
    }));

    // Custom Plugin
    config.registerPlugin(new RateLimitPlugin(rateLimit -> {
        rateLimit.requestsPerMinute = 100;
    }));
}).start();
```

## Evolution from v6 to v7

**Javalin 6.0.0**: Modern plugin API introduced
**Javalin 7.0.0**:
- Plugins remain core design
- RateLimitPlugin replaces RateLimitUtil
- Template engines modularized
- Plugin registration remains in config block
