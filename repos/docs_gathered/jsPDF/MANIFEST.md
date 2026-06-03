# MANIFEST — jsPDF reference corpus

- `architecture.md` — overall design, plugin model, build pipeline, and
  the compat / advanced API switch.
- `drawing_and_paths.md` — coordinate system, shape primitives, free-form
  paths, colors, line attributes, graphics-state stack, patterns,
  transformations, and form XObjects.
- `text_and_fonts.md` — the `text` method, standard fonts, custom TTF
  embedding, UTF-8 handling, Arabic shaping, and line-wrap helpers.
- `images.md` — `addImage`, format detection, per-format decoder plugins
  (PNG, JPEG, GIF, BMP, WebP, RGBA), compression filters, aliasing.
- `forms_acroform.md` — AcroForm field constructors, document-level
  wiring, appearance streams, and field-type specifics.
- `html_and_canvas.md` — the `context2d` Canvas2D shim, the `canvas`
  element wrapper, `addSvgAsImage` via canvg, and `doc.html` via
  html2canvas with optional dompurify sanitization.
- `document_output.md` — `output` formats, `save` and FileSaver,
  PDFSecurity encryption, the virtual file system, `loadFile`, PubSub
  lifecycle events, and the filter chain.
- `page_features.md` — page management, annotations, outlines, viewer
  preferences, display mode, total-pages substitution, metadata, auto
  print, and language tagging.
