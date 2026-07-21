# Error Handling, Logging, and Action Framework

Trestle uses a structured error hierarchy, a logging convention layered on Python's standard `logging` module, and a transactional action/plan abstraction for filesystem mutations.

## Error Hierarchy

All trestle-specific errors are defined in `trestle/common/err.py` and inherit from `TrestleError`, which itself inherits from `RuntimeError`:

```
RuntimeError
  └── TrestleError               # General framework error; carries a msg string
        ├── TrestleNotFoundError # Resource not found
        ├── TrestleRootError     # Workspace root invalid or not initialized
        └── TrestleIncorrectArgsError  # Command arguments incorrect or incomplete
```

`TrestleError.__str__` returns `self.msg` directly, so error messages are clean when printed. All public APIs raise `TrestleError` or a subclass; callers are expected to catch it specifically rather than catching `Exception`.

## Error-to-Return-Code Mapping

The `_exception_to_error_code` function in `err.py` converts exception types to `CmdReturnCodes` integer values:

```python
TrestleRootError        -> CmdReturnCodes.TRESTLE_ROOT_ERROR (5)
TrestleIncorrectArgsError -> CmdReturnCodes.INCORRECT_ARGS (2)
all others              -> CmdReturnCodes.COMMAND_ERROR (1)
```

The `handle_generic_command_exception` function wraps this mapping:

```python
def handle_generic_command_exception(
    exception: Exception,
    logger: Logger,
    msg: str = 'Exception occurred during execution'
) -> int
```

It logs the exception at `error` level (full traceback at higher verbosity) and returns the integer return code. CLI command `_run` methods typically wrap their bodies in a `try/except Exception` block that calls this function at the outer boundary.

## Logging Convention

Every source module creates its own named logger at module scope:

```python
logger = logging.getLogger(__name__)
```

The root logger for trestle is named `'trestle'` (set in `cli.py`). `trestle/common/log.py` provides `set_log_level_from_args(args)`, which reads the `-v/--verbose` count from parsed arguments and sets the log level:

- 0 (default): WARNING
- 1 (`-v`): INFO
- 2+ (`-vv`): DEBUG

The `get_current_verbosity_level(logger)` helper returns the current numeric verbosity, used by `handle_generic_command_exception` to decide whether to log a short message or a full traceback.

A `Trace` wrapper class in `trestle/common/log.py` provides a `log(msg)` method that emits at DEBUG level, used in performance-sensitive paths.

## Action Framework

The action/plan framework in `trestle/core/models/` provides a transactional model for filesystem mutations. Rather than modifying files directly, commands build a `Plan` of `Action` objects and then call `Plan.execute()`.

### Action

`Action` in `trestle/core/models/actions.py` is an abstract base class:

```python
class Action(ABC):
    def __init__(self, action_type: ActionType, has_rollback: bool) -> None: ...
    def get_type(self) -> ActionType: ...
    def has_rollback(self) -> bool: ...
    def has_executed(self) -> bool: ...
    @abstractmethod
    def execute(self) -> None: ...
    @abstractmethod
    def rollback(self) -> None: ...
```

`ActionType` is an enum with values `CREATE_PATH` (10), `WRITE` (11), `REMOVE_PATH` (12), `UPDATE` (20), `REMOVE` (21). File-system actions have codes in the 10s; model-processing actions in the 20s.

Concrete action classes include:
- `CreatePathAction` — creates a file or directory path.
- `RemovePathAction` — removes a file or directory.
- `WriteFileAction` — serializes an `Element` to a file in JSON or YAML format.
- `UpdateAction` — updates an element at a given path within the in-memory model.
- `RemoveAction` — removes an element at a given path.

### Plan

`Plan` in `trestle/core/models/plans.py` is an ordered list of `Action` objects:

```python
class Plan:
    def add_action(self, action: Action) -> None: ...
    def add_actions(self, actions: List[Action]) -> None: ...
    def execute(self) -> None: ...
    def rollback(self) -> None: ...
    def get_actions(self) -> List[Action]: ...
```

`Plan.execute()` runs each action in order. If any action raises an exception, it calls `Plan.rollback()` before re-raising. `rollback()` runs actions in reverse order; if any action declares `has_rollback() == False`, `rollback()` raises `UnsupportedOperation`. This provides best-effort atomicity for multi-step filesystem operations.

## Element and ElementPath

`Element` in `trestle/core/models/elements.py` is a wrapper around an `OscalBaseModel` instance that adds path-based navigation and mutation:

```python
class Element:
    def get(self) -> OscalBaseModel: ...
    def get_at(self, element_path: Optional[ElementPath] = None) -> Any: ...
    def set_at(self, element_path: ElementPath, value: Any) -> 'Element': ...
```

`ElementPath` parses a dot-separated path string (e.g., `'catalog.groups.*'`) into a list of path segments. A single wildcard `*` at the end denotes all elements of a list or dict field. `ElementPath.get_type(root_model)` resolves the Python type at the path using Pydantic field introspection, supporting Union types via `_get_model_type_from_union`.

## FileContentType

`FileContentType` in `trestle/core/models/file_content_type.py` is an enum (`JSON`, `YAML`, `UNKNOWN`) with utility methods:

```python
FileContentType.to_file_extension(content_type) -> str     # '.json' or '.yaml'
FileContentType.path_to_content_type(path) -> FileContentType
FileContentType.path_to_file_extension(path) -> str
```

These are used throughout the codebase wherever code must handle either JSON or YAML without branching manually.
