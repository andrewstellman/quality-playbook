# Redis Data Structures and Encoding — Internal Representations

Extracted from redis.io documentation and Redis source code. This document covers the five primary data structures, their internal encodings, and automatic encoding transitions.

Sources: redis.io/docs/latest/develop/data-types/, Redis source code repository.

---

## 1. Strings — Binary-Safe Byte Sequences

Strings are the most basic Redis data type—a sequence of bytes with an associated length.

### Properties
- Binary-safe (can contain any byte sequence, including null bytes)
- Length stored explicitly (O(1) access to length)
- Maximum size: 512MB per string
- Atomic increment/decrement operations (INCR, DECR)

### String Encoding Variants

**`int` Encoding**
- Internal representation: native long integer (64-bit)
- Stored in object metadata, not allocated separately
- Applies when: string represents integer in range [-2^63, 2^63-1]
- Transition: SET with numeric string → int encoding
- Operations: INCR, DECR, INCRBY work directly on int
- Conversion: APPEND, SETRANGE, GETRANGE forces conversion to `raw`

**`embstr` Encoding**
- Embedded string: byte array allocated contiguously with object header
- Single allocation for object + data
- Applies when: string length ≤ 44 bytes (default threshold)
- Read-only: APPEND, SETRANGE, INCR force conversion to `raw`
- Memory efficient: no separate pointer indirection

**`raw` Encoding**
- Separate allocation for object header and string data
- Pointer from object to data buffer
- Applies when: string length > 44 bytes OR after write operations on embstr
- Used by: APPEND, SETRANGE, write-after-read operations
- Memory: two allocations, slight fragmentation overhead

### Encoding Transition Rules

```
int ─(APPEND/SETRANGE)─> raw
int ─(read-only ops)──> int

embstr ─(APPEND/SETRANGE)─> raw
embstr ─(read-only ops)───> embstr

raw ─(all ops)─────────> raw
```

### Critical Behavior for Code Auditing

1. **INCR on string**: Command assumes string is valid integer. Parsing failure → error
2. **Length caching**: String length is cached in object. Modifications must update length field
3. **Mutation in-place**: raw encoding allows modification in-place if new size ≤ old size
4. **GETRANGE edge cases**: Negative indices count from end. Out-of-range indices return partial strings, not errors

---

## 2. Lists — Ordered Collections

Lists are collections of strings ordered by insertion order (FIFO principle).

### Properties
- Ordered by insertion (leftmost = first pushed, rightmost = last pushed)
- Duplicates allowed
- LPUSH, RPUSH, LPOP, RPOP, LRANGE operations
- Blocking variants: BLPOP, BRPOP, BLMOVE, BLMPOP
- Maximum length: 2^32 - 1 elements

### List Encoding Variants

**`quicklist` Encoding** (Primary, Redis 3.2+)
- Hybrid structure: linked list of ziplist/listpack nodes
- Each node: compressed packed array of elements
- Applies: standard list operations
- Configuration: `list-compress-depth N` (compress deep nodes for memory)
- Configuration: `list-max-ziplist-size M` (max items per node, default -2 = 8KB)

**`linkedlist` Encoding** (Legacy, rarely used)
- Traditional doubly-linked list
- Each element is separate node
- Applies: when quicklist not suitable (deprecated)
- Removed in Redis 7.0+

**`ziplist` Encoding** (Deprecated, replaced by listpack)
- Compact array with length-prefix encoding
- Minimal overhead, good for small lists
- Applied when: list length < threshold AND all elements small
- Now replaced by `listpack` in recent versions

### Element Encoding

Each element in a list is itself encoded:
- **int encoding**: numeric strings stored as 64-bit integers
- **embstr encoding**: short strings (< 44 bytes)
- **raw encoding**: longer strings

### Encoding Transition Rules

- List automatically upgrades from ziplist to quicklist when size thresholds exceeded
- Downgrade does NOT happen (grow-only until persistence)
- LTRIM can convert quicklist back to ziplist if resulting size small enough

### Critical Behavior for Code Auditing

1. **Index semantics**: LINDEX supports negative indices (-1 = rightmost). Out-of-range → nil
2. **LRANGE semantics**: LRANGE -2 -1 gets last two elements. Reversed ranges return empty
3. **LPOP/RPOP atomicity**: LPOP key count (Redis 6.2+) atomically removes multiple elements
4. **Blocking semantics**: BLPOP across multiple keys returns first non-empty. Order: left-to-right key order
5. **LMOVE atomicity**: Atomically moves element from source to destination list in single atomic step
6. **Memory optimization**: Compression on deep nodes means list.compress-depth affects both memory and latency

---

## 3. Sets — Unordered Collections of Unique Strings

Sets contain unique strings with no ordering guarantee.

### Properties
- All members are unique (duplicates are silently ignored on add)
- Set operations: UNION, INTER, DIFF, CARD (cardinality)
- No ordering (iteration order undefined)
- Maximum size: 2^32 - 1 members

### Set Encoding Variants

**`hashtable` Encoding**
- Hash table with strings as keys, value = nil
- O(1) average add/remove/contains
- Applied when: any string member cannot be integer
- Configuration: `set-max-intset-size N` (default 512, elements to stay in intset)

**`intset` Encoding**
- Packed array of integers with adaptive byte width
- Memory efficient for integer-only sets
- Applied when: all members are integers AND set size < set-max-intset-size
- Byte widths: 16-bit, 32-bit, 64-bit (chosen based on value range)
- Encoding transition: one non-integer add → converts to hashtable

### Encoding Transition Rules

```
intset ─(non-integer add)──> hashtable
intset ─(size > threshold)─> hashtable
hashtable ─────────────────> hashtable (no downgrade)
```

### Critical Behavior for Code Auditing

1. **Member uniqueness**: SADD silently ignores duplicates. Returns count of NEW members added
2. **Integer detection**: intset requires ALL members to parse as 64-bit integers. Mixed types → hashtable
3. **Intset ordering**: Internally sorted by value. SMEMBERS iteration still undefined
4. **Set operations**: SINTER, SUNION, SDIFF operate on multiple sets atomically
5. **SPOP atomicity**: SPOP with count atomically removes and returns multiple members (Redis 3.2+)
6. **Memory sensitivity**: intset significantly more compact. Crossing threshold type conversion has performance impact

---

## 4. Hashes — Field-Value Pairs

Hashes store mappings from field names to string values.

### Properties
- Each field maps to exactly one string value
- Field names are strings
- Field values are strings (no nesting)
- Efficient for object representation
- Maximum fields: 2^32 - 1 per hash

### Hash Encoding Variants

**`hashtable` Encoding**
- Hash table implementation with chaining
- O(1) average field lookup
- Applied when: hash grows beyond ziplist thresholds
- Configuration: `hash-max-ziplist-entries N` (default 512)
- Configuration: `hash-max-ziplist-value N` (default 64 bytes)

**`ziplist` Encoding** (Deprecated in recent versions)
- Compact array of field-value pairs alternating
- Memory efficient for small hashes
- Applied when: fewer entries than hash-max-ziplist-entries AND all values < hash-max-ziplist-value
- Traversal: O(n) for full scan, but acceptable for small hashes

**`listpack` Encoding** (Redis 7.0+)
- New compact encoding replacing ziplist
- Better memory density and traversal performance
- Same thresholds as ziplist
- Atomic element updates possible

### Encoding Transition Rules

```
ziplist ─(add field with large value)─> hashtable
ziplist ─(size > entries threshold)───> hashtable
hashtable ─────────────────────────────> hashtable (no downgrade)
```

### Critical Behavior for Code Auditing

1. **Field overwrite**: HSET overwrites existing field. Returns 1 if new field, 0 if updated
2. **HSCAN cursor**: SCAN family with cursor-based iteration. Cursor semantics: may return duplicates, may skip entries during concurrent modifications
3. **HGETALL atomicity**: Returns all fields and values. For large hashes, this is not atomic with respect to other clients
4. **Incremental operations**: HINCRBY atomically increments numeric field. Non-numeric field → error
5. **Threshold crossing**: Adding large value to hash approaching threshold triggers conversion. Temporary memory spike possible
6. **HRANDFIELD**: Random field selection. With count > 0, may return duplicates (depends on implementation)

---

## 5. Sorted Sets — Ordered by Score

Sorted sets contain members ordered by score (floating-point number).

### Properties
- Each member has associated score (double precision float)
- Members ordered by score (lowest to highest), ties broken by lexicographic member order
- Member names are unique (duplicate members update score)
- Range operations: ZRANGE, ZRANGEBYSCORE, ZREVRANGE, etc.
- Maximum size: 2^32 - 1 members

### Sorted Set Encoding Variants

**`skiplist` Encoding** (Primary)
- Skip list + hash table hybrid
- Skip list for range operations (logarithmic traversal)
- Hash table for member → score lookup (O(1) member access)
- Applied: standard sorted sets
- Multiple skip list levels (height determined by random algorithm)

**`ziplist` Encoding** (Small sorted sets)
- Compact array of score-member pairs
- All members and scores packed contiguously
- Applied when: sorted set size < zset-max-ziplist-entries AND all members < zset-max-ziplist-value
- Configuration: `zset-max-ziplist-entries N` (default 128)
- Configuration: `zset-max-ziplist-value N` (default 64 bytes)
- Traversal: O(n) scanning, but appropriate for small sets

**`listpack` Encoding** (Redis 7.0+)
- New compact encoding replacing ziplist for small sets
- Better performance and memory density
- Same thresholds as ziplist

### Score Precision

- Score stored as IEEE 754 double (64-bit)
- Range: -1.79e308 to +1.79e308
- Special values: +inf, -inf (strings "inf", "-inf")
- NaN is invalid (operations reject NaN scores)
- Precision: ~15-17 decimal digits

### Encoding Transition Rules

```
ziplist ─(size > entries threshold)───> skiplist
ziplist ─(member > value threshold)───> skiplist
skiplist ───────────────────────────────> skiplist (no downgrade)
```

### Critical Behavior for Code Auditing

1. **Score ordering**: Members ordered primarily by score, secondarily by name (lexicographically)
2. **Member uniqueness**: ZADD with existing member updates score. Returns 1 if new, 0 if updated
3. **ZRANGE semantics**: Inclusive range [start, stop]. Negative indices count from end. ZRANGE key 0 -1 returns all
4. **ZRANGEBYSCORE precision**: Range is inclusive on both ends. Values compared as floats
5. **Lexicographic range**: ZRANGEBYLEX, ZREVRANGEBYLEX use '[' for inclusive, '(' for exclusive bounds
6. **ZREM atomicity**: ZREM can remove multiple members atomically
7. **ZPOPMIN/ZPOPMAX atomicity**: ZPOPMIN key count removes and returns multiple members atomically
8. **Skip list structure**: NOT self-balancing. Height based on random coin flips. Highly unbalanced lists possible (but rare)
9. **Duplicate scores**: All members with same score maintain lexicographic order internally

---

## 6. Streams — Append-Only Logs

Streams are append-only sequences of entries, each with unique ID.

### Properties
- Entries are auto-assigned IDs (timestamp-sequence)
- Append-only: entries never modified (only XDEL for removal)
- Consumer groups: track which entries consumed by each consumer
- Blocking reads: XREAD BLOCK can wait for new entries
- Ranges and pagination: XRANGE, XREVRANGE

### Stream Entry Structure
- Entry ID: timestamp-ms + sequence-number (e.g., "1526919030474-0")
- IDs ordered by time, then sequence
- XADD with explicit ID allows custom sequences

### Stream Encoding (Internal)
- Radix tree: efficient range lookups
- Consumer group state: separate tracking per group
- Consumer state: per-consumer tracking within group
- Trimming: XTRIM for automatic size capping

### Critical Behavior for Code Auditing

1. **Entry ID semantics**: IDs guaranteed unique and increasing. XADD auto-generates based on system time + counter
2. **Consumer group atomicity**: XREADGROUP marks entries as pending atomically
3. **Pending entry list (PEL)**: Tracks unacked messages. XCLAIM atomically transfers ownership
4. **Trimming**: XTRIM MAXLEN strategy approx (random eviction) vs exact (slower)
5. **Entry immutability**: Entries cannot be modified, only deleted via XDEL
6. **Blocking semantics**: XREAD BLOCK waits for data. Timeout in milliseconds

---

## 7. Encoding Transitions — Performance Implications

### Memory vs. Performance Trade-off

Small collections use compact encodings:
- Compact: ziplist/listpack (low memory, slow traversal)
- Large: hash table / skip list (higher memory, fast operations)

Transition points are configurable and critical for performance:
- Crossing threshold: sudden latency spike during encoding conversion
- Repeated crossing: can cause thrashing if operations near boundary

### Thresholds Configuration

```
list-max-ziplist-size -2         # -2 = 8KB per node, -1 = 4KB
list-compress-depth 0            # 0 = no compression
hash-max-ziplist-entries 512     # Switch to hashtable at this size
hash-max-ziplist-value 64        # Switch if any value > this size
set-max-intset-size 512          # Switch to hashtable if exceeded
zset-max-ziplist-entries 128     # Switch to skiplist if exceeded
zset-max-ziplist-value 64        # Switch if any value > this size
```

### Critical Implications

1. **Predictable operations**: Operations near thresholds have variable latency
2. **Replication**: Encoding choice may differ on replica if thresholds differ
3. **Persistence**: RDB format stores actual encoding. AOF stores commands (encoding reconstructed)
4. **Cluster**: Slot migration may convert encodings if thresholds differ
5. **Upgrades**: New Redis versions may change default thresholds or encoding algorithms

---

## 8. Key Implications for Code Auditing

1. **Encoding-specific bugs**: Logic assuming one encoding may fail with another
2. **Threshold crossing**: Performance regression if operations repeatedly trigger conversions
3. **Atomic operations**: Single commands that appear simple may perform encoding conversions
4. **Memory fragmentation**: Multiple encodings coexisting in memory
5. **Replication consistency**: Encoding differences shouldn't affect correctness, but may show replication lag
6. **Overflow handling**: String lengths capped at 512MB, intset at 2^32-1 members, etc.
7. **Type checking**: Commands must verify input type before encoding-specific operations
