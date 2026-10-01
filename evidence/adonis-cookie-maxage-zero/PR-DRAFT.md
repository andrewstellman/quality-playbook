**Title:** fix(cookies): serialize maxAge of zero as Max-Age=0

## Problem
`serializeCookie` checks `options.maxAge` for truthiness, so `maxAge: 0` emits no `Max-Age` attribute and the cookie becomes a session cookie instead of expiring:

```ts
response.plainCookie('k', 'v', { maxAge: 0 })
// Set-Cookie: k=...; Path=/; HttpOnly   (expected Max-Age=0)
```

## Fix
Treat `0` as a value; `undefined`, `null` and `''` behave as before.

One behaviour change to be aware of: an app whose config sets `cookie: { maxAge: 0 }` currently gets session cookies, and after this gets `Max-Age=0` on every cookie that doesn't set its own `maxAge`.

## Testing
- npm run quick:test (661 passed)
- npm run typecheck
- npx eslint and prettier --check on the changed files

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
