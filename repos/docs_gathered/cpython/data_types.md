# CPython Core Data Types and Collections

## Overview

Python's built-in types and the standard library's `collections` module together provide a comprehensive set of general-purpose container abstractions. The built-ins are implemented in C (in `Objects/`); the `collections` module augments them with specialized pure-Python (and some C-backed) types. All follow the object model described in the object model document: each type exposes its capabilities through the type-slot protocol and through dunder methods accessible from Python code.

## Scalar Built-ins

### `int` (`Objects/longobject.c`)
Python integers are arbitrary-precision. Internally they are stored as arrays of "digits" in a base of either 2^15 or 2^30 (configurable at build time via `--enable-big-digits`). Small integers in the range -5 to 256 are cached as immortal singletons, so `a = 1; b = 1` yields two references to the same object.

The C type is `PyLongObject`. The public C API provides `PyLong_FromLong`, `PyLong_FromLongLong`, `PyLong_FromSize_t`, `PyLong_AsLong`, `PyLong_AsLongLong`, `PyLong_AsSsize_t`, etc. The `numbers.Integral` ABC specifies the abstract interface.

### `float` (`Objects/floatobject.c`)
IEEE 754 double-precision. `PyFloat_FromDouble` / `PyFloat_AsDouble` are the primary C API functions. The `math` module exposes the standard mathematical functions operating on `float`; `cmath` provides complex-number variants.

### `complex` (`Objects/complexobject.c`)
A struct of two `double` values (real and imaginary parts). Python literal syntax: `3+2j`. C API: `PyComplex_FromDoubles`, `PyComplex_RealAsDouble`, `PyComplex_ImagAsDouble`.

### `bool` (`Objects/boolobject.c`)
A subtype of `int` with exactly two singleton instances: `True` (value 1) and `False` (value 0). `PyBool_FromLong` converts C integer values to the appropriate singleton.

### `NoneType`, `NotImplementedType`, `Ellipsis`
Singleton types used as sentinels. `None` is returned by functions that have no explicit return value. `NotImplemented` is returned by binary operator dunder methods to signal that the operation is not implemented for the given operands, prompting Python to try the reflected operation. `...` (Ellipsis) is used as a slice placeholder and in type annotations.

## Sequence Types

### `str` (`Objects/unicodeobject.c`)
Text strings are Unicode (PEP 393 flexible string representation). Internally CPython stores strings in one of three encodings depending on the widest code point present: Latin-1 (1 byte/char), UCS-2 (2 bytes/char), or UCS-4 (4 bytes/char). Strings are immutable. The `str.encode(encoding, errors)` method converts to `bytes`; `bytes.decode(encoding, errors)` converts back.

Interning: short strings that look like identifiers are interned (stored in a per-interpreter dictionary) so that `is` comparison can substitute for `==`. `sys.intern(s)` forces interning.

### `bytes` and `bytearray` (`Objects/bytesobject.c`, `Objects/bytearrayobject.c`)
`bytes` is an immutable sequence of integers in range 0–255; `bytearray` is the mutable counterpart. Both support slicing, concatenation, and searching. `bytes.fromhex`, `bytes.hex`, `struct.pack`/`struct.unpack` are common conversion entry points.

### `tuple` (`Objects/tupleobject.c`)
Immutable fixed-length sequence. Empty tuple and single-element tuples up to some threshold are cached. Tuples use contiguous C arrays for storage; indexing is O(1). The C API functions include `PyTuple_New(n)`, `PyTuple_SET_ITEM(t, i, v)` (for filling newly-created tuples only), and `PyTuple_GetItem(t, i)`.

### `list` (`Objects/listobject.c`)
Mutable dynamic array. Uses over-allocation (doubling roughly) to amortize `append`. Insertion and deletion at arbitrary positions are O(n). List sort (`list.sort`, `sorted`) uses the Timsort algorithm (documented in `Objects/listsort.txt`).

### `range` (`Objects/rangeobject.c`)
An immutable, lazy sequence of integers. `range(start, stop, step)` stores only the three parameters; membership testing and slicing are O(1).

## Mapping Types

### `dict` (`Objects/dictobject.c`)
The central mapping type, used pervasively by the interpreter for module globals, object attributes, and keyword arguments. Implementation notes are in `Objects/dictnotes.txt`. CPython's dict uses open addressing with a compact array of (hash, key, value) entries. Insertion order is preserved (guaranteed since Python 3.7). `dict.keys()`, `dict.values()`, `dict.items()` return view objects that reflect subsequent modifications.

C API: `PyDict_New()`, `PyDict_SetItem`, `PyDict_GetItem` (borrowed ref), `PyDict_GetItemWithError` (raises `KeyError` on miss), `PyDict_DelItem`, `PyDict_Size`, `PyDict_Keys`, `PyDict_Copy`.

### `set` and `frozenset` (`Objects/setobject.c`)
Hash sets of hashable objects. `set` is mutable; `frozenset` is immutable and therefore hashable. Both support standard set operations: union (`|`), intersection (`&`), difference (`-`), symmetric difference (`^`), and their in-place variants.

## The `collections` Module

`collections` provides specialized containers that extend or compose the built-in types:

- **`namedtuple(typename, field_names)`** — factory that generates a `tuple` subclass with named fields accessible by attribute. Generated classes are lightweight (no per-instance `__dict__`) and support `_asdict()`, `_replace(**kwargs)`, and `_fields`.
- **`deque([iterable[, maxlen]])`** — double-ended queue implemented as a doubly-linked list of fixed-size blocks. `appendleft` and `popleft` are O(1), unlike `list.insert(0, x)`. When `maxlen` is set, the deque is bounded.
- **`Counter([iterable-or-mapping])`** — `dict` subclass mapping elements to integer counts. `Counter.most_common(n)` returns the n highest-count elements. Arithmetic between counters is supported.
- **`OrderedDict`** — `dict` subclass that remembers insertion order (predates the language guarantee on `dict`; retained for its `move_to_end` and `popitem(last=True/False)` methods).
- **`defaultdict(default_factory)`** — `dict` subclass that calls `default_factory()` for missing keys, avoiding `KeyError` and simplifying grouping patterns.
- **`ChainMap(*maps)`** — wraps multiple mappings in a single view. Reads search maps left to right; writes go to the first map only.
- **`UserDict`, `UserList`, `UserString`** — thin wrappers around `dict`, `list`, and `str` that make subclassing easier by exposing the underlying data as `self.data`.

## Abstract Base Classes for Collections

`collections.abc` (and its registered aliases in `_collections_abc.py`) defines abstract base classes:
- `Hashable`, `Iterable`, `Iterator`, `Generator`
- `Sized`, `Container`, `Collection`
- `Sequence`, `MutableSequence`
- `Mapping`, `MutableMapping`, `MappingView`, `KeysView`, `ItemsView`, `ValuesView`
- `Set`, `MutableSet`
- `Callable`, `Awaitable`, `Coroutine`, `AsyncIterable`, `AsyncIterator`, `AsyncGenerator`
- `Buffer` (the buffer protocol)

Concrete types may register themselves with an ABC using `ABC.register(cls)` to satisfy `isinstance` checks without inheritance.

## `array` Module

`array.array(typecode[, initializer])` stores a compact array of uniform C-typed values (e.g., `'b'` for signed char, `'d'` for double). It is memory-efficient for large homogeneous numeric collections and implements the buffer protocol.

## Hashability and the Data Model

An object is hashable if it has both `__hash__` and `__eq__`. By default, user-defined classes inherit `__hash__` from `object` (based on identity). Defining `__eq__` without `__hash__` sets `__hash__` to `None`, making the class unhashable. Mutable built-in containers (`list`, `dict`, `set`) are unhashable by design.
