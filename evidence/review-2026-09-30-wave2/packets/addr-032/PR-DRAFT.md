**Title:** Keep pct-encoded triplets in reserved and fragment expansion

```ruby
Addressable::Template.new("{+v}").expand(v: "%20a%2Fb").to_s
# actual:   "%2520a%252Fb"
# expected: "%20a%2Fb"     ({#v} likewise gives "#%2520a%252Fb")
```

`transform_capture` (lib/addressable/template.rb) builds the allowed set for `+` and `#` from `RESERVED + UNRESERVED`, which has no `%`, so `encode_component` encodes the `%` of every existing triplet. The allowed set is now a regexp that leaves `%XX` alone and still encodes a lone `%` (`{+half}` stays `50%25`). Two specs added next to the `{+half}`/`{#half}` ones.

RFC 6570 §3.2.1: "reserved ("+") and fragment ("#") expansions allow the set of characters in the union of ( unreserved / reserved / pct-encoded ) to be passed through without pct-encoding ... Note that the percent character ("%") is only allowed as part of a pct-encoded triplet and only for reserved/fragment expansion".

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
