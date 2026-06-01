# Redis Architecture — Event Loop, Threading, and I/O Model

Extracted from redis.io documentation, GitHub source, and community analysis. This document covers the core architecture decisions that drive Redis performance and the modern I/O threading evolution.

Sources: redis.io/docs, GitHub redis/redis, Redis community blogs.

---

## 1. Single-Threaded Event Loop — Core Design

Redis uses a single-threaded event loop architecture based on the Reactor Pattern. This is the foundational design choice that enables atomicity without locks.

### Event Loop Basics

The main event loop processes two categories of events:

**File Events** (network I/O)
- Triggered when a client socket becomes readable (command data available)
- Triggered when a client socket becomes writable (ready to send response)
- File event handler reads incoming commands from client input buffer
- Handler executes command and writes response to client output buffer
- Uses `select()`, `poll()`, `epoll()`, or `kqueue()` depending on OS

**Time Events** (scheduled tasks)
- Tasks scheduled to run at a specific time or after an interval
- Key expiration checks (periodic background expiry)
- AOF rewrite scheduling
- BGSAVE checks
- Replication synchronization
- Cluster gossip messages
- All time events are demultiplexed with file events in a single loop

### Performance Characteristics

- **Zero context switching**: Single thread never blocked on locks
- **No synchronization overhead**: All state modifications are sequential
- **Predictable latency**: No garbage collection pauses or lock contention
- **Memory efficiency**: One stack per connection, no thread-local storage
- **Cache efficiency**: Hot data remains in CPU L1/L2 cache

The single thread executes commands sequentially, making each operation atomic by design. Two critical guarantees:
1. No two commands execute in parallel
2. Command never sees partial writes from another command

---

## 2. Command Execution Pipeline

Commands move through this pipeline on the main thread:

### Phase 1: Input Buffer and Parsing
- Client data arrives on socket → added to client's input buffer
- Parser reads from buffer and builds command representation
- Input buffer operates on circular buffer principle
- Incremental parsing (handle partial commands)

### Phase 2: Command Execution
- Command handler executes on main thread (ALL commands run here)
- Database state is modified directly
- Responses written to output buffer
- If command blocks (e.g., BLPOP), blocking mechanism invokes at this phase

### Phase 3: Output Buffer and Response
- Response queued in client's output buffer
- When socket is writable, data sent to client
- If output buffer fills, write attempt is retried next event loop iteration
- Client connection remains active throughout

This pipeline guarantees that commands from the same client execute in order, and commands from different clients are interleaved at command boundaries.

---

## 3. I/O Threading Model (Redis 6.0+)

Starting with Redis 6.0, optional I/O threading was introduced to offload network read/write operations without changing command execution semantics.

### Design Constraint

**Command execution remains single-threaded**. The main thread MUST execute all commands. I/O threads only handle network I/O.

### I/O Thread Architecture

Configuration: `io-threads N` (default 1, which disables the feature)

**Main Event Loop Thread**
- Accepts new connections
- Demultiplexes sockets
- Executes all Redis commands
- Writes responses to output buffers

**I/O Worker Threads** (N-1 additional threads)
- Wake up when main thread has work queued
- Read from client sockets into input buffers (synchronous)
- Write to client sockets from output buffers (synchronous)
- Main thread waits for all I/O threads to complete before executing commands

### Synchronization Barriers

I/O threading uses barriers at two points:

1. **Read Barrier**: Main thread waits for all I/O threads to finish reading
   - All input buffers filled
   - All commands parsed
   - Then command execution proceeds

2. **Write Barrier**: Main thread waits for all I/O threads to finish writing
   - All output buffers flushed to sockets
   - Then next event loop iteration begins

This preserves the single-threaded command execution guarantee while parallelizing network I/O.

### Performance Impact

- Benefits systems with many client connections (100+)
- Reduces main thread CPU usage for I/O
- May increase latency if barriers are expensive
- Default disabled (io-threads 1) for small deployments

---

## 4. Blocking Commands and Event-Driven Waiting

Blocking commands (BLPOP, BRPOP, BZPOPMIN, etc.) do not block the main thread.

### Mechanism

1. Client issues blocking command (e.g., BLPOP key1 timeout)
2. Command handler checks if data is immediately available
3. If no data: command handler adds client to "waiting clients" queue
4. Main thread continues processing other clients
5. When data becomes available (another client pushes), waiting client is unblocked
6. Response is queued in client's output buffer
7. Next event loop iteration sends response

**Timeout Handling**: Timeout is registered as a time event. If timeout fires before unblocking, client receives nil response.

**Important**: Only the specific client blocks, not the server. Other clients continue executing commands.

---

## 5. Key Expiration Background Task

Expiration is NOT deterministic—Redis uses probabilistic expiration.

### Deletion Strategy

Redis uses a hybrid approach:

**Lazy Deletion**: When a key is accessed via a command, if it's expired, delete before returning
- Ensures expired keys never returned to client
- No background overhead if key is not accessed
- Problem: Expired but unaccessed keys consume memory

**Active Background Expiration**: During event loop, periodically check random sample of keys
- Default: 25 iterations per second
- Each iteration: sample ~100 keys from random database
- If key expired: delete and continue
- If expiration rate > 25%, repeat iteration (adaptive)
- Prevents unbounded memory growth

### Precision and Consistency

- Expiration is checked in milliseconds (TTL vs PTTL)
- But actual deletion is probabilistic
- Lua scripts see consistent snapshot (expiration frozen during script execution)
- No guarantee on exact deletion time

---

## 6. Modules and Thread Safety

Redis Modules can extend the server with custom commands and data types.

### Module Execution

- Module commands execute on main thread like built-in commands
- Module code MUST NOT block (or use official blocking API)
- Module API is NOT thread-safe for general use

### Blocking Operations in Modules

Modules can implement blocking operations:
1. Module command calls RM_BlockClient()
2. Client is blocked, response deferred
3. Module can spawn worker thread to do expensive work
4. Worker thread calls RM_UnblockClient() to signal completion
5. Unblock handler executes atomically on main thread
6. Response sent to client

The unblock handler runs as an atomic execution unit—all operations are wrapped in implicit MULTI/EXEC when replicated.

### Thread Safety Constraint

Module must acquire the Redis global lock before calling RM_Call() from worker thread. Only one worker thread can hold the lock at a time.

---

## 7. Replication and Background Tasks

Master and replica processes are separate:

### Master
- Main event loop handles client commands
- Replication buffer maintained in memory
- Sends stream of writes to connected replicas
- Does not block on replica acknowledgment (unless WAIT command used)

### Replica
- Separate event loop
- Reads commands from master's replication stream
- Executes commands in same order as master
- Maintains its own database state
- Can serve reads immediately
- Can have its own replicas (replication chain)

### BGSAVE and AOF Rewrite

Both operations fork child processes:
- Child inherits entire memory snapshot (copy-on-write)
- Child writes to disk (I/O in background)
- Main process continues handling client commands
- No blocking on fork or disk I/O

---

## 8. Pub/Sub Model

Pub/Sub is fully implemented in the main event loop.

### Publisher Side
- Client publishes message
- Server finds all subscribers to that channel
- Message queued in each subscriber's output buffer
- Next event loop iteration sends messages

### Subscriber Side
- Client enters subscribe mode
- Special input parsing (only subscribe/unsubscribe/psubscribe allowed)
- Messages arrive asynchronously as they're published
- Subscriber receives messages in order from any publisher

**Important**: Pub/Sub has no persistence. Messages to subscribers that are not connected are lost.

---

## 9. Memory and Data Alignment

### Memory Allocation
- All allocations done on main thread (thread-safe malloc)
- Fragmentation addressed by lazy free deletion and active defragmentation

### Data Structure Alignment
- String: byte array with length prefix
- List: doubly-linked list or ziplist (encoding changes based on size)
- Set: hash table or intset (encoding changes)
- Hash: hash table or ziplist
- Sorted Set: hash table + skip list or ziplist + list (encoding changes)
- Stream: radix tree + consumer groups

Encoding transitions are automatic based on element count and size thresholds.

---

## 10. Critical Implications for Code Auditing

When auditing Redis code, these architectural properties are critical:

1. **Atomicity is built-in**: No locking needed for command-level operations
2. **Main thread is bottleneck**: All expensive operations here impact latency
3. **Memory is shared**: No isolation between logical operations
4. **Event loop must not block**: Any blocking code in command handler causes observable stalls
5. **I/O threads create synchronization points**: Barriers must be correctly implemented
6. **Background tasks compete for CPU**: Expiry, BGSAVE, AOF rewrite all run in event loop
7. **Modules must respect constraints**: Thread safety rules are not enforced by compiler
