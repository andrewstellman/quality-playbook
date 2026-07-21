# Callbacks

## Overview

Callbacks are hooks into the training, evaluation, and prediction lifecycle.
They receive model state and metric logs at well-defined points and can read and
modify training behavior. Every built-in Keras callback is a subclass of
`keras.callbacks.Callback` and lives in `keras.src.callbacks`.

## The Callback Base Class

```python
@keras_export("keras.callbacks.Callback")
class Callback:
    params: dict           # set by the trainer before training begins
    model: keras.Model     # reference to the model being trained

    # Lifecycle hooks (all have default no-op implementations)
    def on_train_begin(self, logs=None): ...
    def on_train_end(self, logs=None): ...

    def on_epoch_begin(self, epoch, logs=None): ...
    def on_epoch_end(self, epoch, logs=None): ...

    def on_train_batch_begin(self, batch, logs=None): ...
    def on_train_batch_end(self, batch, logs=None): ...

    def on_test_begin(self, logs=None): ...
    def on_test_end(self, logs=None): ...
    def on_test_batch_begin(self, batch, logs=None): ...
    def on_test_batch_end(self, batch, logs=None): ...

    def on_predict_begin(self, logs=None): ...
    def on_predict_end(self, logs=None): ...
    def on_predict_batch_begin(self, batch, logs=None): ...
    def on_predict_batch_end(self, batch, logs=None): ...
```

`on_batch_begin` / `on_batch_end` are backwards-compatibility aliases for
`on_train_batch_begin` / `on_train_batch_end`.

The `logs` dict passed to epoch-end hooks contains metric names as keys and their
current values as floats. Validation metrics are prefixed with `val_`.

## model Property Behavior

The `model` property (not just `_model`) has backend-specific logic:
- **PyTorch**: unwraps `DistributedDataParallel` wrappers, returning the underlying
  `keras.Model`.
- **JAX**: calls `model.jax_state_sync()` before returning, ensuring variable values
  are synchronized from device memory before checkpointing or reading weights.

## CallbackList

`CallbackList` manages a list of `Callback` instances and provides the same hook
interface, broadcasting each call to all registered callbacks. The trainer creates a
`CallbackList` in `fit()` / `evaluate()` / `predict()` and fires all hooks through it.

Callbacks can be appended at runtime via `callbacks.append(cb)`. For custom training
loops, the pattern is:

```python
callbacks = keras.callbacks.CallbackList([...])
callbacks.on_train_begin()
for epoch in range(n_epochs):
    callbacks.on_epoch_begin(epoch)
    for step, data in dataset:
        callbacks.on_train_batch_begin(step)
        logs = model.train_step(data)
        callbacks.on_train_batch_end(step, logs)
    callbacks.on_epoch_end(epoch, epoch_logs)
callbacks.on_train_end()
```

## Built-in Callbacks

### ModelCheckpoint

Saves the model (or weights only) at a configurable frequency:

```python
keras.callbacks.ModelCheckpoint(
    filepath="checkpoint.keras",   # may contain {epoch:02d} and {val_loss:.2f} patterns
    monitor="val_loss",
    save_best_only=True,           # only save when monitored metric improves
    save_weights_only=False,
    mode="auto",                   # "auto", "min", or "max"
    save_freq="epoch",             # "epoch" or integer (every N batches)
    verbose=0,
)
```

When `save_weights_only=False`, saves via `model.save(filepath)` using the native
`.keras` format (or `.h5` if the extension is `.h5`).

### EarlyStopping

Halts training when a monitored quantity stops improving:

```python
keras.callbacks.EarlyStopping(
    monitor="val_loss",
    min_delta=0,
    patience=5,
    verbose=0,
    mode="auto",
    baseline=None,
    restore_best_weights=False,   # load weights from the best epoch on stop
    start_from_epoch=0,
)
```

`EarlyStopping` sets `model.stop_training = True` when patience is exhausted,
which causes the training loop to exit cleanly.

### ReduceLROnPlateau

Reduces the learning rate when a metric has stopped improving:

```python
keras.callbacks.ReduceLROnPlateau(
    monitor="val_loss",
    factor=0.1,          # new_lr = lr * factor
    patience=10,
    min_delta=1e-4,
    cooldown=0,          # epochs to wait after reducing before resuming monitoring
    min_lr=0.0,
    verbose=0,
)
```

### TensorBoard

Writes TensorBoard-compatible summary data:

```python
keras.callbacks.TensorBoard(
    log_dir="./logs",
    histogram_freq=0,      # frequency (epochs) to compute weight histograms
    write_graph=True,
    write_images=False,
    update_freq="epoch",   # "batch", "epoch", or integer
    profile_batch=0,
    embeddings_freq=0,
)
```

### CSVLogger

Appends per-epoch metric results to a CSV file. Useful for later analysis without
TensorBoard.

```python
keras.callbacks.CSVLogger("training.log", separator=",", append=False)
```

### LambdaCallback

Creates lightweight callbacks from plain Python functions without subclassing:

```python
keras.callbacks.LambdaCallback(
    on_epoch_begin=None,
    on_epoch_end=lambda epoch, logs: print(epoch, logs),
    on_train_begin=None,
    on_train_end=None,
    on_batch_begin=None,
    on_batch_end=None,
)
```

### BackupAndRestore

Backs up the model at the end of each epoch and restores from that backup if training
is interrupted and resumed:

```python
keras.callbacks.BackupAndRestore(backup_dir="/tmp/backup", save_freq="epoch")
```

### TerminateOnNaN

Terminates training immediately if any loss value becomes `NaN` or `Inf`.

### LearningRateScheduler

Applies a user-provided schedule function to `model.optimizer.learning_rate` at the
start of each epoch:

```python
keras.callbacks.LearningRateScheduler(schedule=lambda epoch, lr: lr * 0.95)
```

### SwapEMAWeights

When an optimizer has `use_ema=True`, swaps EMA weights into the model for
evaluation and swaps back for training. Called automatically by `fit()` when present.

### RemoteMonitor

Posts metrics to a remote HTTP endpoint at the end of each epoch (for experiment
tracking without TensorBoard).

## MonitorCallback Base

`EarlyStopping`, `ReduceLROnPlateau`, and `ModelCheckpoint` all share the
`MonitorCallback` base, which implements:
- `_set_monitor_op()` — resolves `mode="auto"` to `min` or `max` based on metric name.
- `get_monitor_value(logs)` — extracts the monitored quantity from the logs dict with
  an appropriate warning if the key is missing.

## Custom Callbacks

Subclass `keras.callbacks.Callback` and override the hooks you need:

```python
class MyCallback(keras.callbacks.Callback):
    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}
        print(f"Epoch {epoch}: loss = {logs.get('loss'):.4f}")
```

Callbacks have access to `self.model` for reading or modifying model state. Setting
`self.model.stop_training = True` inside any hook terminates the fit loop.

## steps_per_execution Interaction

When `Model.compile(steps_per_execution=N)` is set, `on_train_batch_begin` and
`on_train_batch_end` are called only every `N` batches (once per compiled-function
invocation). This is a performance trade-off for TPU or high-throughput workflows
and affects callbacks that expect per-batch granularity.
