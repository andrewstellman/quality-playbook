# Text rendering and fonts

Text flows through the `text()` method on the core, supported by plugins
for standard-font metrics, TTF embedding, UTF-8 handling, Arabic shaping,
and line wrapping.

## The text method

```ts
text(text: string | string[], x: number, y: number,
     options?: TextOptionsLight, transform?: number | Matrix): jsPDF
```

`text()` accepts a string or an array of lines. `options` surfaces
alignment (`left | center | right | justify`), baseline (`alphabetic |
ideographic | bottom | top | middle | hanging`), rotation angle or
`Matrix`, character spacing, horizontal scale, line-height factor,
`maxWidth`, and rendering mode (`fill`, `stroke`, `fillThenStroke`,
`invisible`, plus four clip-path variants). The flags `noBOM` and
`autoencode` govern PDF escaping; bidi layout is configured via
`isInputVisual`, `isInputRtl`, `isOutputVisual`, `isOutputRtl`, and
`isSymmetricSwapping`, forwarded to `src/libs/bidiEngine.js`.

## Standard fonts and selection

The standard 14 PDF fonts (Helvetica, Times, Courier in regular/bold/
italic, plus Symbol and ZapfDingbats) are registered by
`src/modules/standard_fonts_metrics.js`, which loads precomputed
glyph-width tables so the core can compute text widths without parsing
a font file. These fonts live in StandardEncoding or WinAnsiEncoding
and cannot render outside Latin-1. `setFont(name, style?, weight?)`
selects the active font; `setFontSize(pt)` sets the size in points.
`getFont()` returns id, encoding, PostScript name, style, and metadata;
`getFontList()` returns the family-to-styles map. `addFont` is
overloaded — by PostScript name for already-loaded fonts, or by URL
when the file must be fetched first.

## TTF embedding

`src/modules/ttfsupport.js` and `src/libs/ttffont.js` parse a TrueType
font supplied as a binary string, build glyph and width tables, and
register the font under `Identity-H` encoding. Standard delivery: drop
the binary into the vFS with `addFileToVFS(name, contents)`, then call
`addFont(name, family, style)`. `fontconverter/fontconverter.html` does
the same packaging at build time and emits a JS file callers include
directly.

## UTF-8 and Arabic shaping

`src/modules/utf8.js` provides `pdfEscape16`, converting a string to
the hex-CID form a CIDFontType2 stream expects, and emits the ToUnicode
CMap. The pipeline records used glyph ids so that with
`putOnlyUsedFonts` the subsetter embeds only those glyphs.
`src/modules/arabic.js` exposes `processArabic(text)`, which walks the
codepoint stream, classifies each Arabic letter by joining class, and
substitutes the correct presentation form (isolated, initial, medial,
final). The helper runs automatically inside `text()` for Arabic-block
input and can also be invoked directly.

## Line wrapping

`split_text_to_size.js` provides `splitTextToSize(text, maxWidth,
options?)`. It tokenizes on whitespace, measures each token through
`getStringUnitWidth`, and returns lines that fit within `maxWidth`.
`getTextDimensions(text, options?)` reports `{w, h}`.
`getHorizontalCoordinateString` and `getVerticalCoordinateString` apply
the scale factor and `floatPrecision` rounding for callers building raw
content-stream snippets.
