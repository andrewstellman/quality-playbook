**Title:** fix(registry): only unmap an id when the removed schema still owns it

`add()` lets a later schema take over an id (#5574, pinned by "re-registering same id silently overwrites"), but `remove()` deletes `_idmap[id]` for any schema whose metadata carries that id, including one that no longer owns it:

```ts
const r = z.registry<{ id?: string }>();
const a = z.string();
const b = z.number();
r.add(a, { id: "x" });
r.add(b, { id: "x" });
r.remove(a);
r.has(b);          // true
z.toJSONSchema(r); // { schemas: {} }, expected { schemas: { x: { type: "number" } } }
```

`remove()` now deletes the entry only when it still points at the schema being removed.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
