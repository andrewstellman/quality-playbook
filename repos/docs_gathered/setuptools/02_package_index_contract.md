# PackageIndex Contract — Download Path Lifecycle

## Sources

- Vulnerable source at parent SHA (the entire `package_index.py`):
  https://raw.githubusercontent.com/pypa/setuptools/d8390feaa99091d1ba9626bec0e4ba7072fc507a/setuptools/package_index.py
- Patch (commit and diff):
  https://github.com/pypa/setuptools/commit/[REDACTED]
- Advisory [REDACTED]: https://github.com/advisories/[REDACTED]
- Issue tracking the fix (pypa/setuptools#4946):
  https://github.com/pypa/setuptools[REDACTED]
- easy_install user docs (background on the host allow-list message):
  https://setuptools.pypa.io/en/latest/deprecated/easy_install.html

## Context

`PackageIndex` is the class implementing setuptools' legacy
"download a package from a URL" pipeline. It is exposed as
`setuptools.package_index.PackageIndex` and inherits from
`pkg_resources.Environment`. The constructor's defaults reveal the contract:

```python
class PackageIndex(Environment):
    def __init__(
        self,
        index_url: str = "https://pypi.org/simple/",
        hosts=('*',),                  # allow downloads from any host
        ca_bundle=None,
        verify_ssl: bool = True,       # HTTPS verification on by default
        *args, **kw,
    ) -> None:
```

The class is instantiated by `easy_install`, by `setup.py install_requires`
processing, by `setup.py test`, and historically by anything that wanted a
Python-flavored URL-walking downloader. Any caller that passes a string URL
into `PackageIndex.download(spec, tmpdir)` triggers the vulnerable code path.

## The download lifecycle

The call chain from external entry-point to filesystem write, walked at the
parent SHA (`d8390fea`):

```
PackageIndex.download(spec, tmpdir)
    ├── if URL_SCHEME(spec): -> _download_url(spec, tmpdir)
    │       │
    │       └── _download_url(url, tmpdir):
    │             filename = _resolve_download_filename(url, tmpdir)   ← VULNERABLE
    │             return _download_vcs(url, filename)
    │                 or _download_other(url, filename)
    │                         └── _attempt_download(url, filename)
    │                                 └── _download_to(url, filename)
    │                                         └── open(filename, 'wb')   ← FILE WRITE
    │
    ├── elif os.path.exists(spec): return spec
    └── else: spec = parse_requirement_arg(spec)
              -> fetch_distribution(spec, tmpdir)
              -> find() -> self.download(dist.location, tmpdir)
                          (recurses back to top with dist.location, a URL
                           scraped from an HTML index page)
```

The recursion through `fetch_distribution → find → download` is the
attacker-influenced path: `dist.location` was scraped from a
`<a href=…>` tag on the index HTML, then fed back into `download`, and
ultimately into `_resolve_download_filename` as the URL argument.

## `_resolve_download_filename` — the vulnerable function

Verbatim from the parent SHA, lines 810–825 of
`setuptools/package_index.py`:

```python
@staticmethod
def _resolve_download_filename(url, tmpdir):
    """
    >>> du = PackageIndex._resolve_download_filename
    >>> root = getfixture('tmp_path')
    >>> url = 'https://files.pythonhosted.org/packages/a9/5a/0db.../setuptools-78.1.0.tar.gz'
    >>> import pathlib
    >>> str(pathlib.Path(du(url, root)).relative_to(root))
    'setuptools-78.1.0.tar.gz'
    """
    name, _fragment = egg_info_for_url(url)
    if name:
        while '..' in name:
            name = name.replace('..', '.').replace('\\', '_')
    else:
        name = "__downloaded__"  # default if URL has no path contents

    if name.endswith('.egg.zip'):
        name = name[:-4]  # strip the extra .zip before download

    return os.path.join(tmpdir, name)
```

The function is the single derivation point for the on-disk filename from
a URL. Its contract was, prior to the patch:

- **Input.** `url` (a URL string), `tmpdir` (a directory path string).
- **Output.** A filesystem path under `tmpdir`, "safe" because instances of
  `..` and `\\` have been replaced.
- **Failure modes assumed.** None — the function does not raise.

The patched contract:

- **Output.** A filesystem path under `tmpdir`, *verified* by a startswith
  check.
- **Failure mode.** `ValueError("Invalid filename …")` when the derived
  filename would escape `tmpdir`.

## How filename is derived — `egg_info_for_url`

The `name` value in `_resolve_download_filename` is the first return of
`egg_info_for_url(url)`, also in `package_index.py`:

```python
def egg_info_for_url(url):
    parts = urllib.parse.urlparse(url)
    _scheme, server, path, _parameters, _query, fragment = parts
    base = urllib.parse.unquote(path.split('/')[-1])   # ← URL-DECODE HERE
    if server == 'sourceforge.net' and base == 'download':
        base = urllib.parse.unquote(path.split('/')[-2])
    if '#' in base:
        base, fragment = base.split('#', 1)
    return base, fragment
```

This is the source of the URL-decode bypass that makes the
`%2fhome%2fuser%2f.ssh%2fauthorized_keys` payload work:

1. `urlparse` parses the URL; `path` keeps its percent-encoding because
   `urlparse` does not decode `%2f`.
2. `path.split('/')[-1]` extracts the last `/`-separated segment.
   `%2fhome%2fuser%2f.ssh%2fauthorized_keys` contains *no* unencoded `/`, so
   this returns the whole thing as the last segment.
3. `urllib.parse.unquote(...)` **then** decodes the percent-escapes,
   producing `/home/user/.ssh/authorized_keys` — a string starting with
   `/`, i.e. an absolute path.
4. `egg_info_for_url` returns this as `name`.
5. Back in `_resolve_download_filename`, `name.replace('..', '.')` does
   nothing (there are no `..` sequences).
6. `os.path.join(tmpdir, '/home/user/.ssh/authorized_keys')` returns just
   `/home/user/.ssh/authorized_keys` — `os.path.join` documents that an
   absolute second argument silently discards the first.
7. The caller of `_download_url` opens that path for writing.

## The download path lifecycle, post-patch

After the patch, step 7 above no longer occurs because step 6's result
fails the `[REDACTED]))` check and the function raises
`ValueError`. The change is local — no other function in the chain was
modified. This means:

- `PackageIndex.download` still returns the same `filename` on success.
- `_download_url` still returns the same path string.
- The VCS branch (`_download_vcs`, which clones from git/hg/svn URLs)
  uses `spec_filename.partition('#')` to derive its checkout directory;
  the patch's prefix check happens before this, so VCS clones also benefit
  from the check.
- Any caller that previously relied on `_resolve_download_filename` not
  raising will now see a new exception type.

## What controls reach `download(spec, tmpdir)`

In an `easy_install` invocation (the conventional caller), `spec` and
`tmpdir` originate as follows:

- `tmpdir` — derived from `tempfile.mkdtemp()` in `easy_install`. This is
  what makes the prefix check work: real-world `tmpdir` is always an
  absolute, canonical path like `/tmp/easy_install-abc123/`.
- `spec` — comes from:
  - command-line positional arguments (`easy_install <spec>`),
  - `install_requires=[...]` in `setup.py`,
  - `dependency_links=[...]` in `setup.py` (the historical attack vector),
  - or the recursion through `fetch_distribution`, in which `spec` is a
    `dist.location` URL scraped from an HTML page.

The advisory's risk assessment names this last path explicitly: "via
malicious URLs present on the pages of a package index."

## Invariants

1. **`PackageIndex.download(spec, tmpdir)` writes only inside `tmpdir`.**
   This is the top-level contract. The patch enforces it by checking the
   derived path before any file is opened.

2. **`_resolve_download_filename` is the single chokepoint for path
   derivation.** All download writes go through it. A correct fix
   therefore only has to defend this one function — which is exactly what
   the patch does (16 lines added, 2 lines removed, all in one function).

3. **The function may now raise `ValueError`.** Callers that pass a URL
   pointing outside `tmpdir` get an exception, not a silent escape.

4. **The `.egg.zip` rewrite happens *after* sanitization.** The fix is
   careful: it strips `.egg.zip` → `.egg` *before* the prefix check, so a
   malicious URL ending in `.egg.zip` whose stripped form would escape
   `tmpdir` is still caught.

5. **The fix does not address symlink races, case-folding, or hash
   collisions inside `tmpdir`.** The contract is scoped to "the joined
   path is a string-prefix of tmpdir." Callers requiring stronger
   guarantees must canonicalize `tmpdir` themselves and clean its
   contents between downloads.
