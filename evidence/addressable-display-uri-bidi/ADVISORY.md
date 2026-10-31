Title: display_uri decodes punycode labels containing bidi and other display-changing control characters (pure IDNA backend)

Ecosystem: RubyGems
Package: addressable
Affected versions: <= 2.9.0 and main at d298c9f (pure Ruby IDNA backend, used when libidn / idn-ruby is absent)
Patched versions: none yet
Severity: Low (CVSS 3.1 suggestion: 3.7, AV:N/AC:H/PR:N/UI:R/S:U/C:N/I:L/A:N)
CWE: CWE-451 User Interface (UI) Misrepresentation of Critical Information, CWE-176 Improper Handling of Unicode Encoding
Credit: Andrew Stellman

Description

`Addressable::IDNA.to_unicode` in the pure Ruby backend (lib/addressable/idna/pure.rb:92-99) punycode-decodes an ACE (`xn--`) label and returns the result without the nameprep prohibited-output check (RFC 3454 tables C.8 and C.9; UTS 46 disallows these as well). `Addressable::URI#display_uri` therefore shows hosts containing U+202E RIGHT-TO-LEFT OVERRIDE, the other bidi controls (U+202A to U+202E, U+200E, U+200F) and format characters.

`to_ascii` is correct, so parsing and routing are not affected; the problem is the human-readable form. Any application that renders `display_uri` (link previews, chat and email clients, admin UIs) can be made to display a hostname whose characters are visually reordered, so a hostile domain can be made to read like a trusted one.

Reproduction (unmodified main, pure backend, 2026-10-20)

    Addressable::URI.parse("http://xn--abcmoc-dm0c.com/").display_uri.host
    => "abc‮moc.com"   # code points: U+0061 U+0062 U+0063 U+202E U+006D U+006F U+0063 U+002E U+0063 U+006F U+006D

`xn--abcmoc-dm0c` is the ACE form `to_ascii` itself produces for `"abc‮moc"`, so the label is registrable and round-trips.

Suggested fix

In the pure backend's `to_unicode`, after decoding a label, reject it (return the ACE label unchanged) if the decoded form contains a code point in the nameprep prohibited ranges, at minimum the bidi controls U+200E, U+200F, U+202A-U+202E, U+2066-U+2069 and the other C.8/C.9 format characters. That matches what libidn does, so behaviour becomes consistent between the two backends. I did not write a patch because the exact set of rejected ranges is a design choice for the project; I can prepare one with a regression spec if that helps.

Found with the Quality Playbook (an AI code-review and test-generation skill I maintain); I reproduced it on the pure backend myself. The regression spec I used is below.
