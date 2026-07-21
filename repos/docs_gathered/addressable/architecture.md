# Addressable: Architecture and Design Philosophy

## Overview

Addressable is a Ruby library providing URI and IRI parsing, construction, normalization, and template processing. It serves as an alternative to the URI module in Ruby's standard library, with broader standards conformance and a richer feature set. The library targets RFC 3986 (URI Syntax), RFC 3987 (IRI), and RFC 6570 (URI Templates, up to level 4).

The library ships as a single RubyGem (`addressable`, version 2.8.x) with one runtime dependency: the `public_suffix` gem, which provides top-level domain recognition for host normalization and domain-component accessors.

## Module Layout

The public namespace is `Addressable`. The library exposes two primary classes and one supporting module:

```
Addressable
├── URI            # lib/addressable/uri.rb
├── Template       # lib/addressable/template.rb
└── IDNA           # lib/addressable/idna.rb
    ├── native.rb  # uses idn gem if available
    └── pure.rb    # pure-Ruby fallback
```

The top-level entry point `lib/addressable.rb` simply requires both `uri.rb` and `template.rb`, making the full surface available in a single `require "addressable"` call. Users who only need URI handling can `require "addressable/uri"` directly; users who need templates can `require "addressable/template"` (which itself requires `uri`).

## Design Philosophy

**Standards over convention.** Every component accessor, normalization step, and encoding rule traces back to a specific RFC section. The code includes explicit inline references to RFC 3986 section numbers (for example, path-joining follows section 5.2.2 and 5.2.3, and path normalization follows section 5.2.4). This traceability is intentional: behavior is defined by the specification, not by heuristics.

**Immutable-friendly value objects.** `Addressable::URI` is designed to be used as a value object. Mutating methods exist (setters for each component, `normalize!`, `join!`, `merge!`) but are counterparts to non-mutating equivalents (`normalize`, `join`, `merge`). Calling `freeze` pre-computes all normalized derived values so frozen instances have no deferred state. The `dup` method produces a structurally independent copy.

**Deferred validation.** Because a URI may pass through intermediate invalid states when multiple components are set together (for example, setting a new authority requires coordinating user, password, host, and port), the class provides `defer_validation` — a block form that suppresses the internal `validate` call until the block exits. This pattern is used throughout the setters and construction helpers.

**Lazy computation with sentinels.** Normalized component values are memoized. The sentinel constant `NONE = Module.new.freeze` distinguishes "not yet computed" from `nil` (which is a valid normalized value). Each setter resets the relevant memoized slots to `NONE`, so the next read re-derives them. This avoids recomputing on every access while ensuring correctness after mutation.

**Dual IDNA backends.** Internationalized domain names require Punycode encoding (RFC 3490). Addressable ships a pure-Ruby implementation that handles this via an embedded Unicode codepoint table and a Punycode codec. If the native `idn` gem (backed by libidn) is installed, the `IDNA::Native` module is loaded instead, delegating all operations to the C library. The switch is made at load time with a `rescue LoadError` fallback, so callers never need to branch on IDNA support.

**Heuristic parsing as an optional layer.** The core `URI.parse` method is strict — it applies the RFC 3986 regex and returns components as written, without guessing intent. The separate `URI.heuristic_parse` method adds a preprocessing step that adjusts common non-conforming inputs (repeated slashes, bare IPv4 addresses, bare domain names, mailto-like strings) before delegating to the strict parser. This layering keeps the standards-conformant path clean.

## Subsystem Interactions

The following diagram summarizes how the subsystems relate:

```
Caller
  │
  ├─ require "addressable/uri"
  │     └── Addressable::URI
  │           ├── CharacterClasses / NormalizeCharacterClasses (constants)
  │           └── Addressable::IDNA (for host normalization)
  │
  └─ require "addressable/template"
        └── Addressable::Template
              ├── Addressable::URI (parsing + encoding)
              └── Template::MatchData (result container)
```

`Addressable::Template` depends on `Addressable::URI` for percent-encoding of expanded values and for parsing the expanded result string into a URI object. `Addressable::URI` depends on `Addressable::IDNA` only during host normalization (`normalized_host`). The IDNA module has no dependency on either of the other two.

## Build and Packaging

The gemspec (`addressable.gemspec`) declares:

- `required_ruby_version`: `>= 2.2`
- Runtime dependency: `public_suffix >= 2.0.2, < 8.0`
- No native extensions; the gem is pure Ruby unless the optional `idn-ruby` gem is separately installed

The Rakefile loads task files from `tasks/`. Available rake tasks include `spec` (default), `gem`, `yard` (documentation generation via YARD), `metrics`, and `git`. CI is configured via GitHub Actions (`.github/workflows/test.yml`) running the RSpec test suite. Test coverage is tracked by SimpleCov.

## Error Handling Conventions

Addressable raises two library-specific exceptions:

- `Addressable::URI::InvalidURIError < StandardError` — raised for malformed or structurally invalid URI strings during parsing or component assignment
- `Addressable::Template::InvalidTemplateValueError < StandardError` — raised during template expansion when a processor's `validate` method returns false
- `Addressable::Template::InvalidTemplateOperatorError < StandardError` — raised for unrecognized operator characters in a template pattern
- `Addressable::Template::TemplateOperatorAbortedError < StandardError` — raised internally during operator processing

For type mismatches (non-string input where a string is required), the library raises Ruby's built-in `TypeError` with descriptive messages. For invalid argument combinations, it raises `ArgumentError`. These conventions make Addressable behave consistently with standard Ruby idioms.
