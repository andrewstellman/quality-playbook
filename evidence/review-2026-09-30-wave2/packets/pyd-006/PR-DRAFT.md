**Title:** Reject non-finite values in float `multiple_of` validation

## Change Summary

```python
ta = TypeAdapter(Annotated[float, Field(multiple_of=0.5)])
ta.validate_python(float('inf'))  # also -inf, nan, and validate_json('Infinity')
#> inf    expected a `multiple_of` ValidationError
```

In `pydantic-core/src/validators/float.rs`, the remainder `diff` is NaN for non-finite input, and `NaN > tolerance` is false, so the value is accepted. The Python fallback (`multiple_of_validator` in `pydantic/_internal/_validators.py`, used e.g. after an `AfterValidator`) already rejects `inf`. The fix rejects non-finite values explicitly; the existing tolerance is unchanged.

JSON Schema Validation spec, `multipleOf` keyword (numeric validation keywords): "A numeric instance is valid only if division by this keyword's value results in an integer."

## Related issue number

None.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
