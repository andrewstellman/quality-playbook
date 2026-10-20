# Integration test run summary

- **Date:** 2026-04-03
- **Protocol source:** `quality/RUN_INTEGRATION_TESTS.md`
- **Working directory:** project root
- **Recommendation:** **fix before release**

## Pre-flight

| Check | Result | Key signal |
|------|--------|------------|
| `java -version` | PASS | OpenJDK 21.0.2 |
| `mvn -q -version` | PASS | Maven 3.9.9 |
| `mvn -q -pl gson -DskipTests compile` | PASS | Core `gson` module compiled successfully |
| `native-image --version` | SKIP | Toolchain missing (`native-image: command not found`) |

## Phase 1 plan

- Run Group 1 core contract smoke and Group 2 JPMS boundary after the compile gate passes.
- Run Group 3 shrinker compatibility afterward.
- Mark Group 4 native-image boundary skipped because the toolchain is not installed.

## Phase 2 progress

- `✓ Group 1 core contract smoke`
- `✗ Group 2 JPMS boundary`
- `✗ Group 3 shrinker compatibility`
- `○ Group 4 native-image boundary (skipped: toolchain missing)`

## Phase 3 summary

| Group | Result | Key signal | Recommendation |
|------|--------|------------|----------------|
| Core contract smoke | PASS | `mvn -q -pl gson -Dtest='com.google.gson.quality.FunctionalTest,com.google.gson.functional.MapTest,com.google.gson.functional.SecurityTest,com.google.gson.functional.ReflectionAccessTest,com.google.gson.functional.CircularReferenceTest' test` exited 0 | Ready |
| JPMS boundary | FAIL | `mvn -q -pl test-jpms test` failed in `ModuleTest.testGsonModule` because `Gson.class` loaded from `~/.m2/.../gson-2.13.3-SNAPSHOT.jar` instead of `gson/target/gson-*.jar`, so the module-location assertion failed before any reflection-openness regression signal | Fix JPMS test setup before release; current protocol command does not produce a clean boundary verdict in this workspace |
| Shrinker compatibility | FAIL | Protocol command `mvn -q -pl test-shrinker test` exited 0, but the module’s real integration tests run in Failsafe at `verify`; `mvn -q -pl test-shrinker verify` failed during ProGuard packaging with 274 unresolved Gson-class references and `Obfuscation failed (result=1)` | Fix shrinker packaging/integration setup before release |
| Native-image boundary | SKIP | `native-image` unavailable | Toolchain gap only |

## Notable details

### Group 2 JPMS failure

- Failing assertion: `test-jpms/src/test/java/com/google/gson/jpms_test/ModuleTest.java:48`
- Expected: `gson/target/gson-[^/]+\.jar`
- Actual: `/Users/andrewstellman/.m2/repository/com/google/code/gson/gson/2.13.3-SNAPSHOT/gson-2.13.3-SNAPSHOT.jar`

An additional reactor-scoped retry (`mvn -q -pl gson,test-jpms -am test`) did not improve coverage; it failed earlier during `test-jpms` test compilation with `module not found: com.google.gson`.

### Group 3 shrinker failure

- `test-shrinker/pom.xml` binds the integration workload to Failsafe (`integration-test`, `verify`), so `test` alone is not the full shrinker boundary.
- `mvn -q -pl test-shrinker verify` failed in the ProGuard step with:
  - `there were 274 unresolved references to classes or interfaces`
  - `java.io.IOException: Please correct the above warnings first.`
  - `Failed to execute goal ... proguard-maven-plugin ... Obfuscation failed (result=1)`

## Teardown

- `mvn -q clean` completed successfully.
