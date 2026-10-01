`z.array(z.string()).catch([])` returns the same array on every failed parse, so `arr.parse(1).push("leak")` changes what the next `arr.parse(1)` returns. A `.catch(new Map())` fallback does the same, and so does the `z.compile` path, since it calls the same thunk.

`.default()` already shallow-clones its value on every read (#5173 for arrays, #5855 for Map and Set). `constantCatch` now does the same. A plain object or array passed to `.catch()` is therefore no longer returned by identity, matching `.default()`; `.catch(() => value)` is unchanged and still returns whatever the callback returns.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
