# Models and Layers

## Overview

The `Layer` and `Model` classes are the foundational abstractions in Keras 3. Every
computational unit that holds state and performs a forward pass — from a single `Dense`
layer to a complete ResNet — is a `Layer`. `Model` extends `Layer` with training,
evaluation, and prediction capabilities.

## The Layer Base Class

`keras.Layer` (exported also as `keras.layers.Layer`) inherits from two bases:

- `Operation` — the graph-aware callable that routes between eager and symbolic execution.
- A backend-specific mixin (`TFLayer`, `JaxLayer`, `TorchLayer`, `NumpyLayer`, or
  `OpenvinoLayer`) — injected at import time based on `KERAS_BACKEND`.

The three methods a subclass is expected to implement are:

```python
def __init__(self, ...):          # define layer attributes; create weights that do not depend on input shape
def build(self, input_shape):     # create input-shape-dependent weights via self.add_weight()
def call(self, inputs, ...):      # define the forward computation; may accept `training` and `mask` kwargs
def get_config(self) -> dict:     # return the constructor kwargs for serialization
```

`build()` is called automatically on the first `__call__()` invocation when the
layer has not yet been built. Keras wraps the user's `build` method at class
instantiation time to open a name scope, record `_build_shapes_dict`, set `built=True`,
and lock the variable state.

Weight creation uses `self.add_weight(shape, initializer, trainable, name, ...)`.
Trainable weights appear in `layer.trainable_weights`; non-trainable weights appear
in `layer.non_trainable_weights`; both are concatenated in `layer.weights`.

Layer attributes that are `Variable` instances (or other `Layer` instances, or lists/dicts
of them) are tracked automatically by the `Tracker` subsystem, which walks attribute
assignments to discover nested variables and sub-layers.

The `dtype` argument (or a `keras.DTypePolicy`) controls both the variable dtype
(`variable_dtype`) and the computation dtype (`compute_dtype`). Inputs are automatically
cast to `compute_dtype` before `call()`.

## The Three Model Construction Styles

### 1. Functional API

Construct a `Functional` model by calling `keras.Input(shape=...)` to produce a
`KerasTensor`, chaining layer calls that produce further `KerasTensor` outputs, then
wrapping inputs and outputs in `keras.Model(inputs, outputs)`:

```python
inputs = keras.Input(shape=(37,))
x = keras.layers.Dense(32, activation="relu")(inputs)
outputs = keras.layers.Dense(5, activation="softmax")(x)
model = keras.Model(inputs, outputs)
```

`keras.Model.__new__` detects the functional-init signature and transparently returns
a `Functional` instance. A `Functional` model is a directed acyclic graph of `Node`
objects (one node per layer call) and exposes the full topology for static shape
inference and visualization.

Sub-models can be extracted from intermediate tensors without re-creating layers:
weights are shared automatically.

### 2. Subclassing

Override `keras.Model` with `__init__` (declare sub-layers as attributes) and
`call(self, inputs, training=False)`. Custom logic — variable-length paths, dynamic
shapes, auxiliary losses — lives here:

```python
class MyModel(keras.Model):
    def __init__(self):
        super().__init__()
        self.dense = keras.layers.Dense(32, activation="relu")
    def call(self, inputs, training=False):
        return self.dense(inputs)
```

### 3. Sequential

`keras.Sequential` is a special-case `Functional` model where layers are a linear
stack, each with a single tensor input and single tensor output. Layers are added via
`model.add(layer)` or passed as a list in the constructor. A leading `keras.Input`
layer is optional; without it, the first `__call__` triggers deferred build.

## Layer Catalogue

Built-in layer families live under `keras.src.layers`:

| Family | Examples |
|---|---|
| `core` | `Dense`, `Embedding`, `EinsumDense`, `Lambda`, `Masking`, `Wrapper` |
| `convolutional` | `Conv1D/2D/3D`, `DepthwiseConv2D`, `Conv1D/2DTranspose` |
| `pooling` | `MaxPooling1D/2D/3D`, `GlobalAveragePooling2D`, `AveragePooling*` |
| `normalization` | `BatchNormalization`, `LayerNormalization`, `GroupNormalization`, `SpectralNormalization` |
| `regularization` | `Dropout`, `SpatialDropout1D/2D/3D`, `GaussianDropout`, `ActivityRegularization` |
| `attention` | `MultiHeadAttention`, `GroupedQueryAttention`, `Attention`, `AdditiveAttention` |
| `rnn` | `LSTM`, `GRU`, `SimpleRNN`, `Bidirectional`, `TimeDistributed`, `ConvLSTM2D` |
| `reshaping` | `Flatten`, `Reshape`, `Cropping*`, `ZeroPadding*`, `UpSampling*` |
| `merging` | `Add`, `Concatenate`, `Multiply`, `Average`, `Maximum`, `Minimum`, `Dot` |
| `preprocessing` | `TextVectorization`, `Normalization`, `IntegerLookup`, `StringLookup`, `CategoryEncoding`, `Rescaling` |

## InputSpec

Layers can declare `self.input_spec = InputSpec(ndim=..., dtype=..., shape=...)` to
express constraints on accepted inputs. `InputSpec` validation runs inside `__call__`
before `call()` is invoked and raises `ValueError` with a descriptive message on
mismatch.

## Masking

Keras propagates boolean masks across compatible layers. A layer returns a mask by
overriding `compute_mask(inputs, previous_mask)`. Consumers receive the mask as the
`mask` keyword argument in `call()`. The `Masking` layer creates masks from sentinel
values; `Embedding` can propagate masks via `mask_zero=True`.

## add_loss and Activity Regularization

Inside `call()`, a layer can call `self.add_loss(tensor)` to register auxiliary
scalar losses (for example, activity regularizers or KL terms). These accumulate in
`layer.losses` and are summed into the total loss during `compile`/`fit`.

## Extension Points

- Override `compute_output_spec(self, *args, **kwargs)` to control static shape
  inference for the Functional API without executing actual computation.
- Override `get_config` / `from_config` (classmethod) for serialization.
- Override `quantize(mode)` to add quantization support.
- Implement `save_state` / `load_state` to customize weight serialization.
