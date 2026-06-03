# Architecture

jsPDF is a JavaScript library that produces PDF documents directly in
the browser or in Node.js. The codebase is a single core constructor
plus plugin modules that attach to the constructor's prototype-like
`jsPDF.API` object. The package ships as ECMAScript, UMD, and Node
bundles generated from the same `src/` tree.

## Top-level layout

```
src/
  index.js              entry point — imports core + every shipped plugin
  jspdf.js              core: jsPDF constructor, document model, drawing API
  polyfills.js          optional polyfills for older runtimes
  libs/                 internal utilities (color, encoding, save, fonts)
  modules/              feature plugins (one file per topical area)
types/index.d.ts        TypeScript declarations for the public API
dist/                   built bundles (es, umd, node, polyfills)
docs/                   generated JSDoc HTML
test/                   karma + jasmine test suites
fontconverter/          companion HTML tool for TTF → JS conversion
```

## Core constructor

The core lives in `src/jspdf.js`. The constructor accepts an options
object or positional `(orientation, unit, format, compressPdf)`
arguments. Options include orientation, unit, page format, compression,
precision, user unit, filter list, encryption parameters,
`putOnlyUsedFonts`, an opt-in array of named compatibility toggles, and
`floatPrecision`. Defaults are A4, portrait, millimeters, precision 16.

Internally it maintains a page list (`internal.pages`), a font registry
keyed by PostScript name + style + weight, resource tables for fonts,
GStates, patterns, form objects, and images, a PubSub event bus
(`internal.events`) that plugins hook into, and a scale factor mapping
user coordinates to PDF points.

## Plugin model

Every file under `src/modules/` is an IIFE that receives `jsPDF.API` and
attaches new instance methods. Plugins subscribe to lifecycle events
(`putResources`, `postPutResources`, `addPage`, `putPage`, `addFonts`,
`putFont`, `putXobjectDict`, `putCatalog`) to emit their PDF objects at
the right point. `src/index.js` imports the full plugin set, and
`modules.conf.js` declares each module's name and dependency edges so
the rollup build can also assemble slimmer bundles.

## Two API modes

`compatAPI(cb)` and `advancedAPI(cb)` wrap a callback in one of two
coordinate / default-path regimes. Compat mode (default) matches the
historical MrRio API. Advanced mode prepends a change-of-basis matrix,
sets the default path operation to "none," and exposes the yWorks
transformation, pattern, and FormObject APIs. Each helper restores the
previous mode on return.

## Output pipeline

`doc.output(type, opts)` is the single sink for finished documents,
returning a raw string, `ArrayBuffer`, `Blob`, blob URL, data URI, or
opening the PDF in a new window. `save(filename)` builds on `output`
and delegates to `FileSaver` in the browser bundle and `fs` in Node.

## Build and dependencies

Rollup produces the es, umd, and node bundles; the release chain
(`version` → `build` → `generate-docs`) regenerates `dist/` and the
JSDoc tree. Runtime deps are minimal: `@babel/runtime`, `fflate`
(Flate), `fast-png` (PNG). The heavier `canvg`, `core-js`, `dompurify`,
and `html2canvas` libraries are `optionalDependencies` loaded
dynamically only when the SVG or HTML plugins are called.
