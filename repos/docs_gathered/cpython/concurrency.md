# CPython Concurrency and Parallelism

## Overview

CPython offers three main models for running code concurrently: thread-based parallelism (limited by the GIL in the default build), process-based parallelism (which bypasses the GIL), and cooperative async I/O via `asyncio`. A fourth model — free-threaded Python (the "no-GIL" build, PEP 703) — is available as an experimental build option in recent versions.

## The Global Interpreter Lock (GIL)

In the default CPython build, the GIL is a mutex that ensures only one thread executes Python bytecode at a time within a given interpreter instance. The GIL is released around blocking I/O operations and calls to C extensions that declare they are thread-safe. Consequently:

- **I/O-bound workloads** benefit from threading: while one thread is blocked on a network call, another can run Python bytecode.
- **CPU-bound workloads** do not get parallelism from threads within one interpreter; `multiprocessing` or `ProcessPoolExecutor` are the correct choices there.

The GIL is managed by `Python/ceval_gil.c`. The `sys.getswitchinterval()` / `sys.setswitchinterval(seconds)` API controls the interval between voluntary thread switches (default 5 ms). Extensions that perform long C computations should call `Py_BEGIN_ALLOW_THREADS` / `Py_END_ALLOW_THREADS` to release the GIL around the C work.

## Free-Threaded Build (PEP 703)

The experimental `--disable-gil` configure option builds CPython without the GIL. In this build, reference counts are atomic, and per-object `PyMutex` structs guard mutable state. The garbage collector uses a different algorithm (documented in `InternalDocs/garbage_collector.md`) that pauses other threads during collection. The free-threaded build uses biased reference counting (fast path for the owning thread, atomic for cross-thread operations) to reduce contention overhead. Code that runs correctly under the default build may need explicit locking to be correct under the free-threaded build.

## `threading` — Thread-Based Parallelism

`Lib/threading.py` builds on the lower-level `_thread` extension module. Key classes:

- **`Thread(target, args, kwargs, daemon)`** — represents a single OS thread. `Thread.start()` begins execution; `Thread.join(timeout)` blocks the caller until the thread finishes. Daemon threads do not prevent interpreter shutdown.
- **`Lock` / `RLock`** — mutual exclusion. `RLock` is reentrant (same thread can acquire multiple times without deadlocking). Both support the context manager protocol (`with lock:`).
- **`Condition(lock)`** — adds `wait([timeout])`, `notify()`, `notify_all()` for producer-consumer synchronization.
- **`Semaphore(value)` / `BoundedSemaphore(value)`** — counting semaphores.
- **`Event`** — binary flag with `set()`, `clear()`, `wait([timeout])`.
- **`Barrier(parties)`** — synchronizes a fixed number of threads at a common point.
- **`local()`** — thread-local storage. Attributes set on a `local()` instance are private to the accessing thread.
- **`Timer(interval, function)`** — calls `function` after `interval` seconds in a background thread.

## `concurrent.futures` — High-Level Executor Interface

`concurrent.futures` (PEP 3148) provides a uniform interface for both thread and process pools:

- **`ThreadPoolExecutor(max_workers)`** — submits callables to a thread pool. Each `submit(fn, *args, **kwargs)` returns a `Future`. `map(fn, *iterables, timeout)` applies `fn` lazily.
- **`ProcessPoolExecutor(max_workers, mp_context, initializer, initargs, max_tasks_per_child)`** — same interface but runs each task in a worker process, bypassing the GIL. Worker processes are spawned using `multiprocessing`'s spawn or fork context.
- **`Future`** — represents the result of an asynchronous call. Methods: `result(timeout)` (blocks), `exception(timeout)`, `cancel()`, `done()`, `running()`, `cancelled()`, `add_done_callback(fn)`.
- **`as_completed(futures, timeout)`** — yields futures as they complete, regardless of submission order.
- **`wait(futures, return_when)`** — blocks until conditions are met (`FIRST_COMPLETED`, `FIRST_EXCEPTION`, `ALL_COMPLETED`).

## `multiprocessing` — Process-Based Parallelism

`multiprocessing` (package at `Lib/multiprocessing/`) mirrors the `threading` API but uses OS processes. Key components:

- **`Process(target, args, kwargs, daemon)`** — analogous to `Thread`. `start()`, `join()`, `terminate()`, `kill()`, `is_alive()`.
- **Start methods** — `spawn` (default on Windows and macOS), `fork` (default on Linux, fast but can conflict with threads), `forkserver`. Selected via `set_start_method()` or the `mp_context` argument to `ProcessPoolExecutor`.
- **`Pool(processes, initializer, initargs, maxtasksperchild)`** — a pool of worker processes with `map`, `starmap`, `apply`, `apply_async`, `imap`, `imap_unordered`.
- **Inter-process communication:**
  - `Queue` / `SimpleQueue` — multiprocessing-safe FIFO queues backed by OS pipes.
  - `Pipe()` → `(conn1, conn2)` — pair of `Connection` objects with `send`, `recv`, `poll`.
  - `Value(typecode_or_type, *args)` / `Array(typecode_or_type, size_or_initializer)` — shared memory backed by `mmap`, with optional `Lock`.
  - `Manager()` — proxy-based server that exposes `dict`, `list`, `Namespace`, `Queue`, `Lock`, etc. across processes or even across machines.
- **`multiprocessing.shared_memory`** — direct shared memory blocks with `SharedMemory(name, create, size)` and `ShareableList`.

## `asyncio` — Cooperative Concurrency

`asyncio` (package at `Lib/asyncio/`) implements an event loop for cooperative multitasking using Python's coroutine mechanism (`async def`, `await`, `async for`, `async with`).

### Event Loop

`asyncio.run(coro)` creates an event loop, runs a coroutine to completion, and closes the loop. `asyncio.get_running_loop()` returns the current loop from within a coroutine. The loop dispatches I/O readiness events, timers, and scheduled callbacks.

### Tasks and Coroutines

- **Coroutine** — `async def` function; calling it returns a coroutine object, not a result. Must be `await`ed or wrapped in a `Task`.
- **`asyncio.Task`** — wraps a coroutine so it runs concurrently with other tasks on the same event loop. Created via `asyncio.create_task(coro)`.
- **`asyncio.gather(*coros_or_futures)`** — runs multiple awaitables concurrently, returns their results as a list.
- **`asyncio.wait_for(aw, timeout)`** — cancels the awaitable if it does not complete within `timeout` seconds and raises `TimeoutError`.
- **`asyncio.shield(aw)`** — protects an awaitable from cancellation.

### Synchronization Primitives

`asyncio.Lock`, `asyncio.Event`, `asyncio.Condition`, `asyncio.Semaphore`, `asyncio.BoundedSemaphore`, `asyncio.Queue`, `asyncio.PriorityQueue`, `asyncio.LifoQueue` — analogues of the threading primitives, but designed for coroutines and not thread-safe.

### Streams

`asyncio.StreamReader` / `asyncio.StreamWriter` provide a buffered, high-level API for TCP connections. `asyncio.open_connection` and `asyncio.start_server` are the primary constructors.

## `queue` Module

`queue.Queue`, `queue.LifoQueue`, `queue.PriorityQueue` — thread-safe queues for producer-consumer patterns between `threading.Thread` instances. Not intended for use between coroutines (use `asyncio.Queue` for that).

## `contextvars` — Context Variables

`contextvars.ContextVar` provides per-context variables that are copied automatically when a new `Task` is created in `asyncio`, avoiding the need to thread contextual data through every function call. Used by `decimal`'s thread-local context, structured logging, and request-scoped state in async servers.
