# Webhooks and Background Jobs

The `web` process runs three kinds of background work: webhook delivery, scheduled (cron) tasks, and mailer dispatch. They share the in-process queue primitives in `internal/sync/` and the global stores established at startup.

## Sync primitives

- `ExclusivePool` — per-key mutex pool. Callers `CheckIn(key)` then `CheckOut(key)`; concurrent requests for the same key serialize while different keys proceed in parallel.
- `UniqueQueue` — bounded queue with set semantics: enqueueing an already-queued key is a no-op.

`db.HookQueue = sync.NewUniqueQueue(1000)` is the global webhook dispatch queue.

## Webhook model

`internal/db/webhook.go` defines:

- `HookEvents` — boolean fan-out: `Create`, `Delete`, `Fork`, `Push`, `Issues`, `PullRequest`, `IssueComment`, `Release`.
- `HookEvent` — wraps `HookEvents` with `PushOnly`, `SendEverything`, `ChooseEvents` modes.
- `Webhook` — persisted row with `URL`, `ContentType` (`json` or `form`), `Secret`, `Events`, `IsSSL`, `IsActive`, `HookTaskType`, `Meta`, `LastStatus`.
- `HookTaskType` — enum for delivery format: generic Gogs, Slack, Discord, DingTalk. Renderers live in `webhook_slack.go`, `webhook_discord.go`, `webhook_dingtalk.go`.
- `HookStatus` — `HOOK_STATUS_NONE`, `HOOK_STATUS_SUCCEED`, `HOOK_STATUS_FAILED`.

`HookTask` records each delivery attempt with the encoded payload, response code and body, and delivery timestamp.

## Delivery loop

`db.DeliverHooks()` runs as a goroutine on startup. It drains `HookQueue`, loads pending `HookTask` rows for each enqueued repository, renders them per `HookTaskType`, and POSTs them with the configured content type. Signature headers (`X-Gogs-Signature`) are HMAC-SHA256 keyed on the webhook's `Secret`.

Delivery uses `internal/httplib` with a timeout of `[webhook] DeliverTimeout` seconds. When `[webhook] SKIP_TLS_VERIFY = true`, the client skips certificate verification. Outbound URLs are filtered against `[security] LocalNetworkAllowlist` through `internal/netutil/`.

## Triggering webhooks

When a domain event occurs (push, issue created, pull request opened, release), the handler builds an `api.PushPayload`, `api.IssuesPayload`, or similar from `go-gogs-client`. `db.PrepareWebhooks(repo, event, payload)` enumerates subscribing webhooks (including parent organization webhooks), persists a `HookTask` for each, and enqueues the repository ID; the delivery loop picks up the work asynchronously. Push payloads are produced from `cmd hook post-receive`.

## Webhook types

`[webhook] Types` (default `gogs,slack,discord,dingtalk`) gates which options the admin UI exposes. Generic Gogs uses the JSON shapes from `go-gogs-client`; Slack uses flattened message blocks; Discord uses embed-based payloads; DingTalk uses markdown-card payloads. Rendering is deferred to send time; the persisted task carries the generic payload.

## Cron scheduler

`internal/cron/cron.go` wraps `github.com/gogs/cron`. `cron.NewContext()` registers each enabled job, optionally launches a "run at start" execution in a goroutine, and calls `c.Start()`.

| Section | Action | Function |
|---|---|---|
| `[cron.update_mirrors]` | Fetch every active mirror | `db.MirrorUpdate` |
| `[cron.repo_health_check]` | `git fsck` per repo | `db.GitFsck` |
| `[cron.check_repo_stats]` | Refresh cached repo counts | `db.CheckRepoStats` |
| `[cron.repo_archive_cleanup]` | Delete archives older than `OlderThan` | `db.DeleteOldRepositoryArchives` |

Each job has `Enabled`, `Schedule`, and `RunAtStart`. `cron.ListTasks()` exposes the entries to the admin UI.

## Mailer

`internal/email/` drives outbound mail (registration confirmation, password reset, issue notification, collaboration invitation, pull request notifications). The mailer composes HTML plus optional plain-text alternatives (`[email] AddPlainTextAlt`) and sends through the SMTP relay configured in `[email]`. `[email] UseCertificate` enables TLS client certificate auth; `DisableHELO` and `HELOHostname` override the EHLO greeting.

## Notices and action feed

Administrative notices go into the `notice` table via `db.CreateNotice`; the admin UI lists and clears them. The `action` table records events for the user activity feed and repo dashboard; `db.NewPushCommits` and `db.NotifyWatchers` create rows synchronously from the triggering handlers.
