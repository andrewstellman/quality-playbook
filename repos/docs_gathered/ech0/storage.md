# Ech0 Storage Subsystem (VireFS)

## Overview

Ech0 abstracts all file I/O through [VireFS](https://github.com/lin-snow/VireFS), a virtual filesystem library that provides a unified interface over both local disk and S3-compatible object storage. The application never writes files using raw `os` calls for user content; instead it talks to a VireFS instance and lets the library route to the appropriate backend.

## Storage Manager

`internal/storage/Manager` is the single point of control for storage configuration. It is initialized at startup and can be reloaded at runtime when the operator updates S3 settings through the admin panel:

```go
type Manager struct {
    mu         sync.RWMutex
    defaultCfg config.StorageConfig
    store      S3SettingStore
    selector   *StorageSelector
}
```

Key methods:

| Method | Description |
|---|---|
| `NewStorageManager(store)` | Constructs a manager; immediately loads and merges config |
| `GetSelector()` | Returns the current `StorageSelector` under read lock |
| `GetStorageConfig(ctx)` | Returns the merged active configuration |
| `ReloadFromConfigAndDB(ctx)` | Re-reads DB settings and replaces the active selector |
| `ApplyS3Setting(setting)` | Applies in-memory S3 setting and replaces the selector |

`MergeStorageConfig` merges environment-derived defaults with database-stored S3 settings. Database values take precedence for every field that is non-empty.

## StorageSelector

`StorageSelector` wraps one or two VireFS filesystems — always a local FS, optionally an S3 FS — and routes operations according to the active configuration. When `ObjectEnabled` is true, uploaded files go to the S3 backend; the local backend is still used for system data (database file, backups, logs).

## Storage Categories

Files are classified at upload time by the `Category` type:

```go
type Category string

const (
    CategoryImage    Category = "image"
    CategoryVideo    Category = "video"
    CategoryAudio    Category = "audio"
    CategoryPDF      Category = "pdf"
    CategoryMarkdown Category = "markdown"
    CategoryFile     Category = "file"
)
```

`NormalizeCategory` maps arbitrary strings to known categories; unrecognized values fall back to `CategoryFile`.

## Storage Types

Three storage type identifiers are used in file records:

```go
const (
    StorageTypeLocal    StorageType = "local"
    StorageTypeObject   StorageType = "object"
    StorageTypeExternal StorageType = "external"
)
```

`StorageTypeExternal` is used for user-provided links (URLs), not for files Ech0 itself manages.

## Key Generation

The `KeyGenerator` interface abstracts filename key construction:

```go
type KeyGenerator interface {
    GenerateKey(category Category, userID string, originalFilename string) (string, error)
}
```

Keys are flat strings (no directory prefix). The VireFS schema layer handles directory routing transparently based on category. Keys are stored in the database; the `URLResolver` function maps a stored key back to a publicly accessible URL at request time.

## URL Resolution

A `URLResolver` is a function type constructed once at startup:

```go
type URLResolver func(key string) string
```

When S3 with a CDN URL is configured, the resolver prepends the CDN base URL. Without a CDN URL but with S3 enabled, it constructs the S3 endpoint URL. For local storage it returns a relative path that the Gin server serves from the static file handler.

`TrimLeadingSlash` is a small helper that removes a leading `/` from VireFS virtual paths to produce clean keys for database storage.

## Backup Integration

The backup subsystem (`internal/backup`) also uses VireFS. `ExecuteBackup` opens the `data/` directory as a local VireFS and walks it to collect file keys, excluding the backup output directory and temporary directory from the archive to avoid recursive inclusion. The collected keys are packed into a zip archive using the `VireFS/plugin/zip` plugin.

`UnpackZipToDir` is the corresponding restore function. It opens a destination VireFS (creating the root directory if needed) and unpacks the zip into it using `vizip.Unpack`.

When S3 is enabled, the scheduled backup task additionally uploads the completed zip to S3 via `backup.UploadToS3` after local archiving.

## File Lifecycle

The typical file lifecycle:

1. **Upload** — Handler calls file service, which generates a key via `KeyGenerator`, writes the bytes to the VireFS selector, and persists a file record in the database with the key, category, storage type, and uploader user ID.
2. **Reference** — Posts embed file keys. When rendering or returning file URLs, the `URLResolver` converts stored keys to public URLs.
3. **Orphan cleanup** — The background `CleanupTempFilesTask` runs every 72 hours and calls `fileService.CleanupOrphanFiles()` to delete files that have no associated post references.

## Allowed Upload Types

The default allowed MIME types for uploads are:

- Images: `image/jpeg`, `image/png`, `image/gif`, `image/webp`, `image/svg+xml`, `image/avif`
- Audio: `audio/mpeg`, `audio/flac`, `audio/wav`, `audio/mp4`

These can be extended by modifying the `ECH0_UPLOAD_*` environment variables or by overriding the `UploadConfig.AllowedTypes` slice in a custom build.

## S3 Configuration at Runtime

S3 settings are stored in the `key_values` table under a well-known key. When an operator saves new S3 credentials through the admin panel, the settings service writes the JSON blob to the database and calls `Manager.ApplyS3Setting` to replace the active `StorageSelector` without restarting the process. If the new S3 credentials fail to connect (for example, bucket does not exist or credentials are wrong), `ApplyS3Setting` returns an error and the previous selector remains active.
