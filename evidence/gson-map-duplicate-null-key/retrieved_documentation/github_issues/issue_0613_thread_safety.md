---
source: https://github.com/google/gson/issues/613
retrieved: 2026-04-03
type: github_issue
description: Document that Gson instances are thread safe
---

# Issue #613: Document that Gson instances are thread safe

## Status
**Closed** — Completed in August 2015

## Description

Gson instances are thread-safe, but this critical property was not clearly documented in the library's official documentation or Javadoc. As a result, developers were unnecessarily concerned about thread safety and were creating new Gson instances for each thread or each serialization/deserialization operation.

This practice is both inefficient and unnecessary. Creating new Gson instances has overhead and prevents caching of expensive reflection-based type adapters and other internal metadata. The lack of clear documentation about thread safety led to widespread anti-patterns in production code.

## Key Insight

The Gson class does not maintain any state while invoking JSON operations. All state is either:
- Immutable configuration (set during construction via GsonBuilder)
- Local to the serialization/deserialization operation (stored in local variables and method parameters)

This stateless design is what enables thread-safe usage across multiple threads without synchronization.

## Resolution

The issue was resolved through two pull requests that improved documentation and added compile-time verification:

### PR #664 — JSR-305 Annotation
Added the `@ThreadSafe` annotation (from JSR-305) to the Gson class declaration. This provides:
- Compile-time checking with tools like FindBugs and IntelliJ IDEA
- Clear signal to developers that the class is thread-safe
- Machine-readable metadata about thread safety properties

### PR #685 — Javadoc Documentation
Enhanced the Gson class Javadoc with explicit statement about thread safety. The documentation now clearly states:

> "Gson instances are Thread-safe so you can reuse them freely across multiple threads."

## Implications

With this clarification, the recommended pattern became:

```java
// Anti-pattern (before clarification):
Gson gson = new Gson();  // New instance per thread
String json = gson.toJson(obj);

// Recommended pattern (after clarification):
static final Gson gson = new Gson();  // Shared instance
String json = gson.toJson(obj);
```

The shared instance approach provides:
- Better performance (fewer object allocations)
- Better resource utilization (shared type adapter caches)
- Simpler code
- Reduced memory footprint

## Impact on Existing Code

Once this documentation was available, many projects could simplify their code by:
1. Creating a single static final Gson instance at application startup
2. Reusing that instance across all threads
3. Removing unnecessary synchronization or thread-local storage wrappers

This was a significant optimization opportunity that required no code changes to Gson itself, only clarification of its existing properties.

## Best Practice

The recommended pattern is now:

```java
public class JsonUtils {
    private static final Gson GSON = new Gson();

    public static String toJson(Object obj) {
        return GSON.toJson(obj);
    }

    public static <T> T fromJson(String json, Class<T> type) {
        return GSON.fromJson(json, type);
    }
}
```

This pattern is safe for multi-threaded usage without any additional synchronization.
