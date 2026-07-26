# Ech0 Background Scheduling and Task Management

## Overview

The `internal/task` package implements Ech0's background job scheduler using [gocron](https://pkg.go.dev/github.com/go-co-op/gocron/v2). It runs as an `app.Component`, starting and stopping with the application lifecycle. The scheduler manages four recurring jobs: temporary file cleanup, dead letter consumption, inbox maintenance, and automated backup.

## Tasker

```go
type Tasker struct {
    scheduler      gocron.Scheduler
    fileService    fileService.Service
    settingService settingService.Service
    publisher      *publisher.Publisher
    queueRepo      *queueRepository.QueueRepository
    storageManager *storage.Manager
    started        bool
    mu             sync.Mutex
}
```

The `Tasker` implements `app.Component`:

```go
func (t *Tasker) Start(context.Context) error
func (t *Tasker) Stop(context.Context) error
func (t *Tasker) Name() string  // returns "tasker"
```

`Start` is idempotent: if `started` is already true it returns immediately. `Stop` calls `scheduler.Shutdown()` which drains in-flight jobs before returning.

## Scheduled Jobs

### Cleanup Temporary Files

Runs every **72 hours**. Calls `fileService.CleanupOrphanFiles()` which queries for file records that have no associated echo post references and removes both the database record and the underlying VireFS file.

Files are classified as orphans when they were uploaded but never referenced in a published post, or when a post was deleted and left behind unreferenced attachments.

### Dead Letter Consumption

Runs every **5 minutes**. Fetches up to 10 `DeadLetter` records from the database whose `next_retry` timestamp is in the past and `status` is `pending`. For each record, publishes a `DeadLetterRetriedEvent` to the Busen event bus. The `DeadLetterResolver` subscriber handles the actual retry logic.

Polling every 5 minutes ensures that failed webhook deliveries are retried at approximately minute-level granularity without the scheduler needing to track individual retry timers.

### Inbox Maintenance

Runs **daily at 12:00 UTC**. Publishes two events:

1. `Ech0UpdateCheckEvent` — triggers an HTTP request to check for a new Ech0 release. If a new version is available, an inbox message is created for the admin to see in the admin panel.
2. `InboxClearEvent` — triggers cleanup of inbox messages that have been marked as read and are older than 7 days.

### Automated Backup

A **cron-scheduled** job whose expression is loaded from the `BackupSchedule` setting in the database at startup. The default cron expression when enabled is `0 2 * * 0` (weekly on Sunday at 02:00 UTC). The job is not started automatically; it must be explicitly enabled through the admin panel's backup schedule settings.

When the job fires it:

1. Calls `backup.ExecuteBackup()` which creates a zip archive of the `data/` directory using VireFS.
2. If S3 is configured, uploads the archive to the S3 backend via `backup.UploadToS3`.
3. Publishes a `SystemBackupEvent` to the event bus (which may trigger webhook delivery).

The `ScheduleBackupTask` method auto-detects whether the cron expression has 5 fields (minute-hour-day-month-weekday) or 6 fields (with a leading seconds field) and configures gocron accordingly.

## Dynamic Schedule Updates

The backup schedule can be changed at runtime without restarting the application. When an operator updates the backup cron expression in the admin panel, the settings service publishes a `BackupScheduleUpdatedEvent`. The `eventsubscriber.BackupScheduler` subscriber handles this event by calling `Tasker.ApplyBackupSchedule`:

```go
func (t *Tasker) ApplyBackupSchedule(schedule settingModel.BackupSchedule) error
```

`ApplyBackupSchedule` removes all jobs tagged `BackupSchedule` from the gocron scheduler using `scheduler.RemoveByTags(backupScheduleTag)` and then re-registers the job with the new cron expression (or skips re-registration if `Enable` is false). This allows zero-downtime schedule changes.

## Worker Pool for Webhooks

The `async.WorkerPool` used by the webhook dispatcher is not a gocron job but a long-lived goroutine pool. It is initialized during `Dispatcher` construction and stopped in `Dispatcher.Stop()`. The pool serializes webhook delivery tasks to avoid bursting too many concurrent HTTP requests.

```go
type WorkerPool struct {
    wg      sync.WaitGroup
    tasks   chan func() error
    stopped bool
    mu      sync.Mutex
}
```

`Submit(task)` adds a task to the task channel. Workers drain the channel concurrently up to the configured pool size. `Wait()` blocks until all submitted tasks have been processed. `Stop()` closes the task channel and waits for all workers to finish.

## Dependency Injection

`NewTasker` is wired by Wire using the `TaskerGraphSet`:

```go
func NewTasker(
    fileSvc    fileService.Service,
    settingSvc settingService.Service,
    publisher  *publisher.Publisher,
    queueRepo  *queueRepository.QueueRepository,
    storageManager *storage.Manager,
) *Tasker
```

The tasker is registered as a component in the application's `BuildApp()` output alongside the HTTP server. It starts after the server to ensure event bus subscriptions are ready before any jobs could fire.

## Error Handling

Job-level errors are logged with `logUtil.GetLogger().Error(...)` and do not propagate to the scheduler (no automatic job disabling on error). Each job is independent: a failure in the cleanup job does not affect the dead letter or backup jobs. Errors in `Start` (such as a nil scheduler or failure registering a job) propagate up and abort application startup.
