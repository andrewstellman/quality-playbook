# Shared Libraries — packages/shared-core, packages/string-templates, packages/bbui, packages/frontend-core

## Overview

Four packages provide shared functionality consumed across multiple services and UI bundles. They have no runtime dependency on either `packages/server` or `packages/worker`, making them safe to import from both Node.js and browser contexts.

---

## packages/shared-core

The cross-environment utility library. Imported by `packages/server`, `packages/worker`, `packages/builder`, `packages/client`, and `packages/backend-core`.

### Exports

```ts
export * from "./constants"
export * as dataFilters from "./filters"
export * as helpers from "./helpers"
export * as utils from "./utils"
export * as sdk from "./sdk"
export * from "./table"
export * from "./themes"
export * as automations from "./automations"
export * from "./ids"
export * from "./login"
export * from "./helpers/rowsHelper"
export * from "./translations"
```

### Key Modules

**`dataFilters` (filters.ts)** — functions for building and evaluating `SearchFilters`:

- `getValidOperatorsForType(fieldType)` — returns the set of `SearchFilterOperator` values applicable to a given `FieldType`.
- `buildQuery(filter)` — normalises a `UISearchFilter` or `LegacyFilter[]` into a canonical `SearchFilters` object.
- `runQuery(rows, filters)` — client-side in-memory filter evaluation (used in the builder preview and in `ViewFetch`).
- `processSearchFilters(filters)` — resolves template bindings within filter values.

**`helpers`** — includes:

- `schema` — column-name encoding/decoding for non-ASCII field names (`encodeNonAscii`, `decodeNonAscii`).
- `roles` — role ID manipulation and `BUILTIN_ROLE_IDS`.
- `views` — `isCalculationView`, `extractViewFields`.
- `retry(fn, opts)` — exponential-backoff retry with configurable attempts and delay.
- `normalizeForComparison(name)` — lowercase-trim used for duplicate-name checks.

**`automations`** — re-exports trigger and action step definitions so both server and builder reference the same schema without a runtime dependency on the server.

**`ids`** — `newid()` generates short URL-safe random IDs (used for document IDs and session IDs).

**`utils`** — `Duration` class with `fromMs`, `fromSeconds`, `fromMinutes`, `fromDays` and `toMs`, `toSeconds` converters, used throughout the queue and session configuration.

---

## packages/string-templates

The template engine. Processes `{{ binding }}` and `{{ js "..." }}` expressions in row values, automation inputs, screen component props, and query parameters.

### Design

`string-templates` is environment-agnostic: it works in both Node.js (server, automation thread) and the browser (builder, client runtime). It exposes a `setJSRunner` hook so callers can plug in their own JavaScript evaluation strategy:

- In the browser: uses a safe in-browser VM shim (`@budibase/vm-browserify`).
- In the server automation thread: uses `isolated-vm` via the hook set in `packages/server/src/jsRunner/index.ts`.

### Public API

```ts
// Process an object's string values recursively
processObject(obj: object, context: object, opts?: ProcessOptions): Promise<object>

// Synchronous variant (no async helpers)
processObjectSync(obj: object, context: object, opts?: ProcessOptions): object

// Process a single string
processString(template: string, context: object, opts?: ProcessOptions): Promise<string>

// Synchronous variant
processStringSync(template: string, context: object, opts?: ProcessOptions): string

// Check if a string contains any HBS expressions
isValid(template: string): boolean

// Find all HBS blocks in a string
findHBSBlocks(template: string): string[]
```

`ProcessOptions`:

```ts
interface ProcessOptions {
  noHelpers?: boolean      // disable built-in helper functions
  cacheTemplates?: boolean // cache compiled Handlebars templates
  noEscaping?: boolean     // skip HTML entity escaping
  escapeNewlines?: boolean // escape \n for JSON embedding
  noFinalise?: boolean     // skip post-processing pass
  noThrow?: boolean        // suppress errors, return empty string on failure
}
```

### Handlebars Helpers

`string-templates` extends Handlebars with a large set of built-in helpers registered in `src/helpers/`. Categories include: math, array, object, string, date, URL, comparison, logical, number formatting. The `manifest.json` lists all helpers for the builder to display in the binding panel. The `helpersToRemoveForJs` list excludes a subset of helpers when evaluating `{{ js ... }}` blocks (where full Node.js is available).

### JavaScript Execution (`{{ js "..." }}`)

JS bindings embed base64-encoded JavaScript inside a `{{ js "..." }}` Handlebars expression. The template engine decodes and executes the code via the registered `jsRunner`. Outputs from JS blocks are merged back into the template output. The `UserScriptError` class wraps exceptions thrown by user JS so error messages can be surfaced to the automation log or builder without leaking internal stack frames.

---

## packages/bbui

The Budibase design system and component library for Svelte applications. Used by `packages/builder`. Not imported by `packages/client` (which uses components compiled into apps).

### Component Categories

All components are exported from `src/index.ts`:

- **Form inputs**: `Input`, `TextArea`, `Select`, `Combobox`, `Multiselect`, `RadioGroup`, `Toggle`, `Checkbox`, `DatePicker`, `DateRangePicker`, `Slider`, `Stepper`, `ColorPicker`, `Dropzone`, `RichTextField`, `Search`.
- **Layout**: `Layout`, `Divider`, `Accordion`, `DetailSummary`, `Tabs`, `Switcher`.
- **Feedback**: `Modal`, `Drawer`, `Popover`, `Tooltip`, `InlineAlert`, `Banner`, `Notification`, `Badge`, `StatusLight`.
- **Navigation**: `Menu`, `ActionMenu`, `Link`, `Pagination`, `TreeView`.
- **Data display**: `Table`, `Tags`, `Typography`, `List`, `ProgressBar`, `ProgressCircle`, `Markdown`.
- **Actions**: `Button`, `ButtonGroup`, `ActionButton`, `ActionGroup`, `Icon`, `IconPicker`, `Avatar`.

### Theming

`bbui.css` defines the full set of CSS custom properties that drive the design system: `--spectrum-*` variables for colour, spacing, typography, and radius. Components reference these variables rather than hardcoded values, so the entire UI can be re-themed by overriding the properties at the `:root` level.

---

## packages/frontend-core

Shared TypeScript utilities and Svelte stores for `packages/builder` and `packages/client`.

### API Client

`createAPIClient(opts)` returns an `APIClient` instance — a typed facade over `fetch` that:
- Prepends the base URL to all requests.
- Attaches the auth cookie and CSRF token automatically.
- Normalises 4xx/5xx responses into thrown `Error` instances with `.status` and `.message`.
- Handles file-upload requests (`multipart/form-data`).

The `APIClient` type is a union of method interfaces for each resource (rows, tables, queries, etc.) generated from the route handlers.

### Data Fetch Layer

`fetchData(opts)` is the factory for all paginated data-provider instances used in both the builder's data panel and the client's data-provider components. It accepts a `DataFetchDatasource` discriminated union and returns the appropriate `BaseDataFetch` subclass.

The `DataFetchType` enum lists all source types: `table`, `view`, `viewV2`, `query`, `field`, `user`, `groupUser`, `custom`, `nestedProvider`, `jsonArray`, `queryArray`, `relationship`.

### Shared Stores

`packages/frontend-core/src/stores/` provides stores used in the builder portal: navigation breadcrumbs, notification queue, and form-state utilities.
