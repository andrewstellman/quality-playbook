# Ech0 Event Bus (Busen)

## Overview

Ech0 uses [Busen](https://github.com/lin-snow/Busen), an in-process typed event bus, to decouple the service layer from side effects such as webhook delivery, AI agent invocations, inbox updates, and background maintenance tasks. Rather than calling these subsystems directly from service methods, services publish named events onto the bus; registered subscribers consume those events asynchronously.

The bus is identified in `go.mod` as `github.com/lin-snow/Busen v0.3.0`. Its design prioritizes typed-first message passing, explicit backpressure through configurable channel buffers, and graceful drain shutdown.

## Architecture

The event subsystem lives in `internal/event/` with four sub-packages:

```
internal/event/
  bus/          Busen bus provider and initialization
  contracts/    Event type definitions (the "vocabulary")
  publisher/    Publisher facade used by service code
  registry/     EventRegistrar wires subscribers to the bus at startup
  subscriber/   Subscriber implementations
```

This structure keeps the vocabulary of events (`contracts/`) independent of both publishers and subscribers, preventing circular imports.

## Event Contracts

All event types are defined in `internal/event/contracts/`. Current event types include:

| Event Type | Topic | Description |
|---|---|---|
| `EchoCreatedEvent` | `echo.created` | A post was published |
| `EchoUpdatedEvent` | `echo.updated` | A post was edited |
| `EchoDeletedEvent` | `echo.deleted` | A post was deleted |
| `UserCreatedEvent` | `user.created` | A new user account was registered |
| `UserUpdatedEvent` | `user.updated` | User profile was modified |
| `UserDeletedEvent` | `user.deleted` | User account was deleted |
| `ResourceUploadedEvent` | `resource.uploaded` | A file was uploaded |
| `SystemBackupEvent` | `system.backup` | A backup completed |
| `SystemExportEvent` | `system.export` | A snapshot export completed |
| `BackupScheduleUpdatedEvent` | `system.backup_schedule.updated` | Backup schedule configuration changed |
| `InboxClearEvent` | `inbox.clear` | Inbox cleared |
| `Ech0UpdateCheckEvent` | `ech0.update.check` | Version check triggered |
| `DeadLetterRetriedEvent` | `deadletter.retried` | Dead letter replayed (internal only) |
| `WebhookObservation` | (varies) | Wrapper delivered to all webhook endpoints |
| `WebhookReplayPayload` | — | Payload stored in dead letter for retry |

`WebhookObservation` is the outbound envelope structure. It carries `topic`, `event_name`, `payload_raw`, `metadata`, and `occurred_at`.

## Publisher

`internal/event/publisher/Publisher` is the facade that service code uses to emit events. It provides one method per event type, for example:

```go
func (p *Publisher) EchoCreated(ctx context.Context, event contracts.EchoCreatedEvent) error
func (p *Publisher) SystemBackup(ctx context.Context, event contracts.SystemBackupEvent) error
func (p *Publisher) DeadLetterRetried(ctx context.Context, event contracts.DeadLetterRetriedEvent) error
```

Service code depends on the `Publisher` struct directly (injected via Wire) rather than on an interface. This avoids the overhead of a second abstraction layer while keeping publishers out of the infrastructure packages.

## Event Registry

`internal/event/registry/EventRegistrar` subscribes each subscriber to its events on the bus during the application's `Start` phase. It holds a list of `SubscriptionProvider` values — each subscriber implements this interface to declare what topics it consumes. The registry wires these to the bus and starts the consumption goroutines.

The `WebhookObserver` interface is implemented by `webhook.Dispatcher`, allowing the registry to route all observable events to the dispatcher without hard-coding the webhook package.

## Subscribers

Four production subscribers are registered:

### BackupScheduler

`eventsubscriber.BackupScheduler` listens for `BackupScheduleUpdatedEvent`. When it receives one, it calls `task.Tasker.ApplyBackupSchedule` to dynamically replace the scheduled backup cron job without restarting the process.

### DeadLetterResolver

`eventsubscriber.DeadLetterResolver` handles `DeadLetterRetriedEvent`. It unmarshals the dead letter payload and dispatches the webhook retry through `webhook.Dispatcher.HandleDeadLetter`. On success, the dead letter is marked resolved; on failure, the retry counter is incremented and the next retry is scheduled.

### AgentProcessor

`eventsubscriber.AgentProcessor` listens for events that should trigger AI-generated responses (such as recent content summarization). It invokes `internal/agent.Generate` with the configured provider and model.

### InboxDispatcher

`eventsubscriber.InboxDispatcher` receives system events and creates inbox messages visible in the admin panel. For example, a successful update check triggers an inbox entry that links to release notes.

## Bus Configuration

Buffer sizes and overflow policies for each channel are configurable through `ECH0_EVENT_*` environment variables (see the configuration reference). Default values:

| Channel | Buffer | Overflow |
|---|---|---|
| Default | 512 | `block` |
| Dead letter | 64 | — |
| System | 64 | — |
| Agent | 128 | — |
| Inbox | 64 | — |

The agent parallelism setting (`ECH0_EVENT_AGENT_PARALLELISM`, default 2) controls how many concurrent AI inference calls the AgentProcessor allows.

## Error Handling and Dead Letters

Events that cannot be delivered to their subscriber (for example, a webhook call that fails after retries) are stored as `DeadLetter` records in the database. Each record holds the serialized original payload, the last error message, a retry count, and a `next_retry` timestamp.

The background task scheduler (`internal/task/Tasker.DeadLetterConsumeTask`) polls the dead letter table every five minutes and re-publishes up to ten pending records as `DeadLetterRetriedEvent` messages. The `DeadLetterResolver` subscriber handles those messages and clears the dead letter on success.

Dead letters that exceed the maximum retry count are marked as discarded. Their payloads remain in the database for operator inspection.
