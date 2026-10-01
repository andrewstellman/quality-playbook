**Title:** fix(router): throw E_CANNOT_LOOKUP_ROUTE from findOrFail

```ts
router.get('/users/:id', () => {}).as('users.show')
router.commit()
router.findOrFail('posts.show')
// actual:   Error: Cannot lookup route "posts.show"  (no code, status, not instanceof)
// expected: E_CANNOT_LOOKUP_ROUTE, code 'E_CANNOT_LOOKUP_ROUTE', status 500
```

`E_CANNOT_LOOKUP_ROUTE` is defined in `src/errors.ts` and listed in the exception handler's `ignoreExceptions`, but `Router.findOrFail` (`src/router/main.ts`) throws `new Error(...)`, so nothing raises it. The docs describe it as "raised when you attempt to create a URL for a route using the URL builder", and core 6.x stack traces show `findOrFail` throwing it.

`findOrFail` now throws `E_CANNOT_LOOKUP_ROUTE`, with the same messages as before (including the "for method" variant). This also covers `makeUrl`, the legacy builder and `signedUrlFor`, which go through `findOrFail`.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
