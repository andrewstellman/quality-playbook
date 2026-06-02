# Scheduler

Spark schedules work in two layers. The high-level `DAGScheduler` turns RDD lineage into stages and submits each stage as a `TaskSet`. The low-level `TaskScheduler` distributes tasks across executors and reacts to their results. Both live in `core/src/main/scala/org/apache/spark/scheduler/`.

## DAGScheduler

`DAGScheduler` is created in `SparkContext` and runs an event-loop thread. When a user action calls `SparkContext.runJob`, the scheduler walks the RDD lineage backward (recording shuffle dependencies as stage boundaries), builds a DAG of `Stage` objects (`ResultStage` for the final stage, `ShuffleMapStage` for each shuffle boundary), computes preferred locations from cache state and HDFS block locations, submits a `TaskSet` for each ready stage, and receives `CompletionEvent`s back through its event queue.

Stage retry handles two common failure modes: shuffle output files lost (executor died after writing them — the corresponding `ShuffleMapStage` is resubmitted), and per-task failures within a stage (the `TaskScheduler` retries; if a task fails too many times the stage aborts and the job fails). The scheduler also implements barrier execution mode for gang-scheduled MPI-style workloads, where tasks in a barrier stage either all launch simultaneously or none do.

## TaskScheduler and SchedulerBackend

`TaskScheduler` (interface) and `TaskSchedulerImpl` (default) accept `TaskSet`s from the DAGScheduler and dispatch their tasks to executors. They maintain a queue of pending `TaskSetManager`s (one per active stage), offer pending tasks to executors as resources become available, order TaskSets according to a `SchedulingMode` (FIFO or FAIR) implemented by a `Pool`/`Schedulable` tree, track per-executor health through `HealthTracker`, and support speculation (launching duplicate copies of slow tasks). The per-stage `TaskSetManager` tracks locality preferences (PROCESS_LOCAL, NODE_LOCAL, RACK_LOCAL, ANY) and delays task launches up to `spark.locality.wait` so local-preferred tasks get their preferred executors when possible.

`SchedulerBackend` is the cluster-manager-specific adapter: it accepts executor offers from the cluster manager, notifies the `TaskScheduler` so it can match tasks to offers, sends task launch messages over the RPC layer, and forwards executor lost / decommissioned events. Implementations include `StandaloneSchedulerBackend`, `KubernetesClusterSchedulerBackend`, `YarnClusterSchedulerBackend`, and `LocalSchedulerBackend`; all share `CoarseGrainedSchedulerBackend` as a common base.

## Tasks and TaskContext

A `Task` is the smallest unit of work the scheduler dispatches. There are two concrete subclasses:

- `ShuffleMapTask` computes a partition and writes shuffle output for the next stage.
- `ResultTask` computes a partition and sends its result back to the driver.

When a task starts on an executor, it receives a `TaskContext` describing its `stageId`, `partitionId`, `attemptNumber`, and TaskMetrics handle. User code (and Spark internals) can register completion / failure callbacks on the `TaskContext`. `BarrierTaskContext` extends this with `barrier()` synchronization for barrier stages.

## Job scheduling within an application

Inside a single application, multiple jobs (often from concurrent threads on the driver) compete for executor slots. The scheduling mode is controlled by `spark.scheduler.mode`:

- **FIFO** (default): jobs are served in submit order.
- **FAIR**: jobs are placed in pools and scheduled round-robin; pools have configurable weights and minimum share.

Fair pools are configured via an XML file referenced by `spark.scheduler.allocation.file`.

## Listener bus

`LiveListenerBus` is the publish/subscribe channel for scheduler events. Anything that needs to react to job/stage/task lifecycle (the UI, the event logger, the metrics system, user-registered `SparkListener` implementations) subscribes here. Events include `SparkListenerJobStart`, `SparkListenerStageSubmitted`, `SparkListenerTaskEnd`, `SparkListenerExecutorAdded`, and many more. The listener bus is asynchronous and per-listener; slow listeners back-pressure their own queue without blocking others.

## Resource profiles

Tasks can request distinct CPU, memory, and accelerator (GPU/FPGA) profiles via `ResourceProfile`. The scheduler matches tasks against executor `ResourceProfile`s; cluster managers that support heterogeneous executors (Kubernetes, YARN) can launch the right shape on demand.

## Output commit coordination

`OutputCommitCoordinator` arbitrates when speculative duplicate tasks both attempt to write the same output file. The driver authorizes one attempt and rejects the other so that final output is committed exactly once.
