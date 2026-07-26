# Backend Abstraction

## Overview

Keras 3 is designed to run on top of four production backends — JAX, TensorFlow,
PyTorch, and OpenVINO (inference-only) — plus a NumPy backend used for
development and testing. The backend is selected once at process startup and cannot
change after `keras` is imported.

## Backend Selection

The active backend is determined by reading (in priority order):

1. The `KERAS_BACKEND` environment variable.
2. The `backend` field in `~/.keras/keras.json`.
3. A default of `"tensorflow"` if neither is set.

Valid backend strings: `"tensorflow"`, `"jax"`, `"torch"`, `"openvino"`, `"numpy"`.

```bash
export KERAS_BACKEND="jax"
python train.py
```

Or at the start of a script (must precede `import keras`):

```python
import os
os.environ["KERAS_BACKEND"] = "jax"
import keras
```

## Package Structure

`keras.src.backend` is the runtime-polymorphism hub:

```
keras/src/backend/
    __init__.py         # dispatches wildcard imports based on backend()
    config.py           # floatx, epsilon, image_data_format, backend name
    common/             # backend-agnostic shared utilities
        keras_tensor.py     # KerasTensor — the symbolic tensor type
        variables.py        # Variable — backend-agnostic weight container
        dtypes.py           # dtype normalization and promotion rules
        global_state.py     # process-level mutable state registry
        stateless_scope.py  # StatelessScope for JAX functional style
        symbolic_scope.py   # SymbolicScope for graph tracing
        masking.py          # mask propagation helpers
        name_scope.py       # hierarchical naming support
        remat.py            # rematerialization / gradient checkpointing
    jax/
    tensorflow/
    torch/
    numpy/
    openvino/
```

At import time, `backend/__init__.py` does:

```python
if backend() == "jax":
    from keras.src.backend.jax import *
    from keras.src.backend.jax.core import Variable as BackendVariable
```

And then re-exports a unified `keras.Variable` that inherits from
`BackendVariable`. Each backend module provides the same public names
(arithmetic ops, `cast`, `reshape`, `nn.*`, `random.*`, etc.) so that
higher-level code imports only from `keras.src.backend` and remains portable.

## KerasTensor

`KerasTensor` (`keras.src.backend.common.keras_tensor`) is a symbolic tensor — a
container for `shape` and `dtype` (and optional `sparse`/`ragged` flags) without
holding actual data. It is used during graph construction (Functional API, `compute_output_spec`).

Key properties:
- `shape`: tuple of integers or `None` for unknown dimensions.
- `dtype`: normalized dtype string (e.g., `"float32"`).
- `sparse`, `ragged`: boolean flags.
- Immutable: the `shape` and `dtype` setters raise `AttributeError`.

An operation receiving any `KerasTensor` argument dispatches to its
`symbolic_call` path (shape/dtype inference) rather than its `call` (eager)
path. The `any_symbolic_tensors(args, kwargs)` utility checks for this.

## Variable

`keras.Variable` (`keras.src.backend.common.variables`) is the backend-agnostic
weight container. Constructor signature:

```python
Variable(
    initializer,        # array or callable(shape, dtype) -> array
    shape=None,         # required if initializer is callable
    dtype=None,         # defaults to keras.backend.floatx()
    trainable=True,
    autocast=True,      # layer may cast to compute dtype before use
    aggregation="none", # for distributed: "none", "mean", "sum", "only_first_replica"
    name=None,
)
```

`Variable` delegates `.value`, `.numpy()`, `assign()`, `assign_add()`, and
`assign_sub()` to the backend-specific `BackendVariable`. In JAX, the functional
`StatelessScope` context intercepts assignments and collects updated values as
pure-function outputs instead of mutating global state.

## Configuration Surface (config.py)

`keras.src.backend.config` exposes process-global settings with getter/setter pairs:

| Setting | Default | Getter | Setter |
|---|---|---|---|
| Default float type | `"float32"` | `keras.config.floatx()` | `keras.config.set_floatx(value)` |
| Numeric epsilon | `1e-7` | `keras.config.epsilon()` | `keras.config.set_epsilon(value)` |
| Image data format | `"channels_last"` | `keras.config.image_data_format()` | `keras.config.set_image_data_format(fmt)` |
| Active backend | per env | `keras.config.backend()` | not settable after import |

`floatx` accepts `"bfloat16"`, `"float16"`, `"float32"`, or `"float64"`.
`image_data_format` accepts `"channels_last"` or `"channels_first"`.

Settings are also readable from `~/.keras/keras.json`:

```json
{
    "floatx": "float32",
    "epsilon": 1e-07,
    "image_data_format": "channels_last",
    "backend": "jax"
}
```

## Backend-Specific Layer and Trainer Mixins

Each backend injects behavior into `Layer` and `Trainer` via mixins resolved at
import time:

```python
# In keras/src/layers/layer.py
if backend.backend() == "jax":
    from keras.src.backend.jax.layer import JaxLayer as BackendLayer
```

`JaxLayer`, `TFLayer`, `TorchLayer` etc. provide backend-specific implementations
of variable assignment semantics, state synchronization (e.g., `jax_state_sync`),
and DDP wrapper unwrapping (PyTorch `DistributedDataParallel`).

## StatelessScope

`keras.src.backend.common.stateless_scope.StatelessScope` provides a context manager
that intercepts `Variable.assign*` calls and records the updated values in a mapping
rather than writing them in place. This is essential for the JAX backend, where
`jax.grad` requires a pure function with no global side effects:

```python
with backend.StatelessScope(state_mapping=var_mapping) as scope:
    loss = model.compute_loss(...)
updated_value = scope.get_current_value(some_variable)
```

## SymbolicScope and Computation Graph Tracing

`SymbolicScope` marks a region where tensor operations are recorded into a
computation graph (used by the Functional API). `in_symbolic_scope()` returns
`True` inside such a region, and `Operation.__call__` dispatches to `symbolic_call`
accordingly, which runs `compute_output_spec` and creates a `Node` in the graph.

## dtype Policies

`keras.src.dtype_policies` (exported as `keras.DTypePolicy` and
`keras.mixed_precision`) lets layers separate the dtype of their stored weights
(`variable_dtype`) from the dtype of their computations (`compute_dtype`). Setting
`"mixed_float16"` stores weights in `float32` but computes in `float16`, enabling
Tensor Core acceleration with stable weight updates.

## name_scope

`keras.name_scope` (a thin re-export of the backend's `name_scope`) implements
hierarchical path-based naming for variables and layers. The current path is
accessible via `keras.src.backend.common.name_scope.current_path()` and is used
to set `variable.path` at creation time.
