# URI Parsing and Construction

## Overview

`Addressable::URI` is the core class of the library. It represents a URI or IRI as a set of components, and provides class-level factory methods for creating instances from strings, paths, or component hashes. Once created, a URI object exposes each component as a readable (and writable) attribute, as well as composite views and derived values.

## Factory Methods

### `URI.parse(uri)`

The primary entry point for strict parsing. Accepts a `String`, an existing `Addressable::URI` (returned as a dup), or any object that responds to `to_str`. Returns `nil` when passed `nil`.

Parsing applies the RFC 3986 regex `URIREGEX` to extract scheme, authority, path, query, and fragment in a single scan. The authority is then split further into userinfo (user and password), host, and port. No heuristic adjustments are made; the string is taken as written.

### `URI.heuristic_parse(uri, hints = {})`

A user-friendly alternative that applies preprocessing to common non-conforming inputs before delegating to `parse`. Transformations include:

- Collapsing repeated slashes in `http://`, `https://`, `feed:`, and `file:` URIs
- Prepending a scheme when the input matches an IPv4 address or a bare domain with port
- Moving a bare dotted hostname from the path to the host component

The `hints` hash supports a `:scheme` key (default `"http"`) used when a scheme must be inferred.

### `URI.convert_path(path)`

Creates a `file:` URI from a filesystem path string. Handles Windows-style paths (backslashes, drive letters with `|` or `:` separator), normalizes slashes, and appends a trailing slash for directories. If the input is already an absolute URI with a non-file scheme, it is passed through `parse` without alteration.

### `URI.join(*uris)`

Joins one or more URI strings or objects sequentially, applying RFC 3986 section 5.2 reference resolution at each step. Equivalent to calling `join` on the first URI with each subsequent one.

### `URI.new(options = {})`

Constructs a URI from an options hash. Valid keys are `:scheme`, `:user`, `:password`, `:userinfo`, `:host`, `:port`, `:authority`, `:path`, `:query`, `:query_values`, and `:fragment`. Composite keys (`:userinfo`, `:authority`) may not be combined with their constituent counterparts in the same call. Construction is wrapped in `defer_validation` to allow intermediate invalid states; `validate` is called once at the end.

## Component Accessors

Each URI component is accessible as a read/write attribute:

| Attribute | Type | Notes |
|---|---|---|
| `scheme` | `String` or `nil` | Must match `/\A[a-z][a-z0-9\.\+\-]*\z/i` |
| `user` | `String` or `nil` | Part of userinfo |
| `password` | `String` or `nil` | Requires a non-nil user |
| `userinfo` | `String` or `nil` | Composite: `user:password` |
| `host` | `String` or `nil` | Raw host including brackets for IPv6 |
| `hostname` | `String` or `nil` | Like `host` but strips IPv6 brackets |
| `port` | `Integer` or `nil` | Stored as integer; `0` coerces to `nil` |
| `authority` | `String` or `nil` | Composite: `[userinfo@]host[:port]` |
| `path` | `String` | Never nil; defaults to `""` |
| `query` | `String` or `nil` | Raw query string |
| `fragment` | `String` or `nil` | Fragment identifier |

Additionally, derived accessors are available:

- `site` — scheme plus authority (useful for HTTP origin comparisons)
- `origin` — RFC 6454 origin serialization (scheme, host, and non-default port)
- `tld` — top-level domain via PublicSuffix
- `domain` — registrable domain via PublicSuffix
- `request_uri` — path plus query, for use in HTTP requests
- `inferred_port` — port if explicit, otherwise the default for the scheme
- `default_port` — the default port from `PORT_MAPPING` for the current scheme
- `basename`, `extname` — filename components of the path

Composite setters (`authority=`, `userinfo=`, `site=`, `origin=`, `request_uri=`) parse their string argument and distribute the extracted sub-components to the appropriate individual instance variables, resetting memoized caches as they go.

## Validation

After each component setter, `validate` is called (unless deferred). The validations are:

1. An IP-based URI (`ip_based?`) with a scheme but no host and no path raises `InvalidURIError`.
2. A URI with a port, user, or password but no host raises `InvalidURIError`.
3. A relative path (not starting with `/`) combined with an authority raises `InvalidURIError`.
4. A path beginning with `//` without an authority raises `InvalidURIError`.
5. A host containing characters outside the allowed set raises `InvalidURIError`.

## Joining and Merging

**`join(uri)`** resolves `uri` against `self` using the RFC 3986 section 5.2.2 algorithm. If the argument has a scheme, it replaces all of `self`'s components. If it has an authority, it replaces everything except the scheme. If it has only a path, the base path's last segment is removed and the argument path is appended, with double-dot segments then removed via `normalize_path`. `join!` is the in-place variant. The `+` operator is aliased to `join`.

**`merge(hash)`** replaces specific components (by key) with values from the supplied hash. Unlike `join`, the path is not treated specially — whatever is in `:path` overwrites `self.path` directly. `merge!` is the in-place variant.

## Relative URI Computation

**`route_from(uri)`** computes the shortest normalized relative form of `self` that, when resolved against the normalized form of `uri`, produces `self`. Both URIs must be absolute. The method compares scheme, authority, and path components in sequence, omitting shared prefixes.

**`route_to(uri)`** is the inverse: it computes the relative form of `uri` that uses `self` as the base.

## Serialization and Comparison

`to_s` assembles the components back into a string following the standard scheme `:` `//authority` `path` `?query` `#fragment` grammar. The result is memoized in `@uri_string` and reset whenever any component changes. `to_str` is aliased to `to_s`, allowing implicit string conversion.

`to_hash` returns a plain Ruby `Hash` with the eight component keys as symbols.

Equality uses two operators:
- `==` normalizes both sides before comparing, so `"HTTP://Example.COM/"` equals `"http://example.com/"`.
- `eql?` compares raw (unnormalized) string representations.
- `===` normalizes and compares, returning `false` (rather than raising) if the argument cannot be parsed.

The `hash` method returns a normalized hash value so URI objects can be used as Hash keys and in Sets with normalization-aware deduplication.

`encode_with` and `init_with` provide YAML serialization support.

## Port Mapping

The constant `PORT_MAPPING` maps scheme names to default port numbers for the schemes: http (80), https (443), ftp (21), tftp (69), sftp (22), ssh (22), svn+ssh (22), telnet (23), nntp (119), gopher (70), wais (210), ldap (389), and prospero (1525). When a port equals the scheme's default, `normalized_port` returns `nil` so the port is omitted from the normalized string.
