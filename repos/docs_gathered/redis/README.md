# Redis Documentation for Code Quality Analysis

Comprehensive reference documentation for Redis internal architecture, protocols, and behavioral contracts. Designed for code quality auditing, bug detection, and compliance verification against Redis specifications.

## Overview

These documents provide detailed specifications of Redis behavior at the level of abstraction needed for AI-driven code analysis. Rather than focusing on command tutorial content, they emphasize:

1. **Behavioral contracts**: Exact specifications for what Redis MUST and MUST NOT do
2. **Atomicity guarantees**: Where atomicity is guaranteed and where it's not
3. **Edge cases**: Boundary conditions, overflow scenarios, error cases
4. **Performance implications**: Why operations have variable latency
5. **Concurrency semantics**: Replication, cluster, transactions, blocking
6. **Protocol specifications**: RESP, cluster gossip, replication protocol

## Document Structure

| Document | Focus |
|----------|-------|
| **01-ARCHITECTURE.md** | Event loop, single-thread model, I/O threading, modules, background tasks |
| **02-DATA_STRUCTURES_AND_ENCODING.md** | String, list, set, hash, sorted set internals and encoding transitions |
| **03-PERSISTENCE.md** | RDB snapshots, AOF logs, fsync policies, mixed mode, data loss scenarios |
| **04-REPLICATION.md** | Master-replica protocol, PSYNC, partial resync, backlog, consistency |
| **05-CLUSTER_PROTOCOL.md** | Hash slots, gossip, failover, migration, MOVED/ASK redirection |
| **06-MEMORY_MANAGEMENT.md** | Eviction policies, lazy free, defragmentation, memory accounting |
| **07-COMMAND_PROCESSING.md** | RESP protocol, pipelining, MULTI/EXEC, Lua scripts, pub/sub, blocking |
| **08-BEHAVIORAL_CONTRACTS.md** | Exact semantics, atomicity, edge cases, type checking, expiration |
| **INDEX.md** | Cross-reference guide and audit checklist |

See [INDEX.md](INDEX.md) for complete table of contents.

## Key Contracts Specified

### Atomicity Guarantees

**Single command level**: Every Redis command executes atomically without interleaving. No other client's command can execute during a single command.

**MULTI/EXEC transactions**: All queued commands execute atomically. No other client's commands execute between MULTI and EXEC.

**Lua scripts**: Script execution is atomic. redis.call() functions execute without interleaving from other clients.

**Replication**: NOT atomic (write visible on master before replica). WAIT command provides synchronous replication but only guarantees acknowledgment, not persistence.

### Consistency Semantics

**Eventual consistency**: Replication uses eventual consistency. Write visible on master immediately, on replica after ~1ms.

**Type checking**: Operations check type before execution. WRONGTYPE error if key holds wrong type.

**Expiration**: Expired keys deleted lazily (on access) and actively (background sampling). No guarantee on exact deletion time.

**Cluster**: Eventually consistent topology discovery via gossip. Slot migration uses two-phase state machine.

### Precision and Edge Cases

**Blocking timeouts**: ~100ms precision, not suitable for sub-millisecond timing.

**LRU/LFU eviction**: Sampling-based approximation, not true LRU/LFU.

**Key expiration**: Millisecond precision for TTL, but deletion probabilistic (not deterministic).

**Numeric operations**: INCR/DECR support [-2^63, 2^63-1] range with overflow errors.

**Lists and ranges**: Negative indices supported. Out-of-range indices return empty/nil, not errors.

## Critical Implications for Code Analysis

### Latency and Performance

1. **Event loop bottleneck**: Single thread executes all commands. Long operations block all clients.
2. **Eviction latency**: Eviction may spike latency when maxmemory exceeded.
3. **Lazy free**: Key deletion async, but key inaccessible immediately.
4. **Encoding transitions**: Automatic encoding changes cause variable latency.
5. **SCAN operations**: Safe (non-blocking) but O(n) iteration.

### Concurrency and Consistency

1. **Main thread bottleneck**: All commands, Lua scripts, blocking operations execute on main thread.
2. **Replication lag**: Writes visible on master before replica (eventual consistency).
3. **Cluster topology**: Gossip-based discovery has transient inconsistencies.
4. **Partial resync**: Can fail if backlog exhausted or replica offline too long.
5. **WAIT limitations**: Only guarantees replication delivery, not persistence.

### Data Integrity

1. **Type safety**: Type checking prevents silent data corruption.
2. **Expiration precision**: Lazy deletion means expired keys may temporarily exist.
3. **Memory limits**: Eviction may cause key loss (configured per-policy).
4. **Persistence**: RDB/AOF durability depends on fsync policy.
5. **Replication loss**: Master crashes before replica sees write causes data loss.

### Edge Cases

1. **Overflow**: INCR/DECR overflow on [2^63-1, -2^63] boundaries.
2. **Empty collections**: Proper nil/empty array distinction.
3. **Range operations**: Inclusive on both ends, support negative indices.
4. **Blocking commands**: Return nil on timeout (not error).
5. **Pub/Sub**: No persistence, messages to unsubscribed clients lost.

## How to Use These Documents

### For Code Auditing

1. Start with **ARCHITECTURE.md** to understand event loop constraints
2. Review **COMMAND_PROCESSING.md** for protocol compliance
3. Check **BEHAVIORAL_CONTRACTS.md** for exact operation semantics
4. Consult **PERSISTENCE.md** and **REPLICATION.md** for durability and consistency
5. Use **INDEX.md** for cross-reference and audit checklist

### For Bug Investigation

1. Identify the Redis component (persistence, replication, cluster, memory, etc.)
2. Find the relevant document (01-08)
3. Search for "MUST", "MUST NOT", "Critical", "Edge case"
4. Cross-reference with other documents as needed

### For Understanding Trade-offs

1. **Atomicity vs Performance**: See ARCHITECTURE.md, COMMAND_PROCESSING.md
2. **Consistency vs Availability**: See REPLICATION.md, CLUSTER_PROTOCOL.md
3. **Memory vs Performance**: See MEMORY_MANAGEMENT.md, DATA_STRUCTURES_AND_ENCODING.md
4. **Durability vs Latency**: See PERSISTENCE.md

## Behavioral Specifications Format

Each document follows a consistent format:

- **Section headers**: Organize topics hierarchically
- **MUST/MUST NOT statements**: Absolute requirements
- **Examples**: Concrete scenarios illustrating behavior
- **Edge cases**: Boundary conditions and error scenarios
- **Implications**: What this means for code auditing

### Key Words

- **MUST**: Absolute requirement (must implement)
- **MUST NOT**: Absolute prohibition (must not implement)
- **SHOULD**: Strong recommendation (but not mandatory)
- **MAY**: Optional
- **CRITICAL**: Important for code auditing or bug detection
- **Edge case**: Boundary condition or unusual scenario

## Sources

All documentation extracted from:

- Redis source code (https://github.com/redis/redis)
- Official documentation (https://redis.io/docs)
- RESP protocol specification (https://redis.io/docs/latest/develop/reference/protocol-spec)
- Cluster specification (https://redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec)
- Community discussions and issue analysis
- Implementation analysis and benchmarking

## Version Coverage

These documents cover Redis 6.0 through 7.x with attention to:

- Major version differences (5.x → 6.0 I/O threading, 7.x listpack)
- Breaking changes (quiclist improvements, deprecated encodings)
- Backward compatibility issues
- Default configuration changes

## Maintenance Notes

- These documents focus on behavioral contracts, not implementation details
- Internal structure may change; external behavior (MUST/MUST NOT) remains stable
- New versions may add features; documented contracts remain valid
- Tested against Redis 7.x official documentation

---

**For complete index and cross-reference, see [INDEX.md](INDEX.md)**
