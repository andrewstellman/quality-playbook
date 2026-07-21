# Ech0 Data Migration Subsystem

## Overview

The migration subsystem provides a structured ETL (Extract, Transform, Validate, Load) pipeline for importing historical data from external sources into Ech0. The initial use case is importing posts from earlier Ech0 versions (v3 snapshot exports) and compatible microblog platforms, but the pipeline is designed as a general-purpose framework extensible to additional sources.

## Pipeline Architecture

The pipeline is defined in `internal/migrator/pipeline.go` and composed of four interface stages:

```
Extractor → Transformer → Validator → Loader
```

All four interfaces are declared in `internal/migrator/spec/` and re-exported from `internal/migrator/contracts.go`:

```go
type Extractor interface {
    Extract(ctx context.Context, req ExtractRequest) (ExtractResult, error)
}

type Transformer interface {
    Transform(ctx context.Context, raw RawRecord) (CanonicalRecord, error)
}

type Validator interface {
    Validate(ctx context.Context, record CanonicalRecord) error
}

type Loader interface {
    Load(ctx context.Context, records []CanonicalRecord) (LoadResult, error)
}
```

The `Runner` struct composes all four stages and runs them in sequence for each batch:

```go
type Runner struct {
    extractor   Extractor
    transformer Transformer
    validator   Validator
    loader      Loader
}
```

## Data Types

### ExtractRequest

Passed to `Extractor.Extract` on each batch run:

```go
type ExtractRequest struct {
    // checkpoint from previous batch for resumable extraction
}
```

### ExtractResult

Returned by the extractor:

```go
type ExtractResult struct {
    Records        []RawRecord
    TotalHint      int64
    NextCheckpoint int64
    HasMore        bool
}
```

`HasMore` drives the batch loop: the caller continues submitting batches until `HasMore` is false. `NextCheckpoint` is an opaque cursor (typically a record ID or offset) used in the subsequent `ExtractRequest` for resumable imports.

### RawRecord and CanonicalRecord

`RawRecord` carries source-format data with a `SourceID` string for failure tracking. `CanonicalRecord` is the normalized form after transformation.

### LoadResult

```go
type LoadResult struct {
    Loaded int64
    Failed []FailedItem
}
```

### FailedItem

```go
type FailedItem struct {
    SourceID string
    Reason   string
}
```

## Batch Execution

`Runner.RunBatch` executes one batch:

1. `extractor.Extract(ctx, req)` — fetches a page of raw records
2. For each `RawRecord`:
   - `transformer.Transform(ctx, raw)` — converts to canonical form; failures append to `failed` slice
   - `validator.Validate(ctx, canonical)` — validates the canonical record; failures append to `failed` slice
3. `loader.Load(ctx, canonicalRecords)` — bulk-inserts valid records; the loader may report its own per-record failures in `LoadResult.Failed`
4. Returns `BatchOutcome` aggregating all failures and pagination state

Transform and validate failures are non-fatal per-record: the batch continues processing remaining records and accumulates all failures in `BatchOutcome.Failed`.

## BatchOutcome

```go
type BatchOutcome struct {
    TotalHint      int64
    NextCheckpoint int64
    HasMore        bool
    Loaded         int64
    Failed         []FailedItem
}
```

## Migration Worker

`internal/migrator/Worker` wraps the runner for background execution. When `ECH0_MIGRATION_WORKER_ENABLED` is `true`, the worker is registered as an `app.Component` and starts processing on application startup. Configuration parameters control concurrency and throughput:

| Parameter | Environment Variable | Default |
|---|---|---|
| Worker enabled | `ECH0_MIGRATION_WORKER_ENABLED` | `false` |
| Max concurrency | `ECH0_MIGRATION_MAX_CONCURRENCY` | `1` |
| Batch size | `ECH0_MIGRATION_BATCH_SIZE` | `100` |
| Rate limit | `ECH0_MIGRATION_RATE_LIMIT_PER_SEC` | `20` |

The rate limit prevents a migration run from monopolizing database I/O and network bandwidth during normal operation.

## Source Adapters

The `internal/migrator/factory.go` file registers source-specific implementations of `SourceMigrator`, which is a composite of Extractor, Transformer, Validator, and Loader for a specific data source. The factory pattern allows adding new sources without modifying the pipeline runner.

```go
type SourceMigrator interface {
    Extractor
    Transformer
    Validator
    Loader
}
```

## Progress Tracking

`MigrateProgress` and `MigrateResult` types carry progress metadata back to the caller:

```go
type MigrateProgress struct {
    Total    int64
    Loaded   int64
    Failed   int64
    Done     bool
}

type MigrateResult struct {
    Loaded int64
    Failed []FailedItem
}
```

The `MigrateRequest` type specifies the source and any source-specific parameters:

```go
type MigrateRequest struct {
    Source string
    // source-specific configuration fields
}
```

## API Surface

Migration is triggered and monitored through the admin API:

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/migration/start` | Start or queue a migration job |
| `GET` | `/api/migration/status` | Check current migration job status |
| `GET` | `/api/migration/result` | Retrieve completed migration result |

Migration jobs are modeled in `internal/model/migration/job.go` with status fields tracking started time, completion time, total records, loaded count, and failure details.

## v3 to v4 Migration

The documented upgrade path from Ech0 v3 to v4 uses the migration subsystem:

1. Export a snapshot from the v3 panel (produces a ZIP archive)
2. Deploy v4 fresh
3. Upload the v3 snapshot through the admin panel under "v3 Migration"
4. The migration pipeline extracts, transforms, and loads the v3 records into the v4 schema

The v3 migration source adapter handles schema differences between versions, including changes to post structure, tag representation, and file path formats.
