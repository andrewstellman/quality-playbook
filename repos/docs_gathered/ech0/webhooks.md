# Ech0 Webhook Subsystem

## Overview

The webhook subsystem delivers Ech0 domain events to external HTTP endpoints. When internal events fire — post created, user updated, file uploaded, backup completed, and others — the dispatcher serializes them as JSON and sends an HTTP POST request to each active registered endpoint. Optional HMAC-SHA256 signatures allow receivers to authenticate the request origin.

## Architecture

The subsystem spans two packages:

- `internal/webhook/` — `Dispatcher` and HTTP client
- `internal/webhook/infra/httpclient/` — Low-level send-with-retry logic

The `Dispatcher` subscribes to the event bus through the `WebhookObserver` interface, which is wired in the dependency graph at startup via `eventregistry.WebhookObserver`. All observable events route to `HandleObservation`.

## Dispatcher

```go
type Dispatcher struct {
    client     *http.Client
    repo       WebhookStore
    pool       *async.WorkerPool
    queueRepo  DeadLetterStore
    transactor transaction.Transactor
}
```

The HTTP client is configured with a 5-second timeout, a pool of up to 10 idle connections per host, and a 30-second idle connection timeout.

The worker pool size and queue depth are configurable (`ECH0_EVENT_WEBHOOK_POOL_WORKERS`, `ECH0_EVENT_WEBHOOK_POOL_QUEUE`, both default 6). Each incoming `WebhookObservation` is submitted as a task to the pool so the event bus goroutine is not blocked by network I/O.

## Delivery Flow

1. `HandleObservation(ctx, obs)` queries `WebhookStore.ListActiveWebhooks` to obtain enabled endpoints.
2. Each webhook is submitted to the worker pool as an independent task.
3. `Dispatch(ctx, wh, obs)` calls `httpclient.SendWithRetry` with up to 3 attempts and 500ms initial backoff (exponential).
4. On success (HTTP 2xx), `UpdateWebhookDeliveryStatus` records `status: success` and the trigger timestamp.
5. On failure, the status is set to `failed` and a `DeadLetter` record is written to the database via the `Transactor`.

## Request Format

Each outbound POST carries the following headers:

| Header | Value |
|---|---|
| `Content-Type` | `application/json` |
| `User-Agent` | `Ech0-Webhook-Client` |
| `X-Ech0-Event` | Topic string (e.g., `echo.created`) |
| `X-Ech0-Event-ID` | Nanosecond timestamp string (unique delivery ID) |
| `X-Ech0-Timestamp` | UTC Unix seconds |
| `X-Ech0-Signature` | `sha256=<hex>` (present only when `secret` is configured) |

Request body:

```json
{
  "topic": "echo.created",
  "event_name": "EchoCreatedEvent",
  "payload_raw": { ... },
  "metadata": { ... },
  "occurred_at": 1710000000
}
```

## Signature Verification

When a webhook has a `secret` configured, the dispatcher computes `HMAC-SHA256(secret, rawBodyBytes)` and includes the hex digest in the `X-Ech0-Signature` header as `sha256=<hex>`. Receivers should verify this signature using `crypto.timingSafeEqual` or equivalent to prevent timing attacks.

Recommended receiver checks:
- Verify the signature using the configured secret
- Check `X-Ech0-Timestamp` against the current time (reject if outside a window of ±5 minutes to prevent replay)
- Use `X-Ech0-Event-ID` for idempotent deduplication

## Allowed Topics (Webhook Whitelist)

Only events with the following topics are forwarded to webhook endpoints:

```
user.created          user.updated          user.deleted
echo.created          echo.updated          echo.deleted
resource.uploaded
system.backup         system.export
system.backup_schedule.updated
inbox.clear
ech0.update.check
```

Internal events (e.g., `deadletter.retried`) are not forwarded externally.

## Dead Letter Queue

When `SendWithRetry` exhausts all attempts, a `DeadLetter` record is stored in the database:

```go
type DeadLetter struct {
    Type       string    // "webhook"
    Payload    []byte    // serialized WebhookReplayPayload
    ErrorMsg   string
    RetryCount int
    NextRetry  time.Time // initially 6 hours after failure
    Status     string    // "pending", "success", "discarded"
}
```

The background `DeadLetterConsumeTask` runs every 5 minutes and fetches up to 10 pending dead letters whose `next_retry` is in the past. It publishes each as a `DeadLetterRetriedEvent` on the Busen bus. The `DeadLetterResolver` subscriber picks these up and calls `Dispatcher.HandleDeadLetter`, which runs the same send-with-retry logic as normal dispatch.

On retry success the dead letter is marked `success`. On retry failure the `next_retry` is pushed out further (15 minutes by default) and the retry count is incremented. Dead letters that exceed the maximum retry count are marked `discarded`.

## URL Validation

Webhook URLs undergo server-side validation before being saved. The validation enforces:

- Scheme must be `http` or `https`
- `localhost` is not allowed
- `.local` TLD domains are not allowed
- Private address ranges (10.x.x.x, 192.168.x.x, 172.16–31.x.x, loopback, link-local) are not allowed

This prevents the webhook system from being used to reach internal network services. Local development testing requires a publicly reachable tunnel address.

## Management API

Webhook endpoints are managed through the admin API:

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/webhook` | List all webhooks |
| `POST` | `/api/webhook` | Create a webhook |
| `PUT` | `/api/webhook/:id` | Update a webhook |
| `DELETE` | `/api/webhook/:id` | Delete a webhook |
| `POST` | `/api/webhook/:id/test` | Send a test delivery |

The create/update DTO:

```json
{
  "name": "My Receiver",
  "url": "https://example.com/hooks/ech0",
  "secret": "signing-secret",
  "is_active": true
}
```

The `secret` field is write-only; it is not returned in list or get responses.

The test endpoint sends a `webhook.test` event payload with 2 retry attempts and updates `last_status` and `last_trigger` regardless of outcome.
