# Architecture and Design Philosophy

compliance-trestle (package name `trestle`) is a Python library and command-line tool for managing, authoring, validating, and transforming compliance artifacts using the NIST OSCAL (Open Security Controls Assessment Language) standard. It is designed to integrate naturally into CI/CD pipelines and Git-based workflows, enabling compliance as code.

## Core Design Goals

Trestle bridges two worlds: the governance domain (compliance frameworks, control catalogs, security plans) and the DevOps domain (developers, version control, automated pipelines). Its central premise is that compliance artifacts should be managed with the same rigor and tooling as software source code.

Three capabilities are built into the library at equal priority:

1. **OSCAL model management**: reading, writing, splitting, merging, and validating JSON/YAML OSCAL documents while enforcing schema correctness.
2. **Format transformation**: converting third-party compliance data formats (OSCO, XCCDF, Tanium, spreadsheets) into OSCAL representations.
3. **Authoring and governance**: generating editable markdown from OSCAL content, validating that markdown conforms to templates, and assembling edited markdown back into OSCAL.

## Package Layout

```
trestle/
  cli.py                    # Entry point: the Trestle top-level command
  oscal/                    # Auto-generated Pydantic models for every OSCAL schema
  common/                   # Shared utilities: constants, error types, file utils, model utils
  core/                     # Business logic: commands, validators, profile resolver, catalog API, CRM, markdown
    commands/               # CLI subcommands (split, merge, validate, import, author, task, ...)
      author/               # Author subcommands (catalog, profile, ssp, component, jinja, docs, folders)
    catalog/                # Catalog API: interface, reader, writer, merger
    markdown/               # Markdown parsing, validation, and writing
    models/                 # Internal action/element/plan primitives
    remote/                 # Cache and fetcher for remote OSCAL references
    crm/                    # Control Requirements Management (SSP inheritance, leveraged controls)
  tasks/                    # Pluggable task framework for format conversions
  transforms/               # Transformer framework and concrete transformer implementations
```

## Layered Architecture

The library is organized in three conceptual layers:

**Layer 1 — OSCAL object model** (`trestle/oscal/`): Pydantic data classes for every OSCAL schema element. All OSCAL types are strict: extra fields are forbidden, assignment is validated at runtime, and `json_encoders` handle OSCAL-specific types such as UTC-normalized datetimes. This layer is auto-generated from NIST metaschema definitions.

**Layer 2 — Common utilities** (`trestle/common/`): Shared code that the upper layers consume. Includes the canonical error hierarchy, file system utilities, model-level utilities for loading and resolving models, list and string helpers, and the `OscalBaseModel` / `TrestleBaseModel` base classes that all OSCAL models inherit.

**Layer 3 — Core operations** (`trestle/core/`): The library's public surface. Commands implement CLI verbs; the catalog and CRM APIs expose programmatic interfaces; the profile resolver resolves inheritance chains; the markdown subsystem converts between structured OSCAL and human-editable text; the remote cache fetches referenced resources; the transformer and task frameworks handle third-party format ingestion.

## Workspace Convention

Every trestle project is anchored to a *workspace root* directory containing a `.trestle/` metadata folder and type-named model subdirectories (`catalogs/`, `profiles/`, `system-security-plans/`, etc.). All commands accept a `--trestle-root` flag (default: current working directory). The workspace discipline enforces reproducibility: any OSCAL document in the workspace can be split into sub-files for easier editing and later reassembled without loss.

## Opinionated Defaults

Trestle makes deliberate choices to reduce accidental deviation:

- Only JSON and YAML are natively supported as OSCAL file formats (not XML).
- Model schemas are enforced strictly via Pydantic `Extra.forbid`.
- Datetime fields are always serialized as UTC ISO 8601 with millisecond precision.
- The `dist/` directory separates published artifacts from the editable workspace.
- Plugin discovery follows the `trestle_*` naming convention, keeping third-party extensions clearly identifiable.

## Integration Pattern

Trestle is typically invoked from a CI/CD pipeline in a sequence: `trestle init` to set up the workspace, `trestle import` to bring in upstream OSCAL documents, `trestle author <subcommand> generate` to produce editable markdown, human editing via pull request, `trestle author <subcommand> assemble` to convert back to OSCAL, and `trestle validate` to verify correctness. The `trestle task` command integrates arbitrary third-party data sources at any step.
