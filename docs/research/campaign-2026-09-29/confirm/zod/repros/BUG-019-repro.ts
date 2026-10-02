import * as z from "/tmp/zodw/packages/zod/src/index.js";

const schema = z.fromJSONSchema({
  allOf: [
    { type: "object", properties: { a: { type: "number" } }, additionalProperties: false },
    { type: "object", properties: { b: { type: "number" } } },
  ],
} as any);

const input = { a: 1, b: 1 };
const r = schema.safeParse(input);
console.log("input:", JSON.stringify(input));
console.log("success:", r.success);
if (!r.success) console.log("issues:", JSON.stringify(r.error.issues));

// control: the closed branch alone must reject b
const closed = z.fromJSONSchema({ type: "object", properties: { a: { type: "number" } }, additionalProperties: false } as any);
console.log("closed branch alone success:", closed.safeParse(input).success);

process.exit(r.success ? 1 : 0);
