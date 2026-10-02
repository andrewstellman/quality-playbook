import * as z from "/tmp/zodw/packages/zod/src/index.js";

const A = z.object({ a: z.intersection(z.string().optional(), z.string().optional()) });
const B = z.object({ a: z.success(z.string().optional()) });

const rA = A.safeParse({});
const cA = z.compile(A).safeParse({});
const rB = B.safeParse({});
const cB = z.compile(B).safeParse({});
const vB = z.validate(z.compile(B), {});

console.log("A runtime :", rA.success, rA.success ? "" : JSON.stringify(rA.error.issues));
console.log("A compiled:", cA.success, JSON.stringify(cA.success ? cA.data : cA.error.issues));
console.log("B runtime :", rB.success, rB.success ? "" : JSON.stringify(rB.error.issues));
console.log("B compiled:", cB.success, JSON.stringify(cB.success ? cB.data : cB.error.issues));
console.log("B validate(compiled, {}):", vB);

const bug = rA.success !== cA.success || rB.success !== cB.success;
console.log(bug ? "BUG PRESENT: compiled and runtime disagree" : "no bug");
process.exit(bug ? 1 : 0);
