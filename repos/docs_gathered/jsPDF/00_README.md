# jsPDF — Project Overview

## Sources

- https://github.com/parallax/jsPDF (repository README, master branch)
- https://parall.ax/products/jspdf (project landing page)
- https://github.com/parallax/jsPDF/blob/master/README.md
- https://raw.githubusercontent.com/parallax/jsPDF/master/src/modules/fileloading.js
- https://github.com/parallax/jsPDF/releases (releases, v4.2.1 as latest Mar 17 2026)

## Context

**jsPDF** is a JavaScript library for generating PDFs. It was originally
authored by James Hall (`MrRio`) at Parallax and is now co-maintained by
yWorks GmbH. It is one of the most widely-used PDF generation libraries in
the npm ecosystem (31.2k GitHub stars, 4.8k forks, package name `jspdf`).
License: MIT.

The library ships **multiple builds** from one source tree, distinguished by
where they expect to run. The `dist/` directory contains:

- `jspdf.es.*.js` — Modern ES2015 module format (browser/bundler).
- `jspdf.node.*.js` and `jspdf.node.min.js` — Node.js build. Uses
  `fs.readFileSync` and `fs.readFile` for I/O instead of browser APIs.
- `jspdf.umd.*.js` — UMD module format for AMD or script-tag loading.
- `polyfills.*.js` — Required polyfills for older browsers (e.g., IE).

When importing the bare specifier `"jspdf"`, the build tool (or Node) auto-
selects the appropriate build via `package.json` conditional exports. In
Node, `require("jspdf")` resolves to the **node build**, which is the one
covered by [REDACTED].

## Domain Vocabulary

- **PDF generation**: build a PDF document programmatically by issuing
  drawing/text/image commands against a `jsPDF` instance, then save/output
  it via `doc.save("...")` or `doc.output(...)`.
- **Standard fonts**: the 14 ASCII-limited fonts always available in PDF;
  for non-ASCII glyphs a TTF must be embedded via `addFont` / VFS.
- **VFS (Virtual File System)**: an in-memory store for font binaries used
  during PDF assembly (`addFileToVFS` then `addFont`).
- **`compatAPI` vs `advancedAPI`**: two API modes. "compat" matches the
  original MrRio API; "advanced" exposes the yWorks features (patterns,
  FormObjects, transformation matrices). Toggle via callback wrappers.

## Key APIs that Touch External Resources

These four methods are the public surface that, in the Node build, can
reach the local file system. They are the entry points the [REDACTED]
advisory enumerates as "affected":

- **`loadFile(url, sync, callback)`** — defined in
  `src/modules/fileloading.js`. The lowest-level loader. In the browser
  build it issues an `XMLHttpRequest`; in the Node build it calls
  `nodeReadFile`, which reads via `fs.readFileSync` / `fs.readFile`. Also
  re-exported as `jsPDFAPI.loadImageFile`.
- **`addImage(imageData, format, x, y, w, h, ...)`** — accepts either an
  in-memory image (data URL, base64, typed array, HTMLImage/Canvas) or a
  **path/URL string**. A string is fed to `loadFile`. In the Node build
  this means a string-typed `imageData` resolves to a local-file read.
- **`addFont(postScriptName, id, fontStyle, fontWeight, encoding)`** —
  registers a font with the document. If the caller provides a file path
  rather than VFS-resident binary data, the path is fed to `loadFile`.
- **`html(source, options)`** — converts HTML to PDF. Optional resources
  (images, fonts) referenced in the HTML can route through `loadFile`.
  Depends on the optional `html2canvas` and `dompurify` packages.

In the **browser build**, these methods are confined by the browser's
same-origin / fetch policy and pose no [REDACTED] risk to the host filesystem.
In the **Node build**, they have direct, unsandboxed `fs` access — which
is what [REDACTED] exploited.

## Repo Layout (relevant subset)

```
jsPDF/
├── src/
│   ├── jspdf.js               # core jsPDF class
│   └── modules/
│       ├── fileloading.js     # [REDACTED] fix locus
│       ├── addimage.js
│       ├── html.js
│       └── ttffont.js / standard_fonts_metrics.js
├── dist/
│   ├── jspdf.es.min.js
│   ├── jspdf.umd.min.js
│   ├── jspdf.node.js          # the affected node build
│   └── jspdf.node.min.js      # the affected node build (minified)
├── docs/                      # generated jsdoc HTML
├── examples/
├── test/
├── README.md
├── SECURITY.md
└── package.json
```

## Invariants

- **INV-OVERVIEW-1**: jsPDF ships a Node build (`dist/jspdf.node*.js`) that
  is **functionally distinct** from the browser builds — it has direct
  access to `fs`. Any analysis treating the library as "client-side only"
  misses the entire attack surface of [REDACTED].
- **INV-OVERVIEW-2**: A path string is a valid input type for `addImage`,
  `addFont`, and `html` resource references. Therefore the library
  intentionally bridges caller-controlled strings into `loadFile`. The
  question is not "is path input accepted?" — it is "what restriction
  applies before the path reaches `fs.readFileSync`?"
- **INV-OVERVIEW-3**: The fix locus for [REDACTED] is
  `src/modules/fileloading.js` and specifically the `nodeReadFile`
  function — every other affected public method (`addImage`, `addFont`,
  `html`) reaches the filesystem through this single function.
