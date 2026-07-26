# Backend Core — packages/backend-core

## Overview

`packages/backend-core` is the foundation library shared between `packages/server` and `packages/worker`. It provides: CouchDB access helpers, Redis client management, object storage, the authentication middleware pipeline, event publishing, distributed locks, tenant context management, caching, and queue infrastructure. Neither the server nor the worker should duplicate these concerns — they delegate to `backend-core`.

## Module Map

```
src/
  auth/          — passport strategy registration, auth exports
  blacklist/     — URL blacklist for outbound REST calls
  cache/         — user cache, workspace metadata cache, invite/password-reset tokens,
                   writethrough cache, doc-writethrough queue
  configs/       — config document read with in-memory TTL caching
  constants/     — DB prefix constants, ViewName enum, StaticDatabases
  context/       — async-local-storage request context (tenant, workspace, identity)
  db/            — CouchDB wrapper (nano), Lucene/Mango query builders, Replication
  docIds/        — ID generation and parsing helpers
  environment.ts — shared environment variable declarations
  errors/        — BudibaseError base class, error serialisation
  events/        — analytics event publishing, activity log queue
  features/      — feature flag resolution
  logging/       — structured logging, DataDog APM integration
  middleware/    — Koa middleware: auth, tenancy, CSRF, error handling, CSP, rate limiting
  objectStore/   — S3-compatible object storage (via AWS SDK v3)
  platform/      — platform-level CouchDB documents
  queue/         — BudibaseQueue (Bull wrapper), InMemoryQueue, job constants
  redis/         — Redis client initialisation, distributed locking (Redlock)
  security/      — permissions, roles, session management, encryption, secrets
  sql/           — Knex-based SQL builder (Sql class), SqlTable schema builder
  tenancy/       — tenant ID resolution and doInTenant helper
  timers/        — interval and timeout helpers
  users/         — UserDB (user CRUD backed by global DB)
  utils/         — cookie helpers, JWT helpers, newid, Duration
  warnings/      — API warning headers
```

## Context System

`packages/backend-core/src/context/` implements a request-scoped context using Node.js `AsyncLocalStorage`. The `Context` class stores:

| Key | Value |
|-----|-------|
| `tenantId` | The active tenant ID |
| `workspaceId` | The active workspace/app ID |
| `identity` | The authenticated user or service identity |
| `license` | The cached licence object |
| `snippets` | App-level code snippets (used by the JS runner) |
| `vm` | Reused `IsolatedVM` instance for the current request |
| `cleanup` | Array of cleanup callbacks run at request end |

Helper functions expose the context without callers needing to interact with `AsyncLocalStorage` directly:

```ts
getTenantId(): string
getWorkspaceId(): string | undefined
getWorkspaceDB(): Database
getGlobalDB(): Database
getCurrentIdentity(): IdentityContext | undefined
doInWorkspace(workspaceId, fn)    // run fn with workspace context set
doInTenant(tenantId, fn)          // run fn with tenant context set
```

Multi-workspace operations (e.g., the SQS sync) iterate workspace IDs and call `doInWorkspace` for each.

## CouchDB Layer

`src/db/` wraps the `nano` CouchDB driver behind a `Database` interface. The wrapper:

- Resolves the database name from the current context (tenant + workspace).
- Provides `allDocs`, `get`, `put`, `remove`, `bulk`, `query` (Mango) methods.
- Adds `tryGet` (returns `undefined` on 404 rather than throwing).
- Supports view queries via the `queryGlobalView` and `queryView` helpers.

The `Replication` class manages CouchDB replication jobs between dev and production workspace databases during app publish/revert.

Design documents (CouchDB views) are managed by `src/db/searchIndexes.ts` and `src/sql/designDoc.ts`. The `searchIndexes` module creates the standard views on first use; `designDoc` manages the SQS mirror's design document.

## Object Store

`src/objectStore/objectStore.ts` wraps the AWS SDK v3 `S3` client to provide an S3-compatible object store interface (works with MinIO for self-hosted deployments and AWS S3 for cloud deployments):

```ts
upload({ bucket, filename, type, body, ttl? }): Promise<{ url: string }>
getReadStream(bucket, filename): Promise<Readable>
deleteFile(bucket, filename): Promise<void>
deleteFiles(bucket, filenames[]): Promise<void>
listFiles(bucket, prefix): Promise<string[]>
copyFile(bucket, src, dest): Promise<void>
getSignedUrl(bucket, filename, expiry): Promise<string>
```

Bucket names are defined in `src/objectStore/buckets/` for: apps, attachments, templates, global (logos, email assets), backups, plugins, tmp. TTL-enabled buckets use S3 lifecycle rules via `bucketTTLConfig`. The temporary directory (`budibaseTempDir`) is used for file processing before upload.

CloudFront URL signing for CDN-served attachments is handled in `src/objectStore/cloudfront.ts`.

## Queue Infrastructure

`src/queue/queue.ts` defines `BudibaseQueue<T>`, a typed wrapper around the Bull queue library:

```ts
class BudibaseQueue<T> {
  constructor(name: JobQueue, opts?: BudibaseQueueOptions)
  process(concurrency: number | ProcessFn, fn?: ProcessFn): Promise<void>
  add(data: T, opts?: JobOptions): Promise<Job<T>>
  getBullQueue(): Queue
}
```

In test environments, `BudibaseQueue` is replaced by `InMemoryQueue`, which implements the same interface but processes jobs synchronously without Redis. This is controlled by the `isTest()` check in `environment.ts`.

Defined queues (`src/queue/constants.ts`):

| Name | Purpose |
|------|---------|
| `AUTOMATION` | Automation job processing |
| `APP_BACKUP` | Application backup jobs |
| `ACTIVITY_LOG` | Async activity log writes |
| `SYSTEM_EVENT_QUEUE` | Platform event fan-out |
| `APP_MIGRATION` | Per-app schema migration jobs |
| `DOC_WRITETHROUGH_QUEUE` | Deferred CouchDB writes |
| `DEV_REVERT_PROCESSOR` | Revert dev workspace to last published state |
| `BATCH_USER_SYNC_PROCESSOR` | Batch sync app user metadata |
| `RAG_INGESTION` | Knowledge-base file ingestion |
| `AGENT_LOG_INDEXING` | AI agent log indexing |

Queue lock duration is 5 minutes; lock renewal interval is 30 seconds. Completed and failed jobs are cleaned up every 60 seconds.

## SQL Builder

`src/sql/sql.ts` exports the `Sql` class, which translates `QueryJson` / `EnrichedQueryJson` into parameterised SQL via Knex. Key design decisions:

- All SQL dialects (PostgreSQL, MySQL, SQL Server, Oracle, Snowflake) go through the same `Sql` builder; dialect-specific Knex clients are passed in by the integration.
- Relationship joins are expressed as sub-queries (to avoid `CROSS JOIN` fan-out on many-to-many relationships).
- Row and relationship row count limits (`SQL_MAX_ROWS`, `SQL_MAX_RELATED_ROWS`) are enforced as Knex `limit()` calls.
- Aggregation (`COUNT`, `SUM`, `AVG`, `MIN`, `MAX`) is translated to `GROUP BY` queries with a mandatory `COUNT_FIELD_NAME` column.

## Encryption and Secrets

`src/security/encryption.ts` provides AES-256-CBC encryption/decryption for sensitive config values stored in CouchDB (API keys, OAuth secrets). The encryption key is derived from the `API_ENCRYPTION_KEY` environment variable. `src/security/secrets.ts` provides `stringContainsSecret`, which scans error payloads before they are returned in HTTP responses.

## Distributed Locking

`src/redis/redlockImpl.ts` wraps [Redlock](https://github.com/mike-nichols/redlock-node) to provide distributed mutual-exclusion locks backed by Redis. Used by the builder to prevent concurrent edits to the same app (`clearLock`, `updateLock` in `packages/server/src/utilities/redis.ts`).
