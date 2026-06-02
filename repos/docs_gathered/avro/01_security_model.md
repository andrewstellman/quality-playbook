# 01 — Security Model: Trust Boundaries Around the Avro Schema

## Sources

- `https://avro.apache.org/project/security/` — Apache Avro Security Policy (verbatim quotes below)
- `https://avro.apache.org/docs/1.12.0/specification/` — Avro Specification (schema semantics; what properties are spec-defined vs. user-supplied)

## The Security Policy in Avro's Own Words

The project's official security page (`avro.apache.org/project/security/`) is short and surprisingly load-bearing. Key paragraphs, verbatim:

> The Avro library implementations are designed to read and write any data conforming to a schema. Transport is outside the scope of the Avro library: applications using Avro should be surrounded by security measures that prevent attackers from writing random data and otherwise interfering with the consumers of schemas.

> Although the Avro library will not read or write data except as directed to by invoking it, avoiding leaking data into a side channel like log files is a non-goal security-wise for Avro. This means, for example, that you will need to catch and handle exceptions instead of simply writing them to a log file.

> In some cases, like schema parsing, type conversions and based on explicit schema properties, Avro can execute code provided by the environment. Avro has opt-in mechanisms for code that is eligible for execution. Applications using Avro should have a secured supply chain, ensuring code registered to be executed is safe.

> **This supply chain also includes the schemas being used: if they are user provided, additional validation is strongly advised. Such validation can use the parsed schema, as schema parsing itself is safe: the parser allows SPIs, but is not otherwise configurable.**

That bold sentence is the one that matters for [REDACTED]: the project explicitly classifies the schema as a **supply-chain input**, and explicitly says "if they are user provided, additional validation is strongly advised." The runtime/codegen path was being held to that contract; [REDACTED] closed the gap where it wasn't.

The official summary, again verbatim:

> In short, using Avro is safe, provided applications:
> - are surrounded by security measures that prevent attackers from writing random data and otherwise interfering with the consumers of schemas
> - avoid leaking data by, for example, catching and handling exceptions
> - have a secured supply chain, ensuring code registered to be executed is safe
> - if schemas are user provided, validate the parsed schema before use

## Trust Boundaries

There are three concentric trust zones in any Avro deployment. They map directly onto the threat model QPB needs to test.

### Zone A — Build-time / generation-time trust ([REDACTED] lives here)

- **Inputs:** `.avsc`, `.avpr`, `.avdl` schema files fed to `SpecificCompiler` (directly, via `avro-tools compile`, or via the `avro-maven-plugin`).
- **Outputs:** Java source files written to `outputDir`, then compiled by `javac`.
- **Trust assumption (pre-fix):** the schema was treated as trusted *with respect to the generated source*. String properties like `javaAnnotation` were emitted verbatim into the output `.java` file. `doc` strings were emitted verbatim into Javadoc comments.
- **Threat (pre-fix):** an attacker who controls or can influence a schema file the build picks up can inject arbitrary Java code into the generated source, which is then compiled and run with whatever privileges the resulting application has. The schema would not look obviously malicious — `javaAnnotation` is a documented Avro feature.
- **Trust contract (post-fix):** `SpecificCompiler` must treat every string lifted from the parsed schema as untrusted. `javaAnnotation` values are validated against `VALID_AS_ANNOTATION` (a regex that accepts only a Java identifier optionally followed by a parameter list of literal-or-name=literal pairs); invalid values are dropped silently. `doc` strings are routed through `escapeForJavadoc` before reaching the Velocity templates. `escapeForJavaString` is used wherever a Java string literal is being constructed (most importantly, `SCHEMA$`'s embedded schema JSON).

### Zone B — Schema-parse-time trust

- **Inputs:** Bytes claiming to be Avro JSON schema or Avro IDL, passed to `Schema.Parser` or `Idl`.
- **Trust assumption (per security policy):** parsing itself is safe. The parser exposes SPI hooks for custom logical types but is "not otherwise configurable."
- **Threat history:** [REDACTED] (AVRO-3985) violated this — schema parsing could be coerced into arbitrary code execution. Fixed in 1.11.4 / 1.12.0. This is a different CVE than the one QPB is hunting but informs the larger pattern: untrusted schemas have historically been the attack vector of choice.

### Zone C — Data-read-time trust

- **Inputs:** Avro-encoded bytes (binary or JSON), read against a known reader schema.
- **Trust assumption:** the runtime will read or write any data conforming to a schema. It will not validate semantic content. Applications are expected to do that themselves.
- **Out-of-scope:** transport security, denial of service via pathological inputs (some such issues *have* been treated as CVEs — e.g., the Rust and C# `Allocation of Resources Without Limits` advisories — but the policy explicitly says transport is the application's job).

## Schemas-as-Config vs. Schemas-from-Network

The CVE pivots on a distinction QPB will need to make in any caller's deployment:

- **Schemas-as-config.** Schemas live in the repo alongside the application source, are reviewed in PRs, and only ever hit `SpecificCompiler` at build time. An attacker would have to compromise the source supply chain to introduce a malicious `javaAnnotation`. Risk is non-zero (think: typosquatted Maven dependency that ships an `.avsc` in its JAR, or a build that downloads schemas from a schema registry at compile time) but bounded.
- **Schemas-from-network.** Schemas arrive at runtime: schema-registry-driven Kafka pipelines, RPC handshakes that include peer schemas, IPC. Pre-[REDACTED], if such a runtime path *also* invoked `SpecificCompiler` (e.g., a service that dynamically generates Java classes for incoming schemas — rare but documented in the Avro tooling ecosystem), the attacker controls the codegen input. This is the worst-case framing for [REDACTED]. CVSS v4 6.9 / Moderate reflects that most deployments don't expose this path; the underlying weakness ([REDACTED], [REDACTED]) is severe whenever they do.

## What Codegen Output *Must* Guarantee (the contract violated by [REDACTED])

- A generated `.java` source file must be valid Java regardless of any string content lifted from the schema.
- A schema must not be able to inject statements, declarations, or imports into a generated class body via *any* string property.
- A schema must not be able to inject Java annotations the schema author did not explicitly intend (i.e., `javaAnnotation` values must be syntactically constrained to "annotation-shaped" strings).
- A schema must not be able to break out of a Javadoc comment (`*/` injection), nor out of a Java string literal (`SCHEMA$` embedded JSON).
- Failure mode must be safe: an invalid `javaAnnotation` is **dropped** (not emitted, not raised as a compile error). This is the design choice the patch reflects — silent drop, not fail-closed. QPB should note this is debatable; some maintainers might have preferred a hard error.

## Invariants

- **Schemas are untrusted input.** The Apache Avro security policy says so in writing.
- **The parsed-schema-string -> generated-source [REDACTED] is the principal codegen invariant.** Every string field that ends up in a generated `.java` file must be either (a) validated against a syntactic whitelist (`javaAnnotation` -> `VALID_AS_ANNOTATION` regex) or (b) escaped for its target lexical context (`doc` -> `escapeForJavadoc`; embedded JSON -> `escapeForJavaString`).
- **Validation must happen at codegen time, not IDL-parse time.** `.avdl` is a thin syntactic skin over JSON properties; an `@javaAnnotation("...")` IDL annotation becomes a JSON `javaAnnotation` string property indistinguishable from one a user wrote directly in `.avsc`. Sanitisation in the IDL parser would miss the JSON path entirely.
- **Codegen failures should be silent and benign** (per the [REDACTED] patch). Invalid annotations are dropped; valid ones are emitted. The fix does not throw on bad input.
- **The runtime (GenericData) path is out-of-scope for this CVE** — no Java source is generated, so no codegen-injection invariant applies. (Other CVEs apply, notably [REDACTED].)
