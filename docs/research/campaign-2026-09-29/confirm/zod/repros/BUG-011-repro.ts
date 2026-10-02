import * as z from "/tmp/zodw/packages/zod/src/index.js";

// Doc (json-schema.mdx:453-460) claims:
//   z.float32() => { type:"number", exclusiveMinimum, exclusiveMaximum }
//   z.float64() => same;  z.int() => { type:"integer" };  z.int32() => integer + exclusive bounds
const out = {
  float32: z.toJSONSchema(z.float32()),
  float64: z.toJSONSchema(z.float64()),
  int: z.toJSONSchema(z.int()),
  int32: z.toJSONSchema(z.int32()),
};
for (const [k, v] of Object.entries(out)) console.log(k, JSON.stringify(v));

// Are the runtime bounds inclusive (i.e. is the emitter right and the doc wrong)?
const edge = {
  float32_max_inclusive: z.float32().safeParse(3.4028234663852886e38).success,
  int32_max_inclusive: z.int32().safeParse(2147483647).success,
  int_max_inclusive: z.int().safeParse(Number.MAX_SAFE_INTEGER).success,
  int_beyond_safe_rejected: !z.int().safeParse(Number.MAX_SAFE_INTEGER + 2).success,
};
console.log("runtime:", JSON.stringify(edge));

const docMatches =
  "exclusiveMinimum" in out.float32 && "exclusiveMinimum" in out.float64 &&
  "exclusiveMinimum" in out.int32 && !("minimum" in out.int);
console.log(docMatches ? "DOC MATCHES CODE (no bug)" : "DOC DOES NOT MATCH CODE (bug present)");
process.exit(docMatches ? 0 : 1);
