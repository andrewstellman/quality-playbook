# Ech0 Logging Subsystem

## Overview

All application logging flows through `internal/util/log`, a wrapper around [go.uber.org/zap](https://pkg.go.dev/go.uber.org/zap). The package extends the standard zap pattern with two additional features: an in-memory ring buffer for real-time log streaming to the admin console, and asynchronous file writing to avoid blocking the main log path during I/O bursts.

## Logger Initialization

The global logger is a package-level `*zap.Logger` initialized lazily on first access via `GetLogger()`. Explicit initialization should be called at startup using:

```go
logUtil.InitLoggerWithConfig(config LogConfig)
```

or with the defaults:

```go
logUtil.InitLogger()
```

Re-initialization replaces the logger, rotated file writer, and stream hub atomically under a mutex. Any running file sink goroutine from the previous initialization is drained before the new one starts.

## Log Configuration

```go
type LogConfig struct {
    Level   string       // debug, info, warn, error
    Format  string       // json or console
    Console bool         // also write to stdout
    File    FileConfig
    Stream  StreamConfig
}

type FileConfig struct {
    Enable     bool
    Filename   string
    MaxSize    int    // MB before rotation
    MaxBackups int    // rotated files to keep
    MaxAge     int    // days before deletion
    Compress   bool   // gzip rotated files
}

type StreamConfig struct {
    BufferSize      int    // channel buffer per subscriber
    RecentSize      int    // ring buffer entries for "recent" queries
    DropPolicy      string // "drop_oldest" or "drop_newest"
    FlushBatch      int    // lines per async file write
    FlushIntervalMs int    // write interval
}
```

All fields are mapped from `ECH0_LOG_*` environment variables (see the configuration reference). Default values produce JSON-format logs written to `data/app.log` with file rotation at 100 MB, five backups, 30-day retention, and gzip compression.

## Public Logging Functions

The package exposes level-specific helpers that wrap `GetLogger()` with panic recovery:

```go
func Debug(msg string, fields ...zap.Field)
func Info(msg string, fields ...zap.Field)
func Warn(msg string, fields ...zap.Field)
func Error(msg string, fields ...zap.Field)
func Panic(msg string, fields ...zap.Field)
func Fatal(msg string, fields ...zap.Field)
func GetLogger() *zap.Logger
```

The `Debug`, `Info`, `Warn`, and `Error` wrappers catch any panics from the logger itself and write a fallback message to stderr, ensuring logging failures never crash the application.

## Log Level Conventions

| Level | When to use |
|---|---|
| `Debug` | High-frequency diagnostic information; development only |
| `Info` | Significant lifecycle events: startup, task completion, state transitions |
| `Warn` | Recoverable conditions: retries, fallbacks, graceful degradation |
| `Error` | Failures requiring attention: failed writes, unavailable services, data errors |

Recommended structured fields:
- `zap.String("module", "...")` — subsystem identifier
- `zap.String("user_id", "...")` — acting user
- `zap.String("path", "...")` — resource path
- `zap.String("provider", "...")` — third-party provider name
- `zap.Error(err)` — error value (never `zap.String("error", err.Error())`)

## In-Memory Log Stream

The `LogStreamHub` maintains two structures:

1. **Ring buffer** (`recent`) — a fixed-size circular array of the most recent `RecentSize` entries. Consumed by `RecentLogs(limit)` and served by the `GET /api/system/logs/stream` endpoint.
2. **Subscriber channels** — a map of `chan LogEntry` keyed by subscriber ID. Each subscriber gets its own buffered channel. New subscribers receive entries from the moment they subscribe; there is no replay of historical entries on a new subscription.

The `streamCore` zap core intercepts every `Write` call and passes the entry to the hub before forwarding to the underlying cores. Encoding is reused from a clone of the JSON encoder to avoid allocating a new encoder per entry.

### Subscribing to the Log Stream

```go
id, ch, cancel := logUtil.SubscribeLogs(bufferSize)
defer cancel()
for entry := range ch {
    // handle entry
}
```

`cancel()` closes and removes the subscriber channel. If the hub is closed (on `CloseLogger`), the channel is closed immediately so range loops terminate naturally.

### WebSocket Log Streaming

The dashboard handler subscribes to the log hub and forwards entries over a WebSocket connection. The endpoint is `GET /ws/system/logs`. The Gin route uses `gorilla/websocket` for the upgrade. Each connected browser receives a live stream of log entries; disconnection or WebSocket close triggers `cancel()`.

## Asynchronous File Writing

File I/O is decoupled from the main logging path. When file logging is enabled, the initializer starts a background goroutine (`startFileSink`) that:

1. Subscribes to the log hub with the configured buffer size.
2. Accumulates log entry raw JSON strings in a slice.
3. Flushes the slice to lumberjack's rotating file writer either when the batch size (`FlushBatch`) is reached or when the flush interval (`FlushIntervalMs`) elapses.

On shutdown, `stopFileSink` closes the stop channel, waits for the goroutine to finish flushing, and removes the subscriber. This ensures no log entries are lost during graceful shutdown.

## Log Entry Format

```go
type LogEntry struct {
    Time   string         `json:"time"`
    Level  string         `json:"level"`
    Msg    string         `json:"msg"`
    Module string         `json:"module,omitempty"`
    Caller string         `json:"caller,omitempty"`
    Error  string         `json:"error,omitempty"`
    Fields map[string]any `json:"fields,omitempty"`
    Raw    string         `json:"raw,omitempty"`
}
```

`Raw` contains the original JSON line from the file or stream, useful for forwarding without re-encoding.

## Historical Log Query

`QueryLogFileTail(path, limit, level, keyword)` reads the log file from the beginning, applying optional level and keyword filters, and returns the last `limit` matching entries (up to 5000). This powers the `GET /api/system/logs` endpoint which the admin panel uses for paginated historical log access.
