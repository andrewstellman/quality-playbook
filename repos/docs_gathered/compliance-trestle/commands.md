# Command-Line Interface

Trestle exposes its functionality through a structured CLI built on the `ilcli` library. The entry point is `trestle.cli:run`, registered as the `trestle` console script in `pyproject.toml`.

## Command Tree

The root command class `Trestle` in `trestle/cli.py` declares a `subcommands` list that forms the full command tree:

| Subcommand | Class | Purpose |
|---|---|---|
| `init` | `InitCmd` | Initialize a trestle workspace directory |
| `import` | `ImportCmd` | Import an OSCAL document into the workspace |
| `create` | `CreateCmd` | Create a new empty OSCAL model in the workspace |
| `split` | `SplitCmd` | Split a model file into component sub-files |
| `merge` | `MergeCmd` | Merge split sub-files back into a single model file |
| `assemble` | `AssembleCmd` | Assemble a model from its edited components |
| `replicate` | `ReplicateCmd` | Copy an existing model to a new name |
| `add` | `AddCmd` | Add elements to an existing model |
| `remove` | `RemoveCmd` | Remove elements from an existing model |
| `validate` | `ValidateCmd` | Validate OSCAL models in the workspace |
| `href` | `HrefCmd` | Update href references in a profile |
| `describe` | `DescribeCmd` | Display information about an OSCAL model's fields |
| `version` | `VersionCmd` | Print trestle and OSCAL version |
| `task` | `TaskCmd` | Run a registered transformation task |
| `author` | `AuthorCmd` | Authoring subcommands (umbrella) |

The `author` command is itself an umbrella for a second tier:

| Subcommand | Purpose |
|---|---|
| `author catalog-generate` | Export catalog controls to markdown |
| `author catalog-assemble` | Assemble markdown back into a catalog |
| `author profile-generate` | Export profile controls to markdown |
| `author profile-assemble` | Assemble markdown back into a profile |
| `author profile-inherit` | Generate inheritance markdown from a leveraged SSP |
| `author profile-resolve` | Resolve a profile chain into a resolved catalog |
| `author ssp-generate` | Generate an SSP in markdown from a profile |
| `author ssp-assemble` | Assemble markdown back into an SSP |
| `author ssp-filter` | Filter an SSP by component or profile |
| `author component-generate` | Export component definition to markdown |
| `author component-assemble` | Assemble markdown back into a component definition |
| `author jinja` | Transform a Jinja2 template using OSCAL data |
| `author docs` | Validate governed markdown documents |
| `author folders` | Validate governed markdown folder structures |
| `author headers` | Validate YAML headers in markdown files |

## Command Base Classes

Commands inherit from `CommandBase` or `CommandPlusDocs`, both defined in `trestle/core/commands/command_docs.py`. These classes provide the `add_argument` helper used in `_init_arguments()` and coordinate with `ilcli` for argument parsing and dispatch. Each command implements a `_run(args: argparse.Namespace) -> int` method that returns a `CmdReturnCodes` integer value.

## Return Codes

`trestle/core/commands/common/return_codes.py` defines `CmdReturnCodes`, an `enum.Enum` mapping names to integer exit codes:

| Name | Value | Meaning |
|---|---|---|
| `SUCCESS` | 0 | Operation completed successfully |
| `COMMAND_ERROR` | 1 | Expected error handled by the command |
| `INCORRECT_ARGS` | 2 | Arguments were incorrect or incomplete |
| `DOCUMENTS_VALIDATION_ERROR` | 3 | Markdown or drawio validation failed |
| `OSCAL_VALIDATION_ERROR` | 4 | OSCAL model validation failed |
| `TRESTLE_ROOT_ERROR` | 5 | Workspace setup failure |
| `IO_ERROR` | 6 | File system error |
| `AUTH_ERROR` | 7 | Authentication error accessing cache |
| `UNKNOWN_ERROR` | 8 | Unhandled exception |

## Global Flags

Two flags apply to all commands:

- `-v / --verbose` (count): increases logging verbosity; may be repeated.
- `-tr / --trestle-root` (path): sets the workspace root directory; defaults to the current working directory.

## Plugin-Contributed Commands

At startup, `Trestle.__init__` calls `discovered_plugins('commands')` to find any installed Python packages whose names start with `trestle_`. If a discovered package exports a class derived from `CommandBase` or `CommandPlusDocs`, that class is appended to the `subcommands` list automatically. This gives third-party packages a clean mechanism to add new top-level trestle verbs without forking the core.

## Workspace Initialization

`trestle init` creates the standard workspace layout under a chosen root directory:

- `.trestle/` — configuration directory (created in all modes)
- `.trestle/config.ini` — INI-format configuration file
- Type-named model directories: `catalogs/`, `profiles/`, `system-security-plans/`, `component-definitions/`, `assessment-plans/`, `assessment-results/`, `plan-of-action-and-milestones/`, `mapping-collections/`
- `dist/` — target directory for published artifacts (created in `--full` mode)

Three modes are available via flags: `--full` (all directories), `--local` (model directories only), and `--govdocs` (governance documents structure only).

## Programmatic Use

Beyond the CLI, `trestle/core/repository.py` exposes `ManagedOSCAL` and a `Repository` class for programmatic manipulation of workspace contents. `ManagedOSCAL` wraps a named model instance and provides `read()`, `write()`, `split()`, and `merge()` methods that internally invoke the same command logic used by the CLI.
