# Page-level features

The page model in jsPDF is exposed through the core constructor plus a
set of focused plugins: `annotations.js`, `outline.js`, `total_pages.js`,
`viewerpreferences.js`, `xmp_metadata.js`, and `setlanguage.js`. Together
they organize a document and influence how PDF readers present it.

## Page management

The core tracks pages in `internal.pages` and exposes the chainable
page API: `addPage(format?, orientation?)`, `setPage(pageNumber)`,
`insertPage(beforePage)`, `deletePage(targetPage)`,
`movePage(targetPage, beforePage)`, `getNumberOfPages()`, plus
`getCurrentPageInfo()` and `getPageInfo(pageNumberOneBased)` returning
`{objId, pageNumber, pageContext}`. `internal.pageSize` exposes
`width`, `height`, `getWidth()`, and `getHeight()` honoring the active
orientation.

## Annotations

`src/modules/annotations.js` adds three methods:

- `createAnnotation(options)` — `type` is `"text"`, `"freetext"`, or
  `"link"`; `bounds` is a rectangle; optional fields are `title`,
  `open`, `color`, `name`, `top`, `pageNumber`, `contents`.
- `link(x, y, w, h, options)` — a rectangle linking to a page, named
  destination, or external URL. `options` accepts `pageNumber`,
  `magFactor` (`Fit`, `FitH`, `FitV`, `XYZ`), `zoom`, or `url`.
- `textWithLink(text, x, y, options)` — draws text and attaches a link
  rectangle sized by `getTextWidth(text)`.

Annotations are written into each page's `/Annots` array during
`putPage`. Supported destinations are XYZ, Fit, FitH, FitV.

## Outlines (bookmarks)

`src/modules/outline.js` exposes `doc.outline` with `add(parent, title,
options)`, `render()`, and a tree walker. Entries form a tree of
`{title, children, dest, parent}` nodes; the plugin subscribes to
`postPutResources` and writes the `/Outlines` dictionary, per-entry
objects, and root reference. Destinations are resolved at write time so
entries may be added before the target page exists.

## Viewer preferences

`src/modules/viewerpreferences.js` adds `viewerPreferences(options,
doReset?)` and `viewerPreferences("reset")`. The options object
surfaces the PDF `ViewerPreferences` dictionary as JavaScript fields:
`HideToolbar`, `HideMenubar`, `HideWindowUI`, `FitWindow`,
`CenterWindow`, `DisplayDocTitle`, `NonFullScreenPageMode`, `Direction`,
the `ViewArea` / `ViewClip` / `PrintArea` / `PrintClip` choices, and
the print-side fields `PrintScaling`, `Duplex`, `PickTrayByPDFSize`,
`PrintPageRange`, `NumCopies`. Each has a documented default and is
validated before write.

## Display mode and total pages

`setDisplayMode(zoom, layout, pmode)` controls the initial-view
dictionary. `zoom` accepts a percentage or `fullheight`, `fullwidth`,
`fullpage`, `original`; `layout` accepts `continuous`, `single`,
`twoleft`, `tworight`, `two`; `pmode` accepts `UseOutlines`,
`UseThumbs`, `FullScreen`. `src/modules/total_pages.js` provides
`putTotalPages(pageExpression)`, taking a regular expression that
matches a placeholder written earlier (for example `"{nb}"`); during
finalization the plugin walks every page's content stream and replaces
matches with the actual page count — the supported idiom for
"Page X of N" footers.

## Metadata, auto print, language

`setDocumentProperties(properties)` (alias `setProperties`) sets the
PDF Info dictionary: `title`, `subject`, `author`, `keywords`,
`creator`. `setCreationDate`/`getCreationDate` and `setFileId`/`getFileId`
round out the introspection surface. `src/modules/xmp_metadata.js` adds
`addMetadata(metadata, namespaceuri?)`; the XMP packet is written
during `postPutResources` and referenced from the catalog.
`src/modules/autoprint.js` adds `autoPrint(options?)`, with `variant`
of `"non-conform"` or `"javascript"` (the latter uses a document-level
script hook to trigger the print dialog on open).
`src/modules/setlanguage.js` adds `setLanguage(langCode)` and writes
the value into the catalog's `/Lang` entry; the type declarations list
every supported BCP 47 tag.
