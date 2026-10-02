import * as z from "/tmp/zodw/packages/zod/src/index.js";

const cases: [string, RegExp, string][] = [
  ["i flag", /^abc$/i, "ABC"],
  ["s flag", /^a.c$/s, "a\nc"],
  ["m flag", /^b$/m, "a\nb\nc"],
];
let bug = false;
for (const [name, re, input] of cases) {
  const schema = z.string().regex(re);
  const json = z.toJSONSchema(schema, { io: "input" }) as any;
  const zodAccepts = schema.safeParse(input).success;
  // JSON Schema "pattern" is ECMA-262 with no flags: evaluate as a bare RegExp
  const jsonAccepts = new RegExp(json.pattern).test(input);
  console.log(name, { emitted: json.pattern, zodAccepts, jsonAccepts });
  if (zodAccepts && !jsonAccepts) bug = true;
}
process.exit(bug ? 1 : 0);
