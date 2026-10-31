This is a second case in the same function as the bidi-override report I filed on 20 Oct, and I suggest handling it in the same advisory and fix.

What
The pure IDNA backend's to_unicode punycode-decodes every "xn--" label and returns the result without the check RFC 3490 section 4.2 requires (steps 6 and 7: apply ToASCII to the decoded label and return the original label unless they match). display_uri shows that unchecked result. Two consequences:

1. An ACE label that decodes to plain ASCII is displayed as that ASCII. "xn--google-" decodes to "google", so
       Addressable::URI.parse("http://xn--google-.com/").display_uri.to_s
   returns "http://google.com/", while the URI actually names the host "xn--google-.com".

2. A label can decode to a full-stop lookalike. "xn--paypalcom-b854c" decodes to "paypal．com" (FULLWIDTH FULL STOP), so
       Addressable::URI.parse("http://xn--paypalcom-b854c.attacker.example/").display_uri.host
   returns "paypal．com.attacker.example". U+FF61 behaves the same way.

The native (libidn) backend returns all of these labels unchanged, so only the pure backend is affected. The pure backend is the default because the gemspec does not depend on idn-ruby.

Where
lib/addressable/idna/pure.rb, to_unicode (current main d298c9f, lines 88-108).

Impact
Display spoofing in applications that show display_uri output to users, the same class as the bidi report. The practical reach is limited: public registries do not accept A-labels that decode to pure ASCII, so case 1 mainly matters for hosts under a domain the attacker controls or in private namespaces. I am reporting it with the bidi case because the fix is in the same place and the round-trip check is what RFC 3490 prescribes. I note that the display_uri documentation asks applications to detect semantic attacks themselves (RFC 3986 section 7.6), so you may weigh both cases as hardening rather than a vulnerability.

Affected versions
2.9.0 and current main (d298c9f), pure IDNA backend.

Suggested fix
Apply the round-trip check in pure to_unicode (patch below):

    decoded = punycode_decode(part[/^#{ACE_PREFIX}(.+)/, 1])
    if to_ascii(decoded).downcase == part.downcase
      decoded
    else
      part
    end

The patch adds two specs to the shared "converting from ASCII to unicode" examples. They fail on the pure backend without the fix and pass with it; the native backend passes them unchanged. Full suite: 1435 examples, 0 failures (pure) and 1470 examples, 0 failures (native, idn-ruby with libidn 1.42), on MRI 3.3.6, and 1435 examples, 0 failures on MRI 3.1.6.

The round-trip check does not catch the bidi case, because pure to_ascii re-encodes a label containing U+202E identically, so the prohibited-output check from the bidi report is still needed. It also does not catch U+3002 (IDEOGRAPHIC FULL STOP), because pure to_ascii does not treat U+3002 as a label separator; that is a separate gap in the pure backend's label splitting.

Found with the Quality Playbook (github.com/andrewstellman/quality-playbook), an AI code-review tool I maintain. Claude reproduced it and wrote the patch and test, and I reviewed them.

```diff
From 2541f90d53f1c36d7b3ca02af3880b48fe31bd75 Mon Sep 17 00:00:00 2001
From: Andrew Stellman <astellman@stellman-greene.com>
Date: Wed, 21 Oct 2026 08:42:06 -0400
Subject: [PATCH] Verify ACE labels round-trip in pure IDNA to_unicode

RFC 3490 section 4.2 requires ToUnicode to re-apply ToASCII to the
decoded label and to return the original label unless the two match.
The pure backend skipped this check, so an ACE label such as
'xn--google-' (which decodes to plain 'google') or one that decodes to
a fullwidth full stop was shown in its decoded form by display_uri.
The native (libidn) backend already returns these labels unchanged.

---
 lib/addressable/idna/pure.rb  | 13 +++++++++++--
 spec/addressable/idna_spec.rb | 11 +++++++++++
 2 files changed, 22 insertions(+), 2 deletions(-)

diff --git a/lib/addressable/idna/pure.rb b/lib/addressable/idna/pure.rb
index 6572e64..b3a24ce 100644
--- a/lib/addressable/idna/pure.rb
+++ b/lib/addressable/idna/pure.rb
@@ -91,8 +91,17 @@ module Addressable
       parts.map! do |part|
         if part =~ /^#{ACE_PREFIX}(.+)/
           begin
-            punycode_decode(part[/^#{ACE_PREFIX}(.+)/, 1])
-          rescue Addressable::IDNA::PunycodeBadInput
+            decoded = punycode_decode(part[/^#{ACE_PREFIX}(.+)/, 1])
+            # RFC 3490 section 4.2, steps 6 and 7: re-encode the decoded
+            # label and return the original label unless the result matches
+            # it. This rejects ACE labels that do not come from ToASCII, such
+            # as 'xn--google-', which would otherwise display as 'google'.
+            if to_ascii(decoded).downcase == part.downcase
+              decoded
+            else
+              part
+            end
+          rescue Addressable::IDNA::PunycodeBadInput, ArgumentError
             # toUnicode is explicitly defined as never-fails by the spec
             part
           end
diff --git a/spec/addressable/idna_spec.rb b/spec/addressable/idna_spec.rb
index 428c9ec..96438b0 100644
--- a/spec/addressable/idna_spec.rb
+++ b/spec/addressable/idna_spec.rb
@@ -165,6 +165,17 @@ shared_examples_for "converting from ASCII to unicode" do
       "xn--zckp1cyg1.sblo.jp")
   end
 
+  it "should return the identity conversion for an ACE label that decodes to ASCII" do
+    expect(Addressable::IDNA.to_unicode("xn--google-.com")).to eq(
+      "xn--google-.com")
+  end
+
+  it "should return the identity conversion when ToASCII does not round-trip" do
+    # Decodes to "paypal\uFF0Ecom", which ToASCII maps to "paypal.com".
+    expect(Addressable::IDNA.to_unicode("xn--paypalcom-b854c.example")).to eq(
+      "xn--paypalcom-b854c.example")
+  end
+
   it "should return the identity conversion when the ACE prefix has no suffix" do
     expect(Addressable::IDNA.to_unicode("xn--...-")).to eq("xn--...-")
   end
-- 
2.43.0
```
