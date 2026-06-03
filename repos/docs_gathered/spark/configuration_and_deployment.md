# Configuration and Deployment

A Spark application is configured at three levels: code-level `SparkConf` properties, per-machine environment variables, and `log4j2.properties` for logging. Deployment combines this configuration with a cluster manager and an entry-point script (`spark-submit`, `spark-shell`, `pyspark`, `spark-sql`).

## SparkConf

`org.apache.spark.SparkConf` is a key-value store of string-string pairs. The user typically creates one before constructing a `SparkContext` or `SparkSession`:

```scala
val conf = new SparkConf()
  .setMaster("local[2]")
  .setAppName("Example")
  .set("spark.executor.memory", "2g")
val sc = new SparkContext(conf)
```

After construction, the `SparkConf` is cloned into the running application and its values are frozen. Spark reads the application's master URL, app name, executor configuration, serializer, network ports, plugins, and security settings from this object. Defaults are also pulled in from any Java system properties prefixed `spark.`, and from the file referenced by `--properties-file` (default: `conf/spark-defaults.conf`).

Properties that specify time durations accept suffixes (`25ms`, `5s`, `10m`, `3h`, `5d`). Byte sizes accept binary suffixes (`1k`, `1m`, `1g`, `1t`, `1p`).

## SQL configuration

`org.apache.spark.sql.internal.SQLConf` holds session-scoped SQL knobs separate from the application-level `SparkConf`. Examples include `spark.sql.shuffle.partitions`, `spark.sql.autoBroadcastJoinThreshold`, `spark.sql.adaptive.enabled`, and `spark.sql.session.timeZone`. SQL conf values can be set on `SparkSession.conf` or with `SET key=value` in SQL, and are scoped per `SparkSession`.

## Environment variables and logging

`conf/spark-env.sh` (sourced by the launcher scripts on each node) sets per-machine values: `JAVA_HOME`, `SPARK_HOME`, `PYSPARK_PYTHON`, `PYSPARK_DRIVER_PYTHON`, `SPARK_LOCAL_IP`, `SPARK_PUBLIC_DNS`, `SPARK_WORKER_CORES`, `SPARK_WORKER_MEMORY`, `SPARK_DAEMON_MEMORY`, `SPARK_HISTORY_OPTS`, and `HADOOP_CONF_DIR`/`YARN_CONF_DIR` for Hadoop/YARN integration. Logging uses Log4j 2: copy `conf/log4j2.properties.template` to `conf/log4j2.properties` and adjust. Spark's internal logging goes through `org.apache.spark.internal.Logging`, which wraps Log4j and adds MDC keys for stage id, task attempt, and similar fields.

## Resource configuration

Executors and the driver are sized by:

- `spark.driver.cores` / `spark.driver.memory` / `spark.driver.memoryOverhead`
- `spark.executor.cores` / `spark.executor.memory` / `spark.executor.memoryOverhead`
- `spark.executor.instances` for static allocation, or the `spark.dynamicAllocation.*` family for elastic allocation
- `spark.task.cpus` for the CPU resource a task asks of an executor

Additional resources (GPUs, FPGAs) are requested with `spark.executor.resource.gpu.amount`, `spark.executor.resource.gpu.discoveryScript`, and similar.

## spark-submit

`bin/spark-submit` is the canonical way to launch an application. The launcher script bootstraps a JVM via `org.apache.spark.launcher.Main`, which:

1. Parses arguments (`--master`, `--deploy-mode`, `--class`, `--conf`, `--jars`, `--files`, `--py-files`, `--archives`, `--name`, ...).
2. Constructs the final command line: classpath, `-D` system properties from `--conf` flags, the main class, and the user's arguments.
3. Either execs the JVM directly (client mode) or hands off to the cluster manager (cluster mode).

The companion library in `launcher/` exposes `SparkLauncher` for embedding the same logic into other JVMs.

## Deploy paths

- **Standalone** (`core/src/main/scala/org/apache/spark/deploy/`): `Master` accepts driver and worker registrations and schedules applications (with optional ZooKeeper-based HA); `Worker` registers with the master and launches `ExecutorRunner`s on request; a REST submission server (port 6066) accepts cluster-mode submissions over HTTP. Operational scripts: `sbin/start-master.sh`, `sbin/start-worker.sh`, `sbin/start-history-server.sh`.
- **YARN** (`resource-managers/yarn/`): `Client` packages the application and submits an `ApplicationMaster` to YARN, which then requests executor containers from the YARN ResourceManager. Configuration lives in `yarn-site.xml`; `spark.yarn.*` tunes queue, principal, keytab, and container launch.
- **Kubernetes** (`resource-managers/kubernetes/`): the driver runs as a pod and creates executor pods via the Kubernetes API. `KubernetesClusterSchedulerBackend` polls the API for pod events. Pod templates can be supplied via `spark.kubernetes.driver.podTemplateFile` and `spark.kubernetes.executor.podTemplateFile`.

## Distribution

`./build/mvn -DskipTests clean package` builds Spark from source. `dev/make-distribution.sh` produces a tarball with `bin/`, `sbin/`, `conf/`, `jars/`, and the optional `python/` layout. PyPI distributions (`pyspark`) come from `python/setup.py`; the R distribution is built via `R/install-dev.sh`.

## Plugins and extensions

Several extension points let operators bolt extra behavior onto a running application:

- `spark.plugins` — comma-separated list of classes implementing `org.apache.spark.api.plugin.SparkPlugin`. Each plugin has a driver-side and executor-side component; both are notified of lifecycle events and can register their own metrics sources.
- `spark.extraListeners` — classes implementing `SparkListener`, registered on the listener bus at startup.
- `SparkSessionExtensions` — programmatic API for adding parser, analyzer, optimizer, and planner rules to the SQL engine.
- `spark.sql.extensions` — comma-separated classes implementing `Function1[SparkSessionExtensions, Unit]` that are invoked at session build time.

## Web UI and history server

Every running application exposes a UI on port 4040 (the next free port if multiple drivers share a host). When `spark.eventLog.enabled=true`, the application logs scheduler events to a directory; the history server (`sbin/start-history-server.sh`) replays those logs to reconstruct UIs for completed applications. The history server's behavior is governed by `spark.history.*` properties: log directory, update interval, cache size, and rolling-log compaction settings.
