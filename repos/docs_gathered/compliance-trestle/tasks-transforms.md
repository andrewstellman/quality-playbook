# Tasks and Transformers

Trestle provides two related but distinct extension mechanisms for ingesting third-party compliance data into OSCAL: the **task framework** for configurable, pipeline-oriented workflows, and the **transformer framework** for stateless bidirectional format conversion.

## Task Framework

### Package Layout

```
trestle/tasks/
  base_task.py                      # TaskBase abstract class + TaskOutcome enum
  transform.py                      # Generic transform task (delegates to transformers)
  csv_to_oscal_cd.py                # CSV to Component Definition
  csv_to_oscal_mc.py                # CSV to Mapping Collection
  csv_to_oscal_mc_utilities.py      # Shared utilities for MC tasks
  oscal_catalog_to_csv.py           # Catalog to CSV export
  xlsx_to_oscal_cd.py               # Excel to Component Definition
  xlsx_to_oscal_profile.py          # Excel to Profile
  xlsx_helper.py                    # Shared Excel parsing utilities
  xccdf_result_to_oscal_ar.py       # XCCDF results to Assessment Results
  osco_result_to_oscal_ar.py        # OSCO results to Assessment Results
  tanium_result_to_oscal_ar.py      # Tanium results to Assessment Results
  cis_xlsx_to_oscal_cd.py           # CIS Excel to Component Definition
  cis_xlsx_to_oscal_catalog.py      # CIS Excel to Catalog
  ocp4_cis_profile_to_oscal_cd.py   # OCP4 CIS profile to Component Definition
  ocp4_cis_profile_to_oscal_catalog.py  # OCP4 CIS profile to Catalog
  oscal_profile_to_osco_profile.py  # OSCAL Profile to OSCO format
```

### TaskBase

Every task inherits from `TaskBase` (in `trestle/tasks/base_task.py`):

```python
class TaskBase(ABC):
    name: str = 'base'

    def __init__(self, config_object: Optional[configparser.SectionProxy]) -> None: ...

    @abstractmethod
    def print_info(self) -> None: ...

    @abstractmethod
    def execute(self) -> TaskOutcome: ...

    @abstractmethod
    def simulate(self) -> TaskOutcome: ...
```

`config_object` is a `configparser.SectionProxy` drawn from the `.trestle/config.ini` file (or a custom config file). This design keeps the CLI surface minimal: `trestle task <name>` reads configuration from INI rather than accepting per-task flags.

### TaskOutcome

The `TaskOutcome` enum defines the possible results:

| Value | Meaning |
|---|---|
| `SUCCESS` | Task completed successfully |
| `FAILURE` | Task failed |
| `ROLLEDBACK` | Task was rolled back |
| `SIM_SUCCESS` | Simulation indicated success |
| `SIM_FAILURE` | Simulation indicated failure |
| `NOT_IMPLEMENTED` | Feature not implemented in this task |

The `simulate()` method performs a dry run without committing changes, and `execute()` performs the actual transformation.

### Task Discovery and Dispatch

`TaskCmd` in `trestle/core/commands/task.py` discovers all tasks at runtime. It iterates over the `trestle.tasks` package using `pkgutil.iter_modules` and inspects each module for classes inheriting from `TaskBase`. It builds a dictionary keyed by `task.name`. The `trestle task -l` flag lists all discovered tasks with their `print_info()` output. Plugin packages may contribute additional tasks by including a `tasks/` subpackage that follows the same `TaskBase` pattern.

### Configuration Contract

Tasks read all parameters from `configparser.SectionProxy`, under an INI section named `[task.<task-name>]`. A custom config file may be passed with `trestle task -c <path>`. The `simulate()` method should respect all configuration to perform a faithful dry run.

## Transformer Framework

### Package Layout

```
trestle/transforms/
  transformer_factory.py     # TransformerBase, TransformerFactory, abstract subclasses
  transformer_singleton.py   # Module-level singleton factory instance
  transformer_helper.py      # Shared helper utilities for transformers
  results.py                 # Results data structure (wraps OSCAL AssessmentResults)
  implementations/
    osco.py                  # OSCO-format transformer
    tanium.py                # Tanium-format transformer
    xccdf.py                 # XCCDF-format transformer
```

### TransformerBase

`TransformerBase` in `trestle/transforms/transformer_factory.py` is the abstract root:

```python
class TransformerBase(ABC):
    @staticmethod
    def set_timestamp(value: str) -> None: ...
    @staticmethod
    def get_timestamp() -> str: ...

    @abstractmethod
    def transform(self, blob: Any) -> Any: ...
```

The class-level `_timestamp` attribute is set once on first access and shared across all transformer instances in a process, ensuring consistent timestamps across multiple transformation calls in a single run.

Three abstract specializations narrow the type signatures:

```python
class FromOscalTransformer(TransformerBase):
    @abstractmethod
    def transform(self, obj: OscalBaseModel) -> str: ...

class ToOscalTransformer(TransformerBase):
    @abstractmethod
    def transform(self, obj: str) -> OscalBaseModel: ...

class ResultsTransformer(TransformerBase):
    @abstractmethod
    def transform(self, blob: str) -> Results: ...
```

### TransformerFactory

`TransformerFactory` maintains a registry of transformer classes keyed by name:

```python
class TransformerFactory:
    def register_transformer(self, name: str, transformer: Type[TransformerBase]) -> None: ...
    def get(self, name: str) -> TransformerBase: ...
```

`get` instantiates and returns a new transformer instance. Requesting an unregistered name raises `TrestleError`.

### Results

`trestle/transforms/results.py` defines `Results`, a wrapper around `oscal.assessment_results.AssessmentResults` used as the output type for assessment-result transformers (OSCO, Tanium, XCCDF). It provides convenience accessors for the results structure.

### Implemented Transformers

| Module | Format | Direction |
|---|---|---|
| `implementations/osco.py` | OpenShift Compliance Operator | Input → OSCAL AssessmentResults |
| `implementations/tanium.py` | Tanium endpoint compliance data | Input → OSCAL AssessmentResults |
| `implementations/xccdf.py` | XCCDF (Extensible Configuration Checklist) | Input → OSCAL AssessmentResults |

Each implementation class inherits from `ResultsTransformer` and implements `transform(blob: str) -> Results`.

### Pipeline Integration

The `transform.py` task in `trestle/tasks/` provides a `TransformCmd` task that wires the transformer framework into the task system: it reads a source file, selects the appropriate transformer by name from the factory singleton, calls `transform()`, and writes the resulting OSCAL document to the workspace.
