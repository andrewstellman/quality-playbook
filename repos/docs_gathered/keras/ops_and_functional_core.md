# Ops and Functional Core

## Overview

`keras.ops` is a backend-agnostic tensor operation library. It provides NumPy-style
mathematical operations, neural-network primitives, image ops, and linear algebra
routines — all dispatching to the active backend (JAX, TF, PyTorch, or NumPy) at
call time, while supporting symbolic execution for the Functional API.

## The Operation Class

`keras.Operation` (`keras.src.ops.operation`) is the root of the computation graph.
`Layer` inherits from `Operation`.

```python
class Operation(KerasSaveable):
    def __call__(self, *args, **kwargs):
        if any_symbolic_tensors(args, kwargs):
            return self.symbolic_call(*args, **kwargs)
        else:
            return self.call(*args, **kwargs)   # or quantized_call / rematerialized_call

    def symbolic_call(self, *args, **kwargs):
        outputs = self.compute_output_spec(*args, **kwargs)   # shape/dtype inference
        Node(operation=self, call_args=args, call_kwargs=kwargs, outputs=outputs)
        return outputs

    def call(self, *args, **kwargs): raise NotImplementedError
    def compute_output_spec(self, *args, **kwargs): ...  # default: traces call() on KerasTensors
```

When any argument is a `KerasTensor`, `__call__` routes to `symbolic_call`, which
runs `compute_output_spec` and records a `Node` in the computation graph. In eager
mode (real tensors), it routes directly to `call()` (or `quantized_call` / `rematerialized_call`
when those modes are active).

## Node and Computation Graph

`Node` (`keras.src.ops.node`) wires operations together:
- `node.operation` — the `Operation` that produced this node.
- `node.call_args`, `node.call_kwargs` — the inputs to this call.
- `node.outputs` — the `KerasTensor` outputs.

Each output tensor carries a `._keras_history` attribute pointing back to its `Node`.
The `Functional` model traverses these links (via `_build_map`) to reconstruct the
computation graph from inputs to outputs.

## Function (keras.ops.function)

`Function` is the lower-level graph container underlying `Functional` models:

```python
class Function(Operation):
    def __init__(self, inputs, outputs, name=None): ...
    def call(self, inputs): ...                # eager: runs the graph
    def compute_output_spec(self, inputs): ... # symbolic: propagates through the graph
```

`_build_map(inputs, outputs)` performs a topological traversal from outputs back to
inputs, collecting all nodes in order. `Function.call` iterates these nodes in
forward order, feeding real tensors through each `Operation.call`.

## keras.ops Namespaces

Operations are grouped into sub-namespaces, all exported via `keras.ops.*`:

### numpy (keras.ops.*)

NumPy-compatible element-wise and reduction ops:

```python
keras.ops.add, subtract, multiply, divide, matmul
keras.ops.sum, mean, max, min, prod, std, var
keras.ops.reshape, transpose, expand_dims, squeeze
keras.ops.concatenate, stack, split, tile, repeat
keras.ops.cast, zeros, ones, zeros_like, ones_like, eye
keras.ops.where, select, gather, scatter_update
keras.ops.sort, argsort, argmax, argmin
keras.ops.clip, abs, sign, floor, ceil, round
keras.ops.exp, log, log2, log10, sqrt, power
keras.ops.sin, cos, tan, arcsin, arccos, arctan, arctan2
```

### nn (keras.ops.nn)

Neural-network-specific primitives:

```python
keras.ops.nn.relu, relu6, leaky_relu, elu, selu, gelu, swish, sigmoid
keras.ops.nn.softmax, log_softmax, softplus, softsign
keras.ops.nn.conv(inputs, kernel, strides, padding, data_format, dilation_rate)
keras.ops.nn.depthwise_conv, separable_conv, conv_transpose
keras.ops.nn.max_pool, average_pool
keras.ops.nn.batch_normalization
keras.ops.nn.moments(x, axes, keepdims)    # mean and variance
keras.ops.nn.dot_product_attention(query, key, value, bias=None, mask=None, scale=None)
keras.ops.nn.multi_head_attention(...)
```

### image (keras.ops.image)

Image manipulation ops:

```python
keras.ops.image.resize(images, size, method="bilinear", data_format="channels_last")
keras.ops.image.rgb_to_grayscale, rgb_to_hsv, hsv_to_rgb
keras.ops.image.pad_images, crop_images, flip_images, affine_transform
keras.ops.image.extract_patches, map_coordinates
```

### linalg (keras.ops.linalg)

Linear algebra:

```python
keras.ops.linalg.cholesky, det, eig, eigh, inv, lstsq, lu, norm, qr, solve, svd
```

### math (keras.ops.math)

Extended math:

```python
keras.ops.math.segment_sum, segment_max, top_k, in_top_k
keras.ops.math.logsumexp, extract_sequences, fft, fft2, ifft2, rfft, irfft
keras.ops.math.stft, istft
```

### core (keras.ops.core)

Functional control flow and utility:

```python
keras.ops.map(f, xs)              # map f over leading axis of xs
keras.ops.scan(f, init, xs)       # left-to-right reduction with carry
keras.ops.fori_loop(lower, upper, body_fn, init_val)
keras.ops.while_loop(cond_fn, body_fn, loop_vars)
keras.ops.cond(pred, true_fn, false_fn)
keras.ops.vectorized_map(f, xs)   # vmap analog
keras.ops.cast(x, dtype)
keras.ops.convert_to_tensor(x, dtype)
keras.ops.convert_to_numpy(x)
keras.ops.is_tensor(x)
keras.ops.shape(x)
keras.ops.slice(x, start_indices, shape)
keras.ops.slice_update(x, start_indices, update)
keras.ops.unstack(x, axis=0)
```

`map`, `scan`, `fori_loop`, `while_loop`, and `cond` have backend-native
implementations (e.g., `jax.lax.scan`, `tf.while_loop`, PyTorch `for`-loop
fallback) with symbolic counterparts for shape inference.

### einops (keras.ops.einops)

`keras.ops.einops_rearrange(x, pattern)` and `keras.ops.einops_reduce(x, pattern, reduction)` —
thin wrappers around the `einops` library providing backend-agnostic tensor
rearrangement.

## SymbolicArguments

`keras.src.ops.symbolic_arguments.SymbolicArguments` tracks how real arguments
map to `KerasTensor` slots in a call signature. It is used by `Function` to
reconstruct how to feed real tensors through the recorded graph at call time.

## Static Shape Inference

`compute_output_spec` is the shape/dtype inference path. The default implementation
in `Operation` runs `call()` on the `KerasTensor` inputs inside a
`backend.KerasBackend` that returns `KerasTensor` outputs. Operations that need
exact shape logic (e.g., `Reshape`, `Concatenate`) override `compute_output_spec`
directly.

## Rematerialization / Gradient Checkpointing

`keras.src.backend.common.remat` provides `get_current_remat_mode()` and a
`rematerialized_call` wrapper. When a remat mode is active (set via
`keras.remat` context or layer attribute), `Operation.__call__` wraps `call()` with
the backend's gradient checkpointing primitive (`jax.checkpoint`, `tf.recompute_grad`,
etc.) to trade compute for memory.
