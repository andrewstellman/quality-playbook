**Title:** fix: file symbol path keys under properties in treeifyError

For an object with a symbol key, `z.treeifyError()` puts the issue on an array:

```ts
const k = Symbol("k");
const r = z.object({ [k]: z.string() }).safeParse({ [k]: 1 });
const tree = z.treeifyError(r.error!);
tree.properties; // undefined
tree.items;      // [ [Symbol(k)]: { errors: [...] } ]
```

`treeifyError` branches on `typeof el === "string"` and sends everything else to `items`. `$ZodErrorTree` declares `properties` over `keyof T`, which includes symbol keys, and `flattenError` and `formatError` both file the same issue under the symbol. Now only number segments go to `items`.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
