# Panelist B — Defense-in-Depth Correctness Review (Instruction 203)

**Repo:** `/Users/andrewstellman/Documents/QPB/` @ `36d53ed` (branch `1.5.8`, not pushed)
**Files under review:**
- `bin/publish_npm.py` (`npm_pack_dry_run`, lines 292–347)
- `bin/tests/test_publish_npm.py` (`NpmPackDryRunTests`, lines 229–343)

## 1. Charter recap

Confirm the JSON-start-find logic in `npm_pack_dry_run()` correctly handles clean stdout, polluted stdout, and stdout with no `[` at all; verify the original full-stdout publish-log capture still works; and verify the unit test suite covers all three cases.

## 2. Case-coverage table

| Case | Test name | Assertion that proves the case |
|---|---|---|
| (a) Clean stdout starting with `[` | `NpmPackDryRunTests.test_clean_pack_passes` (lines 230–250) | `self.assertTrue(ok)` + `self.assertIn("SKILL.md", "\n".join(files))` — `payload = json.dumps([...])` starts with `[` at index 0; `find("[")` returns 0, slice is identical to stdout, parse succeeds, files are extracted. |
| (b) Polluted stdout with a progress line before `[` | `NpmPackDryRunTests.test_polluted_stdout_with_progress_line_parses` (lines 285–311) | Payload is literally `"build_channel_package: staged 59 files into /tmp/_bundle\n" + json.dumps([...])`. Assertions: `self.assertTrue(ok, f"expected ok, got: {msg}")` and `self.assertIn("SKILL.md", "\n".join(files))`. This is the exact bug class that broke 202: the line `build_channel_package: staged N files into PATH`. |
| (c) Stdout that contains no `[` at all | `NpmPackDryRunTests.test_stdout_with_no_bracket_fails_with_clear_error` (lines 313–326) | `stdout="nothing useful here\n"`. Assertions: `self.assertFalse(ok)`, `self.assertIn("no '['", msg)`, `self.assertIn("nothing useful here", msg)` — confirms both the False return AND that the error message cites the stdout snippet (per the `repr(stdout[:200])` formatting at publish_npm.py:319). |

All three are matched cleanly by the production code:

```python
stdout = r.stdout or ""
json_start = stdout.find("[")
if json_start < 0:
    return (
        False,
        "npm pack JSON parse failed: no '[' in stdout (stdout="
        + repr(stdout[:200])
        + ")",
        [],
    )
json_payload = stdout[json_start:]
try:
    data = json.loads(json_payload)
except json.JSONDecodeError as e:
    return False, f"npm pack JSON parse failed: {e}", []
```

(a) `find("[")` returns 0 → slice is identical → parse. (b) `find("[")` returns a positive index → slice strips prefix → parse. (c) `find("[")` returns −1 → guarded return with clear error citing stdout snippet.

### Test execution

```
$ python3 -m unittest bin.tests.test_publish_npm.NpmPackDryRunTests -v
test_clean_pack_passes ... ok
test_log_captures_full_unmodified_stdout ... ok
test_pack_failure_fails ... ok
test_pack_with_pyc_fails ... ok
test_polluted_stdout_with_progress_line_parses ... ok
test_stdout_with_no_bracket_fails_with_clear_error ... ok
----------------------------------------------------------------------
Ran 6 tests in 0.001s
OK
```

Full file: **34 tests, all pass.** (Includes the real round-trip test `NpmPackRoundTripStdoutTests.test_npm_pack_dry_run_stdout_is_pure_json` which actually invokes `npm pack --dry-run --json` against the on-disk `package.json` and asserts `stdout.lstrip().startswith("[")` and `name == "quality-playbook"` — closes the 202 coverage gap directly.)

## 3. Log-capture verification — `log_fh.write(r.stdout or "")` BEFORE the strip

Confirmed. `bin/publish_npm.py:298–323`:

```python
    r = _run(
        [npm, "pack", "--dry-run", "--json"],
        cwd=repo_root,
    )
    log_fh.write("--- npm pack --dry-run --json stdout ---\n")
    log_fh.write(r.stdout or "")                              # line 303 — UNMODIFIED stdout
    log_fh.write("--- npm pack --dry-run --json stderr ---\n")
    log_fh.write(r.stderr or "")
    if r.returncode != 0:
        return False, f"npm pack --dry-run failed (exit {r.returncode}).", []
    # ... comment block ...
    stdout = r.stdout or ""                                   # line 313 — local copy, original r.stdout untouched
    json_start = stdout.find("[")                             # line 314 — analysis only, no mutation
    ...
    json_payload = stdout[json_start:]                        # line 323 — slice, original `stdout` untouched
```

Two corroborating points:

1. **Ordering:** lines 302–305 (log writes) execute before line 313 (local stdout assignment). The pollution prefix, if present, is written to the log verbatim.
2. **Immutability:** `r.stdout` is never reassigned, never `.replace()`-d, never mutated. `stdout.find("[")` is a read-only call. `stdout[json_start:]` produces a new string. The original `r.stdout` (now in the log) is preserved in full.

This is explicitly asserted by `NpmPackDryRunTests.test_log_captures_full_unmodified_stdout` (lines 328–343): writes a `"PREPACK NOISE\n" + json.dumps([...])` stdout, then `self.assertIn("PREPACK NOISE", log_contents)` confirms the prefix survived into the log even though the parsing path stripped it.

## 4. Per-finding narrative

None. No CONCERN or FIX-REQUIRED findings.

The fix is correctly scoped, fails closed on the degenerate case with an informative error (including a `repr()`-quoted stdout snippet capped at 200 chars, which avoids both encoding surprises in the log and unbounded message growth), preserves the post-mortem log invariant, and is backed by both unit tests (mocked, fast) and a real round-trip test (skips when `npm`/`python3` missing — appropriate for CI environments without npm). The commit message also documents that mutation verification was performed (reverted the stderr fix → real round-trip test FAILED with the exact pollution detection message → restored via `shutil.copy2` from a /tmp snapshot per `feedback_mutation_bite_pycache`).

## 5. Optional NITs

- **NIT (non-blocking):** `find("[")` will also accept stdout that contains a `[` inside the pollution prefix (e.g., a hypothetical `"[INFO] staged ...\n<json>"` prefix). In such a pathological case, the slice would start at the first `[` of the prefix and `json.loads` would fail with the existing `JSONDecodeError` path (line 326–327), still failing closed with a clear error. Not a correctness defect — the failure mode is benign and the existing test `test_stdout_with_no_bracket_fails_with_clear_error` plus the JSONDecodeError path together cover the degenerate space. Adding a test like `test_pollution_containing_bracket_falls_through_to_jsondecode` would be belt-on-suspenders-on-belt and is not warranted at this scope.
- **NIT (non-blocking):** The fix targets `[` as the JSON-array start sentinel. `npm pack --json` is documented to return an array, and the round-trip test asserts that contract (`assertIsInstance(data, list)`). If npm ever changed the top-level shape to an object, the fix would need a `{`-fallback — but the round-trip test would catch that regression on the next publish dry-run. Acceptable scope.
- **NIT (non-blocking):** The fix-comment block (lines 308–312) references "instruction 203" inline — good provenance for future maintainers tracing the fix.

## 6. Final verdict

```
VERDICT: SHIP
```
