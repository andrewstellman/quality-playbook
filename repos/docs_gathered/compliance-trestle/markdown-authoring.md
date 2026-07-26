# Markdown Authoring and Governance

Trestle's markdown subsystem enables compliance content to be authored, reviewed, and governed in plain text. It provides both the conversion layer between OSCAL and markdown and a governance framework for validating that markdown files conform to defined templates.

## Package Layout

```
trestle/core/markdown/
  markdown_api.py           # Public API for markdown processing
  markdown_processor.py     # Parses markdown text into a node tree
  base_markdown_node.py     # Base node class for the markdown AST
  control_markdown_node.py  # Node variant for OSCAL control sections
  docs_markdown_node.py     # Node variant for general governed documents
  markdown_validator.py     # Validates a markdown instance against a template
  markdown_const.py         # Constants for markdown parsing (header patterns, etc.)
  md_writer.py              # Low-level markdown text writer
trestle/core/
  control_writer.py         # Writes control content as markdown sections
  control_reader.py         # Reads control content from markdown sections
  docs_control_writer.py    # Writes controls for documentation output
  ssp_io.py                 # SSP-specific markdown writer
  draw_io.py                # Reads metadata from drawio files
```

## Markdown Processing

`markdown_processor.py` parses a markdown file's text into a tree of `MarkdownNode` objects. Each node corresponds to a heading-delimited section and carries:

- The section heading text and level (`#`, `##`, etc.).
- The prose content of the section.
- A YAML header (if the file begins with a `---` frontmatter block) parsed by `python-frontmatter`.
- Child nodes for nested subsections.

Two node specializations are used:

- `DocsMarkdownNode` — for general governed documents; used by the `author docs` and `author folders` commands.
- `ControlMarkdownNode` — for control-structured markdown produced by the catalog/profile/SSP authoring workflow; understands OSCAL section naming conventions.

## MarkdownValidator

`MarkdownValidator` in `trestle/core/markdown/markdown_validator.py` compares a markdown instance against a template to enforce governance rules. Construction takes:

```python
MarkdownValidator(
    tmp_path: pathlib.Path,
    template_header: Dict,
    template_tree: DocsMarkdownNode,
    validate_yaml_header: bool,
    validate_md_body: bool,
    governed_section: Optional[str] = None,
)
```

Validation checks that the instance contains all required sections present in the template tree and that YAML header keys required by the template are present in the instance. The `governed_section` parameter restricts validation to a named subsection, allowing partially templated documents.

Template versioning is enforced: the `template-version` field in the YAML header must match the version encoded in the template's directory path. A `TrestleError` is raised on mismatch.

## Control Markdown Format

When the catalog/profile/SSP authoring commands write controls to markdown, each control becomes a separate `.md` file organized in a directory tree that mirrors the OSCAL group structure. The file contains:

- A YAML frontmatter block carrying metadata such as the control ID, title, YAML header fields from configuration, and implementation status.
- Heading-delimited sections for the control statement (`## Control`), objective (`## Control Objective`), parts labeled by their OSCAL `part.name`, and implementation guidance sections.
- Moustache-style placeholders for parameter values (e.g., `{{ param-id }}`), which are substituted according to the `ParameterRep` mode chosen at generation time.

## DrawIO Governance

`draw_io.py` provides the `DrawIO` class for reading metadata from `.drawio` diagram files (XML format). It uses `defusedxml.ElementTree` for safe XML parsing with `forbid_dtd=True`. The class extracts page-level metadata stored in the `style` attributes of diagram elements, excluding reserved keys (`id`, `label`). This allows drawio diagrams to carry governed metadata alongside visual content, validated by the `author` commands.

## SSP Markdown Writer

`ssp_io.py` contains `SSPMarkdownWriter`, which assembles SSP-specific sections for the Jinja templating output path. It renders implemented requirements, leveraged controls, and component-by-control information from an in-memory `SystemSecurityPlan` object into markdown strings suitable for embedding in Jinja templates.

## Jinja Authoring

The `author jinja` command provides Jinja2 template processing with OSCAL-aware extensions. The Jinja environment is constructed with:

- `FileSystemLoader` for templates in the trestle root.
- `DictLoader` for built-in template snippets.
- `ChoiceLoader` combining both loaders.
- Custom extensions registered via `trestle/core/jinja/ext.py`.

The command accepts a look-up table YAML file (`-lut`) that injects key-value variables into the template context. The `-nc` flag enables automatic caption numbering for tables and figures. The `-sv` and `-bf` flags control parameter value substitution and bracket formatting in the output.

## Template Versioning

The `author docs`, `author folders`, and `author headers` commands all rely on versioned templates stored in a directory path that includes the version string. The `START_TEMPLATE_VERSION` constant in `trestle/core/commands/author/consts.py` defines the baseline version. Instances are validated against the template version found in their YAML header's `template-version` field, and a `TrestleError` is raised if the version does not match the template's directory location.
