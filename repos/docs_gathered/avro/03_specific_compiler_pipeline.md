# 03 — The SpecificCompiler Pipeline: Walking the Taint Flow

## Sources

- `https://github.com/apache/avro/commit/84bc7322ca1c04ab4a8e4e708acf1e271541aac4` — the AVRO-4053 fix commit. Eight files changed; six are the pipeline files mentioned below. The diff was inspected end-to-end.
- `https://github.com/apache/avro/blob/main/lang/java/compiler/src/main/java/org/apache/avro/compiler/specific/SpecificCompiler.java` — the compiler source.
- `https://github.com/apache/avro/tree/main/lang/java/compiler/src/main/velocity/org/apache/avro/compiler/specific/templates/java/classic` — the templates.
- `https://github.com/apache/avro/blob/main/lang/java/compiler/src/test/java/org/apache/avro/compiler/specific/TestSpecificCompiler.java` — the test class where `docsAreEscaped_avro4053` was added.
- `https://avro.apache.org/docs/1.12.0/specification/` — verifies which schema attributes are spec-defined (`name`, `namespace`, `aliases`, `doc`, `order`, `default`) vs. arbitrary user properties (`javaAnnotation` and friends).

## Eight Files in the Fix

The AVRO-4053 commit (`84bc7322`) touched exactly eight files. Reading them in pipeline order — i.e., from "where the untrusted string enters" to "where the file is written to disk" — gives the taint flow.

| Stage | File | What it does | What changed |
|---|---|---|---|
| 0 | `simple_record.avsc` (test resource) | Test fixture. The fix added comment-breakout payloads to a `doc` field. | `+/- 7 lines`. A schema that proves the patch works against the obvious exploits. |
| 1 | `SpecificCompiler.java` | Owns the schema, exposes helpers to Velocity. | `+56 / -29`. The `isValidAsAnnotation` validator, the `VALID_AS_ANNOTATION` regex, `escapeForJavaString` rename of `javaEscape`, and `javaAnnotations` is gated. |
| 2 | `record.vm` | Renders generated record classes. | `+16 / -16`. Sixteen `$field.doc()` / `$schema.getDoc()` raw substitutions wrapped in `$this.escapeForJavadoc(...)`. The `SCHEMA$` literal switched to `escapeForJavaString`. |
| 3 | `enum.vm` | Renders generated enums. | `+2 / -2`. `/** $schema.getDoc() */` -> `/** $this.escapeForJavadoc($schema.getDoc()) */`; `SCHEMA$` literal switched to `escapeForJavaString`. |
| 4 | `fixed.vm` | Renders generated fixed-length types. | `+2 / -2`. Same pattern as `enum.vm`. |
| 5 | `protocol.vm` | Renders generated protocol interfaces. | `+4 / -4`. Four `$protocol.getDoc()` / `$p.doc()` raw substitutions wrapped. |
| 6 | `TestSpecificCompiler.java` (compiler module) | Adds the regression test. | `+65 / -16`. Includes `docsAreEscaped_avro4053`. |
| 7 | `TestSpecificCompiler.java` (ipc module) | Adjusts an existing test that was relying on raw doc emission. | `+3 / -2`. |

## The Pipeline, Stage by Stage

### Stage 1 — Schema enters the compiler

`new SpecificCompiler(schema)` (or `new SpecificCompiler(protocol)`) stores the parsed `Schema` / `Protocol`. The Schema object's `getDoc()`, `getName()`, `getNamespace()`, `getProp(...)`, `getObjectProp(...)`, `getFields()`, `getEnumSymbols()` accessors all return whatever was in the JSON, lightly typed. Properties that the spec calls out as reserved (`type`, `name`, `namespace`, `fields`, `symbols`, `items`, `values`, `size`, `aliases`, `doc`, `order`, `default`, `logicalType`) are bound to typed accessors; everything else lives in `JsonProperties` and is reachable via `getObjectProp(String)`.

`javaAnnotation` is one such non-spec property. The Avro JSON spec never mentions it. It's a Java-binding convention. The IDL spec does mention it indirectly: any `@<identifier>(value)` annotation in `.avdl` that isn't one of the known IDL annotations (`@order`, `@namespace`, `@aliases`, `@java-class`, `@java-key-class`, `@logicalType`) becomes a JSON property on the resulting schema, and a property named `javaAnnotation` reaches `SpecificCompiler` as-is.

**Taint point 1:** `props.getObjectProp("javaAnnotation")` in `javaAnnotations(JsonProperties)`. This returns either a `String`, a `List`, or `null`. Both string and list values are user-controlled.

**Taint point 2:** `$schema.getDoc()`, `$field.doc()`, `$protocol.getDoc()`, `$message.getDoc()`, `$p.doc()` in the Velocity templates. The `doc` field is spec-defined but arbitrary in content — a free-form documentation string.

**Taint point 3:** `$schema.toString()` rendered into `SCHEMA$`. This contains the full schema JSON, including any names, doc strings, and properties.

### Stage 2 — Velocity rendering

The compiler instantiates a Velocity engine and renders the appropriate template per named type. The template uses `$this.<helper>(...)` to call back into `SpecificCompiler` whenever it needs a value computed against the schema. The CVE-relevant call sites are:

- **`$this.javaAnnotations($schema)`** — pulls the `javaAnnotation` property, post-fix routes each value through `isValidAsAnnotation`.
- **`$this.javaAnnotations($field)`** — per-field variant; same gating.
- **`$this.escapeForJavadoc(...)`** — post-fix wrapper for every doc-string substitution. (Pre-fix many of these were raw `$field.doc()`.)
- **`$this.escapeForJavaString(...)`** — used inside `"…"` Java string literals; pre-fix named `$this.javaEscape(...)`.
- **`$this.mangle(...)` / `$this.mangleTypeIdentifier(...)`** — produce valid Java identifiers from schema names. Not part of the CVE because these already enforce identifier syntax.
- **`$this.javaType(...)` / `$this.javaUnbox(...)`** — produce the Java type name for a schema. Not the CVE surface either, but post-fix the templates wrap the *output* of `javaType` in `escapeForJavadoc` when it's embedded in Javadoc `<>` generics — defensive against logical types whose names contain `>`.

### Stage 3 — String/file emission

Velocity writes to a `StringWriter`; the compiler writes the `StringWriter` content to disk as `<Namespace path>/<TypeName>.java` under `outputDir`. **At this point the file content is already constructed.** Any sanitization that was going to happen had to happen upstream. There is no post-emit pass — no `javac` lint, no source linter, no review hook. If a `*/` slipped through a `doc` field, it's now in the `.java` file. If a `@Foo public static { … }` slipped through `javaAnnotation`, it's now in the `.java` file. The next step is `javac`, which will compile the file as-is.

This is why the fix must be at the helper level. Anything else would be too late.

## Where Untrusted Strings Flow (audit checklist)

For a given version of the compiler, QPB needs to confirm three things:

1. **Every Velocity template substitution that pulls a schema string passes through a helper.** Grep all four `.vm` files for `$schema.`, `$field.`, `$protocol.`, `$p.`, `$message.`, `$error.` and confirm each match is one of:
   - Wrapped in `$this.mangle(...)`, `$this.mangleTypeIdentifier(...)`, `$this.javaType(...)`, `$this.javaUnbox(...)`, `$this.fingerprint64(...)` (identifier/type/numeric — safe).
   - Wrapped in `$this.escapeForJavadoc(...)` (Javadoc context — safe post-fix).
   - Wrapped in `$this.escapeForJavaString(...)` or `$this.javaEscape(...)` (Java string literal context — safe).
   - Coming from `$this.javaAnnotations(...)` (annotation context — safe post-fix only).
   - A primitive structural fragment that doesn't contain user data (e.g., `$foreach.hasNext`, `$schema.isError()` — safe).

2. **`javaAnnotations` has the `isValidAsAnnotation` gate.** Spot-check `SpecificCompiler.java` for `props.getObjectProp("javaAnnotation")`; the next ~20 lines must include `isValidAsAnnotation(...)` guards on both the `instanceof String` branch and the `instanceof List` foreach.

3. **`VALID_AS_ANNOTATION` regex exists and looks like the canonical form.** It composes `PATTERN_IDENTIFIER`, `PATTERN_PARAMETER_LIST`, `PATTERN_LITERAL_VALUE`, `PATTERN_STRING`, `PATTERN_NUMBER`, `PATTERN_IDENTIFIER_PART`. Absence of these constants in a 1.12.0 codebase is itself the smoking gun for the vulnerable version.

## The Regression Test (canonical pin)

The test added in the fix is `docsAreEscaped_avro4053` in `lang/java/compiler/src/test/java/org/apache/avro/compiler/specific/TestSpecificCompiler.java`. (Per the PR title and the file in the commit's file tree.) Its inputs include the modified `simple_record.avsc` resource file, which contains a `doc` field with `*/` and other Javadoc-breakout characters. The test compiles the schema and asserts:

- The generated Java source is valid (compiles with `javac`).
- The generated Javadoc contains the doc string in escaped form, not as a literal `*/` that would close the comment.

QPB can use the presence/absence of this test in a tree as a direct version oracle: pre-fix trees lack it; post-fix trees have it.

## Common Misreadings (worth flagging to QPB)

- **AVRO-4053's Jira title is misleading.** The Jira ticket reads "Improve doc consistency in SpecificRecord" and the description says "The documentation in generated SpecificRecord classes is inconsistent between messages, protocols, named types and fields. Let's use the format for messages everywhere." That sounds like a cosmetic Javadoc-consistency cleanup. The actual fix is also a security patch — the consistency change *is* the security fix, because making every doc-substitution use `escapeForJavadoc` closes the comment-breakout vector. The CVE assignment came later (CVE-2025-33042 was published Feb 2026, well after the commit landed). QPB should not be fooled by the soft-pitched Jira summary.
- **The PR title is similarly soft-pitched** ("AVRO-4053: doc consistency in velocity templates") and most of the review discussion in PR #3150 is about Java import sort order, not about the security implications. The reviewer (RyanSkraba) does say "I haven't quite finished thoroughly reviewing that Regex construction" — i.e., the `VALID_AS_ANNOTATION` regex *was* recognized as the load-bearing piece, but the security framing isn't in the public PR record. The bulk of the conversation is on style.
- **The `javaEscape` -> `escapeForJavaString` rename is not a behavior change.** They're identical; `javaEscape` is preserved as a `@Deprecated(since = "1.12.1", forRemoval = true)` alias. So a checker that flags "missing `javaEscape` call" in a 1.12.1+ template would be wrong — the template now correctly calls `escapeForJavaString`.

## Invariants

- The taint flow is **schema property -> `SpecificCompiler` helper -> Velocity `$variable` substitution -> string buffer -> `.java` file -> `javac`**. The only intervention point that scales (across template sites, across schemas, across both JSON and IDL inputs) is the helper.
- Three helpers must exist and be consistently used: `isValidAsAnnotation` (gating `javaAnnotation` values), `escapeForJavadoc` (wrapping every doc emission), `escapeForJavaString` / `javaEscape` (wrapping every Java string literal). All three are visible in the post-fix `SpecificCompiler.java`.
- Absence of `isValidAsAnnotation` is the definitive vulnerability marker for the `javaAnnotation` injection. Absence of `escapeForJavadoc` (or its inconsistent use across the four templates) is the marker for the `doc` injection.
- Regression test `docsAreEscaped_avro4053` is the canonical pin; presence implies the fix has landed in that tree.
