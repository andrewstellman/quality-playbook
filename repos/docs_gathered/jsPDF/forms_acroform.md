# Interactive forms (AcroForm)

`src/modules/acroform.js` adds AcroForm support. It attaches a single
instance method, `addField(field)`, to every jsPDF document and exposes
the field constructors as a `doc.AcroForm` namespace.

## Field constructors

```
doc.AcroForm.TextField()
doc.AcroForm.PasswordField()
doc.AcroForm.ChoiceField()
doc.AcroForm.ComboBox()
doc.AcroForm.ListBox()
doc.AcroForm.EditBox()
doc.AcroForm.Button()
doc.AcroForm.PushButton()
doc.AcroForm.RadioButton()
doc.AcroForm.CheckBox()
doc.AcroForm.Appearance()
```

Each constructor returns a field object whose prototype ultimately points
to `AcroFormField`. Configuration is by property assignment: `Rect`,
`FT`, `T` (field name), `V` (value), `DV` (default value), appearance
characteristics, and flags such as `Multiline`, `Password`, `ReadOnly`,
`Required`, `NoExport`. Flag bits are exposed as setters so callers do
not compose the bitmask by hand.

## Document-level wiring

The plugin subscribes to three event topics: it allocates the AcroForm
dictionary on first `addField`, walks the field tree at `putResources`,
and writes annotation arrays at `putPage`. `addField` places the field
into the current page's annotation list and applies the page's
coordinate transform so the rectangle reads correctly under both API
modes.

## Choice fields

`ChoiceField` is the shared base of `ComboBox`, `ListBox`, and `EditBox`.
The `Opt` property accepts option strings or `[exportValue,
displayValue]` pairs. `MultiSelect`, `DoNotSpellCheck`, and
`CommitOnSelChange` are exposed as named booleans. Selection is set with
`V` for single-selection fields and `I` (index array) plus `V` for
multi-select list boxes.

## Buttons

`Button` is the parent of `PushButton`, `RadioButton`, and `CheckBox`.
Radio buttons coordinate through a `parent` field that owns the export
value table; the plugin assigns matching `AS` (appearance state) values
when the caller calls `setAppearance`. Push buttons accept caption,
rollover caption, and down caption strings, plus optional icon streams
that reuse the XObject machinery used by `addImage`.

## Text fields

`TextField` honors `MaxLen`, `MultiLine`, `Password`, `FileSelect`,
`DoNotSpellCheck`, `DoNotScroll`, `Comb`, and `RichText` flags. The
appearance stream is composed using the active font and font size when
the field is added; changing the font and re-emitting regenerates the
stream.

## Appearance streams and actions

`AcroForm.Appearance()` returns an empty appearance dictionary that
callers fill in by writing raw content-stream operators into its
`stream` property. Escape helpers `pdfEscape` / `pdfUnescape` match the
rest of jsPDF's encoding rules; `f2` and `f5` are fixed-precision
formatters for 2- and 5-decimal numeric writes. Fields expose
`Validate` and `Calculate` slots holding JavaScript expressions that
are emitted into the field's `AA` (additional actions) dictionary;
`src/modules/javascript.js` supplies the document-level script slot
referenced by name.
