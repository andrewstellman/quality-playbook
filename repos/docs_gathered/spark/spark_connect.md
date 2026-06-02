# Spark Connect

Spark Connect is a decoupled client-server architecture that lets thin clients drive a remote Spark cluster over gRPC, sending unresolved logical plans rather than executing Spark code locally. The server lives under `sql/connect/server/`, common protocol definitions live in `sql/connect/common/`, and language clients live in `python/pyspark/sql/connect/` (Python) and `connector/connect/client/jvm/` (Scala/JVM).

## Motivation

Classic Spark applications run user code inside the same JVM as the driver. The driver builds RDDs/DataFrames and the user can poke at JVM internals through Py4J (in PySpark) or directly (in Scala/Java). That coupling makes it hard to embed Spark in IDEs, notebooks, web servers, or non-JVM languages and complicates upgrade paths (client and server must move together).

Spark Connect separates the two. The client builds query plans and sends them as protobuf messages over gRPC to a Spark Connect server. The server resolves and executes those plans against a `SparkSession`, then streams results back as Apache Arrow record batches. The client never holds a `SparkContext` and cannot manipulate the driver JVM.

## Protocol

The protocol is defined as protobuf in `sql/connect/common/src/main/protobuf/spark/connect/`. The top-level service exposes RPCs for `ExecutePlan` (submit a plan and stream back response batches), `AnalyzePlan` (schema, explain, persist info), `Config` (read/write session configuration), `AddArtifacts` (upload jars, files, Python code), plus `ArtifactStatus`, `Interrupt`, `ReattachExecute`, `ReleaseExecute`, `ReleaseSession`, and `FetchErrorDetails` for lifecycle and recovery.

`Plan` and `Relation` messages mirror the structure of unresolved Catalyst logical plans: `Project`, `Filter`, `Join`, `Aggregate`, `Sort`, `Read` (with format-specific options), `Range`, `LocalRelation`, plus expressions (`Literal`, `UnresolvedAttribute`, `UnresolvedFunction`). Results stream back as repeated `ExecutePlanResponse` messages, with data batches encoded as Apache Arrow IPC.

## Server side

A Spark Connect server is started by setting the configuration `spark.api.mode=connect` or running `start-connect-server.sh`. Server-side request handlers translate protobuf plans into Catalyst logical plans, call the standard analyzer/optimizer/planner pipeline, and run them in a normal `SparkSession`.

Session isolation is per gRPC session: each connected client gets its own `SparkConnectSession` wrapping a `SparkSession`, with its own `SQLConf`, temporary views, and uploaded artifacts. The driver-level `SparkContext` is shared across sessions but never exposed to the client.

`SparkConnectArtifactManager` handles the artifact upload stream: jars are added to the session's class isolation layer, Python files are forwarded to the Python worker bootstrap, and arbitrary files become available through `SparkFiles`.

## Client side

The PySpark client is the most mature. `pyspark.sql.connect.SparkSession.builder.remote("sc://host:15002").getOrCreate()` returns a session that looks just like the classic one but is backed by gRPC. The same is true for `DataFrame`, `Column`, `GroupedData`, `Catalog`, and `streams`. Methods build protobuf relations rather than invoking Catalyst directly.

The Scala/JVM client lives in `connector/connect/client/jvm/`. It provides the same `SparkSession`/`Dataset` surface but builds plans through the protobuf builders. Clients in other languages (Go, Rust, browser-side) can be implemented against the same proto definitions.

## Differences from the classic API

The Spark Connect client cannot call `SparkContext`, cannot read or set static cluster-wide configuration, cannot access RDDs, and cannot use anything that depends on running on the driver JVM. PySpark's `_jdf`, `_jvm`, and other Py4J escape hatches are absent. In return, the client decouples from the server release: a client of one minor version can talk to a server of a different compatible minor version.

## Connection string

`sc://host:port/;param=value;param=value` is the standard connection URL. Recognized parameters include `user_id`, `session_id`, `token` (for bearer auth), and `use_ssl`. The client library parses the URL and configures the gRPC channel accordingly. Channel options (compression, max message size) are exposed for tuning.

## Streaming and structured streaming

The `streams` attribute on a connected `SparkSession` exposes `StreamingQueryManager` semantics through dedicated RPCs (`AddListenerBus`, `RemoveListenerBus`, query status calls). `writeStream.start()` issues an `ExecutePlan` for the streaming query; subsequent management uses the streaming RPC surface.

## Error handling

Server-side errors flow back as `FetchErrorDetails` responses containing structured error class information (`errorClass`, `sqlState`, message parameters, and a stack trace summary). Clients can re-raise them as language-native exceptions while preserving the structured fields, so error-class-based handling is uniform between classic and Connect modes.
