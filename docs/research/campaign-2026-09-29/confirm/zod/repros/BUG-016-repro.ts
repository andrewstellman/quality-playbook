import * as z from "/tmp/zodw/packages/zod/src/index.js";
const s = z.fromJSONSchema({ type: "string", pattern: "^\\p{L}+$" } as any);
const a = s.safeParse("p{L}").success;
const b = s.safeParse("é").success;
console.log("pattern ^\\p{L}+$  ->  'p{L}' accepted:", a, " 'é' accepted:", b);
// reference: what Unicode-mode ECMA-262 does
console.log("reference /^\\p{L}+$/u  ->  'p{L}':", /^\p{L}+$/u.test("p{L}"), " 'é':", /^\p{L}+$/u.test("é"));
// patternProperties path
const o = z.fromJSONSchema({ type: "object", patternProperties: { "^\\p{L}+$": { type: "number" } }, additionalProperties: false } as any);
console.log("patternProperties: key 'é' accepted:", o.safeParse({ "é": 1 }).success, " key 'p{L}' accepted:", o.safeParse({ "p{L}": 1 }).success);
const bug = a === true && b === false;
console.log(bug ? "BUG PRESENT" : "BUG ABSENT");
process.exit(bug ? 1 : 0);
