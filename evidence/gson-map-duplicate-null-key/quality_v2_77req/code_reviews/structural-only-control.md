# Structural-only review

This review was performed **without** reading `quality/REQUIREMENTS.md`, **without** reading `quality/RUN_CODE_REVIEW.md`, and **without** using any multi-pass review protocol. It is a structural-only review of the core Gson source for comparison against the three-pass review.

## Findings

### 1. `byte` and `short` deserialization silently wrap unsigned-range inputs into negative Java values
- **File and lines:** `gson/src/main/java/com/google/gson/internal/bind/TypeAdapters.java:189-245`
- **Severity:** High
- **Confidence:** High
- **Issue:** The built-in `BYTE` adapter accepts values up to `255` and then returns `(byte) intValue`; the `SHORT` adapter accepts values up to `65535` and then returns `(short) intValue`. In Java those casts wrap, so JSON like `200` deserializes to `-56` for `byte`, and `65535` deserializes to `-1` for `short`. The adapters are explicitly labeled as lossy-checking code, but they permit values that cannot be represented without corruption.

### 2. Duplicate-key detection for `Map` deserialization is bypassed when the previous value is `null`
- **File and lines:** `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java:191-193`, `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java:204-206`
- **Severity:** High
- **Confidence:** High
- **Issue:** Duplicate detection uses `V replaced = map.put(key, value); if (replaced != null) ...`. For maps that allow `null` values, `put` returns `null` both when the key was absent and when the key already existed with a `null` value. That means a JSON object like `{"k":null,"k":1}` slips past the duplicate-key guard and silently overwrites the earlier entry.

### 3. Anonymous and non-static local classes are silently serialized/deserialized as `null`
- **File and lines:** `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java:117-139`
- **Severity:** High
- **Confidence:** High
- **Issue:** For anonymous and non-static local classes, Gson installs an adapter that always calls `in.skipValue(); return null;` on read and `out.nullValue();` on write. This is total data loss with no error signal to the caller. A user can round-trip a value and get `null` back even though the operation appeared to succeed.

### 4. Parsing into `JsonObject` / untyped `Object` silently overwrites duplicate JSON member names
- **File and lines:** `gson/src/main/java/com/google/gson/JsonObject.java:69-70`, `gson/src/main/java/com/google/gson/internal/bind/JsonElementTypeAdapter.java:110-114`, `gson/src/main/java/com/google/gson/internal/bind/ObjectTypeAdapter.java:142-145`
- **Severity:** Medium
- **Confidence:** High
- **Issue:** `JsonObject.add` is a plain `members.put(...)`, and both the tree parser and `Object` parser feed object members straight into that overwrite behavior. As a result, duplicate names in JSON are silently collapsed to the last value when parsing into `JsonElement` or `Object`, which loses input data and makes duplicate-key handling inconsistent with `MapTypeAdapterFactory`, which at least tries to reject duplicates.

### 5. Date-only ISO-8601 strings are parsed in the JVM default timezone instead of UTC
- **File and lines:** `gson/src/main/java/com/google/gson/internal/bind/util/ISO8601Utils.java:175-183`, `gson/src/main/java/com/google/gson/internal/bind/util/ISO8601Utils.java:283-294`
- **Severity:** Medium
- **Confidence:** High
- **Issue:** The date-only path (`yyyy-MM-dd`) creates `new GregorianCalendar(year, month - 1, day)`, which uses the JVM default timezone, while date-time inputs with an explicit offset use a calendar constructed from the parsed timezone. That means `"2023-06-01"` and `"2023-06-01T00:00:00Z"` produce different `Date` instants on non-UTC JVMs, causing silent timezone-dependent behavior for logically equivalent inputs.

### 6. ISO-8601 date parsing accepts trailing garbage after a valid timestamp
- **File and lines:** `gson/src/main/java/com/google/gson/internal/bind/util/ISO8601Utils.java:293`, `gson/src/main/java/com/google/gson/internal/bind/DefaultDateTypeAdapter.java:181-183`
- **Severity:** Medium
- **Confidence:** High
- **Issue:** `ISO8601Utils.parse` records the stopping position in `ParsePosition`, but `DefaultDateTypeAdapter` never checks that the entire input string was consumed. A string like `2023-01-15T00:00:00Zjunk` can therefore be accepted as a valid `Date`, which is an input-validation gap and can hide malformed or concatenated data.

### 7. `BOOLEAN_AS_STRING` turns a `null` Boolean key into `false` on round-trip
- **File and lines:** `gson/src/main/java/com/google/gson/internal/bind/TypeAdapters.java:169-183`
- **Severity:** Medium
- **Confidence:** High
- **Issue:** `BOOLEAN_AS_STRING.write` serializes a `null` Boolean as the JSON string `"null"`, but `read` deserializes that string with `Boolean.valueOf(...)`, which returns `false`. This means a `null` Boolean key does not round-trip and is silently corrupted into `false`.
