# Character Classes and Encoding Tables

## Overview

Addressable manages percent-encoding through a set of constants that define which characters are legal in each URI component. These constants live in nested modules within `Addressable::URI` and are used throughout the parsing, normalization, and template-expansion code. Understanding them is essential for working with the encoding API or extending the library.

## CharacterClasses

`Addressable::URI::CharacterClasses` holds string constants suitable for embedding in regex character class brackets (i.e., the body of `[...]`). Each constant is a concatenated string of character ranges:

| Constant | Characters included |
|---|---|
| `ALPHA` | `a-zA-Z` |
| `DIGIT` | `0-9` |
| `GEN_DELIMS` | `:`, `/`, `?`, `#`, `[`, `]`, `@` |
| `SUB_DELIMS` | `!`, `$`, `&`, `'`, `(`, `)`, `*`, `+`, `,`, `;`, `=` |
| `RESERVED` | `GEN_DELIMS + SUB_DELIMS` |
| `UNRESERVED` | `ALPHA + DIGIT + -._~` |
| `RESERVED_AND_UNRESERVED` | `RESERVED + UNRESERVED` |
| `PCHAR` | `UNRESERVED + SUB_DELIMS + :@` |
| `SCHEME` | `ALPHA + DIGIT + -+.` |
| `HOST` | `UNRESERVED + SUB_DELIMS + [:` `]` |
| `AUTHORITY` | `PCHAR + []` |
| `PATH` | `PCHAR + /` |
| `QUERY` | `PCHAR + /?` |
| `FRAGMENT` | `PCHAR + /?` |

These definitions correspond directly to the ABNF grammar in RFC 3986. The `RESERVED` string is frozen explicitly because Ruby string interpolation prior to 3.0 did not freeze interpolated strings under `frozen_string_literal`.

## CharacterClassesRegexps

`Addressable::URI::CharacterClassesRegexps` holds compiled `Regexp` objects, one per component, each built by negating the corresponding `CharacterClasses` string:

```ruby
AUTHORITY = /[^#{CharacterClasses::AUTHORITY}]/
FRAGMENT  = /[^#{CharacterClasses::FRAGMENT}]/
HOST      = /[^#{CharacterClasses::HOST}]/
PATH      = /[^#{CharacterClasses::PATH}]/
QUERY     = /[^#{CharacterClasses::QUERY}]/
RESERVED  = /[^#{CharacterClasses::RESERVED}]/
RESERVED_AND_UNRESERVED = /[^#{CharacterClasses::RESERVED_AND_UNRESERVED}]/
SCHEME    = /[^#{CharacterClasses::SCHEME}]/
UNRESERVED = /[^#{CharacterClasses::UNRESERVED}]/
```

A regex of the form `/[^allowed-chars]/` matches any character that must be percent-encoded. These are passed to `encode_component` as the `character_class` argument, causing matching characters to be encoded and all others to pass through.

## NormalizeCharacterClasses

`Addressable::URI::NormalizeCharacterClasses` holds regexps for the normalization pass. These are used in `normalize_component` and the individual `normalized_*` accessors. The key difference from `CharacterClassesRegexps` is in the `QUERY` constant, which additionally excludes `%` sequences that should be preserved:

```ruby
QUERY = %r{[^a-zA-Z0-9\-\.\_\~\!\$\'\(\)\*\+\,\=\:\@\/\?%]|%(?!2B|2b)}
```

This regex leaves `%2B` and `%2b` (the encoding of `+`) encoded — rather than decoding them to literal `+` — because `+` has special meaning in form-encoded query strings. All other percent-encoded sequences that decode to allowed characters are normalized out.

## Encoding Tables

Two lookup tables are built once at class load time and frozen, used to avoid repeated format operations inside the encoding hot path:

```ruby
SEQUENCE_ENCODING_TABLE = (0..255).map do |byte|
  format("%02x", byte).freeze
end.freeze

SEQUENCE_UPCASED_PERCENT_ENCODING_TABLE = (0..255).map do |byte|
  format("%%%02X", byte).freeze
end.freeze
```

- `SEQUENCE_ENCODING_TABLE[byte]` returns a two-character lowercase hex string (`"00"` through `"ff"`), used when building `leave_encoded` patterns.
- `SEQUENCE_UPCASED_PERCENT_ENCODING_TABLE[byte]` returns the three-character percent-encoded form (`"%00"` through `"%FF"` with uppercase hex), used by `encode_component` to produce encoded output.

By pre-building these 256 entries, the encoding loop avoids calling `format` for every byte, which is significant in performance-sensitive paths.

## How Encoding Uses Character Classes

The `encode_component` method takes either a `String` (interpreted as a character class body) or a `Regexp`:

```ruby
def self.encode_component(component, character_class = CharacterClassesRegexps::RESERVED_AND_UNRESERVED, upcase_encoded = '')
```

If a `String` is passed, it is wrapped: `/[^#{character_class}]/`. If a `Regexp` is passed, it is used directly. The component is then re-encoded to ASCII-8BIT, and each byte matching the pattern is replaced with its entry from `SEQUENCE_UPCASED_PERCENT_ENCODING_TABLE`.

The default character class — `RESERVED_AND_UNRESERVED` — encodes nothing (both sets are allowed), making the default a pass-through for already-valid components.

## Template Encoding

`Addressable::Template`'s expansion logic inherits the character class strings from `Addressable::URI::CharacterClasses`:

```ruby
anything = CharacterClasses::RESERVED + CharacterClasses::UNRESERVED
```

This combined set is used to build the `RESERVED` and `UNRESERVED` regex fragments that match values inside template expressions, and the `encode_map` selection in `transform_capture` uses `CharacterClasses::RESERVED + CharacterClasses::UNRESERVED` for `+` and `#` operator expansions (which allow reserved characters through) versus `CharacterClasses::UNRESERVED` alone for all other operators.

## Relationship to RFC 3986

The character class hierarchy maps directly to RFC 3986 section 2:

- Section 2.2 defines reserved characters (gen-delims and sub-delims)
- Section 2.3 defines unreserved characters
- Section 2.1 defines percent-encoding
- Sections 3.1 through 3.5 define the allowed characters in each component

Addressable's character class constants are intended to be the authoritative in-code expression of these grammar rules.
