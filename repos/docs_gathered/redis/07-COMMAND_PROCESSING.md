# Redis Command Processing — RESP Protocol, Input Buffer, Pipelining, MULTI/EXEC, and Pub/Sub

Extracted from redis.io documentation and protocol specifications. This document covers command parsing, transaction semantics, and concurrency guarantees.

Sources: redis.io/docs/latest/develop/reference/protocol-spec/, RESP specification.

---

## 1. RESP Protocol (Redis Serialization Protocol)

RESP is the wire protocol for client-server communication. Supports both RESP2 and RESP3.

### RESP2 Protocol (Classic, Redis < 6.0)

RESP2 is based on simple text and binary encoding.

**Simple Strings** (for status replies)
```
+OK\r\n
+PONG\r\n
```

**Errors** (for error replies)
```
-ERR unknown command\r\n
-MOVED 12345 192.168.1.1:6379\r\n
```

**Integers** (for numeric replies)
```
:1000\r\n
:-5\r\n
```

**Bulk Strings** (for binary data)
```
$6\r\nfoobar\r\n        # 6-byte string "foobar"
$-1\r\n                # Null bulk string
$0\r\n\r\n             # Empty string
```

**Arrays** (for multi-element replies)
```
*2\r\n$3\r\nfoo\r\n$3\r\nbar\r\n    # Array of ["foo", "bar"]
*0\r\n                              # Empty array
*-1\r\n                             # Null array
```

### RESP3 Protocol (Modern, Redis >= 6.0)

RESP3 extends RESP2 with:
- **Maps**: for key-value pairs `%<len>\r\n...`
- **Sets**: for unordered collections `~<len>\r\n...`
- **Pushes**: for asynchronous notifications `><len>\r\n...`
- Better streaming support
- More efficient for complex replies

### Protocol Selection

Client selects RESP version via HELLO command:
```
HELLO 3              # Switch to RESP3
HELLO 2              # Switch to RESP2 (default)
```

---

## 2. Client Input Buffer and Command Parsing

### Input Buffer Structure

Each connected client has:
- **Input buffer**: accumulated bytes from socket
- **Output buffer**: reply data to send back
- **Current command**: being parsed

### Parsing Process

1. **Socket readable**: data arrives, added to input buffer
2. **Inline parsing check**: is data in inline format (e.g., `SET key value\r\n`)?
3. **RESP parsing check**: is data in RESP format?
4. **Command extraction**: extract one command if complete
5. **Argument parsing**: parse command name and arguments
6. **Command lookup**: find command handler
7. **Command execution**: execute command
8. **Output buffering**: reply buffered to output buffer
9. **Repeat**: continue parsing if more data in buffer

### Input Buffer Size

Default: 16KB growing to 1GB max
- If command data exceeds buffer: error
- Very large commands rejected (protection against memory exhaustion)

Configuration:
```
client-max-intbuf-len 16777216    # Max 16MB for inline commands
```

### Inline Protocol (Telnet-friendly)

Clients can also use inline format:
```
GET key\r\n
PING\r\n
```

Useful for testing with `telnet` or `nc`. Automatically detected and parsed.

---

## 3. Pipelining — Sending Multiple Commands Without Waiting

### How Pipelining Works

**Without pipelining:**
```
Client              Server
  |                  |
  |------ SET key1 ------>|
  |<------ +OK -----------|
  |                  |
  |------ GET key1 ------>|
  |<------ "value1" ------|
  |                  |
```

Each command waits for response.

**With pipelining:**
```
Client              Server
  |                  |
  |------ SET key1 ------>|
  |------ GET key1 ------>|
  |------ INCR counter --->|
  |<------ +OK -----------|
  |<------ "value1" ------|
  |<------ :123 ----------|
  |                  |
```

All commands sent immediately, responses collected later.

### Pipelining Benefits

- **Latency reduction**: Round-trip latency amortized over N commands
- **Throughput improvement**: Batching utilizes network better
- **CPU efficiency**: Fewer system calls

### Pipelining Caveats

1. **Not atomic**: Commands from different clients interleaved
   ```
   Client A: SET x 1, INCR x, GET x
   Client B: SET x 10
   
   Possible result: Client A sees: +OK, :2, "2" or "10" (depends on interleaving)
   ```

2. **Memory accumulation**: If many commands pipelined, input buffer grows
3. **Response ordering**: Responses always match command order
4. **Error handling**: Errors don't stop subsequent commands (they're queued)

### Practical Pipelining

Typical use: 10-100 commands per batch. Beyond that:
- Diminishing returns on latency
- Memory overhead increases
- Risk of timeout while waiting for response

---

## 4. MULTI/EXEC Transactions

Transaction provides atomicity and isolation.

### MULTI/EXEC Syntax

```
MULTI                 # Start transaction
SET key1 value1       # Queued
LPUSH list1 item      # Queued
GET key1              # Queued
EXEC                  # Execute all atomically
```

### Behavior

1. Client sends MULTI
2. Server responds +OK, enters transaction mode
3. All subsequent commands are queued (not executed)
4. DISCARD: abort transaction
5. EXEC: execute all queued commands atomically
6. Server returns array of results (one per command)

### Atomicity Guarantee

- **All or nothing**: Either all commands execute or none (if client aborts with DISCARD)
- **No interleaving**: Commands from other clients don't execute between MULTI and EXEC
- **Ordering preserved**: Commands executed in sent order

### Watch Mechanism (Optimistic Locking)

```
WATCH key1 key2         # Optimistic lock on keys
MULTI
SET key1 newval1        # Queued
SET key2 newval2        # Queued
EXEC                    # Returns null if key watched and modified
```

**Behavior:**
1. WATCH marks keys as watched
2. If any watched key modified before EXEC: transaction aborted
3. EXEC returns null (not error)
4. Client must retry from WATCH

**Use case:** Optimistic concurrency control for check-and-set pattern.

### WATCH Limitations

1. **Only on same client**: WATCH is per-client connection
2. **No rollback**: If abort, no automatic retry
3. **Performance**: Watching many keys has overhead

### Transaction Errors

**Syntax error before EXEC:**
```
MULTI
GET key1 arg1 arg2    # Wrong number of args
EXEC                  # Returns error
```

Some implementations: EXECABORT error (whole transaction discarded).

**Runtime error during EXEC:**
```
MULTI
LPUSH mystring value  # mystring is not a list
EXEC                  # Returns array: [WrongTypeError, ...]
```

Some commands error, others succeed (atomicity NOT violated, partial execution OK).

### Critical MULTI/EXEC Properties

1. **Queuing**: All commands queued, not executed until EXEC
2. **Blind execution**: Server doesn't validate commands before queuing (syntax errors possible)
3. **Partial failure**: Some commands in transaction fail, others succeed
4. **No automatic rollback**: Failed command doesn't undo previous commands
5. **Isolation level**: Serializable (no dirty reads, lost updates, phantom reads)

---

## 5. Lua Scripting — Atomic Multi-Command Execution

Lua scripts provide atomicity and programmability.

### EVAL Syntax

```
EVAL "return redis.call('SET', KEYS[1], ARGV[1])" 1 mykey myvalue
```

Format: `EVAL script numkeys key1 key2 ... arg1 arg2 ...`

### Lua Environment

- Script has access to `redis.call()` and `redis.pcall()` functions
- `redis.call()`: execute command, return result or error
- `redis.pcall()`: execute command, return result or error object
- KEYS array: key names from script
- ARGV array: additional arguments

### Atomicity Guarantee

1. Script executes on main thread (no interleaving)
2. No other commands execute during script
3. Lua commands atomic as a unit
4. All database state changes atomic

### Script Caching

Scripts are cached by SHA1 hash:
```
SCRIPT LOAD "return 1"         # Returns SHA1 hash
EVALSHA <sha1> 0               # Run cached script
```

Benefits: Small script hash replaces full script transmission.

### Script Atomicity vs. MULTI/EXEC

| Feature | Lua Script | MULTI/EXEC |
|---------|-----------|-----------|
| Atomicity | Guaranteed | Guaranteed |
| Programmability | Full Lua language | Simple queuing |
| Performance | Slightly faster (1 RTT) | Multiple RTTs |
| Error handling | Lua semantics | Partial failure OK |
| Pre-validation | No (syntax errors at runtime) | Some validation before EXEC |

---

## 6. Pub/Sub — Asynchronous Messaging

Pub/Sub is publish-subscribe model within single server.

### Basic Operations

**Publish:**
```
PUBLISH channel1 "Hello"       # Returns number of subscribers
```

**Subscribe:**
```
SUBSCRIBE channel1 channel2    # Enters subscribe mode
```

**Unsubscribe:**
```
UNSUBSCRIBE channel1           # Exit subscribe mode
```

### Subscribe Mode

When client enters subscribe mode:
- Input buffer re-parsing: only subscribe/unsubscribe/psubscribe allowed
- Response format: special array format for messages
- Client blocks: waits for messages (or until disconnect)
- Other commands: not allowed (MULTI, GET, etc. rejected)

### Message Format

Messages arrive as:
```
*3
$7
message
$8
channel1
$5
Hello
```

Message object: ["message", "channel1", "Hello"]

### Pattern Subscription

```
PSUBSCRIBE user.*              # Subscribe to pattern
PUNSUBSCRIBE user.*            # Unsubscribe from pattern
```

Pattern uses glob-style syntax: `*`, `?`, `[abc]`

### Pub/Sub Characteristics

1. **No persistence**: Messages to unsubscribed clients lost
2. **At-most-once delivery**: Message may be lost if subscriber disconnected
3. **No acknowledgment**: Publisher doesn't know if message received
4. **No buffering**: Messages dropped if no subscribers
5. **Ordering**: Messages delivered in order per subscriber

### Pub/Sub Replication

In Sentinel/Cluster:
- Pub/Sub only works per-shard
- Messages not propagated across shards
- Per-instance pub/sub (not global)

---

## 7. Blocking Commands — BLPOP, BRPOP, BZPOPMIN, etc.

Blocking commands wait for data without busy-polling.

### BLPOP Semantics

```
BLPOP key1 key2 timeout        # Block up to timeout seconds
```

Behavior:
1. Check keys in order (key1, then key2)
2. If any key has data: pop and return immediately
3. If no data: block and wait
4. Client unblocked when:
   - Another client pushes to key → return [key, value]
   - Timeout expires → return nil
5. Timeout 0: wait indefinitely

### Timeout Precision

- Timeout in seconds, not milliseconds (use BLMPOP for ms)
- Precision: ~100ms typical
- Timeout 0 waits indefinitely (until data available)

### Critical Blocking Behavior

1. **Multiple clients blocking**: First blocked client unblocked (in order)
2. **Multiple keys**: Checked in order, first with data wins
3. **Atomicity**: Pop + push atomic (no interleaving)
4. **Replication**: Blocking operation replicated (replica executes at same point)
5. **Server shutdown**: Blocked client woken with connection close

### Blocking List Commands

- **BLPOP/BRPOP**: block and pop
- **BLMOVE**: block and move (Redis 6.2+)
- **BZPOPMIN/BZPOPMAX**: block and pop from sorted set

---

## 8. Command Latency and Performance Considerations

### Constant Time Commands (O(1))

- SET, GET, LPUSH (head), SADD, ZADD
- Latency: ~1-5 microseconds
- No scanning or iteration

### Linear Time Commands (O(n))

- LRANGE, KEYS, SCAN (per-iteration)
- Latency: proportional to number of elements
- Large lists can cause latency spikes

### Latency Spikes

Caused by:
- Eviction (if maxmemory exceeded)
- Lazy deletion (if large keys deleted)
- BGSAVE/BGREWRITEAOF (competes with main thread)
- Lua scripts (blocking execution)
- SCAN operations (full iteration)

### Monitoring Latency

Commands:
```
LATENCY DOCTOR          # Latency analysis
SLOWLOG GET 10          # Last 10 slow commands
SLOWLOG LEN             # Number of recorded slow commands
```

Configuration:
```
slowlog-log-slower-than 10000    # Log commands > 10ms
slowlog-max-len 128              # Keep last 128 commands
```

---

## 9. Critical Implications for Code Auditing

1. **Pipelining not atomic**: Interleaving between pipelines from different clients
2. **MULTI/EXEC queuing**: Syntax errors detected before EXEC (some implementations)
3. **Lua atomicity**: Guaranteed, but script must be fast (no long-running scripts)
4. **WATCH optimization**: Only guarantees key not modified, doesn't prevent concurrent transactions
5. **Pub/Sub unreliability**: No persistence, no ordering across subscribers
6. **Blocking commands**: Precision ~100ms, not suitable for precise timing
7. **Input buffer limits**: Very large single commands rejected
8. **Response order**: Always matches command order (even if commands error)
9. **RESP protocol**: Must correctly handle multi-byte integers and nil values
10. **RESP3 compatibility**: Optional, clients must handle both versions
