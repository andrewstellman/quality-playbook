**Title:** Do not add a plus sign to a negative zero float result

## Summary

Arithmetic on a float that was written with an explicit sign renders `+-0.0` when the result is negative zero. tomlkit cannot parse its own output.

```python
import tomlkit

doc = tomlkit.parse("x = +0.0")
doc["x"] *= -1
print(doc.as_string())          # actual: x = +-0.0    expected: x = -0.0
tomlkit.parse(doc.as_string())  # InvalidNumberError: Invalid number at line 1 col 9
```

Cause: `Float._new` (`tomlkit/items.py:879` on master 0518af2) adds `+` when `self._sign and result >= 0`. `-0.0 >= 0` is `True`, and `str(-0.0)` is already `"-0.0"`. A signed integer reaches the same line through true division: `n = +0` followed by `doc["n"] /= -1` also gives `+-0.0`.

Fix: add the `+` only when `str(result)` does not already start with `-`.

The trigger is narrow. The source value must carry an explicit `+` or `-`, and the result must be negative zero. This is the same line that #345 changed for #341; negative zero is an input that change did not cover.

Results other than negative zero render as before. I ran `+1.0 * nan` (`nan`), `+1.0 * inf` (`+inf`), `+1.0 * -inf` (`-inf`), `-1.5 * -1` (`+1.5`) and `+0.0 + 0.0` (`+0.0`) before and after the change. `tests` gives 1069 passed (1068 before, plus the new test).

TOML 1.1.0, section "Float" (https://toml.io/en/v1.1.0): "Float values `-0.0` and `+0.0` are valid and should map according to IEEE 754." The grammar allows one optional sign: `dec-int = [ minus / plus ] unsigned-dec-int` (section "ABNF Grammar", `toml.abnf`).

## Agent Drafting Metadata

- Agent: Quality Playbook (https://github.com/andrewstellman/quality-playbook), run with Claude Code
- Model: Claude Fable 5.1 (found); Claude Opus 5.5 (confirmed, fixed and reviewed); Claude Sonnet 5.5 (ran the audit phases)
- Notes: Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change. The test, the fix and this text were drafted by the agent and reviewed by the author.
