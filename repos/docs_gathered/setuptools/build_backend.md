# Build Backend (PEP 517 Interface)

The module `setuptools.build_meta` is the PEP 517 build backend that frontends invoke to produce wheels and source distributions. A consumer project selects it through `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"
```

## Public hook functions

`setuptools/build_meta.py` exports the following names:

- `get_requires_for_build_sdist(config_settings=None)`
- `get_requires_for_build_wheel(config_settings=None)`
- `get_requires_for_build_editable(config_settings=None)`
- `prepare_metadata_for_build_wheel(metadata_directory, config_settings=None)`
- `prepare_metadata_for_build_editable(metadata_directory, config_settings=None)`
- `build_sdist(sdist_directory, config_settings=None)`
- `build_wheel(wheel_directory, config_settings=None, metadata_directory=None)`
- `build_editable(wheel_directory, config_settings=None, metadata_directory=None)`
- `__legacy__` — a backward-compatible backend object kept for projects whose builds still depend on the previous calling conventions.

Each hook returns the basename of the artifact it wrote into the supplied directory, matching the contracts in PEP 517 and PEP 660.

## Internal flow

When a frontend calls `build_wheel`, the module:

1. Reads `pyproject.toml`, `setup.cfg`, and (if present) `setup.py` to construct a `Distribution`.
2. Temporarily replaces `distutils.core.Distribution` with the local `Distribution` subclass via the `Distribution.patch()` context manager, so that any `setup()` call performed by `setup.py` produces a setuptools-aware distribution.
3. Invokes the appropriate command (`bdist_wheel` for wheels, `sdist` for source distributions, `editable_wheel` for editable installs) through the distribution's command machinery.
4. Captures the produced artifact and returns its basename.

For projects that only declare metadata in `pyproject.toml` (no `setup.py`), the backend synthesises an in-memory invocation of `setuptools.setup()` so the rest of the command graph runs unchanged.

## Environment toggles

`SETUPTOOLS_ENABLE_FEATURES` is an environment variable consulted at backend import time. The token `legacy-editable` (the constant `LEGACY_EDITABLE` in the source) routes editable installs through the older `develop` command path instead of the PEP 660 `editable_wheel` path. Hyphens and underscores are treated as equivalent.

## SetupRequirementsError

`build_meta.SetupRequirementsError` is raised by the internal `Distribution.fetch_build_eggs` override to communicate build-time requirement specifiers to the calling frontend. It carries a `.specifiers` attribute with the parsed requirement list, allowing the frontend to install build-time dependencies into the isolated environment before retrying the build.
