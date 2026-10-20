---
source: https://github.com/google/gson/issues/530
retrieved: 2026-04-03
type: github_issue
description: Object models with circular references cause StackOverflowError when serializing
---

# Issue #530: Circular relationship gives stack overflow

## Status
**Open** — labeled as enhancement

## Description

When object models contain circular references (e.g., a Parent object holds a reference to a Child object, and the Child holds a reference back to Parent), Gson does not detect the circular relationship and simply recurses infinitely until the Java stack overflows with a `StackOverflowError`.

The fundamental problem is that Gson has no built-in circular reference detection mechanism. When serializing an object graph, Gson follows every field recursively without tracking which objects have already been visited or serialized. This makes circular references particularly problematic for real-world object models where bidirectional relationships are common.

## Current Workarounds

1. **Make relationships unidirectional** — Remove the back-reference from the Child to Parent. However, this is not always feasible depending on the domain model requirements.

2. **Use @Expose annotation selectively** — Mark circular fields with `@Expose(serialize = false)` to prevent Gson from attempting to serialize them. This requires explicit configuration for each circular field.

3. **Custom TypeAdapter** — Write a custom TypeAdapter that manually tracks visited objects and omits circular references during serialization.

4. **JSON references approach** — Manually track object IDs during serialization and use a reference format (e.g., `{"$ref": "#/parent"}`) instead of repeating the object.

## Related Issues

This issue is cross-referenced to **Issue #2414** which deals with similar stack overflow problems when serializing Maps that contain circular references.

## Root Cause Analysis

Gson uses a reflective approach to serialization that relies on recursively visiting every field of every object. The `ReflectiveTypeAdapterFactory` and related classes traverse the object graph depth-first without maintaining a visited set. For object graphs with cycles, this traversal never terminates naturally and continues until memory is exhausted.

The lack of a global visited-object registry means that even if a framework-level circular reference detector were added, it would require significant changes to Gson's core serialization pipeline.

## Impact

- Applications dealing with domain models containing bidirectional relationships cannot use Gson without workarounds
- Data structures like graphs and trees with back-pointers cannot be serialized
- The error message (StackOverflowError) provides no diagnostic information about which objects are involved in the cycle

## Potential Solutions

1. **Circular reference detection** — Maintain a thread-local `IdentityHashSet` of objects being serialized. Before serializing an object, check if it's already in the set. If so, either skip it or use a reference format.

2. **Configurable circular reference handling** — Add a `setCircularReferenceHandler()` option to GsonBuilder that allows users to define behavior (skip, reference, throw exception).

3. **Graph serialization framework** — Create a specialized serialization path for object graphs that maintains visited state and can handle cycles intelligently.

## User Impact

This limitation forces users to either restructure their domain models (making relationships unidirectional) or abandon Gson in favor of frameworks like Jackson that provide built-in circular reference handling.
