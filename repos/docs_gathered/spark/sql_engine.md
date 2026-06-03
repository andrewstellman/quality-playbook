# SQL Engine

Spark SQL is the relational engine that powers DataFrames, Datasets, and SQL queries. It is layered as five Maven modules under `sql/`:

- `sql/api` — public types (`DataType`, `Row`, error classes) shared between the JVM engine and the Spark Connect client.
- `sql/catalyst` — implementation-agnostic framework for trees of relational operators and expressions, plus the analyzer and optimizer.
- `sql/core` — physical execution engine that translates logical plans into Spark RDDs, plus the Dataset/DataFrame API and built-in file/JDBC sources.
- `sql/hive` — Hive metastore integration, Hive UDF/UDAF/UDTF wrappers, and Hive SerDe support.
- `sql/hive-thriftserver` — the `bin/spark-sql` CLI and a HiveServer2-compatible JDBC/ODBC server.

## Entry points

`SparkSession` (`org.apache.spark.sql.SparkSession`) is the top-level entry point. It wraps a `SparkContext` and adds the session-level `SQLConf`, `Catalog`, function registry, and experimental methods slot. Multiple `SparkSession`s can coexist on the same `SparkContext`, each with its own `SessionState`. The user-facing surface includes `SparkSession.read` (a `DataFrameReader` for files/JDBC/tables/`DataSource` plugins), `SparkSession.sql(text)` (parse-analyze-optimize-execute a SQL statement), `Dataset[T]` (a strongly-typed view over a query plan — `DataFrame` is `Dataset[Row]`), and `Dataset.write` (a `DataFrameWriter` for persisting to files or tables).

## Catalyst trees

`TreeNode[T]` (in `sql/catalyst/.../trees/TreeNode.scala`) is the immutable tree base class shared by expressions and plans. Every node has a list of children of the same shape and a set of pattern-matching helpers (`transformDown`, `transformUp`, `transformAllExpressions`, etc.) that the rule-based optimizer relies on.

Two parallel hierarchies sit on top of `TreeNode`:

- `Expression` — scalar computations over rows (`Literal`, `Attribute`, `Add`, `If`, `Cast`, aggregate functions, user-defined functions, ...).
- `QueryPlan` — relational operators. Splits into `LogicalPlan` (in `catalyst.plans.logical`) for unresolved/analyzed/optimized plans and `SparkPlan` (in `sql.execution`) for physical plans.

## Analyzer

`Analyzer` (`sql/catalyst/.../analysis/Analyzer.scala`) takes a parsed but unresolved `LogicalPlan` and applies a fixed-point set of rule batches that resolve relations, attributes, functions, aliases, and type coercions. Output is an analyzed `LogicalPlan` where every reference is bound to a concrete schema. `AnalysisException` is the unified error for any failure during this phase, with structured error classes for stable downstream handling.

## Optimizer

`Optimizer` is another fixed-point rule engine. Its batches include predicate pushdown, projection pruning, constant folding, boolean simplification, join reordering, decorrelation of correlated subqueries, and many more. Like the analyzer it is open for extension via `SparkSessionExtensions.injectOptimizerRule`.

## Physical planning and execution

`SparkPlanner` converts a logical plan into a `SparkPlan` by applying strategies that map logical operators to physical implementations. `QueryExecution` orchestrates the phases: analyzed → optimized → sparkPlan → executedPlan. Adaptive Query Execution (AQE) wraps the executed plan with `AdaptiveSparkPlanExec`, which re-plans subtrees at runtime as stages complete.

`SparkPlan` extends `QueryPlan[SparkPlan]` and ultimately exposes `doExecute()` that returns an `RDD[InternalRow]`. Whole-stage code generation fuses a chain of physical operators into a single generated Java class that processes a partition in a tight loop, avoiding per-row virtual dispatch.

## Connectors and DataSource APIs

Two extension surfaces let third parties add storage formats. **DataSource V1** uses the older `RelationProvider` / `SchemaRelationProvider` interfaces and still backs Spark's built-in JSON, JDBC, and text sources. **DataSource V2**, in `org.apache.spark.sql.connector`, defines a richer surface where tables expose `SupportsRead`, `SupportsWrite`, `SupportsRowLevelOperations`, etc., with first-class support for partitioning, transactional writes, streaming reads, and pushdown of filters/aggregates. The bundled `connector/` modules (Avro, Kafka, Kinesis, Protobuf) plug into these APIs.

## Catalogs

`CatalogManager` lets a session see multiple catalogs simultaneously, each implementing the `CatalogPlugin` interface. The default `session_catalog` wraps the Hive metastore (or an in-memory store). Other catalogs can expose Iceberg, Delta, or arbitrary external systems. `USE catalog.database` switches the current namespace.

## SQL parser

`SqlBaseParser` is generated from an ANTLR4 grammar in `sql/api/src/main/antlr4/`. The parser produces an unresolved logical plan or expression tree. The grammar supports Spark SQL's full DDL/DML surface, including CTAS, MERGE INTO, lateral subqueries, table-valued functions, and PIVOT/UNPIVOT.

## SQL configuration

`SQLConf` exposes session-scoped SQL knobs (separate from the application-level `SparkConf`). Examples include `spark.sql.shuffle.partitions`, `spark.sql.adaptive.enabled`, `spark.sql.autoBroadcastJoinThreshold`, and `spark.sql.session.timeZone`. These can be set on `SparkSession.conf` or via `SET` statements in SQL.

## Hive integration

When Spark is built with `-Phive`, `HiveSessionStateBuilder` substitutes a Hive-aware session state. `HiveExternalCatalog` talks to a Hive metastore (Derby, MySQL, PostgreSQL) for table definitions. `HiveClient` isolates the Hive jars in a separate classloader so multiple Hive versions can coexist with Spark at runtime.

## Thrift server

`sql/hive-thriftserver` boots a HiveServer2-compatible Thrift service inside a Spark application. JDBC and ODBC clients connect, submit SQL, and receive results streamed back as row batches. The same `SparkSession` is shared across client sessions, with per-session `SessionState` isolation.
