# Automation Engine — packages/server/src/automations

## Overview

The automation engine allows Budibase users to define event-driven workflows. Each automation consists of a single trigger and an ordered sequence of steps. Automations are persisted in the workspace CouchDB database as `Automation` documents. At runtime, the engine evaluates trigger conditions, resolves Handlebars template bindings in step inputs, executes each step in turn, and stores the result log.

Automations can be selectively disabled via the `APP_FEATURES` environment variable (omitting `automations` from the list). The `/health` endpoint returns 503 if the automation queue is not ready.

## Triggers

Trigger definitions are declared in `packages/shared-core/src/automations/triggers/` and exported as a static `definitions` map keyed by `AutomationTriggerStepId`:

| Step ID | Event |
|---------|-------|
| `ROW_SAVED` | A row is created in a specified table |
| `ROW_UPDATED` | A row is modified in a specified table |
| `ROW_DELETED` | A row is deleted from a specified table |
| `WEBHOOK` | An inbound HTTP POST to the automation's webhook URL |
| `APP` | A programmatic call from within the app (button action or `triggerAutomationRun` step) |
| `CRON` | A cron expression (e.g., `0 9 * * 1` for Monday at 09:00) |
| `EMAIL` | An inbound email |
| `ROW_ACTION` | A row-level action button defined on a table |

Row triggers listen via the `BudibaseEmitter` event emitter in `packages/server/src/events/`. When a row save/update/delete occurs, the emitter calls `queueRelevantRowAutomations`, which queries all automations for the workspace, filters those whose trigger matches the table ID and optional pre-filters (`SearchFilters`), and enqueues matching ones.

Cron triggers are persisted as scheduled Bull jobs. On server startup, `rehydrateScheduledTriggers` re-creates any cron jobs that may have been lost (common in ephemeral Redis deployments). The `disableCronById` utility cancels a cron job's Bull repeat entry when an automation is deleted or deactivated.

## Queue

The automation queue (`bullboard.ts`) is a `BudibaseQueue<AutomationData>` backed by Bull + Redis:

```ts
const automationQueue = new queue.BudibaseQueue<AutomationData>(
  queue.JobQueue.AUTOMATION,
  { removeStalledCb: job => automation.removeStalled(job) }
)
```

The queue is initialized in `automations/index.ts` via `automationQueue.process(async job => processEvent(job))`. Job metadata tags (`automation.id`, `automation.name`, `automation.trigger`, etc.) are attached for observability via Datadog.

## Execution Thread

Each automation job is executed in a separate worker thread via `threads/automation.ts`. This isolates memory and CPU from the main Koa event loop. Thread setup calls `threadUtils.threadSetup()` which configures the DB and context for the thread.

Within the thread, `processEvent` is the main entry function. It:

1. Sets the workspace context from `job.data.event.appId`.
2. Resolves the full `Automation` document.
3. Calls `executeAutomation(automation, event)`.
4. Stores the result log via `storeLog`.

## Step Execution

`executeAutomation` in `threads/automation.ts` iterates the automation's `steps` array. For each step:

1. Input values are resolved: all `{{ ... }}` bindings in the step's input object are processed by `processObject` from `@budibase/string-templates`. The binding context includes the trigger output, prior step outputs, and app/user metadata.
2. `cleanInputValues` coerces string-typed template outputs to the declared type (number, boolean).
3. The step function from `automations/actions.ts` is invoked.
4. The result is stored in the automation context under the step ID.

### Built-in Action Steps

| Step ID | Description |
|---------|-------------|
| `CREATE_ROW` | Insert a row into a table |
| `UPDATE_ROW` | Update fields of an existing row |
| `DELETE_ROW` | Delete a row by ID |
| `GET_ROW` | Fetch a single row by ID |
| `QUERY_ROWS` | Search rows with filters |
| `EXECUTE_QUERY` | Run a saved datasource query |
| `EXECUTE_SCRIPT` / `EXECUTE_SCRIPT_V2` | Run a `{{ js "..." }}` JavaScript block |
| `SERVER_LOG` | Emit a structured log line |
| `SEND_EMAIL_SMTP` | Send an email via SMTP |
| `OUTGOING_WEBHOOK` | HTTP request to an external URL |
| `SLACK` / `DISCORD` / `ZAPIER` / `N8N` / `MAKE` | External app integrations |
| `COLLECT` | Accumulate multiple step outputs into an array |
| `FILTER` | Conditional branch — stops the automation if the condition is not met |
| `DELAY` | Pause execution for a configurable duration |
| `LOOP` (via `LoopV2Step`) | Iterate over an array or delimited string |
| `BRANCH` | Conditional routing: evaluates `SearchFilters` to choose a branch |
| `TRIGGER_AUTOMATION_RUN` | Synchronously invoke a child automation |
| `EXTRACT_STATE` | Extract structured data from prior step outputs |
| `API_REQUEST` | Make an HTTP request with full control over headers and body |
| `BASH` | Run a shell command (self-hosted only) |
| `OPENAI` / AI steps | LLM calls: classify content, prompt LLM, translate, summarise, generate text, extract file data |

### Branching and Looping

`BranchStep` evaluates a list of `BranchSearchFilters` against the current automation context. The first matching branch's sub-steps are executed. `LoopV2Step` iterates an array or splits a string, running the inner steps for each element. Nested loop depth is capped at `AUTOMATION_MAX_NESTED_LOOPS` (default 3). Stored loop results are capped at `AUTOMATION_MAX_STORED_LOOP_RESULTS` (default 50).

## Result Logging

After execution, results are written to CouchDB as `AutomationLog` documents. The log records each step's output, status (`SUCCESS`, `ERROR`, `STOPPED`, `SKIPPED`), and any error messages (truncated at `ERROR_PREVIEW_LENGTH` = 512 characters). Total log size per run is capped at `AUTOMATION_MAX_LOG_SIZE_MB` (default 5 MB). Recurring automations that hit `AUTOMATION_MAX_RECURRING_ERRORS` consecutive failures are automatically disabled.

## Testing Automations

The builder sends a `POST /api/automations/:id/test` request to trigger a single test run. The server routes this through the same execution thread as production runs but sets a test-mode flag (checked via `checkTestFlag` in Redis) so that the test result is routed back to the builder's WebSocket session rather than stored as a production log. The `AutomationTestProgressEvent` system emits incremental progress events back to the builder during the test run.
