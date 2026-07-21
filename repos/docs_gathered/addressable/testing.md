# Testing Conventions

## Overview

Addressable uses RSpec as its testing framework, with SimpleCov (or Coveralls) for coverage tracking. The test suite is structured to cover each public subsystem at the unit level, with spec files that map closely to the library's source modules. The default Rake task runs the full spec suite.

## Test Organization

Spec files are located under `spec/addressable/`:

| Spec file | Module under test |
|---|---|
| `uri_spec.rb` | `Addressable::URI` — parsing, construction, accessors, normalization, encoding, joining, comparison |
| `template_spec.rb` | `Addressable::Template` — expansion, partial expansion, extraction, match data |
| `idna_spec.rb` | `Addressable::IDNA` — Punycode codec, to_ascii, to_unicode, native vs. pure-Ruby behavior |
| `net_http_compat_spec.rb` | Compatibility with Ruby's standard library `Net::HTTP` and `URI` modules |
| `security_spec.rb` | Behavior of the library under various input conditions |

The `spec_helper.rb` configures RSpec with `warnings: true` and `filter_run_when_matching :focus`, allowing individual examples to be focused during development.

## Coverage Configuration

The `.simplecov` file (at the repo root) and the `spec_helper.rb` setup configure SimpleCov to exclude `spec/` and `vendor/` from coverage reporting. If the `coveralls` gem is present, it uploads results automatically. If only `simplecov` is installed, coverage is reported locally. If neither is present, the require is skipped silently.

## Platform and Engine Helpers

`spec_helper.rb` exposes a `TestHelper` utility class with three class methods:

- `TestHelper.is_jruby?` — returns `true` when running on JRuby (`JRUBY_VERSION` constant is defined)
- `TestHelper.is_mri?` — returns `true` when `RUBY_ENGINE == "ruby"` (standard MRI/YARV)
- `TestHelper.is_windows?` — returns `true` when the Ruby description includes `mswin`, `ming`, or `cygwin`
- `TestHelper.native_supported?` — returns `true` when both `is_mri?` and not `is_windows?`, meaning the native IDNA backend can be tested

These helpers are used in `idna_spec.rb` to conditionally run tests that require the native idn gem, skipping them on platforms where it is unavailable.

## Gemfiles for Compatibility Testing

The `gemfiles/` directory contains alternate `Gemfile` configurations for testing against different versions of the `public_suffix` dependency:

- `gemfiles/public_suffix_2.rb` — tests against `public_suffix ~> 2.0`
- `gemfiles/public_suffix_3.rb` — tests against `public_suffix ~> 3.0`
- `gemfiles/public_suffix_4.rb` — tests against `public_suffix ~> 4.0`
- `gemfiles/public_suffix_5.rb` — tests against `public_suffix ~> 5.0`
- `gemfiles/public_suffix_6.rb` — tests against `public_suffix ~> 6.0`
- `gemfiles/public_suffix_7.rb` — tests against `public_suffix ~> 7.0`

The CI workflow (`.github/workflows/test.yml`) runs the matrix of supported Ruby versions against these gemfiles to confirm that the library works across the full range of declared `public_suffix` compatibility.

## Rake Task Setup

The primary task runner is configured in `tasks/rspec.rake`. The default `task :default => "spec"` ensures running `rake` without arguments executes the full spec suite. Additional tasks include:

- `yard` — generates YARD documentation
- `metrics` — code quality metrics
- `gem` — builds the `.gem` artifact
- `clobber` — cleans build artifacts

## Test Patterns in uri_spec.rb

The URI spec is the largest file. It uses RSpec `describe` blocks organized by method name or behavior cluster, for example:

- `describe ".parse"` — round-trip tests for a comprehensive set of URI strings, including edge cases for IPv6 addresses, URIs with percent-encoded characters, relative references, and scheme-specific forms
- `describe "#normalize"` — examples that compare `uri.normalize.to_s` against expected canonical strings
- `describe "#join"` and `describe ".join"` — RFC 3986 section 5.4 test cases for reference resolution
- `describe "#query_values"` — structured query parsing and round-trip encoding
- `describe ".encode_component"` and `describe ".unencode"` — encoding table and character class behavior
- `describe ".form_encode"` and `describe ".form_unencode"` — form encoding round-trips
- `describe "#route_from"` / `describe "#route_to"` — relative URI computation

RSpec `its` (from the `rspec-its` gem, required in `spec_helper.rb`) is used extensively for concise single-attribute assertions on parsed URI instances.

## Test Patterns in template_spec.rb

The template spec is organized around RFC 6570 level-4 test cases, covering all operator types. The structure typically follows:

```ruby
describe "with operator X" do
  it "expands correctly" do ...
  it "extracts correctly" do ...
  it "partially expands correctly" do ...
end
```

Custom processor classes are defined inline within examples to test the `validate`, `transform`, `restore`, and `match` hooks of the processor protocol.

## Test Patterns in idna_spec.rb

The IDNA spec tests both the pure-Ruby and (when available) native backends with the same set of examples, using `TestHelper.native_supported?` to gate native-only blocks. Tests include:

- Punycode encoding and decoding of known Unicode domain labels
- Round-trip `to_ascii` / `to_unicode` for internationalized domain names
- Handling of edge cases: empty labels, labels exactly 63 and 64 characters long, already-ASCII labels
- The deprecated `unicode_normalize_kc` method warning behavior
