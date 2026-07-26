# CPython Object Model and Runtime

## Overview

CPython is the reference implementation of Python, at this version targeting Python 3.15.0 alpha 0. The interpreter is written in C11 and uses a layered architecture that connects a bytecode compiler, an adaptive interpreter, an optional JIT tier, a garbage collector, and a rich standard library. The project's design philosophy prioritizes clarity of semantics, a stable public C API surface, and portability across POSIX, Windows, macOS, iOS, Android, Emscripten, and WASI targets.

## The Object Foundation

Every Python value — integers, strings, lists, functions, types, and modules — is a heap-allocated `PyObject`. The `PyObject` struct (defined in `Include/object.h`) carries two mandatory fields that open every object in memory:

- `ob_refcnt` — the reference count used by the primary memory management scheme.
- `ob_type` — a pointer to the object's `PyTypeObject`, which determines all operations available on that object.

Types themselves are `PyObject` instances whose `ob_type` points to `PyType_Type`, forming a closed tower: every object has a type, and every type is an object.

The macro `PyObject_HEAD` expands to embed this two-field prefix at the top of every concrete object struct, so any `PyObject *` pointer can be safely cast to the concrete type and back. Variable-length objects (strings, tuples, lists) additionally use `PyObject_VAR_HEAD`, which appends an `ob_size` field counting the number of contained items.

## Object Memory Layout

Each object begins with an optional **pre-header** (used by the cycle garbage collector and, in recent versions, by the attribute system) followed by the standard `PyObject_HEAD` fields, followed by type-specific data. The pre-header contains pointers for weak references and the object's attribute dictionary (or an inline values array for objects whose class has `tp_itemsize == 0`). The exact layout varies slightly between the default (GIL) build and the free-threaded build; `Objects/object_layout.md` in the source tree documents each version's structure in detail.

## The Type Slot System

A `PyTypeObject` (in `Include/cpython/object.h`) is a large C struct whose fields are function pointers called **slots**. Slots are organized into protocol groups:

- `tp_as_number` — arithmetic operations (`nb_add`, `nb_multiply`, `nb_bool`, etc.)
- `tp_as_sequence` — sequence operations (`sq_length`, `sq_item`, `sq_concat`, etc.)
- `tp_as_mapping` — mapping operations (`mp_length`, `mp_subscript`, `mp_ass_subscript`)
- `tp_as_buffer` — the buffer protocol for zero-copy data sharing
- Direct slots on `PyTypeObject` itself: `tp_repr`, `tp_hash`, `tp_call`, `tp_richcompare`, `tp_iter`, `tp_iternext`, `tp_init`, `tp_new`, `tp_dealloc`, `tp_traverse`, `tp_clear`, etc.

When a slot is `NULL`, the corresponding operation is unsupported for that type. The abstract object layer (`Include/abstract.h`, `Objects/abstract.c`) provides the canonical C API — functions like `PyObject_GetAttr`, `PyObject_Call`, `PyNumber_Add`, `PySequence_GetItem` — that check these slots and dispatch accordingly. This is the preferred interface for C extension code that wants to operate on objects generically rather than checking concrete types.

## Identity, Type, and Value

The language reference establishes three stable properties for every live object:

- **Identity** — unique for the object's lifetime; `id(x)` returns the memory address in CPython.
- **Type** — fixed at creation; `type(x)` returns the `PyTypeObject` as a Python object.
- **Value** — may or may not change depending on mutability. Immutable types (int, str, tuple, frozenset, bytes) cannot be modified after creation. Mutable types (list, dict, set) can.

## Mutability and Special Cases

Immutability for built-in types is enforced structurally: the type's slots for item assignment (`sq_ass_item`, `mp_ass_subscript`) are simply `NULL`. For user-defined classes, mutability is controlled by whether `__setattr__` and `__delattr__` are defined and by the use of `__slots__` to restrict the instance dictionary.

## Error Handling Convention

The C-level convention throughout the CPython source tree is:

- A function returning `PyObject *` signals failure by returning `NULL` and setting an exception via one of the `PyErr_*` family of functions (`PyErr_SetString`, `PyErr_SetFromErrno`, `PyErr_NoMemory`, etc.).
- A function returning `int` typically signals failure with `-1` (success is `0` or a positive value).
- Callers check return values immediately; they must not call any further `PyErr_*` function if the callee already raised one.
- To discard a pending exception without propagating it, callers call `PyErr_Clear()`.

Exception state is stored per-thread in `PyThreadState`. The exception type, exception value, and traceback are available from Python as the tuple returned by `sys.exc_info()`.

## Reference Counting and Ownership

CPython's primary memory management is reference counting. Every copy of a pointer to a `PyObject` is an ownership stake, and every owner must eventually call `Py_DECREF` (or `Py_XDECREF` for possibly-NULL pointers). When the count reaches zero, `tp_dealloc` is called.

C API functions transfer ownership according to documented conventions:
- **New reference** — the caller owns the returned object and must decref it eventually.
- **Borrowed reference** — the caller does not own the object; it must not decref it without first incrementing the count.

The macros `Py_INCREF`, `Py_DECREF`, `Py_XINCREF`, `Py_XDECREF` manage counts. `Py_CLEAR(p)` sets `p` to NULL and decrefs the previous value atomically-with-respect-to-the-GIL, which is the safe idiom for clearing a field that might be re-entered.

## Immortal Objects

Statically initialized objects (standard type objects, the singletons `None`, `True`, `False`, small cached integers) use a special immortal reference count that is never decremented to zero, avoiding any possibility of deallocation. The flag `_Py_STATICALLY_ALLOCATED_FLAG` and `_Py_IMMORTAL_REFCNT_LOCAL` constants mark these objects in the GIL-disabled (free-threaded) build, where atomic reference counting applies.
