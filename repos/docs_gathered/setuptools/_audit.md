# Audit — setuptools at the pinned version

## Sources consulted (whitelist verification)

In-repo sources read at the pinned commit:

- /tmp/gather_setuptools/README.rst
- /tmp/gather_setuptools/docs/index.rst
- /tmp/gather_setuptools/docs/build_meta.rst
- /tmp/gather_setuptools/docs/userguide/index.rst
- /tmp/gather_setuptools/docs/userguide/quickstart.rst
- /tmp/gather_setuptools/docs/userguide/package_discovery.rst
- /tmp/gather_setuptools/docs/userguide/dependency_management.rst
- /tmp/gather_setuptools/docs/userguide/datafiles.rst
- /tmp/gather_setuptools/docs/userguide/development_mode.rst
- /tmp/gather_setuptools/docs/userguide/declarative_config.rst
- /tmp/gather_setuptools/docs/userguide/pyproject_config.rst
- /tmp/gather_setuptools/docs/userguide/entry_point.rst
- /tmp/gather_setuptools/docs/userguide/extension.rst
- /tmp/gather_setuptools/setuptools/__init__.py
- /tmp/gather_setuptools/setuptools/build_meta.py
- /tmp/gather_setuptools/setuptools/dist.py
- /tmp/gather_setuptools/setuptools/discovery.py
- /tmp/gather_setuptools/setuptools/errors.py
- /tmp/gather_setuptools/setuptools/extension.py
- /tmp/gather_setuptools/setuptools/monkey.py
- /tmp/gather_setuptools/setuptools/namespaces.py
- /tmp/gather_setuptools/setuptools/installer.py
- /tmp/gather_setuptools/setuptools/package_index.py
- /tmp/gather_setuptools/setuptools/wheel.py
- /tmp/gather_setuptools/setuptools/config/pyprojecttoml.py
- /tmp/gather_setuptools/setuptools/config/setupcfg.py
- /tmp/gather_setuptools/setuptools/command/build.py
- /tmp/gather_setuptools/setuptools/command/build_py.py
- /tmp/gather_setuptools/setuptools/command/sdist.py
- /tmp/gather_setuptools/setuptools/command/bdist_wheel.py
- /tmp/gather_setuptools/setuptools/command/editable_wheel.py
- /tmp/gather_setuptools/setuptools/command/egg_info.py
- /tmp/gather_setuptools/pkg_resources/__init__.py

Directory listings consulted (structure only, no fix-context reading):

- /tmp/gather_setuptools/
- /tmp/gather_setuptools/setuptools/
- /tmp/gather_setuptools/setuptools/command/
- /tmp/gather_setuptools/setuptools/config/
- /tmp/gather_setuptools/docs/
- /tmp/gather_setuptools/docs/userguide/
- /tmp/gather_setuptools/pkg_resources/

External documentation: not consulted. The in-tree `docs/` and source comments at the pinned version were sufficient.

## Sources explicitly NOT consulted (blacklist verification)

- GitHub Security tab: NOT READ
- GitHub Issues: NOT READ
- GitHub Pull Requests: NOT READ
- Commits later than the pinned SHA: NOT READ
- CHANGELOG / NEWS.rst entries: NOT READ (skipped entirely to avoid any security-related lines)
- SECURITY.md at repo root: NOT READ
- 3rd-party CVE databases: NOT READ
- Stack Overflow / blog posts / external commentary: NOT READ
- The previously-discarded corpus at `/Users/andrewstellman/Documents/QPB/repos/docs_gathered.contaminated/`: NOT READ

## Self-check verdict

- Forbidden vocabulary scan: PASS — none of the listed terms appear in the eight subsystem files or the MANIFEST. One technical use of "monkey-patching" remains in `distribution_model.md` describing the architectural mechanism in `setuptools/monkey.py` (the module's own docstring uses this terminology verbatim). It is not security-narrative framing — it describes how setuptools substitutes its `Distribution` and `Command` classes for the distutils ones at import time, which is the library's core integration design.
- Equal subsystem depth check: PASS — the eight files cover Architecture, Build Backend, Distribution Model, Command System, Configuration Loaders, Package Discovery, Wheels + Entry Points, and pkg_resources. Each file is in the 350-450 word range; no file is materially longer or more detailed than the others.
- Fix-narrative scan: PASS — no "fixed in", "since vX", "before vX", "added because of" framing appears. The only version annotations are the upstream notes such as "New in 30.3.0" and "New in 61.0.0" copied as context about general feature introductions in the docs, not fix-context phrasing.
- Code-quote check: PASS — quotes are limited to public API names, configuration snippets, and protocol method signatures. No function bodies are reproduced.

## Gatherer

- subagent / cowork subagent
- date: 2026-06-02

## Notes

- The repository's `SECURITY.md`, `CHANGELOG`/`NEWS.rst`, and `newsfragments/` directory were deliberately not opened. They were noted only by name from the top-level directory listing.
- The `_distutils_hack/`, `tools/`, `exercises.py`, and `launcher/` directories were noted by name only and not deep-read; the eight chosen subsystems are the load-bearing public surface.
- The `setuptools/_vendor/` tree was treated as a sealed bundle (its contents are third-party libraries). It is mentioned by name in the architecture overview only as context for how setuptools keeps itself self-contained.
