# jsPDF — File-Loading Contract: loadFile / addImage / addFont / html

## Sources

- https://raw.githubusercontent.com/parallax/jsPDF/master/src/modules/fileloading.js (current/fixed)
- https://raw.githubusercontent.com/parallax/jsPDF/a504e973eeebac633351b41860945ca2a2cdf096/src/modules/fileloading.js (vulnerable parent SHA)
- https://github.com/parallax/jsPDF/security/advisories/GHSA-f8cm-6447-x5h2 (advisory enumerates affected methods)
- https://github.com/parallax/jsPDF/blob/master/README.md (UTF-8 / addFont usage section)
- https://artskydj.github.io/jsPDF/docs/jsPDF.html (API reference)

## Context

The four public methods enumerated by the GHSA-f8cm-6447-x5h2 advisory
(`loadFile`, `addImage`, `html`, `addFont`) are the externally visible
attack surface. All four converge on a single internal function,
`nodeReadFile`, which is the QPB detection target. This file documents
what each method is contractually supposed to accept and where caller-
controlled strings enter the library.

## `loadFile(url, sync, callback)`

Defined in `src/modules/fileloading.js`. The lowest-level loader. Two
implementations, selected by the `MODULE_FORMAT` build flag:

```js
jsPDFAPI.loadFile = function(url, sync, callback) {
  // @if MODULE_FORMAT!='cjs'
  return browserRequest(url, sync, callback);
  // @endif

  // @if MODULE_FORMAT='cjs'
  // eslint-disable-next-line no-unreachable
  return nodeReadFile.call(this, url, sync, callback);
  // @endif
};
```

**Expected source types for `url`:**

- Browser: an HTTP(S) URL or a same-origin relative URL. Resolved against
  `document.baseURI` by `XMLHttpRequest`.
- Node: a filesystem path (absolute or relative). Resolved against
  `process.cwd()` by `path.resolve`.

**Sync vs async:**

- `sync=true` (default) → synchronous read, returns the file contents as
  a `latin1`-encoded string.
- `sync=false` → asynchronous, invokes `callback(data)` on success or
  `callback(undefined)` on failure.

Re-exported under `jsPDFAPI.loadImageFile = jsPDFAPI.loadFile`. The two
names are the same function — auditing for one and missing the other is
a known footgun.

## `addImage(imageData, format, x, y, width, height, alias, compression, rotation)`

When `imageData` is a string and looks like a path/URL (i.e., not a base64
data URL and not already a known internal handle), the addimage module
calls `this.loadFile(imageData, true)` synchronously to fetch the bytes.
The advisory's example attack vector:

```js
import { jsPDF } from "./dist/jspdf.node.js";
const doc = new jsPDF();
doc.addImage("./secret.txt", "JPEG", 0, 0, 10, 10);
doc.save("test.pdf"); // the generated PDF will contain the "secret.txt" file
```

`./secret.txt` is `path.resolve`d to an absolute path, read via
`fs.readFileSync`, and the latin1-decoded bytes are embedded in the PDF
as the "image." There is no validation that the bytes are actually a
valid image — the file contents simply ride along in the PDF stream.

**Local-path access expectation:**
- *Expected* when the developer wants to embed a local image asset they
  control (e.g., `./assets/logo.png`).
- *Unexpected* when `imageData` is downstream of user input (uploaded
  file paths, query-string parameters, form fields, JSON payloads).

## `addFont(postScriptName, id, fontStyle, fontWeight, encoding)`

The font registration path. The first argument is typically the
PostScript name as stored in VFS via `addFileToVFS`, but the path-string
overload reaches `loadFile` to read TTF bytes from disk. The README
documents the VFS-only flow:

```js
const doc = new jsPDF();
const myFont = ... // load the *.ttf font file as binary string
doc.addFileToVFS("MyFont.ttf", myFont);
doc.addFont("MyFont.ttf", "MyFont", "normal");
doc.setFont("MyFont");
```

In this flow the binary is loaded by user code (often via `fetch` or
`fs.readFileSync` outside jsPDF) and inserted into VFS. The vulnerable
path is when `addFont` itself is given a filesystem-readable name and
the library tries to load it via `loadFile`.

**Local-path access expectation:**
- *Expected* when the developer explicitly intends to bundle TTF assets
  from a known directory (`./fonts/*` is the canonical example pattern
  in the post-fix `allowFsRead` documentation).
- *Unexpected* when font filenames originate from request parameters,
  user uploads, or any caller-controllable surface.

## `html(source, options)`

HTML-to-PDF rendering via `html2canvas` + (optional) `dompurify`.
Resources embedded in or referenced by the HTML — `<img src="...">`,
`<link rel="font">`, etc. — can route through `loadFile` when
html2canvas resolves them. In the Node build this means an attacker who
controls any URL in the supplied HTML can dereference a local path.

**Local-path access expectation:**
- *Expected* when the developer renders a static template referencing
  bundled assets.
- *Unexpected* when the HTML originates from user input, even after
  DOMPurify, because DOMPurify does not block well-formed `<img>` tags
  with on-disk relative paths.

## The Shared Sink: `nodeReadFile`

All four public methods reach the filesystem only through `nodeReadFile`.
This makes the function the **single chokepoint** for QPB's invariant
check. Any audit asking "does jsPDF's Node build read attacker paths?"
reduces to "does `nodeReadFile` gate access before `fs.readFileSync`?"

### Vulnerable `nodeReadFile` (parent SHA a504e97)

```js
function nodeReadFile(url, sync, callback) {
  sync = sync === false ? false : true;
  var result = undefined;

  var fs = require("fs");
  var path = require("path");

  url = path.resolve(url);            // ← no gate, no allow-list
  if (sync) {
    try {
      result = fs.readFileSync(url, { encoding: "latin1" });  // ← LFI sink
    } catch (e) {
      return undefined;
    }
  } else {
    fs.readFile(url, { encoding: "latin1" }, function(err, data) {
      ...
      callback(data);
    });
  }
  return result;
}
```

Two things to notice:

1. **No `this`-binding.** Pre-fix, `loadFile` called
   `nodeReadFile(url, sync, callback)` — not `.call(this, ...)`. The
   function had no access to the document's `allowFsRead` even if one
   existed, because the concept didn't exist.
2. **`path.resolve` is normalisation, not validation.** It resolves
   `..` segments and joins against `cwd`, but it does not constrain the
   resulting path. `path.resolve("../../../../../etc/passwd")` returns
   `/etc/passwd` with no error.

### Fixed `nodeReadFile` (master)

The fix restructures the function around three gates, in this order:

```js
function nodeReadFile(url, sync, callback) {
  // ...
  // GATE 1: at least one permission system must be active
  if (!process.permission && !this.allowFsRead) {
    throw new Error("Trying to read a file from local file system. ...");
  }

  // GATE 2: resolve symlinks BEFORE checking permissions
  try {
    url = fs.realpathSync(path.resolve(url));
  } catch (e) { /* return undefined / callback(undefined) */ }

  // GATE 3a: Node permission model (preferred)
  if (process.permission && !process.permission.has("fs.read", url)) {
    throw new Error(`Cannot read file '${url}'. Permission denied.`);
  }

  // GATE 3b: jsPDF.allowFsRead allow-list (fallback)
  if (this.allowFsRead) {
    const allowRead = this.allowFsRead.some(allowedUrl => {
      const starIndex = allowedUrl.indexOf("*");
      if (starIndex >= 0) {
        const fixedPart = allowedUrl.substring(0, starIndex);
        let resolved = path.resolve(fixedPart);
        if (fixedPart.endsWith(path.sep) && !resolved.endsWith(path.sep)) {
          resolved += path.sep;
        }
        return url.startsWith(resolved);
      } else {
        return url === path.resolve(allowedUrl);
      }
    });
    if (!allowRead) {
      throw new Error(`Cannot read file '${url}'. Permission denied.`);
    }
  }

  // Only now: actually read
  if (sync) { result = fs.readFileSync(url, { encoding: "latin1" }); }
  else      { fs.readFile(url, { encoding: "latin1" }, function(err, data) {...}); }
}
```

Note also the call-site change in `loadFile`: it now uses
`return nodeReadFile.call(this, url, sync, callback)` so `this.allowFsRead`
is reachable.

## Invariants

- **INV-CONTRACT-1 (single sink):** `nodeReadFile` is the only function
  that performs `fs.readFileSync` / `fs.readFile` for caller-supplied
  paths in the Node build. Auditing it covers the entire LFI surface for
  `loadFile`, `addImage`, `addFont`, `html`.
- **INV-CONTRACT-2 (aliases included):** `loadImageFile === loadFile` is
  the same function. Any pattern hunting for `loadFile` usage must also
  cover `loadImageFile` to avoid false negatives.
- **INV-CONTRACT-3 (gate-before-read):** Every code path that reaches
  `fs.readFileSync` or `fs.readFile` from caller-supplied input must be
  preceded by both (a) a check that at least one permission system is
  active and (b) a positive permission match against the
  `realpathSync`-resolved absolute path.
- **INV-CONTRACT-4 (resolution-before-check):** Path symlinks must be
  resolved via `realpathSync` BEFORE consulting either
  `process.permission.has("fs.read", url)` or the `allowFsRead`
  comparison. Checking the pre-realpath value is a symlink-bypass.
- **INV-CONTRACT-5 (`path.resolve` is not a validator):** Any review or
  static check that treats `url = path.resolve(url)` as the path
  sanitiser has the same bug pattern as CVE-2025-68428. Resolution does
  not constrain.
- **INV-CONTRACT-6 (this-binding requirement):** The Node loader must
  receive the jsPDF document context (`this`) so it can read
  `this.allowFsRead`. A regression to `nodeReadFile(url, sync, callback)`
  without `.call(this, ...)` re-introduces the no-allow-list condition
  for any non-`undefined` `allowFsRead`.
