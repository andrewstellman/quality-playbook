# jsPDF — Security Model: Browser vs Node Trust Boundaries

## Sources

- https://github.com/parallax/jsPDF/blob/master/README.md (Security section)
- https://github.com/parallax/jsPDF/blob/master/SECURITY.md
- https://github.com/parallax/jsPDF/security/advisories/[REDACTED]
- https://github.com/parallax/jsPDF[REDACTED] (fix PR)
- https://raw.githubusercontent.com/parallax/jsPDF/master/src/modules/fileloading.js
- https://nodejs.org/api/permissions.html (Node permission model, referenced by README)

## Context

jsPDF runs in two fundamentally different threat environments depending on
which `dist/` build is loaded. The library's source is largely shared, but
the I/O primitives are swapped at build time via `// @if MODULE_FORMAT=...`
preprocessor directives that pick between an XHR-based loader (browser) and
an `fs`-based loader (Node). Conflating the two builds is the root error
that produced [REDACTED]: the Node loader inherited the "any URL is
fine" semantics of the browser loader, but `fs.readFileSync(arbitrary)`
in Node is a file-disclosure primitive in any process that runs PDF
generation against untrusted input.

## Trust Boundaries

### Browser build (`jspdf.umd.*.js`, `jspdf.es.*.js`)

- **Sandbox enforced by host (browser).** All I/O goes through
  `XMLHttpRequest` in `browserRequest()`. The same-origin policy, CORS,
  and the user's session cookies are the only "permission system."
- **Threat model.** The attacker controls the caller (page JS) or controls
  the URL passed to `loadFile`. They can issue arbitrary HTTP requests
  the browser would otherwise allow, but they cannot read the user's
  local filesystem from this code path — `XMLHttpRequest` has no
  `file://` reach to arbitrary paths in normal web contexts.
- **What jsPDF must not assume.** Even in the browser, the README warns
  "We strongly advise you to sanitize user input before passing it to
  jsPDF!" — but this is about PDF content injection (later CVEs like
  [REDACTED] HTML injection and [REDACTED] `addJS` PDF
  object injection), not [REDACTED].

### Node build (`jspdf.node.js`, `jspdf.node.min.js`)

- **Sandbox not enforced by host by default.** A normal `node` process
  has full read/write access to anything its UID can reach: `/etc/passwd`,
  `~/.ssh/`, `~/.aws/credentials`, application secrets in process cwd,
  any file the user running the server can read.
- **`nodeReadFile` is the I/O primitive.** It calls
  `path.resolve(url)` then `fs.readFileSync(url, { encoding: "latin1" })`.
  The resolution accepts absolute paths, relative paths, and arbitrary
  traversal sequences (`../`, `.../...//`, symlinks).
- **Threat model the maintainers now adopt.** Any string fed to
  `loadFile` / `addImage` / `addFont` / `html` may be attacker-controlled.
  Therefore the library MUST gate `fs` access by an explicit allow-list
  rather than relying on the calling app to sanitize.

## The Two Layers of Defense (post-fix, v4.0.0+)

The fix in [REDACTED] introduces **two independent layers** that BOTH must
permit a read for it to proceed:

1. **Node `[REDACTED]` (preferred).** Node's experimental
   permission model (stable from v22.13.0 / v23.5.0 / v24.0.0, behind
   `--permission --allow-fs-read=...` CLI flags). When available,
   `[REDACTED].has("fs.read", url)` is consulted *after*
   resolving the path with `fs.[REDACTED](path.resolve(url))`. If Node
   denies access, the read fails with `Permission denied` regardless of
   what `[REDACTED]` says.
2. **`[REDACTED]` allow-list (fallback).** A per-document
   property (`doc.[REDACTED] = [...]`) listing exact paths or glob-style
   prefixes ending in `*`. Entries are resolved with `path.resolve` and
   the **realpath-resolved request URL** must equal one or be prefixed by
   one. The README explicitly labels this the "not recommended" path.

If neither `[REDACTED]` nor `[REDACTED]` is configured, the
library throws an error rather than silently falling back to unrestricted
filesystem access:

```
throw new Error(
  "Trying to read a file from local file system. To enable this feature
   either run node with the --permission and --allow-fs-read flags or
   set the [REDACTED] property."
);
```

This **secure-by-default** posture is the architectural change the CVE
fix delivered. Pre-fix, no opt-in was required for unrestricted reads.

## What the README Documents to Users

```
node --permission --allow-fs-read=... ./scripts/generate.js
```

And for the fallback:

```js
import { jsPDF } from "jspdf";
const doc = new jsPDF();
doc.[REDACTED] = ["./fonts/*", "./images/logo.png"];
```

The README also notes: when using `--allow-fs-read`, **all** imported JS
files (including dependencies) must be covered — otherwise the runtime
will deny module loads. This is a Node-permission-model footgun, not a
jsPDF-specific issue, but it's documented because it bites adopters of
the recommended posture.

## Invariants

- **INV-MODEL-1 (build-discriminator):** Any node-side path-handling
  invariant in jsPDF lives in the code reached by
  `MODULE_FORMAT == 'cjs'` branches. Browser-only code paths (XHR) do
  not need filesystem allow-listing.
- **INV-MODEL-2 (secure-by-default):** With neither `[REDACTED]`
  nor `this.[REDACTED]` set, `nodeReadFile` MUST throw before any `fs`
  syscall. A code path that reaches `fs.readFileSync` without one of
  those two gates being checked is the [REDACTED] regression.
- **INV-MODEL-3 (defense-in-depth ordering):** Node's `[REDACTED]`
  is checked **after** `[REDACTED](path.resolve(url))` resolves
  symlinks. Calling permission checks against the unresolved input would
  permit `/etc/passwd` via a `./mylink → /etc/passwd` symlink. The order
  in the fixed code is: throw-if-no-gate → realpath → [REDACTED]
  check → [REDACTED] check → fs read.
- **INV-MODEL-4 (don't trust the caller):** The README's general advice
  "sanitize user input before passing it to jsPDF" is necessary but not
  sufficient for the Node build. The library itself must enforce the
  filesystem boundary because (a) callers reliably forget and (b) the
  failure mode is silent data exfiltration into a PDF the caller then
  ships somewhere.
- **INV-MODEL-5 (cross-build symbol parity does not imply policy parity):**
  Methods that exist in both builds (`loadFile`, `addImage`, `addFont`,
  `html`) DELIBERATELY behave differently at the I/O layer. A change to
  one build's I/O policy must not "harmonize" them by relaxing the Node
  side to match the browser side.
