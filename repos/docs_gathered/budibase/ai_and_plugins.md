# AI Features and Plugin System — packages/server/src/sdk/workspace/ai, packages/server/src/sdk/plugins

## Overview

Budibase includes a first-party AI layer (chat applications, agents, knowledge bases, RAG ingestion) and a plugin system (custom components, datasources, automations). Both are designed as extension points on top of the core platform: they use the same authentication, queue, object-store, and CouchDB infrastructure as the rest of the server.

---

## AI Features

### LLM Provider Model

AI calls in Budibase are abstracted through a configurable provider layer in `sdk/workspace/ai/llm/`. The factory function:

```ts
async function createLLM(
  configId: string,
  sessionId?: string,
  span?: tracer.Span,
  agentId?: string
): Promise<LLMResponse>
```

reads an `AIConfig` document (stored in the global CouchDB database, `ConfigType.AI`) and returns a client:

- **Budibase AI (cloud)**: routes through the proprietary `BBAI` service (`createBBAIClient`). Quota enforcement applies via `quotas.throwIfBudibaseAICreditsExceeded()`.
- **Self-hosted / third-party**: routes through a LiteLLM proxy gateway (`createLiteLLMOpenAI`). LiteLLM is configured via `litellm_config.yaml` and serves as a unified OpenAI-compatible endpoint in front of any LLM provider (OpenAI, Anthropic, Azure OpenAI, Bedrock, Ollama, etc.).

LiteLLM readiness is checked at server startup: the server polls `LITELLM_MASTER_KEY`-authenticated health endpoints until they respond or `LITELLM_READINESS_TIMEOUT_MS` (default 30 000 ms) elapses.

### AI Configuration

`AIConfig` documents hold:

```ts
interface AIConfig {
  provider: string        // "OPENAI", "ANTHROPIC", "BUDIBASE_AI", etc.
  model: string
  apiKey?: string         // stored encrypted
  baseUrl?: string        // for self-hosted providers
  reasoningEffort?: string
}
```

Multiple AI configs can be stored; each automation AI step and agent references a config by ID.

### Agents

AI agents are stored as `Agent` documents in the global CouchDB database (`DocumentType.AGENT`). Each agent definition carries:

- `name` — unique within a tenant (duplicate-name check enforced at save time).
- `configId` — reference to an `AIConfig`.
- `tools` — list of tool descriptors the agent may invoke.
- `discordIntegration` — optional bot token and channel ID (secret fields stored AES-encrypted).
- `slackIntegration` — optional webhook URL (stored encrypted).

The `encodeSecret` / `decodeSecret` helpers use AES encryption with `SECRET_ENCODING_PREFIX` to distinguish encrypted values from plaintext and avoid double-encryption.

Agent logs are indexed asynchronously via `queue.JobQueue.AGENT_LOG_INDEXING`. Log records are queryable via the builder's agent log panel.

### RAG / Knowledge Bases

The Retrieval-Augmented Generation (RAG) pipeline allows AI agents to answer questions grounded in uploaded documents.

**File ingestion pipeline:**

1. A file is uploaded to the `attachments` object-store bucket.
2. A `KnowledgeBase` document is created in CouchDB referencing the file.
3. A `RagIngestionJob` is enqueued to `queue.JobQueue.RAG_INGESTION`.
4. The queue processor calls `ingestKnowledgeBaseFile`, which:
   - Downloads the file from object storage.
   - Splits the content into chunks.
   - Generates embeddings via the configured LLM provider.
   - Stores the embeddings in a vector database.

The queue is configured with up to 5 retry attempts using exponential backoff (10-second base delay, 10-minute timeout per job), and 2 concurrent workers.

**Vector databases** are stored as `VectorDb` global documents referencing an external vector store (Pinecone, pgvector, etc.). The `vectorDb` SDK module (`sdk/workspace/ai/vectorDb/`) manages create/read/delete operations.

`KnowledgeBase` status transitions: `pending → processing → ready | error`. The `KnowledgeBaseFileStatus` enum tracks per-file state for multi-file knowledge bases.

### Chat Applications

Chat apps (`ChatApp` global documents) allow builders to create LLM-powered conversational interfaces deployed as standalone public URLs. Chat conversations are tracked as `ChatConversation` workspace documents. Chat identity links (`ChatIdentityLink`) associate anonymous session IDs with authenticated user IDs when a user logs in during a chat session.

### AI Automation Steps

The automation engine exposes several AI-powered step types:

| Step ID | Function |
|---------|---------|
| `CLASSIFY_CONTENT` | Classifies input text into provided categories |
| `PROMPT_LLM` | General-purpose LLM prompt with structured output |
| `TRANSLATE` | Translates text between languages |
| `SUMMARISE` | Summarises long-form text |
| `GENERATE_TEXT` | Generates text from a prompt and content type |
| `EXTRACT_FILE_DATA` | Extracts structured data from PDF/image files |

All AI steps use `createLLM(configId)` and share the same retry and timeout behaviour as other automation steps.

---

## Plugin System

### Plugin Types

`PluginType` defines three extension categories:

| Type | Description |
|------|-------------|
| `COMPONENT` | Custom Svelte component rendered in deployed apps |
| `DATASOURCE` | Custom integration (implements `IntegrationBase`) |
| `AUTOMATION` | Custom automation action step |

### Plugin Sources

Plugins can be installed from four sources:

| Source | Mechanism |
|--------|-----------|
| `FILE` | Uploaded `.tar.gz` bundle via the builder UI |
| `NPM` | Package name resolved via `npm pack` |
| `GITHUB` | GitHub repository URL; downloaded as a `.tar.gz` archive |
| `URL` | Direct download URL |

### Installation Flow

Regardless of source, all plugins go through `sdk.plugins.processUploaded(file, source)`:

1. The archive is extracted to a temporary directory.
2. The `package.json` is read to extract name, version, and description.
3. An SHA-256 hash of the bundle content is computed.
4. The bundle is uploaded to the `plugins` object-store bucket at path `<name>/<version>/plugin.min.js`.
5. An icon file (if present) is uploaded alongside.
6. A `Plugin` document is persisted to the global CouchDB database.
7. All connected builder sockets are notified via `clientAppSocket`.

### Runtime Loading

- **Component plugins** are loaded by the client runtime at app launch from a signed object-store URL. The URL is populated on the `Plugin` document as `jsUrl` when the plugin is read.
- **Datasource plugins** are loaded by the server at query time via `getDatasourcePlugin`, which reads the bundle from the `PLUGINS_DIR` filesystem path (populated by mounting the object-store bucket or a persistent volume).
- **Automation plugins** are loaded by the automation thread in the same manner as datasource plugins.

### Update Checks

`sdk/plugins/update.ts` provides `checkPluginUpdates` and `applyPluginUpdates`. For GitHub-sourced plugins, the update checker queries the GitHub API for the latest release tag and compares it against the installed version. If a newer version is found, `applyPluginUpdates` re-runs the installation flow with the new archive URL.
