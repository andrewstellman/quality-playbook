An implemented function throws the core `$ZodError`, not the classic `ZodError`, so `instanceof z.ZodError` checks miss it and `.flatten()` / `.format()` aren't there:

```ts
import * as z from "zod";

const f = z.function({ input: [z.string()], output: z.number() }).implement((s) => s.length);
try {
  f(1 as any);
} catch (e) {
  e instanceof z.ZodError; // false
  e.constructor.name;      // "$ZodError"
  typeof e.flatten;        // "undefined"
}
```

`implementAsync` behaves the same way. `schema.parse` throws `ZodError`, and the docs say an implemented function "will throw a `ZodError` if the input is invalid". Core's `implement` / `implementAsync` validate with the core `parse` / `parseAsync`, which are bound to `$ZodRealError`, and the classic `ZodFunction` doesn't swap in the classic parsers.

Reproduced on `main` at 2bf7b06. One way to fix it is on a branch since PRs are limited to collaborators: __COMPARE__. It overrides `implement` / `implementAsync` in the classic `ZodFunction` to use the classic parsers; that copies the two core method bodies, so you may prefer a hook in core instead. Zod Mini is unchanged.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
