# Redis Replication — Master-Replica Protocol, PSYNC, Partial Resync, and Backlog

Extracted from redis.io documentation and GitHub discussions. This document covers replication protocol details, synchronization semantics, and consistency guarantees.

Sources: redis.io/docs/latest/operate/oss_and_stack/management/replication/, GitHub redis/redis issues.

---

## 1. Replication Architecture Overview

### Master-Replica Model

**Master (Primary)**
- Accepts read and write commands
- Maintains list of connected replicas
- Sends stream of write commands to replicas
- Does not wait for replica acknowledgment (unless WAIT used)
- Can have multiple replicas (fan-out)

**Replica (Slave)**
- Accepts read commands only (writes rejected by default)
- Connects to master and requests synchronization
- Executes commands in same order as master
- Maintains independent database state
- Can serve reads immediately (eventual consistency)
- Can be replication source for other replicas (chain replication)

### Replication Topology

Possible topologies:
- Single master, multiple replicas (fan-out)
- Master-replica chain (A → B → C)
- Multi-replica (each replica can have its own replicas)

No native support for:
- Circular replication (avoided by design)
- Multi-master (use Redis Cluster or Sentinel)
- Replica-to-replica writes (not supported)

---

## 2. Replication ID and Offset

Every Redis master maintains:

### Replication ID (runid)

- Large pseudo-random 40-character string
- Changes on every restart
- Uniquely identifies master "history" or "timeline"
- Used to distinguish between different master instances

### Replication Offset

- 64-bit counter
- Increments by number of bytes produced in replication stream
- Tracks "position" in master's write history
- Reset to 0 on master startup

### Replica Tracking

Replica maintains:
- **Master replication ID**: ID of master it's replicating from
- **Master offset**: Last offset processed from master
- Used in PSYNC command for partial resync negotiation

---

## 3. Synchronization Phases

### Phase 1: Replica Connects to Master

Replica initiates:
```
PING                # Test connection
REPLCONF listening-port <port>   # Register replica port
REPLCONF ACK 0      # Start with offset 0
PSYNC <masterid> <offset>        # Request sync
```

### Phase 2: Full Sync (SYNC) vs Partial Sync (PSYNC)

**Full Sync Scenario**
- Replica sends PSYNC with unknown master ID or non-existent offset
- Master responds: `+FULLRESYNC <masterid> <offset>`
- Master initiates BGSAVE
- Master sends RDB snapshot over TCP
- Replica loads RDB (clears database first)
- Replication stream begins (all new writes from this point)

**Partial Sync Scenario**
- Replica sends PSYNC with known master ID and offset
- Master checks: offset exists in replication backlog?
- If YES: master responds `+CONTINUE` with current offset
- Replication stream resumes from replica's offset
- NO RDB transfer (only missing commands)
- If NO: master falls back to full sync

### Phase 3: Ongoing Replication

Once replica synchronized:
- Master sends every write command to replica
- Replica executes in same order
- Replica acknowledges with REPLCONF ACK offset
- Master uses acknowledgments for:
  - Tracking replica state
  - WAIT command synchronous replication
  - Minimum replicas monitoring

---

## 4. Replication Backlog Buffer

### Purpose

Backlog is a circular buffer maintained by master containing recent replication stream data.

### Configuration

```
repl-backlog-size 1mb          # Size of backlog (default 1MB)
repl-backlog-ttl 3600          # How long to keep backlog after replica disconnects
```

### Behavior

- Master writes every byte of replication stream to backlog
- When backlog fills, oldest entries discarded (circular)
- Replica disconnects: backlog retained for `repl-backlog-ttl` seconds
- Replica reconnects within TTL: partial resync possible
- Replica reconnects after TTL: full resync necessary

### Example

With 1MB backlog:
- If 500KB of writes occur, backlog contains those 500KB
- If 1.5MB of writes occur, only last 1MB retained (first 500KB discarded)
- Replica reconnecting after 500KB writes: can partial resync if offset still in backlog

---

## 5. PSYNC Protocol Details

### PSYNC Command Format

```
PSYNC <master-replication-id> <replication-offset>
```

### Master Response Options

**`+FULLRESYNC <masterid> <offset>`**
- Full sync required
- Master starts BGSAVE
- New master ID returned to replica
- Offset 0 or current depends on implementation

**`+CONTINUE <offset>`**
- Partial sync accepted
- Start sending from this offset
- No RDB needed

**`-ERR`** (or similar)
- Error condition (rare)
- Replica should retry with SYNC (fallback)

### Partial Resync Failure Conditions

Partial sync NOT possible if:
1. Replica's master ID doesn't match master's ID
2. Replica's offset is not in backlog (too far behind)
3. Backlog TTL expired (replica disconnected too long)
4. Explicit PSYNC config prohibits (rare)

---

## 6. Consistency Guarantees and Caveats

### Eventual Consistency

- Master accepts write → returns to client immediately
- Write is NOT immediately visible on replica
- Replica executes write with ~1ms latency (network + processing)
- Client reading from replica may see stale data
- No guarantee on order of write propagation to multiple replicas

### Race Conditions

**Scenario: Master Crash Before Replica Sees Write**
1. Client writes to master
2. Master returns success
3. Master crashes before sending write to replica
4. Replica never sees write
5. If replica becomes new master: write lost
6. Inconsistency: client thinks data written, replica doesn't have it

Mitigation: WAIT command provides synchronous replication.

### Replica Disconnect During Replication

When replica disconnects:
- Backlog buffer retains replication stream for TTL seconds
- If TTL expires: backlog discarded
- Replica reconnecting after TTL: must perform full resync
- Full resync clears replica's database (dangerous)

---

## 7. WAIT Command — Synchronous Replication

### Syntax

```
WAIT <replica-count> <timeout-ms>
```

### Behavior

1. Client sends write command (before WAIT)
2. Client sends WAIT command
3. Server waits for:
   - At least `replica-count` replicas to acknowledge write, OR
   - `timeout-ms` milliseconds elapse
4. WAIT returns number of replicas that acknowledged

### Semantics

- WAIT does NOT make write atomic (write already executed)
- WAIT only waits for replication acknowledgment
- If timeout occurs, returns actual count (may be less than requested)
- Client cannot know if acknowledged replicas actually persisted data
- Replicas may lose data on crash (if no persistence)

### Critical Behavior

1. **Multiple replicas**: WAIT waits for parallel acknowledgments (all replicas, not sequential)
2. **Duplicate WAIT**: Subsequent WAIT waits for MORE replicas (not same write replicated again)
3. **Timeout**: Returns count at timeout moment, not error
4. **No ordering**: WAIT does not order multiple client writes (each client's WAIT is independent)
5. **Replica timeout**: If replica not responding, WAIT blocks until timeout
6. **Module commands**: Module commands do NOT support WAIT (only built-in commands)

---

## 8. Replication Configuration and Behavior

### Important Configuration Options

```
repl-diskless-sync no              # Whether to skip RDB disk write (experimental)
repl-diskless-sync-delay 5         # Delay before starting diskless sync
repl-diskless-load disabled        # How to load RDB on replica
repl-disable-tcp-nodelay no        # Disable TCP_NODELAY (forces ACK batching)
repl-backlog-size 1mb              # Backlog buffer size
repl-backlog-ttl 3600              # Backlog retention time
```

### Diskless Replication (Experimental)

- Master sends RDB over network directly (no disk write)
- Faster for large datasets (no disk I/O)
- Higher network load
- Risk: if network interrupted, must restart
- Configuration: `repl-diskless-sync yes`

### TCP_NODELAY Impact

- `repl-disable-tcp-nodelay no` (default): nagle algorithm disabled, ACKs sent immediately
- `repl-disable-tcp-nodelay yes`: ACKs batched (lower network overhead, higher latency)

---

## 9. Replica Behavior and Limitations

### Read Commands on Replica

- All read commands (GET, LRANGE, ZRANGE, etc.) execute successfully
- Returns potentially stale data (may lag master by milliseconds)
- No automatic routing to master (application must handle)

### Write Commands on Replica

- By default: rejected with error (READONLY)
- Configuration: `slave-read-only yes` (default)
- If disabled (`slave-read-only no`): writes allowed but NOT replicated to other replicas
- Write on replica creates replication cycle: replica → master → replica (dangerous)

### Replica with Replica

A replica can accept writes from other replicas:
```
Master → Replica A → Replica B
```

- Replica A receives from master, forwards to Replica B
- Replica B sees writes from Replica A (as if Replica A were master)
- Replica A maintains own replication ID
- Creates replication chain (limited by network latency accumulation)

---

## 10. Replication Stream Encoding

### Format

Replication stream is RESP protocol:
- Every write command is serialized in RESP format
- Sent to all connected replicas
- Replicas parse and execute

### Commands Replicated

- All write commands: SET, LPUSH, ZADD, INCR, etc.
- Some special commands: FLUSHDB, FLUSHALL, RENAME, etc.
- Some meta commands: SCRIPT LOAD, etc.

### Commands NOT Replicated

- Configuration commands: CONFIG SET, ACL, etc. (sometimes)
- Replication commands: PSYNC, REPLCONF, etc.
- Monitor/debug commands: MONITOR, DEBUG, etc.
- Client commands: HELLO, AUTH, etc.

---

## 11. Sentinel and Automatic Failover

Sentinel is separate tool (not part of core replication):
- Monitors master and replicas
- Detects master failure
- Elects new master from replicas
- Updates replica configs to point to new master
- Notifies clients of master change

Replication itself does NOT implement failover (Sentinel does).

---

## 12. Cluster Replication

In Redis Cluster:
- Each shard is master-replica pair
- Replication works same as standalone
- But gossip protocol handles failover automatically
- Replica can become master if original master fails

---

## 13. Critical Implications for Code Auditing

1. **Eventual consistency**: Write visibility on replica has latency
2. **Replication ID changes on restart**: Breaks partial resync assumptions
3. **Backlog exhaustion**: Replica disconnected too long loses ability to partial resync
4. **WAIT semantics**: Does NOT guarantee persistence (only replication acknowledgment)
5. **Replica divergence**: If master crashes after write but before replica sees it, data loss
6. **Chain replication**: Latency accumulates through chain (A → B → C slower than A → B)
7. **Diskless sync**: Experimental, not recommended for large production datasets
8. **TCP_NODELAY**: Batching ACKs can increase latency unpredictably
9. **Replication backlog**: TTL expiration means gap between disconnect and reconnect can cause full resync
10. **Memory overhead**: Backlog buffer consumed even if no replicas connected (retention for potential reconnect)
