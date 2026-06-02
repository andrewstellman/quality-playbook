# Language Implementations

Each language implementation in `lang/<language>/` is a self-contained
project with its own build system and tests, but all of them implement
the same wire format, schema model, and container file layout. This
file sketches the structure of the four most central implementations —
Java, Python, C++, and C# — at this version.

## Java

Java is the reference implementation and is laid out as a multi-module
Maven build under `lang/java/`. The leaf modules used by application
code are:

- `avro` — the core library (`org.apache.avro` and subpackages).
  Subpackages include `Schema` and `Protocol` parsers, the `io`
  encoders/decoders, `file` container file support, `generic`,
  `specific`, and `reflect` data models, `data` (default builders,
  `TimeConversions`), `message` (single-object framing), `path`
  (rich error tracebacks through nested schemas), and `util`.
- `compiler` and `idl` — schema and IDL parsers plus the source-code
  templates used to generate specific records (Velocity templates
  under `compiler/src/main/resources`).
- `maven-plugin` — Mojo entry points `SchemaMojo` (`schema`),
  `ProtocolMojo` (`protocol`), `IDLMojo` (`idl`), `IDLProtocolMojo`
  (`idl-protocol`), and `InduceMojo` (`induce`). They share the
  `AbstractAvroMojo` base class.
- `ipc`, `ipc-jetty`, `ipc-netty` — the core RPC abstractions and two
  HTTP server backends. Optional integrations live in `grpc`,
  `protobuf`, and `thrift`.
- `mapred` — Hadoop MapReduce input/output formats
  (`AvroInputFormat`, `AvroKeyComparator`, `AvroJob`, ...).
- `tools` — the `avro-tools` command-line app, with one class per
  sub-command (`fromjson`, `tojson`, `idl`, `compile`, `cat`,
  `concat`, `getschema`, ...).
- `trevni` — the columnar Trevni format.

## Python

`lang/py/` packages the implementation as `avro` with a flat module
layout. The key modules are `schema` (schema parsing and the
`Schema`/`NamedSchema` hierarchy), `io` (`BinaryDecoder`,
`BinaryEncoder`, `DatumReader`, `DatumWriter`, and validation
helpers), `datafile` (`DataFileReader`/`DataFileWriter`, the on-disk
metadata schema, codec key constants), `codecs` (the `KNOWN_CODECS`
registry, with implementations for `null`, `deflate`, `bzip2`,
`snappy`, `xz`, and `zstandard`), `protocol`, `ipc`, `name`,
`compatibility`, `constants`, `errors`, and `tool` (the command-line
driver). Test data lives in `avro/test`, and a separate `tether`
subpackage hosts the Hadoop "tether" runner.

The build uses `pyproject.toml` with `setup.py` and `setup.cfg`, and
the test matrix runs through `tox.ini`. Type stubs are advertised by
the `py.typed` marker.

## C++

`lang/c++/` builds with CMake. Public headers live in
`lang/c++/include/avro/` and cover both the high-level surface
(`Schema.hh`, `ValidSchema.hh`, `Generic.hh`, `Specific.hh`,
`DataFile.hh`, `Compiler.hh`, `Encoder.hh`, `Decoder.hh`,
`Stream.hh`) and the lower-level building blocks (`Node.hh`,
`NodeImpl.hh`, `Resolver.hh`, `ResolverSchema.hh`, `Validator.hh`,
`Parser.hh`, `Serializer.hh`, `LogicalType.hh`, `Types.hh`). The
implementation files in `lang/c++/impl/` map onto these headers.
Schema/compiler tests use JSON inputs in `lang/c++/jsonschemas/` and
examples under `lang/c++/examples/`. Doxygen configuration lives in
`Doxyfile` and `MainPage.dox`.

## C# (.NET)

`lang/csharp/` is a multi-project .NET solution (`Avro.sln`). The
main library `src/apache/main/` is organised by subsystem with
namespaces matching the directory names: `Schema`, `IO`, `Generic`,
`Specific`, `File`, `Protocol`, `Reflect`, `CodeGen`, and `Util`,
plus `AvroDecimal.cs` for arbitrary-precision decimals. Sibling
projects under `src/apache/` cover code-generation tools, the test
suite, MSBuild integration, IPC, and AOT support. Style and analysis
configuration sit at the top level (`Avro.ruleset`, the
`CodeAnalysis.*.globalconfig` files, `STYLING.md`).

## Other implementations

The repository also includes implementations in C (`lang/c/`),
JavaScript (`lang/js/`), Perl (`lang/perl/`), PHP (`lang/php/`), and
Ruby (`lang/ruby/`). Each follows the same conventions: native build
tooling for the language, a `share/test` set of cross-language test
vectors, and conformance with the same schema, encoding, container,
and RPC specifications described in the other files in this corpus.
