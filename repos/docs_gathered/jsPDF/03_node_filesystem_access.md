# jsPDF — Node Filesystem Access: path.resolve + fs.readFileSync Pipeline

## Sources

- https://raw.githubusercontent.com/parallax/jsPDF/master/src/modules/fileloading.js (fixed implementation)
- https://raw.githubusercontent.com/parallax/jsPDF/a504e973eeebac633351b41860945ca2a2cdf096/src/modules/fileloading.js (vulnerable parent)
- https://github.com/parallax/jsPDF[REDACTED] (fix PR)
- https://github.com/parallax/jsPDF/security/advisories/[REDACTED]
- https://nodejs.org/api/permissions.html ([REDACTED] API)
- https://nodejs.org/api/path.html#pathresolvepaths (path.resolve semantics)
- https://nodejs.org/api/fs.html#fsrealpathsyncpath-options ([REDACTED] semantics)

## Context

This document drills into the exact Node API calls jsPDF uses to read
files, what each call does and doesn't promise about safety, and what
"permitted vs denied" looks like under the post-fix policy. It is the
ground truth for any QPB invariant check on Node-side file access.

## The Three Node Primitives Involved

### `path.resolve(...segments)`

- Normalises segments to an absolute path. Joins them against
  `process.cwd()` for relative segments. Resolves `..` and `.` segments.
- **Does NOT** check the filesystem. Does not resolve symlinks. Does not
  reject paths outside any "root" — the concept of a root does not exist
  in this API.
- `path.resolve("../../../../etc/passwd")` from a working directory of
  `/home/app` returns `/etc/passwd`. No error.
- `path.resolve("/etc/passwd")` returns `/etc/passwd`. No error.
- **Wrong mental model:** "I called `path.resolve`, so the path is safe."
  Resolution is normalisation, not validation. This is the mental error
  that produced [REDACTED].

### `fs.[REDACTED](path)`

- Resolves a path through symlinks to a canonical absolute path on disk.
- **Throws** if any segment does not exist (in the synchronous variant).
- jsPDF wraps the `[REDACTED]` call in a `try { } catch (e) {}` that
  returns `undefined` / fires `callback(undefined)`. This is intentional:
  a non-existent path should fail closed, not throw out of the loader.
- Critical property: realpath collapses symlink-based escapes. If
  `./mylink` is a symlink to `/etc/passwd`, `[REDACTED]("./mylink")`
  returns `/etc/passwd`, NOT `/cwd/mylink`. Permission checks against
  the realpath therefore see the actual target.

### `fs.readFileSync(path, { encoding: "latin1" })` / `fs.readFile(...)`

- Reads file contents into memory. `latin1` encoding is chosen because
  jsPDF needs raw byte-preserving string handling for binary content
  (TTF font tables, image bytes, etc.) — UTF-8 would mangle bytes
  ≥ 0x80.
- No additional checks: by the time control reaches `readFileSync`, the
  library has already committed to the read. Anything to the right of
  this call (post-read sanitisation) is too late — the bytes are now in
  process memory and will be embedded in the PDF.

## The Vulnerable Pipeline (pre-v4.0.0)

```
url (caller-controlled string)
  └→ path.resolve(url)                         ← normalisation, NOT validation
       └→ fs.readFileSync(url, "latin1")       ← arbitrary read
            └→ result returned, embedded in PDF
```

Three properties of this pipeline make it a clean [REDACTED] primitive:

1. **No allow-list.** Any path that resolves to a readable file on the
   process's filesystem is fair game.
2. **No symlink resolution gate.** Even if the caller passes "obviously
   bounded" paths like `./assets/logo.png`, a symlink in `./assets/` to
   `/etc/passwd` would be followed silently.
3. **No opt-in.** A developer who never intended their Node service to
   expose local files inherited [REDACTED] by importing the package.

## The Permitted Pipeline (v4.0.0+)

```
url (caller-controlled string)
  └→ ensure [REDACTED] || this.allowFsRead is set   ← Gate 1: throw if not
       └→ path.resolve(url)
            └→ fs.[REDACTED](...)             ← resolve symlinks
                 └→ [REDACTED].has("fs.read", url)? ← Gate 2 (if available)
                      └→ allowFsRead match?     ← Gate 3 (if configured)
                           └→ fs.readFileSync(url, "latin1")
```

### Allow-list matching semantics

The post-fix `allowFsRead` array supports two entry forms:

**Exact match.** `url === path.resolve(allowedUrl)`. The entry is
resolved against `process.cwd()` (so `"./fonts/MyFont.ttf"` becomes
e.g. `/srv/app/fonts/MyFont.ttf`) and must equal the realpath-resolved
request URL exactly. Trailing slashes are significant — `path.resolve`
strips them, so `"./fonts/file.ttf"` matches one file only.

**Prefix glob with `*`.** If an entry contains `*`, only the segment
*before* the first `*` is taken as the prefix. Examples:
- `"./fonts/*"` → after resolve, `/srv/app/fonts/`, matches any file
  starting with that prefix.
- `"./assets/*"` → matches `./assets/foo.png` AND `./assets/sub/dir/foo`
  (i.e., recursive prefix match, not single-segment).

There is special-cased path-separator handling: if the fixed-part ends
with `path.sep` but the resolved path does not (because `path.resolve`
strips trailing separators), the code appends `path.sep` back. Without
this fix, `./fonts/*` would resolve fixed-part `./fonts/` to `/srv/app/fonts`
and then `url.startsWith("/srv/app/fonts")` would accept
`/srv/app/fonts_secret/other.dat`.

### Node permission model interaction

`[REDACTED]` is only present when Node is launched with
`--permission`. When present, the check is:

```js
[REDACTED].has("fs.read", url)  // url is already realpath-resolved
```

This is consulted **independently** of `allowFsRead`. Both checks must
pass when both are configured. Either one can refuse, and refusal
throws synchronously.

If `--permission` is set but the requested file is not covered by an
`--allow-fs-read=...` glob, Node throws `ERR_ACCESS_DENIED` from inside
the `fs` call itself. jsPDF's explicit `[REDACTED].has(...)`
check is therefore belt-and-braces: it catches the denial before
issuing the `fs` syscall, producing a clean jsPDF-shaped error message
instead of a generic Node permission error.

## "Permitted vs Denied" Decision Table

| `[REDACTED]` | `this.allowFsRead` | Outcome |
|----------------------|--------------------|---------|
| absent               | undefined          | THROW — "Trying to read a file from local file system..." |
| absent               | defined, no match  | THROW — "Cannot read file '<path>'. Permission denied." |
| absent               | defined, matches   | READ |
| present, denies      | (any)              | THROW — "Cannot read file '<path>'. Permission denied." |
| present, allows      | undefined          | READ |
| present, allows      | defined, no match  | THROW |
| present, allows      | defined, matches   | READ |

The key row is row 1: with neither system configured, the library
refuses. This is what makes the fix **secure-by-default**.

## Bypass Surfaces to Watch in Any Patch

These are the regression patterns QPB should flag if a reviewer is
modifying `fileloading.js` or anything that interacts with it:

1. **Calling `nodeReadFile(url, sync, cb)` without `.call(this, ...)`.**
   Loses the `this.allowFsRead` reference; collapses to "[REDACTED]
   only" or, if that's absent, to the throw-everything default.
2. **Moving the gate-1 throw inside the `try { [REDACTED](...) }`.** If
   the throw happens after a failed realpath (e.g., for a non-existent
   path), the error message becomes "file not found" which is correct
   behavior — but if the throw is removed entirely from the no-gate
   branch, the function silently returns `undefined` and the caller may
   retry or assume a benign missing-asset error.
3. **Checking `[REDACTED].has(...)` against the un-realpath'd
   URL.** Symlink-bypass: an attacker creates `./safe_asset.png` as a
   symlink to `/etc/shadow`; permission check on `./safe_asset.png`
   passes; read happens on `/etc/shadow`.
4. **Allow-list match against the un-realpath'd URL.** Same class of
   bug as #3. The fixed code is careful to assign
   `url = fs.[REDACTED](path.resolve(url))` BEFORE either permission
   check.
5. **Allow-list `startsWith` without separator normalisation.** The
   trailing-separator special case in the fix is load-bearing — without
   it, `./fonts/*` matches `/srv/app/fonts_secret/foo.dat`. A patch
   that "simplifies" by removing the `path.sep` append re-opens this.
6. **A new file-reading method that bypasses `nodeReadFile`.** Any new
   `addX(path)` API that calls `fs.readFileSync` directly (not through
   `loadFile`/`nodeReadFile`) re-opens the entire [REDACTED] surface
   for that one method.

## Invariants

- **INV-FSACCESS-1 (`path.resolve` is normalisation):** No reviewer or
  test pattern may treat `path.resolve(userInput)` as the validation
  step. Validation requires either `[REDACTED]` or
  `allowFsRead` matched against `[REDACTED](path.resolve(userInput))`.
- **INV-FSACCESS-2 (realpath-before-check):** `fs.[REDACTED]` must be
  invoked between `path.resolve` and any permission/allow-list check.
  Otherwise symlink-based escape is trivial.
- **INV-FSACCESS-3 (gate-or-throw):** The presence of neither
  `[REDACTED]` nor `this.allowFsRead` MUST cause a thrown error
  before any `fs` call. A silent-fallback variant (return `undefined`,
  log a warning, etc.) is a regression.
- **INV-FSACCESS-4 (both checks composable):** When both
  `[REDACTED]` and `allowFsRead` are configured, both must
  permit. The fixed code enforces this by running the permission check
  independently of the allow-list match. A patch that makes them an
  "either-or" gate is a regression.
- **INV-FSACCESS-5 (separator handling in glob match):** Prefix entries
  ending in `path.sep` (e.g., `"./fonts/*"`) must preserve the trailing
  separator in the compiled prefix. Stripping it widens the match to
  sibling directories with the same prefix.
- **INV-FSACCESS-6 (single sink discipline):** All Node-side file reads
  for caller-controlled paths must funnel through `nodeReadFile`. A
  parallel `fs.readFileSync` call elsewhere in `src/modules/` that takes
  caller input bypasses the gates entirely.
