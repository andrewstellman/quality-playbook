**Title:** Reject non-finite values in float `multiple_of` validation

## Change Summary

```python
ta = TypeAdapter(Annotated[float, Field(multiple_of=0.5)])
ta.validate_python(float('inf'))  # also -inf, nan, and validate_json('Infinity')
#> inf    expected a `multiple_of` ValidationError
```

In `pydantic-core/src/validators/float.rs`, the remainder `diff` is NaN for non-finite input, and `NaN > tolerance` is false, so the value is accepted. The Python fallback (`multiple_of_validator` in `pydantic/_internal/_validators.py`, used e.g. after an `AfterValidator`) already rejects `inf`. The fix rejects non-finite values explicitly; the existing tolerance is unchanged.

`inf`, `-inf` and `nan` on a field with `multiple_of` are now rejected even when `allow_inf_nan=True`.

JSON Schema Validation spec, `multipleOf` keyword (numeric validation keywords): "A numeric instance is valid only if division by this keyword's value results in an integer."

## Related issue number

Follow-up to closed PR #13473, which noted that rejecting non-finite values for `multiple_of` "probably belongs in pydantic-core".

## Checklist

* [x] The pull request title is a good summary of the changes - it will be used in the changelog
* [x] Unit tests for the changes exist
* [ ] Tests pass on CI
* [ ] Documentation reflects the changes where applicable
* [ ] My PR is ready to review, **please add a comment including the phrase "please review" to assign reviewers**

<<ANDREW: understanding statement>>

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
