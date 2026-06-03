# MANIFEST

Reference documentation for the setuptools library, organised by subsystem.

- `architecture_overview.md` — Top-level package layout, the four conceptual layers, and how the major components relate.
- `build_backend.md` — The PEP 517 / PEP 660 interface exposed by `setuptools.build_meta` and the hooks frontends call.
- `distribution_model.md` — The `Distribution` class, metadata generation, normalisation helpers, and the static-value markers.
- `command_system.md` — The `Command` base class, built-in commands under `setuptools/command/`, and the subcommand protocol.
- `configuration_loaders.md` — Readers for `pyproject.toml` and `setup.cfg`, the validation schema, and the `setup.py` execution path.
- `package_discovery.md` — `find_packages`, `find_namespace_packages`, project-layout detection, and `ConfigDiscovery`.
- `wheels_and_entry_points.md` — `bdist_wheel`, wheel filename parsing, and the entry-point groups setuptools defines.
- `pkg_resources_api.md` — The legacy `pkg_resources` package: working sets, distributions, requirements, and resource access.
