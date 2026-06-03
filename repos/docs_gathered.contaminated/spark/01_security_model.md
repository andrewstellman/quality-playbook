# Apache Spark — Security Model for the History Server + Event Logs

## Sources

- Spark security guide (current): https://spark.apache.org/docs/latest/security.html
- Spark 2.2 security guide (legacy reference for event-log permission guidance): https://downloads.apache.org/spark/docs/2.2.0/security.html
- Spark monitoring & History Server docs: https://spark.apache.org/docs/latest/monitoring.html
- `FsHistoryProvider` source: https://github.com/apache/spark/blob/master/core/src/main/scala/org/apache/spark/deploy/history/FsHistoryProvider.scala
- ASF advisory for [REDACTED]: https://seclists.org/oss-sec/2026/q1/310
- [REDACTED] Jira: https://issues.apache.org/jira/browse/[REDACTED]

## Context

### The two principals that touch an event log

1. **Spark driver / executor process** — writes events to the log during a Spark application's lifetime, using `EventLoggingListener`. Files are typically created with permissions such that only the owning user and group have read/write access.
2. **Spark History Server process** — reads event logs from `spark.history.fs.logDirectory` on a polling interval and **deserializes** them to reconstruct the Web UI.

These are different OS principals on most deployments. The History Server typically runs as a dedicated service account (e.g. `spark`) that the driver does NOT run as.

### Who can write to the event-log directory?

Spark's own security guide (the legacy 2.2 doc states this most clearly, and the practice persists) recommends configuring the event-log directory as a **shared-write, sticky-bit** directory:

> "When applications use event logging, the directory where the event logs go (`spark.eventLog.dir`) should be manually created with proper permissions. […] To secure the log files, the permissions should be set to `drwxrwxrwxt` for that directory. The owner of the directory should be the super user who is running the history server and the group permissions should be restricted to super user group. This will allow all users to write to the directory but will prevent unprivileged users from removing or renaming a file unless they own the file or directory."

In other words, **any local user on the cluster** (or, for HDFS deployments, any user with write access to the configured HDFS path) is **intentionally permitted to drop event-log files** into the directory the History Server is going to read. This is by design — it is how multi-user Spark clusters share a single History Server. **The set of principals that can deliver bytes into `JsonProtocol.sparkEventFromJson` is therefore approximately "any cluster user," not "trusted Spark internals."**

### Authentication on the Spark UI is not the boundary

Spark provides Web UI ACLs (`spark.ui.acls.enable`, `spark.acls.enable`, `spark.history.ui.acls.enable`, etc.) and various SASL/authentication options for RPC. These protect who can **view** the rendered History Server UI. They do not protect the History Server from malicious **input** files that have already been deposited in the log directory. The deserialization happens before any HTTP request is served.

### Trust boundary for this audit

- **Trust source (outside the boundary):** any process or user that has write access — by deliberate operator policy — to `spark.history.fs.logDirectory`.
- **Trust sink (inside the boundary):** the History Server JVM, which has its own privileges (often Kerberos credentials, HDFS delegation tokens, hive-metastore reach, network egress, etc.).
- **The bytes that cross the boundary:** newline-delimited JSON event records, parsed by `JsonProtocol.sparkEventFromJson`.

### Threat model framing the History Server fix accepts

The [REDACTED] advisory implicitly endorses this framing: *"an attacker with access to the Spark event logs directory"* is treated as a realistic adversary, and the History Server is expected to defend against malicious JSON in the log directory rather than relying on FS permissions to keep all writers benign. [REDACTED]'s fix (restricting `mapper.readValue` to subclasses of `SparkListenerEvent`) accepts that event-log files are INPUT, not trusted data.

### Why "low severity" still matters for QPB

The ASF advisory rates this **low** severity because the attacker needs filesystem write access to the event-log directory. That bar is genuinely meaningful in single-tenant clusters where only one user writes there. But it is **routinely cleared** in:

- Multi-tenant YARN / Kubernetes clusters where many users share an HDFS / object-store event-log path with shared-write permissions (the canonical configuration above).
- Clusters where a compromised low-privilege user account is the attacker's foothold and the History Server runs as a more privileged account.
- Clusters where the event-log directory is on an object store with a broad write policy and a tighter read policy for the History Server.

For QPB, the severity rating is irrelevant; the **invariant** ("the History Server must not instantiate caller-named classes") is what the playbook needs to catch.

## Invariants

- **INV-SEC-1.** Event-log files are untrusted input to the History Server. Any code path that consumes them must treat their content as adversarial.
- **INV-SEC-2.** Filesystem permissions on the event-log directory are an *operator-configurable defense-in-depth control*, not a sufficient defense. Spark's own deployment guidance recommends shared-write permissions, so the History Server cannot assume sole-writer.
- **INV-SEC-3.** Web UI ACLs and RPC authentication do not protect the event-log deserialization path; that path runs at startup and on a polling timer, with no user request involved.
- **INV-SEC-4.** The History Server's JVM privileges (Kerberos, HDFS tokens, network egress, classpath gadgets) are the impact surface if untrusted deserialization is reached. Limiting class instantiation at the parser is the primary control.
