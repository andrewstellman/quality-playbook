# Distribution Model

The `Distribution` class in `setuptools/dist.py` is the central data object that holds everything setuptools knows about a project being built: name, version, dependencies, package layout, entry points, command registrations, and the parsed configuration files. It subclasses `distutils.dist.Distribution` and replaces it via the monkey-patching layer in `setuptools.monkey` (see `setuptools/monkey.py`, module docstring "Monkey patching of distutils").

## Construction

`Distribution.__init__(attrs)` accepts a mapping of keyword arguments compatible with the historical `setup()` call: `name`, `version`, `packages`, `install_requires`, `extras_require`, `entry_points`, `package_dir`, `package_data`, `include_package_data`, `scripts`, `ext_modules`, `cmdclass`, and many more. Each is normalised and validated through helpers in `_core_metadata.py`, `_reqs.py`, and `_normalization.py`.

Construction proceeds in a fixed order:

1. Pre-process: filter and rename legacy attributes.
2. Apply defaults: `Distribution.set_defaults` walks the standard attribute list and applies fallback values, including auto-discovery of packages and metadata (see `ConfigDiscovery` from `setuptools/discovery.py`).
3. Parse config files: `pyproject.toml` first (via `setuptools.config.pyprojecttoml.apply_configuration`), then `setup.cfg` (via `setuptools.config.setupcfg.apply_configuration`).
4. Resolve dynamic fields: any field listed under `project.dynamic` is resolved with help from `setuptools.config.expand`.

## Metadata surface

`_core_metadata.py` produces the `PKG-INFO` / `METADATA` payload from the `Distribution`. It implements the Core Metadata specification fields (e.g., `Name`, `Version`, `Summary`, `Author`, `Author-email`, `Requires-Dist`, `Provides-Extra`, `Project-URL`, `License-Expression`, `License-File`).

`_normalization.py` provides:

- `safe_name`, `safer_name` — produce PEP 503 canonical / wheel-safe project names.
- `safe_version` — convert arbitrary strings to PEP 440 versions.
- `_canonicalize_license_expression` — normalise SPDX expressions used by the `license` field.

## Static vs computed values

`setuptools/_static.py` introduces marker subclasses (`Str`, `List`, `Dict`, `Tuple`, `Set`) that flag values originating from a static configuration source (TOML or INI). Downstream tools can distinguish between values that came verbatim from a config file and values produced by dynamic expansion at build time.

## Command graph hookup

`Distribution.cmdclass` is a dict mapping command names (e.g., `bdist_wheel`, `egg_info`) to `Command` subclasses. Defaults are installed via the import-time side effects in `setuptools/command/__init__.py`, but user projects can override individual commands either via `setup(cmdclass=...)` or via the `distutils.commands` entry point group, which lets installed third-party packages contribute commands globally.
