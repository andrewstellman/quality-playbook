**Title:** fix(intersection): merge identical NaN outputs instead of throwing

`mergeValues` decides two values are the same with `a === b`, which is false for NaN. When both sides of an intersection produce NaN, the merge is classed as unmergable and `safeParse` throws `Unmergable intersection`:

```ts
z.nan().and(z.nan()).safeParse(NaN);
z.unknown().and(z.unknown()).safeParse(NaN);
z.looseObject({ a: z.string() }).and(z.looseObject({ b: z.string() })).safeParse({ a: "x", b: "y", c: NaN });
```

The changelog reserves that throw for "an intersection of two incompatible types". Two NaNs from the same input are not incompatible, and `z.nan().and(z.nan())` currently cannot accept any value. The check now also accepts NaN on both sides. `0` and `-0` still merge as before.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
