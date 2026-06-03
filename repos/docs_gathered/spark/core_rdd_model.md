# Core RDD Model

The Resilient Distributed Dataset (RDD) is the foundational abstraction in Spark. An RDD represents an immutable, partitioned collection of elements that can be operated on in parallel. Every higher-level API in Spark — DataFrames, Datasets, structured streaming, MLlib — ultimately compiles down to RDD operations executed by the same scheduler.

## Five properties

The `RDD` abstract class in `core/src/main/scala/org/apache/spark/rdd/RDD.scala` defines an RDD by five properties:

1. A list of `Partition`s — the units of parallelism.
2. A function `compute(partition, TaskContext)` that produces an iterator of values for a partition.
3. A list of `Dependency`s on parent RDDs.
4. Optionally, a `Partitioner` for key-value RDDs.
5. Optionally, a list of preferred locations for each partition (for data locality).

A custom RDD is created by extending `RDD[T]` and implementing these. The built-in subclasses include `MapPartitionsRDD`, `HadoopRDD`, `NewHadoopRDD`, `ShuffledRDD`, `CoGroupedRDD`, `UnionRDD`, `CartesianRDD`, `JdbcRDD`, `CheckpointRDD`, and more.

## Dependencies and lineage

`Dependency` (in `core/src/main/scala/org/apache/spark/Dependency.scala`) comes in two shapes:

- **Narrow dependencies** (`OneToOneDependency`, `RangeDependency`, `PruneDependency`): each parent partition contributes to one child partition. Spark can pipeline these inside a single stage without shuffling.
- **Shuffle dependencies** (`ShuffleDependency`): output is partitioned by key across the network. These mark stage boundaries.

An RDD plus its chain of dependencies forms a lineage graph. The lineage is what makes RDDs *resilient*: if a partition is lost (executor crash, machine failure) Spark can re-derive it from its parents.

## Transformations and actions

RDD operations split into two categories:

- **Transformations** are lazy. They build a new RDD that records the transformation but don't compute anything. Examples: `map`, `filter`, `flatMap`, `union`, `distinct`, `groupByKey`, `reduceByKey`, `join`, `cogroup`, `sortByKey`, `coalesce`, `repartition`.
- **Actions** trigger computation and return a value to the driver or write to storage. Examples: `count`, `collect`, `take`, `first`, `reduce`, `fold`, `aggregate`, `foreach`, `saveAsTextFile`, `saveAsSequenceFile`, `saveAsObjectFile`.

When the user calls an action, the `SparkContext` submits a job. The DAGScheduler walks the lineage backward from the action's RDD to assemble stages.

## PairRDDFunctions and implicit conversions

RDDs of pairs (`RDD[(K, V)]`) gain a richer surface through implicit conversion to `PairRDDFunctions` and `OrderedRDDFunctions`. These add the group-by-key, reduce-by-key, join, cogroup, and sort-by-key operations that drive most aggregation workloads. The implicits are imported from `org.apache.spark.SparkContext._` in older code or are visible by default in current Scala.

## Persistence and storage levels

`rdd.persist(level)` or `rdd.cache()` tells the scheduler to retain partitions after they're first computed. `StorageLevel` (`core/src/main/scala/org/apache/spark/storage/StorageLevel.scala`) parameterizes where (memory, disk, or both), how (deserialized or serialized), and replication factor. Persisted RDDs are managed by the `BlockManager` on each executor, coordinating with the `BlockManagerMaster` on the driver. Cached partitions can be evicted under memory pressure, in which case Spark recomputes them from lineage on next access.

## Shared variables

Two helpers move data alongside tasks:

- **Broadcast variables** (`org.apache.spark.broadcast.Broadcast`) ship a read-only value to each executor once, rather than once per task. The default `TorrentBroadcast` implementation chunks the value and lets executors fetch chunks from each other peer-to-peer.
- **Accumulators** (`org.apache.spark.util.AccumulatorV2`) provide write-only counters or aggregators that workers can add to and the driver can read. The built-in `LongAccumulator`, `DoubleAccumulator`, and `CollectionAccumulator` cover the common cases; users can subclass `AccumulatorV2` for custom merge semantics.

## Checkpointing

Long lineage chains can become expensive to recompute. `rdd.checkpoint()` marks an RDD to be saved to a reliable filesystem (HDFS, S3, etc.) when its next action runs, replacing its lineage with a `ReliableCheckpointRDD` that reads from the saved files. `rdd.localCheckpoint()` performs the same trick using executor storage instead of a reliable filesystem.

## RDD operation scope and metadata

`RDDOperationScope` annotates RDD creation with the user-facing operation that produced it, which the Spark UI uses to draw the DAG visualization. Lineage tracking, partition counts, and storage information are surfaced through `SparkContext.getRDDStorageInfo`, `SparkContext.getExecutorMemoryStatus`, and the REST API exposed by the driver.

## Language bindings

PySpark and SparkR wrap RDDs through their own thin façades. In PySpark, `pyspark.RDD` serializes Python closures and ships them to a Python worker that the executor spawns; communication uses pickled data over a local socket. The driver-side `JavaRDD` and `JavaPairRDD` provide the Java-friendly API surface for the same Scala types.
