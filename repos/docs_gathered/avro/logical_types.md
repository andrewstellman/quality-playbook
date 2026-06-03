# Logical Types

A *logical type* is an Avro primitive or complex type with a
`logicalType` attribute that gives it a higher-level interpretation.
The on-the-wire encoding is exactly that of the underlying primitive
or complex type, so any implementation can read or write data using
the underlying form, even when it does not recognise the logical
overlay. Implementations are expected to ignore unknown logical types
and fall back to the underlying schema, and to also fall back when a
declared logical type is invalid (for example a decimal with `scale`
greater than `precision`).

## Decimal

`decimal` represents an arbitrary-precision signed decimal in the form
`unscaled × 10^-scale`. It annotates Avro `bytes` or `fixed`. The
underlying byte array stores the two's-complement big-endian
representation of the unscaled integer. The attributes are:

- `precision` — a positive integer, the maximum number of base-10
  digits the value may carry. For a `fixed` of size *n*, the maximum
  precision is `floor(log10(2^(8n − 1) − 1))`.
- `scale` — a non-negative integer less than or equal to `precision`;
  defaults to 0.

The alternative `big-decimal` form annotates Avro `bytes` and stores
the scale inline with the value (available in Java and Rust today),
so it can be used when scale cannot be fixed in advance.

For schema resolution, two decimal types match only if both precision
and scale match.

## UUID

`uuid` annotates Avro `string` or a 16-byte `fixed`. The string form
follows RFC 4122; the fixed form holds the raw 16 bytes.

## Date

`date` annotates Avro `int`. The integer is the number of days since
the Unix epoch (1 January 1970) in the proleptic ISO calendar, with no
time-of-day or time-zone information.

## Time

`time-millis` annotates Avro `int`; the integer is the number of
milliseconds since midnight. `time-micros` annotates Avro `long`; the
long is the number of microseconds since midnight.

## Timestamp

`timestamp-millis`, `timestamp-micros`, and `timestamp-nanos` annotate
Avro `long` and represent an instant on the global timeline,
independent of any time zone or calendar. The value is the number of
milliseconds, microseconds, or nanoseconds since the Unix epoch.

The companion `local-timestamp-millis`, `local-timestamp-micros`, and
`local-timestamp-nanos` use the same underlying representation but
denote a local-time instant: implementations preserve the displayed
date/time across writers and readers without committing to a specific
time zone.

## Duration

`duration` annotates Avro `fixed` of size 12. The 12 bytes hold three
little-endian unsigned 32-bit integers: number of months, number of
days, and number of milliseconds. The components are kept separate
because the millisecond length of a month or day depends on the
calendar moment the duration is anchored to.

## Conversions in Java

The Java implementation models conversions through
`org.apache.avro.Conversion<T>` and a registry of built-in
conversions in `org.apache.avro.Conversions` and
`org.apache.avro.data.TimeConversions`. Each conversion knows the
logical type it handles, the Java type it materialises into (for
example `BigDecimal`, `UUID`, `LocalDate`, `Instant`,
`LocalDateTime`), and the round-trip between that Java type and the
underlying Avro encoding. Custom conversions can be registered on
`GenericData` (and inherited by `SpecificData` and `ReflectData`)
through `addLogicalTypeConversion`. The `LogicalTypes` registry
parses `logicalType` attributes on schema load and lets applications
add new logical type names with `LogicalTypes.register`.

The Python implementation handles the standard logical types through
the schema parser and the `io` module's reader/writer plumbing, with
date/time conversions backed by `datetime`, `decimal.Decimal`, and
`uuid.UUID`. Other implementations follow the same convention: native
types where idiomatic, raw underlying Avro types when not.
