# pypa/setuptools — Project Overview

## Sources

- Repository: https://github.com/pypa/setuptools
- Documentation: https://setuptools.pypa.io/en/latest/
- PyPI page: https://pypi.org/project/setuptools/
- Security policy: https://github.com/pypa/setuptools/blob/main/SECURITY.md
- Source of the vulnerable function (this audit's focus):
  https://raw.githubusercontent.com/pypa/setuptools/d8390feaa99091d1ba9626bec0e4ba7072fc507a/setuptools/package_index.py
- Patch commit: https://github.com/pypa/setuptools/commit/250a6d17978f9f6ac3ac887091f2d32886fbbb0b

## Context

`setuptools` is the canonical Python package build/install toolchain, maintained
under the Python Packaging Authority (PyPA). It is one of the most widely-deployed
pieces of Python software in existence: the GitHub repository reports **815k+
dependent projects** and 2.8k stars; nearly every Python installation that has
ever run `pip install` has setuptools on disk. Maintainership is led by Jason R.
Coombs (`@jaraco`) with hundreds of contributors.

The repository under audit is pinned at commit
`d8390feaa99091d1ba9626bec0e4ba7072fc507a` — the **parent of the patch** for
CVE-2025-47273 / GHSA-5rjg-fvgr-3xxf. That parent contains the vulnerable
`PackageIndex._resolve_download_filename` function (lines 810–825 of
`setuptools/package_index.py`) which derives a download filename from an
arbitrary URL and joins it onto a caller-supplied `tmpdir` with `os.path.join`
— with no check that the result actually stays under `tmpdir`.

### Language and toolchain

- **Language.** Python (98.8% of repo) plus a small `launcher.c` shim used to
  build Windows console-script `.exe` launchers (1.2% of repo).
- **Python versions supported.** Recent releases require Python 3.9+. The
  vulnerable file is written in modern Python with `from __future__ import
  annotations`, NamedTuples, type hints, and stdlib-only HTTP (`urllib`).
- **Test framework.** pytest (see `pytest.ini`, `conftest.py`). Doctests live
  inline in source files — the fix for CVE-2025-47273 added a doctest exercising
  the URL-encoded path traversal vector.
- **Linter.** Ruff (`ruff.toml`).
- **Release tooling.** towncrier (`towncrier.toml`, `newsfragments/`),
  bumpversion (`.bumpversion.cfg`).

### Domain — what setuptools does

setuptools is the build system and the runtime support library for Python
packaging. Its public surface includes:

- **PEP 517/518 build backend** (`setuptools.build_meta`) — invoked by `pip`,
  `build`, `uv`, etc. to produce sdists and wheels from a source tree.
- **The `setup.py` / `setup.cfg` / `pyproject.toml` declarative-config layer** —
  the user-facing way of describing a package.
- **`pkg_resources`** — the legacy runtime API for working with installed
  distributions, requirements, and entry points. Used by `package_index.py`.
- **`easy_install`** (deprecated) — the historical "install a package from a
  URL or index" command, predecessor to `pip`. The vulnerable code path lives
  inside `easy_install`'s downloader.
- **`PackageIndex`** (the vulnerable class) — a URL-scraping client that walks
  HTML index pages, follows links matching distribution filename patterns,
  validates checksums, and downloads candidate files into a temporary directory.
- **Distribution format handlers** — wheel (`.whl`), egg (`.egg`, `.egg.zip`,
  `.egg-info`), source distribution (`.tar.gz`, `.tar.bz2`, `.tar`, `.zip`,
  `.tgz`), Windows binary installer (`.exe`).

### Key terminology (used throughout the rest of this docs set)

- **sdist** — *source distribution*. A `.tar.gz` (or similar) containing the
  raw source tree plus packaging metadata. Built by `python -m build --sdist`
  or `python setup.py sdist`.
- **wheel (`.whl`)** — the modern binary distribution format, defined by
  PEP 427. A specially-named zip file. Installable by `pip` without executing
  arbitrary `setup.py` code.
- **egg (`.egg`, `.egg-info`, `.egg.zip`)** — the legacy distribution format
  that setuptools predates wheels with. Still recognized at install time and
  by `pkg_resources` at runtime. The vulnerable `_resolve_download_filename`
  has explicit handling for the `.egg.zip` suffix.
- **easy_install** — the deprecated installer command. The advisory text
  explicitly notes "as easy_install and package_index are deprecated, the
  exploitation surface is reduced" — but the code is still shipped, still
  importable, and still callable from any Python program that imports
  `setuptools.package_index`.
- **dependency_links** — a setup.py keyword (deprecated, but still parsed)
  that lets a package declare arbitrary download URLs for its dependencies.
  Historically this was a primary vector into `PackageIndex.download` from
  user-controlled input. `process_dependency_links` is one of the easy_install
  command-line options that the advisory's referenced CVE-2024-6345 was
  triggered through.
- **package index** — an HTTP server that exposes one HTML page per project
  with links to that project's distribution files. PyPI (`https://pypi.org/simple/`)
  is the canonical example; setuptools also supports `--find-links` URLs and
  `--index-url` overrides. The `PackageIndex` class scrapes these pages.
- **fragment / `#egg=name-version`** — setuptools' historical convention for
  attaching dependency metadata to a URL. Parsed by `egg_info_for_url` and
  `EGG_FRAGMENT` in `package_index.py`.
- **tmpdir** — the caller-supplied directory into which `PackageIndex.download`
  writes downloaded files. The vulnerability is that the downloaded file can
  escape this directory.

### Project layout (relevant subset)

```
setuptools/                  ← the importable package
├── package_index.py         ← VULNERABLE FILE — easy_install's URL scraper
│                              and downloader
├── wheel.py                 ← wheel handling
├── build_meta.py            ← PEP 517 backend
├── command/                 ← setup.py subcommand implementations,
│                              including easy_install
├── tests/                   ← test suite
└── ...
pkg_resources/               ← runtime distribution API (separate package)
_distutils_hack/             ← shim that intercepts `import distutils`
docs/                        ← Sphinx documentation source (deployed to
                                setuptools.pypa.io)
newsfragments/               ← towncrier news fragments for the next release
SECURITY.md                  ← one-line policy: report via Tidelift
```

## Invariants (project-wide)

These are documentation-level expectations the codebase is supposed to uphold.
File-specific invariants are in `04_invariants.md`.

1. **Setuptools is a trusted-input tool by design, with one large exception:
   the package_index downloader was originally written to walk arbitrary HTML
   pages on the internet.** That makes the `PackageIndex` class — and only
   the `PackageIndex` class — the internet-facing attack surface, despite
   setuptools' overall "developer-runs-it-locally" posture.

2. **`easy_install` / `package_index` are deprecated but not removed.** The
   maintainers have repeatedly stated they want users to migrate to `pip`,
   and the advisory cites the deprecation when scoring impact. **For audit
   purposes this is irrelevant**: the code is still shipped in every
   `setuptools` wheel on PyPI, still importable, and any third-party tool
   that does `from setuptools.package_index import PackageIndex` still
   inherits the bug.

3. **Downloads MUST stay inside the caller-supplied tmpdir.** This is what
   the patch (`if not filename.startswith(str(tmpdir)): raise ValueError`)
   enforces. The doctest added in the fix encodes the invariant explicitly:
   a URL containing `%2fhome%2fuser%2f.ssh%2fauthorized_keys` must raise
   `ValueError`, not silently write to `~/.ssh/authorized_keys`.

4. **Security disclosures go through Tidelift, not GitHub Issues.** The
   project's `SECURITY.md` is two lines long and points at
   https://tidelift.com/security. CVE-2025-47273 was reported via Huntr
   (huntr.com/bounties/d6362117-ad57-4e83-951f-b8141c6e7ca5) and tracked
   as a GitHub private advisory (GHSA-5rjg-fvgr-3xxf) before public
   disclosure on May 17, 2025.
