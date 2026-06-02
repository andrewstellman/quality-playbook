# Command System

Setuptools (like distutils before it) is organised around the command pattern. Each unit of build work — compiling Python modules, packaging an sdist, writing egg-info, building a wheel — is implemented as a `Command` subclass under `setuptools/command/`. The `Distribution` holds an ordered registry of these commands and orchestrates them.

## Command base class

`setuptools.Command` is defined in `setuptools/__init__.py` and extends `distutils.core.Command`. The protocol every command implements:

- `initialize_options(self)` — set instance attributes to their defaults.
- `finalize_options(self)` — validate and finalise option values, often after pulling defaults from the `Distribution`.
- `run(self)` — perform the actual work, optionally delegating to subcommands via `self.run_command(name)`.

Commands declare a `user_options` list (a triple of long-form option name, short flag, and help text) so they can be invoked from the command line, and a `description` string used by `--help-commands`.

## Built-in commands

The `setuptools/command/` directory contains:

- **Building.** `build` (umbrella), `build_py` (pure-Python modules + package data), `build_ext` (C/Cython extensions), `build_clib`, `build_scripts`.
- **Packaging.** `sdist` (source distribution), `bdist_wheel` (wheel), `bdist_egg` (legacy egg), `bdist_rpm`, `dist_info`, `egg_info` (writes `.egg-info/` metadata).
- **Installation.** `install`, `install_lib`, `install_scripts`, `install_egg_info`, `develop` (legacy editable), `editable_wheel` (PEP 660 editable).
- **Utilities.** `alias`, `saveopts`, `setopt`, `rotate`, `easy_install` (deprecated installer entry point), `test` (legacy `python setup.py test`).

Subcommand chains are declared in `build.sub_commands` (`build_py`, `build_clib`, `build_ext`, `build_scripts`) so calling `build` runs each of them in order if they have work to do.

## Subcommand protocol for editable installs

`setuptools/command/build.py` defines a `SubCommand` `Protocol` describing what each build subcommand exposes so editable installs (PEP 660) can compose them: a writable `editable_mode` attribute, plus `get_outputs()` and `get_output_mapping()` methods that report which files will be produced and how source paths map to build paths. Subcommands honour `editable_mode=True` by returning early when generated artifacts are unnecessary, or by writing files in place so the editable install can link them back to the source tree.

## Extending via entry points

The `distutils.commands` entry-point group lets third-party packages register additional commands once installed. Setuptools' own commands are registered the same way.
