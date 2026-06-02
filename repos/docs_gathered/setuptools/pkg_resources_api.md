# pkg_resources API

`pkg_resources` is a separate top-level package shipped alongside `setuptools`. It provides the legacy runtime API for working with installed distributions, requirement parsing, and resource access from inside Python applications. The module docstring marks it as deprecated and directs new code to `importlib.resources`, `importlib.metadata`, and `packaging`. The package is retained because a large body of installed code still imports it.

## Public surface

The module exports `WorkingSet`, `Distribution`, `Environment`, `Requirement`, `EntryPoint`, `ResolutionError`, `DistributionNotFound`, `VersionConflict`, and helpers such as `iter_entry_points`, `require`, `find_distributions`, `resource_filename`, `resource_stream`, `resource_string`, `resource_isdir`, `resource_listdir`, `get_distribution`, `parse_version`, `parse_requirements`, and the name normalisers `safe_name`, `to_filename`, `safe_version`, and `safe_extra`.

## Working set and environment

A `WorkingSet` is an ordered collection of `Distribution` objects representing what is importable in the current process. The default `pkg_resources.working_set` is constructed from `sys.path` at import time. `Environment` extends this with platform-tag filtering for distribution candidates discovered on disk.

The combination supports `working_set.resolve(requirements, installer=None)`, the function that walks a dependency graph, calls back to an installer for missing distributions, and returns a topologically ordered list.

## Distribution metadata

`Distribution` represents a single installed project. It can be constructed from a filesystem path (`Distribution.from_filename`, `Distribution.from_location`) or by introspecting a loaded module. Metadata is read from `*.egg-info/`, `*.dist-info/`, or an `.egg` archive through an `IMetadataProvider` interface (`PathMetadata`, `FileMetadata`, `EggMetadata`, `EmptyProvider`).

## Resource access

The resource API treats files inside packages as logical names using `/`-separated paths. Implementations exist for filesystem packages (`DefaultProvider`), zip-archive packages (`ZipProvider`), and other PEP 302 loaders that implement `get_data()`. `resource_filename` extracts zipped resources to a per-user cache directory obtained via `platformdirs.user_cache_dir` when on-disk access is required.

## Requirement and version parsing

`Requirement`, `parse_requirements`, `parse_version`, and `safe_name` delegate to the `packaging` library bundled under `setuptools/_vendor/`. The wrappers preserve the historical `pkg_resources` calling conventions while ensuring all version logic matches PEP 440 and PEP 508.

## Namespace declaration

`declare_namespace(name)` is used at runtime by legacy namespace packages whose `__init__.py` contains `__import__('pkg_resources').declare_namespace(__name__)`. New projects are encouraged to use PEP 420 namespace packages instead.
