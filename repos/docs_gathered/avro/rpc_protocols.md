# Protocols and RPC

Avro defines an RPC framework on top of the same schema language used
for data serialization. A *protocol* is a JSON document that declares
named types, errors, and messages; clients and servers exchange
protocol hashes at connect time, and message arguments and responses
are encoded with the same binary rules used for data.

## Protocol declaration

A protocol is a JSON object with attributes:

- `protocol` — the protocol's simple name (required).
- `namespace` — optional namespace, applied with the same rules used
  for named schemas.
- `doc` — optional human description.
- `types` — optional list of named schema definitions (records, enums,
  fixeds and *errors*; an error is a record declared with
  `"type": "error"`). Forward references are not allowed.
- `messages` — optional map whose keys are message names and whose
  values are message objects.

A message has a `request` (a list of named, typed parameter schemas
matching the form of record fields), a `response` schema, an optional
declared `errors` union, and an optional `one-way` boolean. The
effective error union prepends `"string"` to the declared union so
servers can signal undeclared system errors. A one-way message must
have `response: "null"` and no errors, and no response data is sent
when one-way is true over a stateful transport.

The Java surface for these documents is `org.apache.avro.Protocol`,
which exposes nested `Message`, `TwoWayMessage`, and `OneWayMessage`
classes; protocols can be parsed from `.avpr` JSON or from `.avdl` IDL
files compiled by the `avro-tools idl` command.

## Wire layout

Above the byte level, each call consists of a request and (for two-way
messages) a paired response. Both directions are *framed* as a list of
buffers: a four-byte big-endian length followed by that many bytes,
repeated, terminated by a zero-length buffer. Framing is independent
of message content and exists so that large parameters can be moved
without extra copies (for example, a buffer that wraps a memory-mapped
file can be written directly to a socket).

A request payload is:

- *request metadata* — a `map<bytes>`.
- the *message name* as an Avro `string`.
- the *parameters*, encoded as an anonymous record matching the
  message's `request` declaration.

A response payload is:

- *response metadata* — a `map<bytes>`.
- a one-byte error flag, followed by either the encoded response (flag
  = 0) or the encoded error from the effective error union (flag = 1).

The empty string as a message name pings the server: the server
returns an empty response without invoking any handler.

## Handshakes

Before any messages flow, peers negotiate a handshake. The handshake
record schemas `org.apache.avro.ipc.HandshakeRequest` and
`org.apache.avro.ipc.HandshakeResponse` are part of the
specification. A client sends an MD5 hash of its own protocol text
plus a guess at the server's hash. The server replies with a
`HandshakeMatch` of `BOTH` (both hashes recognised — proceed),
`CLIENT` (client's protocol recognised but server's hash was wrong;
the server returns its protocol text so the client can update its
cache), or `NONE` (server does not know the client's protocol; the
client must resend with the full client protocol text). Once a
stateful transport has completed a successful `BOTH` handshake, later
calls on the same connection skip the handshake bytes entirely.

## Transports

Transports are pluggable. The Java implementation models a transport
as `org.apache.avro.ipc.Transceiver`, with concrete subclasses
including `HttpTransceiver`, `SocketTransceiver` (TCP),
`SaslSocketTransceiver` (TCP wrapped in SASL), `DatagramTransceiver`
(UDP), and `LocalTransceiver` (in-process). Each pairs with a `Server`
of the same family, and `Requestor`/`Responder` classes drive the
request/response cycle on top of `Transceiver`. Optional modules
provide HTTP servers based on Jetty (`ipc-jetty`) and Netty
(`ipc-netty`).

When HTTP is the transport, each request/response is exactly one HTTP
request/response with `Content-Type: avro/binary`; HTTP is treated as
a stateless transport, so a handshake prefixes every call.

The SASL profile defined alongside the spec covers connection-based
authentication and integrity protection for the socket transport,
following the framing rules from RFC 2222.
