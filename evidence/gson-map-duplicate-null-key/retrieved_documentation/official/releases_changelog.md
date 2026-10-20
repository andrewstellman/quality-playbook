---
source: https://github.com/google/gson/releases
retrieved: 2026-04-03
type: official
description: GitHub Releases page content for Gson versions 2.10 through 2.13.2 (supplements CHANGELOG.md which stops at 2.10)
---

# Gson Releases — Version 2.10 through 2.13.2

## Overview

The CHANGELOG.md file in the repo only covers versions up to 2.10. Newer release notes are on the GitHub Releases page.

## Gson 2.13.2 (September 10, 2024)

**Focus:** Java Platform Module System (JPMS) improvements and internal cleanup.

- Enhanced JPMS module declaration packaging
- Fixed Eclipse and VS Code module reference issues
- Removed internal GsonPreconditions class
- Improved module resolution for IDE tooling compatibility

## Gson 2.13.1 (April 24, 2024)

**Focus:** Field naming strategies and ProGuard examples cleanup.

- Enabled FieldNamingStrategy to return multiple string name options
  - Allows more flexible field name mapping configurations
- Removed outdated Android ProGuard examples
  - Reflected changes in ProGuard/R8 landscape

## Gson 2.13.0 (April 11, 2024)

**Focus:** Collection deserialization bug fixes and error messaging improvements.

- Fixed collection deserialization bugs where abstract types like `ImmutableList` were incorrectly instantiated as `ArrayList`
  - Previously: attempting to deserialize into abstract collection types would fail at runtime
  - Now: proper error detection and meaningful error messages
- Renamed internal classes removing "$" characters
  - Improved consistency in internal class naming conventions
- "Abstract classes can't be instantiated" errors now properly direct users toward solutions
  - Error messages guide developers to use concrete types or custom deserializers

## Gson 2.12.1 (January 30, 2024)

**Focus:** Dependency management for modular environments.

- Minor release with dependency refinement
- Made `com.google.errorprone.annotations` an optional OSGi dependency rather than required
  - Reduces transitive dependency footprint for projects not using Error Prone

## Gson 2.12.0 (January 27, 2024)

**Focus:** Java version support, deserialization safety, and output control.

- Dropped Java 7 support
  - Gson now requires Java 8 or higher
- Permitted JsonElement adapters again
  - Reverted the 2.11 restriction that disallowed custom adapters for JsonElement types
- Introduced nesting limits for JsonReader
  - Prevents stack overflow attacks from deeply nested JSON structures
  - Configurable nesting limit threshold
- Added NullSafeTypeAdapter
  - Prevents nested null-safe wrappers that could cause unexpected behavior
  - Automatically manages null handling without manual configuration

## Gson 2.11.0 (May 20, 2023)

**Focus:** Output formatting, API strictness, and type safety.

- Major release with significant API additions
- ProGuard/R8 default rules bundled
  - Automatic obfuscation rules for Android/ProGuard users
- New Strictness API
  - LENIENT, DEFAULT, STRICT modes for JSON compliance
  - Allows per-call strictness specification via `fromJson(..., Strictness.STRICT)`
- FormattingStyle for output formatting
  - Control JSON pretty-printing via FormattingStyle enum
- TypeToken now prevents type variable capture by default
  - Reduces subtle bugs from improper generic type specifications
- Anonymous and local classes gained serialization support with custom adapters
  - Previously not serializable without workarounds

## Gson 2.10.1 (January 6, 2023)

**Focus:** Bug fixes and API convenience.

- Added `JsonObject.isEmpty()` method
  - Check if a JsonObject has any properties
- Fixed non-thread-safe adapter creation for cyclic types
  - Concurrent adapter creation no longer causes race conditions
- Improved duplicate field name exception messages
  - Clearer errors when JSON contains duplicate object keys

## Gson 2.10 (October 25, 2022)

**Focus:** Modern Java support and convenience methods.

- Java record support (Java 16+)
  - Records now automatically deserialize and serialize correctly
- `JsonArray.asList()` and `JsonObject.asMap()` view methods
  - Convert JsonArray to List and JsonObject to Map without full copying
- `Gson.fromJson(..., TypeToken)` overloads
  - Direct TypeToken parameter (Gson 2.10+) without needing `.getType()`
- Fixed concurrent adapter creation
  - Thread-safe initialization of adapters in multi-threaded scenarios

## Gson 2.9.1 (July 31, 2021)

**Focus:** Stack safety, security, and deserialization flexibility.

- Made Object and JsonElement deserialization iterative rather than recursive
  - Prevents stack overflow on deeply nested JSON structures
  - Handles arbitrary nesting depth safely
- Enum `toString()` parsing support
  - Can now deserialize using enum custom toString() methods
- Reflection access filter
  - Control which fields and methods Gson can access via reflection
  - Security enhancement for restricted environments
- Improved TypeToken validation
  - Better error messages for incorrect TypeToken usage

## Gson 2.9.0 (February 11, 2021)

**Focus:** Minimum Java version bump and thread safety.

- Minimum Java version increased to 7
  - Gson 2.8 supported Java 5; 2.9 requires Java 7 or higher
- `GsonBuilder.disableJdkUnsafe()`
  - Disable use of Unsafe API for environments that restrict it
- `UPPER_CASE_WITH_UNDERSCORES` field naming strategy
  - New built-in naming convention for field mapping
- Improved TreeTypeAdapter thread-safety
  - Adapter caching no longer causes synchronization overhead or race conditions

## Gson 2.8.9 and Earlier

See CHANGELOG.md in the repository for releases prior to 2.9.

## Version Selection Guide

- **Latest stable (2.13.2):** For new projects; includes all improvements and bug fixes
- **2.13.0+:** Needed if deserializing abstract collection types like ImmutableList
- **2.12.0+:** Needed for Java 8+ features; includes nesting safety
- **2.11.0+:** Needed for strict JSON validation or TypeToken improvements
- **2.10+:** Needed for Java record support or convenience methods like `asList()`
- **Pre-2.10:** Legacy projects; recommend upgrading for security and performance improvements

## Summary

Recent Gson releases have focused on:
1. **Safety:** Stack-safe deserialization, nesting limits, null-safety wrappers
2. **Performance:** Non-recursive algorithms, improved adapter caching
3. **Compatibility:** Java module system support, record types, Java 8+
4. **Usability:** Better error messages, convenience methods, simpler APIs
5. **Correctness:** Fixed abstract type handling, concurrent adapter creation
