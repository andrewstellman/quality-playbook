# Javalin Official Documentation Overview

## Project Information
- **Framework**: Javalin - A lightweight Java and Kotlin web framework
- **Built On**: Jetty 12
- **Java Requirement**: Java 17+ (Javalin 7)
- **License**: Apache 2
- **Website**: https://javalin.io
- **GitHub**: https://github.com/javalin/javalin

## Core Philosophy

Javalin explicitly rejects the full-framework approach. The project aims to be "a lightweight REST API library (or a micro framework)" rather than a comprehensive web framework with MVC architecture.

### Key Design Principles

**Simplicity Over Complexity**
- Intentionally excludes MVC patterns while providing selective conveniences like template engines, WebSockets, and static file serving
- Hybrid approach allows developers to use Javalin for both API backends and basic static content delivery
- Requires no separate server infrastructure (applications compile to standalone JARs with embedded Jetty)

**Fluent API Design**
- All Javalin methods return `this`, enabling a declarative programming style
- Intuitive for developers across teams

**Language Interoperability**
- Seamless Java-Kotlin compatibility
- Core classes implemented in Java
- Library primarily written in Kotlin
- Positions Javalin as accessible entry point to Kotlin for Java-focused organizations

## Influences

Javalin draws inspiration from established micro-frameworks:
- **Sinatra** (Ruby)
- **Spark** (Java/Kotlin)
- **koa.js** (JavaScript)

This lineage shapes its minimalist philosophy and practical REST API focus.

## Javalin vs Other Frameworks

### Javalin vs Spark

Javalin originated as a Spark fork but quickly evolved:
- Reached feature parity with Spark within months
- Became a ground-up rewrite influenced by express.js
- Offers capabilities Spark lacks:
  - Fully configurable Jetty with HTTP2 support
  - OpenAPI/Swagger integration
  - Async request handling
  - Lambda WebSockets with routing
  - Server-sent events (SSE)
  - Built-in session handling
  - Input validation and casting
  - Error mapping and access management

**API Design Differences**:
- Javalin: Unified `Handler` model operating through `Context` object
- Spark: Separates `Routes` (with return values) and `Filters` (void methods)

**Performance & Code Quality**:
- Javalin codebase ~1/3 the size of Spark's
- Written in Kotlin with proper type safety
- Performs ~2x faster according to TechEmpower Benchmarks
- Comprehensive test coverage exceeding actual code volume

**Maintenance Status**:
- Spark's last feature release was over a year ago
- Only receiving bugfixes
- Many developers migrating from Spark to Spring Boot or Javalin

### Javalin vs Spring Boot

| Aspect | Javalin | Spring Boot |
|--------|---------|------------|
| **Scope** | Lightweight REST APIs | Comprehensive enterprise framework |
| **Architecture** | Minimalistic, no external dependencies | Full-fledged with modular architecture |
| **Learning Curve** | Smaller, intuitive API | Larger, many concepts to learn |
| **Features** | Basic web dev (no DB, ORM, advanced security) | Complete coverage (DB, security, validation) |
| **Community** | Smaller, growing ecosystem | Large, mature, extensive documentation |
| **Use Cases** | Lightweight REST APIs with minimal deps | Enterprise applications, complex features |

## Framework Statistics
- **GitHub Stars**: 2,466+
- **Commits**: 1,163+
- **Contributors**: 649+
- **Discord Members**: 638+
- **Open Issues**: 1,323+
- **Releases**: 154+

## Documentation Availability
- Official documentation: https://javalin.io/documentation
- Tutorials: https://javalin.io/tutorials (35+ tutorials, official and community)
- Archive docs (older versions): https://javalin.io/archive/docs/
- GitHub repository: https://github.com/javalin/javalin

## Core Framework Information

### Request Handling
- HTTP handlers (before, endpoint, after, wrapper types)
- WebSocket support with multiple event handlers
- Server-sent Events (SSE)
- Request/response context objects

### Validation & Security
- Built-in validator API for query params, form data, and request bodies
- Access management through role-based handlers
- Exception and error mapping mechanisms
- Default HTTP response classes (404, 401, 403, etc.)

### Configuration
- HTTP settings (ETags, compression, timeouts)
- Jetty server customization
- Static file serving and SPA routing
- Request logging and CORS support

### Advanced Features
- Asynchronous request handling with CompletableFuture
- Plugin system for extending functionality
- Custom JSON mapper configuration (Jackson default)
- Rate limiting through RateLimitPlugin

## Key Implementation Patterns

**Routes Declaration** (Javalin 7):
Routes must be declared within `config.routes` during application creation—you can no longer add routes after calling `.start()`. This ensures all routes are registered before the server starts.

**Handler Groups and Paths**:
Supports organizing endpoints through handler groups and path building, with support for custom HTTP methods like PROPFIND for WebDAV protocols.

## Deployment & Integration

Javalin applications support integration with:
- Heroku
- AWS Lambda
- Servlet containers
- GraalVM native images
- Virtual thread support
