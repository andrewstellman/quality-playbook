**Title:** fix(response): do not send content with a 205 response

```ts
response.status(205).send('hello world')
// actual:   205, content-length: 11, content-type: text/plain, body "hello world"
// expected: 205, content-length: 0, no content-type, no body
```

`writeBody` in `src/response.ts` drops content only for 1xx, 204 and 304, so a 205 goes through the normal body path. The fix ends 205 responses with `Content-Length: 0` and no `Content-Type`; plain header stripping isn't enough because Node doesn't treat 205 as body-less, and it would leave a keep-alive response unframed. `resetContent()` now takes the same path. It previously sent `Transfer-Encoding: chunked` with an empty chunk.

RFC 9110 §15.3.6: "Since the 205 status code implies that no additional content will be provided, a server MUST NOT generate content in a 205 response."

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
