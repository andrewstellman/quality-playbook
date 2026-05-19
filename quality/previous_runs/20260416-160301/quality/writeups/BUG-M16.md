# BUG-M16 Writeup: Functional Test Existence Check Uses ls-glob (Nullglob Vulnerable)

**Severity**: MEDIUM
**File:Line**: `quality_gate.sh:124`
**Requirement**: REQ-019

---

## Summary

`quality_gate.sh:124` uses an `ls`-glob to check whether a functional test file exists. Under `nullglob` (the default in zsh on macOS, or enabled in bash), an unmatched glob expands to nothing rather than the literal glob string. `ls` with no arguments lists the current working directory and exits 0 — causing the gate to report `PASS: functional test file exists` when no test file is present. This is the same nullglob vulnerability class confirmed in BUG-M8 (lines 152-153, 331, 567-568, 595), BUG-M12 (line 479), and BUG-M13 (line 143), but at a previously unaddressed location.

---

## Root Cause

```diff
- if ls ${q}/test_functional.* ${q}/FunctionalSpec.* ${q}/FunctionalTest.* ${q}/functional.test.* &>/dev/null 2>&1; then
+ if find "${q}" -maxdepth 1 \( \
+        -name "test_functional.*" \
+        -o -name "FunctionalSpec.*" \
+        -o -name "FunctionalTest.*" \
+        -o -name "functional.test.*" \
+    \) -print -quit 2>/dev/null | grep -q .; then
```

Under nullglob, the four glob patterns in the `ls` invocation each expand to nothing when no matching file exists. `ls` receives zero arguments and lists the current working directory, returning exit 0. The gate's `if` branch executes, emitting `pass "functional test file exists"` when no test file is present.

The `find -print -quit | grep -q .` pattern is immune: if no file matches, `find` produces no output, and `grep -q .` exits 1.

---

## Impact

A CI system running `quality_gate.sh` in a zsh environment (macOS default) or any bash environment with `nullglob` set will receive a false `PASS` for the functional test file existence check. An agent can omit `test_functional.*` from its output and the gate will not detect the omission. The artifact contract documented in SKILL.md (line 94: `quality/test_functional.*` — "Required: If bugs found") is not enforced.

---

## Fix

Replace the `ls`-glob with `find`-based detection (matching the pattern at lines 449-454):

```diff
- if ls ${q}/test_functional.* ${q}/FunctionalSpec.* ${q}/FunctionalTest.* ${q}/functional.test.* &>/dev/null 2>&1; then
-     pass "functional test file exists"
- else
-     fail "functional test file missing (test_functional.*, FunctionalSpec.*, FunctionalTest.*, functional.test.*)"
- fi
+ if find "${q}" -maxdepth 1 \( \
+        -name "test_functional.*" \
+        -o -name "FunctionalSpec.*" \
+        -o -name "FunctionalTest.*" \
+        -o -name "functional.test.*" \
+    \) -print -quit 2>/dev/null | grep -q .; then
+     pass "functional test file exists"
+ else
+     fail "functional test file missing (test_functional.*, FunctionalSpec.*, FunctionalTest.*, functional.test.*)"
+ fi
```

---

## TDD Evidence

- **Red phase log**: `quality/results/BUG-M16.red.log` — first line `RED`
  - `grep -qE 'if ls \$\{q\}/test_functional\.'` matches line 124 → test exits 1 (FAIL)
- **Green phase log**: `quality/results/BUG-M16.green.log` — first line `GREEN`
  - Inline verification: find-based detection correctly fails for empty dir, passes when file exists
  - Post-fix test function would exit 0 (PASS)
- **Regression test**: `quality/patches/BUG-M16-regression-test.patch`
- **Fix patch**: `quality/patches/BUG-M16-fix.patch`
