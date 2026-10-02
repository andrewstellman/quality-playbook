import * as z from "/tmp/zodw/packages/zod/src/index.js";

const r1 = z.fromJSONSchema({ const: { a: 1 } } as any).safeParse({ a: 1 });
const r2 = z.fromJSONSchema({ enum: [[1, 2], "x"] } as any).safeParse([1, 2]);
const r3 = z.fromJSONSchema({ enum: [[1, 2], "x"] } as any).safeParse("x");
const r4 = z.fromJSONSchema({ enum: [{ a: 1 }] } as any).safeParse({ a: 1 });

console.log("const {a:1} vs {a:1}   ->", r1.success, r1.success ? "" : JSON.stringify(r1.error.issues));
console.log("enum [[1,2],'x'] vs [1,2] ->", r2.success, r2.success ? "" : JSON.stringify(r2.error.issues));
console.log("enum [[1,2],'x'] vs 'x'   ->", r3.success);
console.log("enum [{a:1}] vs {a:1}     ->", r4.success);

const bug = !r1.success || !r2.success || !r4.success;
console.log(bug ? "BUG PRESENT" : "BUG ABSENT");
process.exit(bug ? 1 : 0);
