# Apache Spark — Consolidated Invariants for the History Server Audit

## Sources

- [REDACTED] Jira: https://issues.apache.org/jira/browse/[REDACTED]
- [REDACTED] fix PR (master): https://github.com/apache/spark[REDACTED]
- [REDACTED] backport PR (4.0): https://github.com/apache/spark[REDACTED]
- [REDACTED] advisory: https://seclists.org/oss-sec/2026/q1/310
- Tenable CVE record: https://www.tenable.com/cve/[REDACTED]
- Wiz CVE summary: https://www.wiz.io/vulnerability-database/cve/[REDACTED]
- Jackson [REDACTED] CVE Criteria: https://github.com/FasterXML/jackson/wiki/Jackson-Polymorphic-Deserialization-CVE-Criteria
- Spark security guide: https://spark.apache.org/docs/latest/security.html
- Spark monitoring docs (History Server): https://spark.apache.org/docs/latest/monitoring.html
- `JsonProtocol.scala`: https://github.com/apache/spark/blob/master/core/src/main/scala/org/apache/spark/util/JsonProtocol.scala

## Context

This file consolidates the invariants that the QPB skill should derive (blind) from the docs, the security advisory, and Jackson hardening guidance. The categorization is by **what the playbook is checking** rather than by source.

### Primary invariants (the ones that catch [REDACTED])

- **INV-1.** `JsonProtocol.sparkEventFromJson` must restrict the fallback path so that the class instantiated via `mapper.readValue(json, targetClass)` is a subtype of `SparkListenerEvent`. Concretely: between `Utils.classForName(other)` and any constructor call, there must be a guard equivalent to `if (classOf[SparkListenerEvent].[REDACTED])`.
- **INV-2.** `Utils.classForName` (or any reflective class-lookup primitive) must never be invoked with an unverified caller-supplied class name *and have the result fed into a constructor / `readValue` call* without a type-hierarchy gate. Lookup alone is benign; lookup-then-instantiate from untrusted strings is the bug class.
- **INV-3.** When the fallback class is not a `SparkListenerEvent`, the code must **throw before construction** — not "construct then `asInstanceOf` cast then catch ClassCastException." Construction side effects must not run on rejected input.

### Defense-in-depth invariants

- **INV-4.** Both overloads of `sparkEventFromJson` (the `JValue`/json4s overload and the `JsonNode`/Jackson overload) must enforce the same `[REDACTED]` gate. A patch that fixes only one overload while leaving the other vulnerable is incomplete.
- **INV-5.** The Jackson `ObjectMapper` used by `JsonProtocol` must not enable Default Typing globally (`enableDefaultTyping`, `activateDefaultTyping(LaissezFaireSubTypeValidator.instance, ...)`). If polymorphic typing is needed for sub-fields, it must use an explicit `@JsonSubTypes` registry or a `PolymorphicTypeValidator` restricted to a closed root.
- **INV-6.** No `SparkListenerEvent` subclass should declare field-level `@JsonTypeInfo(use = Id.CLASS)` or `Id.MINIMAL_CLASS` on attacker-reachable fields without a validator. (The [REDACTED] advisory explicitly cites `@JsonTypeInfo.Id.CLASS` on the top-level event as the structural problem; the same antipattern must not reappear on nested fields.)
- **INV-7.** Event-log deserialization must not call `ObjectInputStream.readObject()`, `SerializationUtils.deserialize`, `Kryo.readClassAndObject`, or any other native deserialization sink on log content. Event logs are JSON; if any non-JSON deserializer appears on this path, treat it as a finding.

### Trust-boundary invariants

- **INV-8.** Event-log file content is **untrusted input** at the History Server. Filesystem permissions on `spark.history.fs.logDirectory` are an operator-configurable defense-in-depth, not a sufficient defense. Spark's deployment guidance recommends shared-write (`drwxrwxrwxt`) permissions, so the History Server cannot assume sole-writer.
- **INV-9.** Web UI ACLs (`spark.ui.acls.enable`, `spark.history.ui.acls.enable`) and RPC authentication (`spark.authenticate`) do not protect the deserialization path. They gate **viewing** the rendered UI; deserialization runs at startup and on a polling timer with no HTTP request involved.
- **INV-10.** Authentication / authorization for the application API (`spark.history.ui.acls.enable`, ACL provider) is downstream of replay. Any check that runs after `sparkEventFromJson` cannot prevent the deserialization bug.

### Code-shape invariants the playbook can grep for

- **INV-11.** Inside `core/src/main/scala/org/apache/spark/util/JsonProtocol.scala`, every call site of `mapper.readValue(*, *)` whose target-class argument is derived from JSON content must have a `classOf[SparkListenerEvent].[REDACTED](...)` gate on the path to that call. (Calls whose target class is a literal type — `mapper.readValue(json, classOf[SparkListenerJobStart])` — are safe.)
- **INV-12.** Inside `JsonProtocol`, every call site of `Utils.classForName(...)` whose argument is derived from JSON content must either (a) be followed by an `[REDACTED]` gate before any constructor / `readValue` call, or (b) be inside a method that only returns the `Class<?>` and not an instance.
- **INV-13.** The History Server's classloader / `Utils.classForName` call chain has access to the full Spark + Hadoop + (optionally) Hive + transitive classpath. Restrictions cannot rely on "the gadget class won't be present" because the History Server inherits its classpath from `$SPARK_HOME/jars/` and operator-installed extras. The defense must be at the type-gate, not at the classpath.

### Observability / testability invariants

- **INV-14.** Unit tests must cover the rejection path: feeding `sparkEventFromJson` a JSON document whose `"Event"` field names a class that is not a `SparkListenerEvent` subclass must yield a thrown exception **and no instantiation of the named class**. A test that only asserts on the exception type without verifying no constructor ran is insufficient.
- **INV-15.** Test coverage must exist for at least one well-known gadget class (e.g. `java.lang.Runtime`, a custom test gadget) — i.e. the negative test must use a class whose construction would be observable if the gate failed.

### Out-of-scope invariants (explicitly NOT enforced here)

- **NOT-INV.** This audit does not opine on Spark's SQL planner, Catalyst, MLlib, Structured Streaming, Kubernetes operator, YARN ApplicationMaster, or shuffle service. Each of those has its own deserialization surface and its own threat model; they are separate audits.
- **NOT-INV.** This audit does not require that the History Server validate file *origin* (i.e. that the writer was a real Spark driver). The operator policy for who can write to `spark.history.fs.logDirectory` is configurable; the audit invariants apply regardless.

## Cross-references

- The implementation invariants (INV-1, INV-2, INV-3, INV-4, INV-11, INV-12) map to the bug surface documented in `02_event_log_serialization_contract.md` and the safe/unsafe patterns in `03_deserialization_safety.md`.
- The trust-boundary invariants (INV-8, INV-9, INV-10) map to `01_security_model.md`.
- The Jackson hardening invariants (INV-5, INV-6, INV-7) map to the Jackson community guidance summarized in `03_deserialization_safety.md` and `05_known_issues_and_advisories.md`.
