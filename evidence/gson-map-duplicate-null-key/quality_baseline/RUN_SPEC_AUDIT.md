# Spec Audit Protocol: Gson

## The Definitive Audit Prompt

Give this prompt identically to three independent AI tools.

---

**Context files to read:**

1. `quality/QUALITY.md`
2. `quality/REQUIREMENTS.md`
3. `README.md`
4. `UserGuide.md`
5. `Troubleshooting.md`
6. `GsonDesignDocument.md`
7. `AGENTS.md`

**Code to audit:**

- `gson/src/main/java/com/google/gson/`
- `gson/src/main/java/com/google/gson/internal/`
- `gson/src/main/java/com/google/gson/internal/bind/`
- `gson/src/main/java/com/google/gson/stream/`
- If relevant to the finding, also inspect `test-jpms/`, `test-shrinker/`, and `test-graal-native-image/`

**Task:** Act as the Tester. Read the actual code and compare it against the specifications and requirements above.

**Requirement confidence tiers:**

- **formal** — written by humans in public docs or API documentation; treat divergence as a real finding
- **user-confirmed** — none currently recorded for this playbook
- **inferred** — derived from stable code behavior or tests; report divergence as **NEEDS REVIEW** unless corroborated by stronger evidence

**Rules:**

- ONLY list defects. Do not summarize what already matches.
- For EVERY defect, cite specific file and line number(s).
- Before claiming something is missing, grep the codebase.
- Before claiming something exists, read the function body.
- Classify every defect as **MISSING / DIVERGENT / UNDOCUMENTED / PHANTOM**.
- For findings against inferred requirements, append **NEEDS REVIEW**.

**Project-specific scrutiny areas:**

1. Read `gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java`. Verify that anonymous/local-class handling, duplicate-field rejection, static-final writes, and reflection-access failures still match `REQ-021` through `REQ-025`.
2. Read `gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java`. Verify the instantiation fallback order and confirm there is no path that bypasses `disableJdkUnsafe()` or constructs interfaces/abstract classes (`REQ-026` to `REQ-028`).
3. Read `gson/src/main/java/com/google/gson/stream/JsonReader.java`. Check whether strictness, skipping, nesting limits, and trailing-data semantics still satisfy `REQ-011` through `REQ-018`.
4. Compare `gson/src/main/java/com/google/gson/JsonObject.java` against `gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java`. Is the duplicate-key split between tree APIs and typed map binding still intentional and documented?
5. Read `gson/src/main/java/com/google/gson/reflect/TypeToken.java` and its callers. Verify raw-type rejection and captured-type-variable rejection still protect against false type-safety (`REQ-037`, `REQ-038`, `REQ-040`).
6. Read `gson/src/main/java/com/google/gson/Gson.java` and `gson/src/main/java/com/google/gson/GsonBuilder.java`. Check builder snapshotting, adapter precedence, and the propagation of lenient/strict and prefix configuration (`REQ-001`, `REQ-002`, `REQ-006`, `REQ-007`, `REQ-009`).
7. Compare public docs (`README.md`, `UserGuide.md`, `Troubleshooting.md`) with actual platform-boundary modules (`test-jpms`, `test-shrinker`, `test-graal-native-image`). Are any supported environments undocumented, or any documented guarantees unsupported by tests?
8. Audit the scenarios in `quality/QUALITY.md` directly: constructor bypass defaults, raw-type imposters, duplicate-key split-brain, complex map-key reversibility, lenient malformed JSON, local-class nulls, reflection barriers, cycle overflow, shrinker compatibility, and XSSI prefix compatibility.

**Output format:**

### `path/to/file.java`
- **Line NNN:** `[MISSING / DIVERGENT / UNDOCUMENTED / PHANTOM] [Req: tier — source]` description.  
  Spec says: ...  
  Code does: ...  
  *(Add `NEEDS REVIEW` if the requirement is inferred.)*

---

## Running the Audit

1. Give the identical prompt above to three independent tools.
2. Keep the auditors isolated; do not show one model another model’s report.
3. Save outputs under `quality/spec_audits/YYYY-MM-DD-[model].md`.

## Triage Process

| Confidence | Found by | Action |
|------------|----------|--------|
| Highest | All three | Treat as real until disproved |
| High | Two of three | Verify quickly, then fix or update docs |
| Needs verification | One only | Probe with a focused read-only verification pass |

### Verification probe

When the models disagree:

1. Pick a model that did **not** make the disputed claim.
2. Quote the exact claim.
3. Ask it to read only the implicated files and lines.
4. Compare its evidence to the original finding before deciding.

## Categorize each confirmed finding

- **Spec bug** — update docs or requirements
- **Design decision** — requires human judgment
- **Real code bug** — fix in a small subsystem-focused batch
- **Documentation gap** — feature exists but public docs omit it
- **Missing test** — code may be correct but no test proves it
- **Inferred requirement wrong** — correct `quality/QUALITY.md` or `quality/REQUIREMENTS.md`

## Fix execution rules

- Fix in batches of 3-5 findings from the same subsystem.
- After each batch, rerun only the most relevant tests first, then the broader affected suite.
- Update `quality/REQUIREMENTS.md` or `quality/QUALITY.md` when the finding reveals that the documented contract was wrong or incomplete.
