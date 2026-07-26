# CPython Documentation Corpus — Manifest

| File | Description |
|------|-------------|
| `object_model.md` | The runtime object foundation: PyObject layout, type slots, reference counting, memory management, error-handling conventions, and the C API's ownership model. |
| `import_system.md` | The module import machinery: finders, loaders, module specs, the sys.modules cache, import hooks, packages, namespace packages, and the importlib source layout. |
| `io_and_filesystem.md` | The layered I/O class hierarchy (raw, buffered, text), the open() built-in, the os module's filesystem interface, pathlib, os.path, shutil, tempfile, and codec handling. |
| `data_types.md` | Built-in scalar and container types (int, float, complex, str, bytes, tuple, list, range, dict, set), the collections module's specialized containers, and the abstract base classes for collections. |
| `numeric_stack.md` | The numeric ABC tower (numbers.py), arbitrary-precision int, IEEE 754 float, decimal exact arithmetic, fractions rational arithmetic, math, cmath, statistics, random, and struct. |
| `networking.md` | The socket module's BSD socket interface, TLS via ssl, http.client, urllib, http.server, socketserver, the email package, asyncio networking APIs, selectors, and json. |
| `concurrency.md` | The GIL and free-threaded build, threading (Thread, Lock, Condition, Semaphore, Barrier, local), concurrent.futures (ThreadPoolExecutor, ProcessPoolExecutor, Future), multiprocessing, asyncio event loop and tasks, queue, and contextvars. |
| `build_system.md` | The Autoconf/Make build system, configure.ac options (PGO, LTO, GIL-disabled, JIT, ABI), generated source files and regen-* targets, the Clinic tool, Windows PCbuild, platform-specific builds, and the stable ABI. |
| `packaging.md` | sysconfig installation paths and schemes, site.py path initialization, venv virtual environments (PEP 405), ensurepip pip bootstrapping (PEP 453), zipimport, zipapp, compileall, py_compile, pkgutil, and importlib.resources. |
| `testing.md` | The unittest framework (TestCase, assert methods, skip decorators, subtests), doctest, the Lib/test/ directory structure, test.support utilities, the libregrtest harness and its command-line options, and CPython testing conventions. |
| `interpreter_and_compiler.md` | The end-to-end compilation pipeline (lexer → PEG parser → AST → compiler → CFG optimizer → assembler), the PyCodeObject format, the adaptive Tier 1 interpreter with specialization, the Tier 2 micro-op optimizer and JIT, zero-cost exception handling, and frame lifecycle. |
