# Redis Memory Management — Eviction, Lazy Free, Defragmentation, and Accounting

Extracted from redis.io documentation and implementation analysis. This document covers memory limits, eviction policies, and memory optimization techniques.

Sources: redis.io/docs/latest/develop/reference/eviction/, memory management guides.

---

## 1. Memory Limits and Maxmemory

### Maxmemory Configuration

```
maxmemory <bytes>
```

When Redis memory usage exceeds maxmemory:
1. Eviction policy is applied (if configured)
2. Keys are removed according to policy
3. More space is freed
4. New writes allowed if space available
5. If no space available and no eviction: commands fail (or OOM error)

### Default Behavior

If maxmemory not set or 0:
- No memory limit
- Server uses all available RAM
- If OS runs out: system crashes or kernel OOM killer terminates process

### Memory Usage Calculation

`INFO memory` command reports:
- `used_memory`: Total memory allocated (includes internal fragmentation)
- `used_memory_rss`: Resident set size (OS view, includes page table overhead)
- `used_memory_peak`: Highest memory usage ever observed
- `used_memory_dataset`: Approximate data size (excluding overhead)
- `mem_fragmentation_ratio`: used_memory_rss / used_memory (>1 indicates fragmentation)

---

## 2. Eviction Policies

When maxmemory exceeded, policy determines which keys to remove.

### Policy: `noeviction` (Default)

- No keys evicted
- Commands fail with OOM error
- Suitable for: accurate data (loss unacceptable)
- Behavior: client receives error, must retry or handle gracefully

### LRU Policies (Least Recently Used)

**`allkeys-lru`**
- Evicts least recently used key (ignoring TTL)
- All keys eligible for eviction
- Best for: general caching

**`volatile-lru`**
- Evicts least recently used key WITH expiration (TTL)
- Keys without TTL cannot be evicted
- If no volatile keys: behaves like `noeviction`
- Best for: cache with mix of permanent and temporary data

### LFU Policies (Least Frequently Used)

**`allkeys-lfu`**
- Evicts least frequently used key
- Tracks how often key accessed
- All keys eligible
- Best for: working set changes frequently

**`volatile-lfu`**
- Evicts least frequently used key WITH expiration
- Keys without TTL exempt
- Best for: cache with heat-based working set

### Random Policies

**`allkeys-random`**
- Evicts random key
- All keys eligible
- Fastest eviction (no tracking)
- Best for: when eviction is rare

**`volatile-random`**
- Evicts random key WITH expiration
- Suitable for: TTL-based cleanup with randomness

### TTL-Based Policy

**`volatile-ttl`**
- Evicts key with shortest remaining TTL
- Only keys with expiration eligible
- Best for: cleanup of soon-expiring keys first

---

## 3. Eviction Behavior and Edge Cases

### Eviction Process

1. Command received, memory check performed
2. If maxmemory exceeded: eviction triggered
3. Policy applied to select key
4. Selected key deleted
5. Memory freed
6. Check: still exceeding limit?
7. If yes: repeat from step 3
8. If no: continue with command execution

### LRU/LFU Sampling

For performance, eviction doesn't scan entire database:

**Default behavior**
- Random sample of keys selected (default: 5 keys)
- LRU/LFU tracking only on sampled keys
- Evicts "least recently/frequently used" of sample
- Approximates true LRU/LFU

**Configuration: `maxmemory-samples N`**
- Higher N: more accurate but slower
- Default: 5 (reasonable approximation)
- Range: typically 1-10

### Eviction Timing

Eviction happens:
- Before command execution (proactive)
- Only if space needed for command
- Not on every command (lazy)

### Critical Edge Cases

1. **Empty database**: If no keys eligible, eviction cannot free space (OOM error)
2. **All permanent keys**: With `volatile-*` policies, permanent keys cannot be evicted
3. **Rapid eviction**: If commands keep exceeding limit, eviction happens repeatedly (latency spike)
4. **Fairness**: Older keys more likely to be LRU (fair distribution of eviction)
5. **Size estimation**: Eviction doesn't know key size, evicts single key even if large

---

## 4. Lazy Free (Lazy Deletion)

Background deletion for large keys without blocking main thread.

### Motivation

Deleting large keys (e.g., 1GB string, 10M-element list) blocks server for seconds.

### Lazy Free Configuration

```
lazyfree-lazy-eviction yes       # Async delete during eviction
lazyfree-lazy-expire yes         # Async delete when key expires
lazyfree-lazy-server-del yes     # Async delete on DEL/UNLINK
lazyfree-lazy-user-del yes       # Async delete on client DEL (if unlink=yes)
```

### How It Works

1. Command requests key deletion
2. If lazy free enabled: key marked for async deletion
3. Command returns immediately
4. Background thread handles actual memory freeing
5. Key becomes inaccessible immediately (even if freeing in background)

### UNLINK Command

`UNLINK key` (replaces DEL in some cases):
- Always async if possible
- Returns count of keys deleted (like DEL)
- Different from DEL: does not block

### Deletion Ordering

Lazy free processes deletions in order:
1. Mark key as deleted (inaccessible)
2. Queue for background deletion
3. Background thread processes queue

If many deletions queued: background thread may accumulate work.

### Performance Impact

- **Pros**: Eliminates blocking on large key deletions
- **Cons**: Delayed memory reclamation (key data remains in memory briefly)

---

## 5. Memory Fragmentation and Active Defragmentation

### Fragmentation Causes

1. **Repeated allocations/deallocations**: Memory allocator creates holes
2. **Different object sizes**: Malloc cannot coalesce holes if unsuitable size
3. **Copying data structures**: Operations like APPEND, LPUSH may allocate new chunks
4. **Lazy deletion**: Key marked deleted but memory not immediately freed

### Memory Fragmentation Ratio

```
fragmentation_ratio = used_memory_rss / used_memory
```

- Ratio > 1: memory fragmented
- Ratio > 1.5: significant fragmentation
- Example: used_memory = 100MB, used_memory_rss = 150MB → 1.5x fragmentation

### Active Defragmentation

Redis can automatically defragment memory during idle CPU usage.

Configuration:
```
activedefrag yes                   # Enable active defrag
active-defrag-ignore-bytes 100mb   # Minimum data size to trigger defrag
active-defrag-threshold-lower 10   # Start defrag when fragmentation > 10%
active-defrag-threshold-upper 100  # Stop defrag when fragmentation < 100% (always stop at this)
```

### Defragmentation Process

1. Main thread triggers defrag if idle and fragmentation exceeds lower threshold
2. Background thread copies data to reduce fragmentation
3. Continues until fragmentation drops below upper threshold (or stops on timeout)
4. Does NOT block command processing

### Defragmentation Trade-offs

- **Pros**: Reduces memory footprint (RSS)
- **Cons**: CPU overhead, may reduce memory access locality
- **Use case**: Long-running servers with high fragmentation

---

## 6. Memory Accounting and Overhead

### Per-Object Overhead

Every Redis object has metadata:
- Object type (string, list, set, etc.)
- Encoding type
- Reference count (for freed object tracking)
- Last access time (for LRU)
- Frequency counter (for LFU)

Typical overhead: 48-64 bytes per object.

### String Memory Layout

```
RedisObject (56 bytes)
  ↓
StringData (variable)
  ↓
Actual bytes
```

For short strings: overhead significant (e.g., 64-byte object + 10-byte string = 86% overhead).

For long strings: overhead negligible (e.g., 64-byte object + 1MB string = 0.006% overhead).

### Collection Memory Layout

Lists, sets, hashes: memory includes:
- Container object (56 bytes)
- Interior array/table (scales with size)
- Element objects (if not embedded)

### Memory Efficiency Tips

1. **Use hash tags**: Reduce number of objects (multiple fields in one hash)
2. **Compress if possible**: RDB snapshots compress well, but in-memory data doesn't
3. **Use appropriate encoding**: Trust Redis to choose (ziplist/quicklist efficient)
4. **Set maxmemory**: Prevent unexpected OOM
5. **Monitor fragmentation**: Use `INFO memory` regularly
6. **Clean up expired keys**: Manual cleanup if expiration not aggressive enough

---

## 7. Key Expiration and Memory

### Expiration Storage

Each key with TTL has:
- Expiration time (millisecond precision)
- Stored in separate expiration dictionary
- Extra ~16-32 bytes per key

### Expiration Deletion

**Lazy deletion**: On access, if expired → delete
**Active background deletion**: Periodic sampling and deletion

Both mechanisms work together:
- Command accesses expired key → lazy delete
- No command accesses expired key → eventually active delete

### Expiration Precision

- TTL stored in milliseconds
- EXPIRE (seconds) converted to milliseconds
- EXPIREAT (unix time) stored directly
- Precision: ±100ms typical (depends on active deletion rate)

### Memory Savings from Expiration

If 80% of keys have TTL and are regularly expired:
- Memory footprint decreases over time
- Rate of decrease depends on:
  - Access patterns (lazy deletion rate)
  - Active deletion intensity
  - Expiration density

---

## 8. Maxmemory and Policy Interaction

### Choosing Eviction Policy

| Scenario | Policy | Reason |
|----------|--------|--------|
| Cache (any key ok to lose) | `allkeys-lru` or `allkeys-lfu` | Good cache semantics |
| Mix permanent + cache | `volatile-lru` | Keep permanent, evict cache |
| Session storage | `volatile-ttl` | Clean up shortest-lived sessions |
| Accurate data (loss = bug) | `noeviction` + alerting | Prevent silent data loss |
| High-freq access pattern | `allkeys-lfu` | Retain hot keys |
| Access order matters | `allkeys-lru` | Simple LRU semantics |

### Policy Edge Cases

1. **`noeviction` + `lazy-free`**: Keys deleted lazily, but no new keys added until space freed
2. **`volatile-*` + no expiring keys**: Behaves like `noeviction`
3. **Sampling bias**: LRU/LFU approximation may over-represent frequently accessed keys
4. **Eviction storm**: If maxmemory too small, eviction happens repeatedly (high latency)

---

## 9. Redis Modules and Memory

Modules can allocate memory:
- Allocations tracked (if using module API correctly)
- Participate in eviction (if registered with Redis)
- If not registered: may cause OOM despite maxmemory setting

---

## 10. Critical Implications for Code Auditing

1. **Eviction timing**: Commands may have variable latency if eviction triggered
2. **Lazy free delays**: Key appears deleted but memory freed asynchronously
3. **LRU approximation**: Not true LRU, sampling-based approximation
4. **Memory spikes**: Copying large objects (APPEND, LPUSH) causes temporary overage
5. **Fragmentation growth**: Repeated small allocations accumulate fragmentation
6. **Defragmentation overhead**: Active defrag runs in background, impacts latency
7. **TTL + eviction**: Expired keys eventually deleted (lazy + active), but timing unpredictable
8. **Policy fairness**: Eviction policy may be biased toward certain key types
9. **Multiple evictions**: Single command may trigger multiple evictions (latency spike)
10. **OOM safety**: No guarantee of safe shutdown; process may be killed by OS
