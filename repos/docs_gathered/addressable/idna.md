# Internationalized Domain Names (IDNA)

## Overview

`Addressable::IDNA` is the module responsible for converting between Unicode domain name labels and their ASCII-compatible encoding (ACE) forms as defined by RFC 3490 (Internationalized Domain Names in Applications). This module is used internally by `Addressable::URI` during host normalization and display URI generation. Application code typically does not need to call it directly.

## Dual Backend Architecture

The IDNA module uses a load-time feature switch to select between two implementations:

```ruby
# lib/addressable/idna.rb
begin
  require "addressable/idna/native"
rescue LoadError
  require "addressable/idna/pure"
end
```

If the `idn` gem (which wraps the C library libidn) is available, the native backend is loaded. Otherwise, the pure-Ruby backend is used. Both backends expose the same public method surface, so callers never need to know which is active.

## Native Backend (`idna/native.rb`)

The native backend wraps the `IDN::Idna` and `IDN::Punycode` interfaces from the `idn-ruby` gem:

- `IDNA.to_ascii(value)` — splits the input on `.`, and for each non-empty label shorter than 64 characters, calls `IDN::Idna.toASCII` with `ALLOW_UNASSIGNED`. Labels 64 characters or longer are passed through unchanged (they are already in a form that does not require encoding). Empty labels (from consecutive dots) produce empty strings. The resulting parts are joined with `.`.

- `IDNA.to_unicode(value)` — the reverse: splits on `.`, calls `IDN::Idna.toUnicode` for short labels, and joins the results. The `ALLOW_UNASSIGNED` flag is passed here as well.

- `IDNA.punycode_encode(value)` — delegates to `IDN::Punycode.encode`.
- `IDNA.punycode_decode(value)` — delegates to `IDN::Punycode.decode`.

The native backend relies on libidn being installed at the OS level. The README gives installation commands for Debian/Ubuntu (`apt-get install libidn11-dev`) and macOS (`brew install libidn`), followed by `gem install idn-ruby`.

## Pure-Ruby Backend (`idna/pure.rb`)

The pure-Ruby implementation handles the full conversion pipeline in Ruby, without native extensions.

### Constants

- `ACE_PREFIX = "xn--"` — the Punycode prefix defined by RFC 3490.
- `UTF8_REGEX` — validates that a string is well-formed UTF-8 (matches the complete byte-sequence grammar, excluding surrogates and overlong encodings).
- `UTF8_REGEX_MULTIBYTE` — matches any multi-byte UTF-8 sequence (i.e., identifies strings that contain non-ASCII characters).
- `UNICODE_DATA` — an embedded hash mapping Unicode codepoints to arrays of [combining_class, exclusion, canonical, compatibility, uppercase, lowercase, titlecase] data. This table covers the codepoints required for case folding and normalization in internationalized domain names.

### `to_ascii(input)`

1. Forces the input to UTF-8 encoding and applies NFKC normalization via `unicode_normalize(:nfkc)`.
2. Switches to binary encoding for regex processing.
3. If the string is valid UTF-8 and contains at least one multi-byte sequence, it applies `unicode_downcase` and splits on `.`.
4. For each label that is valid UTF-8 and multi-byte, it prepends `ACE_PREFIX` and encodes the label with `punycode_encode`.
5. All labels are joined with `.` and the result is forced to UTF-8.

If the input is already ASCII-only (no multi-byte sequences), it is returned after the NFKC normalization step without any Punycode transformation.

### `to_unicode(input)`

Splits on `.`, and for each label that starts with `ACE_PREFIX`, attempts `punycode_decode` on the suffix. If decoding raises `PunycodeBadInput`, the original label is left unchanged (per the RFC's requirement that `toUnicode` never fails). All labels are joined with `.` and the output is forced to UTF-8.

### Unicode Case Folding

`unicode_downcase(input)` (private) unpacks the string as Unicode codepoints, maps each through `lookup_unicode_lowercase`, and repacks. `lookup_unicode_lowercase` consults `UNICODE_DATA` for the lowercase mapping (`UNICODE_DATA_LOWERCASE` index 5). Codepoints not present in the table are returned unchanged.

### Punycode Codec

The pure-Ruby backend includes a full Punycode encoder and decoder (implementing RFC 3492):

- `punycode_encode(input)` — encodes a Unicode string to a Punycode ASCII string. The algorithm: insert basic codepoints first, then encode non-basic codepoints using the generalized variable-length integer scheme (bias adaptation, delta encoding).
- `punycode_decode(input)` — decodes a Punycode string back to Unicode. Raises `PunycodeBadInput` if the input is malformed.

The Punycode implementation uses constants `BASE`, `TMIN`, `TMAX`, `SKEW`, `DAMP`, `INITIAL_BIAS`, `INITIAL_N`, and `DELIMITER` as defined in RFC 3492.

## Integration with URI Normalization

`Addressable::URI#normalized_host` calls `IDNA.to_ascii` during normalization:

```ruby
result = ::Addressable::IDNA.to_ascii(
  URI.unencode_component(self.host.strip.downcase)
)
```

This means a host like `www.詹姆斯.com` is normalized to `www.xn--8ws00zhy3a.com`. The raw `host` attribute retains the original form; `normalized_host` always produces the ACE form.

`Addressable::URI#display_uri` reverses this for display purposes, calling `IDNA.to_unicode` on the normalized host to restore the Unicode form before presenting the URI to users.

## Deprecated Method

Both backends expose `unicode_normalize_kc(value)` as a deprecated class method, which forwards to `value.unicode_normalize(:nfkc)`. The method is marked deprecated (removal target: 2023-04) with `Gem::Deprecate`. Application code should use `String#unicode_normalize(:nfkc)` directly.
