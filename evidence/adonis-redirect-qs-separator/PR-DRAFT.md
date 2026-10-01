**Title:** fix(redirect): append query string with & when url already has one

```ts
response.redirect().withQs('age', 28).toPath('/foo?username=virk')
// Location: /foo?username=virk?age=28   (actual)
// Location: /foo?username=virk&age=28   (expected)
```

`Redirect#sendResponse` (src/redirect.ts) always joined the stringified query with `?`, without checking whether the target url already had a query string. The same happens with `withQs()` forwarding the current request's query onto such a target.

The fix uses `&` as the separator when the url already contains `?`, leaving the target's existing query text untouched. The docs say `withQs` is used "to append a query string to the redirect URL".

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
