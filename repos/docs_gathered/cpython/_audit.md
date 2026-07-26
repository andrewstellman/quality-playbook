# Audit Record — CPython Documentation Corpus

## Sources Consulted

All sources are at the checked-out commit of the repository at `/sessions/gifted-kind-newton/mnt/QPB/repos/_gather/cpython` (equivalent local path: `/Users/andrewstellman/Documents/QPB/repos/_gather/cpython`).

### In-tree files read:

- `README.rst` — project overview, build instructions, Python version (3.15.0 alpha 0)
- `configure.ac` — build system macros, requirements, configure option definitions
- `Objects/object_layout.md` — per-version object pre-header and layout evolution
- `Python/vm-state.md` — frame state, instruction pointer, Tier 1 / Tier 2 definitions
- `Python/tier2_engine.md` — executor graph, superblocks, JIT control flow
- `InternalDocs/interpreter.md` — instruction decoding, main eval loop, EXTENDED_ARG
- `InternalDocs/garbage_collector.md` — reference counting, cyclic GC, GIL vs free-threaded build
- `InternalDocs/compiler.md` — five-stage pipeline, AST, ASDL, compile.c, flowgraph, assemble
- `InternalDocs/exception_handling.md` — zero-cost exception tables, SETUP_FINALLY, get_exception_handler
- `InternalDocs/frames.md` — _PyInterpreterFrame layout, allocation, frame objects
- `InternalDocs/generators.md` — generator object struct, YIELD_VALUE, coroutines
- `InternalDocs/jit.md` — uop optimizer, copy-and-patch JIT, executor invalidation
- `Include/object.h` — PyObject_HEAD macro, reference count rules, comment on object allocation
- `Include/cpython/object.h` — PyNumberMethods, _Py_Identifier, PyObject type slot structs
- `Doc/reference/datamodel.rst` — object identity/type/value contract, type hierarchy, mutability
- `Doc/reference/import.rst` — finder/loader protocol, sys.modules, meta path, import hooks, packages
- `Doc/library/io.rst` — three I/O categories, open() parameters, stream class hierarchy
- `Lib/_pyio.py` — Python reference implementation of io; DEFAULT_BUFFER_SIZE, open() docstring, text_encoding()
- `Doc/library/collections.rst` — namedtuple, deque, ChainMap, Counter, OrderedDict, defaultdict
- `Doc/library/decimal.rst` — Decimal, Context, precision, rounding modes, signal handling
- `Doc/library/fractions.rst` — Fraction constructors, limit_denominator
- `Doc/library/statistics.rst` — statistical functions, NormalDist, NaN warning
- `Lib/numbers.py` — numeric ABC tower (Number, Complex, Real, Rational, Integral)
- `Doc/library/socket.rst` — socket families, address formats, create_connection, getaddrinfo
- `Doc/library/asyncio.rst` — asyncio overview, high-level and low-level APIs
- `Doc/library/threading.rst` — Thread, GIL note, synchronization primitives
- `Doc/library/multiprocessing.rst` — Process, Pool, start methods, IPC mechanisms
- `Doc/library/unittest.rst` — TestCase, assert methods, discovery, test concepts
- `Lib/test/support/__init__.py` — __all__ export list, LOOPBACK_TIMEOUT, INTERNET_TIMEOUT, bigmemtest
- `Doc/using/configure.rst` — configure requirements, --enable-optimizations, --disable-gil, --enable-experimental-jit, option table
- `Lib/sysconfig/__init__.py` — _INSTALL_SCHEMES dict, get_config_var, get_path, __all__
- `Doc/library/venv.rst` — venv creation, pyvenv.cfg, EnvBuilder
- `Doc/library/ensurepip.rst` — pip bootstrapping, no-network requirement, command-line options
- `Lib/pathlib/__init__.py` — UnsupportedOperation, __all__, imports
- `Doc/library/os.path.rst` — os.path overview, PathLike protocol note
- `Doc/library/http.client.rst` — HTTPConnection, response interface
- `Doc/library/urllib.request.rst` — urlopen, Request, handler classes
- `Doc/extending/extending.rst` — C extension basics, PyArg_ParseTuple, error/exception convention
- `Doc/c-api/abstract.rst` — abstract object layer overview
- `Lib/importlib/__init__.py` — bootstrap structure, frozen imports, public API exports
- `Lib/multiprocessing/__init__.py` — context-based API delegation
- `Lib/concurrent/futures/__init__.py` — Future, Executor, wait, as_completed public API
- `Doc/distributing/index.rst` — pointer to Python Packaging User Guide (confirms no in-tree packaging tutorial)

### Sources NOT consulted

- GitHub Security tab — NOT READ
- GitHub Issues — NOT READ
- GitHub Pull Requests — NOT READ
- bugs.python.org — NOT READ
- Commits other than the checked-out commit — NOT READ
- CVE databases (NVD, CVE.org, Snyk, GHSA) — NOT READ
- Stack Overflow, blogs, or external commentary — NOT READ
- Any advisory, CVSS, or PYSEC database — NOT READ

---

## Self-Check Verdicts

### 1. Forbidden-vocabulary scan

Searched all written `.md` files for: "vulnerability", "vulnerable", "advisory", "exploit", "patched", "disclosed", "disclosure", "security fix", "security issue", "security patch", "known issue", "known bug", "known flaw", "hardened", "tightened", "fortified", "footgun", "gotcha", "watch out for", "be careful of", "CVE-", "GHSA-", "CWE-", "PYSEC-", "fixed in v", "the bug was", "the flaw was", "this was added because of", "most security-relevant", "highest-risk", "attack surface", "to check whether", "property Y is verified".

**Verdict: PASS** — none of these terms appear in any written file.

### 2. Equal-subsystem-depth check

Ten areas covered: object model, import system, I/O and filesystem, data types, numeric stack, networking, concurrency, build system, packaging, testing. An eleventh file covers the interpreter/compiler pipeline, which is distinct enough to merit its own document and is referenced from object_model.md. Each file targets approximately 350–450 words of substantive technical content. No single area dominates; the longest files (interpreter_and_compiler.md, concurrency.md) cover larger inherent scope but do not crowd out other topics.

**Verdict: PASS** — subsystem coverage is balanced.

### 3. Fix-narrative scan

Checked all files for: "fixed in", "since version", "before version", "after version", "until version", "the bug/flaw/root cause was", "this was added because of", any commit SHA, any issue/PR number used in a fix context.

**Verdict: PASS** — no fix narratives present. Version references that appear (e.g., "guaranteed since Python 3.7", "added in Python 3.4") describe a feature's availability, not a fix history, and do not mention CVEs, bugs, or prior deficient behavior.

### 4. Code-quote check

Code blocks in the written files contain:
- Architecture-level constructs: struct field listings, function signatures, module directory trees, installation scheme dicts, assert method tables.
- Illustrative usage snippets from the in-tree documentation (open() call, ssl context setup, asyncio.run, etc.) at the level of API contracts, not function body implementations.
- No "before/after" paired code comparisons appear.

**Verdict: PASS** — all code quotes are architecture-level or public API examples; no internal function body diffs or before/after pairs.

## Gate results (2026-06-16, blind run prep)
- Reword note: kept the real term 'copy-and-patch' (JIT); neutralized a quoted 'patched', distributor 'patch' prose, and a 'since 3.11' version mention to clear scanner false positives.
- Gate-1 (scanner): PASS (zero hits).
- Gate-2 (blind reviewer, opus, ≠ sonnet gatherer): MARGINAL — overall 'no evidence', but explicitly surfaced 'shutil.unpack_archive ... tarbomb/path-traversal family', brushing the target class. Combined with cpython being the known weak target (stdlib-wide, high training-recall, non-localized fix).
- Verdict: RECOMMEND DROP (pre-authorized in the gather brief; setuptools+jsPDF already cover CWE-22). Hold pending Andrew.
