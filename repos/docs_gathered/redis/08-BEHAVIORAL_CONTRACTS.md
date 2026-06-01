# Redis Behavioral Contracts and Edge Cases

Extracted from redis.io documentation, source code analysis, and community discussions. This document specifies exact semantics, atomicity guarantees, and edge cases critical for code auditing.

Sources: redis.io/docs, GitHub redis/redis issues, community discussions.

---

## 1. Atomicity Guarantees

### Single Command Atomicity

MUST:
- Each command executes atomically without interleaving
- No other client's command executes during a command
- Modifications are visible immediately after return (or before on replicas)
- No partial results returned if command fails

Examples:
- INCR atomically increments and returns new value
- LPUSH atomically pushes multiple values in one call
- ZADD atomically adds multiple members with scores
- HSET atomically sets multiple fields

### MULTI/EXEC Transaction Atomicity

MUST:
- All commands in transaction execute sequentially
- No other client's command executes between commands in transaction
- Either all commands execute or none (if DISCARD issued)
- Results returned in array matching command order

MUST NOT:
- Provide rollback on command failure (partial execution acceptable)
- Block other transactions (serializable isolation)
- Execute in different order than queued

### Lua Script Atomicity

MUST:
- Script execution is atomic
- redis.call() functions execute atomically
- No other command executes during script
- Script failure aborts all further redis.call() (unless pcall used)

MUST NOT:
- Allow long-running scripts (Redis 5.0+ implements timeout mechanism)
- Permit scripts to spawn threads or async operations

---

## 2. Key Expiration Semantics

### MUST

- Expiration time is stored in milliseconds internally
- EXPIRE (seconds) converted to PEXPIRE (milliseconds)
- SET with EX/PX sets expiration
- TTL/PTTL return:
  - -1: key exists, no expiration
  - -2: key doesn't exist
  - ≥0: remaining TTL
- PERSIST removes expiration (returns 1 if had expiration, 0 otherwise)

### Expiration Precision

- Precision: milliseconds (internally)
- Lazy deletion on access
- Background active deletion sampling
- No guarantee on exact deletion time (probabilistic, not deterministic)

### Expired Key Visibility

MUST NOT:
- Return expired key to client (GET, LRANGE, etc.)
- Count expired key in DBSIZE (implementation dependent)
- Include expired key in KEYS pattern

Behavior:
- Command access: lazy delete (key removed before returning)
- No command access: eventually active deleted
- Lua scripts: see consistent snapshot (expiration frozen during script)

### Expiration and Type Checking

MUST:
- Type check performed BEFORE checking expiration
- Example: LPUSH on non-list key → error (type check first)
- Example: LPUSH on expired list key → deleted, then LPUSH succeeds

### Expiration Replication

MUST:
- Replication sends EXPIRE commands (not raw timestamps)
- Replica calculates own expiration time (based on local clock)
- Clock skew: if master and replica clocks differ, expiration times differ
- Solution: NTP synchronization recommended

---

## 3. Type Checking and Operation Semantics

### Type Errors

MUST:
- Reject operation on wrong type
- Error format: "WRONGTYPE Operation against a key holding the wrong kind of value"
- Command still fails atomically (no partial execution)

Examples:
- LPUSH on string → error
- HGET on list → error
- INCR on non-numeric string → error

### Type Conversion Semantics

MUST NOT:
- Implicitly convert types
- Cast string "5" to integer 5 for INCR (unless numeric string)
- Truncate or modify values during type check

### Numeric String Semantics

For INCR/DECR family:
- String must parse as valid integer (or float for INCRF)
- Range: [-2^63, 2^63-1] for integers
- Overflow: error if result exceeds range
- Non-numeric: error (not conversion)

---

## 4. List Operation Semantics

### List Index Semantics

MUST:
- Negative indices: -1 = last, -2 = second-to-last, etc.
- Out-of-range indices return nil (not error)
- LINDEX on empty list → nil
- LINDEX on non-list → error (type check)

### LRANGE Semantics

MUST:
- LRANGE key start stop (inclusive on both ends)
- LRANGE list 0 -1 → entire list
- LRANGE list 0 0 → first element
- LRANGE list -2 -1 → last two elements
- If start > stop → empty list (not error)
- If start > length → empty list
- If stop < start (and start ≤ length) → empty list

### LPUSH/RPUSH Multiple Elements

MUST:
- LPUSH key a b c → pushes in order: c, b, a (c is new head)
- RPUSH key a b c → pushes in order: a, b, c (c is new tail)
- LPUSH returns length after push
- Atomic: all elements pushed before return

### LPOP/RPOP Count Semantics (Redis 6.2+)

MUST:
- LPOP key 2 → pops 2 elements, returns array
- LPOP key 0 → error (invalid count)
- LPOP key -1 → error (invalid count)
- LPOP key 100 (list has 50) → returns 50 elements
- LPOP on empty → nil (not empty array)

---

## 5. Set Operation Semantics

### Set Member Uniqueness

MUST:
- Duplicate members ignored on add
- SADD key a a a → returns 1 (one new member)
- SREM returns count of members actually removed
- Order undefined (no ordering guarantee)

### Set Iteration Order

MUST NOT:
- Guarantee iteration order (SMEMBERS, SCARD, etc.)
- Maintain insertion order
- Order members lexicographically (unless ZSET)

### Set Operations Across Multiple Keys

MUST:
- SINTER key1 key2 → intersection (members in both)
- SUNION key1 key2 → union (members in either)
- SDIFF key1 key2 → difference (in key1 but not key2)
- Operations on non-existent keys: treat as empty set
- Return order undefined

### SPOP Semantics

MUST:
- SPOP returns and removes random member
- SPOP key count returns array of random members
- Members returned are distinct (no duplicates)
- If count > set size: return entire set

---

## 6. Hash Operation Semantics

### Field Overwrite

MUST:
- HSET key field value overwrites existing field
- HSET returns 1 if new field, 0 if updated
- HSETNX (set if not exists) only sets if field absent
- HINCRBY: error if field non-numeric

### Field Ordering

MUST NOT:
- Guarantee field order
- Maintain insertion order
- Return fields in consistent order across commands

### Hash Iteration (HSCAN)

MUST:
- HSCAN returns [cursor, [field1, value1, field2, value2, ...]]
- Cursor semantics: cursor 0 starts scan, returned cursor used for next iteration
- May return duplicate fields during concurrent modifications
- May skip fields during concurrent modifications
- Iteration complete when cursor returns to 0

---

## 7. Sorted Set Score Semantics

### Score Range and Precision

MUST:
- Score is IEEE 754 double (64-bit)
- Range: -1.79e308 to +1.79e308
- Precision: ~15-17 decimal digits
- Special values: +inf, -inf (strings "inf", "-inf")
- NaN is invalid (operations reject)

### Score Comparison

MUST:
- Scores compared as floats
- Lexicographic tie-breaking: if scores equal, compare members alphabetically
- ZRANGE returns members in ascending score order (ties broken lexicographically)

### Score Increment Semantics (ZINCRBY)

MUST:
- ZINCRBY atomically increments score
- Returns new score as bulk string (or bulk integer)
- Non-numeric score → error
- Increment amount must be numeric

### Range Query Semantics

MUST:
- ZRANGE key 0 -1 → all members by score
- ZRANGEBYSCORE key 10 20 → members with scores in [10, 20]
- ZRANGEBYSCORE key (10 20 → members with scores in (10, 20]
- ZREVRANGE key 0 -1 → all members in reverse score order
- ZREVRANGEBYSCORE key 20 10 → reverse order (stop ≤ start in reverse direction)

### ZRANGEBYLEX Semantics

MUST:
- ZRANGEBYLEX requires all members have same score (or approximately)
- Comparison is lexicographic (string comparison)
- Format: ZRANGEBYLEX key [member1 [member2
- '[' inclusive, '(' exclusive
- '-' minimum, '+' maximum

---

## 8. Stream Operation Semantics

### Stream Entry IDs

MUST:
- Entry ID format: milliseconds-sequence
- IDs are unique and ordered
- XADD returns ID (auto-generated or provided)
- XADD with explicit ID: must be > previous (or same ms, higher sequence)
- XADD with * : auto-generates ID

### Consumer Group Semantics

MUST:
- XREADGROUP blocks client until pending entry available
- XACK marks entry as acknowledged
- Entry remains in pending list until acknowledged
- XCLAIM transfers ownership to different consumer

### Trimming Semantics (XTRIM)

MUST:
- XTRIM MAXLEN N keeps at most N entries
- XTRIM MAXLEN ~ N (approximate): may keep more for efficiency
- XTRIM MINID removes entries older than ID
- Returns count of entries removed

---

## 9. String Operation Edge Cases

### APPEND and Length

MUST:
- APPEND returns new length
- APPEND to non-existent key creates key
- Maximum size: 512MB

### GETRANGE and SETRANGE

MUST:
- GETRANGE key 0 -1 → entire string
- GETRANGE key start stop (inclusive)
- Out-of-range indices return partial string or empty string
- SETRANGE extends string with null bytes if necessary
- SETRANGE returns new length

### INCR/DECR on Non-Existent Keys

MUST:
- INCR on non-existent key: creates key with value 1
- DECR on non-existent key: creates key with value -1
- INCRBY key 0 on non-existent: creates key with value 0

### INCR Overflow

MUST:
- Integer range: [-2^63, 2^63-1]
- INCR when at max → error (overflow)
- DECR when at min → error (underflow)

---

## 10. Key Scanning (KEYS, SCAN)

### KEYS Blocking Behavior

MUST:
- KEYS pattern blocks main thread until complete
- Large databases (millions of keys) cause latency spike
- Not safe for production (use SCAN instead)

### SCAN Cursor Semantics

MUST:
- SCAN cursor count returns [new_cursor, keys]
- Cursor 0 starts scan, progress tracked by returned cursor
- Each call returns (roughly) count keys (count is hint, not exact)
- Iteration complete when cursor returns 0
- Concurrent modifications may cause:
  - Duplicate keys in results
  - Skipped keys in results
- SCAN is safe to use in production (doesn't block)

---

## 11. Blocking Command Edge Cases

### BLPOP Multiple Keys

MUST:
- BLPOP key1 key2 key3 timeout checks in order
- Returns first non-empty key
- Multiple clients blocking: all unblocked if key becomes available
- FIFO order: first blocked client unblocked first

### Blocking Command Timeout

MUST:
- Timeout in seconds (0 = wait indefinitely)
- Precision: ~100-500ms typical
- Returns nil on timeout
- Returns [key, element] if data available

### Blocking Command with Zero Elements

MUST:
- BLPOP on empty list blocks
- BLPOP with LPUSH from another client unblocks first
- Multiple clients: unblock in order of blocking

---

## 12. Database Selection and FLUSHDB

### SELECT Database

MUST:
- SELECT database-number switches to database
- Databases 0-15 (default)
- Configuration: databases N (change total count)
- Each database is separate namespace

### FLUSHDB Semantics

MUST:
- FLUSHDB clears current database
- FLUSHALL clears all databases
- ASYNC (or SYNC) flag controls async/sync deletion
- Returns number of keys deleted (or +OK)

---

## 13. WAIT Command and Replication Semantics

### WAIT Semantics

MUST:
- WAIT numreplicas timeout waits for acknowledgment
- Returns number of replicas that acknowledged (≤ numreplicas)
- Does NOT wait for persistence (only replication)
- Replicas may lose data on crash

### Partial Resync and WAIT

MUST NOT:
- Assume replicas persisted data
- WAIT only guarantees replication delivery
- If replica crashes: data lost (unless persistence enabled)

---

## 14. Lua Script Constraints

### Script Semantics

MUST:
- Script atomicity: no commands interleaved
- redis.call() failures abort script
- redis.pcall() returns error object (doesn't abort)
- KEYS and ARGV available to script

### Script Timeout

MUST:
- Default: 5 seconds timeout
- After timeout: script killed, connection killed
- Configuration: lua-time-limit (milliseconds)
- Long-running scripts cause client disconnection

### Script Determinism

MUST:
- Scripts must be deterministic (same input → same output)
- redis.call('TIME') returns different time on each call (allowed)
- redis.call('RANDOMKEY') non-deterministic (may select different key)
- Replication: script replayed on replicas (results must match)

---

## 15. Module API Thread Safety

### Module Memory Allocation

MUST:
- Module memory tracked if RM_Alloc used
- Participate in eviction (if registered)
- MUST NOT use malloc() directly (memory not tracked)

### Module Commands and Blocking

MUST:
- Module command executes on main thread
- RM_BlockClient() allows client blocking
- Worker thread can do async work
- RM_UnblockClient() must be called from worker thread
- Unblock handler runs atomically on main thread

### Module Globals

MUST NOT:
- Assume thread-local storage (module global state shared)
- Use module globals without synchronization (unsafe)
- Spawn threads without proper locking

---

## 16. Known Edge Cases and Gotchas

### Edge Case 1: Empty Key Operations

Commands return:
- GET on non-existent → nil
- LRANGE on non-existent → empty array
- HGETALL on non-existent → empty array
- SMEMBERS on non-existent → empty array
- ZRANGE on non-existent → empty array

### Edge Case 2: Type Mismatch

Operation on wrong type ALWAYS errors:
- LPUSH on string → WRONGTYPE error
- HGET on list → WRONGTYPE error
- INCR on list → WRONGTYPE error

### Edge Case 3: Database Persistence

Different persistence modes:
- RDB only: cold start slower, snapshot lag up to SAVE interval
- AOF only: warm start faster, fsync overhead
- Mixed: RDB + AOF (both must be consistent)

### Edge Case 4: Memory Limits

With maxmemory:
- Eviction may happen before command execution
- Some commands fail if no space available
- Latency spikes possible during eviction

### Edge Case 5: Replication Clock Skew

Master and replica clocks may differ:
- Expiration times may differ by clock offset
- TTL/PEXPIRE computed from local clock
- Solution: NTP synchronization

---

## 17. Critical Implications for Code Auditing

1. **Atomicity is command-level**: Not transaction-level by default
2. **Expiration is probabilistic**: No guarantee on exact deletion time
3. **Type checking first**: Errors checked before execution
4. **Range operations inclusive**: Both start and stop inclusive
5. **Negative indices supported**: -1 = last element in lists/ranges
6. **Nil is different from empty**: GET returns nil, LRANGE returns empty array
7. **WAIT doesn't guarantee persistence**: Only replication, not disk
8. **Lua scripts must be deterministic**: For replication consistency
9. **Blocking operations have precision limit**: ~100ms, not suitable for precise timing
10. **Replication is eventually consistent**: Write visibility has latency
