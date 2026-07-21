# URI Normalization

## Overview

Normalization in Addressable transforms a URI into a canonical form as specified by RFC 3986 section 6. Each component has a corresponding `normalized_*` accessor that returns the normalized version of that component's raw value. The full-URI `normalize` method assembles these into a new `Addressable::URI` object. Normalization is non-destructive by default; `normalize!` replaces the receiver in place.

## Lazy Memoization

Normalized values are computed on first access and memoized. The sentinel constant `NONE = Module.new.freeze` marks "not yet computed" — distinct from `nil`, which is a legitimate normalized value. Each raw-component setter resets the relevant memoized slots to `NONE`:

- `scheme=` resets `@normalized_scheme`
- `user=` resets `@normalized_user` and `@normalized_userinfo`
- `password=` resets `@normalized_password` and `@normalized_userinfo`
- `host=` resets `@normalized_host`
- `port=` resets `@normalized_port`
- `path=` resets `@normalized_path`
- `query=` resets `@normalized_query`
- `fragment=` resets `@normalized_fragment`

Calling `freeze` on a URI pre-computes all normalized values before freezing, so frozen URIs have no deferred computation and no risk of mutation after the fact.

## Component-by-Component Normalization

### Scheme

`normalized_scheme` lowercases the scheme and strips surrounding whitespace. The `ssh+svn` scheme is retained as-is without normalization (it has been deprecated but is handled specially to avoid breaking existing users).

### User and Password

`normalized_user` and `normalized_password` strip whitespace, then percent-encode any characters outside the UNRESERVED character class. For HTTP and HTTPS URIs, if both user and password are blank after stripping, both normalize to `nil` (empty credentials are removed from the canonical form).

### Host

`normalized_host` is the most complex component:

1. The raw host is first unencoded (to handle any percent-encoded characters in the host string).
2. It is lowercased.
3. The result is passed through `Addressable::IDNA.to_ascii`, which converts any internationalized label (containing non-ASCII characters) to its Punycode ACE form (`xn--...`).
4. A single trailing dot is removed (trailing dots are syntactically legal but semantically redundant).
5. The result is percent-encoded against the HOST character class.

This means `normalized_host` always produces an ASCII string in lowercase, with IDN labels in Punycode, suitable for DNS lookup and comparison.

### Port

`normalized_port` returns `nil` when the port equals the default for the normalized scheme (as given in `PORT_MAPPING`). Otherwise, it returns the integer port as-is. The effect is that default ports are suppressed from the canonical representation.

### Authority

`normalized_authority` assembles `normalized_userinfo`, `normalized_host`, and `normalized_port` with the standard `@` and `:` separators.

### Path

`normalized_path` performs two transformations:

1. Each path segment is individually percent-encoded against the PCHAR character class, applying Unicode NFC normalization before encoding (via `normalize_component`).
2. The assembled path is then passed through `URI.normalize_path`, which applies the RFC 3986 section 5.2.4 dot-segment removal rules:
   - `/./` and `/.` at the end of a path are replaced by `/`
   - `/../` and `/..` at the end, along with the preceding segment, are replaced by `/`
   - Leading `../` and `./` segments are removed
   - Paths beginning with `/../` or `/..` are reduced to `/`

For HTTP, HTTPS, FTP, and TFTP URIs, if the normalized path is empty, it is set to `/`.

Relative paths that start with a segment containing a colon (which could be misread as a scheme) have the colon in the first segment percent-encoded to disambiguate.

### Query

`normalized_query` normalizes each `key=value` pair separated by `&`, applying `normalize_component` with the QUERY character class. The `+` sign is preserved in plus-encoded query strings. Two optional flag arguments influence behavior:

- `:compacted` — removes empty pairs and deduplicates
- `:sorted` — sorts pairs alphabetically

These flags are not applied by default through `normalize`; they can be used by calling `normalized_query(:compacted)` or `normalized_query(:sorted)` directly.

### Fragment

`normalized_fragment` applies `normalize_component` with the FRAGMENT character class. An empty fragment normalizes to `nil`.

## Full URI Normalization

`normalize` constructs a new `Addressable::URI` from the individual normalized components:

```ruby
Addressable::URI.new(
  scheme:    normalized_scheme,
  authority: normalized_authority,
  path:      normalized_path,
  query:     normalized_query,
  fragment:  normalized_fragment
)
```

It uses `authority` rather than the individual user/password/host/port keys to avoid triggering redundant validation on intermediate states.

The `feed:` scheme receives special handling: a `feed:` URI wrapping an `http:` URI (such as `feed:http://example.com/rss`) is unwrapped to just the `http:` URI before normalization.

## Display URI

`display_uri` returns a normalized URI suitable for display, with the host component converted back from Punycode to Unicode via `IDNA.to_unicode`. This allows showing `www.example.com` in Unicode when the underlying host was entered or stored in internationalized form, while the `normalize` method always uses the Punycode form for wire-level and comparison use.

## Component-Level Encoding Helpers

These class methods operate on individual string components rather than full URIs:

### `URI.encode_component(component, character_class, upcase_encoded = '')`

Percent-encodes a string component. Characters matching the `character_class` (a `String` specifying the allowed character set as a regex character class body, or a `Regexp`) are left alone; all others are replaced with `%XX` sequences (uppercase hex). The optional `upcase_encoded` parameter specifies bytes whose existing percent-encoded representations should be upcased for normalization. The operation is performed on a binary-encoded copy of the string to correctly handle bytes in the 0x80–0xFF range. Aliased as `escape_component`.

### `URI.unencode(uri, return_type = String, leave_encoded = '')`

Decodes percent-encoded sequences in a string or URI, returning the decoded value as either a `String` or `Addressable::URI`. The `leave_encoded` parameter lists characters that should remain encoded. Aliased as `unescape`, `unencode_component`, and `unescape_component`.

### `URI.normalize_component(component, character_class, leave_encoded = '')`

Combines decoding and re-encoding: first decodes the input, applies Unicode NFC normalization (`unicode_normalize(:nfc)`), then re-encodes. This ensures that components in different normalization forms or with unnecessarily percent-encoded characters are brought to a canonical representation. Falls back to encoding without NFC if the string contains malformed UTF-8.

### `URI.encode(uri, return_type = String)` / `URI.normalized_encode(uri, return_type = String)`

`encode` encodes an entire URI string by parsing it, then re-encoding each component against its appropriate character class. `normalized_encode` first decodes all components, applies NFC normalization, then re-encodes — the host component is left un-encoded to permit internationalized domain names in the display representation. Both accept a `return_type` of `String` or `Addressable::URI`.

## Form Encoding

`URI.form_encode(form_values, sort = false)` encodes key/value pairs in `application/x-www-form-urlencoded` format: characters outside UNRESERVED are percent-encoded, and spaces are rendered as `+`. Input may be a `Hash` or an `Array` of pairs. Newlines are normalized to CRLF pairs before encoding. The optional `sort` parameter sorts pairs before encoding, which can be useful for deterministic OAuth signatures or cache keys.

`URI.form_unencode(encoded_value)` is the inverse: it splits on `&`, splits each pair on the first `=`, and decodes the `+` sign as space and percent-encoded sequences as their character values. Returns an `Array` of `[key, value]` pairs to correctly handle duplicate keys.
