# Binary and JSON Encoding

Avro defines two on-the-wire encodings of typed values: a compact
binary encoding used by almost all real workloads, and a JSON encoding
used for debugging, web payloads, and other places where a
human-readable form is preferred. Both encodings assume that the
reader knows the schema separately — the data itself carries no type
tags or field names.

## Binary encoding of primitives

- `null` is written as zero bytes.
- `boolean` is one byte, `0x00` for false and `0x01` for true.
- `int` and `long` use variable-length zig-zag coding: the signed
  integer is mapped to an unsigned one (`(n << 1) ^ (n >> 31)` for
  `int`, with the appropriate width for `long`) and then written as a
  sequence of 7-bit groups in little-endian order, the high bit of each
  byte indicating continuation.
- `float` is four little-endian bytes obtained from
  `Float.floatToRawIntBits`. `double` is eight little-endian bytes
  obtained from `Double.doubleToRawLongBits`.
- `bytes` is encoded as a `long` length followed by that many raw
  bytes. `string` is encoded the same way, with the bytes being the
  UTF-8 encoding of the text.

## Binary encoding of complex types

A `record` is encoded as the concatenation of its fields' encodings, in
declared order. An `enum` is encoded as the `int`-encoded zero-based
position of the symbol. A `fixed` is encoded as exactly the declared
number of raw bytes.

A `union` is encoded as the `int`-encoded zero-based branch index,
followed by the value encoded per that branch's schema.

`array` and `map` values share a *blocked* representation. A value is
written as a sequence of blocks; each block consists of a `long`
count followed by that many items (key/value pairs for maps, items for
arrays). A block whose count is zero terminates the value. If a count
is encoded as a negative long, its absolute value is the item count
and it is immediately followed by another `long` giving the byte size
of the block, which allows readers to skip the block without parsing
its contents. Map keys are always strings.

## JSON encoding

For every type other than union, the JSON encoding matches the form
used for default values: a record is a JSON object, an array is a JSON
array, a map is a JSON object, an enum is its symbol as a JSON string,
`bytes` and `fixed` are strings whose Unicode code points 0–255 stand
for byte values 0–255, and numeric primitives use the obvious JSON
numbers. A union value is encoded as `null` if its branch is `null`,
and otherwise as a JSON object with a single name/value pair whose
name is the branch type (the fullname for named types, the type name
otherwise) and whose value is the recursively encoded branch value.
The schema is still required to read a JSON-encoded value because, for
example, JSON cannot distinguish `int` from `long` or records from
maps.

## Single-object encoding

For situations such as Kafka messages where one Avro value is stored
in isolation, Avro defines a single-object framing built on top of
binary encoding: a two-byte marker `C3 01`, the eight-byte
little-endian CRC-64-AVRO fingerprint of the writer's schema, and
then the binary encoding of the value. The marker lets readers cheaply
check whether a payload is Avro before attempting a fingerprint lookup
in their schema store.

The Java implementation exposes this framing through the
`org.apache.avro.message` package, in particular `BinaryMessageEncoder`
and `BinaryMessageDecoder`, with a pluggable `SchemaStore` interface
for resolving fingerprints to writer schemas.
