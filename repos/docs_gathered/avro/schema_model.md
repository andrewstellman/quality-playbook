# Schema Model

The schema model is the heart of Avro. A schema is a JSON document that
describes the shape of one or more values, and every encoding,
decoding, container file, RPC handshake, and code generator in the
project takes a parsed schema as its primary input.

## Schema declaration forms

A schema is represented in JSON by one of three things:

- A bare JSON string that names a defined type — for example
  `"int"` or `"my.namespace.User"`.
- A JSON object of the form `{"type": "typeName", ...attributes...}`.
  Attributes not defined by the specification are permitted as user
  metadata and must not change the serialized layout of values.
- A JSON array, which denotes a union of the embedded types.

The primitive type names are `null`, `boolean`, `int` (32-bit signed),
`long` (64-bit signed), `float` (IEEE-754 32-bit), `double` (IEEE-754
64-bit), `bytes`, and `string` (Unicode). The complex types are
`record`, `enum`, `array`, `map`, `union`, and `fixed`.

## Named types

Records, enums, and fixed types are *named*. Each named type has a
fullname formed from a simple `name` and an optional `namespace`,
separated by a dot. Names must match `[A-Za-z_][A-Za-z0-9_]*`, and a
namespace is a dot-separated sequence of such names. If a `name`
contains a dot it is treated as a fullname and any sibling `namespace`
attribute is ignored. A simple name without a namespace inherits the
namespace of the most tightly enclosing named schema, or the null
namespace if there is none. A schema or protocol may not contain two
definitions of the same fullname, and a name must be defined before it
is referenced in a depth-first traversal.

Records, enums, and fields can declare `aliases` — alternate names
used to map a writer's schema onto a differently-named reader's
schema during resolution. An alias may be either fully qualified or
relative to the namespace of the name it is an alias for.

## Records, enums, fixed, arrays, maps, unions

A `record` carries an ordered list of fields. Each field has a `name`
and a `type`, plus optional `doc`, `aliases`, `order`
(`ascending`/`descending`/`ignore`) and `default`. A `default` is
applied only at read time when a reader's schema declares a field that
the writer's schema lacks; it does not make the field optional at
encoding time.

An `enum` has a list of `symbols` (matching the same name regex) and
an optional `default` symbol used when the reader encounters a writer
symbol it does not know. An `array` carries an `items` schema; a `map`
carries a `values` schema, with keys always strings. A `fixed` has an
integer `size` and represents that many raw bytes per value.

A `union` is a JSON array of branch schemas. A union may not contain
two branches with the same primitive type, two arrays, two maps, or
two fixeds; it may contain multiple named types so long as their
fullnames differ, and unions may not directly nest other unions. The
default of a record field whose type is a union must match the union's
first branch.

## Avro IDL

The same schema universe can also be authored in Avro IDL, a C-like
surface syntax stored in `.avdl` files. IDL supports `record`,
`error`, `enum`, `fixed`, `protocol`, `import idl`, `import protocol`,
and `import schema` statements; annotations such as `@namespace`,
`@aliases`, and `@logicalType` decorate declarations. The `idl`
sub-command of `avro-tools` and the Maven plugin's `idl` and
`idl-protocol` goals convert `.avdl` files into `.avsc` schema files
or `.avpr` protocol files.
