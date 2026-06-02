# Casbin Adapters and Watchers

Sources:
- https://casbin.apache.org/docs/adapters
- https://casbin.apache.org/docs/watchers
- https://casbin.apache.org/docs/dispatchers
- https://casbin.apache.org/docs/enforcers

## Adapters

### Overview

Adapters handle policy persistence in Casbin. The enforcer calls `LoadPolicy()` to retrieve rules from storage and `SavePolicy()` to store them back. This architecture separates the authorization engine from storage, supporting file, database, key-value store, and cloud storage backends.

### Core Interface

All adapters must implement two mandatory methods:
- **LoadPolicy()**: Load all policy rules from storage
- **SavePolicy()**: Save all policy rules to storage

The underlying data structure supports reading at minimum six columns. Default database name: `casbin`, default table: `casbin_rule`. Table schema: `ptype` (not `p_type`), plus columns `v0` through `v5`. The unique key index is built on columns `ptype, v0, v1, v2, v3, v4, v5`.

### Policy Loading

When initializing an enforcer with an adapter, policies load automatically. To refresh policies after initialization, call `e.LoadPolicy()`.

**Security-critical behavior**: `SavePolicy()` wipes the storage and rewrites ALL policies. This is a destructive operation -- if interrupted, policies can be lost. There is no built-in transactional guarantee in the base adapter interface.

### AutoSave

AutoSave allows adapters to persist individual policy changes directly to storage without a full save operation. This contrasts with `SavePolicy()`, which rewrites everything.

AutoSave is controlled via `Enforcer.EnableAutoSave()`, defaulting to enabled for compatible adapters.

AutoSave requires three optional adapter methods:
- `AddPolicy()`: Add a single policy rule
- `RemovePolicy()`: Remove a single policy rule
- `RemoveFilteredPolicy()`: Remove matching policy rules

**Security note**: Adapters lacking AutoSave support should provide empty implementations returning "not implemented" errors. Casbin enforcers ignore these exceptions during optional method invocation. This means if you expect AutoSave to work but the adapter doesn't support it, policy changes are only persisted on explicit `SavePolicy()` calls -- they exist only in memory until then.

### Advanced Adapter Interfaces

**UpdateAdapter**: Extends basic functionality with `UpdatePolicy()`, `UpdatePolicies()`, and `UpdateFilteredPolicies()` for direct modifications without remove-and-add sequences.

**ContextAdapter**: Enables context-aware operations, useful for timeout control for adapter API calls. Without context support, a hung database connection could block the enforcer indefinitely.

**TransactionalAdapter**: Supports transaction handling through `WithTransaction()` or manual `BeginTransaction()`/`Commit()` patterns. This provides consistency guarantees that the base adapter interface lacks.

### Filtered Policy Loading

Filtered file adapters support policy subset loading, allowing selective rule retrieval based on filter parameters. This is useful for large policy sets where loading all rules is impractical.

**Security implication**: If filtered loading omits relevant deny rules, the enforcer will make authorization decisions without complete information, potentially allowing access that should be denied.

### Migration Between Adapters

To switch storage systems:
1. Load policies from source adapter into memory
2. Call `SetAdapter()` with new adapter
3. Invoke `SavePolicy()` to persist to destination

### Runtime Operations

- `LoadModel()`: Reload the model configuration
- `LoadPolicy()`: Refresh rules from storage
- `SavePolicy()`: Persist in-memory changes to storage

### Supported Backends

File, MySQL, PostgreSQL, SQLite, Oracle, SQL Server, MongoDB, DynamoDB, Cassandra, Redis, Etcd, AWS S3, Azure Cosmos DB, GCP Firestore, Kubernetes, and many more across Go, Java, Node.js, PHP, Python, .NET, Rust, Ruby, Swift, and Lua.

## Watchers

### Overview

Watchers keep policy in sync across multiple enforcer instances. When one enforcer updates policy, it notifies others through a message bus (etcd, Redis, Kafka, etc.), allowing them to reload their in-memory policies.

### Synchronization Mechanism

1. Enforcer A modifies a policy
2. Enforcer A's watcher broadcasts a notification to the message bus
3. Other enforcers' watchers receive the notification
4. Each receiving enforcer calls `LoadPolicy()` to refresh from storage

### Watcher Interface

- **SetUpdateCallback(func)**: Configures the callback invoked when other instances modify policies
- **Update()**: Notifies other instances to synchronize after policy changes
- **Close()**: Stops the watcher and prevents further callbacks

### WatcherEx (Enhanced Interface)

For incremental synchronization, `WatcherEx` distinguishes between specific update actions:
- `UpdateForAddPolicy` - policy additions
- `UpdateForRemovePolicy` - policy removals
- `UpdateForRemoveFilteredPolicy` - filtered removals
- `UpdateForSavePolicy` - complete policy saves
- `UpdateForAddPolicies` / `UpdateForRemovePolicies` - batch operations

**Critical note from documentation**: "there is currently no implementation of WatcherEx." The docs recommend using dispatchers for incremental synchronization instead.

### Supported Backends

Redis, etcd, TiKV, PostgreSQL, MongoDB, Kafka, NATS, RabbitMQ, RocketMQ, ZooKeeper. Available for Go, Java, Node.js, Python, .NET, Ruby, PHP, Rust.

## Dispatchers

### Overview

Dispatchers propagate incremental policy updates to multiple enforcer instances using consistency protocols like Raft.

### Key Difference from Watchers

- Watchers notify instances to reload ALL policies from storage
- Dispatchers propagate the specific incremental change directly

### Critical Limitation

**Dispatchers only sync changes after initialization. They do NOT fix existing divergence.** All enforcer instances must begin with identical policies from a shared source (database or snapshot) before enabling dispatch functionality. If instances start with different policies, the dispatcher will not reconcile the difference.

### DistributedEnforcer

The `DistributedEnforcer` wraps `SyncedEnforcer` to integrate dispatcher functionality for distributed systems.

## Enforcer Types and Thread Safety

### Base Enforcer
The primary interface for policy and model operations. **NOT thread-safe** for concurrent use.

### CachedEnforcer
In-memory caching of enforcement results. Features configurable cache expiration and thread-safe operations through read-write locks. Caching enabled by default via `EnableCache`.

**Security implication**: Cached enforcement results can become stale if policies change between cache entries. If a deny policy is added after a request was cached as "allow," subsequent identical requests will still return "allow" until the cache expires or is invalidated.

### SyncedEnforcer
Synchronized access for thread-safe operations. **Required for concurrent environments.** Uses the base enforcer in a multi-goroutine context without SyncedEnforcer risks race conditions in policy evaluation.

Can auto-reload policy: call `StartAutoLoadPolicy()` to poll the policy source and reload when it changes.

### SyncedCachedEnforcer
Combines caching and thread-safe synchronization.

### DistributedEnforcer
Wraps SyncedEnforcer for use with dispatchers in distributed systems.

## Security-Relevant Considerations

### Stale Cache = Authorization Bypass
1. CachedEnforcer caches Enforce() results
2. Policy is updated (e.g., deny rule added)
3. Cache still returns the old "allow" result
4. Authorization is bypassed until cache expires

Mitigation: Use watchers/dispatchers to invalidate caches on policy change, or disable caching for security-critical checks.

### Race Conditions
Using the base Enforcer in concurrent Go code (multiple goroutines) can cause:
- Inconsistent policy reads during updates
- Partially loaded policies
- Incorrect authorization decisions

Always use SyncedEnforcer or SyncedCachedEnforcer in concurrent environments.

### Adapter Interruption
If SavePolicy() is interrupted (process crash, network failure), the storage may contain incomplete policies. The wipe-and-rewrite behavior means there is a window where the storage has zero or partial policies.

### Watcher Notification Failure
If a watcher notification is lost (network partition, message bus failure), other enforcer instances will not reload policies. They will continue using stale policies until the next notification or manual reload.

### Dispatcher Initialization Divergence
If enforcer instances start with different policies (e.g., loaded from different database replicas during a lag), the dispatcher will NOT reconcile this difference. All subsequent incremental updates will be applied, but the base divergence persists.

### Filtered Loading Completeness
If filtered policy loading omits relevant rules (deny rules, domain-scoped rules), the enforcer operates with an incomplete policy set. This is equivalent to having no deny rules for filtered-out subjects/resources.
