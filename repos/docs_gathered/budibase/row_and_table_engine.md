# Row and Table Engine — packages/server/src/sdk/workspace/rows, packages/server/src/sdk/workspace/tables

## Overview

The row and table engine is the core data-access layer of `packages/server`. It abstracts over internal (CouchDB-backed) and external (integration-backed) storage, presenting a uniform API to controllers regardless of where data physically resides. All row and table operations go through this layer; no controller accesses CouchDB or integration classes directly.

## Routing: Internal vs External

The central dispatch pattern appears throughout the layer:

```ts
function pickApi(tableOrViewId: string) {
  const tableId = isViewId(tableOrViewId)
    ? getTableIdFromViewId(tableOrViewId)
    : tableOrViewId
  return isExternalTableID(tableId) ? external : internal
}
```

`isExternalTableID` checks whether the table ID prefix indicates an external datasource. Internal table IDs use the `INTERNAL_TABLE_SOURCE_ID` prefix; external tables use a composite ID that encodes the datasource ID and table name.

## Row SDK (`sdk/workspace/rows/`)

### Core Operations

```ts
// Save (create or update) a row
save(sourceId: string, row: Row, userId?: string, opts?: { updateAIColumns: boolean }): Promise<Row>

// Find a single row by ID
find(sourceId: string, rowId: string): Promise<Row>

// Delete one or more rows
destroy(sourceId: string, rows: Row | Row[]): Promise<void>

// Search rows with filters, sort, and pagination
search(options: RowSearchParams, context?: Record<string, any>): Promise<SearchResponse<Row>>
```

`sourceId` may be either a table ID or a view ID. When it is a view ID, the engine resolves the parent table and applies the view's filters and schema restrictions on top.

### Input and Output Processing

All rows pass through `inputProcessing` before write and `outputProcessing` after read. These functions in `utilities/rowProcessor/` perform:

- **Auto-columns**: `_id`, `_rev`, `createdAt`, `updatedAt`, `createdBy`, `updatedBy` are populated automatically based on `AutoFieldSubType`.
- **Formula columns**: static and dynamic formula expressions are evaluated. Static formulas are stored with the row; dynamic formulas are evaluated at read time.
- **BB Reference fields**: `BB_REFERENCE` and `BB_REFERENCE_SINGLE` values are resolved to full user objects (name, email, avatar) at read time and stripped back to IDs at write time.
- **Attachment handling**: attachment fields store metadata objects (`{ name, size, extension, key }`); a signed URL is generated and attached to the response at read time.
- **Type coercion**: the `TYPE_TRANSFORM_MAP` maps each `FieldType` to coercion rules for empty strings, null, and `parse` conversions.

### Row Search

`sdk/workspace/rows/search.ts` routes search to:

- **`internal`** — uses the SQS (CouchDB-SQS SQLite mirror) endpoint when available, falling back to Mango queries.
- **`external`** — translates `RowSearchParams` into a `QueryJson` and routes through the integration layer via `makeExternalQuery`.

The `RowSearchParams` type:

```ts
interface RowSearchParams {
  tableId: string
  viewId?: string
  query?: SearchFilters
  sort?: string
  sortOrder?: SortOrder
  sortType?: SortType
  limit?: number
  bookmark?: string    // cursor for keyset pagination (internal)
  paginate?: boolean
  fields?: string[]    // column projection
  countRows?: boolean  // include total count
}
```

`SearchFilters` supports nested `$and` / `$or` trees and operator types: `equal`, `notEqual`, `empty`, `notEmpty`, `fuzzy`, `string`, `range`, `oneOf`, `notOneOf`, `contains`, `notContains`, `containsAny`, `allOr`.

### Link Rows (Relationships)

Internal relationship fields (`FieldType.LINK`) are backed by `LinkDocument` records. `outputProcessing` calls `linkRows.attachFullLinkedDocs` to resolve the linked row IDs to full row objects. On write, `LinkController` creates or removes `LinkDocument` entries to maintain the bidirectional index.

## Table SDK (`sdk/workspace/tables/`)

### Core Operations

```ts
getTable(tableId: string): Promise<Table>
getAllTables(): Promise<Table[]>
saveTable(table: Table): Promise<Table>
deleteTable(tableId: string): Promise<void>
```

`processTable` enriches a raw `Table` document before returning it to the caller:

- For external tables, ensures each field has a `name` property (fills from the key if missing).
- For tables with ViewV2 definitions, calls `ensureQueryUISet` to normalise the view's `queryUI` field.

### Schema Migration

When a column is renamed (`TableRequest._rename`), `saveTable` propagates the rename to all existing rows and updates link documents that reference the old column name. The pending rename is tracked in `Table.pendingColumnRenames` and applied atomically.

When a table is deleted, all linked `LinkDocument` records referencing it are removed, and all automations that reference the table are invalidated.

### Import / Export

Tables support bulk row import via `POST /api/tables/:tableId/import` and CSV-to-JSON conversion via `POST /api/tables/csv/validate`. The `csv` module from `@budibase/backend-core` parses CSV content into an array of row objects with schema inference.

## View Engine (`sdk/workspace/views/`)

Views come in two versions:

- **`View` (v1)**: MapReduce views stored in CouchDB design documents. Support grouping and calculation via `map`/`reduce` functions.
- **`ViewV2`**: Stored as sub-documents of the parent `Table` document. Support column projection, static filters, aggregations (`SUM`, `AVG`, `MIN`, `MAX`, `COUNT`), and column-level read-only flags.

`ViewV2` search is routed through the same `search` function as table search, with the view's filters merged into the `RowSearchParams.query`.

Calculation views aggregate over all rows (not pages), so they are executed as full-table scans with grouping on the designated column. `canGroupBySchema` in `packages/types` determines which field types support grouping.

## Row Actions (`sdk/workspace/rowActions/`)

Row actions are user-defined buttons that appear in table grids and trigger automations. They are stored as `RowAction` documents on the `Table`. Each `RowAction` carries:

- `name` — display label.
- `automationId` — the automation to trigger.
- `allowedSources` — the views/contexts where the button is visible.
- `permissions` — the roles allowed to invoke the action.

The `triggerRowActionAuthorised` middleware validates that the requesting user's role is in the action's permission list before allowing the trigger.

## Concurrency Model

Row operations in the main server run on Node.js's single-threaded event loop. Database I/O is async (CouchDB via `nano`; Redis via `ioredis`). Datasource queries run in a worker thread pool via Node.js `worker_threads`. The automation queue processes jobs in worker threads as well, keeping CPU-bound automation steps off the main event loop.

CouchDB document conflicts (arising from concurrent edits to the same `_id`) are surfaced as `409 Conflict` HTTP errors. The server does not implement automatic retry on conflict; callers must re-fetch and re-apply.
