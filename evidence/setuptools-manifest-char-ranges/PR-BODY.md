## Summary of changes

With `graft keys` and `exclude keys/[a-z].pem` in MANIFEST.in, the sdist still contains `keys/b.pem`. `translate_pattern` passes the inside of a `[...]` class through `re.escape`, so `-` is literal and `[a-c]` matches only `a`, `-` and `c`, although the docs say ranges such as `[a-z]` are supported and `include` honours them. The fix leaves `-` unescaped inside the class, and two new `translate_specs` entries cover `[a-c]` and `[!a-c]`.

Found with the Quality Playbook, an AI code-review tool I maintain. The fix and test were written with AI assistance and reviewed by me.

### Pull Request Checklist
- [x] Changes have tests
- [x] News fragment added in `newsfragments/`.
