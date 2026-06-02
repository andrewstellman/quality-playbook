# Apache Spark — Issue Tracker Themes (History Server + Serialization)

## Sources

- ASF Jira — SPARK project: https://issues.apache.org/jira/projects/SPARK/issues
- SPARK-52381 (this CVE): https://issues.apache.org/jira/browse/SPARK-52381
- SPARK-49751 — Fix deserialization of SparkListenerConnectServiceStarted: https://issues.apache.org/jira/browse/SPARK-49751
- SPARK-42754 — 3.4 SHS SQL tab incorrectly groups SQL executions when replaying 3.3 logs: https://issues.apache.org/jira/browse/SPARK-42754
- SPARK-18462 — SparkListenerDriverAccumUpdates does not deserialize properly: https://issues.apache.org/jira/browse/SPARK-18462
- SPARK-22264 — History server unavailable on large event-log files: https://issues.apache.org/jira/browse/SPARK-22264
- SPARK-22783 — Event-log dir filled by large `.inprogress` files: https://issues.apache.org/jira/browse/SPARK-22783
- SPARK-32529 — 3.0 History Server may never finish one round of log-dir scan: https://issues.apache.org/jira/browse/SPARK-32529
- SPARK-18085 — SPIP: Better History Server scalability: https://issues.apache.org/jira/browse/SPARK-18085
- SPARK-45126 — Multi-tenant history server: https://issues.apache.org/jira/browse/SPARK-45126
- SPARK-3697 — HistoryServer can't list event logs when a no-perms directory is present: https://issues.apache.org/jira/browse/SPARK-3697
- SPARK-26912 — Allow setting permission for event_log: https://github.com/apache/spark/pull/23827
- GitHub Advisories tagged `spark`: https://github.com/advisories?query=spark

## Context

Apache Spark tracks issues in the ASF Jira project key `SPARK`. Pull requests on GitHub typically have `[SPARK-NNNNN]` prefixes that link back. Below are the recurring themes most relevant to the QPB History Server audit. Each theme groups issues with a shared shape so the playbook can reason about "what kinds of failures cluster on this code path."

### Theme 1 — Event-log JSON schema drift causes deserialization failures

A recurring class of issue: a new Spark version emits an event field that the old version's `JsonProtocol` parser doesn't recognize, or vice versa, and the History Server fails to replay the log.

- **SPARK-49751** — `SparkListenerConnectServiceStarted` (a Spark Connect–related event) added in a recent version did not deserialize properly when read by an older History Server.
- **SPARK-42754** — Spark 3.4's History Server SQL tab incorrectly groups SQL executions when replaying event logs from Spark 3.3 and earlier, because Jackson's "ignore missing properties" behavior silently fills in defaults rather than raising.
- **SPARK-18462** — `SparkListenerDriverAccumUpdates` event does not deserialize properly in the History Server; a `ClassCastException` due to oddities in Jackson object mapping breaks the SQL tab.

**Audit relevance.** This theme establishes that **the JsonProtocol parser is fragile and silently coerces unexpected input**, which is exactly the failure mode the CVE-2025-54920 fix has to harden. Fixes in this theme typically add per-event missing-field defaults or per-event parser branches; the playbook should flag any such fix that adds a new `case other =>`-style fallback without a type gate, or that relaxes Jackson configuration (`@JsonIgnoreProperties(ignoreUnknown=true)` is fine; `enableDefaultTyping` is not).

### Theme 2 — Multi-tenant / shared event-log directory operations

Operating Spark in production typically means multiple users sharing one History Server instance. The Jira reflects the operational complexity (and security posture) of that arrangement.

- **SPARK-45126** — Multi-tenant history server. Establishes that the design target IS multi-tenant; the History Server is expected to read logs written by many distinct cluster users.
- **SPARK-3697** — A no-perms directory inside `spark.eventLog.dir` breaks the listing scan, blocking the History Server from loading other users' logs.
- **SPARK-26912** — Allow setting permission for event_log. The PR thread covers the operational debate over how restrictive event-log file permissions can be without breaking the History Server's read access.

**Audit relevance.** Confirms the trust-boundary claim in `01_security_model.md`: the event-log directory is a *shared* writable surface by design, and the History Server is the privileged consumer. The playbook should treat "logs are written by Spark drivers we trust" as a misconception — the docs and Jira tickets both treat the directory as multi-writer.

### Theme 3 — Event-log files at scale (rolling, compaction, replay perf)

A large secondary theme: event-log files grow unboundedly for streaming and long-running applications, and the History Server's replay performance becomes load-bearing.

- **SPARK-22264** — History server is unavailable when an event-log file is too large; replay OOMs or stalls.
- **SPARK-22783** — Event-log directory fills with large `.inprogress` files from streaming apps.
- **SPARK-32529** — Spark 3.0 History Server may never finish one round of log-dir scan because the scan is sequential and per-file work dominates.
- **SPARK-18085** — SPIP for better History Server scalability for many / large applications. Introduced rolling event logs (`spark.eventLog.rolling.enabled`) and per-app compaction.

**Audit relevance.** Rolling event logs split one app's events across multiple files; compaction rewrites old files. Both operations touch the same `JsonProtocol` deserialization path. The audit invariants in `04_invariants.md` apply equally to compacted files and to rolling-segment files. The playbook should not assume "only one entry point" — any code that reads event-log bytes and calls `JsonProtocol.sparkEventFromJson` is in scope.

### Theme 4 — Security advisories and CVEs in `core/`

GitHub Advisories tagged `spark` returns a sparse but recurring stream of `core/`-targeting CVEs:

- **CVE-2025-54920 / SPARK-52381** — this audit's target. Insecure deserialization in `JsonProtocol`.
- **CVE-2022-33891** — `spark-submit` `doAs` command injection via `groups.command`. CWE-78 in `core/`.
- **CVE-2020-9480** — RPC authentication shared-secret bypass.
- **CVE-2018-17190 / CVE-2018-11770** — Standalone master REST API accepts unauthenticated code submission.
- **CVE-2017-12612** — Spark Launcher API unsafe Java deserialization (`ObjectInputStream.readObject` on socket data).

**Audit relevance.** Establishes the precedent that **`core/` has a recurring pattern of input-to-code-execution bugs**. Of the prior CVEs, CVE-2017-12612 is the closest analogue: untrusted bytes → Java deserialization → RCE. The Launcher API's response (kill the API, recommend `spark-submit`) is different from JsonProtocol's response (typecheck before construction), but the underlying invariant — *don't deserialize untrusted bytes into code-equivalent objects* — is the same.

### Theme 5 — Jackson configuration / version churn

Spark's `JsonProtocol` historically used `json4s` (built on Jackson); newer code paths use Jackson directly via `ObjectMapper`. Periodic upgrades of `jackson-databind` to pick up CVE fixes cause version-skew bugs and reshape the deserialization surface.

- Examples: `jackson-databind` is repeatedly bumped in `pom.xml` / `build.sbt` across Spark releases to clear the long CVE backlog.
- Spark provides two `ObjectMapper` configurations in different code paths (`JsonProtocol`'s own mapper vs. one in `JsonUtils` / REST APIs); inconsistencies between them have been a source of bugs.

**Audit relevance.** The playbook should not assume Jackson defaults are uniform across Spark's codebase. The `ObjectMapper` instance used by `JsonProtocol` is the one whose configuration matters for this audit; auditors should verify that mapper does not have `activateDefaultTyping` configured.

### Theme 6 — Listener-bus event extensibility hatch (the structural pressure that created the bug)

`SparkListenerEvent` was deliberately designed as an open extension point. Third-party code (Sparklens, Spark Atlas, custom metric exporters, vendor integrations like Cloudera Navigator) registers listeners and posts custom event classes. The History Server needs to replay those custom events to reconstruct the UI faithfully — which is **why** the `case other =>` fallback exists.

- Sparklens (qubole/sparklens) and similar tools post custom events; their replay depends on the fallback path.
- Issue threads on the SPARK-52381 PR (especially commentary from `mridulm`) debate whether removing the fallback breaks downstream extension authors. The fix preserves extension by allowing any `SparkListenerEvent` subclass while denying everything else, which is the minimal restriction.

**Audit relevance.** The fallback is not vestigial code; it's a load-bearing extension hatch. The right invariant is "the hatch must require a `SparkListenerEvent` type contract," not "remove the hatch." The playbook should not flag the existence of the fallback — it should flag the *absence* of the type gate.

## Invariants

- **INV-TRACKER-1.** New event-type additions in `JsonProtocol` must be added as named dispatcher cases with their own typed parsers, not by widening the fallback.
- **INV-TRACKER-2.** Schema-drift fixes (per Theme 1) must not relax Jackson typing configuration; if they configure the mapper to ignore unknown fields, that's acceptable, but enabling default typing is not.
- **INV-TRACKER-3.** Performance / scalability work on event-log replay (Theme 3) must preserve the type gate; rolling-log and compaction code paths that call `sparkEventFromJson` inherit the same invariant.
- **INV-TRACKER-4.** The extension hatch (Theme 6) is preserved by the `isAssignableFrom(SparkListenerEvent)` allowlist. The playbook must not propose "remove the fallback" as a fix; the right fix is to gate it.
