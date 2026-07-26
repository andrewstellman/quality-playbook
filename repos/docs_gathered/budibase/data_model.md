# Data Model — packages/types, packages/backend-core/src/db

## Overview

Budibase's data model is defined in the `packages/types` package as TypeScript interfaces and enums. All persistent documents extend the base `Document` interface (containing `_id`, `_rev`, and standard CouchDB fields). There are two categories of database: the **global database** (one per tenant) and **workspace databases** (one per application, split into a dev and a production variant).

## Database Layout

| Database name pattern | Contents |
|----------------------|---------|
| `global-db` (or `<tenantId>_global-db`) | Users, groups, configs, API keys, activity logs, templates, plugins, AI configs, agent definitions |
| `<appId>` (dev) | Tables, rows, screens, automations, datasources, queries, roles, links |
| `<productionAppId>` | Published snapshot of the dev workspace |
| `bb-activity-logs` | Append-only activity log documents |

The `StaticDatabases` constant in `backend-core` names the well-known databases: `GLOBAL`, `ACTIVITY_LOGS`, `SCIM_LOGS`, `PLATFORM_INFO`.

## Document ID Conventions

CouchDB document IDs encode the document type and a separator (`_`), making prefix queries efficient. The `DocumentType` and `VirtualDocumentType` enums (in `packages/types`) define the prefixes:

| Prefix | Document type |
|--------|--------------|
| `ta_` | Table |
| `ro_` | Row |
| `sc_` | Screen |
| `au_` | Automation |
| `at_` | Automation log |
| `ds_` | Datasource |
| `q_` | Query |
| `li_` | Link (relationship) |
| `role_` | Role |
| `wh_` | Webhook |
| `la_` | Layout |
| `config_` | Configuration |
| `plugin_` | Plugin |

Helper functions like `generateTableID`, `generateRowID`, `generateDatasourceID`, etc. construct IDs by concatenating the prefix, a separator, and a `newid()` value (a short URL-safe random string from `@budibase/shared-core`).

## Core Document Types

### `Workspace` (app metadata)

Stored in the workspace DB as a singleton. Key fields:

```ts
interface Workspace extends Document {
  appId: string          // production app ID
  name: string
  url: string | undefined
  version: string
  componentLibraries: string[]
  tenantId: string
  status: string         // "development" | "published"
  theme?: Theme
  customTheme?: AppCustomTheme
  features?: WorkspaceFeatures
  automations?: AutomationSettings
  usedPlugins?: Plugin[]
  snippets?: Snippet[]
  scripts?: AppScript[]
  resourcesPublishedAt?: Record<string, string>
}
```

### `Table`

```ts
interface Table extends Document {
  type: "table"
  sourceType: TableSourceType   // "internal" | "external"
  sourceId: string              // INTERNAL_TABLE_SOURCE_ID or datasource ID
  name: string
  schema: TableSchema           // Record<string, FieldSchema>
  primary?: string[]            // primary key columns
  primaryDisplay?: string       // column shown in relationship labels
  views?: Record<string, View | ViewV2>
  sql?: boolean
  rowHeight?: number
}
```

### `FieldType` Enum

Fields in a table schema carry a `FieldType` that governs storage, UI rendering, and validation:

`STRING`, `LONGFORM`, `OPTIONS`, `NUMBER`, `BOOLEAN`, `ARRAY`, `DATETIME`, `BIGINT`, `LINK`, `FORMULA`, `AUTO`, `JSON`, `INTERNAL`, `BARCODEQR`, `SIGNATURE_SINGLE`, `BB_REFERENCE`, `BB_REFERENCE_SINGLE`, `ATTACHMENTS`, `ATTACHMENT_SINGLE`, `AI`.

The `LINK` type persists separate `LinkDocument` records, described below.

### `Row`

```ts
interface Row extends Document {
  type?: string
  tableId?: string
  _viewId?: string
  [key: string]: any   // field values keyed by column name
}
```

Internal rows live in the workspace CouchDB database. External rows are read/written through the integration layer and are not stored in CouchDB.

### `LinkDocument`

Relationship links between internal rows are stored as `LinkDocument` records (prefix `li_`). Each `LinkDocument` encodes a bidirectional relationship: `tableId`, `rowId`, `fieldName` for each side. The `LinkController` maintains these records when rows are saved or deleted.

### `Datasource`

```ts
interface Datasource extends Document {
  type: string
  name?: string
  source: SourceName
  config?: Record<string, any>   // integration-specific config
  plus?: boolean                  // true for schema-introspection capable integrations
  isSQL?: boolean
  entities?: Record<string, Table>   // imported schema (SQL integrations)
  restTemplateId?: RestTemplateId
  usesEnvironmentVariables?: boolean
}
```

### `Query`

A saved parameterised query. Fields include `datasourceId`, `queryVerb` (the operation type), `fields` (the query body), `parameters` (named parameters with defaults), `transformer` (a JS string run over the raw result), and `schema` (the expected output schema).

### `Automation`

```ts
interface Automation extends Document {
  name: string
  definition: {
    trigger: AutomationTrigger
    steps: AutomationStep[]
  }
  appId: string
  active?: boolean
  live?: boolean
}
```

Each `AutomationStep` carries `id`, `stepId`, `type` (`ACTION` | `LOGIC` | `TRIGGER`), `name`, `inputs`, `schema.inputs`, and `schema.outputs`.

### `ViewV2`

Views V2 are stored as sub-documents under their parent `Table.views`. They carry:

- `query` — `SearchFilters` applied when fetching rows.
- `sort` — default sort column and direction.
- `schema` — a `Record<string, ViewV2ColumnEnriched>` controlling which columns are visible, their display name, and read-only status.
- `calculation` — aggregation fields supporting `SUM`, `AVG`, `MIN`, `MAX`, `COUNT`.

### Global Documents

Stored in the global DB:

| Type | Key fields |
|------|-----------|
| `User` | `email`, `roles` (Record<appId, roleId>), `builder`, `admin`, `forceResetPassword` |
| `Config` | `type` (SMTP, Google, OIDC, AI, etc.), `config` (typed per ConfigType) |
| `Plugin` | `name`, `version`, `source`, `schema`, `hash` |
| `EnvironmentVariables` | `variables: Record<string, string>` |
| `ApiKey` | userId → encrypted key mapping |

## Internal Tables

Two tables are built into every Budibase app:

- `ta_users` (`InternalTable.USER_METADATA`) — stores per-app user metadata rows synced from the global user store.
- `ta_bb_references` — internal reference rows used by `BB_REFERENCE` fields.

## SQS / SQLite Layer

For high-performance internal row search, Budibase maintains an SQLite mirror (`COUCH_DB_SQL_URL`) of internal table rows. The `sqs` SDK module (`packages/server/src/sdk/workspace/sqs/`) handles syncing CouchDB rows into the SQLite store and routing `search` calls to the SQS endpoint when available, falling back to CouchDB Mango queries.
