# OSCAL Object Model

The `trestle/oscal/` package contains the Python object model for all NIST OSCAL schema types. These classes are the canonical in-memory representation used throughout the library.

## Package Contents

```
trestle/oscal/
  __init__.py              # Exports OSCAL_VERSION constant
  common.py                # Shared OSCAL types used across schemas
  catalog.py               # Catalog model
  profile.py               # Profile model
  ssp.py                   # System Security Plan model
  component.py             # Component Definition model
  assessment_plan.py       # Assessment Plan model
  assessment_results.py    # Assessment Results model
  poam.py                  # Plan of Action and Milestones model
  mapping.py               # Mapping Collection model
```

The models correspond one-to-one with the eight top-level OSCAL schemas that NIST defines. Trestle 4.x targets OSCAL 1.2.1. The constants in `trestle/common/const.py` define canonical string names for each model type (e.g., `MODEL_TYPE_CATALOG = 'catalog'`), directory names (e.g., `MODEL_DIR_CATALOG = 'catalogs'`), and Python module names.

## Base Class Hierarchy

All OSCAL model classes inherit from `OscalBaseModel`, which itself inherits from `TrestleBaseModel`, which wraps Pydantic `BaseModel`:

```
pydantic.BaseModel
  └── TrestleBaseModel          (trestle/core/trestle_base_model.py)
        └── OscalBaseModel      (trestle/core/base_model.py)
              └── <all OSCAL classes>
```

`TrestleBaseModel` overrides `parse_obj` to surface meaningful errors when OSCAL version fields fail validation, and customizes `__str__`, `__eq__`, and `__hash__` to handle Pydantic v1 `__root__` wrapper models correctly.

`OscalBaseModel` configures the Pydantic model class for OSCAL:

- `json_loads = orjson.loads` — high-performance JSON parsing.
- `json_encoders = {datetime.datetime: robust_datetime_serialization}` — UTC-normalized ISO 8601 output.
- `allow_population_by_field_name = True` — allows both Python attribute names and OSCAL JSON aliases.
- `extra = Extra.forbid` — strict schema: no unknown fields are accepted.
- `validate_assignment = True` — field validation runs on every assignment, not just at construction.

## Common Types

`trestle/oscal/common.py` contains the OSCAL-defined shared types that other schemas import: `Property`, `Part`, `Link`, `Metadata`, `BackMatter`, `ImplementationStatus`, and many others. These types are referenced directly from the top-level schema modules and from `trestle/common/common_types.py`, which defines the `TopLevelOscalModel` union type used throughout the library.

## Datetime Serialization

The `robust_datetime_serialization` function in `trestle/core/base_model.py` enforces that any `datetime` stored in an OSCAL document carries full timezone information and is output as UTC ISO 8601 to millisecond precision. A `TrestleError` is raised if a naive datetime (without timezone) is encountered.

## Model Generation

The OSCAL models are auto-generated from NIST metaschema definitions using `datamodel-code-generator`. The `pyproject.toml` `[tool.black]` and `[tool.isort]` sections set `line-length = 500` specifically for this generation step so that each `Field()` definition occupies a single line, enabling consistent text comparison in normalization tooling. The `trestle/oscal/` directory is excluded from the Ruff linter to avoid flagging generated code.

## Model Utilities

`trestle/common/model_utils.py` provides `ModelUtils`, a collection of class methods for working with the model layer:

- `load_distributed(model_path, trestle_root)` — loads a model that may be split across multiple files, reassembling it into a single in-memory object.
- `get_model_path_for_name_and_class(trestle_root, name, cls)` — resolves the file path for a named model of a given class.
- `model_type_to_model_dir(model_type)` — maps a model type string to the workspace directory name.
- `get_all_models(trestle_root)` — enumerates all models present in the workspace.

The `generators.py` module (`trestle/core/generators.py`) provides `generate_sample_model(cls)`, which uses Pydantic type introspection to construct a minimal valid instance of any OSCAL model class — useful for testing and for creating scaffolding in new workspaces.

## Union Type Resolution

OSCAL 1.2.x introduced Union types for certain elements (e.g., `Group1 | Group2`, `Parameter1 | Parameter2`) where the OSCAL schema allows variant structures. The `_get_model_type_from_union` helper in `model_utils.py` resolves the appropriate concrete type from a Union annotation, checking which variant carries a particular field name. Pydantic's smart validators handle deserialization automatically; this helper is used in non-deserialization contexts such as element-path traversal.
