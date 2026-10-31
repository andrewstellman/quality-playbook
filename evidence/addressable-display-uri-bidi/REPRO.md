# addressable BUG-044 reproduction (security triage, reproduce-only)

Date (UTC): run on 2026-10-20. Repo https://github.com/sporkmonger/addressable

## Clone and head
- Cloned current main into `/tmp/claude-0/sec/addressable/src` with `--depth 50`, `GIT_LFS_SKIP_SMUDGE=1`.
- HEAD: `d298c9f551fa9748d16dbfb6273b70f60b3d61bc` (same commit the campaign recorded as head)
- HEAD date: `2026-05-17T22:21:47+02:00`
- HEAD subject: `Build(deps): Bump github/codeql-action from 4.35.4 to 4.35.5 (#594)`

## Install
- Ruby 3.3.6, bundler 4.0.18.
- `idn-ruby` (the libidn binding) fails to build here (no system libidn). That is the right configuration for this bug: it is specifically about the pure Ruby IDNA backend, which is the default when libidn is absent. The Gemfile gates idn-ruby behind `ENV["IDNA_MODE"] != "pure"`, so `IDNA_MODE=pure bundle install` installs the rest cleanly (`Bundle complete! 11 Gemfile dependencies, 24 gems`). `BUNDLE_PATH=/tmp/claude-0/sec/addressable/.bundle`.
- Confirmed the pure backend loads: `Addressable::IDNA.name` is `Addressable::IDNA` (the pure module), `to_ascii` responds.

## Fix-since-run check
HEAD equals the campaign head (d298c9f), so nothing has landed on main since the run. Separately, `git log -1 -- lib/addressable/idna/pure.rb` is `a27b0df` dated `2025-11-25`, well before the run; the affected `to_unicode` punycode-decode path (idna/pure.rb:92-99) is unchanged. Not fixed.

## Reproduction
Script `/tmp/claude-0/sec/scripts/repro_addr.rb`, run with `IDNA_MODE=pure bundle exec ruby` against the clone's `lib`. Verbatim output:
```
IDNA backend: Addressable::IDNA
to_ascii: "xn--abcmoc-dm0c"
display_uri.host: "abc‮moc.com"
contains U+202E (RLO): true
codepoints: U+0061 U+0062 U+0063 U+202E U+006D U+006F U+0063 U+002E U+0063 U+006F U+006D
```
`Addressable::IDNA.to_ascii("abc‮moc")` produces the ACE label `xn--abcmoc-dm0c`. Parsing `http://xn--abcmoc-dm0c.com/` and calling `display_uri.host` punycode-decodes the label back to `abc‮moc`, i.e. it re-introduces U+202E RIGHT-TO-LEFT OVERRIDE into the displayed host. The pure `to_unicode` returns the decoded label without the nameprep prohibited-output (RFC 3454 table C.8) check, so a display-changing character survives into the string an application would show to a user.

## Regression test (applied from the record's patch)
`spec/addressable/qpb_bug_044_spec.rb`, example "BUG-044: display_uri renders bidi-override ...". Run red (verbatim):
```
  1) BUG-044 regression (REQ-017) BUG-044: display_uri renders bidi-override and other display-changing characters decoded from ACE labels (e.g. U+202E), a display spoof
     Failure/Error: expect(shown).not_to match(/[‪-‮‎‏]/)
       expected "abc‮moc.com" not to match /[‪-‮‎‏]/
     # ./spec/addressable/qpb_bug_044_spec.rb:14 ...
Finished in 0.09456 seconds (files took 0.74744 seconds to load)
1 example, 1 failure
```
RED on unmodified main. (The record describes it as "pending-guarded"; the actual patch is a plain failing example, which is what ran.)

## Full suite baseline (unmodified main, pure mode)
```
1433 examples, 9 failures, 5 pending
```
The 9 failures are all `Encoding::CompatibilityError: invalid byte sequence in US-ASCII` raised inside the installed `public_suffix` 7.0.5 gem's TLD-list parsing (`public_suffix/list.rb:76`), reached from addressable's `tld`/`domain` specs. That is a dependency-version/environment mismatch (the gem resolved to 7.0.5 here), not an addressable defect, and unrelated to BUG-044. 5 pending are pre-existing pending examples.

## No fix written
A fix patch exists in the record but was not applied/written; the task says to write a fix only if it is a few obvious lines. The correct fix (re-run the nameprep prohibited-output / display-changing-character check in `to_unicode` and fall back to the ACE form) is a design choice about which code-point ranges to reject and is more than a couple of obvious lines, so no fix was attempted.

## Impact assessment
- Input controller: whoever supplies the hostname/URI that an application parses and then displays via `display_uri` (e.g. a URL in user-generated content, an email, a chat message, a link preview).
- What the attacker gains: a registrable ACE/punycode label (`xn--...`) that `display_uri` decodes to a string containing U+202E (or other bidi/format controls), so the displayed host renders with its characters reordered. This is a homograph/bidi display-spoofing vector: `xn--abcmoc-dm0c.com` can be shown as something that reads differently (the tail renders reversed), which can make a hostile host look like a trusted one in any UI that renders `display_uri` output.
- Vulnerability or ordinary bug: a real security-relevant display-spoofing bug, but low severity (the campaign downgraded it MEDIUM -> LOW). It does not corrupt parsing or routing; `to_ascii`/the actual host is correct, only the human-readable rendering is spoofable, and it only bites applications that both use the pure backend (libidn absent) and display `display_uri` to users without their own sanitization. I would call it a genuine vulnerability of the display-spoof class, low severity.

## Paths written
- `/tmp/claude-0/sec/addressable/REPRO.md` (this file)
- `/tmp/claude-0/sec/addressable/out/0001-BUG-044-regression-test-display_uri-renders-bidi-ove.patch`
- Script: `/tmp/claude-0/sec/scripts/repro_addr.rb`
