Confirmer (addressable 2.9.0 = upstream main): CONFIRMED. {+v} with "%20abc" -> "%2520abc"; {#v} with "a%2Fb" -> "#a%252Fb"; lone % still -> %25 (correct).
RFC 6570 §3.2.1, cite/rfc6570-uri-template.txt:1080-1087: reserved and fragment expansions "allow the set of characters in the union of ( unreserved / reserved / pct-encoded ) to be passed through without pct-encoding ... Note that the percent character ("%") is only allowed as part of a pct-encoded triplet and only for reserved/fragment expansion".
Duplicates: none (#399 IRI chars, #135 @ in simple expansion). Open PRs #604-#622 do not touch encode_map; fixer verified all 17 still apply cleanly on top.
Fixer notes: rspec run with an empty bundler/setup stub; no rubocop config.
