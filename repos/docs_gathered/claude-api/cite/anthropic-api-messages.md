# Messages API - Claude API Reference

*Source: https://docs.claude.com/en/api/messages (canonical reference) + https://docs.claude.com/en/build-with-claude/working-with-messages (practical patterns)*
*Fetched: 2026-04-27*
*Tier: 1 (citable)*

---

> Note: The reference endpoint page at /en/api/messages renders its parameter table via JavaScript and the static HTML is sparse.
> This file pairs the reference URL with the build-with-claude/working-with-messages guide, which provides full prose coverage of
> request/response shape, multi-turn conversations, prefill, vision input, and other Messages API patterns.

---

Building with Claude
# Using the Messages API
Copy pagePractical patterns and examples for using the Messages API effectivelyCopy page

Anthropic offers two ways to build with Claude, each suited to different use cases:
Messages APIClaude Managed Agents**What it is**Direct model prompting accessPre-built, configurable agent harness that runs in managed infrastructure**Best for**Custom agent loops and fine-grained controlLong-running tasks and asynchronous work**Learn more**[Messages API docs](/docs/en/build-with-claude/working-with-messages)[Claude Managed Agents docs](/docs/en/managed-agents/overview)

This guide covers common patterns for working with the Messages API, including basic requests, multi-turn conversations, prefill techniques, and vision capabilities. For complete API specifications, see the [Messages API reference](/docs/en/api/messages/create).

This feature is eligible for [Zero Data Retention (ZDR)](/docs/en/build-with-claude/api-and-data-retention). When your organization has a ZDR arrangement, data sent through this feature is not stored after the API response is returned.

## Basic request and response

cURLCLIPythonTypeScriptC#GoJavaPHPRuby

```
message = anthropic.Anthropic().messages.create(
 model="claude-opus-4-7",
 max_tokens=1024,
 messages=[{"role": "user", "content": "Hello, Claude"}],
)
print(message)
```

Output

```
{
 "id": "msg_01XFDUDYJgAACzvnptvVoYEL",
 "type": "message",
 "role": "assistant",
 "content": [
 {
 "type": "text",
 "text": "Hello!"
 }
 ],
 "model": "claude-opus-4-7",
 "stop_reason": "end_turn",
 "stop_sequence": null,
 "usage": {
 "input_tokens": 12,
 "output_tokens": 6
 }
}
```

## Multiple conversational turns

The Messages API is stateless, which means that you always send the full conversational history to the API. You can use this pattern to build up a conversation over time. Earlier conversational turns don't necessarily need to actually originate from Claude. You can use synthetic `assistant` messages.
cURLCLIPythonTypeScriptC#GoJavaPHPRuby

```
message = anthropic.Anthropic().messages.create(
 model="claude-opus-4-7",
 max_tokens=1024,
 messages=[
 {"role": "user", "content": "Hello, Claude"},
 {"role": "assistant", "content": "Hello!"},
 {"role": "user", "content": "Can you describe LLMs to me?"},
 ],
)
print(message)
```

Output

```
{
 "id": "msg_018gCsTGsXkYJVqYPxTgDHBU",
 "type": "message",
 "role": "assistant",
 "content": [
 {
 "type": "text",
 "text": "Sure, I'd be happy to provide..."
 }
 ],
 "stop_reason": "end_turn",
 "stop_sequence": null,
 "usage": {
 "input_tokens": 30,
 "output_tokens": 309
 }
}
```

## Putting words in Claude's mouth

You can pre-fill part of Claude's response in the last position of the input messages list. This can be used to shape Claude's response. The example below uses `"max_tokens": 1` to get a single multiple choice answer from Claude.
cURLCLIPythonTypeScriptC#GoJavaPHPRuby

```
message = anthropic.Anthropic().messages.create(
 model="claude-sonnet-4-5",
 max_tokens=1,
 messages=[
 {
 "role": "user",
 "content": "What is latin for Ant? (A) Apoidea, (B) Rhopalocera, (C) Formicidae",
 },
 {"role": "assistant", "content": "The answer is ("},
 ],
)
print(message)
```

Output

```
{
 "id": "msg_01Q8Faay6S7QPTvEUUQARt7h",
 "type": "message",
 "role": "assistant",
 "content": [
 {
 "type": "text",
 "text": "C"
 }
 ],
 "model": "claude-sonnet-4-5",
 "stop_reason": "max_tokens",
 "stop_sequence": null,
 "usage": {
 "input_tokens": 42,
 "output_tokens": 1
 }
}
```

Prefilling is not supported on [Claude Mythos Preview](https://anthropic.com/glasswing), Claude Opus 4.7, Claude Opus 4.6, and Claude Sonnet 4.6. Requests using prefill with these models return a 400 error. Use [structured outputs](/docs/en/build-with-claude/structured-outputs) or system prompt instructions instead. See the [migration guide](/docs/en/about-claude/models/migration-guide) for migration patterns.

## Vision

Claude can read both text and images in requests. Images can be supplied using the `base64`, `url`, or `file` source types. The `file` source type references an image uploaded through the [Files API](/docs/en/build-with-claude/files). Supported media types are `image/jpeg`, `image/png`, `image/gif`, and `image/webp`. See the [vision guide](/docs/en/build-with-claude/vision) for more details.
cURLCLIPythonTypeScriptC#GoJavaPHPRuby

```
import base64
import httpx

# Option 1: Base64-encoded image
image_url = "https://upload.wikimedia.org/wikipedia/commons/a/a7/Camponotus_flavomarginatus_ant.jpg"
image_media_type = "image/jpeg"
image_data = base64.standard_b64encode(httpx.get(image_url).content).decode("utf-8")

message = anthropic.Anthropic().messages.create(
 model="claude-opus-4-7",
 max_tokens=1024,
 messages=[
 {
 "role": "user",
 "content": [
 {
 "type": "image",
 "source": {
 "type": "base64",
 "media_type": image_media_type,
 "data": image_data,
 },
 },
 {"type": "text", "text": "What is in the above image?"},
 ],
 }
 ],
)
print(message)

# Option 2: URL-referenced image
message_from_url = anthropic.Anthropic().messages.create(
 model="claude-opus-4-7",
 max_tokens=1024,
 messages=[
 {
 "role": "user",
 "content": [
 {
 "type": "image",
 "source": {
 "type": "url",
 "url": "https://upload.wikimedia.org/wikipedia/commons/a/a7/Camponotus_flavomarginatus_ant.jpg",
 },
 },
 {"type": "text", "text": "What is in the above image?"},
 ],
 }
 ],
)
print(message_from_url)
```

Output

```
{
 "id": "msg_01EcyWo6m4hyW8KHs2y2pei5",
 "type": "message",
 "role": "assistant",
 "content": [
 {
 "type": "text",
 "text": "This image shows an ant, specifically a close-up view of an ant. The ant is shown in detail, with its distinct head, antennae, and legs clearly visible. The image is focused on capturing the intricate details and features of the ant, likely taken with a macro lens to get an extreme close-up perspective."
 }
 ],
 "model": "claude-opus-4-7",
 "stop_reason": "end_turn",
 "stop_sequence": null,
 "usage": {
 "input_tokens": 1551,
 "output_tokens": 71
 }
}
```

## Tool use and computer use

See the [tool use guide](/docs/en/agents-and-tools/tool-use/overview) for examples of how to use tools with the Messages API.
See the [computer use guide](/docs/en/agents-and-tools/tool-use/computer-use-tool) for examples of how to control desktop computer environments with the Messages API.
For guaranteed JSON output, see [Structured Outputs](/docs/en/build-with-claude/structured-outputs).

Was this page helpful?
