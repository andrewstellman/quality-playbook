# URI Templates

## Overview

`Addressable::Template` implements RFC 6570 (URI Template) up to and including level 4. A URI template is a string containing zero or more expressions enclosed in braces — for example, `http://example.com/{+path}{?query*}`. The class supports three primary operations on templates: expansion (filling in variables to produce a URI), partial expansion (filling in some variables while leaving others as expressions), and extraction (matching a URI against a template to recover variable values).

## Creating a Template

```ruby
template = Addressable::Template.new("http://example.com/{resource}{?format}")
```

The constructor accepts any string-like object (`to_str`). The pattern string is duplicated and frozen. Attempting to pass a non-string raises `TypeError`.

`freeze` on a Template pre-computes the variable list, variable defaults, and named captures (derived from the underlying Regexp), so frozen templates are ready for repeated use without additional setup cost.

## Template Pattern Syntax

Addressable follows RFC 6570. An expression has the form `{[operator]varlist}` where:

- **operator** (optional): a single character from `+ # . / ; ? & = , ! @ |`
- **varlist**: a comma-separated list of varspecs
- **varspec**: a variable name optionally followed by a modifier: `*` (explode) or `:\d+` (prefix/length)

The operators Addressable handles for expansion and extraction are:

| Operator | Expansion Style | Leader | Joiner |
|---|---|---|---|
| (none) | Simple string | (none) | `,` |
| `+` | Reserved | (none) | `,` |
| `#` | Fragment | `#` | `,` |
| `.` | Label | `.` | `.` |
| `/` | Path segment | `/` | `/` |
| `;` | Path-style params | `;` | `;` |
| `?` | Form-style query | `?` | `&` |
| `&` | Form-style query continuation | `&` | `&` |

The `LEADERS` and `JOINERS` hash constants in the class capture these rules.

Variable names may contain letters, digits, underscores, and percent-encoded characters. The `VARNAME` and `VARSPEC` regular expressions enforce this grammar. The full expression grammar is captured in `EXPRESSION = /\{([operator])?(varlist)\}/`.

## Expansion

### Full Expansion: `expand(mapping, processor = nil, normalize_values = true)`

Produces an `Addressable::URI` by substituting all variables in the pattern from the `mapping` hash. Unmapped variables contribute nothing (they are omitted from the output). Keys may be strings or symbols; the mapping is normalized to string keys internally.

The encoding applied to each substituted value depends on the operator:
- For `+` and `#` operators: reserved characters (from both RESERVED and UNRESERVED classes) are allowed through without encoding.
- For all other operators: only UNRESERVED characters are allowed; everything else is percent-encoded.

Array and Hash values are supported and produce exploded or joined forms according to the `*` modifier and the operator's joiner character.

If `normalize_values` is `true` (the default), string values are Unicode-NFC normalized before encoding.

If a `processor` object is supplied, it may implement:
- `validate(name, value)` — returns `true` or `false`; if false, `InvalidTemplateValueError` is raised
- `transform(name, value)` — returns a string to substitute in place of the percent-encoded value; when a transform is used, automatic percent-encoding is bypassed

### Partial Expansion: `partial_expand(mapping, processor = nil, normalize_values = true)`

Produces a new `Addressable::Template` with some variables filled in and others left as expressions. The returned template is a valid RFC 6570 template that can be expanded further.

The method handles operator transitions for form-style query expressions: when the `?` operator's first variable is supplied, subsequent variables in the same expansion shift to the `&` operator in the output pattern, preserving valid query-string syntax.

### Inspecting Variables

- `variables` — returns an Array of variable name strings in the order they appear in the pattern, deduplicated
- `keys` and `names` — aliases for `variables`
- `variable_defaults` — returns a Hash of variable names to their default values (when specified in the pattern via default syntax); variables without defaults are excluded

## Extraction

### `match(uri, processor = nil)`

Matches the URI against the template pattern and returns an `Addressable::Template::MatchData` object, or `nil` if the URI does not match. The matching is performed by converting the template pattern into a regular expression and running it against the URI string. The regex is constructed by `parse_template_pattern`, which translates each expression into a capturing group.

For each captured group, the method applies the appropriate value decoding:
- Simple, `+`, `#`, `/`, `.` operators: splits on the operator's joiner if the `*` explode modifier is present
- `;`, `?`, `&` operators: splits on the joiner and then on `=` to recover key/value structure for exploded hash values

If a `processor` object implements `restore(name, value)`, it is called for each extracted value, allowing custom reverse-transformations (such as converting `+` back to spaces in query values). Without a processor, values are passed through `URI.unencode_component`.

### `extract(uri, processor = nil)`

A convenience wrapper around `match` that returns the `mapping` hash directly, or `nil` if there is no match.

## Template::MatchData

The match data object returned by `match` exposes:

- `uri` — the `Addressable::URI` that was matched, frozen
- `template` — the `Addressable::Template` used for matching
- `mapping` — a frozen `Hash` of variable names to extracted values; variables present in the template but absent in the URI are included with a `nil` value
- `variables` / `keys` / `names` — the full variable list from the template
- `values` / `captures` — an Array of captured values in variable order, with `nil` for unmatched variables
- `[](key, len = nil)` — access by variable name (String/Symbol) or positional index (Integer), mirroring `::MatchData` behavior
- `values_at(*indexes)` — multiple captures at once
- `to_a` — the matched URI string followed by all values
- `to_s` / `string` — the matched URI as a string
- `pre_match` / `post_match` — empty strings (provided for code that expects a `::MatchData`-like object)

## Regexp Coercion

`to_regexp` converts the template pattern to a Ruby `Regexp` using the same internal `parse_template_pattern` that `match` uses. The resulting regex matches (but does not extract structured data from) URIs that would match the template. `source` returns the regex source string, and `named_captures` returns the named-capture hash.

## Equality

Two templates are equal (`==` / `eql?`) if and only if their pattern strings are equal. No normalization of the pattern is performed.

## Processor Protocol

The processor argument accepted by `expand`, `partial_expand`, and `match` is an informal protocol (duck typing, not a class or module). The expected methods are:

For expansion (`expand` / `partial_expand`):
- `validate(name, value) → Boolean` — return false to abort expansion with `InvalidTemplateValueError`
- `transform(name, value) → String` — return a pre-encoded string value

For extraction (`match` / `extract`):
- `restore(name, value) → String` — reverse-transform an extracted string value
- `match(name) → String` — return a regex capture group source for a variable (default `".*?"`)

Any subset of these methods may be implemented; the template checks `respond_to?` before calling each one.
