# Javalin Documentation Index

Quick reference guide to find topics in the Javalin documentation collection.

## Files at a Glance

| File | Purpose | Pages | Key Topics |
|------|---------|-------|-----------|
| `README.md` | **START HERE** - Overview and quick start | 5 | Framework intro, file guide, learning paths |
| `sources.md` | Source attribution and references | 8 | 100+ URLs, research methodology, updates |
| `01_Official_Documentation_Overview.md` | Framework overview | 5 | Philosophy, comparisons, statistics |
| `02_Routing_and_Endpoints.md` | HTTP routing | 7 | Handlers, routes, path params, validation |
| `03_WebSocket_SSE_Async.md` | Real-time communication | 7 | WebSocket, SSE, async patterns |
| `04_Plugin_System_Architecture.md` | Plugin design | 8 | Plugin API, bundled plugins, community plugins |
| `05_Migration_Guide_v6_to_v7.md` | Upgrade guide | 10 | **CRITICAL if upgrading**, breaking changes |
| `06_Authentication_Authorization.md` | Security | 11 | JWT, OAuth, RBAC, authentication patterns |
| `07_Testing_Guide.md` | Testing strategies | 13 | Unit, integration, E2E testing |
| `08_OpenAPI_Swagger_Documentation.md` | API documentation | 16 | OpenAPI, Swagger UI, CRUD example |
| `09_CORS_Error_Handling.md` | Cross-origin & errors | 15 | CORS config, error handlers, troubleshooting |
| `10_Database_Integration_Hibernate.md` | Database ORM | 17 | Hibernate setup, transactions, query patterns |
| `11_Deployment_Guides.md` | Deployment & operations | 13 | Docker, Kubernetes, AWS, GraalVM, monitoring |
| `12_Tutorials_Overview.md` | Tutorial index | 10 | 38+ official & community tutorials, learning paths |

**Total: 14 files, 5,492 lines, 176KB**

## Find Topics by Search

### A - Application
- **Application Server Integration**: `11_Deployment_Guides.md` (Embedded Jetty section)
- **Architecture**: `01_Official_Documentation_Overview.md`, `04_Plugin_System_Architecture.md`

### B - Best Practices
- **Best Practices**: `06_Authentication_Authorization.md`, `09_CORS_Error_Handling.md`, `07_Testing_Guide.md`
- **Bundled Plugins**: `04_Plugin_System_Architecture.md`

### C - Configuration
- **Configuration**: `01_Official_Documentation_Overview.md`, `04_Plugin_System_Architecture.md`
- **CORS**: `09_CORS_Error_Handling.md` (Complete section with examples)
- **Creating REST APIs**: `02_Routing_and_Endpoints.md`, `08_OpenAPI_Swagger_Documentation.md`

### D - Database
- **Database Integration**: `10_Database_Integration_Hibernate.md`
- **Deployment**: `11_Deployment_Guides.md`
- **Docker**: `11_Deployment_Guides.md` (Docker section)

### E - Error Handling
- **Error Handling**: `09_CORS_Error_Handling.md` (Complete section)
- **Exception Handlers**: `09_CORS_Error_Handling.md`

### F - Frontend
- **Frontend Integration**: `12_Tutorials_Overview.md` (Vue, Mithril sections)
- **Framework Comparison**: `01_Official_Documentation_Overview.md`

### G - Getting Started
- **Getting Started**: `README.md`, `01_Official_Documentation_Overview.md`
- **GraalVM Native Image**: `11_Deployment_Guides.md` (GraalVM section)
- **GraphQL**: `04_Plugin_System_Architecture.md` (Community plugins)

### H - Handlers
- **Handlers**: `02_Routing_and_Endpoints.md` (Handler types section)
- **Heroku**: `11_Deployment_Guides.md` (Heroku section)
- **Hibernate**: `10_Database_Integration_Hibernate.md`

### J - JWT
- **JWT**: `06_Authentication_Authorization.md` (JWT section)

### K - Kubernetes
- **Kubernetes**: `11_Deployment_Guides.md` (Kubernetes section)

### L - Lambda
- **Lambda (AWS)**: `11_Deployment_Guides.md` (AWS Lambda section)
- **Learning Path**: `README.md`, `12_Tutorials_Overview.md`

### M - Migration
- **Migration**: `05_Migration_Guide_v6_to_v7.md` (**CRITICAL for upgrades**)
- **Monitoring**: `11_Deployment_Guides.md` (Monitoring section)

### O - OpenAPI
- **OpenAPI/Swagger**: `08_OpenAPI_Swagger_Documentation.md` (Complete section)

### P - Plugin
- **Plugin Architecture**: `04_Plugin_System_Architecture.md` (Complete section)
- **Performance**: `11_Deployment_Guides.md` (Performance tuning section)

### R - Routes
- **Routing**: `02_Routing_and_Endpoints.md` (Complete section)
- **RBAC**: `06_Authentication_Authorization.md` (Access control section)

### S - Security
- **Security**: `06_Authentication_Authorization.md` (Complete section)
- **Server-Sent Events**: `03_WebSocket_SSE_Async.md` (SSE section)
- **Static Files**: `02_Routing_and_Endpoints.md` (Static files and SPA section)
- **Sureness Framework**: `06_Authentication_Authorization.md`

### T - Testing
- **Testing**: `07_Testing_Guide.md` (Complete section)
- **Tutorials**: `12_Tutorials_Overview.md` (Complete index of 38+ tutorials)

### V - Validation
- **Validation**: `02_Routing_and_Endpoints.md` (Input validation section)

### W - WebSocket
- **WebSocket**: `03_WebSocket_SSE_Async.md` (Complete section)

## Common Tasks & Where to Find Them

### I want to...

**Create a Hello World app**
→ `01_Official_Documentation_Overview.md` + `02_Routing_and_Endpoints.md` → `12_Tutorials_Overview.md` (tutorials)

**Build a REST API**
→ `02_Routing_and_Endpoints.md` → `06_Authentication_Authorization.md` → `08_OpenAPI_Swagger_Documentation.md`

**Add authentication/JWT**
→ `06_Authentication_Authorization.md` (JWT section) + `07_Testing_Guide.md` (testing auth)

**Create real-time features (WebSocket/SSE)**
→ `03_WebSocket_SSE_Async.md` (WebSocket or SSE section) → `12_Tutorials_Overview.md` (chat tutorial)

**Add database (Hibernate)**
→ `10_Database_Integration_Hibernate.md` (complete guide)

**Document my API**
→ `08_OpenAPI_Swagger_Documentation.md` (complete CRUD example)

**Test my application**
→ `07_Testing_Guide.md` (unit, integration, E2E patterns)

**Deploy to production**
→ `11_Deployment_Guides.md` (Docker, Kubernetes, AWS, Heroku, GraalVM)

**Upgrade from v6 to v7**
→ `05_Migration_Guide_v6_to_v7.md` (**READ COMPLETELY - breaking changes**)

**Handle errors & CORS**
→ `09_CORS_Error_Handling.md` (complete section with examples)

**Use plugins**
→ `04_Plugin_System_Architecture.md` (architecture & plugin list)

**Find tutorials**
→ `12_Tutorials_Overview.md` (38+ tutorials indexed and described)

## Code Examples by Topic

### Authentication
- Basic auth: `06_Authentication_Authorization.md` (Basic Authentication section)
- JWT: `06_Authentication_Authorization.md` (JWT section)
- OAuth: `06_Authentication_Authorization.md` (OAuth 2.0 section)
- RBAC: `06_Authentication_Authorization.md` (Role-Based Access Control section)

### Database
- Entity mapping: `10_Database_Integration_Hibernate.md` (Entity Class section)
- Transactions: `10_Database_Integration_Hibernate.md` (Hibernate Wrapper section)
- Queries: `10_Database_Integration_Hibernate.md` (Advanced Patterns section)

### Error Handling
- Exception handlers: `09_CORS_Error_Handling.md` (Exception Handlers section)
- Error handlers: `09_CORS_Error_Handling.md` (Error Handlers section)
- Complete example: `09_CORS_Error_Handling.md` (Complete Error Handling Example section)

### WebSocket
- Basic setup: `03_WebSocket_SSE_Async.md` (WebSocket Configuration section)
- Chat app: `03_WebSocket_SSE_Async.md` (WebSocket Chat Example section)
- Testing: `07_Testing_Guide.md` (Testing WebSockets section)

### Testing
- Unit tests: `07_Testing_Guide.md` (Unit Tests section)
- Integration: `07_Testing_Guide.md` (Functional/Integration Tests section)
- WebSocket: `07_Testing_Guide.md` (Testing WebSockets section)

## Quick Navigation

### For Different User Types

**Beginner Java Developer**
1. `README.md` (overview)
2. `01_Official_Documentation_Overview.md` (framework philosophy)
3. `02_Routing_and_Endpoints.md` (basic routing)
4. `07_Testing_Guide.md` (testing basics)

**Experienced Spring Developer**
1. `01_Official_Documentation_Overview.md` (Javalin vs Spring comparison)
2. `02_Routing_and_Endpoints.md` (routing differences)
3. `06_Authentication_Authorization.md` (security patterns)
4. `10_Database_Integration_Hibernate.md` (familiar ORM)

**DevOps/SRE**
1. `11_Deployment_Guides.md` (all deployment options)
2. `11_Deployment_Guides.md` (Docker section, Kubernetes section)
3. `11_Deployment_Guides.md` (monitoring & performance)

**Full-Stack Developer**
1. `README.md` (overview)
2. `02_Routing_and_Endpoints.md` (backend routing)
3. `06_Authentication_Authorization.md` (security)
4. `10_Database_Integration_Hibernate.md` (database)
5. `12_Tutorials_Overview.md` (frontend integration tutorials)

**Security Professional**
1. `06_Authentication_Authorization.md` (auth methods)
2. `09_CORS_Error_Handling.md` (CORS & errors)
3. `12_Tutorials_Overview.md` (mTLS, Sureness tutorials)

**API Developer**
1. `02_Routing_and_Endpoints.md` (endpoint design)
2. `08_OpenAPI_Swagger_Documentation.md` (API documentation)
3. `07_Testing_Guide.md` (testing APIs)

## Version-Specific Information

**Javalin 7.x (Current)**
- Primary focus of this documentation
- See `05_Migration_Guide_v6_to_v7.md` for changes from v6
- Java 17+ required
- Jetty 12+ required

**Upgrading from Earlier Versions**
- v6 → v7: `05_Migration_Guide_v6_to_v7.md`
- v5 → v6: Referenced in `05_Migration_Guide_v6_to_v7.md`
- Archived docs: See `sources.md` for archive links

## Depth Levels

**Shallow (5-10 min read)**
- `README.md`
- `01_Official_Documentation_Overview.md`
- Specific sections from other files

**Intermediate (30-45 min read)**
- Single files: `02_Routing_and_Endpoints.md`, `03_WebSocket_SSE_Async.md`, `04_Plugin_System_Architecture.md`
- Topic combinations: routing + testing, auth + CORS, etc.

**Deep (1-2 hour read)**
- `05_Migration_Guide_v6_to_v7.md` (if upgrading)
- `06_Authentication_Authorization.md`, `08_OpenAPI_Swagger_Documentation.md`, `10_Database_Integration_Hibernate.md`
- `11_Deployment_Guides.md` (multiple deployment options)

**Comprehensive (4+ hours)**
- Read entire collection
- Study code examples
- Follow learning paths in `README.md`
- Reference tutorials in `12_Tutorials_Overview.md`

## File Relationships

```
README.md (START)
    ↓
01_Official_Documentation_Overview.md (Framework intro)
    ├→ 02_Routing_and_Endpoints.md (Core feature)
    │   └→ 07_Testing_Guide.md (How to test)
    ├→ 03_WebSocket_SSE_Async.md (Real-time)
    ├→ 04_Plugin_System_Architecture.md (Extensions)
    │   └→ 08_OpenAPI_Swagger_Documentation.md (Documentation plugin)
    ├→ 06_Authentication_Authorization.md (Security)
    ├→ 10_Database_Integration_Hibernate.md (Data layer)
    └→ 09_CORS_Error_Handling.md (Common issues)

05_Migration_Guide_v6_to_v7.md (Upgrade path)
11_Deployment_Guides.md (Production)
12_Tutorials_Overview.md (External resources)
sources.md (Source attribution)
```

## Frequently Asked Section Locations

| Question | File | Section |
|----------|------|---------|
| What is Javalin? | `01` | Overview |
| How do I get started? | `README.md` | Quick Start |
| Where's the API reference? | `02` | All sections |
| How do I upgrade? | `05` | **ENTIRE FILE** |
| How do I add security? | `06` | All sections |
| How do I test? | `07` | All sections |
| How do I document? | `08` | All sections |
| How do I handle errors? | `09` | Error Handlers section |
| How do I use a database? | `10` | All sections |
| How do I deploy? | `11` | All sections |
| Where are tutorials? | `12` | All sections |
| Where are sources? | `sources.md` | All sections |

---

**Total Coverage**: 14 comprehensive files covering all aspects of Javalin framework development and deployment.

**Recommendation**: Start with `README.md`, then navigate to topic-specific files as needed using this index.
