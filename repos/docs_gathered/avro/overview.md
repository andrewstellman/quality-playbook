# Apache Avro — Overview

Apache Avro is a data serialization system. It provides a compact, fast,
binary data format together with a container file format for persistent
storage, a JSON-based schema language, and a remote procedure call (RPC)
framework that uses the same schema language to describe message
protocols. The project ships official implementations for several
languages — Java is the reference implementation, with first-class
support also in Python, C, C++, C#, JavaScript, Perl, PHP, and Ruby.
The Rust implementation lives in its own companion repository.

## Design philosophy

Three properties drive Avro's design:

- **Schemas travel with data.** Every Avro datum is written against a
  schema, and the writer's schema is always available to the reader —
  either embedded in a container file or exchanged at the start of an
  RPC connection. Because the schema is always known at read time,
  binary encodings carry no per-value tag bytes.
- **Schemas are first-class JSON.** Schemas are defined as JSON
  documents, so every language with a JSON parser already has the
  pieces it needs to implement Avro. Schemas can also be authored in a
  C-like surface syntax called Avro IDL (`.avdl` files) and compiled
  down to JSON.
- **Code generation is optional.** Avro supports a fully dynamic
  programming model where records, arrays and maps are read into
  generic in-memory containers. Statically typed languages may also
  generate classes from schemas for ergonomics and speed, but no
  feature of Avro requires that generation step.

## What an implementation provides

A complete Avro implementation typically offers the following building
blocks:

- A **schema parser** that converts JSON schema text into an in-memory
  schema object.
- **Binary encoders and decoders** that translate between schema-typed
  values and the canonical Avro binary wire form.
- **JSON encoders and decoders** that translate between Avro values
  and a JSON projection useful for debugging and web use.
- **Object container file** readers and writers that persist a sequence
  of values together with the writing schema, block framing, and a
  compression codec.
- **Generic, specific, and reflect** data models, which provide
  respectively a map/list/record-style API, generated typed classes,
  and reflective bindings to existing application classes.
- A **schema resolution** layer that lets a reader translate data
  written against a different but compatible schema.
- An **RPC layer** that uses Avro protocols to describe messages and
  exchanges them over pluggable transports.

## Source layout

The repository organises each language implementation under
`lang/<language>/`. Cross-cutting assets live at the top level: the
`doc/` tree builds the project website with Hugo, `share/` holds shared
test schemas, test data and editor support, and the root `build.sh`
orchestrates per-language builds, including a Docker-based path that
reproduces the project's CI environment. Each `lang/<language>/`
directory has its own README, build script, and test suite using that
language's native tooling — Maven for Java, `pyproject`/`tox` for
Python, CMake for C and C++, `.csproj`/MSBuild for C#, and so on.
