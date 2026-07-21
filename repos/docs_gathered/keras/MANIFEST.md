# Keras Documentation Manifest

| File | Description |
|---|---|
| `models_and_layers.md` | The `Layer` and `Model` base classes, the three model construction styles (Functional, subclassing, Sequential), the built-in layer catalogue, and extension points for custom layers. |
| `training_loop.md` | The `compile`/`fit`/`evaluate`/`predict` API, the `DataAdapter` subsystem, backend-specific trainer implementations (JAX, TF, Torch), `train_step` overrides, and JIT compilation semantics. |
| `backend_abstraction.md` | Backend selection, the `keras.src.backend` package structure, `KerasTensor`, the `Variable` class, the `config.py` configuration surface, `StatelessScope`, `SymbolicScope`, dtype policies, and `name_scope`. |
| `data_pipeline.md` | Dataset loading utilities (`image_dataset_from_directory`, text, audio, timeseries), the `PyDataset` API for parallel data generation, the `DataAdapter` protocol, and preprocessing layers (text, image, normalization, audio spectrogram). |
| `serialization.md` | The `.keras` native format, HDF5 legacy format, `save_model`/`load_model` entry points, the `serialization_lib` object–JSON round-trip, the `KerasSaveable` base, custom object registration, and the `get_config`/`from_config` contract. |
| `callbacks.md` | The `Callback` base class and all lifecycle hooks, `CallbackList`, and every built-in callback (`ModelCheckpoint`, `EarlyStopping`, `ReduceLROnPlateau`, `TensorBoard`, `CSVLogger`, `LambdaCallback`, `BackupAndRestore`, `TerminateOnNaN`, `LearningRateScheduler`, `SwapEMAWeights`, `RemoteMonitor`). |
| `optimizers_and_metrics.md` | The `BaseOptimizer` class, all built-in optimizers, `LossScaleOptimizer`, learning-rate schedules, the `Metric` accumulation contract, all built-in metric families, the `Loss` base class with reduction modes, all built-in loss classes, and how `CompileLoss`/`CompileMetrics` wrap them inside the trainer. |
| `ops_and_functional_core.md` | The `Operation` class, `Node`/computation-graph wiring, `Function`, and all `keras.ops` namespaces (`numpy`, `nn`, `image`, `linalg`, `math`, `core`, `einops`) including functional control-flow ops and rematerialization. |
| `distribution_and_build.md` | The distributed-training API (`DeviceMesh`, `TensorLayout`, `DataParallel`, `ModelParallel`, multi-host initialization), the `pyproject.toml` build system, `pip_build.py`/`api_gen.py` tooling, the `@keras_export` public-API mechanism, test conventions, code-style tooling, and the docstring schema. |
