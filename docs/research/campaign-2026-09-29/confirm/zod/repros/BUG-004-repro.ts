import * as z from "/tmp/zodw/packages/zod/src/index.js";

const r1 = z.record(z.literal("a"), z.any()).safeParse({});
const r2 = z.record(z.enum(["a", "b"]), z.unknown()).safeParse({ a: 1 });
const r3 = z.record(z.enum(["a", "b"]), z.string()).safeParse({ a: "x" }); // control: non-undefined value schema
const o1 = z.object({ a: z.any() }).safeParse({}); // sibling comparison
const js = z.toJSONSchema(z.record(z.enum(["a", "b"]), z.unknown()));

console.log("record(literal a, any).safeParse({}):", JSON.stringify(r1));
console.log("record(enum[a,b], unknown).safeParse({a:1}):", JSON.stringify(r2));
console.log("record(enum[a,b], string).safeParse({a:'x'}):", JSON.stringify(r3, null, 0));
console.log("object({a: any}).safeParse({}):", JSON.stringify(o1));
console.log("toJSONSchema(record(enum[a,b], unknown)).required:", JSON.stringify((js as any).required));

const bug = r1.success || r2.success;
console.log(bug ? "BUG PRESENT" : "BUG ABSENT");
process.exit(bug ? 1 : 0);
