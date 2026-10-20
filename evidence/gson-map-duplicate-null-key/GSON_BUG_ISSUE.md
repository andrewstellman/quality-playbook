# Title

Map deserialization silently accepts duplicate keys when first value is null

# Body

## Gson version

2.13.3-SNAPSHOT (current `main` branch, commit as of 2026-04-03). Also affects all prior versions back to 2.4 when the duplicate-key check was introduced in PR #649.

## Java / Android version

Reproduced on OpenJDK 21.0.6 (macOS aarch64). Not platform-specific.

## Description

`MapTypeAdapterFactory` detects duplicate keys during map deserialization using:

```java
V replaced = map.put(key, value);
if (replaced != null) {
    throw new JsonSyntaxException("duplicate key: " + key);
}
```

This fails when the **first** occurrence of a duplicate key maps to `null`. `Map.put()` returns the previous value, which is `null`, so `replaced != null` evaluates to `false` and the duplicate is silently accepted. The second value overwrites the first with no exception.

The bug exists in both code paths — object form (line ~204) and array-of-entries form (line ~191).

## Expected behavior

`gson.fromJson("{\"a\":null,\"a\":1}", type)` should throw `JsonSyntaxException("duplicate key: a")`, the same as `gson.fromJson("{\"a\":1,\"a\":2}", type)` does.

## Actual behavior

`gson.fromJson("{\"a\":null,\"a\":1}", type)` silently returns `{a=1}` with no exception.

## Reproduction

```java
import com.google.gson.Gson;
import com.google.gson.JsonSyntaxException;
import com.google.gson.reflect.TypeToken;
import java.lang.reflect.Type;
import java.util.Map;

public class DuplicateKeyNullBug {
    public static void main(String[] args) {
        Gson gson = new Gson();
        Type type = new TypeToken<Map<String, Integer>>() {}.getType();

        // Works correctly: throws JsonSyntaxException("duplicate key: a")
        try {
            gson.fromJson("{\"a\":1,\"a\":2}", type);
        } catch (JsonSyntaxException e) {
            System.out.println("Non-null first value: correctly threw " + e.getMessage());
        }

        // Bug: silently returns {a=1}
        try {
            Map<String, Integer> result = gson.fromJson("{\"a\":null,\"a\":1}", type);
            System.out.println("Null first value: no exception, returned " + result);
        } catch (JsonSyntaxException e) {
            System.out.println("Null first value: correctly threw " + e.getMessage());
        }
    }
}
```

Output:
```
Non-null first value: correctly threw duplicate key: a
Null first value: no exception, returned {a=1}
```

The bug also affects string values, both-null cases, and the array-of-entries form with `enableComplexMapKeySerialization()`.

## Failing test

Added to `MapTest.java`:

```java
@Test
public void testMapDeserializationWithDuplicateKeysNullFirstValue() {
    Type type = new TypeToken<Map<String, Integer>>() {}.getType();
    var e = assertThrows(JsonSyntaxException.class,
        () -> gson.fromJson("{\"a\":null,\"a\":1}", type));
    assertThat(e).hasMessageThat().isEqualTo("duplicate key: a");
}
```

Result: `expected com.google.gson.JsonSyntaxException to be thrown, but nothing was thrown`

## Root cause

`MapTypeAdapterFactory.Adapter.read()` uses `map.put(key, value)` return value to detect duplicates. `Map.put()` returns the **previous** value for the key, or `null` if there was no mapping. But `null` return also occurs when the previous value **was** `null`. The check `if (replaced != null)` cannot distinguish "no previous mapping" from "previous mapping to null".

Gson's `LinkedTreeMap` (used for `Map<String, ...>`) allows null values by default (`allowNullValues = true` in the no-arg constructor), so `put("a", null)` stores the null value. The subsequent `put("a", 1)` returns `null` (the previous value), and the check passes without throwing.

The existing tests (`testMapDeserializationWithDuplicateKeys` and `testTwoTypesCollapseToOneDeserialize`) both use non-null first values, so this edge case was never covered.

## Suggested fix

In `MapTypeAdapterFactory.java`, at both duplicate-key checks (object form and array-of-entries form), replace:

```java
V replaced = map.put(key, value);
if (replaced != null) {
    throw new JsonSyntaxException("duplicate key: " + key);
}
```

with:

```java
V replaced = map.put(key, value);
if (replaced != null || map.containsKey(key)) {
    throw new JsonSyntaxException("duplicate key: " + key);
}
```

`map.containsKey(key)` returns `true` when the key exists regardless of whether its value is `null`, so this catches both null and non-null duplicates. Note: the `replaced != null` short-circuit means `containsKey` is only called in the null-replaced case, so there is no performance impact for the common (non-null) path.

I'm happy to submit a PR with the fix and tests if that would be helpful.
