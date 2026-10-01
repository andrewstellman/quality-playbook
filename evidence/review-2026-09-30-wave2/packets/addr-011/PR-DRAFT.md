**Title:** Fix route_from when only the base URI has a query

```ruby
uri = Addressable::URI.parse("http://example.com/file.txt")
uri.route_from("http://example.com/file.txt?x=1").to_s
# actual:   ""          (joins back to "http://example.com/file.txt?x=1")
# expected: "file.txt"  (joins back to "http://example.com/file.txt")
```

When the paths are equal, `route_from` (lib/addressable/uri.rb) drops the path and only clears the query if both queries match, so a target without a query routed from a base with one gets an empty reference, which resolves back to the base. It now returns the target's last path segment, or `./` for a directory, so `base.join(uri.route_from(base)) == uri` holds as described in #126. Two specs added to the existing `route_from` examples.

RFC 3986 §5.2.2 (Transform References): `if (R.path == "") then T.path = Base.path; if defined(R.query) then T.query = R.query; else T.query = Base.query;`

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
