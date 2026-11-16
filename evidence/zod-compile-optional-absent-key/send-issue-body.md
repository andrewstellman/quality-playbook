With `zod/compile` loaded, `z.object({ a: z.success(z.string().optional()) }).safeParse({})` succeeds, and so does the same object with `a: z.intersection(z.string().optional(), z.string().optional())`, while the runtime parser rejects `{}` for both with a `nonoptional` issue. `z.validate(schema, {})` also returns `true` for the compiled schema. Neither wrapper declares `optin`, so the runtime requires the key. `fastPathAcceptsAbsence` in `compile.ts` answers a non-exact optional by asking its inner schema (here `z.string()`, which doesn't accept absence), but the generated code for that optional accepts `undefined` whatever the inner is, so the compiled object emits no presence guard for `a`.

A fix with a test is on <fork-branch-url>.

Found with the Quality Playbook, an AI code-review tool I maintain. The fix and test were written with AI assistance and reviewed by me.
