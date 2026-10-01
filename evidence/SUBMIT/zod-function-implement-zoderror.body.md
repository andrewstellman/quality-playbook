An implemented function throws the core `$ZodError`, not the classic `ZodError`:

```ts
const f = z.function({ input: [z.string()], output: z.number() }).implement((s) => s.length);
try { f(1 as any); } catch (e) {
  e instanceof z.ZodError; // false
  typeof e.flatten;        // "undefined"
}
```

`schema.parse` throws `ZodError`, and the docs say an implemented function "will throw a `ZodError` if the input is invalid". Core's `implement`/`implementAsync` validate with the core parsers, which are bound to `$ZodError`; the classic `ZodFunction` never substituted the classic ones. It now overrides both methods to use the classic `parse`/`parseAsync`, the same way `ZodType.parse` does. Zod Mini is unchanged and still throws `$ZodError`.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
