import * as z from "/tmp/zodw/packages/zod/src/index.js";

const s = z.fromJSONSchema({ properties: { a: { type: "number" } }, required: ["a"] } as any);
const r1 = s.safeParse({});          // expected: fail (required a)
const r2 = s.safeParse({ a: "x" });  // expected: fail (a not number)
const r3 = s.safeParse("str");       // expected: pass (non-object)
const r4 = s.safeParse({ a: 1 });    // expected: pass
console.log("constructor:", s.constructor.name);
console.log("{}        ->", r1.success);
console.log("{a:'x'}   ->", r2.success);
console.log("'str'     ->", r3.success);
console.log("{a:1}     ->", r4.success);

const s2 = z.fromJSONSchema({ minLength: 3 } as any);
console.log("minLength:3 on 'ab' ->", s2.safeParse("ab").success);

const bug = r1.success || r2.success || s2.safeParse("ab").success;
console.log(bug ? "BUG PRESENT" : "BUG ABSENT");
process.exit(bug ? 1 : 0);
