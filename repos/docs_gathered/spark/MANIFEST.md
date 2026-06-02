# Manifest — Apache Spark reference corpus

This corpus describes Apache Spark at a single point in its history, oriented toward a developer joining the project who wants to understand the major subsystems.

- `architecture_overview.md` — Driver/executor process model, cluster managers, submission flow, repository module layout, and the job/stage/task vocabulary.
- `core_rdd_model.md` — The Resilient Distributed Dataset abstraction: partitions, dependencies, transformations vs. actions, persistence, shared variables, and checkpointing.
- `scheduler.md` — The two-layer scheduler: `DAGScheduler` for stage planning, `TaskScheduler` and `SchedulerBackend` for task dispatch, listener bus, and resource profiles.
- `sql_engine.md` — Spark SQL: module layout, `SparkSession` entry points, the Catalyst tree framework, analyzer and optimizer, physical planning, data source APIs, catalogs, and Hive integration.
- `structured_streaming.md` — Structured Streaming: programming model, micro-batch and continuous execution engines, triggers, checkpointing, state stores, watermarks, and source/sink interfaces.
- `spark_connect.md` — The decoupled client-server architecture: gRPC protocol, server-side request handling, client libraries, connection strings, and how it differs from the classic API.
- `mllib_overview.md` — MLlib's DataFrame-based pipeline API: `Transformer`/`Estimator`/`Pipeline`, the `Params` system, algorithm families, linear algebra, and model persistence.
- `configuration_and_deployment.md` — `SparkConf`, `SQLConf`, environment variables, logging, `spark-submit`, the standalone/YARN/Kubernetes deploy paths, extension points, and the history server.
