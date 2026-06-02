# 04 — Invariants for Detecting Code-Injection / Unsafe-Code-Generation Failures

## Sources

- `https://avro.apache.org/project/security/` — Apache Avro security policy.
- `https://github.com/apache/avro/commit/[REDACTED]` — the [REDACTED] fix commit.
- `https://github.com/apache/avro[REDACTED]` — the PR; includes maintainer discussion confirming the regex was the load-bearing piece.
- `https://github.com/advisories/[REDACTED]` — the GitHub Security Advisory for [REDACTED] ([REDACTED], Improper Control of Generation of Code).
- `https://avro.apache.org/docs/1.12.0/specification/` — Avro spec; defines what is a reserved property vs. an arbitrary user property.

## Synthesizing the Invariants

The invariants below are derived directly from (a) the [REDACTED] patch, which shows the exact methods/sites that needed to change; (b) the Apache Avro security policy's statement that "if schemas are user provided, validate the parsed schema before use"; and (c) the [REDACTED] classification.

Phrased as audit checks, they should be straightforward to mechanize.

---

### Invariant CG-1: Generated code must never embed unvalidated schema strings

**Statement.** No string lifted from a parsed Avro schema may reach a code-generation output stream without first passing through a context-appropriate sanitizer.

**Why.** This is the canonical [REDACTED] invariant. Avro's security policy classifies schemas as untrusted supply-chain input; codegen must enforce that.

**Where to check.** `lang/java/compiler/src/main/java/org/apache/avro/compiler/specific/SpecificCompiler.java` and the four Velocity templates in `lang/java/compiler/src/main/velocity/.../templates/java/classic/{enum,fixed,protocol,record}.vm`.

**Smoking-gun pattern (vulnerable form).** A Velocity template line of the shape:

```velocity
/** $schema.getDoc() */
```

or

```velocity
* @param ${this.mangle($p.name())} $p.doc()
```

— i.e., a `$schema.getDoc()` / `$field.doc()` / `$protocol.getDoc()` / `$p.doc()` / `$message.getDoc()` substitution **not** wrapped in `$this.escapeForJavadoc(...)`.

**Safe pattern (post-fix form).**

```velocity
/** $this.escapeForJavadoc($schema.getDoc()) */
* @param ${this.mangle($p.name())} $this.escapeForJavadoc($p.doc())
```

---

### Invariant CG-2: All template substitutions must escape for their lexical context

**Statement.** Every `$variable` substitution in a Velocity template must either be a structurally-safe value (a Java identifier produced by `mangle`/`mangleTypeIdentifier`, a numeric constant, a fingerprint) or must be wrapped in a helper appropriate for its surrounding lexical context.

The three lexical contexts in the templates are:

| Context | Wrap with | What it protects |
|---|---|---|
| Inside a Javadoc comment (`/** … */` or `* …`) | `$this.escapeForJavadoc(...)` | `*/` breakout, `@tag` injection |
| Inside a Java string literal (`"…"`) | `$this.escapeForJavaString(...)` (or the deprecated alias `$this.javaEscape(...)`) | `"` and `\` breakout |
| Annotation literal (`@$annotation`) | `$this.javaAnnotations(...)` (which now applies `[REDACTED]`) | full Java syntax injection |

**Where to check.** The four templates and any other `.vm` file that gets added to `lang/java/compiler/src/main/velocity/`. Also any future templates under non-`classic` template directories — the fix only covers `classic`; future template families would need parallel coverage.

**Audit mechanism.** Grep each `.vm` file for the substitution markers `$schema.`, `$field.`, `$protocol.`, `$p.`, `$message.`, `$error.`. For each match, confirm the surrounding context and the wrapping helper match the table above.

**Known exemptions.** Mangled identifiers from `$this.mangle(...)` and type names from `$this.javaType(...)` are safe by construction. `$schema.isError()`, `$schema.isNullable()`, `$foreach.hasNext`, etc. are boolean/control-flow values, not strings — safe.

---

### Invariant CG-3: `javaAnnotation` values must match `VALID_AS_ANNOTATION`

**Statement.** Any `javaAnnotation` schema property — whether a single string or a list of strings — must be validated against the `VALID_AS_ANNOTATION` regex before being emitted into generated Java source. Values that fail validation must be silently dropped.

**Why this specific regex.** Java annotation syntax is a tight subset of Java: a dotted identifier optionally followed by a parenthesized list of literals or `name=literal` pairs. Whitelist-validating to that grammar makes injection impossible while preserving every legal use. The maintainers explicitly chose silent-drop over throw; QPB should note this and decide whether the deployment under audit prefers fail-closed.

**Where to check.** `SpecificCompiler.java`:

```java
public String[] javaAnnotations(JsonProperties props) {
  final Object value = props.getObjectProp("javaAnnotation");
  if (value instanceof String && [REDACTED]((String) value))   // <- the gate
    return new String[] { value.toString() };
  if (value instanceof List) {
    ...
    for (Object o : list) {
      if ([REDACTED](o.toString()))                              // <- the gate
        annots.add(o.toString());
    }
    ...
  }
  return new String[0];
}
```

The `VALID_AS_ANNOTATION` `Pattern` constant must be defined and used by `[REDACTED]`:

```java
private static final Pattern VALID_AS_ANNOTATION = Pattern.compile(
    String.format("%s(?:%s)?", PATTERN_IDENTIFIER, PATTERN_PARAMETER_LIST));

private boolean [REDACTED](String value) {
  return VALID_AS_ANNOTATION.matcher(value.strip()).matches();
}
```

**Smoking-gun pattern (vulnerable form).** `annots.add(o.toString())` without a guard, or `return new String[] { value.toString() }` directly on the `instanceof String` branch.

---

### Invariant CG-4: `doc` strings must pass through `escapeForJavadoc` at every emission point

**Statement.** Every place a template renders a `doc` string — class-level, field-level, method-level, parameter-level, return-value-level — must wrap the value in `$this.escapeForJavadoc(...)`.

**Why.** The `doc` field is spec-defined and arbitrary in content; it can carry `*/`, `@param`, or any other character. The pre-fix templates emit it raw, which permits Javadoc-comment-breakout [REDACTED].

**Where to check.** The four templates. The fix touched fifteen distinct emission sites in `record.vm` alone (see Section 02). Spot-check by grepping each template for any reference to `$schema.getDoc()`, `$field.doc()`, `$protocol.getDoc()`, `$message.getDoc()`, `$p.doc()` and confirming each is wrapped.

**Smoking-gun pattern.** Any of those substitutions appearing outside an `escapeForJavadoc(...)` call.

---

### Invariant CG-5: Embedded schema JSON in `SCHEMA$` must use `escapeForJavaString`

**Statement.** The `SCHEMA$` constant in every generated type embeds the schema's JSON form as a Java string literal. That literal must use `escapeForJavaString` (or the deprecated alias `javaEscape`) to escape backslashes and double quotes; nothing weaker.

**Where to check.** Search `.vm` files for `Schema.Parser().parse(` and confirm the argument is `"${this.escapeForJavaString($schema.toString())}"` (post-fix) or `"${this.javaEscape($schema.toString())}"` (pre-fix; semantically equivalent, deprecated).

**Smoking-gun pattern.** `"${$schema.toString()}"` or any raw substitution would be a critical bug; the patch is symmetric across `enum.vm`, `fixed.vm`, and `record.vm`.

---

### Invariant CG-6: Sanitization is centralized in helpers, not pushed to call sites

**Statement.** Sanitization helpers — `[REDACTED]`, `escapeForJavadoc`, `escapeForJavaString` — must be the *single* path through which schema strings reach generated output. Templates must not embed inline transformations.

**Why.** Centralization makes the audit tractable. Three helpers, ~50 lines of `SpecificCompiler.java`, four `.vm` files: that's the whole surface. If a template starts doing `$schema.getDoc().replace("*/", "*&#47;")` inline, the surface grows in places greppers won't find.

**Audit mechanism.** Grep each `.vm` file for `.replace(` and `.replaceAll(` — these should be empty or have benign matches (e.g., in `javaSplit`, which is a length-chunking utility, not a sanitizer).

---

### Invariant CG-7: Validation lives at codegen, not at schema parse

**Statement.** `Schema.Parser` must not be the location of the fix. The patch belongs in `SpecificCompiler` (and its templates), because the threat is contextual — it depends on the target language being Java — and the parser is shared across runtime and codegen consumers.

**Why this matters.** The Apache Avro security policy says parsing "itself is safe" and "the parser allows SPIs, but is not otherwise configurable." Moving validation into the parser would either reject schemas that have legal-but-quirky doc strings (breaking the runtime/GenericData path that doesn't need any of this) or fail to catch IDL-sourced `javaAnnotation` values that arrive through a parallel codepath.

**Audit mechanism.** If a future fix attempt is proposed that lives in `Schema.Parser` rather than `SpecificCompiler`, that's a signal something is being routed around. Confirm `SpecificCompiler` carries the gate.

---

### Invariant CG-8: The regression test `docsAreEscaped_avro4053` exists

**Statement.** `lang/java/compiler/src/test/java/org/apache/avro/compiler/specific/TestSpecificCompiler.java` must contain a test named `docsAreEscaped_avro4053` (or its equivalent successor), which feeds a schema with a Javadoc-breakout `doc` value through `SpecificCompiler` and asserts the output is well-formed.

**Why.** Tests are the version pin. The test name carries the Jira ID, so it's discoverable even after refactors. Absence of a test that names [REDACTED] in a 1.12.x tree means either the fix never landed there or the test was removed.

**Audit mechanism.** Grep `TestSpecificCompiler.java` for `avro4053` (case-insensitive). Present -> patched; absent -> suspect.

---

## Cross-Invariant Summary

| Invariant | Where it lives | Greppable signal |
|---|---|---|
| CG-1 (no unvalidated string) | All eight files | `$.+\.getDoc()` / `$.+\.doc()` / `$.+\.getName()` substitutions outside helpers |
| CG-2 (lexical-context escaping) | The four `.vm` files | `$schema.`, `$field.`, `$protocol.`, `$p.`, `$message.` matches in each template |
| CG-3 (annotation regex) | `SpecificCompiler.java` | `VALID_AS_ANNOTATION`, `[REDACTED]`, `PATTERN_IDENTIFIER` |
| CG-4 (Javadoc escaping) | The four `.vm` files | `$this.escapeForJavadoc(` count vs. raw `.doc()` references |
| CG-5 (Java string escaping) | `enum.vm`, `fixed.vm`, `record.vm` | `escapeForJavaString` or `javaEscape` around `$schema.toString()` |
| CG-6 (centralized helpers) | The four `.vm` files | `.replace(` / `.replaceAll(` inside templates |
| CG-7 (codegen, not parser) | Diff between `lang/java/avro/` and `lang/java/compiler/` | Sanitization changes in `Schema.Parser` (none expected) |
| CG-8 (regression test) | `TestSpecificCompiler.java` | `avro4053` test method |

A QPB invariant-driven sweep that checks these eight will catch the [REDACTED] vulnerable form, the patched form, and the most likely future regressions (e.g., a new template family added without parallel escaping, a new schema property added without parallel gating).
