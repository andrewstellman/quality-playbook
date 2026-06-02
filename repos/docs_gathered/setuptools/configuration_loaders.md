# Configuration Loaders

Setuptools accepts project configuration from three sources at this version: `pyproject.toml`, `setup.cfg`, and `setup.py`. The first two are read by dedicated loader modules under `setuptools/config/`; the third is executed inside a managed environment as part of the build.

## pyproject.toml

Module `setuptools/config/pyprojecttoml.py` implements the PEP 621 reader.

- `load_file(filepath)` — opens the file in binary mode and parses it via `tomllib` (3.11+) or `tomli` (older).
- `validate(config, filepath)` — runs the JSON-Schema validator in `setuptools/config/_validate_pyproject/` against the parsed TOML. The schema is also exposed as `setuptools/config/setuptools.schema.json` and `setuptools/config/distutils.schema.json`.
- `read_configuration(filepath, expand=True, ignore_option_errors=False, dist=None)` — top-level entry point returning a dict.
- `apply_configuration(dist, filepath, ignore_option_errors=False)` — calls `read_configuration` and applies the result onto a `Distribution` via `_apply_pyprojecttoml.apply`.

The module also handles the `project.dynamic` mechanism: fields listed there are resolved later via `setuptools.config.expand` (which can call `attr:` or `file:` directives or invoke a callable).

## setup.cfg

Module `setuptools/config/setupcfg.py` implements the declarative INI loader.

- `read_configuration(filepath, find_others=False, ignore_option_errors=False)` — parses with `configparser` and returns a dict.
- Helper types `SingleCommandOptions` and `AllCommandOptions` are exposed as `TypeAlias`es. They map command names to `{option_name: (source, value)}` tuples, where `source` records the origin file. This preserves provenance for later diagnostic messages.
- Per-section handlers (`ConfigMetadataHandler`, `ConfigOptionsHandler`) translate `[metadata]`, `[options]`, `[options.packages.find]`, `[options.entry_points]`, `[options.extras_require]`, `[options.package_data]`, etc.

Directives understood inside values include `file:` (read content from one or more files), `attr:` (import the listed attribute from a module), and `find:` / `find_namespace:` (delegate package discovery).

## setup.py

`setup.py` remains supported but is executed inside the `setuptools.build_meta` context. The backend installs the setuptools `Distribution` in place of the distutils one and reads the script via `tokenize.open`, so non-UTF-8 encodings declared with a PEP 263 coding line are honoured.

## Schemas

The JSON-Schema files in `setuptools/config/` give the validator a single source of truth for what keys, types, and combinations are accepted. They are bundled at install time so validation works without network access.
