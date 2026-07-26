# Ech0 Configuration Reference

## Configuration Philosophy

Ech0 uses a single-source-of-truth pattern: all configuration values are loaded once at process start from environment variables (and optionally a `.env` file), coalesced with typed defaults, and stored in an `AppConfig` singleton. The singleton is initialized with `sync.Once` and accessed throughout the codebase via `config.Config()`.

A `.env` file in the working directory is loaded automatically if present. System environment variables take precedence over `.env` values. If no file is found the process continues with system environment variables alone.

## AppConfig Structure

The top-level configuration type groups settings by concern:

```go
type AppConfig struct {
    Server    ServerConfig
    Database  DatabaseConfig
    Log       LogConfig
    Auth      AuthConfig
    Upload    UploadConfig
    Storage   StorageConfig
    Event     EventConfig
    Migration MigrationConfig
    Setting   SettingConfig
    Comment   CommentConfig
    Security  SecurityConfig
    Web       WebConfig
}
```

## Server

| Environment Variable | Default | Description |
|---|---|---|
| `ECH0_SERVER_PORT` | `6277` | TCP port to listen on |
| `ECH0_SERVER_HOST` | `0.0.0.0` | Bind address |
| `ECH0_SERVER_MODE` | `release` | Gin mode (`debug` or `release`) |

## Database

| Environment Variable | Default | Description |
|---|---|---|
| `ECH0_DB_TYPE` | `sqlite` | Database type (only SQLite is currently wired) |
| `ECH0_DB_PATH` | `data/ech0.db` | Path to the SQLite database file |
| `ECH0_DB_LOGMODE` | `release` | GORM log verbosity |

## Authentication

| Environment Variable | Default | Description |
|---|---|---|
| `JWT_SECRET` | random 32-char hex | HMAC-SHA256 signing key for all tokens; **set this in production** |
| `ECH0_JWT_EXPIRES` | `2592000` (30 days) | Session token lifetime in seconds |
| `ECH0_JWT_ISSUER` | `ech0` | JWT `iss` claim |
| `ECH0_JWT_AUDIENCE` | `ech0` | JWT `aud` claim |
| `ECH0_AUTH_REDIRECT_ALLOWED_RETURN_URLS` | (empty) | Comma-separated list of allowed OAuth redirect return URLs |
| `ECH0_AUTH_WEBAUTHN_RP_ID` | (empty) | WebAuthn Relying Party ID (domain only, no scheme) |
| `ECH0_AUTH_WEBAUTHN_ORIGINS` | (empty) | Comma-separated WebAuthn allowed origins |

If `JWT_SECRET` is not set, a random 32-byte hex secret is generated at startup. This means session tokens are invalidated every time the process restarts. For persistent sessions across deployments, always set `JWT_SECRET` explicitly.

## Storage

### Local storage

| Environment Variable | Default | Description |
|---|---|---|
| `ECH0_STORAGE_DATA_ROOT` | `data/files` | Root directory for locally stored files |
| `ECH0_UPLOAD_IMAGE_MAX_SIZE` | `20971520` (20 MB) | Maximum image upload size in bytes |
| `ECH0_UPLOAD_AUDIO_MAX_SIZE` | `20971520` (20 MB) | Maximum audio upload size in bytes |

### S3-compatible object storage

| Environment Variable | Default | Description |
|---|---|---|
| `ECH0_OBJECT_ENABLED` | `false` | Enable S3 object storage in addition to local |
| `ECH0_S3_ENDPOINT` | (empty) | S3 endpoint without `http://` or `https://` |
| `ECH0_S3_ACCESS_KEY` | (empty) | Access key ID |
| `ECH0_S3_SECRET_KEY` | (empty) | Secret access key |
| `ECH0_S3_BUCKET` | (empty) | Bucket name |
| `ECH0_S3_REGION` | (empty) | Region |
| `ECH0_S3_PROVIDER` | (empty) | Provider hint: `aws`, `r2`, `minio`, or `other` |
| `ECH0_S3_USE_SSL` | `false` | Use HTTPS when connecting to S3 |
| `ECH0_S3_CDN_URL` | (empty) | CDN base URL for publicly serving objects |
| `ECH0_S3_PATH_PREFIX` | (empty) | Key prefix for all objects in the bucket |

S3 settings can also be configured at runtime through the admin panel; database-stored values are merged over environment defaults at every reload.

## Logging

| Environment Variable | Default | Description |
|---|---|---|
| `ECH0_LOG_LEVEL` | `info` | Log level: `debug`, `info`, `warn`, `error` |
| `ECH0_LOG_FORMAT` | `json` | `json` or `console` |
| `ECH0_LOG_CONSOLE` | `false` | Also write logs to stdout |
| `ECH0_LOG_FILE_ENABLE` | `true` | Write logs to a rotating file |
| `ECH0_LOG_FILE_PATH` | `data/app.log` | Log file path |
| `ECH0_LOG_FILE_MAX_SIZE` | `100` | Maximum file size before rotation (MB) |
| `ECH0_LOG_FILE_MAX_BACKUPS` | `5` | Number of old log files to retain |
| `ECH0_LOG_FILE_MAX_AGE` | `30` | Maximum age of log files in days |
| `ECH0_LOG_FILE_COMPRESS` | `true` | Gzip-compress rotated files |
| `ECH0_LOG_BUFFER_SIZE` | `2048` | In-memory log stream buffer size |
| `ECH0_LOG_RECENT_SIZE` | `2000` | Number of recent entries retained for live console |
| `ECH0_LOG_DROP_POLICY` | `drop_oldest` | Buffer overflow policy: `drop_oldest` or `drop_newest` |
| `ECH0_LOG_FLUSH_BATCH` | `128` | Batch size for async file writes |
| `ECH0_LOG_FLUSH_INTERVAL_MS` | `500` | Flush interval for async file writes (milliseconds) |

## Event Bus (Busen)

| Environment Variable | Default | Description |
|---|---|---|
| `ECH0_EVENT_DEFAULT_BUFFER` | `512` | Default channel buffer size |
| `ECH0_EVENT_DEFAULT_OVERFLOW` | `block` | Default overflow policy |
| `ECH0_EVENT_DEADLETTER_BUFFER` | `64` | Dead letter channel buffer |
| `ECH0_EVENT_SYSTEM_BUFFER` | `64` | System event channel buffer |
| `ECH0_EVENT_AGENT_BUFFER` | `128` | AI agent event channel buffer |
| `ECH0_EVENT_AGENT_PARALLELISM` | `2` | Concurrent agent invocations |
| `ECH0_EVENT_INBOX_BUFFER` | `64` | Inbox event channel buffer |
| `ECH0_EVENT_WEBHOOK_POOL_WORKERS` | `6` | Webhook worker goroutines |
| `ECH0_EVENT_WEBHOOK_POOL_QUEUE` | `6` | Webhook task queue depth |

## Data Migration Worker

| Environment Variable | Default | Description |
|---|---|---|
| `ECH0_MIGRATION_WORKER_ENABLED` | `false` | Enable background ETL migration worker |
| `ECH0_MIGRATION_MAX_CONCURRENCY` | `1` | Parallel migration batch workers |
| `ECH0_MIGRATION_BATCH_SIZE` | `100` | Records per extraction batch |
| `ECH0_MIGRATION_RATE_LIMIT_PER_SEC` | `20` | Maximum records processed per second |

## Web / CORS

| Environment Variable | Default | Description |
|---|---|---|
| `ECH0_WEB_CORS_ALLOWED_ORIGINS` | (empty) | Comma-separated additional CORS allowed origins |

## Runtime-Overridable Settings

A second category of settings lives in the database (key-value store) and can be modified through the admin panel at runtime without a restart. These include:

- Site title, logo, server name, and service URL
- User registration toggle
- Footer content and links
- MetingAPI endpoint for music card resolution
- Custom CSS and JavaScript injection
- Comment system enable/disable and CAPTCHA parameters
- S3 storage credentials and endpoint
- OAuth2 / OIDC provider configuration
- WebAuthn relying party settings
- Webhook endpoint registry
- Backup schedule cron expression
- AI agent provider, model, and prompt

These database-backed settings are loaded and cached on first access; the storage manager and settings service expose `Reload` methods so changes take effect without process restart.
