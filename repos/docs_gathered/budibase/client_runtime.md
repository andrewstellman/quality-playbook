# Client Runtime — packages/client

## Overview

`packages/client` is the browser bundle that renders published Budibase applications. It reads a JSON screen definition produced by the builder and mounts a live, interactive single-page application. It is also loaded inside the builder's iframe for live preview. The entry point is `src/index.ts`; the root component is `src/components/ClientApp.svelte`.

## Initialisation

`src/index.ts` exports a set of functions that the hosting page calls to bootstrap the runtime:

```ts
// Pseudocode — reflects the actual public surface
initialise({ screens, theme, navigation, ... })   // first call: provides the app definition
updateState(key, value)                            // mutate in-app state from outside
notifyLoaded()                                    // signal that assets are ready
```

On first load, `initialise` populates the stores, sets up the WebSocket connection to the server (for real-time data updates), and mounts `ClientApp.svelte` into the DOM.

## Component Hierarchy

```
ClientApp.svelte
  ├── CustomThemeWrapper.svelte   — applies CSS custom properties from the app theme
  ├── Router.svelte               — client-side routing between screens
  │     └── Screen.svelte         — renders the active screen's component tree
  │           └── Component.svelte — recursive component renderer
  ├── RecaptchaV2.svelte          — optional reCAPTCHA gate
  ├── MaintenanceScreen.svelte    — shown when the app is updating
  └── UpdatingApp.svelte          — shown during a live deploy
```

`Component.svelte` reads the component's `_component` type from the screen JSON, looks it up in the component library, and mounts the correct Svelte component with the resolved props. Component libraries ship as separately bundled JS files; custom plugin components are loaded from object storage URLs at runtime via dynamic `import()`.

`Block.svelte` and `BlockComponent.svelte` support compound "block" components — pre-wired multi-component assemblies (e.g., a table with a detail panel) that expose a simplified configuration surface.

## Store Architecture

The client runtime manages a distinct set of stores from the builder. All stores are under `src/stores/`:

| Store | Purpose |
|-------|---------|
| `appStore` | App metadata: name, version, theme, features |
| `authStore` | Current authenticated user identity and role |
| `routeStore` | Current route, navigation history |
| `screenStore` | Screen definitions and the currently-active screen |
| `stateStore` | In-app key/value state (persisted via `localStorage` or session) |
| `componentStore` | Component definitions from the library manifest |
| `blockStore` | Block component registrations |
| `builderStore` | Builder communication channel (active when running in preview iframe) |
| `dndStore` | Drag-and-drop state for grid-layout components |
| `hoverStore` | Currently-hovered component (used in preview to show selection handles) |
| `notificationStore` | Toast notification queue |
| `eventStore` | Custom event listeners registered by component actions |
| `environmentStore` | Environment-variable bindings exposed to the client |

## Data Fetching Layer

The client does not call the server API directly from components. Instead, components bind to a *data provider* context. Data providers are powered by `DataFetch` instances from `@budibase/frontend-core`:

- `TableFetch` — paginates rows from an internal table.
- `ViewFetch` / `ViewV2Fetch` — rows from a saved view.
- `QueryFetch` — result of a saved query.
- `RelationshipFetch` — rows related to a given row via a link field.
- `UserFetch` / `GroupUserFetch` — users from the global user store.
- `CustomFetch` — arbitrary in-memory data supplied by a block.
- `JSONArrayFetch` — local JSON array binding.

Each fetch class extends the abstract `BaseDataFetch`, which owns a Svelte `derived` store exposing `{ rows, schema, loading, hasNextPage, hasPrevPage, error, ... }`. Components subscribe to this store reactively; pagination is driven by `nextPage()` / `prevPage()` methods.

## Action System

User interactions (button clicks, form submissions, etc.) are mapped to *actions* defined as JSON arrays in the screen definition. The action system (`src/actions.js`) dispatches these sequences:

- Navigate to screen / external URL.
- Save / delete / duplicate a row.
- Execute a query.
- Trigger an automation.
- Update in-app state (`stateStore`).
- Open / close a modal or side panel.
- Scroll to component.
- Export data.
- Log out.

Actions run sequentially; each action receives the outputs of the previous one through a shared context object.

## Binding Resolution

At render time, component props that contain `{{ ... }}` template strings are resolved using `processObjectSync` from `@budibase/string-templates`. The binding context includes: the current user, in-app state, environment variables, URL parameters, query parameters, and the row/rows exposed by ancestor data-provider components.

## Builder Communication (Preview Mode)

When running inside the builder preview iframe, the `builderStore` listens for `postMessage` events from the parent frame. The builder can send:

- A new screen definition (triggers a re-render without a page reload).
- A selected-component ID (the client highlights the component).
- Theme changes.
- Device-size changes.

The client sends back component-selection events when the user clicks a component in preview mode.

## WebSocket Integration

`src/websocket.js` establishes a Socket.IO connection to `/socket/client` on the server. The server pushes real-time notifications when the app is re-published. On receipt, the client triggers `UpdatingApp.svelte` and reloads the screen definitions without a hard page refresh.

## Plugin Support

Custom component plugins are loaded at runtime. The `componentStore` holds a `customComponents` list of component type names whose implementations are loaded from object-storage URLs (populated by the server from `PLUGINS_DIR`). The client loads the plugin bundle via a dynamic `import()` call and registers the Svelte component under its declared type name. The Svelte runtime is exposed globally (`window.__budibase_svelte`) so that plugins compiled against a different Svelte version can interoperate.
