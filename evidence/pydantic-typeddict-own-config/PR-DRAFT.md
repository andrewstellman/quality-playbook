**Title:** Use the `TypedDict`'s own config when serializing

## Change Summary

```python
@with_config(ConfigDict(ser_json_bytes='base64'))
class TD(TypedDict):
    b: bytes

TypeAdapter(TD).dump_json({'b': b'hi'})
#> b'{"b":"hi"}'    expected b'{"b":"aGk="}'
```

`TypedDictSerializer::build` (`pydantic-core/src/serializers/type_serializers/typed_dict.rs`) builds the field serializers with the parent config and never reads the schema's own `config`, although the typed dict validator does. It now uses the schema's config when present and falls back to the parent config otherwise.

Behaviour change: a `TypedDict` with any config of its own no longer inherits the parent's `ser_json_*` settings.

The configuration docs (`docs/concepts/config.md`, "Configuration propagation") say: "For stdlib types (dataclasses and typed dictionaries), configuration will be propagated, unless the type has its own configuration set".

## Related issue number

None.

## Checklist

* [x] The pull request title is a good summary of the changes - it will be used in the changelog
* [x] Unit tests for the changes exist
* [ ] Tests pass on CI
* [x] Documentation reflects the changes where applicable
* [ ] My PR is ready to review, **please add a comment including the phrase "please review" to assign reviewers**

<<ANDREW: understanding statement>>

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
