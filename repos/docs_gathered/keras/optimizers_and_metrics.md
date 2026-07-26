# Optimizers, Metrics, and Losses

## Overview

Keras 3 provides backend-agnostic implementations of standard optimizers, metrics,
and loss functions. All three subsystems follow a common pattern: a base class defines
the update or accumulation contract; concrete subclasses implement specific algorithms;
and the `keras_export` decorator registers each class for serialization by string name.

---

## Optimizers

### BaseOptimizer

All optimizers inherit from `keras.src.optimizers.base_optimizer.BaseOptimizer`
(exported via the `Optimizer` alias in `keras.src.optimizers.optimizer`). The public
constructor interface:

```python
class BaseOptimizer(KerasSaveable):
    def __init__(
        self,
        learning_rate: float | LearningRateSchedule | Callable,
        weight_decay=None,
        clipnorm=None,
        clipvalue=None,
        global_clipnorm=None,
        use_ema=False,
        ema_momentum=0.99,
        ema_overwrite_frequency=None,
        loss_scale_factor=None,
        gradient_accumulation_steps=None,
        name=None,
    ): ...
```

`learning_rate` can be:
- A `float` — stored as a non-trainable `Variable`.
- A `LearningRateSchedule` instance — called with the step count each iteration.
- A callable `step -> lr_value`.

Only one of `clipnorm`, `clipvalue`, `global_clipnorm` may be set simultaneously;
passing more than one raises `ValueError`.

`gradient_accumulation_steps` must be `>= 2` when set; gradients are accumulated
over that many steps before a parameter update.

`use_ema=True` enables exponential moving average of weights with decay
`ema_momentum`. When `ema_overwrite_frequency` is set, EMA weights are copied back
into the model weights at that interval.

### Implementing a Custom Optimizer

Three methods to override:

```python
class MyOptimizer(keras.Optimizer):
    def build(self, variables):
        super().build(variables)
        # Create optimizer state variables via self.add_variable_from_reference(...)

    def update_step(self, gradient, variable, learning_rate):
        # Compute and apply the parameter update

    def get_config(self):
        config = super().get_config()
        config.update({"my_param": self.my_param})
        return config
```

### Built-in Optimizers

| Class | Export |
|---|---|
| `SGD` | `keras.optimizers.SGD` |
| `Adam` | `keras.optimizers.Adam` |
| `AdamW` | `keras.optimizers.AdamW` |
| `Adagrad` | `keras.optimizers.Adagrad` |
| `Adadelta` | `keras.optimizers.Adadelta` |
| `Adamax` | `keras.optimizers.Adamax` |
| `Adafactor` | `keras.optimizers.Adafactor` |
| `Nadam` | `keras.optimizers.Nadam` |
| `RMSprop` | `keras.optimizers.RMSprop` |
| `Ftrl` | `keras.optimizers.Ftrl` |
| `Lion` | `keras.optimizers.Lion` |
| `Lamb` | `keras.optimizers.Lamb` |
| `Muon` | `keras.optimizers.Muon` |

Optimizers are referenced by string name in `compile()`:
`model.compile(optimizer="adam")` resolves to `keras.optimizers.Adam()` with
default hyperparameters via `keras.optimizers.get(identifier)`.

### LossScaleOptimizer

`keras.optimizers.LossScaleOptimizer` wraps another optimizer and dynamically scales
the loss before backward and unscales gradients before the weight update — enabling
`float16` training without underflow. It is applied automatically by `compile()` when
`auto_scale_loss=True` and the model dtype policy is `"mixed_float16"`.

### Learning Rate Schedules

Schedules live in `keras.optimizers.schedules` and implement a callable interface:

```python
class LearningRateSchedule:
    def __call__(self, step): ...       # returns the lr for this step
    def get_config(self) -> dict: ...
    @classmethod
    def from_config(cls, config): ...
```

Built-in schedules:
- `ExponentialDecay(initial_learning_rate, decay_steps, decay_rate, staircase=False)`
- `PiecewiseConstantDecay(boundaries, values)`
- `PolynomialDecay(initial_learning_rate, decay_steps, end_learning_rate, power, cycle)`
- `CosineDecay(initial_learning_rate, decay_steps, alpha)`
- `CosineDecayRestarts(initial_learning_rate, first_decay_steps, t_mul, m_mul, alpha)`
- `InverseTimeDecay(initial_learning_rate, decay_steps, decay_rate, staircase=False)`

---

## Metrics

### Metric Base Class

`keras.Metric` (also `keras.metrics.Metric`) encapsulates accumulation state and
reduction logic across batches:

```python
class Metric(KerasSaveable):
    def update_state(self, *args, **kwargs): ...   # accumulate statistics
    def result(self) -> Tensor: ...                # compute and return the scalar
    def reset_state(self): ...                     # zero all state variables
```

State variables are created via `self.add_variable(shape, initializer, name)` in
`__init__`. `reset_state()` zeros all variables; it is called automatically between
epochs.

The typical usage pattern (standalone):

```python
m = keras.metrics.MeanSquaredError()
for batch in dataset:
    m.update_state(y_true_batch, y_pred_batch)
print(m.result().numpy())
```

### Built-in Metric Families

**Accuracy:**
- `Accuracy`, `BinaryAccuracy`, `CategoricalAccuracy`, `SparseCategoricalAccuracy`
- `TopKCategoricalAccuracy`, `SparseTopKCategoricalAccuracy`

**Regression:**
- `MeanSquaredError`, `RootMeanSquaredError`, `MeanAbsoluteError`,
  `MeanAbsolutePercentageError`, `MeanSquaredLogarithmicError`, `CosineSimilarity`,
  `LogCoshError`

**Probabilistic:**
- `KLDivergence`, `BinaryCrossentropy`, `CategoricalCrossentropy`,
  `SparseCategoricalCrossentropy`

**Confusion matrix:**
- `TruePositives`, `TrueNegatives`, `FalsePositives`, `FalseNegatives`,
  `Precision`, `Recall`, `AUC`, `PrecisionAtRecall`, `RecallAtPrecision`,
  `SensitivityAtSpecificity`, `SpecificityAtSensitivity`

**F-score:** `F1Score`, `FBetaScore`

**IoU (segmentation):** `IoU`, `BinaryIoU`, `MeanIoU`, `OneHotIoU`, `OneHotMeanIoU`

**Hinge:** `Hinge`, `SquaredHinge`, `CategoricalHinge`

**Correlation:** `PearsonCorrelation`

**Reduction:** `Mean`, `Sum`, `MeanRelativeError`, `MeanMetricWrapper`

### CompileMetrics

Inside the trainer, metrics passed to `compile()` are wrapped in `CompileMetrics`,
which handles multi-output models (dict-keyed metrics), `weighted_metrics` support,
and the automatic string-to-class resolution (`"accuracy"` → `BinaryAccuracy`,
`CategoricalAccuracy`, or `SparseCategoricalAccuracy` based on output/target shapes).

---

## Losses

### Loss Base Class

`keras.losses.Loss` defines the interface:

```python
class Loss:
    def call(self, y_true, y_pred) -> Tensor: ...   # unweighted, unreduced loss
    def __call__(self, y_true, y_pred, sample_weight=None) -> Tensor: ...
    def get_config(self) -> dict: ...
```

The `reduction` argument controls how per-sample losses are aggregated:
- `"sum_over_batch_size"` (default) — mean over samples.
- `"sum"` — scalar sum.
- `"mean_with_sample_weight"` — divides by total sample weight.
- `"none"` / `None` — no reduction; returns per-sample tensor.

`LossFunctionWrapper` bridges standalone functions (e.g., `mean_squared_error`)
to the `Loss` class interface, enabling both class-based and function-based usage.

### Built-in Loss Classes

**Regression:**
- `MeanSquaredError`, `MeanAbsoluteError`, `MeanAbsolutePercentageError`,
  `MeanSquaredLogarithmicError`, `Huber`, `LogCosh`

**Classification:**
- `BinaryCrossentropy(from_logits=False, label_smoothing=0)`,
  `CategoricalCrossentropy(from_logits=False, label_smoothing=0)`,
  `SparseCategoricalCrossentropy`

**Hinge / Ranking:**
- `Hinge`, `SquaredHinge`, `CategoricalHinge`

**Probabilistic:**
- `KLDivergence`, `Poisson`

**Cosine:**
- `CosineSimilarity(axis=-1)`

**Contrastive:**
- `ContrastiveLoss`

Losses are retrievable by string name in `compile()`:
`model.compile(loss="mse")` → `keras.losses.get("mse")` → `MeanSquaredError()`.

### CompileLoss

The `CompileLoss` wrapper (in `keras.src.trainers.compile_utils`) handles:
- Multi-output models with per-output loss dict or list.
- Per-output `loss_weights` scaling.
- Aggregation of per-output losses into a single scalar for the optimizer.
- Tracking of per-output loss values as individual `Mean` metrics.

### Functional API for Losses

All loss functions are also available as standalone callables in `keras.losses`:

```python
loss_value = keras.losses.mean_squared_error(y_true, y_pred)
loss_value = keras.losses.binary_crossentropy(y_true, y_pred, from_logits=True)
```

---

## Serialization

Optimizers, metrics, and losses all implement `get_config()` / `from_config()` and
are registered via `@keras_export`. They can be passed by string name to `compile()`
and will be reconstructed from config when loading a saved model.
