# MLlib Overview

MLlib is Spark's machine-learning library. There are two coexisting API surfaces:

- `org.apache.spark.ml` — the DataFrame-based API. This is the recommended, actively developed surface.
- `org.apache.spark.mllib` — the older RDD-based API, kept for compatibility and for algorithms not yet ported to the DataFrame API.

The `mllib-local/` module provides the linear-algebra types (`Vector`, `Matrix`) and core math operations without depending on Spark's distributed runtime, so they can be used inside model objects on a single machine. The full `mllib/` module depends on `spark-core` and `spark-sql`.

## Pipeline abstraction (spark.ml)

The DataFrame-based API models ML workflows as composable pipelines built from three core abstractions, defined in `mllib/src/main/scala/org/apache/spark/ml/`:

- **`Transformer`** — converts a `DataFrame` to another `DataFrame`. Examples: `Tokenizer`, `HashingTF`, `StandardScalerModel`, any fitted `Model`.
- **`Estimator`** — learns from a `DataFrame` and produces a `Model` (which is a `Transformer`). Examples: `LogisticRegression`, `RandomForestClassifier`, `KMeans`.
- **`Pipeline`** — an `Estimator` whose stages are an ordered sequence of `Transformer`s and `Estimator`s. `Pipeline.fit(df)` runs each stage in turn; the result is a `PipelineModel` (a `Transformer`) that reproduces the same chain on new data.

`PipelineStage` is the common parent of `Transformer` and `Estimator`. Every stage exposes a `transformSchema(StructType)` method so that the pipeline can validate schemas without running the workload.

## Params

`Param[T]` and `Params` (in `org.apache.spark.ml.param`) provide a typed, self-documenting configuration system for ML stages. Each algorithm declares its hyperparameters as `Param`s with a name, doc string, and optional validator. `ParamMap` holds values; `Params.set(param, value)` and the generated `setMaxIter(...)` style setters are the usual entry points.

Params support default values, parent ownership (so a value set on one stage's param doesn't leak to another), and a `copy(extra)` semantic that lets pipelines override params per-stage at fit time.

## Algorithm families

Inside `spark.ml`, algorithms are organized by task: `classification/` (`LogisticRegression`, decision-tree and random-forest classifiers, `GBTClassifier`, `LinearSVC`, `NaiveBayes`, `MultilayerPerceptronClassifier`, `OneVsRest`), `regression/` (`LinearRegression`, tree and ensemble regressors, `IsotonicRegression`, `AFTSurvivalRegression`, `GeneralizedLinearRegression`), `clustering/` (`KMeans`, `BisectingKMeans`, `GaussianMixture`, `LDA`, `PowerIterationClustering`), `recommendation/` (`ALS`), `feature/` (preprocessing transformers like `VectorAssembler`, `StandardScaler`, `OneHotEncoder`, `StringIndexer`, `Tokenizer`, `CountVectorizer`, `IDF`, `Word2Vec`, `PCA`, `Bucketizer`, `Imputer`), `evaluation/` (per-task evaluators), `tuning/` (`CrossValidator`, `TrainValidationSplit`, `ParamGridBuilder`), `fpm/` (frequent pattern mining: `FPGrowth`, `PrefixSpan`), `stat/` (`Correlation`, `ChiSquareTest`, `Summarizer`), and `tree/` (shared decision-tree code).

## Linear algebra

`org.apache.spark.ml.linalg` provides the public `Vector` (`DenseVector`, `SparseVector`) and `Matrix` (`DenseMatrix`, `SparseMatrix`) types. The `mllib-local` module backs these with BLAS calls; native BLAS (OpenBLAS, MKL) is used when available through `dev.ludovic.netlib` bindings, with a pure-Java fallback otherwise. `org.apache.spark.mllib.linalg` is the older, RDD-API counterpart with conversion methods to the new types.

## Distributed-vs-local responsibilities

Training is distributed: `Dataset` rows are partitioned across executors, each algorithm implements an iterative aggregation (typically via tree-aggregate or LBFGS) on top of RDD operations, and the driver gathers and updates model parameters. Inference is per-row and runs as a normal `Transformer.transform(df)`, which is just a Spark SQL projection — usable on streaming DataFrames too.

## Persistence

ML models implement `MLWritable` / `MLReadable`. `model.write.save(path)` serializes the model and its params to a directory with a `metadata/` JSON manifest plus algorithm-specific data files (Parquet for coefficients, JSON for params, etc.). `PipelineModel.load(path)` rehydrates an entire pipeline.

This format is stable across compatible Spark versions and is the standard way to ship trained models from a training job to a serving job.

## Instrumentation and events

The `events.scala` file under `mllib/src/main/scala/org/apache/spark/ml/` defines `MLEvent` and `MLListener` for observability. Fit, transform, save, and load operations emit start/end events; the `Instrumentation` helper threads instrumentation IDs through training so log messages and listener events can be correlated.

## Python and R bindings

`pyspark.ml` mirrors the Scala API. Each Python class wraps a JVM-side counterpart through Py4J in classic mode or through Spark Connect RPCs in Connect mode. `SparkR`'s `spark.lda`, `spark.glm`, `spark.kmeans`, etc., expose a subset of the same models with R-friendly formula syntax.
