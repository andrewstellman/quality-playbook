# Drawing, paths, and graphics state

The drawing API lives in the core (`src/jspdf.js`) and mirrors the PDF
content-stream operators with a chainable JavaScript surface. Every shape
and color call returns the `jsPDF` instance.

## Coordinate system

Coordinates use the unit chosen at construction (`pt`, `px`, `in`, `mm`,
`cm`, `ex`, `em`, `pc`). The core derives a `scaleFactor` from the unit
and applies it whenever it writes a numeric value. In compat mode the
origin is the top-left corner; in advanced mode the prepended
change-of-basis matrix flips the Y axis to the PDF native bottom-left.

## Shape primitives and paths

Chainable primitives include `line`, `rect`, `roundedRect`, `triangle`,
`circle`, `ellipse`, and `lines` (a polyline / curve driver). The
trailing `style` argument selects the painting mode: `S` (stroke), `F`
(fill), `DF`/`FD` (fill then stroke), `f*` (even-odd fill). A `null`
style leaves the path on the stack for a later painter such as
`clip()`. Lower-level path construction is available through `moveTo`,
`lineTo`, `curveTo`, `close`, `stroke`, `fill`, `fillEvenOdd`,
`fillStroke`, and `fillStrokeEvenOdd`. `clip()` / `clipEvenOdd()`
install the current path as a clipping region; `discardPath()` drops
it without painting, useful when building patterns.

## Colors and line attributes

`setDrawColor`, `setFillColor`, and `setTextColor` accept a CSS string,
a single grayscale number, an RGB triple, or a CMYK quadruple; the
color space is selected by argument arity, with matching getters. CSS
parsing is delegated to `src/libs/rgbcolor.js`. `setLineWidth`,
`setLineCap`, `setLineJoin`, `setLineMiterLimit`, and
`setLineDashPattern(dashArray, phase)` control stroke geometry, with
matching getters.

## Graphics state and transformation

`saveGraphicsState()` / `restoreGraphicsState()` wrap the PDF `q`/`Q`
operators. The `GState` constructor accepts an `opacity` and
`stroke-opacity` map; an instance is registered with `addGState(key,
gState)` and selected with `setGState(gState)`. In the advanced API,
`Matrix(a, b, c, d, e, f)` is a value type with helpers `multiply`,
`inversed`, `clone`, `applyToPoint`, `applyToRectangle`, `decompose`,
`join`, `toString`. `matrixMult(m1, m2)` and `unitMatrix` round out the
algebra; `setCurrentTransformationMatrix(matrix)` writes the matrix
into the stream via PDF `cm`.

## Patterns and shading

`ShadingPattern(type, coords, colors, gState?, matrix?)` constructs an
axial or radial gradient. `TilingPattern(boundingBox, xStep, yStep,
gState?, matrix?)` builds a tiling pattern; the caller pairs it with
`beginTilingPattern`, draws into it, then closes with `endTilingPattern`.
Patterns are attached with `addShadingPattern(key, pattern)` and
referenced when calling `fill(pattern)` or `fillEvenOdd(pattern)`.

## Form XObjects

`beginFormObject`, `endFormObject`, `doFormObject`, and `getFormObject`
let the caller record drawing commands into a reusable form XObject and
replay it across pages with a transformation matrix. This is the
foundation the SVG and HTML plugins build on.
