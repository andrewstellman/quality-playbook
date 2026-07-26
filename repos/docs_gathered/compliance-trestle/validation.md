# Validation Subsystem

Trestle provides a multi-layer validation framework that checks both OSCAL schema correctness and higher-level semantic consistency of models in the workspace.

## Architecture

```
trestle/core/
  validator.py              # Abstract Validator base class
  validator_factory.py      # ValidatorFactory singleton
  all_validator.py          # Composite: runs all registered validators
  catalog_validator.py      # Validates catalog-specific constraints
  duplicates_validator.py   # Checks for duplicate UUIDs/IDs
  links_validator.py        # Validates internal link references
  refs_validator.py         # Validates cross-model references
  rule_parameters_validator.py  # Validates rule parameter consistency
trestle/common/
  load_validate.py          # Convenience: load a model and validate in one call
```

## Validator Base Class

`Validator` in `trestle/core/validator.py` is an abstract base class:

```python
class Validator(ABC):
    def error_msg(self) -> Optional[str]: ...  # Descriptive name for this validator
    @abstractmethod
    def model_is_valid(
        self,
        model: TopLevelOscalModel,
        quiet: bool,
        trestle_root: Optional[pathlib.Path] = None
    ) -> bool: ...
    def validate(self, args: argparse.Namespace) -> int: ...
```

The `validate` method on the base class handles CLI-level dispatch: it determines whether to validate models by type (`--type`), by name (`--name`), all models (`--all`), or a specific file (`--file`), loading each model via `ModelUtils.load_distributed` and calling `model_is_valid`. It returns a `CmdReturnCodes` integer.

## ValidatorFactory

`validator_factory` is a module-level singleton of `ValidatorFactory`. The `ValidateCmd` and the `load_validate.py` helpers call `validator_factory.get(args)` to obtain a validator configured for the requested mode:

```python
validator_factory.get(args: argparse.Namespace) -> Validator
```

The `args.mode` value selects which validator(s) to run. The special mode `VAL_MODE_ALL` (constant defined in `trestle/common/const.py`) returns the `AllValidator`.

## AllValidator

`AllValidator` in `trestle/core/all_validator.py` is a composite that runs every registered concrete validator in sequence. If any validator returns `False` from `model_is_valid`, the overall result is invalid. This is the default mode used by `trestle validate` and by `load_validate_model_path`.

## Concrete Validators

| Class | File | What it checks |
|---|---|---|
| `CatalogValidator` | `catalog_validator.py` | Catalog-specific structural rules |
| `DuplicatesValidator` | `duplicates_validator.py` | No duplicate UUIDs or IDs within a model |
| `LinksValidator` | `links_validator.py` | Href links within the model resolve to existing anchors |
| `RefsValidator` | `refs_validator.py` | Cross-model `$ref` and UUID references resolve correctly |
| `RuleParametersValidator` | `rule_parameters_validator.py` | Rule parameter declarations are consistent |

Each validator is a concrete subclass of `Validator`. The `error_msg()` method returns a human-readable description used in log output (e.g., `INVALID: Model X did not pass the <validator description>`).

## Load-and-Validate Helpers

`trestle/common/load_validate.py` provides two convenience functions used throughout the codebase:

```python
def load_validate_model_path(
    trestle_root: Path, model_path: Path
) -> TopLevelOscalModel

def load_validate_model_name(
    trestle_root: Path,
    model_name: str,
    model_class: TG,
    file_content_type: Optional[FileContentType] = None
) -> Tuple[TG, Path]
```

`load_validate_model_path` calls `ModelUtils.load_distributed` to assemble a potentially split model, then runs `AllValidator` in quiet mode. If the model fails validation, a warning is logged but the model is returned anyway (the caller decides how to handle invalidity). `load_validate_model_name` resolves the path from the name and class using `ModelUtils.get_model_path_for_name_and_class` before calling `load_validate_model_path`.

## Pydantic Schema Validation

At the object-model level, Pydantic enforces schema correctness automatically. The `OscalBaseModel` configuration `extra = Extra.forbid` means any field not declared in the schema raises a `ValidationError` at parse time. `validate_assignment = True` means reassigning a field to an invalid value also raises a `ValidationError`. The `TrestleBaseModel.parse_obj` override catches `ValidationError` on the `oscal-version` field specifically and raises a `TrestleError` with a meaningful message instead.

## validate CLI Command

`trestle validate` invokes the validation framework from the command line:

```
trestle validate --type <model-type>            # validate all models of a type
trestle validate --type <model-type> --name <n> # validate a specific named model
trestle validate --all                          # validate all models in workspace
trestle validate --file <path>                  # validate a specific file
trestle validate --quiet                        # suppress output on success
```

The return code is `CmdReturnCodes.SUCCESS` (0) on success or `CmdReturnCodes.OSCAL_VALIDATION_ERROR` (4) on failure.
