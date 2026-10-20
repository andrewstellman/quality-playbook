---
source: https://github.com/google/gson/issues/2787
retrieved: 2026-04-03
type: github_issue
description: GsonBuilder backwards compatibility broken, throws 'Cannot override built-in adapter' error
---

# Issue #2787: GsonBuilder backwards compatibility broken, throws 'Cannot override built-in adapter' error

## Status
**Closed** — Fixed in Gson 2.12.0 by reverting strict validation

## Description

Gson 2.11 introduced validation in `GsonBuilder` that prevented custom adapters from being registered for `JsonElement` and its subclasses (`JsonObject`, `JsonArray`, `JsonPrimitive`, `JsonNull`). This validation broke backward compatibility with existing libraries and applications that had custom serializers for these types as workarounds for older issues.

The most notable affected library was `cloudant-client`, which registered custom serializers for `JsonObject` as a workaround for issue #362 (fixed in Gson 2.2.3). After upgrading to Gson 2.11, these libraries would throw a `GsonBuilderException` with the message: "Cannot override built-in adapter".

## Problem Scenario

```java
// This code worked in Gson 2.10 and earlier
new GsonBuilder()
    .registerJsonSerializer(JsonObject.class, (src, typeOfSrc, context) -> {
        // Custom serialization logic for JsonObject
        return customSerialize(src);
    })
    .create();

// In Gson 2.11: Throws GsonBuilderException
// "Cannot override built-in adapter for JsonElement"
```

## Root Cause

Gson 2.11 added validation logic to the `GsonBuilder` that explicitly prevented overriding adapters for built-in types:

```java
if (type == JsonElement.class || JsonElement.class.isAssignableFrom(type)) {
    throw new GsonBuilderException(
        "Cannot override built-in adapter for " + type);
}
```

The intent was to prevent users from accidentally breaking Gson's core JSON handling by overriding adapters for fundamental types. However, this validation was:
1. Too strict
2. Breaking legitimate use cases
3. Preventing libraries from working around older issues
4. Not respecting the library's historical behavior

## Why Libraries Did This

Libraries like `cloudant-client` had registered custom adapters for `JsonObject` because:
1. They needed special handling for certain edge cases
2. Gson issue #362 prevented proper behavior with standard adapters (before it was fixed)
3. The workaround worked reliably for versions with the old issue
4. No error was thrown, so it seemed like a valid approach

## The Resolution in Gson 2.12.0

Rather than maintain the strict validation, Gson 2.12.0 took a different approach:

**Attempting to override built-in adapters now silently fails rather than throwing an exception.**

This means:
1. No error is thrown
2. The custom adapter is not registered (ignored)
3. The built-in adapter is used regardless
4. The behavior is backward compatible with Gson 2.10

### Reasoning from Maintainer

The Gson maintainer explained the rationale:

> "Probably most people who try to register an adapter for JsonElement will find out quickly enough that it doesn't work."

In other words:
1. If someone tries to register a custom adapter for JsonElement and it silently fails, they'll notice during testing
2. The error would prevent legitimate use cases unnecessarily
3. Silently failing is preferable to breaking code

## Code Behavior Comparison

### Gson 2.10 and earlier:
```java
GsonBuilder builder = new GsonBuilder();
builder.registerJsonSerializer(JsonElement.class, customAdapter);
// Custom adapter registered successfully (silently accepted)
Gson gson = builder.create();
// Custom adapter is used
```

### Gson 2.11:
```java
GsonBuilder builder = new GsonBuilder();
builder.registerJsonSerializer(JsonElement.class, customAdapter);
// Throws: GsonBuilderException: "Cannot override built-in adapter"
```

### Gson 2.12.0+:
```java
GsonBuilder builder = new GsonBuilder();
builder.registerJsonSerializer(JsonElement.class, customAdapter);
// Silent success (adapter is ignored, no exception thrown)
Gson gson = builder.create();
// Built-in adapter is used (custom adapter ignored)
```

## Impact on Affected Libraries

### Before Fix:
- `cloudant-client` and similar libraries would fail to build with Gson 2.11
- Dependency resolution would break during upgrade
- Users couldn't use Gson 2.11+ without modified libraries

### After Fix:
- Libraries compile without errors with Gson 2.11+
- Custom adapter registration "succeeds" but the adapter is not used
- Libraries may not work as intended, but at least they don't crash

### Workaround for Library Maintainers:
Libraries that need special handling for JsonElement should:
1. Migrate away from custom JsonElement adapters
2. Handle the special cases in their own code instead
3. File new issues if the underlying problem (like old issue #362) still exists

## Design Philosophy

This resolution reflects an important principle in library design:

**Silent failure for harmless mistakes is often better than strict validation**

The rationale:
1. Users will discover the issue during development/testing
2. No code is broken by the change
3. Backward compatibility is maintained
4. Libraries that legitimately use this pattern can still function

## Lessons Learned

### What This Teaches:
1. **Strict validation can break legitimate uses** — Even if the use case seems wrong, users may have valid reasons
2. **Backward compatibility is important** — Breaking changes should be carefully justified
3. **Silent failure vs. loud failure** — Both have tradeoffs
4. **Workarounds become dependencies** — Code written to work around issues becomes part of the contract

### For Library Maintainers:
- Consider whether validation is truly necessary
- Weigh the cost of breaking changes
- Document what is and isn't supported
- Provide migration paths

## Timeline

- **Gson 2.10 and earlier** — Custom adapters for JsonElement allowed
- **Gson 2.11** — Validation added, throws exception
- **Reported** — Issue #2787 opened
- **Resolved** — Gson 2.12.0, validation removed (silently fail instead)

## Version Recommendation

- For new projects: Use Gson 2.12.0+
- For projects with custom JsonElement adapters: Ensure running Gson 2.12.0+ or work around the 2.11 limitation
- For migration: If upgrading from 2.10 to 2.11 breaks your build, skip to 2.12.0

## Related Issues

- **Issue #362** — Original issue that prompted custom adapters (fixed in 2.2.3)
- **PR #2787** — This fix

## Best Practices Going Forward

1. **Don't override JsonElement adapters** — If possible, avoid this pattern
2. **Report the underlying issue** — If you need custom JsonElement handling, file an issue instead of working around it
3. **Test adapter registration** — Verify that custom adapters are actually being used
4. **Update dependencies regularly** — Keep libraries up to date to benefit from compatibility improvements

## Impact Assessment

- **Severity of original break** — High (breaks existing code)
- **Severity of fix** — Low (silent failure, maintains compatibility)
- **User-facing impact** — Minimal (libraries work without changes)
- **Code quality** — Slightly reduced (custom adapters silently ignored)
