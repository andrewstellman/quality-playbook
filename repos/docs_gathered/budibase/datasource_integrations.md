# Datasource Integrations — packages/server/src/integrations

## Overview

The integration layer provides a uniform interface for connecting Budibase apps to external data systems and running queries against them. Every integration is a TypeScript class that implements `IntegrationBase` (read-only queries) or `DatasourcePlus` (full read/write with schema introspection). Integrations self-describe via a static `schema` object of type `Integration`, which the builder reads to render the configuration form.

## Built-in Integrations

Declared in `packages/server/src/integrations/index.ts` and keyed by `SourceName`:

| `SourceName` key | Class | Type |
|-----------------|-------|------|
| `POSTGRES` | `PostgresIntegration` | SQL (Relational) |
| `MYSQL` | `MySQLIntegration` | SQL (Relational) |
| `SQL_SERVER` | `MicrosoftSqlServerIntegration` | SQL (Relational) |
| `ORACLE` | `OracleIntegration` | SQL (Relational) |
| `SNOWFLAKE` | `SnowflakeIntegration` | SQL (Relational) |
| `MONGODB` | `MongoDBIntegration` | Non-SQL |
| `ELASTICSEARCH` | `ElasticSearchIntegration` | Non-SQL |
| `COUCHDB` | `CouchDBIntegration` | Non-SQL |
| `DYNAMODB` | `DynamoDBIntegration` | Non-SQL |
| `FIRESTORE` | `FirestoreIntegration` | Non-SQL |
| `REDIS` | `RedisIntegration` | Non-SQL |
| `S3` | `S3Integration` | Object store |
| `REST` | `RestIntegration` | HTTP |
| `GOOGLE_SHEETS` | `GoogleSheetsIntegration` | Spreadsheet |
| `AIRTABLE` | deprecated | — |
| `ARANGODB` | deprecated | — |

## Interface Contracts

### `IntegrationBase`

Minimum contract for any integration:

```ts
interface IntegrationBase {
  query(json: QueryJson | EnrichedQueryJson): Promise<any>
  testConnection?(): Promise<ConnectionInfo>
  disconnect?(): Promise<void>
}
```

### `DatasourcePlus`

Extended contract for SQL and schema-aware integrations:

```ts
interface DatasourcePlus extends IntegrationBase {
  query(json: EnrichedQueryJson): Promise<DatasourcePlusQueryResponse>
  buildSchema(
    datasourceId: string,
    entities: Record<string, Table>
  ): Promise<Schema>
  getRelationships?(
    config: DatasourceRelationshipConfig
  ): Promise<DatasourceRelationshipType[]>
}
```

SQL integrations that implement `DatasourcePlus` set `plus: true` in their `schema` and are eligible for table introspection — the builder can import an existing database schema and present it as Budibase tables.

### `Integration` Schema Object

Each integration exports a `schema: Integration` describing:

- `docs` — URL to driver documentation.
- `friendlyName` — display name in the builder.
- `type` — `"Relational"`, `"Non-relational"`, etc.
- `description` — short description.
- `features` — a `Record<DatasourceFeature, boolean>` advertising optional capabilities such as `CONNECTION_CHECKING`, `FETCH_TABLE_NAMES`, `EXPORT_SCHEMA`.
- `datasource` — a `Record<string, IntegrationField>` describing each config option (type, display name, required flag, default).
- `query` — a `Record<QueryType, ...]>` describing the query types supported (e.g. `READ`, `CREATE`, `UPDATE`, `DELETE`, `BULK_CREATE`).

## Query Execution Pipeline

All external queries flow through `packages/server/src/integrations/base/query.ts`:

```
makeExternalQuery(json: QueryJson | EnrichedQueryJson)
  → enrichQueryJson(json)           // resolves table + datasource from DB
  → sdk.datasources.enrich(ds)     // substitutes env-variable placeholders
  → getIntegration(source)         // looks up class in INTEGRATIONS map
  → new Integration(config)
  → integration.query(json)
```

`QueryJson` carries the operation type (`READ`, `CREATE`, `UPDATE`, `DELETE`, `BULK_CREATE`, `BULK_UPSERT`, `COUNT`, `AGGREGATE`), table reference, filters (`SearchFilters`), sort, pagination, and an optional `relationship[]` list for JOIN-equivalent fetches.

`EnrichedQueryJson` extends `QueryJson` with the resolved `Datasource` document and `Table` entity already attached, so the integration class does not need to re-fetch them.

## SQL Abstraction Layer

SQL integrations do not build SQL strings directly. They call into the shared `Sql` builder class (`packages/backend-core/src/sql/sql.ts`), which uses [Knex](https://knexjs.org/) as its underlying query builder. `Sql` translates `QueryJson` → Knex chain → parameterised SQL + bindings. This ensures consistent behaviour across SQL dialects.

Key `Sql` behaviours:

- Row limit applied from `SQL_MAX_ROWS` (default 5 000).
- Related-row sub-queries limited by `SQL_MAX_RELATED_ROWS` (default 500).
- Filters expressed as `SearchFilters` (nested `$and` / `$or` trees, operator enums) are recursively translated to Knex `where` clauses.
- The `COUNT_FIELD_NAME` (`__bb_total`) column is appended to `COUNT` / `AGGREGATE` queries so pagination can report total row counts.

## REST Integration

The REST integration (`integrations/rest.ts`) is the most flexible built-in. It supports:

- HTTP methods: GET, POST, PUT, PATCH, DELETE.
- Auth types: `basic`, `bearer`, `oauth2`, `apiKey` (header or query-string).
- Body types: JSON, form data, XML, raw, encoded.
- Pagination config: page-number, cursor, or link-header strategies.
- Dynamic variables: values resolved from previous query responses and cached in Redis.
- Response parsing: JSON, XML, binary (returned as attachments).

OAuth2 tokens for REST datasources are stored in CouchDB as `OAuth2Config` documents and refreshed automatically when the token expires.

## Plugin Integrations

Third-party datasource plugins are loaded from `PLUGINS_DIR` (default `/plugins`) at query time via `getDatasourcePlugin`. A plugin is a directory containing a bundled JS file; its exported `schema` and class constructor are registered into the `INTEGRATIONS` and `DEFINITIONS` maps at runtime, making them indistinguishable from built-ins during query execution.

## Schema Mapping

When a SQL datasource is introspected, the integration's `buildSchema` method returns a `Schema` containing a `Record<string, Table>` of Budibase `Table` objects. SQL column types are mapped to Budibase `FieldType` values in `integrations/utils/utils.ts` via lookup maps (`SQL_NUMBER_TYPE_MAP`, `SQL_DATE_TYPE_MAP`, `SQL_STRING_TYPE_MAP`, `SQL_BOOLEAN_TYPE_MAP`). Unknown types default to `FieldType.STRING`.

## Environment Variables in Datasource Config

Datasource config values may reference environment variables using the prefix `env.VARIABLE_NAME`. Before a query is executed, `sdk.datasources.enrich` replaces these references with the actual values stored in the `EnvironmentVariables` global document, so plaintext secrets never need to be stored in the datasource config document itself.
