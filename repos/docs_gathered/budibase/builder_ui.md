# Builder UI — packages/builder

## Overview

`packages/builder` is the Svelte single-page application that Budibase engineers and low-code developers use to build, configure, and publish applications. It runs entirely in the browser and communicates with `packages/server` over REST and WebSocket. The entry point is `src/main.js`; routing is file-system based (SvelteKit-style pages under `src/pages/`).

## Page Structure

```
src/pages/
  builder/
    auth/          ← login, forgot password, OIDC/Google SSO buttons
    workspaces.svelte   ← workspace (application) list
    workspace/
      [application]/
        home/           ← app home with metrics and controls
        design/         ← screen and component editor
        data/           ← table, view, query, datasource editors
        automation/     ← automation editor
        settings/       ← app settings, embed config
```

The URL segment `[application]` binds to the current workspace's `appId`. The layout hierarchy at `workspace/_layout.svelte` mounts the navigation sidebar and the top bar, then delegates to the active panel.

## Store Architecture

All shared state is managed through Svelte stores defined in `src/stores/`. The stores are split into two groups:

### Builder stores (`src/stores/builder/`)

These govern in-context editing of a single open application:

| Store | Responsibility |
|-------|---------------|
| `appStore` | Current workspace metadata (name, version, features, theme) |
| `componentStore` | Component definitions, selected component, clipboard |
| `screenStore` | Screen list, selected screen |
| `automationStore` | Automation list, selected automation, history/undo |
| `datasources` | Datasource list and selected datasource |
| `tables` | Table metadata for the open app |
| `views` / `viewsV2` | View definitions |
| `queries` | Saved query definitions |
| `roles` | Role list |
| `permissions` | Permission assignments |
| `builderStore` | UI meta-state: preview mode, device size, selected panel |
| `previewStore` | Live-preview session state |
| `websocket` | Builder WebSocket connection (broadcasts resource locks, schema changes) |
| `workspaceConnections` | Multi-workspace connection state |

### Portal stores (`src/stores/portal/`)

These span across all applications in a tenant and cover admin/global concerns:

| Store | Responsibility |
|-------|---------------|
| `apps` | All workspace records |
| `auth` | Current user identity |
| `users` / `groups` | User management |
| `plugins` | Plugin catalog |
| `licensing` | License and feature-flag state |
| `ai` / `aiConfigs` | AI configuration |
| `agents` | AI agent definitions |
| `knowledgeBases` / `vectorDbs` | RAG knowledge bases |
| `organisation` | Global org settings |
| `email` | SMTP configuration |
| `oidc` | OIDC SSO configuration |
| `features` | Feature flags |

All stores extend `BudiStore` (in `src/stores/BudiStore.ts`), which wraps a Svelte writable store and provides a consistent `set` / `update` / `subscribe` surface plus optional history tracking.

## Component Editor

The design panel (`src/components/design/`) is built around a component tree. The `componentStore` holds a `Record<string, ComponentDefinition>` of all available component types (loaded from the server's component library manifest). When a component is selected, its settings are rendered from its JSON schema into the settings panel.

Component operations supported by `componentStore`:

- Add a component at a given parent/index position.
- Duplicate (with unique ID regeneration via `makeComponentUnique`).
- Move (drag-and-drop within the component tree).
- Paste from clipboard.
- Apply conditional display rules (`ComponentCondition[]`).

The `history` store wraps automation and component mutations to provide multi-level undo/redo.

## Data Binding System

`src/dataBinding.js` is the central binding helper. It exposes `getSchemaForDatasource`, which resolves a binding context from any data source type (table, view, query, user, environment variables). Template bindings use Handlebars syntax `{{ value }}` or `{{ js "..." }}` for JavaScript blocks; the `@budibase/string-templates` package processes them at runtime.

`buildFormSchema` constructs the expected field schema for a form component from its bound table, enabling the builder to render typed field inputs.

## API Client

`src/api.ts` creates an `APIClient` instance (from `@budibase/frontend-core`) pre-configured with the builder's base URL. All store actions that need server data call methods on this client rather than using `fetch` directly. The client handles request serialisation, error normalisation, and authentication headers.

## Preview Mode

When the builder preview is active (`previewStore.startPreview()`), an iframe loads the `packages/client` bundle. The builder communicates with the iframe via `postMessage`, passing the current screen definition JSON. The client runtime renders a live preview of the app without requiring a full publish cycle.

## Analytics

The builder integrates analytics via `src/analytics/index.js`. Analytics calls are made at key points (component added, app published, datasource connected). The analytics module checks the `ENABLE_ANALYTICS` environment variable and respects user opt-out preferences from the portal store.

## Build and Packaging

The builder is bundled with Vite. It is served as a static asset by `packages/server` from the `/builder` path. In development, the Vite dev server runs separately and proxies API calls to the server process. The production build outputs to `dist/` and is embedded in the server's Docker image at build time.
