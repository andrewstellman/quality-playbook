# CPython Packaging and Installation Tooling

## Overview

CPython ships several modules that together handle the creation, installation, and management of Python packages and virtual environments. These range from low-level installation infrastructure (`sysconfig`, `site`) through environment isolation (`venv`) to the pip bootstrapping mechanism (`ensurepip`). Third-party packaging tools (pip, setuptools, wheel, build, twine) are not part of CPython itself but integrate through the interfaces described here.

## `sysconfig` — Build Configuration and Install Paths

`Lib/sysconfig/__init__.py` exposes the configuration data generated at build time and provides install-path resolution.

**Key functions:**
- `get_config_var(name)` — returns a single build variable (e.g., `CC`, `CFLAGS`, `LDFLAGS`, `EXT_SUFFIX`, `SOABI`, `py_version_short`). Returns `None` for unknown variables.
- `get_config_vars(*names)` — returns a dict of all (or selected) build variables.
- `get_path(name, scheme, vars)` — resolves an installation path. `name` is one of `stdlib`, `platstdlib`, `purelib`, `platlib`, `include`, `platinclude`, `scripts`, `data`. `scheme` selects the installation layout.
- `get_paths(scheme, vars)` — returns a dict of all paths for a scheme.
- `get_scheme_names()` — lists available installation schemes.
- `get_platform()` — returns a platform tag (e.g., `linux-x86_64`, `macosx-14.0-arm64`).
- `get_python_version()` — returns `'3.15'` (major.minor string).
- `parse_config_h(fp, vars)` — parses a `pyconfig.h`-style file.

**Installation schemes** define where the installer puts files for different environments:
- `posix_prefix` — standard Unix install under a prefix.
- `posix_home` — `--home`-style install into a user-specified home directory.
- `posix_venv` — used when bootstrapping virtual environments; identical to `posix_prefix` by design, intentionally not modified by downstream distributors.
- `nt` — Windows install layout.
- `nt_venv` — Windows virtual environment.
- User-scheme variants: `posix_user`, `nt_user` — for `pip install --user`.

Downstream distributors (Debian, Fedora, etc.) may override `posix_prefix` to reflect their modified layout (e.g., putting pure-Python packages in a different directory). The `*_venv` schemes are intentionally kept stable to ensure virtual environment creation works regardless of distributor modifications.

## `site` — Site-Packages Initialization

`Lib/site.py` is imported automatically during interpreter startup (unless `-S` is passed). It:

1. Adds `site-packages` and `dist-packages` directories to `sys.path` using the `sysconfig` install paths.
2. Processes `.pth` files found in those directories (each non-comment line is either a path to add to `sys.path` or a Python statement to `exec`).
3. Installs `sitecustomize` and `usercustomize` modules if they exist.
4. Sets `sys.prefix`, `sys.exec_prefix`, `sys.base_prefix`, `sys.base_exec_prefix`.

Virtual environments are detected by the presence of `pyvenv.cfg`; in that case, `site.py` adjusts paths to point into the virtual environment.

## `venv` — Virtual Environments (PEP 405)

`Lib/venv/` implements lightweight isolated Python environments. A virtual environment is a directory containing:
- A copy or symlink of the Python executable.
- A `pyvenv.cfg` file recording the `home` path and version.
- A `lib/pythonX.Y/site-packages/` directory for installed packages.

**Creating a virtual environment:**
```sh
python -m venv /path/to/env
```
Or programmatically:
```python
import venv
venv.create('/path/to/env', with_pip=True, symlinks=True, clear=False, upgrade=True)
```

Key `create()` parameters:
- `system_site_packages=True` — makes the base installation's site-packages visible inside the environment.
- `with_pip=True` — calls `ensurepip` to install pip inside the environment.
- `symlinks=True` — uses symlinks instead of copies for the Python binary (default on non-Windows).
- `upgrade=True` — upgrades an existing environment in-place.
- `prompt` — sets the environment's prompt prefix.

The `EnvBuilder` class is the primary extension point; subclasses can override `setup_python`, `setup_scripts`, `post_setup`, and `install_scripts` to customize environment creation.

## `ensurepip` — pip Bootstrapping (PEP 453)

`Lib/ensurepip/` bundles the pip wheel directly in the standard library and provides the mechanism to install it. It does not use the network; all files needed to bootstrap pip are included as internal parts of the package.

**Command-line usage:**
```sh
python -m ensurepip             # install pip if not present
python -m ensurepip --upgrade   # upgrade pip
python -m ensurepip --default-pip  # also install pip without version suffix
```

**Programmatic API:**
- `ensurepip.version()` — returns the version of pip that would be installed.
- `ensurepip.bootstrap(root, upgrade, user, altinstall, default_pip, verbosity)` — installs pip into the environment.

`ensurepip` is called by `venv.create(with_pip=True)`. The bundled pip version is updated with each CPython release.

## `zipimport` — Importing from ZIP Files

`zipimport.zipimporter` implements the `PathEntryFinder` and `Loader` protocols for paths that point to zip files (or paths within zip files). `sys.path` entries ending in `.zip` are handled automatically. The frozen import bootstrap ensures that the interpreter can import from a zip without depending on the file system being ready.

## `zipapp` — Creating Executable Archives

`zipapp` creates `.pyz` archives: zip files with a `__main__.py` entry point and a `#!` shebang, runnable as `python archive.pyz`. The API is `zipapp.create_archive(source, target, interpreter, main, filter, compressed)`.

## `compileall` — Pre-Compiling Python Files

`compileall.compile_dir(dir, ...)` and `compile_file(fullname, ...)` produce `.pyc` files in `__pycache__/` directories. `python -m compileall <path>` does the same from the command line. Pre-compilation improves startup time by skipping the source-to-bytecode compilation step.

## `py_compile` — Single-File Bytecode Compilation

`py_compile.compile(file, cfile, dfile, doraise, optimize, invalidation_mode, quiet)` compiles one source file to bytecode. The `invalidation_mode` parameter controls how the `.pyc` file is validated on future imports: `TIMESTAMP` (default), `CHECKED_HASH`, or `UNCHECKED_HASH`.

## `pkgutil` — Package Utilities

`pkgutil` provides utilities for working with packages and the import system:
- `pkgutil.iter_modules(path, prefix)` — iterates over top-level modules and packages available on `path`.
- `pkgutil.walk_packages(path, prefix, onerror)` — recursively walks all packages.
- `pkgutil.get_data(package, resource)` — reads a resource file from inside a package (falls back to `importlib.resources`).
- `pkgutil.resolve_name(name)` — resolves a dotted name to a Python object.

## `importlib.resources` — Package Resource Access

`importlib.resources` provides a portable API for accessing data files included in packages:
- `importlib.resources.files(package)` — returns a `Traversable` representing the package's resource root.
- `importlib.resources.as_file(path)` — context manager yielding a `pathlib.Path` to a (possibly extracted) resource.
- `importlib.resources.contents(package)` — lists available resources in a package.

This API works correctly whether the package is installed as source, as a wheel, or as a frozen module.
