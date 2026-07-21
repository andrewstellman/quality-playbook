# CPython Testing Framework and Conventions

## Overview

CPython's test suite lives under `Lib/test/` and is one of the largest test suites in any open-source project. Tests are written using the `unittest` module from the standard library, extended by a large body of test support utilities in `Lib/test/support/`. The suite is run by the `libregrtest` harness, which handles parallelism, resource management, platform skipping, and reporting.

## `unittest` — The Test Framework

`Lib/unittest/` implements a JUnit-style test framework. The core abstractions are:

- **`TestCase`** — the base class for test classes. Each method whose name begins with `test` is a test. `setUp()` and `tearDown()` run before and after each test method; `setUpClass()` and `tearDownClass()` (class methods) run once per class.
- **`TestSuite`** — a collection of `TestCase` instances or other suites; used to aggregate tests.
- **`TestLoader`** — discovers tests from modules, classes, or directories. `TestLoader.loadTestsFromModule`, `loadTestsFromTestCase`, `discover(start_dir, pattern)`.
- **`TestRunner`** — executes a suite and reports results. `TextTestRunner` writes to a stream; `unittest.main()` is the command-line entry point.
- **`TestResult`** — accumulates pass/fail/error/skip counts and traceback text.

### Assert Methods

`TestCase` provides a rich vocabulary of assertion methods:

| Method | Tests |
|--------|-------|
| `assertEqual(a, b)` | `a == b` |
| `assertNotEqual(a, b)` | `a != b` |
| `assertTrue(x)` | `bool(x)` |
| `assertFalse(x)` | `not bool(x)` |
| `assertIs(a, b)` | `a is b` |
| `assertIsNone(x)` | `x is None` |
| `assertIn(a, b)` | `a in b` |
| `assertRaises(exc, callable, *args)` | callable raises exc |
| `assertRaisesRegex(exc, regex, ...)` | message matches regex |
| `assertWarns(warning, ...)` | callable emits warning |
| `assertAlmostEqual(a, b, places)` | `round(a-b, places) == 0` |
| `assertRegex(text, regexp)` | `re.search(regexp, text)` |
| `assertMultiLineEqual(a, b)` | equality with diff output |
| `assertListEqual`, `assertDictEqual`, `assertSetEqual`, `assertTupleEqual` | typed equality with diffs |
| `assertLogs(logger, level)` | context manager checking log records |
| `assertNoLogs(logger, level)` | context manager checking no log records |

### Skipping and Expected Failures

- `@unittest.skip(reason)` — unconditionally skip.
- `@unittest.skipIf(condition, reason)` — skip if condition is true.
- `@unittest.skipUnless(condition, reason)` — skip unless condition is true.
- `@unittest.expectedFailure` — mark a test expected to fail; passes if it does fail, counts as an unexpected success if it passes.

### Subtests

`with self.subTest(key=value):` runs a block of assertions as a named sub-case within a test method. Failures are reported individually without stopping the remaining subtests.

## `doctest` — Embedded Tests in Docstrings

`doctest` finds and runs examples in docstrings (lines starting with `>>>` in the interactive-session style). `doctest.testmod(module)` tests all examples in a module's docstrings. `doctest.run_docstring_examples(f, globs)` tests a single object. The `doctest` module is commonly used to keep usage examples accurate, not as a replacement for comprehensive unit tests.

## The `Lib/test/` Directory Structure

```
Lib/test/
  __init__.py          # identifies the package; re-exports run_tests
  __main__.py          # entry point for `python -m test`
  support/             # test helper utilities
    __init__.py        # the bulk of the support API
    import_helper.py   # import isolation helpers
    os_helper.py       # temp dirs, temp files, filesystem helpers
    script_helper.py   # subprocess-based script runners
    socket_helper.py   # port allocation for network tests
    threading_helper.py
    warnings_helper.py
    bytecode_helper.py
  libregrtest/         # the regression test runner
    main.py            # command-line parsing, test selection, reporting
    runtest.py         # per-test execution, timeout enforcement
    parallel.py        # worker process pool for -jN
  test_*.py            # individual test modules, one per standard library area
```

## `test.support` — Test Utilities

`Lib/test/support/__init__.py` provides a large collection of helpers:

**Platform and capability guards:**
- `requires(resource, msg)` — skips if a resource (network, audio, subprocess, etc.) is unavailable or disabled.
- `cpython_only` decorator — skips on non-CPython implementations.
- `requires_gil_enabled` / `requires_jit_enabled` / `requires_jit_disabled` — capability-specific skips.
- `skip_if_sanitizer(*sanitizers)` — skips under ASAN, MSAN, UBSAN.
- `requires_fork()`, `requires_subprocess()`, `requires_working_socket()`.

**I/O capture:**
- `captured_stdout()`, `captured_stderr()`, `captured_stdin()` — context managers that replace `sys.stdout`, `sys.stderr`, `sys.stdin` with `io.StringIO` instances.

**Timeout constants:**
- `LOOPBACK_TIMEOUT` — for tests using a local loopback server (typically 5s).
- `INTERNET_TIMEOUT` — for tests using a real network server (typically 60s).
- `SHORT_TIMEOUT` — for tests that should complete very quickly (typically 30s).
- `LONG_TIMEOUT` — for tests that may take longer (typically 5 minutes).

**Memory and resource management:**
- `bigmemtest(size, memuse)` — decorator for tests requiring large amounts of memory; controlled by `-M <size>` flag.
- `SuppressCrashReport` — context manager that suppresses OS crash dialog boxes on Windows and core dumps on Unix.

**Filesystem helpers (in `os_helper`):**
- `temp_dir()` — context manager for temporary directories.
- `temp_cwd(name)` — temporary directory + chdir.
- `unlink(filename)` — silent unlink.
- `TESTFN` — a per-test temporary filename constant.

## The `libregrtest` Harness

`python -m test [options] [tests]` is the command-line interface. Key options:

- `-j N` — run N test files in parallel using worker processes.
- `-x test_name` — exclude a test module.
- `-u resource1,resource2` — enable resources (`network`, `subprocess`, `audio`, `gui`, `decimal`, etc.).
- `-W` — turn all warnings into errors.
- `-m testmethod` — run only tests matching a method name pattern.
- `--timeout N` — kill a test process after N seconds.
- `-F` — run continuously in a loop until failure (for flaky test detection).
- `--list-tests` — list test module names without running them.
- `--slowest` — report the N slowest tests.
- `-r` — randomize test order.
- `--randseed N` — use a specific seed for randomization.

## Testing Conventions

CPython test modules follow these conventions:

1. Each module under test has a corresponding `Lib/test/test_<module>.py`.
2. Test classes subclass `unittest.TestCase`. Class names start with `Test`.
3. Tests import from `test.support` for any platform-dependent skipping or resource guarding.
4. Tests that exercise the filesystem create files under `support.TESTFN` or `os_helper.temp_dir()` and clean up in `tearDown` or `addCleanup(os.unlink, path)`.
5. Tests that need network access are guarded by `support.requires('network')`.
6. C-level behavior is sometimes tested using the `ctypes` module or by spawning a subprocess with `subprocess.run` / `script_helper.assert_python_ok`.
7. Timing-sensitive tests use `support.SHORT_TIMEOUT` or `support.LOOPBACK_TIMEOUT` as reference values rather than hard-coded constants.
8. Tests that are expected to be skipped on certain platforms use `@unittest.skipIf(sys.platform == 'win32', ...)` or the `support.requires_*` family.

## `doctest` Integration

Many library modules include doctests in their docstrings. `Lib/test/test_<module>.py` typically includes a `load_tests` function that calls `doctest.DocTestSuite(module)` to pull those examples into the `unittest` runner, ensuring they are exercised by the standard test run.
