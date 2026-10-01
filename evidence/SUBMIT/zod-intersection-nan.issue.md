`mergeValues` decides two outputs are the same with `a === b`, which is false for NaN. When both sides of an intersection produce NaN, the merge is classed as unmergable and `safeParse` throws instead of returning a result:

```ts
import * as z from "zod";

z.nan().and(z.nan()).safeParse(NaN);          // throws: Unmergable intersection. Error path: []
z.unknown().and(z.unknown()).safeParse(NaN);  // throws
z.looseObject({ a: z.string() })
  .and(z.looseObject({ b: z.string() }))
  .safeParse({ a: "x", b: "y", c: NaN });     // throws, path ["c"]
```

The changelog reserves that throw for "an intersection of two incompatible types". Two NaNs from the same input aren't incompatible, and `z.nan().and(z.nan())` currently can't accept any value. The compiled path reuses `mergeValues`, so it throws too.

Reproduced on `main` at 2bf7b06. A one-line fix, `a === b || (Number.isNaN(a) && Number.isNaN(b))`, with a test, is on a branch since PRs are limited to collaborators: __COMPARE__. `0` and `-0` still merge as before (`Object.is` would have split them).

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
