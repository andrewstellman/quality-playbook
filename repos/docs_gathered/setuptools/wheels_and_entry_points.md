# Wheels and Entry Points

## bdist_wheel

`setuptools/command/bdist_wheel.py` is the command that produces a `.whl` archive. A wheel filename has the form `{name}-{version}(-{build})?-{python}-{abi}-{platform}.whl`, parsed by the regular expression `WHEEL_NAME` in `setuptools/wheel.py`.

Key helpers inside `bdist_wheel.py`:

- `safe_version(version)` — normalises an arbitrary string into a PEP 440 version using `packaging.version.Version`.
- `python_tag()` — returns `f"py{sys.version_info.major}"` by default.
- `get_platform(archive_root)` — derives the platform tag from `sysconfig.get_platform()`. On macOS it delegates to `wheel.macosx_libfile.calculate_macosx_platform_tag` so the deployment target embedded in shared libraries is reflected. On 32-bit interpreters it remaps `linux-x86_64` to `linux-i686`.
- `get_abi_tag()` — derives the ABI tag from `SOABI`, with branches for CPython, PyPy, and GraalPy.
- `get_flag(var, fallback, expected=True, warn=True)` — reads a `sysconfig` flag and falls back if it is missing, optionally emitting a `RuntimeWarning`.

The `bdist_wheel` class itself subclasses `setuptools.Command`. Its `run()` builds an unpacked wheel tree, writes `WHEEL`, `RECORD`, and `METADATA` files, and produces a deterministic ZIP archive using `ZIP_DEFLATED` (with `ZIP_STORED` as an option).

## Wheel parsing

`setuptools/wheel.py` provides the `Wheel` class for working with wheels already on disk. `Wheel(filename)` parses the components into attributes (`project_name`, `version`, `build`, `py_version`, `abi`, `platform`). `_get_supported_tags()` is a `functools.cache` wrapper over `packaging.tags.sys_tags()` so compatibility checks across many candidate wheels are fast.

## Entry points

The `setuptools/_entry_points.py` module loads entry-point declarations from `Distribution.entry_points` and writes the `entry_points.txt` section of the egg-info / dist-info. The data is a mapping of group name to a list of `name = module:attr` lines. Built-in groups include:

- `console_scripts` — installed as executable wrappers in `bin/` (or `Scripts/` on Windows).
- `gui_scripts` — same, with the GUI launcher on Windows.
- `distutils.commands` — third-party setuptools commands.
- `distutils.setup_keywords` — handlers for custom `setup()` keyword arguments.
- `egg_info.writers` — extra files to drop into `*.egg-info/`.
- `setuptools.finalize_distribution_options` — last-chance hooks that adjust the `Distribution` before commands run.
- `setuptools.file_finders` — used by `sdist.walk_revctrl` to enumerate version-controlled files.

On Windows, console and GUI script wrappers are built around the pre-compiled `cli-*.exe` / `gui-*.exe` launchers in the repository root, which stamp the target Python entry point into a stub.
