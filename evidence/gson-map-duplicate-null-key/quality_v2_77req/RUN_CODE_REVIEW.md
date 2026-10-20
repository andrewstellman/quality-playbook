# Code Review Protocol: Gson

## Bootstrap (Read First)

Before reviewing, read these files for context:

1. `quality/QUALITY.md` — quality constitution and fitness-to-purpose scenarios
2. `quality/REQUIREMENTS.md` — behavioral requirements derived per subsystem
3. `README.md` — project goals, maintenance-mode constraints, Android caveats
4. `UserGuide.md` — user-facing behavior contracts and examples
5. `Troubleshooting.md` — known failure modes and required remediation
6. `GsonDesignDocument.md` — design rationale for fields-vs-getters, instantiation, and type-tree navigation
7. For environment-sensitive work, also read `test-jpms/`, `test-shrinker/`, and `test-graal-native-image/`

## Review scope guidance

Start with the highest-risk files unless the diff is obviously isolated:

- `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`
- `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`
- `gson/src/main/java/com/google/gson/stream/JsonReader.java`
- `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java`
- `gson/src/main/java/com/google/gson/reflect/TypeToken.java`
- `gson/src/main/java/com/google/gson/Gson.java`
- `gson/src/main/java/com/google/gson/GsonBuilder.java`

## Pass 1: Structural Review

Read the changed code and report anything that looks incorrect on its own terms. This is a full structural review; do not save attention for later passes.

### Guardrails

- **Line numbers are mandatory.** If you cannot cite a line, do not include the finding.
- **Read function bodies, not just signatures.**
- **If unsure, mark the finding as `QUESTION`, not `BUG`.**
- **Grep before claiming something is missing.**
- **Do not suggest style changes or refactors.** Only correctness issues matter.

### Gson-specific structural prompts

Look especially for:

1. Changes that alter builder snapshotting or adapter precedence.
2. Reflection-access changes that could weaken `ReflectionAccessFilter` or JPMS behavior.
3. Constructor path changes that move instantiation toward `Unsafe`, skip validation, or change fallback order.
4. Parser-state changes in `JsonReader` or `JsonWriter` that could desynchronize nesting or path tracking.
5. Map or tree-model changes that alter duplicate-key semantics or key-stringification behavior.
6. Type-token changes that weaken generic-type validation.

### Output format

#### `path/to/file.java`
- **Line NNN:** `BUG` / `QUESTION` / `INCOMPLETE` — expected vs. actual behavior, and why it matters.

## Pass 2: Requirement Verification

Read `quality/REQUIREMENTS.md`. For each requirement that touches the reviewed code, answer only one question: **does this code satisfy the requirement?**

### Status values

- **SATISFIED**
- **VIOLATED**
- **PARTIALLY SATISFIED**
- **NOT ASSESSABLE**

### Reviewer workflow

1. Copy the requirement ID and summary.
2. Read the relevant code path fully.
3. Quote the evidence that satisfies or violates the requirement.
4. If the requirement is directional, verify all touched sibling paths in the same subsystem before marking it satisfied.

### Output format

#### REQ-NNN: summary
**Status:** SATISFIED / VIOLATED / PARTIALLY SATISFIED / NOT ASSESSABLE  
**Evidence:** `file:line-line` — code quote or behavior summary  
**Analysis:** why the evidence satisfies or violates the requirement  
**Severity:** only for violated or partially satisfied items

## Pass 3: Cross-Requirement Consistency

Compare requirements that share a concept and verify the code keeps them consistent across files.

### Priority consistency pairs for Gson

1. **REQ-006 vs REQ-007** — non-executable prefix generation must match prefixed-input consumption.
2. **REQ-008 vs REQ-040** — typed collection guidance must agree with raw-type degradation behavior.
3. **REQ-021 vs REQ-022** — local/anonymous-class null behavior must not be confused with inner-class instantiation rules.
4. **REQ-023 vs REQ-030 vs REQ-041** — reflection barriers, custom adapters, and JPMS module openness must form a coherent escape-hatch story.
5. **REQ-031 vs REQ-033** — tree-model replacement semantics and map duplicate-key rejection must stay explicitly distinct and documented.
6. **REQ-035 vs REQ-036** — complex-map-key round-tripping must not accidentally change the default `Map<String, ...>` or raw-`Map` implementation contract.
7. **REQ-026 vs REQ-027 vs REQ-028** — constructor fallback order, unsafe disablement, and non-instantiable type rejection must stay mutually consistent.
8. **REQ-013 vs REQ-016 vs REQ-018** — strictness settings, trailing-data behavior, and parser state transitions must not contradict one another.
9. **REQ-044 vs REQ-045** — null bypass and per-type null opt-ins must agree about which adapter paths can actually observe null values.
10. **REQ-046 vs REQ-047** — custom parent-type handling and `JsonElement` compatibility shims must not steal unrelated serialization paths.
11. **REQ-001 vs REQ-048** — public thread-safe reuse guarantees must hold during concurrent adapter bootstrap, not just after steady-state cache warmup.

### Output format

#### Shared Concept: concept name
**Requirements:** REQ-X, REQ-Y  
**What REQ-X claims:** ...  
**What REQ-Y claims:** ...  
**Consistency:** CONSISTENT / INCONSISTENT  
**Code evidence:** `file:line-line`, `file:line-line`  
**Analysis:** ...  
**Impact:** only when inconsistent

## Combined Summary

| Source | Finding | Severity | Status |
|--------|---------|----------|--------|
| Pass 1 | Structural anomaly | High / Medium / Low | BUG / QUESTION |
| Pass 2 | Requirement violation | High / Medium / Low | VIOLATED / PARTIALLY SATISFIED |
| Pass 3 | Cross-requirement inconsistency | High / Medium / Low | INCONSISTENT |

- Total findings by pass
- Highest-risk subsystem touched
- Overall assessment: **SHIP IT / FIX FIRST / NEEDS DISCUSSION**

## Regression tests for confirmed bugs

After confirming real bugs, add reproducing tests to `quality/test_regression.java` or the most relevant existing test package. Every confirmed bug should gain:

1. A failing reproducer on the pre-fix implementation.
2. A doc comment linking back to the review finding.
3. A confirmation table saved under `quality/results/`.
