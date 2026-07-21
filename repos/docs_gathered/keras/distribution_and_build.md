# Distribution, Build, and Project Conventions

## Overview

This file covers Keras 3's distributed training API, the package build and
installation system, public API export mechanism, test conventions, and
general contribution workflow.

---

## Distributed Training

### API Location

`keras.distribution` (`keras.src.distribution.distribution_lib`) provides a
unified multi-device sharding API modeled on `jax.sharding.Mesh` and
`tf.dtensor.Mesh`. Primary JAX support is present; TensorFlow via `tf.dtensor` is
planned for a future release.

### Core Concepts

**DeviceMesh** — a logical grid of physical devices:

```python
@keras_export("keras.distribution.DeviceMesh")
class DeviceMesh:
    def __init__(self, shape, axis_names, devices=None): ...
```

- `shape`: tuple of ints, e.g., `(8,)` for pure data-parallel or `(4, 2)` for
  combined model + data parallelism.
- `axis_names`: list of strings matching `shape` length (e.g., `["batch", "model"]`).
- `devices`: optional list from `keras.distribution.list_devices(device_type)`.

**TensorLayout** — a mapping from tensor axes to mesh axes:

```python
@keras_export("keras.distribution.TensorLayout")
class TensorLayout:
    def __init__(self, axes, device_mesh=None): ...
```

`axes` is a tuple of strings (matching `device_mesh.axis_names`) or `None` for
unsharded dimensions. A `TensorLayout` without a `device_mesh` is incomplete; the
mesh is typically attached later via `DataParallel` or `ModelParallel`.

**DataParallel** — the standard data-parallel strategy:

```python
strategy = keras.distribution.DataParallel(device_mesh=mesh)
keras.distribution.set_distribution(strategy)
```

When a distribution is set globally, variables and gradients are automatically
sharded/replicated according to the strategy when `model.fit()` runs.

**ModelParallel** — tensor parallelism with explicit layout maps for variables.

### Multi-Host Initialization

For multi-process (multi-node) runs:

```python
keras.distribution.initialize(
    job_addresses="10.0.0.1:1234,10.0.0.2:2345",
    num_processes=2,
    process_id=0,
)
```

All three arguments can alternatively be set via environment variables:
`KERAS_DISTRIBUTION_JOB_ADDRESSES`, `KERAS_DISTRIBUTION_NUM_PROCESSES`,
`KERAS_DISTRIBUTION_PROCESS_ID`.

### Distribution in the Layer System

`keras.src.distribution.distribution_lib` provides the `get_distribution()` /
`set_distribution()` process-global accessors (backed by `global_state`). During
`Layer.add_weight()`, the active distribution strategy is consulted to determine
the layout of the new variable. The `distribution_lib` module in each backend
(e.g., `keras.src.backend.jax.distribution_lib`) implements the actual sharding
primitives (`jax.sharding`, `dtensor`, etc.).

---

## Build and Packaging

### pyproject.toml

Keras uses the `setuptools` build backend:

```toml
[build-system]
requires = ["setuptools >=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "keras"
requires-python = ">=3.10"
license = {text = "Apache License 2.0"}
dependencies = [
    "absl-py", "numpy", "rich", "namex", "h5py",
    "optree", "ml-dtypes", "packaging",
]
```

Backend dependencies (TensorFlow, JAX, PyTorch, OpenVINO) are **not** listed in
`dependencies` — they are declared as optional and installed separately. This allows
Keras to be installed in environments that only have one backend.

Backend-specific CUDA requirements are in separate files:
`requirements-jax-cuda.txt`, `requirements-tensorflow-cuda.txt`, `requirements-torch-cuda.txt`.

### Package Layout Remapping

```toml
[tool.setuptools.package-dir]
"" = "."
"keras" = "keras/api"      # the public API package root is keras/api/
"keras.src" = "keras/src"  # internals are exposed as keras.src for tests
```

The public installable package (`keras`) maps to `keras/api/`, which contains only
the generated public API. `keras/src/` holds all implementation and is accessible
as `keras.src` for internal use and tests.

### pip_build.py and api_gen.py

- `python pip_build.py --install` — builds the distribution and installs it locally.
- `python api_gen.py` (or `./shell/api_gen.sh`) — regenerates `keras/api/` from the
  `@keras_export` decorators scattered across `keras/src/`. This must be run before
  committing changes that add or rename public API symbols.
- `./shell/format.sh` — runs Ruff formatter and linter across the codebase.

### Version

`keras/__version__` is read dynamically from `keras.src.version.__version__` in
`pyproject.toml` via `dynamic = ["version"]`.

---

## Public API Export System

`@keras_export(path)` is the mechanism by which internal symbols become part of the
public `keras.*` namespace. Implemented in `keras.src.api_export`:

```python
@keras_export(["keras.Layer", "keras.layers.Layer"])
class Layer(BackendLayer, Operation): ...
```

- If `namex` is installed, `keras_export` delegates to `namex.export` (which writes
  the API stubs into `keras/api/`).
- Otherwise, it acts as a no-op decorator while still calling
  `register_internal_serializable` to populate the name registry.

Multiple export paths can be listed; the first path is the canonical serialization
name. Both `keras.Layer` and `keras.layers.Layer` point to the same class, but
`"keras.Layer"` is what appears in saved configs.

---

## Test Conventions

Keras uses `pytest`. Test files live alongside their source files, named
`<module>_test.py`. Integration tests are in `integration_tests/`.

### Running Tests

```shell
pytest keras/src/losses/losses_test.py                        # entire file
pytest keras/src/losses/losses_test.py::MeanSquaredErrorTest  # single class
pytest keras/src/losses/losses_test.py::MeanSquaredErrorTest::test_sample_weighted  # single method
```

### conftest.py

`conftest.py` at the repo root configures the pytest session. The `pyproject.toml`
`[tool.pytest.ini_options]` block sets:

```toml
filterwarnings = ["error", "ignore::DeprecationWarning", ...]
addopts = "-vv"
norecursedirs = ["build"]
```

`filterwarnings = ["error"]` means unexpected warnings become test failures (with
specific categories ignored).

### Backend Selection in Tests

Tests that need to run against a specific backend set `KERAS_BACKEND` before
importing Keras. The test suite is designed to run on any backend; backend-specific
logic is guarded with `if backend.backend() == "jax":` checks.

### codecov.yml

Coverage reporting is configured in `codecov.yml`. Coverage is collected via
`pytest-cov`; `pyproject.toml` excludes `*_test.py` files and `keras/src/legacy/`
from coverage reports.

---

## Code Style and Pre-commit

`ruff` is the formatter and linter (configured in `pyproject.toml`). The pre-commit
hook (`.pre-commit-config.yaml`) runs API generation, formatting, and linting on
every commit. Run `pre-commit install` once after cloning.

Key Ruff rules: `E` (pycodestyle), `F` (Pyflakes), `I` (isort). Notable ignores:
`E722` (bare except), `E741` (ambiguous variable names), `E731` (lambda assignment).

---

## Docstring Conventions

Class docstrings follow this structure (per `CONTRIBUTING.md`):
1. One-line description.
2. Paragraph(s) of detail.
3. Optional `Examples` section.
4. `Args` for `__init__` parameters.
5. For layers: `Call arguments`, `Returns`, optional `Raises`.

Function docstrings follow: description, detail, `Examples`, `Args`, `Returns`,
optional `Raises`.

---

## Examples and Guides

`examples/` contains runnable demo scripts for each backend:
- `demo_functional.py` — Functional API model building.
- `demo_subclass.py` — Model subclassing.
- `demo_custom_jax_workflow.py`, `demo_custom_tf_workflow.py`, `demo_custom_torch_workflow.py` —
  writing custom training loops per backend.
- `demo_jax_distributed.py`, `demo_torch_multi_gpu.py` — distributed training.

`guides/` contains longer narrative scripts (intended to be rendered as tutorials):
functional API, sequential model, custom layers, transfer learning, masking/padding,
custom training loops per backend, distributed training per backend, writing callbacks.
