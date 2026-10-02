import * as z from "/tmp/zodw/packages/zod/src/index.js";

const partI = z.string().regex(/^abc$/i);
const tplI = z.templateLiteral([partI]);
const partU = z.string().regex(/^\p{Lu}+$/u);
const tplU = z.templateLiteral([partU]);

const rows = [
  ["i-part alone, 'ABC'", partI.safeParse("ABC").success, true],
  ["i-template, 'ABC'", tplI.safeParse("ABC").success, true],
  ["u-part alone, 'p{Lu}'", partU.safeParse("p{Lu}").success, false],
  ["u-template, 'p{Lu}'", tplU.safeParse("p{Lu}").success, false],
  ["u-part alone, 'É'", partU.safeParse("É").success, true],
  ["u-template, 'É'", tplU.safeParse("É").success, true],
] as const;

let bug = false;
for (const [label, actual, expected] of rows) {
  console.log(`${label}: actual=${actual} expected=${expected}${actual !== expected ? "  <-- MISMATCH" : ""}`);
  if (actual !== expected) bug = true;
}
console.log("template regex (i):", (tplI as any)._zod.pattern);
console.log("template regex (u):", (tplU as any)._zod.pattern);
process.exit(bug ? 1 : 0);
