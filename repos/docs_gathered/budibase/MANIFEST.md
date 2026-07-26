# Budibase Documentation Manifest

| File | Description |
|------|-------------|
| `server_api.md` | The Koa HTTP application (packages/server): startup sequence, middleware pipeline, route groups, public API surface, WebSocket channels, error handling, and test conventions. |
| `builder_ui.md` | The Svelte builder single-page application (packages/builder): page structure, store architecture, component editor, data binding system, preview mode, and build packaging. |
| `client_runtime.md` | The browser client runtime (packages/client): initialisation, component hierarchy, data fetching layer, action system, binding resolution, and plugin loading. |
| `datasource_integrations.md` | The external datasource integration layer (packages/server/src/integrations): built-in connectors, interface contracts, query execution pipeline, SQL abstraction, REST integration, and plugin datasources. |
| `automation_engine.md` | The event-driven automation engine (packages/server/src/automations): triggers, queue, execution thread, built-in action steps, branching and looping, and result logging. |
| `auth_and_sessions.md` | Authentication strategies, session storage, middleware pipeline, role and permission model, CSRF protection, and multi-tenancy (packages/backend-core/src/auth, packages/worker). |
| `data_model.md` | CouchDB database layout, document ID conventions, and the full set of core document type interfaces defined in packages/types. |
| `shared_libraries.md` | The four shared packages consumed across services and UI bundles: shared-core (filters, helpers, automation definitions), string-templates (Handlebars + JS engine), bbui (Svelte design system), and frontend-core (API client, data fetch layer). |
| `worker_service.md` | The global worker Koa service (packages/worker): global and system route groups, user management, email delivery, configuration management, licensing, activity logging, and SCIM provisioning. |
| `row_and_table_engine.md` | The internal/external row and table SDK (packages/server/src/sdk/workspace/rows and tables): dispatch routing, input/output processing, search, link rows, schema migration, views, and row actions. |
| `backend_core.md` | The foundation library (packages/backend-core): context system, CouchDB wrapper, object storage, queue infrastructure, SQL builder, encryption, and distributed locking. |
| `ai_and_plugins.md` | AI features (LLM provider model, agents, RAG/knowledge bases, chat apps, AI automation steps) and the plugin system (component, datasource, and automation plugins). |
| `deployment_and_hosting.md` | Docker Compose stack, service roles, persistent volumes, monorepo build system (Lerna + Nx), Kubernetes Helm charts, cluster mode, multi-tenancy in cloud, and the CLI tool. |
