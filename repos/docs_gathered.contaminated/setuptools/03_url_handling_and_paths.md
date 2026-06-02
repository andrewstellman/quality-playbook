# URL Handling and Filesystem Paths — The os.path.join Footgun

## Sources

- Vulnerable source at parent SHA:
  https://raw.githubusercontent.com/pypa/setuptools/d8390feaa99091d1ba9626bec0e4ba7072fc507a/setuptools/package_index.py
- Patch diff:
  https://github.com/pypa/setuptools/commit/[REDACTED].patch
- Advisory [REDACTED]: https://github.com/advisories/[REDACTED]
- CPython docs for `os.path.join` (canonical statement of the absolute-path
  behavior): https://docs.python.org/3/library/os.path.html#os.path.join
- CPython docs for `urllib.parse.unquote`:
  https://docs.python.org/3/library/urllib.parse.html#urllib.parse.unquote

## Context

This file documents the two-step pattern that produces the [REDACTED]
in setuptools — the same pattern that appears under many names in many
Python codebases. The bug is at the intersection of:

1. **URL parsing in Python** — what `urlparse` decodes and what it leaves
   percent-encoded.
2. **Filesystem path joining in Python** — what `os.path.join` does when one
   of its arguments is absolute.

Both behaviors are *documented*, *intentional*, and individually reasonable.
The bug is the composition.

## How setuptools parses URLs

`package_index.py` imports `urllib.parse` and uses three primitives:

- `urllib.parse.urlparse(url)` — splits a URL into scheme, netloc, path,
  params, query, fragment. **Does not** percent-decode any of them.
- `urllib.parse.unquote(s)` — percent-decodes a string (`%2f` → `/`,
  `%20` → space, etc.).
- `urllib.parse.urlsplit(url)` — like `urlparse` but does not separate
  parameters from path. Used by `_resolve_vcs` and `_vcs_split_rev_from_url`.

The order of operations in `egg_info_for_url` (the function that produces
the eventual filename) is:

```python
def egg_info_for_url(url):
    parts = urllib.parse.urlparse(url)
    _scheme, server, path, _parameters, _query, fragment = parts
    base = urllib.parse.unquote(path.split('/')[-1])   # split FIRST, decode LAST
    ...
    return base, fragment
```

**The order matters.** `path.split('/')` runs against the still-encoded
path, then `unquote` runs against the segment that came out. Any `/` that
was percent-encoded as `%2f` in the URL survives the split and only
becomes a literal `/` afterwards. The encoded-then-split sequence
preserves the attacker's slashes inside what the code then treats as a
single filename.

## What gets URL-decoded, when

Tracing decode boundaries in `package_index.py`:

| Location | Operation | What it decodes |
|---|---|---|
| `egg_info_for_url` | `urlparse(url)` | Nothing (path stays encoded). |
| `egg_info_for_url` | `path.split('/')[-1]` | Operates on still-encoded path. Percent-encoded slashes (`%2f`) **survive** the split. |
| `egg_info_for_url` | `urllib.parse.unquote(...)` | Decodes percent-escapes in the last segment. Slashes are reintroduced here. |
| `_scan` (index page scanning) | `urllib.parse.unquote` on each `/`-split part | Decodes BEFORE the slash split, so this consumer is safe — but it does not feed `_resolve_download_filename`. |
| `_encode_auth` | `urllib.parse.unquote(auth)` | Decodes credentials from the userinfo portion of a URL. Not relevant to [REDACTED]. |

The asymmetry between `egg_info_for_url` (decode AFTER split) and `_scan`
(decode BEFORE split) is the structural bug. The "safe" pattern is
`_scan`'s; the unsafe pattern is `egg_info_for_url`'s.

## The `os.path.join` absolute-path footgun

Python's `os.path.join(a, b, c, ...)` documents this behavior verbatim:

> If a component is an absolute path, all previous components are
> thrown away and joining continues from the absolute path component.

This means:

```python
>>> import os.path
>>> os.path.join('/tmp/safe', '/etc/passwd')
'/etc/passwd'
>>> os.path.join('/tmp/safe', 'subdir/file')
'/tmp/safe/subdir/file'
```

The function is designed for the case "join optional path fragments
that may already be rooted." The cost of that ergonomic choice is that
any code path of the shape `os.path.join(safe_dir, untrusted_name)` is
unsafe the instant `untrusted_name` can be an absolute path.

This is a known footgun across the Python ecosystem; the CPython
`os.path` documentation explicitly warns about it, and many advisories
in the GitHub Advisory Database trace to exactly this pattern. The
setuptools `_resolve_download_filename` is one such case.

## How the two footguns compose into [REDACTED]

Concrete walk-through with the payload from the advisory's doctest:

Input URL: `https://anyhost/%2fhome%2fuser%2f.ssh%2fauthorized_keys`

```
1. urlparse('https://anyhost/%2fhome%2fuser%2f.ssh%2fauthorized_keys')
   → path == '/%2fhome%2fuser%2f.ssh%2fauthorized_keys'

2. path.split('/')
   → ['', '%2fhome%2fuser%2f.ssh%2fauthorized_keys']
   (note: only one literal '/' at the start; the %2fs are still encoded)

3. path.split('/')[-1]
   → '%2fhome%2fuser%2f.ssh%2fauthorized_keys'

4. urllib.parse.unquote('%2fhome%2fuser%2f.ssh%2fauthorized_keys')
   → '/home/user/.ssh/authorized_keys'    ← absolute path now

5. name = '/home/user/.ssh/authorized_keys'

6. '..' not in name  →  the while-loop sanitizer is a no-op

7. name.endswith('.egg.zip')  → False, name unchanged

8. os.path.join('/tmp/setuptools-XYZ/', '/home/user/.ssh/authorized_keys')
   → '/home/user/.ssh/authorized_keys'
   (tmpdir discarded because second arg is absolute)

9. (pre-patch) Return '/home/user/.ssh/authorized_keys'
   open(...) for writing  →  [REDACTED]
```

The patch (step 9 replaced):

```python
filename = os.path.join(tmpdir, name)
[REDACTED]:
    raise ValueError(f"Invalid filename {filename}")
return filename
```

`'/home/user/.ssh/authorized_keys'.startswith('/tmp/setuptools-XYZ/')` is
`False`, so `ValueError` is raised before any file is opened.

## Why the existing sanitizer didn't catch it

The pre-patch sanitizer is:

```python
if name:
    while '..' in name:
        name = name.replace('..', '.').replace('\\', '_')
else:
    name = "__downloaded__"
```

This was written to defend against the dot-dot-slash style of traversal
(`../../etc/passwd`). It is wrong in three independent ways for the
URL-encoded payload:

1. **It looks for literal `..`.** The payload contains no `..`. The
   `while` loop terminates immediately.
2. **It replaces `\\` with `_`.** This is a Windows traversal mitigation;
   no relation to the URL-encoded payload.
3. **Even if `..` were present, replacing it with `.` does not stop
   traversal in the absolute-path case.** A URL like
   `%2f..%2f..%2fetc%2fpasswd` would decode to `/../../etc/passwd`, the
   `..` replacement would turn it into `/././etc/passwd`, which still
   absolute-paths into `/etc/passwd` once joined.

The sanitizer is doing string surgery on a *name* and reasoning about
*paths* implicitly. The bug is that the implicit step (URL decode →
absolute path → os.path.join discarding tmpdir) is never made explicit.
The patch fixes this by making the check on the *final path*, not the
input string.

## Related patterns elsewhere in `package_index.py`

The audit should check whether other functions in the file have the same
shape "URL → derived string → joined with a trusted dir → open()" without
a containment check. Surveyed at the parent SHA:

- `gen_setup`: writes `os.path.join(tmpdir, 'setup.py')` — `'setup.py'`
  is a literal, not URL-derived. Safe.
- `gen_setup` also calls `os.path.join(tmpdir, basename)` where
  `basename = os.path.basename(filename)`. The `filename` here is
  whatever was returned by `_resolve_download_filename` — i.e. once the
  patch is applied, `basename` cannot escape because `filename` cannot.
  Defensive, but transitively safe.
- `scan_egg_link`: uses `os.path.join(path, entry)` where `entry` is read
  from `os.listdir(path)`. `os.listdir` returns entries without path
  separators on POSIX, so `entry` is a single filename. Safe in practice
  but not by explicit contract.
- `process_filename`: uses `os.path.join(path, item)` similarly to
  `scan_egg_link`. Same reasoning.
- `local_open`: uses `urllib.request.url2pathname(path)`. Converts a
  `file://` URL to a local path. Not currently bounded by `tmpdir`
  because the call point's contract is "open a local file the user
  named."

The patch's scope is appropriate: `_resolve_download_filename` is the
only function in the file where untrusted URL data is converted into a
write path under a caller-supplied directory.

## Invariants

1. **URL parsing must decode BEFORE splitting on `/`, not after.** The
   pattern `urlparse(url).path.split('/')[-1]` followed by `unquote(...)`
   is structurally unsafe because percent-encoded slashes survive into
   what is then treated as one filename.

2. **`os.path.join(trusted_dir, untrusted_name)` is unsafe whenever
   `untrusted_name` can be absolute.** Any code of this shape needs a
   post-join containment check (or a switch to a safer primitive like
   `pathlib.Path(trusted_dir, untrusted_name).resolve()` with a check
   that the result is `is_relative_to(trusted_dir)`).

3. **String-level sanitization of `..` is not path-level
   containment.** The two are not interchangeable. A check that asserts
   the final path is inside the trust boundary is the only correct
   defense. The patch uses `filename[REDACTED]` for this.

4. **URL-decoding boundaries are a security-relevant code property.**
   For an audit, every `unquote` call site is a place to check: what
   was the input, what is the output, and what does the output flow
   into? In `package_index.py` there are three such call sites
   (`egg_info_for_url`, `_scan`, `_encode_auth`); only the first one
   feeds the filesystem.
