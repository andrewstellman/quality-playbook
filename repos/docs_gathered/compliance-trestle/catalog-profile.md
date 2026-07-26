# Catalog and Profile Subsystem

The catalog and profile subsystem handles OSCAL Catalog and Profile documents — the two schema types that define control frameworks and customizations. It provides both a programmatic API and CLI authoring commands for round-tripping between OSCAL and human-editable markdown.

## Package Layout

```
trestle/core/catalog/
  catalog_api.py        # Main entry point: CatalogAPI
  catalog_interface.py  # In-memory control access and manipulation
  catalog_reader.py     # Reads markdown into catalog structures
  catalog_writer.py     # Writes catalog structures to markdown
  catalog_merger.py     # Merges markdown-derived changes into the in-memory catalog
trestle/core/
  profile_resolver.py   # Resolves a profile chain into a resolved catalog
  control_interface.py  # Shared data structures and utilities for control content
  control_context.py    # ControlContext: authoring mode and path configuration
  control_reader.py     # Lower-level markdown parsing for individual controls
  control_writer.py     # Lower-level markdown rendering for individual controls
```

## CatalogAPI

`CatalogAPI` (in `catalog_api.py`) is the primary programmatic interface for interacting with a catalog in memory. It composes `CatalogInterface`, `CatalogWriter`, `CatalogReader`, and `CatalogMerger` internally:

```python
class CatalogAPI:
    def __init__(self, catalog: Optional[cat.Catalog], context: Optional[ControlContext] = None)
    def update_context(self, context: ControlContext) -> None
    def write_catalog_as_markdown(self, label_as_key: bool = False) -> None
    def read_additional_content_from_md(self, label_as_key: bool = False)
    def write_catalog_as_profile_markdown(self, ...)
    def write_catalog_as_component_markdown(self, ...)
    def assemble_catalog(self, ...) -> cat.Catalog
```

When no catalog is supplied, `CatalogAPI` generates a minimal sample catalog via `generate_sample_model`. The `ControlContext` object passed to the constructor or `update_context` carries the authoring *purpose* (catalog, profile, component, or SSP) and the filesystem paths where markdown files should be read from or written to.

## CatalogInterface

`CatalogInterface` is the in-memory access layer. It organizes controls from all groups and nested groups into a flat dictionary for efficient lookup, and provides methods such as:

- `get_all_controls_from_dict()` — iterate all controls regardless of nesting depth.
- `get_statement_part_id_map(label_as_key)` — build a mapping from part IDs to display labels.
- `update_catalog_controls()` — push modified controls back into the catalog's group tree.
- `get_catalog()` — retrieve the current `cat.Catalog` object.

## ProfileResolver

`ProfileResolver` in `trestle/core/profile_resolver.py` takes a profile and produces a *resolved catalog* by following the profile's `import` chain, applying all `modify`, `alter`, and `set-parameter` operations in order.

The key public method:

```python
@staticmethod
def get_resolved_profile_catalog_and_inherited_props(
    trestle_root: pathlib.Path,
    profile_path: str,
    block_adds: bool = False,
    block_params: bool = False,
    params_format: Optional[str] = None,
    param_rep: ParameterRep = ParameterRep.LEAVE_MOUSTACHE,
    show_value_warnings: bool = False,
    value_assigned_prefix: Optional[str] = None,
    value_not_assigned_prefix: Optional[str] = None,
) -> Tuple[cat.Catalog, Optional[Dict[str, Any]]]
```

Resolution proceeds by constructing an `Import` filter object for each level of the profile chain and passing the accumulated result through the pipeline. Inherited properties — props added by upstream profiles — are tracked in a temporary `Part` named by `const.TRESTLE_INHERITED_PROPS_TRACKER` and extracted before the resolved catalog is returned.

A convenience wrapper `get_resolved_profile_catalog` exposes the same logic without returning inherited props.

## ControlContext and ContextPurpose

`ControlContext` (in `trestle/core/control_context.py`) is a dataclass that carries configuration for a single authoring operation. The `ContextPurpose` enum selects the authoring mode:

| Value | Meaning |
|---|---|
| `CATALOG` | Authoring a catalog directly |
| `PROFILE` | Authoring profile alterations |
| `COMPONENT` | Authoring component definition control implementations |
| `SSP` | Authoring an SSP's control implementations |

The context also carries the markdown root directory, YAML header path, section configuration, profile object, component definition references, and flags like `force_overwrite`.

## ParameterRep Enum

`ParameterRep` in `trestle/core/control_interface.py` controls how OSCAL parameters are rendered when written to markdown:

| Value | Behavior |
|---|---|
| `LEAVE_MOUSTACHE` | Leave `{{ param-id }}` placeholders unchanged |
| `VALUE_OR_STRING_NONE` | Substitute the assigned value, or the string `"None"` |
| `LABEL_OR_CHOICES` | Substitute label or enumerated choices |
| `VALUE_OR_LABEL_OR_CHOICES` | Prefer value, fall back to label or choices |
| `VALUE_OR_EMPTY_STRING` | Substitute value, or empty string |
| `ASSIGNMENT_FORM` | Render as an assignment expression |
| `LABEL_FORM` | Render the parameter label |

## Author CLI Commands

The `author catalog-generate` command calls `CatalogAPI.write_catalog_as_markdown()` to produce a directory of markdown files, one per control. The `author catalog-assemble` command calls `CatalogAPI.assemble_catalog()`, which reads those markdown files via `CatalogReader` and merges the result via `CatalogMerger` into an updated OSCAL catalog.

The same pattern applies to profiles: `author profile-generate` first runs `ProfileResolver` to compute the resolved control set, then writes it as markdown. `author profile-assemble` reads the edited markdown and generates profile alteration statements. `author profile-resolve` runs the resolver and writes the result directly as an OSCAL catalog.

`author profile-inherit` generates *inheritance markdown* describing which controls from a leveraged SSP can be inherited. This calls into the CRM subsystem via `SSPInheritanceAPI` (see the `crm.md` document).
