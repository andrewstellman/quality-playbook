```python
from marshmallow import validate
v = validate.URL(relative=True)
v("/redirect?to=http://example.com")  # actual: ValidationError "Not a valid URL."; expected: returns the value
v("/a#http://x.y")                    # same
```

The scheme check split on the first "://" even when the text before it contained "/", "?" or "#". Here that text was `/redirect?to=http`, which is not in `schemes`.

The `relative` parameter is documented only as "Whether to allow relative URLs." (`src/marshmallow/validate.py:91`). That does not mention "://". I am relying on the URL regex, which already accepts these values once the scheme check is skipped.

Behaviour change: with `relative=True`, values with "://" after the first "/", "?" or "#" were rejected and are now accepted, and `schemes` is not consulted for them. `//host/x` was already accepted before this change. With the default `relative=False`, the two examples above, `//host/x`, `/p?u=ws://q`, `/a/b://c` and `ws://test.test` are rejected both before and after. `ws://test.test` is also still rejected with `relative=True`.

Adds two cases to `test_url_relative_valid`. Full suite passes (1192 tests).

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
