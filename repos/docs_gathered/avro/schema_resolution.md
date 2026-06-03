# Schema Resolution, Canonical Form, and Fingerprints

Because every Avro value is read against a schema that need not match
the schema it was written with, Avro defines an explicit set of rules
for resolving differences between a writer's schema and a reader's
schema. The same rules apply whether the data lives in a container
file, in an RPC payload, or in a single-object framed message.

## Match rules

Two schemas *match* when one of the following holds:

- Both are arrays whose item schemas match.
- Both are maps whose value schemas match.
- Both are enums whose unqualified names match.
- Both are fixeds whose unqualified names and sizes match.
- Both are records with the same unqualified name.
- Either schema is a union.
- Both are the same primitive type.
- The writer's primitive type can be *promoted* to the reader's:
  `int` → `long`/`float`/`double`, `long` → `float`/`double`,
  `float` → `double`, `string` ↔ `bytes`.

For matching records, fields are paired by name (taking aliases into
account). Fields present only on the writer side are skipped; fields
present only on the reader side are filled in from the reader's
declared `default`, and if there is no default the read fails. For
matching enums, a writer symbol that the reader does not know falls
back to the reader's `default` symbol (and otherwise raises an error).

Unions resolve by trying each branch of the reader's union in order
against the writer's branch; the first branch that matches is used. A
reader union against a non-union writer matches the first reader
branch that matches the writer; a non-union reader against a writer
union must match the writer's selected branch.

`doc` is purely descriptive and is ignored during resolution.

## Parsing Canonical Form

To make "is this the same schema?" precise, the specification defines
*Parsing Canonical Form*: a normalised JSON form produced by a series
of mechanical transformations on a schema:

1. **PRIMITIVES** — collapse `{"type":"int"}` and similar to `"int"`.
2. **FULLNAMES** — expand all short names into fullnames and drop
   redundant `namespace` attributes.
3. **STRIP** — keep only the attributes that affect parsing (`type`,
   `name`, `fields`, `symbols`, `items`, `values`, `size`).
4. **ORDER** — order surviving attributes within an object as `name`,
   `type`, `fields`, `symbols`, `items`, `values`, `size`.
5. **STRINGS** — convert escape sequences to their UTF-8 equivalents.
6. **INTEGERS** — strip leading zeros and quotes from integer literals.
7. **WHITESPACE** — eliminate JSON whitespace outside string literals.

Two schemas have the same parsing canonical form when they accept the
same binary data, so canonical form is the right reference for cache
keys and equivalence checks.

## Schema fingerprints

A *fingerprint* is a short bit string that identifies a parsing
canonical form. The specification recommends three algorithms,
covering different size and collision trade-offs:

- **SHA-256** for 256-bit fingerprints when storage is plentiful.
- **MD5** for 128-bit fingerprints when many millions of schemas are
  in play.
- **CRC-64-AVRO** (a 64-bit Rabin fingerprint) for the compact case;
  the specification lists a reference implementation along with the
  initial value `0xC15D213AA4D7A795` and the standard 256-entry
  lookup table.

CRC-64-AVRO is also the fingerprint embedded in single-object
encoding. Fingerprints are convenience identifiers, not cryptographic
commitments — they exist to key caches and tag messages, and the
specification recommends that surrounding security mechanisms handle
adversarial concerns.

## Compatibility checking

The Java implementation provides higher-level compatibility utilities
in `org.apache.avro.SchemaCompatibility`. Its entry point
`checkReaderWriterCompatibility(reader, writer)` returns a result
object whose `getCompatibility()` enum reports `COMPATIBLE` or
`INCOMPATIBLE`, accompanied by the reader/writer pair and a human
message. The `SchemaValidator` family
(`ValidateLatest`/`ValidateAll`/`ValidateCanRead`/`ValidateCanBeRead`
/`ValidateMutualRead`) supplies multi-version validation strategies
suitable for schema-registry style use.
