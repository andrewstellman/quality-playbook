`z.record(z.literal("a"), z.any()).safeParse({})` succeeds, and so does `z.record(z.enum(["a", "b"]), z.unknown()).safeParse({ a: 1 })`, while `z.object({ a: z.any() }).safeParse({})` fails. The docs say Zod "will exhaustively check that all enum values exist in the input as keys", and that a value schema that can stand in for an absent key (`.default()`, `.prefault()`, `.optional()`) makes the key optional, "the same as it does inside `z.object()`". `z.input` types the key as required and `z.toJSONSchema()` lists it in `required`. The exhaustive branch of `$ZodRecord` runs the value schema on `input[key]` without checking that the key is present, and the compiled record has the same gap.

A fix with a test is on <fork-branch-url>.

Found with the Quality Playbook, an AI code-review tool I maintain. The fix and test were written with AI assistance and reviewed by me.
