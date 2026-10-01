A constant `.catch()` value is returned by reference, so mutating one fallback result changes every later one:

```ts
import * as z from "zod";

const arr = z.array(z.string()).catch([]);
arr.parse(1).push("leak");
arr.parse(1); // ["leak"]

const m = z.map(z.string(), z.number()).catch(new Map());
m.parse(1).set("k", 1);
m.parse(1).size; // 1
```

The `z.compile` path does the same, since it calls the same thunk. `.default()` already shallow-clones its value on every read (#5173 for arrays, #5855 for Map and Set); `.catch()` never got the same treatment.

Reproduced on `main` at 2bf7b06. A one-line fix (`constantCatch`'s thunk returns `shallowClone(value)`, keeping the `CONSTANT_CATCH` tag), with a test, is on a branch since PRs are limited to collaborators: __COMPARE__. It means a plain object or array passed to `.catch()` is no longer returned by identity, matching `.default()`; `.catch(() => value)` is unchanged.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
