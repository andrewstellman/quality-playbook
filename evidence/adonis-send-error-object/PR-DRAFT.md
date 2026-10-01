**Title:** fix(response): serialize error objects as plain text

```ts
response.send(new Error('boom'))
// actual:   200 application/json  body: {}
// expected: 200 text/plain        body: Error: boom
```

`writeBody` in `src/response.ts` special-cases `RegExp` and `Date`, but an `Error` falls through to `serializeJSON`, and because its `message`/`stack` are non-enumerable the body is `{}`. This handles `Error` in the same branch as `RegExp` (`String(content)` + `text/plain`).

The response docs say: "Regular expressions and error objects are converted to a string by calling the toString method."

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
