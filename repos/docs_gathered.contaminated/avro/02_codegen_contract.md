# 02 — The Codegen Contract: SpecificCompiler, Velocity Templates, Escape Helpers

## Sources

- `https://github.com/apache/avro/commit/[REDACTED]` — the [REDACTED] fix commit (8 files changed, +148 / -73). Verbatim diff inspected.
- `https://github.com/apache/avro[REDACTED]` — the PR that landed the fix (titled "[REDACTED]: doc consistency in velocity templates"). Includes the test name `docsAreEscaped_avro4053` and reviewer discussion.
- `lang/java/compiler/src/main/java/org/apache/avro/compiler/specific/SpecificCompiler.java` — the Java class under audit.
- `lang/java/compiler/src/main/velocity/org/apache/avro/compiler/specific/templates/java/classic/{enum,fixed,protocol,record}.vm` — the Velocity templates under audit.
- `https://avro.apache.org/docs/1.12.0/idl-language/` — IDL spec; documents that user annotations become arbitrary JSON properties (so `javaAnnotation` is reachable from both `.avsc` and `.avdl` paths).

## Where Codegen Lives

The Java SDK produces `SpecificRecord` classes via `org.apache.avro.compiler.specific.SpecificCompiler`. There are three normal entry points to it:

1. **`avro-tools compile`** — CLI: `java -jar avro-tools.jar compile schema input.avsc output/`.
2. **`avro-maven-plugin`** — Maven plugin under `lang/java/maven-plugin/`; invoked at build time, walks the schema source directories, calls `SpecificCompiler` per schema, writes generated `.java` under `target/generated-sources/`.
3. **Direct API use** — applications instantiate `SpecificCompiler` with a `Schema` or `Protocol` and call `compileToDestination(...)`. Rare but real.

In all three, the same Velocity templates are rendered and the same compiler helper methods are called. There is no separate "safe" path; the [REDACTED] fix sits between the schema and the templates and applies uniformly.

## How a Schema Property Becomes Generated Java

The flow, walked end-to-end against the fix commit:

1. **Schema parsing.** `Schema.Parser` reads the JSON and produces a `Schema` (or `Protocol`) object tree. Custom properties — anything not in the Avro reserved list (`type`, `name`, `namespace`, `fields`, `symbols`, `items`, `values`, `size`, `aliases`, `doc`, `order`, `default`, `logicalType`, etc.) — are stashed on the `Schema`/`Field`/`Protocol`/`Message` objects as `JsonProperties`. The string values are kept exactly as written. **No sanitization at parse time.**
2. **`SpecificCompiler` setup.** The compiler is constructed with the parsed schema. It owns the Velocity engine, the helper methods exposed to templates (`mangle`, `javaType`, `javaUnbox`, `javaAnnotations`, `escapeForJavadoc`, `escapeForJavaString`, formerly `javaEscape`), and configuration toggles (`gettersReturnOptional`, `createSetters`, `createOptionalGetters`, etc.).
3. **Template rendering.** For each named type in the schema, the appropriate Velocity template (`record.vm`, `enum.vm`, `fixed.vm`, or `protocol.vm`) is rendered. The templates pull values off the schema and stitch them into Java source. Two distinct kinds of substitution happen:
   - **Identifiers / structural fragments** — type names, field names, method names. These flow through `mangle(...)` / `mangleTypeIdentifier(...)`, which already enforce Java-identifier syntax. Not the CVE surface.
   - **Free-form strings lifted from the schema** — `doc`, `javaAnnotation`, the full schema JSON serialized into `SCHEMA$`. **This is the CVE surface.**
4. **File write.** Velocity renders to a `Writer`; the result is written out as a `.java` file under `outputDir`.

## The Three Free-Form String Surfaces (with the pre- and post-fix handling)

### Surface 1: `javaAnnotation` -> Java annotation literal in the class body

**Where it shows up in templates** — every named-type template calls `$this.javaAnnotations($schema)` to get back a list of annotation strings, then emits each as `@$annotation`:

```velocity
#foreach ($annotation in $this.javaAnnotations($schema))
@$annotation
#end
```

(From `enum.vm`, `fixed.vm`, `protocol.vm`, and `record.vm`. The pattern is the same in all four. `record.vm` also calls it per-field for field-level annotations.)

**Pre-fix `javaAnnotations` method** (from the diff, lines removed in the commit):

```java
public String[] javaAnnotations(JsonProperties props) {
  final Object value = props.getObjectProp("javaAnnotation");
  if (value == null) return new String[0];
  if (value instanceof String) return new String[] { value.toString() };
  if (value instanceof List) {
    final List<?> list = (List<?>) value;
    final List<String> annots = new ArrayList<>(list.size());
    for (Object o : list) {
      annots.add(o.toString());          // <-- verbatim toString, no validation
    }
    return annots.toArray(new String[0]);
  }
  return new String[0];
}
```

**Post-fix `javaAnnotations` method** (from the diff, lines added in the commit):

```java
public String[] javaAnnotations(JsonProperties props) {
  final Object value = props.getObjectProp("javaAnnotation");
  if (value instanceof String && [REDACTED]((String) value))
    return new String[] { value.toString() };
  if (value instanceof List) {
    final List<?> list = (List<?>) value;
    final List<String> annots = new ArrayList<>(list.size());
    for (Object o : list) {
      if ([REDACTED](o.toString()))
        annots.add(o.toString());        // <-- now gated
    }
    return annots.toArray(new String[0]);
  }
  return new String[0];
}
```

**The validator added by the fix** (verbatim from the diff):

```java
private static final String PATTERN_IDENTIFIER_PART =
    "\\p{javaJavaIdentifierStart}\\p{javaJavaIdentifierPart}*";
private static final String PATTERN_IDENTIFIER =
    String.format("(?:%s(?:\\.%s)*)", PATTERN_IDENTIFIER_PART, PATTERN_IDENTIFIER_PART);
private static final String PATTERN_STRING =
    "\"(?:\\\\[\\\\\"ntfb]|(?<!\\\\).)*\"";
private static final String PATTERN_NUMBER =
    "(?:\\((?:byte|char|short|int|long|float|double)\\))?[x0-9_.]*[fl]?";
private static final String PATTERN_LITERAL_VALUE =
    String.format("(?:%s|%s|true|false)", PATTERN_STRING, PATTERN_NUMBER);
private static final String PATTERN_PARAMETER_LIST = String.format(
    "\\(\\s*(?:%s|%s\\s*=\\s*%s(?:\\s*,\\s*%s\\s*=\\s*%s)*)?\\s*\\)",
    PATTERN_LITERAL_VALUE, PATTERN_IDENTIFIER,
    PATTERN_LITERAL_VALUE, PATTERN_IDENTIFIER, PATTERN_LITERAL_VALUE);
private static final Pattern VALID_AS_ANNOTATION = Pattern.compile(
    String.format("%s(?:%s)?", PATTERN_IDENTIFIER, PATTERN_PARAMETER_LIST));

private boolean [REDACTED](String value) {
  return VALID_AS_ANNOTATION.matcher(value.strip()).matches();
}
```

What the regex accepts: a dotted Java identifier (e.g., `Deprecated`, `org.junit.Test`, `com.example.Foo`), optionally followed by a parenthesized parameter list. The parameter list may be empty, a single literal value (string, number, or `true`/`false`), or a comma-separated list of `name = literal` pairs. Crucially, it does *not* allow nested expressions, method calls, the `+` operator, statement separators, or anything else that could be parsed as Java code outside of an annotation. Whitespace around the value is stripped (`value.strip()`) before matching.

What the regex rejects: anything with a `;`, a `{`, a `}`, a `=` not in the `name=value` form, a `+`, embedded code blocks, multiple annotations chained together, etc. So an attempted injection like `Deprecated public static { Runtime.getRuntime().exec("…"); } @Override` would fail the match and be silently dropped.

### Surface 2: `doc` -> Javadoc comment text

**Where it shows up in templates** — every place a schema/protocol/field doc string was emitted, the patch wrapped it in `$this.escapeForJavadoc(...)`. Pre-fix vs. post-fix examples from the diff:

| Template | Pre-fix (vulnerable) | Post-fix (escaped) |
|---|---|---|
| `record.vm` line 32 | `/** $schema.getDoc() */` | `/** $this.escapeForJavadoc($schema.getDoc()) */` |
| `record.vm` line 119 (per-field) | `/** $field.doc() */` | `/** $this.escapeForJavadoc($field.doc()) */` |
| `enum.vm` line 22 | `/** $schema.getDoc() */` | `/** $this.escapeForJavadoc($schema.getDoc()) */` |
| `fixed.vm` line 22 | `/** $schema.getDoc() */` | `/** $this.escapeForJavadoc($schema.getDoc()) */` |
| `protocol.vm` line 23 / 65 | `/** $protocol.getDoc() */` | `/** $this.escapeForJavadoc($protocol.getDoc()) */` |
| `protocol.vm` line 40 / 81 (per-param) | `* @param ${mangle($p.name())} $p.doc()` | `* @param ${mangle($p.name())} $this.escapeForJavadoc($p.doc())` |
| `record.vm` lines 158, 231, 241, 260, 272, 326, 405, 416, 427, 444, 455, 472, 486, 497 | `$field.doc()` raw | `$this.escapeForJavadoc($field.doc())` |

The pre-fix template embedded the raw doc string straight into a Javadoc block. A `doc` value containing `*/ public static { … } /*` would break out of the comment, inject arbitrary code, and reopen a comment to swallow the trailing `*/`. The patch routes every `doc` string through `escapeForJavadoc`, which (based on the existing utility, already present in the file before the patch) escapes the `*/` comment-end sequence with HTML entities, defanging the breakout.

(The diff also calls out `escapeForJavadoc` being applied to `javaType(...)` results inside generics like `Optional<${this.escapeForJavadoc(${this.javaType($field.schema())})}>` — that's belt-and-suspenders against a synthesized Java type name containing `>` characters from a logical type, not part of the CVE itself.)

### Surface 3: Embedded schema JSON in `SCHEMA$` -> Java string literal

**Where it shows up in templates** — every named-type template declares a `SCHEMA$` constant whose value is the schema's JSON serialization wrapped in a string literal:

```velocity
public static final org.apache.avro.Schema SCHEMA$ =
    new org.apache.avro.Schema.Parser().parse(
        "${this.javaEscape($schema.toString())}");
```

Pre-fix this used `javaEscape`. The patch renamed it to `escapeForJavaString` (keeping `javaEscape` as a deprecated alias for backwards source compatibility) and updated all three templates that use it (`enum.vm`, `fixed.vm`, and inside `record.vm`'s `SCHEMA$` block):

```velocity
public static final org.apache.avro.Schema SCHEMA$ =
    new org.apache.avro.Schema.Parser().parse(
        "${this.escapeForJavaString($schema.toString())}");
```

`escapeForJavaString` (pre-fix `javaEscape`) is straightforward — it escapes `\\` and `\"`:

```java
public static String escapeForJavaString(String o) {
  return o.replace("\\", "\\\\").replace("\"", "\\\"");
}

@Deprecated(since = "1.12.1", forRemoval = true)
public static String javaEscape(String o) {
  return escapeForJavaString(o);
}
```

This protects against schema content (names, doc strings, properties) being able to break out of the `"…"` string literal at template-render time. The rename is purely cosmetic — the behavior matches pre- and post-fix. But the rename matters as a QPB signal: any project pulling in 1.12.0 vs. 1.12.1 will see a method name change in the template-utility surface.

## What the Patch Doesn't Change

- The Velocity engine itself. No template autoescaping was turned on. Templates remain fully trusted; the discipline is "every external string passes through a helper before reaching `$variable` substitution."
- The schema parser. Parsed properties are still stored raw on the Schema object. The runtime/GenericData path doesn't need this fix because it never generates Java source.
- Failure handling. Invalid `javaAnnotation` values are silently dropped, not reported as a warning, error, or build failure. Silent-drop was the maintainers' call; a reasonable alternative would have been a `--strict` mode that throws.
- The Python / C / C# / etc. compilers under `lang/<other>/` — those don't generate Java, but they do generate code in their own languages and would need parallel audits. Out of scope for QPB's current hunt.

## Invariants

- **`javaAnnotation` values must pass `[REDACTED]` before being emitted.** `VALID_AS_ANNOTATION = PATTERN_IDENTIFIER (PATTERN_PARAMETER_LIST)?` — dotted Java identifier optionally followed by a parameterised list of literals or `name=literal` pairs. Anything else is silently dropped.
- **`doc` strings must pass through `escapeForJavadoc` at every Javadoc-emit site.** A pre-fix `/** $schema.getDoc() */` is a vulnerability; a post-fix `/** $this.escapeForJavadoc($schema.getDoc()) */` is the patched form. Spot-check by greping the templates for `$schema.getDoc()`, `$field.doc()`, `$protocol.getDoc()`, `$p.doc()`, `$message.getDoc()` — every match must be wrapped.
- **Embedded schema JSON in `SCHEMA$` must use `escapeForJavaString` (formerly `javaEscape`).** Any `"...${this.…($schema.toString())}..."` literal that calls anything else is suspect.
- **Templates must never `$variable`-substitute a raw schema string into a Java construct.** The audit pattern: for each `$variable` reference in a template, the variable must come from a helper that performs context-appropriate escaping/validation, not from a getter on the schema object directly. `${this.mangle(...)}`, `${this.escapeForJavadoc(...)}`, `${this.escapeForJavaString(...)}`, `${this.javaAnnotations(...)}` are safe; `$schema.getDoc()` / `$field.doc()` / `$protocol.getDoc()` / `$p.doc()` raw are not.
- **Sanitisation lives in `SpecificCompiler.java`, not in the schema parser.** Schemas may carry arbitrary string-valued properties; only the codegen path interprets them as Java source fragments.
