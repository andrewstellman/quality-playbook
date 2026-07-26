# Tool use with Claude - Claude API Docs

*Source: https://docs.claude.com/en/docs/agents-and-tools/tool-use/overview*
*Fetched: 2026-04-27*
*Tier: 1 (citable)*

---

Tools
# Tool use with Claude
Copy pageConnect Claude to external tools and APIs. Learn where tools execute and how the agentic loop works.Copy page

Tool use lets Claude call functions you define or that Anthropic provides. Claude decides when to call a tool based on the user's request and the tool's description, then returns a structured call that your application executes (client tools) or that Anthropic executes (server tools).

Here's the simplest example using a server tool, where Anthropic handles execution:
cURLCLIPythonTypeScript

```
import anthropic

client = anthropic.Anthropic()
response = client.messages.create(
 model="claude-opus-4-7",
 max_tokens=1024,
 tools=[{"type": "web_search_20260209", "name": "web_search"}],
 messages=[{"role": "user", "content": "What's the latest on the Mars rover?"}],
)
print(response.content)
```

## How tool use works

Tools differ primarily by where the code executes. **Client tools** (including user-defined tools and Anthropic-schema tools like bash and text_editor) run in your application: Claude responds with `stop_reason: "tool_use"` and one or more `tool_use` blocks, your code executes the operation, and you send back a `tool_result`. **Server tools** (web_search, code_execution, web_fetch, tool_search) run on Anthropic's infrastructure: you see the results directly without handling execution.

For the full conceptual model including the agentic loop and when to choose each approach, see [How tool use works](/docs/en/agents-and-tools/tool-use/how-tool-use-works).

For connecting to MCP servers, see the [MCP connector](/docs/en/agents-and-tools/mcp-connector). For building your own MCP client, see [modelcontextprotocol.io](https://modelcontextprotocol.io/docs/develop/build-client).

**Guarantee schema conformance with strict tool use**

Add `strict: true` to your tool definitions to ensure Claude's tool calls always match your schema exactly. See [Strict tool use](/docs/en/agents-and-tools/tool-use/strict-tool-use).

Tool access is one of the highest-leverage primitives you can give an agent. On benchmarks like [LAB-Bench FigQA](https://lab-bench.org/) (scientific figure interpretation) and [SWE-bench](https://www.swebench.com/) (real-world software engineering), adding even basic tools produces outsized capability gains, often surpassing human expert baselines.

## Tool use examples

For a complete hands-on walkthrough, see the [tutorial](/docs/en/agents-and-tools/tool-use/build-a-tool-using-agent). For reference examples of individual concepts, see [Define tools](/docs/en/agents-and-tools/tool-use/define-tools) and [Handle tool calls](/docs/en/agents-and-tools/tool-use/handle-tool-calls).

### What happens when Claude needs more information

## Pricing

Tool use requests are priced based on:

1. The total number of input tokens sent to the model (including in the `tools` parameter)

2. The number of output tokens generated

3. For server-side tools, additional usage-based pricing (e.g., web search charges per search performed)

Client-side tools are priced the same as any other Claude API request, while server-side tools may incur additional charges based on their specific usage.

The additional tokens from tool use come from:

- The `tools` parameter in API requests (tool names, descriptions, and schemas)

- `tool_use` content blocks in API requests and responses

- `tool_result` content blocks in API requests

When you use `tools`, we also automatically include a special system prompt for the model which enables tool use. The number of tool use tokens required for each model are listed below (excluding the additional tokens listed above). Note that the table assumes at least 1 tool is provided. If no `tools` are provided, then a tool choice of `none` uses 0 additional system prompt tokens.
ModelTool choiceTool use system prompt token countClaude Opus 4.7`auto`, `none``any`, `tool`346 tokens313 tokensClaude Opus 4.6`auto`, `none``any`, `tool`346 tokens313 tokensClaude Opus 4.5`auto`, `none``any`, `tool`346 tokens313 tokensClaude Opus 4.1`auto`, `none``any`, `tool`346 tokens313 tokensClaude Opus 4`auto`, `none``any`, `tool`346 tokens313 tokensClaude Sonnet 4.6`auto`, `none``any`, `tool`346 tokens313 tokensClaude Sonnet 4.5`auto`, `none``any`, `tool`346 tokens313 tokensClaude Sonnet 4`auto`, `none``any`, `tool`346 tokens313 tokensClaude Sonnet 3.7 ([deprecated](/docs/en/about-claude/model-deprecations))`auto`, `none``any`, `tool`346 tokens313 tokensClaude Haiku 4.5`auto`, `none``any`, `tool`346 tokens313 tokensClaude Haiku 3.5`auto`, `none``any`, `tool`264 tokens340 tokensClaude Opus 3 ([deprecated](/docs/en/about-claude/model-deprecations))`auto`, `none``any`, `tool`530 tokens281 tokensClaude Sonnet 3`auto`, `none``any`, `tool`159 tokens235 tokensClaude Haiku 3`auto`, `none``any`, `tool`264 tokens340 tokens

These token counts are added to your normal input and output tokens to calculate the total cost of a request.

Refer to the [models overview table](/docs/en/about-claude/models/overview#latest-models-comparison) for current per-model prices.

When you send a tool use prompt, just like any other API request, the response will output both input and output token counts as part of the reported `usage` metrics.

## Next steps

### Choose your path

[Understand the concepts

Where tools run, how the loop works, and when to use tools.](/docs/en/agents-and-tools/tool-use/how-tool-use-works)[Build step by step

The tutorial: from a single tool call to production.](/docs/en/agents-and-tools/tool-use/build-a-tool-using-agent)[Browse all tools

Directory of Anthropic-provided tools and properties.](/docs/en/agents-and-tools/tool-use/tool-reference)

Was this page helpful?
