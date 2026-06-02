# Security Model — Trust Boundaries Around PackageIndex

## Sources

- Repository: https://github.com/pypa/setuptools
- SECURITY.md: https://github.com/pypa/setuptools/blob/main/SECURITY.md
- Vulnerable source (parent SHA `d8390fea`):
  https://raw.githubusercontent.com/pypa/setuptools/d8390feaa99091d1ba9626bec0e4ba7072fc507a/setuptools/package_index.py
- Advisory GHSA-5rjg-fvgr-3xxf: https://github.com/advisories/GHSA-5rjg-fvgr-3xxf
- Related advisories establishing the same threat model:
  - GHSA-r9hx-vwmv-q579 (CVE-2022-40897 — ReDoS via PyPI page):
    https://github.com/advisories/GHSA-r9hx-vwmv-q579
  - GHSA-cx63-2mw6-8hw5 (CVE-2024-6345 — RCE via package URL):
    https://github.com/advisories/GHSA-cx63-2mw6-8hw5

## Context

`setuptools` is fundamentally a developer tool: the user (a developer or a CI
job) runs it locally and asks it to assemble a package. By that frame, almost
every input is "trusted" — the developer chose to run `python setup.py
sdist`, the developer wrote the metadata, the developer typed the command. The
`SECURITY.md` is two lines long for exactly this reason.

There is **one carve-out**, and it is the entire focus of this audit:

> **`setuptools.package_index.PackageIndex` is internet-facing.**

`PackageIndex` is the legacy `easy_install` downloader. It accepts an index
URL (`https://pypi.org/simple/` by default but configurable to anything),
fetches HTML pages from that URL, parses out all `<a href=...>` links it can
find, and downloads any that look like Python distributions. The instant
setuptools follows a link, **the bytes on the wire are attacker-controlled**:
the attacker can be an upstream PyPI mirror, a typosquatted index, an
HTML page served by a `--find-links` URL, a `dependency_links` entry in some
package being installed, or any redirect target chained off a legitimate
fetch.

The CVE-2022-40897 advisory described this attack surface as "malicious HTML
from a PyPI package or custom PackageIndex page." The CVE-2024-6345 advisory
(an RCE in the same module) described it as "package URLs … exposed to
user-controlled inputs." CVE-2025-47273 — the focus of this audit — is the
third member of that family.

## Trust boundaries

Inputs to `PackageIndex` ordered from most-trusted to least-trusted:

1. **`tmpdir`** (caller-supplied, trusted). The directory passed to
   `PackageIndex.download(spec, tmpdir)`. Typically a freshly-`mkdtemp`'d
   path. The caller has the right to expect setuptools to write only inside
   it.
2. **`index_url`** (configurable, semi-trusted). Defaults to
   `https://pypi.org/simple/`. Can be overridden by `--index-url`, environment
   variables, or `.pypirc`. For audit purposes, treat as **attacker-controlled
   if not the default PyPI**. Even when it IS the default PyPI, the HTML
   content of a project's page is partly attacker-influenced — anyone can
   register a project on PyPI and put whatever links they want on its page.
3. **`hosts` allow-list** (configurable, semi-trusted). The
   `--allow-hosts` glob list that controls which hosts setuptools will
   actually download from. By default it is `('*',)` — everything allowed.
4. **URLs scraped from index HTML pages** (untrusted). Whatever
   `<a href=...>` strings the HTML response contains. These flow directly
   into the URL parser, the filename derivation, and ultimately
   `os.path.join(tmpdir, name)`.
5. **`spec`** when it is a literal URL string (untrusted in any pipeline
   where `spec` is reachable from configuration). The `PackageIndex.download`
   docstring notes "`spec` … may be … a string containing a URL." If `spec`
   is built from a `dependency_links` entry, a CLI flag, or any other channel
   that's not "the developer typing at a shell," it must be treated as
   network input.

## The tmpdir contract

This is the contract the patch retroactively documents:

> Given `tmpdir` and any URL `url`, the file written to disk by
> `PackageIndex._download_url(url, tmpdir)` MUST have a path that is a
> descendant of `tmpdir`.

The contract is stated three ways in the patched code:

1. **A doctest.** `PackageIndex._resolve_download_filename` doctests that a
   well-formed URL produces a path equal to `tmpdir / 'setuptools-78.1.0.tar.gz'`,
   and that a URL containing `%2fhome%2fuser%2f.ssh%2fauthorized_keys` raises
   `ValueError: Invalid filename…`.
2. **A runtime check.** `if not filename.startswith(str(tmpdir)): raise
   ValueError(...)`. This is a string-prefix check, intentional in its choice
   not to use `os.path.realpath` — discussion in the patch comments shows the
   maintainer accepted that string prefix is sufficient because the bug
   being defended against is that `os.path.join` returned a fully-absolute,
   non-prefixed path.
3. **A docstring comment.** `# ensure path resolves within the tmpdir`.

### What this contract does NOT promise (and the patch does not enforce)

- It does not promise that the filename is unique within tmpdir. Two URLs
  with the same path component will collide; later download overwrites
  earlier.
- It does not promise that the downloaded bytes match a hash, mime type,
  or any structural validation beyond an optional `#md5=…` fragment.
- It does not promise non-symlink-following inside tmpdir. If an earlier
  download placed a symlink in tmpdir pointing outside it, the prefix check
  passes but the actual write follows the symlink. (No public exploit
  exercises this; flagging it as a residual risk only.)
- It does not promise immunity from symlink-style attacks on Windows
  case-folding (e.g., `TMPDIR` vs `tmpdir` may not match `startswith` in a
  case-sensitive comparison). The maintainer's chosen check is a literal
  string-prefix comparison; on case-insensitive filesystems this can be
  bypassed by case-variant inputs.

## Threat model summary

| Asset | Threat | Pre-patch protection | Post-patch protection |
|---|---|---|---|
| Filesystem outside `tmpdir` | Path traversal via URL-derived filename | None (the `..` replacement is bypassed by URL-encoding and by absolute paths) | `ValueError` if joined path doesn't start with `tmpdir` |
| `tmpdir` contents | Tampering by malicious filename | None | Same — the patch is scope-limited to the escape case |
| Process integrity | Code execution via downloaded content | None at this layer — assumed handled by sdist/wheel install logic | Unchanged |
| Network confidentiality | HTTPS downgrade | TLS is enforced by `urllib` defaults; `verify_ssl=True` is the constructor default | Unchanged |

## Invariants

1. **`PackageIndex` is internet-facing**, even though it lives inside the
   "trusted developer tool" called setuptools. Any audit of setuptools that
   treats the whole package as trusted-input will miss this entire class
   of bug. Three CVEs (2022-40897, 2024-6345, 2025-47273) confirm the
   threat model.

2. **The tmpdir invariant is "downloaded path stays under tmpdir."** This
   is the *only* path-safety contract in `package_index.py`, and prior to
   the patch it was not enforced — it was *hoped*. The presence of the
   `name.replace('..', '.').replace('\\', '_')` line in the pre-patch code
   shows the original author believed they were defending the invariant;
   they were not.

3. **Filename sanitization at the string level is insufficient.** Any
   path-safety reasoning in this module must terminate at a check on the
   *constructed path*, not on the input string. The `..` replacement is the
   classic broken sanitizer; the patch leaves the replacement in place
   (defense-in-depth) but adds the post-join prefix check as the actual
   defense.

4. **Caller-provided `tmpdir` is the trust anchor.** The patch defends the
   contract by string-comparing against the caller's `tmpdir`. If the
   caller passes a relative path, or a path with trailing slash
   irregularities, or a path that itself contains a symlink, the
   semantics of the prefix check change. The contract therefore implicitly
   asks callers to pass a canonicalized absolute path. The patch does not
   enforce this on the caller's behalf.

5. **Security disclosure is out-of-band.** The repository's
   `SECURITY.md` directs reporters to Tidelift; the project does not accept
   security reports via public GitHub issues. CVE-2025-47273 was reported
   via Huntr and triaged as a GitHub private advisory before public
   disclosure.
