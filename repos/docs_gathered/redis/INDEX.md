# Redis Documentation Index

Complete reference documentation for Redis internal architecture, protocols, and behavioral contracts. These docs are optimized for code quality analysis and bug detection.

---

## Document Overview

### 1. [Architecture](01-ARCHITECTURE.md)
Core Redis architecture covering the event loop, single-threaded execution model, and I/O threading evolution.

**Topics:**
- Single-threaded event loop with Reactor pattern
- File events (network I/O) and time events (scheduled tasks)
- Command execution pipeline and atomicity guarantees
- I/O threading (Redis 6.0+) with synchronization barriers
- Blocking commands and event-driven waiting
- Key expiration: lazy deletion and active background expiration
- Modules and thread safety constraints
- Replication and background tasks (BGSAVE, AOF rewrite)
- Pub/Sub model implementation
- Memory and data alignment

**For auditing:** Understand event loop bottlenecks, blocking semantics, module API constraints, and performance implications of background tasks.

---

### 2. [Data Structures and Encoding](02-DATA_STRUCTURES_AND_ENCODING.md)
Internal representations of Redis data types and automatic encoding transitions.

**Topics:**
- Strings: int, embstr, raw encodings with mutation semantics
- Lists: quicklist (primary), ziplist (deprecated), linkedlist (removed)
- Sets: hashtable and intset encodings with automatic transitions
- Hashes: hashtable and ziplist/listpack encodings
- Sorted Sets: skiplist + hashtable and ziplist/listpack variants
- Streams: radix tree structure, consumer groups, entry IDs
- Encoding transition rules and thresholds
- Performance implications of encoding choices
- Memory efficiency and element encoding

**For auditing:** Understand why operations have variable latency (encoding transitions), find bugs in encoding-specific code paths, verify proper type checking, and detect memory efficiency issues.

---

### 3. [Persistence](03-PERSISTENCE.md)
Durability mechanisms: RDB snapshots, AOF logs, mixed mode, and fsync policies.

**Topics:**
- RDB: point-in-time snapshots with SAVE/BGSAVE, file format, loading
- AOF: append-only file with three fsync policies (always, everysec, no)
- Mixed persistence: hybrid RDB + AOF with automatic scheduling
- Replication backlog: buffer for partial resync, TTL, overflow
- Data loss scenarios across different configurations
- Background task scheduling and mutual exclusion
- RDB checksum and AOF truncation recovery
- Startup precedence and recovery procedures
- Performance tuning and recovery time expectations

**For auditing:** Understand durability guarantees (or lack thereof), detect race conditions between BGSAVE and BGREWRITEAOF, verify fsync policy enforcement, and identify data loss scenarios.

---

### 4. [Replication](04-REPLICATION.md)
Master-replica protocol, PSYNC partial resync, backlog, and consistency semantics.

**Topics:**
- Master-replica architecture with fan-out and chain topology
- Replication ID and offset tracking
- SYNC (full resync) vs PSYNC (partial resync) protocol
- Replication backlog: circular buffer, TTL, exhaustion scenarios
- PSYNC response handling: FULLRESYNC vs CONTINUE
- Partial resync failure conditions and fallback to full sync
- Eventual consistency guarantees and race conditions
- WAIT command: synchronous replication semantics and limitations
- Replica behavior: read-only mode, no automatic write forwarding
- Replication chain: replica with replica topology
- Sentinel and automatic failover (separate tool)
- Cluster replication integration

**For auditing:** Identify consistency bugs (master writes before replica sees them), verify WAIT command limitations, detect backlog exhaustion scenarios, and verify replication protocol compliance.

---

### 5. [Cluster Protocol](05-CLUSTER_PROTOCOL.md)
Distributed key-value sharding with gossip topology discovery, slot migration, and client redirection.

**Topics:**
- Hash slots (16384 total) and keyspace partitioning
- Hash slot calculation (CRC16) and hash tags
- Slot states: STABLE, MIGRATING, IMPORTING, ASKED
- Gossip protocol: PING/PONG messages, cluster bus
- Master-replica failover with replication offset-based election
- Slot migration: SETSLOT commands and state machine
- Client redirection: MOVED (permanent) vs ASK (temporary)
- ASKING mechanism for migration transparency
- Pub/Sub per-shard topology (not cross-shard)
- Transaction restrictions to single slot
- CLUSTER SLOTS and CLUSTER NODES commands
- Cluster limitations: KEYS, SCAN, FLUSHDB per-shard

**For auditing:** Verify slot assignment correctness, detect hash slot calculation mismatches, find migration race conditions, understand client redirection semantics, and identify cluster-specific atomicity violations.

---

### 6. [Memory Management](06-MEMORY_MANAGEMENT.md)
Memory limits, eviction policies, lazy free deletion, defragmentation, and accounting.

**Topics:**
- Maxmemory configuration and behavior on overflow
- Eviction policies: noeviction, allkeys-lru, volatile-lru, allkeys-lfu, volatile-lfu, volatile-ttl, random variants
- LRU/LFU sampling for performance (approximation, not exact)
- Eviction process and edge cases (empty database, all permanent keys)
- Lazy free: async deletion without blocking
- UNLINK command for explicit async deletion
- Active defragmentation: copy-on-write, idle-time optimization
- Memory fragmentation ratio and causes
- Per-object overhead and memory accounting
- Memory efficiency tips and encoding selection
- Expiration and memory: TTL storage, lazy vs. active deletion

**For auditing:** Detect eviction bugs, understand latency spikes during eviction, verify lazy free semantics, identify fragmentation risks, and validate memory accounting.

---

### 7. [Command Processing](07-COMMAND_PROCESSING.md)
Protocol handling, pipelining, transactions, and pub/sub implementation.

**Topics:**
- RESP2 and RESP3 protocol formats
- Protocol selection via HELLO command
- Client input buffer, circular buffer semantics, size limits
- Command parsing: inline and RESP protocol
- Pipelining: multiple commands without waiting
- Pipelining caveats: not atomic, response ordering guaranteed
- MULTI/EXEC transactions: queuing, EXEC execution, atomicity
- WATCH mechanism: optimistic locking for check-and-set
- Transaction errors: syntax before EXEC, runtime during EXEC
- Lua scripting: EVAL/EVALSHA with atomicity
- Script caching by SHA1 hash
- Pub/Sub: SUBSCRIBE, PUBLISH, pattern matching
- Subscribe mode: restricted input parsing, async message delivery
- Blocking commands: BLPOP, BRPOP, BZPOPMIN with timeout semantics
- Command latency: O(1) vs O(n) operations

**For auditing:** Verify protocol compliance, detect pipelining atomicity issues, validate MULTI/EXEC semantics, understand Lua script constraints, and identify blocking command timeout precision issues.

---

### 8. [Behavioral Contracts](08-BEHAVIORAL_CONTRACTS.md)
Exact specifications for atomicity, consistency, edge cases, and gotchas.

**Topics:**
- Single command atomicity and no-interleaving guarantee
- MULTI/EXEC transaction atomicity and isolation level (serializable)
- Lua script atomicity and redis.call semantics
- Key expiration: millisecond precision, lazy + active deletion
- Expired key visibility: never returned, lazy delete on access
- Expiration replication: EXPIRE commands sent, clock skew possible
- Type checking: performed before execution, WRONGTYPE errors
- Type conversion: no implicit conversion
- Numeric string semantics for INCR/DECR
- List index semantics: negative indices, out-of-range behavior
- LRANGE inclusive semantics and edge cases
- LPUSH/RPUSH multiple elements: atomic, ordered
- LPOP/RPOP count semantics and edge cases
- Set member uniqueness and SADD behavior
- Set iteration order: undefined
- Set operations across keys: SINTER, SUNION, SDIFF
- Hash field overwrite and HSET return value
- Sorted set score: IEEE 754 double, precision limits, special values
- Score comparison: float comparison with lexicographic tie-breaking
- Stream entry IDs: unique, ordered, auto-generated or explicit
- Consumer group semantics and XREADGROUP
- String APPEND/GETRANGE/SETRANGE edge cases
- INCR/DECR: non-existent keys, overflow, underflow
- KEYS vs SCAN: blocking vs non-blocking, cursor semantics
- BLPOP multiple keys: order preservation, FIFO unblocking
- WAIT command: replication not persistence
- Lua script determinism: allowed non-determinism (TIME, RANDOMKEY)
- Module API thread safety and RM_BlockClient semantics

**For auditing:** Verify exact behavioral compliance, identify atomicity violations, find edge case handling bugs, and validate consistency guarantees.

---

## Cross-Reference by Topic

### Event Loop and Threading
- **Architecture**: Event loop, file events, time events, main thread bottleneck
- **Command Processing**: Command execution on main thread, pipelining
- **Memory Management**: Eviction during command execution

### Atomicity
- **Architecture**: Single-threaded command execution
- **Command Processing**: MULTI/EXEC, Lua scripts, pipelining
- **Behavioral Contracts**: Atomicity guarantees and edge cases

### Replication
- **Architecture**: Master-replica, BGSAVE, replication stream
- **Persistence**: Replication backlog, AOF/RDB load on startup
- **Replication**: PSYNC, partial resync, consistency
- **Cluster Protocol**: Master-replica failover

### Consistency
- **Replication**: Eventual consistency, race conditions
- **Cluster Protocol**: Slot ownership, gossip reliability
- **Behavioral Contracts**: Expiration precision, WAIT semantics

### Memory
- **Data Structures**: Encoding choices and thresholds
- **Memory Management**: Eviction, fragmentation, lazy free
- **Persistence**: RDB/AOF memory usage, BGSAVE copy-on-write

### Protocol
- **Command Processing**: RESP, input buffer, pipelining
- **Cluster Protocol**: Client redirection (MOVED/ASK)

---

## Key Contracts and Guarantees

### Absolute Guarantees
1. **Single-command atomicity**: No interleaving within single command
2. **Type checking**: Operations fail on wrong type
3. **Command ordering**: Commands execute in sent order (per client)
4. **MULTI/EXEC serialization**: Transaction commands not interleaved

### Probabilistic Guarantees
1. **Key expiration**: Eventually deleted (lazy + active), not deterministic
2. **Eviction**: Approximately follows policy (sampling-based)
3. **Blocking timeouts**: ~100ms precision, not guaranteed

### Eventual Consistency
1. **Replication**: Write visible on replica with ~1ms latency
2. **Cluster topology**: Gossip-based discovery (eventual consistency)
3. **Expiration**: Triggered by access or background task (timing variable)

---

## Critical Audit Checklist

- [ ] Verify event loop never blocks on main thread
- [ ] Check I/O threading barriers properly synchronize
- [ ] Validate atomicity at command level (no interleaving)
- [ ] Verify type checking before operation execution
- [ ] Check expiration: lazy deletion on access, background sampling
- [ ] Validate MULTI/EXEC queuing and EXEC execution
- [ ] Verify Lua script atomicity and timeout handling
- [ ] Check replication: PSYNC vs SYNC, backlog overflow
- [ ] Validate cluster: slot assignment, MOVED vs ASK redirection
- [ ] Check eviction: policy application, latency spikes
- [ ] Verify persistence: RDB/AOF corruption handling, fsync semantics
- [ ] Check modules: thread safety, global state protection
- [ ] Validate edge cases: empty collections, type mismatches, overflows
- [ ] Check memory accounting: fragmentation, object overhead
- [ ] Verify protocol compliance: RESP parsing, pipelining semantics

---

## Related Resources

- Redis source: https://github.com/redis/redis
- Official docs: https://redis.io/docs/
- Protocol spec: https://redis.io/docs/latest/develop/reference/protocol-spec/
- Cluster spec: https://redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec/
