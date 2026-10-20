---
source: https://github.com/google/gson/issues/2295
retrieved: 2026-04-03
type: github_issue
description: Strict mode for JSON parsing
---

# Issue #2295: Strict mode for JSON parsing

## Status
**Closed** — Implemented in Gson 2.11.0 via PR #2323

## Description

Despite having a `setLenient(boolean)` method, Gson's "strict" mode (lenient=false) was not actually strict. The parser accepted several non-standard JSON formats that violate RFC 8259:

1. **Case-insensitive boolean/null literals** — `true`, `false`, `null` could be written as `True`, `FALSE`, `Null`, etc.
2. **Non-standard escape sequences** — `\'` (single quote escape) and `\<LF>` (line feed escape) were accepted even though they're not valid in JSON
3. **Unescaped control characters** — Control characters (ASCII 0-31) in strings were accepted without escaping

These lenient behaviors were useful for some applications but made it impossible to strictly validate JSON compliance.

## Problem

Developers who needed strict RFC 8259 compliance had no way to enforce it. The parser would:
- Accept `{true: 1}` even though JSON requires boolean keys to be strings
- Accept `"line1\<LF>line2"` even though unescaped line feeds are not allowed
- Accept `"control\u0000char"` without proper escaping

This meant that code using `setLenient(false)` might still accept invalid JSON by strict standards.

## Solution: Strictness Enum

PR #2323 introduced a new `Strictness` enum with three levels to replace the simple boolean `setLenient()` method:

### 1. LENIENT
Maximum flexibility, accepts non-standard JSON:
- Case-insensitive boolean/null literals (`True`, `False`, `Null`)
- Non-standard escape sequences (`\'`, `\<LF>`)
- Unescaped control characters in strings
- Single-quoted strings
- Trailing commas in arrays/objects
- Comments (// and /* */)

### 2. DEFAULT (new in 2.11.0)
Balanced approach, reasonable compatibility:
- Strict RFC 8259 compliance for the JSON structure itself
- But allows some lenient behaviors for broader compatibility
- This becomes the new default behavior

### 3. STRICT
Full RFC 8259 compliance:
- All non-standard behaviors rejected
- Boolean/null must be lowercase: `true`, `false`, `null`
- Only standard escape sequences allowed
- Control characters must be properly escaped
- No trailing commas
- No comments

## API Usage

The new Strictness enum is available on three classes:

### GsonBuilder
```java
Gson strictGson = new GsonBuilder()
    .setStrictness(Strictness.STRICT)
    .create();

Gson lenientGson = new GsonBuilder()
    .setStrictness(Strictness.LENIENT)
    .create();

Gson defaultGson = new GsonBuilder()
    .setStrictness(Strictness.DEFAULT)
    .create();
```

### JsonReader
```java
JsonReader reader = new JsonReader(inputStream);
reader.setStrictness(Strictness.STRICT);
// Parse JSON with strict RFC 8259 compliance
```

### JsonWriter
```java
JsonWriter writer = new JsonWriter(outputStream);
writer.setStrictness(Strictness.STRICT);
// Generate strictly valid JSON
```

## Examples of Behavior Differences

### Example 1: Boolean Literals
```java
String json = "{\"valid\": True}";  // Note: capital T

// With LENIENT: ✓ Accepted
JsonReader reader1 = new JsonReader(new StringReader(json));
reader1.setStrictness(Strictness.LENIENT);
// Reads successfully

// With STRICT: ✗ Rejected
JsonReader reader2 = new JsonReader(new StringReader(json));
reader2.setStrictness(Strictness.STRICT);
// Throws JsonSyntaxException: "Illegal character 'T'"
```

### Example 2: Escape Sequences
```java
String json = "{\"message\": \"line1\\<LF>line2\"}";  // Unescaped LF

// With LENIENT: ✓ Accepted
// With STRICT: ✗ Rejected (unescaped control character)
```

### Example 3: Trailing Commas
```java
String json = "{\"items\": [1, 2, 3,]}";  // Trailing comma

// With LENIENT: ✓ Accepted
// With STRICT: ✗ Rejected
```

## Backward Compatibility

The change maintains backward compatibility in an important way:
- `setLenient(true)` is equivalent to `setStrictness(Strictness.LENIENT)`
- `setLenient(false)` is equivalent to `setStrictness(Strictness.DEFAULT)` (not STRICT!)
- The default behavior becomes slightly more lenient to match user expectations

This means existing code using `setLenient(false)` will continue to work but may still accept some non-standard JSON.

## Migration Guide

### For strict JSON validation:
```java
// Before: False hope of strictness
reader.setLenient(false);

// After: Actual RFC 8259 compliance
reader.setStrictness(Strictness.STRICT);
```

### For maximum compatibility:
```java
// Before
reader.setLenient(true);

// After (unchanged)
reader.setStrictness(Strictness.LENIENT);
```

## Implementation Details

The implementation involved:
1. Adding the Strictness enum with three levels
2. Updating JsonReader and JsonWriter to respect strictness levels
3. Modifying the lexer to enforce strict escape sequence rules
4. Adding validation for control characters in strings
5. Implementing case-sensitivity checks for boolean/null literals

## Impact on JSON Processing

### Security implications:
- Strict mode ensures JSON is compliant with standards, reducing attack surface
- Non-standard formats are explicitly rejected rather than silently accepted

### Performance:
- No significant performance difference between strictness levels
- Validation adds minimal overhead

### Compatibility:
- Applications expecting strict compliance can now enforce it
- Applications needing lenient parsing can use LENIENT explicitly

## RFC 8259 Compliance

RFC 8259 specifies:
- Boolean literals MUST be lowercase (`true`, `false`)
- Null literal MUST be lowercase (`null`)
- Strings MUST properly escape control characters
- Object keys MUST be strings
- No comments are allowed

Gson's STRICT mode now fully complies with RFC 8259.

## Use Cases

### STRICT mode appropriate for:
- REST API clients validating server responses
- Data import validation
- Security-sensitive JSON processing
- Standard compliance testing
- JSON Schema validation

### LENIENT mode appropriate for:
- Legacy data migration
- User-provided JSON (configuration files, user input)
- Backward compatibility with non-standard formats
- Exploratory/debug scenarios

## Version Information

- Introduced: Gson 2.11.0 (October 2024)
- Related PR: #2323
- Backward compatible: Yes (with caveats about strictness level equivalence)
