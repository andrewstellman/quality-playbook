# Architecture Overview

Apache Spark is a unified analytics engine for large-scale data processing. It exposes high-level APIs in Scala, Java, Python, and R (deprecated), and runs the same physical execution engine underneath each of them. A Spark application is composed of a single *driver* process and a fleet of *executor* processes that the driver coordinates through a *cluster manager*.

## Process model

Every Spark application centers on a `SparkContext` (and, in the Dataset API, a `SparkSession` that wraps it). The `SparkContext` is created in the user's `main` function inside the driver program and represents the connection to the cluster. The driver:

- holds the application's user code, broadcast variable values, and accumulator state
- builds the logical computation graph (RDDs, DataFrames, or streaming queries)
- decomposes that graph into stages and tasks
- tracks task state and listens for status from executors

Executors are JVM processes launched on worker nodes for the lifetime of one application. They:

- run tasks sent by the driver
- cache RDD blocks and intermediate shuffle output in memory or on disk
- report metrics and heartbeats back to the driver

Each application has its own isolated set of executors. Two Spark applications cannot share RDDs or DataFrames in memory; data shared across applications must be written to external storage. This isolation is structural — different applications run in different JVMs, each scheduled by its own driver.

## Cluster managers

`SparkContext` connects to one of several cluster managers, which acquire executor processes on its behalf:

- **Standalone**: a simple cluster manager bundled with Spark, with its own master (`spark.deploy.master.Master`) and worker (`spark.deploy.worker.Worker`) processes.
- **YARN**: Hadoop's resource manager. Spark requests YARN containers and launches executors inside them.
- **Kubernetes**: Spark submits the driver and executors as pods through the Kubernetes API.
- **Local**: a single-JVM mode used for development and testing (`local`, `local[N]`, `local[*]`).

Spark is agnostic to the cluster manager: as long as executors can be acquired and can talk to the driver, the rest of the system behaves identically. The cluster manager is selected by the `--master` flag of `spark-submit` (or `setMaster` on `SparkConf`).

## Communication

Communication between driver and executors uses Spark's RPC layer (`org.apache.spark.rpc`), which is built on Netty. Endpoints are addressable by `RpcEndpointRef`s; messages are serialized with either Java serialization or Kryo, controlled by configuration. The driver listens on a stable port and the executors connect outward to it. Long-running connections carry heartbeats, task launch messages, status updates, and shuffle metadata.

The driver also exposes a web UI (default port 4040) that surfaces stages, tasks, executors, storage, and SQL query plans for the running application.

## Submission flow

Applications are submitted through `bin/spark-submit`, which sets up the classpath and JVM and invokes the user's main class. Two deploy modes determine where the driver runs: **client mode** (driver runs in the submitting process — useful for shells and notebooks) and **cluster mode** (the cluster manager places the driver on a worker node). The driver then requests executors from the cluster manager, sized by `spark.executor.instances`, `spark.executor.memory`, and `spark.executor.cores`. Dynamic allocation can add or remove executors at runtime based on pending workload.

## Job, stage, task vocabulary

Spark uses a layered vocabulary that recurs across logs, UI, and APIs:

- **Job**: a parallel computation kicked off by an *action* (`collect`, `save`, `count`, etc.).
- **Stage**: a set of tasks within a job that can run together because they share narrow dependencies. Stage boundaries are introduced by shuffles.
- **Task**: a single unit of work sent to one executor — it processes one partition of an RDD.

A `DataFrame` query goes through analysis, optimization, and physical planning before reaching this RDD level; a structured streaming query does the same per micro-batch. The RDD/stage/task model is the substrate on top of which the higher-level APIs are built.

## Modules at a glance

The repository is organized so each major subsystem lives in its own Maven module: `core/` (RDD model, scheduler, storage, shuffle, RPC), `sql/api`/`sql/catalyst`/`sql/core`/`sql/hive`/`sql/hive-thriftserver` (DataFrame/Dataset API, analyzer, optimizer, execution engine), `sql/connect/` (Spark Connect server), `streaming/` (DStream-based streaming), `mllib/` and `mllib-local/` (machine learning), `graphx/` (graph processing), `python/` (PySpark), `R/` (SparkR, deprecated), `connector/` (Avro, Kafka, Kinesis, Protobuf data sources), `resource-managers/yarn` and `resource-managers/kubernetes`, `launcher/` (programmatic launcher), `common/` (network, sketch, kvstore, unsafe), and `docs/`.
