# Architecture Overview

Setuptools is a Python packaging library that builds source and binary distributions for projects. It operates as a :pep:`517` build backend (`setuptools.build_meta`) invoked by frontends such as `pip` and `build`. Internally it inherits and extends Python's historical `distutils` codebase, which is now vendored under `setuptools._distutils` and surfaced again under the `distutils` import name via the `_distutils_hack` shim.

## Top-level package layout

At this version, the repository contains three importable packages plus supporting infrastructure:

- `setuptools/` — the main packaging library. Public surface includes `setuptools.setup`, `setuptools.Distribution`, `setuptools.Extension`, `setuptools.Command`, and the helpers `find_packages` and `find_namespace_packages`.
- `setuptools/_distutils/` — a vendored copy of `distutils`, kept in tree because the standard-library version was removed in Python 3.12 (per :pep:`632`).
- `pkg_resources/` — a separate top-level package providing the legacy resource-and-distribution API used by older code that needed runtime introspection of installed distributions.
- `_distutils_hack/` — an import shim that ensures any `import distutils` resolves to the bundled copy in setuptools.
- `setuptools/_vendor/` — third-party dependencies (e.g. `packaging`, `more_itertools`, `jaraco.text`, `wheel`) bundled to keep the build backend self-contained.
- `launcher/` and the pre-built `cli-*.exe`, `gui-*.exe` binaries — Windows entry-point launchers used to wrap installed console and GUI scripts.

## Layered model

The library has four conceptual layers:

1. **Backend interface** (`setuptools/build_meta.py`) — the :pep:`517` entry points (`build_wheel`, `build_sdist`, `prepare_metadata_for_build_wheel`, `build_editable`, etc.) that frontends call.
2. **Distribution model** (`setuptools/dist.py`, `setuptools/_core_metadata.py`) — the `Distribution` class that holds project metadata, requirements, and the registered command graph.
3. **Command graph** (`setuptools/command/*`) — the per-action classes (`build_py`, `bdist_wheel`, `sdist`, `egg_info`, `editable_wheel`, `install`, …) that implement the actual work of producing artifacts. Each is a `setuptools.Command` subclass and many extend their `distutils` counterparts.
4. **Configuration loaders** (`setuptools/config/*`) — readers for `pyproject.toml`, `setup.cfg`, and `setup.py`, which populate the `Distribution`.

Auxiliary modules around the four layers handle discovery (`discovery.py`), wheel parsing (`wheel.py`), namespace packages (`namespaces.py`), and Windows specifics (`windows_support.py`, `msvc.py`).
