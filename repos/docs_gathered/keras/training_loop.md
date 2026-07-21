# Training Loop

## Overview

Keras provides a high-level training loop through `Model.compile()` / `Model.fit()`,
as well as the building blocks to write fully custom loops. The `Trainer` mixin
(in `keras.src.trainers.trainer`) is inherited by every `Model` and provides the
compile/fit/evaluate/predict surface.

## compile()

`Model.compile()` configures the model for training:

```python
model.compile(
    optimizer="adam",              # string name or Optimizer instance
    loss="sparse_categorical_crossentropy",  # string, callable, or Loss instance
    metrics=["accuracy"],          # list of strings, callables, or Metric instances
    weighted_metrics=None,         # metrics weighted by sample_weight
    run_eagerly=False,             # bypass compilation; slower but debuggable
    steps_per_execution=1,         # batches per compiled-function call (TPU perf)
    jit_compile="auto",            # XLA / torch.compile; "auto" picks per backend
    auto_scale_loss=True,          # wraps optimizer in LossScaleOptimizer for mixed_float16
)
```

Key behaviors:
- `jit_compile="auto"` enables XLA on JAX/TF when the model supports it; defaults to
  eager on Torch (`torch.compile` is opt-in via `jit_compile=True`).
- `auto_scale_loss=True` automatically wraps the optimizer in a `LossScaleOptimizer`
  when the model dtype policy is `"mixed_float16"`.
- `compile()` stores a `SerializableDict` snapshot of its arguments for later
  serialization (loaded models can be recompiled to the same settings).

`CompileLoss` and `CompileMetrics` (in `keras.src.trainers.compile_utils`) normalize
the loss and metrics arguments — resolving string names, handling multi-output dicts,
and wiring per-output loss weights.

## fit()

`Model.fit()` signature (abbreviated):

```python
model.fit(
    x, y=None, batch_size=32,
    epochs=1, verbose="auto",
    callbacks=None,
    validation_split=0.0, validation_data=None,
    shuffle=True,
    class_weight=None, sample_weight=None,
    initial_epoch=0, steps_per_epoch=None,
    validation_steps=None, validation_batch_size=None,
    validation_freq=1,
)
```

`fit()` returns a `History` object whose `.history` dict maps metric names to
per-epoch lists.

## EpochIterator and Data Adapters

Data is normalized through the `DataAdapter` abstraction
(`keras.src.trainers.data_adapters`). Concrete adapters handle:

| Input type | Adapter |
|---|---|
| NumPy arrays / Python lists | `ArrayDataAdapter` |
| `keras.utils.PyDataset` | `PyDatasetAdapter` |
| `tf.data.Dataset` | `TFDatasetAdapter` |
| PyTorch `DataLoader` | `TorchDataLoaderAdapter` |
| Python generators | `GeneratorDataAdapter` |
| Grain `IterDataset` | `GrainDatasetAdapter` |

`EpochIterator` wraps a `DataAdapter` and controls the step-level iteration loop,
yielding `(step, data)` tuples.  It reports `num_batches` when known.

Data tuples are expected in the form `(x,)`, `(x, y)`, or `(x, y, sample_weight)`.
`keras.utils.unpack_x_y_sample_weight` and `pack_x_y_sample_weight` are convenience
utilities for working with this convention in custom `train_step` overrides.

## train_step / test_step / predict_step

The core of each iteration is a backend-specific step function. The high-level mixin
defines the contract:

```python
def train_step(self, data):
    x, y, sample_weight = data_adapter_utils.unpack_x_y_sample_weight(data)
    # forward pass
    y_pred = self(x, training=True)
    loss = self.compute_loss(x, y, y_pred, sample_weight, training=True)
    # backward pass (handled by backend trainer)
    self.optimizer.apply(gradients, self.trainable_variables)
    return self.compute_metrics(x, y, y_pred, sample_weight)
```

Subclasses override `train_step` to inject custom logic while keeping the rest of the
loop (callbacks, metric tracking, validation) intact.

## Backend-Specific Trainers

Each backend has its own Trainer subclass:

- **JAXTrainer** (`keras.src.backend.jax.trainer`): Implements `train_step` as a
  pure-function pair `(compute_loss_and_updates, jax.grad)` suitable for `jax.jit`.
  State is passed functionally (trainable variables, non-trainable variables, metrics
  variables) and updated via `StatelessScope`. Uses `nnx.jit` when the NNX backend is
  enabled.
- **TensorFlowTrainer** (`keras.src.backend.tensorflow.trainer`): Uses `tf.GradientTape`
  for gradient computation and optionally `tf.function` for graph compilation.
- **TorchTrainer** (`keras.src.backend.torch.trainer`): Calls `loss.backward()` and
  `optimizer.step()` in PyTorch idiom; integrates with `torch.compile` when requested.

## Custom Training Loops

For full control, callers skip `compile`/`fit` and iterate manually:

```python
for epoch in range(epochs):
    for step, data in enumerate(dataset):
        with tf.GradientTape() as tape:           # TF example
            loss = model.compute_loss(...)
        grads = tape.gradient(loss, model.trainable_variables)
        optimizer.apply(grads, model.trainable_variables)
```

The JAX path uses `jax.grad` against `model.stateless_compute_loss`, which accepts
explicit variable lists and returns updated variable lists without side effects.

## compute_loss / compute_metrics

- `compute_loss(x, y, y_pred, sample_weight, training)` — sums `_compile_loss` output
  with any auxiliary losses registered via `add_loss`. Subclasses override this to
  inject custom loss terms.
- `compute_metrics(x, y, y_pred, sample_weight)` — calls `update_state` on all compiled
  metrics and returns a `{name: value}` dict.

## evaluate() and predict()

- `Model.evaluate(x, y, ...)` runs a full pass through the test data adapters, calling
  `test_step` at each iteration, and returns the metric values.
- `Model.predict(x, ...)` calls `predict_step` at each batch and concatenates outputs.

Both methods share the same `DataAdapter` routing and callback firing used by `fit()`.

## JIT Compilation Semantics

`jit_compile` on the `Trainer` is resolved to a boolean at `compile()` time:
- `"auto"` → `True` on JAX/TF when `model_supports_jit(model)` is True; `False` on
  CPU-only TF; `False` with `tf.distribute`; `False` on Torch.
- If `run_eagerly=True`, `jit_compile` is forced to `False` with a warning.
