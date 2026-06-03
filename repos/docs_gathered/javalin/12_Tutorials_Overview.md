# Javalin Tutorials Overview

Complete listing and reference guide for all official and community tutorials available on javalin.io.

## Official Tutorials

Fundamental guides focusing on one core concept at a time, with examples in both Java and Kotlin.

### Getting Started
1. **Building an Omegle Clone in Javalin**
   - WebSocket implementation
   - Real-time messaging
   - User connections and routing
   - GitHub: javalin-samples repository

2. **A Quick Intro to SSL in Java**
   - HTTPS configuration
   - Certificate management
   - Secure endpoints
   - Production TLS setup

3. **Gradle Setup**
   - Project structure
   - Dependency management
   - Build configuration
   - Best practices

4. **Maven Setup**
   - Maven POM configuration
   - Dependency versions
   - Build and packaging
   - Plugin setup

### Core Features

5. **Testing Javalin Applications**
   - Unit tests with mocking
   - Integration tests (functional)
   - End-to-end UI tests
   - Test tools and frameworks
   - Reference: 07_Testing_Guide.md

6. **Documenting Endpoints with OpenAPI 3**
   - OpenAPI specification
   - Swagger UI integration
   - API documentation generation
   - Reference: 08_OpenAPI_Swagger_Documentation.md

7. **Simple Frontends with Javalin and Vue**
   - JavalinVue plugin
   - Single-file components
   - Server-side routing
   - SPA integration

8. **Jetty Session Handling**
   - Session configuration
   - Session attributes
   - Cookie management
   - Session lifecycle

9. **WebSockets Google Docs Clone**
   - Real-time collaboration
   - WebSocket routing
   - Message broadcasting
   - Conflict resolution patterns

10. **Creating Monitoring Dashboards**
    - Metrics collection
    - Dashboard creation
    - Real-time monitoring
    - Performance tracking

11. **WebSockets Chat Application**
    - Basic WebSocket setup
    - Message routing
    - User management
    - Broadcasting messages

12. **Secure Your Endpoints**
    - Authentication patterns
    - Authorization rules
    - Role-based access control
    - Reference: 06_Authentication_Authorization.md

13. **Sending Emails from a Javalin Backend**
    - Email integration
    - SMTP configuration
    - Email templates
    - Async sending

14. **HTML Forms & Javalin Backend**
    - Form data handling
    - Form validation
    - File uploads
    - CSRF protection

15. **Single-Page App with Kotlin and Vue.js**
    - Kotlin backend
    - Vue.js frontend
    - SPA routing
    - State management

16. **Deploying to Heroku**
    - Heroku setup
    - Procfile configuration
    - Environment variables
    - Reference: 11_Deployment_Guides.md

17. **Kotlin CRUD REST API**
    - Kotlin-specific features
    - CRUD operations
    - RESTful design
    - Data classes

18. **Docker Setup**
    - Dockerfile creation
    - Docker Compose
    - Container orchestration
    - Reference: 11_Deployment_Guides.md

## Community Tutorials

More complex, specialized topics maintained by the community.

### Advanced Features

19. **Using Javalin with Cloudflare**
    - Cloudflare Workers integration
    - CDN configuration
    - Performance optimization
    - Edge computing

20. **Using Javalin with Hibernate ORM**
    - Database integration
    - Entity mapping
    - Transaction management
    - Reference: 10_Database_Integration_Hibernate.md

21. **Extra Details on Javalin and Logging Providers**
    - SLF4J configuration
    - Logback setup
    - Log levels and patterns
    - Structured logging

22. **mTLS in Javalin**
    - Mutual TLS/SSL
    - Certificate authentication
    - Client verification
    - Secure service-to-service communication

23. **Javalin with Java Platform Module System (JPMS) and Gradle**
    - Module system setup
    - Module dependencies
    - Service providers
    - Gradle module configuration

24. **Using Javalin with Bukkit, Spigot, Paper, BungeeCord, or Waterfall**
    - Minecraft server integration
    - Plugin development
    - Network communication
    - Event handling

25. **Serving Protobuf via a REST API**
    - Protocol Buffers integration
    - Binary serialization
    - REST endpoint setup
    - Type definitions

26. **Javalin as a Simulator for HTTP-Based APIs**
    - Mock API servers
    - Request matching
    - Response generation
    - Testing tool usage

### Frontend Integration

27. **Frontends With Mithril and Javalin**
    - Mithril.js framework
    - Component-based UI
    - Lightweight frontend
    - Type-safe integration

### Infrastructure & Operations

28. **Tracing Javalin Application**
    - Distributed tracing
    - OpenTelemetry integration
    - Jaeger/Elastic APM
    - Request tracking
    - Reference: 11_Deployment_Guides.md (Monitoring section)

29. **Real-Time Analytics with InfluxDB**
    - Time-series data
    - Metrics storage
    - Dashboard creation
    - Data visualization

### Security

30. **Using Sureness to Protect REST API Security**
    - RBAC implementation
    - Authentication methods
    - Permission management
    - Reference: 06_Authentication_Authorization.md

31. **JWT in a Javalin Application**
    - Token generation
    - Token validation
    - Refresh tokens
    - Reference: 06_Authentication_Authorization.md

### Deployment & Infrastructure

32. **Deploy Kotlin REST API to Raspberry Pi**
    - ARM deployment
    - IoT applications
    - Resource-constrained environments
    - Cross-compilation

33. **Running on GraalVM (22MB Total Size)**
    - Native image compilation
    - Startup optimization
    - Memory footprint
    - Reference: 11_Deployment_Guides.md (GraalVM section)

### Rendering & Templating

34. **Rendering JTE Templates in Javalin**
    - Java Template Engine
    - Template syntax
    - Dynamic content
    - Server-side rendering

### Testing & Development

35. **Mockito Testing**
    - Mock object creation
    - Unit test patterns
    - Handler testing
    - Context mocking

36. **Embed Javalin Into Servlet Container**
    - WAR deployment
    - Application servers
    - Servlet compatibility
    - Legacy system integration

### Miscellaneous

37. **Basic Website Structure**
    - Project layout
    - Directory organization
    - Configuration files
    - Development setup

38. **Java 10 and Google Guice**
    - Dependency injection
    - Guice integration
    - Bean management
    - Configuration patterns

## Tutorial Resources

### Example Projects

The javalin-samples repository contains complete working examples:
- GitHub: https://github.com/javalin/javalin-samples
- Covers Javalin 4+
- Multiple example applications
- Best practices demonstration

### Tutorial Submissions

The Javalin community welcomes tutorial contributions:
- Submit via GitHub Pull Request to website repository
- Follow existing tutorial format
- Include both Java and Kotlin examples where applicable
- Add explanatory diagrams when helpful

## Learning Path Recommendations

### Beginner
1. **Gradle Setup** (or Maven Setup)
2. **Simple Frontends with Javalin and Vue**
3. **Kotlin CRUD REST API** (or basic REST examples)
4. **Testing Javalin Applications**

### Intermediate
5. **Secure Your Endpoints** (06_Authentication_Authorization.md)
6. **Using Javalin with Hibernate ORM** (10_Database_Integration_Hibernate.md)
7. **Documenting Endpoints with OpenAPI 3** (08_OpenAPI_Swagger_Documentation.md)
8. **Docker Setup** (11_Deployment_Guides.md)

### Advanced
9. **WebSockets Chat Application** (03_WebSocket_SSE_Async.md)
10. **Tracing Javalin Application**
11. **Running on GraalVM** (11_Deployment_Guides.md)
12. **Using Sureness to Protect REST API Security** (06_Authentication_Authorization.md)

### Specialized Topics
- **Frontend Integration**: Mithril, Vue, JavalinVue examples
- **Infrastructure**: Cloudflare, InfluxDB, Elastic APM
- **Deployment**: Heroku, Raspberry Pi, GraalVM native image
- **Protocols**: mTLS, Protobuf, Minecraft servers

## Key Topics by Document Reference

| Topic | Document(s) |
|-------|------------|
| Routing & Endpoints | 02_Routing_and_Endpoints.md |
| WebSockets & SSE | 03_WebSocket_SSE_Async.md |
| Plugins | 04_Plugin_System_Architecture.md |
| Migration | 05_Migration_Guide_v6_to_v7.md |
| Auth & Security | 06_Authentication_Authorization.md |
| Testing | 07_Testing_Guide.md |
| API Documentation | 08_OpenAPI_Swagger_Documentation.md |
| CORS & Errors | 09_CORS_Error_Handling.md |
| Database | 10_Database_Integration_Hibernate.md |
| Deployment | 11_Deployment_Guides.md |

## Official Javalin Resources

- **Website**: https://javalin.io
- **Tutorials Hub**: https://javalin.io/tutorials/
- **GitHub**: https://github.com/javalin/javalin
- **GitHub Samples**: https://github.com/javalin/javalin-samples
- **Discord Community**: Community support and discussions
- **News/Blog**: https://javalin.io/news/

## Tutorial Statistics

- **Official Tutorials**: 18
- **Community Tutorials**: 20
- **Total Available**: 38+
- **Languages Covered**: Java and Kotlin
- **Complexity Levels**: Beginner to Advanced
- **Last Updated**: Continuously maintained

## Contributing to Documentation

If you'd like to contribute:
1. Fork https://github.com/javalin/website
2. Add tutorial in `_posts/tutorials/` directory
3. Follow existing format and naming conventions
4. Include both Java and Kotlin examples
5. Submit pull request
6. Community review and feedback
7. Merge and publication

## Tutorial File Structure

Tutorials are stored in:
```
website/_posts/tutorials/
├── official/
│   ├── year/
│   │   └── tutorial-name.md
└── community/
    ├── year/
    │   └── tutorial-name.md
```

Each file includes:
- Title and description
- Date published/updated
- Author information
- Example code (Java and Kotlin)
- Links to related resources
- Source repository links

## Related Learning Resources

Beyond tutorials, see:
- **Official API Documentation**: https://javalin.io/documentation
- **GitHub Issues**: Real-world use cases and edge cases
- **Community Discord**: Questions and discussions
- **Blog Posts**: In-depth technical articles
- **Generated Javadocs**: API reference documentation
