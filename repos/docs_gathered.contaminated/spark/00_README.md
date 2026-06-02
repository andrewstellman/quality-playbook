# Apache Spark — Overview for QPB History Server Audit

## Sources

- Apache Spark project page: https://spark.apache.org/
- Spark monitoring & History Server docs: https://spark.apache.org/docs/latest/monitoring.html
- Spark security guide: https://spark.apache.org/docs/latest/security.html
- Spark GitHub repository: https://github.com/apache/spark
- `JsonProtocol` source (master): https://github.com/apache/spark/blob/master/core/src/main/scala/org/apache/spark/util/JsonProtocol.scala
- `FsHistoryProvider` source (master): https://github.com/apache/spark/blob/master/core/src/main/scala/org/apache/spark/deploy/history/FsHistoryProvider.scala
- "The Internals of Apache Spark" — History Server chapter: https://books.japila.pl/apache-spark-internals/history-server/
- Spark Event Log notes (Luca Canali): https://github.com/LucaCanali/Miscellaneous/blob/master/Spark_Notes/Spark_EventLog.md

## Context

Apache Spark is a large open-source distributed compute engine written primarily in **Scala** (with Java, Python, R, and SQL surface APIs) and running on the **JVM**. The codebase is split into many subprojects: `core`, `sql`, `mllib`, `streaming`, `structured-streaming`, `kubernetes`, `yarn`, etc. **This audit is scoped narrowly to the Spark History Server + event-log serialization surface**; the SQL planner, ML, and streaming engines are explicitly out of scope.

### Scope of this audit

Only the following code path is in scope:

```
event-log file (JSON, one event per line)
        |
        v
ReplayListenerBus              <- Spark History Server
        |
        v
JsonProtocol.sparkEventFromJson(json)
        |
        v
SparkListenerEvent subclass instance
```

The bug class is **insecure [REDACTED]**: a JSON field names a Java class, and the deserializer instantiates that class without checking that it actually belongs to `SparkListenerEvent`'s closed hierarchy.

### The Spark History Server

The **Spark History Server** (SHS) is a long-running HTTP service that reconstructs the Spark Web UI for **completed** applications by replaying their event logs. Live Spark applications expose a UI on port 4040 while running; once the driver exits, that UI disappears. The History Server fills the gap so operators can inspect job/stage/task timelines, executor metrics, SQL plans, and environment info after the fact.

Key characteristics:

- Started via `sbin/start-history-server.sh`.
- Configured by `spark.history.fs.logDirectory` (defaults to the same place applications write event logs: `spark.eventLog.dir`).
- The default backing store is the local filesystem; HDFS, S3, GCS, ABFS, and other Hadoop-compatible FSes are also supported.
- On startup and on a polling interval (`spark.history.fs.update.interval`, default 10s), the `FsHistoryProvider` scans the log directory, finds new or changed files, and submits them to a thread pool (`replayExecutor`) to be **replayed**.
- "Replay" means: read the file line by line, parse each line as a JSON `SparkListenerEvent`, and feed it into a `ReplayListenerBus` which dispatches it to the same listeners that built the original UI.

### Event log format

Event logs are **newline-delimited JSON** (NDJSON), one Spark listener event per line. Each line has a string `"Event"` field that names the event type, plus per-event payload fields. Built-in event types use a short logical name (e.g. `"SparkListenerJobStart"`, `"SparkListenerTaskEnd"`). User-defined or third-party event types fall through to a generic class-name path — `"Event"` holds a fully-qualified Java class name and Jackson is asked to instantiate it.

### Trust assumptions (the load-bearing claim)

Event logs are written by Spark drivers and executors, which are themselves trusted. But the History Server reads event logs **from a directory on a filesystem**, and the trust boundary for that filesystem is whatever the operator configures it to be. Any principal that can write to `spark.history.fs.logDirectory` can deliver arbitrary JSON to `JsonProtocol.sparkEventFromJson`. **The History Server must treat event-log content as untrusted input.** Historically it has not — see `04_invariants.md` and `05_known_issues_and_advisories.md`.

### Why this matters for the History Server specifically

The driver writes events into a file it owns; nothing on the driver-write path deserializes attacker-controlled classes. The History Server, by contrast, **deserializes the file**. The driver's trust posture and the History Server's trust posture are different even though the file is the same. The 2026 [REDACTED] disclosure is the formal acknowledgement of that asymmetry.

## Invariants (overview-level)

- **INV-OVERVIEW-1.** The History Server replays event logs read from a filesystem path; that path is the trust boundary for History Server inputs.
- **INV-OVERVIEW-2.** Event-log content is structurally untrusted from the History Server's perspective, regardless of who *intended* to write it.
- **INV-OVERVIEW-3.** Audit scope is `core/` — specifically `core/src/main/scala/org/apache/spark/util/JsonProtocol.scala` and `core/src/main/scala/org/apache/spark/deploy/history/**`. SQL, MLlib, Structured Streaming are out of scope.
