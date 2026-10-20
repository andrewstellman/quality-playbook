---
source: https://github.com/google/gson/issues/2739
retrieved: 2026-04-03
type: github_issue
description: Class loading deadlock with JsonElementTypeAdapter
---

# Issue #2739: Class loading deadlock with JsonElementTypeAdapter

## Status
**Closed** — Completed, fixed in September 2024 via PR #2740

## Description

A critical class loading deadlock was discovered that could occur during Gson initialization in multi-threaded environments. The deadlock was introduced by PR #2727 and involved a circular dependency between the `TypeAdapters` class and the `JsonElementTypeAdapter` class during class loading.

This was a severe issue because:
1. It could cause the entire application to hang during startup
2. The deadlock occurred at the JVM class loading level, making it very difficult to work around
3. It only manifested in specific timing scenarios with multiple threads loading classes simultaneously
4. The fix required restructuring fundamental Gson class dependencies

## Deadlock Scenario

The deadlock occurred between two threads in this pattern:

```
Thread 1: Loads TypeAdapters class
├─ TypeAdapters static initializer executes
├─ Needs: JsonElementTypeAdapter (for static final field)
└─ Waits for: JsonElementTypeAdapter class lock

Thread 2: Loads JsonElementTypeAdapter class
├─ JsonElementTypeAdapter static initializer executes
├─ Needs: TypeAdapters (for static reference)
└─ Waits for: TypeAdapters class lock

Result: DEADLOCK (both threads waiting for each other)
```

The circular dependency was:
- `TypeAdapters` class had a static final field of type `JsonElementTypeAdapter`
- `JsonElementTypeAdapter` class referenced `TypeAdapters` in its initialization
- These initializations could occur in either order depending on which thread loaded which class first

## Root Cause Analysis

PR #2727 introduced changes that for backward compatibility needed:
1. Static final fields in `TypeAdapters` class holding `JsonElementTypeAdapter` instances
2. `JsonElementTypeAdapter` to access these fields during its own class loading
3. No coordination mechanism to ensure proper initialization order

When a field is declared as `static final TypeAdapter<JsonElement>`, the JVM must load the `JsonElementTypeAdapter` class during `TypeAdapters` initialization. If another thread is simultaneously loading `JsonElementTypeAdapter` and that class needs something from `TypeAdapters`, the deadlock occurs.

## Java Class Loading Mechanics

Java's class loading is synchronized at the class loader level. When a class is being loaded:
1. A lock is acquired on the class being loaded
2. If that class references another class, the loader recursively loads it
3. If the new class references the original class, we have a circular dependency

```java
// TypeAdapters.java
static {
    ELEMENT_ADAPTER = new JsonElementTypeAdapter();  // Loads JsonElementTypeAdapter
}

// JsonElementTypeAdapter.java
static {
    // References TypeAdapters — circular!
    TypeAdapters.registerAdapter(this);
}
```

## The Fix: PR #2740

The fix restructured class dependencies to eliminate the circular reference:

### Before (Problematic):
```
TypeAdapters ──refers to──> JsonElementTypeAdapter
     ↑                              │
     └──────────refers to──────────┘
     (circular dependency)
```

### After (Fixed):
```
TypeAdapters ──refers to──> JsonElementTypeAdapter
                                   │
                                   └──> separate holder class
                                        (breaks the cycle)
```

The specific changes in PR #2740:
1. Separated the `JsonElementTypeAdapter` into a different initialization context
2. Created an intermediate holder or factory class that breaks the dependency cycle
3. Ensured that `JsonElementTypeAdapter` doesn't directly reference `TypeAdapters` in its static initializer
4. Unified the class loading paths to ensure consistent ordering

## Why This Bug Never Reached Production

The deadlock was:
1. **Timing-dependent** — Only occurred under specific thread scheduling conditions
2. **Non-deterministic** — Might not happen during testing or development
3. **Environment-dependent** — More likely on systems with many cores or high load
4. **Test-evasive** — Single-threaded tests wouldn't expose it

The fix was prioritized immediately upon discovery because while it didn't affect most users, any affected user would experience a complete application hang.

## Technical Details of the Solution

Class loading deadlock avoidance typically requires:

1. **Avoid circular static initializers** — Ensure static blocks don't reference classes that reference back
2. **Lazy initialization** — Defer initialization until it's actually needed (after all classes are loaded)
3. **Initialization holders** — Use holder classes to separate concerns
4. **Explicit ordering** — Ensure classes are loaded in a safe order

The solution used one or more of these techniques to restructure Gson's initialization.

## Impact Assessment

- **Severity**: Critical (could hang entire application)
- **Scope**: Affected only Gson initialization, not runtime operations
- **Exposure**: Required specific timing conditions to manifest
- **Fix complexity**: Moderate (required significant refactoring of class structure)

## Testing

PR #2740 included tests to verify:
1. No deadlock occurs during concurrent class loading
2. All adapter functionality still works correctly
3. Backward compatibility is maintained
4. Static final fields are properly initialized
5. Multiple threads can initialize Gson simultaneously

## Lesson Learned

This incident highlighted important principles:
1. **Static initialization is dangerous** — Avoid complex logic in static blocks
2. **Circular dependencies are problematic** — Especially in class loading
3. **Backward compatibility can introduce complexity** — Maintaining old APIs can require careful structuring
4. **Thread safety starts at class loading** — Consider concurrency from the lowest levels

## Version Information

- Introduced in: PR #2727
- Fixed in: PR #2740, included in Gson 2.11.0+ (September 2024)
- Never reached stable release: Caught during development/pre-release testing

## Prevention Going Forward

To prevent similar issues:
1. Static initializer review in pull request process
2. Explicit circular dependency analysis tools
3. Concurrent testing during development
4. Stress testing with multiple threads loading classes
5. Code review checklist for static field initialization

## Related Deadlock Concerns

Similar issues have been found in:
- Log4j (CVE-2021-45046)
- Other Java libraries with complex static initialization
- Frameworks managing singletons via static initialization
