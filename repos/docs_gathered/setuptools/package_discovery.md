# Package Discovery

The `setuptools/discovery.py` module finds packages, modules, and project metadata when the user has not enumerated them explicitly. The same machinery powers `find_packages()`, `find_namespace_packages()`, and the auto-discovery that runs when `pyproject.toml` or `setup.cfg` leave fields unset.

## Project layouts

The module recognises three layouts:

- **src-layout** — sources live under `src/<pkg>/`. A `src/` directory at the project root is the trigger.
- **flat-layout** — each top-level package directory sits beside `pyproject.toml`.
- **single-module** — a single `.py` file at the project root, no package directory.

## Finder classes

`_Finder` is the base class. Two public subclasses are exposed via the top-level `setuptools` namespace:

- `PackageFinder` — discovers regular packages (those with `__init__.py`). `find_packages = PackageFinder.find`.
- `PEP420PackageFinder` — discovers implicit namespace packages (PEP 420). `find_namespace_packages = PEP420PackageFinder.find`.

Both expose the same `find(where='.', exclude=(), include=('*',))` classmethod:

```python
from setuptools import find_packages
find_packages(where='src', exclude=['tests*'])
```

`_Filter` is a callable wrapper around an ordered set of fnmatch patterns; finders use one filter for `include` and another for `exclude` to keep matching predictable across platforms.

## Auto-discovery (`ConfigDiscovery`)

`ConfigDiscovery` runs from `Distribution.set_defaults` when the relevant config field is missing. It:

1. Inspects the directory tree to decide which layout applies.
2. Picks a finder (`PackageFinder` or `PEP420PackageFinder`) based on whether any candidate directory contains `__init__.py`.
3. Populates `Distribution.packages`, `package_dir`, and `py_modules`.
4. Refuses to guess when an ambiguous flat layout would force a multi-package distribution; in that case it raises `PackageDiscoveryError` (defined in `setuptools/errors.py`) with a message asking the user to be explicit.

## Name validation

`_valid_name(path)` requires that each path component be a valid Python identifier via `str.isidentifier()`. Anything else is silently skipped, which lets discovery walk past directories such as `docs/`, `tests/`, or generated build folders without producing invalid module names.

## Namespace packages

For PEP 420 namespace packages the finder skips the `__init__.py` requirement and yields any importable subtree. `setuptools/namespaces.py` then handles writing `.pth` files at install time for legacy declarative namespaces.
