# Control Requirements Management (CRM)

The CRM subsystem handles multi-SSP inheritance — the OSCAL pattern where a system's security plan can *leverage* controls inherited from another system (the "provider") rather than implementing them independently. This reflects real-world shared responsibility models, such as cloud infrastructure controls inherited by a cloud-hosted application.

## Package Layout

```
trestle/core/crm/
  ssp_inheritance_api.py    # High-level API for reading and writing inheritance markdown
  bycomp_interface.py       # By-component view of control implementations
  export_reader.py          # Reads exported control statements from a leveraged SSP
  export_writer.py          # Writes inheritance markdown from a leveraged SSP
  leveraged_statements.py   # Data structures for leveraged and satisfied statements
```

## SSPInheritanceAPI

`SSPInheritanceAPI` is the primary entry point for the CRM subsystem:

```python
class SSPInheritanceAPI:
    def __init__(
        self,
        inheritance_md_path: pathlib.Path,
        trestle_root: pathlib.Path
    ) -> None: ...

    def write_inheritance_as_markdown(
        self,
        leveraged_ssp_reference: str,
        catalog_api: Optional[CatalogAPI] = None
    ) -> None: ...

    def read_inheritance_for_ssp(
        self,
        leveraged_ssp_reference: str,
        ssp: ossp.SystemSecurityPlan
    ) -> ossp.SystemSecurityPlan: ...
```

`write_inheritance_as_markdown` fetches the leveraged SSP (via `FetcherFactory`), iterates its `by-component` control implementations, and writes markdown files describing which controls can be inherited. When a `CatalogAPI` is provided, the output is filtered to only those controls present in the provided catalog. Each markdown file represents a single control and carries YAML frontmatter describing the leveraged components and their `export` statements.

`read_inheritance_for_ssp` reads those markdown files back and populates the inheriting SSP's `by-component` statements with `inherited` and `satisfied` entries referencing the leveraged system's component UUIDs.

## ExportWriter and ExportReader

`ExportWriter` iterates the leveraged SSP's `implemented-requirements` and, for each `by-component` entry that carries an `export` block, writes a markdown representation of the exportable statements. The export block contains:

- `provided` statements: control implementations that the leveraged system provides and that inheriting systems may reference.
- `responsibilities`: obligations that the inheriting system must satisfy.

`ExportReader` parses the inheritance markdown files back into OSCAL `by-component` entries, constructing `inherited` and `satisfied` statement objects with correct UUIDs and prose.

## ByCompInterface

`ByCompInterface` in `bycomp_interface.py` provides a view of a system security plan organized by component rather than by control. It maps component UUIDs to their control implementations, enabling efficient lookup when assembling inheritance relationships. This is used by `ExportWriter` to navigate the leveraged SSP's structure.

## LeveragedStatements

`leveraged_statements.py` defines data structures for the two statement types used in inheritance:

- `LeveragedStatements`: captures what the leveraged system provides, corresponding to OSCAL `implemented-requirement.by-component.export.provided`.
- `SatisfiedStatements`: captures what the inheriting system has done to meet a responsibility, corresponding to OSCAL `implemented-requirement.by-component.satisfied`.

These structures carry the statement UUID, prose, and component metadata needed to round-trip through the markdown representation.

## Integration with SSP Commands

The `author ssp-generate` command accepts a `--leveraged-ssp` flag. When provided, it calls `SSPInheritanceAPI.write_inheritance_as_markdown` to generate inheritance markdown alongside the control implementation markdown. During assembly (`author ssp-assemble`), `SSPInheritanceAPI.read_inheritance_for_ssp` reads that markdown and incorporates the inherited/satisfied statements into the assembled SSP.

The `author profile-inherit` command also calls into this subsystem: it produces the inheritance markdown files from a leveraged SSP, giving the SSP author a view of which controls are available to inherit before they write the SSP.

## OSCAL Inheritance Model

In OSCAL, inheritance is expressed through the `by-component.export` structure:

```
system-security-plan
  control-implementation
    implemented-requirement (per control)
      by-component (per component)
        export
          provided []    <- what this system offers to inheritors
          responsibilities []  <- what inheritors must do
        inherited []     <- referenced from a leveraged system's provided
        satisfied []     <- how this system meets a leveraged responsibility
```

Trestle's CRM subsystem automates the population of the `inherited` and `satisfied` arrays in the inheriting SSP from the `provided` and `responsibilities` arrays in the leveraged SSP, mediated by human-editable markdown.
