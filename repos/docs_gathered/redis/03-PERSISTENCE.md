# Redis Persistence — RDB, AOF, Mixed Mode, and Fsync Policies

Extracted from redis.io documentation, persistence guides, and implementation details. This document covers durability mechanisms, fsync semantics, and data loss scenarios.

Sources: redis.io/docs/latest/operate/oss_and_stack/management/persistence/, persistence guides.

---

## 1. RDB (Redis Database) Snapshots

RDB is a point-in-time snapshot of the entire dataset saved to binary file.

### SAVE and BGSAVE Commands

**SAVE (synchronous)**
- Blocks all client commands during save
- Main thread writes snapshot to disk
- All clients receive "LOADING" responses during save
- Dangerous in production: any long snapshot blocks all operations
- Used primarily for testing

**BGSAVE (background save)**
- Forks child process
- Child process writes snapshot to disk
- Main thread continues serving clients
- Incremental approach with copy-on-write semantics:
  - Parent and child share memory pages initially
  - When parent modifies a page, new copy is created for child
  - Child sees data state at fork time only
- Command returns immediately

### Automatic Snapshots

Configuration: `save <seconds> <changes>`
- Default: `save 900 1` (1 change in 900 seconds)
- Default: `save 300 10` (10 changes in 300 seconds)
- Default: `save 60 10000` (10000 changes in 60 seconds)
- Multiple rules: ANY rule triggering causes snapshot

### RDB File Format

The `.rdb` file structure:
1. **Header**: REDIS version identifier, Redis version that created it
2. **Auxiliary metadata**: creation time, Redis version, CRC64 checksum enabled flag
3. **Database metadata**: selected database number
4. **Key-value data**: all keys and values in selected databases
5. **Expiration times**: TTL values for each key
6. **Footer**: end-of-file marker, CRC64 checksum

### Loading RDB File

On startup:
1. Server opens `.rdb` file if exists
2. Validates format and CRC checksum
3. Reconstructs dataset in memory
4. Server becomes operational when RDB fully loaded
5. Does NOT accept client connections until loading complete

### RDB-Specific Properties

1. **Data loss on crash**: Writes between last snapshot and crash are lost
2. **Recovery time**: Slow if dataset is large (loading involves deserialization)
3. **Compression**: RDB files are compressed (LZF by default)
4. **Encoding efficiency**: RDB stores optimal internal encoding, not command replay
5. **Memory spike**: BGSAVE doubles memory during copy-on-write (worst case)

### Critical Behavioral Contracts

- **Atomicity of snapshot**: Snapshot is atomic at fork time. No partial snapshots.
- **Expiration semantics**: Expired keys may or may not appear in RDB (implementation dependent)
- **Replication ID**: RDB does NOT contain replication ID (assigned fresh on startup)
- **Config changes**: Settings not in RDB (must reconfigure after load)

---

## 2. AOF (Append-Only File)

AOF logs every write command and replays them on startup.

### How AOF Works

1. Client sends write command (SET, LPUSH, INCR, etc.)
2. Command executes on main thread
3. Command is appended to AOF buffer (in memory)
4. Fsync policy determines when buffer is written to disk
5. On startup, all commands in AOF are replayed in order

### AOF Command Format

Commands logged in RESP protocol format:
```
*3
$3
SET
$3
key
$5
value
```

Each command is a complete serialized command, not a custom format. All data structures and commands are logged.

### Fsync Policies

Configuration: `appendfsync <policy>`

**`appendfsync always`**
- Every write command is immediately fsynced to disk
- Maximum durability: machine crash loses at most the command in progress
- Lowest performance: fsync is slow I/O operation
- Latency impact: visible to client (acknowledgment waits for fsync)
- Typical latency: 1-10ms per fsync
- Use case: strict durability requirements

**`appendfsync everysec`** (Default)
- AOF buffer flushed every ~1 second via fsync
- Background thread (or main thread) performs fsync
- Commands acknowledged to client before fsync completes
- If crash occurs: up to ~1 second of writes may be lost
- Balances durability and performance
- Latency impact: minimal (no per-command fsync)

**`appendfsync no`**
- OS determines when data is written to disk (typically 30 seconds)
- Fastest performance
- Highest data loss risk: entire unflushed buffer lost on crash
- Not recommended for production
- Use case: caching scenarios where durability not critical

### AOF Rewrite

AOF file can grow unbounded (contains all writes ever executed).

**BGREWRITEAOF Command**
- Forks child process
- Child process reads all keys from current dataset
- Child writes optimized commands to new AOF file
  - E.g., 1000 individual LPUSH becomes single LPUSH with 1000 items
  - E.g., 100 INCR to same key becomes single SET to final value
- Parent continues logging writes to old AOF
- When child finishes, all parent writes since fork are appended to new AOF
- Rename: old AOF removed, new AOF becomes current

**Automatic AOF Rewrite**
- Configuration: `auto-aof-rewrite-percentage N` (default 100)
- Configuration: `auto-aof-rewrite-min-size N` (default 64MB)
- Triggered when: current size > min size AND size > last rewrite size * (1 + percentage/100)

### AOF Durability Guarantees

- **everysec**: Up to ~1 second of data loss possible
- **always**: Only data in command currently executing lost
- **no**: Unpredictable data loss (OS buffer dependent)

### Critical Behavioral Contracts

1. **Command format**: Commands logged in client-provided format (client input protocol)
2. **Replication commands**: Internal replication commands NOT logged to AOF
3. **MULTI/EXEC atomicity**: All commands in transaction logged atomically
4. **Expiration commands**: EXPIRE, PEXPIRE commands ARE logged (not expiration events)
5. **Read commands**: Read-only commands (GET, LRANGE, etc.) NOT logged
6. **ACL commands**: CONFIG SET, ACL changes may not be logged (depends on config)

---

## 3. Mixed Persistence Mode

Both RDB and AOF can be enabled simultaneously for hybrid durability.

### Configuration

```
save 900 1              # Enable RDB
appendonly yes          # Enable AOF
appendfsync everysec    # AOF fsync policy
```

### Startup Behavior

When both enabled, startup loads data in this order:
1. Check if AOF file exists
2. If AOF exists: load AOF (replay all commands)
3. If AOF doesn't exist: load RDB
4. AOF takes priority (most recent data)

### Why Mixed Mode?

**Advantages**
- RDB: fast recovery, efficient point-in-time backups
- AOF: fine-grained durability, last-minute saves possible
- Combined: AOF handles everyday writes, RDB handles clean snapshots for backups

**Disadvantages**
- Double write overhead: every write goes to both RDB buffer (at intervals) and AOF file
- Disk space: two files must be maintained
- Replication: both RDB and AOF replicated to slaves

### Background Task Scheduling

Redis prevents BGSAVE and BGREWRITEAOF from running simultaneously:
- If BGSAVE in progress, BGREWRITEAOF deferred until BGSAVE completes
- If BGREWRITEAOF in progress, BGSAVE deferred until BGREWRITEAOF completes
- Reason: both operations are I/O heavy, prevent disk thrashing

### Critical Behavioral Contracts

1. **Startup precedence**: AOF loaded if both exist (AOF is more recent)
2. **BGSAVE + BGREWRITEAOF mutual exclusion**: Cannot run concurrently
3. **Replication**: Replica receives both RDB snapshots and AOF updates
4. **Partial resync**: Works with both RDB and AOF active
5. **Master/slave divergence**: If replication broken, master and replica may diverge (resolved on reconnect)

---

## 4. Fsync and OS-Level Guarantees

### Fsync Semantics

`fsync()` system call flushes OS page cache to disk, but does NOT guarantee:
- Physical disk write completion
- Durability if power lost (unless journaled filesystem)
- No reordering of writes on disk (disk may cache and reorder)

### File Ordering

On filesystems without barriers, multiple writes may be reordered:
- AOF write, AOF fsync, RDB write, RDB fsync
- Actual disk order may differ
- Power loss during intermediate state possible

### AOF Truncation Risk

If Redis crashes during AOF write:
- Partial command may be appended to AOF file
- On restart, partial command causes parse error
- Redis provides: `redis-check-aof` utility to detect and fix truncation

### RDB Checksum

RDB files include CRC64 checksum:
- Detects corruption from bit flips or storage errors
- On load, checksum verified (default enabled via `rdbcompression` setting)
- If checksum fails, RDB rejected and error logged

---

## 5. Data Loss Scenarios

### Scenario 1: Crash with `appendfsync everysec`
- Last ~1 second of writes lost
- RDB snapshots available at fixed intervals (SAVE intervals)
- Combined loss: potentially 1 second to N minutes depending on SAVE config

### Scenario 2: Crash with `appendfsync always`
- Only command in-flight lost (that command is atomic)
- All committed commands preserved
- Strong durability but highest latency

### Scenario 3: Crash with both RDB and AOF
- AOF replayed first (most recent)
- RDB acts as safety net if AOF corrupted
- Partial AOF write detected and fixed by redis-check-aof

### Scenario 4: Disk Full During Snapshot
- BGSAVE or BGREWRITEAOF fails (no space)
- Old RDB/AOF remains intact
- New snapshot not created (old files retained)
- Data not lost, but no new backup created

### Scenario 5: Master-Replica Divergence
- Master and replica both running
- Network partition occurs
- Master accepts writes, replica stales
- Replication recovers (partial resync) when connection restored
- If master loses data between partition and restart, inconsistency possible

---

## 6. Persistence Tuning Considerations

### High Durability (Always)
```
save ""                 # Disable RDB snapshots
appendonly yes          # Enable AOF
appendfsync always      # Fsync every write
```
- Highest durability, lowest throughput
- ~10-50% latency overhead per command

### Balanced (Typical)
```
save 900 1              # RDB snapshot every 15 minutes (if any write)
appendonly yes          # Enable AOF
appendfsync everysec    # Fsync every second
```
- Good durability (max 1 second loss)
- Good performance
- Two files maintained

### High Performance (Caching)
```
save ""                 # Disable RDB
appendonly no           # Disable AOF
```
- Zero persistence overhead
- Complete data loss on crash
- Suitable for caching only

### Recovery Time Expectations

For 10GB dataset:
- RDB load: 10-30 seconds (depends on storage speed)
- AOF replay: 60-300 seconds (command execution slower than snapshot load)
- Mixed mode: RDB load + missing AOF commands only (faster)

---

## 7. Critical Implications for Code Auditing

1. **Persistence is not transparent**: BGSAVE and BGREWRITEAOF are separate processes with synchronization points
2. **Replication ID handling**: Changed after restart (affects partial resync)
3. **Expiration state**: Expired keys in memory, not in RDB (lazy deletion)
4. **Fsync blocking**: Even with background processes, fsync can block main thread in some modes
5. **AOF rewrite**: Creates temporary file. Must handle filename collisions
6. **RDB recovery**: Data corrupted if load interrupted midway
7. **Copy-on-write overhead**: Memory spike during BGSAVE if dataset heavily modified
