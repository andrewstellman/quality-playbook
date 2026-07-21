# Packaging and Configuration

## Gem Metadata

Addressable is distributed as a single RubyGem. The gemspec (`addressable.gemspec`) declares:

- **Name**: `addressable`
- **Version**: `2.8.9` (defined in `Addressable::VERSION::STRING` via `lib/addressable/version.rb`)
- **Authors**: Bob Aman (`bob@sporkmonger.com`)
- **License**: Apache-2.0
- **Summary**: "URI Implementation"
- **Required Ruby**: `>= 2.2`
- **Required RubyGems**: `>= 0` (no minimum pinned)
- **Homepage**: `https://github.com/sporkmonger/addressable`

The `require_paths` array is `["lib"]`, so `require "addressable"` loads `lib/addressable.rb`, which in turn requires both `lib/addressable/uri.rb` and `lib/addressable/template.rb`.

The `s.files` list is explicit and minimal, covering exactly the public-facing library and documentation files:

```
CHANGELOG.md
LICENSE.txt
README.md
lib/addressable.rb
lib/addressable/idna.rb
lib/addressable/idna/native.rb
lib/addressable/idna/pure.rb
lib/addressable/template.rb
lib/addressable/uri.rb
lib/addressable/version.rb
```

Test files, benchmark files, and Rake tasks are not included in the packaged gem.

## Runtime Dependency

The only declared runtime dependency is:

```ruby
spec.add_dependency 'addressable', '~> 2.7'
# within the gem itself, the gemspec declares:
s.add_runtime_dependency('public_suffix', ['>= 2.0.2', '< 8.0'])
```

`public_suffix` provides the `PublicSuffix` module used by `Addressable::URI#tld`, `Addressable::URI#tld=`, and `Addressable::URI#domain`. The wide version range (`>= 2.0.2, < 8.0`) accommodates the broad set of major versions that have been tested.

## Optional Native Dependency

The `idn-ruby` gem (which wraps libidn) is an optional runtime dependency. When installed, it activates the `Addressable::IDNA::Native` backend, which delegates IDNA processing to the C library for improved performance and accuracy. The library detects its presence at load time via `rescue LoadError` and falls back gracefully to the pure-Ruby IDNA implementation.

To install the native backend:
```console
$ sudo apt-get install libidn11-dev   # Debian/Ubuntu
$ brew install libidn                 # macOS
$ gem install idn-ruby
```

No code changes are required; the backend switch is automatic.

## Version Module

`lib/addressable/version.rb` defines:

```ruby
module Addressable
  module VERSION
    MAJOR = 2
    MINOR = 8
    TINY  = 9
    STRING = [MAJOR, MINOR, TINY].join('.')
  end
end
```

This module is loaded first (before `uri.rb` and `template.rb`) and is guarded with `if !defined?(Addressable::VERSION)` to prevent double-loading.

## Semantic Versioning

The project follows Semantic Versioning. The README recommends pinning with a pessimistic constraint:

```ruby
spec.add_dependency 'addressable', '~> 2.7'
```

This allows patch and minor updates within the 2.x series while preventing a major version bump from being silently picked up. For bug-fix pinning:

```ruby
spec.add_dependency 'addressable', '~> 2.3', '>= 2.3.7'
```

## Rakefile and Build Tasks

The `Rakefile` loads task files from `tasks/*.rake`:

| Task file | Purpose |
|---|---|
| `tasks/rspec.rake` | Defines the `spec` task using RSpec |
| `tasks/yard.rake` | Generates YARD API documentation |
| `tasks/gem.rake` | Builds the `.gem` artifact |
| `tasks/git.rake` | Git-related release tasks |
| `tasks/metrics.rake` | Code quality metrics |
| `tasks/clobber.rake` | Removes generated files |
| `tasks/profile.rake` | Performance profiling hooks |

The default Rake task is `spec`, so `rake` with no arguments runs the full test suite.

## YARD Documentation

The `.yardopts` file configures YARD for documentation generation. The gemspec declares `README.md` as the `--main` document. YARD can be run via `rake yard`.

## CI Configuration

GitHub Actions workflows in `.github/workflows/`:

- `test.yml` — runs the RSpec suite across a matrix of Ruby versions and `public_suffix` gemfile variants. This confirms compatibility with the declared `>= 2.0.2, < 8.0` range.
- `release.yml` — automates gem publication on tag push.
- `codeql-analysis.yml` — static analysis via GitHub's CodeQL.

Dependabot (`.github/dependabot.yml`) is configured for automated dependency update PRs.

## Benchmarks

The `benchmark/` directory contains two scripts for profiling:

- `benchmark/simple.rb` — measures URI parsing and normalization throughput
- `benchmark/unicode_normalize.rb` — measures Unicode normalization performance specifically

These are not part of the CI suite; they are run manually when evaluating performance changes. A timing chart (`benchmark/time.gif`) is included in the repository for visual comparison.

## Coverage Configuration

`.simplecov` at the repo root configures SimpleCov. `spec_helper.rb` activates it when the `simplecov` gem is available, filtering out the `spec/` and `vendor/` directories. When the `coveralls` gem is present, results are uploaded to Coveralls as part of the CI run.
