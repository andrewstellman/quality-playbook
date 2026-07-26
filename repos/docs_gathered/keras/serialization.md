# Serialization and Model Saving

## Overview

Keras 3 has a first-class native save format (`.keras`), legacy HDF5 support
(`.h5` / `.hdf5`), and a `SavedModel`-style export path for deployment frameworks.
The saving system is split into two layers: the high-level API (`saving_api.py`) that
routes to the right format based on the file extension, and the low-level library
(`saving_lib.py`) that performs actual serialization.

## The .keras Format

The native format is a ZIP archive with the following structure:

```
model.keras (ZIP)
    config.json          # JSON-serialized architecture and hyperparameters
    metadata.json        # Keras version, date, backend info
    model.weights.h5     # HDF5 file with all variable values
    assets/              # optional directory for vocabulary files etc.
```

Save and load:

```python
model.save("model.keras")                            # or keras.saving.save_model(model, path)
loaded = keras.saving.load_model("model.keras")

# Unzipped form (for Hugging Face Hub uploads)
model.save("hf://username/repo-name")               # zipped=False is the default for hf:// paths
```

`saving_lib.save_model` drives the process:
1. Serializes the architecture via `serialize_keras_object(model)` → `config.json`.
2. Writes `metadata.json` with the Keras version and timestamp.
3. Visits all `KerasSaveable` objects discoverable through `dir(model)` and calls
   their `save_state(store, options)` methods, writing weights to `model.weights.h5`.

`saving_lib.load_model` reverses the process: deserializes config → reconstructs
the object graph via `deserialize_keras_object` → calls `load_state` on each saveable.

## HDF5 Legacy Format

Files with `.h5` or `.hdf5` extensions are handled by `legacy_h5_format`. This path
is considered legacy; the native `.keras` format is preferred. A deprecation warning
is emitted when saving to HDF5 via `model.save()`.

## keras.saving.save_model / load_model

Public entry points (exported at both `keras.saving.*` and `keras.models.*`):

```python
keras.saving.save_model(model, filepath, overwrite=True, zipped=None)
keras.saving.load_model(filepath, custom_objects=None, compile=True, safe_mode=True)
```

`save_model` raises `ValueError` if the extension is unrecognized. `load_model`
accepts:
- `custom_objects`: dict mapping string names to classes/functions for custom components.
- `compile`: whether to re-compile the loaded model to the saved optimizer/loss/metrics.
- `safe_mode`: when `True` (the default), lambda deserialization is blocked. Call
  `keras.config.enable_unsafe_deserialization()` to allow lambdas globally.

## Serialization Library (serialization_lib.py)

`keras.src.saving.serialization_lib` provides the object → JSON round-trip:

```python
serialize_keras_object(obj)   -> dict   # {"class_name": ..., "config": ..., "module": ...}
deserialize_keras_object(config, custom_objects=None) -> obj
```

The config dict has the form:

```json
{
  "class_name": "keras>Dense",
  "config": {"units": 32, "activation": "relu", ...},
  "module": "keras.layers",
  "registered_name": "Dense"
}
```

Built-in Keras objects are identified by their registration name, registered via the
`@keras_export` decorator. Custom objects are resolved via:
1. The `custom_objects` argument to `load_model`.
2. The `keras.saving.custom_object_scope()` context manager.
3. The `keras.saving.register_keras_serializable` decorator.

`BUILTIN_MODULES` is a frozenset of the Keras modules whose members can be
deserialized by short name (`"activations"`, `"constraints"`, `"initializers"`,
`"losses"`, `"metrics"`, `"optimizers"`, `"regularizers"`).

`SafeModeScope` and `in_safe_mode()` propagate the safe-mode flag through nested
deserialization calls using `global_state`.

`ObjectSharingScope` enables deduplication of shared sub-objects (e.g., a shared
embedding layer in a Siamese network) across serialization and deserialization via
an `id → obj` map stored in `global_state`.

## KerasSaveable

`KerasSaveable` (`keras.src.saving.keras_saveable`) is the abstract base for all
saveable objects (`Layer`, `Metric`, `Optimizer`, `Loss`). It provides:
- `_obj_type()` — must be overridden by subclasses to return a string type identifier.
- `__reduce__` — enables `pickle` support by serializing through `saving_lib`; not
  recommended as a primary serialization path, but useful for distributed computing
  frameworks.
- `save_state(store, options)` / `load_state(store, options)` — override in subclasses
  to customize how state is written/read.

## object_registration.py

`keras.src.saving.object_registration` maintains a bidirectional registry:
- `REGISTERED_NAMES_TO_OBJS` — string name → class.
- `REGISTERED_OBJS_TO_NAMES` — class → canonical string name.

The `@keras_export("keras.layers.Dense")` decorator calls
`register_internal_serializable` to populate both dicts. Lookup functions:
- `get_symbol_from_name(name)` — returns the class or `None`.
- `get_name_from_symbol(cls)` — returns the canonical name or `None`.

`@keras.saving.register_keras_serializable(package)` lets user-defined classes join
the registry without being part of the Keras source tree.

## get_config / from_config Contract

Every layer / metric / optimizer / loss intended for serialization must implement:

```python
def get_config(self) -> dict:
    # Return all constructor args needed to recreate the object.
    config = super().get_config()
    config.update({"units": self.units, "activation": self.activation})
    return config

@classmethod
def from_config(cls, config):
    return cls(**config)
```

If constructor argument names differ from the config keys, `from_config` must be
overridden to perform the mapping.

## Model Weights API

```python
model.save_weights("weights.weights.h5")   # saves only variable values
model.load_weights("weights.weights.h5")   # loads into matching variable names
```

Weight files use HDF5 keyed by the variable's `path` attribute (set by the
name-scope system). Loading by name tolerates architecture differences as long as
the paths match.

## Export for Deployment

`model.export("path/to/exported")` produces a framework-compatible `SavedModel`
or TFLite artifact via `keras.src.export`. This path is separate from `.keras`
saving and is intended for TFLite / TF Serving integration.

## Hugging Face Hub Integration

When `filepath` starts with `hf://`, `saving_lib` uses `huggingface_hub` (if
installed) to upload the unzipped format. A model card template is generated
automatically in this path. The format defaults to `zipped=False` for Hub uploads
to allow diffing individual files.
