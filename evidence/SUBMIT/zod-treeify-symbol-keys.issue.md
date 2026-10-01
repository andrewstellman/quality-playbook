For an object with a symbol key, `z.treeifyError()` puts the issue on an array under `items`:

```ts
import * as z from "zod";

const k = Symbol("k");
const r = z.object({ [k]: z.string() }).safeParse({ [k]: 1 });
const tree = z.treeifyError(r.error!);
tree.properties; // undefined
tree.items;      // [ [Symbol(k)]: { errors: ["Invalid input: expected string, received number"] } ]
```

`treeifyError` branches on `typeof el === "string"` and sends every other segment to `items`. `$ZodErrorTree` declares `properties` over `keyof T`, which includes symbol keys, and `flattenError` and `formatError` both file the same issue under the symbol.

Reproduced on `main` at 2bf7b06. The fix is one token (`typeof el !== "number"` in place of `typeof el === "string"`), with a test, on a branch since PRs are limited to collaborators: __COMPARE__.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
