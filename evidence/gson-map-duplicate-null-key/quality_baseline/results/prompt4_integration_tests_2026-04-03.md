# Prompt 4 integration test run — 2026-04-03

## Phase 1: Plan

- **Will run:** Group 1 core contract smoke, Group 2 JPMS boundary, Group 3 shrinker compatibility
- **Will skip:** Group 4 native-image boundary
- **Skip reason:** `native-image --version` failed because GraalVM native-image is not installed in this environment

## Phase 2: Progress

- `⧗ Group 1 core contract smoke`
- `✓ Group 1 core contract smoke`
- `⧗ Group 2 JPMS boundary`
- `✗ Group 2 JPMS boundary`
- `⧗ Group 3 shrinker compatibility`
- `✓ Group 3 shrinker compatibility`
- `○ Group 4 native-image boundary skipped`

## Phase 3: Summary

| Group | Result | Key signal | Recommendation |
|------|--------|------------|----------------|
| Core contract smoke | PASS | `FunctionalTest` (25/25), `MapTest` (52/52), `SecurityTest` (5/5), `ReflectionAccessTest` (3 run, 1 skipped), and `CircularReferenceTest` (6/6) all passed | ready |
| JPMS boundary | FAIL | The documented `mvn -q -pl test-jpms test` invocation first needed local snapshot installation, then failed `ModuleTest.testGsonModule` because Gson loaded from `~/.m2/.../gson-2.13.3-SNAPSHOT.jar` instead of matching `gson/target/gson-[^/]+\.jar` | fix before release |
| Shrinker compatibility | PASS | The documented `mvn -q -pl test-shrinker test` command exited successfully but did not execute the actual integration tests; running `mvn -q -pl test-shrinker verify` executed `ShrinkingIT` with 10 completed, 0 failures, 0 errors, 1 skipped | ready |
| Native-image boundary | SKIP | `native-image` toolchain missing | toolchain gap only |

## Notes

1. **Pre-flight passed:** JDK 21.0.2 and Maven 3.9.9 were available, and `mvn -q -pl gson -DskipTests compile` succeeded.
2. **JPMS command caveat:** `test-jpms` depends on the snapshot `gson` artifact, so running it directly required installing `gson` and the root parent POM locally first. After that, the remaining failure was the test's expected jar path, not a reflection-openness assertion.
3. **Shrinker command caveat:** `test-shrinker` binds its real integration coverage to Maven Failsafe (`integration-test` / `verify`) via `ShrinkingIT`, so the prompt's `test` phase is a false green for this module.
4. **Overall recommendation:** **fix before release** because the JPMS integration command currently does not produce a trustworthy boundary result under the documented protocol.
