# Apache Spark — Event Log Serialization Contract (`JsonProtocol`)

## Sources

- `JsonProtocol.scala` (master): https://github.com/apache/spark/blob/master/core/src/main/scala/org/apache/spark/util/JsonProtocol.scala
- `JsonProtocol` JavaDoc (Spark 4.0): https://spark.apache.org/docs/latest/api/java/org/apache/spark/util/JsonProtocol.html
- `FsHistoryProvider.scala` (master): https://github.com/apache/spark/blob/master/core/src/main/scala/org/apache/spark/deploy/history/FsHistoryProvider.scala
- SparkListenerEvent reference (community internals book): https://wforget.github.io/apache-spark-internals/SparkListenerEvent/
- SPARK-52381 fix PR (master): https://github.com/apache/spark/pull/51061
- SPARK-52381 backport PR (4.0): https://github.com/apache/spark/pull/51312
- SPARK-22264 (large-event-log replay issue, references the same code path): https://issues.apache.org/jira/browse/SPARK-22264

## Context

### `SparkListenerEvent` is the closed type the protocol is supposed to handle

`SparkListenerEvent` is a sealed-ish trait in `core/src/main/scala/org/apache/spark/scheduler/SparkListener.scala` and the parent of every event Spark publishes on its `LiveListenerBus`. Examples:

- `SparkListenerJobStart`, `SparkListenerJobEnd`
- `SparkListenerStageSubmitted`, `SparkListenerStageCompleted`
- `SparkListenerTaskStart`, `SparkListenerTaskEnd`, `SparkListenerTaskGettingResult`
- `SparkListenerExecutorAdded`, `SparkListenerExecutorRemoved`, `SparkListenerExecutorMetricsUpdate`
- `SparkListenerBlockManagerAdded`, `SparkListenerBlockManagerRemoved`, `SparkListenerBlockUpdated`
- `SparkListenerEnvironmentUpdate`, `SparkListenerApplicationStart`, `SparkListenerApplicationEnd`
- `SparkListenerLogStart`, `SparkListenerNodeBlacklisted`, `SparkListenerResourceProfileAdded`
- A small open-extension hatch: anything mixed in with `SparkListenerEvent` can be published; SQL and Structured Streaming layers extend this set in their own packages.

The contract `JsonProtocol` is supposed to maintain is: **the JSON wire form holds enough information to reconstruct a `SparkListenerEvent` subclass**, and `sparkEventFromJson` returns an instance of that closed hierarchy.

### How events are serialized

`JsonProtocol.sparkEventToJson(event: SparkListenerEvent): JValue` (and its newer Jackson-based equivalents) writes an event by pattern-matching on its known subtypes. Each known subtype has a dedicated `*ToJson` writer that emits a JSON object whose `"Event"` field is a short logical name like `"SparkListenerJobStart"`, plus the per-event payload. For unknown subtypes — typically user-defined events posted to the listener bus — the writer falls back to writing `"Event"` as the fully-qualified Java class name and using Jackson's bean serializer for the payload.

### How events are deserialized — `sparkEventFromJson` dispatch

`sparkEventFromJson(json)` reads the `"Event"` field as a string and dispatches:

```scala
val SPARK_LISTENER_JOB_START     = Utils.getFormattedClassName(SparkListenerJobStart)
val SPARK_LISTENER_JOB_END       = Utils.getFormattedClassName(SparkListenerJobEnd)
// ... many constants ...

(json \ "Event").extract[String] match {
  case `SPARK_LISTENER_JOB_START`       => jobStartFromJson(json)
  case `SPARK_LISTENER_JOB_END`         => jobEndFromJson(json)
  case `SPARK_LISTENER_TASK_START`      => taskStartFromJson(json)
  case `SPARK_LISTENER_TASK_END`        => taskEndFromJson(json)
  case `stageExecutorMetrics`           => stageExecutorMetricsFromJson(json)
  case `blockUpdate`                    => blockUpdateFromJson(json)
  case `resourceProfileAdded`           => resourceProfileAddedFromJson(json)
  // ... many more ...
  case other                            =>
    // FALLBACK — load and instantiate an arbitrary class by name
    mapper.readValue(json.toString, Utils.classForName(other))
}
```

The first N branches are **safe** — each maps a known string to a dedicated parser that yields a specific known `SparkListenerEvent` subclass. The trailing `case other =>` branch is the bug surface: it hands the attacker-controlled `other` string to `Utils.classForName`, which is a thin wrapper over `Class.forName(...)` on Spark's classpath, then asks Jackson's `mapper.readValue` to instantiate that class from the JSON.

### Why the fallback exists

User-defined `SparkListenerEvent` subclasses (third-party tools that post their own events to the listener bus — Sparklens, Spark Atlas hooks, Cloudera Navigator integrations, custom telemetry) want to be replayable by the History Server too. The fallback was the open-extension hatch for that case. The intended invariant — "the loaded class extends `SparkListenerEvent`" — was left implicit and enforced only by an `asInstanceOf[SparkListenerEvent]` cast later in the call chain, which happens **after** Jackson has already instantiated the class and run its default constructor / `@JsonCreator` factory / setter side effects.

### The `mapper.readValue` step is where impact happens

Jackson's `ObjectMapper.readValue(json, targetClass)`:

1. Loads `targetClass` (already done by `Utils.classForName`).
2. Selects a creator: default no-arg constructor, `@JsonCreator`-annotated constructor, factory method, or builder.
3. Walks the JSON tree and, for each property, looks for a matching setter / field / constructor parameter on `targetClass` (or its parents).
4. Invokes setters / constructor with attacker-controlled string values.

Any side effect in steps 2–4 — a constructor that opens a TCP connection, a setter that launches a thread, a factory that performs JNDI lookup, an `@JsonDeserialize` annotation that runs a custom deserializer — runs inside the History Server JVM with its full privileges. The PoC in the CVE uses `org.apache.hive.jdbc.HiveConnection`: a class whose constructor parses a JDBC URI and opens a JDBC connection. Other classes on the classpath have analogous side effects.

### The fix: typecheck before instantiation

The SPARK-52381 patch reshapes the fallback so that the class is **looked up but not instantiated** unless it is verifiably a `SparkListenerEvent` subclass:

```scala
case other =>
  val otherClass = Utils.classForName(other)
  if (classOf[SparkListenerEvent].isAssignableFrom(otherClass)) {
    mapper.readValue(json.toString, otherClass)
      .asInstanceOf[SparkListenerEvent]
  } else {
    throw new SparkException(s"Unknown event type: $other")
  }
```

The PR description (PR #51061) makes the semantic explicit: *"if you have an Event which is a class that does not extend `SparkListenerEvent` — we will create a class instance and then try to cast to `SparkListenerEvent` and get a `ClassCastException`. New code: we fail without creating a class instance — but with a `SparkException` instead."* The key behavioral difference is **no class instance is constructed** if the class is not a subclass of `SparkListenerEvent`. That closes the gadget surface.

### Two API surfaces — both must be patched

`JsonProtocol` exposes two overloads of `sparkEventFromJson`:

- `sparkEventFromJson(json: JValue): SparkListenerEvent` (json4s flavor)
- `sparkEventFromJson(json: JsonNode): SparkListenerEvent` (Jackson flavor, newer)

Either can reach the same `mapper.readValue(..., Utils.classForName(other))` sink if either one's fallback is unguarded. The fix applies to whichever branches exist in a given Spark version. Auditors should check both.

### Callers of `sparkEventFromJson`

- `ReplayListenerBus.replay()` in the History Server replay path — this is the in-scope, security-critical caller.
- `EventLoggingListener` round-trip tests in `core/src/test/scala/`.
- A handful of CLI tools (`HistoryServerSuite` and similar test scaffolding).

Only the History Server replay caller is exposed to attacker-controlled JSON in production.

## Invariants

- **INV-CONTRACT-1.** `sparkEventFromJson` must return only instances of `SparkListenerEvent` subclasses. The set of permissible runtime types is exactly the closed hierarchy rooted at `SparkListenerEvent`.
- **INV-CONTRACT-2.** Class lookup (`classForName`) on caller-supplied strings is acceptable IF the resulting `Class` is gated through `isAssignableFrom(classOf[SparkListenerEvent])` BEFORE instantiation. Lookup-then-cast-after-construction is NOT acceptable, because construction has observable side effects.
- **INV-CONTRACT-3.** Both overloads of `sparkEventFromJson` (`JValue`-flavor and `JsonNode`-flavor) must enforce the same type restriction.
- **INV-CONTRACT-4.** The fallback `case other =>` branch is the protocol's only polymorphic surface; the named-case branches deserialize fixed types and do not need a runtime typecheck.
