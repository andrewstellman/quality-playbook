# Data Pipeline and Preprocessing

## Overview

Keras provides utilities for loading datasets from disk, building preprocessing
pipelines as part of the model graph, and a `PyDataset` API for generating batches
in Python with optional parallelism. The framework is backend-agnostic at the
data-loading level: the same model can consume NumPy arrays, `tf.data.Dataset`
pipelines, or PyTorch `DataLoader` objects.

## Dataset Loading Utilities

### Image Datasets

`keras.utils.image_dataset_from_directory` generates batches from a directory tree
organized by class:

```
main_directory/
    class_a/
        image1.jpg
    class_b/
        image2.png
```

```python
train_ds = keras.utils.image_dataset_from_directory(
    "main_directory",
    labels="inferred",          # or a list of integer labels
    label_mode="int",           # "int", "categorical", "binary"
    color_mode="rgb",           # "rgb", "rgba", "grayscale"
    batch_size=32,
    image_size=(256, 256),
    shuffle=True,
    seed=42,
    validation_split=0.2,
    subset="training",          # "training" or "validation"
    interpolation="bilinear",
    data_format=None,           # defaults to keras.backend.image_data_format()
    format="tf",                # "tf" returns tf.data.Dataset; "grain" returns grain.IterDataset
)
```

Supported formats: `.bmp`, `.gif`, `.jpeg`, `.jpg`, `.png`. Animated GIFs are
truncated to the first frame.

### Text Datasets

`keras.utils.text_dataset_from_directory` mirrors the image API but reads `.txt`
files. It returns batches of raw string tensors paired with integer class labels.

### Audio and Timeseries

- `keras.utils.audio_dataset_from_directory` — loads audio files, applies optional
  resampling.
- `keras.utils.timeseries_dataset_from_array` — windows a 1-D or 2-D array into
  overlapping sequences of configurable length and stride.

## PyDataset (keras.utils.PyDataset)

`PyDataset` (also exported as `keras.utils.Sequence` for backwards compatibility)
is the base class for Python-defined datasets with optional worker parallelism:

```python
class MyDataset(keras.utils.PyDataset):
    def __init__(self, x, y, batch_size, **kwargs):
        super().__init__(**kwargs)
        self.x, self.y = x, y
        self.batch_size = batch_size

    def __len__(self):
        return math.ceil(len(self.x) / self.batch_size)

    def __getitem__(self, idx):
        lo = idx * self.batch_size
        hi = min(lo + self.batch_size, len(self.x))
        return self.x[lo:hi], self.y[lo:hi]
```

Constructor arguments:

| Argument | Default | Purpose |
|---|---|---|
| `workers` | `1` | Number of threads or processes for parallel `__getitem__` calls |
| `use_multiprocessing` | `False` | Use `multiprocessing` instead of threading |
| `max_queue_size` | `10` | Upper bound on the prefetch queue |

When `use_multiprocessing=True`, the dataset object must be picklable. The
`PyDatasetAdapter` starts the worker pool during `fit()` and shuts it down
cleanly via `weakref` finalizers.

`on_epoch_begin()` and `on_epoch_end()` are optional callbacks invoked by the
adapter before and after each epoch, allowing the dataset to shuffle indices or
perform other per-epoch mutations.

## DataAdapter Protocol

`DataAdapter` (`keras.src.trainers.data_adapters.data_adapter.DataAdapter`) defines
the interface that all adapters implement:

```python
class DataAdapter:
    def get_numpy_iterator(self): ...   # yields NumPy arrays
    def get_tf_dataset(self): ...       # returns tf.data.Dataset
    def get_jax_iterator(self): ...     # yields JAX-compatible arrays
    def get_torch_dataloader(self): ... # returns torch.utils.data.DataLoader

    @property
    def builtin_prefetch(self) -> bool: ...  # True if adapter handles prefetch internally
    @property
    def num_batches(self): ...          # int or None
    @property
    def batch_size(self): ...           # int or None
    @property
    def has_partial_batch(self) -> bool: ...
    @property
    def partial_batch_size(self): ...
```

The `EpochIterator` selects the appropriate iterator method based on the active backend.

## Preprocessing Layers

Keras exposes preprocessing as layers (`keras.layers.preprocessing.*`) so that
normalization, tokenization, or image augmentation can be embedded directly in the
model graph. Preprocessing layers have a `DataLayer` base that separates
"compute from the model's perspective" from "adapt from a dataset".

### TextVectorization

Tokenizes and optionally encodes text sequences:

```python
vectorizer = keras.layers.TextVectorization(
    max_tokens=10000,
    output_mode="int",    # "int", "multi_hot", "count", "tf_idf"
    output_sequence_length=100,
)
vectorizer.adapt(text_dataset)   # builds vocabulary from data
```

### Normalization

Computes feature-wise mean and variance from data and applies standardization:

```python
norm = keras.layers.Normalization(axis=-1)
norm.adapt(training_data)
```

### IntegerLookup / StringLookup / CategoryEncoding

Vocabulary-table layers for integer and string categorical features:
- `IntegerLookup` / `StringLookup` map tokens to integer indices, with optional OOV
  buckets and inversion support.
- `CategoryEncoding` converts integer indices to one-hot, multi-hot, or count encodings.

### Image Preprocessing

`keras.layers.Rescaling(scale, offset)` rescales pixel values (e.g., `1./255`).

The `image_preprocessing` sub-package provides augmentation layers
(`RandomCrop`, `RandomFlip`, `RandomRotation`, `RandomBrightness`, etc.) that
derive from `BaseImagePreprocessingLayer`. The base class handles:
- A `factor` argument (scalar or two-tuple `[lower, upper]`) for randomized strength.
- `bounding_box_format` for object-detection compatible augmentation.
- Separate `transform_images`, `transform_labels`, `transform_bounding_boxes`, and
  `transform_segmentation_masks` methods that subclasses implement.

Augmentation layers accept a `training` argument to `call()` and apply random
transformations only when `training=True`.

### Mel Spectrogram and STFT Spectrogram

`keras.layers.MelSpectrogram` and `keras.layers.STFTSpectrogram` convert raw waveform
tensors to frequency-domain representations suitable for audio classification tasks.

### FeatureSpace

`keras.layers.FeatureSpace` provides a high-level API for combining heterogeneous
tabular features (categorical, numerical, cross-features) into a single dense
representation, built on top of the lookup and encoding layers.

## Backend Compatibility

The framework normalizes data across backends before feeding it to the model:
- NumPy arrays are cast to the appropriate framework tensor type inside the adapter.
- `tf.data.Dataset` can be consumed on any backend — the TF dataset adapter
  iterates it and converts outputs to the active backend's array type.
- PyTorch `DataLoader` outputs are consumed through the Torch adapter.

Users do not need separate pipelines per backend; the adapter layer abstracts
the conversion automatically.
