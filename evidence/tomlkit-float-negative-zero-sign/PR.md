## Summary

Arithmetic on a float written with an explicit sign renders `+-0.0` when the result is negative zero, and tomlkit cannot parse that output.

```python
import tomlkit

doc = tomlkit.parse("x = -1.5")
doc["x"] *= 0
print(doc.as_string())          # actual: x = +-0.0    expected: x = -0.0
tomlkit.parse(doc.as_string())  # InvalidNumberError: Invalid number at line 1 col 9
```

`Float._new` (`tomlkit/items.py:879` on master) adds `+` when `self._sign and result >= 0`. `-0.0 >= 0` is `True`, and `str(-0.0)` is already `"-0.0"`. This is the line #345 changed for #341, and negative zero is the case that change left open. A signed integer reaches the same line through true division (`n = +0`, then `doc["n"] /= -1`).

The fix adds the `+` only when `str(result)` does not already start with `-`. Negative zero is the only value that is `>= 0` and prints with a leading `-`, so no other result renders differently.

## Agent Drafting Metadata

- Agent: Quality Playbook, run with Claude Code
- Model: Claude Fable 5.1, Claude Opus 5.5 and Claude Sonnet 5.5
- Notes: Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change. The agent also drafted the test, the fix and this text.
