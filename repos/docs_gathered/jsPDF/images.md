# Image embedding

The image pipeline is rooted in `src/modules/addimage.js` and supported
by one focused decoder plugin per format. It accepts pixel data, encoded
files, DOM image elements, and `<canvas>` elements, normalizes them, and
writes them as PDF XObjects.

## Public surface

```ts
addImage(imageData, format, x, y, w, h, alias?, compression?, rotation?): jsPDF
addImage(imageData, x, y, w, h, alias?, compression?, rotation?): jsPDF
addImage(options: ImageOptions): jsPDF
getImageProperties(imageData): ImageProperties
```

`imageData` can be a base64 or binary string, a data URI, an
`HTMLImageElement`, an `HTMLCanvasElement`, a `Uint8Array`, or an
`RGBAData` record carrying a `Uint8ClampedArray`. `compression` is one
of `NONE`, `FAST`, `MEDIUM`, `SLOW`; `format` is one of `RGBA`, `PNG`,
`TIFF`, `JPG`, `JPEG`, `JPEG2000`, `GIF87a`, `GIF89a`, `WEBP`, or
`BMP`. The `alias` argument lets callers reuse a single image stream
across many placements. `ImageOptions` (the third overload) bundles the
same fields plus an optional `rotation` in degrees. `ImageProperties`,
returned by `getImageProperties`, describes width, height, color space,
bits per component, filter, palette, and transparency.

## Format detection

`addimage.js` maintains a `imageFileTypeHeaders` table of magic-number
patterns and walks the candidate against each pattern. Patterns use
`undefined` as a "match any byte" wildcard, which lets a single
signature recognize JFIF, Exif, and raw JPEG variants. When detection
returns `UNKNOWN`, the caller supplies `format` explicitly.

## Per-format plugins

- `png_support.js` decodes PNGs through `src/libs/fast-png`, honoring
  interlace, palette, and tRNS chunks.
- `jpeg_support.js` extracts dimensions and color metadata from the
  JPEG markers and embeds the bytes directly with `DCTDecode`.
  `src/libs/JPEGEncoder.js` provides synthesis from RGBA buffers.
- `gif_support.js` decodes GIF87a/GIF89a via `src/libs/omggif.js`.
- `bmp_support.js` uses `src/libs/BMPDecoder.js`.
- `webp_support.js` uses `src/libs/WebPDecoder.js`.
- `rgba_support.js` handles raw `Uint8ClampedArray` data from a canvas,
  packs the alpha channel into an `sMask` XObject, and writes the RGB
  plane as `DeviceRGB`.

## Compression, filters, and aliasing

Image bitstreams pass through `src/modules/filters.js`: `FlateEncode`
(via fflate), `DCTDecode` (JPEG), `LZWDecode`, `RunLengthEncode`,
`ASCIIHexEncode`, `ASCII85Encode`. The `compression` argument selects
filters for RGBA and palette images; JPEG/JPEG2000 use `DCTDecode`
regardless. When the same `alias` is reused, `addImage` records the
image once and emits a reference XObject at each placement; without an
alias, jsPDF hashes the buffer so identical content deduplicates.
Internal helpers exposed under `jsPDFAPI.__addimage__` are reused by
the SVG and HTML plugins for canvas rasterization.
