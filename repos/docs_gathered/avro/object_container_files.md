# Object Container Files

The object container file is Avro's standard way to persist a sequence
of values together with the schema that describes them. A container
file is self-describing — the schema, the compression codec, any
user-defined metadata, and a synchronisation marker all travel inside
the file alongside the data.

## File structure

A container file consists of:

1. A **file header** with three pieces:
   - The four-byte magic `O`, `b`, `j`, `0x01`.
   - A metadata map written as Avro `{"type":"map","values":"bytes"}`.
   - A 16-byte sync marker, generated randomly per file.
2. One or more **data blocks**, each consisting of:
   - A `long` count of objects in the block.
   - A `long` byte size of the block's payload after codec compression.
   - The payload itself, optionally codec-compressed.
   - The file's 16-byte sync marker again, repeated verbatim.

The block-level sync marker lets readers split files at block
boundaries for parallel processing and detect block boundaries when
resuming a stream. The Java implementation describes the layout with
the Avro schemas `org.apache.avro.file.Header` and
`org.apache.avro.file.DataBlock`.

## Metadata

File metadata is a string-to-`bytes` map. Any keys are allowed, but
keys beginning with `avro.` are reserved by the specification. The two
reserved keys defined today are:

- `avro.schema` — the writer's schema, stored as its JSON text.
- `avro.codec` — the codec name. Absent means `null` (no compression).

Application metadata can be stored alongside these and is round-tripped
unchanged.

## Codecs

The specification requires the `null` (uncompressed) and `deflate`
(RFC 1951) codecs. Optional codecs defined by the spec include
`bzip2`, `snappy`, `xz`, and `zstandard`. The Snappy codec frames each
compressed block with a trailing big-endian CRC-32 of the uncompressed
data.

In the Java implementation, codec selection goes through
`org.apache.avro.file.CodecFactory`, which exposes factory methods
such as `nullCodec()`, `deflateCodec(int)`, `snappyCodec()`,
`bzip2Codec()`, `xzCodec(int)`, and `zstandardCodec()`. Compression
level for `deflate` and `xz` is an integer between 1 and 9.
Applications can register custom codecs with
`CodecFactory.addCodec(name, factory)`. The Python implementation
exposes the codec registry through `avro.codecs.KNOWN_CODECS`.

## Reading and writing

The Java reader/writer pair is `DataFileWriter<D>` and
`DataFileReader<D>` in `org.apache.avro.file`. A writer is constructed
with a `DatumWriter<D>` (generic, specific, or reflect), then opened
against an `OutputStream` or `File` with a chosen schema and codec.
Records are appended with `append(D)`, and the writer flushes whenever
the in-memory buffer crosses a configurable sync interval (the default
constant is `DataFileConstants.DEFAULT_SYNC_INTERVAL`). Container
files may also be appended to: opening with `appendTo(File)` reads the
existing header, validates the schema, and continues writing new
blocks under the existing sync marker.

A reader is a `FileReader<D>` constructed from a `DatumReader<D>` and
a seekable input (`SeekableFileInput`, `SeekableByteArrayInput`).
Beyond iteration, the API exposes `seek(long)` for direct byte offsets
and `sync(long)` for resync to the next block boundary, both built on
the embedded 16-byte sync markers. The Python `avro.datafile` module
mirrors the same layout, with `DataFileWriter`/`DataFileReader`
classes that read and write the same on-disk format.
