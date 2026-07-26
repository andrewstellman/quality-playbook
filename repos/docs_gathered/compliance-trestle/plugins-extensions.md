# Plugin System and Extension Points

Trestle provides a plugin discovery mechanism that allows third-party packages to contribute additional CLI commands and tasks without modifying the core library.

## Plugin Discovery

Plugin discovery is implemented in `trestle/core/plugins.py`:

```python
_discovered_plugins = {
    name: importlib.import_module(name)
    for finder, name, ispkg in pkgutil.iter_modules()
    if name.startswith('trestle_')
}

def discovered_plugins(search_module: str) -> Iterator[Tuple[str, Any]]:
    """Yield discovered plugin classes within a given module name."""
    for plugin, value in _discovered_plugins.items():
        for _, module, _ in pkgutil.iter_modules([pathlib.Path(value.__path__[0], search_module)]):
            plugin_module = importlib.import_module(f'{plugin}.{search_module}.{module}')
            clsmembers = inspect.getmembers(plugin_module, inspect.isclass)
            for _, plugin_cls in clsmembers:
                yield (plugin, plugin_cls)
```

At import time, `_discovered_plugins` is populated with all top-level installed packages whose name begins with `trestle_`. The `discovered_plugins(search_module)` generator then looks inside each discovered package for submodules in a named sub-package (e.g., `commands` or `tasks`), imports them, and yields every class defined there.

## Plugin Naming Convention

A plugin package must:

1. Be installed in the same Python environment as trestle.
2. Have a package name starting with `trestle_` (e.g., `trestle_myorg`).
3. Contain a `commands/` subdirectory for additional CLI commands, or a `tasks/` subdirectory for additional tasks, or both.

## Extending the CLI with Commands

In `trestle/cli.py`, after declaring the built-in `subcommands` list, `Trestle` iterates `discovered_plugins('commands')`:

```python
for plugin, cmd_cls in discovered_plugins('commands'):
    if issubclass(cmd_cls, CommandBase):
        if cmd_cls is not CommandPlusDocs and cmd_cls is not CommandBase:
            subcommands.append(cmd_cls)
```

Any class that inherits from `CommandBase` or `CommandPlusDocs` (excluding those two abstract bases themselves) is appended to the command tree. The new command becomes available as `trestle <command-name>` immediately.

Plugin command classes follow the same protocol as built-in commands:

- Define a `name` class attribute (the CLI verb).
- Implement `_init_arguments(self)` to declare flags.
- Implement `_run(self, args: argparse.Namespace) -> int` returning a `CmdReturnCodes` value.

## Extending Tasks

`TaskCmd` in `trestle/core/commands/task.py` discovers tasks from both the built-in `trestle.tasks` package and from any installed plugin packages that contain a `tasks/` subdirectory. Task discovery uses `pkgutil.iter_modules` over the tasks package path and inspects each module for `TaskBase` subclasses.

Plugin task classes must:

- Inherit from `TaskBase`.
- Define a `name` class attribute matching the INI config section name.
- Implement `print_info()`, `execute()`, and `simulate()`.

Once installed, `trestle task <name>` dispatches to the plugin task using the same configuration file mechanism as built-in tasks.

## Jinja Extensions

The Jinja authoring pipeline supports custom extensions via `trestle/core/jinja/ext.py`. The `extensions` list is passed to the Jinja2 `Environment` constructor. This allows trestle-aware Jinja tags or filters to be registered. Plugin packages may contribute Jinja extensions by placing them in a location discoverable by the Jinja environment.

## Build and Packaging

Trestle uses Hatch as its build backend (`hatchling`). The `pyproject.toml` configuration defines:

- `[build-system]`: `requires = ["hatchling"]`, `build-backend = "hatchling.build"`.
- `[tool.hatch.version]`: version is read from `trestle/__init__.py:__version__`.
- `[tool.hatch.build.targets.sdist]`: includes `trestle/`, excludes `tests/`.
- `[tool.hatch.build.targets.wheel]`: packages `["trestle"]`.

The `dev` optional-dependencies group adds `datamodel-code-generator` for regenerating the OSCAL models from metaschema, `gitpython` for Git integration in scripts, and `python-semantic-release` for automated version management.

Three Hatch environments are defined:

- `default`: adds `coverage` for coverage reporting.
- `hatch-test`: adds `pytest`, `pytest-xdist`, `pytest-randomly`, `mypy`; runs tests in parallel across Python 3.10, 3.11, and 3.12.
- `docs`: adds the full MkDocs toolchain for building the documentation website.

## Configuration Surface

The `.trestle/config.ini` file is the primary configuration mechanism. It is an INI file where each section corresponds to a task (e.g., `[task.csv-to-oscal-cd]`). Section keys are task-specific and documented by each task's `print_info()` method.

There is no global programmatic configuration API beyond the workspace directory convention and the config INI file. Environmental configuration (credentials for remote fetchers) is read from environment variables or a `.env` file loaded by `python-dotenv`.

The `trestle init --full` command copies a default `config.ini` from the package's bundled resources (`trestle/resources/`) into `.trestle/config.ini` as a starting point. The `importlib_resources` package is used to locate and copy these bundled files.
