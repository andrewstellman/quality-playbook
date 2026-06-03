# Structured Streaming

Structured Streaming is the streaming engine built on top of the SQL execution engine. A streaming query is written with the same DataFrame/Dataset API as a batch query; the engine repeatedly incrementally executes the same logical plan against newly arrived data. It lives primarily in `sql/core/src/main/scala/org/apache/spark/sql/execution/streaming/` with public types under `org.apache.spark.sql.streaming`.

## Programming model

A streaming `DataFrame` is created with `sparkSession.readStream` and a source name (`"kafka"`, `"file"`, `"rate"`, `"socket"`, or any `DataSource V2` streaming source). Operations on the resulting `Dataset[Row]` look the same as batch:

```scala
val lines = spark.readStream.format("kafka")...load()
val counts = lines.groupBy("word").count()
val query  = counts.writeStream
  .outputMode("complete")
  .format("console")
  .start()
```

`start()` registers and launches a `StreamingQuery`. The `StreamingQueryManager` (`sparkSession.streams`) tracks active queries, awaits their termination, and dispatches lifecycle events to registered `StreamingQueryListener`s.

## Output modes, engines, and triggers

A sink defines what `outputMode` it supports: **Append** (only rows finalized since the last batch), **Update** (rows whose aggregation changed), or **Complete** (the full result table every batch).

`StreamExecution` is the abstract base for streaming query execution. Two concrete engines extend it: `MicroBatchExecution` (the default — repeatedly plans and runs a small batch of new data) and `ContinuousExecution` (experimental low-latency engine that keeps long-running tasks pulling without re-planning per batch). Both walk the user's logical plan once, identify streaming sources and sinks, and on each trigger compose an incremental batch plan that the SQL engine plans and runs like an ordinary query.

`Trigger` controls when each batch fires: `ProcessingTime("10 seconds")` for fixed-interval, `Once` / `AvailableNow` for one-shot batches (useful for periodic ETL), and `Continuous("1 second")` for the continuous engine. With no explicit trigger, micro-batches launch as soon as the previous batch finishes.

## Checkpointing

Each streaming query requires a checkpoint location (`option("checkpointLocation", path)`). Spark writes several logs to that directory:

- `offsets/` — per-batch offsets read from each source, written via `OffsetSeqLog` before the batch starts.
- `commits/` — per-batch commit markers via `CommitLog`, written after a batch's sink writes succeed.
- `state/` — per-operator state stores for aggregations, joins, deduplication, and the `[flat]MapGroupsWithState` operators.
- `sources/` — source-specific bookkeeping (e.g., `FileStreamSourceLog` for file sources).

The checkpoint location is the source of truth for replay. On restart, Spark consults `offsets/` to determine which batch to re-run and `commits/` to know whether the sink already received it. This gives the engine exactly-once semantics end-to-end when paired with idempotent or transactional sinks.

## State store

Stateful operators (windowed aggregations, streaming joins, deduplication, arbitrary stateful processing via `mapGroupsWithState` / `flatMapGroupsWithState`, and the newer transformWithState API) store key-value state in a `StateStore` abstraction. Two implementations exist:

- `HDFSBackedStateStoreProvider` — versioned snapshots and deltas written to the checkpoint filesystem.
- `RocksDBStateStoreProvider` — embedded RocksDB instance per partition, with periodic checkpoint uploads.

The store is partitioned the same way as the upstream shuffle. State is keyed by the operator id, partition id, and version; older versions can be loaded for replay.

## Watermarks and event-time

`Dataset.withWatermark("eventTime", "10 minutes")` defines an event-time column and a slack interval. The engine tracks the maximum event time seen and advances the watermark to `max(eventTime) - slack`. State older than the watermark can be discarded; late records past the watermark may be dropped depending on the output mode.

## Source and sink interfaces

A streaming source implements `SparkDataStream` (V2). The micro-batch path uses `MicroBatchStream` with `latestOffset`, `planInputPartitions(start, end)`, and `commit(end)`. The continuous path uses `ContinuousStream`. File-based sources also implement `FileStreamSource` with its own offset log of consumed file paths.

Sinks implement `Table` with `SupportsWrite`. Foreach and ForeachBatch hooks let users supply a sink in code:

- `foreach(ForeachWriter[T])` — per-row callback with open/process/close lifecycle.
- `foreachBatch((df, batchId) => ...)` — receive the per-batch DataFrame and write it however needed (commonly used to write to systems without a native streaming sink).

## Progress and observability

Each query emits `StreamingQueryProgress` records every batch, including input rate, processing rate, watermark, and per-source/sink metrics. `StreamingQueryListener` receives `QueryStartedEvent`, `QueryProgressEvent`, and `QueryTerminatedEvent`. The Spark UI's Structured Streaming tab surfaces the same data graphically.
