`add()` lets a later schema take over an id (#5574, pinned by the "re-registering same id silently overwrites" test), but `remove()` deletes `_idmap[id]` for any schema whose metadata carries that id, including one that no longer owns it:

```ts
import * as z from "zod";

const r = z.registry<{ id?: string }>();
const a = z.string();
const b = z.number();
r.add(a, { id: "x" });
r.add(b, { id: "x" });
r.remove(a);

r.has(b);          // true
z.toJSONSchema(r); // { schemas: {} }   expected { schemas: { x: { type: "number" } } }
```

Reproduced on `main` at 2bf7b06. The fix is a one-line guard in `remove()` (only delete the id entry when it still points at the schema being removed), with a test, on a branch since PRs are limited to collaborators: __COMPARE__.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
