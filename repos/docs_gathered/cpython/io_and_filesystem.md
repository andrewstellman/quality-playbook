# CPython I/O and Filesystem Layer

## Overview

CPython's I/O system is organized as a layered class hierarchy defined in the `io` module. The module ships both a C implementation (the default, in `Modules/_io/`) and a pure-Python reference implementation (`Lib/_pyio.py`). The two implementations present identical public interfaces; the C version is preferred for performance and the Python version serves as readable documentation of the contracts.

## Three I/O Categories

The `io` module recognizes three distinct categories of stream:

### Raw I/O (unbuffered)
`RawIOBase` is the lowest layer, operating on bytes with no buffering. `FileIO` implements raw I/O for file descriptors. Raw streams support `read(size)`, `readinto(b)`, and `write(b)`, all of which may return fewer bytes than requested (consistent with the underlying OS call).

### Binary I/O (buffered)
`BufferedIOBase` sits above raw I/O and adds buffering. Concrete subclasses:
- `BufferedReader` — adds a read-ahead buffer; `read()` always returns exactly the requested number of bytes unless EOF.
- `BufferedWriter` — accumulates writes and flushes to the underlying raw stream.
- `BufferedRandom` — read/write buffering for seekable streams.
- `BufferedRWPair` — pairs a separate reader and writer for non-seekable bidirectional streams.
- `BytesIO` — in-memory binary stream; no underlying file.

The default buffer size is `DEFAULT_BUFFER_SIZE` (128 KiB), but `open()` uses `max(min(blocksize, 8 MiB), DEFAULT_BUFFER_SIZE)` when the device block size is known.

### Text I/O
`TextIOBase` wraps a binary stream with codec-based encoding/decoding and optional newline translation. `TextIOWrapper` is the concrete class; `StringIO` is its in-memory variant. Text streams accept and return `str`; passing `bytes` to a text stream's `write()` raises `TypeError`, and vice versa.

## The `open()` Built-in

`open(file, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None)` is the standard entry point. It constructs the appropriate stack of stream objects based on `mode`:

| Mode | Stack |
|------|-------|
| `'rb'` | `FileIO` → (none) |
| `'r'`  | `FileIO` → `BufferedReader` → `TextIOWrapper` |
| `'wb'` | `FileIO` → `BufferedWriter` |
| `'w'`  | `FileIO` → `BufferedWriter` → `TextIOWrapper` |
| `'rb', buffering=0` | `FileIO` (raw, no buffer) |

The `encoding` parameter defaults to `"locale"` (or `"utf-8"` in UTF-8 mode, controlled by `PYTHONUTF8` or the `-X utf8` flag). `errors` sets the codec error handler (`"strict"`, `"replace"`, `"ignore"`, `"surrogateescape"`, etc.). `newline` controls newline translation.

The `opener` parameter accepts a callable with the signature `(path, flags) -> fd`, enabling custom file-open logic (e.g., opening relative to a directory file descriptor using `os.open`).

## Context Management Protocol

All stream objects implement `__enter__` and `__exit__`, making them usable with `with` statements. `__exit__` calls `close()`. `close()` is idempotent; calling it more than once is safe. The `closed` attribute reflects the current state.

## The `os` Module and Low-Level Filesystem Access

`os` exposes the POSIX/Windows system call interface directly:
- `os.open(path, flags, mode=0o777, *, dir_fd=None)` — returns an integer file descriptor.
- `os.read(fd, n)`, `os.write(fd, b)`, `os.close(fd)` — raw fd operations.
- Directory operations: `os.listdir`, `os.scandir`, `os.mkdir`, `os.makedirs`, `os.rmdir`, `os.remove`, `os.rename`, `os.replace`.
- Stat and metadata: `os.stat`, `os.lstat`, `os.fstat`; the result is a `os.stat_result` named tuple with fields `st_mode`, `st_size`, `st_mtime`, `st_atime`, `st_ctime`, etc.
- Symbolic links: `os.symlink`, `os.readlink`, `os.unlink`.
- File descriptor duplication and inheritance: `os.dup`, `os.dup2`, `os.set_inheritable`.

`os.scandir(path)` returns an iterator of `DirEntry` objects with cached `name`, `path`, `inode()`, `is_dir()`, `is_file()`, `is_symlink()`, and `stat()` methods, avoiding redundant `stat()` system calls when the OS provides the information from the directory read itself.

## `pathlib` — Object-Oriented Paths

`pathlib.Path` (in `Lib/pathlib/`) provides an object-oriented interface layered on `os` and `os.path`. The hierarchy is:
- `PurePath` — pure path manipulation without filesystem access (subclasses: `PurePosixPath`, `PureWindowsPath`).
- `Path(PurePath)` — adds filesystem operations (subclasses: `PosixPath`, `WindowsPath`).

`Path` objects support operators: `/` for joining, `==` for comparison. Key methods: `open()`, `read_text()`, `write_text()`, `read_bytes()`, `write_bytes()`, `stat()`, `exists()`, `is_dir()`, `is_file()`, `iterdir()`, `glob()`, `rglob()`, `mkdir()`, `unlink()`, `rename()`, `replace()`, `symlink_to()`, `resolve()` (returns the absolute real path).

## `os.path` — Functional Path Utilities

`os.path` (implemented in `Lib/posixpath.py` for POSIX and `Lib/ntpath.py` for Windows) provides functional path manipulation: `join`, `split`, `dirname`, `basename`, `abspath`, `realpath`, `exists`, `isfile`, `isdir`, `splitext`, `expanduser`, `expandvars`, `commonpath`, `commonprefix`. All functions accept `str`, `bytes`, or any object implementing `os.PathLike`.

## `shutil` — High-Level File Operations

`shutil` provides operations not directly in `os`:
- `shutil.copy`, `shutil.copy2` — copy file content and optionally metadata.
- `shutil.copytree`, `shutil.rmtree` — recursive directory copy and deletion.
- `shutil.move` — rename across filesystems.
- `shutil.make_archive`, `shutil.unpack_archive` — create/extract zip, tar, gz, bz2, and xz archives.
- `shutil.disk_usage` — returns `(total, used, free)` for a path's filesystem.

## `tempfile` — Temporary Files and Directories

`tempfile.TemporaryFile()`, `tempfile.NamedTemporaryFile()`, `tempfile.SpooledTemporaryFile()`, and `tempfile.TemporaryDirectory()` all implement context managers. By default, temporary files are removed automatically on close or context exit.

## Encoding Handling

Text I/O encoding is explicit and codec-driven. CPython's `codecs` module (C core in `Modules/_codecsmodule.c`, Python interface in `Lib/codecs.py`) maintains a registry of named codecs. `open()` passes the `encoding` string to `codecs.lookup(encoding)` to obtain the codec. The `EncodingWarning` (enabled by `-X warn_default_encoding`) alerts callers that rely on the platform default encoding without specifying one explicitly.
