# Invariants — Path Safety in PackageIndex Downloads

## Sources

- Patch (verbatim diff and doctest):
  https://github.com/pypa/setuptools/commit/[REDACTED].patch
- Vulnerable source at parent SHA:
  https://raw.githubusercontent.com/pypa/setuptools/d8390feaa99091d1ba9626bec0e4ba7072fc507a/setuptools/package_index.py
- Advisory [REDACTED]: https://github.com/advisories/[REDACTED]
- Issue pypa/setuptools#4946: https://github.com/pypa/setuptools[REDACTED]
- Cross-reference advisories establishing the wider invariant set:
  - [REDACTED] ([REDACTED]): https://github.com/advisories/[REDACTED]
  - [REDACTED] ([REDACTED]): https://github.com/advisories/[REDACTED]

## Context

This file collects the invariants the audit should look for, expressed as
positive statements the code MUST uphold. Each invariant is tied to the
evidence (code, docstring, advisory text, or maintainer commit) that
establishes it.

## The single load-bearing invariant

### I-1. Downloaded filename must always stay within tmpdir

**Statement.** Given any URL `url` and any caller-supplied directory
`tmpdir`, the path that `PackageIndex._resolve_download_filename(url,
tmpdir)` returns MUST be located inside `tmpdir`. Equivalently, the file
opened for writing by `PackageIndex._download_url(url, tmpdir)` MUST be
inside `tmpdir`.

**Evidence — patch.** The patched function adds:

```python
filename = os.path.join(tmpdir, name)
# ensure path resolves within the tmpdir
[REDACTED]:
    raise ValueError(f"Invalid filename {filename}")
return filename
```

**Evidence — doctest.** The same commit adds an explicit positive and
negative test:

```python
>>> str(pathlib.Path(du(url, root)).relative_to(root))
'setuptools-78.1.0.tar.gz'

Ensures the target is always in tmpdir.

>>> url = 'https://anyhost/%2fhome%2fuser%2f.ssh%2fauthorized_keys'
>>> du(url, root)
Traceback (most recent call last):
...
ValueError: Invalid filename...
```

**Evidence — commit message.** The patch is titled "Add a check to ensure
the name resolves relative to the tmpdir." This is the maintainer's
verbatim statement of the invariant.

**Evidence — advisory description.** [REDACTED] describes the
bug as [REDACTED] via a URL-derived name that escapes tmpdir, with
[REDACTED] as the consequence.

**Pre-patch status.** Not enforced. The `name.replace('..', '.')` loop
was the author's *attempt* at the invariant; it does not enforce it.

**Post-patch status.** Enforced by string prefix check on the
constructed path.

## Supporting invariants

### I-2. URL-derived names must never escape tmpdir after URL-decode

**Statement.** Any name component derived from URL parsing (i.e. from
`egg_info_for_url(url)`) must be treated as untrusted *after*
percent-decoding, not before. Specifically, percent-encoded slashes
(`%2F`/`%2f`) in URL paths must be assumed to be a hostile attempt to
inject path separators into a filename.

**Evidence.** The doctest payload in the patch is
`'https://anyhost/%2fhome%2fuser%2f.ssh%2fauthorized_keys'`. The
advisory text says: "`name` is derived from a URL without sufficient
sanitization. While there is some attempt to sanitize by replacing
instances of '..' with '.', it is insufficient."

**Why this is a separate invariant from I-1.** I-1 is enforced by a
post-join check; I-2 is the upstream property the post-join check
defends. An auditor looking for the vulnerability without knowing about
the patch should reason from I-2 (a URL-decode is happening; what's the
output of the decode; where does it flow?) to find the bug.

### I-3. Filename derivation has a single chokepoint

**Statement.** All write-paths for downloaded content go through
`PackageIndex._resolve_download_filename`. No other code path in
`package_index.py` derives a download write-path from a URL.

**Evidence.** A grep of the parent-SHA source for `os.path.join(tmpdir`
(or `os.path.join(spec_filename`) finds:

- `_resolve_download_filename` itself (the bug site)
- `gen_setup`: `os.path.join(tmpdir, basename)` where `basename` is from
  `os.path.basename(filename)` and `filename` came from a prior
  `_resolve_download_filename` call
- `gen_setup`: `os.path.join(tmpdir, 'setup.py')` (literal name)

Everything else inside the file uses `os.path.join` with paths that came
either from the local filesystem (`os.listdir`, `os.path.realpath`) or
from literal constants.

**Audit implication.** A correct fix only has to defend
`_resolve_download_filename`. A correct audit only has to verify this one
function (and the absence of other URL-→-path conversions sharing the
trust boundary).

### I-4. Sanitization must be on the constructed path, not the input string

**Statement.** Path-traversal defenses must be checks on the
*post-join* path against the *trusted directory*, not pattern-based
filters on the input string.

**Evidence.** The pre-patch code attempted string-level filtering
(`while '..' in name: name = name.replace('..', '.')`) and failed
because:
- The attacker payload contained no `..`.
- Even if it had, `os.path.join` with an absolute second argument would
  still discard the trusted directory.

The patch keeps the string-level filtering (defense-in-depth) but adds
the *actual* defense: `[REDACTED]: raise`.

### I-5. `.egg.zip` rewriting happens before the safety check

**Statement.** Any rewriting of the derived name (e.g. stripping
`.egg.zip` to `.egg`) must happen *before* the containment check, so
that the check is performed on the actual on-disk name.

**Evidence.** Order in the patched function:

```python
name, _fragment = egg_info_for_url(url)
if name:
    while '..' in name:
        name = name.replace('..', '.').replace('\\', '_')
else:
    name = "__downloaded__"

if name.endswith('.egg.zip'):
    name = name[:-4]  # strip the extra .zip before download

filename = os.path.join(tmpdir, name)

# ensure path resolves within the tmpdir
[REDACTED]:
    raise ValueError(f"Invalid filename {filename}")
```

**Audit implication.** Any future rewrite added between `os.path.join`
and the `raise` would re-open the door. The check must be the *last*
operation before `return`.

### I-6. The check fails closed, not open

**Statement.** When the containment check fails, the function raises
an exception, not a fallback like "use `__downloaded__` instead."

**Evidence.** The patched code raises `ValueError`, terminating the
download. The advisory specifies this is the correct disposition:
silently substituting a safe name would surface as a misleading "wrong
file downloaded" rather than as the security failure it represents.

### I-7. PackageIndex is internet-facing despite living in setuptools

**Statement.** Any audit of `setuptools.package_index` must treat its
inputs as adversarial, regardless of setuptools' overall "trusted
developer tool" framing.

**Evidence.** Three confirmed CVEs in this exact module within three
years:
- [REDACTED] (ReDoS via HTML parsing on PyPI page)
- [REDACTED] (RCE via package URL)
- [REDACTED] ([REDACTED], this audit's focus)

The advisory text for [REDACTED] explicitly cites [REDACTED]
("could be exploited in a similar fashion … via malicious URLs present
on the pages of a package index") as the precedent for how user
input reaches the vulnerable function.

### I-8. Even "deprecated" code paths require security fixes

**Statement.** Deprecation does not remove obligation. The vulnerable
code is reachable as long as `setuptools.package_index` is importable,
regardless of `easy_install`'s deprecation status.

**Evidence.** The advisory's "Risk Assessment" notes "as easy_install
and package_index are deprecated, the exploitation surface is reduced"
— but a fix was nonetheless shipped in 78.1.1, backported to other
maintained lines, and tracked through Debian LTS. The reduced surface
did not justify leaving the bug.

### I-9. The trust anchor (tmpdir) is the caller's responsibility to
       canonicalize

**Statement.** The `startswith(str(tmpdir))` check assumes `tmpdir` is
an absolute, canonical path. Callers that pass relative paths, paths
with embedded symlinks, or paths whose case differs from on-disk reality
get weaker guarantees than the doctest suggests.

**Evidence.** The patch does not normalize `tmpdir`. It does not call
`os.path.realpath(tmpdir)` or `pathlib.Path(tmpdir).resolve()` before
the comparison. The maintainer chose the simpler string prefix check.

**Audit implication.** An auditor looking for residual risk should
check whether all callers of `PackageIndex.download` pass an
already-canonicalized `tmpdir`. The conventional caller (`easy_install`
with `tempfile.mkdtemp()`) does. Third-party callers may not.

## Invariants explicitly NOT in scope (residual risks)

These are things the patch does NOT guarantee, listed here so the audit
can mark them as known limitations rather than overlooked issues:

- **No protection against case-folding attacks on case-insensitive
  filesystems.** `'/Tmp/X/...'.startswith('/tmp/X/')` is False even when
  both refer to the same directory on macOS / Windows.
- **No protection against symlink races.** If `tmpdir` itself or any of
  its ancestors becomes a symlink to elsewhere between the check and
  the open, the write goes to the symlink target.
- **No collision protection.** Two URLs with the same trailing path
  component produce the same filename; later download overwrites
  earlier.
- **No hash binding.** The fix does not require URLs to carry an
  `#md5=` (or sha) fragment to be downloaded; `HashChecker.from_url`
  returns the no-op `ContentChecker` when no hash is in the fragment.
