**Title:** fix(redirect): keep toRoute qs option intact across redirects

## Problem
`Redirect.toRoute` passes `options.qs` to `withQs()` and then sets `options.qs = undefined` on the caller's object. A brisk redirect route reuses that object on every request, so only the first request keeps the query string:

```ts
router.on('/old').redirect('new', {}, { qs: { a: 1 } })
// 1st GET /old -> /new?a=1, every later GET /old -> /new
```

## Fix
`toRoute` no longer mutates the options it is given.

## Testing
- npm run quick:test (661 passed)
- npm run typecheck
- npx eslint and prettier --check on the changed files

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
