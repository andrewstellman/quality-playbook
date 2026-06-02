# 00 — Apache Avro: Project Overview

## Sources

- `https://github.com/apache/avro` — canonical repository
- `https://avro.apache.org/` — project website
- `https://avro.apache.org/docs/1.12.0/` — official documentation (current release)
- `https://avro.apache.org/docs/1.12.0/specification/` — Avro Specification (data model, encoding, sort order, logical types)
- `https://avro.apache.org/docs/1.12.0/idl-language/` — IDL Language reference (`.avdl` higher-level schema authoring)

## What Avro Is

Apache Avro is a **schema-driven data serialization system** maintained at the Apache Software Foundation. It is a peer of Thrift and Protocol Buffers in the "interface description language + binary wire format" space, but with two distinguishing design choices:

- **Dynamic typing.** Code generation is not required to read or write data files nor to use/implement RPC protocols. Generation is an optional optimization, "only worth implementing for statically typed languages." (Avro 1.12.0 docs, *Introduction*.)
- **Schemas travel with the data.** When Avro data is stored in a file, its schema is stored with it. When Avro is used in RPC, the client and server exchange schemas in the connection handshake. Result: the wire format is tag-free (no per-field IDs, no per-value type tags), which is small and fast.

Schemas themselves are written in **JSON**. The IDL (`.avdl`) is a higher-level language that compiles to JSON `.avsc` (schema) or `.avpr` (protocol) files; the binary wire format is defined against the JSON form.

## Languages Implemented in the Apache/avro Repo

The single `apache/avro` GitHub monorepo carries implementations for multiple languages, each under `lang/<language>/`:

- **Java** (~48% of the codebase) — the reference implementation; the one most affected by CVE-2025-33042.
- **C#** (~16%)
- **C** (~10%)
- **C++** (~9%)
- **Python** (~5%)
- **JavaScript** (~4%)
- Other: Perl, PHP, Ruby

The Rust SDK is moving out of this repo to `https://github.com/apache/avro-rs`.

CI badges in the README cover `test-lang-{c, csharp, c++, java, js, perl, ruby, py, php}.yml` and CodeQL static analysis for C#, Java, JavaScript, and Python — meaning the security-scanning surface is broad but the code-injection surface this audit cares about is **Java-only**.

## Key Terms (canonical glossary)

- **Schema** — a JSON document describing a type. Primitive types: `null`, `boolean`, `int`, `long`, `float`, `double`, `bytes`, `string`. Complex/named types: `record`, `enum`, `array`, `map`, `union`, `fixed`. (Spec §Named Types, §Primitive Types.)
- **Record** — a named, ordered set of fields, each with a name and a type. The most common composite type. Records carry optional `doc`, `aliases`, and arbitrary user properties.
- **Named type** — `record`, `enum`, or `fixed`. Has a `name` and optional `namespace`; identified by its fullname (e.g., `org.apache.avro.test.Employee`).
- **Logical type** — an Avro primitive/complex type with a `logicalType` attribute that denotes a derived type (e.g., `decimal`, `uuid`, `date`, `timestamp-millis`). Implementations must ignore unknown logical types and fall back to the underlying type.
- **Codec** — compression mechanism for object container files (`null`, `deflate`, `snappy`, `bzip2`, `xz`, `zstandard`).
- **IDL (`.avdl`)** — Avro Interface Definition Language. Higher-level, Java-/C-/C++-like syntax that compiles to JSON `.avsc` (schema) or `.avpr` (protocol) files. Supports `@order`, `@namespace`, `@aliases`, `@java-class`, `@java-key-class`, `@logicalType`, and arbitrary user annotations (which become JSON properties on the resulting schema).
- **Protocol** — a named set of messages (RPC operations), plus the named types those messages reference. Files: `.avpr` (JSON) or `.avdl` (IDL source).
- **SpecificRecord** — the Java code-generation target. Each named type in a schema becomes a generated `.java` file with a `SCHEMA$` constant, getters/setters, a `Builder`, and Javadoc derived from the schema's `doc` field. **This is the surface CVE-2025-33042 lives on.**
- **GenericRecord / GenericData** — Java's schema-driven, no-codegen path. Records are `Map`-like at runtime. Not affected by CVE-2025-33042 because no Java source is generated.
- **`javaAnnotation` property** — a non-spec, Java-codegen-only schema property recognised by `SpecificCompiler`. When present on a schema/record/field, its string value is emitted verbatim as a Java annotation (`@<value>`) on the generated class/field. **The taint source for CVE-2025-33042.**
- **`doc` field** — a JSON-spec-defined optional string on records, fields, enums, etc. Surfaced into Javadoc by the templates. Also a taint source (separately patched in AVRO-4053).
- **Velocity template** — the SpecificCompiler renders generated Java source through Apache Velocity templates living in `lang/java/compiler/src/main/velocity/org/apache/avro/compiler/specific/templates/java/classic/{record,enum,fixed,protocol}.vm`. The templates call back into compiler helper methods (`javaAnnotations(...)`, `escapeForJavadoc(...)`, `escapeForJavaString(...)`, formerly `javaEscape(...)`).

## Repo Layout (relevant subset)

```
apache/avro/
  doc/                              <- Hugo source for avro.apache.org
  lang/
    java/
      avro/                         <- core Java library (schema parsing, GenericData)
      compiler/
        src/main/java/org/apache/avro/compiler/specific/
          SpecificCompiler.java     <- the vulnerable Java codegen (CVE-2025-33042)
        src/main/velocity/.../templates/java/classic/
          enum.vm                   <- Velocity templates (patched in AVRO-4053)
          fixed.vm
          protocol.vm
          record.vm
      ipc/                          <- RPC
      tools/                        <- avro-tools CLI (idl, idl2schemata, compile, etc.)
      maven-plugin/                 <- invokes SpecificCompiler from Maven
    py/                             <- Python implementation
    c/  c++/  csharp/  js/  perl/  php/  ruby/
  share/                            <- shared test data, editor support
```

## What QPB Is Looking For (caller's framing)

The audit target is **CVE-2025-33042 / AVRO-4053**: an unsanitized-taint flow in `SpecificCompiler` (Java) where the `javaAnnotation` schema property (and the `doc` string) were emitted verbatim into generated Java source. Classic codegen injection (CWE-94). Vulnerable parent commit `80400781a796bc0e90dd8ea1db42234926db33e9`; fix commit `84bc7322ca1c04ab4a8e4e708acf1e271541aac4` (PR #3150). The fix adds a regex validator `isValidAsAnnotation()` plus an `escapeForJavadoc()` Velocity helper used throughout the templates.

## Invariants

- The Java SDK's code-generation entry point is `SpecificCompiler` in `lang/java/compiler/src/main/java/org/apache/avro/compiler/specific/`; any code-injection invariant lives there or in its Velocity templates.
- Schemas are JSON and may carry arbitrary string-valued user properties; the spec does not restrict their content.
- Generation is optional — the dynamic GenericData path is not affected.
- The IDL layer (`@java-class`, `@java-key-class`, `@logicalType`, etc.) is a thin wrapper that produces ordinary JSON schema properties; an IDL `@javaAnnotation("…")` becomes a regular `javaAnnotation` JSON string property on the resulting schema. Any sanitization must therefore happen in `SpecificCompiler`, not in the IDL parser.
