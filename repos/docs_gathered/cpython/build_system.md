# CPython Build System and Configuration

## Overview

CPython uses a traditional Autoconf/Make build system on Unix-like platforms, a Visual Studio project (`PCbuild/`) on Windows, and Xcode project support for macOS framework builds. The build system is responsible for: detecting platform capabilities, selecting which standard library extension modules to compile, generating C source files from grammar and bytecode DSL inputs, and producing the final `python` binary plus the standard library tree.

## Source Layout

The top-level directories map to distinct roles:

| Directory | Contents |
|-----------|----------|
| `Python/` | Core interpreter: compiler, eval loop, GC, lifecycle, marshal |
| `Objects/` | Built-in type implementations |
| `Parser/` | Lexer, tokenizer, PEG parser, AST |
| `Include/` | Public C API headers; `Include/cpython/` adds internal-but-stable APIs; `Include/internal/` holds private headers |
| `Modules/` | Standard library extension modules written in C |
| `Lib/` | Standard library modules written in Python |
| `Grammar/` | `python.gram` (PEG grammar), `Tokens` (terminal definitions) |
| `Tools/` | Code generators, release tools, test utilities |
| `Doc/` | Sphinx documentation source |
| `Mac/` | macOS-specific build support |
| `PC/` / `PCbuild/` | Windows build files |
| `InternalDocs/` | Design documents for interpreter internals |
| `Misc/` | Changelog (`NEWS`), `SpecialBuilds.txt`, miscellaneous notes |

## `configure.ac` and the Generated `configure` Script

The `configure.ac` script (processed by Autoconf 2.72) drives capability detection. It requires:

- A C11 compiler.
- IEEE 754 floating-point support and NaN support.
- Thread support.
- `pkg-config` for locating external libraries.
- `autoconf-archive` for M4 macros.

The recommended regeneration path is `autoreconf -ivf -Werror` or the helper `Tools/build/regen-configure.sh` (which uses an Ubuntu container for reproducibility). The generated `configure` script is checked in; contributors who modify `configure.ac` must regenerate and commit `configure` and `aclocal.m4`.

## Key `./configure` Options

### General Options

- `--enable-optimizations` — enables Profile-Guided Optimization (PGO) and optionally Link-Time Optimization (LTO). Produces a faster binary by instrumenting a training run, then rebuilding with collected profiling data.
- `--with-pydebug` — enables assertions, reference count debugging (`Py_DEBUG`, `Py_REF_DEBUG`), memory allocator tracking. Used for development builds.
- `--disable-gil` — builds the free-threaded (no-GIL) variant; produces a `python3.Xt` binary where `t` denotes the free-threaded ABI.
- `--enable-experimental-jit[=interpreter|yes]` — enables the Tier 2 optimizer and JIT compiler (copy-and-patch technology). `=interpreter` selects the micro-op interpreter without machine-code generation, useful for debugging.
- `--with-lto[=full|thin|no]` — controls Link-Time Optimization.
- `--enable-big-digits=[15|30]` — controls the internal digit size for `int` arithmetic.
- `--with-suffix=SUFFIX` — sets the Python binary suffix (e.g., `.exe`, `.wasm`).
- `--with-platlibdir=DIRNAME` — sets the platform library directory name (default `lib`; some distros use `lib64`).
- `--with-tzpath=<path-list>` — sets the compile-time default timezone search path for `zoneinfo`.
- `--without-decimal-contextvar` — uses thread-local instead of coroutine-local context for `decimal`.
- `--with-wheel-pkg-dir=PATH` — locates a local wheel directory for `ensurepip`.

### External Library Options

Each major optional extension module has a corresponding `--with-<library>` / `--without-<library>` flag: `--with-openssl`, `--with-sqlite`, `--with-tcl`, `--with-dbmliborder`, `--with-readline` (or `--with-editline`), `--with-zlib`, `--with-bz2`, `--with-lzma`, `--with-uuid`, etc. When a library is absent or explicitly disabled, the corresponding module is omitted from the build.

## `Makefile.pre.in`

The `Makefile.pre.in` template is processed by `./configure` to produce `Makefile`. Key targets:

- `make` — builds the interpreter and extensions.
- `make test` — runs the full regression test suite.
- `make install` — installs to the prefix configured by `--prefix` (default `/usr/local`).
- `make regen-all` — regenerates all generated C source files (parser, bytecode cases, etc.).
- `make regen-configure` — regenerates `configure` from `configure.ac`.
- `make regen-stdlib-module-names` — updates `Python/stdlib_module_names.h`.
- `make regen-limited-abi` — checks/updates the stable ABI list.

## Generated Source Files

To reduce build-time dependencies, CPython checks in several auto-generated C files:

| Generated file | Generator | Inputs |
|----------------|-----------|--------|
| `Parser/parser.c` | `Tools/peg_generator/peg_parser_generator` | `Grammar/python.gram` |
| `Python/generated_cases.c.h` | `Tools/cases_generator/generate_cases.py` | `Python/bytecodes.c` |
| `Python/executor_cases.c.h` | `Tools/cases_generator/tier2_generator.py` | `Python/bytecodes.c` |
| `Python/optimizer_cases.c.h` | `Tools/cases_generator/tier2_optimizer_generator.py` | `Python/bytecodes.c` |
| `Include/internal/pycore_opcode_metadata.h` | `Tools/cases_generator/opcode_metadata_generator.py` | `Python/bytecodes.c` |
| `Python/Python-ast.c`, `Include/cpython/Python-ast.h` | `Parser/asdl_c.py` | `Parser/Python.asdl` |

`make regen-all` regenerates all of these. Contributors who modify the grammar or bytecode DSL must run the appropriate `regen-*` target and commit the updated generated files.

## The Clinic Tool

`Tools/clinic/clinic.py` is the "Argument Clinic" preprocessor that generates argument-parsing boilerplate for C extension functions. Each clinic block in a `.c` file begins with `/*[clinic input]` and ends with `/*[clinic end generated code: ...]`. Running `make clinic` or `python Tools/clinic/clinic.py <file.c>` regenerates the boilerplate. The generated code uses `_PyArg_ParseTupleAndKeywordsFast` for efficient, typed argument parsing.

## Windows Build (`PCbuild/`)

On Windows, CPython is built using Visual Studio 2017 or later. `PCbuild/build.bat` handles downloading external dependencies (OpenSSL, Tcl/Tk, sqlite, etc.) and invoking MSBuild. `PCbuild/readme.txt` documents the process in detail.

## Platform-Specific Builds

- **macOS**: `Mac/README.rst` documents framework builds (producing `Python.framework`), universal binaries (x86_64 + arm64), and the installer creation pipeline.
- **iOS / Android**: `iOS/` and `Android/` directories contain platform-specific support libraries and build scripts.
- **Emscripten / WASI**: `configure` detects these targets and adjusts defaults (e.g., disabling fork/exec-dependent modules, producing `.wasm` or `.html` output).

## ABI Stability

CPython maintains a "limited API" (`Py_LIMITED_API`) and a corresponding "stable ABI". Extension modules compiled with `Py_LIMITED_API` defined (and linked against `python3.dll` / `libpython3.so`) can run on multiple CPython minor versions without recompilation. `Misc/stable_abi.toml` records every function, type, and constant that is part of the stable ABI.
