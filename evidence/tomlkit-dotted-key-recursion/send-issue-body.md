A 100-part dotted key, which is at the nesting limit added in #510 and parses on its own (`test_parse_accepts_nesting_at_the_depth_limit`), can't be parsed once a second key under the same first part follows it. Inside a table, `parse()` raises a raw `RecursionError` from `copy.deepcopy` in the out-of-order table validation, not a `ParseError`. At the document root the same recursion is caught and reported as `ParseError: maximum recursion depth exceeded`. It starts at about 92 parts, and `tomllib` parses all of these documents.

```python
import tomlkit

key = ".".join(["a"] * 100)
tomlkit.parse(f"{key} = 1\n")                # parses
tomlkit.parse(f"[t]\n{key} = 1\na.b = 2\n")  # RecursionError: maximum recursion depth exceeded
tomlkit.parse(f"{key} = 1\na.b = 2\n")       # ParseError: maximum recursion depth exceeded at line 2 col 0
```

Expected: the second and third documents parse, since no key has more than 100 parts. If tomlkit can't support that depth here, it should at least raise `ParseError`, as #510 intended, rather than a `RecursionError` that callers catching `TOMLKitError` won't handle.

Reproduced on master at 7bf7284 with Python 3.13.18 and the default recursion limit.

Found with the Quality Playbook, an AI code-review tool I maintain. This report was written with AI assistance and reviewed by me.
