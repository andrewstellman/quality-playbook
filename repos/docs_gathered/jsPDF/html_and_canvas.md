# HTML, Canvas, and SVG conversion

jsPDF ships three rendering bridges that let callers reuse existing web
content. All three live under `src/modules/`: `canvas.js`, `context2d.js`,
`html.js`, and `svg.js`.

## context2d — Canvas2D operator surface

`src/modules/context2d.js` implements `CanvasRenderingContext2D` on top
of jsPDF's drawing primitives. The `context2d` instance exposes the
familiar state (`fillStyle`, `strokeStyle`, `lineWidth`, `lineCap`,
`lineJoin`, `globalAlpha`, `font`, `textAlign`, `textBaseline`, shadows,
`imageSmoothingEnabled`, transform) and operators (`beginPath`,
`moveTo`, `lineTo`, `bezierCurveTo`, `quadraticCurveTo`, `arc`, `arcTo`,
`rect`, `closePath`, `fill`, `stroke`, `fillRect`, `strokeRect`,
`clearRect`, `clip`, `clipEvenOdd`, `fillText`, `strokeText`,
`measureText`, `drawImage`, `createLinearGradient`,
`createRadialGradient`, `createPattern`, `save`, `restore`, `translate`,
`scale`, `rotate`, `transform`, `setTransform`). State sits on a
`ContextLayer` stack so `save`/`restore` work like real canvas; each
geometry operator routes through the core drawing API after applying
the active transform and style.

## canvas and svg

`src/modules/canvas.js` wraps the context2d implementation in an object
that mimics an `HTMLCanvasElement`: `width`, `height`, `style`, a
back-reference to `pdf`, and `getContext(type)` returning the context2d
singleton. Third-party libraries (notably canvg) bind to this shim when
they expect a canvas but the destination is a PDF page.
`src/modules/svg.js` exposes `addSvgAsImage(svg, x, y, w, h, alias?,
compression?, rotation?)`, dynamically loading `canvg` (host global,
ESM `import()`, CommonJS `require`, or AMD `define`, in that order),
drawing the SVG into the canvas shim, and forwarding the raster to
`addImage`. canvg is an `optionalDependencies` entry, so applications
that never call `addSvgAsImage` pay no bundle cost.

## html — HTML to PDF

`src/modules/html.js` is the largest rendering bridge. The entry point
is `doc.html(src, options?)`, where `src` is an HTML string or
`HTMLElement` and `options` is an `HTMLOptions` record. The call
returns an `HTMLWorker` walking a small state machine (`from`, `to`,
`outputPdf`, `save`) with a `then(callback)` hook. Two paths exist: a
**raster path** that dynamically loads `html2canvas`, screenshots the
element, and embeds the resulting image via `addImage` (visual
fidelity, non-selectable text); and a **vector path** invoked via
`html.adapter` that walks the DOM directly so text nodes go through
`text()`, block boxes through `rect()`, and inline images through
`addImage` (selectable text, limited CSS subset).

`HTMLOptions` exposes `html2canvas` (passthrough) and `jsPDF` (partial
reconfiguration), plus margin tuples, `autoPaging` (`true | false |
'text' | 'slice'`), `pagebreak` (`mode`, `before`, `after`, `avoid`),
`windowWidth`, `width`, and `enableLinks`. When `src` is a string and
the optional `dompurify` dependency is present, the html plugin
sanitizes markup before rendering; dompurify is loaded through the
same dynamic-import ladder as html2canvas and canvg. The TypeScript
declarations define `Context2d`, `Gradient`, `Html2CanvasOptions`,
`HTMLOptions`, `HTMLAdapter`, `HTMLFontFace`, `HTMLWorker`, and the
`canvas` property on `jsPDF`.
