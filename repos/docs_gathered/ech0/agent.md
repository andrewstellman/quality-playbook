# Ech0 AI Agent Subsystem

## Overview

Ech0 includes a configurable AI agent subsystem that enables LLM-generated content features — such as summarizing recent posts — from within the application. The agent is implemented in `internal/agent/agent.go` and uses the [CloudWeGo Eino](https://github.com/cloudwego/eino) framework as a common interface over multiple LLM providers. Agent configuration (provider, model, API key, base URL, and system prompt) is stored in the settings database and manageable from the admin panel.

## Supported Providers

The `Generate` function dispatches to the appropriate provider SDK based on the `setting.Provider` string:

| Provider Constant | Value | Underlying SDK |
|---|---|---|
| `OpenAI` | `openai` | `cloudwego/eino-ext/components/model/openai` |
| `Anthropic` | `anthropic` | `cloudwego/eino-ext/components/model/claude` |
| `Gemini` | `gemini` | `google.golang.org/genai` + `eino-ext/components/model/gemini` |
| `Qwen` | `qwen` | `cloudwego/eino-ext/components/model/qwen` |
| `DeepSeek` | `deepseek` | `cloudwego/eino-ext/components/model/deepseek` |
| `Ollama` | `ollama` | `cloudwego/eino-ext/components/model/ollama` |
| `Custom` | `custom` | OpenAI-compatible endpoint via `eino-ext/components/model/openai` |

The `Custom` provider uses the OpenAI-compatible chat completion API, allowing any endpoint that speaks the OpenAI protocol to be used without native SDK support.

## Generate Function

```go
func Generate(
    ctx     context.Context,
    setting model.AgentSetting,
    in      []*schema.Message,
    usePrompt bool,
    temperature ...float32,
) (string, error)
```

Parameters:
- `setting` — the full agent configuration loaded from the database
- `in` — the message slice to send (chat history or single-turn prompt)
- `usePrompt` — if true, prepends `setting.Prompt` as a user-role message before the rest of `in`
- `temperature` — optional; if omitted the provider default is used

Returns the generated text content string, or an error if the provider rejects the request or configuration is incomplete.

Guards checked before provider dispatch:
- `setting.Enable` must be true
- `setting.Model` must be non-empty
- `setting.Provider` must be a known provider string
- `setting.ApiKey` must be non-empty (Ollama is the only provider that does not use API keys but still validates this field)

## Agent Settings Model

```go
type AgentSetting struct {
    Enable   bool   `json:"enable"`
    Provider string `json:"provider"`
    ApiKey   string `json:"api_key"`
    BaseURL  string `json:"base_url"`
    Model    string `json:"model"`
    Prompt   string `json:"prompt"`
}
```

Settings are stored as a JSON blob in the key-value settings table and read via `settingService.GetAgentSettings`. The `api_key` field is masked when returned to the frontend (`GetAgentInfo` vs. `GetAgentSettings`).

## Message Schema

The agent uses `github.com/cloudwego/eino/schema` types for messages:

```go
type Message struct {
    Role    Role
    Content string
}
```

Roles include `schema.User`, `schema.Assistant`, and `schema.System`. The `usePrompt` path inserts the configured system prompt as a `schema.User` message at the beginning of `in`.

## Integration with the Event Bus

Agent invocations are triggered by the `AgentProcessor` event subscriber in `internal/event/subscriber/`. When an event that requires AI processing fires — for example a request to generate a summary of recent posts — the `AgentProcessor` builds the message list, calls `agent.Generate`, and persists or delivers the result. The agent is never called synchronously in the HTTP handler path; all LLM calls happen asynchronously on the event bus consumer goroutine.

The event bus `AgentBuffer` (default 128) and `AgentParallelism` (default 2) settings control how many concurrent `Generate` calls the subscriber allows. The parallelism is enforced by the subscriber's own worker pool, separate from the webhook worker pool.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/agent/info` | Returns agent status without sensitive fields |
| `GET` | `/api/agent/settings` | Returns full settings (admin only) |
| `PUT` | `/api/agent/settings` | Update agent configuration |
| `GET` | `/api/agent/recent` | Generate a summary of recent posts |

The `GET /api/agent/recent` endpoint is the primary user-facing feature. It calls `agentService.GenerateRecent`, which fetches recent posts from the echo service, formats them into a message list, and calls `agent.Generate` with `usePrompt: true`. The response is the generated text, returned inside the standard `Result[string]` envelope.

## Error Handling

`Generate` returns typed errors with message constants from `commonModel`:

| Condition | Error |
|---|---|
| Agent disabled | `AGENT_NOT_ENABLED` |
| Missing model | `AGENT_MODEL_MISSING` |
| Unknown provider | `AGENT_PROVIDER_NOT_FOUND` |
| Missing API key | `AGENT_API_KEY_MISSING` |

Provider-level errors (network failures, authentication errors, rate limits) are returned directly from the Eino SDK as Go errors and propagate up to the handler, which returns them in the standard failure envelope.

## Adding a New Provider

To add support for a new LLM provider:

1. Add a provider constant to `commonModel` (e.g., `const MyProvider = "myprovider"`).
2. Add a case to the `switch` in `agent.Generate` that constructs the provider's chat model and calls `Generate`.
3. Add the provider's SDK as a dependency in `go.mod`.
4. Add the provider name to the frontend provider selector in the agent settings UI.
