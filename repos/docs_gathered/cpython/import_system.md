# CPython Import System

## Overview

The import system is the mechanism by which Python code in one module gains access to code in another. It is fully extensible and implemented primarily in Python itself (via `importlib`), with a thin C bootstrap layer that initializes the machinery before the interpreter is ready to run Python code.

## Entry Points

The `import` statement is the most common way to invoke import. Internally it compiles to a call to the built-in `__import__` function. Alternative entry points include:

- `importlib.import_module(name)` — the recommended programmatic interface.
- `importlib.reload(module)` — re-executes the module's code in the existing module object without creating a new one, so previously imported references remain valid.
- `__import__(name, globals, locals, fromlist, level)` — the raw hook; replaceable by setting `builtins.__import__`.

## The Module Cache

The first step in every import is a lookup in `sys.modules`, a dict mapping fully qualified module names to module objects. If the name is found and the value is not `None`, that module object is returned immediately. If the value is `None`, a `ModuleNotFoundError` is raised. This cache is the authoritative registry of loaded modules; code may insert, remove, or replace entries directly, with the understanding that doing so affects all future imports but not existing references held by other modules.

## Finders and Loaders

When a module is not in `sys.modules`, the import machinery walks `sys.meta_path`, a list of **meta path finder** objects, querying each one by calling `finder.find_spec(fullname, path, target)`. A finder that can locate the module returns a `ModuleSpec` object (defined in `importlib.machinery`); a finder that cannot returns `None`. The first non-`None` spec wins.

A `ModuleSpec` encapsulates:
- The fully qualified name.
- The **loader** that will execute the module's code.
- The origin (file path or `None` for namespace packages).
- Whether the module is a package (has a `__path__` attribute).
- Submodule search locations (`submodule_search_locations`).

The loader's `exec_module(module)` method (or the older `load_module` for legacy loaders) performs the actual code execution. The import machinery creates the module object, inserts it into `sys.modules` before execution begins, and removes it if execution fails — this ordering ensures that circular imports see a partially-initialized module rather than triggering infinite recursion.

## Default Meta Path Finders

CPython installs three default finders on `sys.meta_path` at startup:

1. **`BuiltinImporter`** — handles modules compiled directly into the interpreter binary (e.g., `sys`, `builtins`). These are listed in `sys.builtin_module_names`.
2. **`FrozenImporter`** — handles modules whose bytecode has been frozen into the interpreter binary. The core importlib bootstrap modules are frozen this way so that import machinery is available before the file system is accessible.
3. **`PathFinder`** — searches `sys.path` (and per-package `__path__` attributes) for modules on the file system or in zip archives. Each entry in `sys.path` is passed to callables in `sys.path_hooks`; a matching hook returns a **path entry finder** for that location. Results are cached in `sys.path_importer_cache`.

## Import Hooks

Two extension points allow third-party code to customize import:

- **Meta hooks** — objects appended to `sys.meta_path`. They are consulted before any default processing, allowing interception of all imports including built-ins.
- **Path hooks** — callables in `sys.path_hooks`. When `PathFinder` encounters a path entry it has not seen before, it tries each hook in order until one returns a finder for that path entry (or raises `ImportError`).

These hooks are the standard mechanism for importing from zip files (via `zipimport.zipimporter`), from network locations, or from any custom storage backend.

## Packages

A **package** is a module that has a `__path__` attribute. Regular packages correspond to directories containing an `__init__.py`; that file is executed when the package is imported. **Namespace packages** (PEP 420) have no `__init__.py`; they are assembled from multiple directory portions across `sys.path` and use a custom iterable for `__path__` that triggers a new search if the parent path changes.

Subpackage names are dot-separated. Importing `foo.bar.baz` causes Python to import `foo`, then `foo.bar`, then `foo.bar.baz` in sequence; each intermediate import may trigger execution of its respective `__init__.py`.

## Relative Imports

Inside a package, `from . import sibling` or `from ..parent import x` use the current package's `__name__` and `__package__` attributes to resolve the dot prefix to an absolute name before performing the normal search.

## The importlib Source Layout

The `Lib/importlib/` package contains:
- `_bootstrap.py` — frozen into the interpreter; provides the core machinery that must be available before the file system is accessible.
- `_bootstrap_external.py` — also frozen; adds file-system-based loaders (`SourceFileLoader`, `SourcelessFileLoader`, `ExtensionFileLoader`).
- `abc.py` — abstract base classes (`MetaPathFinder`, `PathEntryFinder`, `Loader`, `ResourceLoader`, `InspectLoader`, `ExecutionLoader`, `SourceLoader`).
- `machinery.py` — re-exports concrete finder and loader classes.
- `util.py` — utilities for loader implementors, including `module_from_spec`, `spec_from_file_location`, and `LazyLoader`.
- `resources/` — the resource-reading API for accessing data files bundled with packages.

## Error Propagation

`ModuleNotFoundError` (a subclass of `ImportError`) is raised when no finder returns a spec. Any other exception raised during module execution propagates normally; the partially-initialized module is removed from `sys.modules` so that a subsequent import attempt starts fresh.
