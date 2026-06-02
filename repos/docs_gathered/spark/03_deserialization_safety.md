# Apache Spark — Deserialization Safety on the History Server Path

## Sources

- SPARK-52381 fix PR (master, with the diff and reviewer thread): https://github.com/apache/spark/pull/51061
- SPARK-52381 backport PR (4.0): https://github.com/apache/spark/pull/51312
- CVE-2025-54920 advisory: https://seclists.org/oss-sec/2026/q1/310
- Jackson polymorphic-deserialization CVE criteria (FasterXML wiki): https://github.com/FasterXML/jackson/wiki/Jackson-Polymorphic-Deserialization-CVE-Criteria
- "On Jackson CVEs" (Tatu Saloranta, jackson-databind lead): https://cowtowncoder.medium.com/on-jackson-cves-dont-panic-here-is-what-you-need-to-know-54cd0d6e8062
- jackson-databind CVE-2017-7525 issue: https://github.com/FasterXML/jackson-databind/issues/1599
- Exploiting Jackson RCE (Adam Caudill): https://adamcaudill.com/2017/10/04/exploiting-jackson-rce-cve-2017-7525/

## Context

### When polymorphic class instantiation from a string-typed event happens

Inside `JsonProtocol.sparkEventFromJson`, three conditions must all hold for an attacker to reach class instantiation from a string they control:

1. The input JSON contains an `"Event"` field whose string value is **not** one of the known dispatcher cases.
2. The fallback branch runs `Utils.classForName(other)`. If `other` is a fully-qualified class name resolvable on the History Server JVM's classpath, this returns a `Class<?>` object.
3. The fallback branch runs `mapper.readValue(json.toString, returnedClass)`. Jackson selects a creator (no-arg constructor, `@JsonCreator` factory, builder) on that class and invokes it with attacker-controlled JSON values.

Step 3 is where impact materializes. Steps 1 and 2 are harmless on their own — class lookup has no side effects beyond classloader caching; bytecode execution begins at construction.

### The safe pattern

```scala
val cls = Utils.classForName(other)
if (classOf[SparkListenerEvent].isAssignableFrom(cls)) {
  mapper.readValue(json.toString, cls).asInstanceOf[SparkListenerEvent]
} else {
  throw new SparkException(s"Unknown event type: $other")
}
```

Why this is safe:

- The typecheck happens on the `Class<?>` object (a reflective handle) **before** any constructor or factory runs. No bytecode from the user-named class has executed yet.
- `isAssignableFrom` is a JVM intrinsic that walks the class hierarchy; it cannot be tricked by overridden methods on the target class because it does not invoke any methods.
- The hierarchy under `SparkListenerEvent` is a closed, well-known set of Spark internal classes whose constructors / setters are auditable and do not perform IO during deserialization. (Auditors should still spot-check that none of these accept polymorphic sub-fields with their own unsafe typing, but the attack surface shrinks from "every class on the classpath" to "every class in Spark's event hierarchy.")

### The unsafe pattern

```scala
mapper.readValue(json.toString, Utils.classForName(other))
```

Why this is unsafe:

- `other` is a string from attacker-controlled JSON.
- `classForName(other)` resolves it against the History Server's classpath, which on a typical Spark deployment includes Spark core, Spark SQL, Spark MLlib, Hadoop client libraries, Hive client libraries (when the optional Hive bundle is present), Jackson, Guava, log4j, Netty, and any vendor-shipped extras.
- `mapper.readValue(..., cls)` then constructs an instance of `cls`. Any side effect inside that construction runs.

### Gadget classes are the impact multiplier

A "gadget" is a class whose construction (or whose setter side effects during Jackson population) does something useful to an attacker. The CVE-2025-54920 PoC uses `org.apache.hive.jdbc.HiveConnection`, whose constructor parses a JDBC URI like `jdbc:hive2://<attacker-host>:<port>/` and **opens a TCP connection** to that endpoint. Other classes commonly present on a Spark classpath that have side-effectful constructors or setters include:

- `org.springframework.context.support.ClassPathXmlApplicationContext` — loads a Spring config from a URL the attacker controls; the config can contain `bean` definitions with `init-method` that run arbitrary code.
- `com.sun.rowset.JdbcRowSetImpl` — performs JNDI lookup on its `dataSourceName` setter; combine with an LDAP-based JNDI gadget for RCE.
- JNDI-aware classes generally, in JDK versions where JNDI didn't enforce the `trustURLCodebase=false` policy.
- HTTP/JDBC client constructors that initiate connections to attacker endpoints (data exfil / DNS exfil).

The set of available gadgets depends entirely on the History Server's classpath. Spark by default does **not** bundle Hive, but the `spark-hive` profile is widely deployed; many production Spark builds include it. The History Server inherits whatever JARs the operator dropped into `$SPARK_HOME/jars`.

### Standard Java / Jackson deserialization-of-untrusted-input pitfalls

This bug is a clean instance of **CWE-502 Deserialization of Untrusted Data**. The Jackson community has documented its analogous footgun extensively:

- **Default Typing** (`ObjectMapper.enableDefaultTyping()`) is the classic Jackson antipattern. When default typing is on, Jackson writes a `@class` field next to every polymorphic field and reads it back to drive `Class.forName`. Decades of CVEs (CVE-2017-7525, CVE-2017-15095, CVE-2018-7489, CVE-2019-12086, …) blacklist specific gadget classes one by one. Jackson 2.10 introduced `activateDefaultTyping(PolymorphicTypeValidator)` to force developers to explicitly allowlist subtypes.
- The Spark bug is **structurally equivalent** to default-typing-without-a-validator: the `"Event"` field plays the role of `@class`, and `Utils.classForName(other)` plays the role of the default-typing resolver. The only difference is that the dispatch is hand-rolled rather than annotation-driven, which means existing Jackson hardening (PolymorphicTypeValidator, Default Typing blocklist) does not help.
- **Mitigations that the Jackson community recommends**, mapped to this codebase:
  - Use `@JsonTypeInfo(use = Id.NAME)` with an explicit `@JsonSubTypes` registry rather than `Id.CLASS` / `Id.MINIMAL_CLASS`. The Spark dispatcher is morally `Id.NAME`-style (a logical name like `"SparkListenerJobStart"`) for known events, but the fallback collapses to `Id.CLASS` semantics. Removing the fallback or gating it on `isAssignableFrom` collapses it back to a constrained set.
  - Use a `PolymorphicTypeValidator` that restricts subtypes to a closed root. The `isAssignableFrom(classOf[SparkListenerEvent])` check is the hand-rolled equivalent.
  - Treat the `Class<?>` argument to `readValue` as part of the trust boundary: it must come from a server-side allowlist, never from the JSON itself.

### Other unsafe patterns to watch for in the same code path

While auditing the History Server path, the playbook should also flag adjacent failure modes:

- **`ObjectInputStream.readObject()` on event-log bytes.** Spark's event logs are JSON, not Java serialization, so this should not appear; if it does in a custom log format, it's strictly worse.
- **Reflection-driven setters fed JSON values.** Even within the `SparkListenerEvent` hierarchy, if any event's fields accept polymorphic sub-objects (e.g. a `properties` map whose values can be any class), Jackson may re-enter polymorphic resolution. The fix should restrict only the *root* class; Jackson's per-field typing for `SparkListenerEvent` subclasses should not use `Id.CLASS`.
- **Service-loader auto-discovery from event-log content.** If any event triggers a `ServiceLoader.load(...)` call whose iterator is influenced by event content, that's another class-name-from-JSON path.
- **Hadoop / Hive `Configuration.set` from event values.** Hive/Hadoop `Configuration` objects honor `*.class` keys to load classes; passing attacker-controlled config in is another unsafe-class-loading sink.

### Summary of the safe/unsafe distinction

| Aspect | Unsafe (pre-SPARK-52381) | Safe (post-SPARK-52381) |
| --- | --- | --- |
| Order of operations | look up class, **instantiate**, then cast | look up class, **typecheck**, then instantiate |
| Failure mode for non-event class | `ClassCastException` after construction side effects already ran | `SparkException` thrown before construction |
| Attacker reach | every class on the History Server classpath | only `SparkListenerEvent` subclasses |
| Side effects on attack input | constructor / setters of attacker-named class run | none |

## Invariants

- **INV-DESER-1.** Class lookup may use a caller-supplied name; class **instantiation** must not, unless the class has been verified to extend `SparkListenerEvent` first.
- **INV-DESER-2.** `mapper.readValue(json, targetClass)` calls inside `JsonProtocol` must have `targetClass` either bound to a literal type or gated through `classOf[SparkListenerEvent].isAssignableFrom(targetClass)`.
- **INV-DESER-3.** Failure mode for a non-event class name must be **throw before construction**, not "construct then cast." `ClassCastException` after construction is unacceptable because constructor side effects have already fired.
- **INV-DESER-4.** Jackson default typing (`enableDefaultTyping`, `activateDefaultTyping(LaissezFaireSubTypeValidator)`) must not be enabled on the `ObjectMapper` used by `JsonProtocol`. Use an explicit `@JsonSubTypes` registry or a hand-rolled dispatcher.
- **INV-DESER-5.** No sub-field within a `SparkListenerEvent` subclass should declare polymorphic typing as `JsonTypeInfo.Id.CLASS` or `Id.MINIMAL_CLASS` without a `PolymorphicTypeValidator` restricting the allowed subtypes.
- **INV-DESER-6.** Event-log deserialization must not call `ObjectInputStream.readObject()`, `Serialization.deserialize(bytes)`, or any other native Java-serialization sink on log content.
