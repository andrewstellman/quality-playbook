# HTTP/2 Specifications - RFC 9113

**Source:** RFC 9113 - HTTP/2 (June 2022) - Supersedes RFC 7540
**References:**
- RFC 9113 official specification: https://www.rfc-editor.org/rfc/rfc9113.html

**Accessed:** April 2026

## Overview

RFC 9113 specifies "an optimized expression of the semantics of the Hypertext Transfer Protocol (HTTP), referred to as HTTP version 2 (HTTP/2)."

**Key difference from HTTP/1.1:**
- HTTP/1.1: Text-based protocol
- HTTP/2: Binary framing layer enabling multiplexed streams, header compression, and efficient TCP connection usage

## Connection Establishment

### Connection Preface

HTTP/2 connections begin with a **connection preface**—a protocol handshake ensuring both endpoints use HTTP/2.

**Client sends:**
- 24-octet sequence: `"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"`
- Immediately followed by a SETTINGS frame

**Server responds:**
- Sends its own SETTINGS frame

**Critical specification:** "the [SETTINGS](#SETTINGS) frames received from a peer as part of the connection preface MUST be acknowledged" before further communication.

**Behavioral implication for httpx:** Must properly implement connection preface and SETTINGS frame acknowledgment.

## Frame Architecture

### Frame Format

All HTTP/2 frames follow a strict binary format with a **9-octet (72-bit) header**:

1. **Length (24 bits)** - Unsigned integer
   - Payload length in octets
   - Does not include 9-octet frame header
   - Default maximum: 16,384 octets
   - Can be increased via SETTINGS

2. **Type (8 bits)** - Frame type code
   - Identifies frame purpose
   - Values: 0x00-0x0A for standard types
   - Unknown types must be ignored

3. **Flags (8 bits)** - Boolean frame flags
   - Type-specific flags
   - Indicate presence of optional features or state

4. **Reserved Bit (1 bit)** - Always 0

5. **Stream Identifier (31 bits)**
   - Identifies the stream
   - 0x00: Connection stream (reserved)
   - 0x01 onwards: Regular streams
   - Even/odd patterns have meaning

**Important note:** "the 9 octets of the frame header are not included in" the stated payload length.

### Frame Structure
- 9-octet header (fixed)
- Variable-length payload (0 to max length)
- Frames are not fragmented; serialization of frames is complete

## Standard Frame Types

### HEADERS Frame (0x01)
- **Purpose:** Opens streams and carries field section data
- **Contents:** HTTP header fields (request or response)
- **Flow control:** Not subject to flow control
- **Multiplexing:** Starts new streams

### DATA Frame (0x00)
- **Purpose:** Transmits message content (request/response body)
- **Contents:** Payload data
- **Flow control:** Subject to flow control constraints
- **Size limits:** Cannot exceed max frame size

### SETTINGS Frame (0x04)
- **Purpose:** Configures connection parameters
- **Contents:** Key-value pairs of settings
- **ACK handling:** Must be acknowledged unless has ACK flag
- **Direction:** Bidirectional (both endpoints can send)

**Common settings:**
- HEADER_TABLE_SIZE
- ENABLE_PUSH
- MAX_CONCURRENT_STREAMS
- INITIAL_WINDOW_SIZE
- MAX_FRAME_SIZE
- MAX_HEADER_LIST_SIZE

### RST_STREAM Frame (0x03)
- **Purpose:** Terminates individual streams with error codes
- **Contents:** Error code and stream ID
- **Scope:** Affects only that stream
- **Connection:** Connection remains open

### WINDOW_UPDATE Frame (0x08)
- **Purpose:** Manages flow-control credits
- **Contents:** Window size increment
- **Types:** Connection-level or stream-level
- **Function:** Allows sender to resume transmission after flow control throttling

### GOAWAY Frame (0x07)
- **Purpose:** Connection termination
- **Contents:** Last stream ID and error code
- **Effect:** Initiates connection close
- **Graceful shutdown:** Allows pending streams to complete

### PUSH_PROMISE Frame (0x05)
- **Purpose:** Server push notification
- **Contents:** Promised stream ID and headers
- **Response:** Server pre-sends response for expected requests

### PING Frame (0x06)
- **Purpose:** Connection keep-alive and round-trip time measurement
- **Contents:** 8-octet payload (usually 0)
- **ACK handling:** Must be acknowledged

### CONTINUATION Frame (0x09)
- **Purpose:** Continuation of header block fragmentation
- **Contents:** Remaining header block data
- **Usage:** When header block doesn't fit in HEADERS frame

## Stream State Management

### Stream Lifecycle
Streams progress through defined states:

```
idle → open → half-closed → closed
```

**Stream states:**
- **Idle:** Not yet opened
- **Open:** Active stream with request/response in progress
- **Half-Closed (Local):** Client sent HEADERS+DATA, awaiting response
- **Half-Closed (Remote):** Client received response headers, awaiting data
- **Closed:** Stream terminated (via END_STREAM or RST_STREAM)

### Stream Semantics

**Critical specification:** "the order of [HEADERS](#HEADERS) and [DATA](#DATA) frames is semantically significant," requiring strict sequential processing.

**Ordering requirement:**
1. HEADERS frame must come first
2. DATA frames follow in order
3. END_STREAM flag indicates last frame

## Flow Control

### Window-Based Flow Control

Each stream and connection has a **flow control window** (initial: 65,535 octets).

**Mechanisms:**
- Sender tracks window size
- DATA frames consume window credits
- WINDOW_UPDATE frames add credits
- Sender blocked when window reaches 0

**Important:** Applies only to DATA frames, not HEADERS or other frame types.

## Error Handling

### Connection Errors
- Terminate the entire link
- Sent via GOAWAY frame
- Common error codes: PROTOCOL_ERROR, INTERNAL_ERROR, etc.

### Stream Errors
- Affect only individual streams
- Sent via RST_STREAM frame
- Connection remains open
- Other streams unaffected

## Multiplexing Benefits

### Single TCP Connection
- Multiple concurrent request/response exchanges on one connection
- Eliminates overhead of connection setup
- Reduces latency (no new TCP handshakes)

### Stream Prioritization
- Streams can have priority dependencies
- Server can optimize response order
- Lower-latency responses first

### Header Compression
- HPACK compression for HTTP headers
- Reduces bandwidth compared to HTTP/1.1
- Stateful compression (maintains context between requests)

## Behavioral Specifications for httpx

### Connection Preface
HTTPX must:
- Send correct 24-octet client preface
- Follow with SETTINGS frame
- Acknowledge server SETTINGS frame

### Frame Construction
HTTPX must:
- Construct frames with correct 9-octet headers
- Validate frame types
- Respect frame size limits
- Process frame flags correctly

### Stream Multiplexing
HTTPX must:
- Support multiple concurrent streams on single connection
- Manage stream IDs correctly (client uses odd, server uses even)
- Handle stream state transitions
- Maintain separate flow control windows per stream

### Settings Negotiation
HTTPX must:
- Send SETTINGS frame
- Acknowledge received SETTINGS
- Respect connection parameters (max frame size, concurrent streams, etc.)

### Flow Control
HTTPX must:
- Implement window-based flow control
- Send WINDOW_UPDATE frames when consuming data
- Not send DATA frames exceeding window size
- Handle flow control blocking

### Error Handling
HTTPX must:
- Send GOAWAY on connection errors
- Send RST_STREAM on stream errors
- Process received GOAWAY frames
- Handle connection termination gracefully

## Known HTTP/2 Issues in httpx

### Server Disconnection
When httpx connects to HTTP/2 servers that disconnect, issues can occur if `keepalive_expiry` exceeds server keep-alive timeout.

**Cause:** Connection reuse attempted on stale connections.

**Mitigation:**
- Align `keepalive_expiry` with server expectations
- Monitor connection health
- Implement reconnection logic

### Stream Allocation
Under high concurrency, HTTP/2 stream allocation and connection reuse must follow RFC 9113 strictly to avoid creating multiple connections when one should suffice.
