# Query String Handling

## Overview

Addressable provides a layered approach to query strings. The raw `query` attribute stores the query component as a plain string. The `query_values` accessor provides structured access to the query as a `Hash` or `Array` of key/value pairs, with automatic encoding and decoding. Class-level methods handle `application/x-www-form-urlencoded` encoding independently of any URI instance.

## Raw Query Access

The `query` attribute on `Addressable::URI` stores the query component exactly as it appears in the URI string (without the leading `?`). Reading `query` returns `nil` if no query component is present, or an empty string `""` if the query is present but empty (e.g., the URI ends in `?`).

Setting `query=` accepts any string-like object (or `nil`). It resets the memoized `@normalized_query` to `NONE` and clears the composite string cache `@uri_string`. No encoding or validation is applied during assignment; the value is stored verbatim.

## Structured Query Access: `query_values`

### Reading: `query_values(return_type = Hash)`

Parses the raw query string into a structured form. Splitting on `&` decomposes the query into individual `key=value` pairs (or bare keys). Each key and value is then:

1. Passed through `URI.unencode_component` to decode percent-encoded sequences
2. For HTTP and HTTPS URIs (and when the scheme is `nil`), `+` is interpreted as a space before decoding (HTML 4.01 form-encoding convention)

The `return_type` parameter controls the output structure:
- `Hash` (default) — last value wins for duplicate keys; returns `{}` for an empty query string; returns `nil` if `query` is `nil`
- `Array` — preserves all pairs, including duplicates, as `[key, value]` arrays; returns `[]` for an empty query string; returns `nil` if `query` is `nil`

Passing any other class raises `ArgumentError`.

Examples:
```ruby
uri = Addressable::URI.parse("?one=1&two=2&three=3")
uri.query_values
#=> {"one" => "1", "two" => "2", "three" => "3"}

uri = Addressable::URI.parse("?one=two&one=three")
uri.query_values(Array)
#=> [["one", "two"], ["one", "three"]]

uri.query_values(Hash)
#=> {"one" => "three"}   # last value wins
```

### Writing: `query_values=`

Accepts a `Hash` (or any object responding to `to_hash`) or an `Array` of `[key, value]` pairs. The method encodes each key and value using `URI.encode_component` with the UNRESERVED character class, joining pairs with `=` and pairs with `&`.

For `Hash` input, the pairs are sorted alphabetically before encoding (useful for deterministic OAuth signatures and cache keys). For `Array` input, the original order is preserved. Symbol keys are converted to strings.

Array values may be nested:
- `[['b', ['c', 'd', 'e']]]` expands to `b=c&b=d&b=e`
- `[['flag']]` (pair with no value) expands to `flag&`

Setting `query_values = nil` sets `query` to `nil`, removing the query component.

## Class-Level Form Encoding

These methods encode and decode strings in `application/x-www-form-urlencoded` format independently of any URI object. They are useful for encoding HTTP POST bodies or URL query strings from scratch.

### `URI.form_encode(form_values, sort = false)`

Accepts a `Hash` (via `to_hash`) or an `Array` (via `to_ary`) of `[key, value]` pairs. Array values within pairs are expanded into repeated keys. Keys and values are encoded by:

1. Normalizing line breaks within each value to CRLF (`\r\n`)
2. Percent-encoding all characters outside the UNRESERVED class
3. Replacing `%20` (the encoded space) with `+`

The optional `sort` parameter, when `true`, sorts the pairs before encoding. This is documented as useful for OAuth and cache-optimization scenarios.

The return value is a single `String` with pairs joined by `&`.

### `URI.form_unencode(encoded_value)`

Decodes an `application/x-www-form-urlencoded` string. The string is split on `&`, each piece is split on the first `=` (up to 2 parts), and each part is decoded:

1. `+` is replaced with `%20`
2. `URI.unencode_component` decodes all percent-encoded sequences
3. CRLF sequences are normalized to bare `\n`

Returns an `Array` of `[key, value]` pairs. Duplicate keys are preserved as separate pairs. A missing value (key without `=`) returns `nil` as the value.

## Normalized Query

`normalized_query` is the normalized form of the raw query string. It applies `normalize_component` (decode → NFC → re-encode) to each `key=value` pair individually, using the `NormalizeCharacterClasses::QUERY` regexp. The `+` sign is preserved in the encoding (not decoded to space) to maintain the distinction between `+`-encoded and `%20`-encoded spaces.

Two optional flags affect the normalization:
- `:compacted` — after normalizing, removes empty pairs and deduplicates identical pairs
- `:sorted` — sorts the remaining pairs alphabetically by the normalized pair string

These flags are applied by calling `normalized_query(:compacted)` or `normalized_query(:sorted)` or `normalized_query(:compacted, :sorted)`. The default `normalize` method calls `normalized_query` without flags, so compaction and sorting are opt-in.

## Interaction with Template Query Expansion

`Addressable::Template` uses the `?` operator for form-style query string generation:

```ruby
template = Addressable::Template.new("http://example.com/{?one,two,three}")
template.expand({"one" => "1", "two" => "2", "three" => "3"}).to_s
#=> "http://example.com/?one=1&two=2&three=3"
```

The template encoding for `?` and `&` operators uses the UNRESERVED character class (same as `query_values=`), and hash/array values are joined with `&`. Partial expansion of `?` operators correctly transitions remaining variables to `&` to maintain a valid query string.

Template extraction of `?` and `&` operator expressions decodes the query-string representation back into structured values: splitting on the joiner and then on `=`, producing strings for scalar values and Hashes for exploded mappings.
