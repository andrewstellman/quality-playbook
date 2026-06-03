# Redis Cluster Protocol — Gossip, Failover, Slot Migration, Redirection

Extracted from redis.io/docs/cluster-spec and implementation analysis. This document covers cluster topology discovery, slot migration, and client redirection semantics.

Sources: redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec/, redis/redis GitHub.

---

## 1. Cluster Overview

### What is Redis Cluster

Cluster is a distributed deployment where:
- Multiple Redis instances work together
- Data is sharded across instances (horizontal partitioning)
- 16384 hash slots divide the keyspace
- Each slot assigned to one node
- Automatic failover (if majority of nodes agree)

### Cluster Requirements

- Minimum 3 master nodes for quorum-based failover
- Each master can have 0+ replicas
- All nodes must be reachable via gossip (cluster bus)
- Not transparent: clients must support MOVED/ASK redirections

### Key Differences from Standalone

- No single point of failure (if node fails, replicas take over)
- No automatic key redistribution on node join (must manually migrate)
- Pub/Sub works per-shard (published in one shard, visible in that shard only)
- Some commands not supported (KEYS, SCAN have limitations)
- Transactions restricted to single slot keys

---

## 2. Hash Slots and Slot Assignment

### Hash Slot Calculation

```
slot = CSPEC.HASHSLOT(key) mod 16384
```

HASHSLOT algorithm:
1. Find `{` and `}` in key (hash tag syntax)
2. If found: hash the substring between them
3. If not found: hash entire key
4. Hash algorithm: CRC16

### Hash Tag Examples

```
CSPEC.HASHSLOT("user:1")      → slot based on "user:1"
CSPEC.HASHSLOT("user:{id}:profile")  → slot based on "id" (hash tag)
CSPEC.HASHSLOT("cache:{x}:{y}")      → slot based on "x" (first tag found)
```

Hash tags allow force keys to same slot for transactions.

### Slot Assignment

Configuration: cluster nodes manually assigned slots
- Each master owns disjoint set of slots
- Replicas don't own slots (they replicate master's slots)
- All 16384 slots must be assigned
- Unassigned slots → cluster not accepting commands

### Slot States

**`STABLE`** (normal)
- Slot assigned to node
- All writes go to that node
- Replicas replicate slot's data

**`MIGRATING <target-node>`**
- Slot being migrated OUT of this node
- Node still owns slot, but...
- Commands for keys in this slot forwarded to target (if key exists locally)
- Commands for non-existent keys return MOVED error
- Used during slot migration process

**`IMPORTING <source-node>`**
- Slot being migrated INTO this node
- Node doesn't own slot yet, but...
- Accepts commands for keys with ASKING redirection
- Source node still considers itself owner
- Used during slot migration process

**`ASKED`**
- Temporary flag indicating ASKING redirection in progress
- Allows single command to bypass IMPORTING check
- Cleared after command execution

---

## 3. Gossip Protocol

### Purpose

Gossip protocol spreads cluster topology information:
- Node joins/leaves cluster
- Slot assignments change
- Master fails (replica election)
- Failover occurs

### Cluster Bus

- Separate TCP port from client port (default: client_port + 10000)
- All nodes connected to all other nodes (full mesh)
- Gossip messages exchanged every second

### PING/PONG Messages

Every ~1 second, node sends PING to:
- 1-2 random nodes (maintain connectivity)
- Includes information about 2-3 known nodes (help others discover)

PONG responses include node state:
- Replication ID, offset (for failover)
- Slots assignment
- Master/replica status
- Timestamps (for timeout detection)

### Failure Detection

Node considered failed when:
- Majority of nodes haven't received PONG for `cluster-node-timeout` seconds (default 15s)
- At least 1 master detects failure (for failover eligibility)

### Cluster Formation

On node startup:
1. Node generates unique node ID (random)
2. Sends PING to seed nodes (if configured)
3. Receives PONG with existing topology
4. Propagates via gossip
5. Gradually learns entire cluster state

---

## 4. Master-Replica Failover

### Failure Detection

When master fails:
1. Replicas detect connection timeout
2. Replicas send `CLUSTER REPLCONF` with replication offset
3. Replicas request voting from other masters
4. Masters vote for replica with highest replication offset
5. When majority agrees: winning replica promoted to master

### Replica Election

Election rules:
1. Replica must have non-empty replication offset
2. Replica requests votes using replication offset
3. Masters vote for replica with HIGHEST offset (most data)
4. First replica with majority votes becomes master
5. All masters vote only once per timeout period

### Failover Delay

Configuration: `cluster-replica-validity-factor N` (default 10)

Replica eligibility: replica must have replication offset > master_offset * (1 - 1/(cluster-replica-validity-factor))

This prevents stale replicas from being elected.

### Configuration Update

After failover:
1. Elected replica announced as new master
2. Other replicas reconfigure to replicate from new master
3. Replicas of old master now orphaned (must be manually reassigned)
4. Cluster remains available throughout failover

---

## 5. Slot Migration (Resharding)

### Migration Command Sequence

Slot migration uses commands:
```
SOURCE> CLUSTER SETSLOT <slot> MIGRATING <target-node-id>
TARGET> CLUSTER SETSLOT <slot> IMPORTING <source-node-id>
```

Then migrate individual keys:
```
SOURCE> MIGRATE <target-host> <target-port> <key> 0 <timeout>
```

Then finalize:
```
CLUSTER SETSLOT <slot> STABLE <node-id>   # On source
CLUSTER SETSLOT <slot> STABLE <node-id>   # On target (and all nodes)
```

### Migration State Machine

Source: STABLE → MIGRATING → STABLE (done)
Target: STABLE → IMPORTING → STABLE (done)

During migration:
- SOURCE slot state: MIGRATING
- TARGET slot state: IMPORTING
- Clients see both MOVED and ASK errors

### Client Behavior During Migration

**For existing keys:**
1. Client sends command to source (which has MIGRATING state)
2. Source checks: key exists?
3. If EXISTS: source executes, returns result
4. If NOT EXISTS: source sends MOVED error to target
5. Client redirects to target

**For new keys:**
1. Client sends command to source
2. Source sends MOVED error (doesn't execute)
3. Client retries on target

### ASKING Redirection Mechanism

During IMPORTING:
- Target rejects commands with MOVED error normally
- But with ASKING redirection, target accepts once

Flow:
1. Client receives ASK error from source
2. Client sends ASKING command to target (no args)
3. Client immediately sends actual command
4. Target executes (ASKING sets temp flag)
5. Flag cleared after command

---

## 6. Client Redirection Errors

### MOVED Error

```
-MOVED <slot> <ip>:<port>
```

Indicates:
- Slot permanently moved to different node
- Client should update routing table
- All future commands for this slot go to target
- Example: after failover or migration completion

Client behavior:
1. Parse MOVED response
2. Cache routing: slot → node
3. Retry command on target node
4. Update local slot cache for future commands

### ASK Error

```
-ASK <slot> <ip>:<port>
```

Indicates:
- Slot temporarily in migration
- Data may or may not be on target
- Client should NOT cache (temporary)
- Use ASKING before retry

Client behavior:
1. Parse ASK response
2. DO NOT cache routing
3. Send ASKING command to target
4. Send actual command immediately after
5. ASKING "unlocks" single command execution

### Error Differences

| Aspect | MOVED | ASK |
|--------|-------|-----|
| Meaning | Permanent redirection | Temporary (migration) |
| Cache | Client SHOULD cache | Client SHOULD NOT cache |
| Prerequisite | None | ASKING command required |
| Recovery | Normal | Single command only |

---

## 7. Cluster Topology Discovery

### CLUSTER NODES Command

Returns every node's:
- Node ID
- IP address and cluster port
- Role (master/replica)
- Master ID (if replica)
- Replication offset
- Slot ranges assigned
- Status (connected/failing/failed)

Format: plain text, one node per line

### CLUSTER SLOTS Command

Returns slots grouped by:
- Slot range
- Master endpoint (IP:port)
- Replica endpoints

More efficient for client library routing table construction.

### Client Initialization

On startup:
1. Client connects to any cluster node
2. Issues CLUSTER SLOTS or CLUSTER NODES
3. Builds routing table (slot → node)
4. For each command:
   - Hash key to slot
   - Send to correct node
   - On MOVED: update routing table
   - On ASK: send ASKING then retry (no table update)

---

## 8. Pub/Sub in Cluster

### Topology

Pub/Sub is per-shard:
- Message published in shard A
- Only visible to subscribers in shard A
- Not propagated to other shards

### Channel to Shard Mapping

Channel name hashed to slot:
```
slot = CRC16(channel) mod 16384
```

Subscribers to same channel in different shards DON'T receive each other's publications.

### Cross-Shard Subscription

No direct cross-shard pub/sub (design limitation).

Workaround: publish to multiple channels (one per shard) and subscribe to all.

---

## 9. Transactions in Cluster

### Single-Slot Transactions

Supported:
```
MULTI
SET user:{123}:name Alice
LPUSH user:{123}:orders 1
EXEC
```

All keys have same hash tag → same slot → atomic.

### Multi-Slot Transactions

NOT supported:
```
MULTI
SET user:{123}:name Alice
SET order:{456}:status shipped
EXEC
```

Different slots → different nodes → cannot atomically execute.

Error: CROSSSLOT error returned.

---

## 10. Cluster Limitations and Behavioral Contracts

### Unsupported Commands

- **KEYS**: Returns only keys in local shard
- **SCAN**: Similar limitation
- **FLUSHALL/FLUSHDB**: Must execute separately per node
- **CONFIG**: Per-node configuration, no global config
- **MONITOR**: Per-node monitoring, not global

### Consistency Semantics

- **Eventual consistency**: After failover, some clients may see different data
- **MOVE errors**: Slot in migration may return MOVED or ASK unpredictably
- **Replication lag**: Replica failover may lose recent writes

### Failover Edge Cases

1. **Minority partition**: If node in minority partition, it becomes FAILED (stops accepting commands)
2. **Multiple failures**: If multiple masters fail simultaneously, cluster may not have quorum
3. **Split brain prevention**: Only majority partition accepts writes
4. **Dangling replicas**: Replicas of failed master without assigned master slot

### Critical Behavioral Contracts

1. **Slot ownership**: Exactly one master owns each slot (except during migration)
2. **MOVED permanence**: MOVED should be trusted and cached
3. **ASK impermanence**: ASK is one-time, must not be cached
4. **Gossip consistency**: Topology eventually consistent (transient inconsistencies possible)
5. **Redirection loops**: If client ignores MOVED, it loops. Implementation must handle.
6. **Configuration safety**: Only CLUSTER ADDSLOTS/DELSLOTS change slot ownership (manual intervention required)

---

## 11. Critical Implications for Code Auditing

1. **Slot calculation**: CRC16 hash implementation must match (common source of misrouting)
2. **ASKING handling**: Missing ASKING in migration causes failures
3. **Topology refresh**: Clients must refresh routing table on MOVED (or cache inconsistency)
4. **Failover timing**: Cluster accepts client commands during failover, but from which master?
5. **Slot boundaries**: Off-by-one errors in slot migration cause data loss
6. **Gossip reliability**: Gossip not reliable for critical updates (eventual consistency)
7. **Cross-slot transactions**: Atomicity only guaranteed within single slot
8. **Network partitions**: Cluster splits if minority partition unreachable
