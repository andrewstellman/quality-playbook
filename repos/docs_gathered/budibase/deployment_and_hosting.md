# Deployment and Hosting — hosting/, lerna.json, nx.json, packages/cli

## Overview

Budibase is packaged as a Docker Compose stack for self-hosted deployments and delivered as a managed cloud service (Budibase Cloud). The monorepo uses Lerna (version 3.34.6) with Yarn workspaces for package management and Nx for build-task orchestration.

---

## Docker Compose Stack

The reference compose file is `hosting/docker-compose.yaml`. It declares the following services:

| Service | Image | Port | Role |
|---------|-------|------|------|
| `app-service` | `budibase/apps` | 4002 (internal) | Main Koa app server (packages/server) |
| `worker-service` | `budibase/worker` | 4003 (internal) | Global worker (packages/worker) |
| `proxy-service` | `budibase/proxy` | 80 / 443 | Nginx reverse proxy and rate limiter |
| `couchdb-service` | `budibase/database:2.1.0` | 5984 (internal) | Primary document store |
| `minio-service` | `minio/minio` | 9000 (internal) | S3-compatible object storage |
| `redis-service` | `redis` | 6379 (internal) | Queue backend and session store |
| `litellm-service` | `ghcr.io/berriai/litellm:main-v1.81.14-stable` | 4000 (configurable) | LLM proxy gateway |
| `litellm-db` | `postgres:16` | 5432 (internal) | LiteLLM metadata store |

The proxy service applies rate limits:
- Webhook endpoints: `PROXY_RATE_LIMIT_WEBHOOKS_PER_SECOND` (default 10 req/s).
- API endpoints: `PROXY_RATE_LIMIT_API_PER_SECOND` (default 50 req/s).

### Persistent Volumes

| Volume | Mounted by |
|--------|-----------|
| `couchdb3_data` | `couchdb-service:/data` |
| `minio_data` | `minio-service` |
| `redis_data` | `redis-service:/data` |
| `litellm_data` | `litellm-db:/var/lib/postgresql/data` |

Plugins can be mounted into the app service by uncommenting the `volumes:` block and setting `PLUGINS_DIR`.

### Key Environment Variables (app-service)

```
SELF_HOSTED=1
COUCH_DB_URL=http://<user>:<pass>@couchdb-service:5984
WORKER_URL=http://worker-service:4003
MINIO_URL=http://minio-service:9000
REDIS_URL=redis-service:6379
INTERNAL_API_KEY=<shared secret>
JWT_SECRET=<signing secret>
API_ENCRYPTION_KEY=<AES key>
LITELLM_URL=http://litellm-service:4000
LITELLM_MASTER_KEY=<litellm key>
BB_ADMIN_USER_EMAIL=<initial admin email>
BB_ADMIN_USER_PASSWORD=<initial admin password>
ENABLE_ANALYTICS=true
```

On first boot with `SELF_HOSTED=1` and `BB_ADMIN_USER_EMAIL` / `BB_ADMIN_USER_PASSWORD` set, the server automatically creates the initial admin user if one does not already exist.

---

## Monorepo Build System

### Lerna

`lerna.json` configures Lerna to use Yarn as the npm client with a concurrency of 20 for parallel package builds. The `version` field is `3.34.6` — the current monorepo version string.

### Nx

`nx.json` provides task caching and dependency-graph analysis. Nx understands the import graph between packages and avoids rebuilding packages whose sources and dependencies have not changed. TypeScript builds (`tsc`) and Vite/Rollup bundle builds are the primary tasks in the Nx graph.

### Package build order (inferred from dependencies)

```
packages/types
  → packages/shared-core
  → packages/string-templates
  → packages/backend-core
  → packages/bbui
  → packages/frontend-core
  → packages/sdk
  → packages/server   (depends on backend-core, shared-core, string-templates, types)
  → packages/worker   (depends on backend-core, shared-core, types)
  → packages/builder  (depends on bbui, frontend-core, shared-core, string-templates, types)
  → packages/client   (depends on frontend-core, shared-core, string-templates, types, bbui)
```

### TypeScript Configuration

Root `tsconfig.build.json` declares path aliases for monorepo packages so that `import { ... } from "@budibase/types"` resolves to the local `packages/types/src/index.ts` during development. The compiled output in `dist/` is used by production Docker builds.

---

## Kubernetes and Cloud

The `charts/` directory contains Helm charts for Kubernetes deployments. The Helm chart mirrors the Docker Compose services but adds Kubernetes-native features: horizontal pod autoscaling (HPA) for the app-service and worker-service, ConfigMap management for environment variables, and persistent volume claims (PVC) for CouchDB and MinIO.

### Cluster Mode

Setting `CLUSTER_MODE=1` in the app-service environment enables Node.js cluster mode, forking one process per CPU core. The Socket.IO adapter automatically switches to Redis pub/sub (via `@socket.io/redis-adapter`) when cluster mode is active, so WebSocket messages are broadcast across all worker processes.

### Multi-Tenancy in Cloud

Budibase Cloud uses `MULTI_TENANCY=1`. Each tenant is isolated by:

- A dedicated global CouchDB database (`<tenantId>_global-db`).
- Separate workspace CouchDB databases (`<appId>`).
- Object-store prefixes derived from the tenant ID.
- Redis key namespacing by tenant ID.

Tenant ID is resolved from the JWT on each request and set in `AsyncLocalStorage` by `buildTenancyMiddleware`.

---

## CLI (`packages/cli`)

The `packages/cli` package provides the `budi` command-line tool for local development. Its capabilities include:

- Scaffold a new plugin project (component, datasource, or automation step).
- Install a plugin bundle into a local Budibase instance.
- Start the development stack.
- Manage environment variables for local `.env` files.

The CLI is not a runtime dependency of the server; it is distributed separately for developer use.
